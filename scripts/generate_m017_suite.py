#!/usr/bin/env python3
"""M017 prospective synthetic cohort generator (canary + final, held-out only).

Derived from the M015 TinyChoice semantics (same five rule families and
labeling truth), but a DISTINCT versioned generator as M017 requires:
- new namespace: m017-g###### groups, m017-<rule>-v1 families, fresh RNG
  stream (seeds 170017/170018), new nuisance surface vocabulary;
- held-out cohorts only: `canary` (60 groups, public parity cohort) and
  `final` (1000 groups, single-use qualification cohort). No train/dev
  partition is constructed; frozen M016 models never train on these rows.
- overlap discipline: case/group/pair/option IDs cannot collide with M015
  by construction (m017- prefix); verify_m017_freeze.py audits option-ID
  and near-duplicate disjointness against all committed M015/M016 bytes.

Synthetic-only, MIT, no human or application data. Deterministic: same
(seed, cohort) always yields identical bytes (asserted by the freeze).
"""
import argparse
import hashlib
import json
import os
import random
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RULES = ("all_required", "any_required", "exclusive", "threshold", "category_and_flag")
CANARY_GROUPS = 60
FINAL_GROUPS = 1000
CANARY_SEED = 170017
FINAL_SEED = 170018

# New nuisance surface (must not reuse M015 note/memo/load literals).
NUISANCE_NOTES = ("granite feldspar log", "standard operations entry")
NUISANCE_MEMOS = ("appendix", None)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def rule_label(rule, context, candidate):
    """Independent target checker (same target semantics as M015 by design)."""
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


def _satisfying_candidate(name):
    if name == "threshold":
        return {"capacity": 7, "kind": "primary", "enabled": True, "alpha": True, "beta": False}
    if name == "category_and_flag":
        return {"capacity": 3, "kind": "primary", "enabled": True, "alpha": True, "beta": False}
    if name == "exclusive":
        return {"capacity": 3, "kind": "other", "enabled": False, "alpha": True, "beta": False}
    if name == "any_required":
        return {"capacity": 3, "kind": "other", "enabled": False, "alpha": True, "beta": False}
    return {"capacity": 3, "kind": "other", "enabled": False, "alpha": True, "beta": True}


def make_group(group_id, seed, cohort):
    rng = random.Random(seed + group_id * 7919)
    name = RULES[group_id % len(RULES)]
    rule = _rule_for(rng, name)
    cardinality = 2 + rng.randrange(7)
    candidates = []
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
    block = group_id // len(RULES)
    available = (block // 11) % 5 != 0
    group_key = f"m017-g{group_id:06d}"
    rows = []
    ids = [f"tc-{rng.getrandbits(40):010x}" for _ in candidates]
    for variant in (0, 1):
        order = list(range(cardinality))
        if variant:
            order.reverse()
        chosen = next((ids[i] for i, c in enumerate(candidates) if _label_with_source(rule, c)), None) if available else None
        rows.append({
            "case_id": f"{group_key}-n{variant}", "group_id": group_key,
            "pair_id": f"{group_key}-nuisance", "pair_type": "nuisance", "family": f"m017-{name}-v1",
            "split": cohort,
            "track": "rule_conditioned" if name == "exclusive" else "fixed_rule",
            "rule": rule,
            "context": {"active": bool(group_id % 2), "available": available, "load": round(rng.random() * 8 + (7.5 if variant else 0), 3), "note": NUISANCE_NOTES[variant], "memo": NUISANCE_MEMOS[variant]},
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
            "pair_type": "causal_flip", "causal_feature": causal_field, "family": f"m017-{name}-v1",
            "split": cohort, "track": "rule_conditioned" if name == "exclusive" else "fixed_rule",
            "rule": rule, "context": {"active": bool(group_id % 2), "available": True, "load": 3.0, "note": "causal control", "memo": "appendix"},
            "options": [{"id": ids[i], "semantics": candidates[i]} for i in range(cardinality)],
            "label": ids[next(i for i, candidate in enumerate(candidates) if rule_label(rule, {}, candidate))],
            "oracle": {"satisfying_option_count": 1, "available": True},
        })
        rows.append({
            "case_id": f"{causal_pair}-after", "group_id": group_key, "pair_id": causal_pair,
            "pair_type": "causal_flip", "causal_feature": causal_field, "family": f"m017-{name}-v1",
            "split": cohort, "track": "rule_conditioned" if name == "exclusive" else "fixed_rule",
            "rule": rule, "context": {"active": bool(group_id % 2), "available": True, "load": 3.0, "note": "causal control", "memo": "appendix"},
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
        raise FileExistsError(f"refusing to overwrite different M017 output: {path}")
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return digest


def cohort_seed(cohort):
    if cohort == "canary":
        return CANARY_SEED
    if cohort == "final":
        return FINAL_SEED
    raise ValueError(f"unknown cohort {cohort!r}")


def cohort_groups(cohort):
    if cohort == "canary":
        return CANARY_GROUPS
    if cohort == "final":
        return FINAL_GROUPS
    raise ValueError(f"unknown cohort {cohort!r}")


def generate(out, cohort):
    groups = cohort_groups(cohort)
    seed = cohort_seed(cohort)
    out = Path(out)
    digest = hashlib.sha256()
    count_rows = 0
    fd, temp_name = tempfile.mkstemp(prefix=f"{cohort}.", dir=out)
    try:
        with os.fdopen(fd, "wb") as f:
            for group_id in range(groups):
                for row in make_group(group_id, seed, cohort):
                    data = _canonical(row) + b"\n"
                    digest.update(data)
                    f.write(data)
                    count_rows += 1
            f.flush()
            os.fsync(f.fileno())
        hexdigest = digest.hexdigest()
        target = out / f"{cohort}.jsonl"
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() == hexdigest:
                os.unlink(temp_name)
            else:
                raise FileExistsError(f"refusing to overwrite different M017 output: {target}")
        else:
            os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    manifest = {
        "format": "sdm-m017-dataset-v1",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cohort": cohort, "seed": seed, "groups": groups, "rows": count_rows,
        "output_sha256": "sha256:" + hexdigest,
        "train_partition": "not constructed",
        "rules": list(RULES),
        "provenance": "synthetic-only; MIT; no external or application data",
    }
    write_atomic(out / f"{cohort}-manifest.json",
                 (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode())
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "target/m017")
    ap.add_argument("--cohort", choices=("canary", "final", "both"), default="both")
    args = ap.parse_args()
    cohorts = ("canary", "final") if args.cohort == "both" else (args.cohort,)
    for cohort in cohorts:
        manifest = generate(args.out, cohort)
        print(json.dumps(manifest, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
