"""Constructed M014 generator and leakage-integrity regressions."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_m014_synthetic_suite as gen
import analyze_m014_qualification as analysis


class M014SuiteTests(unittest.TestCase):
    def source(self):
        bundle = json.loads((ROOT / "fixtures/synthetic-choice-typed-v1.json").read_text())
        source = copy.deepcopy(bundle["examples"][0])
        for option in source["request"]["spec"]["options"]:
            option["id"] = option["label"].lower().replace(" ", "-")
        gen.add_rule_feature(source)
        return source

    def test_rule_families_have_source_defined_opposite_active_mappings(self):
        source = self.source()
        # Odd group => rule_b, available, and rule_b selects yes for inactive.
        inactive = gen.make_example("choice", 803, False, source)
        active = gen.make_example("choice", 803, True, source)
        self.assertEqual(inactive["label"]["value"], next(iter(inactive["typed_rank_features"]["candidates"])))
        self.assertNotEqual(inactive["label"]["value"], active["label"]["value"])
        self.assertEqual(gen.normalized_pair(inactive), gen.normalized_pair(active))

    def test_test_families_are_group_complete_and_distinct_from_training_families(self):
        self.assertEqual(gen.family(0), "train-id-a")
        self.assertEqual(gen.family(300), "train-id-b")
        self.assertEqual(gen.family(600), "id-a")
        self.assertEqual(gen.family(700), "id-b")
        self.assertEqual([gen.family(i * 100 + 800) for i in range(4)], list(gen.TEST_FAMILIES))
        self.assertEqual(len(gen.TEST_FAMILIES), 4)

    def test_rule_and_nuisance_values_are_fixed_within_group(self):
        source = self.source()
        left = gen.make_example("choice", 1004, False, source)
        right = gen.make_example("choice", 1004, True, source)
        self.assertEqual(left["leakage_group"], right["leakage_group"])
        self.assertEqual(left["counterfactual_pair"], right["counterfactual_pair"])
        self.assertEqual(gen.normalized_pair(left), gen.normalized_pair(right))
        self.assertNotEqual(left["label"]["value"], right["label"]["value"])

    def test_bootstrap_resamples_whole_groups_and_is_seeded(self):
        groups = {f"g{i}": [float(i), float(i + 1)] for i in range(12)}
        stat = lambda values: sum(x[1] - x[0] for x in values) / len(values)
        first = analysis.bootstrap(groups, stat, 140015, replicates=300)
        second = analysis.bootstrap(groups, stat, 140015, replicates=300)
        self.assertEqual(first, second)
        self.assertEqual(first["groups"], 12)
        self.assertEqual(first["estimate"], 1.0)

    def test_answerable_top1_is_scored_even_when_decision_abstains(self):
        self.assertTrue(analysis.choice_top1_correct("yes-id", ["yes-id", "no-id"], [0.9, 0.1]))
        self.assertFalse(analysis.choice_top1_correct("yes-id", ["yes-id", "no-id"], [0.2, 0.8]))


if __name__ == "__main__":
    unittest.main()
