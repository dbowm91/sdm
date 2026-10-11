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
    #[serde(default)]
    pub quality_diagnostics: bool,
    #[serde(default)]
    pub seeded_epoch_order: bool,
    /// Opt-in train-only removal of exactly constant encoded Binary coordinates.
    #[serde(default)]
    pub binary_constant_mask: bool,
    /// Binary L2 weight decay; the scalar intercept remains unpenalized.
    #[serde(default)]
    pub binary_l2_weight_decay: f64,
    /// Set false for train/dev candidate screening that must not score held-out rows.
    #[serde(default = "default_true")]
    pub evaluate_test: bool,
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
    pub outcomes: Vec<RankCaseOutcome>,
    pub verdict: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RankCaseOutcome {
    pub case_id: String,
    pub leakage_group: String,
    pub relevance: BTreeMap<String, f64>,
    pub prediction: Vec<CandidatePrediction>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "semantic", content = "metrics", rename_all = "snake_case")]
pub enum SemanticMetrics {
    Binary(sdm_eval::BinaryMetrics),
    Choice(sdm_eval::ChoiceMetrics),
    Score(sdm_eval::ScoreMetrics),
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SemanticExperimentRunManifest {
    pub dataset_sha256: String,
    pub split_fingerprint: String,
    pub semantic: String,
    pub seed: u64,
    pub train_ids: Vec<String>,
    pub dev_ids: Vec<String>,
    pub test_ids: Vec<String>,
    pub model_sha256: String,
    pub calibration_sha256: String,
    pub artifact_sha256: String,
    pub report_sha256: String,
    pub metrics: SemanticMetrics,
    pub abstentions: usize,
    pub outcomes: Vec<SemanticCaseOutcome>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub binary_masked_coordinates: Vec<usize>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub binary_training_policy: Option<BinaryTrainingPolicy>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub training_curve: Vec<TrainingEpochLoss>,
    pub verdict: String,
    #[serde(default = "default_true", skip_serializing_if = "is_true")]
    pub test_evaluation_performed: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dev_diagnostics: Option<BTreeMap<String, f64>>,
}

fn default_true() -> bool {
    true
}
fn is_true(value: &bool) -> bool {
    *value
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainingEpochLoss {
    pub epoch: usize,
    pub train_loss: f64,
    pub dev_loss: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BinaryTrainingPolicy {
    pub version: String,
    pub variation_threshold: f64,
    pub masked_coordinates: Vec<usize>,
    pub retained_coordinates: Vec<usize>,
    pub encoder_fingerprint: String,
    pub training_fingerprint: String,
    pub l2_weight_decay: f64,
    pub intercept: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SemanticCaseOutcome {
    pub case_id: String,
    pub leakage_group: String,
    pub target: serde_json::Value,
    pub prediction: serde_json::Value,
    pub score: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub raw_probabilities: Option<Vec<f64>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub raw_logits: Option<Vec<f64>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub answerability_probability: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub nuisance_probabilities: Option<BTreeMap<String, f64>>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub abstained: bool,
}

fn is_false(value: &bool) -> bool {
    !value
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
        .max_by(|a, b| a.0.total_cmp(&b.0).then_with(|| b.1.total_cmp(&a.1)))
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

fn semantic_task(architecture: &str) -> Option<&'static str> {
    match architecture {
        "typed-binary" => Some("binary"),
        "typed-choice" | "typed-choice-cross" | "typed-choice-compositional" => Some("choice"),
        "typed-score" => Some("score"),
        _ => None,
    }
}
fn sigmoid(z: f64) -> f64 {
    1.0 / (1.0 + (-z).exp())
}
type TypedTaskModel = (
    sdm_core::FittedFeatureEncoderV2,
    Vec<f64>,
    f64,
    Option<Vec<f64>>,
    Option<f64>,
    f64,
    Option<Vec<(usize, usize)>>,
    Option<Vec<(usize, usize, usize)>>,
    Vec<usize>,
    Vec<TrainingEpochLoss>,
);

struct PreparedTypedExample {
    context: Vec<f64>,
    standalone: Vec<f64>,
    options: Vec<Vec<f64>>,
}

fn prepare_typed_examples(
    encoder: &sdm_core::FittedFeatureEncoderV2,
    examples: &[&DatasetExample],
    task: &str,
    choice_cross: bool,
    compositional_triples: &[(usize, usize, usize)],
    cross_pairs: &[(usize, usize)],
) -> Result<Vec<PreparedTypedExample>, ExperimentError> {
    examples
        .iter()
        .map(|e| {
            let binding = e
                .typed_rank_features
                .as_ref()
                .ok_or_else(|| ExperimentError::Invalid("typed features missing".into()))?;
            let context = encoder
                .encode(&binding.context)
                .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
            let mut standalone = context.clone();
            standalone.resize(
                if task == "choice" && !choice_cross && compositional_triples.is_empty() {
                    context.len() * 3
                } else if !compositional_triples.is_empty() {
                    context.len() * 2 + compositional_triples.len()
                } else {
                    context.len() * 2 + if choice_cross { cross_pairs.len() } else { 0 }
                },
                0.0,
            );
            let options = if task == "choice" {
                let sdm_core::DecisionSpec::Choice { options, .. } = &e.request.spec else {
                    return Err(ExperimentError::Invalid(
                        "Choice request missing options".into(),
                    ));
                };
                options
                    .iter()
                    .map(|o| {
                        let item = encoder
                            .encode(binding.candidates.get(&o.id).ok_or_else(|| {
                                ExperimentError::Invalid("typed option projection missing".into())
                            })?)
                            .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
                        let mut vector = context
                            .iter()
                            .copied()
                            .chain(item.iter().copied())
                            .collect::<Vec<_>>();
                        if choice_cross {
                            vector.extend(cross_pairs.iter().map(|(c, o)| context[*c] * item[*o]));
                        } else if !compositional_triples.is_empty() {
                            vector.extend(
                                compositional_triples
                                    .iter()
                                    .map(|(a, b, o)| context[*a] * context[*b] * item[*o]),
                            );
                        } else {
                            vector.extend(context.iter().zip(&item).map(|(c, o)| c * o));
                        }
                        Ok(vector)
                    })
                    .collect::<Result<Vec<_>, ExperimentError>>()?
            } else {
                Vec::new()
            };
            Ok(PreparedTypedExample {
                context,
                standalone,
                options,
            })
        })
        .collect()
}

fn binary_log_loss(y: f64, p: f64) -> f64 {
    let p = p.clamp(1e-15, 1.0 - 1e-15);
    -y * p.ln() - (1.0 - y) * (1.0 - p).ln()
}

fn training_order(length: usize, seed: u64, epoch: usize, shuffled: bool) -> Vec<usize> {
    let mut order: Vec<usize> = (0..length).collect();
    if shuffled {
        let mut state = seed ^ (epoch as u64).wrapping_mul(0x9e3779b97f4a7c15);
        for i in (1..order.len()).rev() {
            state = state.wrapping_add(0x9e3779b97f4a7c15);
            let mut z = state;
            z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
            z ^= z >> 31;
            order.swap(i, (z as usize) % (i + 1));
        }
    }
    order
}

fn typed_task_loss(
    examples: &[&DatasetExample],
    prepared: &[PreparedTypedExample],
    task: &str,
    weights: &[f64],
    bias: f64,
    answerability_weights: Option<&[f64]>,
    answerability_bias: Option<f64>,
) -> f64 {
    if examples.is_empty() {
        return 0.0;
    }
    let mut loss = 0.0;
    for (e, x) in examples.iter().zip(prepared) {
        match (&e.label, task) {
            (TargetLabel::Binary(y), "binary") => {
                let z = x
                    .standalone
                    .iter()
                    .zip(weights)
                    .map(|(a, b)| a * b)
                    .sum::<f64>()
                    + bias;
                loss += binary_log_loss(f64::from(*y), sigmoid(z));
            }
            (TargetLabel::Choice(target), "choice") => {
                let aw = answerability_weights.expect("Choice answerability head");
                let p = sigmoid(
                    x.context.iter().zip(aw).map(|(a, b)| a * b).sum::<f64>()
                        + answerability_bias.unwrap_or(0.0),
                );
                loss += binary_log_loss(f64::from(target.is_some()), p);
                if let Some(target) = target {
                    let sdm_core::DecisionSpec::Choice { options, .. } = &e.request.spec else {
                        unreachable!()
                    };
                    let scores = x
                        .options
                        .iter()
                        .map(|v| v.iter().zip(weights).map(|(a, b)| a * b).sum::<f64>() + bias)
                        .collect::<Vec<_>>();
                    let max = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                    let lse = max + scores.iter().map(|s| (s - max).exp()).sum::<f64>().ln();
                    if let Some(i) = options.iter().position(|o| o.id == *target) {
                        loss += lse - scores[i];
                    }
                }
            }
            (TargetLabel::Score(y), "score") => {
                let sdm_core::DecisionSpec::Score {
                    minimum, maximum, ..
                } = &e.request.spec
                else {
                    unreachable!()
                };
                let target = (*y - *minimum) / (*maximum - *minimum);
                let z = x
                    .standalone
                    .iter()
                    .zip(weights)
                    .map(|(a, b)| a * b)
                    .sum::<f64>()
                    + bias;
                loss += binary_log_loss(target, sigmoid(z));
            }
            _ => {}
        }
    }
    loss / examples.len() as f64
}

#[allow(clippy::too_many_arguments)]
fn train_typed_task(
    train: &[&DatasetExample],
    dev: &[&DatasetExample],
    task: &str,
    seed: u64,
    epochs: usize,
    lr: f64,
    choice_cross: bool,
    choice_compositional: bool,
    binary_constant_mask: bool,
    binary_l2_weight_decay: f64,
    seeded_epoch_order: bool,
    quality_diagnostics: bool,
) -> Result<TypedTaskModel, ExperimentError> {
    let first = train
        .first()
        .and_then(|e| e.typed_rank_features.as_ref())
        .ok_or_else(|| ExperimentError::Invalid("typed task requires train projections".into()))?;
    let mut projections = Vec::new();
    for e in train {
        let b = e
            .typed_rank_features
            .as_ref()
            .ok_or_else(|| ExperimentError::Invalid("typed training projection missing".into()))?;
        if b.schema
            .fingerprint()
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?
            != first
                .schema
                .fingerprint()
                .map_err(|e| ExperimentError::Invalid(e.to_string()))?
        {
            return Err(ExperimentError::Invalid(
                "typed schema drift in train partition".into(),
            ));
        }
        projections.push(b.context.clone());
        projections.extend(b.candidates.values().cloned());
    }
    let encoder = sdm_core::FittedFeatureEncoderV2::fit(&first.schema, &projections)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let input_dim = encoder
        .dimension()
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let cross_pairs = if task == "choice" && choice_cross {
        bounded_nontext_cross_pairs(&encoder)?
    } else {
        Vec::new()
    };
    let compositional_triples = if task == "choice" && choice_compositional {
        bounded_nontext_choice_triples(&encoder)?
    } else {
        Vec::new()
    };
    let dim = input_dim
        * if task == "choice" && !choice_cross && !choice_compositional {
            3
        } else {
            2
        }
        + cross_pairs.len()
        + compositional_triples.len();
    let mut weights = vec![0.0; dim];
    let mut bias = 0.0;
    let mut answerability_weights = (task == "choice").then(|| vec![0.0; input_dim]);
    let mut answerability_bias = (task == "choice").then_some(0.0);
    let train_prepared = prepare_typed_examples(
        &encoder,
        train,
        task,
        choice_cross,
        &compositional_triples,
        &cross_pairs,
    )?;
    let dev_prepared = prepare_typed_examples(
        &encoder,
        dev,
        task,
        choice_cross,
        &compositional_triples,
        &cross_pairs,
    )?;
    let mut training_curve = Vec::new();
    let masked_coordinates = if task == "binary" && binary_constant_mask {
        (0..input_dim)
            .filter(|j| {
                train_prepared
                    .iter()
                    .all(|x| x.standalone[*j] == train_prepared[0].standalone[*j])
            })
            .collect::<Vec<_>>()
    } else {
        Vec::new()
    };
    for epoch in 0..epochs {
        let order = training_order(train.len(), seed, epoch, seeded_epoch_order);
        for index in order {
            let e = train[index];
            let prepared = &train_prepared[index];
            match (&e.label, &e.request.spec) {
                (TargetLabel::Binary(y), sdm_core::DecisionSpec::Binary { .. }) => {
                    let x = &prepared.standalone;
                    let p = sigmoid(x.iter().zip(&weights).map(|(a, b)| a * b).sum::<f64>() + bias);
                    let error = f64::from(*y) - p;
                    bias += lr * error;
                    for (j, (w, x)) in weights.iter_mut().zip(x).enumerate() {
                        if !masked_coordinates.contains(&j) {
                            *w += lr * (error * x - binary_l2_weight_decay * *w);
                        }
                    }
                }
                (TargetLabel::Choice(target), sdm_core::DecisionSpec::Choice { options, .. })
                    if task == "choice" =>
                {
                    let context = &prepared.context;
                    let ans_w = answerability_weights.as_mut().unwrap();
                    let ans_b = answerability_bias.as_mut().unwrap();
                    let p_answerable = sigmoid(
                        context
                            .iter()
                            .zip(ans_w.iter())
                            .map(|(x, w)| x * w)
                            .sum::<f64>()
                            + *ans_b,
                    );
                    let answer_error = f64::from(target.is_some()) - p_answerable;
                    *ans_b += lr * answer_error;
                    for (w, x) in ans_w.iter_mut().zip(context.iter()) {
                        *w += lr * answer_error * x;
                    }
                    if target.is_none() {
                        continue;
                    }
                    let xs = &prepared.options;
                    let scores: Vec<_> = xs
                        .iter()
                        .map(|x| x.iter().zip(&weights).map(|(a, b)| a * b).sum::<f64>() + bias)
                        .collect();
                    let max = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                    let exps: Vec<_> = scores.iter().map(|s| (s - max).exp()).collect();
                    let sum = exps.iter().sum::<f64>();
                    let mut gradient = vec![0.0; weights.len()];
                    let mut bias_gradient = 0.0;
                    for ((option, x), exp) in options.iter().zip(xs).zip(exps) {
                        let p = exp / sum;
                        let desired =
                            target.as_ref().is_some_and(|target| option.id == *target) as u8 as f64;
                        let error = desired - p;
                        bias_gradient += error;
                        for (g, x) in gradient.iter_mut().zip(x) {
                            *g += error * x;
                        }
                    }
                    bias += lr * bias_gradient;
                    for (w, g) in weights.iter_mut().zip(gradient) {
                        *w += lr * g;
                    }
                }
                (
                    TargetLabel::Score(y),
                    sdm_core::DecisionSpec::Score {
                        minimum, maximum, ..
                    },
                ) => {
                    let x = &prepared.standalone;
                    let target = (*y - *minimum) / (*maximum - *minimum);
                    let z = x.iter().zip(&weights).map(|(a, b)| a * b).sum::<f64>() + bias;
                    let p = sigmoid(z);
                    let error = (target - p) * p * (1.0 - p);
                    bias += lr * error;
                    for (w, x) in weights.iter_mut().zip(x) {
                        *w += lr * error * x;
                    }
                }
                _ => {
                    return Err(ExperimentError::Invalid(
                        "label/task mismatch in typed task training".into(),
                    ))
                }
            }
        }
        if quality_diagnostics {
            training_curve.push(TrainingEpochLoss {
                epoch: epoch + 1,
                train_loss: typed_task_loss(
                    train,
                    &train_prepared,
                    task,
                    &weights,
                    bias,
                    answerability_weights.as_deref(),
                    answerability_bias,
                ),
                dev_loss: typed_task_loss(
                    dev,
                    &dev_prepared,
                    task,
                    &weights,
                    bias,
                    answerability_weights.as_deref(),
                    answerability_bias,
                ),
            });
        }
    }
    let mut obs = Vec::new();
    for (dev_index, e) in dev.iter().enumerate() {
        let prepared = &dev_prepared[dev_index];
        match (&e.label, &e.request.spec) {
            (TargetLabel::Binary(y), sdm_core::DecisionSpec::Binary { .. }) if task == "binary" => {
                let x = &prepared.standalone;
                let p = sigmoid(x.iter().zip(&weights).map(|(a, b)| a * b).sum::<f64>() + bias);
                obs.push((p.max(1.0 - p), (p >= 0.5) == *y));
            }
            (TargetLabel::Choice(target), sdm_core::DecisionSpec::Choice { .. })
                if task == "choice" =>
            {
                let context = &prepared.context;
                let confidence = sigmoid(
                    context
                        .iter()
                        .zip(answerability_weights.as_ref().unwrap())
                        .map(|(x, w)| x * w)
                        .sum::<f64>()
                        + answerability_bias.unwrap(),
                );
                obs.push((confidence, target.is_some()));
            }
            (TargetLabel::Score(_), sdm_core::DecisionSpec::Score { .. }) if task == "score" => {}
            _ => {
                return Err(ExperimentError::Invalid(
                    "label/task mismatch in typed dev partition".into(),
                ))
            }
        }
    }
    let mut threshold = if task == "score" {
        0.0
    } else {
        select_threshold(&obs)
    };
    if task == "choice" {
        if let Some(max_no_answer) = obs
            .iter()
            .filter(|(_, answerable)| !*answerable)
            .map(|(confidence, _)| *confidence)
            .max_by(f64::total_cmp)
        {
            threshold = threshold.max((max_no_answer + 0.01).min(1.0));
        }
    }
    Ok((
        encoder,
        weights,
        bias,
        answerability_weights,
        answerability_bias,
        threshold,
        if choice_cross {
            Some(cross_pairs)
        } else {
            None
        },
        if choice_compositional {
            Some(compositional_triples)
        } else {
            None
        },
        masked_coordinates,
        training_curve,
    ))
}

fn bounded_nontext_cross_pairs(
    encoder: &sdm_core::FittedFeatureEncoderV2,
) -> Result<Vec<(usize, usize)>, ExperimentError> {
    let mut coordinates = Vec::new();
    let mut offset = 0usize;
    for field in &encoder.schema.fields {
        let width = match field.value_type {
            sdm_core::FeatureType::Text => 0,
            sdm_core::FeatureType::Category => field.categories.len(),
            _ => 1,
        };
        if width > 0 {
            coordinates.extend(offset..offset + width);
        }
        offset += match field.value_type {
            sdm_core::FeatureType::Text => {
                encoder.text_vocabulary.get(&field.id).map_or(0, Vec::len)
            }
            sdm_core::FeatureType::Category => field.categories.len(),
            _ => 1,
        };
    }
    let count = coordinates
        .len()
        .checked_mul(coordinates.len())
        .ok_or_else(|| ExperimentError::Invalid("cross term count overflow".into()))?;
    if count == 0 || count > 4096 {
        return Err(ExperimentError::Invalid(
            "declared Choice cross terms exceed 4096".into(),
        ));
    }
    Ok(coordinates
        .iter()
        .flat_map(|c| coordinates.iter().map(move |o| (*c, *o)))
        .collect())
}

fn bounded_nontext_choice_triples(
    encoder: &sdm_core::FittedFeatureEncoderV2,
) -> Result<Vec<(usize, usize, usize)>, ExperimentError> {
    let mut coordinates = Vec::new();
    let mut offset = 0usize;
    for field in &encoder.schema.fields {
        let width = match field.value_type {
            sdm_core::FeatureType::Text => 0,
            sdm_core::FeatureType::Category => field.categories.len(),
            _ => 1,
        };
        coordinates.extend(offset..offset + width);
        offset += match field.value_type {
            sdm_core::FeatureType::Text => {
                encoder.text_vocabulary.get(&field.id).map_or(0, Vec::len)
            }
            sdm_core::FeatureType::Category => field.categories.len(),
            _ => 1,
        };
    }
    let count = coordinates
        .len()
        .checked_mul(coordinates.len() + 1)
        .and_then(|n| n.checked_div(2))
        .and_then(|n| n.checked_mul(coordinates.len()))
        .ok_or_else(|| ExperimentError::Invalid("compositional term count overflow".into()))?;
    if count == 0 || count > 4096 {
        return Err(ExperimentError::Invalid(
            "declared Choice compositional terms exceed 4096".into(),
        ));
    }
    let mut triples = Vec::with_capacity(count);
    for (i, a) in coordinates.iter().enumerate() {
        for b in coordinates.iter().skip(i) {
            for o in &coordinates {
                triples.push((*a, *b, *o));
            }
        }
    }
    Ok(triples)
}

pub fn run_semantic(
    spec: &ExperimentSpec,
) -> Result<SemanticExperimentRunManifest, ExperimentError> {
    let task = semantic_task(&spec.architecture)
        .ok_or_else(|| ExperimentError::Invalid("not a typed non-Rank architecture".into()))?;
    let choice_cross = spec.architecture == "typed-choice-cross";
    let choice_compositional = spec.architecture == "typed-choice-compositional";
    if choice_cross && task != "choice" {
        return Err(ExperimentError::Invalid(
            "cross architecture is Choice-only".into(),
        ));
    }
    if spec.epochs == 0
        || spec.epochs > 10_000
        || !spec.learning_rate.is_finite()
        || !(0.0..=1.0).contains(&spec.learning_rate)
        || !spec.binary_l2_weight_decay.is_finite()
        || !(0.0..=1.0).contains(&spec.binary_l2_weight_decay)
    {
        return Err(ExperimentError::Invalid("invalid training bounds".into()));
    }
    let mut raw = Vec::new();
    fs::File::open(&spec.dataset_path)?
        .take((sdm_data::MAX_DATASET_BYTES + 1) as u64)
        .read_to_end(&mut raw)?;
    let bundle: serde_json::Value = serde_json::from_slice(&raw)?;
    let provenance: Provenance = serde_json::from_value(bundle["provenance"].clone())?;
    let examples: Vec<DatasetExample> = serde_json::from_value(bundle["examples"].clone())?;
    if provenance != spec.provenance {
        return Err(ExperimentError::Invalid(
            "config provenance differs from dataset".into(),
        ));
    }
    let ds = validate_dataset(&examples, &provenance)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let mut split_raw = Vec::new();
    fs::File::open(&spec.split_path)?
        .take((MAX_CONFIG_BYTES + 1) as u64)
        .read_to_end(&mut split_raw)?;
    let split: SplitManifest = serde_json::from_slice(&split_raw)?;
    validate_split(&examples, &split, &ds).map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let train = rank_parts(&examples, &split.train)?;
    let dev = rank_parts(&examples, &split.dev)?;
    let test = if spec.evaluate_test {
        rank_parts(&examples, &split.test)?
    } else {
        Vec::new()
    };
    for e in &examples {
        if e.typed_rank_features.is_none()
            || !matches!(
                (task, &e.label),
                ("binary", TargetLabel::Binary(_))
                    | ("choice", TargetLabel::Choice(_))
                    | ("score", TargetLabel::Score(_))
            )
        {
            return Err(ExperimentError::Invalid(
                "dataset must contain one matching typed semantic family".into(),
            ));
        }
    }
    let (
        encoder,
        weights,
        bias,
        answerability_weights,
        answerability_bias,
        threshold,
        cross_pairs,
        compositional_triples,
        binary_masked_coordinates,
        training_curve,
    ) = train_typed_task(
        &train,
        &dev,
        task,
        spec.seed,
        spec.epochs,
        spec.learning_rate,
        choice_cross,
        choice_compositional,
        spec.binary_constant_mask,
        spec.binary_l2_weight_decay,
        spec.seeded_epoch_order,
        spec.quality_diagnostics,
    )?;
    let train_id = digest(&train.to_vec())?;
    let binary_training_policy =
        if task == "binary" && (spec.binary_constant_mask || spec.binary_l2_weight_decay > 0.0) {
            let dimension = encoder
                .dimension()
                .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
            let masked: BTreeSet<_> = binary_masked_coordinates.iter().copied().collect();
            Some(BinaryTrainingPolicy {
                version: "binary-train-coordinate-policy-v1".into(),
                variation_threshold: 0.0,
                masked_coordinates: binary_masked_coordinates.clone(),
                retained_coordinates: (0..dimension).filter(|i| !masked.contains(i)).collect(),
                encoder_fingerprint: encoder.fingerprint.clone(),
                training_fingerprint: train_id.clone(),
                l2_weight_decay: spec.binary_l2_weight_decay,
                intercept: "unpenalized-scalar-bias-v1".into(),
            })
        } else {
            None
        };
    let envelope = if let Some(triples) = compositional_triples {
        sdm_runtime::ArtifactEnvelopeV2::for_typed_choice_compositional(
            &encoder,
            weights,
            bias,
            answerability_weights.unwrap(),
            answerability_bias.unwrap(),
            triples,
            threshold,
            digest(&dev.to_vec())?,
            train_id.clone(),
            format!("{task}:{train_id}"),
            sdm_core::MAX_OPTIONS,
        )
    } else if let Some(pairs) = cross_pairs {
        sdm_runtime::ArtifactEnvelopeV2::for_typed_choice_cross(
            &encoder,
            weights,
            bias,
            answerability_weights.unwrap(),
            answerability_bias.unwrap(),
            pairs,
            threshold,
            digest(&dev.to_vec())?,
            train_id.clone(),
            format!("{task}:{train_id}"),
            sdm_core::MAX_OPTIONS,
        )
    } else {
        sdm_runtime::ArtifactEnvelopeV2::for_typed_task(
            task,
            &encoder,
            weights,
            bias,
            answerability_weights,
            answerability_bias,
            threshold,
            digest(&dev.to_vec())?,
            train_id.clone(),
            format!("{task}:{train_id}"),
            sdm_core::MAX_OPTIONS,
        )
    }
    .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let artifact = serde_json::to_vec(&envelope)?;
    let model_sha = envelope.tensor_payload_sha256.clone();
    let calibration_sha = envelope.calibration_sha256.clone();
    let loaded = load_artifact(&artifact).map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let LoadedArtifact::TypedTaskV2(runtime) = loaded else {
        return Err(ExperimentError::Invalid(
            "typed task artifact did not dispatch".into(),
        ));
    };
    let mut abstentions = 0usize;
    let mut outcomes = Vec::with_capacity(test.len());
    let metrics =
        match task {
            "binary" => {
                let mut truth = Vec::new();
                let mut probabilities = Vec::new();
                for e in &test {
                    let TargetLabel::Binary(y) = e.label else {
                        unreachable!()
                    };
                    truth.push(y);
                    let b = e.typed_rank_features.as_ref().unwrap();
                    let r = runtime
                        .decide_typed(&e.request, b)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
                    if r.answer.is_none() {
                        abstentions += 1;
                    }
                    let probs = runtime
                        .binary_probability(&e.request, b)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
                    probabilities.push(probs);
                    let was_abstained = r.answer.is_none();
                    let nuisance_probabilities = if spec.quality_diagnostics {
                        let base = e.typed_rank_features.as_ref().unwrap();
                        let mut results = BTreeMap::new();
                        for shift in ["load", "text", "combined"] {
                            let mut changed = base.clone();
                            for field in &mut changed.context.fields {
                                if field.id == "load" && matches!(shift, "load" | "combined") {
                                    field.value = Some(sdm_core::FeatureValue::Number(20.0));
                                }
                                if field.id == "note" && matches!(shift, "text" | "combined") {
                                    field.value = Some(sdm_core::FeatureValue::Text(
                                        "quartz nebula unseen".into(),
                                    ));
                                }
                            }
                            results.insert(
                                shift.into(),
                                runtime
                                    .binary_probability(&e.request, &changed)
                                    .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
                            );
                        }
                        Some(results)
                    } else {
                        None
                    };
                    outcomes.push(SemanticCaseOutcome {
                        case_id: e.case_id.clone(),
                        leakage_group: e.leakage_group.clone(),
                        target: serde_json::json!(y),
                        prediction: if spec.quality_diagnostics && was_abstained {
                            serde_json::Value::Null
                        } else {
                            serde_json::json!(probs >= 0.5)
                        },
                        score: Some(probs),
                        raw_probabilities: spec.quality_diagnostics.then_some(vec![probs]),
                        raw_logits: None,
                        answerability_probability: None,
                        nuisance_probabilities,
                        abstained: spec.quality_diagnostics && was_abstained,
                    });
                }
                SemanticMetrics::Binary(
                    sdm_eval::evaluate_binary(&truth, &probabilities, 0.5)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
                )
            }
            "choice" => {
                let mut truth = Vec::new();
                let mut probs = Vec::new();
                for e in &test {
                    let TargetLabel::Choice(target) = &e.label else {
                        unreachable!()
                    };
                    let b = e.typed_rank_features.as_ref().unwrap();
                    let r = runtime
                        .decide_typed(&e.request, b)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
                    if r.answer.is_none() {
                        abstentions += 1;
                    }
                    if let Some(target) = target {
                        let sdm_core::DecisionSpec::Choice { options, .. } = &e.request.spec else {
                            unreachable!()
                        };
                        truth.push(options.iter().position(|o| &o.id == target).ok_or_else(
                            || ExperimentError::Invalid("choice target outside options".into()),
                        )?);
                        probs.push(
                            runtime
                                .choice_probabilities(&e.request, b)
                                .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
                        );
                    }
                    let raw_probs = if spec.quality_diagnostics {
                        Some(
                            runtime
                                .choice_probabilities(&e.request, b)
                                .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
                        )
                    } else {
                        None
                    };
                    let raw_logits = if spec.quality_diagnostics {
                        Some(
                            runtime
                                .choice_logits(&e.request, b)
                                .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
                        )
                    } else {
                        None
                    };
                    let answerability = if spec.quality_diagnostics {
                        Some(
                            runtime
                                .choice_answerability_probability(&e.request, b)
                                .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
                        )
                    } else {
                        None
                    };
                    let abstained = r.answer.is_none();
                    let predicted = match r.answer {
                        Some(sdm_core::DecisionAnswer::Choice { option_id, .. }) => {
                            serde_json::Value::String(option_id)
                        }
                        _ => serde_json::Value::Null,
                    };
                    outcomes.push(SemanticCaseOutcome {
                        case_id: e.case_id.clone(),
                        leakage_group: e.leakage_group.clone(),
                        target: serde_json::json!(target),
                        prediction: predicted,
                        score: None,
                        raw_probabilities: raw_probs,
                        raw_logits,
                        answerability_probability: answerability,
                        nuisance_probabilities: None,
                        abstained: spec.quality_diagnostics && abstained,
                    });
                }
                SemanticMetrics::Choice(
                    sdm_eval::evaluate_choice(&truth, &probs)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?,
                )
            }
            "score" => {
                let mut scored = Vec::new();
                for e in &test {
                    let TargetLabel::Score(y) = e.label else {
                        unreachable!()
                    };
                    let b = e.typed_rank_features.as_ref().unwrap();
                    let r = runtime
                        .decide_typed(&e.request, b)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
                    if let Some(sdm_core::DecisionAnswer::Score { value, .. }) = r.answer {
                        let sdm_core::DecisionSpec::Score {
                            minimum, maximum, ..
                        } = &e.request.spec
                        else {
                            unreachable!()
                        };
                        if !y.is_finite()
                            || !value.is_finite()
                            || y < *minimum
                            || y > *maximum
                            || value < *minimum
                            || value > *maximum
                        {
                            return Err(ExperimentError::Invalid(
                                "score outside per-example rubric".into(),
                            ));
                        }
                        scored.push((y, value));
                        outcomes.push(SemanticCaseOutcome {
                            case_id: e.case_id.clone(),
                            leakage_group: e.leakage_group.clone(),
                            target: serde_json::json!(y),
                            prediction: serde_json::json!(value),
                            score: Some(value),
                            raw_probabilities: None,
                            raw_logits: None,
                            answerability_probability: None,
                            nuisance_probabilities: None,
                            abstained: false,
                        });
                    } else {
                        abstentions += 1;
                        outcomes.push(SemanticCaseOutcome {
                            case_id: e.case_id.clone(),
                            leakage_group: e.leakage_group.clone(),
                            target: serde_json::json!(y),
                            prediction: serde_json::Value::Null,
                            score: None,
                            raw_probabilities: None,
                            raw_logits: None,
                            answerability_probability: None,
                            nuisance_probabilities: None,
                            abstained: true,
                        });
                    }
                }
                let mut squared = 0.0;
                let mut absolute = 0.0;
                for (y, p) in &scored {
                    absolute += (y - p).abs();
                    squared += (y - p).powi(2);
                }
                SemanticMetrics::Score(sdm_eval::ScoreMetrics {
                    count: scored.len(),
                    mae: (!scored.is_empty()).then_some(absolute / scored.len() as f64),
                    rmse: (!scored.is_empty()).then_some((squared / scored.len() as f64).sqrt()),
                })
            }
            _ => unreachable!(),
        };
    let dev_diagnostics = if spec.evaluate_test || !spec.quality_diagnostics {
        None
    } else {
        let mut values = BTreeMap::new();
        match task {
            "binary" => {
                let mut brier = 0.0;
                let mut note_delta: f64 = 0.0;
                let mut load_delta: f64 = 0.0;
                let mut combined_delta: f64 = 0.0;
                let mut causal_delta = 0.0;
                for e in &dev {
                    let TargetLabel::Binary(y) = e.label else {
                        unreachable!()
                    };
                    let binding = e.typed_rank_features.as_ref().unwrap();
                    let p = runtime
                        .binary_probability(&e.request, binding)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
                    brier += (p - f64::from(y)).powi(2);
                    let shifted =
                        |change_note: bool, change_load: bool| -> Result<f64, ExperimentError> {
                            let mut changed = binding.clone();
                            for field in &mut changed.context.fields {
                                if change_note && field.id == "note" {
                                    field.value = Some(sdm_core::FeatureValue::Text(
                                        "quartz nebula unseen m014".into(),
                                    ));
                                }
                                if change_load && field.id == "load" {
                                    field.value = Some(sdm_core::FeatureValue::Number(20.0));
                                }
                            }
                            runtime
                                .binary_probability(&e.request, &changed)
                                .map_err(|e| ExperimentError::Invalid(e.to_string()))
                        };
                    note_delta = note_delta.max((shifted(true, false)? - p).abs());
                    load_delta = load_delta.max((shifted(false, true)? - p).abs());
                    combined_delta = combined_delta.max((shifted(true, true)? - p).abs());
                    let mut flipped = binding.clone();
                    for field in &mut flipped.context.fields {
                        if field.id == "active" {
                            if let Some(sdm_core::FeatureValue::Boolean(active)) =
                                field.value.as_mut()
                            {
                                *active = !*active;
                            }
                        }
                    }
                    causal_delta += (runtime
                        .binary_probability(&e.request, &flipped)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?
                        - p)
                        .abs();
                }
                let n = dev.len() as f64;
                values.insert("dev_brier".into(), brier / n);
                values.insert("dev_note_only_max_abs_probability_delta".into(), note_delta);
                values.insert("dev_load_only_max_abs_probability_delta".into(), load_delta);
                values.insert(
                    "dev_combined_max_abs_probability_delta".into(),
                    combined_delta,
                );
                values.insert(
                    "dev_active_flip_mean_abs_probability_delta".into(),
                    causal_delta / n,
                );
            }
            "choice" => {
                let mut answerable = 0usize;
                let mut correct = 0usize;
                let mut no_answer = 0usize;
                let mut no_answer_correct = 0usize;
                let mut covered = 0usize;
                let mut pair_correct = BTreeMap::<String, Vec<bool>>::new();
                for e in &dev {
                    let TargetLabel::Choice(target) = &e.label else {
                        unreachable!()
                    };
                    let binding = e.typed_rank_features.as_ref().unwrap();
                    let confidence = runtime
                        .choice_answerability_probability(&e.request, binding)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
                    let response = runtime
                        .decide_typed(&e.request, binding)
                        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
                    if let Some(target) = target {
                        answerable += 1;
                        if response.answer.is_some() {
                            covered += 1;
                        }
                        let logits = runtime
                            .choice_logits(&e.request, binding)
                            .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
                        let sdm_core::DecisionSpec::Choice { options, .. } = &e.request.spec else {
                            unreachable!()
                        };
                        let best = logits
                            .iter()
                            .enumerate()
                            .max_by(|a, b| a.1.total_cmp(b.1))
                            .map(|(i, _)| i)
                            .unwrap();
                        let ok = options[best].id == *target;
                        correct += usize::from(ok);
                        if let Some(pair) = &e.counterfactual_pair {
                            pair_correct.entry(pair.clone()).or_default().push(ok);
                        }
                    } else {
                        no_answer += 1;
                        if confidence < runtime.abstention_threshold() {
                            no_answer_correct += 1;
                        }
                    }
                }
                let pairs = pair_correct
                    .values()
                    .filter(|correct| correct.len() == 2)
                    .collect::<Vec<_>>();
                let both = pairs.iter().filter(|pair| pair.iter().all(|x| *x)).count();
                values.insert(
                    "dev_answerable_accuracy".into(),
                    correct as f64 / answerable.max(1) as f64,
                );
                values.insert(
                    "dev_answerable_coverage".into(),
                    covered as f64 / answerable.max(1) as f64,
                );
                values.insert(
                    "dev_no_answer_recall".into(),
                    no_answer_correct as f64 / no_answer.max(1) as f64,
                );
                values.insert("dev_counterfactual_pairs".into(), pairs.len() as f64);
                values.insert(
                    "dev_counterfactual_correct_on_both".into(),
                    both as f64 / pairs.len().max(1) as f64,
                );
            }
            _ => {}
        }
        Some(values)
    };
    let mut report = SemanticExperimentRunManifest {
        dataset_sha256: ds,
        split_fingerprint: split.fingerprint.clone(),
        semantic: task.into(),
        seed: spec.seed,
        train_ids: split.train,
        dev_ids: split.dev,
        test_ids: split.test,
        model_sha256: model_sha,
        calibration_sha256: calibration_sha,
        artifact_sha256: format!("sha256:{:x}", Sha256::digest(&artifact)),
        report_sha256: String::new(),
        metrics,
        abstentions,
        outcomes,
        binary_masked_coordinates,
        binary_training_policy,
        training_curve,
        verdict: if spec.evaluate_test {
            "synthetic-mechanics-only"
        } else {
            "train-dev-only"
        }
        .into(),
        test_evaluation_performed: spec.evaluate_test,
        dev_diagnostics,
    };
    report.report_sha256 = if let Some(diagnostics) = &report.dev_diagnostics {
        digest(&(
            &report.dataset_sha256,
            &report.split_fingerprint,
            &report.semantic,
            &report.model_sha256,
            &report.calibration_sha256,
            &report.metrics,
            &report.abstentions,
            &report.outcomes,
            &report.binary_masked_coordinates,
            &report.binary_training_policy,
            &report.training_curve,
            diagnostics,
        ))?
    } else if report.binary_training_policy.is_none()
        && report.binary_masked_coordinates.is_empty()
        && report.training_curve.is_empty()
    {
        digest(&(
            &report.dataset_sha256,
            &report.split_fingerprint,
            &report.semantic,
            &report.model_sha256,
            &report.calibration_sha256,
            &report.metrics,
            &report.abstentions,
            &report.outcomes,
        ))?
    } else if report.binary_training_policy.is_none() && report.binary_masked_coordinates.is_empty()
    {
        digest(&(
            &report.dataset_sha256,
            &report.split_fingerprint,
            &report.semantic,
            &report.model_sha256,
            &report.calibration_sha256,
            &report.metrics,
            &report.abstentions,
            &report.outcomes,
            &report.training_curve,
        ))?
    } else {
        digest(&(
            &report.dataset_sha256,
            &report.split_fingerprint,
            &report.semantic,
            &report.model_sha256,
            &report.calibration_sha256,
            &report.metrics,
            &report.abstentions,
            &report.outcomes,
            &report.binary_masked_coordinates,
            &report.binary_training_policy,
            &report.training_curve,
        ))?
    };
    atomic_write(&spec.artifact_path, &artifact)?;
    atomic_write(&spec.report_path, &serde_json::to_vec_pretty(&report)?)?;
    Ok(report)
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
            digest(&dev.to_vec())?,
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
            LoadedArtifact::TypedTaskV2(rt) => rt.decide_typed(
                &e.request,
                e.typed_rank_features.as_ref().ok_or_else(|| {
                    ExperimentError::Invalid("typed task features absent at inference".into())
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
    let outcomes = test_examples
        .iter()
        .zip(&predictions)
        .map(|(example, prediction)| {
            let TargetLabel::Rank { relevance, .. } = &example.label else {
                unreachable!()
            };
            RankCaseOutcome {
                case_id: example.case_id.clone(),
                leakage_group: example.leakage_group.clone(),
                relevance: relevance.clone(),
                prediction: prediction.candidates.clone(),
            }
        })
        .collect::<Vec<_>>();
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
        outcomes,
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
        &report.outcomes,
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
            quality_diagnostics: false,
            seeded_epoch_order: false,
            binary_constant_mask: false,
            binary_l2_weight_decay: 0.0,
            evaluate_test: true,
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
    fn seeded_epoch_order_is_repeatable_and_manifest_order_is_legacy_default() {
        let ordered = training_order(20, 14014, 0, false);
        assert_eq!(ordered, (0..20).collect::<Vec<_>>());
        let a = training_order(20, 14014, 3, true);
        assert_eq!(a, training_order(20, 14014, 3, true));
        assert_ne!(a, training_order(20, 14015, 3, true));
        assert_ne!(a, training_order(20, 14014, 4, true));
    }
    #[test]
    fn opt_in_quality_reports_include_loss_curves_final_decisions_and_nuisance_probes() {
        let root = temp_root();
        for task in ["binary", "choice"] {
            let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../fixtures");
            let dataset = dir
                .join(format!("synthetic-{task}-typed-v1.json"))
                .display()
                .to_string();
            let split = dir
                .join(format!("synthetic-{task}-typed-v1.split.json"))
                .display()
                .to_string();
            let raw: serde_json::Value = serde_json::from_str(if task == "binary" {
                include_str!("../../../fixtures/synthetic-binary-typed-v1.json")
            } else {
                include_str!("../../../fixtures/synthetic-choice-typed-v1.json")
            })
            .unwrap();
            let provenance: Provenance = serde_json::from_value(raw["provenance"].clone()).unwrap();
            let mut cfg = spec(
                &root,
                &format!("typed-{task}"),
                &dataset,
                &split,
                task,
                provenance,
            );
            cfg.epochs = 2;
            cfg.quality_diagnostics = true;
            cfg.seeded_epoch_order = true;
            let report = run_semantic(&cfg).unwrap();
            assert_eq!(report.training_curve.len(), 2);
            assert!(report
                .training_curve
                .iter()
                .all(|row| row.train_loss.is_finite() && row.dev_loss.is_finite()));
            assert!(report
                .outcomes
                .iter()
                .all(|row| row.raw_probabilities.is_some()));
            if task == "binary" {
                assert!(report.outcomes.iter().all(|row| row
                    .nuisance_probabilities
                    .as_ref()
                    .is_some_and(|m| m.len() == 3)));
            } else {
                assert!(
                    report
                        .outcomes
                        .iter()
                        .all(|row| row.raw_logits.is_some()
                            && row.answerability_probability.is_some())
                );
            }
        }
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn diagonal_choice_head_cannot_represent_active_candidate_kind_flip() {
        // Context [active, available, choice-category, yes-category, no-category].
        // Each candidate shares active/available and changes only its kind.
        let diagonal_delta = |active: f64| {
            let context = [active, 1.0, 1.0, 0.0, 0.0];
            let yes = [active, 1.0, 0.0, 1.0, 0.0];
            let no = [active, 1.0, 0.0, 0.0, 1.0];
            let vector = |item: &[f64]| {
                context
                    .iter()
                    .copied()
                    .chain(item.iter().copied())
                    .chain(context.iter().zip(item).map(|(a, b)| a * b))
                    .collect::<Vec<_>>()
            };
            let weights: Vec<f64> = (0..vector(&yes).len())
                .map(|i| (i as f64 + 1.0) / 10.0)
                .collect();
            let dot = |x: Vec<f64>| x.iter().zip(&weights).map(|(a, b)| a * b).sum::<f64>();
            dot(vector(&yes)) - dot(vector(&no))
        };
        let inactive_delta = diagonal_delta(0.0);
        let active_delta = diagonal_delta(1.0);
        assert!((inactive_delta - active_delta).abs() < 1e-12);

        // The declared (active, candidate-kind) crosses can encode the rule.
        let crossed_delta = |active: f64| active * 1.0 - active * 0.0 - (1.0 - active) * 1.0;
        assert!(crossed_delta(0.0) < 0.0);
        assert!(crossed_delta(1.0) > 0.0);
        // Truth table includes both availability states; answerability is a
        // separate context head and does not change conditional option scores.
        for available in [false, true] {
            for active in [false, true] {
                let target_is_yes = active;
                assert_eq!(crossed_delta(f64::from(active)) > 0.0, target_is_yes);
                let is_answerable = available;
                assert_eq!(is_answerable, available);
            }
        }
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

    #[test]
    fn binary_choice_score_train_reload_infer_and_evaluate() {
        let root = temp_root();
        for task in ["binary", "choice", "score"] {
            let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../fixtures");
            let dataset = dir
                .join(format!("synthetic-{task}-typed-v1.json"))
                .display()
                .to_string();
            let split = dir
                .join(format!("synthetic-{task}-typed-v1.split.json"))
                .display()
                .to_string();
            let raw: serde_json::Value = serde_json::from_str(match task {
                "binary" => include_str!("../../../fixtures/synthetic-binary-typed-v1.json"),
                "choice" => include_str!("../../../fixtures/synthetic-choice-typed-v1.json"),
                _ => include_str!("../../../fixtures/synthetic-score-typed-v1.json"),
            })
            .unwrap();
            let provenance: Provenance = serde_json::from_value(raw["provenance"].clone()).unwrap();
            let mut cfg = spec(
                &root,
                &format!("typed-{task}"),
                &dataset,
                &split,
                task,
                provenance,
            );
            cfg.epochs = 120;
            cfg.learning_rate = 0.2;
            let report = run_semantic(&cfg).unwrap();
            assert_eq!(report.semantic, task);
            assert_eq!(report.verdict, "synthetic-mechanics-only");
            assert!(report.test_ids.len() >= 4);
            let bytes = fs::read(root.join(format!("{task}.artifact.json"))).unwrap();
            assert!(matches!(
                load_artifact(&bytes).unwrap(),
                LoadedArtifact::TypedTaskV2(_)
            ));
        }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn m014_policies_emit_mask_provenance_and_compositional_artifacts() {
        let root = temp_root();
        let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../fixtures");
        let bin_path = dir.join("synthetic-binary-typed-v1.json");
        let bin_split = dir.join("synthetic-binary-typed-v1.split.json");
        let bin_raw: serde_json::Value = serde_json::from_str(include_str!(
            "../../../fixtures/synthetic-binary-typed-v1.json"
        ))
        .unwrap();
        let bin_provenance: Provenance =
            serde_json::from_value(bin_raw["provenance"].clone()).unwrap();
        let mut bin = spec(
            &root,
            "typed-binary",
            &bin_path.display().to_string(),
            &bin_split.display().to_string(),
            "m014-binary",
            bin_provenance,
        );
        bin.binary_constant_mask = true;
        let binary = run_semantic(&bin).unwrap();
        assert!(!binary.binary_masked_coordinates.is_empty());
        let policy = binary.binary_training_policy.as_ref().unwrap();
        assert_eq!(policy.version, "binary-train-coordinate-policy-v1");
        assert_eq!(policy.intercept, "unpenalized-scalar-bias-v1");
        assert!(policy
            .masked_coordinates
            .iter()
            .all(|i| !policy.retained_coordinates.contains(i)));
        assert!(policy.training_fingerprint.starts_with("sha256:"));

        let choice_path = dir.join("synthetic-choice-typed-v1.json");
        let choice_split = dir.join("synthetic-choice-typed-v1.split.json");
        let choice_raw: serde_json::Value = serde_json::from_str(include_str!(
            "../../../fixtures/synthetic-choice-typed-v1.json"
        ))
        .unwrap();
        let choice_provenance: Provenance =
            serde_json::from_value(choice_raw["provenance"].clone()).unwrap();
        let mut choice = spec(
            &root,
            "typed-choice-compositional",
            &choice_path.display().to_string(),
            &choice_split.display().to_string(),
            "m014-choice",
            choice_provenance,
        );
        choice.epochs = 5;
        let result = run_semantic(&choice).unwrap();
        assert_eq!(result.semantic, "choice");
        let bytes = fs::read(root.join("m014-choice.artifact.json")).unwrap();
        let envelope: sdm_runtime::ArtifactEnvelopeV2 = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(envelope.architecture, "sdm-typed-choice-compositional-v1");
        assert!(matches!(
            load_artifact(&bytes).unwrap(),
            LoadedArtifact::TypedTaskV2(_)
        ));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn semantic_test_only_mutations_leave_model_and_calibration_unchanged() {
        let root = temp_root();
        for task in ["binary", "choice", "score"] {
            let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../fixtures");
            let dataset = dir
                .join(format!("synthetic-{task}-typed-v1.json"))
                .display()
                .to_string();
            let split_path = dir
                .join(format!("synthetic-{task}-typed-v1.split.json"))
                .display()
                .to_string();
            let raw = match task {
                "binary" => include_str!("../../../fixtures/synthetic-binary-typed-v1.json"),
                "choice" => include_str!("../../../fixtures/synthetic-choice-typed-v1.json"),
                _ => include_str!("../../../fixtures/synthetic-score-typed-v1.json"),
            };
            let mut bundle: Bundle = serde_json::from_str(raw).unwrap();
            let split: SplitManifest =
                serde_json::from_slice(&fs::read(&split_path).unwrap()).unwrap();
            let mut cfg = spec(
                &root,
                &format!("typed-{task}"),
                &dataset,
                &split_path,
                &format!("{task}-base"),
                bundle.provenance.clone(),
            );
            cfg.epochs = 120;
            cfg.learning_rate = 0.2;
            let baseline = run_semantic(&cfg).unwrap();
            let test_id = &split.test[0];
            let example = bundle
                .examples
                .iter_mut()
                .find(|e| &e.case_id == test_id)
                .unwrap();
            match &mut example.label {
                TargetLabel::Binary(v) => *v = !*v,
                TargetLabel::Choice(v) => {
                    *v = Some(
                        if v.as_deref() == Some("yes") {
                            "no"
                        } else {
                            "yes"
                        }
                        .into(),
                    )
                }
                TargetLabel::Score(v) => {
                    *v = if *v < 5.0 {
                        (*v + 0.25).min(5.0)
                    } else {
                        (*v - 0.25).max(1.0)
                    }
                }
                _ => unreachable!(),
            }
            let binding = example.typed_rank_features.as_mut().unwrap();
            let load = binding
                .context
                .fields
                .iter_mut()
                .find(|f| f.id == "load")
                .unwrap();
            load.value = Some(sdm_core::FeatureValue::Number(1.0e300));
            let changed_hash = validate_dataset(&bundle.examples, &bundle.provenance).unwrap();
            let mut changed_split = split;
            changed_split.dataset_sha256 = changed_hash;
            changed_split.fingerprint.clear();
            changed_split.fingerprint = digest(&changed_split).unwrap();
            let changed_data = root.join(format!("{task}-mutated.json"));
            let changed_split_path = root.join(format!("{task}-mutated-split.json"));
            fs::write(&changed_data, serde_json::to_vec(&bundle).unwrap()).unwrap();
            fs::write(
                &changed_split_path,
                serde_json::to_vec(&changed_split).unwrap(),
            )
            .unwrap();
            cfg.dataset_path = changed_data.display().to_string();
            cfg.split_path = changed_split_path.display().to_string();
            cfg.artifact_path = root
                .join(format!("{task}-mutated.artifact.json"))
                .display()
                .to_string();
            cfg.report_path = root
                .join(format!("{task}-mutated.report.json"))
                .display()
                .to_string();
            let mutated = run_semantic(&cfg).unwrap();
            assert_eq!(baseline.model_sha256, mutated.model_sha256);
            assert_eq!(baseline.calibration_sha256, mutated.calibration_sha256);
        }
        fs::remove_dir_all(root).unwrap();
    }
}
