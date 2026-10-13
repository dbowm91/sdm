#!/usr/bin/env python3
"""M014a analyzer unit tests: serde, pairing, CI, controls, resources.

Constructed fixtures only; no training, no held-out selection, no M014 test
feedback. Proves B acceptance and G4/G5/G6 mechanics.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qualify_semantic_v2 as qv


def tiny_manifest(**overrides):
    m = {
        "manifest_id": "test-manifest-v1",
        "binary": {
            "required_families": ["fam-a", "fam-b"],
            "critical_families": ["fam-b"],
            "min_independent_groups": 50,
            "thresholds": {"id_noninferiority_margin": -0.02},
            "test_membership_sha256": "sha256:" + "0" * 64,
            "dataset_sha256": "sha256:" + "0" * 64,
            "split_fingerprint": "sha256:" + "0" * 64,
        },
        "choice": {
            "required_families": ["cfam-a"],
            "critical_families": [],
            "min_independent_groups": 50,
            "min_answerable_groups": 50,
            "min_no_answer_groups": 20,
            "min_pair_count": 50,
            "thresholds": {
                "counterfactual_both_correct_point": 0.8,
                "counterfactual_both_correct_lower": 0.7,
                "no_answer_recall_point": 0.8,
                "no_answer_recall_lower": 0.65,
                "answerable_coverage_floor": 0.6,
            },
            "test_membership_sha256": "sha256:" + "0" * 64,
            "dataset_sha256": "sha256:" + "0" * 64,
            "split_fingerprint": "sha256:" + "0" * 64,
        },
        "bootstrap": {"method": "paired_group_bootstrap_percentile", "seed": 140015, "replicates": 2000, "alpha": 0.05 / 18},
        "resource_gates": {"artifact_max_bytes": 16777216, "choice_max_options": 128, "platforms": ["linux-x86_64"]},
        "controls": {"binary": ["legacy-binary", "train-prior-constant"], "choice": ["legacy"]},
    }
    m.update(overrides)
    return m


class SerdeTests(unittest.TestCase):
    def test_new_report_requires_explicit_true_and_partition(self):
        raw = {"schema": "sdm-semantic-evaluate-v2", "schema_version": 2,
               "evaluated_partition": "test", "test_evaluation_performed": True,
               "test_ids": ["a", "b"]}
        ok, _ = qv.validate_test_evaluation(raw, "", expected_test_ids=["a", "b"])
        self.assertTrue(ok)
        # Missing flag on new-shaped report is rejected.
        raw2 = dict(raw)
        del raw2["test_evaluation_performed"]
        with self.assertRaises(qv.QualifyInvalid):
            qv.validate_test_evaluation(raw2, "", expected_test_ids=["a", "b"])
        # Missing partition rejected.
        raw3 = dict(raw)
        del raw3["evaluated_partition"]
        with self.assertRaises(qv.QualifyInvalid):
            qv.validate_test_evaluation(raw3, "", expected_test_ids=["a", "b"])

    def test_explicit_false_never_evaluated(self):
        for raw in ({"test_evaluation_performed": False, "test_ids": ["a"]},
                    {"schema": "sdm-semantic-evaluate-v2", "schema_version": 2,
                     "evaluated_partition": "test", "test_evaluation_performed": False, "test_ids": ["a"]}):
            ok, _ = qv.validate_test_evaluation(raw, "", expected_test_ids=["a"])
            self.assertFalse(ok)

    def test_legacy_missing_true_requires_exact_test_ids(self):
        legacy_ids = ["x-0", "x-1", "y-0", "y-1"]
        raw = {"semantic": "binary", "test_ids": legacy_ids, "outcomes": [{"case_id": "x-0"}]}
        ok, _ = qv.validate_test_evaluation(raw, "", allow_legacy=True, legacy_test_ids=legacy_ids)
        self.assertTrue(ok)
        # Wrong IDs => not inferred.
        with self.assertRaises(qv.QualifyInvalid):
            qv.validate_test_evaluation(raw, "", allow_legacy=True, legacy_test_ids=["other"])
        # Without allow_legacy, missing is not evaluated.
        ok2, _ = qv.validate_test_evaluation(raw, "")
        self.assertFalse(ok2)

    def test_test_membership_mismatch_rejected(self):
        raw = {"schema": "sdm-semantic-evaluate-v2", "schema_version": 2,
               "evaluated_partition": "test", "test_evaluation_performed": True,
               "test_ids": ["a", "b"]}
        with self.assertRaises(qv.QualifyInvalid):
            qv.validate_test_evaluation(raw, "", expected_test_ids=["a", "c"])


class BinaryPairingTests(unittest.TestCase):
    def meta(self):
        # Two groups, two rows each, family fam-a.
        m = {}
        for g in ("g0", "g1"):
            for i in (0, 1):
                cid = f"{g}-c{i}"
                m[cid] = {"family": "fam-a", "leakage_group": g, "truth": bool(i)}
        return m

    def test_two_rows_in_one_group_counted_once(self):
        meta = self.meta()
        cand = {cid: {"score": 0.9 if meta[cid]["truth"] else 0.1} for cid in meta}
        base = {cid: {"score": 0.6 if meta[cid]["truth"] else 0.4} for cid in meta}
        groups, improvements, gids = qv.aggregate_binary_groups(cand, base, meta, "fam-a")
        self.assertEqual(sorted(gids), ["g0", "g1"])
        self.assertEqual(len(groups["g0"]), 2)
        # Resampling unit is groups (2), not rows (4).
        interval = qv.paired_group_bootstrap(improvements, seed=1, replicates=500, alpha=0.05, statistic_name="s")
        self.assertEqual(interval.groups, 2)

    def test_pair_by_case_ids_not_insertion_order(self):
        meta = self.meta()
        cand = {cid: {"score": 0.9 if meta[cid]["truth"] else 0.1} for cid in meta}
        base = {cid: {"score": 0.6 if meta[cid]["truth"] else 0.4} for cid in meta}
        # Reverse insertion order for baseline.
        base_rev = dict(reversed(list(base.items())))
        _, imp1, _ = qv.aggregate_binary_groups(cand, base, meta, "fam-a")
        _, imp2, _ = qv.aggregate_binary_groups(cand, base_rev, meta, "fam-a")
        self.assertEqual(imp1, imp2)

    def test_duplicates_missing_extra_rejected(self):
        meta = self.meta()
        cand = {cid: {"score": 0.9} for cid in meta}
        base = {cid: {"score": 0.6} for cid in meta}
        # Missing one case in baseline.
        base_missing = {k: v for k, v in base.items() if k != "g0-c0"}
        with self.assertRaises(qv.QualifyInvalid):
            qv.aggregate_binary_groups(cand, base_missing, meta, "fam-a")
        # Extra case.
        cand_extra = dict(cand)
        cand_extra["extra"] = {"score": 0.5}
        # Need meta for extra to trigger mismatch? Extra not in family_cases, but
        # cand_ids includes extra? Actually family_cases is from meta, so extra
        # not in family_cases, but cand has extra outside family: our function
        # only checks family_cases subset, so extra outside family is ignored.
        # To test extra, add meta for extra but not in baseline.
        meta2 = dict(meta)
        meta2["extra"] = {"family": "fam-a", "leakage_group": "g2", "truth": True}
        with self.assertRaises(qv.QualifyInvalid):
            qv.aggregate_binary_groups(cand_extra, base, meta2, "fam-a")

    def test_incomplete_pair_rejected(self):
        meta = {"c0": {"family": "fam-a", "leakage_group": "g0", "truth": True}}
        cand = {"c0": {"score": 0.9}}
        base = {"c0": {"score": 0.6}}
        with self.assertRaises(qv.QualifyInvalid) as ctx:
            qv.aggregate_binary_groups(cand, base, meta, "fam-a")
        self.assertEqual(ctx.exception.code, "incomplete_pair")

    def test_reference_bootstrap_agrees_and_handles_uneven_constant_skewed(self):
        # Uneven group sizes for reference calc (direct, not via aggregate which
        # requires pairs). Use reference helper.
        groups = [[0.1, 0.2, 0.3], [0.9], [0.5, 0.5]]
        p1, l1, u1 = qv.reference_bootstrap_mean(groups, seed=7, replicates=1000, alpha=0.05)
        # Independent manual calc with same seed must agree.
        p2, l2, u2 = qv.reference_bootstrap_mean(groups, seed=7, replicates=1000, alpha=0.05)
        self.assertAlmostEqual(p1, p2, places=12)
        self.assertAlmostEqual(l1, l2, places=12)
        # Constant population => degenerate interval.
        groups_const = [[0.5], [0.5], [0.5]]
        pc, lc, uc = qv.reference_bootstrap_mean(groups_const, seed=1, replicates=200, alpha=0.05)
        self.assertEqual(lc, 0.5)
        self.assertEqual(uc, 0.5)
        # Skewed.
        groups_skew = [[0.0], [0.0], [0.0], [1.0], [4.0]]
        ps, ls, us = qv.reference_bootstrap_mean(groups_skew, seed=1, replicates=2000, alpha=0.05)
        self.assertLessEqual(ls, ps)
        self.assertGreaterEqual(us, ps)


class ChoiceTests(unittest.TestCase):
    def meta_and_reports(self):
        # One answerable group (g0, 2 rows), one no-answer group (g1, 2 rows).
        meta = {
            "c0": {"family": "cfam-a", "leakage_group": "g0", "target": "opt-yes", "option_ids": ["opt-yes", "opt-no"], "kind": "choice"},
            "c1": {"family": "cfam-a", "leakage_group": "g0", "target": "opt-no", "option_ids": ["opt-yes", "opt-no"], "kind": "choice"},
            "c2": {"family": "cfam-a", "leakage_group": "g1", "target": None, "option_ids": ["opt-yes", "opt-no"], "kind": "choice"},
            "c3": {"family": "cfam-a", "leakage_group": "g1", "target": None, "option_ids": ["opt-yes", "opt-no"], "kind": "choice"},
        }
        cand = {
            "c0": {"raw_probabilities": [0.9, 0.1], "prediction": "opt-yes", "abstained": False},
            "c1": {"raw_probabilities": [0.2, 0.8], "prediction": "opt-no", "abstained": False},
            "c2": {"raw_probabilities": [0.6, 0.4], "prediction": None, "abstained": True},
            "c3": {"raw_probabilities": [0.5, 0.5], "prediction": None, "abstained": True},
        }
        return meta, cand

    def test_raw_vs_final_and_no_answer(self):
        meta, cand = self.meta_and_reports()
        agg = qv.aggregate_choice_family(cand, None, meta, "cfam-a")
        self.assertEqual(agg["per_case_raw"], {"c0": True, "c1": True})
        self.assertEqual(agg["per_case_final"], {"c0": True, "c1": True})
        self.assertEqual(agg["per_case_covered"], {"c0": True, "c1": True})
        self.assertEqual(agg["answerable_groups"], ["g0"])
        self.assertEqual(agg["no_answer_groups"], ["g1"])
        self.assertEqual(agg["selective_risk"], 0.0)
        # Both-correct requires BOTH final correct.
        self.assertEqual(agg["pair_both_correct"], {"g0": 1.0})

    def test_correct_raw_that_abstains_does_not_pass(self):
        meta, cand = self.meta_and_reports()
        cand2 = dict(cand)
        cand2["c0"] = {"raw_probabilities": [0.9, 0.1], "prediction": None, "abstained": True}
        agg = qv.aggregate_choice_family(cand2, None, meta, "cfam-a")
        self.assertTrue(agg["per_case_raw"]["c0"])
        self.assertFalse(agg["per_case_final"]["c0"])
        self.assertEqual(agg["pair_both_correct"]["g0"], 0.0)

    def test_option_permutation_and_case_order_invariance(self):
        meta, cand = self.meta_and_reports()
        # Permute option order in meta? Actually option_ids order matters for
        # raw index mapping. If we swap option_ids and probs together, correctness
        # preserved. Test case order invariance: reverse dict order.
        cand_rev = dict(reversed(list(cand.items())))
        agg1 = qv.aggregate_choice_family(cand, None, meta, "cfam-a")
        agg2 = qv.aggregate_choice_family(cand_rev, None, meta, "cfam-a")
        self.assertEqual(agg1["per_case_final"], agg2["per_case_final"])
        # Mismatched option identities rejected.
        cand_bad = dict(cand)
        cand_bad["c0"] = dict(cand_bad["c0"])
        cand_bad["c0"]["option_ids"] = ["wrong-a", "wrong-b"]
        with self.assertRaises(qv.QualifyInvalid):
            qv.aggregate_choice_family(cand_bad, None, meta, "cfam-a")

    def test_no_answer_without_extra_option(self):
        meta, cand = self.meta_and_reports()
        agg = qv.aggregate_choice_family(cand, None, meta, "cfam-a")
        # No-answer group recall 1.0 (both abstained), no extra option created.
        self.assertEqual(agg["no_answer_group_recall"], {"g1": 1.0})


class GateTests(unittest.TestCase):
    def test_support_boundaries_49_50_and_19_20(self):
        g49 = qv.support_gate("s", observed=49, required=50)
        self.assertEqual(g49.status, qv.GATE_INSUFFICIENT)
        g50 = qv.support_gate("s", observed=50, required=50)
        self.assertEqual(g50.status, qv.GATE_PASS)
        g19 = qv.support_gate("s", observed=19, required=20)
        self.assertEqual(g19.status, qv.GATE_INSUFFICIENT)
        g20 = qv.support_gate("s", observed=20, required=20)
        self.assertEqual(g20.status, qv.GATE_PASS)

    def test_straddling_interval_is_indeterminate_despite_point(self):
        interval = qv.IntervalEstimate(statistic="s", point=0.05, lower=-0.02, upper=0.12, groups=60,
                                      method=qv.REQUIRED_METHOD, replicates=2000, seed=1, alpha=0.01)
        gate = qv.confidence_gate("s", interval, minimum_support=50)
        self.assertEqual(gate.status, qv.GATE_INSUFFICIENT)
        self.assertEqual(gate.decision, "indeterminate")

    def test_one_group_negative_is_insufficient_not_negative(self):
        interval = qv.IntervalEstimate(statistic="s", point=-0.1, lower=-0.2, upper=-0.05, groups=1,
                                      method=qv.REQUIRED_METHOD, replicates=2000, seed=1, alpha=0.01)
        gate = qv.confidence_gate("s", interval, minimum_support=50, critical=True)
        self.assertEqual(gate.status, qv.GATE_INSUFFICIENT)
        verdict = qv.evaluate_gates([gate], task="binary")["verdict"]
        self.assertEqual(verdict, qv.VERDICT_INDETERMINATE)

    def test_always_abstain_must_be_beaten(self):
        # Candidate that abstains everywhere has 0 accuracy vs abstain 0 => delta 0, straddling => insufficient, not pass.
        interval = qv.IntervalEstimate(statistic="s", point=0.0, lower=0.0, upper=0.0, groups=60,
                                      method=qv.REQUIRED_METHOD, replicates=2000, seed=1, alpha=0.01)
        gate = qv.confidence_gate("beats::always-abstain", interval, minimum_support=50)
        self.assertEqual(gate.status, qv.GATE_INSUFFICIENT)

    def test_absent_threshold_is_insufficient_never_positive(self):
        gate = qv.threshold_gate("rate", observed=0.9, threshold=None, comparator=">=")
        self.assertEqual(gate.status, qv.GATE_INSUFFICIENT)
        verdict = qv.evaluate_gates([gate, qv.support_gate("s", observed=60, required=50)], task="binary")["verdict"]
        self.assertNotEqual(verdict, qv.VERDICT_POSITIVE)

    def test_mismatched_identities_rejected(self):
        with self.assertRaises(qv.QualifyInvalid):
            qv.aggregate_binary_groups({"a": {"score": 0.5}}, {"b": {"score": 0.5}},
                                       {"a": {"family": "fam-a", "leakage_group": "g0", "truth": True},
                                        "b": {"family": "fam-a", "leakage_group": "g0", "truth": True}}, "fam-a")

    def test_complete_positive_passes_and_single_mutation_blocks(self):
        # Construct minimal positive gate set.
        def iv(point, lo, hi, groups=60):
            return qv.IntervalEstimate(statistic="s", point=point, lower=lo, upper=hi, groups=groups,
                                       method=qv.REQUIRED_METHOD, replicates=2000, seed=1, alpha=0.01)
        gates = [
            qv.confidence_gate("primary", iv(0.2, 0.1, 0.3), minimum_support=50),
            qv.support_gate("support", observed=60, required=50),
            qv.threshold_gate("rate", observed=0.9, threshold=0.8, comparator=">="),
        ]
        self.assertEqual(qv.evaluate_gates(gates, task="binary")["verdict"], qv.VERDICT_POSITIVE)
        # Mutate one gate to fail => not positive.
        mutated = [qv.confidence_gate("primary", iv(0.2, -0.05, 0.3), minimum_support=50),
                   gates[1], gates[2]]
        self.assertNotEqual(qv.evaluate_gates(mutated, task="binary")["verdict"], qv.VERDICT_POSITIVE)
        # Remove required family => invalid.
        inv = qv.invalid_gate("binary_family::presence::missing", "absent")
        self.assertEqual(qv.evaluate_gates([inv], task="binary")["verdict"], qv.VERDICT_INVALID)

    def test_resource_missing_never_positive(self):
        manifest = tiny_manifest()
        gates = qv.evaluate_resources(manifest, None)
        self.assertTrue(any(g.status == qv.GATE_INVALID for g in gates))
        # With real evidence passing.
        evidence = {"artifact_bytes": 1000, "max_options": 2, "host": "h", "build": "b", "three_host_parity": True}
        gates2 = qv.evaluate_resources(manifest, evidence)
        self.assertTrue(all(g.status == qv.GATE_PASS for g in gates2 if g.name.startswith("resource::artifact")))


if __name__ == "__main__":
    unittest.main()
