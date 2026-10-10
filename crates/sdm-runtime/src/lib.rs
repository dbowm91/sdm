//! Small, offline decision-model runtime. This crate has no training or network dependency.
pub use sdm_core::{features_for, features_for_tokens, tokens};
use sdm_core::{
    DecisionAnswer, DecisionCandidate, DecisionError, DecisionProvenance, DecisionRequest,
    DecisionResponse, DecisionSpec, DecisionStatus, RankedDecisionCandidate,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

pub const ARTIFACT_SCHEMA: u16 = 1;
pub const RUNTIME_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const MAX_ARTIFACT_BYTES: usize = 4 * 1024 * 1024;
pub const ARTIFACT_ENVELOPE_V2: u16 = 2;
pub const V2_MAX_ARTIFACT_BYTES: usize = 16 * 1024 * 1024;
pub const V2_MAX_TENSOR_ELEMENTS: usize = 1_000_000;

/// Explicit additive envelope for architecture-specific payloads. Digests
/// detect corruption and establish identity, not author authenticity.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ArtifactEnvelopeV2 {
    pub schema_version: u16,
    pub architecture: String,
    pub model_id: String,
    pub required_feature_schema_sha256: String,
    pub capabilities: Vec<String>,
    pub max_candidates: usize,
    pub parameter_count: usize,
    pub tensor_payload_sha256: String,
    pub calibration_sha256: String,
    pub calibration_payload: Vec<u8>,
    pub license: String,
    pub source: String,
    pub payload: Vec<u8>,
}

impl ArtifactEnvelopeV2 {
    #[allow(clippy::too_many_arguments)]
    pub fn for_typed_task(
        task: &str,
        encoder: &sdm_core::FittedFeatureEncoderV2,
        weights: Vec<f64>,
        bias: f64,
        answerability_weights: Option<Vec<f64>>,
        answerability_bias: Option<f64>,
        threshold: f64,
        calibration_fingerprint: impl Into<String>,
        training_fingerprint: impl Into<String>,
        model_id: impl Into<String>,
        max_candidates: usize,
    ) -> Result<Self, RuntimeError> {
        if !["binary", "choice", "score"].contains(&task)
            || !bias.is_finite()
            || !threshold.is_finite()
            || !(0.0..=1.0).contains(&threshold)
        {
            return Err(RuntimeError::InvalidArtifact(
                "invalid typed task metadata".into(),
            ));
        }
        encoder
            .validate()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let dim = encoder
            .dimension()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let multiplier = if task == "choice" { 3 } else { 2 };
        if weights.len() != dim.saturating_mul(multiplier)
            || weights
                .iter()
                .any(|w| !w.is_finite() || w.abs() > 1_000_000.0)
            || bias.abs() > 1_000_000.0
        {
            return Err(RuntimeError::InvalidArtifact(
                "typed task weight shape or value mismatch".into(),
            ));
        }
        if task == "choice" {
            if answerability_weights.as_ref().is_none_or(|v| {
                v.len() != dim || v.iter().any(|w| !w.is_finite() || w.abs() > 1_000_000.0)
            }) || answerability_bias.is_none_or(|b| !b.is_finite() || b.abs() > 1_000_000.0)
            {
                return Err(RuntimeError::InvalidArtifact(
                    "Choice answerability head is missing or malformed".into(),
                ));
            }
        } else if answerability_weights.is_some() || answerability_bias.is_some() {
            return Err(RuntimeError::InvalidArtifact(
                "unexpected answerability head".into(),
            ));
        }
        let payload = serde_json::to_vec(&TypedTaskPayload {
            task: task.into(),
            encoder: encoder.clone(),
            weights,
            bias,
            answerability_weights,
            answerability_bias,
            training_fingerprint: training_fingerprint.into(),
        })
        .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let calibration_payload = serde_json::to_vec(&TypedCalibration {
            threshold,
            dev_fingerprint: calibration_fingerprint.into(),
            policy: "dev-answerability-v1".into(),
        })
        .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let envelope = Self {
            schema_version: ARTIFACT_ENVELOPE_V2,
            architecture: "sdm-typed-task-v1".into(),
            model_id: model_id.into(),
            required_feature_schema_sha256: encoder
                .schema
                .fingerprint()
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?,
            capabilities: vec![task.into()],
            max_candidates,
            parameter_count: payload.len(),
            tensor_payload_sha256: format!("sha256:{:x}", Sha256::digest(&payload)),
            calibration_sha256: format!("sha256:{:x}", Sha256::digest(&calibration_payload)),
            calibration_payload,
            license: "MIT".into(),
            source: "sdm-experiment".into(),
            payload,
        };
        envelope.validate()?;
        Ok(envelope)
    }
    #[allow(clippy::too_many_arguments)]
    pub fn for_typed_rank(
        encoder: &sdm_core::FittedFeatureEncoderV2,
        weights: Vec<f64>,
        bias: f64,
        threshold: f64,
        calibration_fingerprint: impl Into<String>,
        training_fingerprint: impl Into<String>,
        model_id: impl Into<String>,
        max_candidates: usize,
    ) -> Result<Self, RuntimeError> {
        encoder
            .validate()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        if !bias.is_finite() || !threshold.is_finite() || !(0.0..=1.0).contains(&threshold) {
            return Err(RuntimeError::InvalidArtifact(
                "invalid typed Rank parameters".into(),
            ));
        }
        let dim = encoder
            .dimension()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        if weights.len() != dim.saturating_mul(2) || weights.iter().any(|x| !x.is_finite()) {
            return Err(RuntimeError::InvalidArtifact(
                "typed Rank weight shape or value mismatch".into(),
            ));
        }
        let payload = serde_json::to_vec(&TypedRankPayload {
            encoder: encoder.clone(),
            weights,
            bias,
            training_fingerprint: training_fingerprint.into(),
        })
        .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let calibration_payload = serde_json::to_vec(&TypedCalibration {
            threshold,
            dev_fingerprint: calibration_fingerprint.into(),
            policy: "dev-max-relevance-v1".into(),
        })
        .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let envelope = Self {
            schema_version: ARTIFACT_ENVELOPE_V2,
            architecture: "sdm-typed-linear-rank-v1".into(),
            model_id: model_id.into(),
            required_feature_schema_sha256: encoder
                .schema
                .fingerprint()
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?,
            capabilities: vec!["rank".into()],
            max_candidates,
            parameter_count: payload.len(),
            tensor_payload_sha256: format!("sha256:{:x}", Sha256::digest(&payload)),
            calibration_sha256: format!("sha256:{:x}", Sha256::digest(&calibration_payload)),
            calibration_payload,
            license: "MIT".into(),
            source: "sdm-experiment".into(),
            payload,
        };
        envelope.validate()?;
        Ok(envelope)
    }
    pub fn for_nonlinear(
        model: &sdm_nonlinear::PairwiseModel,
        model_id: impl Into<String>,
        max_candidates: usize,
        threshold: f64,
        license: impl Into<String>,
        source: impl Into<String>,
    ) -> Result<Self, RuntimeError> {
        validate_nonlinear_rank_schema(model)?;
        if !threshold.is_finite() || !(0.0..=1.0).contains(&threshold) {
            return Err(RuntimeError::InvalidArtifact(
                "invalid nonlinear threshold".into(),
            ));
        }
        let payload = model
            .to_bytes()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let calibration_payload = serde_json::to_vec(&RankCalibration { threshold })
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let envelope = Self {
            schema_version: ARTIFACT_ENVELOPE_V2,
            architecture: sdm_nonlinear::ARCHITECTURE.into(),
            model_id: model_id.into(),
            required_feature_schema_sha256: model
                .feature_schema_sha256()
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?,
            capabilities: vec!["rank".into()],
            max_candidates,
            parameter_count: model
                .parameter_count()
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?,
            tensor_payload_sha256: format!("sha256:{:x}", Sha256::digest(&payload)),
            calibration_sha256: format!("sha256:{:x}", Sha256::digest(&calibration_payload)),
            calibration_payload,
            license: license.into(),
            source: source.into(),
            payload,
        };
        envelope.validate()?;
        Ok(envelope)
    }

    pub fn from_bytes(bytes: &[u8]) -> Result<Self, RuntimeError> {
        if bytes.len() > V2_MAX_ARTIFACT_BYTES {
            return Err(RuntimeError::InvalidArtifact(
                "v2 artifact exceeds byte limit".into(),
            ));
        }
        let value: Self = serde_json::from_slice(bytes)
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        value.validate()?;
        Ok(value)
    }

    pub fn validate(&self) -> Result<(), RuntimeError> {
        if self.schema_version != ARTIFACT_ENVELOPE_V2 {
            return Err(RuntimeError::InvalidArtifact(
                "unsupported envelope version".into(),
            ));
        }
        if self.architecture.is_empty()
            || self.model_id.is_empty()
            || self.source.is_empty()
            || self.license.is_empty()
        {
            return Err(RuntimeError::InvalidArtifact(
                "missing artifact identity or provenance".into(),
            ));
        }
        if self.max_candidates == 0
            || self.max_candidates > sdm_core::MAX_CANDIDATES
            || self.parameter_count > V2_MAX_TENSOR_ELEMENTS
            || self.payload.len() > V2_MAX_ARTIFACT_BYTES
        {
            return Err(RuntimeError::InvalidArtifact(
                "v2 resource limit exceeded".into(),
            ));
        }
        if self.capabilities.is_empty()
            || self
                .capabilities
                .iter()
                .any(|c| !["binary", "choice", "score", "rank"].contains(&c.as_str()))
        {
            return Err(RuntimeError::InvalidArtifact(
                "invalid capability declaration".into(),
            ));
        }
        let actual = format!("sha256:{:x}", Sha256::digest(&self.payload));
        if self.tensor_payload_sha256 != actual {
            return Err(RuntimeError::InvalidArtifact(
                "payload digest mismatch".into(),
            ));
        }
        if self.calibration_payload.len() > 4096
            || self.calibration_sha256
                != format!("sha256:{:x}", Sha256::digest(&self.calibration_payload))
        {
            return Err(RuntimeError::InvalidArtifact(
                "calibration payload digest mismatch or size limit".into(),
            ));
        }
        for digest in [
            &self.required_feature_schema_sha256,
            &self.calibration_sha256,
        ] {
            if !digest.starts_with("sha256:") || digest.len() != 71 {
                return Err(RuntimeError::InvalidArtifact(
                    "invalid manifest digest".into(),
                ));
            }
        }
        Ok(())
    }
}

pub fn parameter_digest(bias: f64, weights: &BTreeMap<String, f64>) -> String {
    let mut bytes = bias.to_bits().to_le_bytes().to_vec();
    for (name, value) in weights {
        bytes.extend_from_slice(&(name.len() as u64).to_le_bytes());
        bytes.extend_from_slice(name.as_bytes());
        bytes.extend_from_slice(&value.to_bits().to_le_bytes());
    }
    format!("sha256:{:x}", Sha256::digest(bytes))
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ArtifactManifest {
    pub schema_version: u16,
    pub architecture: String,
    pub input_schema_version: u16,
    pub capabilities: Vec<String>,
    pub max_state_bytes: usize,
    pub max_candidates: usize,
    pub model_sha256: String,
    pub training_fingerprint: String,
    pub calibration_version: u16,
    pub calibration_sha256: String,
    pub license: String,
    pub source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct LinearArtifact {
    pub manifest: ArtifactManifest,
    /// Intercept and sparse token weights for a bounded binary relevance model.
    pub bias: f64,
    pub weights: BTreeMap<String, f64>,
    pub threshold: f64,
}

#[derive(Debug, Clone)]
pub struct Runtime {
    artifact: LinearArtifact,
    digest: String,
}

#[derive(Debug, Clone)]
pub enum LoadedArtifact {
    LinearV1(Runtime),
    NonlinearV2(NonlinearRuntime),
    TypedRankV2(TypedRankRuntime),
    TypedTaskV2(TypedTaskRuntime),
    UnsupportedV2(ArtifactEnvelopeV2),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RankCalibration {
    threshold: f64,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
struct TypedCalibration {
    threshold: f64,
    dev_fingerprint: String,
    policy: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TypedRankPayload {
    encoder: sdm_core::FittedFeatureEncoderV2,
    weights: Vec<f64>,
    bias: f64,
    training_fingerprint: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TypedTaskPayload {
    task: String,
    encoder: sdm_core::FittedFeatureEncoderV2,
    weights: Vec<f64>,
    bias: f64,
    #[serde(default)]
    answerability_weights: Option<Vec<f64>>,
    #[serde(default)]
    answerability_bias: Option<f64>,
    training_fingerprint: String,
}
#[derive(Debug, Clone)]
pub struct TypedTaskRuntime {
    payload: TypedTaskPayload,
    model_id: String,
    max_candidates: usize,
    threshold: f64,
    digest: String,
}

impl TypedTaskRuntime {
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, RuntimeError> {
        let envelope = ArtifactEnvelopeV2::from_bytes(bytes)?;
        if envelope.architecture != "sdm-typed-task-v1" {
            return Err(RuntimeError::InvalidArtifact(
                "unsupported typed task architecture".into(),
            ));
        }
        let payload: TypedTaskPayload = serde_json::from_slice(&envelope.payload)
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        payload
            .encoder
            .validate()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let dim = payload
            .encoder
            .dimension()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        if !["binary", "choice", "score"].contains(&payload.task.as_str())
            || envelope.capabilities != [payload.task.as_str()]
            || payload.weights.len()
                != dim.saturating_mul(if payload.task == "choice" { 3 } else { 2 })
            || payload
                .weights
                .iter()
                .any(|w| !w.is_finite() || w.abs() > 1_000_000.0)
            || !payload.bias.is_finite()
            || payload.bias.abs() > 1_000_000.0
            || payload.training_fingerprint.is_empty()
            || payload
                .encoder
                .schema
                .fingerprint()
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?
                != envelope.required_feature_schema_sha256
        {
            return Err(RuntimeError::InvalidArtifact(
                "invalid typed task payload".into(),
            ));
        }
        if payload.task == "choice" {
            if payload.answerability_weights.as_ref().is_none_or(|v| {
                v.len() != dim || v.iter().any(|w| !w.is_finite() || w.abs() > 1_000_000.0)
            }) || payload
                .answerability_bias
                .is_none_or(|b| !b.is_finite() || b.abs() > 1_000_000.0)
            {
                return Err(RuntimeError::InvalidArtifact(
                    "Choice answerability head is malformed".into(),
                ));
            }
        } else if payload.answerability_weights.is_some() || payload.answerability_bias.is_some() {
            return Err(RuntimeError::InvalidArtifact(
                "unexpected answerability head".into(),
            ));
        }
        let calibration: TypedCalibration =
            serde_json::from_slice(&envelope.calibration_payload)
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        if !calibration.threshold.is_finite()
            || !(0.0..=1.0).contains(&calibration.threshold)
            || calibration.dev_fingerprint.is_empty()
            || calibration.policy != "dev-answerability-v1"
        {
            return Err(RuntimeError::InvalidArtifact(
                "invalid typed task calibration".into(),
            ));
        }
        Ok(Self {
            payload,
            model_id: envelope.model_id,
            max_candidates: envelope.max_candidates,
            threshold: calibration.threshold,
            digest: format!("sha256:{:x}", Sha256::digest(bytes)),
        })
    }
    pub fn digest(&self) -> &str {
        &self.digest
    }
    pub fn binary_probability(
        &self,
        request: &DecisionRequest,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<f64, DecisionError> {
        request.validate()?;
        if self.payload.task != "binary"
            || !matches!(request.spec, sdm_core::DecisionSpec::Binary { .. })
            || features.schema.fingerprint()? != self.payload.encoder.schema.fingerprint()?
        {
            return Err(DecisionError::InvalidRequest(
                "binary task or schema mismatch".into(),
            ));
        }
        features.context.validate_for(&features.schema)?;
        if !features.candidates.is_empty() {
            return Err(DecisionError::InvalidRequest(
                "Binary typed input cannot contain options".into(),
            ));
        }
        let context = self.payload.encoder.encode(&features.context)?;
        Ok(1.0 / (1.0 + (-self.score(&context, None)?).exp()))
    }
    fn score(
        &self,
        context: &[f64],
        item: Option<&sdm_core::FeatureProjectionV2>,
    ) -> Result<f64, DecisionError> {
        let mut x = context.to_vec();
        if let Some(p) = item {
            let item = self.payload.encoder.encode(p)?;
            x.extend(item.iter().copied());
            if self.payload.task == "choice" {
                x.extend(context.iter().zip(&item).map(|(a, b)| a * b));
            }
        } else {
            x.resize(
                context.len() * if self.payload.task == "choice" { 3 } else { 2 },
                0.0,
            );
        }
        Ok(x.iter()
            .zip(&self.payload.weights)
            .map(|(a, b)| a * b)
            .sum::<f64>()
            + self.payload.bias)
    }
    fn answerability(&self, context: &[f64]) -> f64 {
        let weights = self
            .payload
            .answerability_weights
            .as_ref()
            .expect("validated Choice head");
        1.0 / (1.0
            + (-(context.iter().zip(weights).map(|(x, w)| x * w).sum::<f64>()
                + self.payload.answerability_bias.unwrap_or(0.0)))
            .exp())
    }
    pub fn choice_probabilities(
        &self,
        request: &DecisionRequest,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<Vec<f64>, DecisionError> {
        request.validate()?;
        let sdm_core::DecisionSpec::Choice { options, .. } = &request.spec else {
            return Err(DecisionError::InvalidRequest(
                "choice probabilities require Choice request".into(),
            ));
        };
        if self.payload.task != "choice"
            || options.len() > self.max_candidates
            || features.schema.fingerprint()? != self.payload.encoder.schema.fingerprint()?
        {
            return Err(DecisionError::InvalidRequest(
                "choice task or schema mismatch".into(),
            ));
        }
        let expected: std::collections::BTreeSet<_> =
            options.iter().map(|o| o.id.as_str()).collect();
        if features
            .candidates
            .keys()
            .map(String::as_str)
            .collect::<std::collections::BTreeSet<_>>()
            != expected
        {
            return Err(DecisionError::InvalidRequest(
                "typed option identities mismatch".into(),
            ));
        }
        let context = self.payload.encoder.encode(&features.context)?;
        let scores = options
            .iter()
            .map(|o| self.score(&context, Some(&features.candidates[&o.id])))
            .collect::<Result<Vec<_>, _>>()?;
        let max = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let exps: Vec<_> = scores.iter().map(|x| (x - max).exp()).collect();
        let sum = exps.iter().sum::<f64>();
        Ok(exps.into_iter().map(|x| x / sum).collect())
    }
    pub fn decide_typed(
        &self,
        request: &DecisionRequest,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<DecisionResponse, DecisionError> {
        request.validate()?;
        let task = match request.spec {
            sdm_core::DecisionSpec::Binary { .. } => "binary",
            sdm_core::DecisionSpec::Choice { .. } => "choice",
            sdm_core::DecisionSpec::Score { .. } => "score",
            sdm_core::DecisionSpec::Rank { .. } => {
                return Err(DecisionError::InvalidRequest(
                    "typed task artifact does not support Rank".into(),
                ))
            }
        };
        if task != self.payload.task {
            return Err(DecisionError::InvalidRequest(
                "typed artifact/task mismatch".into(),
            ));
        }
        if features.schema.fingerprint()? != self.payload.encoder.schema.fingerprint()? {
            return Err(DecisionError::InvalidRequest(
                "typed schema differs from artifact".into(),
            ));
        }
        features.context.validate_for(&features.schema)?;
        let expected: std::collections::BTreeSet<&str> = match &request.spec {
            sdm_core::DecisionSpec::Choice { options, .. } => {
                options.iter().map(|o| o.id.as_str()).collect()
            }
            _ => std::collections::BTreeSet::new(),
        };
        if features
            .candidates
            .keys()
            .map(String::as_str)
            .collect::<std::collections::BTreeSet<_>>()
            != expected
        {
            return Err(DecisionError::InvalidRequest(
                "typed option identities mismatch".into(),
            ));
        }
        let context = self.payload.encoder.encode(&features.context)?;
        let (status, answer) = match &request.spec {
            sdm_core::DecisionSpec::Binary { .. } => {
                let p = 1.0 / (1.0 + (-self.score(&context, None)?).exp());
                let confidence = p.max(1.0 - p);
                if confidence < self.threshold {
                    (
                        sdm_core::DecisionStatus::Abstained {
                            reason: Some("typed binary confidence below dev threshold".into()),
                        },
                        None,
                    )
                } else {
                    (
                        sdm_core::DecisionStatus::Answered,
                        Some(DecisionAnswer::Binary {
                            probability_true: p,
                            confidence: Some(confidence),
                        }),
                    )
                }
            }
            sdm_core::DecisionSpec::Choice { options, .. } => {
                if options.len() > self.max_candidates {
                    return Err(DecisionError::InvalidRequest(
                        "typed Choice item limit exceeded".into(),
                    ));
                }
                let probs = self.choice_probabilities(request, features)?;
                let best = (0..options.len())
                    .max_by(|a, b| {
                        probs[*a]
                            .total_cmp(&probs[*b])
                            .then_with(|| options[*b].id.cmp(&options[*a].id))
                    })
                    .unwrap();
                if self.answerability(&context) < self.threshold {
                    (
                        sdm_core::DecisionStatus::Abstained {
                            reason: Some("typed choice confidence below dev threshold".into()),
                        },
                        None,
                    )
                } else {
                    (
                        sdm_core::DecisionStatus::Answered,
                        Some(DecisionAnswer::Choice {
                            option_id: options[best].id.clone(),
                            probability: Some(probs[best]),
                        }),
                    )
                }
            }
            sdm_core::DecisionSpec::Score {
                minimum, maximum, ..
            } => {
                let p = 1.0 / (1.0 + (-self.score(&context, None)?).exp());
                (
                    sdm_core::DecisionStatus::Answered,
                    Some(DecisionAnswer::Score {
                        value: minimum + p * (maximum - minimum),
                        confidence: None,
                    }),
                )
            }
            sdm_core::DecisionSpec::Rank { .. } => unreachable!(),
        };
        let response = DecisionResponse {
            request_id: request.request_id.clone(),
            schema_version: request.schema_version,
            status,
            answer,
            provenance: DecisionProvenance {
                backend: "sdm-local-typed-task".into(),
                model: Some(self.model_id.clone()),
                runtime_version: Some(RUNTIME_VERSION.into()),
                latency_micros: 0,
            },
        };
        response.validate_for(request)?;
        Ok(response)
    }
}

#[derive(Debug, Clone)]
pub struct TypedRankRuntime {
    payload: TypedRankPayload,
    model_id: String,
    max_candidates: usize,
    threshold: f64,
    digest: String,
}

impl TypedRankRuntime {
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, RuntimeError> {
        let envelope = ArtifactEnvelopeV2::from_bytes(bytes)?;
        if envelope.architecture != "sdm-typed-linear-rank-v1" {
            return Err(RuntimeError::InvalidArtifact(
                "unsupported typed architecture".into(),
            ));
        }
        let payload: TypedRankPayload = serde_json::from_slice(&envelope.payload)
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        payload
            .encoder
            .validate()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        let dim = payload
            .encoder
            .dimension()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        if payload.weights.len() != dim.saturating_mul(2)
            || payload
                .weights
                .iter()
                .any(|x| !x.is_finite() || x.abs() > 1_000_000.0)
            || !payload.bias.is_finite()
            || payload.bias.abs() > 1_000_000.0
            || payload.training_fingerprint.is_empty()
            || payload
                .encoder
                .schema
                .fingerprint()
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?
                != envelope.required_feature_schema_sha256
        {
            return Err(RuntimeError::InvalidArtifact(
                "invalid typed Rank payload".into(),
            ));
        }
        let calibration: TypedCalibration =
            serde_json::from_slice(&envelope.calibration_payload)
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        if !calibration.threshold.is_finite()
            || !(0.0..=1.0).contains(&calibration.threshold)
            || calibration.dev_fingerprint.is_empty()
            || calibration.policy != "dev-max-relevance-v1"
        {
            return Err(RuntimeError::InvalidArtifact(
                "invalid typed Rank threshold".into(),
            ));
        }
        Ok(Self {
            payload,
            model_id: envelope.model_id,
            max_candidates: envelope.max_candidates,
            threshold: calibration.threshold,
            digest: format!("sha256:{:x}", Sha256::digest(bytes)),
        })
    }
    pub fn digest(&self) -> &str {
        &self.digest
    }
    pub fn decide_typed(
        &self,
        request: &DecisionRequest,
        features: &sdm_core::TypedRankProjectionV2,
    ) -> Result<DecisionResponse, DecisionError> {
        request.validate()?;
        let sdm_core::DecisionSpec::Rank { candidates, .. } = &request.spec else {
            return Err(DecisionError::InvalidRequest(
                "typed Rank artifact requires Rank request".into(),
            ));
        };
        if candidates.len() > self.max_candidates {
            return Err(DecisionError::InvalidRequest(
                "typed Rank candidate limit exceeded".into(),
            ));
        }
        features.context.validate_for(&features.schema)?;
        if features.schema.fingerprint()? != self.payload.encoder.schema.fingerprint()? {
            return Err(DecisionError::InvalidRequest(
                "typed schema differs from artifact".into(),
            ));
        }
        let expected: std::collections::BTreeSet<_> =
            candidates.iter().map(|c| c.id.as_str()).collect();
        let supplied: std::collections::BTreeSet<_> =
            features.candidates.keys().map(String::as_str).collect();
        if expected != supplied {
            return Err(DecisionError::InvalidRequest(
                "typed candidate IDs differ from request".into(),
            ));
        }
        let context = self.payload.encoder.encode(&features.context)?;
        let mut ranked = Vec::with_capacity(candidates.len());
        for candidate in candidates {
            let projection = &features.candidates[&candidate.id];
            let mut vector = context.clone();
            vector.extend(self.payload.encoder.encode(projection)?);
            let score = vector
                .iter()
                .zip(&self.payload.weights)
                .map(|(x, w)| x * w)
                .sum::<f64>()
                + self.payload.bias;
            let relevance = 1.0 / (1.0 + (-score).exp());
            ranked.push(RankedDecisionCandidate {
                candidate_id: candidate.id.clone(),
                relevance,
                ranking_score: score,
            });
        }
        let (status, answer) = if ranked.iter().any(|c| c.relevance >= self.threshold) {
            (
                DecisionStatus::Answered,
                Some(DecisionAnswer::Rank { candidates: ranked }),
            )
        } else {
            (
                DecisionStatus::Abstained {
                    reason: Some("no typed candidate met threshold".into()),
                },
                None,
            )
        };
        let response = DecisionResponse {
            request_id: request.request_id.clone(),
            schema_version: request.schema_version,
            status,
            answer,
            provenance: DecisionProvenance {
                backend: "sdm-local-typed-rank".into(),
                model: Some(self.model_id.clone()),
                runtime_version: Some(RUNTIME_VERSION.into()),
                latency_micros: 0,
            },
        };
        response.validate_for(request)?;
        Ok(response)
    }
}

#[derive(Debug, Clone)]
pub struct NonlinearRuntime {
    model: sdm_nonlinear::PairwiseModel,
    model_id: String,
    max_candidates: usize,
    threshold: f64,
    digest: String,
}

impl NonlinearRuntime {
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, RuntimeError> {
        let envelope = ArtifactEnvelopeV2::from_bytes(bytes)?;
        if envelope.architecture != sdm_nonlinear::ARCHITECTURE {
            return Err(RuntimeError::InvalidArtifact(
                "unsupported nonlinear architecture".into(),
            ));
        }
        if envelope.capabilities != ["rank"] {
            return Err(RuntimeError::InvalidArtifact(
                "nonlinear engine supports Rank only".into(),
            ));
        }
        let model = sdm_nonlinear::PairwiseModel::from_bytes(&envelope.payload)
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        validate_nonlinear_rank_schema(&model)?;
        if model
            .feature_schema_sha256()
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?
            != envelope.required_feature_schema_sha256
            || model
                .parameter_count()
                .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?
                != envelope.parameter_count
        {
            return Err(RuntimeError::InvalidArtifact(
                "model schema or parameter count mismatch".into(),
            ));
        }
        let calibration: RankCalibration = serde_json::from_slice(&envelope.calibration_payload)
            .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
        if !calibration.threshold.is_finite() || !(0.0..=1.0).contains(&calibration.threshold) {
            return Err(RuntimeError::InvalidArtifact(
                "invalid Rank calibration".into(),
            ));
        }
        Ok(Self {
            model,
            model_id: envelope.model_id,
            max_candidates: envelope.max_candidates,
            threshold: calibration.threshold,
            digest: format!("sha256:{:x}", Sha256::digest(bytes)),
        })
    }

    pub fn digest(&self) -> &str {
        &self.digest
    }

    pub fn decide(&self, request: &DecisionRequest) -> Result<DecisionResponse, DecisionError> {
        request.validate()?;
        let (status, answer) = match &request.spec {
            DecisionSpec::Rank { candidates, .. } if candidates.len() <= self.max_candidates => {
                let context = request
                    .state
                    .iter()
                    .map(|f| f.value.as_str())
                    .collect::<Vec<_>>()
                    .join(" ");
                let mut ranked = Vec::with_capacity(candidates.len());
                for candidate in candidates {
                    let text = format!("{} {}", candidate.label, candidate.description);
                    let features = self
                        .model
                        .rank_features(&context, &text)
                        .map_err(|e| DecisionError::InvalidRequest(e.to_string()))?;
                    let score = self
                        .model
                        .score(&features)
                        .map_err(|e| DecisionError::InvalidRequest(e.to_string()))?;
                    ranked.push(RankedDecisionCandidate {
                        candidate_id: candidate.id.clone(),
                        relevance: 1.0 / (1.0 + (-score).exp()),
                        ranking_score: score,
                    });
                }
                if ranked.iter().any(|c| c.relevance >= self.threshold) {
                    (
                        DecisionStatus::Answered,
                        Some(DecisionAnswer::Rank { candidates: ranked }),
                    )
                } else {
                    (
                        DecisionStatus::Abstained {
                            reason: Some("no candidate met nonlinear threshold".into()),
                        },
                        None,
                    )
                }
            }
            DecisionSpec::Rank { .. } => (
                DecisionStatus::Unsupported {
                    reason: "candidate limit exceeded".into(),
                },
                None,
            ),
            _ => (
                DecisionStatus::Unsupported {
                    reason: "nonlinear artifact supports Rank only".into(),
                },
                None,
            ),
        };
        let response = DecisionResponse {
            request_id: request.request_id.clone(),
            schema_version: request.schema_version,
            status,
            answer,
            provenance: DecisionProvenance {
                backend: "sdm-local-nonlinear".into(),
                model: Some(self.model_id.clone()),
                runtime_version: Some(RUNTIME_VERSION.into()),
                latency_micros: 0,
            },
        };
        response.validate_for(request)?;
        Ok(response)
    }
}

fn validate_nonlinear_rank_schema(
    model: &sdm_nonlinear::PairwiseModel,
) -> Result<(), RuntimeError> {
    for id in &model.feature_ids {
        let Some((kind, token)) = id.split_once(':') else {
            return Err(RuntimeError::InvalidArtifact(
                "nonlinear Rank feature ID lacks kind prefix".into(),
            ));
        };
        if token.is_empty() || !matches!(kind, "ctx" | "cand" | "both") {
            return Err(RuntimeError::InvalidArtifact(
                "unsupported nonlinear Rank feature ID".into(),
            ));
        }
    }
    model
        .rank_features("", "")
        .map_err(|e| RuntimeError::InvalidArtifact(e.to_string()))?;
    Ok(())
}

/// Version-aware loader. V2 envelopes are validated but remain Unsupported
/// until an explicitly registered inference engine claims their architecture.
pub fn load_artifact(bytes: &[u8]) -> Result<LoadedArtifact, RuntimeError> {
    if bytes.len() > V2_MAX_ARTIFACT_BYTES {
        return Err(RuntimeError::InvalidArtifact(
            "artifact exceeds maximum byte limit".into(),
        ));
    }
    let value: serde_json::Value = serde_json::from_slice(bytes)
        .map_err(|_| RuntimeError::InvalidArtifact("invalid artifact JSON".into()))?;
    if value
        .get("schema_version")
        .and_then(serde_json::Value::as_u64)
        == Some(u64::from(ARTIFACT_ENVELOPE_V2))
    {
        let envelope = ArtifactEnvelopeV2::from_bytes(bytes)?;
        if envelope.architecture == sdm_nonlinear::ARCHITECTURE {
            Ok(LoadedArtifact::NonlinearV2(NonlinearRuntime::from_bytes(
                bytes,
            )?))
        } else if envelope.architecture == "sdm-typed-linear-rank-v1" {
            Ok(LoadedArtifact::TypedRankV2(TypedRankRuntime::from_bytes(
                bytes,
            )?))
        } else if envelope.architecture == "sdm-typed-task-v1" {
            Ok(LoadedArtifact::TypedTaskV2(TypedTaskRuntime::from_bytes(
                bytes,
            )?))
        } else {
            Ok(LoadedArtifact::UnsupportedV2(envelope))
        }
    } else {
        Ok(LoadedArtifact::LinearV1(Runtime::from_bytes(bytes)?))
    }
}

impl Runtime {
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, RuntimeError> {
        if bytes.len() > MAX_ARTIFACT_BYTES {
            return Err(RuntimeError::InvalidArtifact(
                "artifact exceeds byte limit".into(),
            ));
        }
        let artifact: LinearArtifact = serde_json::from_slice(bytes)
            .map_err(|_| RuntimeError::InvalidArtifact("invalid artifact JSON".into()))?;
        validate_artifact(&artifact)?;
        let digest = format!("sha256:{:x}", Sha256::digest(bytes));
        Ok(Self { artifact, digest })
    }
    pub fn artifact(&self) -> &LinearArtifact {
        &self.artifact
    }
    pub fn digest(&self) -> &str {
        &self.digest
    }
    pub fn decide(&self, request: &DecisionRequest) -> Result<DecisionResponse, DecisionError> {
        request.validate()?;
        let context = request
            .state
            .iter()
            .map(|field| field.value.as_str())
            .collect::<Vec<_>>()
            .join(" ")
            .to_lowercase();
        let context_tokens: std::collections::BTreeSet<_> = tokens(&context).collect();
        let state_bytes: usize = request
            .state
            .iter()
            .map(|f| f.key.len().saturating_add(f.value.len()))
            .sum();
        let (status, answer) = match &request.spec {
            DecisionSpec::Rank { .. } if state_bytes > self.artifact.manifest.max_state_bytes => (
                DecisionStatus::Unsupported {
                    reason: "state limit exceeds artifact capability".into(),
                },
                None,
            ),
            DecisionSpec::Rank { candidates, .. }
                if candidates.len() <= self.artifact.manifest.max_candidates =>
            {
                let ranked: Vec<_> = candidates
                    .iter()
                    .map(|c| {
                        let score = self.score(&context_tokens, c);
                        RankedDecisionCandidate {
                            candidate_id: c.id.clone(),
                            relevance: 1.0 / (1.0 + (-score).exp()),
                            ranking_score: score,
                        }
                    })
                    .collect();
                if ranked
                    .iter()
                    .any(|candidate| candidate.relevance >= self.artifact.threshold)
                {
                    (
                        DecisionStatus::Answered,
                        Some(DecisionAnswer::Rank { candidates: ranked }),
                    )
                } else {
                    (
                        DecisionStatus::Abstained {
                            reason: Some("no candidate met artifact threshold".into()),
                        },
                        None,
                    )
                }
            }
            DecisionSpec::Rank { .. } => (
                DecisionStatus::Unsupported {
                    reason: "candidate limit exceeded".into(),
                },
                None,
            ),
            _ => (
                DecisionStatus::Unsupported {
                    reason: "artifact supports Rank only".into(),
                },
                None,
            ),
        };
        let response = DecisionResponse {
            request_id: request.request_id.clone(),
            schema_version: request.schema_version,
            status,
            answer,
            provenance: DecisionProvenance {
                backend: "sdm-local".into(),
                model: Some(self.digest.clone()),
                runtime_version: Some(RUNTIME_VERSION.into()),
                latency_micros: 0,
            },
        };
        response.validate_for(request)?;
        Ok(response)
    }
    fn score(
        &self,
        context: &std::collections::BTreeSet<String>,
        candidate: &DecisionCandidate,
    ) -> f64 {
        let option = format!("{} {}", candidate.label, candidate.description).to_lowercase();
        features_for_tokens(context, &option)
            .into_iter()
            .map(|token| self.artifact.weights.get(&token).copied().unwrap_or(0.0))
            .sum::<f64>()
            + self.artifact.bias
    }
}

#[derive(Debug, thiserror::Error)]
pub enum RuntimeError {
    #[error("invalid artifact: {0}")]
    InvalidArtifact(String),
}

pub fn validate_artifact(a: &LinearArtifact) -> Result<(), RuntimeError> {
    let fail = |s: &str| RuntimeError::InvalidArtifact(s.into());
    if a.manifest.schema_version != ARTIFACT_SCHEMA {
        return Err(fail("unsupported schema"));
    }
    if a.manifest.input_schema_version != 1 || a.manifest.calibration_version != 1 {
        return Err(fail("unsupported input or calibration version"));
    }
    if a.manifest.architecture != "sdm-binary-linear-v1" {
        return Err(fail("unsupported architecture"));
    }
    if a.manifest.capabilities != ["rank"] {
        return Err(fail("invalid capabilities"));
    }
    if a.manifest.max_state_bytes == 0
        || a.manifest.max_state_bytes > 65_536
        || a.manifest.max_candidates == 0
        || a.manifest.max_candidates > 256
    {
        return Err(fail("invalid limits"));
    }
    if !a.bias.is_finite()
        || !a.threshold.is_finite()
        || !(0.0..=1.0).contains(&a.threshold)
        || a.weights.len() > 100_000
        || a.weights.values().any(|v| !v.is_finite())
    {
        return Err(fail("invalid parameters"));
    }
    if !a.manifest.model_sha256.starts_with("sha256:")
        || a.manifest.training_fingerprint.trim().is_empty()
        || a.manifest.license.trim().is_empty()
        || a.manifest.source.trim().is_empty()
    {
        return Err(fail("missing provenance"));
    }
    let expected = parameter_digest(a.bias, &a.weights);
    if a.manifest.model_sha256 != expected {
        return Err(RuntimeError::InvalidArtifact(format!(
            "parameter digest mismatch: manifest {}, computed {expected}",
            a.manifest.model_sha256
        )));
    }
    let calibration = format!(
        "sha256:{:x}",
        Sha256::digest(a.threshold.to_bits().to_le_bytes())
    );
    if a.manifest.calibration_sha256 != calibration {
        return Err(fail("calibration digest mismatch"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn v2_envelope_checks_payload_and_loads_as_explicitly_unsupported() {
        let payload = vec![1, 2, 3];
        let env = ArtifactEnvelopeV2 {
            schema_version: 2,
            architecture: "future".into(),
            model_id: "m".into(),
            required_feature_schema_sha256: format!("sha256:{}", "a".repeat(64)),
            capabilities: vec!["rank".into()],
            max_candidates: 16,
            parameter_count: 2,
            tensor_payload_sha256: format!("sha256:{:x}", Sha256::digest(&payload)),
            calibration_sha256: format!("sha256:{:x}", Sha256::digest(b"none")),
            calibration_payload: b"none".to_vec(),
            license: "MIT".into(),
            source: "test".into(),
            payload,
        };
        let bytes = serde_json::to_vec(&env).unwrap();
        assert!(matches!(
            load_artifact(&bytes).unwrap(),
            LoadedArtifact::UnsupportedV2(_)
        ));
        let mut bad = env;
        bad.payload.push(4);
        assert!(bad.validate().is_err());
    }

    #[test]
    fn nonlinear_v2_roundtrips_through_bounded_runtime_dispatch() {
        let model = sdm_nonlinear::initialize(
            vec![
                "ctx:inspect".into(),
                "cand:source".into(),
                "both:inspect".into(),
            ],
            4,
            77,
        )
        .unwrap();
        let envelope =
            ArtifactEnvelopeV2::for_nonlinear(&model, "test-model", 16, 0.0, "MIT", "unit-test")
                .unwrap();
        let bytes = serde_json::to_vec(&envelope).unwrap();
        let LoadedArtifact::NonlinearV2(engine) = load_artifact(&bytes).unwrap() else {
            panic!("nonlinear engine was not selected")
        };
        let request = DecisionRequest {
            request_id: "r".into(),
            schema_version: 1,
            state: vec![sdm_core::StateField {
                key: "task".into(),
                value: "inspect source".into(),
            }],
            spec: DecisionSpec::Rank {
                instruction: "rank".into(),
                candidates: vec![DecisionCandidate {
                    id: "c1".into(),
                    label: "source".into(),
                    description: "read source".into(),
                }],
                multi_relevance: true,
            },
        };
        let response = engine.decide(&request).unwrap();
        response.validate_for(&request).unwrap();
        let expected_features = model
            .rank_features("inspect source", "source read source")
            .unwrap();
        let expected_score = model.score(&expected_features).unwrap();
        let Some(DecisionAnswer::Rank { candidates }) = &response.answer else {
            panic!("expected ranked output")
        };
        assert!((candidates[0].ranking_score - expected_score).abs() < 1e-12);
        assert_eq!(response.provenance.model, Some("test-model".into()));
        assert_eq!(response.provenance.backend, "sdm-local-nonlinear");
    }

    #[test]
    fn typed_rank_artifact_uses_same_fitted_encoder_and_rejects_identity_injection() {
        let schema = sdm_core::FeatureSchemaV2 {
            version: 2,
            fields: vec![sdm_core::FeatureSchemaField {
                id: "kind".into(),
                value_type: sdm_core::FeatureType::Category,
                required: true,
                categories: vec!["candidate".into(), "task".into()],
            }],
        };
        let projection = |value: &str| sdm_core::FeatureProjectionV2 {
            schema_version: 2,
            schema_sha256: schema.fingerprint().unwrap(),
            fields: vec![sdm_core::FeatureField {
                id: "kind".into(),
                required: true,
                value: Some(sdm_core::FeatureValue::Category(value.into())),
            }],
        };
        let encoder = sdm_core::FittedFeatureEncoderV2::fit(
            &schema,
            &[projection("task"), projection("candidate")],
        )
        .unwrap();
        let envelope = ArtifactEnvelopeV2::for_typed_rank(
            &encoder,
            vec![0.0, 0.0, 5.0, 0.0],
            0.0,
            0.5,
            "dev-sha",
            "train-sha",
            "typed-model",
            8,
        )
        .unwrap();
        let bytes = serde_json::to_vec(&envelope).unwrap();
        let LoadedArtifact::TypedRankV2(engine) = load_artifact(&bytes).unwrap() else {
            panic!("typed runtime not dispatched")
        };
        let request = DecisionRequest {
            request_id: "typed".into(),
            schema_version: 1,
            state: vec![],
            spec: DecisionSpec::Rank {
                instruction: "rank".into(),
                multi_relevance: true,
                candidates: vec![DecisionCandidate {
                    id: "c".into(),
                    label: "c".into(),
                    description: "candidate".into(),
                }],
            },
        };
        let features = sdm_core::TypedRankProjectionV2 {
            schema: schema.clone(),
            context: projection("task"),
            candidates: std::collections::BTreeMap::from([("c".into(), projection("candidate"))]),
        };
        let response = engine.decide_typed(&request, &features).unwrap();
        let Some(DecisionAnswer::Rank { candidates }) = response.answer else {
            panic!("expected typed Rank answer")
        };
        assert!((candidates[0].ranking_score - 5.0).abs() < 1e-12);
        let mut injected = features;
        injected
            .candidates
            .insert("injected".into(), projection("candidate"));
        assert!(engine.decide_typed(&request, &injected).is_err());
    }
    #[test]
    fn manifest_rejects_invalid_limits() {
        let a = LinearArtifact {
            manifest: ArtifactManifest {
                schema_version: 1,
                architecture: "sdm-binary-linear-v1".into(),
                input_schema_version: 1,
                capabilities: vec!["rank".into()],
                max_state_bytes: 0,
                max_candidates: 16,
                model_sha256: "sha256:x".into(),
                training_fingerprint: "seed:1".into(),
                calibration_version: 1,
                calibration_sha256: "sha256:x".into(),
                license: "MIT".into(),
                source: "test".into(),
            },
            bias: 0.0,
            weights: BTreeMap::new(),
            threshold: 0.5,
        };
        assert!(validate_artifact(&a).is_err());
    }
}
