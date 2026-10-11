#!/usr/bin/env python3
"""Tests for the future-only pre-freeze support validator.

These use constructed fixtures. They never reclassify frozen M013a history: the
validator must refuse that outright, and this suite asserts it does.

Run with:
    python3 -m unittest discover -s scripts -p 'test_m013b_*.py'
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_future_support import FROZEN_HISTORY, main, support_report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _example(case_id: str, group: str, family: str, target):
    return {
        "case_id": case_id,
        "leakage_group": group,
        "counterfactual_pair": f"pair-{group}",
        "family": family,
        "request": {"request_id": case_id, "spec": {"kind": "choice", "options": []}},
        "label": {"kind": "choice", "value": target},
    }


def _corpus(answerable_per_family: int, no_answer_per_family: int):
    """Construct a test split with a precise answerable/no-answer group mix."""
    examples = []
    split = {"train": [], "dev": [], "test": [], "excluded": []}
    for family_index, family in enumerate(("fam-a", "fam-b")):
        for index in range(answerable_per_family):
            group = f"{family}-g{index}"
            case_id = f"{family}-a{index}"
            examples.append(_example(case_id, group, family, "alpha"))
            split["test"].append(case_id)
        for index in range(no_answer_per_family):
            group = f"{family}-g{answerable_per_family + index}"
            case_id = f"{family}-n{index}"
            examples.append(_example(case_id, group, family, None))
            split["test"].append(case_id)
    for index in range(4):
        case_id = f"train-{index}"
        examples.append(_example(case_id, f"train-g{index}", "train-family", "alpha"))
        split["train"].append(case_id)
    return {"provenance": {}, "examples": examples}, split


class SupportValidatorTests(unittest.TestCase):
    def _report(self, answerable, no_answer, **kwargs):
        bundle, split = _corpus(answerable, no_answer)
        options = dict(
            task="choice",
            required_families=("fam-a", "fam-b"),
            min_answerable_groups=50,
            min_no_answer_groups=20,
            min_independent_groups=50,
        )
        options.update(kwargs)
        return support_report(bundle["examples"], split, **options)

    def test_sufficient_support_passes(self):
        report = self._report(60, 25)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["failures"], [])

    def test_total_groups_cannot_substitute_for_answerable_support(self):
        """The exact M013a defect: many total groups, too few answerable."""
        report = self._report(44, 23)
        self.assertEqual(report["verdict"], "insufficient_support")
        for family in ("fam-a", "fam-b"):
            checks = report["slices"][family]["checks"]
            self.assertEqual(checks["independent_groups"]["observed"], 67)
            self.assertEqual(checks["independent_groups"]["status"], "pass")
            self.assertEqual(checks["answerable_groups"]["observed"], 44)
            self.assertEqual(checks["answerable_groups"]["status"], "insufficient_support")
            self.assertEqual(checks["no_answer_groups"]["status"], "pass")

    def test_exact_answerable_boundary(self):
        self.assertEqual(self._report(50, 20)["verdict"], "pass")
        self.assertEqual(self._report(49, 20)["verdict"], "insufficient_support")
        self.assertEqual(self._report(50, 19)["verdict"], "insufficient_support")

    def test_binary_task_does_not_require_answerable_support(self):
        bundle, split = _corpus(60, 0)
        for example in bundle["examples"]:
            example["label"] = {"kind": "binary", "value": bool(len(example["leakage_group"]) % 2)}
        report = support_report(
            bundle["examples"],
            split,
            task="binary",
            required_families=("fam-a", "fam-b"),
            min_answerable_groups=50,
            min_no_answer_groups=20,
            min_independent_groups=50,
        )
        self.assertEqual(report["verdict"], "pass")
        self.assertNotIn("answerable_groups", report["slices"]["fam-a"]["checks"])

    def test_required_family_outside_test_split_is_rejected(self):
        bundle, split = _corpus(60, 25)
        with self.assertRaises(ValueError):
            support_report(
                bundle["examples"],
                split,
                task="choice",
                required_families=("train-family",),
                min_answerable_groups=50,
                min_no_answer_groups=20,
                min_independent_groups=50,
            )

    def test_missing_required_family_is_invalid(self):
        bundle, split = _corpus(60, 25)
        report = support_report(
            bundle["examples"],
            split,
            task="choice",
            required_families=("fam-a", "missing-family"),
            min_answerable_groups=50,
            min_no_answer_groups=20,
            min_independent_groups=50,
        )
        self.assertEqual(report["verdict"], "insufficient_support")
        self.assertEqual(report["slices"]["missing-family"]["status"], "invalid")

    def test_split_overlap_is_rejected(self):
        bundle, split = _corpus(60, 25)
        split["dev"].append(split["test"][0])
        with self.assertRaises(ValueError):
            support_report(
                bundle["examples"],
                split,
                task="choice",
                required_families=("fam-a",),
                min_answerable_groups=50,
                min_no_answer_groups=20,
                min_independent_groups=50,
            )

    def test_unknown_case_id_is_rejected(self):
        bundle, split = _corpus(60, 25)
        split["test"].append("not-in-corpus")
        with self.assertRaises(ValueError):
            support_report(
                bundle["examples"],
                split,
                task="choice",
                required_families=("fam-a",),
                min_answerable_groups=50,
                min_no_answer_groups=20,
                min_independent_groups=50,
            )

    def test_frozen_history_is_never_reclassified(self):
        """The real M013a corpus must be refused, not silently revalidated."""
        with self.assertRaises(SystemExit) as ctx:
            main(
                [
                    "--dataset",
                    str(ROOT / "fixtures/m013a-choice-v1.json"),
                    "--split",
                    str(ROOT / "fixtures/m013a-choice-v1.split.json"),
                    "--task",
                    "choice",
                    "--required-family",
                    "m013a-choice-load-shift-v1",
                ]
            )
        self.assertIn("frozen history", str(ctx.exception))
        self.assertEqual(len(FROZEN_HISTORY), 2)

    def test_cli_end_to_end_on_a_constructed_future_dataset(self):
        bundle, split = _corpus(60, 25)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            dataset = base / "future.json"
            split_file = base / "future.split.json"
            dataset.write_text(json.dumps(bundle))
            split_file.write_text(json.dumps(split))
            out = base / "support.json"
            code = main(
                [
                    "--dataset",
                    str(dataset),
                    "--split",
                    str(split_file),
                    "--task",
                    "choice",
                    "--required-family",
                    "fam-a",
                    "--required-family",
                    "fam-b",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(code, 0)
            written = json.loads(out.read_text())
            self.assertEqual(written["verdict"], "pass")
            digest = "sha256:" + hashlib.sha256(dataset.read_bytes()).hexdigest()
            self.assertEqual(written["dataset_sha256"], digest)
            self.assertNotIn(digest, FROZEN_HISTORY)


if __name__ == "__main__":
    unittest.main()