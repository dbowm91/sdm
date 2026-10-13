#!/usr/bin/env python3
"""Validate M015 TRAIN/DEV and emit development-only grouped baseline diagnostics."""
import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from generate_m015_suite import rule_label


def read_rows(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def accuracy(rows, predictor):
    return sum(predictor(row) == row["label"] for row in rows) / max(1, len(rows))


def bootstrap_group_ci(rows, predictor, seed=150015, reps=2000):
    groups = defaultdict(list)
    for row in rows:
        groups[row["group_id"]].append(row)
    keys = sorted(groups)
    if len(keys) < 2:
        return [None, None]
    rng = random.Random(seed)
    values = []
    for _ in range(reps):
        sample = [key for _ in keys for key in [rng.choice(keys)]]
        sampled = [row for key in sample for row in groups[key]]
        values.append(accuracy(sampled, predictor))
    values.sort()
    return [values[int(.025 * reps)], values[min(reps - 1, int(.975 * reps))]]


def score_rows(train, dev):
    by_group = defaultdict(set)
    for split, rows in (("train", train), ("dev", dev)):
        for row in rows:
            if row["split"] != split:
                raise ValueError(f"row assigned to wrong partition: {row['case_id']}")
            by_group[row["group_id"]].add(split)
    crossing = [key for key, splits in by_group.items() if len(splits) != 1]
    if crossing:
        raise ValueError(f"group leakage across partitions: {crossing[:3]}")
    disagreements = []
    for row in train + dev:
        matches = [o["id"] for o in row["options"] if rule_label(row["rule"], row["context"], o["semantics"])]
        expected = matches[0] if row["context"]["available"] and len(matches) == 1 else None
        if expected != row["label"]:
            disagreements.append(row["case_id"])
    if disagreements:
        raise ValueError(f"oracle disagreement: {disagreements[:3]}")

    pairs = defaultdict(list)
    for row in train + dev:
        pairs[row["pair_id"]].append(row)
    for pair_id, pair in pairs.items():
        if len(pair) != 2:
            raise ValueError(f"counterfactual pair {pair_id} has {len(pair)} rows")
        left, right = pair
        pair_type = left["pair_type"]
        if left["split"] != right["split"] or right["pair_type"] != pair_type:
            raise ValueError(f"pair split/type mismatch: {pair_id}")
        if pair_type == "nuisance":
            if left["label"] != right["label"]:
                raise ValueError(f"nuisance pair target changed: {pair_id}")
            allowed_context_changes = {"load", "note", "memo"}
            for key in set(left["context"]) | set(right["context"]):
                if key not in allowed_context_changes and left["context"].get(key) != right["context"].get(key):
                    raise ValueError(f"undeclared context change within nuisance pair: {pair_id}:{key}")
        elif pair_type == "causal_flip":
            if left["label"] == right["label"] or left["context"] != right["context"]:
                raise ValueError(f"causal pair failed to flip only target semantics: {pair_id}")
        else:
            raise ValueError(f"unknown pair type: {pair_type}")
        if {o["id"] for o in left["options"]} != {o["id"] for o in right["options"]}:
            raise ValueError(f"candidate identity changed within nuisance pair: {pair_id}")
        left_semantics = {o["id"]: o["semantics"] for o in left["options"]}
        right_semantics = {o["id"]: o["semantics"] for o in right["options"]}
        if pair_type == "nuisance":
            if left_semantics != right_semantics:
                raise ValueError(f"candidate semantics changed within nuisance pair: {pair_id}")
            if [o["id"] for o in left["options"]] == [o["id"] for o in right["options"]]:
                raise ValueError(f"option order did not change within nuisance pair: {pair_id}")
            if left["context"].get("load") == right["context"].get("load") or left["context"].get("note") == right["context"].get("note"):
                raise ValueError(f"declared nuisance perturbation missing within pair: {pair_id}")
        else:
            differences = [(option_id, key) for option_id in left_semantics for key in set(left_semantics[option_id]) | set(right_semantics[option_id]) if left_semantics[option_id].get(key) != right_semantics[option_id].get(key)]
            if len(differences) != 1 or differences[0][1] != left["causal_feature"] or [o["id"] for o in left["options"]] != [o["id"] for o in right["options"]]:
                raise ValueError(f"causal pair changed undeclared candidate fields: {pair_id}")

    def none(_row): return None
    def first(row): return row["options"][0]["id"] if row["context"]["available"] else None
    # The direct typed semantic oracle is an upper bound, not a learned baseline.
    def oracle(row):
        for option in row["options"]:
            if rule_label(row["rule"], row["context"], option["semantics"]):
                return option["id"] if row["context"]["available"] else None
        return None

    controls = {"always_none": none, "first_option": first, "synthetic_oracle_upper_bound": oracle}
    report = {
        "format": "sdm-m015-dev-report-v1", "partition": "DEV only",
        "train_rows": len(train), "dev_rows": len(dev),
        "train_groups": len({r["group_id"] for r in train}), "dev_groups": len({r["group_id"] for r in dev}),
        "oracle_disagreements": 0,
        "families": {name: sum(r["family"] == name for r in dev) for name in sorted({r["family"] for r in dev})},
        "tracks": {name: {"rows": sum(r["track"] == name for r in dev), "groups": len({r["group_id"] for r in dev if r["track"] == name}), "families": sorted({r["family"] for r in dev if r["track"] == name})} for name in sorted({r["track"] for r in dev})},
        "answerability_by_family": {name: {"groups": len({r["group_id"] for r in dev if r["family"] == name}), "answerable_groups": len({r["group_id"] for r in dev if r["family"] == name and r["context"]["available"]}), "no_answer_groups": len({r["group_id"] for r in dev if r["family"] == name and not r["context"]["available"]})} for name in sorted({r["family"] for r in dev})},
        "dev_accuracy": {name: {"value": accuracy(dev, fn), "group_bootstrap_95_ci": bootstrap_group_ci(dev, fn)} for name, fn in controls.items()},
        "learned_baselines": {"typed_linear": "run by scripts/run_m015_baselines.py on the identical M015 TRAIN/DEV typed corpus", "typed_cross": "run by scripts/run_m015_baselines.py on the identical M015 TRAIN/DEV typed corpus", "typed_compositional": "run by scripts/run_m015_baselines.py on the identical M015 TRAIN/DEV typed corpus"},
        "pair_controls": {"nuisance_pairs": sum(p[0]["split"] == "dev" and p[0]["pair_type"] == "nuisance" for p in pairs.values()), "causal_flip_pairs": sum(p[0]["split"] == "dev" and p[0]["pair_type"] == "causal_flip" for p in pairs.values()), "id_sets_preserved": True, "candidate_semantics_preserved_for_nuisance": True, "option_order_reversed_for_nuisance": True, "nuisance_fields_perturbed": True, "causal_pairs_change_one_declared_candidate_feature": True},
        "selection_policy": "No candidate or threshold selected. M017 final is not constructed.",
    }
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, default=Path("target/m015/train.jsonl"))
    ap.add_argument("--dev", type=Path, default=Path("target/m015/dev.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("target/m015/dev-report.json"))
    args = ap.parse_args()
    report = score_rows(read_rows(args.train), read_rows(args.dev))
    payload = json.dumps(report, sort_keys=True, indent=2).encode() + b"\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    report["report_sha256"] = hashlib.sha256(payload).hexdigest()
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
