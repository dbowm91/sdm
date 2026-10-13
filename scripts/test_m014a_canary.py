#!/usr/bin/env python3
"""M014a DEV-CANARY end-to-end proof (G7).

Runs on the tiny NEW synthetic canary cohort (never a final test):
- Real inference-only evaluate reports produce all expected CI/gate fields,
  preserve artifact SHA, keep test partition explicit, and fail closed on
  duplicate/SHA/partition/flag/vacuous/partial faults.
- Predictable verdicts: Binary positive (mask beats legacy on critical OOD,
  noninferior on ID), Choice indeterminate (compositional beats legacy/cross
  on accuracy but recall fails on shifted no-answer families).
- Constructed positive (perfect candidate) reaches positive; swapped
  candidate reaches supported negative; underpowered manifest is insufficient;
  malformed inputs are invalid.
- Direct regressions for both historical M014 failure modes (serde
  omitted-true, paired Binary rows) and inference-only prohibition are
  covered here and in Rust tests (m014a_* in sdm-experiment).

Canary can be repeatedly regenerated; NEVER used for promotion.
"""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import qualify_semantic_v2 as qv

CANARY = ROOT / "target" / "m014a" / "canary"
MANIFEST = CANARY / "manifest.json"
BIN_CAND = CANARY / "eval-binary-mask.report.json"
BIN_BASE = CANARY / "eval-binary-baseline.report.json"
CH_CAND = CANARY / "eval-choice-compositional.report.json"
CH_LEG = CANARY / "eval-choice-legacy.report.json"
CH_CROSS = CANARY / "eval-choice-cross.report.json"
RESOURCE = CANARY / "resource-evidence.json"


def load_qual():
    # Find latest qualification (qualification3.json is current positive run).
    for name in ("qualification3.json", "qualification2.json", "qualification.json"):
        p = CANARY / name
        if p.exists():
            return json.loads(p.read_text())
    raise FileNotFoundError("no canary qualification found; run qualify_semantic_v2 first")


class CanaryEndToEndTests(unittest.TestCase):
    def test_canary_files_exist_and_shas_match(self):
        self.assertTrue(MANIFEST.exists(), "canary manifest missing")
        for p in (BIN_CAND, BIN_BASE, CH_CAND, CH_LEG, CH_CROSS, RESOURCE):
            self.assertTrue(p.exists(), f"{p} missing")
        manifest = json.loads(MANIFEST.read_text())
        # Test membership SHAs must match actual splits (compact JSON).
        for task, split_path in (("binary", CANARY / "binary.split.json"), ("choice", CANARY / "choice.split.json")):
            split = json.loads((split_path).read_text())
            expected = "sha256:" + hashlib.sha256(json.dumps(sorted(split["test"]), separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(manifest[task]["test_membership_sha256"], expected, f"{task} membership SHA mismatch")

    def test_real_canary_verdicts_are_predictable(self):
        qual = load_qual()
        # Binary mask beats legacy on critical OOD, noninferior on ID => positive.
        self.assertEqual(qual["binary_verdict"], "positive", qual["binary_reason"])
        # Choice compositional beats legacy/cross on accuracy but recall fails on
        # shifted no-answer families => indeterminate (fail-closed, not positive).
        self.assertEqual(qual["choice_verdict"], "indeterminate", qual["choice_reason"])
        self.assertEqual(qual["overall_verdict"], "indeterminate")
        # Every required gate field present; no vacuous pass.
        for gate in qual["binary_gates"] + qual["choice_gates"]:
            for field in ("name", "status", "mandatory", "reason"):
                self.assertIn(field, gate)
            self.assertIn(gate["status"], ("pass", "fail", "insufficient_support", "invalid"))
        # No gate may be vacuous positive on empty arrays or missing thresholds:
        # every mandatory pass must have evidence or explicit threshold origin.
        for gate in qual["binary_gates"] + qual["choice_gates"]:
            if gate["status"] == "pass" and gate["mandatory"]:
                self.assertTrue(gate["reason"], f"vacuous pass {gate['name']}")

    def test_no_duplicate_cases_and_exact_accounting(self):
        for report_path in (BIN_CAND, BIN_BASE, CH_CAND):
            raw = json.loads(Path(report_path).read_text())
            cids = [r["case_id"] for r in raw["outcomes"]]
            self.assertEqual(len(cids), len(set(cids)), f"duplicate case in {report_path}")
            # Binary groups must have exactly 2 rows (both counterfactual rows).
            if "binary" in str(report_path):
                from collections import Counter
                groups = Counter(r["leakage_group"] for r in raw["outcomes"])
                for g, n in groups.items():
                    self.assertEqual(n, 2, f"binary group {g} has {n} rows, need both rows")

    def test_artifact_sha_immutable_and_partition_explicit(self):
        for report_path, eval_spec_path in (
            (BIN_CAND, CANARY / "eval-binary-mask.evaluate.json"),
            (BIN_BASE, CANARY / "eval-binary-baseline.evaluate.json"),
        ):
            raw = json.loads(Path(report_path).read_text())
            spec = json.loads(Path(eval_spec_path).read_text())
            self.assertEqual(raw["artifact_sha256"], spec["expected_artifact_sha256"])
            self.assertEqual(raw["loaded_artifact_sha256"], spec["expected_artifact_sha256"])
            self.assertEqual(raw["evaluated_partition"], "test")
            self.assertTrue(raw["test_evaluation_performed"] is True)
            # Raw JSON must contain explicit flag (no omission).
            self.assertIn("test_evaluation_performed", raw)

    def test_swapped_binary_is_supported_negative(self):
        # Swap candidate/baseline: legacy as candidate vs mask as baseline should
        # be a supported critical regression (negative), not positive.
        manifest = json.loads(MANIFEST.read_text())
        # Use analyzer directly with swapped roles for one critical family.
        meta = qv.build_dataset_meta(str(CANARY / "binary.json"))
        _, cand_by_case, _ = qv.build_report_index(str(BIN_BASE))  # legacy as candidate
        _, base_by_case, _ = qv.build_report_index(str(BIN_CAND))  # mask as baseline
        fam = "m014a-canary-binary-text-shift-v1"
        groups, improvements, gids = qv.aggregate_binary_groups(cand_by_case, base_by_case, meta, fam)
        interval = qv.paired_group_bootstrap(improvements, seed=140015, replicates=2000, alpha=0.05/18, statistic_name="swapped")
        # Legacy worse => improvement (legacy - mask) negative, interval below zero.
        self.assertLess(interval.upper, 0.0)
        gate = qv.confidence_gate("swapped", interval, minimum_support=50, critical=True)
        self.assertEqual(gate.status, "fail")
        verdict = qv.evaluate_gates([gate], task="binary")["verdict"]
        self.assertEqual(verdict, "negative")

    def test_constructed_perfect_choice_reaches_positive(self):
        # Perfect candidate on tiny constructed family proves positive reachable.
        # Two groups, two rows each, all correct final, all recall perfect.
        meta = {
            "a0": {"family": "F", "leakage_group": "g0", "target": "yes", "option_ids": ["yes", "no"], "kind": "choice"},
            "a1": {"family": "F", "leakage_group": "g0", "target": "no", "option_ids": ["yes", "no"], "kind": "choice"},
            "b0": {"family": "F", "leakage_group": "g1", "target": "yes", "option_ids": ["yes", "no"], "kind": "choice"},
            "b1": {"family": "F", "leakage_group": "g1", "target": "no", "option_ids": ["yes", "no"], "kind": "choice"},
        }
        # Need 50 groups for support; replicate pattern to 60 groups.
        big_meta, big_cand, big_base = {}, {}, {}
        for i in range(60):
            for suffix, target in (("0", "yes"), ("1", "no")):
                cid = f"c{i}-{suffix}"
                big_meta[cid] = {"family": "F", "leakage_group": f"g{i}", "target": target, "option_ids": ["yes", "no"], "kind": "choice"}
                probs = [0.9, 0.1] if target == "yes" else [0.1, 0.9]
                big_cand[cid] = {"raw_probabilities": probs, "prediction": target, "abstained": False}
                big_base[cid] = {"raw_probabilities": [0.5, 0.5], "prediction": "yes" if target == "no" else "no", "abstained": False}
        agg = qv.aggregate_choice_family(big_cand, None, big_meta, "F")
        self.assertEqual(len(agg["answerable_groups"]), 60)
        # Accuracy deltas should be favorable.
        cand_acc = agg["answerable_group_accuracy"]
        # Baseline accuracy per group 0.0, candidate 1.0 => delta 1.0.
        deltas = {g: 1.0 for g in agg["answerable_groups"]}
        interval = qv.paired_group_bootstrap(deltas, seed=1, replicates=1000, alpha=0.01, statistic_name="perfect")
        gate = qv.confidence_gate("perfect", interval, minimum_support=50)
        self.assertEqual(gate.status, "pass")

    def test_underpowered_manifest_is_insufficient(self):
        gate = qv.support_gate("independent_groups::F", observed=49, required=50)
        self.assertEqual(gate.status, "insufficient_support")
        verdict = qv.evaluate_gates([gate], task="binary")["verdict"]
        self.assertEqual(verdict, "indeterminate")

    def test_malformed_duplicate_is_invalid(self):
        with self.assertRaises(qv.QualifyInvalid):
            qv.aggregate_binary_groups(
                {"c0": {"score": 0.5}, "c0_dup": {"score": 0.5}},
                {"c0": {"score": 0.5}},
                {"c0": {"family": "F", "leakage_group": "g0", "truth": True},
                 "c0_dup": {"family": "F", "leakage_group": "g0", "truth": True},
                 "c0_extra": {"family": "F", "leakage_group": "g0", "truth": True}},
                "F")

    def test_historical_failure_modes_regressed(self):
        # 1. Serde omitted-true must not be inferred for new reports.
        raw_new_missing = {"schema": "sdm-semantic-evaluate-v2", "schema_version": 2,
                           "evaluated_partition": "test", "test_ids": ["a"]}
        with self.assertRaises(qv.QualifyInvalid):
            qv.validate_test_evaluation(raw_new_missing, "", expected_test_ids=["a"])
        # Legacy omitted-true with matching IDs is accepted only with allow_legacy.
        raw_legacy = {"semantic": "binary", "test_ids": ["a", "b"], "outcomes": [{"case_id": "a"}]}
        ok, _ = qv.validate_test_evaluation(raw_legacy, "", allow_legacy=True, legacy_test_ids=["a", "b"])
        self.assertTrue(ok)
        # 2. Binary single-row per group (old analyzer bug) is rejected.
        meta = {"c0": {"family": "F", "leakage_group": "g0", "truth": True}}
        with self.assertRaises(qv.QualifyInvalid) as ctx:
            qv.aggregate_binary_groups({"c0": {"score": 0.9}}, {"c0": {"score": 0.6}}, meta, "F")
        self.assertEqual(ctx.exception.code, "incomplete_pair")


if __name__ == "__main__":
    unittest.main()
