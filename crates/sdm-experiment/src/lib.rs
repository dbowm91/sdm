//! Reproducible, frozen-split Rank experiments. Training and calibration APIs
//! receive only their respective partitions; test labels are evaluation-only.
use sdm_core::{features_for, DecisionSpec};
use sdm_data::{
    validate_dataset, validate_split, DatasetExample, Provenance, SplitManifest, TargetLabel,
};
use sdm_eval::{evaluate_rank, CandidatePrediction, RankPrediction};
use sdm_runtime::{load_artifact, ArtifactEnvelopeV2, LinearArtifact, LoadedArtifact, Runtime};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::{Read, Write},
    path::Path,
};

pub const MAX_CONFIG_BYTES: usize = 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExperimentSpec {
    pub dataset_path: String,
    pub split_path: String,
    pub architecture: String,
    pub seed: u64,
    pub epochs: usize,
    pub learning_rate: f64,
    pub artifact_path: String,
    pub report_path: String,
    pub provenance: Provenance,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExperimentRunManifest {
    pub dataset_sha256: String,
    pub split_fingerprint: String,
    pub architecture: String,
    pub seed: u64,
    pub train_ids: Vec<String>,
    pub dev_ids: Vec<String>,
    pub test_ids: Vec<String>,
    pub model_sha256: String,
    pub calibration_sha256: String,
    pub artifact_sha256: String,
    pub report_sha256: String,
    pub metrics: sdm_eval::RankMetrics,
    pub verdict: String,
}

#[derive(Debug, thiserror::Error)]
pub enum ExperimentError {
    #[error("invalid experiment: {0}")]
    Invalid(String),
    #[error("I/O: {0}")]
    Io(#[from] std::io::Error),
    #[error("encoding: {0}")]
    Json(#[from] serde_json::Error),
}

fn digest<T: Serialize>(value: &T) -> Result<String, ExperimentError> {
    Ok(format!(
        "sha256:{:x}",
        Sha256::digest(serde_json::to_vec(value)?)
    ))
}

fn atomic_write(path: &str, bytes: &[u8]) -> Result<(), ExperimentError> {
    let target = Path::new(path);
    if target.exists() {
        return Err(ExperimentError::Invalid(format!(
            "refusing to overwrite {}",
            target.display()
        )));
    }
    let parent = target
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let tmp = parent.join(format!(
        ".sdm-experiment-{}-{}.tmp",
        std::process::id(),
        Sha256::digest(path.as_bytes())[0]
    ));
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&tmp)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    // Validate complete JSON bytes before making the artifact visible.
    let _: serde_json::Value = serde_json::from_slice(bytes)?;
    fs::hard_link(&tmp, target)?;
    fs::remove_file(tmp)?;
    Ok(())
}

fn rank_parts<'a>(
    examples: &'a [DatasetExample],
    ids: &[String],
) -> Result<Vec<&'a DatasetExample>, ExperimentError> {
    let map: BTreeMap<_, _> = examples.iter().map(|e| (e.case_id.as_str(), e)).collect();
    ids.iter()
        .map(|id| {
            map.get(id.as_str())
                .copied()
                .ok_or_else(|| ExperimentError::Invalid("split references missing case".into()))
        })
        .collect()
}

fn rank_y(e: &DatasetExample, id: &str) -> bool {
    matches!(&e.label, TargetLabel::Rank { relevance, .. } if relevance.get(id).copied().unwrap_or(0.0) > 0.0)
}
fn rank_text(e: &DatasetExample) -> (String, &Vec<sdm_core::DecisionCandidate>) {
    let context = e
        .request
        .state
        .iter()
        .map(|s| s.value.as_str())
        .collect::<Vec<_>>()
        .join(" ");
    let DecisionSpec::Rank { candidates, .. } = &e.request.spec else {
        unreachable!("dataset validation guards semantics")
    };
    (context, candidates)
}
fn linear_probability(
    a: &LinearArtifact,
    context: &str,
    candidate: &sdm_core::DecisionCandidate,
) -> f64 {
    let option = format!("{} {}", candidate.label, candidate.description);
    let z = features_for(&context.to_lowercase(), &option.to_lowercase())
        .iter()
        .map(|f| a.weights.get(f).copied().unwrap_or(0.0))
        .sum::<f64>()
        + a.bias;
    1.0 / (1.0 + (-z).exp())
}

fn train_linear(
    train: &[&DatasetExample],
    dev: &[&DatasetExample],
    seed: u64,
    epochs: usize,
) -> Result<LinearArtifact, ExperimentError> {
    let mut weights = BTreeMap::<String, f64>::new();
    let mut bias = 0.0;
    for _ in 0..epochs {
        for e in train {
            let (context, candidates) = rank_text(e);
            for c in candidates {
                let x = features_for(
                    &context.to_lowercase(),
                    &format!("{} {}", c.label, c.description).to_lowercase(),
                );
                let p = 1.0
                    / (1.0
                        + (-(x
                            .iter()
                            .map(|f| weights.get(f).copied().unwrap_or(0.0))
                            .sum::<f64>()
                            + bias))
                            .exp());
                let error = f64::from(rank_y(e, &c.id)) - p;
                bias += 0.05 * error;
                for f in x {
                    *weights.entry(f).or_default() += 0.05 * error;
                }
            }
        }
    }
    let mut observations = Vec::new();
    for e in dev {
        let (ctx, cs) = rank_text(e);
        let max = cs
            .iter()
            .map(|c| {
                linear_probability(
                    &LinearArtifact {
                        manifest: dummy_manifest(),
                        bias,
                        weights: weights.clone(),
                        threshold: 0.5,
                    },
                    &ctx,
                    c,
                )
            })
            .fold(0.0_f64, f64::max);
        observations.push((max, cs.iter().any(|c| rank_y(e, &c.id))));
    }
    let threshold = select_threshold(&observations);
    let model_sha = sdm_runtime::parameter_digest(bias, &weights);
    let calibration_sha = format!(
        "sha256:{:x}",
        Sha256::digest(threshold.to_bits().to_le_bytes())
    );
    let train_digest = digest(&train.to_vec())?;
    let artifact = LinearArtifact {
        manifest: sdm_runtime::ArtifactManifest {
            schema_version: 1,
            architecture: "sdm-binary-linear-v1".into(),
            input_schema_version: 1,
            capabilities: vec!["rank".into()],
            max_state_bytes: 65_536,
            max_candidates: 256,
            model_sha256: model_sha,
            training_fingerprint: train_digest,
            calibration_version: 1,
            calibration_sha256: calibration_sha,
            license: "MIT".into(),
            source: format!("sdm-experiment-seed-{seed}"),
        },
        bias,
        weights,
        threshold,
    };
    Runtime::from_bytes(&serde_json::to_vec(&artifact)?)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    Ok(artifact)
}
fn dummy_manifest() -> sdm_runtime::ArtifactManifest {
    sdm_runtime::ArtifactManifest {
        schema_version: 1,
        architecture: "sdm-binary-linear-v1".into(),
        input_schema_version: 1,
        capabilities: vec!["rank".into()],
        max_state_bytes: 65536,
        max_candidates: 256,
        model_sha256: String::new(),
        training_fingerprint: String::new(),
        calibration_version: 1,
        calibration_sha256: String::new(),
        license: "MIT".into(),
        source: "temporary".into(),
    }
}
fn select_threshold(obs: &[(f64, bool)]) -> f64 {
    if obs.is_empty() {
        return 0.5;
    }
    let pos = obs.iter().filter(|x| x.1).count();
    let neg = obs.len() - pos;
    (0..=100)
        .map(|i| {
            let t = i as f64 / 100.0;
            let tp = obs.iter().filter(|(p, y)| *y && *p >= t).count();
            let tn = obs.iter().filter(|(p, y)| !*y && *p < t).count();
            let score = match (pos > 0, neg > 0) {
                (true, true) => 0.5 * (tp as f64 / pos as f64 + tn as f64 / neg as f64),
                (true, false) => tp as f64 / pos as f64,
                (false, true) => tn as f64 / neg as f64,
                _ => 0.5,
            };
            (score, t)
        })
        .max_by(|a, b| a.0.total_cmp(&b.0))
        .map(|x| x.1)
        .unwrap_or(0.5)
}

fn train_nonlinear(
    train: &[&DatasetExample],
    dev: &[&DatasetExample],
    seed: u64,
    epochs: usize,
    lr: f64,
) -> Result<(sdm_nonlinear::PairwiseModel, f64), ExperimentError> {
    let mut ids = BTreeSet::new();
    for e in train {
        let (ctx, cs) = rank_text(e);
        for c in cs {
            for t in sdm_core::tokens(&ctx) {
                ids.insert(format!("ctx:{t}"));
            }
            for t in sdm_core::tokens(&format!("{} {}", c.label, c.description)) {
                ids.insert(format!("cand:{t}"));
            }
        }
    }
    if ids.is_empty() {
        ids.insert("ctx:empty".into());
    }
    let mut model = sdm_nonlinear::initialize(ids.into_iter().collect(), 8, seed)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let mut pairs = Vec::new();
    for e in train {
        let (ctx, cs) = rank_text(e);
        for c in cs {
            let x = model
                .rank_features(&ctx, &format!("{} {}", c.label, c.description))
                .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
            pairs.push((x, f64::from(rank_y(e, &c.id))));
        }
    }
    sdm_nonlinear::train(&mut model, &pairs, epochs, lr)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let observations = dev
        .iter()
        .map(|e| {
            let (ctx, cs) = rank_text(e);
            let max = cs
                .iter()
                .filter_map(|c| {
                    model
                        .rank_features(&ctx, &format!("{} {}", c.label, c.description))
                        .ok()
                        .and_then(|x| model.score(&x).ok())
                        .map(|s| 1.0 / (1.0 + (-s).exp()))
                })
                .fold(0.0_f64, f64::max);
            (max, cs.iter().any(|c| rank_y(e, &c.id)))
        })
        .collect::<Vec<_>>();
    Ok((model, select_threshold(&observations)))
}

fn train_typed_rank(
    train: &[&DatasetExample],
    dev: &[&DatasetExample],
    seed: u64,
    epochs: usize,
    lr: f64,
) -> Result<(sdm_core::FittedFeatureEncoderV2, Vec<f64>, f64, f64), ExperimentError> {
    const MAX_TYPED_RANK_PAIRS: usize = 100_000;
    let pair_count = train.iter().try_fold(0usize, |n, e| {
        let (_, candidates) = rank_text(e);
        n.checked_add(candidates.len())
            .filter(|v| *v <= MAX_TYPED_RANK_PAIRS)
            .ok_or_else(|| ExperimentError::Invalid("typed training pair bound exceeded".into()))
    })?;
    if pair_count == 0 {
        return Err(ExperimentError::Invalid(
            "typed training partition has no candidates".into(),
        ));
    }
    let first = train
        .first()
        .and_then(|e| e.typed_rank_features.as_ref())
        .ok_or_else(|| {
            ExperimentError::Invalid(
                "typed-linear requires typed Rank features on every row".into(),
            )
        })?;
    let schema = &first.schema;
    let mut projections = Vec::new();
    for e in train {
        let binding = e.typed_rank_features.as_ref().ok_or_else(|| {
            ExperimentError::Invalid("typed Rank features missing from training row".into())
        })?;
        if binding
            .schema
            .fingerprint()
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?
            != schema
                .fingerprint()
                .map_err(|e| ExperimentError::Invalid(e.to_string()))?
        {
            return Err(ExperimentError::Invalid(
                "typed schema drift in training split".into(),
            ));
        }
        projections.push(binding.context.clone());
        projections.extend(binding.candidates.values().cloned());
    }
    let encoder = sdm_core::FittedFeatureEncoderV2::fit(schema, &projections)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let dim = encoder
        .dimension()
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?
        * 2;
    let mut weights = vec![0.0; dim];
    let mut bias = 0.0;
    for _ in 0..epochs {
        for e in train {
            let binding = e.typed_rank_features.as_ref().unwrap();
            let context = encoder
                .encode(&binding.context)
                .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
            for (id, candidate) in &binding.candidates {
                let mut x = context.clone();
                x.extend(
                    encoder
                        .encode(candidate)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
                );
                let z = x.iter().zip(&weights).map(|(a, b)| a * b).sum::<f64>() + bias;
                let p = 1.0 / (1.0 + (-z).exp());
                let error = f64::from(rank_y(e, id)) - p;
                bias += lr * error;
                for (w, v) in weights.iter_mut().zip(x) {
                    *w += lr * error * v;
                }
            }
        }
    }
    let mut observations = Vec::new();
    for e in dev {
        let binding = e.typed_rank_features.as_ref().ok_or_else(|| {
            ExperimentError::Invalid("typed Rank features missing from dev row".into())
        })?;
        let context = encoder
            .encode(&binding.context)
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let mut max = 0.0_f64;
        for candidate in binding.candidates.values() {
            let mut x = context.clone();
            x.extend(
                encoder
                    .encode(candidate)
                    .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
            );
            let z = x.iter().zip(&weights).map(|(a, b)| a * b).sum::<f64>() + bias;
            max = max.max(1.0 / (1.0 + (-z).exp()));
        }
        observations.push((max, binding.candidates.keys().any(|id| rank_y(e, id))));
    }
    let threshold = select_threshold(&observations);
    let _ = seed;
    Ok((encoder, weights, bias, threshold))
}

pub fn run(spec: &ExperimentSpec) -> Result<ExperimentRunManifest, ExperimentError> {
    if spec.epochs == 0
        || spec.epochs > 10_000
        || !spec.learning_rate.is_finite()
        || !(0.0..=1.0).contains(&spec.learning_rate)
        || !["linear", "nonlinear", "typed-linear"].contains(&spec.architecture.as_str())
    {
        return Err(ExperimentError::Invalid(
            "invalid architecture or training bounds".into(),
        ));
    }
    let mut dataset_bytes = Vec::new();
    fs::File::open(&spec.dataset_path)?
        .take((sdm_data::MAX_DATASET_BYTES + 1) as u64)
        .read_to_end(&mut dataset_bytes)?;
    if dataset_bytes.len() > sdm_data::MAX_DATASET_BYTES {
        return Err(ExperimentError::Invalid(
            "dataset byte limit exceeded".into(),
        ));
    }
    #[derive(Deserialize, Serialize)]
    struct Bundle {
        provenance: Provenance,
        examples: Vec<DatasetExample>,
    }
    let bundle: Bundle = serde_json::from_slice(&dataset_bytes)?;
    if bundle.provenance != spec.provenance {
        return Err(ExperimentError::Invalid(
            "config provenance differs from dataset bundle".into(),
        ));
    }
    let dataset_sha256 = validate_dataset(&bundle.examples, &spec.provenance)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let mut split_bytes = Vec::new();
    fs::File::open(&spec.split_path)?
        .take((MAX_CONFIG_BYTES + 1) as u64)
        .read_to_end(&mut split_bytes)?;
    if split_bytes.len() > MAX_CONFIG_BYTES {
        return Err(ExperimentError::Invalid(
            "split manifest exceeds limit".into(),
        ));
    }
    let split: SplitManifest = serde_json::from_slice(&split_bytes)?;
    validate_split(&bundle.examples, &split, &dataset_sha256)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let train = rank_parts(&bundle.examples, &split.train)?;
    let dev = rank_parts(&bundle.examples, &split.dev)?;
    let test = rank_parts(&bundle.examples, &split.test)?;
    for e in bundle.examples.iter() {
        if !matches!(e.label, TargetLabel::Rank { .. }) {
            return Err(ExperimentError::Invalid(
                "experiment accepts Rank examples only".into(),
            ));
        }
    }
    let train_identity = digest(&train.to_vec())?;
    let (artifact_bytes, model_sha256, calibration_sha256) = if spec.architecture == "linear" {
        let artifact = train_linear(&train, &dev, spec.seed, spec.epochs)?;
        let model = artifact.manifest.model_sha256.clone();
        let calibration = artifact.manifest.calibration_sha256.clone();
        (serde_json::to_vec(&artifact)?, model, calibration)
    } else if spec.architecture == "typed-linear" {
        let (encoder, weights, bias, threshold) =
            train_typed_rank(&train, &dev, spec.seed, spec.epochs, spec.learning_rate)?;
        let env = ArtifactEnvelopeV2::for_typed_rank(
            &encoder,
            weights,
            bias,
            threshold,
            train_identity.clone(),
            format!("typed-rank:{train_identity}"),
            256,
        )
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let model = env.tensor_payload_sha256.clone();
        let calibration = env.calibration_sha256.clone();
        (serde_json::to_vec(&env)?, model, calibration)
    } else {
        let (model, threshold) =
            train_nonlinear(&train, &dev, spec.seed, spec.epochs, spec.learning_rate)?;
        let model_sha = format!(
            "sha256:{:x}",
            Sha256::digest(
                model
                    .to_bytes()
                    .map_err(|e| ExperimentError::Invalid(e.to_string()))?
            )
        );
        let env = ArtifactEnvelopeV2::for_nonlinear(
            &model,
            format!("{}:{}", train_identity, spec.seed),
            256,
            threshold,
            "MIT",
            "sdm-experiment",
        )
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let calibration = env.calibration_sha256.clone();
        (serde_json::to_vec(&env)?, model_sha, calibration)
    };
    let loaded =
        load_artifact(&artifact_bytes).map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let test_examples = test.iter().map(|e| (*e).clone()).collect::<Vec<_>>();
    let mut predictions = Vec::new();
    for e in &test {
        let response = match &loaded {
            LoadedArtifact::LinearV1(rt) => rt.decide(&e.request),
            LoadedArtifact::NonlinearV2(rt) => rt.decide(&e.request),
            LoadedArtifact::TypedRankV2(rt) => rt.decide_typed(
                &e.request,
                e.typed_rank_features.as_ref().ok_or_else(|| {
                    ExperimentError::Invalid("typed Rank features absent at inference".into())
                })?,
            ),
            LoadedArtifact::UnsupportedV2(_) => {
                return Err(ExperimentError::Invalid(
                    "runtime does not support trained artifact".into(),
                ))
            }
        }
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let DecisionSpec::Rank { candidates, .. } = &e.request.spec else {
            unreachable!()
        };
        let scored = match response.answer {
            Some(sdm_core::DecisionAnswer::Rank { candidates }) => candidates
                .into_iter()
                .map(|c| CandidatePrediction {
                    candidate_id: c.candidate_id,
                    score: c.ranking_score,
                })
                .collect(),
            _ => candidates
                .iter()
                .map(|c| CandidatePrediction {
                    candidate_id: c.id.clone(),
                    score: f64::NEG_INFINITY,
                })
                .collect(),
        };
        predictions.push(RankPrediction {
            case_id: e.case_id.clone(),
            candidates: scored,
        });
    }
    // Abstention becomes a stable tied minimum while preserving exact candidate identities.
    for p in &mut predictions {
        for c in &mut p.candidates {
            if !c.score.is_finite() {
                c.score = -1.0e300;
            }
        }
    }
    let metrics = evaluate_rank(&test_examples, &predictions, 5)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let artifact_sha256 = format!("sha256:{:x}", Sha256::digest(&artifact_bytes));
    let mut report = ExperimentRunManifest {
        dataset_sha256: dataset_sha256.clone(),
        split_fingerprint: split.fingerprint.clone(),
        architecture: spec.architecture.clone(),
        seed: spec.seed,
        train_ids: split.train.clone(),
        dev_ids: split.dev.clone(),
        test_ids: split.test.clone(),
        model_sha256,
        calibration_sha256,
        artifact_sha256,
        report_sha256: String::new(),
        metrics,
        verdict: "indeterminate".into(),
    };
    // Synthetic corpus mechanics are informative, but do not claim real-world qualification.
    report.verdict = "synthetic-mechanics-only".into();
    report.report_sha256 = digest(&(
        &report.dataset_sha256,
        &report.split_fingerprint,
        &report.architecture,
        &report.model_sha256,
        &report.calibration_sha256,
        &report.metrics,
    ))?;
    atomic_write(&spec.artifact_path, &artifact_bytes)?;
    atomic_write(&spec.report_path, &serde_json::to_vec_pretty(&report)?)?;
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[derive(Deserialize, Serialize)]
    struct Bundle {
        provenance: Provenance,
        examples: Vec<DatasetExample>,
    }
    fn spec(
        root: &Path,
        architecture: &str,
        dataset: &str,
        split: &str,
        tag: &str,
        provenance: Provenance,
    ) -> ExperimentSpec {
        ExperimentSpec {
            dataset_path: dataset.into(),
            split_path: split.into(),
            architecture: architecture.into(),
            seed: 42,
            epochs: 8,
            learning_rate: 0.02,
            artifact_path: root
                .join(format!("{tag}.artifact.json"))
                .display()
                .to_string(),
            report_path: root
                .join(format!("{tag}.report.json"))
                .display()
                .to_string(),
            provenance,
        }
    }
    fn temp_root() -> std::path::PathBuf {
        static NEXT: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
        let nonce = NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let p = std::env::temp_dir().join(format!(
            "sdm-experiment-test-{}-{}-{nonce}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&p).unwrap();
        p
    }
    #[test]
    fn both_architectures_train_package_reload_and_evaluate_exact_candidates() {
        let root = temp_root();
        let workspace = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let dataset = workspace
            .join("fixtures/standalone-rank-v1.json")
            .display()
            .to_string();
        let split = workspace
            .join("fixtures/standalone-rank-v1.split.json")
            .display()
            .to_string();
        let bundle: Bundle =
            serde_json::from_str(include_str!("../../../fixtures/standalone-rank-v1.json"))
                .unwrap();
        for arch in ["linear", "nonlinear"] {
            let result = run(&spec(
                &root,
                arch,
                &dataset,
                &split,
                arch,
                bundle.provenance.clone(),
            ))
            .unwrap();
            assert_eq!(result.verdict, "synthetic-mechanics-only");
            assert_eq!(result.metrics.candidate_universe_coverage, 1.0);
            assert_eq!(result.metrics.cases, result.test_ids.len());
            let bytes = fs::read(root.join(format!("{arch}.artifact.json"))).unwrap();
            assert!(matches!(
                load_artifact(&bytes).unwrap(),
                LoadedArtifact::LinearV1(_) | LoadedArtifact::NonlinearV2(_)
            ));
        }
        let typed_dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../fixtures");
        let typed_dataset = typed_dir
            .join("standalone-typed-rank-v1.json")
            .display()
            .to_string();
        let typed_split = typed_dir
            .join("standalone-typed-rank-v1.split.json")
            .display()
            .to_string();
        let typed_bundle: Bundle = serde_json::from_str(include_str!(
            "../../../fixtures/standalone-typed-rank-v1.json"
        ))
        .unwrap();
        let typed = run(&spec(
            &root,
            "typed-linear",
            &typed_dataset,
            &typed_split,
            "typed",
            typed_bundle.provenance,
        ))
        .unwrap();
        assert_eq!(typed.verdict, "synthetic-mechanics-only");
        assert_eq!(typed.metrics.candidate_universe_coverage, 1.0);
        let typed_bytes = fs::read(root.join("typed.artifact.json")).unwrap();
        assert!(matches!(
            load_artifact(&typed_bytes).unwrap(),
            LoadedArtifact::TypedRankV2(_)
        ));
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn held_out_label_changes_do_not_change_model_or_dev_calibration() {
        let root = temp_root();
        let mut bundle: Bundle =
            serde_json::from_str(include_str!("../../../fixtures/standalone-rank-v1.json"))
                .unwrap();
        let split: SplitManifest = serde_json::from_str(include_str!(
            "../../../fixtures/standalone-rank-v1.split.json"
        ))
        .unwrap();
        let mut path = std::env::temp_dir();
        path.push(format!("sdm-mutated-{}.json", std::process::id()));
        let mut spath = std::env::temp_dir();
        spath.push(format!("sdm-mutated-split-{}.json", std::process::id()));
        let a = run(&spec(
            &root,
            "linear",
            &Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../../fixtures/standalone-rank-v1.json")
                .display()
                .to_string(),
            &Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../../fixtures/standalone-rank-v1.split.json")
                .display()
                .to_string(),
            "base",
            bundle.provenance.clone(),
        ))
        .unwrap();
        if let TargetLabel::Rank {
            relevance,
            no_relevant,
        } = &mut bundle
            .examples
            .iter_mut()
            .find(|e| e.case_id == split.test[0])
            .unwrap()
            .label
        {
            relevance.clear();
            *no_relevant = !*no_relevant;
        }
        let data_hash = validate_dataset(&bundle.examples, &bundle.provenance).unwrap();
        let mut changed_split = split;
        changed_split.dataset_sha256 = data_hash;
        changed_split.fingerprint.clear();
        changed_split.fingerprint = digest(&changed_split).unwrap();
        fs::write(&path, serde_json::to_vec(&bundle).unwrap()).unwrap();
        fs::write(&spath, serde_json::to_vec(&changed_split).unwrap()).unwrap();
        let b = run(&spec(
            &root,
            "linear",
            path.to_str().unwrap(),
            spath.to_str().unwrap(),
            "mutated",
            bundle.provenance,
        ))
        .unwrap();
        assert_eq!(a.model_sha256, b.model_sha256);
        assert_eq!(a.calibration_sha256, b.calibration_sha256);
        fs::remove_file(path).unwrap();
        fs::remove_file(spath).unwrap();
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn held_out_typed_values_and_labels_do_not_refit_preprocessor_or_model() {
        let root = temp_root();
        let mut bundle: Bundle = serde_json::from_str(include_str!(
            "../../../fixtures/standalone-typed-rank-v1.json"
        ))
        .unwrap();
        let split: SplitManifest = serde_json::from_str(include_str!(
            "../../../fixtures/standalone-typed-rank-v1.split.json"
        ))
        .unwrap();
        let workspace = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../fixtures");
        let dataset = workspace
            .join("standalone-typed-rank-v1.json")
            .display()
            .to_string();
        let split_path = workspace
            .join("standalone-typed-rank-v1.split.json")
            .display()
            .to_string();
        let a = run(&spec(
            &root,
            "typed-linear",
            &dataset,
            &split_path,
            "typed-base",
            bundle.provenance.clone(),
        ))
        .unwrap();
        let test_id = &split.test[0];
        if let TargetLabel::Rank {
            relevance,
            no_relevant,
        } = &mut bundle
            .examples
            .iter_mut()
            .find(|e| &e.case_id == test_id)
            .unwrap()
            .label
        {
            relevance.clear();
            *no_relevant = !*no_relevant;
        }
        let typed = bundle
            .examples
            .iter_mut()
            .find(|e| &e.case_id == test_id)
            .unwrap()
            .typed_rank_features
            .as_mut()
            .unwrap();
        typed
            .context
            .fields
            .iter_mut()
            .find(|f| f.id == "load")
            .unwrap()
            .value = Some(sdm_core::FeatureValue::Number(1.0e300));
        let data_hash = validate_dataset(&bundle.examples, &bundle.provenance).unwrap();
        let mut changed_split = split;
        changed_split.dataset_sha256 = data_hash;
        changed_split.fingerprint.clear();
        changed_split.fingerprint = digest(&changed_split).unwrap();
        let dataset_path = root.join("typed-mutated.json");
        let split_path = root.join("typed-mutated-split.json");
        fs::write(&dataset_path, serde_json::to_vec(&bundle).unwrap()).unwrap();
        fs::write(&split_path, serde_json::to_vec(&changed_split).unwrap()).unwrap();
        let b = run(&spec(
            &root,
            "typed-linear",
            dataset_path.to_str().unwrap(),
            split_path.to_str().unwrap(),
            "typed-mutated",
            bundle.provenance,
        ))
        .unwrap();
        assert_eq!(a.model_sha256, b.model_sha256);
        assert_eq!(a.calibration_sha256, b.calibration_sha256);
        fs::remove_dir_all(root).unwrap();
    }
}
