#!/usr/bin/env python3
"""M013b versioned pure evaluator for counterfactual sensitivity and quality gates.

Design contract (M013b work packages A and B):

* Pure and deterministic. No file, network, environment or clock access. No
  mutation of caller-supplied structures. Bootstrap randomness is derived from a
  frozen protocol seed only.
* Additive. `scripts/analyze_m013a_quality.py` and its archived outputs stay
  byte-reproducible; nothing in this module is imported by it.
* Fail closed. Malformed provenance, ambiguous option identity, non-finite
  numbers and incomplete gate sets raise `M013bInvalid` instead of coercing.

Defect A addressed here: the historical M013a analyzer derived a pair "raw
target margin" as ``raw_logits[target_index] - raw_logits[other_index]``. Because
``target_index`` moves when the label flips, an unchanged score vector such as
[2, 1] produces +1 then -1 with *zero* response to the input. This module keeps
that quantity only as an explicitly labelled `label_alignment` metric and
computes causal sensitivity from the SAME physical option identity on both sides
of a pair.

Defect B addressed here: a `positive` verdict is reachable only when every
mandatory gate passes. An empty or missing gate set can never pass through a
vacuous `all()`.

Version: m013b-evaluator-v1
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

EVALUATOR_VERSION = "m013b-evaluator-v1"

#: Numeric near-equality band. Values within this band count as unchanged.
EQUALITY_EPSILON = 1e-9

#: Frozen M013a bootstrap settings; mirrored, never redefined, by later protocols.
DEFAULT_SEED = 14014
DEFAULT_REPLICATES = 10_000
DEFAULT_CONFIDENCE = 0.95

#: Machine-readable gate states.
GATE_PASS = "pass"
GATE_FAIL = "fail"
GATE_INSUFFICIENT_SUPPORT = "insufficient_support"
GATE_INVALID = "invalid"
GATE_STATUSES = (GATE_PASS, GATE_FAIL, GATE_INSUFFICIENT_SUPPORT, GATE_INVALID)

#: Machine-readable task verdicts.
VERDICT_POSITIVE = "positive"
VERDICT_NEGATIVE = "negative"
VERDICT_INDETERMINATE = "indeterminate"
VERDICT_INVALID = "invalid"
VERDICTS = (VERDICT_POSITIVE, VERDICT_NEGATIVE, VERDICT_INDETERMINATE, VERDICT_INVALID)


class M013bInvalid(ValueError):
    """Raised when evidence, provenance or option identity cannot be trusted.

    Carries a stable machine-readable ``code`` so callers can map a rejection
    onto the ``invalid`` gate state without string matching.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _reject(code: str, detail: str) -> "M013bInvalid":
    return M013bInvalid(code, detail)


# --------------------------------------------------------------------------
# Numeric helpers
# --------------------------------------------------------------------------


def is_finite_number(value: Any) -> bool:
    """True only for finite real numbers. Booleans are rejected on purpose."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def require_finite(value: Any, code: str, what: str) -> float:
    if not is_finite_number(value):
        raise _reject(code, f"{what} is not a finite number: {value!r}")
    return float(value)


def require_probability(value: Any, code: str, what: str) -> float:
    number = require_finite(value, code, what)
    if not 0.0 <= number <= 1.0:
        raise _reject(code, f"{what} is outside [0, 1]: {number!r}")
    return number


def mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def quantile(values: Sequence[float], probability: float) -> float:
    """Return a linearly interpolated quantile, independent of input ordering.

    A sorted copy is used so callers can safely pass RNG-ordered bootstrap
    draws and their sequence is never mutated. The interpolation convention is
    the same as the frozen M013a analyzer and M013c evaluator.
    """
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
        raise _reject("empty_population", "quantile requires a non-empty numeric sequence")
    probability = require_probability(probability, "invalid_probability", "quantile probability")
    ordered = sorted(require_finite(value, "non_finite_statistic", "quantile value") for value in values)
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def group_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    statistic: Callable[[Sequence[Mapping[str, Any]]], float | None],
    *,
    seed: int = DEFAULT_SEED,
    replicates: int = DEFAULT_REPLICATES,
    confidence: float = DEFAULT_CONFIDENCE,
) -> dict[str, Any]:
    """Paired leakage-group bootstrap.

    Each independent leakage group is sampled with replacement once per
    replicate, matching the frozen M013a protocol. Returns an explicit
    ``groups`` count so denominators are never implicit.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise _reject("invalid_bootstrap_seed", "seed must be an integer")
    if isinstance(replicates, bool) or not isinstance(replicates, int) or not 1 <= replicates <= 1_000_000:
        raise _reject("invalid_bootstrap_replicates", "replicates must be an integer in [1, 1000000]")
    confidence = require_finite(confidence, "invalid_bootstrap_confidence", "confidence")
    if not 0.0 < confidence < 1.0:
        raise _reject("invalid_bootstrap_confidence", "confidence must be strictly between 0 and 1")

    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, Mapping):
            raise _reject("invalid_bootstrap_row", "each bootstrap row must be a mapping")
        key = row.get("leakage_group")
        if not isinstance(key, str) or not key:
            raise _reject("invalid_bootstrap_group", f"invalid leakage group id: {key!r}")
        groups[key].append(row)
    per_group = {}
    for key, members in groups.items():
        try:
            value = statistic(members)
        except Exception as exc:
            raise _reject("invalid_bootstrap_statistic", f"statistic failed for leakage group {key!r}: {exc}") from exc
        if value is not None:
            per_group[key] = require_finite(value, "non_finite_statistic", f"statistic for leakage group {key!r}")
    keys = sorted(per_group)
    if not keys:
        return {"groups": 0, "replicates": replicates, "confidence": confidence, "lower": None, "upper": None}
    rng = random.Random(seed)
    replicates_values = []
    for _ in range(replicates):
        replicates_values.append(
            mean([per_group[keys[rng.randrange(len(keys))]] for _ in range(len(keys))])
        )
    tail = (1.0 - confidence) / 2.0
    return {
        "groups": len(keys),
        "replicates": replicates,
        "confidence": confidence,
        "lower": quantile(replicates_values, tail),
        "upper": quantile(replicates_values, 1.0 - tail),
    }


# --------------------------------------------------------------------------
# Structural extraction from frozen dataset examples and runtime reports
# --------------------------------------------------------------------------


def _typed_features(example: Mapping[str, Any]) -> Mapping[str, Any]:
    binding = example.get("typed_rank_features")
    if not isinstance(binding, Mapping):
        raise _reject("missing_typed_features", f"example {example.get('case_id')!r} has no typed_rank_features")
    return binding


def projection_field_value(projection: Mapping[str, Any], field_id: str) -> Any:
    """Read one field value out of a typed feature projection."""
    fields = projection.get("fields")
    if not isinstance(fields, Sequence):
        raise _reject("malformed_projection", "projection has no fields list")
    seen: set[str] = set()
    for item in fields:
        if not isinstance(item, Mapping):
            raise _reject("malformed_projection", "projection field is not an object")
        identifier = item.get("id")
        if identifier in seen:
            raise _reject("duplicate_projection_field", f"duplicate field id {identifier!r}")
        seen.add(identifier)
        if identifier == field_id:
            value = item.get("value")
            if not isinstance(value, Mapping):
                raise _reject("malformed_projection", f"field {field_id!r} has no value object")
            return value.get("value")
    raise _reject("missing_projection_field", f"projection has no field {field_id!r}")


def causal_active(example: Mapping[str, Any]) -> bool:
    """The causal manipulated field. Orientations never rely on report order."""
    value = projection_field_value(_typed_features(example)["context"], "active")
    if not isinstance(value, bool):
        raise _reject("malformed_active_field", f"active is not a boolean: {value!r}")
    return value


def schema_fingerprint(example: Mapping[str, Any]) -> str:
    schema = _typed_features(example).get("schema")
    if not isinstance(schema, Mapping):
        raise _reject("missing_schema", "typed binding has no schema")
    return str(schema.get("fingerprint", "<none>"))


def option_ids(example: Mapping[str, Any]) -> list[str]:
    """Physical option identities in the order the runtime emitted scores."""
    spec = example.get("request", {}).get("spec", {})
    options = spec.get("options")
    if not isinstance(options, Sequence) or not options:
        raise _reject("missing_options", "example is not a Choice request with options")
    ids: list[str] = []
    for option in options:
        if not isinstance(option, Mapping):
            raise _reject("malformed_option", "option entry is not an object")
        identifier = option.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise _reject("malformed_option_id", f"invalid option id: {identifier!r}")
        if identifier in ids:
            raise _reject("duplicate_option_id", f"duplicate option id {identifier!r}")
        ids.append(identifier)
    return ids


def candidate_roles(example: Mapping[str, Any]) -> dict[str, str]:
    """Semantic role per physical candidate projection.

    The runtime keys candidate projections by option id, so this doubles as a
    check that the physical candidate identity mapping is consistent.
    """
    candidates = _typed_features(example).get("candidates")
    if not isinstance(candidates, Mapping) or not candidates:
        raise _reject("missing_candidates", "typed binding has no candidate projections")
    roles: dict[str, str] = {}
    for identifier, projection in candidates.items():
        roles[str(identifier)] = str(projection_field_value(projection, "task_kind"))
    return roles


def validate_option_identity(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    """Return the shared option identity set, rejecting ambiguity.

    Both sides of a counterfactual pair must expose the same option ids in the
    same physical order, and each option id must map to exactly one candidate
    projection with a stable semantic role.
    """
    before_ids = option_ids(before)
    after_ids = option_ids(after)
    if set(before_ids) != set(after_ids):
        raise _reject(
            "option_identity_mismatch",
            f"pair option ids differ: {sorted(before_ids)} vs {sorted(after_ids)}",
        )
    if before_ids != after_ids:
        raise _reject(
            "option_order_mismatch",
            f"pair option order differs: {before_ids} vs {after_ids}",
        )
    before_roles = candidate_roles(before)
    after_roles = candidate_roles(after)
    if set(before_roles) != set(before_ids):
        raise _reject(
            "candidate_identity_missing",
            f"candidate projections {sorted(before_roles)} do not cover options {sorted(before_ids)}",
        )
    if before_roles != after_roles:
        raise _reject(
            "inconsistent_projection_role",
            f"candidate roles changed across pair: {before_roles} vs {after_roles}",
        )
    if len(set(before_roles.values())) != len(before_roles):
        raise _reject("inconsistent_projection_role", "two options share one candidate role")
    return before_ids


# --------------------------------------------------------------------------
# Work package A — causal, target-independent counterfactual sensitivity
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CounterfactualPair:
    """One manipulated pair: two runtime outcomes plus their frozen examples."""

    pair_id: str
    leakage_group: str
    before_example: Mapping[str, Any]
    after_example: Mapping[str, Any]
    before_outcome: Mapping[str, Any]
    after_outcome: Mapping[str, Any]


def build_pairs(
    examples: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> list[CounterfactualPair]:
    """Group outcomes by `counterfactual_pair` and orient by the causal field.

    Validation is strict: unknown case ids, duplicate outcomes, cardinality other
    than two, mismatched leakage groups and equal causal values are all rejected
    rather than skipped.
    """
    by_case: dict[str, Mapping[str, Any]] = {}
    for example in examples:
        case_id = example.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise _reject("malformed_case_id", f"invalid case id: {case_id!r}")
        if case_id in by_case:
            raise _reject("duplicate_case_id", f"duplicate example case id {case_id!r}")
        by_case[case_id] = example

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    seen_cases: set[str] = set()
    for outcome in outcomes:
        case_id = outcome.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise _reject("malformed_case_id", f"invalid outcome case id: {case_id!r}")
        if case_id in seen_cases:
            raise _reject("duplicate_outcome_case", f"duplicate outcome for case {case_id!r}")
        seen_cases.add(case_id)
        if case_id not in by_case:
            raise _reject("unknown_case_id", f"outcome case {case_id!r} is absent from the frozen dataset")
        grouped[str(by_case[case_id]["counterfactual_pair"])].append(outcome)

    pairs: list[CounterfactualPair] = []
    for pair_id in sorted(grouped):
        members = grouped[pair_id]
        if len(members) != 2:
            raise _reject("pair_cardinality", f"pair {pair_id!r} has {len(members)} members, expected 2")
        left, right = (by_case[str(m["case_id"])] for m in members)
        group_left = str(left["leakage_group"])
        group_right = str(right["leakage_group"])
        if group_left != group_right:
            raise _reject("pair_group_mismatch", f"pair {pair_id!r} spans leakage groups {group_left}/{group_right}")
        active_left = causal_active(left)
        active_right = causal_active(right)
        if active_left == active_right:
            raise _reject(
                "pair_not_counterfactual",
                f"pair {pair_id!r} has active={active_left} on both sides",
            )
        # Orient by the causal field, never by report order.
        if active_left:
            before_example, after_example = right, left
            before_outcome, after_outcome = members[1], members[0]
        else:
            before_example, after_example = left, right
            before_outcome, after_outcome = members[0], members[1]
        if schema_fingerprint(before_example) != schema_fingerprint(after_example):
            raise _reject("pair_schema_mismatch", f"pair {pair_id!r} spans two feature schemas")
        # Validate option identity and raw scores eagerly so a malformed pair is
        # rejected before any metric is computed from it.
        ids = validate_option_identity(before_example, after_example)
        _identity_scores(before_outcome, ids)
        _identity_scores(after_outcome, ids)
        for outcome in (before_outcome, after_outcome):
            require_probability(
                outcome.get("answerability_probability"),
                "missing_answerability",
                "answerability probability",
            )
        pairs.append(
            CounterfactualPair(
                pair_id=pair_id,
                leakage_group=group_left,
                before_example=before_example,
                after_example=after_example,
                before_outcome=before_outcome,
                after_outcome=after_outcome,
            )
        )
    if not pairs:
        raise _reject("no_pairs", "no counterfactual pairs were found")
    return pairs


def _identity_scores(
    outcome: Mapping[str, Any],
    ids: Sequence[str],
    *,
    probability_key: str = "raw_probabilities",
    logit_key: str = "raw_logits",
) -> dict[str, tuple[float, float]]:
    """Map positional runtime scores onto physical option identities."""
    probabilities = outcome.get(probability_key)
    logits = outcome.get(logit_key)
    if probabilities is None or logits is None:
        raise _reject("missing_raw_scores", f"outcome {outcome.get('case_id')!r} lacks raw probabilities or logits")
    if not isinstance(probabilities, Sequence) or not isinstance(logits, Sequence):
        raise _reject("malformed_raw_scores", "raw probabilities/logits are not sequences")
    if not probabilities:
        raise _reject("empty_probabilities", f"outcome {outcome.get('case_id')!r} has empty raw probabilities")
    if len(probabilities) != len(ids) or len(logits) != len(ids):
        raise _reject(
            "score_identity_mismatch",
            f"outcome {outcome.get('case_id')!r} has {len(probabilities)} probabilities / {len(logits)} logits "
            f"for {len(ids)} options",
        )
    total = 0.0
    for value in probabilities:
        number = require_probability(value, "non_finite_probability", "raw probability")
        total += number
    if not math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise _reject("probabilities_not_normalized", f"raw probabilities sum to {total!r}")
    scored: dict[str, tuple[float, float]] = {}
    for identifier, probability, logit in zip(ids, probabilities, logits):
        scored[identifier] = (
            require_probability(probability, "non_finite_probability", "raw probability"),
            require_finite(logit, "non_finite_logit", "raw logit"),
        )
    return scored


def argmax_identity(scored: Mapping[str, Mapping[str, float]], key: str) -> tuple[str, bool]:
    """Identity-normalized argmax with deterministic tie handling.

    Returns ``(option_id, tie_present)``. Ties resolve to the lexicographically
    smallest identity so permutation of the option list cannot change the answer.
    """
    best_id: str | None = None
    best_value = -math.inf
    tied = False
    for identifier in sorted(scored):
        value = scored[identifier][key]
        if best_id is None or value > best_value + EQUALITY_EPSILON:
            best_id, best_value, tied = identifier, value, False
        elif abs(value - best_value) <= EQUALITY_EPSILON:
            tied = True
    if best_id is None:
        raise _reject("empty_probabilities", "no scored options to compare")
    return best_id, tied


def _final_decision(outcome: Mapping[str, Any]) -> dict[str, Any]:
    abstained = bool(outcome.get("abstained", False))
    prediction = outcome.get("prediction")
    if not abstained and not isinstance(prediction, str):
        raise _reject("malformed_final_decision", f"outcome {outcome.get('case_id')!r} answered without a prediction")
    return {"abstained": abstained, "prediction": None if abstained else prediction}


def _target_correct(outcome: Mapping[str, Any], decision: Mapping[str, Any]) -> bool | None:
    target = outcome.get("target")
    if target is None:
        return None
    return (not decision["abstained"]) and decision["prediction"] == target


def evaluate_pair(pair: CounterfactualPair) -> dict[str, Any]:
    """Causal, target-independent comparison of one manipulated pair.

    The returned ``input_response`` block is computed from the same physical
    option identity on both sides, so it cannot be produced by a label flip
    alone. ``label_alignment`` retains the historical target-relative margin,
    explicitly relabelled as a non-causal measure.
    """
    if schema_fingerprint(pair.before_example) != schema_fingerprint(pair.after_example):
        raise _reject("pair_schema_mismatch", f"pair {pair.pair_id!r} spans two feature schemas")
    ids = validate_option_identity(pair.before_example, pair.after_example)
    before_scores = _identity_scores(pair.before_outcome, ids)
    after_scores = _identity_scores(pair.after_outcome, ids)

    per_option = {}
    max_abs_logit_delta = 0.0
    max_abs_probability_delta = 0.0
    for identifier in ids:
        before_probability, before_logit = before_scores[identifier]
        after_probability, after_logit = after_scores[identifier]
        delta_logit = after_logit - before_logit
        delta_probability = after_probability - before_probability
        max_abs_logit_delta = max(max_abs_logit_delta, abs(delta_logit))
        max_abs_probability_delta = max(max_abs_probability_delta, abs(delta_probability))
        per_option[identifier] = {
            "logit_before": before_logit,
            "logit_after": after_logit,
            "delta_logit": delta_logit,
            "probability_before": before_probability,
            "probability_after": after_probability,
            "delta_probability": delta_probability,
            "changed": abs(delta_logit) > EQUALITY_EPSILON,
        }

    before_argmax, before_tie = argmax_identity(
        {i: {"logit": s[1]} for i, s in before_scores.items()}, "logit"
    )
    after_argmax, after_tie = argmax_identity(
        {i: {"logit": s[1]} for i, s in after_scores.items()}, "logit"
    )

    before_decision = _final_decision(pair.before_outcome)
    after_decision = _final_decision(pair.after_outcome)
    before_correct = _target_correct(pair.before_outcome, before_decision)
    after_correct = _target_correct(pair.after_outcome, after_decision)
    answerable = before_correct is not None and after_correct is not None

    before_answerability = require_probability(
        pair.before_outcome.get("answerability_probability"),
        "missing_answerability",
        "before answerability probability",
    )
    after_answerability = require_probability(
        pair.after_outcome.get("answerability_probability"),
        "missing_answerability",
        "after answerability probability",
    )

    # Label alignment only: retained for continuity, never used as sensitivity.
    label_alignment = None
    before_target = pair.before_outcome.get("target")
    after_target = pair.after_outcome.get("target")
    for side, target in (("before", before_target), ("after", after_target)):
        if target is not None and target not in ids:
            raise _reject(
                "absent_option_identity",
                f"pair {pair.pair_id!r} {side} target {target!r} is not one of the options {ids}",
            )
    if isinstance(before_target, str) and isinstance(after_target, str):
        other_before = next(i for i in ids if i != before_target)
        other_after = next(i for i in ids if i != after_target)
        before_margin = before_scores[before_target][1] - before_scores[other_before][1]
        after_margin = after_scores[after_target][1] - after_scores[other_after][1]
        label_alignment = {
            "before_target": before_target,
            "after_target": after_target,
            "target_margin_before": before_margin,
            "target_margin_after": after_margin,
            "sign_flips": before_margin * after_margin < 0,
            "interpretation": "label_alignment_only_not_input_sensitivity",
        }

    return {
        "pair_id": pair.pair_id,
        "leakage_group": pair.leakage_group,
        "options": list(ids),
        "input_response": {
            "max_abs_logit_delta": max_abs_logit_delta,
            "max_abs_probability_delta": max_abs_probability_delta,
            "options_responded": sorted(i for i, m in per_option.items() if m["changed"]),
            "responded": max_abs_logit_delta > EQUALITY_EPSILON,
        },
        "per_option": per_option,
        "identity_normalized_argmax": {
            "before": before_argmax,
            "after": after_argmax,
            "changed": before_argmax != after_argmax,
            "tie_before": before_tie,
            "tie_after": after_tie,
        },
        "answerability": {
            "before": before_answerability,
            "after": after_answerability,
            "delta": after_answerability - before_answerability,
            "threshold_crossed": _threshold_crossed(before_answerability, after_answerability, _cutoff(pair)),
        },
        "final_decision": {
            "before": before_decision,
            "after": after_decision,
            "changed": before_decision["prediction"] != after_decision["prediction"],
            "abstention_transition": _abstention_transition(before_decision, after_decision),
            "threshold_only_change": _threshold_only_change(
                before_scores, after_scores, before_decision, after_decision, before_argmax, after_argmax
            ),
        },
        "target_correctness": {
            "answerable": answerable,
            "before": before_correct,
            "after": after_correct,
            "both_correct": bool(answerable and before_correct and after_correct),
            "note": "excluded from answerable denominators when the pair has no target",
        },
        "label_alignment": label_alignment,
    }


def _cutoff(pair: CounterfactualPair) -> float | None:
    for outcome in (pair.before_outcome, pair.after_outcome):
        value = outcome.get("answerability_cutoff")
        if is_finite_number(value):
            return float(value)
    return None


def _threshold_crossed(before: float, after: float, cutoff: float | None) -> bool | None:
    if cutoff is None:
        return None
    return (before >= cutoff) != (after >= cutoff)


def _abstention_transition(before: Mapping[str, Any], after: Mapping[str, Any]) -> str:
    left = "abstain" if before["abstained"] else "answer"
    right = "abstain" if after["abstained"] else "answer"
    return f"{left}->{right}"


def _threshold_only_change(
    before_scores: Mapping[str, tuple[float, float]],
    after_scores: Mapping[str, tuple[float, float]],
    before_decision: Mapping[str, Any],
    after_decision: Mapping[str, Any],
    before_argmax: str,
    after_argmax: str,
) -> bool:
    """True when only the answerability cutoff, not the option scores, changed.

    Keeps cutoff-driven abstention separate from genuine raw option movement.
    """
    scores_unchanged = all(
        abs(after_scores[i][1] - before_scores[i][1]) <= EQUALITY_EPSILON for i in before_scores
    )
    if not scores_unchanged:
        return False
    return before_decision["prediction"] != after_decision["prediction"] or before_argmax != after_argmax


def summarize_pairs(metrics: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate pair metrics with explicit, correct denominators."""
    total = len(metrics)
    if total == 0:
        raise _reject("no_pairs", "cannot summarize an empty pair set")

    alignment = [m for m in metrics if m["label_alignment"] is not None]
    answerable = [m for m in metrics if m["target_correctness"]["answerable"]]

    both_correct_ci = group_bootstrap(
        answerable,
        lambda members: mean([float(m["target_correctness"]["both_correct"]) for m in members]),
    )

    return {
        "pairs": total,
        "answerable_pairs": len(answerable),
        "unanswerable_pairs": total - len(answerable),
        "input_response": {
            "pairs_with_any_option_logit_response": sum(1 for m in metrics if m["input_response"]["responded"]),
            "response_rate": mean([float(m["input_response"]["responded"]) for m in metrics]),
            "mean_max_abs_logit_delta": mean([m["input_response"]["max_abs_logit_delta"] for m in metrics]),
            "mean_max_abs_probability_delta": mean([m["input_response"]["max_abs_probability_delta"] for m in metrics]),
        },
        "identity_normalized_argmax_change": {
            "rate": mean([float(m["identity_normalized_argmax"]["changed"]) for m in metrics]),
            "tie_rate": mean(
                [
                    float(m["identity_normalized_argmax"]["tie_before"] or m["identity_normalized_argmax"]["tie_after"])
                    for m in metrics
                ]
            ),
        },
        "abstention_transitions": {
            key: sum(1 for m in metrics if m["final_decision"]["abstention_transition"] == key)
            for key in sorted({m["final_decision"]["abstention_transition"] for m in metrics})
        },
        "final_decision_change_rate": mean([float(m["final_decision"]["changed"]) for m in metrics]),
        "threshold_only_change_rate": mean([float(m["final_decision"]["threshold_only_change"]) for m in metrics]),
        "answerability": {
            "mean_delta": mean([m["answerability"]["delta"] for m in metrics]),
            "crossed_rate": _optional_rate([m["answerability"]["threshold_crossed"] for m in metrics]),
        },
        "target_correctness": {
            "denominator": len(answerable),
            "before_rate": mean([float(m["target_correctness"]["before"]) for m in answerable]),
            "after_rate": mean([float(m["target_correctness"]["after"]) for m in answerable]),
            "both_correct_rate": mean([float(m["target_correctness"]["both_correct"]) for m in answerable]),
            "both_correct_ci": both_correct_ci,
        },
        "label_alignment": {
            "pairs": len(alignment),
            "sign_flip_rate": _optional_rate([m["label_alignment"]["sign_flips"] for m in alignment]),
            "interpretation": "label_alignment_only_not_input_sensitivity",
        },
    }


def _optional_rate(values: Iterable[bool | None]) -> float | None:
    observed = [float(v) for v in values if v is not None]
    return mean(observed) if observed else None


# --------------------------------------------------------------------------
# Work package B — executable, fail-closed preregistered quality gates
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Gate:
    """One machine-readable preregistered gate outcome."""

    name: str
    status: str
    mandatory: bool
    critical: bool = False
    evidence_count: int | None = None
    observed: float | None = None
    threshold: float | None = None
    comparator: str | None = None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "mandatory": self.mandatory,
            "critical": self.critical,
            "evidence_count": self.evidence_count,
            "observed": self.observed,
            "threshold": self.threshold,
            "comparator": self.comparator,
            "reason": self.reason,
        }


def _check_gate_status(status: str) -> str:
    if status not in GATE_STATUSES:
        raise _reject("unknown_gate_status", f"{status!r} is not a valid gate status")
    return status


def support_gate(
    name: str,
    *,
    observed: int,
    required: int,
    mandatory: bool = True,
) -> Gate:
    """Independent-unit support gate, counted in the eligible population."""
    if not isinstance(observed, int) or isinstance(observed, bool) or observed < 0:
        raise _reject("malformed_support_count", f"{name} observed support is not a count: {observed!r}")
    if not isinstance(required, int) or required <= 0:
        raise _reject("malformed_support_threshold", f"{name} required support is not positive: {required!r}")
    status = GATE_PASS if observed >= required else GATE_INSUFFICIENT_SUPPORT
    return Gate(
        name=name,
        status=status,
        mandatory=mandatory,
        critical=False,
        evidence_count=observed,
        observed=float(observed),
        threshold=float(required),
        comparator=">=",
        reason=f"{observed} eligible independent units, preregistered minimum {required}",
    )


def threshold_gate(
    name: str,
    *,
    observed: float | None,
    threshold: float | None,
    comparator: str,
    evidence_count: int | None = None,
    mandatory: bool = True,
    critical: bool = False,
    description: str = "",
) -> Gate:
    """Numeric success/failure gate that refuses undeclared thresholds.

    A missing or undeclared threshold can never yield ``pass``: without a
    preregistered quantitative criterion the honest state is ``insufficient_support``.
    """
    if threshold is None:
        return Gate(
            name=name,
            status=GATE_INSUFFICIENT_SUPPORT,
            mandatory=mandatory,
            critical=critical,
            evidence_count=evidence_count,
            observed=observed,
            threshold=None,
            comparator=comparator,
            reason=(
                f"{description or name} has no preregistered numeric threshold; positive eligibility "
                "cannot be established retrospectively"
            ),
        )
    if observed is None:
        return Gate(
            name=name,
            status=GATE_INSUFFICIENT_SUPPORT,
            mandatory=mandatory,
            critical=critical,
            evidence_count=evidence_count,
            observed=None,
            threshold=float(threshold),
            comparator=comparator,
            reason=f"{description or name} could not be estimated from the supplied evidence",
        )
    observed = require_finite(observed, "non_finite_gate_observation", f"{name} observed value")
    met = {
        ">": observed > threshold,
        ">=": observed >= threshold,
        "<": observed < threshold,
        "<=": observed <= threshold,
        "==": observed == threshold,
    }.get(comparator)
    if met is None:
        raise _reject("unknown_comparator", f"{comparator!r} is not a supported comparator")
    return Gate(
        name=name,
        status=GATE_PASS if met else GATE_FAIL,
        mandatory=mandatory,
        critical=critical,
        evidence_count=evidence_count,
        observed=observed,
        threshold=float(threshold),
        comparator=comparator,
        reason=f"observed {observed!r} {comparator} preregistered {threshold!r}"
        + (f" ({description})" if description else ""),
    )


def invalid_gate(name: str, reason: str, *, mandatory: bool = True) -> Gate:
    return Gate(name=name, status=GATE_INVALID, mandatory=mandatory, critical=False, reason=reason)


@dataclass(frozen=True)
class GateEvaluation:
    verdict: str
    reason: str
    gates: list[Gate] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "gates": [g.as_dict() for g in self.gates],
        }


def evaluate_gates(gates: Sequence[Gate], *, task: str) -> GateEvaluation:
    """Resolve a gate set into a task verdict, failing closed.

    Priority, highest first:

    1. ``invalid``           — corrupt inputs, integrity or provenance; or an
                               empty/missing gate set, which can never pass.
    2. ``negative``          — a *supported*, preregistered critical regression.
    3. ``indeterminate``     — insufficient support, an unestimable statistic,
                               an undeclared positive threshold, or any other
                               mandatory gate that is not a ``pass``.
    4. ``positive``          — only when every mandatory gate passes.

    Any non-``pass`` mandatory gate blocks promotion; none of them can be
    silently ignored and no ``all()`` runs over an empty sequence.
    """
    if task not in ("choice", "binary"):
        raise _reject("unknown_task", f"unknown task {task!r}")
    materialised = list(gates)
    if not materialised:
        raise _reject(
            "empty_gate_set",
            "an empty gate set must never pass; no preregistered gate evidence was supplied",
        )
    for gate in materialised:
        _check_gate_status(gate.status)
    for gate in materialised:
        if gate.status == GATE_INVALID:
            return GateEvaluation(
                verdict=VERDICT_INVALID,
                reason=f"{task}: gate {gate.name!r} is invalid: {gate.reason}",
                gates=materialised,
            )

    for gate in materialised:
        if gate.critical and gate.status == GATE_FAIL and _supported(gate):
            return GateEvaluation(
                verdict=VERDICT_NEGATIVE,
                reason=f"{task}: critical gate {gate.name!r} failed: {gate.reason}",
                gates=materialised,
            )

    blockers = [g for g in materialised if g.mandatory and g.status != GATE_PASS]
    if blockers:
        return GateEvaluation(
            verdict=VERDICT_INDETERMINATE,
            reason=(
                f"{task}: {len(blockers)} mandatory gate(s) did not pass; "
                f"first is {blockers[0].name!r} ({blockers[0].status}): {blockers[0].reason}"
            ),
            gates=materialised,
        )

    return GateEvaluation(
        verdict=VERDICT_POSITIVE,
        reason=f"{task}: all {len(materialised)} gates passed",
        gates=materialised,
    )


def _supported(gate: Gate) -> bool:
    """A failing gate counts against a task only when it had enough support."""
    return gate.evidence_count is not None and gate.evidence_count > 0
