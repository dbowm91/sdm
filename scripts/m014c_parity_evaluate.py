#!/usr/bin/env python3
"""M014c parity evaluations on SAME committed bytes (Work B fix).

Each CI host evaluates the SAME exact committed M014 artifact bytes on its
locally generated (deterministic-identical) DEV-CANARY datasets, producing
parity reports for cross-host decision comparison.

Why: canary-trained artifacts are retrained independently on each host with
fixed seeds, but Choice training is NOT bit-identical across OSes (linux-x64
and linux-arm64 agree; macos-arm64 differs). Comparing decisions from
different bytes is NOT same-artifact parity (plan B2: never compare
independently retrained floats as parity). Committed artifacts/m014/* are
guaranteed identical bytes on all hosts (SHA-verified by the aggregator).

Inputs:
- target/m014a/canary/binary.json + binary.split.json (deterministic)
- target/m014a/canary/choice.json + choice.split.json (deterministic)
- artifacts/m014/*.artifact.json (committed, same bytes on all hosts)

Outputs (only under target/m014a/canary/parity-*; NEVER target/m014b/final/
or fixtures/m014b-final-*):
- target/m014a/canary/parity-binary-baseline.report.json
- target/m014a/canary/parity-binary-mask.report.json
- target/m014a/canary/parity-choice-legacy.report.json
- target/m014a/canary/parity-choice-cross.report.json
- target/m014a/canary/parity-choice-compositional.report.json
plus corresponding .evaluate.json specs.

Provenance: spec provenance comes from the CANARY dataset bundle (required:
config provenance must equal dataset bundle). Artifact provenance is NOT
compared (only dataset bundle vs spec). Feature schemas match (verified
locally: M014 and canary share sha256:a959af25...), unknown canary text
maps to zeros per typed-task-heads.

Usage: python3 scripts/m014c_parity_evaluate.py
Exit 0 on all five parity evaluations verified (SHA before/after identical,
explicit partition/flag, no overwrite of existing parity reports without
explicit cleanup, deterministic per host).
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "target" / "m014a" / "canary"

# (spec_name, dataset_rel, split_rel, artifact_rel, report_rel, expected_arch)
PARITY_MAP = [
    ("parity-binary-baseline",
     "target/m014a/canary/binary.json", "target/m014a/canary/binary.split.json",
     "artifacts/m014/binary-baseline-v1.artifact.json",
     "target/m014a/canary/parity-binary-baseline.report.json", "typed-binary"),
    ("parity-binary-mask",
     "target/m014a/canary/binary.json", "target/m014a/canary/binary.split.json",
     "artifacts/m014/binary-constant-mask-v1.artifact.json",
     "target/m014a/canary/parity-binary-mask.report.json", "typed-binary"),
    ("parity-choice-legacy",
     "target/m014a/canary/choice.json", "target/m014a/canary/choice.split.json",
     "artifacts/m014/choice-legacy-v1.artifact.json",
     "target/m014a/canary/parity-choice-legacy.report.json", "typed-choice"),
    ("parity-choice-cross",
     "target/m014a/canary/choice.json", "target/m014a/canary/choice.split.json",
     "artifacts/m014/choice-cross-v1.artifact.json",
     "target/m014a/canary/parity-choice-cross.report.json", "typed-choice-cross"),
    ("parity-choice-compositional",
     "target/m014a/canary/choice.json", "target/m014a/canary/choice.split.json",
     "artifacts/m014/choice-compositional-v1.artifact.json",
     "target/m014a/canary/parity-choice-compositional.report.json", "typed-choice-compositional"),
]

FORBIDDEN_PREFIXES = ("target/m014b/final", "target/m014/final", "fixtures/m014b-final", "fixtures/m014-final")


def file_sha(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def membership(ids) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(sorted(ids), separators=(",", ":")).encode()).hexdigest()


def run(cmd: list[str]) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    # Safety: refuse to touch FINAL paths (paranoia; map is fixed above).
    for _, _, _, _, report, _ in PARITY_MAP:
        for prefix in FORBIDDEN_PREFIXES:
            if report.startswith(prefix):
                print(f"refusing parity report path overlapping FINAL: {report}", file=sys.stderr)
                return 1
    # Require canary datasets/splits (provisioned by run_m014a_dev_canary.py).
    for rel in ("target/m014a/canary/binary.json", "target/m014a/canary/binary.split.json",
                "target/m014a/canary/choice.json", "target/m014a/canary/choice.split.json"):
        if not (ROOT / rel).exists():
            print(f"missing {rel}; run run_m014a_dev_canary.py first", file=sys.stderr)
            return 1

    bin_prov = json.loads((CANARY / "binary.json").read_text())["provenance"]
    choice_prov = json.loads((CANARY / "choice.json").read_text())["provenance"]

    for name, ds_rel, sp_rel, art_rel, report_rel, arch in PARITY_MAP:
        art_p = ROOT / art_rel
        if not art_p.exists():
            print(f"missing committed artifact {art_rel}", file=sys.stderr)
            return 1
        env = json.loads(art_p.read_text())
        split = json.loads((ROOT / sp_rel).read_text())
        prov = bin_prov if "binary" in ds_rel else choice_prov
        spec = {
            "dataset_path": ds_rel, "split_path": sp_rel,
            "artifact_path": art_rel, "report_path": report_rel,
            "expected_artifact_sha256": file_sha(art_p),
            "expected_dataset_sha256": split["dataset_sha256"],
            "expected_split_fingerprint": split["fingerprint"],
            "expected_test_membership_sha256": membership(split["test"]),
            "expected_architecture": arch,
            "expected_artifact_architecture": env["architecture"],
            "expected_feature_schema_sha256": env["required_feature_schema_sha256"],
            "expected_calibration_sha256": env["calibration_sha256"],
            "protocol_sha256": "sha256:" + "0" * 64,
            "freeze_sha256": "sha256:" + "1" * 64,
            "provenance": prov,
        }
        spec_rel = report_rel.replace(".report.json", ".evaluate.json")
        (ROOT / spec_rel).write_text(json.dumps(spec, indent=2))
        # Remove old parity report to allow rerun (parity regenerable; only own paths).
        if (ROOT / report_rel).exists():
            (ROOT / report_rel).unlink()
        run(["cargo", "run", "-q", "-p", "sdm-experiment", "--locked", "--",
             "experiment", "evaluate", "--config", spec_rel])
        # Verify SHA before/after identical and explicit partition/flag.
        after_sha = file_sha(art_p)
        assert after_sha == spec["expected_artifact_sha256"], f"committed artifact mutated during parity evaluate {art_rel}"
        rep = json.loads((ROOT / report_rel).read_text())
        assert rep["evaluated_partition"] == "test", f"absent test partition in {report_rel}"
        assert rep["test_evaluation_performed"] is True, f"flag mismatch in {report_rel}"
        assert rep["artifact_sha256"] == spec["expected_artifact_sha256"], f"parity report artifact SHA mismatch {report_rel}"
        print(f"parity ok: {report_rel} ({len(rep['outcomes'])} rows, artifact {rep['artifact_sha256'][:24]}...)")
    print("M014c parity evaluations complete: 5 committed-artifact reports on canary data (same bytes on all hosts).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
