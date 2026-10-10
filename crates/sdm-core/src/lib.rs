//! Bounded, backend-neutral decision semantics shared by CodeGG adapters.
//!
//! This module deliberately contains no tool authority, model, transport, or
//! artifact concepts. Callers own policy and decide whether a response is usable.

use std::{collections::BTreeSet, time::Instant};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;

pub const DECISION_SCHEMA_VERSION: u16 = 1;
pub const MAX_STATE_FIELDS: usize = 64;
pub const MAX_STATE_KEY_BYTES: usize = 128;
pub const MAX_STATE_VALUE_BYTES: usize = 16 * 1024;
pub const MAX_STATE_BYTES: usize = 64 * 1024;
pub const MAX_OPTIONS: usize = 128;
pub const MAX_CANDIDATES: usize = 256;
pub const MAX_ID_BYTES: usize = 256;
pub const MAX_LABEL_BYTES: usize = 1024;
pub const MAX_REASON_BYTES: usize = 512;
pub const FEATURE_SCHEMA_VERSION: u16 = 2;
pub const MAX_FEATURES: usize = 256;
pub const MAX_FEATURE_ID_BYTES: usize = 128;

/// Shared legacy lexical projection. Kept stable for v1 artifact parity.
pub fn tokens(text: &str) -> impl Iterator<Item = String> + '_ {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
        .map(str::to_lowercase)
}

pub fn features_for(context: &str, option: &str) -> Vec<String> {
    let context: BTreeSet<_> = tokens(context).collect();
    features_for_tokens(&context, option)
}

pub fn features_for_tokens(context: &BTreeSet<String>, option: &str) -> Vec<String> {
    let option: BTreeSet<_> = tokens(option).collect();
    let mut features: Vec<_> = context.iter().map(|t| format!("ctx:{t}")).collect();
    features.extend(option.iter().map(|t| format!("opt:{t}")));
    features.extend(
        context
            .intersection(&option)
            .map(|t| format!("overlap:{t}")),
    );
    features
}

/// A bounded, typed value in the additive feature projection contract.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", content = "value", rename_all = "snake_case")]
pub enum FeatureValue {
    Text(String),
    Number(f64),
    Boolean(bool),
    Category(String),
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FeatureField {
    pub id: String,
    pub required: bool,
    pub value: Option<FeatureValue>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FeatureSchemaV2 {
    pub version: u16,
    pub fields: Vec<FeatureSchemaField>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeatureSchemaField {
    pub id: String,
    pub value_type: FeatureType,
    pub required: bool,
    pub categories: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FeatureType {
    Text,
    Number,
    Boolean,
    Category,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FeatureProjectionV2 {
    pub schema_version: u16,
    pub schema_sha256: String,
    pub fields: Vec<FeatureField>,
}

impl FeatureSchemaV2 {
    pub fn validate(&self) -> Result<(), DecisionError> {
        if self.version != FEATURE_SCHEMA_VERSION || self.fields.len() > MAX_FEATURES {
            return Err(DecisionError::InvalidRequest(
                "unsupported or oversized feature schema".into(),
            ));
        }
        let mut ids = BTreeSet::new();
        for field in &self.fields {
            if field.id.is_empty()
                || field.id.len() > MAX_FEATURE_ID_BYTES
                || !ids.insert(&field.id)
            {
                return Err(DecisionError::InvalidRequest(
                    "invalid or duplicate feature id".into(),
                ));
            }
            if field.value_type != FeatureType::Category && !field.categories.is_empty() {
                return Err(DecisionError::InvalidRequest(
                    "categories only apply to category features".into(),
                ));
            }
            let mut categories = BTreeSet::new();
            if field
                .categories
                .iter()
                .any(|v| v.is_empty() || v.len() > MAX_LABEL_BYTES || !categories.insert(v))
            {
                return Err(DecisionError::InvalidRequest(
                    "invalid or duplicate category".into(),
                ));
            }
        }
        Ok(())
    }

    pub fn fingerprint(&self) -> Result<String, DecisionError> {
        self.validate()?;
        let mut schema = self.clone();
        schema.fields.sort_by(|a, b| a.id.cmp(&b.id));
        for field in &mut schema.fields {
            field.categories.sort();
        }
        let bytes = serde_json::to_vec(&schema)
            .map_err(|e| DecisionError::InvalidRequest(e.to_string()))?;
        Ok(format!("sha256:{:x}", Sha256::digest(bytes)))
    }
}

impl FeatureProjectionV2 {
    pub fn validate_for(&self, schema: &FeatureSchemaV2) -> Result<(), DecisionError> {
        schema.validate()?;
        if self.schema_version != FEATURE_SCHEMA_VERSION
            || self.schema_sha256 != schema.fingerprint()?
        {
            return Err(DecisionError::InvalidRequest(
                "feature schema fingerprint mismatch".into(),
            ));
        }
        if self.fields.len() > MAX_FEATURES {
            return Err(DecisionError::InvalidRequest(
                "too many feature values".into(),
            ));
        }
        let expected: std::collections::BTreeMap<_, _> =
            schema.fields.iter().map(|f| (f.id.as_str(), f)).collect();
        let mut seen = BTreeSet::new();
        for field in &self.fields {
            let spec = expected
                .get(field.id.as_str())
                .ok_or_else(|| DecisionError::InvalidRequest("unknown feature id".into()))?;
            if !seen.insert(field.id.as_str()) {
                return Err(DecisionError::InvalidRequest("duplicate feature id".into()));
            }
            match &field.value {
                None if field.required || spec.required => {
                    return Err(DecisionError::InvalidRequest(
                        "required feature missing".into(),
                    ))
                }
                None => {}
                Some(value) => {
                    let ty = match value {
                        FeatureValue::Text(_) => FeatureType::Text,
                        FeatureValue::Number(n) if n.is_finite() => FeatureType::Number,
                        FeatureValue::Number(_) => {
                            return Err(DecisionError::InvalidRequest("non-finite feature".into()))
                        }
                        FeatureValue::Boolean(_) => FeatureType::Boolean,
                        FeatureValue::Category(_) => FeatureType::Category,
                    };
                    if ty != spec.value_type {
                        return Err(DecisionError::InvalidRequest(
                            "feature type mismatch".into(),
                        ));
                    }
                    let text = match value {
                        FeatureValue::Text(s) | FeatureValue::Category(s) => Some(s.as_str()),
                        _ => None,
                    };
                    if text.is_some_and(|s| {
                        s.len() > MAX_STATE_VALUE_BYTES
                            || (ty == FeatureType::Category
                                && !spec.categories.is_empty()
                                && !spec.categories.iter().any(|c| c == s))
                    }) {
                        return Err(DecisionError::InvalidRequest(
                            "feature value outside schema bounds".into(),
                        ));
                    }
                }
            }
        }
        if schema
            .fields
            .iter()
            .any(|f| f.required && !seen.contains(f.id.as_str()))
        {
            return Err(DecisionError::InvalidRequest(
                "required feature missing".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StateField {
    pub key: String,
    pub value: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DecisionOption {
    pub id: String,
    pub label: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DecisionCandidate {
    /// Stable application identity. Labels are payload and never authority.
    pub id: String,
    pub label: String,
    pub description: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum DecisionSpec {
    Binary {
        question: String,
    },
    Choice {
        question: String,
        options: Vec<DecisionOption>,
    },
    Score {
        rubric: String,
        minimum: f64,
        maximum: f64,
    },
    Rank {
        instruction: String,
        candidates: Vec<DecisionCandidate>,
        multi_relevance: bool,
    },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DecisionRequest {
    pub request_id: String,
    pub schema_version: u16,
    pub state: Vec<StateField>,
    pub spec: DecisionSpec,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum DecisionStatus {
    Answered,
    Abstained { reason: Option<String> },
    Unsupported { reason: String },
    Unavailable { reason: String },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum DecisionAnswer {
    Binary {
        probability_true: f64,
        confidence: Option<f64>,
    },
    Choice {
        option_id: String,
        probability: Option<f64>,
    },
    Score {
        value: f64,
        confidence: Option<f64>,
    },
    Rank {
        candidates: Vec<RankedDecisionCandidate>,
    },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RankedDecisionCandidate {
    pub candidate_id: String,
    pub relevance: f64,
    pub ranking_score: f64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DecisionProvenance {
    pub backend: String,
    pub model: Option<String>,
    pub runtime_version: Option<String>,
    pub latency_micros: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DecisionResponse {
    pub request_id: String,
    pub schema_version: u16,
    pub status: DecisionStatus,
    pub answer: Option<DecisionAnswer>,
    pub provenance: DecisionProvenance,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum DecisionError {
    #[error("invalid decision request: {0}")]
    InvalidRequest(String),
    #[error("invalid decision response: {0}")]
    InvalidResponse(String),
}

impl DecisionRequest {
    pub fn validate(&self) -> Result<(), DecisionError> {
        if self.schema_version != DECISION_SCHEMA_VERSION {
            return Err(DecisionError::InvalidRequest(
                "unsupported schema version".into(),
            ));
        }
        validate_id(&self.request_id).map_err(DecisionError::InvalidRequest)?;
        if self.state.len() > MAX_STATE_FIELDS {
            return Err(DecisionError::InvalidRequest(
                "too many state fields".into(),
            ));
        }
        let mut keys = BTreeSet::new();
        let mut total_bytes = 0usize;
        for field in &self.state {
            if field.key.is_empty() || field.key.len() > MAX_STATE_KEY_BYTES {
                return Err(DecisionError::InvalidRequest(
                    "invalid state key length".into(),
                ));
            }
            if field.value.len() > MAX_STATE_VALUE_BYTES {
                return Err(DecisionError::InvalidRequest(
                    "state value exceeds limit".into(),
                ));
            }
            if !keys.insert(&field.key) {
                return Err(DecisionError::InvalidRequest("duplicate state key".into()));
            }
            total_bytes = total_bytes
                .saturating_add(field.key.len())
                .saturating_add(field.value.len());
        }
        if total_bytes > MAX_STATE_BYTES {
            return Err(DecisionError::InvalidRequest(
                "state exceeds byte limit".into(),
            ));
        }
        match &self.spec {
            DecisionSpec::Binary { question } => validate_label(question, "question"),
            DecisionSpec::Choice { question, options } => {
                validate_label(question, "question")?;
                if options.len() < 2 {
                    return Err(DecisionError::InvalidRequest(
                        "Choice needs at least two options".into(),
                    ));
                }
                validate_named_items(
                    options.iter().map(|o| (o.id.as_str(), o.label.as_str())),
                    MAX_OPTIONS,
                )
            }
            DecisionSpec::Score {
                rubric,
                minimum,
                maximum,
            } => {
                validate_label(rubric, "rubric")?;
                if !minimum.is_finite() || !maximum.is_finite() || minimum >= maximum {
                    return Err(DecisionError::InvalidRequest("invalid score range".into()));
                }
                Ok(())
            }
            DecisionSpec::Rank {
                instruction,
                candidates,
                ..
            } => {
                validate_label(instruction, "instruction")?;
                if candidates.is_empty() {
                    return Err(DecisionError::InvalidRequest(
                        "Rank needs at least one candidate".into(),
                    ));
                }
                if candidates.len() > MAX_CANDIDATES {
                    return Err(DecisionError::InvalidRequest("too many candidates".into()));
                }
                validate_named_items(
                    candidates.iter().map(|c| (c.id.as_str(), c.label.as_str())),
                    MAX_CANDIDATES,
                )?;
                for candidate in candidates {
                    if candidate.description.len() > MAX_STATE_VALUE_BYTES {
                        return Err(DecisionError::InvalidRequest(
                            "candidate description exceeds limit".into(),
                        ));
                    }
                }
                Ok(())
            }
        }
    }

    /// Stable digest independent of caller ordering for semantically unordered
    /// state fields, choices, and rank candidates.
    pub fn canonical_fingerprint(&self) -> Result<String, DecisionError> {
        self.validate()?;
        let mut canonical = self.clone();
        canonical.state.sort_by(|a, b| a.key.cmp(&b.key));
        match &mut canonical.spec {
            DecisionSpec::Choice { options, .. } => options.sort_by(|a, b| a.id.cmp(&b.id)),
            DecisionSpec::Rank { candidates, .. } => candidates.sort_by(|a, b| a.id.cmp(&b.id)),
            _ => {}
        }
        let bytes = serde_json::to_vec(&canonical)
            .map_err(|error| DecisionError::InvalidRequest(error.to_string()))?;
        Ok(format!("sha256:{:x}", Sha256::digest(bytes)))
    }
}

impl DecisionResponse {
    pub fn validate_for(&self, request: &DecisionRequest) -> Result<(), DecisionError> {
        let invalid = |why: &str| DecisionError::InvalidResponse(why.to_string());
        if self.request_id != request.request_id || self.schema_version != request.schema_version {
            return Err(invalid("request identity or schema mismatch"));
        }
        validate_id(&self.provenance.backend).map_err(|error| invalid(&error))?;
        if self
            .provenance
            .model
            .as_ref()
            .is_some_and(|v| v.len() > MAX_ID_BYTES)
            || self
                .provenance
                .runtime_version
                .as_ref()
                .is_some_and(|v| v.len() > MAX_ID_BYTES)
        {
            return Err(invalid("provenance field exceeds limit"));
        }
        match &self.status {
            DecisionStatus::Abstained {
                reason: Some(reason),
            } if reason.len() > MAX_REASON_BYTES => {
                return Err(invalid("status reason exceeds limit"));
            }
            DecisionStatus::Unsupported { reason } | DecisionStatus::Unavailable { reason }
                if reason.len() > MAX_REASON_BYTES =>
            {
                return Err(invalid("status reason exceeds limit"));
            }
            _ => {}
        }
        match (&self.status, &self.answer) {
            (DecisionStatus::Answered, Some(answer)) => validate_answer(answer, &request.spec),
            (DecisionStatus::Answered, None) => Err(invalid("answered response has no answer")),
            (_, None) => Ok(()),
            (_, Some(_)) => Err(invalid("non-answer status carries an answer")),
        }
    }
}

fn validate_answer(answer: &DecisionAnswer, spec: &DecisionSpec) -> Result<(), DecisionError> {
    let invalid = |why: &str| DecisionError::InvalidResponse(why.to_string());
    match (answer, spec) {
        (
            DecisionAnswer::Binary {
                probability_true,
                confidence,
            },
            DecisionSpec::Binary { .. },
        ) => {
            validate_probability(*probability_true).map_err(invalid)?;
            if let Some(value) = confidence {
                validate_probability(*value).map_err(invalid)?;
            }
            Ok(())
        }
        (
            DecisionAnswer::Choice {
                option_id,
                probability,
            },
            DecisionSpec::Choice { options, .. },
        ) => {
            if !options.iter().any(|o| o.id == *option_id) {
                return Err(invalid("unknown choice option"));
            }
            if let Some(value) = probability {
                validate_probability(*value).map_err(invalid)?;
            }
            Ok(())
        }
        (
            DecisionAnswer::Score { value, confidence },
            DecisionSpec::Score {
                minimum, maximum, ..
            },
        ) => {
            if !value.is_finite() || *value < *minimum || *value > *maximum {
                return Err(invalid("score outside requested bounds"));
            }
            if let Some(value) = confidence {
                validate_probability(*value).map_err(invalid)?;
            }
            Ok(())
        }
        (
            DecisionAnswer::Rank { candidates },
            DecisionSpec::Rank {
                candidates: requested,
                ..
            },
        ) => {
            if candidates.len() != requested.len() {
                return Err(invalid("rank candidate set mismatch"));
            }
            let expected: BTreeSet<_> = requested.iter().map(|c| c.id.as_str()).collect();
            let actual: BTreeSet<_> = candidates.iter().map(|c| c.candidate_id.as_str()).collect();
            if actual.len() != candidates.len() || actual != expected {
                return Err(invalid("rank candidate identities mismatch"));
            }
            if candidates
                .iter()
                .any(|c| !c.relevance.is_finite() || !c.ranking_score.is_finite())
            {
                return Err(invalid("rank contains non-finite score"));
            }
            Ok(())
        }
        _ => Err(invalid("answer kind does not match request")),
    }
}

fn validate_named_items<'a>(
    items: impl Iterator<Item = (&'a str, &'a str)>,
    max: usize,
) -> Result<(), DecisionError> {
    let mut ids = BTreeSet::new();
    for (id, label) in items {
        validate_id(id).map_err(DecisionError::InvalidRequest)?;
        validate_label(label, "label")?;
        if !ids.insert(id) {
            return Err(DecisionError::InvalidRequest("duplicate item id".into()));
        }
    }
    if ids.len() > max {
        return Err(DecisionError::InvalidRequest("too many items".into()));
    }
    Ok(())
}

fn validate_id(value: &str) -> Result<(), String> {
    if value.is_empty() || value.len() > MAX_ID_BYTES {
        Err("invalid id length".into())
    } else {
        Ok(())
    }
}

fn validate_label(value: &str, field: &str) -> Result<(), DecisionError> {
    if value.is_empty() || value.len() > MAX_LABEL_BYTES {
        Err(DecisionError::InvalidRequest(format!(
            "invalid {field} length"
        )))
    } else {
        Ok(())
    }
}

fn validate_probability(value: f64) -> Result<(), &'static str> {
    if value.is_finite() && (0.0..=1.0).contains(&value) {
        Ok(())
    } else {
        Err("probability outside [0,1]")
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BackendState {
    Off,
    Ready,
    Degraded(String),
    Unsupported(String),
    Unavailable(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BackendCapabilities {
    pub binary: bool,
    pub choice: bool,
    pub score: bool,
    pub rank: bool,
    pub max_options: usize,
    pub max_candidates: usize,
}

#[async_trait]
pub trait DecisionEngine: Send + Sync {
    fn state(&self) -> BackendState;
    fn capabilities(&self) -> BackendCapabilities;
    /// Implementations must validate the request before performing backend I/O.
    async fn decide(
        &self,
        request: DecisionRequest,
        deadline: Instant,
    ) -> Result<DecisionResponse, DecisionError>;
}

#[derive(Debug, Default, Clone, Copy)]
pub struct NoopDecisionEngine;

#[async_trait]
impl DecisionEngine for NoopDecisionEngine {
    fn state(&self) -> BackendState {
        BackendState::Off
    }
    fn capabilities(&self) -> BackendCapabilities {
        BackendCapabilities {
            binary: false,
            choice: false,
            score: false,
            rank: false,
            max_options: 0,
            max_candidates: 0,
        }
    }
    async fn decide(
        &self,
        request: DecisionRequest,
        _deadline: Instant,
    ) -> Result<DecisionResponse, DecisionError> {
        request.validate()?;
        Ok(DecisionResponse {
            request_id: request.request_id,
            schema_version: request.schema_version,
            status: DecisionStatus::Unavailable {
                reason: "decision engine is off".into(),
            },
            answer: None,
            provenance: DecisionProvenance {
                backend: "noop".into(),
                model: None,
                runtime_version: None,
                latency_micros: 0,
            },
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn typed_feature_projection_checks_schema_identity_and_values() {
        let schema = FeatureSchemaV2 {
            version: FEATURE_SCHEMA_VERSION,
            fields: vec![
                FeatureSchemaField {
                    id: "risk".into(),
                    value_type: FeatureType::Number,
                    required: true,
                    categories: vec![],
                },
                FeatureSchemaField {
                    id: "kind".into(),
                    value_type: FeatureType::Category,
                    required: false,
                    categories: vec!["safe".into()],
                },
            ],
        };
        let projection = FeatureProjectionV2 {
            schema_version: FEATURE_SCHEMA_VERSION,
            schema_sha256: schema.fingerprint().unwrap(),
            fields: vec![
                FeatureField {
                    id: "risk".into(),
                    required: true,
                    value: Some(FeatureValue::Number(0.5)),
                },
                FeatureField {
                    id: "kind".into(),
                    required: false,
                    value: Some(FeatureValue::Category("safe".into())),
                },
            ],
        };
        projection.validate_for(&schema).unwrap();
        let mut bad = projection.clone();
        bad.schema_sha256 = "sha256:wrong".into();
        assert!(bad.validate_for(&schema).is_err());
        let mut bad = projection;
        bad.fields[0].value = Some(FeatureValue::Number(f64::NAN));
        assert!(bad.validate_for(&schema).is_err());
    }

    fn rank_request() -> DecisionRequest {
        DecisionRequest {
            request_id: "req-1".into(),
            schema_version: DECISION_SCHEMA_VERSION,
            state: vec![StateField {
                key: "task".into(),
                value: "inspect".into(),
            }],
            spec: DecisionSpec::Rank {
                instruction: "rank tools".into(),
                multi_relevance: true,
                candidates: vec![
                    DecisionCandidate {
                        id: "tool/a".into(),
                        label: "A".into(),
                        description: "first".into(),
                    },
                    DecisionCandidate {
                        id: "tool/b".into(),
                        label: "B".into(),
                        description: "second".into(),
                    },
                ],
            },
        }
    }

    fn response(request: &DecisionRequest) -> DecisionResponse {
        DecisionResponse {
            request_id: request.request_id.clone(),
            schema_version: request.schema_version,
            status: DecisionStatus::Answered,
            answer: Some(DecisionAnswer::Rank {
                candidates: vec![
                    RankedDecisionCandidate {
                        candidate_id: "tool/a".into(),
                        relevance: 0.8,
                        ranking_score: 3.0,
                    },
                    RankedDecisionCandidate {
                        candidate_id: "tool/b".into(),
                        relevance: 0.4,
                        ranking_score: 1.0,
                    },
                ],
            }),
            provenance: DecisionProvenance {
                backend: "test".into(),
                model: None,
                runtime_version: None,
                latency_micros: 1,
            },
        }
    }

    #[test]
    fn rank_preserves_multi_relevance_and_requires_exact_candidate_identity() {
        let request = rank_request();
        request.validate().unwrap();
        response(&request).validate_for(&request).unwrap();
        let mut malformed = response(&request);
        if let Some(DecisionAnswer::Rank { candidates }) = &mut malformed.answer {
            candidates.pop();
        }
        assert!(malformed.validate_for(&request).is_err());
    }

    #[test]
    fn unsupported_status_is_explicit_and_response_identity_is_checked() {
        let request = rank_request();
        let mut response = DecisionResponse {
            request_id: request.request_id.clone(),
            schema_version: request.schema_version,
            status: DecisionStatus::Unsupported {
                reason: "rank is unsupported".into(),
            },
            answer: None,
            provenance: DecisionProvenance {
                backend: "fixture".into(),
                model: None,
                runtime_version: None,
                latency_micros: 0,
            },
        };
        response.validate_for(&request).unwrap();
        response.request_id = "wrong-request".into();
        assert!(response.validate_for(&request).is_err());
    }

    #[test]
    fn request_rejects_duplicate_ids_oversize_state_and_non_finite_score_range() {
        let mut request = rank_request();
        if let DecisionSpec::Rank { candidates, .. } = &mut request.spec {
            candidates[1].id = candidates[0].id.clone();
        }
        assert!(request.validate().is_err());
        let mut request = rank_request();
        request.state[0].value = "x".repeat(MAX_STATE_VALUE_BYTES + 1);
        assert!(request.validate().is_err());
        let request = DecisionRequest {
            request_id: "score".into(),
            schema_version: DECISION_SCHEMA_VERSION,
            state: vec![],
            spec: DecisionSpec::Score {
                rubric: "quality".into(),
                minimum: 0.0,
                maximum: f64::INFINITY,
            },
        };
        assert!(request.validate().is_err());
    }

    #[test]
    fn binary_choice_and_score_have_distinct_validated_answers() {
        let base = |spec| DecisionRequest {
            request_id: "semantic".into(),
            schema_version: DECISION_SCHEMA_VERSION,
            state: vec![],
            spec,
        };
        let cases = [
            (
                base(DecisionSpec::Binary {
                    question: "is it safe?".into(),
                }),
                DecisionAnswer::Binary {
                    probability_true: 0.25,
                    confidence: Some(0.8),
                },
            ),
            (
                base(DecisionSpec::Choice {
                    question: "select one".into(),
                    options: vec![
                        DecisionOption {
                            id: "yes".into(),
                            label: "Yes".into(),
                        },
                        DecisionOption {
                            id: "no".into(),
                            label: "No".into(),
                        },
                    ],
                }),
                DecisionAnswer::Choice {
                    option_id: "no".into(),
                    probability: Some(0.9),
                },
            ),
            (
                base(DecisionSpec::Score {
                    rubric: "quality".into(),
                    minimum: 0.0,
                    maximum: 5.0,
                }),
                DecisionAnswer::Score {
                    value: 4.0,
                    confidence: Some(0.7),
                },
            ),
        ];
        for (request, answer) in cases {
            request.validate().unwrap();
            let response = DecisionResponse {
                request_id: request.request_id.clone(),
                schema_version: request.schema_version,
                status: DecisionStatus::Answered,
                answer: Some(answer),
                provenance: DecisionProvenance {
                    backend: "fixture".into(),
                    model: None,
                    runtime_version: None,
                    latency_micros: 0,
                },
            };
            response.validate_for(&request).unwrap();
        }
        let choice = base(DecisionSpec::Choice {
            question: "select one".into(),
            options: vec![DecisionOption {
                id: "only".into(),
                label: "Only".into(),
            }],
        });
        assert!(choice.validate().is_err());
    }

    #[test]
    fn canonical_fingerprint_ignores_unordered_input_order() {
        let mut a = rank_request();
        let mut b = rank_request();
        b.state.reverse();
        if let DecisionSpec::Rank { candidates, .. } = &mut b.spec {
            candidates.reverse();
        }
        assert_eq!(
            a.canonical_fingerprint().unwrap(),
            b.canonical_fingerprint().unwrap()
        );
        if let DecisionSpec::Rank { candidates, .. } = &mut a.spec {
            candidates[0].label = "different".into();
        }
        assert_ne!(
            a.canonical_fingerprint().unwrap(),
            b.canonical_fingerprint().unwrap()
        );
    }

    #[tokio::test]
    async fn noop_is_off_and_returns_explicit_unavailable_without_io() {
        let engine = NoopDecisionEngine;
        let request = rank_request();
        let response = engine
            .decide(request.clone(), Instant::now())
            .await
            .unwrap();
        assert_eq!(engine.state(), BackendState::Off);
        assert_eq!(
            response.status,
            DecisionStatus::Unavailable {
                reason: "decision engine is off".into()
            }
        );
        response.validate_for(&request).unwrap();
        let mut malformed = request;
        malformed.request_id.clear();
        assert!(engine.decide(malformed, Instant::now()).await.is_err());
    }
}
