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
    # Stratify each contiguous block of five rule families while keeping pairs intact.
    return "dev" if (group_id // len(RULES)) % 10 == 0 else "train"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def rule_label(rule, context, candidate):
    """Independent target checker. Reject malformed/unknown descriptors."""
    if not isinstance(rule, dict) or set(rule) != {"name", "operands"}:
        raise ValueError("rule descriptor must have exactly name and operands")
    name, operands = rule["name"], rule["operands"]
    if name == "all_required" and set(operands) == {"features"} and isinstance(operands["features"], list) and operands["features"]:
        return all(candidate.get(k) is True for k in operands["features"])
    if name == "any_required" and set(operands) == {"features"} and isinstance(operands["features"], list) and operands["features"]:
        return any(candidate.get(k) is True for k in operands["features"])
    if name == "exclusive" and set(operands) == {"features"} and isinstance(operands["features"], list) and operands["features"]:
        return sum(candidate.get(k) is True for k in operands["features"]) == 1
    if name == "threshold" and set(operands) == {"feature", "minimum"} and isinstance(operands["feature"], str) and isinstance(operands["minimum"], (int, float)) and not isinstance(operands["minimum"], bool) and -100 <= operands["minimum"] <= 100:
        return isinstance(candidate.get(operands["feature"]), (int, float)) and not isinstance(candidate.get(operands["feature"]), bool) and candidate[operands["feature"]] >= operands["minimum"]
    if name == "category_and_flag" and set(operands) == {"category_feature", "category", "flag_feature"} and isinstance(operands["category"], str):
        return candidate.get(operands["category_feature"]) == operands["category"] and candidate.get(operands["flag_feature"]) is True
    raise ValueError(f"malformed operands for rule {name!r}")


def _rule_for(rng, name):
    if name in ("all_required", "any_required", "exclusive"):
        return {"name": name, "operands": {"features": ["alpha", "beta"]}}
    if name == "threshold":
        return {"name": name, "operands": {"feature": "capacity", "minimum": 5}}
    return {"name": name, "operands": {"category_feature": "kind", "category": "primary", "flag_feature": "enabled"}}


def _label_with_source(name, candidate):
    """Labeling implementation kept separate from the public oracle checker."""
    if name == "all_required":
        return bool(candidate.get("alpha")) and bool(candidate.get("beta"))
    if name == "any_required":
        return bool(candidate.get("alpha")) or bool(candidate.get("beta"))
    if name == "exclusive":
        return bool(candidate.get("alpha")) != bool(candidate.get("beta"))
    if name == "threshold":
        return candidate.get("capacity", -101) >= 5
    if name == "category_and_flag":
        return candidate.get("kind") == "primary" and candidate.get("enabled") is True
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
            cand = {"capacity": i, "kind": "primary" if i == 0 else "other", "enabled": i == 0, "alpha": i == 0, "beta": False}
        elif name == "all_required":
            cand = {"capacity": i, "kind": "other", "enabled": False, "alpha": i == 0, "beta": i == 0}
        elif name == "any_required":
            cand = {"capacity": i, "kind": "other", "enabled": False, "alpha": i == 0, "beta": False}
        else:
            cand = {"capacity": i, "kind": "other", "enabled": False, "alpha": i == 0, "beta": False}
        candidates.append(cand)
        semantic_roles.append(i == 0)
    available = group_id % 5 != 0
    # Paired rows differ only in a nuisance perturbation; causal values are shared.
    pair_id = f"m015-g{group_id:06d}"
    rows = []
    ids = [f"tc-{rng.getrandbits(40):010x}" for _ in candidates]
    for variant in (0, 1):
        order = list(range(cardinality))
        if variant:
            order.reverse()
        chosen = next((ids[i] for i, c in enumerate(candidates) if _label_with_source(name, c)), None) if available else None
        rows.append({
            "case_id": f"{pair_id}-v{variant}", "group_id": pair_id,
            "pair_id": pair_id, "family": f"m015-{name}-v1",
            "split": split_for(group_id),
            "track": "fixed_rule" if group_id % 2 == 0 else "rule_conditioned",
            "rule": rule,
            "context": {"active": bool(group_id % 2), "available": available, "load": round(rng.random() * 10 + (15 if variant else 0), 3), "note": f"nuisance-{variant}-{rng.randrange(100000)}", "memo": None if variant else "optional"},
            "options": [{"id": ids[i], "semantics": candidates[i]} for i in order],
            "label": chosen,
            "oracle": {"satisfying_option_count": sum(rule_label(rule, {}, c) for c in candidates), "available": available},
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
    try:
        with os.fdopen(fd, "wb") as f:
            for group_id in range(groups):
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
    dev_groups = sum(split_for(i) == "dev" for i in range(groups))
    manifest = {"format": "sdm-m015-dataset-v1", "generator_sha256": source_sha, "task_spec_sha256": hashlib.sha256((ROOT / "docs/m015-task-spec-v1.md").read_bytes()).hexdigest(), "seed": seed, "independent_groups": groups, "train_groups": groups - dev_groups, "dev_groups": dev_groups, "rows_per_group": 2, "rules": list(RULES), "outputs_sha256": output_hashes, "final_partition": "not constructed", "provenance": "synthetic-only; MIT; no external or application data"}
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
