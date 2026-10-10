#!/usr/bin/env python3
"""Generate fresh, deterministic M011 mechanics suites from versioned templates."""
import copy
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures"
N = 400
SEED = 11012


def read(name):
    return json.loads((OUT / name).read_text())


def set_projection(projection, values):
    for field in projection["fields"]:
        if field["id"] in values:
            field["value"]["value"] = values[field["id"]]


def template(task):
    name = "standalone-typed-rank-v1.json" if task == "rank" else f"synthetic-{task}-typed-v1.json"
    bundle = read(name)
    return bundle["provenance"], bundle["examples"][0]


def make(task, i, source, rng):
    ex = copy.deepcopy(source)
    # Adjacent rows form a true counterfactual pair: only active flips.
    pair_index = i // 2
    pair_rng = random.Random(SEED + pair_index)
    active = i % 2 == 1
    available = pair_index % 7 not in (0, 1)
    ood_family = pair_index != 0 and pair_index % 8 == 0
    excluded_family = not ood_family and pair_index % 37 == 0
    load = 12.0 + pair_rng.randrange(0, 81) / 10 if ood_family else pair_rng.randrange(0, 101) / 10
    ex["case_id"] = f"m011-{task}-{i:03}"
    ex["leakage_group"] = f"m011-{task}-group-{i // 2:03}"
    ex["counterfactual_pair"] = f"m011-{task}-pair-{i // 2:03}"
    ex["family"] = (
        f"m011-{task}-ood-v2" if ood_family else
        f"m011-{task}-excluded-v2" if excluded_family else
        f"m011-{task}-generated-v2"
    )
    ex["request"]["request_id"] = f"m011-{task}-request-{i:03}"
    tf = ex["typed_rank_features"]
    values = {"active": active, "available": available, "load": load,
              "note": "quartz nebula telemetry record" if ood_family else f"release sample {pair_index} load {int(load * 10)}",
              "task_kind": "source" if task == "rank" else task}
    set_projection(tf["context"], values)
    if task == "binary":
        ex["label"] = {"kind": "binary", "value": bool(active and available)}
    elif task == "choice":
        target = None if not available else ("yes" if active else "no")
        ex["label"] = {"kind": "choice", "value": target}
        for key, projection in tf["candidates"].items():
            set_projection(projection, {**values, "task_kind": key})
    elif task == "score":
        value = 1.0 + 4.0 * (0.6 * min(load, 10.0) / 10.0 + 0.4 * float(active))
        ex["label"] = {"kind": "score", "value": round(value, 6)}
    elif task == "rank":
        candidates = ex["request"]["spec"]["candidates"]
        ranked = sorted(candidates, key=lambda c: c["id"])
        chosen = ranked[0 if active else -1]["id"]
        relevance = {c["id"]: (1.0 if available and c["id"] == chosen else 0.0) for c in candidates}
        ex["label"] = {"kind": "rank", "value": {"relevance": relevance, "no_relevant": not available}}
        for candidate_id, projection in tf["candidates"].items():
            set_projection(projection, {**values, "task_kind": "source" if candidate_id == "relevant" else "calendar"})
    return ex


def check_counterfactual_pairs(examples):
    groups = {}
    for example in examples:
        groups.setdefault(example["counterfactual_pair"], []).append(example)
    for pair_id, members in groups.items():
        if len(members) != 2 or members[0]["leakage_group"] != members[1]["leakage_group"]:
            raise ValueError(f"counterfactual pair {pair_id} is malformed")
        left, right = (copy.deepcopy(member) for member in members)
        left["request"].pop("request_id", None)
        right["request"].pop("request_id", None)
        for member in (left, right):
            tf = member["typed_rank_features"]
            for projection in [tf["context"], *tf["candidates"].values()]:
                for field in projection["fields"]:
                    if field["id"] == "active":
                        field["value"]["value"] = False
        if left["request"] != right["request"] or left["typed_rank_features"] != right["typed_rank_features"]:
            raise ValueError(f"counterfactual pair {pair_id} changes more than active")


def main():
    rng = random.Random(SEED)
    for task in ("binary", "choice", "score", "rank"):
        provenance, source = template(task)
        provenance = dict(provenance)
        provenance.update({"source": "SDM M011 synthetic generated suite v2",
                           "label_lineage": f"generator scripts/generate_m011_synthetic_suite.py; seed {SEED}; deterministic {task} rule"})
        examples = [make(task, i, source, rng) for i in range(N)]
        check_counterfactual_pairs(examples)
        (OUT / f"m011-v2-{task}.json").write_text(json.dumps({"provenance": provenance, "examples": examples}, indent=2) + "\n")


if __name__ == "__main__":
    main()
