import importlib.util
import tempfile
import unittest
from pathlib import Path
import sys

SCRIPT = Path(__file__).with_name("generate_m015_suite.py")
SPEC = importlib.util.spec_from_file_location("generate_m015_suite", SCRIPT)
m015 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m015)
sys.path.insert(0, str(SCRIPT.parent))
from analyze_m015_dev import score_rows


class M015SuiteTests(unittest.TestCase):
    def test_independent_oracle_truth_tables(self):
        c = {"alpha": True, "beta": False, "capacity": 7, "kind": "primary", "enabled": True}
        cases = {
            "all_required": ({"features": ["alpha", "beta"]}, False),
            "any_required": ({"features": ["alpha", "beta"]}, True),
            "exclusive": ({"features": ["alpha", "beta"]}, True),
            "threshold": ({"feature": "capacity", "minimum": 5}, True),
            "category_and_flag": ({"category_feature": "kind", "category": "primary", "flag_feature": "enabled"}, True),
        }
        for name, (operands, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(m015.rule_label({"name": name, "operands": operands}, {}, c), expected)

    def test_unknown_or_malformed_rule_fails_closed(self):
        for rule in ({"name": "typo", "operands": {}}, {"name": "threshold", "operands": {}}, {"name": "all_required", "operands": {"features": ["alpha"], "fallback": True}}):
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                m015.rule_label(rule, {}, {"alpha": True})

    def test_hidden_rule_change_is_unidentifiable(self):
        context = {"available": True}
        candidate = {"alpha": True, "beta": False}
        and_rule = {"name": "all_required", "operands": {"features": ["alpha", "beta"]}}
        or_rule = {"name": "any_required", "operands": {"features": ["alpha", "beta"]}}
        # Same observed causal values, contradictory target when the rule selector is hidden.
        self.assertNotEqual(m015.rule_label(and_rule, context, candidate), m015.rule_label(or_rule, context, candidate))

    def test_cardinality_and_answerability_support(self):
        counts = {len(m015.make_group(i, 7)[0]["options"]) for i in range(100)}
        self.assertTrue(counts.issubset(set(range(2, 9))))
        self.assertIn(2, counts)
        self.assertIn(8, counts)
        self.assertTrue(any(m015.make_group(i, 7)[0]["label"] is None for i in range(20)))

    def test_generated_pairs_are_oracle_correct_and_grouped(self):
        for group in range(200):
            rows = m015.make_group(group, 1234)
            self.assertEqual(rows[0]["group_id"], rows[1]["group_id"])
            self.assertEqual(rows[0]["split"], rows[1]["split"])
            self.assertNotEqual([o["id"] for o in rows[0]["options"]], [o["id"] for o in rows[1]["options"]])
            self.assertEqual({r["rule"]["name"] for r in rows}, {rows[0]["rule"]["name"]})
            for row in rows:
                matches = [o["id"] for o in row["options"] if m015.rule_label(row["rule"], row["context"], o["semantics"])]
                self.assertEqual(row["label"], matches[0] if row["context"]["available"] and matches else None)
                self.assertIn(len(row["options"]), range(2, 9))

    def test_generation_is_deterministic_and_refuses_different_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            manifest = m015.generate(out, 2_000, 991)
            self.assertEqual(m015.generate(out, 2_000, 991), manifest)
            with self.assertRaises(FileExistsError):
                m015.generate(out, 2_000, 992)

    def test_group_split_has_no_crossing(self):
        for group in range(100):
            rows = m015.make_group(group, 44)
            self.assertEqual(len({row["split"] for row in rows}), 1)
        self.assertEqual(m015.make_group(0, 44)[0]["split"], "dev")
        self.assertEqual(m015.make_group(5, 44)[0]["split"], "train")

    def test_dev_analyzer_checks_oracle_and_leakage(self):
        groups = [m015.make_group(i, 33) for i in range(20)]
        train = [row for pair in groups for row in pair if row["split"] == "train"]
        dev = [row for pair in groups for row in pair if row["split"] == "dev"]
        report = score_rows(train, dev)
        self.assertEqual(report["oracle_disagreements"], 0)
        self.assertEqual(report["dev_groups"], 5)
        leaked = dict(dev[0]); leaked["split"] = "train"
        with self.assertRaises(ValueError):
            score_rows(train + [leaked], dev)


if __name__ == "__main__":
    unittest.main()
