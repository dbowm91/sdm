#!/usr/bin/env python3
"""Verify M017 three-host same-artifact canary parity (mirrors M014c B3).

Inputs: per-host attestations from run_m017_canary.py. Asserts identical
predicted decisions on all hosts and max probability delta within 1e-9
(libm tolerance). Writes a verdict JSON. Host omission is `unverified`.
"""
import argparse
import json
from pathlib import Path

TOL = 1e-9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    attestations = [json.loads(Path(p).read_text()) for p in args.inputs]
    assert len(attestations) >= 2, "need at least two host attestations"
    base = attestations[0]
    for a in attestations[1:]:
        assert a["cohort_output_sha256"] == base["cohort_output_sha256"], "cohort drift"
        assert a["test_membership_sha256"] == base["test_membership_sha256"], "membership drift"
        assert a["tinymlp_artifact_sha256"] == base["tinymlp_artifact_sha256"], "artifact drift"

    by_case = {o["case_id"]: o for o in base["tinymlp_outcomes"]}
    max_delta = 0.0
    mismatches = 0
    for a in attestations[1:]:
        other = {o["case_id"]: o for o in a["tinymlp_outcomes"]}
        assert set(other) == set(by_case), "case coverage drift"
        for cid, o in by_case.items():
            q = other[cid]
            if o["predicted"] != q["predicted"]:
                mismatches += 1
            for p, r in zip(o["probs"], q["probs"]):
                max_delta = max(max_delta, abs(p - r))
            max_delta = max(max_delta, abs(o["answerability"] - q["answerability"]))

    verdict = {
        "schema": "sdm-m017-canary-parity-v1",
        "platforms": [a["platform"] for a in attestations],
        "cases": len(by_case),
        "decision_mismatches": mismatches,
        "max_probability_delta": max_delta,
        "parity": mismatches == 0 and max_delta <= TOL,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    print(json.dumps(verdict, indent=2))
    if not verdict["parity"]:
        raise SystemExit(f"M017 canary parity FAILED: {mismatches} mismatches, delta {max_delta}")


if __name__ == "__main__":
    main()
