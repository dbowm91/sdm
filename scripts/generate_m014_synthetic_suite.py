#!/usr/bin/env python3
"""Regenerate M014's independent synthetic Binary and Choice groups in target/."""
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
OUT = ROOT / "target" / "m014"
SEED = 140_014
GROUPS = 1_200
TEST_FAMILIES = ("text-shift", "combined-shift", "load-shift", "unknown-vocab")
REQUIRED_FAMILIES = ("id-a", "id-b", *TEST_FAMILIES)


def canonical_schema_hash(schema):
    schema = copy.deepcopy(schema)
    schema["fields"].sort(key=lambda f: f["id"])
    for field in schema["fields"]:
        field["categories"].sort()
    return "sha256:" + hashlib.sha256(json.dumps(schema, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def family(group):
    if group < 300:
        return "train-id-a"
    if group < 600:
        return "train-id-b"
    if group < 700:
        return "id-a"
    if group < 800:
        return "id-b"
    return TEST_FAMILIES[(group - 800) // 100]


def add_rule_feature(example):
    tf = example["typed_rank_features"]
    schema = tf["schema"]
    schema["fields"].append({"id": "rule_family", "value_type": "category", "required": True, "categories": ["rule_a", "rule_b"]})
    digest = canonical_schema_hash(schema)
    for projection in [tf["context"], *tf["candidates"].values()]:
        projection["schema_sha256"] = digest
        projection["fields"].append({"id": "rule_family", "required": True, "value": {"type": "category", "value": "rule_a"}})
    return digest


def set_projection(projection, values):
    for field in projection["fields"]:
        if field["id"] in values:
            field["value"]["value"] = values[field["id"]]


def make_example(task, group, active, source):
    fam = family(group)
    rng = random.Random(SEED + group * 7919)
    available = group % 3 != 0
    rule_b = bool(group % 2)
    load = round(rng.uniform(0, 10), 2)
    note = f"routine service record case{group % 37}"
    if fam in ("load-shift", "combined-shift"):
        load = round(rng.uniform(15, 25), 2)
    if fam in ("text-shift", "combined-shift"):
        note = f"quartz nebula payload token{group % 29}"
    elif fam == "unknown-vocab":
        note = f"m014 xenolith lexeme token{group % 23}"
    ex = copy.deepcopy(source)
    ex_id = f"m014-{task}-{group:04}-{int(active)}"
    ex.update({
        "case_id": ex_id,
        "leakage_group": f"m014-{task}-group-{group:04}",
        "counterfactual_pair": f"m014-{task}-pair-{group:04}",
        "family": f"m014-{task}-{fam}-v1",
    })
    ex["request"]["request_id"] = ex_id + "-request"
    rule = "rule_b" if rule_b else "rule_a"
    values = {"active": active, "available": available, "load": load, "note": note,
              "task_kind": "choice" if task == "choice" else "binary", "rule_family": rule}
    tf = ex["typed_rank_features"]
    set_projection(tf["context"], values)
    if task == "binary":
        ex["label"] = {"kind": "binary", "value": bool(active and available)}
        return ex

    semantic_yes = (not active) if rule_b else active
    ids = {"yes": f"item-{group:04}-q", "no": f"item-{group:04}-z"}
    if group % 2:
        ids = {"yes": ids["no"], "no": ids["yes"]}
    options = [{"id": ids[role], "label": f"Option {role.upper()}"} for role in ("yes", "no")]
    if (group // 3) % 2:
        options.reverse()
    ex["request"]["spec"]["options"] = options
    ex["typed_rank_features"]["candidates"] = {}
    source_candidates = source["typed_rank_features"]["candidates"]
    for role in ("yes", "no"):
        projection = copy.deepcopy(source_candidates[role])
        set_projection(projection, {**values, "task_kind": role})
        ex["typed_rank_features"]["candidates"][ids[role]] = projection
    ex["label"] = {"kind": "choice", "value": ids["yes" if semantic_yes else "no"] if available else None}
    return ex


def normalized_pair(row):
    row = copy.deepcopy(row)
    row["case_id"] = "<case>"
    row["request"]["request_id"] = "<request>"
    row["label"]["value"] = "<target>"
    for projection in [row["typed_rank_features"]["context"], *row["typed_rank_features"]["candidates"].values()]:
        for field in projection["fields"]:
            if field["id"] == "active":
                field["value"]["value"] = "<active>"
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    outputs = {}
    for task in ("binary", "choice"):
        base = json.loads((FIXTURES / f"synthetic-{task}-typed-v1.json").read_text())
        source = copy.deepcopy(base["examples"][0])
        if task == "choice":
            for option in source["request"]["spec"]["options"]:
                option["id"] = option["label"].lower().replace(" ", "-")
        add_rule_feature(source)
        examples = [make_example(task, group, active, source)
                    for group in range(GROUPS) for active in (False, True)]
        for i in range(0, len(examples), 2):
            if normalized_pair(examples[i]) != normalized_pair(examples[i + 1]):
                raise ValueError(f"counterfactual pair changed more than active: {examples[i]['counterfactual_pair']}")
        provenance = {
            "source": "SDM M014 deterministic synthetic quality suite v1",
            "license": "MIT",
            "consent_scope": "synthetic-only; no human or application data",
            "label_lineage": f"{Path(__file__).relative_to(ROOT)} sha256:{source_sha}; seed={SEED}; groups={GROUPS}; source-defined active/available and rule-family truth functions",
            "redistributable": True,
        }
        path = OUT / f"{task}.json"
        path.write_text(json.dumps({"provenance": provenance, "examples": examples}, indent=2, ensure_ascii=False) + "\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        outputs[task] = {"path": str(path.relative_to(ROOT)), "sha256": f"sha256:{digest}", "examples": len(examples),
                         "groups": GROUPS, "test_family_groups": {name: 100 for name in REQUIRED_FAMILIES}}
    print(json.dumps({"seed": SEED, "generator_sha256": f"sha256:{source_sha}", "outputs": outputs}, indent=2))


if __name__ == "__main__":
    main()
