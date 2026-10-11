#!/usr/bin/env python3
"""Pre-freeze support validator for FUTURE protocols (M013c and later).

Distinct from `scripts/validate_m013a_freeze.py`, which is a hash-only guard for
exact frozen history. This validator checks that every preregistered metric's
ELIGIBLE population meets its support requirement *independently*, before any
final inference is run.

The M013a defect this exists to prevent: three Choice OOD accuracy slices had
67, 67 and 66 total groups, which clears a naive 50-group check, but only 44, 44
and 45 answerable groups, which does not clear the preregistered 50-answerable-
group requirement for an accuracy metric.

This validator NEVER reclassifies an already-frozen cohort. It refuses to score
any dataset whose identity is in the frozen M013a ledger, so a historical freeze
can never be silently revalidated under future, stricter rules.

Usage:
    python3 scripts/validate_future_support.py --dataset fixtures/x.json \\
        --split fixtures/x.split.json --task choice \\
        --required-family m013c-choice-load-shift-v1 --out target/m013b/x.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m013b_audit_m013a import atomic_write_json  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

#: Datasets whose support was already judged under the M013a rules. Applying a
#: future, stricter validator to them would retroactively reclassify frozen
#: history, which this repository forbids.
FROZEN_HISTORY = {
    "sha256:52189cafbe52f5dbca66f286257cf91a5c961e06029e8a92a5013ee46257e586": "m013a choice corpus",
    "sha256:edc857be6cc0b06e21b81df77f62a4bc261befa6f7adc58abf4788e6b842c1da": "m013a binary corpus",
}

DEFAULT_MIN_ANSWERABLE_GROUPS = 50
DEFAULT_MIN_NO_ANSWER_GROUPS = 20
DEFAULT_MIN_INDEPENDENT_GROUPS = 50


def support_report(
    examples,
    split,
    *,
    task: str,
    required_families,
    min_answerable_groups: int,
    min_no_answer_groups: int,
    min_independent_groups: int,
) -> dict:
    by_case = {e["case_id"]: e for e in examples}
    missing = [case_id for part in ("train", "dev", "test", "excluded") for case_id in split[part] if case_id not in by_case]
    if missing:
        raise ValueError(f"split references {len(missing)} unknown case ids, e.g. {missing[:3]}")

    parts = {name: set(split[name]) for name in ("train", "dev", "test", "excluded")}
    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        if parts[left] & parts[right]:
            raise ValueError(f"case split overlaps between {left} and {right}")
    for name in ("train", "dev", "test"):
        for case_id in parts[name]:
            family = by_case[case_id]["family"]
            if family in required_families and name != "test":
                raise ValueError(f"required family {family} appears outside the test split ({name})")

    slices = {}
    failures = []
    for family in required_families:
        rows = [by_case[case_id] for case_id in parts["test"] if by_case[case_id]["family"] == family]
        if not rows:
            failures.append(f"{family}: no test rows")
            slices[family] = {"status": "invalid", "reason": "no test rows"}
            continue
        answerable = [r for r in rows if r["label"]["value"] is not None]
        no_answer = [r for r in rows if r["label"]["value"] is None]
        independent = len({r["leakage_group"] for r in rows})
        answerable_groups = len({r["leakage_group"] for r in answerable})
        no_answer_groups = len({r["leakage_group"] for r in no_answer})

        # Support is asserted per metric, in that metric's own eligible population.
        checks = [
            ("independent_groups", independent, min_independent_groups, True),
            ("answerable_groups", answerable_groups, min_answerable_groups, task == "choice"),
            ("no_answer_groups", no_answer_groups, min_no_answer_groups, task == "choice" and bool(no_answer)),
        ]
        entry = {
            "test_rows": len(rows),
            "independent_groups": independent,
            "answerable_groups": answerable_groups,
            "no_answer_groups": no_answer_groups,
            "checks": {},
        }
        for name, observed, required, applies in checks:
            if not applies:
                continue
            ok = observed >= required
            entry["checks"][name] = {"observed": observed, "required": required, "status": "pass" if ok else "insufficient_support"}
            if not ok:
                failures.append(f"{family}: {name}={observed} < required {required}")
        entry["status"] = "pass" if all(c["status"] == "pass" for c in entry["checks"].values()) else "insufficient_support"
        entry["note"] = (
            "total slice groups are NOT a substitute for the eligible population of a given metric; "
            "an accuracy metric requires answerable groups"
        )
        slices[family] = entry

    return {
        "task": task,
        "required_families": list(required_families),
        "thresholds": {
            "min_independent_groups": min_independent_groups,
            "min_answerable_groups": min_answerable_groups if task == "choice" else None,
            "min_no_answer_groups": min_no_answer_groups if task == "choice" else None,
        },
        "slices": slices,
        "failures": failures,
        "verdict": "pass" if not failures else "insufficient_support",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Pre-freeze eligible-subgroup support validator")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--task", required=True, choices=("choice", "binary"))
    parser.add_argument("--required-family", action="append", default=[])
    parser.add_argument("--min-independent-groups", type=int, default=DEFAULT_MIN_INDEPENDENT_GROUPS)
    parser.add_argument("--min-answerable-groups", type=int, default=DEFAULT_MIN_ANSWERABLE_GROUPS)
    parser.add_argument("--min-no-answer-groups", type=int, default=DEFAULT_MIN_NO_ANSWER_GROUPS)
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    dataset_path = Path(args.dataset)
    split_path = Path(args.split)
    raw = dataset_path.read_bytes()
    import hashlib

    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if digest in FROZEN_HISTORY:
        raise SystemExit(
            f"refusing to revalidate frozen history ({FROZEN_HISTORY[digest]}) under future support rules; "
            "use scripts/validate_m013a_freeze.py for that cohort"
        )

    bundle = json.loads(raw)
    split = json.loads(split_path.read_text())
    report = support_report(
        bundle["examples"],
        split,
        task=args.task,
        required_families=args.required_family,
        min_answerable_groups=args.min_answerable_groups,
        min_no_answer_groups=args.min_no_answer_groups,
        min_independent_groups=args.min_independent_groups,
    )
    report["dataset"] = str(dataset_path)
    report["dataset_sha256"] = digest
    report["policy"] = (
        "Pre-inference only. Passing this check does not qualify a model; it only establishes that each "
        "preregistered metric will have the support its own threshold requires."
    )
    if args.out:
        atomic_write_json(Path(args.out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())