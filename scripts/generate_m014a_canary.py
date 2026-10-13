#!/usr/bin/env python3
"""Generate M014a DEV-CANARY tiny synthetic cohort in target/m014a/canary/.

DEV-CANARY is explicitly NOT an independent final test and never becomes one.
It proves the entire scoring and adjudication path with every required gate
before M014b is allowed to freeze a NEW independent final cohort.

Tiny but sufficient for gate support tests: 420 groups per task (840 rows),
50 groups per required family (id-a, id-b, text-shift, combined-shift,
load-shift, unknown-vocab) plus 120 train groups. IDs are distinct
(m014a-canary-...) and never overlap M014/M013a FINAL groups. Includes
two-row Binary counterfactual pairs, Choice no-answer groups (available=False
for group%3==0), role/option permutations, and representative ID/text/load/OOD
families.
"""
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
OUT = ROOT / "target" / "m014a" / "canary"
SEED = 140_141
GROUPS = 570
TEST_FAMILIES = ("text-shift", "combined-shift", "load-shift", "unknown-vocab")
REQUIRED_FAMILIES = ("id-a", "id-b", *TEST_FAMILIES)
PREFIX = "m014a-canary"


def canonical_schema_hash(schema):
    schema = copy.deepcopy(schema)
    schema["fields"].sort(key=lambda f: f["id"])
    for field in schema["fields"]:
        field["categories"].sort()
    return "sha256:" + hashlib.sha256(json.dumps(schema, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def family(group: int) -> str:
    if group < 60:
        return "train-id-a"
    if group < 120:
        return "train-id-b"
    if group < 195:
        return "id-a"
    if group < 270:
        return "id-b"
    idx = (group - 270) // 75
    return TEST_FAMILIES[idx]


def add_rule_feature(example):
    tf = example["typed_rank_features"]
    schema = tf["schema"]
    # Avoid duplicating if source already has rule_family (synthetic-choice has no rule_family).
    if not any(f["id"] == "rule_family" for f in schema["fields"]):
        schema["fields"].append({"id": "rule_family", "value_type": "category", "required": True, "categories": ["rule_a", "rule_b"]})
    digest = canonical_schema_hash(schema)
    for projection in [tf["context"], *tf["candidates"].values()]:
        projection["schema_sha256"] = digest
        if not any(f["id"] == "rule_family" for f in projection["fields"]):
            projection["fields"].append({"id": "rule_family", "required": True, "value": {"type": "category", "value": "rule_a"}})
    return digest


def set_projection(projection, values):
    for field in projection["fields"]:
        if field["id"] in values:
            field["value"]["value"] = values[field["id"]]


def make_example(task: str, group: int, active: bool, source):
    fam = family(group)
    rng = random.Random(SEED + group * 7919)
    available = group % 3 != 0
    rule_b = bool(group % 2)
    load = round(rng.uniform(0, 10), 2)
    note = f"canary routine record case{group % 19}"
    if fam in ("load-shift", "combined-shift"):
        load = round(rng.uniform(15, 25), 2)
    if fam in ("text-shift", "combined-shift"):
        note = f"canary quartz payload token{group % 17}"
    elif fam == "unknown-vocab":
        note = f"canary xenolith lexeme token{group % 13}"
    ex = copy.deepcopy(source)
    ex_id = f"{PREFIX}-{task}-{group:04}-{int(active)}"
    ex.update({
        "case_id": ex_id,
        "leakage_group": f"{PREFIX}-{task}-group-{group:04}",
        "counterfactual_pair": f"{PREFIX}-{task}-pair-{group:04}",
        "family": f"{PREFIX}-{task}-{fam}-v1",
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
    ids = {"yes": f"citem-{group:04}-q", "no": f"citem-{group:04}-z"}
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
            "source": "SDM M014a DEV-CANARY synthetic suite v1 (NOT a final test)",
            "license": "MIT",
            "consent_scope": "synthetic-only; no human or application data",
            "label_lineage": f"{Path(__file__).relative_to(ROOT)} sha256:{source_sha}; seed={SEED}; groups={GROUPS}; canary active/available and rule-family truth functions; never for promotion",
            "redistributable": True,
        }
        path = OUT / f"{task}.json"
        path.write_text(json.dumps({"provenance": provenance, "examples": examples}, indent=2, ensure_ascii=False) + "\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        outputs[task] = {"path": str(path.relative_to(ROOT)), "sha256": f"sha256:{digest}", "examples": len(examples),
                         "groups": GROUPS, "test_family_groups": {name: 75 for name in REQUIRED_FAMILIES}}
    print(json.dumps({"seed": SEED, "generator_sha256": f"sha256:{source_sha}", "outputs": outputs, "canary": True,
                      "note": "DEV-CANARY explicitly NOT an independent final test and never becomes one"}, indent=2))


if __name__ == "__main__":
    main()
