#!/usr/bin/env python3
"""Materialize an M017 cohort (canary/final JSONL) as a typed Choice dataset.

Uses the byte-identical 12-field feature schema as M015 (imported, not
copied: frozen M016 artifacts bind that schema fingerprint at inference).
The split manifest carries the cohort rows as `test` with empty
train/dev/excluded (validate_split permits this; leakage-group isolation is
trivially satisfied within one cohort).

Outputs (atomic, no-overwrite): <out>/typed-choice.json,
<out>/typed-choice.split.json. Never touches train/dev/FINAL history.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from run_m015_baselines import FIELDS, canonical  # noqa: E402  (identical schema)

MAX_TYPED_DATASET_BYTES = 64 * 1024 * 1024


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def materialize(cohort_path, output_dir):
    rows = read_jsonl(cohort_path)
    assert rows, "empty cohort"
    cohort = rows[0]["split"]
    assert all(r["split"] == cohort for r in rows), "mixed-cohort input"
    schema_fields = [{"id": name, "value_type": kind, "required": required, "categories": cats} for name, kind, required, cats in FIELDS]
    canonical_schema = {"version": 2, "fields": sorted([{**field, "categories": sorted(field["categories"])} for field in schema_fields], key=lambda f: f["id"])}
    schema_sha = "sha256:" + hashlib.sha256(canonical(canonical_schema)).hexdigest()

    def projection(values):
        result = []
        for name, kind, required, _cats in FIELDS:
            value = values.get(name)
            wrapped = None if value is None else {"type": kind, "value": value}
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
            "typed_rank_features": {"schema": {"version": 2, "fields": schema_fields}, "context": projection(context_values), "candidates": projections},
            "m017_split": cohort,
        })
    provenance = {"source": "SDM M017 TinyChoice synthetic held-out only", "license": "MIT", "consent_scope": "synthetic-only; no human or application data", "label_lineage": "source-defined rule families; see docs/m015-task-spec-v1.md", "redistributable": True}
    bundle = {"provenance": provenance, "examples": examples}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = output_dir / "typed-choice.json"
    dataset_bytes = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode()
    if len(dataset_bytes) > MAX_TYPED_DATASET_BYTES:
        raise ValueError(f"M017 typed corpus is {len(dataset_bytes)} bytes; limit is {MAX_TYPED_DATASET_BYTES}")
    if dataset_path.exists() and dataset_path.read_bytes() != dataset_bytes:
        raise FileExistsError(f"refusing to replace different dataset {dataset_path}")
    dataset_path.write_bytes(dataset_bytes)
    validated = subprocess.run(["cargo", "run", "-q", "-p", "sdm-data", "--bin", "sdm-dataset", "--locked", "--", "validate", str(dataset_path)], cwd=ROOT, capture_output=True, text=True, check=True)
    dataset_sha = validated.stdout.strip().split()[-1]
    test_ids = sorted(e["case_id"] for e in examples)
    split = {"version": 3, "dataset_sha256": dataset_sha, "seed": 170018 if cohort == "final" else 170017, "train": [], "dev": [], "test": test_ids, "excluded": [], "fingerprint": ""}
    split["fingerprint"] = "sha256:" + hashlib.sha256(canonical(split)).hexdigest()
    split_path = output_dir / "typed-choice.split.json"
    split_bytes = (json.dumps(split, indent=2) + "\n").encode()
    if split_path.exists() and split_path.read_bytes() != split_bytes:
        raise FileExistsError(f"refusing to replace different split {split_path}")
    split_path.write_bytes(split_bytes)
    return dataset_path, split_path, provenance


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    dataset, split, _ = materialize(args.cohort, args.out)
    print(json.dumps({"dataset": str(dataset), "split": str(split)}, indent=2))


if __name__ == "__main__":
    main()
