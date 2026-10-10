//! Provenance-bearing datasets and immutable, leakage-aware split manifests.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::io::BufRead;
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
    #[error("dataset input: {0}")]
    Input(#[from] std::io::Error),
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DuplicateAuditEntry {
    pub request_sha256: String,
    pub case_ids: Vec<String>,
    pub labels_conflict: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct NearDuplicatePair {
    pub left_case_id: String,
    pub right_case_id: String,
    pub left_group: String,
    pub right_group: String,
    pub jaccard_similarity: f64,
}

/// Reads one JSON-encoded example per line while enforcing byte and row limits.
pub fn read_jsonl<R: BufRead>(
    reader: R,
    provenance: &Provenance,
) -> Result<Vec<DatasetExample>, DataError> {
    let mut reader = reader.take((MAX_DATASET_BYTES + 1) as u64);
    let mut examples = Vec::new();
    let mut total_bytes = 0usize;
    let mut line = Vec::new();
    loop {
        line.clear();
        let read = reader.read_until(b'\n', &mut line)?;
        if read == 0 {
            break;
        }
        total_bytes = total_bytes
            .checked_add(read)
            .ok_or_else(|| DataError::Invalid("dataset byte count overflow".into()))?;
        if total_bytes > MAX_DATASET_BYTES {
            return Err(DataError::Invalid("dataset byte limit exceeded".into()));
        }
        if line.iter().all(u8::is_ascii_whitespace) {
            continue;
        }
        if examples.len() >= MAX_CASES {
            return Err(DataError::Invalid("case count limit exceeded".into()));
        }
        let example = serde_json::from_slice::<DatasetExample>(&line)?;
        examples.push(example);
    }
    validate_dataset(&examples, provenance)?;
    Ok(examples)
}

/// Finds exact canonical request duplicates and flags disagreements in labels.
/// Similarity is deliberately not inferred here; callers can add reviewed
/// near-duplicate relations to `leakage_group`/`counterfactual_pair` metadata.
pub fn audit_exact_duplicates(
    examples: &[DatasetExample],
) -> Result<Vec<DuplicateAuditEntry>, DataError> {
    let mut buckets = BTreeMap::<String, Vec<(&str, Vec<u8>)>>::new();
    for example in examples {
        let mut request = example.request.clone();
        request.request_id = "canonical-duplicate-audit".into();
        let request_sha256 = request
            .canonical_fingerprint()
            .map_err(|e| DataError::Invalid(e.to_string()))?;
        let label = serde_json::to_vec(&example.label)?;
        buckets
            .entry(request_sha256)
            .or_default()
            .push((&example.case_id, label));
    }
    Ok(buckets
        .into_iter()
        .filter_map(|(request_sha256, rows)| {
            if rows.len() < 2 {
                return None;
            }
            let labels_conflict = rows.iter().skip(1).any(|(_, label)| label != &rows[0].1);
            Some(DuplicateAuditEntry {
                request_sha256,
                case_ids: rows.into_iter().map(|(id, _)| id.to_owned()).collect(),
                labels_conflict,
            })
        })
        .collect())
}

/// Bounded MinHash/LSH candidate audit over normalized request text. This is
/// advisory lexical evidence, not a semantic proof; confirmed pairs should be
/// assigned to one leakage group before a split is frozen.
pub fn audit_near_duplicates(
    examples: &[DatasetExample],
    minimum_jaccard: f64,
    max_comparisons: usize,
) -> Result<Vec<NearDuplicatePair>, DataError> {
    if !minimum_jaccard.is_finite()
        || !(0.5..=1.0).contains(&minimum_jaccard)
        || max_comparisons == 0
    {
        return Err(DataError::Invalid(
            "invalid near-duplicate audit bounds".into(),
        ));
    }
    const HASHES: usize = 64;
    const BAND: usize = 8;
    let token_sets: Vec<BTreeSet<String>> = examples
        .iter()
        .map(|e| {
            let mut text = String::new();
            for field in &e.request.state {
                text.push_str(&field.key);
                text.push(' ');
                text.push_str(&field.value);
                text.push(' ');
            }
            match &e.request.spec {
                sdm_core::DecisionSpec::Binary { question }
                | sdm_core::DecisionSpec::Choice { question, .. } => text.push_str(question),
                sdm_core::DecisionSpec::Score { rubric, .. } => text.push_str(rubric),
                sdm_core::DecisionSpec::Rank {
                    instruction,
                    candidates,
                    ..
                } => {
                    text.push_str(instruction);
                    for candidate in candidates {
                        text.push(' ');
                        text.push_str(&candidate.label);
                        text.push(' ');
                        text.push_str(&candidate.description);
                    }
                }
            }
            sdm_core::tokens(&text).collect()
        })
        .collect();
    let mut buckets = BTreeMap::<Vec<u64>, Vec<usize>>::new();
    for (index, tokens) in token_sets.iter().enumerate() {
        if tokens.is_empty() {
            continue;
        }
        let mut signature = [u64::MAX; HASHES];
        for token in tokens {
            let digest = Sha256::digest(token.as_bytes());
            let base = u64::from_be_bytes(digest[..8].try_into().unwrap());
            for (seed, slot) in signature.iter_mut().enumerate() {
                let mut mixed = base ^ (seed as u64).wrapping_mul(0x9e3779b97f4a7c15);
                mixed = (mixed ^ (mixed >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
                mixed = (mixed ^ (mixed >> 27)).wrapping_mul(0x94d049bb133111eb);
                mixed ^= mixed >> 31;
                *slot = (*slot).min(mixed);
            }
        }
        for band in 0..HASHES / BAND {
            let key = signature[band * BAND..(band + 1) * BAND].to_vec();
            buckets.entry(key).or_default().push(index);
        }
    }
    let mut candidates = BTreeSet::<(usize, usize)>::new();
    for members in buckets.values() {
        if members.len() > 512 {
            return Err(DataError::Invalid(
                "near-duplicate bucket exceeds bound".into(),
            ));
        }
        for a in 0..members.len() {
            for b in a + 1..members.len() {
                candidates.insert((members[a], members[b]));
                if candidates.len() > max_comparisons {
                    return Err(DataError::Invalid(
                        "near-duplicate comparison bound exceeded".into(),
                    ));
                }
            }
        }
    }
    let mut result = Vec::new();
    for (left, right) in candidates {
        let a = &token_sets[left];
        let b = &token_sets[right];
        let union = a.union(b).count();
        if union == 0 {
            continue;
        }
        let similarity = a.intersection(b).count() as f64 / union as f64;
        if similarity >= minimum_jaccard {
            result.push(NearDuplicatePair {
                left_case_id: examples[left].case_id.clone(),
                right_case_id: examples[right].case_id.clone(),
                left_group: examples[left].leakage_group.clone(),
                right_group: examples[right].leakage_group.clone(),
                jaccard_similarity: similarity,
            });
        }
    }
    Ok(result)
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

    #[test]
    fn streaming_jsonl_and_duplicate_audit_ignore_request_ids() {
        let provenance = Provenance {
            source: "synthetic".into(),
            license: "MIT".into(),
            consent_scope: "synthetic-only".into(),
            label_lineage: "generated".into(),
            redistributable: true,
        };
        let first = row(1);
        let mut second = first.clone();
        second.case_id = "case-copy".into();
        second.leakage_group = "group-copy".into();
        second.request.request_id = "different-request-id".into();
        let mut input = serde_json::to_vec(&first).unwrap();
        input.push(b'\n');
        input.extend(serde_json::to_vec(&second).unwrap());
        let parsed = read_jsonl(std::io::Cursor::new(input), &provenance).unwrap();
        assert_eq!(parsed.len(), 2);
        let audit = audit_exact_duplicates(&parsed).unwrap();
        assert_eq!(audit.len(), 1);
        assert!(!audit[0].labels_conflict);
        assert_eq!(audit_near_duplicates(&parsed, 0.8, 100).unwrap().len(), 1);
        let mut conflicting = parsed;
        conflicting[1].label = TargetLabel::Binary(true);
        assert!(audit_exact_duplicates(&conflicting).unwrap()[0].labels_conflict);
    }
}
