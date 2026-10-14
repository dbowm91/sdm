#!/usr/bin/env python3
"""M017 one-time final inference (LOCAL ONLY — never invoked by CI).

Preconditions (all fail-closed):
- M016 merged-main green + M017 freeze commit merged (binding present,
  final_status == FINAL_NOT_YET_RUN);
- no existing final ledger (single-use: a second run is a protocol
  violation, never a new verdict).

Steps:
1. Regenerate the final cohort + typed dataset; assert frozen SHAs.
2. Regenerate the three legacy baselines from frozen M015 bytes
   (run_m015_baselines) and assert their DEV v2 pins match the freeze
   within 1e-9 (functional equivalence; byte-identity is host-local).
3. Build the four `experiment evaluate` specs binding the preliminary SHA,
   test membership, model/provenance SHAs (mirrors freeze phase-2).
4. Run each evaluation EXACTLY ONCE (read-only, no training), then run
   analyze_m017_final.py into the original-byte ledger.
5. Print verdicts. Commit the ledger + closure via a reviewed PR; CI
   re-analyzes committed bytes without re-running inference.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import generate_m017_suite  # noqa: E402
import materialize_m017  # noqa: E402
import run_m015_baselines  # noqa: E402

LEGACY = ("typed-choice", "typed-choice-cross", "typed-choice-compositional")
TINYMLP_EVAL_ARCH = "typed-choice-tinymlp"
TINYMLP_ENVELOPE = "sdm-typed-choice-tinymlp-v1"
LEGACY_ENVELOPES = {
    "typed-choice": "sdm-typed-task-v1",
    "typed-choice-cross": "sdm-typed-choice-cross-v1",
    "typed-choice-compositional": "sdm-typed-choice-compositional-v1",
}
PIN_TOL = 1e-9


def sha_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_cargo(args):
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"cargo failed: {proc.stderr.strip()[-2000:]}")
    return proc.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "target/m017/final")
    ap.add_argument("--binding", type=Path, default=ROOT / "docs/m017-binding-v1.json")
    ap.add_argument("--tinymlp-artifact", type=Path,
                    default=ROOT / "fixtures/m016-tinymlp-selected.artifact.json")
    args = ap.parse_args()
    out = Path(args.out)
    ledger_path = out / "m017-final-ledger.json"
    if ledger_path.exists():
        raise SystemExit(f"final already consumed: {ledger_path} (no reruns)")

    binding = json.loads(args.binding.read_text())
    assert binding["final_status"] == "FINAL_NOT_YET_RUN", "freeze already consumed"
    prelim = json.loads((ROOT / "docs/m017-preliminary-v1.json").read_text())
    prelim_sha = binding["preliminary_sha256"]
    assert sha_file(ROOT / "docs/m017-preliminary-v1.json") == prelim_sha
    protocol_sha = sha_file(ROOT / "docs/m017-protocol-v1.json")
    assert protocol_sha == prelim["protocol_sha256"], "protocol drift since freeze"

    # 1. Final cohort (fresh generation, SHA-bound).
    workdir = out / "cohort"
    workdir.mkdir(parents=True, exist_ok=True)
    manifest = generate_m017_suite.generate(workdir, "final")
    assert manifest["output_sha256"] == prelim["cohorts"]["final"]["output_sha256"], \
        "final cohort drift"
    dataset, split, _ = materialize_m017.materialize(
        workdir / "final.jsonl", workdir / "typed")
    split_doc = json.loads(Path(split).read_text())
    test_ids = sorted(split_doc["test"])
    mem_sha = "sha256:" + hashlib.sha256(
        json.dumps(test_ids, separators=(",", ":")).encode()).hexdigest()

    # 2. Legacy baselines regenerated + DEV pins checked (real runtime
    # replay over M015 DEV through the versioned v2 contract).
    ctrl = out / "controls"
    summary = run_m015_baselines.run(ctrl, 2000, 150015)
    assert summary["mode"] == "TRAIN/DEV only"
    replay_out = out / "dev-pins"
    replay_cmd = [sys.executable, str(ROOT / "scripts/analyze_m015a_final_actions.py"),
                  "--corpus-train", str(ctrl / "corpus/train.jsonl"),
                  "--corpus-dev", str(ctrl / "corpus/dev.jsonl"),
                  "--typed-dataset", str(ctrl / "typed-choice.json"),
                  "--typed-split", str(ctrl / "typed-choice.split.json"),
                  "--artifacts-dir", str(ctrl), "--reports-dir", str(ctrl),
                  "--out", str(replay_out)]
    proc = subprocess.run(replay_cmd, capture_output=True, text=True, cwd=ROOT)
    if proc.returncode:
        raise RuntimeError(f"DEV replay failed: {proc.stderr.strip()[-2000:]}")
    dev_summary = json.loads((replay_out / "m015a-summary.json").read_text())
    for arch in LEGACY:
        pin = prelim["frozen_models"]["legacy_dev_pins"][arch]
        got = dev_summary["models"][arch]["v2"]
        for key, pin_key in (
                ("dev_conditional_argmax_accuracy_v2", "dev_conditional_argmax_accuracy_v2"),
                ("dev_answerable_final_accuracy_v2", "dev_answerable_final_accuracy_v2"),
                ("dev_false_abstention_rate_v2", "dev_false_abstention_rate_v2"),
                ("dev_no_answer_final_recall_v2", "dev_no_answer_recall_v2")):
            gv, pv = got[key]["value"], pin[pin_key]
            assert gv is not None and abs(gv - pv) <= PIN_TOL, \
                f"{arch} DEV pin drift: {key} {gv} != {pv}"
        assert got["causal_both_final_correct"]["value"] == pin["causal_both_final"]
        assert got["nuisance_both_final_correct"]["value"] == pin["nuisance_both_final"]

    manifests = {}
    for arch in LEGACY + (TINYMLP_EVAL_ARCH,):
        if arch == TINYMLP_EVAL_ARCH:
            artifact = args.tinymlp_artifact
            envelope_arch = TINYMLP_ENVELOPE
        else:
            artifact = ctrl / f"{arch}.artifact.json"
            envelope_arch = LEGACY_ENVELOPES[arch]
        env = json.loads(Path(artifact).read_text())
        bundle = json.loads(Path(dataset).read_text())
        spec = {
            "dataset_path": str(dataset), "split_path": str(split),
            "artifact_path": str(artifact),
            "report_path": str(out / f"{arch}.evaluate.report-w.json"),
            "expected_artifact_sha256": sha_file(artifact),
            "expected_dataset_sha256": split_doc["dataset_sha256"],
            "expected_split_fingerprint": split_doc["fingerprint"],
            "expected_test_membership_sha256": mem_sha,
            "expected_architecture": arch,
            "expected_artifact_architecture": envelope_arch,
            "expected_feature_schema_sha256": env["required_feature_schema_sha256"],
            "expected_calibration_sha256": env["calibration_sha256"],
            "protocol_sha256": protocol_sha,
            "freeze_sha256": prelim_sha,
            "provenance": bundle["provenance"],
        }
        spec_path = out / f"{arch}.evaluate.json"
        spec_path.write_text(json.dumps(spec, indent=2) + "\n")
        stdout = run_cargo(["cargo", "run", "-q", "-p", "sdm-experiment", "--locked",
                            "--", "experiment", "evaluate", "--config", str(spec_path)])
        manifest_path = out / f"{arch}.manifest.json"
        manifest_path.write_bytes((json.dumps(json.loads(stdout), indent=2,
                                              sort_keys=True) + "\n").encode())
        manifests[arch] = manifest_path

    # 3. One-time analysis into the ledger.
    dev_controls = ROOT / "target/m016/m016-comparison.json"
    assert dev_controls.exists(), "M016 DEV evidence required for N1 carried control"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/analyze_m017_final.py"),
         "--manifests"] + [str(manifests[a]) for a in
                            (TINYMLP_EVAL_ARCH,) + LEGACY] + [
             "--corpus", str(workdir / "final.jsonl"),
             "--protocol", str(ROOT / "docs/m017-protocol-v1.json"),
             "--binding", str(args.binding),
             "--dev-controls", str(dev_controls),
             "--out", str(ledger_path)],
        capture_output=True, text=True, cwd=ROOT)
    print(proc.stdout)
    if proc.returncode:
        raise SystemExit(f"analyzer failed (indeterminate by definition): {proc.stderr[-3000:]}")
    print(f"M017 final consumed exactly once: {ledger_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
