#!/usr/bin/env python3
"""Freeze M016 same-artifact parity fixtures from authoritative evidence.

Reads the winning TinyMLP sidecar (with per-case emission) + the typed
dataset bundle and writes:
- fixtures/m016-tinymlp-selected.artifact.json (byte copy of the winner);
- fixtures/m016-parity-sample.json: fixed DEV rows (request + typed
  features + expected decision/probs/answerability) for the
  `tinymlp_fixture_parity` test that runs on every CI host.

Deterministic fixed selection: first 4 answerable + first 4 no-answer DEV
cases in sidecar order (group, case_id), covering causal + nuisance pairs.
Refuses to overwrite different bytes (explicit re-freeze discipline).
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comparison", type=Path, required=True,
                    help="target/m016/m016-comparison.json (authoritative run)")
    ap.add_argument("--sidecar", type=Path, required=True,
                    help="winning typed-choice-tinymlp sidecar (with cases)")
    ap.add_argument("--train-report", type=Path, required=True)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--artifact-override", type=Path, default=None,
                    help="explicit artifact file (resolves hosted-evidence swaps)")
    args = ap.parse_args()

    comp = json.loads(args.comparison.read_text())
    assert comp["schema"] == "sdm-m016-comparison-v1"
    assert comp["partition"] == "DEV only" and comp["test_evaluation_performed"] is False
    rep = json.loads(args.train_report.read_text())
    artifact = Path(args.artifact_override) if args.artifact_override \
        else Path(rep["selected_artifact_path"])
    assert artifact.exists(), artifact
    sidecar = json.loads(args.sidecar.read_text())
    assert sidecar["partition"] == "DEV only"
    assert sidecar["artifact_sha256"] == comp["models"]["typed-choice-tinymlp"]["artifact_sha256"]
    cases = sidecar.get("cases")
    assert cases and len(cases) == sidecar["dev_rows"], "sidecar must carry all DEV cases"

    bundle = json.loads(args.dataset.read_text())
    by_case = {e["case_id"]: e for e in bundle["examples"]}

    answerable = [c for c in cases if c["target"] is not None]
    no_answer = [c for c in cases if c["target"] is None]
    picked = answerable[:4] + no_answer[:4]
    assert len(picked) == 8 and len(answerable) >= 4 and len(no_answer) >= 4
    kinds = {c["pair_type"] for c in picked}
    assert "nuisance" in kinds and "causal_flip" in kinds, kinds

    rows = []
    for c in picked:
        ex = by_case[c["case_id"]]
        rows.append({
            "case_id": c["case_id"],
            "request": ex["request"],
            "features": ex["typed_rank_features"],
            "expected_predicted": c["predicted"],
            "expected_probs": c["conditional_probs"],
            "expected_answerability": c["answerability_p"],
        })
    sample = {
        "schema": "sdm-m016-parity-v1",
        "artifact_sha256": sha_file(artifact),
        "dataset_sha256": comp["dataset_sha256"],
        "split_fingerprint": comp["split_fingerprint"],
        "contract": comp["contract"],
        "rows": rows,
    }

    fixture_art = ROOT / "fixtures/m016-tinymlp-selected.artifact.json"
    fixture_sample = ROOT / "fixtures/m016-parity-sample.json"
    for path, payload in (
        (fixture_art, artifact.read_bytes()),
        (fixture_sample, (json.dumps(sample, indent=2, sort_keys=True) + "\n").encode()),
    ):
        if path.exists() and path.read_bytes() != payload:
            raise FileExistsError(f"refusing to overwrite different fixture: {path}")
        if not path.exists():
            path.write_bytes(payload)
    print(f"fixture artifact: {sha_file(fixture_art)}")
    print(f"parity sample: {sha_file(fixture_sample)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
