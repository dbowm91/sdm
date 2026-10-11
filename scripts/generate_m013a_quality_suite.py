#!/usr/bin/env python3
"""Generate the fresh M013a synthetic suite with checked one-factor pairs."""
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
N_GROUPS = 1532
SEED = 14014
def family_for(group):
    if group < 666: return "id-a"
    if group < 1332: return "id-b"
    if group < 1399: return "load-shift"
    if group < 1466: return "text-shift"
    return "combined-shift"

def read(path):
    return json.loads((FIX / path).read_text())

def schema_hash(schema):
    canonical = copy.deepcopy(schema)
    canonical["fields"].sort(key=lambda f: f["id"])
    for field in canonical["fields"]:
        field["categories"].sort()
    raw = json.dumps(canonical, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def set_values(projection, values):
    for field in projection["fields"]:
        if field["id"] in values:
            field["value"]["value"] = values[field["id"]]

def prepare(base, rule_categories):
    schema = base["typed_rank_features"]["schema"]
    schema["fields"].append({"id":"rule_family", "value_type":"category", "required":True, "categories":rule_categories})
    digest = schema_hash(schema)
    def update(proj):
        proj["schema_sha256"] = digest
        proj["fields"].append({"id":"rule_family", "required":True, "value":{"type":"category","value":rule_categories[0]}})
    tf = base["typed_rank_features"]
    update(tf["context"])
    for projection in tf["candidates"].values(): update(projection)
    return digest

def make_example(task, group, side, source, rng):
    family = family_for(group)
    rule = "rule_b" if group % 2 else "rule_a"
    active = bool(side)
    available = (group % 3 != 0)
    load = rng.randrange(0, 101) / 10
    note = f"routine service record {group % 31}"
    if family in ("load-shift", "combined-shift"): load = 12 + rng.randrange(0, 81) / 10
    if family in ("text-shift", "combined-shift"): note = f"quartz nebula payload {group % 17}"
    rule_value = "b" if rule == "rule_b" else "a"
    ex = copy.deepcopy(source)
    ex.update({"case_id":f"m013a-{task}-{group:04}-{side}", "leakage_group":f"m013a-{task}-group-{group:04}",
               "counterfactual_pair":f"m013a-{task}-pair-{group:04}", "family":f"m013a-{task}-{family}-v1"})
    ex["request"]["request_id"] = ex["case_id"] + "-request"
    values = {"active":active, "available":available, "load":load, "note":note,
              "task_kind":"choice" if task == "choice" else "binary", "rule_family":rule_value}
    tf = ex["typed_rank_features"]
    set_values(tf["context"], values)
    if task == "binary":
        ex["label"] = {"kind":"binary", "value":bool(active and available)}
    else:
        # Rule A selects yes when active; Rule B selects yes when inactive.
        semantic_yes = active if rule == "rule_a" else not active
        target_role = "yes" if semantic_yes else "no"
        id_map = {"yes":"alpha", "no":"beta"} if group % 3 else {"yes":"beta", "no":"alpha"}
        options = [{"id":id_map["yes"],"label":"Option A"},{"id":id_map["no"],"label":"Option B"}]
        if group % 2: options.reverse()
        ex["request"]["spec"]["options"] = options
        candidate_sources = tf["candidates"]
        ex["typed_rank_features"]["candidates"] = {}
        for role in ("yes", "no"):
            p = copy.deepcopy(candidate_sources[role])
            set_values(p, {**values,"task_kind":role})
            ex["typed_rank_features"]["candidates"][id_map[role]] = p
        ex["label"] = {"kind":"choice", "value":id_map[target_role] if available else None}
    return ex

def validate_pairs(examples):
    pairs={}
    for e in examples: pairs.setdefault(e["counterfactual_pair"],[]).append(e)
    for pair, rows in pairs.items():
        if len(rows)!=2 or rows[0]["leakage_group"]!=rows[1]["leakage_group"]:
            raise ValueError(f"malformed pair {pair}")
        normalized=[]
        for row in rows:
            x=copy.deepcopy(row)
            x["case_id"]="<case>"; x["request"]["request_id"]="<request>"
            x["label"]["value"]="<target>"
            for projection in [x["typed_rank_features"]["context"],*x["typed_rank_features"]["candidates"].values()]:
                for field in projection["fields"]:
                    if field["id"]=="active":field["value"]["value"]="<active>"
            normalized.append(x)
        if normalized[0]!=normalized[1]: raise ValueError(f"pair changes more than active: {pair}")

def main():
    sources = {}
    for task in ("binary","choice"):
        bundle = read(f"synthetic-{task}-typed-v1.json")
        source = copy.deepcopy(bundle["examples"][0])
        if task == "choice":
            # Normalize option identities; the generator applies independent per-group relabeling.
            for o in source["request"]["spec"]["options"]: o["id"] = o["label"].lower()
        prepare(source, ["a","b"])
        sources[task] = bundle["provenance"], source
    for task, (old_provenance, source) in sources.items():
        examples = []
        for group in range(N_GROUPS):
            for side in (0,1):
                # Reinitialize from the group identity so both rows share every
                # random nuisance value; only the declared active field flips.
                rng = random.Random(SEED + group * 19)
                examples.append(make_example(task, group, side, source, rng))
        validate_pairs(examples)
        provenance = {"source":"SDM M013a deterministic synthetic quality suite v1", "license":"MIT",
                      "consent_scope":"synthetic-only; no human or application data",
                      "label_lineage":f"scripts/generate_m013a_quality_suite.py; seed {SEED}; rule and nuisance family definitions are versioned here",
                      "redistributable":True}
        (FIX / f"m013a-{task}-v1.json").write_text(json.dumps({"provenance":provenance,"examples":examples},indent=2)+"\n")

if __name__ == "__main__": main()
