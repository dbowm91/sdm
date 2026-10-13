#!/usr/bin/env python3
"""M014c three-host parity aggregator (Work B).

Downloads (as CI artifacts) the three per-host attestation JSON files,
verifies exact expected platforms, head/source/model SHA and case-set
equality, then compares ACTUAL decisions by fixed case and candidate identity.

- Requires exactly three attestations with platforms
  {linux-x86_64, linux-aarch64, macos-aarch64}. Missing/duplicate host blocks pass.
- Requires identical source_commit across hosts (same exact commit).
- Requires identical test-membership/dataset/split SHAs (deterministic generation).
- Records parity artifact SHAs per host (in --parity mode these are SAME
  committed bytes; in default mode retrained canary bytes); if they differ,
  reports artifact divergence separately (never compare independently
  retrained floats as parity without flagging). Committed artifact SHAs must
  match exactly.
- Compares actual decisions: for each case_id, prediction and abstained must
  match exactly across hosts. Numerical probability/logit tolerances are
  recorded separately (f64) but NEVER allow a changed selected action/
  abstention to pass under float tolerance.
- Host-specific timings/RSS are labeled as such and never compared.

A single-host locally generated JSON can never satisfy parity (requires 3).

Usage:
  python3 scripts/verify_m014c_parity.py --inputs a.json b.json c.json --out parity-verdict.json

Exit 0 on parity pass, 2 on divergence (with minimal reproducible difference),
1 on malformed/missing input.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

EXPECTED_PLATFORMS = ("linux-x86_64", "linux-aarch64", "macos-aarch64")
PROB_TOL = 1e-9


def load(p: Path) -> dict:
    return json.loads(p.read_text())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="M014c parity aggregator")
    ap.add_argument("--inputs", nargs="+", required=True, help="three attestation JSON paths")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prob-tol", type=float, default=PROB_TOL)
    args = ap.parse_args(argv)

    if len(args.inputs) != 3:
        print(json.dumps({"error": "parity requires exactly three host attestations",
                          "got": len(args.inputs)}))
        return 1

    atts = [load(Path(p)) for p in args.inputs]

    # Platform check.
    platforms = sorted(a.get("platform") for a in atts)
    if platforms != sorted(EXPECTED_PLATFORMS):
        result = {"verdict": "fail", "reason": f"platform set {platforms} != expected {sorted(EXPECTED_PLATFORMS)}",
                  "platforms": platforms, "expected": sorted(EXPECTED_PLATFORMS)}
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, sort_keys=True))
        return 2
    # Duplicate host check (platforms unique already implies distinct, but also
    # check attestation SHAs distinct? Same content on different hosts would give
    # same attestation SHA except host_detail/build differ, so SHAs differ. Just
    # check platforms unique.)
    if len(set(platforms)) != 3:
        result = {"verdict": "fail", "reason": f"duplicate platform in {platforms}"}
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, sort_keys=True))
        return 2

    # Source commit equality.
    commits = {a.get("source_commit") for a in atts}
    if len(commits) != 1 or "unknown" in commits:
        result = {"verdict": "fail", "reason": f"source_commit mismatch or unknown: {sorted(commits)}",
                  "source_commits": sorted(commits)}
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, sort_keys=True))
        return 2
    source_commit = next(iter(commits))

    # Dataset/split/membership equality.
    for key in ("binary_test_membership_sha256", "choice_test_membership_sha256",
                "binary_dataset_sha256", "choice_dataset_sha256",
                "binary_split_fingerprint", "choice_split_fingerprint",
                "manifest_id", "evaluator_sha256"):
        vals = {a.get(key) for a in atts}
        if len(vals) != 1:
            result = {"verdict": "fail", "reason": f"input/case mismatch: {key} differs {sorted(str(v)[:24] for v in vals)}",
                      "key": key, "values": sorted(str(v) for v in vals)}
            Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(json.dumps(result, sort_keys=True))
            return 2

    # Committed artifact SHAs must match exactly (same bytes on all hosts).
    committed_keys = set()
    for a in atts:
        committed_keys.update(a.get("committed_artifact_sha256", {}).keys())
    for rel in sorted(committed_keys):
        vals = {a.get("committed_artifact_sha256", {}).get(rel) for a in atts}
        if len(vals) != 1:
            result = {"verdict": "fail", "reason": f"committed artifact {rel} SHA differs across hosts",
                      "values": sorted(str(v) for v in vals)}
            Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(json.dumps(result, sort_keys=True))
            return 2

    # Canary-trained artifact SHAs: record per-host ledger. If they differ,
    # report artifact divergence explicitly (retraining nondeterminism), not
    # silent parity. Require match for parity pass (deterministic-canonical).
    canary_ledger = {}
    artifact_divergence = []
    canary_names = set()
    for a in atts:
        canary_names.update(a.get("canary_artifact_sha256", {}).keys())
    for name in sorted(canary_names):
        per_host = {a["platform"]: a.get("canary_artifact_sha256", {}).get(name) for a in atts}
        canary_ledger[name] = per_host
        if len(set(per_host.values())) != 1:
            artifact_divergence.append({"artifact": name, "per_host": per_host})

    # Case-set equality.
    ref_bin_ids = [c["case_id"] for c in atts[0]["binary_cases"]]
    ref_ch_ids = [c["case_id"] for c in atts[0]["choice_cases"]]
    for a in atts[1:]:
        got_bin = [c["case_id"] for c in a["binary_cases"]]
        got_ch = [c["case_id"] for c in a["choice_cases"]]
        if got_bin != ref_bin_ids:
            result = {"verdict": "fail", "reason": f"binary case-set mismatch on {a['platform']}",
                      "expected_count": len(ref_bin_ids), "got_count": len(got_bin)}
            Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(json.dumps(result, sort_keys=True))
            return 2
        if got_ch != ref_ch_ids:
            result = {"verdict": "fail", "reason": f"choice case-set mismatch on {a['platform']}",
                      "expected_count": len(ref_ch_ids), "got_count": len(got_ch)}
            Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(json.dumps(result, sort_keys=True))
            return 2

    # Decision comparison: exact match on prediction/abstained.
    divergences = []
    max_prob_delta = 0.0
    # Index by case_id.
    for task in ("binary_cases", "choice_cases"):
        ref = {c["case_id"]: c for c in atts[0][task]}
        for other in atts[1:]:
            for cid, rc in ref.items():
                oc = next(c for c in other[task] if c["case_id"] == cid)
                # Selected action/abstention must match exactly; float tolerance
                # NEVER excuses a changed action.
                if rc.get("prediction") != oc.get("prediction") or bool(rc.get("abstained")) != bool(oc.get("abstained")):
                    divergences.append({"task": task, "case_id": cid,
                                        "platforms": (atts[0]["platform"], other["platform"]),
                                        "ref_prediction": rc.get("prediction"), "other_prediction": oc.get("prediction"),
                                        "ref_abstained": rc.get("abstained"), "other_abstained": oc.get("abstained")})
                    if len(divergences) >= 5:
                        break
            if len(divergences) >= 5:
                break
        # Probability tolerance recorded separately (informational only).
        if task == "choice_cases":
            for c in atts[0][task]:
                cid = c["case_id"]
                rp = c.get("raw_probabilities") or []
                for other in atts[1:]:
                    oc = next(x for x in other[task] if x["case_id"] == cid)
                    op = oc.get("raw_probabilities") or []
                    if len(rp) == len(op) and rp:
                        for a, b in zip(rp, op):
                            try:
                                d = abs(float(a) - float(b))
                                if d > max_prob_delta:
                                    max_prob_delta = d
                            except Exception:
                                pass

    ledger = {
        "verdict": "pass" if not divergences and not artifact_divergence else "fail",
        "source_commit": source_commit,
        "platforms": platforms,
        "per_host_attestation_sha256": {a["platform"]: a.get("attestation_sha256") for a in atts},
        "per_host_report_sha256": {a["platform"]: a.get("report_sha256") for a in atts},
        "canary_artifact_ledger": canary_ledger,
        "artifact_divergence": artifact_divergence,
        "decision_divergences": divergences[:5],
        "decision_divergence_count": len(divergences),
        "max_probability_delta": max_prob_delta,
        "prob_tolerance": args.prob_tol,
        "binary_case_count": len(ref_bin_ids),
        "choice_case_count": len(ref_ch_ids),
        "note": "Probabilities compared with tolerance separately; changed action/abstention never passes under tolerance. Host timings/RSS not compared.",
    }
    if artifact_divergence and not divergences:
        ledger["reason"] = f"parity artifact bytes differ across hosts ({len(artifact_divergence)} artifacts); not same-artifact evidence"
    elif divergences:
        first = divergences[0]
        ledger["reason"] = (f"decision divergence on {first['task']} {first['case_id']}: "
                            f"{first['ref_prediction']}/{first['ref_abstained']} vs "
                            f"{first['other_prediction']}/{first['other_abstained']}")
    else:
        ledger["reason"] = (f"same-artifact decisions agree across {platforms} "
                            f"({len(ref_bin_ids)} binary + {len(ref_ch_ids)} choice cases)")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verdict": ledger["verdict"], "reason": ledger["reason"]}, sort_keys=True))
    return 0 if ledger["verdict"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
