//! Small deterministic nonlinear Rank scorer and CPU trainer (no external backend).
use serde::{Deserialize, Serialize};
use sha2::Digest;
use std::collections::BTreeMap;
use thiserror::Error;

pub const ARCHITECTURE: &str = "sdm-pairwise-tanh-v2";
pub const MAX_HIDDEN: usize = 128;
pub const MAX_FEATURES: usize = 4096;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PairwiseModel {
    pub feature_ids: Vec<String>,
    pub hidden: usize,
    pub input_weights: Vec<f64>,
    pub hidden_bias: Vec<f64>,
    pub output_weights: Vec<f64>,
    pub output_bias: f64,
}
#[derive(Debug, Error)]
pub enum ModelError {
    #[error("invalid model: {0}")]
    Invalid(String),
}

impl PairwiseModel {
    pub fn to_bytes(&self) -> Result<Vec<u8>, ModelError> {
        self.validate()?;
        let bytes = serde_json::to_vec(self).map_err(|e| ModelError::Invalid(e.to_string()))?;
        if bytes.len() > sdm_runtime::V2_MAX_ARTIFACT_BYTES {
            return Err(ModelError::Invalid(
                "model payload exceeds byte bound".into(),
            ));
        }
        Ok(bytes)
    }
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, ModelError> {
        if bytes.len() > sdm_runtime::V2_MAX_ARTIFACT_BYTES {
            return Err(ModelError::Invalid(
                "model payload exceeds byte bound".into(),
            ));
        }
        let model: Self =
            serde_json::from_slice(bytes).map_err(|e| ModelError::Invalid(e.to_string()))?;
        model.validate()?;
        Ok(model)
    }
    pub fn validate(&self) -> Result<(), ModelError> {
        let expected = self
            .hidden
            .checked_mul(self.feature_ids.len())
            .ok_or_else(|| ModelError::Invalid("shape overflow".into()))?;
        if self.hidden == 0
            || self.hidden > MAX_HIDDEN
            || self.feature_ids.is_empty()
            || self.feature_ids.len() > MAX_FEATURES
            || self.input_weights.len() != expected
            || self.hidden_bias.len() != self.hidden
            || self.output_weights.len() != self.hidden
            || self
                .input_weights
                .iter()
                .chain(&self.hidden_bias)
                .chain(&self.output_weights)
                .chain(std::iter::once(&self.output_bias))
                .any(|x| !x.is_finite())
        {
            return Err(ModelError::Invalid("shape or numeric bounds".into()));
        }
        Ok(())
    }
    pub fn score(&self, x: &[f64]) -> Result<f64, ModelError> {
        self.validate()?;
        if x.len() != self.feature_ids.len() || x.iter().any(|v| !v.is_finite()) {
            return Err(ModelError::Invalid("feature vector mismatch".into()));
        }
        let mut y = self.output_bias;
        for h in 0..self.hidden {
            let z = self.hidden_bias[h]
                + self.input_weights[h * x.len()..(h + 1) * x.len()]
                    .iter()
                    .zip(x)
                    .map(|(w, v)| w * v)
                    .sum::<f64>();
            y += self.output_weights[h] * z.tanh();
        }
        if !y.is_finite() {
            return Err(ModelError::Invalid("non-finite score".into()));
        }
        Ok(y)
    }
    pub fn digest(&self) -> Result<String, ModelError> {
        self.validate()?;
        let b = serde_json::to_vec(self).map_err(|e| ModelError::Invalid(e.to_string()))?;
        Ok(format!("sha256:{:x}", sha2::Sha256::digest(b)))
    }
}

/// Stable low-dimensional context/candidate/intersection projection. Each lexical
/// token contributes context, candidate and context×candidate coordinates.
pub fn pair_features(context: &str, candidate: &str, vocabulary: &[String]) -> Vec<f64> {
    let c: BTreeMap<_, _> = context
        .to_lowercase()
        .split_whitespace()
        .map(|t| (t.to_owned(), 1.0))
        .collect();
    let o: BTreeMap<_, _> = candidate
        .to_lowercase()
        .split_whitespace()
        .map(|t| (t.to_owned(), 1.0))
        .collect();
    let mut v = Vec::with_capacity(vocabulary.len() * 3);
    for t in vocabulary {
        let a = c.contains_key(t) as u8 as f64;
        let b = o.contains_key(t) as u8 as f64;
        v.extend([a, b, a * b]);
    }
    v
}

/// Fixed-seed compact tanh network initialization; caller supplies bounded data.
pub fn initialize(
    feature_ids: Vec<String>,
    hidden: usize,
    seed: u64,
) -> Result<PairwiseModel, ModelError> {
    if hidden == 0
        || hidden > MAX_HIDDEN
        || feature_ids.is_empty()
        || feature_ids.len() > MAX_FEATURES
    {
        return Err(ModelError::Invalid("initialization bounds".into()));
    }
    let mut x = seed;
    let mut next = || {
        x = x
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        ((x >> 11) as f64 / (1u64 << 53) as f64 - 0.5) * 0.04
    };
    let n = hidden * feature_ids.len();
    let m = PairwiseModel {
        feature_ids,
        hidden,
        input_weights: (0..n).map(|_| next()).collect(),
        hidden_bias: vec![0.0; hidden],
        output_weights: (0..hidden).map(|_| next()).collect(),
        output_bias: 0.0,
    };
    m.validate()?;
    Ok(m)
}

/// One bounded SGD update on squared error; deterministic and intentionally small.
#[cfg(any(feature = "training", test))]
pub fn train_step(
    model: &mut PairwiseModel,
    x: &[f64],
    target: f64,
    learning_rate: f64,
) -> Result<(), ModelError> {
    if !target.is_finite()
        || !learning_rate.is_finite()
        || learning_rate <= 0.0
        || learning_rate > 1.0
    {
        return Err(ModelError::Invalid("training bounds".into()));
    }
    let pred = model.score(x)?;
    let error = pred - target;
    for h in 0..model.hidden {
        let start = h * x.len();
        let z = model.hidden_bias[h]
            + model.input_weights[start..start + x.len()]
                .iter()
                .zip(x)
                .map(|(w, v)| w * v)
                .sum::<f64>();
        let a = z.tanh();
        let delta = error * model.output_weights[h] * (1.0 - a * a);
        model.output_weights[h] -= learning_rate * error * a;
        model.hidden_bias[h] -= learning_rate * delta;
        for (w, v) in model.input_weights[start..start + x.len()]
            .iter_mut()
            .zip(x)
        {
            *w -= learning_rate * delta * v;
        }
    }
    model.output_bias -= learning_rate * error;
    model.validate()
}

#[cfg(feature = "training")]
#[derive(Debug, Clone, PartialEq)]
pub struct TrainingSummary {
    pub epochs_completed: usize,
    pub examples_seen: usize,
    pub final_mse: f64,
    pub model_sha256: String,
}

#[cfg(feature = "training")]
pub fn train(
    model: &mut PairwiseModel,
    examples: &[(Vec<f64>, f64)],
    epochs: usize,
    learning_rate: f64,
) -> Result<TrainingSummary, ModelError> {
    if examples.is_empty() || epochs == 0 || epochs > 100_000 || examples.len() > 1_000_000 {
        return Err(ModelError::Invalid("training work bounds".into()));
    }
    for (x, y) in examples {
        if x.len() != model.feature_ids.len() || x.iter().any(|v| !v.is_finite()) || !y.is_finite()
        {
            return Err(ModelError::Invalid("invalid training example".into()));
        }
    }
    for _ in 0..epochs {
        for (x, y) in examples {
            train_step(model, x, *y, learning_rate)?;
        }
    }
    let final_mse = examples
        .iter()
        .map(|(x, y)| model.score(x).map(|p| (p - y).powi(2)))
        .collect::<Result<Vec<_>, _>>()?
        .iter()
        .sum::<f64>()
        / examples.len() as f64;
    Ok(TrainingSummary {
        epochs_completed: epochs,
        examples_seen: examples.len() * epochs,
        final_mse,
        model_sha256: model.digest()?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn model_is_finite_bounded_and_seeded() {
        let ids = vec![
            "ctx:alpha".into(),
            "cand:alpha".into(),
            "both:alpha".into(),
            "ctx:beta".into(),
            "cand:beta".into(),
            "both:beta".into(),
        ];
        let mut a = initialize(ids.clone(), 4, 9).unwrap();
        let b = initialize(ids, 4, 9).unwrap();
        assert_eq!(a, b);
        let encoded = a.to_bytes().unwrap();
        assert_eq!(PairwiseModel::from_bytes(&encoded).unwrap(), a);
        let p = pair_features(
            "alpha beta",
            "alpha gamma",
            &["alpha".into(), "beta".into()],
        );
        let before = a.score(&p).unwrap();
        train_step(&mut a, &p, 1.0, 0.01).unwrap();
        assert_ne!(before, a.score(&p).unwrap());
    }

    #[cfg(feature = "training")]
    #[test]
    fn trained_model_uses_pair_features_and_two_capacity_points() {
        let inputs = vec![
            (vec![1.0, 1.0, 1.0, 0.0], 1.0),
            (vec![1.0, 0.0, 0.0, 1.0], 0.0),
            (vec![0.0, 1.0, 0.0, 0.0], 0.0),
        ];
        let ids = vec![
            "context".into(),
            "candidate".into(),
            "interaction".into(),
            "other".into(),
        ];
        for hidden in [4, 8] {
            let mut model = initialize(ids.clone(), hidden, 19).unwrap();
            let result = train(&mut model, &inputs, 20, 0.02).unwrap();
            assert_eq!(result.epochs_completed, 20);
            assert!(result.final_mse.is_finite());
        }
    }
}
