//! M015a Choice final-action evaluation-integrity corrective (v2 contract).
//!
//! This module is additive and does not change any historical metric meaning.
//! Historical keys such as `dev_answerable_accuracy`,
//! `dev_counterfactual_correct_on_both`, `dev_nuisance_correct_on_both` and
//! `dev_nuisance_pair_prediction_agreement` retain their implemented (mixed
//! raw/final) semantics in old reports. New v2 keys are versioned and operate
//! on **final** runtime actions only.
//!
//! Final-action correctness:
//! - truth `Some(id)`: only an answered `Choice(id)` with that exact ID is
//!   correct. Any abstention is a false abstention; any other ID is a wrong
//!   choice.
//! - truth `None`: only a final abstention is correct. Any chosen ID is a
//!   false positive. Unsupported/invalid requests (0/1 options) must fail
//!   closed before reaching this evaluator and are never valid `Choice(None)`.
//!
//! Raw conditional ranking (`argmax` of `conditional_probs`), answerability
//! (`answerability_p`), coverage and calibration are reported separately and
//! never conflated with final correctness.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};

use crate::EvalError;

pub const CONTRACT_VERSION: &str = "choice-final-v2";
pub const CONTRACT_SEED: u64 = 150015;
pub const CONTRACT_REPLICATES: usize = 2000;
pub const CONTRACT_CONFIDENCE: f64 = 0.95;
pub const CONTRACT_METHOD: &str = "grouped_bootstrap_percentile_sorted_v1";

/// Source-defined no-answer provenance. Must be supplied from corpus
/// provenance (available flag + satisfying count + rule), never inferred
/// from the prediction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NoAnswerOrigin {
    /// `available == false`: context explicitly unavailable.
    UnavailableContext,
    /// `available == true` with zero satisfying candidates after the
    /// declared causal flip.
    ZeroSatisfyingCandidates,
}

/// Declarative pair kind. The matcher accepts only these two; any other
/// suffix or label fails closed (no ad-hoc "everything else is causal").
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PairKind {
    Nuisance,
    Causal,
}

impl PairKind {
    pub fn from_pair_id(pair_id: &str) -> Result<Self, EvalError> {
        if pair_id.ends_with("-nuisance") {
            Ok(Self::Nuisance)
        } else if pair_id.ends_with("-causal") {
            Ok(Self::Causal)
        } else {
            Err(EvalError::Invalid(format!(
                "pair id '{pair_id}' has no declarative -nuisance/-causal suffix"
            )))
        }
    }

    pub fn from_pair_type_label(label: &str) -> Result<Self, EvalError> {
        match label {
            "nuisance" => Ok(Self::Nuisance),
            "causal_flip" | "causal" => Ok(Self::Causal),
            _ => Err(EvalError::Invalid(format!(
                "unknown declarative pair type '{label}'"
            ))),
        }
    }
}

/// One typed Choice case with final runtime outputs and source provenance.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ChoiceFinalCase {
    pub case_id: String,
    pub leakage_group: String,
    pub family: String,
    pub split: String,
    pub pair_id: Option<String>,
    /// Source pair_type label (`nuisance` / `causal_flip`); None when unpaired.
    pub pair_type: Option<String>,
    pub target: Option<String>,
    /// Permitted option IDs in request order.
    pub option_ids: Vec<String>,
    /// Final runtime decision: Some(id) when answered, None when abstained.
    pub predicted: Option<String>,
    /// Conditional probabilities aligned to `option_ids` order.
    pub conditional_probs: Vec<f64>,
    pub conditional_logits: Option<Vec<f64>>,
    /// Explicit P(answerable) before thresholding.
    pub answerability_p: f64,
    /// Required when target is None; must be None when target is Some.
    pub no_answer_origin: Option<NoAnswerOrigin>,
    /// Opaque digests for strict pair validation (canonical JSON SHA of
    /// context / option semantics / rule). Empty string disables that check
    /// for unit fixtures that do not carry corpus digests.
    #[serde(default)]
    pub context_digest: String,
    #[serde(default)]
    pub semantics_digest: String,
    #[serde(default)]
    pub rule_digest: String,
}

impl ChoiceFinalCase {
    pub fn validate(&self) -> Result<(), EvalError> {
        if self.case_id.is_empty() || self.leakage_group.is_empty() || self.family.is_empty() {
            return Err(EvalError::Invalid("empty case/group/family id".into()));
        }
        if self.split != "train" && self.split != "dev" {
            return Err(EvalError::Invalid(format!(
                "split must be train/dev, got '{}'",
                self.split
            )));
        }
        if self.option_ids.len() < 2 || self.option_ids.len() > 128 {
            return Err(EvalError::Invalid(format!(
                "Choice requires 2..=128 options, got {}",
                self.option_ids.len()
            )));
        }
        let mut seen = BTreeSet::new();
        for id in &self.option_ids {
            if id.is_empty() || !seen.insert(id.as_str()) {
                return Err(EvalError::Invalid("duplicate or empty option id".into()));
            }
        }
        let option_set: BTreeSet<_> = self.option_ids.iter().collect();
        if let Some(t) = &self.target {
            if !option_set.contains(t) {
                return Err(EvalError::Invalid(
                    "choice target outside permitted option identities".into(),
                ));
            }
            if self.no_answer_origin.is_some() {
                return Err(EvalError::Invalid(
                    "answerable row must not carry a no-answer origin".into(),
                ));
            }
        } else if self.no_answer_origin.is_none() {
            return Err(EvalError::Invalid(
                "no-answer row must carry an explicit source origin".into(),
            ));
        }
        if let Some(p) = &self.predicted {
            if !option_set.contains(p) {
                return Err(EvalError::Invalid(
                    "predicted id outside permitted option identities".into(),
                ));
            }
        }
        if self.conditional_probs.len() != self.option_ids.len() {
            return Err(EvalError::Invalid(
                "conditional probability length must match option order".into(),
            ));
        }
        if self
            .conditional_probs
            .iter()
            .any(|p| !p.is_finite() || *p < 0.0 || *p > 1.0)
        {
            return Err(EvalError::Invalid(
                "non-finite or out-of-range conditional probability".into(),
            ));
        }
        let sum: f64 = self.conditional_probs.iter().sum();
        if (sum - 1.0).abs() > 1e-8 {
            return Err(EvalError::Invalid(format!(
                "conditional probabilities must sum to 1 (got {sum})"
            )));
        }
        if let Some(logits) = &self.conditional_logits {
            if logits.len() != self.option_ids.len() || logits.iter().any(|x| !x.is_finite()) {
                return Err(EvalError::Invalid(
                    "conditional logits length/finiteness mismatch".into(),
                ));
            }
        }
        if !self.answerability_p.is_finite() || !(0.0..=1.0).contains(&self.answerability_p) {
            return Err(EvalError::Invalid(
                "answerability probability must be finite in [0,1]".into(),
            ));
        }
        if let Some(pair_id) = &self.pair_id {
            if pair_id.is_empty() {
                return Err(EvalError::Invalid("empty pair id".into()));
            }
            // Declarative suffix must be present; no silent default.
            PairKind::from_pair_id(pair_id)?;
            if let Some(label) = &self.pair_type {
                let from_id = PairKind::from_pair_id(pair_id)?;
                let from_label = PairKind::from_pair_type_label(label)?;
                if from_id != from_label {
                    return Err(EvalError::Invalid(format!(
                        "pair id suffix {from_id:?} disagrees with pair type label '{label}'"
                    )));
                }
            } else {
                return Err(EvalError::Invalid(
                    "paired row must carry an explicit pair_type label".into(),
                ));
            }
        } else if self.pair_type.is_some() {
            return Err(EvalError::Invalid("pair_type without pair_id".into()));
        }
        Ok(())
    }

    /// Final-action correctness: answered exact ID for Some, abstention for None.
    pub fn is_final_correct(&self) -> bool {
        match (&self.target, &self.predicted) {
            (Some(t), Some(p)) => t == p,
            (None, None) => true,
            _ => false,
        }
    }

    pub fn is_false_abstention(&self) -> bool {
        self.target.is_some() && self.predicted.is_none()
    }

    pub fn is_false_positive(&self) -> bool {
        self.target.is_none() && self.predicted.is_some()
    }

    pub fn is_answered(&self) -> bool {
        self.predicted.is_some()
    }

    /// Raw conditional argmax in request order, with the runtime tie-break
    /// (larger probability wins; ties resolve to the smaller option ID).
    pub fn conditional_argmax(&self) -> String {
        let mut best = 0usize;
        for i in 1..self.option_ids.len() {
            let ord = self.conditional_probs[i].total_cmp(&self.conditional_probs[best]);
            if ord == std::cmp::Ordering::Greater
                || (ord == std::cmp::Ordering::Equal && self.option_ids[i] < self.option_ids[best])
            {
                best = i;
            }
        }
        self.option_ids[best].clone()
    }

    pub fn is_conditional_argmax_correct(&self) -> Option<bool> {
        self.target
            .as_ref()
            .map(|t| &self.conditional_argmax() == t)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SupportStatus {
    Ok,
    InsufficientSupport,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MetricEstimate {
    pub value: Option<f64>,
    pub eligible_cases: usize,
    pub eligible_groups: usize,
    pub status: SupportStatus,
}

impl MetricEstimate {
    pub fn ok(value: f64, cases: usize, groups: usize) -> Self {
        Self {
            value: Some(value),
            eligible_cases: cases,
            eligible_groups: groups,
            status: SupportStatus::Ok,
        }
    }
    pub fn insufficient(cases: usize, groups: usize) -> Self {
        Self {
            value: None,
            eligible_cases: cases,
            eligible_groups: groups,
            status: SupportStatus::InsufficientSupport,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BootstrapCi {
    pub lower: f64,
    pub upper: f64,
    pub confidence: f64,
    pub groups: usize,
    pub replicates: usize,
    pub seed: u64,
    pub method: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FamilyMetrics {
    pub family: String,
    pub eligible_cases: usize,
    pub eligible_groups: usize,
    pub answerable_cases: usize,
    pub no_answer_cases: usize,
    pub final_accuracy: MetricEstimate,
    pub answerable_final_accuracy: MetricEstimate,
    pub no_answer_recall: MetricEstimate,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PairClassMetrics {
    /// Eligible pairs after strict fail-closed validation.
    pub eligible_pairs: usize,
    pub eligible_groups: usize,
    /// Ineligible pair IDs with fail-closed reasons (capped for readability).
    pub ineligible_pairs: BTreeMap<String, String>,
    pub both_final_correct: MetricEstimate,
    pub both_final_correct_ci: Option<BootstrapCi>,
    /// For nuisance: fraction where both final decisions are identical
    /// (including double abstention). Consistency alone is not robustness.
    pub prediction_consistency: MetricEstimate,
    /// Fraction where both final decisions are identical AND correctness is
    /// preserved (both correct). Distinguishes harmless stable abstention
    /// from false double abstention.
    pub correctness_preserving_agreement: MetricEstimate,
    /// Optional raw conditional argmax agreement (distinct from final).
    pub raw_argmax_agreement: MetricEstimate,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ChoiceFinalReportV2 {
    pub contract: String,
    pub eligible_cases: usize,
    pub eligible_groups: usize,
    pub answerable_cases: usize,
    pub answerable_groups: usize,
    pub no_answer_cases: usize,
    pub no_answer_groups: usize,
    pub no_answer_by_origin: BTreeMap<String, OriginSupport>,
    pub dev_final_action_accuracy_v2: MetricEstimate,
    pub dev_final_action_accuracy_v2_ci: Option<BootstrapCi>,
    pub dev_answerable_final_accuracy_v2: MetricEstimate,
    pub dev_answerable_final_accuracy_v2_ci: Option<BootstrapCi>,
    pub dev_false_abstention_rate_v2: MetricEstimate,
    pub dev_no_answer_final_recall_v2: MetricEstimate,
    pub dev_no_answer_final_recall_v2_ci: Option<BootstrapCi>,
    pub dev_answerable_final_coverage_v2: MetricEstimate,
    pub dev_conditional_argmax_accuracy_v2: MetricEstimate,
    pub dev_conditional_argmax_accuracy_v2_ci: Option<BootstrapCi>,
    pub dev_answered_conditional_accuracy_v2: MetricEstimate,
    pub dev_answerability_brier_v2: MetricEstimate,
    pub dev_answerability_log_loss_v2: MetricEstimate,
    pub dev_answerability_ece_10_bins_v2: MetricEstimate,
    pub dev_conditional_nll_v2: MetricEstimate,
    pub dev_conditional_brier_v2: MetricEstimate,
    pub causal: PairClassMetrics,
    pub nuisance: PairClassMetrics,
    pub families: BTreeMap<String, FamilyMetrics>,
    pub bootstrap_seed: u64,
    pub bootstrap_replicates: usize,
    pub bootstrap_confidence: f64,
    pub bootstrap_method: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct OriginSupport {
    pub cases: usize,
    pub groups: usize,
    pub recall: MetricEstimate,
    pub false_positives: usize,
}

fn groups_of<'a>(cases: &[&'a ChoiceFinalCase]) -> BTreeSet<&'a str> {
    cases.iter().map(|c| c.leakage_group.as_str()).collect()
}

fn ece_10_bins(cases: &[&ChoiceFinalCase]) -> f64 {
    let mut bins = [(0usize, 0.0f64, 0.0f64); 10];
    for c in cases {
        let bin = ((c.answerability_p * 10.0).floor() as usize).min(9);
        bins[bin].0 += 1;
        bins[bin].1 += c.answerability_p;
        bins[bin].2 += f64::from(c.target.is_some());
    }
    let n = cases.len().max(1) as f64;
    bins.iter()
        .filter(|b| b.0 > 0)
        .map(|(count, conf, obs)| {
            (*count as f64 / n) * ((conf / *count as f64) - (obs / *count as f64)).abs()
        })
        .sum()
}

fn grouped_ci(
    observations: &[(String, f64)],
    seed: u64,
    replicates: usize,
    confidence: f64,
) -> Result<Option<BootstrapCi>, EvalError> {
    let interval = crate::grouped_bootstrap_mean(observations, seed, replicates, confidence)?;
    Ok(interval.map(|ci| BootstrapCi {
        lower: ci.lower,
        upper: ci.upper,
        confidence: ci.confidence,
        groups: ci.groups,
        replicates: ci.replicates,
        seed,
        method: CONTRACT_METHOD.into(),
    }))
}

fn mean_or_insufficient(correct: usize, total: usize, groups: usize) -> MetricEstimate {
    if total == 0 {
        MetricEstimate::insufficient(0, groups)
    } else {
        MetricEstimate::ok(correct as f64 / total as f64, total, groups)
    }
}

/// Strict exactly-two pair matcher. Fails closed on missing, duplicate,
/// three-member, split-crossing, relabeled-nuisance, changed-context causal
/// and mismatched-option pairs. Returns eligible pairs plus an ineligible map.
pub type PairMatch = (
    BTreeMap<String, Vec<ChoiceFinalCase>>,
    BTreeMap<String, String>,
);
#[allow(clippy::type_complexity)]
pub fn match_pairs(cases: &[ChoiceFinalCase]) -> Result<PairMatch, EvalError> {
    for c in cases {
        c.validate()?;
    }
    // Group rows by pair_id.
    let mut by_pair: BTreeMap<String, Vec<ChoiceFinalCase>> = BTreeMap::new();
    for c in cases {
        if let Some(pid) = &c.pair_id {
            by_pair.entry(pid.clone()).or_default().push(c.clone());
        }
    }
    let mut eligible: BTreeMap<String, Vec<ChoiceFinalCase>> = BTreeMap::new();
    let mut ineligible: BTreeMap<String, String> = BTreeMap::new();
    // Detect duplicate case IDs globally (same case in two pairs is malformed).
    let mut case_to_pair: BTreeMap<&str, &str> = BTreeMap::new();
    for (pid, members) in &by_pair {
        for m in members {
            if let Some(old) = case_to_pair.insert(m.case_id.as_str(), pid.as_str()) {
                if old != pid.as_str() {
                    ineligible.insert(
                        pid.clone(),
                        format!("duplicate case {} also in {old}", m.case_id),
                    );
                }
            }
        }
    }
    for (pid, members) in &by_pair {
        if ineligible.contains_key(pid) {
            continue;
        }
        // Declarative suffix must parse; unknown suffix fails closed.
        let kind = match PairKind::from_pair_id(pid) {
            Ok(k) => k,
            Err(e) => {
                ineligible.insert(pid.clone(), e.to_string());
                continue;
            }
        };
        // Exactly two unique case IDs.
        let unique_cases: BTreeSet<_> = members.iter().map(|m| m.case_id.as_str()).collect();
        if members.len() != 2 || unique_cases.len() != 2 {
            ineligible.insert(
                pid.clone(),
                format!(
                    "pair must have exactly two unique case ids (got {} rows, {} unique)",
                    members.len(),
                    unique_cases.len()
                ),
            );
            continue;
        }
        let a = &members[0];
        let b = &members[1];
        // Same leakage group, split, family, rule.
        if a.leakage_group != b.leakage_group {
            ineligible.insert(pid.clone(), "pair spans leakage groups".into());
            continue;
        }
        if a.split != b.split {
            ineligible.insert(pid.clone(), "pair crosses splits".into());
            continue;
        }
        if a.family != b.family {
            ineligible.insert(pid.clone(), "pair spans families".into());
            continue;
        }
        if !a.rule_digest.is_empty() && !b.rule_digest.is_empty() && a.rule_digest != b.rule_digest
        {
            ineligible.insert(pid.clone(), "pair spans rules".into());
            continue;
        }
        // Pair type label must agree with suffix (validated per-case, re-check).
        match (
            PairKind::from_pair_type_label(a.pair_type.as_ref().unwrap()),
            kind,
        ) {
            (Ok(k), expected) if k == expected => {}
            _ => {
                ineligible.insert(pid.clone(), "pair type label mismatch".into());
                continue;
            }
        }
        if b.pair_type != a.pair_type {
            ineligible.insert(pid.clone(), "pair members disagree on pair_type".into());
            continue;
        }
        // Compatible option identity sets.
        let set_a: BTreeSet<_> = a.option_ids.iter().collect();
        let set_b: BTreeSet<_> = b.option_ids.iter().collect();
        if set_a != set_b {
            ineligible.insert(pid.clone(), "mismatched option identity sets".into());
            continue;
        }
        match kind {
            PairKind::Nuisance => {
                // Nuisance must preserve targets exactly; accidentally relabeled
                // nuisance (targets differ) fails closed as ineligible.
                if a.target != b.target {
                    ineligible.insert(
                        pid.clone(),
                        "nuisance pair targets differ (accidental relabel)".into(),
                    );
                    continue;
                }
                // Candidate semantics must be preserved when digests present.
                if !a.semantics_digest.is_empty()
                    && !b.semantics_digest.is_empty()
                    && a.semantics_digest != b.semantics_digest
                {
                    ineligible.insert(
                        pid.clone(),
                        "nuisance pair changed candidate semantics".into(),
                    );
                    continue;
                }
                // Order-reversal control: same ID set but different order is the
                // expected eligible nuisance class. Identical order is still
                // eligible but recorded as a separate class downstream; we do
                // not reject it here. Different ID sets already rejected above.
                // Context should differ (declared nuisance perturbation) when
                // digests present; identical context is suspicious but not
                // rejected to keep the matcher reusable.
            }
            PairKind::Causal => {
                // M015 candidate-flip contract: exactly one None and one Some.
                let none_count = [&a.target, &b.target]
                    .iter()
                    .filter(|t| t.is_none())
                    .count();
                if none_count != 1 {
                    ineligible.insert(
                        pid.clone(),
                        format!(
                            "causal candidate-flip pair must have exactly one no-answer member (got {none_count})"
                        ),
                    );
                    continue;
                }
                // Context must be identical when digests present; a changed
                // context causal pair fails closed.
                if !a.context_digest.is_empty()
                    && !b.context_digest.is_empty()
                    && a.context_digest != b.context_digest
                {
                    ineligible.insert(
                        pid.clone(),
                        "causal pair changed context (must hold context fixed)".into(),
                    );
                    continue;
                }
                // Semantics must differ (declared single-feature flip) when
                // digests present.
                if !a.semantics_digest.is_empty()
                    && !b.semantics_digest.is_empty()
                    && a.semantics_digest == b.semantics_digest
                {
                    ineligible.insert(
                        pid.clone(),
                        "causal pair preserved candidate semantics (no declared flip)".into(),
                    );
                    continue;
                }
                // Option order must be preserved for causal flips.
                if a.option_ids != b.option_ids {
                    ineligible.insert(pid.clone(), "causal pair changed option order".into());
                    continue;
                }
            }
        }
        eligible.insert(pid.clone(), members.clone());
    }
    Ok((eligible, ineligible))
}

/// Reusable v2 final-action evaluator. All denominators are explicit;
/// empty strata return `insufficient_support`, never 0/0 -> 0.
pub fn evaluate_choice_final_v2(
    cases: &[ChoiceFinalCase],
) -> Result<ChoiceFinalReportV2, EvalError> {
    for c in cases {
        c.validate()?;
    }
    // Stable sorted inputs for deterministic grouping and bootstrap.
    let mut sorted: Vec<&ChoiceFinalCase> = cases.iter().collect();
    sorted.sort_by(|a, b| {
        a.leakage_group
            .cmp(&b.leakage_group)
            .then_with(|| a.case_id.cmp(&b.case_id))
    });

    let eligible_groups = groups_of(&sorted).len();
    let answerable: Vec<&ChoiceFinalCase> = sorted
        .iter()
        .copied()
        .filter(|c| c.target.is_some())
        .collect();
    let no_answer: Vec<&ChoiceFinalCase> = sorted
        .iter()
        .copied()
        .filter(|c| c.target.is_none())
        .collect();
    let answerable_groups = groups_of(&answerable).len();
    let no_answer_groups = groups_of(&no_answer).len();

    let final_correct = sorted.iter().filter(|c| c.is_final_correct()).count();
    let dev_final_action_accuracy_v2 = if sorted.is_empty() {
        MetricEstimate::insufficient(0, 0)
    } else {
        mean_or_insufficient(final_correct, sorted.len(), eligible_groups)
    };

    let answerable_correct = answerable.iter().filter(|c| c.is_final_correct()).count();
    let dev_answerable_final_accuracy_v2 = if answerable.is_empty() {
        MetricEstimate::insufficient(0, 0)
    } else {
        mean_or_insufficient(answerable_correct, answerable.len(), answerable_groups)
    };

    let false_abstentions = answerable
        .iter()
        .filter(|c| c.is_false_abstention())
        .count();
    let dev_false_abstention_rate_v2 = if answerable.is_empty() {
        MetricEstimate::insufficient(0, 0)
    } else {
        MetricEstimate::ok(
            false_abstentions as f64 / answerable.len() as f64,
            answerable.len(),
            answerable_groups,
        )
    };

    let no_answer_correct = no_answer.iter().filter(|c| c.is_final_correct()).count();
    let dev_no_answer_final_recall_v2 = if no_answer.is_empty() {
        MetricEstimate::insufficient(0, 0)
    } else {
        mean_or_insufficient(no_answer_correct, no_answer.len(), no_answer_groups)
    };

    let answered_answerable = answerable.iter().filter(|c| c.is_answered()).count();
    let dev_answerable_final_coverage_v2 = if answerable.is_empty() {
        MetricEstimate::insufficient(0, 0)
    } else {
        MetricEstimate::ok(
            answered_answerable as f64 / answerable.len() as f64,
            answerable.len(),
            answerable_groups,
        )
    };

    // Raw conditional ranking stays separate.
    let raw_correct = answerable
        .iter()
        .filter(|c| c.is_conditional_argmax_correct() == Some(true))
        .count();
    let dev_conditional_argmax_accuracy_v2 = if answerable.is_empty() {
        MetricEstimate::insufficient(0, 0)
    } else {
        mean_or_insufficient(raw_correct, answerable.len(), answerable_groups)
    };

    // Answered-only selective accuracy: denominator is answered answerable rows.
    let answered_cases: Vec<&ChoiceFinalCase> = answerable
        .iter()
        .copied()
        .filter(|c| c.is_answered())
        .collect();
    let answered_groups = groups_of(&answered_cases).len();
    let answered_correct = answered_cases
        .iter()
        .filter(|c| c.is_final_correct())
        .count();
    let dev_answered_conditional_accuracy_v2 = if answered_cases.is_empty() {
        MetricEstimate::insufficient(0, 0)
    } else {
        mean_or_insufficient(answered_correct, answered_cases.len(), answered_groups)
    };

    // Answerability calibration (uses explicit P(answerable)).
    let mut brier_sum = 0.0;
    let mut nll_sum = 0.0;
    for c in &sorted {
        let y = f64::from(c.target.is_some());
        brier_sum += (c.answerability_p - y).powi(2);
        let p = c.answerability_p.clamp(1e-15, 1.0 - 1e-15);
        nll_sum += if c.target.is_some() {
            -p.ln()
        } else {
            -(1.0 - p).ln()
        };
    }
    let (brier_est, nll_est, ece_est) = if sorted.is_empty() {
        (
            MetricEstimate::insufficient(0, 0),
            MetricEstimate::insufficient(0, 0),
            MetricEstimate::insufficient(0, 0),
        )
    } else {
        (
            MetricEstimate::ok(
                brier_sum / sorted.len() as f64,
                sorted.len(),
                eligible_groups,
            ),
            MetricEstimate::ok(nll_sum / sorted.len() as f64, sorted.len(), eligible_groups),
            MetricEstimate::ok(ece_10_bins(&sorted), sorted.len(), eligible_groups),
        )
    };

    // Conditional NLL/Brier on answerable rows only.
    let mut cond_nll = 0.0;
    let mut cond_brier = 0.0;
    for c in &answerable {
        let target_idx = c
            .option_ids
            .iter()
            .position(|id| Some(id) == c.target.as_ref())
            .ok_or_else(|| EvalError::Invalid("target outside options".into()))?;
        cond_nll -= c.conditional_probs[target_idx].clamp(1e-15, 1.0).ln();
        cond_brier += c
            .conditional_probs
            .iter()
            .enumerate()
            .map(|(i, p)| (p - f64::from(i == target_idx)).powi(2))
            .sum::<f64>();
    }
    let (cond_nll_est, cond_brier_est) = if answerable.is_empty() {
        (
            MetricEstimate::insufficient(0, 0),
            MetricEstimate::insufficient(0, 0),
        )
    } else {
        (
            MetricEstimate::ok(
                cond_nll / answerable.len() as f64,
                answerable.len(),
                answerable_groups,
            ),
            MetricEstimate::ok(
                cond_brier / answerable.len() as f64,
                answerable.len(),
                answerable_groups,
            ),
        )
    };

    // Grouped bootstrap CIs (sorted replicate arrays via shared helper).
    let final_obs: Vec<(String, f64)> = sorted
        .iter()
        .map(|c| (c.leakage_group.clone(), f64::from(c.is_final_correct())))
        .collect();
    let answerable_obs: Vec<(String, f64)> = answerable
        .iter()
        .map(|c| (c.leakage_group.clone(), f64::from(c.is_final_correct())))
        .collect();
    let no_answer_obs: Vec<(String, f64)> = no_answer
        .iter()
        .map(|c| (c.leakage_group.clone(), f64::from(c.is_final_correct())))
        .collect();
    let raw_obs: Vec<(String, f64)> = answerable
        .iter()
        .map(|c| {
            (
                c.leakage_group.clone(),
                f64::from(c.is_conditional_argmax_correct() == Some(true)),
            )
        })
        .collect();
    let dev_final_action_accuracy_v2_ci = if sorted.is_empty() {
        None
    } else {
        grouped_ci(
            &final_obs,
            CONTRACT_SEED,
            CONTRACT_REPLICATES,
            CONTRACT_CONFIDENCE,
        )?
    };
    let dev_answerable_final_accuracy_v2_ci = if answerable.is_empty() {
        None
    } else {
        grouped_ci(
            &answerable_obs,
            CONTRACT_SEED,
            CONTRACT_REPLICATES,
            CONTRACT_CONFIDENCE,
        )?
    };
    let dev_no_answer_final_recall_v2_ci = if no_answer.is_empty() {
        None
    } else {
        grouped_ci(
            &no_answer_obs,
            CONTRACT_SEED,
            CONTRACT_REPLICATES,
            CONTRACT_CONFIDENCE,
        )?
    };
    let dev_conditional_argmax_accuracy_v2_ci = if answerable.is_empty() {
        None
    } else {
        grouped_ci(
            &raw_obs,
            CONTRACT_SEED,
            CONTRACT_REPLICATES,
            CONTRACT_CONFIDENCE,
        )?
    };

    // No-answer by origin: separate recall/support/false positives.
    let mut no_answer_by_origin: BTreeMap<String, OriginSupport> = BTreeMap::new();
    for origin in [
        NoAnswerOrigin::UnavailableContext,
        NoAnswerOrigin::ZeroSatisfyingCandidates,
    ] {
        let key = match origin {
            NoAnswerOrigin::UnavailableContext => "available_false",
            NoAnswerOrigin::ZeroSatisfyingCandidates => "available_true_zero_satisfying",
        };
        let rows: Vec<&ChoiceFinalCase> = no_answer
            .iter()
            .copied()
            .filter(|c| c.no_answer_origin == Some(origin))
            .collect();
        let g = groups_of(&rows).len();
        let correct = rows.iter().filter(|c| c.is_final_correct()).count();
        let recall = if rows.is_empty() {
            MetricEstimate::insufficient(0, 0)
        } else {
            mean_or_insufficient(correct, rows.len(), g)
        };
        // False positives with this origin cannot occur (origin only on None
        // rows); count answerable false positives globally for visibility.
        no_answer_by_origin.insert(
            key.into(),
            OriginSupport {
                cases: rows.len(),
                groups: g,
                recall,
                false_positives: 0,
            },
        );
    }
    // Global false positives (answerable predicted as abstained is false
    // abstention; no-answer predicted as chosen is false positive).
    let global_false_positives = sorted.iter().filter(|c| c.is_false_positive()).count();
    // Attribute false positives to no-answer aggregate for reporting.
    // (Per-origin false positives are zero by construction; the aggregate
    // false-positive count is the number of None rows predicted as Some.)

    // Pair metrics via strict matcher.
    let (eligible_pairs, ineligible_pairs) = match_pairs(cases)?;
    let mut causal_pairs: BTreeMap<String, Vec<ChoiceFinalCase>> = BTreeMap::new();
    let mut nuisance_pairs: BTreeMap<String, Vec<ChoiceFinalCase>> = BTreeMap::new();
    for (pid, members) in &eligible_pairs {
        match PairKind::from_pair_id(pid)? {
            PairKind::Causal => {
                causal_pairs.insert(pid.clone(), members.clone());
            }
            PairKind::Nuisance => {
                nuisance_pairs.insert(pid.clone(), members.clone());
            }
        }
    }
    let causal_metrics = pair_class_metrics(&causal_pairs, &ineligible_pairs, "-causal")?;
    let nuisance_metrics = pair_class_metrics(&nuisance_pairs, &ineligible_pairs, "-nuisance")?;

    // Per-family tables.
    let mut families: BTreeMap<String, FamilyMetrics> = BTreeMap::new();
    let mut by_family: BTreeMap<&str, Vec<&ChoiceFinalCase>> = BTreeMap::new();
    for c in &sorted {
        by_family.entry(c.family.as_str()).or_default().push(c);
    }
    for (family, rows) in &by_family {
        let g = groups_of(rows).len();
        let ans: Vec<&ChoiceFinalCase> = rows
            .iter()
            .copied()
            .filter(|c| c.target.is_some())
            .collect();
        let na: Vec<&ChoiceFinalCase> = rows
            .iter()
            .copied()
            .filter(|c| c.target.is_none())
            .collect();
        let ag = groups_of(&ans).len();
        let final_c = rows.iter().filter(|c| c.is_final_correct()).count();
        let ans_c = ans.iter().filter(|c| c.is_final_correct()).count();
        let na_c = na.iter().filter(|c| c.is_final_correct()).count();
        families.insert(
            (*family).to_string(),
            FamilyMetrics {
                family: (*family).to_string(),
                eligible_cases: rows.len(),
                eligible_groups: g,
                answerable_cases: ans.len(),
                no_answer_cases: na.len(),
                final_accuracy: if rows.is_empty() {
                    MetricEstimate::insufficient(0, 0)
                } else {
                    mean_or_insufficient(final_c, rows.len(), g)
                },
                answerable_final_accuracy: if ans.is_empty() {
                    MetricEstimate::insufficient(0, 0)
                } else {
                    mean_or_insufficient(ans_c, ans.len(), ag)
                },
                no_answer_recall: if na.is_empty() {
                    MetricEstimate::insufficient(0, 0)
                } else {
                    let ng = groups_of(&na).len();
                    mean_or_insufficient(na_c, na.len(), ng)
                },
            },
        );
    }

    let _ = global_false_positives;
    Ok(ChoiceFinalReportV2 {
        contract: CONTRACT_VERSION.into(),
        eligible_cases: sorted.len(),
        eligible_groups,
        answerable_cases: answerable.len(),
        answerable_groups,
        no_answer_cases: no_answer.len(),
        no_answer_groups,
        no_answer_by_origin,
        dev_final_action_accuracy_v2,
        dev_final_action_accuracy_v2_ci,
        dev_answerable_final_accuracy_v2,
        dev_answerable_final_accuracy_v2_ci,
        dev_false_abstention_rate_v2,
        dev_no_answer_final_recall_v2,
        dev_no_answer_final_recall_v2_ci,
        dev_answerable_final_coverage_v2,
        dev_conditional_argmax_accuracy_v2,
        dev_conditional_argmax_accuracy_v2_ci,
        dev_answered_conditional_accuracy_v2,
        dev_answerability_brier_v2: brier_est,
        dev_answerability_log_loss_v2: nll_est,
        dev_answerability_ece_10_bins_v2: ece_est,
        dev_conditional_nll_v2: cond_nll_est,
        dev_conditional_brier_v2: cond_brier_est,
        causal: causal_metrics,
        nuisance: nuisance_metrics,
        families,
        bootstrap_seed: CONTRACT_SEED,
        bootstrap_replicates: CONTRACT_REPLICATES,
        bootstrap_confidence: CONTRACT_CONFIDENCE,
        bootstrap_method: CONTRACT_METHOD.into(),
    })
}

fn pair_class_metrics(
    eligible: &BTreeMap<String, Vec<ChoiceFinalCase>>,
    ineligible: &BTreeMap<String, String>,
    suffix: &str,
) -> Result<PairClassMetrics, EvalError> {
    let ineligible_filtered: BTreeMap<String, String> = ineligible
        .iter()
        .filter(|(k, _)| k.ends_with(suffix))
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    if eligible.is_empty() {
        return Ok(PairClassMetrics {
            eligible_pairs: 0,
            eligible_groups: 0,
            ineligible_pairs: ineligible_filtered,
            both_final_correct: MetricEstimate::insufficient(0, 0),
            both_final_correct_ci: None,
            prediction_consistency: MetricEstimate::insufficient(0, 0),
            correctness_preserving_agreement: MetricEstimate::insufficient(0, 0),
            raw_argmax_agreement: MetricEstimate::insufficient(0, 0),
        });
    }
    let groups: BTreeSet<&str> = eligible
        .values()
        .map(|m| m[0].leakage_group.as_str())
        .collect();
    let both_correct = eligible
        .values()
        .filter(|m| m.iter().all(|c| c.is_final_correct()))
        .count();
    let consistent = eligible
        .values()
        .filter(|m| m[0].predicted == m[1].predicted)
        .count();
    // Correctness-preserving agreement: identical predictions AND both correct.
    // Double abstention on answerable pairs is consistent but not
    // correctness-preserving; it is counted in `consistent` but not here.
    let preserving = eligible
        .values()
        .filter(|m| m[0].predicted == m[1].predicted && m.iter().all(|c| c.is_final_correct()))
        .count();
    let raw_agree = eligible
        .values()
        .filter(|m| {
            // Raw agreement uses conditional argmax identities; requires both
            // answerable (argmax undefined for None rows in the conditional
            // sense, so pairs with any None are excluded from raw agreement
            // and counted as insufficient for that sub-metric only).
            if m.iter().any(|c| c.target.is_none()) {
                return false;
            }
            m[0].conditional_argmax() == m[1].conditional_argmax()
        })
        .count();
    // For raw agreement denominator, use only pairs where both members are
    // answerable; if none, report insufficient for that sub-metric.
    let answerable_pairs = eligible
        .values()
        .filter(|m| m.iter().all(|c| c.target.is_some()))
        .count();
    let both_est = mean_or_insufficient(both_correct, eligible.len(), groups.len());
    let consist_est = mean_or_insufficient(consistent, eligible.len(), groups.len());
    let preserving_est = mean_or_insufficient(preserving, eligible.len(), groups.len());
    let raw_est = if answerable_pairs == 0 {
        MetricEstimate::insufficient(0, 0)
    } else {
        // Count raw agreement among answerable pairs only.
        let raw_among_answerable = eligible
            .values()
            .filter(|m| m.iter().all(|c| c.target.is_some()))
            .filter(|m| m[0].conditional_argmax() == m[1].conditional_argmax())
            .count();
        mean_or_insufficient(raw_among_answerable, answerable_pairs, groups.len())
    };
    let _ = raw_agree;
    // CI over pair-level both-correct (grouped by leakage group).
    let mut obs: Vec<(String, f64)> = eligible
        .values()
        .map(|m| {
            (
                m[0].leakage_group.clone(),
                f64::from(m.iter().all(|c| c.is_final_correct())),
            )
        })
        .collect();
    obs.sort_by(|a, b| a.0.cmp(&b.0));
    let ci = grouped_ci(
        &obs,
        CONTRACT_SEED,
        CONTRACT_REPLICATES,
        CONTRACT_CONFIDENCE,
    )?;
    Ok(PairClassMetrics {
        eligible_pairs: eligible.len(),
        eligible_groups: groups.len(),
        ineligible_pairs: ineligible_filtered,
        both_final_correct: both_est,
        both_final_correct_ci: ci,
        prediction_consistency: consist_est,
        correctness_preserving_agreement: preserving_est,
        raw_argmax_agreement: raw_est,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[allow(clippy::too_many_arguments)]
    fn case(
        id: &str,
        group: &str,
        target: Option<&str>,
        predicted: Option<&str>,
        options: &[&str],
        probs: &[f64],
        answerability: f64,
        origin: Option<NoAnswerOrigin>,
    ) -> ChoiceFinalCase {
        ChoiceFinalCase {
            case_id: id.into(),
            leakage_group: group.into(),
            family: "m015-test-v1".into(),
            split: "dev".into(),
            pair_id: None,
            pair_type: None,
            target: target.map(str::to_string),
            option_ids: options.iter().map(|s| s.to_string()).collect(),
            predicted: predicted.map(str::to_string),
            conditional_probs: probs.to_vec(),
            conditional_logits: None,
            answerability_p: answerability,
            no_answer_origin: origin,
            context_digest: String::new(),
            semantics_digest: String::new(),
            rule_digest: String::new(),
        }
    }

    #[test]
    fn final_action_counts_false_abstention_and_wrong_id_as_errors() {
        let options = ["a", "b"];
        let rows = vec![
            // Correct answered.
            case(
                "c1",
                "g1",
                Some("a"),
                Some("a"),
                &options,
                &[0.8, 0.2],
                0.9,
                None,
            ),
            // False abstention: raw argmax is correct but final abstains.
            case(
                "c2",
                "g2",
                Some("b"),
                None,
                &options,
                &[0.2, 0.8],
                0.1,
                None,
            ),
            // Wrong choice.
            case(
                "c3",
                "g3",
                Some("a"),
                Some("b"),
                &options,
                &[0.2, 0.8],
                0.9,
                None,
            ),
            // Correct abstention.
            case(
                "c4",
                "g4",
                None,
                None,
                &options,
                &[0.5, 0.5],
                0.1,
                Some(NoAnswerOrigin::UnavailableContext),
            ),
            // False positive.
            case(
                "c5",
                "g5",
                None,
                Some("a"),
                &options,
                &[0.8, 0.2],
                0.9,
                Some(NoAnswerOrigin::ZeroSatisfyingCandidates),
            ),
        ];
        let report = evaluate_choice_final_v2(&rows).unwrap();
        // 2/5 final correct (c1, c4).
        assert_eq!(report.dev_final_action_accuracy_v2.value, Some(0.4));
        // 1/3 answerable final correct.
        assert_eq!(
            report.dev_answerable_final_accuracy_v2.value,
            Some(1.0 / 3.0)
        );
        // 1/3 false abstention.
        assert_eq!(report.dev_false_abstention_rate_v2.value, Some(1.0 / 3.0));
        // 1/2 no-answer recall.
        assert_eq!(report.dev_no_answer_final_recall_v2.value, Some(0.5));
        // 2/3 coverage (c1, c3 answered).
        assert_eq!(
            report.dev_answerable_final_coverage_v2.value,
            Some(2.0 / 3.0)
        );
        // Raw argmax: c1 correct, c2 correct (raw), c3 wrong -> 2/3.
        assert_eq!(
            report.dev_conditional_argmax_accuracy_v2.value,
            Some(2.0 / 3.0)
        );
        // Answered-only: c1 correct, c3 wrong -> 1/2.
        assert_eq!(report.dev_answered_conditional_accuracy_v2.value, Some(0.5));
    }

    #[test]
    fn mixed_raw_metric_false_positive_is_rejected_by_final_pair() {
        // Answerable member: raw argmax correct but final abstains (false
        // abstention). No-answer member: correctly abstained. Historical mixed
        // raw/final scoring would report success; v2 must reject.
        let options = ["a", "b"];
        let before = ChoiceFinalCase {
            case_id: "g1-before".into(),
            leakage_group: "g1".into(),
            family: "m015-test-v1".into(),
            split: "dev".into(),
            pair_id: Some("g1-causal".into()),
            pair_type: Some("causal_flip".into()),
            target: Some("a".into()),
            option_ids: vec!["a".into(), "b".into()],
            predicted: None,
            conditional_probs: vec![0.9, 0.1],
            conditional_logits: None,
            answerability_p: 0.1,
            no_answer_origin: None,
            context_digest: "ctx-same".into(),
            semantics_digest: "sem-before".into(),
            rule_digest: "rule".into(),
        };
        let after = ChoiceFinalCase {
            case_id: "g1-after".into(),
            leakage_group: "g1".into(),
            family: "m015-test-v1".into(),
            split: "dev".into(),
            pair_id: Some("g1-causal".into()),
            pair_type: Some("causal_flip".into()),
            target: None,
            option_ids: vec!["a".into(), "b".into()],
            predicted: None,
            conditional_probs: vec![0.5, 0.5],
            conditional_logits: None,
            answerability_p: 0.1,
            no_answer_origin: Some(NoAnswerOrigin::ZeroSatisfyingCandidates),
            context_digest: "ctx-same".into(),
            semantics_digest: "sem-after".into(),
            rule_digest: "rule".into(),
        };
        // Raw argmax on before is correct; final is wrong (abstained).
        assert_eq!(before.is_conditional_argmax_correct(), Some(true));
        assert!(!before.is_final_correct());
        assert!(after.is_final_correct());
        let report = evaluate_choice_final_v2(&[before, after]).unwrap();
        assert_eq!(report.causal.eligible_pairs, 1);
        // Both-final-correct must be 0, not 1.
        assert_eq!(report.causal.both_final_correct.value, Some(0.0));
        let _ = options;
    }

    #[test]
    fn context_only_answerability_impossibility_is_tested() {
        // Same context digest implies identical answerability under the legacy
        // head. If the after row is correctly abstained, the before row with
        // the same answerability must be falsely abstained when the threshold
        // separates them.
        let before = case(
            "b",
            "g1",
            Some("a"),
            None,
            &["a", "b"],
            &[0.9, 0.1],
            0.1,
            None,
        );
        let after = case(
            "a",
            "g1",
            None,
            None,
            &["a", "b"],
            &[0.5, 0.5],
            0.1,
            Some(NoAnswerOrigin::ZeroSatisfyingCandidates),
        );
        // Identical answerability.
        assert_eq!(before.answerability_p, after.answerability_p);
        // After correct, before false abstention: pair cannot be both correct.
        assert!(!before.is_final_correct());
        assert!(after.is_final_correct());
        let report = evaluate_choice_final_v2(&[before, after]).unwrap();
        assert_eq!(report.dev_answerable_final_coverage_v2.value, Some(0.0));
        assert_eq!(report.dev_false_abstention_rate_v2.value, Some(1.0));
    }

    #[test]
    fn pair_matcher_fails_closed_on_malformed_pairs() {
        let good_nuisance_a = ChoiceFinalCase {
            case_id: "g1-n0".into(),
            leakage_group: "g1".into(),
            family: "m015-test-v1".into(),
            split: "dev".into(),
            pair_id: Some("g1-nuisance".into()),
            pair_type: Some("nuisance".into()),
            target: Some("a".into()),
            option_ids: vec!["a".into(), "b".into()],
            predicted: Some("a".into()),
            conditional_probs: vec![0.9, 0.1],
            conditional_logits: None,
            answerability_p: 0.9,
            no_answer_origin: None,
            context_digest: "c0".into(),
            semantics_digest: "s".into(),
            rule_digest: "r".into(),
        };
        let mut good_nuisance_b = good_nuisance_a.clone();
        good_nuisance_b.case_id = "g1-n1".into();
        good_nuisance_b.option_ids = vec!["b".into(), "a".into()];
        good_nuisance_b.conditional_probs = vec![0.1, 0.9];
        good_nuisance_b.context_digest = "c1".into();
        let (eligible, ineligible) =
            match_pairs(&[good_nuisance_a.clone(), good_nuisance_b.clone()]).unwrap();
        assert_eq!(eligible.len(), 1);
        assert!(ineligible.is_empty());

        // Unknown suffix fails closed.
        let mut bad = good_nuisance_a.clone();
        bad.pair_id = Some("g1-weird".into());
        assert!(bad.validate().is_err());

        // Three-member pair fails closed.
        let mut third = good_nuisance_a.clone();
        third.case_id = "g1-n2".into();
        let (eligible, ineligible) =
            match_pairs(&[good_nuisance_a.clone(), good_nuisance_b.clone(), third]).unwrap();
        assert!(eligible.is_empty());
        assert_eq!(ineligible.len(), 1);

        // Split-crossing fails closed.
        let mut split_bad = good_nuisance_b.clone();
        split_bad.split = "train".into();
        let (_, ineligible) = match_pairs(&[good_nuisance_a.clone(), split_bad]).unwrap();
        assert_eq!(ineligible.len(), 1);

        // Accidentally relabeled nuisance (targets differ) fails closed.
        let mut relabeled = good_nuisance_b.clone();
        relabeled.target = Some("b".into());
        let (_, ineligible) = match_pairs(&[good_nuisance_a.clone(), relabeled]).unwrap();
        assert_eq!(ineligible.len(), 1);

        // Changed-context causal fails closed.
        let causal_a = ChoiceFinalCase {
            case_id: "g2-before".into(),
            leakage_group: "g2".into(),
            family: "m015-test-v1".into(),
            split: "dev".into(),
            pair_id: Some("g2-causal".into()),
            pair_type: Some("causal_flip".into()),
            target: Some("a".into()),
            option_ids: vec!["a".into(), "b".into()],
            predicted: Some("a".into()),
            conditional_probs: vec![0.9, 0.1],
            conditional_logits: None,
            answerability_p: 0.9,
            no_answer_origin: None,
            context_digest: "ctx-a".into(),
            semantics_digest: "sem-a".into(),
            rule_digest: "r".into(),
        };
        let mut causal_b = causal_a.clone();
        causal_b.case_id = "g2-after".into();
        causal_b.target = None;
        causal_b.predicted = None;
        causal_b.no_answer_origin = Some(NoAnswerOrigin::ZeroSatisfyingCandidates);
        causal_b.context_digest = "ctx-B-DIFFERENT".into();
        causal_b.semantics_digest = "sem-b".into();
        let (_, ineligible) = match_pairs(&[causal_a.clone(), causal_b]).unwrap();
        assert_eq!(ineligible.len(), 1);

        // Mismatched options fails closed.
        let mut mismatched = good_nuisance_b.clone();
        mismatched.option_ids = vec!["a".into(), "c".into()];
        mismatched.conditional_probs = vec![0.9, 0.1];
        assert!(mismatched.validate().is_ok());
        let (_, ineligible) = match_pairs(&[good_nuisance_a.clone(), mismatched]).unwrap();
        assert_eq!(ineligible.len(), 1);

        // Missing member (single row for a pair) is ineligible.
        let (_, ineligible) = match_pairs(std::slice::from_ref(&good_nuisance_a)).unwrap();
        assert_eq!(ineligible.len(), 1);

        // Duplicate member fails closed.
        let (_, ineligible) =
            match_pairs(&[good_nuisance_a.clone(), good_nuisance_a.clone()]).unwrap();
        assert_eq!(ineligible.len(), 1);

        // Swapped ID / label leakage: target outside options fails validation.
        let mut swapped = good_nuisance_a.clone();
        swapped.target = Some("injected".into());
        assert!(swapped.validate().is_err());
    }

    #[test]
    fn nuisance_double_abstain_is_consistent_but_not_correctness_preserving() {
        // Both answerable, both abstain: consistent but both incorrect.
        let a = case(
            "n0",
            "g1",
            Some("a"),
            None,
            &["a", "b"],
            &[0.9, 0.1],
            0.1,
            None,
        );
        let b = case(
            "n1",
            "g1",
            Some("a"),
            None,
            &["a", "b"],
            &[0.9, 0.1],
            0.1,
            None,
        );
        let a = ChoiceFinalCase {
            pair_id: Some("g1-nuisance".into()),
            pair_type: Some("nuisance".into()),
            context_digest: "c0".into(),
            semantics_digest: "s".into(),
            rule_digest: "r".into(),
            ..a
        };
        let b = ChoiceFinalCase {
            pair_id: Some("g1-nuisance".into()),
            pair_type: Some("nuisance".into()),
            context_digest: "c1".into(),
            semantics_digest: "s".into(),
            rule_digest: "r".into(),
            ..b
        };
        // Need reversed order for nuisance eligibility with same ID set.
        let mut b_ordered = b.clone();
        b_ordered.option_ids = vec!["b".into(), "a".into()];
        b_ordered.conditional_probs = vec![0.1, 0.9];
        let report = evaluate_choice_final_v2(&[a, b_ordered]).unwrap();
        assert_eq!(report.nuisance.eligible_pairs, 1);
        assert_eq!(report.nuisance.prediction_consistency.value, Some(1.0));
        assert_eq!(report.nuisance.both_final_correct.value, Some(0.0));
        assert_eq!(
            report.nuisance.correctness_preserving_agreement.value,
            Some(0.0)
        );
    }

    #[test]
    fn empty_strata_are_insufficient_not_zero() {
        let report = evaluate_choice_final_v2(&[]).unwrap();
        assert_eq!(
            report.dev_final_action_accuracy_v2.status,
            SupportStatus::InsufficientSupport
        );
        assert_eq!(report.dev_final_action_accuracy_v2.value, None);
        assert_eq!(
            report.causal.both_final_correct.status,
            SupportStatus::InsufficientSupport
        );
        assert_eq!(
            report.nuisance.both_final_correct.status,
            SupportStatus::InsufficientSupport
        );
        // No-answer-only input: answerable strata insufficient.
        let only_none = case(
            "c",
            "g1",
            None,
            None,
            &["a", "b"],
            &[0.5, 0.5],
            0.1,
            Some(NoAnswerOrigin::UnavailableContext),
        );
        let report = evaluate_choice_final_v2(std::slice::from_ref(&only_none)).unwrap();
        assert_eq!(
            report.dev_answerable_final_accuracy_v2.status,
            SupportStatus::InsufficientSupport
        );
        assert_eq!(report.dev_answerable_final_accuracy_v2.value, None);
        assert_eq!(report.dev_no_answer_final_recall_v2.value, Some(1.0));
    }

    #[test]
    fn grouped_bootstrap_is_sorted_and_nondegenerate() {
        // Non-degenerate observations must yield a valid sorted interval.
        let rows = vec![
            case(
                "c1",
                "g1",
                Some("a"),
                Some("a"),
                &["a", "b"],
                &[0.9, 0.1],
                0.9,
                None,
            ),
            case(
                "c2",
                "g2",
                Some("a"),
                None,
                &["a", "b"],
                &[0.9, 0.1],
                0.1,
                None,
            ),
            case(
                "c3",
                "g3",
                Some("b"),
                Some("b"),
                &["a", "b"],
                &[0.1, 0.9],
                0.9,
                None,
            ),
            case(
                "c4",
                "g4",
                None,
                None,
                &["a", "b"],
                &[0.5, 0.5],
                0.1,
                Some(NoAnswerOrigin::UnavailableContext),
            ),
        ];
        let report = evaluate_choice_final_v2(&rows).unwrap();
        let ci = report.dev_final_action_accuracy_v2_ci.clone().unwrap();
        assert!(ci.lower <= ci.upper);
        assert_eq!(ci.groups, 4);
        assert_eq!(ci.replicates, CONTRACT_REPLICATES);
        assert_eq!(ci.seed, CONTRACT_SEED);
        assert_eq!(ci.method, CONTRACT_METHOD);
        // Deterministic: second run identical.
        let again = evaluate_choice_final_v2(&rows).unwrap();
        assert_eq!(report, again);
    }

    #[test]
    fn invalid_requests_fail_closed() {
        // 0/1 options are invalid Choice and must error, never become None.
        let mut bad = case(
            "c",
            "g1",
            None,
            None,
            &["a"],
            &[1.0],
            0.1,
            Some(NoAnswerOrigin::UnavailableContext),
        );
        bad.option_ids = vec!["only".into()];
        bad.conditional_probs = vec![1.0];
        assert!(bad.validate().is_err());
        // Target outside options fails.
        let bad2 = case(
            "c",
            "g1",
            Some("ghost"),
            Some("ghost"),
            &["a", "b"],
            &[0.5, 0.5],
            0.9,
            None,
        );
        assert!(bad2.validate().is_err());
        // Predicted outside options fails.
        let bad3 = case(
            "c",
            "g1",
            Some("a"),
            Some("ghost"),
            &["a", "b"],
            &[0.5, 0.5],
            0.9,
            None,
        );
        assert!(bad3.validate().is_err());
        // Missing origin on None fails.
        let bad4 = case("c", "g1", None, None, &["a", "b"], &[0.5, 0.5], 0.1, None);
        assert!(bad4.validate().is_err());
        // Origin on Some fails.
        let bad5 = case(
            "c",
            "g1",
            Some("a"),
            Some("a"),
            &["a", "b"],
            &[0.9, 0.1],
            0.9,
            Some(NoAnswerOrigin::UnavailableContext),
        );
        assert!(bad5.validate().is_err());
    }
}
