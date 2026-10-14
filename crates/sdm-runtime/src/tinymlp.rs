//! TinyMLP Choice architecture (`sdm-typed-choice-tinymlp-v1`).
//!
//! M016 additive, inference-only, native-CPU Choice head with:
//! - one SHARED context/candidate nonlinear scorer (single hidden layer, tanh),
//! - separately supervised permutation-invariant answerability head
//!   (context + mean/max-pooled candidate summary),
//! - strict bounded validated payload, SHA-before-alloc, finite checks,
//! - 2..=128 Choice options, exact ID membership, no synthetic None option.
//!
//! No training, Python, GPU, network, or file IO in this module. Training lives
//! in `sdm-experiment` (M016 trainer) and produces bytes consumed here.

use sdm_core::{
    DecisionAnswer, DecisionError, DecisionRequest, DecisionResponse, DecisionSpec, DecisionStatus,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

pub const TINYMLP_ARCHITECTURE: &str = "sdm-typed-choice-tinymlp-v1";
pub const TINYMLP_HIDDEN_WIDTHS: [usize; 2] = [32, 64];
pub const TINYMLP_MAX_CANDIDATES: usize = 128;
pub const TINYMLP_MAX_PARAMS: usize = 1_000_000;
pub const TINYMLP_WEIGHT_BOUND: f64 = 1_000_000.0;
pub const TINYMLP_ACTIVATION: &str = "tanh";

/// Encoded batch: (context, per-candidate encodings in sorted-ID order, sorted IDs).
type EncodedBatch = (Vec<f64>, Vec<Vec<f64>>, Vec<String>);

/// Bounded TinyMLP Choice payload (serialized inside `ArtifactEnvelopeV2.payload`).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TinyMlpPayload {
    pub task: String,
    pub encoder: sdm_core::FittedFeatureEncoderV2,
    pub hidden_width: usize,
    pub activation: String,
    /// Row-major `W1`: `(2*D) x H` flattened as `[(2*D)*H]`, index `i*H + h`.
    pub w1: Vec<f64>,
    pub b1: Vec<f64>,
    /// Output layer `W2`: `[H]`, plus scalar `b2`.
    pub w2: Vec<f64>,
    pub b2: f64,
    /// Answerability head over `[context, mean_candidate, max_candidate]` (`3*D`).
    pub answerability_weights: Vec<f64>,
    pub answerability_bias: f64,
    pub training_fingerprint: String,
    pub seed: u64,
}

impl TinyMlpPayload {
    pub fn parameter_count(&self) -> usize {
        self.w1
            .len()
            .saturating_add(self.b1.len())
            .saturating_add(self.w2.len())
            .saturating_add(1)
            .saturating_add(self.answerability_weights.len())
            .saturating_add(1)
    }

    pub fn validate_shapes(&self) -> Result<usize, String> {
        if self.task != "choice" {
            return Err("tinymlp task must be choice".into());
        }
        if self.activation != TINYMLP_ACTIVATION {
            return Err("tinymlp activation must be tanh".into());
        }
        if !TINYMLP_HIDDEN_WIDTHS.contains(&self.hidden_width) {
            return Err("tinymlp hidden width must be 32 or 64".into());
        }
        self.encoder
            .validate()
            .map_err(|e| format!("tinymlp encoder invalid: {e}"))?;
        let dim = self
            .encoder
            .dimension()
            .map_err(|e| format!("tinymlp encoder dimension: {e}"))?;
        if dim == 0 {
            return Err("tinymlp encoder dimension is zero".into());
        }
        let h = self.hidden_width;
        // Preflight multiplication with saturating ops to avoid OOM before alloc.
        let two_d = dim.saturating_mul(2);
        let w1_expected = two_d.saturating_mul(h);
        let ans_expected = dim.saturating_mul(3);
        if w1_expected / h.max(1) != two_d {
            return Err("tinymlp dimension overflow".into());
        }
        if self.w1.len() != w1_expected {
            return Err(format!(
                "tinymlp w1 shape mismatch: got {}, expected {} (2D={} H={})",
                self.w1.len(),
                w1_expected,
                two_d,
                h
            ));
        }
        if self.b1.len() != h {
            return Err("tinymlp b1 shape mismatch".into());
        }
        if self.w2.len() != h {
            return Err("tinymlp w2 shape mismatch".into());
        }
        if self.answerability_weights.len() != ans_expected {
            return Err(format!(
                "tinymlp answerability shape mismatch: got {}, expected {}",
                self.answerability_weights.len(),
                ans_expected
            ));
        }
        for w in self
            .w1
            .iter()
            .chain(&self.b1)
            .chain(&self.w2)
            .chain(&self.answerability_weights)
        {
            if !w.is_finite() || w.abs() > TINYMLP_WEIGHT_BOUND {
                return Err("tinymlp weight non-finite or out of bounds".into());
            }
        }
        if !self.b2.is_finite()
            || self.b2.abs() > TINYMLP_WEIGHT_BOUND
            || !self.answerability_bias.is_finite()
            || self.answerability_bias.abs() > TINYMLP_WEIGHT_BOUND
        {
            return Err("tinymlp bias non-finite or out of bounds".into());
        }
        if self.training_fingerprint.trim().is_empty() {
            return Err("tinymlp training fingerprint is missing".into());
        }
        let params = self.parameter_count();
        if params > TINYMLP_MAX_PARAMS {
            return Err(format!(
                "tinymlp parameter count {} exceeds {}",
                params, TINYMLP_MAX_PARAMS
            ));
        }
        Ok(dim)
    }
}

#[derive(Debug, Clone)]
pub struct TinyMlpChoiceRuntime {
    payload: TinyMlpPayload,
    model_id: String,
    max_candidates: usize,
    threshold: f64,
    digest: String,
}

impl TinyMlpChoiceRuntime {
    pub fn from_envelope(
        envelope: &crate::ArtifactEnvelopeV2,
        payload: TinyMlpPayload,
        threshold: f64,
    ) -> Result<Self, crate::RuntimeError> {
        use crate::RuntimeError;
        // SHA already validated by envelope.validate() before this call (SHA-before-alloc).
        if envelope.architecture != TINYMLP_ARCHITECTURE {
            return Err(RuntimeError::InvalidArtifact(
                "tinymlp architecture mismatch".into(),
            ));
        }
        if envelope.capabilities != ["choice"] {
            return Err(RuntimeError::InvalidArtifact(
                "tinymlp capabilities must be [choice]".into(),
            ));
        }
        if !(2..=TINYMLP_MAX_CANDIDATES).contains(&envelope.max_candidates) {
            return Err(RuntimeError::InvalidArtifact(
                "tinymlp max candidates must be 2..=128".into(),
            ));
        }
        if !threshold.is_finite() || !(0.0..=1.0).contains(&threshold) {
            return Err(RuntimeError::InvalidArtifact(
                "tinymlp threshold must be in [0,1]".into(),
            ));
        }
        let dim = payload
            .validate_shapes()
            .map_err(RuntimeError::InvalidArtifact)?;
        let schema_fp = payload
            .encoder
            .schema
            .fingerprint()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        if schema_fp != envelope.required_feature_schema_sha256 {
            return Err(RuntimeError::InvalidArtifact(
                "tinymlp schema fingerprint mismatch".into(),
            ));
        }
        // Declared param count must match actual (tamper detection).
        if envelope.parameter_count != envelope.payload.len() {
            return Err(RuntimeError::InvalidArtifact(
                "tinymlp parameter count mismatch".into(),
            ));
        }
        let _ = dim;
        Ok(Self {
            payload,
            model_id: envelope.model_id.clone(),
            max_candidates: envelope.max_candidates,
            threshold,
            digest: format!(
                "sha256:{:x}",
                Sha256::digest(
                    serde_json::to_vec(envelope)
                        .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?
                )
            ),
        })
    }

    pub fn from_bytes(bytes: &[u8]) -> Result<Self, crate::RuntimeError> {
        use crate::RuntimeError;
        if bytes.len() > crate::V2_MAX_ARTIFACT_BYTES {
            return Err(RuntimeError::InvalidArtifact(
                "artifact exceeds maximum byte limit".into(),
            ));
        }
        let envelope = crate::ArtifactEnvelopeV2::from_bytes(bytes)?;
        // from_bytes validates SHA before we allocate model tensors.
        if envelope.architecture != TINYMLP_ARCHITECTURE {
            return Err(RuntimeError::InvalidArtifact(
                "unsupported tinymlp architecture".into(),
            ));
        }
        let payload: TinyMlpPayload = serde_json::from_slice(&envelope.payload)
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let calibration: crate::TypedCalibrationShim =
            serde_json::from_slice(&envelope.calibration_payload)
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        calibration.validate()?;
        Self::from_envelope(&envelope, payload, calibration.threshold)
    }

    pub fn digest(&self) -> &str {
        &self.digest
    }
    pub fn model_id(&self) -> &str {
        &self.model_id
    }
    pub fn abstention_threshold(&self) -> f64 {
        self.threshold
    }
    pub fn hidden_width(&self) -> usize {
        self.payload.hidden_width
    }

    /// Shared scorer: `s = W2·tanh(W1·[ctx;cand] + b1) + b2`. No position/ID input.
    fn score_one(&self, context: &[f64], candidate: &[f64]) -> f64 {
        let h = self.payload.hidden_width;
        let mut hidden = vec![0.0; h];
        for (j, hj) in hidden.iter_mut().enumerate() {
            let mut z = self.payload.b1[j];
            for (i, x) in context.iter().chain(candidate.iter()).enumerate() {
                z += x * self.payload.w1[i * h + j];
            }
            *hj = z.tanh();
        }
        let mut s = self.payload.b2;
        for (hh, w) in hidden.iter().zip(&self.payload.w2) {
            s += hh * w;
        }
        s
    }

    /// Symmetric answerability: `a = sigmoid(W·[ctx;mean;max] + b)`.
    /// Mean/max pooling over encoded candidates is permutation invariant.
    fn answerability_from_encodings(&self, context: &[f64], candidates: &[Vec<f64>]) -> f64 {
        let d = context.len();
        if candidates.is_empty() || d == 0 {
            return 0.0;
        }
        let mut mean = vec![0.0; d];
        let mut max = vec![f64::NEG_INFINITY; d];
        for c in candidates {
            for (i, x) in c.iter().enumerate().take(d) {
                mean[i] += *x;
                if *x > max[i] {
                    max[i] = *x;
                }
            }
        }
        let n = candidates.len() as f64;
        for m in &mut mean {
            *m /= n;
        }
        let mut z = self.payload.answerability_bias;
        for (i, x) in context
            .iter()
            .chain(mean.iter())
            .chain(max.iter())
            .enumerate()
        {
            z += x * self.payload.answerability_weights[i];
        }
        1.0 / (1.0 + (-z).exp())
    }

    fn encode_all(
        &self,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<EncodedBatch, DecisionError> {
        let context = self
            .payload
            .encoder
            .encode(&features.context)
            .map_err(|e| DecisionError::InvalidRequest(e.to_string()))?;
        let mut ids: Vec<String> = features.candidates.keys().cloned().collect();
        ids.sort();
        let mut enc = Vec::with_capacity(ids.len());
        for id in &ids {
            let p = features
                .candidates
                .get(id)
                .ok_or_else(|| DecisionError::InvalidRequest("tinymlp candidate missing".into()))?;
            enc.push(
                self.payload
                    .encoder
                    .encode(p)
                    .map_err(|e| DecisionError::InvalidRequest(e.to_string()))?,
            );
        }
        Ok((context, enc, ids))
    }

    fn check_request(
        &self,
        request: &DecisionRequest,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<Vec<sdm_core::DecisionOption>, DecisionError> {
        request.validate()?;
        let DecisionSpec::Choice { options, .. } = &request.spec else {
            return Err(DecisionError::InvalidRequest(
                "tinymlp requires Choice request".into(),
            ));
        };
        if options.len() < 2 || options.len() > self.max_candidates {
            return Err(DecisionError::InvalidRequest(
                "tinymlp option count must be 2..=max_candidates".into(),
            ));
        }
        // Exact ID membership, no synthetic IDs.
        let expected: BTreeSet<_> = options.iter().map(|o| o.id.as_str()).collect();
        let got: BTreeSet<_> = features.candidates.keys().map(String::as_str).collect();
        if expected != got {
            return Err(DecisionError::InvalidRequest(
                "typed option identities mismatch".into(),
            ));
        }
        if features.schema.fingerprint()? != self.payload.encoder.schema.fingerprint()? {
            return Err(DecisionError::InvalidRequest(
                "tinymlp schema differs from artifact".into(),
            ));
        }
        Ok(options.clone())
    }

    pub fn choice_logits(
        &self,
        request: &DecisionRequest,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<Vec<f64>, DecisionError> {
        let options = self.check_request(request, features)?;
        let (context, enc, ids) = self.encode_all(features)?;
        // Map sorted-id encodings back to request option order.
        let id_to_idx: std::collections::BTreeMap<&str, usize> = ids
            .iter()
            .enumerate()
            .map(|(i, id)| (id.as_str(), i))
            .collect();
        options
            .iter()
            .map(|o| {
                let idx = id_to_idx[o.id.as_str()];
                Ok(self.score_one(&context, &enc[idx]))
            })
            .collect()
    }

    pub fn choice_probabilities(
        &self,
        request: &DecisionRequest,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<Vec<f64>, DecisionError> {
        let scores = self.choice_logits(request, features)?;
        if scores.iter().any(|s| !s.is_finite()) {
            return Err(DecisionError::InvalidRequest(
                "tinymlp produced non-finite score".into(),
            ));
        }
        let max = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let exps: Vec<_> = scores.iter().map(|x| (x - max).exp()).collect();
        let sum: f64 = exps.iter().sum();
        if !sum.is_finite() || sum <= 0.0 {
            return Err(DecisionError::InvalidRequest(
                "tinymlp softmax normalization failed".into(),
            ));
        }
        Ok(exps.into_iter().map(|x| x / sum).collect())
    }

    pub fn choice_answerability_probability(
        &self,
        request: &DecisionRequest,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<f64, DecisionError> {
        self.check_request(request, features)?;
        let (context, enc, _) = self.encode_all(features)?;
        let a = self.answerability_from_encodings(&context, &enc);
        if !a.is_finite() {
            return Err(DecisionError::InvalidRequest(
                "tinymlp answerability non-finite".into(),
            ));
        }
        Ok(a)
    }

    pub fn decide_typed(
        &self,
        request: &DecisionRequest,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<DecisionResponse, DecisionError> {
        let options = self.check_request(request, features)?;
        let (context, enc, ids) = self.encode_all(features)?;
        let a = self.answerability_from_encodings(&context, &enc);
        if !a.is_finite() {
            return Err(DecisionError::InvalidRequest(
                "tinymlp answerability non-finite".into(),
            ));
        }
        let id_to_idx: std::collections::BTreeMap<&str, usize> = ids
            .iter()
            .enumerate()
            .map(|(i, id)| (id.as_str(), i))
            .collect();
        let scores: Vec<f64> = options
            .iter()
            .map(|o| self.score_one(&context, &enc[id_to_idx[o.id.as_str()]]))
            .collect();
        if scores.iter().any(|s| !s.is_finite()) {
            return Err(DecisionError::InvalidRequest(
                "tinymlp produced non-finite score".into(),
            ));
        }
        let answer = if a < self.threshold {
            None
        } else {
            // Deterministic argmax: higher score wins, ties resolve to the
            // smaller option ID (same pattern as legacy TypedTaskRuntime).
            let probs = {
                let max = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                let exps: Vec<_> = scores.iter().map(|x| (x - max).exp()).collect();
                let sum: f64 = exps.iter().sum();
                exps.into_iter().map(|x| x / sum).collect::<Vec<_>>()
            };
            let best = (0..options.len())
                .max_by(|x, y| {
                    scores[*x]
                        .total_cmp(&scores[*y])
                        .then_with(|| options[*y].id.cmp(&options[*x].id))
                })
                .unwrap_or(0);
            Some(DecisionAnswer::Choice {
                option_id: options[best].id.clone(),
                probability: Some(probs[best]),
            })
        };
        Ok(DecisionResponse {
            request_id: request.request_id.clone(),
            schema_version: 1,
            status: if answer.is_some() {
                DecisionStatus::Answered
            } else {
                DecisionStatus::Abstained {
                    reason: Some("tinymlp answerability below dev threshold".into()),
                }
            },
            answer,
            provenance: sdm_core::DecisionProvenance {
                backend: "sdm-typed-choice-tinymlp-v1".into(),
                model: Some(self.model_id.clone()),
                runtime_version: Some(crate::RUNTIME_VERSION.into()),
                latency_micros: 0,
            },
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sdm_core::{
        DecisionOption, DecisionRequest, FeatureField, FeatureProjectionV2, FeatureSchemaField,
        FeatureSchemaV2, FeatureType, FeatureValue, TypedRankProjectionV2,
    };
    use std::collections::BTreeMap;

    fn tiny_schema() -> FeatureSchemaV2 {
        FeatureSchemaV2 {
            version: 2,
            fields: vec![
                FeatureSchemaField {
                    id: "active".into(),
                    value_type: FeatureType::Boolean,
                    required: true,
                    categories: vec![],
                },
                FeatureSchemaField {
                    id: "role".into(),
                    value_type: FeatureType::Category,
                    required: true,
                    categories: vec!["no".into(), "yes".into()],
                },
            ],
        }
    }

    fn proj(schema: &FeatureSchemaV2, active: bool, role: &str) -> FeatureProjectionV2 {
        FeatureProjectionV2 {
            schema_version: 2,
            schema_sha256: schema.fingerprint().unwrap(),
            fields: vec![
                FeatureField {
                    id: "active".into(),
                    required: true,
                    value: Some(FeatureValue::Boolean(active)),
                },
                FeatureField {
                    id: "role".into(),
                    required: true,
                    value: Some(FeatureValue::Category(role.into())),
                },
            ],
        }
    }

    fn tiny_payload(encoder: &sdm_core::FittedFeatureEncoderV2, hidden: usize) -> TinyMlpPayload {
        let dim = encoder.dimension().unwrap();
        // Deterministic small weights: w1[i*H+j] = 0.01*((i+j)%7 - 3), etc.
        let w1: Vec<f64> = (0..2 * dim * hidden)
            .map(|k| 0.01 * (((k % 7) as f64) - 3.0))
            .collect();
        let b1 = vec![0.0; hidden];
        let w2: Vec<f64> = (0..hidden)
            .map(|k| 0.05 * (((k % 5) as f64) - 2.0))
            .collect();
        let ans: Vec<f64> = (0..3 * dim)
            .map(|k| 0.02 * (((k % 5) as f64) - 2.0))
            .collect();
        TinyMlpPayload {
            task: "choice".into(),
            encoder: encoder.clone(),
            hidden_width: hidden,
            activation: TINYMLP_ACTIVATION.into(),
            w1,
            b1,
            w2,
            b2: 0.0,
            answerability_weights: ans,
            answerability_bias: 2.0,
            training_fingerprint: "sha256:test-train".into(),
            seed: 16016,
        }
    }

    fn tiny_fixture(
        hidden: usize,
    ) -> (TinyMlpChoiceRuntime, DecisionRequest, TypedRankProjectionV2) {
        let schema = tiny_schema();
        let encoder = sdm_core::FittedFeatureEncoderV2::fit(
            &schema,
            &[proj(&schema, true, "yes"), proj(&schema, true, "no")],
        )
        .unwrap();
        let payload = tiny_payload(&encoder, hidden);
        let env = crate::ArtifactEnvelopeV2::for_typed_choice_tinymlp(
            &encoder,
            payload,
            0.5,
            "sha256:test-cal",
            "tiny-test",
            8,
        )
        .unwrap();
        let rt = TinyMlpChoiceRuntime::from_bytes(&serde_json::to_vec(&env).unwrap()).unwrap();
        let request = DecisionRequest {
            request_id: "tiny-test".into(),
            schema_version: 1,
            state: vec![],
            spec: DecisionSpec::Choice {
                question: "select".into(),
                options: vec![
                    DecisionOption {
                        id: "alpha".into(),
                        label: "first".into(),
                    },
                    DecisionOption {
                        id: "beta".into(),
                        label: "second".into(),
                    },
                ],
            },
        };
        let features = TypedRankProjectionV2 {
            schema: schema.clone(),
            context: proj(&schema, true, "no"),
            candidates: BTreeMap::from([
                ("alpha".into(), proj(&schema, true, "no")),
                ("beta".into(), proj(&schema, true, "yes")),
            ]),
        };
        (rt, request, features)
    }

    #[test]
    fn tinymlp_scores_are_finite_and_order_invariant() {
        let (rt, request, features) = tiny_fixture(32);
        let logits = rt.choice_logits(&request, &features).unwrap();
        assert_eq!(logits.len(), 2);
        assert!(logits.iter().all(|s| s.is_finite()));
        let probs = rt.choice_probabilities(&request, &features).unwrap();
        assert!((probs.iter().sum::<f64>() - 1.0).abs() < 1e-9);
        // Reversed option order permutes outputs (order equivariance, no position input).
        let mut reversed = request.clone();
        if let DecisionSpec::Choice { options, .. } = &mut reversed.spec {
            options.reverse();
        }
        let reordered = rt.choice_probabilities(&reversed, &features).unwrap();
        assert!((reordered[0] - probs[1]).abs() < 1e-12);
        assert!((reordered[1] - probs[0]).abs() < 1e-12);
    }

    #[test]
    fn tinymlp_answerability_is_candidate_symmetric() {
        let (rt, request, features) = tiny_fixture(32);
        let a1 = rt
            .choice_answerability_probability(&request, &features)
            .unwrap();
        // Swap candidate payloads with relabeled IDs: symmetric summary unchanged.
        let mut swapped = features.clone();
        let alpha = swapped.candidates.remove("alpha").unwrap();
        let beta = swapped.candidates.remove("beta").unwrap();
        swapped.candidates.insert("alpha".into(), beta);
        swapped.candidates.insert("beta".into(), alpha);
        let a2 = rt
            .choice_answerability_probability(&request, &swapped)
            .unwrap();
        assert!((a1 - a2).abs() < 1e-12, "{a1} vs {a2}");
    }

    #[test]
    fn tinymlp_rejects_mismatched_ids_and_bad_counts() {
        let (rt, request, features) = tiny_fixture(32);
        // Mismatched IDs fail closed.
        let mut bad = features.clone();
        bad.candidates.remove("beta");
        bad.candidates
            .insert("gamma".into(), proj(&tiny_schema(), true, "yes"));
        assert!(rt.choice_logits(&request, &bad).is_err());
        // 0/1 options fail closed (request validation, never synthetic None).
        let mut one = request.clone();
        if let DecisionSpec::Choice { options, .. } = &mut one.spec {
            options.truncate(1);
        }
        assert!(rt.decide_typed(&one, &features).is_err());
    }

    #[test]
    fn tinymlp_rejects_bad_shapes_and_nonfinite() {
        let schema = tiny_schema();
        let encoder = sdm_core::FittedFeatureEncoderV2::fit(
            &schema,
            &[proj(&schema, true, "yes"), proj(&schema, true, "no")],
        )
        .unwrap();
        let mut p = tiny_payload(&encoder, 32);
        p.w1.truncate(p.w1.len() - 1);
        assert!(p.validate_shapes().is_err());
        let mut p2 = tiny_payload(&encoder, 32);
        p2.w2[0] = f64::INFINITY;
        assert!(p2.validate_shapes().is_err());
        let p3 = tiny_payload(&encoder, 33);
        assert!(p3.validate_shapes().is_err());
        let mut p4 = tiny_payload(&encoder, 32);
        p4.task = "binary".into();
        assert!(p4.validate_shapes().is_err());
    }

    #[test]
    fn tinymlp_decide_picks_maximum_score_option() {
        // Regression: decide_typed must answer the argmax-logit option when
        // answerable (an inverted comparison once returned the minimum).
        let (rt, request, features) = tiny_fixture(32);
        let logits = rt.choice_logits(&request, &features).unwrap();
        let probs = rt.choice_probabilities(&request, &features).unwrap();
        let a = rt
            .choice_answerability_probability(&request, &features)
            .unwrap();
        assert!(a >= 0.5, "fixture must be answerable, got {a}");
        let resp = rt.decide_typed(&request, &features).unwrap();
        let expected_best = logits
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.total_cmp(b.1))
            .map(|x| x.0)
            .unwrap();
        let sdm_core::DecisionSpec::Choice { options, .. } = &request.spec else {
            panic!("fixture must be Choice");
        };
        match resp.answer {
            Some(sdm_core::DecisionAnswer::Choice {
                option_id,
                probability,
            }) => {
                assert_eq!(option_id, options[expected_best].id);
                assert!((probability.unwrap() - probs[expected_best]).abs() < 1e-12);
            }
            other => panic!("expected answered Choice, got {other:?}"),
        }
        // Three-option fixture: the winner must be the unique max, not min.
        let mut three = request.clone();
        if let DecisionSpec::Choice { options, .. } = &mut three.spec {
            options.push(DecisionOption {
                id: "gamma".into(),
                label: "third".into(),
            });
        }
        let mut feat3 = features.clone();
        feat3
            .candidates
            .insert("gamma".into(), proj(&tiny_schema(), false, "no"));
        let logits3 = rt.choice_logits(&three, &feat3).unwrap();
        assert_eq!(logits3.len(), 3);
        let resp3 = rt.decide_typed(&three, &feat3).unwrap();
        let best3 = logits3
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.total_cmp(b.1))
            .map(|x| x.0)
            .unwrap();
        let sdm_core::DecisionSpec::Choice { options: opts3, .. } = &three.spec else {
            panic!("fixture must be Choice");
        };
        match resp3.answer {
            Some(sdm_core::DecisionAnswer::Choice { option_id, .. }) => {
                assert_eq!(option_id, opts3[best3].id);
            }
            other => panic!("expected answered Choice, got {other:?}"),
        }
    }

    #[test]
    fn tinymlp_fixture_parity() {
        // M16-7 same-artifact cross-host parity: the committed M016 selected
        // artifact must decide identically on every host over a fixed DEV
        // sample. Decisions match exactly; probabilities use 1e-9 tolerance
        // for libm variation. Fails closed when fixtures are absent.
        let art_path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../fixtures/m016-tinymlp-selected.artifact.json"
        );
        let sample_path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../fixtures/m016-parity-sample.json"
        );
        let bytes = std::fs::read(art_path).expect("m016 fixture artifact missing");
        let rt = TinyMlpChoiceRuntime::from_bytes(&bytes).expect("fixture must load");
        let sample: serde_json::Value = serde_json::from_slice(
            &std::fs::read(sample_path).expect("m016 parity sample missing"),
        )
        .unwrap();
        assert_eq!(sample["schema"], "sdm-m016-parity-v1");
        let rows = sample["rows"].as_array().unwrap();
        assert!(!rows.is_empty(), "parity sample must not be empty");
        for row in rows {
            let case_id = row["case_id"].as_str().unwrap();
            let request: DecisionRequest = serde_json::from_value(row["request"].clone()).unwrap();
            let features: TypedRankProjectionV2 =
                serde_json::from_value(row["features"].clone()).unwrap();
            let resp = rt.decide_typed(&request, &features).unwrap();
            let predicted = match resp.answer {
                Some(sdm_core::DecisionAnswer::Choice { option_id, .. }) => {
                    serde_json::Value::from(option_id)
                }
                None => serde_json::Value::Null,
                _ => panic!("{case_id}: non-Choice answer"),
            };
            assert_eq!(
                predicted, row["expected_predicted"],
                "{case_id}: decision parity"
            );
            let probs = rt.choice_probabilities(&request, &features).unwrap();
            let expected = row["expected_probs"].as_array().unwrap();
            assert_eq!(probs.len(), expected.len(), "{case_id}: prob length");
            for (p, e) in probs.iter().zip(expected) {
                assert!(
                    (p - e.as_f64().unwrap()).abs() <= 1e-9,
                    "{case_id}: prob parity {p} vs {e}"
                );
            }
            let a = rt
                .choice_answerability_probability(&request, &features)
                .unwrap();
            assert!(
                (a - row["expected_answerability"].as_f64().unwrap()).abs() <= 1e-9,
                "{case_id}: answerability parity"
            );
        }
    }

    #[test]
    fn tinymlp_hidden_64_validates() {
        let (rt, _, _) = tiny_fixture(64);
        assert_eq!(rt.hidden_width(), 64);
    }
}
