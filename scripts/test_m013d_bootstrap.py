"""Focused regression tests for the M013b unsorted bootstrap correction."""

from __future__ import annotations

import itertools
import hashlib
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m013b_evaluator import M013bInvalid, group_bootstrap, quantile  # noqa: E402
from m013c_evaluator import grouped_bootstrap  # noqa: E402
from m013d_provenance_audit import atomic_write_json  # noqa: E402


def _statistic(rows):
    values = [row["value"] for row in rows]
    return sum(values) / len(values) if values else None


def _old_unsorted_interval(rows, *, seed=14014, replicates=10_000, confidence=0.95):
    """Reproduce the pre-fix M013b percentile bug for explicit comparison."""
    grouped = {}
    for row in rows:
        grouped.setdefault(row["leakage_group"], []).append(row)
    per_group = {key: _statistic(members) for key, members in grouped.items()}
    per_group = {key: value for key, value in per_group.items() if value is not None}
    keys = sorted(per_group)
    rng = random.Random(seed)
    draws = [
        sum(per_group[keys[rng.randrange(len(keys))]] for _ in range(len(keys))) / len(keys)
        for _ in range(replicates)
    ]
    tail = (1 - confidence) / 2

    def old_quantile(values, probability):
        position = (len(values) - 1) * probability
        low, high = math.floor(position), math.ceil(position)
        if low == high:
            return float(values[low])
        return values[low] + (values[high] - values[low]) * (position - low)

    return old_quantile(draws, tail), old_quantile(draws, 1 - tail)


def _m013a_sorted_interval(rows, *, seed=14014, replicates=10_000, confidence=0.95):
    """Independent reproduction of the frozen M013a sorted bootstrap path."""
    grouped = {}
    for row in rows:
        grouped.setdefault(row["leakage_group"], []).append(row)
    per_group = {key: _statistic(members) for key, members in grouped.items()}
    per_group = {key: value for key, value in per_group.items() if value is not None}
    keys = list(per_group)
    rng = random.Random(seed)
    draws = [
        sum(per_group[keys[rng.randrange(len(keys))]] for _ in range(len(keys))) / len(keys)
        for _ in range(replicates)
    ]

    def sorted_quantile(values, probability):
        ordered = sorted(values)
        position = (len(ordered) - 1) * probability
        low, high = math.floor(position), math.ceil(position)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    tail = (1 - confidence) / 2
    return sorted_quantile(draws, tail), sorted_quantile(draws, 1 - tail)


class M013dQuantileTests(unittest.TestCase):
    def test_unsorted_permutations_and_boundaries(self):
        values = [3, 1, 2]
        before = list(values)
        expected = {0: 1.0, 0.5: 2.0, 1: 3.0}
        for permutation in itertools.permutations(values):
            for probability, result in expected.items():
                self.assertEqual(quantile(permutation, probability), result)
        self.assertEqual(values, before)
        self.assertEqual(quantile([0, 10], 0.25), 2.5)
        self.assertEqual(quantile([0, 10], 0.975), 9.75)
        self.assertEqual(quantile([10, 0], 0), 0.0)
        self.assertEqual(quantile([10, 0], 1), 10.0)

    def test_invalid_quantile_inputs_fail_closed(self):
        for values, probability in (([], 0.5), ([1, math.nan], 0.5), ([1, math.inf], 0.5), ([1], -0.1), ([1], 1.1), ([1], math.nan)):
            with self.subTest(values=values, probability=probability), self.assertRaises(M013bInvalid):
                quantile(values, probability)

    def test_constructed_non_degenerate_populations_match_correct_references(self):
        populations = {
            "skewed": [0, 0, 0, 1, 4, 15, 40],
            # Two paired rows in each leakage group. The estimator must sample
            # the five independent groups, not treat these ten rows as support.
            "paired": [(-3, 1), (-1, 2), (0, 2), (1, 4), (2, 5)],
        }
        results = {}
        for name, values in populations.items():
            rows = []
            if name == "skewed":
                rows = [{"leakage_group": f"g{i}", "value": value} for i, value in enumerate(values)]
            else:
                for index, pair in enumerate(values):
                    rows.extend(
                        {"leakage_group": f"g{index}", "value": value}
                        for value in pair
                    )
            corrected = group_bootstrap(rows, _statistic, seed=14014, replicates=10_000, confidence=0.95)
            m013c = grouped_bootstrap(rows, _statistic, seed=14014, replicates=10_000, confidence=0.95)
            m013a = _m013a_sorted_interval(rows)
            self.assertEqual(corrected["groups"], len(values))
            self.assertEqual(corrected["replicates"], 10_000)
            self.assertAlmostEqual(corrected["lower"], m013c["lower"], delta=1e-12)
            self.assertAlmostEqual(corrected["upper"], m013c["upper"], delta=1e-12)
            self.assertAlmostEqual(corrected["lower"], m013a[0], delta=1e-12)
            self.assertAlmostEqual(corrected["upper"], m013a[1], delta=1e-12)
            old = _old_unsorted_interval(rows)
            self.assertTrue(
                abs(old[0] - corrected["lower"]) > 1e-9 or abs(old[1] - corrected["upper"]) > 1e-9,
                f"old unsorted interval unexpectedly matched {name}: {old}",
            )
            repeated = group_bootstrap(rows, _statistic, seed=14014, replicates=10_000, confidence=0.95)
            self.assertEqual(corrected, repeated)
            results[name] = (corrected["lower"], corrected["upper"], old)
        # Numeric examples are deliberately fixed so drift in seed, draw count,
        # group membership, or quantile convention is visible in review.
        self.assertEqual(results["skewed"][:2], (0.7142857142857143, 19.860714285714234))
        self.assertEqual(results["paired"][:2], (0.0, 2.7))

    def test_group_order_and_input_order_are_stable(self):
        rows = [
            {"leakage_group": "z", "value": 8},
            {"leakage_group": "a", "value": 1},
            {"leakage_group": "m", "value": 3},
        ]
        expected = group_bootstrap(rows, _statistic)
        self.assertEqual(group_bootstrap(list(reversed(rows)), _statistic), expected)
        self.assertEqual(group_bootstrap(rows, _statistic), expected)

    def test_degenerate_zero_and_one_group_semantics(self):
        constant = [{"leakage_group": f"g{i}", "value": 7} for i in range(4)]
        result = group_bootstrap(constant, _statistic)
        self.assertEqual((result["lower"], result["upper"]), (7.0, 7.0))
        one = group_bootstrap([{"leakage_group": "only", "value": 9}], _statistic)
        self.assertEqual((one["groups"], one["lower"], one["upper"]), (1, 9.0, 9.0))
        zero = group_bootstrap([], _statistic)
        self.assertEqual((zero["groups"], zero["lower"], zero["upper"]), (0, None, None))

    def test_invalid_bootstrap_inputs_fail_closed(self):
        rows = [{"leakage_group": "g", "value": 1}]
        invalid_settings = (
            {"seed": True},
            {"seed": 1.5},
            {"replicates": 0},
            {"replicates": 1_000_001},
            {"replicates": True},
            {"confidence": 0},
            {"confidence": 1},
            {"confidence": math.nan},
        )
        for kwargs in invalid_settings:
            with self.subTest(kwargs=kwargs), self.assertRaises(M013bInvalid):
                group_bootstrap(rows, _statistic, **kwargs)
        for invalid_row in ({}, {"leakage_group": "", "value": 1}, {"leakage_group": 7, "value": 1}):
            with self.subTest(row=invalid_row), self.assertRaises(M013bInvalid):
                group_bootstrap([invalid_row], _statistic)
        for bad_value in (math.nan, math.inf, "1"):
            with self.subTest(value=bad_value), self.assertRaises(M013bInvalid):
                group_bootstrap([{"leakage_group": "g", "value": bad_value}], _statistic)


class M013dProvenanceTests(unittest.TestCase):
    def test_interrupted_audit_write_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text('{"accepted": "old"}\n')
            with patch("m013d_provenance_audit.os.replace", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    atomic_write_json(path, {"accepted": "new"})
            self.assertEqual(path.read_text(), '{"accepted": "old"}\n')
            self.assertEqual(list(path.parent.glob(".audit.json.*.tmp")), [])

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[1] / "target/m013c/m013c-decision-audit.json").is_file(),
        "generated M013a/M013b/M013c sidecars are not present",
    )
    def test_current_sidecars_chain_source_hashes_and_retain_verdicts(self):
        root = Path(__file__).resolve().parents[1]
        m013b_path = root / "target/m013b/m013a-audit-erratum.json"
        m013b_diagnostics_path = root / "target/m013b/m013b-diagnostics.json"
        m013c_path = root / "target/m013c/m013c-decision-audit.json"
        m013b = json.loads(m013b_path.read_text())
        m013c = json.loads(m013c_path.read_text())
        current_source_sha = hashlib.sha256((root / "scripts/m013b_evaluator.py").read_bytes()).hexdigest()
        current_m013b_sha = hashlib.sha256(m013b_path.read_bytes()).hexdigest()
        self.assertEqual(m013b["input_sha256"]["scripts/m013b_evaluator.py"], current_source_sha)
        self.assertEqual(m013c["input_sha256"]["target/m013b/m013a-audit-erratum.json"], current_m013b_sha)
        self.assertEqual(m013b["gate_verdicts"]["binary"]["verdict"], "negative")
        self.assertEqual(m013b["gate_verdicts"]["choice"]["verdict"], "indeterminate")
        self.assertEqual(m013c["retained_disposition"]["binary"], "negative")
        self.assertEqual(m013c["retained_disposition"]["choice"], "indeterminate")
        # These original ledgers remain fixed at their historical commits. The
        # current sidecars must differ only because their provenance chain now
        # includes the repaired evaluator source hash.
        self.assertNotEqual(current_m013b_sha, "07fb99f1e984354a6746f3645f893beadfbbb3fd40ce4e37d4b6a834a0e15901")
        diagnostics = json.loads(m013b_diagnostics_path.read_text())
        self.assertEqual(diagnostics["evidence_policy"]["partitions_forbidden"], ["test"])
        self.assertEqual(diagnostics["root_cause_status"]["binary"], "root_cause_isolated")
        self.assertEqual(diagnostics["root_cause_status"]["choice"], "root_cause_isolated")

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[1] / "target/m013d/bootstrap-provenance-audit.json").is_file(),
        "generated M013d provenance audit is not present",
    )
    def test_machine_readable_provenance_audit_passed(self):
        root = Path(__file__).resolve().parents[1]
        audit = json.loads((root / "target/m013d/bootstrap-provenance-audit.json").read_text())
        self.assertIs(audit["historical_preserved"], True)
        self.assertIs(audit["model_qualifications_unchanged"], True)
        self.assertEqual(audit["binary_disposition"], "negative")
        self.assertEqual(audit["choice_disposition"], "indeterminate")
        self.assertTrue(all(audit["semantic_comparison"].values()))


if __name__ == "__main__":
    unittest.main()
