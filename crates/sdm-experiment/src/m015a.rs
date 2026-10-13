//! M015a DEV-only final-action replay. Additive sidecar; does not alter
//! historical `run_semantic` diagnostics or frozen reports.
//!
//! Reads the M015 typed dataset/split, a frozen Choice artifact (read-only),
//! and the source corpus JSONL for provenance (available flag, satisfying
//! counts, pair_type, family, rule, context/semantics digests). Runs actual
//! `TypedTaskRuntime::decide_typed` + conditional probabilities + answerability
//! for every DEV row, builds [`sdm_eval::choice_final_v2::ChoiceFinalCase`]s,
//! evaluates the v2 contract, and writes an atomic uniquely-named sidecar.

use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::Read,
    path::Path,
};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use sdm_data::{validate_dataset, validate_split, DatasetExample, Provenance, SplitManifest};
use sdm_eval::choice_final_v2::{
    self, ChoiceFinalCase, ChoiceFinalReportV2, NoAnswerOrigin, CONTRACT_METHOD,
};
use sdm_runtime::load_artifact;

use crate::ExperimentError;

fn file_sha256(path: &str) -> Result<String, ExperimentError> {
    let bytes = fs::read(path)?;
    Ok(format!("sha256:{:x}", Sha256::digest(&bytes)))
}

fn canonical_sha(value: &serde_json::Value) -> String {
    // serde_json::Map is BTreeMap-backed, so to_vec is canonical (sorted keys).
    format!(
        "sha256:{:x}",
        Sha256::digest(serde_json::to_vec(value).unwrap_or_default())
    )
}

fn atomic_write_new(path: &str, bytes: &[u8]) -> Result<(), ExperimentError> {
    let target = Path::new(path);
    if target.exists() {
        return Err(ExperimentError::Invalid(format!(
            "refusing to overwrite {path}"
        )));
    }
    let parent = target
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    fs::create_dir_all(parent)?;
    let tmp = parent.join(format!(
        ".sdm-m015a-{}-{}.tmp",
        std::process::id(),
        Sha256::digest(path.as_bytes())[0]
    ));
    use std::io::Write;
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&tmp)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    let _: serde_json::Value = serde_json::from_slice(bytes)?;
    fs::hard_link(&tmp, target)?;
    fs::remove_file(tmp)?;
    Ok(())
}

/// DEV-only replay config. Denies training fields; fails closed on unknown
/// keys, missing SHAs, or non-DEV partitions.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct M015aReplaySpec {
    pub dataset_path: String,
    pub split_path: String,
    pub artifact_path: String,
    pub corpus_train_path: String,
    pub corpus_dev_path: String,
    pub generator_path: String,
    pub task_spec_path: String,
    pub output_path: String,
    pub expected_artifact_sha256: String,
    pub expected_dataset_sha256: String,
    pub expected_split_fingerprint: String,
    pub expected_generator_sha256: String,
    pub expected_task_spec_sha256: String,
    pub expected_corpus_train_sha256: String,
    pub expected_corpus_dev_sha256: String,
    pub architecture: String,
    pub provenance: Provenance,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct M015aSidecar {
    pub schema: String,
    pub schema_version: u16,
    pub contract: String,
    pub architecture: String,
    pub partition: String,
    pub dataset_sha256: String,
    pub split_fingerprint: String,
    pub artifact_sha256: String,
    pub calibration_sha256: String,
    pub artifact_architecture: String,
    pub generator_sha256: String,
    pub task_spec_sha256: String,
    pub corpus_train_sha256: String,
    pub corpus_dev_sha256: String,
    pub dataset_file_sha256: String,
    pub split_file_sha256: String,
    pub source_commit: String,
    pub train_rows: usize,
    pub train_groups: usize,
    pub dev_rows: usize,
    pub dev_groups: usize,
    pub dev_answerable_rows: usize,
    pub dev_no_answer_rows: usize,
    pub dev_nuisance_pairs: usize,
    pub dev_causal_pairs: usize,
    pub report: ChoiceFinalReportV2,
    /// Legacy mixed-metric values from the frozen report for explicit
    /// before/after comparison (read-only, not recomputed).
    pub legacy_comparison: BTreeMap<String, serde_json::Value>,
    pub bootstrap: BTreeMap<String, serde_json::Value>,
    pub report_sha256: String,
}

fn validate_sha_format(value: &str, what: &str) -> Result<(), ExperimentError> {
    if !value.starts_with("sha256:") || value.len() != 71 {
        return Err(ExperimentError::Invalid(format!(
            "{what} must be sha256:<64 hex>"
        )));
    }
    if !value[7..].chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(ExperimentError::Invalid(format!("{what} contains non-hex")));
    }
    Ok(())
}

fn load_corpus(path: &str) -> Result<Vec<serde_json::Value>, ExperimentError> {
    let text = fs::read_to_string(path)?;
    let mut rows = Vec::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let v: serde_json::Value = serde_json::from_str(line)?;
        rows.push(v);
    }
    Ok(rows)
}

pub fn run_m015a_replay(spec: &M015aReplaySpec) -> Result<M015aSidecar, ExperimentError> {
    for (v, what) in [
        (&spec.expected_artifact_sha256, "expected_artifact_sha256"),
        (&spec.expected_dataset_sha256, "expected_dataset_sha256"),
        (&spec.expected_generator_sha256, "expected_generator_sha256"),
        (&spec.expected_task_spec_sha256, "expected_task_spec_sha256"),
        (
            &spec.expected_corpus_train_sha256,
            "expected_corpus_train_sha256",
        ),
        (
            &spec.expected_corpus_dev_sha256,
            "expected_corpus_dev_sha256",
        ),
    ] {
        validate_sha_format(v, what)?;
    }
    validate_sha_format(
        &spec.expected_split_fingerprint,
        "expected_split_fingerprint",
    )?;
    if spec.architecture != "typed-choice"
        && spec.architecture != "typed-choice-cross"
        && spec.architecture != "typed-choice-compositional"
    {
        return Err(ExperimentError::Invalid(
            "m015a replay supports typed-choice heads only".into(),
        ));
    }
    // Verify file SHAs before any inference.
    let actual_artifact_sha = file_sha256(&spec.artifact_path)?;
    if actual_artifact_sha != spec.expected_artifact_sha256 {
        return Err(ExperimentError::Invalid(format!(
            "artifact SHA mismatch: expected {} got {actual_artifact_sha}",
            spec.expected_artifact_sha256
        )));
    }
    let actual_generator_sha = file_sha256(&spec.generator_path)?;
    if actual_generator_sha != spec.expected_generator_sha256 {
        return Err(ExperimentError::Invalid(format!(
            "generator SHA mismatch: expected {} got {actual_generator_sha}",
            spec.expected_generator_sha256
        )));
    }
    let actual_spec_sha = file_sha256(&spec.task_spec_path)?;
    if actual_spec_sha != spec.expected_task_spec_sha256 {
        return Err(ExperimentError::Invalid(format!(
            "task-spec SHA mismatch: expected {} got {actual_spec_sha}",
            spec.expected_task_spec_sha256
        )));
    }
    // Corpus raw bytes SHAs (hex without prefix in manifest; accept both).
    let train_bytes = fs::read(&spec.corpus_train_path)?;
    let dev_bytes = fs::read(&spec.corpus_dev_path)?;
    let actual_train_hex = format!("{:x}", Sha256::digest(&train_bytes));
    let actual_dev_hex = format!("{:x}", Sha256::digest(&dev_bytes));
    let expected_train_hex = spec
        .expected_corpus_train_sha256
        .strip_prefix("sha256:")
        .unwrap_or(&spec.expected_corpus_train_sha256);
    let expected_dev_hex = spec
        .expected_corpus_dev_sha256
        .strip_prefix("sha256:")
        .unwrap_or(&spec.expected_corpus_dev_sha256);
    if actual_train_hex != expected_train_hex {
        return Err(ExperimentError::Invalid(format!(
            "corpus train SHA mismatch: expected {expected_train_hex} got {actual_train_hex}"
        )));
    }
    if actual_dev_hex != expected_dev_hex {
        return Err(ExperimentError::Invalid(format!(
            "corpus dev SHA mismatch: expected {expected_dev_hex} got {actual_dev_hex}"
        )));
    }

    // Load typed dataset + split (read-only, validated).
    let mut raw = Vec::new();
    fs::File::open(&spec.dataset_path)?
        .take((sdm_data::MAX_DATASET_BYTES + 1) as u64)
        .read_to_end(&mut raw)?;
    let bundle: serde_json::Value = serde_json::from_slice(&raw)?;
    let provenance: Provenance = serde_json::from_value(bundle["provenance"].clone())?;
    if provenance != spec.provenance {
        return Err(ExperimentError::Invalid(
            "config provenance differs from dataset".into(),
        ));
    }
    let examples: Vec<DatasetExample> = serde_json::from_value(bundle["examples"].clone())?;
    let dataset_sha = validate_dataset(&examples, &provenance)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    if dataset_sha != spec.expected_dataset_sha256 {
        return Err(ExperimentError::Invalid(format!(
            "dataset SHA mismatch: expected {} got {dataset_sha}",
            spec.expected_dataset_sha256
        )));
    }
    let mut split_raw = Vec::new();
    fs::File::open(&spec.split_path)?
        .take((crate::MAX_CONFIG_BYTES + 1) as u64)
        .read_to_end(&mut split_raw)?;
    let split: SplitManifest = serde_json::from_slice(&split_raw)?;
    validate_split(&examples, &split, &dataset_sha)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    if split.fingerprint != spec.expected_split_fingerprint {
        return Err(ExperimentError::Invalid(format!(
            "split fingerprint mismatch: expected {} got {}",
            spec.expected_split_fingerprint, split.fingerprint
        )));
    }
    if !split.test.is_empty() {
        return Err(ExperimentError::Invalid(
            "m015a replay requires empty test partition (train-dev-only)".into(),
        ));
    }

    // Load artifact read-only; SHA already verified.
    let artifact_bytes = fs::read(&spec.artifact_path)?;
    if artifact_bytes.len() > sdm_runtime::V2_MAX_ARTIFACT_BYTES {
        return Err(ExperimentError::Invalid("artifact exceeds 16MiB".into()));
    }
    let loaded =
        load_artifact(&artifact_bytes).map_err(|e| ExperimentError::Invalid(e.to_string()))?;
    let sdm_runtime::LoadedArtifact::TypedTaskV2(runtime) = loaded else {
        return Err(ExperimentError::Invalid(
            "m015a replay requires typed Choice artifact".into(),
        ));
    };
    let envelope: sdm_runtime::ArtifactEnvelopeV2 = serde_json::from_slice(&artifact_bytes)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;

    // Load corpus rows for provenance.
    let train_rows = load_corpus(&spec.corpus_train_path)?;
    let dev_rows = load_corpus(&spec.corpus_dev_path)?;
    let mut corpus_by_case: BTreeMap<String, serde_json::Value> = BTreeMap::new();
    for r in train_rows.iter().chain(dev_rows.iter()) {
        let case_id = r["case_id"]
            .as_str()
            .ok_or_else(|| ExperimentError::Invalid("corpus row missing case_id".into()))?;
        if corpus_by_case
            .insert(case_id.to_string(), r.clone())
            .is_some()
        {
            return Err(ExperimentError::Invalid(format!(
                "duplicate corpus case {case_id}"
            )));
        }
    }

    // Census checks on corpus (source of truth for counts).
    let dev_corpus: Vec<&serde_json::Value> = dev_rows.iter().collect();
    let dev_groups: BTreeSet<&str> = dev_corpus
        .iter()
        .map(|r| r["group_id"].as_str().unwrap_or_default())
        .collect();
    let train_corpus_groups: BTreeSet<&str> = train_rows
        .iter()
        .map(|r| r["group_id"].as_str().unwrap_or_default())
        .collect();
    // Expected M015 census: 2000 train groups / 7200 rows, 200 dev groups / 720 rows.
    if train_rows.len() != 7200 || train_corpus_groups.len() != 2000 {
        return Err(ExperimentError::Invalid(format!(
            "train census drift: got {} rows / {} groups (need 7200/2000)",
            train_rows.len(),
            train_corpus_groups.len()
        )));
    }
    if dev_rows.len() != 720 || dev_groups.len() != 200 {
        return Err(ExperimentError::Invalid(format!(
            "dev census drift: got {} rows / {} groups (need 720/200)",
            dev_rows.len(),
            dev_groups.len()
        )));
    }
    let mut nuisance_pairs = BTreeSet::new();
    let mut causal_pairs = BTreeSet::new();
    for r in &dev_rows {
        let pt = r["pair_type"].as_str().unwrap_or_default();
        let pid = r["pair_id"].as_str().unwrap_or_default();
        if pt == "nuisance" {
            nuisance_pairs.insert(pid);
        } else if pt == "causal_flip" {
            causal_pairs.insert(pid);
        }
    }
    if nuisance_pairs.len() != 200 || causal_pairs.len() != 160 {
        return Err(ExperimentError::Invalid(format!(
            "pair census drift: nuisance {} (need 200), causal {} (need 160)",
            nuisance_pairs.len(),
            causal_pairs.len()
        )));
    }

    // Build DEV ChoiceFinalCases via actual runtime inference.
    let by_id: BTreeMap<&str, &DatasetExample> =
        examples.iter().map(|e| (e.case_id.as_str(), e)).collect();
    let mut cases: Vec<ChoiceFinalCase> = Vec::with_capacity(split.dev.len());
    for case_id in &split.dev {
        let ex = by_id.get(case_id.as_str()).ok_or_else(|| {
            ExperimentError::Invalid(format!("split dev id {case_id} missing from dataset"))
        })?;
        let sdm_data::TargetLabel::Choice(target) = &ex.label else {
            return Err(ExperimentError::Invalid(
                "m015a replay requires Choice labels".into(),
            ));
        };
        let binding = ex
            .typed_rank_features
            .as_ref()
            .ok_or_else(|| ExperimentError::Invalid("typed features missing".into()))?;
        let sdm_core::DecisionSpec::Choice { options, .. } = &ex.request.spec else {
            return Err(ExperimentError::Invalid(
                "Choice request missing options".into(),
            ));
        };
        let response = runtime
            .decide_typed(&ex.request, binding)
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let predicted = match response.answer {
            Some(sdm_core::DecisionAnswer::Choice { option_id, .. }) => Some(option_id),
            None => None,
            _ => {
                return Err(ExperimentError::Invalid(
                    "unexpected non-Choice answer".into(),
                ))
            }
        };
        let probs = runtime
            .choice_probabilities(&ex.request, binding)
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let logits = runtime
            .choice_logits(&ex.request, binding)
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let answerability = runtime
            .choice_answerability_probability(&ex.request, binding)
            .map_err(|e| ExperimentError::Invalid(e.to_string()))?;
        let corpus = corpus_by_case.get(case_id.as_str()).ok_or_else(|| {
            ExperimentError::Invalid(format!("dev case {case_id} missing from corpus"))
        })?;
        let available = corpus["context"]["available"].as_bool().ok_or_else(|| {
            ExperimentError::Invalid(format!("corpus {case_id} missing available"))
        })?;
        let satisfying = corpus["oracle"]["satisfying_option_count"]
            .as_u64()
            .ok_or_else(|| {
                ExperimentError::Invalid(format!("corpus {case_id} missing oracle count"))
            })?;
        let origin = match (target, available, satisfying) {
            (Some(_), _, _) => None,
            (None, false, _) => Some(NoAnswerOrigin::UnavailableContext),
            (None, true, 0) => Some(NoAnswerOrigin::ZeroSatisfyingCandidates),
            (None, true, n) => {
                return Err(ExperimentError::Invalid(format!(
                    "corpus {case_id}: available true with {n} satisfying but label None"
                )))
            }
        };
        let pair_id = ex.counterfactual_pair.clone();
        let pair_type = corpus["pair_type"].as_str().map(str::to_string);
        let family = ex
            .family
            .clone()
            .unwrap_or_else(|| corpus["family"].as_str().unwrap_or("unknown").to_string());
        // Digests for strict pair validation.
        let context_digest = canonical_sha(&corpus["context"]);
        // Semantics: sorted id -> semantics map (order-independent).
        let mut sem_map = BTreeMap::new();
        if let Some(opts) = corpus["options"].as_array() {
            for o in opts {
                let id = o["id"].as_str().unwrap_or_default();
                sem_map.insert(id.to_string(), o["semantics"].clone());
            }
        }
        let semantics_digest = canonical_sha(&serde_json::to_value(&sem_map).unwrap_or_default());
        let rule_digest = canonical_sha(&corpus["rule"]);
        let option_ids: Vec<String> = options.iter().map(|o| o.id.clone()).collect();
        cases.push(ChoiceFinalCase {
            case_id: ex.case_id.clone(),
            leakage_group: ex.leakage_group.clone(),
            family,
            split: "dev".into(),
            pair_id,
            pair_type,
            target: target.clone(),
            option_ids,
            predicted,
            conditional_probs: probs,
            conditional_logits: Some(logits),
            answerability_p: answerability,
            no_answer_origin: origin,
            context_digest,
            semantics_digest,
            rule_digest,
        });
    }

    // Sort for determinism (evaluator also sorts).
    cases.sort_by(|a, b| {
        a.leakage_group
            .cmp(&b.leakage_group)
            .then_with(|| a.case_id.cmp(&b.case_id))
    });

    let report: ChoiceFinalReportV2 = choice_final_v2::evaluate_choice_final_v2(&cases)
        .map_err(|e| ExperimentError::Invalid(e.to_string()))?;

    // Legacy comparison: read frozen report dev_diagnostics for this architecture
    // if present beside the artifact? Caller supplies via sidecar legacy map;
    // here we leave it empty and let the Python orchestrator fill it from the
    // committed frozen reports. Keep the field for schema stability.
    let mut bootstrap = BTreeMap::new();
    bootstrap.insert(
        "seed".into(),
        serde_json::Value::from(sdm_eval::choice_final_v2::CONTRACT_SEED),
    );
    bootstrap.insert(
        "replicates".into(),
        serde_json::Value::from(sdm_eval::choice_final_v2::CONTRACT_REPLICATES),
    );
    bootstrap.insert(
        "confidence".into(),
        serde_json::Value::from(sdm_eval::choice_final_v2::CONTRACT_CONFIDENCE),
    );
    bootstrap.insert("method".into(), serde_json::Value::from(CONTRACT_METHOD));

    let dataset_file_sha = file_sha256(&spec.dataset_path)?;
    let split_file_sha = file_sha256(&spec.split_path)?;
    // Best-effort source commit (fails closed to "unknown" on shallow checkouts).
    let source_commit = std::process::Command::new("git")
        .args(["rev-parse", "HEAD"])
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|| "unknown".into());

    let mut sidecar = M015aSidecar {
        schema: "sdm-m015a-dev-final-v1".into(),
        schema_version: 1,
        contract: sdm_eval::choice_final_v2::CONTRACT_VERSION.into(),
        architecture: spec.architecture.clone(),
        partition: "DEV only".into(),
        dataset_sha256: dataset_sha,
        split_fingerprint: split.fingerprint.clone(),
        artifact_sha256: actual_artifact_sha,
        calibration_sha256: envelope.calibration_sha256.clone(),
        artifact_architecture: envelope.architecture.clone(),
        generator_sha256: actual_generator_sha,
        task_spec_sha256: actual_spec_sha,
        corpus_train_sha256: format!("sha256:{actual_train_hex}"),
        corpus_dev_sha256: format!("sha256:{actual_dev_hex}"),
        dataset_file_sha256: dataset_file_sha,
        split_file_sha256: split_file_sha,
        source_commit,
        train_rows: train_rows.len(),
        train_groups: train_corpus_groups.len(),
        dev_rows: dev_rows.len(),
        dev_groups: dev_groups.len(),
        dev_answerable_rows: report.answerable_cases,
        dev_no_answer_rows: report.no_answer_cases,
        dev_nuisance_pairs: nuisance_pairs.len(),
        dev_causal_pairs: causal_pairs.len(),
        report,
        legacy_comparison: BTreeMap::new(),
        bootstrap,
        report_sha256: String::new(),
    };
    let digest = format!(
        "sha256:{:x}",
        Sha256::digest(
            serde_json::to_vec(&(
                &sidecar.schema,
                &sidecar.contract,
                &sidecar.architecture,
                &sidecar.dataset_sha256,
                &sidecar.split_fingerprint,
                &sidecar.artifact_sha256,
                &sidecar.calibration_sha256,
                &sidecar.generator_sha256,
                &sidecar.task_spec_sha256,
                &sidecar.corpus_train_sha256,
                &sidecar.corpus_dev_sha256,
                &sidecar.report,
            ))
            .map_err(ExperimentError::Json)?
        )
    );
    sidecar.report_sha256 = digest;
    atomic_write_new(&spec.output_path, &serde_json::to_vec_pretty(&sidecar)?)?;
    Ok(sidecar)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn m015a_replay_spec_denies_training_fields() {
        let raw = serde_json::json!({
            "dataset_path": "a",
            "split_path": "b",
            "artifact_path": "c",
            "corpus_train_path": "d",
            "corpus_dev_path": "e",
            "generator_path": "f",
            "task_spec_path": "g",
            "output_path": "h",
            "expected_artifact_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "expected_dataset_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "expected_split_fingerprint": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "expected_generator_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "expected_task_spec_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "expected_corpus_train_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "expected_corpus_dev_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "architecture": "typed-choice",
            "provenance": {"source":"s","license":"MIT","consent_scope":"c","label_lineage":"l","redistributable":true},
            "epochs": 5
        });
        assert!(serde_json::from_value::<M015aReplaySpec>(raw).is_err());
    }

    #[test]
    fn m015a_replay_rejects_empty_test_violation_and_bad_arch() {
        let spec = M015aReplaySpec {
            dataset_path: "nope".into(),
            split_path: "nope".into(),
            artifact_path: "nope".into(),
            corpus_train_path: "nope".into(),
            corpus_dev_path: "nope".into(),
            generator_path: "nope".into(),
            task_spec_path: "nope".into(),
            output_path: "nope".into(),
            expected_artifact_sha256:
                "sha256:0000000000000000000000000000000000000000000000000000000000000000".into(),
            expected_dataset_sha256:
                "sha256:0000000000000000000000000000000000000000000000000000000000000000".into(),
            expected_split_fingerprint:
                "sha256:0000000000000000000000000000000000000000000000000000000000000000".into(),
            expected_generator_sha256:
                "sha256:0000000000000000000000000000000000000000000000000000000000000000".into(),
            expected_task_spec_sha256:
                "sha256:0000000000000000000000000000000000000000000000000000000000000000".into(),
            expected_corpus_train_sha256:
                "sha256:0000000000000000000000000000000000000000000000000000000000000000".into(),
            expected_corpus_dev_sha256:
                "sha256:0000000000000000000000000000000000000000000000000000000000000000".into(),
            architecture: "typed-binary".into(),
            provenance: Provenance {
                source: "s".into(),
                license: "MIT".into(),
                consent_scope: "c".into(),
                label_lineage: "l".into(),
                redistributable: true,
            },
        };
        assert!(run_m015a_replay(&spec).is_err());
    }
}
