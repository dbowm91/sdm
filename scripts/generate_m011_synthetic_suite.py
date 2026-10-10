#!/usr/bin/env python3
"""Generate fresh, deterministic M011 mechanics suites from versioned templates."""
import copy
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures"
N = 300
SEED = 11011


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
    pair_rng = random.Random(SEED + i // 2)
    active = i % 2 == 1
    available = (i // 2) % 7 not in (0, 1)
    load = pair_rng.randrange(0, 101) / 10
    ex["case_id"] = f"m011-{task}-{i:03}"
    ex["leakage_group"] = f"m011-{task}-group-{i // 2:03}"
    ex["counterfactual_pair"] = f"m011-{task}-pair-{i // 2:03}"
    ex["family"] = f"m011-{task}-generated-v1"
    ex["request"]["request_id"] = f"m011-{task}-request-{i:03}"
    tf = ex["typed_rank_features"]
    values = {"active": active, "available": available, "load": load,
              "note": f"release sample {i} load {int(load * 10)}",
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
        value = 1.0 + 4.0 * (0.6 * load / 10.0 + 0.4 * float(active))
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


def main():
    rng = random.Random(SEED)
    for task in ("binary", "choice", "score", "rank"):
        provenance, source = template(task)
        provenance = dict(provenance)
        provenance.update({"source": "SDM M011 synthetic generated suite v1",
                           "label_lineage": f"generator scripts/generate_m011_synthetic_suite.py; seed {SEED}; deterministic {task} rule"})
        examples = [make(task, i, source, rng) for i in range(1, N + 1)]
        (OUT / f"m011-{task}-v1.json").write_text(json.dumps({"provenance": provenance, "examples": examples}, indent=2) + "\n")


if __name__ == "__main__":
    main()
