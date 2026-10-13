#!/usr/bin/env python3
"""Generate bounded M015 TRAIN/DEV-only synthetic Choice research data."""
import argparse
import hashlib
import json
import os
import random
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ("all_required", "any_required", "exclusive", "threshold", "category_and_flag")
ALLOWED_GROUPS = (2_000, 10_000, 50_000)
SEED = 150_015


def split_for(group_id):
    # Hold out one of every eleven five-group family blocks for DEV. This yields
    # exactly 10% DEV while preserving the requested TRAIN-group budget.
    return "dev" if (group_id // len(RULES)) % 11 == 0 else "train"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def rule_label(rule, context, candidate):
    """Independent target checker. Reject malformed/unknown descriptors."""
    if not isinstance(context, dict) or not isinstance(candidate, dict):
        raise ValueError("context and candidate must be objects")
    if not isinstance(rule, dict) or set(rule) != {"name", "operands"}:
        raise ValueError("rule descriptor must have exactly name and operands")
    name, operands = rule["name"], rule["operands"]
    if not isinstance(operands, dict):
        raise ValueError("rule operands must be an object")
    feature_list = operands.get("features")
    valid_features = isinstance(feature_list, list) and bool(feature_list) and all(isinstance(k, str) and k for k in feature_list) and len(set(feature_list)) == len(feature_list)
    if name == "all_required" and set(operands) == {"features"} and valid_features:
        return all(candidate.get(k) is True for k in operands["features"])
    if name == "any_required" and set(operands) == {"features"} and valid_features:
        return any(candidate.get(k) is True for k in operands["features"])
    if name == "exclusive" and set(operands) == {"features", "invert"} and valid_features and isinstance(operands["invert"], bool):
        return (sum(candidate.get(k) is True for k in operands["features"]) == 1) != operands["invert"]
    if name == "threshold" and set(operands) == {"feature", "minimum"} and isinstance(operands["feature"], str) and isinstance(operands["minimum"], (int, float)) and not isinstance(operands["minimum"], bool) and -100 <= operands["minimum"] <= 100:
        return isinstance(candidate.get(operands["feature"]), (int, float)) and not isinstance(candidate.get(operands["feature"]), bool) and candidate[operands["feature"]] >= operands["minimum"]
    if name == "category_and_flag" and set(operands) == {"category_feature", "category", "flag_feature", "numeric_feature", "minimum"} and all(isinstance(operands[k], str) and operands[k] for k in ("category_feature", "category", "flag_feature", "numeric_feature")) and isinstance(operands["minimum"], (int, float)) and not isinstance(operands["minimum"], bool) and -100 <= operands["minimum"] <= 100:
        return candidate.get(operands["category_feature"]) == operands["category"] and candidate.get(operands["flag_feature"]) is True and candidate.get(operands["numeric_feature"], -101) >= operands["minimum"]
    raise ValueError(f"malformed operands for rule {name!r}")


def _rule_for(rng, name):
    if name in ("all_required", "any_required", "exclusive"):
        operands = {"features": ["alpha", "beta"]}
        if name == "exclusive":
            operands["invert"] = bool(rng.randrange(2))
        return {"name": name, "operands": operands}
    if name == "threshold":
        return {"name": name, "operands": {"feature": "capacity", "minimum": 5}}
    return {"name": name, "operands": {"category_feature": "kind", "category": "primary", "flag_feature": "enabled", "numeric_feature": "capacity", "minimum": 5}}


def _label_with_source(rule, candidate):
    """Labeling implementation kept separate from the public oracle checker."""
    name = rule["name"]
    if name == "all_required":
        return bool(candidate.get("alpha")) and bool(candidate.get("beta"))
    if name == "any_required":
        return bool(candidate.get("alpha")) or bool(candidate.get("beta"))
    if name == "exclusive":
        return (bool(candidate.get("alpha")) != bool(candidate.get("beta"))) != rule["operands"]["invert"]
    if name == "threshold":
        return candidate.get("capacity", -101) >= 5
    if name == "category_and_flag":
        return candidate.get("kind") == "primary" and candidate.get("enabled") is True and candidate.get("capacity", -101) >= rule["operands"]["minimum"]
    raise ValueError(f"unknown source rule: {name}")


def _satisfying_candidate(rng, name, rule):
    if name == "threshold":
        return {"capacity": 7, "kind": "primary", "enabled": True, "alpha": True, "beta": False}
    if name == "category_and_flag":
        return {"capacity": 3, "kind": "primary", "enabled": True, "alpha": True, "beta": False}
    if name == "exclusive":
        return {"capacity": 3, "kind": "other", "enabled": False, "alpha": True, "beta": False}
    if name == "any_required":
        return {"capacity": 3, "kind": "other", "enabled": False, "alpha": True, "beta": False}
    return {"capacity": 3, "kind": "other", "enabled": False, "alpha": True, "beta": True}


def make_group(group_id, seed):
    rng = random.Random(seed + group_id * 7919)
    name = RULES[group_id % len(RULES)]
    rule = _rule_for(rng, name)
    cardinality = 2 + rng.randrange(7)
    candidates = []
    semantic_roles = []
    for i in range(cardinality):
        if name == "threshold":
            value = 7 if i == 0 else rng.randrange(0, 5)
            cand = {"capacity": value, "kind": "primary" if i == 0 else "other", "enabled": i == 0, "alpha": i == 0, "beta": False}
        elif name == "category_and_flag":
            cand = {"capacity": 7 if i == 0 else i, "kind": "primary" if i == 0 else "other", "enabled": i == 0, "alpha": i == 0, "beta": False}
        elif name == "all_required":
            cand = {"capacity": i, "kind": "other", "enabled": False, "alpha": i == 0, "beta": i == 0}
        elif name == "any_required":
            cand = {"capacity": i, "kind": "other", "enabled": False, "alpha": i == 0, "beta": False}
        elif name == "exclusive":
            invert = rule["operands"]["invert"]
            cand = {"capacity": i, "kind": "other", "enabled": False, "alpha": i == 0 or invert, "beta": i == 0 and invert}
        else:
            cand = {"capacity": i, "kind": "other", "enabled": False, "alpha": i == 0, "beta": False}
        candidates.append(cand)
        semantic_roles.append(i == 0)
    # Stratify answerability independently within every five-family block so
    # it cannot be decoded from family and each family has both classes.
    block = group_id // len(RULES)
    available = (block // 11) % 5 != 0
    # Paired nuisance rows preserve causal values. A second pair applies one
    # declared causal flip on answerable groups only.
    group_key = f"m015-g{group_id:06d}"
    rows = []
    ids = [f"tc-{rng.getrandbits(40):010x}" for _ in candidates]
    for variant in (0, 1):
        order = list(range(cardinality))
        if variant:
            order.reverse()
        chosen = next((ids[i] for i, c in enumerate(candidates) if _label_with_source(rule, c)), None) if available else None
        rows.append({
            "case_id": f"{group_key}-n{variant}", "group_id": group_key,
            "pair_id": f"{group_key}-nuisance", "pair_type": "nuisance", "family": f"m015-{name}-v1",
            "split": split_for(group_id),
            "track": "rule_conditioned" if name == "exclusive" else "fixed_rule",
            "rule": rule,
            "context": {"active": bool(group_id % 2), "available": available, "load": round(rng.random() * 10 + (15 if variant else 0), 3), "note": "routine status record" if variant == 0 else "quartz basalt record", "memo": None if variant else "optional"},
            "options": [{"id": ids[i], "semantics": candidates[i]} for i in order],
            "label": chosen,
            "oracle": {"satisfying_option_count": sum(rule_label(rule, {}, c) for c in candidates), "available": available},
        })
    if available:
        flipped = [dict(candidate) for candidate in candidates]
        causal_field = {"all_required": "beta", "any_required": "alpha", "exclusive": "alpha", "threshold": "capacity", "category_and_flag": "enabled"}[name]
        if name == "all_required":
            flipped[0][causal_field] = False
        elif name == "any_required":
            flipped[0][causal_field] = False
            flipped[0]["beta"] = False
        elif name == "exclusive":
            flipped[0][causal_field] = not flipped[0][causal_field]
        elif name == "threshold":
            flipped[0][causal_field] = 4
        elif name == "category_and_flag":
            flipped[0][causal_field] = False
        if any(rule_label(rule, {}, candidate) for candidate in flipped):
            raise AssertionError(f"causal flip failed to alter target for {name}")
        causal_pair = f"{group_key}-causal"
        rows.append({
            "case_id": f"{causal_pair}-before", "group_id": group_key, "pair_id": causal_pair,
            "pair_type": "causal_flip", "causal_feature": causal_field, "family": f"m015-{name}-v1",
            "split": split_for(group_id), "track": "rule_conditioned" if name == "exclusive" else "fixed_rule",
            "rule": rule, "context": {"active": bool(group_id % 2), "available": True, "load": 3.0, "note": "causal control", "memo": "optional"},
            "options": [{"id": ids[i], "semantics": candidates[i]} for i in range(cardinality)],
            "label": ids[next(i for i, candidate in enumerate(candidates) if rule_label(rule, {}, candidate))],
            "oracle": {"satisfying_option_count": 1, "available": True},
        })
        rows.append({
            "case_id": f"{causal_pair}-after", "group_id": group_key, "pair_id": causal_pair,
            "pair_type": "causal_flip", "causal_feature": causal_field, "family": f"m015-{name}-v1",
            "split": split_for(group_id), "track": "rule_conditioned" if name == "exclusive" else "fixed_rule",
            "rule": rule, "context": {"active": bool(group_id % 2), "available": True, "load": 3.0, "note": "causal control", "memo": "optional"},
            "options": [{"id": ids[i], "semantics": flipped[i]} for i in range(cardinality)],
            "label": None, "oracle": {"satisfying_option_count": 0, "available": True},
        })
    return rows


def write_atomic(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            return digest
        raise FileExistsError(f"refusing to overwrite different M015 output: {path}")
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name): os.unlink(temp_name)
    return digest


def write_split(path, split, groups, seed):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    digest = hashlib.sha256()
    total_groups = groups + groups // 10
    try:
        with os.fdopen(fd, "wb") as f:
            for group_id in range(total_groups):
                if split_for(group_id) != split:
                    continue
                for row in make_group(group_id, seed):
                    data = _canonical(row) + b"\n"
                    digest.update(data)
                    f.write(data)
            f.flush(); os.fsync(f.fileno())
        hexdigest = digest.hexdigest()
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() == hexdigest:
                os.unlink(temp_name)
                return hexdigest
            raise FileExistsError(f"refusing to overwrite different M015 output: {path}")
        os.replace(temp_name, path)
        return hexdigest
    finally:
        if os.path.exists(temp_name): os.unlink(temp_name)


def generate(out, groups, seed):
    if groups not in ALLOWED_GROUPS:
        raise ValueError(f"groups must be one of {ALLOWED_GROUPS}")
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be a uint32")
    out = Path(out)
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output_hashes = {}
    for split in ("train", "dev"):
        output_hashes[split] = write_split(out / f"{split}.jsonl", split, groups, seed)
    total_groups = groups + groups // 10
    dev_groups = sum(split_for(i) == "dev" for i in range(total_groups))
    train_groups = total_groups - dev_groups
    if train_groups != groups:
        raise AssertionError(f"train group budget drift: requested {groups}, generated {train_groups}")
    manifest = {"format": "sdm-m015-dataset-v1", "generator_sha256": source_sha, "task_spec_sha256": hashlib.sha256((ROOT / "docs/m015-task-spec-v1.md").read_bytes()).hexdigest(), "seed": seed, "independent_groups": total_groups, "train_groups": train_groups, "dev_groups": dev_groups, "rows_per_group_min": 2, "rows_per_group_max": 4, "pair_types": ["nuisance", "causal_flip"], "rules": list(RULES), "outputs_sha256": output_hashes, "final_partition": "not constructed", "provenance": "synthetic-only; MIT; no external or application data"}
    write_atomic(out / "manifest.json", json.dumps(manifest, sort_keys=True, indent=2).encode() + b"\n")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "target/m015")
    ap.add_argument("--groups", type=int, choices=ALLOWED_GROUPS, default=2_000)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    print(json.dumps(generate(args.out, args.groups, args.seed), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
