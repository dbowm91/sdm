#!/usr/bin/env python3
"""Adversarial tests for the M013b evaluator: counterfactual sensitivity and gates.

These tests are constructed fixtures only. They fit nothing, read no held-out
report and assert the two properties the M013b plan requires:

* target-independent fixed-option sensitivity, proven against swapped labels and
  option permutations;
* a `positive` verdict that is unreachable while any mandatory gate fails or is
  underpowered.

Run with:
    python3 -m unittest discover -s scripts -p 'test_m013b_*.py'
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m013b_evaluator import (  # noqa: E402
    EQUALITY_EPSILON,
    EVALUATOR_VERSION,
    GATE_FAIL,
    GATE_INSUFFICIENT_SUPPORT,
    GATE_INVALID,
    GATE_PASS,
    VERDICT_INDETERMINATE,
    VERDICT_INVALID,
    VERDICT_NEGATIVE,
    VERDICT_POSITIVE,
    CounterfactualPair,
    Gate,
    M013bInvalid,
    argmax_identity,
    build_pairs,
    evaluate_gates,
    evaluate_pair,
    invalid_gate,
    summarize_pairs,
    support_gate,
    threshold_gate,
)

PROTOCOL_PATH = Path(__file__).resolve().parent / "m013b_protocol_v1.json"


# --------------------------------------------------------------------------
# Constructed fixtures
# --------------------------------------------------------------------------


def _schema():
    return {
        "version": 2,
        "fingerprint": "sha256:constructed",
        "fields": [
            {"id": "active", "value_type": "boolean", "required": True, "categories": []},
            {"id": "available", "value_type": "boolean", "required": True, "categories": []},
            {"id": "load", "value_type": "number", "required": True, "categories": []},
            {"id": "note", "value_type": "text", "required": True, "categories": []},
            {"id": "task_kind", "value_type": "category", "required": True, "categories": ["no", "yes"]},
        ],
    }


def _projection(task_kind: str, active: bool, load: float = 5.0):
    return {
        "schema": _schema(),
        "schema_sha256": "sha256:constructed",
        "fields": [
            {"id": "active", "value_type": "boolean", "required": True, "value": {"type": "boolean", "value": active}},
            {
                "id": "available",
                "value_type": "boolean",
                "required": True,
                "value": {"type": "boolean", "value": True},
            },
            {"id": "load", "value_type": "number", "required": True, "value": {"type": "number", "value": load}},
            {
                "id": "note",
                "value_type": "text",
                "required": True,
                "value": {"type": "text", "value": "routine service record 3"},
            },
            {
                "id": "task_kind",
                "value_type": "category",
                "required": True,
                "value": {"type": "category", "value": task_kind},
            },
        ],
    }


def _example(case_id: str, group: str, active: bool, yes_id: str, no_id: str, reverse: bool = False):
    options = [{"id": yes_id, "label": "Yes"}, {"id": no_id, "label": "No"}]
    if reverse:
        options = list(reversed(options))
    return {
        "case_id": case_id,
        "leakage_group": group,
        "counterfactual_pair": f"pair-{group}",
        "family": "constructed",
        "request": {"request_id": case_id + "-request", "spec": {"kind": "choice", "options": options}},
        "typed_rank_features": {
            "schema": _schema(),
            "context": _projection("choice", active),
            "candidates": {
                yes_id: _projection("yes", active),
                no_id: _projection("no", active),
            },
        },
        "label": {"kind": "choice", "value": None},
    }


def _outcome(case_id, group, target, logits, *, prediction=None, abstained=False, answerability=0.9):
    probabilities = []
    total = 0.0
    for value in logits:
        value = max(float(value), -700.0)
        probability = 1.0 / (1.0 + pow(2.718281828459045, -value))
        probabilities.append(probability)
        total += probability
    probabilities = [p / total for p in probabilities]
    if prediction is None and not abstained:
        # Mirror the runtime's raw argmax tie-break over physical positions.
        prediction = "yes" if probabilities[0] >= probabilities[1] else "no"
    return {
        "case_id": case_id,
        "leakage_group": group,
        "target": target,
        "prediction": prediction,
        "score": None,
        "raw_probabilities": probabilities,
        "raw_logits": [float(v) for v in logits],
        "answerability_probability": answerability,
        "abstained": abstained,
    }


def _pair_group(group: str = "g0", yes_id: str = "yes", no_id: str = "no"):
    """A single two-row counterfactual pair with flipped `active`."""
    before = _example(f"{group}-0", group, False, yes_id, no_id)
    after = _example(f"{group}-1", group, True, yes_id, no_id)
    return before, after


# --------------------------------------------------------------------------
# Work package A — causal, target-independent sensitivity
# --------------------------------------------------------------------------


class FixedOptionSensitivityTests(unittest.TestCase):
    def test_unchanged_logits_with_swapped_target_shows_no_input_response(self):
        """The historical false proof: identical scores, flipped label.

        A fixed score vector [2, 1] must report ZERO input response even though
        the label-relative margin appears to change sign.
        """
        before, after = _pair_group()
        before_outcome = _outcome("g0-0", "g0", target="no", logits=[2.0, 1.0], prediction="no")
        after_outcome = _outcome("g0-1", "g0", target="yes", logits=[2.0, 1.0], prediction="no")

        metric = evaluate_pair(
            CounterfactualPair("pair-g0", "g0", before, after, before_outcome, after_outcome)
        )

        self.assertFalse(metric["input_response"]["responded"])
        self.assertEqual(metric["input_response"]["options_responded"], [])
        self.assertEqual(metric["input_response"]["max_abs_logit_delta"], 0.0)
        self.assertFalse(metric["identity_normalized_argmax"]["changed"])
        # ...while the misleading label-alignment quantity does flip sign.
        self.assertTrue(metric["label_alignment"]["sign_flips"])
        self.assertEqual(metric["label_alignment"]["interpretation"], "label_alignment_only_not_input_sensitivity")

    def test_true_logit_response_is_detected(self):
        before, after = _pair_group()
        before_outcome = _outcome("g0-0", "g0", target="no", logits=[2.0, 1.0], prediction="no")
        after_outcome = _outcome("g0-1", "g0", target="yes", logits=[1.0, 2.0], prediction="yes")

        metric = evaluate_pair(
            CounterfactualPair("pair-g0", "g0", before, after, before_outcome, after_outcome)
        )

        self.assertTrue(metric["input_response"]["responded"])
        self.assertEqual(sorted(metric["input_response"]["options_responded"]), ["no", "yes"])
        self.assertTrue(metric["identity_normalized_argmax"]["changed"])
        self.assertEqual(metric["identity_normalized_argmax"]["before"], "yes")
        self.assertEqual(metric["identity_normalized_argmax"]["after"], "no")
        self.assertLess(metric["per_option"]["yes"]["delta_logit"], 0.0)
        self.assertGreater(metric["per_option"]["no"]["delta_logit"], 0.0)

    def test_option_list_permutation_yields_identical_identity_normalized_comparison(self):
        """Relabeling physical option identities must not change any comparison.

        Same identities with the same semantic roles; only the physical order of
        the emitted option list and the positional score arrays change.
        """
        before, after = _pair_group(yes_id="alpha", no_id="beta")
        before_outcome = _outcome("g0-0", "g0", target="beta", logits=[2.0, 1.0], prediction="alpha")
        after_outcome = _outcome("g0-1", "g0", target="alpha", logits=[1.0, 2.0], prediction="beta")
        base = evaluate_pair(
            CounterfactualPair("pair-g0", "g0", before, after, before_outcome, after_outcome)
        )

        # Identical causal world with the option list physically reversed:
        # positions become [beta, alpha], so scores move with their identity.
        p_before = _example("g0-0", "g0", False, "alpha", "beta", reverse=True)
        p_after = _example("g0-1", "g0", True, "alpha", "beta", reverse=True)
        p_before_outcome = _outcome("g0-0", "g0", target="beta", logits=[1.0, 2.0], prediction="alpha")
        p_after_outcome = _outcome("g0-1", "g0", target="alpha", logits=[2.0, 1.0], prediction="beta")
        permuted = evaluate_pair(
            CounterfactualPair("pair-g0", "g0", p_before, p_after, p_before_outcome, p_after_outcome)
        )

        # The physical order differs; the identity set does not.
        self.assertEqual(base["options"], ["alpha", "beta"])
        self.assertEqual(permuted["options"], ["beta", "alpha"])
        self.assertEqual(sorted(base["options"]), sorted(permuted["options"]))
        self.assertEqual(
            base["input_response"]["max_abs_logit_delta"], permuted["input_response"]["max_abs_logit_delta"]
        )
        self.assertEqual(base["input_response"]["responded"], permuted["input_response"]["responded"])
        self.assertEqual(
            base["identity_normalized_argmax"]["before"], permuted["identity_normalized_argmax"]["before"]
        )
        self.assertEqual(
            base["identity_normalized_argmax"]["after"], permuted["identity_normalized_argmax"]["after"]
        )
        self.assertEqual(
            base["identity_normalized_argmax"]["changed"], permuted["identity_normalized_argmax"]["changed"]
        )
        self.assertEqual(
            base["target_correctness"]["both_correct"], permuted["target_correctness"]["both_correct"]
        )
        self.assertEqual(sorted(base["per_option"]), sorted(permuted["per_option"]))
        for identity in base["per_option"]:
            self.assertAlmostEqual(
                base["per_option"][identity]["delta_logit"],
                permuted["per_option"][identity]["delta_logit"],
                places=12,
            )
            self.assertAlmostEqual(
                base["per_option"][identity]["probability_after"],
                permuted["per_option"][identity]["probability_after"],
                places=12,
            )

    def test_argmax_is_identity_normalized_not_positional(self):
        scored = {"yes": {"logit": 0.5}, "no": {"logit": 2.0}}
        identity, tie = argmax_identity(scored, "logit")
        self.assertEqual(identity, "no")
        self.assertFalse(tie)
        # Positional argmax of [0.5, 2.0] is index 1 == "no" only by accident of
        # ordering; the evaluator must key off identities, not positions.
        self.assertEqual(argmax_identity({"no": {"logit": 0.5}, "yes": {"logit": 2.0}}, "logit")[0], "yes")

    def test_threshold_only_abstention_change_is_separated_from_raw_option_change(self):
        before, after = _pair_group()
        before_outcome = _outcome("g0-0", "g0", target="yes", logits=[2.0, 1.0], prediction="yes", answerability=0.9)
        # Only the answerability cutoff moves; raw option scores are identical.
        after_outcome = _outcome(
            "g0-1", "g0", target="yes", logits=[2.0, 1.0], prediction=None, abstained=True, answerability=0.1
        )
        after_outcome["answerability_cutoff"] = 0.5
        before_outcome["answerability_cutoff"] = 0.5

        metric = evaluate_pair(
            CounterfactualPair("pair-g0", "g0", before, after, before_outcome, after_outcome)
        )

        self.assertFalse(metric["input_response"]["responded"])
        self.assertTrue(metric["final_decision"]["changed"])
        self.assertTrue(metric["final_decision"]["threshold_only_change"])
        self.assertEqual(metric["final_decision"]["abstention_transition"], "answer->abstain")
        self.assertTrue(metric["answerability"]["threshold_crossed"])

    def test_unanswerable_pair_is_excluded_from_answerable_denominator(self):
        before, after = _pair_group()
        before_outcome = _outcome("g0-0", "g0", target=None, logits=[2.0, 1.0], prediction=None, abstained=True)
        after_outcome = _outcome("g0-1", "g0", target=None, logits=[1.0, 2.0], prediction=None, abstained=True)

        metric = evaluate_pair(
            CounterfactualPair("pair-g0", "g0", before, after, before_outcome, after_outcome)
        )

        self.assertFalse(metric["target_correctness"]["answerable"])
        self.assertFalse(metric["target_correctness"]["both_correct"])
        self.assertIsNone(metric["label_alignment"])

    def test_both_correct_is_independent_of_label_alignment(self):
        """A genuinely responsive model and a frozen one are told apart correctly.

        Note the structural consequence: if both final decisions are correct then
        the target-relative margin is positive on both sides, so it cannot flip
        sign. A label-alignment sign flip is therefore evidence that the model did
        NOT follow the label, never evidence of counterfactual success.
        """
        before, after = _pair_group()
        good = evaluate_pair(
            CounterfactualPair(
                "pair-g0",
                "g0",
                before,
                after,
                _outcome("g0-0", "g0", target="no", logits=[1.0, 2.0], prediction="no"),
                _outcome("g0-1", "g0", target="yes", logits=[2.0, 1.0], prediction="yes"),
            )
        )
        frozen = evaluate_pair(
            CounterfactualPair(
                "pair-g0",
                "g0",
                before,
                after,
                _outcome("g0-0", "g0", target="no", logits=[2.0, 1.0], prediction="yes"),
                _outcome("g0-1", "g0", target="yes", logits=[2.0, 1.0], prediction="yes"),
            )
        )
        self.assertTrue(good["target_correctness"]["both_correct"])
        self.assertTrue(good["input_response"]["responded"])
        self.assertFalse(good["label_alignment"]["sign_flips"])

        self.assertFalse(frozen["target_correctness"]["both_correct"])
        self.assertFalse(frozen["input_response"]["responded"])
        self.assertTrue(frozen["label_alignment"]["sign_flips"])

    def test_ties_are_deterministic_and_flagged(self):
        before, after = _pair_group()
        metric = evaluate_pair(
            CounterfactualPair(
                "pair-g0",
                "g0",
                before,
                after,
                _outcome("g0-0", "g0", target="yes", logits=[1.0, 1.0], prediction="yes"),
                _outcome("g0-1", "g0", target="yes", logits=[1.0, 1.0], prediction="yes"),
            )
        )
        self.assertTrue(metric["identity_normalized_argmax"]["tie_before"])
        self.assertTrue(metric["identity_normalized_argmax"]["tie_after"])
        # Tie resolves deterministically to the lexicographically smallest id.
        self.assertEqual(metric["identity_normalized_argmax"]["before"], "no")
        self.assertEqual(metric["identity_normalized_argmax"]["after"], "no")
        self.assertFalse(metric["identity_normalized_argmax"]["changed"])

    def test_near_equal_epsilon_counts_as_unchanged(self):
        before, after = _pair_group()
        tiny = EQUALITY_EPSILON / 10.0
        metric = evaluate_pair(
            CounterfactualPair(
                "pair-g0",
                "g0",
                before,
                after,
                _outcome("g0-0", "g0", target="yes", logits=[2.0, 1.0], prediction="yes"),
                _outcome("g0-1", "g0", target="yes", logits=[2.0 + tiny, 1.0], prediction="yes"),
            )
        )
        self.assertFalse(metric["input_response"]["responded"])

    def test_target_only_flip_cannot_manufacture_counterfactual_success(self):
        """No metric may report responsiveness merely because labels differ."""
        before, after = _pair_group()
        metric = evaluate_pair(
            CounterfactualPair(
                "pair-g0",
                "g0",
                before,
                after,
                _outcome("g0-0", "g0", target="yes", logits=[2.0, 1.0], prediction="yes"),
                _outcome("g0-1", "g0", target="no", logits=[2.0, 1.0], prediction="yes"),
            )
        )
        self.assertTrue(metric["label_alignment"]["sign_flips"])
        self.assertFalse(metric["input_response"]["responded"])
        self.assertFalse(metric["identity_normalized_argmax"]["changed"])
        summary = summarize_pairs([metric])
        self.assertEqual(summary["input_response"]["pairs_with_any_option_logit_response"], 0)
        self.assertEqual(summary["input_response"]["response_rate"], 0.0)


class MalformedInputTests(unittest.TestCase):
    def _build(self, *, outcomes=None, examples=None):
        before, after = _pair_group()
        examples = examples if examples is not None else [before, after]
        outcomes = outcomes if outcomes is not None else [
            _outcome("g0-0", "g0", target="yes", logits=[2.0, 1.0], prediction="yes"),
            _outcome("g0-1", "g0", target="no", logits=[1.0, 2.0], prediction="no"),
        ]
        return examples, outcomes

    def test_absent_option_id_is_rejected(self):
        examples, outcomes = self._build()
        broken = copy.deepcopy(examples[0])
        broken["request"]["spec"]["options"] = [{"id": "yes", "label": "Yes"}, {"id": "gamma", "label": "Zeta"}]
        broken["typed_rank_features"]["candidates"]["gamma"] = _projection("no", False)
        with self.assertRaises(M013bInvalid):
            build_pairs([broken, examples[1]], outcomes)

    def test_mismatched_option_identity_across_pair_is_rejected(self):
        examples, outcomes = self._build()
        broken = copy.deepcopy(examples[1])
        broken["request"]["spec"]["options"][1]["id"] = "delta"
        with self.assertRaises(M013bInvalid):
            build_pairs([examples[0], broken], outcomes)

    def test_inconsistent_projection_role_is_rejected(self):
        examples, outcomes = self._build()
        broken = copy.deepcopy(examples[1])
        broken["typed_rank_features"]["candidates"]["no"]["fields"][-1]["value"]["value"] = "yes"
        with self.assertRaises(M013bInvalid) as ctx:
            build_pairs([examples[0], broken], outcomes)
        self.assertEqual(ctx.exception.code, "inconsistent_projection_role")

    def test_duplicate_pair_member_is_rejected(self):
        examples, outcomes = self._build()
        duplicated = [outcomes[0], copy.deepcopy(outcomes[0])]
        with self.assertRaises(M013bInvalid) as ctx:
            build_pairs(examples, duplicated)
        self.assertEqual(ctx.exception.code, "duplicate_outcome_case")

    def test_unknown_case_id_is_rejected(self):
        examples, outcomes = self._build()
        mutated = copy.deepcopy(outcomes)
        mutated[0]["case_id"] = "not-in-corpus"
        with self.assertRaises(M013bInvalid) as ctx:
            build_pairs(examples, mutated)
        self.assertEqual(ctx.exception.code, "unknown_case_id")

    def test_wrong_pair_cardinality_is_rejected(self):
        examples, outcomes = self._build()
        with self.assertRaises(M013bInvalid) as ctx:
            build_pairs(examples, outcomes[:1])
        self.assertEqual(ctx.exception.code, "pair_cardinality")

    def test_pair_with_identical_active_values_is_rejected(self):
        examples, outcomes = self._build()
        broken = copy.deepcopy(examples[1])
        broken["typed_rank_features"]["context"]["fields"][0]["value"]["value"] = False
        with self.assertRaises(M013bInvalid) as ctx:
            build_pairs([examples[0], broken], outcomes)
        self.assertEqual(ctx.exception.code, "pair_not_counterfactual")

    def test_non_finite_and_malformed_scores_are_rejected_not_coerced(self):
        examples, outcomes = self._build()
        for mutation in (
            lambda o: o["raw_logits"].__setitem__(0, float("nan")),
            lambda o: o["raw_probabilities"].__setitem__(0, float("inf")),
            lambda o: o.__setitem__("raw_probabilities", []),
            lambda o: o.__setitem__("raw_probabilities", None),
            lambda o: o.__setitem__("answerability_probability", 1.5),
        ):
            mutated = copy.deepcopy(outcomes)
            mutation(mutated[0])
            with self.assertRaises(M013bInvalid):
                build_pairs(examples, mutated)

    def test_score_count_mismatch_is_rejected(self):
        examples, outcomes = self._build()
        mutated = copy.deepcopy(outcomes)
        mutated[0]["raw_logits"].append(0.5)
        with self.assertRaises(M013bInvalid) as ctx:
            build_pairs(examples, mutated)
        self.assertEqual(ctx.exception.code, "score_identity_mismatch")

    def test_pairs_are_oriented_by_active_not_report_order(self):
        before, after = _pair_group()
        outcomes = [
            _outcome("g0-1", "g0", target="yes", logits=[9.0, 1.0], prediction="yes"),
            _outcome("g0-0", "g0", target="no", logits=[1.0, 9.0], prediction="no"),
        ]
        pairs = build_pairs([before, after], outcomes)
        metric = evaluate_pair(pairs[0])
        self.assertEqual(metric["per_option"]["yes"]["logit_before"], 1.0)
        self.assertEqual(metric["per_option"]["yes"]["logit_after"], 9.0)


class SummaryDenominatorTests(unittest.TestCase):
    def test_summary_separates_answerable_and_unanswerable_pairs(self):
        metrics = []
        before, after = _pair_group()
        metrics.append(
            evaluate_pair(
                CounterfactualPair(
                    "pair-g0",
                    "g0",
                    before,
                    after,
                    _outcome("g0-0", "g0", target="yes", logits=[2.0, 1.0], prediction="yes"),
                    _outcome("g0-1", "g0", target="no", logits=[2.0, 1.0], prediction="no"),
                )
            )
        )
        summary = summarize_pairs(metrics)
        self.assertEqual(summary["pairs"], 1)
        self.assertEqual(summary["answerable_pairs"], 1)
        self.assertEqual(summary["unanswerable_pairs"], 0)
        self.assertEqual(summary["target_correctness"]["denominator"], 1)
        self.assertEqual(summary["label_alignment"]["pairs"], 1)
        self.assertEqual(summary["evaluator_version"] if "evaluator_version" in summary else EVALUATOR_VERSION, EVALUATOR_VERSION)


# --------------------------------------------------------------------------
# Work package B — fail-closed preregistered gates
# --------------------------------------------------------------------------


class SupportGateTests(unittest.TestCase):
    def test_exact_support_boundaries(self):
        self.assertEqual(support_gate("s", observed=50, required=50).status, GATE_PASS)
        self.assertEqual(support_gate("s", observed=49, required=50).status, GATE_INSUFFICIENT_SUPPORT)
        self.assertEqual(support_gate("s", observed=20, required=20).status, GATE_PASS)
        self.assertEqual(support_gate("s", observed=19, required=20).status, GATE_INSUFFICIENT_SUPPORT)

    def test_total_slice_groups_cannot_substitute_for_answerable_support(self):
        """44 answerable groups inside a 67-group slice stays insufficient."""
        gate = support_gate("answerable_groups", observed=44, required=50)
        self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT)
        self.assertEqual(gate.evidence_count, 44)


class GateVerdictTests(unittest.TestCase):
    def test_empty_gate_set_never_passes(self):
        with self.assertRaises(M013bInvalid) as ctx:
            evaluate_gates([], task="choice")
        self.assertEqual(ctx.exception.code, "empty_gate_set")

    def test_favorable_ci_with_low_ood_support_is_never_positive(self):
        gates = [
            threshold_gate("primary_ci", observed=0.11, threshold=0.0, comparator=">", evidence_count=276),
            support_gate("ood_answerable_groups", observed=44, required=50),
        ]
        self.assertEqual(evaluate_gates(gates, task="choice").verdict, VERDICT_INDETERMINATE)

    def test_favorable_ci_with_zero_counterfactual_both_correct_is_never_positive(self):
        gates = [
            threshold_gate("primary_ci", observed=0.11, threshold=0.0, comparator=">", evidence_count=276),
            threshold_gate("counterfactual_both_correct", observed=0.0, threshold=0.5, comparator=">", evidence_count=276),
        ]
        self.assertEqual(evaluate_gates(gates, task="choice").verdict, VERDICT_INDETERMINATE)

    def test_missing_mandatory_ood_result_is_invalid(self):
        gates = [
            threshold_gate("primary_ci", observed=0.11, threshold=0.0, comparator=">", evidence_count=276),
            invalid_gate("critical_ood_text_shift", "required OOD result absent from the report"),
        ]
        self.assertEqual(evaluate_gates(gates, task="choice").verdict, VERDICT_INVALID)

    def test_always_abstain_with_perfect_no_answer_recall_is_never_positive(self):
        gates = [
            threshold_gate("primary_ci", observed=0.11, threshold=0.0, comparator=">", evidence_count=276),
            threshold_gate("no_answer_recall", observed=1.0, threshold=0.0, comparator=">", evidence_count=22),
            # always-abstain scores 0 answerable accuracy; the learned criterion
            # must still gate on real answerable improvement.
            threshold_gate("answerable_accuracy_improvement", observed=0.0, threshold=0.0, comparator=">", evidence_count=44),
        ]
        self.assertEqual(evaluate_gates(gates, task="choice").verdict, VERDICT_INDETERMINATE)

    def test_significantly_negative_critical_binary_shift_is_negative(self):
        """A critical gate whose success criterion is improvement fails => negative."""
        gates = [
            threshold_gate(
                "binary_text_shift_brier_improvement",
                observed=-0.2696,
                threshold=0.0,
                comparator=">",
                evidence_count=67,
                critical=True,
                description="Brier improvement over train prior on the text-shift family",
            ),
            support_gate("text_shift_groups", observed=67, required=50),
        ]
        result = evaluate_gates(gates, task="binary")
        self.assertEqual(result.verdict, VERDICT_NEGATIVE)
        self.assertIn("binary_text_shift", result.reason)

    def test_unsupported_critical_failure_does_not_claim_negative(self):
        """No support means no verdict — it degrades to indeterminate."""
        gates = [
            threshold_gate(
                "binary_text_shift_brier_improvement",
                observed=None,
                threshold=0.0,
                comparator=">",
                evidence_count=0,
                critical=True,
            )
        ]
        self.assertEqual(evaluate_gates(gates, task="binary").verdict, VERDICT_INDETERMINATE)

    def test_undeclared_positive_threshold_is_indeterminate_not_pass(self):
        gate = threshold_gate("counterfactual_response", observed=1.0, threshold=None, comparator=">")
        self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT)
        gates = [
            threshold_gate("primary_ci", observed=0.11, threshold=0.0, comparator=">", evidence_count=276),
            gate,
        ]
        self.assertEqual(evaluate_gates(gates, task="choice").verdict, VERDICT_INDETERMINATE)

    def test_all_frozen_gates_passing_yields_positive_on_constructed_fixture(self):
        gates = [
            threshold_gate("primary_ci", observed=0.11, threshold=0.0, comparator=">", evidence_count=276),
            support_gate("ood_answerable_groups", observed=50, required=50),
            support_gate("ood_no_answer_groups", observed=20, required=20),
            threshold_gate("counterfactual_both_correct", observed=0.5, threshold=0.0, comparator=">", evidence_count=276),
            threshold_gate("answerability_no_answer_recall", observed=0.9, threshold=0.5, comparator=">=", evidence_count=22),
        ]
        result = evaluate_gates(gates, task="choice")
        self.assertEqual(result.verdict, VERDICT_POSITIVE)
        self.assertTrue(all(g["status"] == GATE_PASS for g in result.as_dict()["gates"]))

    def test_every_mandatory_gate_must_pass_for_positive(self):
        """Sweep each gate to a non-pass state in turn; positive must vanish."""
        good = [
            Gate("primary_ci", GATE_PASS, True, evidence_count=276, observed=0.11, threshold=0.0, comparator=">"),
            Gate("ood_support", GATE_PASS, True, evidence_count=50, observed=50.0, threshold=50.0, comparator=">="),
            Gate("counterfactual", GATE_PASS, True, evidence_count=276, observed=0.5, threshold=0.0, comparator=">"),
        ]
        self.assertEqual(evaluate_gates(good, task="choice").verdict, VERDICT_POSITIVE)
        for index in range(len(good)):
            for bad_status in (GATE_FAIL, GATE_INSUFFICIENT_SUPPORT, GATE_INVALID):
                mutated = copy.deepcopy(good)
                mutated[index] = Gate(
                    mutated[index].name, bad_status, True, evidence_count=276, observed=0.0, threshold=0.0
                )
                self.assertNotEqual(
                    evaluate_gates(mutated, task="choice").verdict,
                    VERDICT_POSITIVE,
                    msg=f"gate {mutated[index].name} as {bad_status} must block positive",
                )

    def test_non_mandatory_failing_gate_does_not_block_but_is_recorded(self):
        gates = [
            threshold_gate("primary_ci", observed=0.11, threshold=0.0, comparator=">", evidence_count=276),
            Gate("exploratory_note", GATE_FAIL, mandatory=False, evidence_count=10),
        ]
        result = evaluate_gates(gates, task="choice")
        self.assertEqual(result.verdict, VERDICT_POSITIVE)
        self.assertTrue(any(g["name"] == "exploratory_note" and g["status"] == GATE_FAIL for g in result.as_dict()["gates"]))

    def test_unsupported_or_empty_ci_is_indeterminate(self):
        gates = [
            threshold_gate("primary_ci", observed=None, threshold=0.0, comparator=">", evidence_count=0),
        ]
        self.assertEqual(evaluate_gates(gates, task="choice").verdict, VERDICT_INDETERMINATE)

    def test_malformed_gate_status_and_support_are_rejected(self):
        with self.assertRaises(M013bInvalid):
            evaluate_gates([Gate("bad", "maybe", True)], task="choice")
        with self.assertRaises(M013bInvalid):
            support_gate("s", observed=-1, required=50)
        with self.assertRaises(M013bInvalid):
            support_gate("s", observed=50, required=0)
        with self.assertRaises(M013bInvalid):
            evaluate_gates([Gate("g", GATE_PASS, True)], task="rank")


class ProtocolSourceTests(unittest.TestCase):
    def test_frozen_protocol_declares_no_favorable_posthoc_thresholds(self):
        protocol = json.loads(PROTOCOL_PATH.read_text())
        self.assertEqual(protocol["evaluator_version"], EVALUATOR_VERSION)
        choice = protocol["choice_gates"]
        for key in (
            "counterfactual_both_correct_min_rate",
            "counterfactual_response_min_rate",
            "answerability_no_answer_recall_min",
            "calibration_max_conditional_brier",
        ):
            self.assertIsNone(choice[key], msg=f"{key} must stay undeclared")
        self.assertEqual(choice["unmet_threshold_consequence"], "indeterminate")
        self.assertEqual(protocol["support"]["min_answerable_groups_per_accuracy_slice"], 50)
        self.assertEqual(protocol["support"]["min_no_answer_groups_per_no_answer_slice"], 20)
        self.assertEqual(protocol["bootstrap"]["seed"], 14014)
        self.assertEqual(protocol["bootstrap"]["replicates"], 10000)


if __name__ == "__main__":
    unittest.main()