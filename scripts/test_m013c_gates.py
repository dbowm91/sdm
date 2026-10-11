#!/usr/bin/env python3
"""Adversarial tests for the M013c qualification-gate hardening.

Constructed fixtures only: nothing here reads a held-out report, fits a model or
consumes M013a test feedback. Every case below is one the M013c plan requires by
name.

The properties proven rather than asserted:

* a decision is made by the 95% interval bound, never by a point estimate;
* a critical failure below its own preregistered support minimum is
  `insufficient_support`, never `negative`;
* a malformed interval, bound or provenance record is `invalid`, never a number;
* a missing required family or an unmeasured declared control is `invalid`;
* every declared negative control is measured separately on the same answerable
  population, and a control that cannot discriminate is recorded rather than
  silently dropped or replaced by a zero baseline;
* `positive` is reachable only under an explicitly prospective protocol with
  numeric thresholds, and the frozen M013a protocol can never reach it.

Run with:
    python3 -m unittest discover -s scripts -p 'test_m013c_*.py'
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import math  # noqa: E402

from m013b_evaluator import mean  # noqa: E402
from m013c_evaluator import (  # noqa: E402
    M013C_EVALUATOR_VERSION,
    _quantile,
    REQUIRED_BOOTSTRAP_METHOD,
    REQUIRED_CONFIDENCE,
    REQUIRED_NEGATIVE_CONTROLS,
    REQUIRED_REPLICATES,
    REQUIRED_SEED,
    DECISION_FAVORABLE,
    DECISION_INDETERMINATE,
    DECISION_UNFAVORABLE,
    GATE_FAIL,
    GATE_INSUFFICIENT_SUPPORT,
    GATE_INVALID,
    GATE_PASS,
    VERDICT_INDETERMINATE,
    VERDICT_INVALID,
    VERDICT_NEGATIVE,
    VERDICT_POSITIVE,
    ControlMeasurement,
    Gate,
    IntervalEstimate,
    M013cInvalid,
    aggregate_by_group,
    completeness_gates,
    confidence_gate,
    control_discriminates,
    evaluate_controls,
    grouped_bootstrap,
    evaluate_gates,
    gate_status_counts,
    invalid_gate,
    paired_group_interval,
    support_gate,
    validate_protocol,
)

PROTOCOL_PATH = Path(__file__).resolve().parent / "m013c_protocol_v1.json"

BINARY_FAMILIES = (
    "m013a-binary-id-a-v1",
    "m013a-binary-id-b-v1",
    "m013a-binary-load-shift-v1",
    "m013a-binary-text-shift-v1",
    "m013a-binary-combined-shift-v1",
)
BINARY_CRITICAL = ("m013a-binary-text-shift-v1", "m013a-binary-combined-shift-v1")

CHOICE_OOD = (
    "m013a-choice-load-shift-v1",
    "m013a-choice-text-shift-v1",
    "m013a-choice-combined-shift-v1",
)
CHOICE_CRITICAL_OOD = ("m013a-choice-text-shift-v1", "m013a-choice-combined-shift-v1")

#: The minimum support the frozen protocol declares for an accuracy family.
MIN_SUPPORT = 50


def interval(point, lower, upper, groups, **overrides):
    """A complete, provenance-valid interval unless a test breaks one field."""
    payload = {
        "statistic": "constructed",
        "point_estimate": point,
        "lower": lower,
        "upper": upper,
        "groups": groups,
        "method": REQUIRED_BOOTSTRAP_METHOD,
        "replicates": REQUIRED_REPLICATES,
        "seed": REQUIRED_SEED,
        "confidence": REQUIRED_CONFIDENCE,
    }
    payload.update(overrides)
    return IntervalEstimate(**payload)


# --------------------------------------------------------------------------
# C1 — the decision is the interval bound, never the point estimate
# --------------------------------------------------------------------------


class IntervalBoundDecisionTests(unittest.TestCase):
    """Plan C1.1: exact interval/support edge cases, named case by case."""

    def test_positive_point_estimate_with_straddling_interval_is_indeterminate(self):
        """+0.02 point estimate but CI [-0.04, +0.08] at n=67 must not qualify."""
        gate = confidence_gate(
            "brier_improvement_vs_train_prior::text",
            interval(0.02, -0.04, 0.08, 67),
            minimum_group_support=MIN_SUPPORT,
        )
        self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT)
        self.assertEqual(gate.decision, DECISION_INDETERMINATE)
        self.assertNotEqual(gate.status, GATE_PASS)

    def test_negative_point_estimate_with_straddling_interval_is_not_negative(self):
        """-0.02 point estimate but CI [-0.08, +0.04] at n=67 is not a regression."""
        gate = confidence_gate(
            "brier_improvement_vs_train_prior::combined",
            interval(-0.02, -0.08, 0.04, 67),
            minimum_group_support=MIN_SUPPORT,
            critical=True,
        )
        self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT)
        self.assertEqual(gate.decision, DECISION_INDETERMINATE)
        self.assertNotEqual(gate.status, GATE_FAIL)

    def test_supported_negative_interval_at_50_groups_is_a_negative(self):
        gate = confidence_gate(
            "brier_improvement_vs_train_prior::text",
            interval(-0.12, -0.20, -0.04, 50),
            minimum_group_support=MIN_SUPPORT,
            critical=True,
        )
        self.assertEqual(gate.status, GATE_FAIL)
        self.assertEqual(gate.decision, DECISION_UNFAVORABLE)

    def test_supported_negative_interval_at_67_groups_is_a_negative(self):
        gate = confidence_gate(
            "brier_improvement_vs_train_prior::combined",
            interval(-0.12, -0.20, -0.04, 67),
            minimum_group_support=MIN_SUPPORT,
            critical=True,
        )
        self.assertEqual(gate.status, GATE_FAIL)
        self.assertEqual(evaluate_gates([gate], task="binary").verdict, VERDICT_NEGATIVE)

    def test_negative_interval_below_support_minimum_is_insufficient_not_negative(self):
        """CI [-0.20,-0.04] at n=1 and n=49 is insufficient support, NOT negative."""
        for groups in (1, 49):
            gate = confidence_gate(
                "brier_improvement_vs_train_prior::text",
                interval(-0.12, -0.20, -0.04, groups),
                minimum_group_support=MIN_SUPPORT,
                critical=True,
            )
            self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT, msg=f"n={groups}")
            self.assertEqual(gate.decision, DECISION_INDETERMINATE, msg=f"n={groups}")
            verdict = evaluate_gates([gate], task="binary").verdict
            self.assertEqual(verdict, VERDICT_INDETERMINATE, msg=f"n={groups} must never be negative")

    def test_favorable_interval_at_exact_support_boundary(self):
        gate = confidence_gate(
            "primary",
            interval(0.07, 0.01, 0.13, 50),
            minimum_group_support=MIN_SUPPORT,
        )
        self.assertEqual(gate.status, GATE_PASS)
        self.assertEqual(gate.decision, DECISION_FAVORABLE)

    def test_favorable_interval_one_group_below_minimum_is_insufficient(self):
        gate = confidence_gate(
            "primary",
            interval(0.07, 0.01, 0.13, 49),
            minimum_group_support=MIN_SUPPORT,
        )
        self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT)
        self.assertEqual(gate.decision, DECISION_INDETERMINATE)

    def test_intervals_touching_zero_are_indeterminate_on_both_sides(self):
        """A bound exactly at zero is not wholly above or wholly below it."""
        for lower, upper, point in ((-0.08, 0.00, -0.02), (0.00, 0.06, 0.02)):
            gate = confidence_gate(
                "boundary",
                interval(point, lower, upper, 67),
                minimum_group_support=MIN_SUPPORT,
                critical=True,
            )
            self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT, msg=f"[{lower}, {upper}]")
            self.assertEqual(gate.decision, DECISION_INDETERMINATE, msg=f"[{lower}, {upper}]")

    def test_point_estimate_never_overrides_a_straddling_interval(self):
        """A large point mean inside a straddling interval still decides nothing."""
        for point in (-0.049, 0.049):
            gate = confidence_gate(
                "family",
                interval(point, -0.05, 0.05, 500),
                minimum_group_support=MIN_SUPPORT,
                critical=True,
            )
            self.assertEqual(gate.decision, DECISION_INDETERMINATE, msg=f"point={point}")

    def test_missing_interval_is_insufficient_not_invalid_or_positive(self):
        gate = confidence_gate("family", None, minimum_group_support=MIN_SUPPORT)
        self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT)
        self.assertEqual(gate.decision, DECISION_INDETERMINATE)


class MalformedEvidenceTests(unittest.TestCase):
    """Plan C1.1: malformed evidence is invalid, never coerced to a number."""

    def test_reversed_bounds_are_rejected(self):
        with self.assertRaises(M013cInvalid) as ctx:
            interval(0.0, 0.2, -0.2, 67)
        self.assertEqual(ctx.exception.code, "reversed_interval")

    def test_non_finite_bounds_are_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(M013cInvalid):
                interval(bad, -0.1, 0.1, 67)
            with self.assertRaises(M013cInvalid):
                interval(0.0, bad, 0.1, 67)
            with self.assertRaises(M013cInvalid):
                interval(0.0, -0.1, bad, 67)

    def test_mean_contradicting_its_own_interval_is_rejected(self):
        """A claimed mean that cannot come from its own bounds is invalid."""
        with self.assertRaises(M013cInvalid) as ctx:
            interval(0.50, -0.20, -0.04, 67)
        self.assertEqual(ctx.exception.code, "point_estimate_outside_interval")

    def test_wrong_ci_sign_versus_claimed_mean_is_rejected(self):
        with self.assertRaises(M013cInvalid) as ctx:
            interval(-0.50, 0.04, 0.20, 67)
        self.assertEqual(ctx.exception.code, "point_estimate_outside_interval")

    def test_unrecognised_bootstrap_method_is_rejected(self):
        with self.assertRaises(M013cInvalid) as ctx:
            interval(0.05, 0.01, 0.09, 67, method="per_row_bootstrap")
        self.assertEqual(ctx.exception.code, "unsupported_bootstrap_method")

    def test_changed_seed_or_replicate_count_is_rejected(self):
        with self.assertRaises(M013cInvalid) as ctx:
            interval(0.05, 0.01, 0.09, 67, seed=999)
        self.assertEqual(ctx.exception.code, "bootstrap_seed_mismatch")
        with self.assertRaises(M013cInvalid) as ctx:
            interval(0.05, 0.01, 0.09, 67, replicates=1000)
        self.assertEqual(ctx.exception.code, "bootstrap_replicate_mismatch")
        with self.assertRaises(M013cInvalid) as ctx:
            interval(0.05, 0.01, 0.09, 67, confidence=0.9)
        self.assertEqual(ctx.exception.code, "bootstrap_confidence_mismatch")

    def test_empty_population_is_rejected(self):
        with self.assertRaises(M013cInvalid) as ctx:
            interval(0.05, 0.01, 0.09, 0)
        self.assertEqual(ctx.exception.code, "empty_population")

    def test_report_interval_missing_metadata_is_rejected(self):
        declared = {"seed": REQUIRED_SEED, "replicates": REQUIRED_REPLICATES, "confidence": REQUIRED_CONFIDENCE}
        with self.assertRaises(M013cInvalid) as ctx:
            IntervalEstimate.from_report("s", {"lower": 0.1, "upper": 0.2, "groups": 60}, point=0.15, declared=declared)
        self.assertEqual(ctx.exception.code, "incomplete_interval_metadata")

    def test_report_interval_disagreeing_with_protocol_is_rejected(self):
        declared = {"seed": REQUIRED_SEED, "replicates": REQUIRED_REPLICATES, "confidence": REQUIRED_CONFIDENCE}
        with self.assertRaises(M013cInvalid) as ctx:
            IntervalEstimate.from_report(
                "s",
                {"lower": 0.1, "upper": 0.2, "groups": 60, "replicates": 1000, "confidence": 0.95},
                point=0.15,
                declared=declared,
            )
        self.assertEqual(ctx.exception.code, "bootstrap_replicate_mismatch")
        with self.assertRaises(M013cInvalid) as ctx:
            IntervalEstimate.from_report(
                "s",
                {"lower": 0.1, "upper": 0.2, "groups": 60, "replicates": 10000, "confidence": 0.90},
                point=0.15,
                declared=declared,
            )
        self.assertEqual(ctx.exception.code, "bootstrap_confidence_mismatch")

    def test_report_interval_with_a_different_seed_is_rejected(self):
        with self.assertRaises(M013cInvalid) as ctx:
            IntervalEstimate.from_report(
                "s",
                {"lower": 0.1, "upper": 0.2, "groups": 60, "replicates": 10000, "confidence": 0.95, "seed": 7},
                point=0.15,
                declared={"seed": REQUIRED_SEED, "replicates": REQUIRED_REPLICATES, "confidence": REQUIRED_CONFIDENCE},
            )
        self.assertEqual(ctx.exception.code, "bootstrap_seed_mismatch")


class BootstrapOrderingTests(unittest.TestCase):
    """Defect E: replicate quantiles must be taken over sorted values.

    `m013b_evaluator.quantile` indexes as if already sorted while its
    `group_bootstrap` caller passes replicate values in random draw order, so a
    non-degenerate interval through that path is not a true percentile. The
    frozen M013a analyzer sorts first, so recorded evidence is unaffected; M013c
    must not inherit the defect.
    """

    def test_quantile_is_order_independent(self):
        """The defect is that quantiles were read off an unsorted replicate list."""
        values = [0.9, 0.1, 0.5, 0.3, 0.7, 0.2, 0.8, 0.4, 0.6, 0.05, 0.95]
        ordered = sorted(values)
        for probability in (0.025, 0.25, 0.5, 0.975):
            expected = _quantile(ordered, probability)
            self.assertAlmostEqual(_quantile(values, probability), expected, places=12, msg=str(probability))
            self.assertAlmostEqual(_quantile(list(reversed(values)), probability), expected, places=12, msg=str(probability))

    def test_quantile_matches_the_frozen_analyzer_definition(self):
        """M013c must agree with the sorting M013a analyzer, byte for byte."""
        values = [0.31, 0.02, 0.77, 0.55, 0.18, 0.94, 0.41, 0.63, 0.08, 0.86, 0.25, 0.69]
        for probability in (0.025, 0.5, 0.975):
            ordered = sorted(values)
            position = (len(ordered) - 1) * probability
            low, high = math.floor(position), math.ceil(position)
            expected = (
                ordered[low]
                if low == high
                else ordered[low] + (ordered[high] - ordered[low]) * (position - low)
            )
            self.assertAlmostEqual(_quantile(values, probability), expected, places=12)

    def test_grouped_bootstrap_uses_sorted_percentiles(self):
        """A grouped interval must equal the sorted-quantile interval exactly."""
        rows = [{"leakage_group": f"g{i % 30}", "delta": float((i * 37) % 11) / 10.0} for i in range(300)]
        stat = lambda m: mean([r["delta"] for r in m])  # noqa: E731
        out = grouped_bootstrap(rows, stat, replicates=3000)
        self.assertLessEqual(out["lower"], out["upper"])
        # A correct percentile bounds a wide fraction of the replicates.
        self.assertLess(out["lower"], mean([r["delta"] for r in rows]))
        self.assertGreater(out["upper"], mean([r["delta"] for r in rows]))

    def test_interval_bounds_are_ordered_and_bracket_the_mean(self):
        rows = [{"leakage_group": f"g{i % 40}", "delta": float((i * 37) % 11) / 10.0} for i in range(400)]
        out = grouped_bootstrap(rows, lambda m: mean([r["delta"] for r in m]), replicates=2000)
        self.assertLessEqual(out["lower"], out["upper"])
        self.assertLessEqual(out["lower"], mean([r["delta"] for r in rows]))
        self.assertGreaterEqual(out["upper"], mean([r["delta"] for r in rows]))

    def test_degenerate_constant_population_is_a_point_interval(self):
        rows = [{"leakage_group": f"g{i}", "delta": 0.0} for i in range(50)]
        out = grouped_bootstrap(rows, lambda m: mean([r["delta"] for r in m]), replicates=500)
        self.assertEqual(out["lower"], 0.0)
        self.assertEqual(out["upper"], 0.0)

    def test_wider_replicate_set_never_shrinks_the_interval(self):
        rows = [{"leakage_group": f"g{i % 25}", "delta": float(i % 7) / 4.0} for i in range(175)]
        stat = lambda m: mean([r["delta"] for r in m])  # noqa: E731
        narrow = grouped_bootstrap(rows, stat, replicates=200)
        wide = grouped_bootstrap(rows, stat, replicates=4000)
        self.assertLessEqual(wide["lower"], narrow["lower"] + 1e-9)
        self.assertGreaterEqual(wide["upper"], narrow["upper"] - 1e-9)


class GroupedResamplingTests(unittest.TestCase):
    """Plan C1.1/C2: group identity integrity in the paired interval."""

    def test_several_cases_per_group_are_collapsed_not_rejected(self):
        rows = [
            {"case_id": "c1", "leakage_group": "g0", "delta": 1.0},
            {"case_id": "c2", "leakage_group": "g0", "delta": 0.0},
            {"case_id": "c3", "leakage_group": "g1", "delta": 1.0},
        ]
        grouped = aggregate_by_group(rows, "s")
        self.assertEqual([row["leakage_group"] for row in grouped], ["g0", "g1"])
        self.assertAlmostEqual(grouped[0]["delta"], 0.5)

    def test_duplicate_case_id_is_rejected(self):
        rows = [
            {"case_id": "c1", "leakage_group": "g0", "delta": 1.0},
            {"case_id": "c1", "leakage_group": "g1", "delta": 1.0},
        ]
        with self.assertRaises(M013cInvalid) as ctx:
            aggregate_by_group(rows, "s")
        self.assertEqual(ctx.exception.code, "duplicate_case_id")

    def test_case_in_two_groups_is_rejected(self):
        rows = [
            {"case_id": "c1", "leakage_group": "g0", "delta": 1.0},
            {"case_id": "c1", "leakage_group": "g1", "delta": 1.0},
        ]
        # Duplicate case detection fires first; both are integrity failures.
        with self.assertRaises(M013cInvalid) as ctx:
            aggregate_by_group(rows, "s")
        self.assertEqual(ctx.exception.code, "duplicate_case_id")

    def test_malformed_group_id_is_rejected(self):
        for bad in ("", None, 17):
            with self.assertRaises(M013cInvalid) as ctx:
                aggregate_by_group([{"case_id": "c1", "leakage_group": bad, "delta": 1.0}], "s")
            self.assertEqual(ctx.exception.code, "malformed_group_id")

    def test_non_finite_delta_is_rejected(self):
        with self.assertRaises(M013cInvalid) as ctx:
            aggregate_by_group([{"case_id": "c1", "leakage_group": "g0", "delta": float("nan")}], "s")
        self.assertEqual(ctx.exception.code, "non_finite_delta")

    def test_empty_rows_are_rejected(self):
        with self.assertRaises(M013cInvalid) as ctx:
            aggregate_by_group([], "s")
        self.assertEqual(ctx.exception.code, "empty_population")

    def test_interval_counts_independent_groups_not_rows(self):
        rows = [{"case_id": f"c{i}", "leakage_group": "g0", "delta": 1.0} for i in range(40)]
        rows += [{"case_id": f"d{i}", "leakage_group": "g1", "delta": 0.0} for i in range(3)]
        estimate = paired_group_interval(rows, "s")
        self.assertEqual(estimate.groups, 2)

    def test_non_preregistered_replicate_count_is_rejected(self):
        """A test-only shortcut must not silently produce an accepted interval."""
        rows = [{"case_id": "c0", "leakage_group": "g0", "delta": 1.0}]
        with self.assertRaises(M013cInvalid) as ctx:
            paired_group_interval(rows, "s", replicates=200)
        self.assertEqual(ctx.exception.code, "bootstrap_replicate_mismatch")


# --------------------------------------------------------------------------
# C2 — required-family and control completeness
# --------------------------------------------------------------------------


def binary_protocol(**overrides):
    protocol = {
        "binary_gates": {
            "required_families": list(BINARY_FAMILIES),
            "critical_families": list(BINARY_CRITICAL),
            "diagnostic_only_families": [],
            "min_independent_groups_per_family": MIN_SUPPORT,
        },
        "support": {"min_independent_groups_per_primary_slice": MIN_SUPPORT},
    }
    protocol.update(overrides)
    return protocol


class RequiredSetCompletenessTests(unittest.TestCase):
    """Plan C2: a missing mandatory family is invalid, never silently skipped."""

    def test_every_declared_binary_family_is_enumerated_in_protocol_order(self):
        gates = completeness_gates(BINARY_FAMILIES, {f: {} for f in BINARY_FAMILIES}, label="binary_family", critical=BINARY_CRITICAL)
        names = [gate.name for gate in gates]
        self.assertEqual(
            names,
            [f"binary_family::presence::{family}" for family in BINARY_FAMILIES],
        )
        self.assertTrue(all(gate.status == GATE_PASS for gate in gates))

    def test_missing_required_binary_family_is_invalid(self):
        present = {f: {} for f in BINARY_FAMILIES if f != "m013a-binary-text-shift-v1"}
        gates = completeness_gates(BINARY_FAMILIES, present, label="binary_family", critical=BINARY_CRITICAL)
        statuses = {gate.name: gate.status for gate in gates}
        self.assertEqual(statuses["binary_family::presence::m013a-binary-text-shift-v1"], GATE_INVALID)

    def test_missing_noncritical_choice_ood_family_is_invalid(self):
        present = {f: {} for f in CHOICE_OOD if f != "m013a-choice-load-shift-v1"}
        gates = completeness_gates(CHOICE_OOD, present, label="choice_ood_family", critical=CHOICE_CRITICAL_OOD)
        statuses = {gate.name: gate.status for gate in gates}
        self.assertEqual(statuses["choice_ood_family::presence::m013a-choice-load-shift-v1"], GATE_INVALID)

    def test_undeclared_family_is_rejected(self):
        present = {f: {} for f in BINARY_FAMILIES}
        present["surprise-family-v9"] = {}
        gates = completeness_gates(BINARY_FAMILIES, present, label="binary_family", critical=BINARY_CRITICAL)
        undeclared = next(g for g in gates if g.name == "binary_family::undeclared_family")
        self.assertEqual(undeclared.status, GATE_INVALID)
        self.assertIn("surprise-family-v9", undeclared.reason)

    def test_declared_diagnostic_only_family_is_recorded_and_excluded(self):
        present = {f: {} for f in CHOICE_OOD}
        present["m013a-choice-id-a-v1"] = {}
        gates = completeness_gates(
            CHOICE_OOD,
            present,
            label="choice_ood_family",
            critical=CHOICE_CRITICAL_OOD,
            diagnostic_only=("m013a-choice-id-a-v1",),
        )
        statuses = {gate.name: gate.status for gate in gates}
        self.assertNotIn("choice_ood_family::undeclared_family", statuses)
        self.assertEqual(statuses["choice_ood_family::diagnostic_only"], GATE_PASS)
        diagnostic = next(g for g in gates if g.name == "choice_ood_family::diagnostic_only")
        self.assertFalse(diagnostic.mandatory)


class ProtocolValidationTests(unittest.TestCase):
    """Plan C2: the evaluator must never receive a silently incomplete set."""

    def test_critical_family_not_in_required_list_is_rejected(self):
        protocol = binary_protocol()
        protocol["binary_gates"]["required_families"] = ["m013a-binary-id-a-v1"]
        with self.assertRaises(M013cInvalid) as ctx:
            validate_protocol(protocol, task="binary")
        self.assertEqual(ctx.exception.code, "critical_not_required")

    def test_duplicate_declared_family_is_rejected(self):
        protocol = binary_protocol()
        protocol["binary_gates"]["required_families"] = list(BINARY_FAMILIES) + ["m013a-binary-id-a-v1"]
        with self.assertRaises(M013cInvalid) as ctx:
            validate_protocol(protocol, task="binary")
        self.assertEqual(ctx.exception.code, "duplicate_declared_name")

    def test_empty_mandatory_array_is_rejected(self):
        protocol = binary_protocol()
        protocol["binary_gates"]["required_families"] = []
        with self.assertRaises(M013cInvalid) as ctx:
            validate_protocol(protocol, task="binary")
        self.assertEqual(ctx.exception.code, "empty_mandatory_array")

    def test_family_both_required_and_diagnostic_only_is_rejected(self):
        protocol = binary_protocol()
        protocol["binary_gates"]["diagnostic_only_families"] = ["m013a-binary-id-a-v1"]
        with self.assertRaises(M013cInvalid) as ctx:
            validate_protocol(protocol, task="binary")
        self.assertEqual(ctx.exception.code, "contradictory_family_configuration")

    def test_missing_protocol_key_is_rejected(self):
        with self.assertRaises(M013cInvalid) as ctx:
            validate_protocol({}, task="binary")
        self.assertEqual(ctx.exception.code, "missing_protocol_key")

    def test_non_positive_support_minimum_is_rejected(self):
        protocol = binary_protocol()
        protocol["binary_gates"]["min_independent_groups_per_family"] = 0
        with self.assertRaises(M013cInvalid) as ctx:
            validate_protocol(protocol, task="binary")
        self.assertEqual(ctx.exception.code, "malformed_support_threshold")

    def test_frozen_m013c_protocol_is_internally_consistent(self):
        protocol = json.loads(PROTOCOL_PATH.read_text())
        self.assertEqual(protocol["evaluator_version"], M013C_EVALUATOR_VERSION)
        binary = validate_protocol(protocol, task="binary")
        choice = validate_protocol(protocol, task="choice")
        self.assertEqual(set(binary["required"]), set(BINARY_FAMILIES))
        self.assertEqual(set(choice["required"]), set(CHOICE_OOD))
        self.assertEqual(protocol["bootstrap"]["seed"], REQUIRED_SEED)
        self.assertEqual(protocol["bootstrap"]["replicates"], REQUIRED_REPLICATES)
        self.assertEqual(protocol["support"]["min_independent_groups_per_primary_slice"], MIN_SUPPORT)


class NegativeControlTests(unittest.TestCase):
    """Plan C2/C3: five named controls, measured separately, none omitted."""

    @staticmethod
    def _measurement(name, *, delta_lower, delta_upper, groups=60, discriminates=True, accuracy=0.5, note="constructed control"):
        return ControlMeasurement(
            name=name,
            control_accuracy=accuracy,
            learned_accuracy=0.62,
            # The mean is the midpoint of the declared bounds, so the fixture is
            # internally consistent; a degenerate control has a zero-width delta.
            paired_delta=interval((delta_lower + delta_upper) / 2.0, delta_lower, delta_upper, groups),
            groups=groups,
            discriminates=discriminates,
            note=note,
        )

    def _all_controls(self):
        return [
            self._measurement("train_majority_option_id", delta_lower=0.04, delta_upper=0.20),
            self._measurement("always_abstain", delta_lower=0.40, delta_upper=0.70, discriminates=True, accuracy=0.0, note="never answers; structural"),
            self._measurement("always_answer", delta_lower=0.00, delta_upper=0.00, discriminates=False),
            self._measurement("shuffled_score", delta_lower=0.02, delta_upper=0.18),
            self._measurement("context_only_identical_option_features_min_id", delta_lower=0.01, delta_upper=0.22),
        ]

    def test_five_controls_are_required_by_name(self):
        self.assertEqual(len(REQUIRED_NEGATIVE_CONTROLS), 5)
        gates = evaluate_controls(self._all_controls(), minimum_group_support=MIN_SUPPORT, threshold=0.0)
        measured = [gate.name for gate in gates if gate.name.startswith("negative_control::measured::")]
        self.assertEqual(len(measured), 5)
        for name in REQUIRED_NEGATIVE_CONTROLS:
            self.assertIn(f"negative_control::measured::{name}", measured)

    def test_omitted_control_is_invalid_not_silently_dropped(self):
        for omitted in ("always_answer", "shuffled_score", "context_only_identical_option_features_min_id"):
            controls = [c for c in self._all_controls() if c.name != omitted]
            gates = evaluate_controls(controls, minimum_group_support=MIN_SUPPORT, threshold=0.0)
            missing = next(g for g in gates if g.name == f"negative_control::measured::{omitted}")
            self.assertEqual(missing.status, GATE_INVALID, msg=omitted)

    def test_duplicate_control_measurement_is_rejected(self):
        controls = self._all_controls()
        controls.append(controls[0])
        with self.assertRaises(M013cInvalid) as ctx:
            evaluate_controls(controls, minimum_group_support=MIN_SUPPORT, threshold=0.0)
        self.assertEqual(ctx.exception.code, "duplicate_control")

    def test_non_discriminating_control_is_recorded_but_never_evidence(self):
        """always-answer is the candidate's own argmax: zero delta by construction."""
        self.assertFalse(control_discriminates("always_answer"))
        gates = evaluate_controls(self._all_controls(), minimum_group_support=MIN_SUPPORT, threshold=0.0)
        measured = next(g for g in gates if g.name == "negative_control::measured::always_answer")
        self.assertEqual(measured.status, GATE_PASS, msg="it must still be measured on the same population")
        gate = next(g for g in gates if g.name == "negative_control::beats::always_answer")
        self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT)
        self.assertIn("cannot discriminate", gate.reason)

    def test_always_abstain_must_be_beaten_on_answerable_accuracy(self):
        """Beating always-abstain is a real requirement, not a free pass."""
        self.assertTrue(control_discriminates("always_abstain"))
        gates = evaluate_controls(self._all_controls(), minimum_group_support=MIN_SUPPORT, threshold=0.0)
        abstain = next(g for g in gates if g.name == "negative_control::beats::always_abstain")
        self.assertEqual(abstain.status, GATE_PASS)

    def test_always_abstain_perfect_recall_is_not_learned_answerability(self):
        """A model that abstains on every answerable case fails always-abstain."""
        controls = self._all_controls()
        controls[1] = ControlMeasurement(
            name="always_abstain",
            control_accuracy=0.0,
            learned_accuracy=0.0,
            paired_delta=interval(0.0, 0.0, 0.0, 60),
            groups=60,
            discriminates=True,
            note="never answers; structural",
        )
        gates = evaluate_controls(controls, minimum_group_support=MIN_SUPPORT, threshold=0.0)
        abstain = next(g for g in gates if g.name == "negative_control::beats::always_abstain")
        self.assertEqual(abstain.status, GATE_INSUFFICIENT_SUPPORT)
        self.assertEqual(abstain.decision, DECISION_INDETERMINATE)

    def test_control_straddling_zero_does_not_pass(self):
        controls = self._all_controls()
        controls[3] = self._measurement("shuffled_score", delta_lower=-0.02, delta_upper=0.18)
        gates = evaluate_controls(controls, minimum_group_support=MIN_SUPPORT, threshold=0.0)
        gate = next(g for g in gates if g.name == "negative_control::beats::shuffled_score")
        self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT)

    def test_control_favouring_the_control_fails_the_gate(self):
        controls = self._all_controls()
        controls[3] = self._measurement("shuffled_score", delta_lower=-0.20, delta_upper=-0.02)
        gates = evaluate_controls(controls, minimum_group_support=MIN_SUPPORT, threshold=0.0)
        gate = next(g for g in gates if g.name == "negative_control::beats::shuffled_score")
        self.assertEqual(gate.status, GATE_FAIL)

    def test_control_below_support_minimum_is_insufficient(self):
        controls = self._all_controls()
        controls[3] = self._measurement("shuffled_score", delta_lower=-0.20, delta_upper=-0.02, groups=49)
        gates = evaluate_controls(controls, minimum_group_support=MIN_SUPPORT, threshold=0.0)
        gate = next(g for g in gates if g.name == "negative_control::beats::shuffled_score")
        self.assertEqual(gate.status, GATE_INSUFFICIENT_SUPPORT)
        self.assertEqual(gate.decision, DECISION_INDETERMINATE)

    def test_undeclared_control_threshold_is_indeterminate(self):
        gates = evaluate_controls(self._all_controls(), minimum_group_support=MIN_SUPPORT, threshold=None)
        beats = [gate for gate in gates if gate.name.startswith("negative_control::beats::")]
        self.assertEqual(len(beats), 5)
        self.assertTrue(all(gate.status == GATE_INSUFFICIENT_SUPPORT for gate in beats))
        self.assertTrue(all("no numeric learned-versus-control threshold" in gate.reason for gate in beats))


# --------------------------------------------------------------------------
# C3 — constructed positive is reachable, and only under a prospective protocol
# --------------------------------------------------------------------------


def prospective_protocol():
    """A fully specified protocol with numeric thresholds, frozen in advance."""
    protocol = binary_protocol()
    protocol["binary_gates"]["critical_regression_rule"] = "supported critical regression yields negative"
    protocol["negative_controls"] = {
        "required": list(REQUIRED_NEGATIVE_CONTROLS),
        "learned_beats_control_min_delta": 0.0,
    }
    return protocol


class ConstructedPositiveTests(unittest.TestCase):
    """Plan C3.3: one fully populated constructed positive, then break each gate."""

    def _positive_gate_set(self):
        gates = []
        for family in BINARY_FAMILIES:
            critical = family in BINARY_CRITICAL
            gates.append(
                confidence_gate(
                    f"brier_improvement_vs_train_prior::{family}",
                    interval(0.20, 0.10, 0.30, 60),
                    minimum_group_support=MIN_SUPPORT,
                    critical=critical,
                )
            )
            gates.append(support_gate(f"independent_groups::{family}", observed=60, required=MIN_SUPPORT))
        gates.extend(completeness_gates(BINARY_FAMILIES, {f: {} for f in BINARY_FAMILIES}, label="binary_family", critical=BINARY_CRITICAL))
        gates.extend(
            evaluate_controls(
                [
                    ControlMeasurement("train_majority_option_id", 0.5, 0.7, interval(0.2, 0.10, 0.30, 60), 60, True, "constructed"),
                    ControlMeasurement("always_abstain", 0.0, 0.7, interval(0.7, 0.60, 0.80, 60), 60, True, "structural"),
                    ControlMeasurement("always_answer", 0.7, 0.7, interval(0.0, 0.00, 0.00, 60), 60, False, "own argmax"),
                    ControlMeasurement("shuffled_score", 0.5, 0.7, interval(0.2, 0.10, 0.30, 60), 60, True, "constructed"),
                    ControlMeasurement("context_only_identical_option_features_min_id", 0.5, 0.7, interval(0.2, 0.10, 0.30, 60), 60, True, "constructed"),
                ],
                minimum_group_support=MIN_SUPPORT,
                threshold=0.0,
            )
        )
        return gates

    def test_full_construction_is_positive_under_a_prospective_protocol(self):
        result = evaluate_gates(self._positive_gate_set(), task="binary")
        self.assertEqual(result.verdict, VERDICT_POSITIVE)
        self.assertEqual(gate_status_counts(result.gates)["invalid"], 0)

    def test_removing_any_single_mandatory_gate_makes_positive_unreachable(self):
        gates = self._positive_gate_set()
        for index in range(len(gates)):
            if not gates[index].mandatory:
                continue
            for bad_status in (GATE_FAIL, GATE_INSUFFICIENT_SUPPORT, GATE_INVALID):
                mutated = copy.deepcopy(gates)
                mutated[index] = type(gates[index])(
                    **{**gates[index].as_dict(), "status": bad_status, "reason": "constructed mutation"}
                )
                verdict = evaluate_gates(mutated, task="binary").verdict
                self.assertNotEqual(
                    verdict, VERDICT_POSITIVE, msg=f"gate {gates[index].name} as {bad_status} must block positive"
                )

    def test_dropping_one_groups_support_makes_positive_unreachable(self):
        gates = self._positive_gate_set()
        index = next(i for i, gate in enumerate(gates) if gate.name.startswith("independent_groups::"))
        mutated = copy.deepcopy(gates)
        mutated[index] = support_gate(gates[index].name, observed=49, required=MIN_SUPPORT)
        self.assertEqual(evaluate_gates(mutated, task="binary").verdict, VERDICT_INDETERMINATE)

    def test_dropping_one_family_interval_makes_positive_unreachable(self):
        gates = self._positive_gate_set()
        index = next(i for i, gate in enumerate(gates) if gate.name.endswith("::m013a-binary-text-shift-v1"))
        mutated = copy.deepcopy(gates)
        mutated[index] = confidence_gate(
            "brier_improvement_vs_train_prior::m013a-binary-text-shift-v1",
            interval(0.20, -0.05, 0.30, 60),
            minimum_group_support=MIN_SUPPORT,
            critical=True,
        )
        self.assertNotEqual(evaluate_gates(mutated, task="binary").verdict, VERDICT_POSITIVE)

    def test_one_group_short_on_a_control_makes_positive_unreachable(self):
        controls = [
            ControlMeasurement("train_majority_option_id", 0.5, 0.7, interval(0.2, 0.10, 0.30, 49), 49, True, "c"),
            ControlMeasurement("always_abstain", 0.0, 0.7, interval(0.7, 0.60, 0.80, 60), 60, True, "c"),
            ControlMeasurement("always_answer", 0.7, 0.7, interval(0.0, 0.00, 0.00, 60), 60, False, "c"),
            ControlMeasurement("shuffled_score", 0.5, 0.7, interval(0.2, 0.10, 0.30, 60), 60, True, "c"),
            ControlMeasurement("context_only_identical_option_features_min_id", 0.5, 0.7, interval(0.2, 0.10, 0.30, 60), 60, True, "c"),
        ]
        gates = evaluate_controls(controls, minimum_group_support=MIN_SUPPORT, threshold=0.0)
        beaten = next(g for g in gates if g.name == "negative_control::beats::train_majority_option_id")
        self.assertEqual(beaten.status, GATE_INSUFFICIENT_SUPPORT)


class FrozenProtocolReplayTests(unittest.TestCase):
    """Plan C3.3: the legacy frozen protocol can NEVER produce a positive."""

    def test_frozen_protocol_declares_no_favorable_thresholds(self):
        protocol = json.loads(PROTOCOL_PATH.read_text())
        choice = protocol["choice_gates"]
        for key in (
            "counterfactual_both_correct_min_rate",
            "counterfactual_response_min_rate",
            "answerability_no_answer_recall_min",
            "calibration_max_conditional_brier",
        ):
            self.assertIsNone(choice[key], msg=f"{key} must stay undeclared")
        self.assertIsNone(protocol["negative_controls"]["learned_beats_control_min_delta"])
        self.assertEqual(choice["unmet_threshold_consequence"], "indeterminate")

    def test_frozen_protocol_gates_cannot_yield_positive_even_with_favourable_evidence(self):
        """Give the frozen protocol the best possible evidence. It still cannot pass."""
        protocol = json.loads(PROTOCOL_PATH.read_text())
        choice = protocol["choice_gates"]
        gates = [
            # A perfectly favourable primary interval.
            confidence_gate(
                "primary_paired_answerable_accuracy",
                interval(0.20, 0.10, 0.30, 500),
                minimum_group_support=protocol["support"]["min_independent_groups_per_primary_slice"],
            ),
            # Every declared OOD family present and fully supported.
            *completeness_gates(
                choice["required_ood_families"],
                {family: {} for family in choice["required_ood_families"]},
                label="choice_ood_family",
                critical=choice["critical_ood_families"],
                diagnostic_only=choice["diagnostic_only_families"],
            ),
            support_gate("answerable_groups::ood", observed=500, required=50),
            support_gate("no_answer_groups::ood", observed=100, required=20),
        ]
        # The four undeclared-threshold gates.
        for name in (
            "counterfactual_both_correct_rate",
            "counterfactual_fixed_option_response_rate",
            "answerability_no_answer_recall",
            "calibration_max_conditional_brier",
        ):
            gates.append(
                Gate(
                    name=name,
                    status=GATE_INSUFFICIENT_SUPPORT,
                    mandatory=True,
                    reason="frozen protocol declares no numeric threshold",
                )
            )
        # All five controls measured and, where discriminating, strongly favourable.
        gates.extend(
            evaluate_controls(
                [
                    ControlMeasurement("train_majority_option_id", 0.1, 0.7, interval(0.6, 0.5, 0.7, 500), 500, True, "c"),
                    ControlMeasurement("always_abstain", 0.0, 0.7, interval(0.7, 0.6, 0.8, 500), 500, True, "c"),
                    ControlMeasurement("always_answer", 0.7, 0.7, interval(0.0, 0.0, 0.0, 500), 500, False, "c"),
                    ControlMeasurement("shuffled_score", 0.1, 0.7, interval(0.6, 0.5, 0.7, 500), 500, True, "c"),
                    ControlMeasurement("context_only_identical_option_features_min_id", 0.1, 0.7, interval(0.6, 0.5, 0.7, 500), 500, True, "c"),
                ],
                minimum_group_support=50,
                threshold=protocol["negative_controls"]["learned_beats_control_min_delta"],
            )
        )
        result = evaluate_gates(gates, task="choice")
        self.assertNotEqual(result.verdict, VERDICT_POSITIVE)
        self.assertEqual(result.verdict, VERDICT_INDETERMINATE)


# --------------------------------------------------------------------------
# Verdict priority
# --------------------------------------------------------------------------


class VerdictPriorityTests(unittest.TestCase):
    """Plan A5: invalid > supported negative > indeterminate > positive."""

    def test_empty_gate_set_never_passes(self):
        with self.assertRaises(M013cInvalid) as ctx:
            evaluate_gates([], task="binary")
        self.assertEqual(ctx.exception.code, "empty_gate_set")

    def test_invalid_outranks_a_supported_critical_negative(self):
        gates = [
            invalid_gate("binary_family::presence::missing", "required family absent"),
            confidence_gate("critical", interval(-0.12, -0.20, -0.04, 60), minimum_group_support=MIN_SUPPORT, critical=True),
        ]
        self.assertEqual(evaluate_gates(gates, task="binary").verdict, VERDICT_INVALID)

    def test_supported_critical_negative_outranks_indeterminate(self):
        gates = [
            confidence_gate("critical", interval(-0.12, -0.20, -0.04, 60), minimum_group_support=MIN_SUPPORT, critical=True),
            confidence_gate("other", interval(0.0, -0.1, 0.1, 60), minimum_group_support=MIN_SUPPORT),
        ]
        self.assertEqual(evaluate_gates(gates, task="binary").verdict, VERDICT_NEGATIVE)

    def test_critical_failure_without_attached_support_minimum_is_indeterminate(self):
        from m013c_evaluator import Gate

        gate = Gate(
            name="critical_without_support",
            status=GATE_FAIL,
            mandatory=True,
            critical=True,
            evidence_count=999,
            reason="no minimum attached",
        )
        result = evaluate_gates([gate], task="binary")
        self.assertEqual(result.verdict, VERDICT_INDETERMINATE)
        self.assertIn("without an attached support minimum", result.reason)

    def test_non_mandatory_failing_gate_is_recorded_but_does_not_block(self):
        gates = [
            confidence_gate("primary", interval(0.2, 0.1, 0.3, 60), minimum_group_support=MIN_SUPPORT),
            Gate(
                name="exploratory_note", status=GATE_FAIL, mandatory=False, evidence_count=10
            ),
        ]
        result = evaluate_gates(gates, task="binary")
        self.assertEqual(result.verdict, VERDICT_POSITIVE)
        self.assertTrue(any(g["name"] == "exploratory_note" and g["status"] == GATE_FAIL for g in result.as_dict()["gates"]))

    def test_duplicate_gate_names_are_rejected(self):
        gate = confidence_gate("primary", interval(0.2, 0.1, 0.3, 60), minimum_group_support=MIN_SUPPORT)
        with self.assertRaises(M013cInvalid) as ctx:
            evaluate_gates([gate, gate], task="binary")
        self.assertEqual(ctx.exception.code, "duplicate_gate_name")

    def test_unknown_gate_status_and_task_are_rejected(self):
        from m013c_evaluator import Gate

        with self.assertRaises(M013cInvalid) as ctx:
            evaluate_gates([Gate("bad", "maybe", True)], task="binary")
        self.assertEqual(ctx.exception.code, "unknown_gate_status")
        with self.assertRaises(M013cInvalid) as ctx:
            evaluate_gates([Gate("g", GATE_PASS, True)], task="rank")
        self.assertEqual(ctx.exception.code, "unknown_task")

    def test_support_gate_boundaries(self):
        self.assertEqual(support_gate("s", observed=50, required=50).status, GATE_PASS)
        self.assertEqual(support_gate("s", observed=49, required=50).status, GATE_INSUFFICIENT_SUPPORT)
        self.assertEqual(support_gate("s", observed=20, required=20).status, GATE_PASS)
        self.assertEqual(support_gate("s", observed=19, required=20).status, GATE_INSUFFICIENT_SUPPORT)
        with self.assertRaises(M013cInvalid):
            support_gate("s", observed=-1, required=50)
        with self.assertRaises(M013cInvalid):
            support_gate("s", observed=50, required=0)


if __name__ == "__main__":
    unittest.main()
