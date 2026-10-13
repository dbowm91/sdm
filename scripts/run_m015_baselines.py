#!/usr/bin/env python3
"""Materialize M015 as typed Choice and run existing architectures on TRAIN/DEV only."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from generate_m015_suite import RULES, generate

MAX_TYPED_DATASET_BYTES = 64 * 1024 * 1024


FIELDS = [
    ("active", "boolean", True, []),
    ("available", "boolean", True, []),
    ("load", "number", True, []),
    ("memo", "text", False, []),
    ("note", "text", False, []),
    ("rule_family", "category", True, list(RULES)),
    ("rule_invert", "boolean", True, []),
    ("alpha", "boolean", True, []),
    ("beta", "boolean", True, []),
    ("capacity", "number", True, []),
    ("enabled", "boolean", True, []),
    ("kind", "category", True, ["other", "primary"]),
]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def materialize(source_dir, output_dir):
    train = read_jsonl(source_dir / "train.jsonl")
    dev = read_jsonl(source_dir / "dev.jsonl")
    rows = train + dev
    schema_fields = [{"id": name, "value_type": kind, "required": required, "categories": cats} for name, kind, required, cats in FIELDS]
    schema = {"version": 2, "fields": schema_fields}
    canonical_schema = {"version": 2, "fields": sorted([{**field, "categories": sorted(field["categories"])} for field in schema_fields], key=lambda f: f["id"])}
    schema_sha = "sha256:" + hashlib.sha256(canonical(canonical_schema)).hexdigest()

    def projection(values):
        result = []
        for name, kind, required, _cats in FIELDS:
            value = values.get(name)
            if value is None:
                wrapped = None
            else:
                wrapped = {"type": kind, "value": value}
            result.append({"id": name, "required": required, "value": wrapped})
        return {"schema_version": 2, "schema_sha256": schema_sha, "fields": result}

    examples = []
    for row in rows:
        context = row["context"]
        option_list = []
        projections = {}
        for option in row["options"]:
            semantics = option["semantics"]
            option_list.append({"id": option["id"], "label": f"Candidate {len(option_list)}"})
            candidate_values = {**context, "rule_family": row["rule"]["name"], "rule_invert": row["rule"]["operands"].get("invert", False), **semantics}
            projections[option["id"]] = projection(candidate_values)
        context_values = {**context, "rule_family": row["rule"]["name"], "rule_invert": row["rule"]["operands"].get("invert", False), "alpha": False, "beta": False, "capacity": 0.0, "enabled": False, "kind": "other"}
        examples.append({
            "case_id": row["case_id"], "leakage_group": row["group_id"], "family": row["family"], "counterfactual_pair": row["pair_id"],
            "request": {"request_id": row["case_id"] + "-request", "schema_version": 1, "state": [], "spec": {"kind": "choice", "question": "Choose the candidate satisfying the visible rule and context.", "options": option_list}},
            "label": {"kind": "choice", "value": row["label"]},
            "typed_rank_features": {"schema": schema, "context": projection(context_values), "candidates": projections},
            "m015_split": row["split"],
        })
    provenance = {"source": "SDM M015 TinyChoice synthetic TRAIN/DEV only", "license": "MIT", "consent_scope": "synthetic-only; no human or application data", "label_lineage": "source-defined rule families; see docs/m015-task-spec-v1.md", "redistributable": True}
    bundle = {"provenance": provenance, "examples": examples}
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = output_dir / "typed-choice.json"
    dataset_bytes = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode()
    if len(dataset_bytes) > MAX_TYPED_DATASET_BYTES:
        raise ValueError(f"M015 typed corpus is {len(dataset_bytes)} bytes; sdm-data limit is {MAX_TYPED_DATASET_BYTES}")
    if dataset_path.exists() and dataset_path.read_bytes() != dataset_bytes:
        raise FileExistsError(f"refusing to replace different dataset {dataset_path}")
    dataset_path.write_bytes(dataset_bytes)
    validated = subprocess.run(["cargo", "run", "-q", "-p", "sdm-data", "--bin", "sdm-dataset", "--locked", "--", "validate", str(dataset_path)], cwd=ROOT, capture_output=True, text=True, check=True)
    dataset_sha = validated.stdout.strip().split()[-1]
    train_ids = sorted(e["case_id"] for e in examples if e["m015_split"] == "train")
    dev_ids = sorted(e["case_id"] for e in examples if e["m015_split"] == "dev")
    split = {"version": 3, "dataset_sha256": dataset_sha, "seed": 150015, "train": train_ids, "dev": dev_ids, "test": [], "excluded": [], "fingerprint": ""}
    split["fingerprint"] = "sha256:" + hashlib.sha256(canonical(split)).hexdigest()
    split_path = output_dir / "typed-choice.split.json"
    split_bytes = json.dumps(split, indent=2).encode() + b"\n"
    if split_path.exists() and split_path.read_bytes() != split_bytes:
        raise FileExistsError(f"refusing to replace different split {split_path}")
    split_path.write_bytes(split_bytes)
    return dataset_path, split_path, provenance


def run(out, groups, seed):
    corpus = out / "corpus"
    generate(corpus, groups, seed)
    dataset, split, provenance = materialize(corpus, out)
    results = {}
    for architecture in ("typed-choice", "typed-choice-cross", "typed-choice-compositional"):
        config = {"dataset_path": str(dataset), "split_path": str(split), "architecture": architecture, "seed": 150015, "epochs": 20, "learning_rate": 0.2, "artifact_path": str(out / f"{architecture}.artifact.json"), "report_path": str(out / f"{architecture}.report.json"), "provenance": provenance, "quality_diagnostics": True, "evaluate_test": False}
        config_path = out / f"{architecture}.experiment.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        proc = subprocess.run(["cargo", "run", "-q", "-p", "sdm-experiment", "--locked", "--", "experiment", "run", "--config", str(config_path)], cwd=ROOT, capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(f"{architecture} failed ({proc.returncode}): {proc.stderr.strip()}")
        manifest = json.loads(proc.stdout)
        if manifest.get("test_evaluation_performed") is not False:
            raise RuntimeError(f"{architecture} unexpectedly evaluated a test partition")
        diagnostics = manifest.get("dev_diagnostics") or {}
        required_metrics = (
            "dev_answerable_accuracy", "dev_no_answer_recall", "dev_answerability_brier",
            "dev_answerability_log_loss", "dev_answerability_ece_10_bins",
            "dev_answerable_conditional_choice_nll", "dev_answerable_conditional_choice_brier",
            "dev_answerable_accuracy_group_bootstrap_95_ci_lower",
            "dev_answerable_accuracy_group_bootstrap_95_ci_upper",
            "dev_counterfactual_correct_on_both", "dev_nuisance_pair_prediction_agreement",
        )
        missing = [name for name in required_metrics if name not in diagnostics]
        if missing:
            raise RuntimeError(f"{architecture} diagnostic report missing {missing}")
        results[architecture] = {
            "architecture": architecture, "seed": manifest["seed"], "verdict": manifest["verdict"],
            "test_evaluation_performed": manifest["test_evaluation_performed"],
            "train_cases": len(manifest["train_ids"]), "dev_cases": len(manifest["dev_ids"]),
            "artifact_sha256": manifest["artifact_sha256"],
            "artifact_bytes": (out / f"{architecture}.artifact.json").stat().st_size,
            "metrics": {name: diagnostics[name] for name in required_metrics},
            "answerability_calibration_bins": [
                {"count": diagnostics.get(f"dev_answerability_bin_{i}_count", 0),
                 "confidence": diagnostics.get(f"dev_answerability_bin_{i}_confidence"),
                 "observed_rate": diagnostics.get(f"dev_answerability_bin_{i}_observed_rate")}
                for i in range(10)
            ],
        }
    return {"mode": "TRAIN/DEV only", "groups": groups, "models": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "target/m015-baselines")
    # The typed dataset is expanded per option and the shared sdm-data cap is
    # 64 MiB. Keep baseline materialization at the measured 2k TRAIN-group size.
    parser.add_argument("--groups", type=int, choices=(2_000,), default=2_000)
    parser.add_argument("--seed", type=int, default=150015)
    args = parser.parse_args()
    summary = run(args.out, args.groups, args.seed)
    payload = json.dumps(summary, sort_keys=True, indent=2).encode() + b"\n"
    summary_path = args.out / "baseline-summary.json"
    if summary_path.exists() and summary_path.read_bytes() != payload:
        raise FileExistsError(f"refusing to replace different baseline summary {summary_path}")
    summary_path.write_bytes(payload)
    print(payload.decode(), end="")


if __name__ == "__main__":
    main()
