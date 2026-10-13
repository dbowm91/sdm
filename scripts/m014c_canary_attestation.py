#!/usr/bin/env python3
"""M014c per-host canary attestation (Work B).

Each independent CI host runs the SAME exact committed or
deterministic-canonical canary artifact bytes and exports bounded per-case
decisions to an integrity-hashed JSON attestation.

Inputs (all under target/m014a/canary/ unless overridden):
- manifest.json
- eval-binary-mask.report.json, eval-binary-baseline.report.json
- eval-choice-compositional.report.json, eval-choice-legacy.report.json,
  eval-choice-cross.report.json
- candidates/canary-*.artifact.json (deterministic-canonical; SHA recorded)
- committed reference artifacts/m014/* (guaranteed same bytes; SHA recorded)

Outputs:
- attestation JSON with host/build/platform/source-commit/artifact SHAs,
  dataset/split/test-membership SHAs, report SHAs, per-case decisions
  (case_id, family, leakage_group, target, prediction, abstained,
  architecture, artifact SHA), timings labeled host-specific, and
  attestation_sha256 (canonical SHA over payload excluding itself).

Does NOT leak raw feature text or user data (IDs/groups/families only).
Does NOT set three_host_parity; parity is decided only by the downstream
aggregator scripts/verify_m014c_parity.py over three hosts.

Usage:
  python3 scripts/m014c_canary_attestation.py \
    --platform linux-x86_64 --out target/m014a/canary/attestation-linux-x64.json
  python3 scripts/m014c_canary_attestation.py \
    --platform linux-aarch64 --out target/m014a/canary/attestation-linux-arm64.json
  python3 scripts/m014c_canary_attestation.py \
    --platform macos-aarch64 --out target/m014a/canary/attestation-macos-arm64.json

Platform must be one of linux-x86_64, linux-aarch64, macos-aarch64.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "target" / "m014a" / "canary"

EXPECTED_PLATFORMS = ("linux-x86_64", "linux-aarch64", "macos-aarch64")


def file_sha(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def canonical_sha(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def load_report(path: Path) -> dict:
    return json.loads(path.read_text())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="M014c per-host canary attestation")
    ap.add_argument("--platform", required=True, choices=list(EXPECTED_PLATFORMS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--canary-dir", default=str(CANARY))
    args = ap.parse_args(argv)

    canary = Path(args.canary_dir)
    manifest_path = canary / "manifest.json"
    bin_mask_path = canary / "eval-binary-mask.report.json"
    bin_base_path = canary / "eval-binary-baseline.report.json"
    ch_comp_path = canary / "eval-choice-compositional.report.json"
    ch_leg_path = canary / "eval-choice-legacy.report.json"
    ch_cross_path = canary / "eval-choice-cross.report.json"

    for p in (manifest_path, bin_mask_path, bin_base_path, ch_comp_path, ch_leg_path, ch_cross_path):
        if not p.exists():
            print(f"missing required canary file {p}; run run_m014a_dev_canary.py first", file=sys.stderr)
            return 1

    manifest = json.loads(manifest_path.read_text())
    bin_mask = load_report(bin_mask_path)
    bin_base = load_report(bin_base_path)
    ch_comp = load_report(ch_comp_path)
    ch_leg = load_report(ch_leg_path)
    ch_cross = load_report(ch_cross_path)

    # Artifact SHAs: deterministic-canonical canary artifacts (trained locally
    # with fixed seed; SHA recorded so aggregator can distinguish artifact
    # divergence from decision divergence — never compare retrained floats
    # as parity without this check).
    canary_artifacts = {}
    for name in ("canary-binary-mask", "canary-binary-baseline",
                 "canary-choice-compositional", "canary-choice-legacy", "canary-choice-cross"):
        p = canary / "candidates" / f"{name}.artifact.json"
        if not p.exists():
            print(f"missing canary artifact {p}", file=sys.stderr)
            return 1
        canary_artifacts[name] = file_sha(p)

    # Committed reference artifacts (guaranteed same bytes on all hosts).
    committed_artifacts = {}
    for rel in ("artifacts/m014/binary-baseline-v1.artifact.json",
                "artifacts/m014/binary-constant-mask-v1.artifact.json",
                "artifacts/m014/choice-legacy-v1.artifact.json",
                "artifacts/m014/choice-cross-v1.artifact.json",
                "artifacts/m014/choice-compositional-v1.artifact.json"):
        p = ROOT / rel
        if not p.exists():
            print(f"missing committed artifact {rel}", file=sys.stderr)
            return 1
        committed_artifacts[rel] = file_sha(p)

    # Source commit (all hosts must match).
    try:
        source_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        source_commit = "unknown"

    try:
        host_detail = subprocess.run(["uname", "-a"], capture_output=True, text=True).stdout.strip()
    except Exception:
        host_detail = "unknown"
    try:
        build = subprocess.run(["rustc", "-V"], capture_output=True, text=True).stdout.strip()
    except Exception:
        build = "unknown"

    try:
        evaluator_sha = "sha256:" + hashlib.sha256((ROOT / "scripts/qualify_semantic_v2.py").read_bytes()).hexdigest()
    except Exception:
        evaluator_sha = "sha256:" + "0" * 64

    # Per-case decisions: bounded, no raw feature text.
    # Binary: use mask candidate (primary) + baseline for reference.
    binary_cases = []
    for row in bin_mask["outcomes"]:
        binary_cases.append({
            "case_id": row["case_id"],
            "family": row.get("family"),
            "leakage_group": row.get("leakage_group"),
            "target": row.get("target"),
            "prediction": row.get("prediction"),
            "abstained": bool(row.get("abstained", False)),
            "score": row.get("score"),
            "architecture": bin_mask.get("artifact_architecture"),
            "artifact_sha256": bin_mask.get("artifact_sha256"),
        })
    binary_cases.sort(key=lambda r: r["case_id"])

    # Choice compositional (primary) + legacy/cross (compatibility).
    choice_cases = []
    for row in ch_comp["outcomes"]:
        choice_cases.append({
            "case_id": row["case_id"],
            "family": row.get("family"),
            "leakage_group": row.get("leakage_group"),
            "target": row.get("target"),
            "prediction": row.get("prediction"),
            "abstained": bool(row.get("abstained", False)),
            "raw_probabilities": row.get("raw_probabilities"),
            "architecture": ch_comp.get("artifact_architecture"),
            "artifact_sha256": ch_comp.get("artifact_sha256"),
        })
    choice_cases.sort(key=lambda r: r["case_id"])

    # Legacy/cross decisions for compatibility (prediction/abstained only).
    def compact(report: dict) -> list[dict]:
        out = []
        for row in report["outcomes"]:
            out.append({
                "case_id": row["case_id"],
                "prediction": row.get("prediction"),
                "abstained": bool(row.get("abstained", False)),
            })
        out.sort(key=lambda r: r["case_id"])
        return out

    payload = {
        "attestation_id": "sdm-m014c-canary-attestation-v1",
        "platform": args.platform,
        "host_detail": host_detail,
        "build": build,
        "source_commit": source_commit,
        "manifest_id": manifest.get("manifest_id"),
        "evaluator_sha256": evaluator_sha,
        "binary_test_membership_sha256": manifest["binary"]["test_membership_sha256"],
        "choice_test_membership_sha256": manifest["choice"]["test_membership_sha256"],
        "binary_dataset_sha256": manifest["binary"]["dataset_sha256"],
        "choice_dataset_sha256": manifest["choice"]["dataset_sha256"],
        "binary_split_fingerprint": manifest["binary"]["split_fingerprint"],
        "choice_split_fingerprint": manifest["choice"]["split_fingerprint"],
        "canary_artifact_sha256": canary_artifacts,
        "committed_artifact_sha256": committed_artifacts,
        "report_sha256": {
            "eval-binary-mask": bin_mask.get("report_sha256"),
            "eval-binary-baseline": bin_base.get("report_sha256"),
            "eval-choice-compositional": ch_comp.get("report_sha256"),
            "eval-choice-legacy": ch_leg.get("report_sha256"),
            "eval-choice-cross": ch_cross.get("report_sha256"),
        },
        "binary_case_count": len(binary_cases),
        "choice_case_count": len(choice_cases),
        "binary_cases": binary_cases,
        "choice_cases": choice_cases,
        "choice_legacy_compact": compact(ch_leg),
        "choice_cross_compact": compact(ch_cross),
        "note": "Per-host same-artifact decisions; host timings/RSS are host-specific and not compared. Parity decided only by downstream aggregator over three hosts.",
    }
    payload["attestation_sha256"] = canonical_sha(payload)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Refuse overwrite? Attestation is regenerable per host; allow overwrite
    # of same-host file but never of other hosts (distinct paths enforce).
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(out)
    print(json.dumps({"attestation": str(out), "platform": args.platform,
                      "attestation_sha256": payload["attestation_sha256"],
                      "binary_cases": len(binary_cases), "choice_cases": len(choice_cases)},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
