#!/usr/bin/env python3
"""M015a DEV-only final-action replay sidecar.

Uses the three existing Choice heads and actual final `decide_typed` outputs
via the additive Rust `experiment m015a-replay` path. Produces versioned v2
final-action metrics, per-family support tables, and a legacy glossary that
labels the old `dev_counterfactual_correct_on_both` as mixed raw/final.

TRAIN/DEV only. Never trains, never touches test, never rewrites historical
artifacts/reports. Outputs only under the given --out directory (default
target/m015a) with atomic no-overwrite semantics and explicit input SHA binding.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURES = ("typed-choice", "typed-choice-cross", "typed-choice-compositional")


def sha_file(path):
    h = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return "sha256:" + h


def sha_bytes(data: bytes):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def atomic_write(path: Path, payload: bytes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            return digest
        raise FileExistsError(f"refusing to overwrite different M015a output: {path}")
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        import os

        with open(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        # Validate JSON before publishing.
        json.loads(payload)
        os.replace(tmp, path)
    finally:
        import os as _os

        if _os.path.exists(tmp):
            _os.unlink(tmp)
    return digest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-train", type=Path, default=ROOT / "target/m015-baselines-v7/corpus/train.jsonl")
    ap.add_argument("--corpus-dev", type=Path, default=ROOT / "target/m015-baselines-v7/corpus/dev.jsonl")
    ap.add_argument("--typed-dataset", type=Path, default=ROOT / "target/m015-baselines-v7/typed-choice.json")
    ap.add_argument("--typed-split", type=Path, default=ROOT / "target/m015-baselines-v7/typed-choice.split.json")
    ap.add_argument("--generator", type=Path, default=ROOT / "scripts/generate_m015_suite.py")
    ap.add_argument("--task-spec", type=Path, default=ROOT / "docs/m015-task-spec-v1.md")
    ap.add_argument("--artifacts-dir", type=Path, default=ROOT / "target/m015-baselines-v7")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "target/m015-baselines-v7")
    ap.add_argument("--out", type=Path, default=ROOT / "target/m015a")
    args = ap.parse_args()

    out = Path(args.out)
    # Census: verify source corpus counts before any inference.
    train_rows = [json.loads(l) for l in args.corpus_train.open() if l.strip()]
    dev_rows = [json.loads(l) for l in args.corpus_dev.open() if l.strip()]
    train_groups = {r["group_id"] for r in train_rows}
    dev_groups = {r["group_id"] for r in dev_rows}
    assert len(train_rows) == 7200, f"train rows {len(train_rows)} != 7200"
    assert len(train_groups) == 2000, f"train groups {len(train_groups)} != 2000"
    assert len(dev_rows) == 720, f"dev rows {len(dev_rows)} != 720"
    assert len(dev_groups) == 200, f"dev groups {len(dev_groups)} != 200"
    nuisance = {r["pair_id"] for r in dev_rows if r["pair_type"] == "nuisance"}
    causal = {r["pair_id"] for r in dev_rows if r["pair_type"] == "causal_flip"}
    assert len(nuisance) == 200, f"nuisance {len(nuisance)} != 200"
    assert len(causal) == 160, f"causal {len(causal)} != 160"
    answerable = sum(1 for r in dev_rows if r["label"] is not None)
    assert answerable == 480, f"answerable {answerable} != 480"

    generator_sha = sha_file(args.generator)
    task_spec_sha = sha_file(args.task_spec)
    corpus_train_hex = hashlib.sha256(args.corpus_train.read_bytes()).hexdigest()
    corpus_dev_hex = hashlib.sha256(args.corpus_dev.read_bytes()).hexdigest()
    corpus_train_sha = "sha256:" + corpus_train_hex
    corpus_dev_sha = "sha256:" + corpus_dev_hex

    # Provenance from typed dataset bundle (58MB; load fully for correctness).
    full = read_json(args.typed_dataset)
    provenance = full["provenance"]

    split_doc = read_json(args.typed_split)
    # Expected dataset/split from frozen reports (all three share them).
    sample_report = read_json(args.reports_dir / "typed-choice.report.json")
    expected_dataset = sample_report["dataset_sha256"]
    expected_split = sample_report["split_fingerprint"]
    assert split_doc["fingerprint"] == expected_split, "split fingerprint drift"
    assert split_doc["dataset_sha256"] == expected_dataset, "dataset sha drift"
    assert split_doc["test"] == [], "M015a requires empty test partition"
    assert len(split_doc["train"]) == 7200 and len(split_doc["dev"]) == 720

    results = {}
    for arch in ARCHITECTURES:
        artifact_path = args.artifacts_dir / f"{arch}.artifact.json"
        frozen_report_path = args.reports_dir / f"{arch}.report.json"
        frozen = read_json(frozen_report_path)
        artifact_sha = sha_file(artifact_path)
        assert frozen["artifact_sha256"] == artifact_sha, f"{arch} artifact drift"
        assert frozen["dataset_sha256"] == expected_dataset
        assert frozen["test_evaluation_performed"] is False
        assert frozen["verdict"] == "train-dev-only"
        legacy = frozen.get("dev_diagnostics") or {}

        output_path = out / f"{arch}.sidecar.json"
        config = {
            "dataset_path": str(args.typed_dataset),
            "split_path": str(args.typed_split),
            "artifact_path": str(artifact_path),
            "corpus_train_path": str(args.corpus_train),
            "corpus_dev_path": str(args.corpus_dev),
            "generator_path": str(args.generator),
            "task_spec_path": str(args.task_spec),
            "output_path": str(output_path),
            "expected_artifact_sha256": artifact_sha,
            "expected_dataset_sha256": expected_dataset,
            "expected_split_fingerprint": expected_split,
            "expected_generator_sha256": generator_sha,
            "expected_task_spec_sha256": task_spec_sha,
            "expected_corpus_train_sha256": corpus_train_sha,
            "expected_corpus_dev_sha256": corpus_dev_sha,
            "architecture": arch,
            "provenance": provenance,
        }
        config_path = out / f"{arch}.m015a-replay.json"
        # Write config atomically (allow overwrite of identical bytes for reruns).
        payload = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.exists():
            if config_path.read_bytes() != payload:
                raise FileExistsError(f"refusing to replace different replay config {config_path}")
        else:
            # Use atomic helper for new files.
            atomic_write(config_path, payload)
        proc = subprocess.run(
            ["cargo", "run", "-q", "-p", "sdm-experiment", "--locked", "--",
             "experiment", "m015a-replay", "--config", str(config_path)],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"{arch} m015a-replay failed: {proc.stderr.strip()[-4000:]}")
        sidecar = json.loads(proc.stdout)
        # Verify sidecar file matches stdout and input binding.
        on_disk = read_json(output_path)
        assert on_disk["report_sha256"] == sidecar["report_sha256"], f"{arch} sidecar stdout/disk digest drift"
        assert on_disk["artifact_sha256"] == artifact_sha
        assert on_disk["dataset_sha256"] == expected_dataset
        assert on_disk["partition"] == "DEV only"
        assert on_disk["train_rows"] == 7200 and on_disk["dev_rows"] == 720
        assert on_disk["dev_nuisance_pairs"] == 200 and on_disk["dev_causal_pairs"] == 160
        # Attach legacy comparison (read-only frozen values) for erratum tables.
        legacy_keys = [
            "dev_answerable_accuracy", "dev_answerable_coverage",
            "dev_no_answer_recall", "dev_counterfactual_correct_on_both",
            "dev_nuisance_correct_on_both", "dev_nuisance_pair_prediction_agreement",
            "dev_answerability_brier", "dev_answerability_log_loss",
            "dev_answerable_conditional_choice_nll", "dev_answerable_conditional_choice_brier",
        ]
        sidecar["legacy_comparison"] = {k: legacy.get(k) for k in legacy_keys}
        # Persist enriched sidecar (overwrite only if identical or new).
        enriched = (json.dumps(sidecar, indent=2, sort_keys=True) + "\n").encode()
        # The on-disk file currently lacks legacy_comparison; update it once.
        if on_disk.get("legacy_comparison") != sidecar["legacy_comparison"]:
            # Remove old file only if we are enriching (first write); refuse
            # to silently replace differing core metrics.
            core_old = {k: on_disk.get(k) for k in ("report", "artifact_sha256", "dataset_sha256")}
            core_new = {k: sidecar.get(k) for k in ("report", "artifact_sha256", "dataset_sha256")}
            assert core_old == core_new, f"{arch} core metrics changed during enrichment"
            output_path.unlink()
            atomic_write(output_path, enriched)
        results[arch] = sidecar
        print(f"{arch}: final_acc={sidecar['report']['dev_final_action_accuracy_v2']['value']} "
              f"answerable_final={sidecar['report']['dev_answerable_final_accuracy_v2']['value']} "
              f"coverage={sidecar['report']['dev_answerable_final_coverage_v2']['value']} "
              f"causal_both={sidecar['report']['causal']['both_final_correct']['value']} "
              f"nuisance_both={sidecar['report']['nuisance']['both_final_correct']['value']}",
              file=sys.stderr)

    # Combined summary with SHA ledger and no-test attestation.
    summary = {
        "schema": "sdm-m015a-summary-v1",
        "contract": "choice-final-v2",
        "partition": "DEV only",
        "generator_sha256": generator_sha,
        "task_spec_sha256": task_spec_sha,
        "corpus_train_sha256": corpus_train_sha,
        "corpus_dev_sha256": corpus_dev_sha,
        "dataset_sha256": expected_dataset,
        "split_fingerprint": expected_split,
        "test_membership": [],
        "test_evaluation_performed": False,
        "census": {
            "train_rows": 7200, "train_groups": 2000,
            "dev_rows": 720, "dev_groups": 200,
            "dev_answerable_rows": 480,
            "dev_no_answer_rows": 240,
            "dev_no_answer_available_false": 80,
            "dev_no_answer_available_true_zero_satisfying": 160,
            "dev_nuisance_pairs": 200, "dev_causal_pairs": 160,
        },
        "models": {
            arch: {
                "artifact_sha256": results[arch]["artifact_sha256"],
                "calibration_sha256": results[arch]["calibration_sha256"],
                "report_sha256": results[arch]["report_sha256"],
                "output_bytes": Path(out / f"{arch}.sidecar.json").stat().st_size,
                "output_sha256": sha_file(out / f"{arch}.sidecar.json"),
                "v2": {
                    "dev_final_action_accuracy_v2": results[arch]["report"]["dev_final_action_accuracy_v2"],
                    "dev_answerable_final_accuracy_v2": results[arch]["report"]["dev_answerable_final_accuracy_v2"],
                    "dev_false_abstention_rate_v2": results[arch]["report"]["dev_false_abstention_rate_v2"],
                    "dev_no_answer_final_recall_v2": results[arch]["report"]["dev_no_answer_final_recall_v2"],
                    "dev_answerable_final_coverage_v2": results[arch]["report"]["dev_answerable_final_coverage_v2"],
                    "dev_conditional_argmax_accuracy_v2": results[arch]["report"]["dev_conditional_argmax_accuracy_v2"],
                    "dev_answered_conditional_accuracy_v2": results[arch]["report"]["dev_answered_conditional_accuracy_v2"],
                    "causal_both_final_correct": results[arch]["report"]["causal"]["both_final_correct"],
                    "nuisance_both_final_correct": results[arch]["report"]["nuisance"]["both_final_correct"],
                    "nuisance_consistency": results[arch]["report"]["nuisance"]["prediction_consistency"],
                    "nuisance_preserving": results[arch]["report"]["nuisance"]["correctness_preserving_agreement"],
                    "families": results[arch]["report"]["families"],
                    "no_answer_by_origin": results[arch]["report"]["no_answer_by_origin"],
                },
                "legacy_mixed": results[arch]["legacy_comparison"],
            }
            for arch in ARCHITECTURES
        },
        "glossary": {
            "dev_answerable_accuracy": "HISTORICAL mixed raw: conditional argmax vs true ID without requiring final answer (D1). Preserved; do not compare to v2.",
            "dev_counterfactual_correct_on_both": "HISTORICAL mixed raw/final: raw argmax on answerable member + final abstention on no-answer member (D2). Labeled mixed, not final pair success.",
            "dev_nuisance_correct_on_both": "HISTORICAL raw conditional correctness on answerable nuisance rows (D2). See v2 nuisance_both_final_correct.",
            "dev_nuisance_pair_prediction_agreement": "HISTORICAL prediction identity including double abstention without correctness (D2). See v2 consistency vs preserving.",
            "dev_final_action_accuracy_v2": "V2 final-action correctness over all DEV rows (answered exact ID or correct abstention).",
            "dev_answerable_final_accuracy_v2": "V2 final correctness over answerable rows only; false abstentions are errors.",
            "dev_conditional_argmax_accuracy_v2": "V2 raw conditional ranking alone, separate from final actions.",
        },
        "selection_policy": "No candidate or threshold selected. M017 final not constructed. Historical M015 reports unchanged.",
    }
    summary_bytes = (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode()
    atomic_write(out / "m015a-summary.json", summary_bytes)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
