//! Provenance-bearing datasets and immutable, leakage-aware split manifests.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

pub const DATASET_VERSION: u16 = 2;
pub const MAX_DATASET_BYTES: usize = 64 * 1024 * 1024;
pub const MAX_CASES: usize = 100_000;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "kind", content = "value", rename_all = "snake_case")]
pub enum TargetLabel {
    Binary(bool),
    Choice(Option<String>),
    Score(f64),
    Rank {
        relevance: BTreeMap<String, f64>,
        no_relevant: bool,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DatasetExample {
    pub case_id: String,
    pub leakage_group: String,
    pub family: Option<String>,
    pub counterfactual_pair: Option<String>,
    pub request: sdm_core::DecisionRequest,
    pub label: TargetLabel,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Provenance {
    pub source: String,
    pub license: String,
    pub consent_scope: String,
    pub label_lineage: String,
    pub redistributable: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DatasetManifestV2 {
    pub version: u16,
    pub dataset_id: String,
    pub revision: String,
    pub intended_semantics: Vec<String>,
    pub feature_schema_sha256: String,
    pub content_sha256: String,
    pub example_count: usize,
    pub provenance: Provenance,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SplitManifest {
    pub version: u16,
    pub dataset_sha256: String,
    pub seed: u64,
    pub train: Vec<String>,
    pub dev: Vec<String>,
    pub test: Vec<String>,
    pub excluded: Vec<String>,
    pub fingerprint: String,
}

#[derive(Debug, Error)]
pub enum DataError {
    #[error("invalid dataset: {0}")]
    Invalid(String),
    #[error("dataset encoding: {0}")]
    Encoding(#[from] serde_json::Error),
}

pub fn validate_dataset(
    examples: &[DatasetExample],
    provenance: &Provenance,
) -> Result<String, DataError> {
    if examples.is_empty() || examples.len() > MAX_CASES {
        return Err(DataError::Invalid("case count outside bounds".into()));
    }
    if provenance.source.is_empty()
        || provenance.license.is_empty()
        || provenance.consent_scope.is_empty()
        || provenance.label_lineage.is_empty()
    {
        return Err(DataError::Invalid("provenance fields are required".into()));
    }
    let mut ids = BTreeSet::new();
    let mut pairs = BTreeMap::<&str, &str>::new();
    for e in examples {
        if e.case_id.is_empty() || e.leakage_group.is_empty() || !ids.insert(e.case_id.as_str()) {
            return Err(DataError::Invalid(
                "empty or duplicate case/group id".into(),
            ));
        }
        e.request
            .validate()
            .map_err(|x| DataError::Invalid(x.to_string()))?;
        match &e.label {
            TargetLabel::Binary(_) => {
                if !matches!(e.request.spec, sdm_core::DecisionSpec::Binary { .. }) {
                    return Err(DataError::Invalid("binary label/request mismatch".into()));
                }
            }
            TargetLabel::Choice(v) => {
                if !matches!(e.request.spec, sdm_core::DecisionSpec::Choice { .. }) {
                    return Err(DataError::Invalid("choice label/request mismatch".into()));
                }
                if let Some(id) = v {
                    if let sdm_core::DecisionSpec::Choice { options, .. } = &e.request.spec {
                        if !options.iter().any(|o| &o.id == id) {
                            return Err(DataError::Invalid(
                                "choice label references unknown option".into(),
                            ));
                        }
                    }
                }
            }
            TargetLabel::Score(v) => {
                if !v.is_finite()
                    || !matches!(e.request.spec, sdm_core::DecisionSpec::Score { minimum, maximum, .. } if *v >= minimum && *v <= maximum)
                {
                    return Err(DataError::Invalid("score label outside rubric".into()));
                }
            }
            TargetLabel::Rank {
                relevance,
                no_relevant,
            } => {
                let sdm_core::DecisionSpec::Rank { candidates, .. } = &e.request.spec else {
                    return Err(DataError::Invalid("rank label/request mismatch".into()));
                };
                let ids: BTreeSet<_> = candidates.iter().map(|c| c.id.as_str()).collect();
                if relevance.keys().any(|id| !ids.contains(id.as_str()))
                    || relevance.values().any(|v| !v.is_finite() || *v < 0.0)
                    || (*no_relevant && relevance.values().any(|v| *v > 0.0))
                {
                    return Err(DataError::Invalid("invalid rank relevance labels".into()));
                }
            }
        }
        if let Some(pair) = &e.counterfactual_pair {
            if let Some(old) = pairs.insert(pair, &e.leakage_group) {
                if old != e.leakage_group {
                    return Err(DataError::Invalid(
                        "counterfactual pair spans leakage groups".into(),
                    ));
                }
            }
        }
    }
    let bytes = serde_json::to_vec(examples)?;
    if bytes.len() > MAX_DATASET_BYTES {
        return Err(DataError::Invalid("dataset byte limit exceeded".into()));
    }
    Ok(format!("sha256:{:x}", Sha256::digest(bytes)))
}

/// Deterministically assigns whole leakage groups, plus optional family holdouts.
pub fn freeze_splits(
    examples: &[DatasetExample],
    dataset_sha256: &str,
    seed: u64,
    excluded_families: &BTreeSet<String>,
) -> Result<SplitManifest, DataError> {
    let mut groups = BTreeMap::<&str, Vec<&DatasetExample>>::new();
    for e in examples {
        groups.entry(&e.leakage_group).or_default().push(e);
    }
    let mut train = vec![];
    let mut dev = vec![];
    let mut test = vec![];
    let mut excluded = vec![];
    for (group, rows) in groups {
        let family_excluded = rows.iter().any(|e| {
            e.family
                .as_ref()
                .is_some_and(|f| excluded_families.contains(f))
        });
        let bucket = u64::from_be_bytes(
            Sha256::digest([seed.to_le_bytes().as_slice(), group.as_bytes()].concat())[..8]
                .try_into()
                .unwrap(),
        ) % 100;
        for e in rows {
            if family_excluded {
                excluded.push(e.case_id.clone());
            } else if bucket < 70 {
                train.push(e.case_id.clone());
            } else if bucket < 85 {
                dev.push(e.case_id.clone());
            } else {
                test.push(e.case_id.clone());
            }
        }
    }
    for v in [&mut train, &mut dev, &mut test, &mut excluded] {
        v.sort();
    }
    if train.is_empty() || dev.is_empty() || test.is_empty() {
        return Err(DataError::Invalid(
            "seed does not produce non-empty train/dev/test".into(),
        ));
    }
    let mut manifest = SplitManifest {
        version: DATASET_VERSION,
        dataset_sha256: dataset_sha256.into(),
        seed,
        train,
        dev,
        test,
        excluded,
        fingerprint: String::new(),
    };
    let bytes = serde_json::to_vec(&manifest)?;
    manifest.fingerprint = format!("sha256:{:x}", Sha256::digest(bytes));
    Ok(manifest)
}

pub fn validate_split(
    examples: &[DatasetExample],
    manifest: &SplitManifest,
    dataset_sha256: &str,
) -> Result<(), DataError> {
    if manifest.version != DATASET_VERSION || manifest.dataset_sha256 != dataset_sha256 {
        return Err(DataError::Invalid("split dataset identity drift".into()));
    }
    let expected: BTreeSet<_> = examples.iter().map(|e| e.case_id.as_str()).collect();
    let mut actual = BTreeSet::new();
    for part in [
        &manifest.train,
        &manifest.dev,
        &manifest.test,
        &manifest.excluded,
    ] {
        for id in part {
            if !actual.insert(id.as_str()) {
                return Err(DataError::Invalid(
                    "case assigned to multiple split partitions".into(),
                ));
            }
        }
    }
    if expected != actual {
        return Err(DataError::Invalid(
            "split does not cover exact dataset".into(),
        ));
    }
    let group_of: BTreeMap<_, _> = examples
        .iter()
        .map(|e| (e.case_id.as_str(), e.leakage_group.as_str()))
        .collect();
    for i in 0..4 {
        for j in i + 1..4 {
            let a = [
                &manifest.train,
                &manifest.dev,
                &manifest.test,
                &manifest.excluded,
            ][i];
            let b = [
                &manifest.train,
                &manifest.dev,
                &manifest.test,
                &manifest.excluded,
            ][j];
            let ga: BTreeSet<_> = a.iter().map(|x| group_of[x.as_str()]).collect();
            if b.iter().any(|x| ga.contains(group_of[x.as_str()])) {
                return Err(DataError::Invalid(
                    "leakage group crosses partitions".into(),
                ));
            }
        }
    }
    let mut canonical = manifest.clone();
    let recorded = canonical.fingerprint.clone();
    canonical.fingerprint.clear();
    let bytes = serde_json::to_vec(&canonical)?;
    if recorded != format!("sha256:{:x}", Sha256::digest(bytes)) {
        return Err(DataError::Invalid(
            "split manifest fingerprint mismatch".into(),
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn row(i: usize) -> DatasetExample {
        DatasetExample {
            case_id: format!("case-{i}"),
            leakage_group: format!("group-{i}"),
            family: None,
            counterfactual_pair: None,
            request: sdm_core::DecisionRequest {
                request_id: format!("req-{i}"),
                schema_version: 1,
                state: vec![],
                spec: sdm_core::DecisionSpec::Binary {
                    question: "q".into(),
                },
            },
            label: TargetLabel::Binary(i.is_multiple_of(2)),
        }
    }
    #[test]
    fn data_fingerprint_and_split_are_group_disjoint_and_immutable() {
        let rows: Vec<_> = (0..100).map(row).collect();
        let provenance = Provenance {
            source: "synthetic".into(),
            license: "MIT".into(),
            consent_scope: "synthetic-only".into(),
            label_lineage: "generated".into(),
            redistributable: true,
        };
        let digest = validate_dataset(&rows, &provenance).unwrap();
        let split = freeze_splits(&rows, &digest, 42, &BTreeSet::new()).unwrap();
        validate_split(&rows, &split, &digest).unwrap();
        let mut changed = split.clone();
        changed.train.pop();
        assert!(validate_split(&rows, &changed, &digest).is_err());
        assert!(validate_dataset(
            &rows,
            &Provenance {
                consent_scope: String::new(),
                ..provenance
            }
        )
        .is_err());
    }
}
