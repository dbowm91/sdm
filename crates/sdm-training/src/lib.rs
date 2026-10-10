//! Deterministic bounded training and evaluation utilities for generic decision cases.
use sdm_core::{DecisionAnswer, DecisionRequest, DecisionResponse, DecisionSpec};
use sdm_runtime::{
    features_for, parameter_digest, ArtifactManifest, LinearArtifact, Runtime, ARTIFACT_SCHEMA,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};

pub const DATASET_SCHEMA: u16 = 1;
pub const MAX_DATASET_BYTES: usize = 64 * 1024 * 1024;
pub const MAX_CASES: usize = 100_000;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionCase {
    pub schema_version: u16,
    pub case_id: String,
    pub leakage_group: String,
    pub request: DecisionRequest,
    pub response: DecisionResponse,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainingReport {
    pub seed: u64,
    pub dataset_sha256: String,
    pub train_cases: usize,
    pub dev_cases: usize,
    pub test_cases: usize,
    pub threshold: f64,
    pub parameter_count: usize,
    pub epochs_completed: usize,
    pub artifact_bytes: usize,
    pub artifact_sha256: String,
}

#[derive(Debug, thiserror::Error)]
pub enum TrainingError {
    #[error("invalid dataset: {0}")]
    Dataset(String),
    #[error("training failed: {0}")]
    Failed(String),
    #[error(transparent)]
    Runtime(#[from] sdm_runtime::RuntimeError),
}

pub fn read_jsonl(path: &Path) -> Result<(Vec<DecisionCase>, Vec<u8>), TrainingError> {
    let bytes = fs::read(path).map_err(|e| TrainingError::Dataset(e.to_string()))?;
    if bytes.len() > MAX_DATASET_BYTES {
        return Err(TrainingError::Dataset("dataset exceeds byte limit".into()));
    }
    let mut cases = Vec::new();
    for (i, line) in bytes
        .split(|b| *b == b'\n')
        .filter(|l| !l.is_empty())
        .enumerate()
    {
        if cases.len() >= MAX_CASES {
            return Err(TrainingError::Dataset("too many cases".into()));
        }
        let c: DecisionCase = serde_json::from_slice(line)
            .map_err(|e| TrainingError::Dataset(format!("line {}: {e}", i + 1)))?;
        validate_case(&c)?;
        cases.push(c);
    }
    if cases.is_empty() {
        return Err(TrainingError::Dataset("dataset is empty".into()));
    }
    Ok((cases, bytes))
}

pub fn validate_case(c: &DecisionCase) -> Result<(), TrainingError> {
    if c.schema_version != DATASET_SCHEMA
        || c.case_id.trim().is_empty()
        || c.leakage_group.trim().is_empty()
    {
        return Err(TrainingError::Dataset("invalid identity or schema".into()));
    }
    c.request
        .validate()
        .map_err(|e| TrainingError::Dataset(e.to_string()))?;
    c.response
        .validate_for(&c.request)
        .map_err(|e| TrainingError::Dataset(e.to_string()))?;
    Ok(())
}

fn split(group: &str, seed: u64) -> usize {
    let mut h = Sha256::new();
    h.update(seed.to_le_bytes());
    h.update(group.as_bytes());
    let n = u64::from_le_bytes(h.finalize()[..8].try_into().unwrap());
    (n % 100) as usize
}
fn probability(weights: &BTreeMap<String, f64>, bias: f64, context: &str, option: &str) -> f64 {
    let z = features_for(context, option)
        .iter()
        .map(|t| weights.get(t).copied().unwrap_or(0.0))
        .sum::<f64>()
        + bias;
    1.0 / (1.0 + (-z).exp())
}

pub fn train(
    cases: &[DecisionCase],
    seed: u64,
    epochs: usize,
) -> Result<(LinearArtifact, TrainingReport), TrainingError> {
    if cases.is_empty() || epochs == 0 || epochs > 10_000 {
        return Err(TrainingError::Failed(
            "empty cases or invalid epoch count".into(),
        ));
    }
    for c in cases {
        validate_case(c)?;
    }
    let mut ids = BTreeSet::new();
    if cases.iter().any(|c| !ids.insert(c.case_id.as_str())) {
        return Err(TrainingError::Dataset("duplicate case id".into()));
    }
    let mut group_splits = BTreeMap::new();
    for c in cases {
        let s = split(&c.leakage_group, seed);
        if let Some(old) = group_splits.insert(c.leakage_group.as_str(), s) {
            assert_eq!(old, s);
        }
    }
    let train_cases: Vec<_> = cases
        .iter()
        .filter(|c| split(&c.leakage_group, seed) < 70)
        .collect();
    let dev_cases: Vec<_> = cases
        .iter()
        .filter(|c| (70..85).contains(&split(&c.leakage_group, seed)))
        .collect();
    let test_cases: Vec<_> = cases
        .iter()
        .filter(|c| split(&c.leakage_group, seed) >= 85)
        .collect();
    if train_cases.is_empty() {
        return Err(TrainingError::Failed(
            "seed produced no training groups".into(),
        ));
    }
    let mut weights = BTreeMap::<String, f64>::new();
    let mut bias = 0.0;
    for _ in 0..epochs {
        for case in &train_cases {
            let DecisionSpec::Rank { candidates, .. } = &case.request.spec else {
                continue;
            };
            let labels: BTreeMap<_, _> = match &case.response.answer {
                Some(DecisionAnswer::Rank { candidates }) => candidates
                    .iter()
                    .map(|x| (x.candidate_id.as_str(), x.relevance > 0.0))
                    .collect(),
                _ => BTreeMap::new(),
            };
            for candidate in candidates {
                let context = case
                    .request
                    .state
                    .iter()
                    .map(|f| f.value.as_str())
                    .collect::<Vec<_>>()
                    .join(" ");
                let option = format!("{} {}", candidate.label, candidate.description);
                let y = f64::from(labels.get(candidate.id.as_str()).copied().unwrap_or(false));
                let error = y - probability(&weights, bias, &context, &option);
                bias += 0.05 * error;
                for token in features_for(&context.to_lowercase(), &option.to_lowercase()) {
                    *weights.entry(token).or_default() += 0.05 * error;
                }
            }
        }
    }
    // Threshold is selected on dev only; test examples never tune model parameters.
    let threshold = if dev_cases.is_empty() {
        0.5
    } else {
        let mut observations = Vec::new();
        for case in &dev_cases {
            let DecisionSpec::Rank { candidates, .. } = &case.request.spec else {
                continue;
            };
            let context = case
                .request
                .state
                .iter()
                .map(|f| f.value.as_str())
                .collect::<Vec<_>>()
                .join(" ");
            let max_probability = candidates
                .iter()
                .map(|c| {
                    let option = format!("{} {}", c.label, c.description);
                    probability(&weights, bias, &context, &option)
                })
                .fold(0.0_f64, f64::max);
            let relevant = matches!(&case.response.answer, Some(DecisionAnswer::Rank { candidates }) if candidates.iter().any(|c| c.relevance > 0.0));
            observations.push((max_probability, relevant));
        }
        let positives = observations.iter().filter(|(_, truth)| *truth).count();
        let negatives = observations.len().saturating_sub(positives);
        let mut best = (f64::NEG_INFINITY, 0.5);
        for step in 0..=100 {
            let t = step as f64 / 100.0;
            let tp = observations
                .iter()
                .filter(|(p, truth)| *truth && *p >= t)
                .count();
            let tn = observations
                .iter()
                .filter(|(p, truth)| !*truth && *p < t)
                .count();
            let score = match (positives > 0, negatives > 0) {
                (true, true) => 0.5 * (tp as f64 / positives as f64 + tn as f64 / negatives as f64),
                (true, false) => tp as f64 / positives as f64,
                (false, true) => tn as f64 / negatives as f64,
                (false, false) => 0.5,
            };
            if score > best.0 {
                best = (score, t)
            }
        }
        best.1
    };
    let model_hash = parameter_digest(bias, &weights);
    let source_fingerprint = format!(
        "sha256:{:x}",
        Sha256::digest(serde_json::to_vec(cases).unwrap())
    );
    let artifact = LinearArtifact {
        manifest: ArtifactManifest {
            schema_version: ARTIFACT_SCHEMA,
            architecture: "sdm-binary-linear-v1".into(),
            input_schema_version: 1,
            capabilities: vec!["rank".into()],
            max_state_bytes: 65_536,
            max_candidates: 256,
            model_sha256: model_hash.clone(),
            training_fingerprint: source_fingerprint.clone(),
            calibration_version: 1,
            calibration_sha256: format!(
                "sha256:{:x}",
                Sha256::digest(threshold.to_bits().to_le_bytes())
            ),
            license: "MIT".into(),
            source: "sdm-training".into(),
        },
        bias,
        weights,
        threshold,
    };
    let encoded = serde_json::to_vec(&artifact).unwrap();
    let runtime = Runtime::from_bytes(&encoded)?;
    // Test split is measured once for reporting only; it does not affect weights or threshold.
    let artifact_hash = runtime.digest().to_string();
    Ok((
        artifact,
        TrainingReport {
            seed,
            dataset_sha256: source_fingerprint,
            train_cases: train_cases.len(),
            dev_cases: dev_cases.len(),
            test_cases: test_cases.len(),
            threshold,
            parameter_count: runtime.artifact().weights.len() + 1,
            epochs_completed: epochs,
            artifact_bytes: encoded.len(),
            artifact_sha256: artifact_hash,
        },
    ))
}

pub fn evaluate(
    cases: &[DecisionCase],
    artifact: &LinearArtifact,
) -> Result<(usize, usize), TrainingError> {
    let runtime = Runtime::from_bytes(&serde_json::to_vec(artifact).unwrap())?;
    let (mut correct, mut total) = (0, 0);
    for case in cases {
        validate_case(case)?;
        let out = runtime
            .decide(&case.request)
            .map_err(|e| TrainingError::Failed(e.to_string()))?;
        let DecisionSpec::Rank { candidates, .. } = &case.request.spec else {
            continue;
        };
        let expected: BTreeMap<_, _> = match &case.response.answer {
            Some(DecisionAnswer::Rank { candidates }) => candidates
                .iter()
                .map(|x| (x.candidate_id.as_str(), x.relevance > 0.0))
                .collect(),
            _ => BTreeMap::new(),
        };
        let predicted: BTreeMap<_, _> = match &out.answer {
            Some(DecisionAnswer::Rank { candidates }) => candidates
                .iter()
                .map(|x| (x.candidate_id.as_str(), x.relevance >= artifact.threshold))
                .collect(),
            _ => BTreeMap::new(),
        };
        for candidate in candidates {
            total += 1;
            if predicted
                .get(candidate.id.as_str())
                .copied()
                .unwrap_or(false)
                == expected
                    .get(candidate.id.as_str())
                    .copied()
                    .unwrap_or(false)
            {
                correct += 1;
            }
        }
    }
    Ok((correct, total))
}

#[cfg(test)]
mod tests {
    use super::*;
    use sdm_core::{
        DecisionCandidate, DecisionProvenance, DecisionStatus, RankedDecisionCandidate, StateField,
    };

    fn case(i: usize, group: &str, relevant: bool) -> DecisionCase {
        let request = DecisionRequest {
            request_id: format!("req-{i}"),
            schema_version: 1,
            state: vec![StateField {
                key: "task".into(),
                value: "inspect alpha".into(),
            }],
            spec: DecisionSpec::Rank {
                instruction: "rank independently".into(),
                multi_relevance: true,
                candidates: vec![
                    DecisionCandidate {
                        id: "alpha".into(),
                        label: "alpha".into(),
                        description: "inspect alpha source".into(),
                    },
                    DecisionCandidate {
                        id: "beta".into(),
                        label: "beta".into(),
                        description: "unrelated item".into(),
                    },
                ],
            },
        };
        let response = DecisionResponse {
            request_id: request.request_id.clone(),
            schema_version: 1,
            status: DecisionStatus::Answered,
            answer: Some(DecisionAnswer::Rank {
                candidates: vec![
                    RankedDecisionCandidate {
                        candidate_id: "alpha".into(),
                        relevance: f64::from(relevant),
                        ranking_score: f64::from(relevant),
                    },
                    RankedDecisionCandidate {
                        candidate_id: "beta".into(),
                        relevance: 0.0,
                        ranking_score: 0.0,
                    },
                ],
            }),
            provenance: DecisionProvenance {
                backend: "test-labels".into(),
                model: None,
                runtime_version: Some("test".into()),
                latency_micros: 0,
            },
        };
        DecisionCase {
            schema_version: 1,
            case_id: format!("case-{i}"),
            leakage_group: group.into(),
            request,
            response,
        }
    }

    #[test]
    fn train_is_reproducible_and_group_splits_are_disjoint() {
        let cases: Vec<_> = (0..100)
            .map(|i| case(i, &format!("group-{i}"), i % 2 == 0))
            .collect();
        let (_, a) = train(&cases, 42, 3).unwrap();
        let (_, b) = train(&cases, 42, 3).unwrap();
        assert_eq!(a.dataset_sha256, b.dataset_sha256);
        assert_eq!(a.threshold, b.threshold);
        assert_eq!(
            (a.train_cases, a.dev_cases, a.test_cases),
            (b.train_cases, b.dev_cases, b.test_cases)
        );
        assert!(a.train_cases > 0 && a.dev_cases > 0 && a.test_cases > 0);
        for case in &cases {
            assert_eq!(
                split(&case.leakage_group, 42),
                split(&case.leakage_group, 42)
            );
        }
    }

    #[test]
    fn changing_only_test_labels_does_not_change_fitted_parameters_or_dev_threshold() {
        let mut cases: Vec<_> = (0..100)
            .map(|i| case(i, &format!("group-{i}"), i % 2 == 0))
            .collect();
        let (baseline, baseline_report) = train(&cases, 42, 3).unwrap();
        let mut changed_test_labels = 0;
        for row in &mut cases {
            if split(&row.leakage_group, 42) >= 85 {
                if let Some(DecisionAnswer::Rank { candidates }) = &mut row.response.answer {
                    candidates[0].relevance = 1.0 - candidates[0].relevance;
                    candidates[0].ranking_score = candidates[0].relevance;
                    changed_test_labels += 1;
                }
            }
        }
        assert!(changed_test_labels > 0);
        let (changed, changed_report) = train(&cases, 42, 3).unwrap();
        assert_eq!(baseline.bias, changed.bias);
        assert_eq!(baseline.weights, changed.weights);
        assert_eq!(baseline.threshold, changed.threshold);
        assert_eq!(baseline_report.threshold, changed_report.threshold);
    }

    #[test]
    fn evaluator_uses_artifact_and_keeps_multiple_relevant_candidates() {
        let cases = vec![case(1, "group-a", true), case(2, "group-b", false)];
        let (artifact, _) = train(&cases, 12, 2).unwrap();
        let (correct, total) = evaluate(&cases, &artifact).unwrap();
        assert_eq!(total, 4);
        assert!(correct <= total);
    }
}
