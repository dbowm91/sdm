//! Algorithm-neutral metrics for frozen predictions; no training dependency.
use serde::{Deserialize, Serialize};
use sha2::Digest;
use thiserror::Error;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct QualificationProtocol {
    pub version: u16,
    pub dataset_sha256: String,
    pub split_fingerprint: String,
    pub artifact_sha256: String,
    pub calibration_sha256: String,
    pub source_revision: String,
    pub rank_k: usize,
    pub minimum_cases: usize,
    pub gates: std::collections::BTreeMap<String, f64>,
    pub fingerprint: String,
}

impl QualificationProtocol {
    pub fn freeze(&mut self) -> Result<(), EvalError> {
        self.validate_fields()?;
        self.fingerprint.clear();
        let bytes = serde_json::to_vec(self).map_err(|e| EvalError::Invalid(e.to_string()))?;
        self.fingerprint = format!("sha256:{:x}", sha2::Sha256::digest(bytes));
        Ok(())
    }
    pub fn validate(
        &self,
        dataset_sha256: &str,
        split_fingerprint: &str,
        artifact_sha256: &str,
        calibration_sha256: &str,
    ) -> Result<(), EvalError> {
        self.validate_fields()?;
        if self.dataset_sha256 != dataset_sha256
            || self.split_fingerprint != split_fingerprint
            || self.artifact_sha256 != artifact_sha256
            || self.calibration_sha256 != calibration_sha256
        {
            return Err(EvalError::Invalid("qualification identity mismatch".into()));
        }
        let mut copy = self.clone();
        let recorded = copy.fingerprint.clone();
        copy.fingerprint.clear();
        let bytes = serde_json::to_vec(&copy).map_err(|e| EvalError::Invalid(e.to_string()))?;
        if recorded != format!("sha256:{:x}", sha2::Sha256::digest(bytes)) {
            return Err(EvalError::Invalid("protocol fingerprint mismatch".into()));
        }
        Ok(())
    }
    fn validate_fields(&self) -> Result<(), EvalError> {
        if self.version != 1
            || self.rank_k == 0
            || self.minimum_cases == 0
            || self.source_revision.is_empty()
            || [
                &self.dataset_sha256,
                &self.split_fingerprint,
                &self.artifact_sha256,
                &self.calibration_sha256,
            ]
            .iter()
            .any(|x| !x.starts_with("sha256:") || x.len() != 71)
            || self.gates.values().any(|x| !x.is_finite())
        {
            return Err(EvalError::Invalid("invalid frozen protocol".into()));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BinaryMetrics {
    pub count: usize,
    pub accuracy: Option<f64>,
    pub brier: Option<f64>,
    pub log_loss: Option<f64>,
    pub precision: Option<f64>,
    pub recall: Option<f64>,
    pub f1: Option<f64>,
}
pub fn evaluate_binary(
    truth: &[bool],
    probability_true: &[f64],
    threshold: f64,
) -> Result<BinaryMetrics, EvalError> {
    if truth.len() != probability_true.len()
        || !threshold.is_finite()
        || !(0.0..=1.0).contains(&threshold)
        || probability_true
            .iter()
            .any(|p| !p.is_finite() || !(0.0..=1.0).contains(p))
    {
        return Err(EvalError::Invalid(
            "invalid binary prediction vectors".into(),
        ));
    }
    if truth.is_empty() {
        return Ok(BinaryMetrics {
            count: 0,
            accuracy: None,
            brier: None,
            log_loss: None,
            precision: None,
            recall: None,
            f1: None,
        });
    }
    let (mut correct, mut brier, mut loss, mut tp, mut fp, mut fn_) = (0, 0.0, 0.0, 0, 0, 0);
    for (y, p) in truth.iter().zip(probability_true) {
        let pred = *p >= threshold;
        correct += usize::from(pred == *y);
        let t = f64::from(*y);
        brier += (p - t).powi(2);
        loss -= if *y {
            p.max(1e-15).ln()
        } else {
            (1.0 - p).max(1e-15).ln()
        };
        match (pred, *y) {
            (true, true) => tp += 1,
            (true, false) => fp += 1,
            (false, true) => fn_ += 1,
            _ => {}
        }
    }
    let precision = (tp + fp > 0).then_some(tp as f64 / (tp + fp) as f64);
    let recall = (tp + fn_ > 0).then_some(tp as f64 / (tp + fn_) as f64);
    let f1 = match (precision, recall) {
        (Some(p), Some(r)) if p + r > 0.0 => Some(2.0 * p * r / (p + r)),
        _ => None,
    };
    let n = truth.len() as f64;
    Ok(BinaryMetrics {
        count: truth.len(),
        accuracy: Some(correct as f64 / n),
        brier: Some(brier / n),
        log_loss: Some(loss / n),
        precision,
        recall,
        f1,
    })
}

/// Equal-width expected calibration error; empty input is undefined.
pub fn expected_calibration_error(
    truth: &[bool],
    probability_true: &[f64],
    bins: usize,
) -> Result<Option<f64>, EvalError> {
    if truth.len() != probability_true.len()
        || bins == 0
        || probability_true
            .iter()
            .any(|p| !p.is_finite() || !(0.0..=1.0).contains(p))
    {
        return Err(EvalError::Invalid("invalid calibration inputs".into()));
    }
    if truth.is_empty() {
        return Ok(None);
    }
    let mut counts = vec![0usize; bins];
    let mut confidence = vec![0.0; bins];
    let mut positives = vec![0.0; bins];
    for (y, p) in truth.iter().zip(probability_true) {
        let index = ((*p * bins as f64).floor() as usize).min(bins - 1);
        counts[index] += 1;
        confidence[index] += p;
        positives[index] += f64::from(*y);
    }
    let n = truth.len() as f64;
    let value = (0..bins)
        .filter(|i| counts[*i] > 0)
        .map(|i| {
            counts[i] as f64 / n
                * ((confidence[i] / counts[i] as f64) - (positives[i] / counts[i] as f64)).abs()
        })
        .sum();
    Ok(Some(value))
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ScoreMetrics {
    pub count: usize,
    pub mae: Option<f64>,
    pub rmse: Option<f64>,
}
pub fn evaluate_score(
    truth: &[f64],
    predicted: &[f64],
    minimum: f64,
    maximum: f64,
) -> Result<ScoreMetrics, EvalError> {
    if truth.len() != predicted.len()
        || !minimum.is_finite()
        || !maximum.is_finite()
        || minimum >= maximum
        || truth
            .iter()
            .chain(predicted)
            .any(|x| !x.is_finite() || *x < minimum || *x > maximum)
    {
        return Err(EvalError::Invalid("invalid score vectors or rubric".into()));
    }
    if truth.is_empty() {
        return Ok(ScoreMetrics {
            count: 0,
            mae: None,
            rmse: None,
        });
    }
    let n = truth.len() as f64;
    let mse = truth
        .iter()
        .zip(predicted)
        .map(|(a, b)| (a - b).powi(2))
        .sum::<f64>()
        / n;
    Ok(ScoreMetrics {
        count: truth.len(),
        mae: Some(
            truth
                .iter()
                .zip(predicted)
                .map(|(a, b)| (a - b).abs())
                .sum::<f64>()
                / n,
        ),
        rmse: Some(mse.sqrt()),
    })
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ChoiceMetrics {
    pub count: usize,
    pub accuracy: Option<f64>,
    pub log_loss: Option<f64>,
}
pub fn evaluate_choice(
    truth: &[usize],
    probabilities: &[Vec<f64>],
) -> Result<ChoiceMetrics, EvalError> {
    if truth.len() != probabilities.len()
        || probabilities.iter().zip(truth).any(|(row, y)| {
            row.len() < 2
                || *y >= row.len()
                || row.iter().any(|p| !p.is_finite() || *p < 0.0 || *p > 1.0)
                || (row.iter().sum::<f64>() - 1.0).abs() > 1e-8
        })
    {
        return Err(EvalError::Invalid(
            "invalid choice probability distribution".into(),
        ));
    }
    if truth.is_empty() {
        return Ok(ChoiceMetrics {
            count: 0,
            accuracy: None,
            log_loss: None,
        });
    }
    let correct = truth
        .iter()
        .zip(probabilities)
        .filter(|(y, row)| {
            row.iter()
                .enumerate()
                .max_by(|a, b| a.1.total_cmp(b.1).then_with(|| b.0.cmp(&a.0)))
                .is_some_and(|(i, _)| i == **y)
        })
        .count();
    let loss = truth
        .iter()
        .zip(probabilities)
        .map(|(y, row)| -row[*y].max(1e-15).ln())
        .sum::<f64>()
        / truth.len() as f64;
    Ok(ChoiceMetrics {
        count: truth.len(),
        accuracy: Some(correct as f64 / truth.len() as f64),
        log_loss: Some(loss),
    })
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CandidatePrediction {
    pub candidate_id: String,
    pub score: f64,
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RankPrediction {
    pub case_id: String,
    pub candidates: Vec<CandidatePrediction>,
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RankMetrics {
    pub cases: usize,
    pub mrr: Option<f64>,
    pub recall_at_k: Option<f64>,
    pub ndcg: Option<f64>,
    pub precision: Option<f64>,
    pub recall: Option<f64>,
    pub f1: Option<f64>,
    pub candidate_coverage: f64,
}
#[derive(Debug, Error)]
pub enum EvalError {
    #[error("invalid predictions: {0}")]
    Invalid(String),
}

pub fn evaluate_rank(
    examples: &[sdm_data::DatasetExample],
    predictions: &[RankPrediction],
    k: usize,
) -> Result<RankMetrics, EvalError> {
    if examples.len() != predictions.len() || k == 0 {
        return Err(EvalError::Invalid(
            "prediction/case count mismatch or k=0".into(),
        ));
    }
    let mut reciprocal = 0.0;
    let mut recall_k = 0.0;
    let mut ndcg = 0.0;
    let mut tp = 0usize;
    let mut fp = 0usize;
    let mut fn_ = 0usize;
    let mut eligible = 0usize;
    let mut coverage = 0usize;
    for (e, p) in examples.iter().zip(predictions) {
        if e.case_id != p.case_id {
            return Err(EvalError::Invalid(
                "prediction case identity mismatch".into(),
            ));
        }
        let sdm_data::TargetLabel::Rank { relevance, .. } = &e.label else {
            continue;
        };
        let sdm_core::DecisionSpec::Rank { candidates, .. } = &e.request.spec else {
            return Err(EvalError::Invalid("rank label without rank request".into()));
        };
        let expected: std::collections::BTreeSet<_> =
            candidates.iter().map(|c| c.id.as_str()).collect();
        let mut seen = std::collections::BTreeSet::new();
        if p.candidates.iter().any(|x| {
            !x.score.is_finite()
                || !expected.contains(x.candidate_id.as_str())
                || !seen.insert(x.candidate_id.as_str())
        }) {
            return Err(EvalError::Invalid(
                "invalid/duplicate/unknown candidate prediction".into(),
            ));
        }
        if seen != expected {
            return Err(EvalError::Invalid("candidate universe mismatch".into()));
        }
        let mut ranked = p.candidates.clone();
        ranked.sort_by(|a, b| {
            b.score
                .total_cmp(&a.score)
                .then_with(|| a.candidate_id.cmp(&b.candidate_id))
        });
        let positives: std::collections::BTreeSet<_> = relevance
            .iter()
            .filter(|(_, v)| **v > 0.0)
            .map(|(id, _)| id.as_str())
            .collect();
        if !positives.is_empty() {
            eligible += 1;
            coverage += candidates.len();
            if let Some(i) = ranked
                .iter()
                .position(|x| positives.contains(x.candidate_id.as_str()))
            {
                reciprocal += 1.0 / (i + 1) as f64;
            }
            let hit = ranked
                .iter()
                .take(k)
                .filter(|x| positives.contains(x.candidate_id.as_str()))
                .count();
            recall_k += hit as f64 / positives.len() as f64;
            let dcg: f64 = ranked
                .iter()
                .take(k)
                .enumerate()
                .map(|(i, x)| {
                    relevance.get(&x.candidate_id).copied().unwrap_or(0.0) / ((i + 2) as f64).log2()
                })
                .sum();
            let mut ideal: Vec<_> = relevance.values().copied().collect();
            ideal.sort_by(|a, b| b.total_cmp(a));
            let idcg: f64 = ideal
                .iter()
                .take(k)
                .enumerate()
                .map(|(i, v)| v / ((i + 2) as f64).log2())
                .sum();
            if idcg > 0.0 {
                ndcg += dcg / idcg;
            }
        }
        let predicted: std::collections::BTreeSet<_> = ranked
            .iter()
            .take(k)
            .filter(|x| x.score > 0.0)
            .map(|x| x.candidate_id.as_str())
            .collect();
        tp += predicted.intersection(&positives).count();
        fp += predicted.difference(&positives).count();
        fn_ += positives.difference(&predicted).count();
    }
    let precision = if tp + fp == 0 {
        None
    } else {
        Some(tp as f64 / (tp + fp) as f64)
    };
    let recall = if tp + fn_ == 0 {
        None
    } else {
        Some(tp as f64 / (tp + fn_) as f64)
    };
    let f1 = match (precision, recall) {
        (Some(p), Some(r)) if p + r > 0.0 => Some(2.0 * p * r / (p + r)),
        _ => None,
    };
    Ok(RankMetrics {
        cases: examples.len(),
        mrr: (eligible > 0).then_some(reciprocal / eligible as f64),
        recall_at_k: (eligible > 0).then_some(recall_k / eligible as f64),
        ndcg: (eligible > 0).then_some(ndcg / eligible as f64),
        precision,
        recall,
        f1,
        candidate_coverage: if examples.is_empty() {
            0.0
        } else {
            coverage as f64 / examples.len() as f64
        },
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn binary_score_choice_and_protocol_gates_are_validated() {
        assert_eq!(
            evaluate_binary(&[true, false], &[0.9, 0.2], 0.5)
                .unwrap()
                .accuracy,
            Some(1.0)
        );
        assert_eq!(
            evaluate_score(&[2.0], &[3.0], 0.0, 5.0).unwrap().mae,
            Some(1.0)
        );
        assert_eq!(
            evaluate_choice(&[1], &[vec![0.2, 0.8]]).unwrap().accuracy,
            Some(1.0)
        );
        assert!(evaluate_choice(&[0], &[vec![0.2, 0.2]]).is_err());
        let mut p = QualificationProtocol {
            version: 1,
            dataset_sha256: "sha256:".to_owned() + &"a".repeat(64),
            split_fingerprint: "sha256:".to_owned() + &"b".repeat(64),
            artifact_sha256: "sha256:".to_owned() + &"c".repeat(64),
            calibration_sha256: "sha256:".to_owned() + &"d".repeat(64),
            source_revision: "test".into(),
            rank_k: 5,
            minimum_cases: 10,
            gates: Default::default(),
            fingerprint: String::new(),
        };
        p.freeze().unwrap();
        p.validate(
            &p.dataset_sha256,
            &p.split_fingerprint,
            &p.artifact_sha256,
            &p.calibration_sha256,
        )
        .unwrap();
        p.rank_k = 2;
        assert!(p
            .validate(
                &p.dataset_sha256,
                &p.split_fingerprint,
                &p.artifact_sha256,
                &p.calibration_sha256
            )
            .is_err());
    }
}
