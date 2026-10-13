#!/usr/bin/env python3
"""Generate M014b independent prospective Binary/Choice cohort in target/m014b/.

Distinct from M014 (seed 140014, IDs m014-*, rules AND/XOR, vocabs routine/quartz/xenolith),
M013a FINAL, and M014a canary (seed 140141, IDs m014a-canary-*, same old rules).
M014b uses seed 140142, IDs m014b-*, NEW structural label functions:
- Binary: (active AND available) XOR rule_b (vs M014 AND only). Flipping active
  flips truth when available (XOR), holds when unavailable (both rule_b).
- Choice: XNOR (NOT XOR): semantic_yes = (active == rule_b) i.e. NOT (active XOR rule_b)
  (vs M014 XOR). Flipping active still flips target for answerable cases.
Counterfactual pairs differ ONLY in active; all noncausal fields (available,
rule, load, note, IDs, order except active) identical within group. Includes
stable label-preserving OOD text-only/load-only/combined, unknown vocab,
option order/identity permutations, answerable (available) vs no-answer support.

570 groups/task (1140 rows), 75 per required family (id-a/id-b/text/combined/load/unknown)
+ 120 train groups. Never rerun/resplit/reuse M014 FINAL; no M013a test reuse.
"""
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
OUT = ROOT / "target" / "m014b"
SEED = 140_142
GROUPS = 570
TEST_FAMILIES = ("text-shift", "combined-shift", "load-shift", "unknown-vocab")
REQUIRED_FAMILIES = ("id-a", "id-b", *TEST_FAMILIES)
PREFIX = "m014b"


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
    # Distinct nuisance vocabularies, never overlapping M014/M013a FINAL or canary.
    load = round(rng.uniform(0, 10), 2)
    note = f"m014b ledger entry case{group % 23}"
    if fam in ("load-shift", "combined-shift"):
        load = round(rng.uniform(15, 25), 2)
    if fam in ("text-shift", "combined-shift"):
        note = f"m014b basalt signal token{group % 31}"
    elif fam == "unknown-vocab":
        note = f"m014b obsidian lexeme token{group % 27}"
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
        # NEW: (active AND available) XOR rule_b (distinct from M014 AND only).
        base = bool(active and available)
        ex["label"] = {"kind": "binary", "value": bool(base ^ rule_b)}
        return ex
    # NEW: XNOR (NOT XOR): semantic_yes = (active == rule_b) (distinct from M014 XOR).
    semantic_yes = (active == rule_b)
    ids = {"yes": f"bitem-{group:04}-q", "no": f"bitem-{group:04}-z"}
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
        examples = [make_example(task, group, active, source) for group in range(GROUPS) for active in (False, True)]
        for i in range(0, len(examples), 2):
            if normalized_pair(examples[i]) != normalized_pair(examples[i + 1]):
                raise ValueError(f"counterfactual pair changed more than active: {examples[i]['counterfactual_pair']}")
        provenance = {
            "source": "SDM M014b independent prospective quality suite v1",
            "license": "MIT",
            "consent_scope": "synthetic-only; no human or application data",
            "label_lineage": f"{Path(__file__).relative_to(ROOT)} sha256:{source_sha}; seed={SEED}; groups={GROUPS}; NEW Binary (AND XOR rule_b) and Choice XNOR truth functions; distinct from M014 AND/XOR and canary",
            "redistributable": True,
        }
        path = OUT / f"{task}.json"
        path.write_text(json.dumps({"provenance": provenance, "examples": examples}, indent=2, ensure_ascii=False) + "\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        outputs[task] = {"path": str(path.relative_to(ROOT)), "sha256": f"sha256:{digest}", "examples": len(examples), "groups": GROUPS, "test_family_groups": {name: 75 for name in REQUIRED_FAMILIES}}
    print(json.dumps({"seed": SEED, "generator_sha256": f"sha256:{source_sha}", "outputs": outputs, "distinct_rules": ["binary-AND-XOR-rule_b", "choice-XNOR"]}, indent=2))


if __name__ == "__main__":
    main()
