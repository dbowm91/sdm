//! Small, offline decision-model runtime. This crate has no training or network dependency.
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

pub fn tokens(text: &str) -> impl Iterator<Item = String> + '_ {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
        .map(str::to_lowercase)
}

/// Sparse, domain-neutral context/option and lexical-overlap features.
pub fn features_for(context: &str, option: &str) -> Vec<String> {
    let context: std::collections::BTreeSet<_> = tokens(context).collect();
    features_for_tokens(&context, option)
}

pub fn features_for_tokens(
    context: &std::collections::BTreeSet<String>,
    option: &str,
) -> Vec<String> {
    let option: std::collections::BTreeSet<_> = tokens(option).collect();
    let mut features: Vec<_> = context.iter().map(|t| format!("ctx:{t}")).collect();
    features.extend(option.iter().map(|t| format!("opt:{t}")));
    features.extend(
        context
            .intersection(&option)
            .map(|t| format!("overlap:{t}")),
    );
    features
}

#[cfg(test)]
mod tests {
    use super::*;
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
