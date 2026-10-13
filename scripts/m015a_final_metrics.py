#!/usr/bin/env python3
"""M015a v2 final-action metric contract (Python mirror of sdm-eval choice_final_v2).

Additive, versioned, fail-closed. Historical key meanings are preserved;
new keys carry a `_v2` suffix and operate on final runtime actions only.

Final-action correctness:
- target Some(id): only answered Choice(id) is correct; abstention is false
  abstention; any other ID is wrong choice.
- target None: only final abstention is correct; any chosen ID is false positive.
- 0/1 options are invalid and raise; never synthesize Choice(None).

Pair matcher accepts only declarative `-nuisance` / `-causal` suffixes with
matching `nuisance` / `causal_flip` labels. Exactly two unique case IDs, same
group/split/family/rule, compatible option sets, and the M015 candidate-flip
contract (exactly one None + one Same-context for causal) are required.
Otherwise the pair is ineligible (fail-closed), never silently dropped.

Empty strata return insufficient_support (value None), never 0/0 -> 0.
Group bootstrap draws leakage groups (sorted), sorts replicates, and reports
seed/replicates/method.
"""

CONTRACT = "choice-final-v2"
SEED = 150015
REPLICATES = 2000
CONFIDENCE = 0.95
METHOD = "grouped_bootstrap_percentile_sorted_v1"


def final_correct(target, predicted):
    if target is not None:
        return predicted == target
    return predicted is None


def is_false_abstention(target, predicted):
    return target is not None and predicted is None


def is_false_positive(target, predicted):
    return target is None and predicted is not None


def conditional_argmax(option_ids, probs):
    """Runtime tie-break: larger prob wins; ties resolve to smaller option ID."""
    best = 0
    for i in range(1, len(option_ids)):
        if probs[i] > probs[best]:
            best = i
        elif probs[i] == probs[best] and option_ids[i] < option_ids[best]:
            best = i
    return option_ids[best]


def validate_case(c):
    if not c.get("case_id") or not c.get("leakage_group") or not c.get("family"):
        raise ValueError("empty case/group/family id")
    if c.get("split") not in ("train", "dev"):
        raise ValueError(f"split must be train/dev, got {c.get('split')!r}")
    options = c.get("option_ids") or []
    if not 2 <= len(options) <= 128:
        raise ValueError(f"Choice requires 2..=128 options, got {len(options)}")
    if len(set(options)) != len(options) or any(not o for o in options):
        raise ValueError("duplicate or empty option id")
    target = c.get("target")
    predicted = c.get("predicted")
    if target is not None and target not in options:
        raise ValueError("choice target outside permitted option identities")
    if target is not None and c.get("no_answer_origin") is not None:
        raise ValueError("answerable row must not carry a no-answer origin")
    if target is None and c.get("no_answer_origin") is None:
        raise ValueError("no-answer row must carry an explicit source origin")
    if predicted is not None and predicted not in options:
        raise ValueError("predicted id outside permitted option identities")
    probs = c.get("conditional_probs") or []
    if len(probs) != len(options):
        raise ValueError("conditional probability length must match option order")
    if any(not isinstance(p, float) and not isinstance(p, int) for p in probs):
        raise ValueError("non-numeric conditional probability")
    if any(not (0.0 <= float(p) <= 1.0) or p != p for p in probs):
        raise ValueError("non-finite or out-of-range conditional probability")
    if abs(sum(float(p) for p in probs) - 1.0) > 1e-8:
        raise ValueError("conditional probabilities must sum to 1")
    logits = c.get("conditional_logits")
    if logits is not None:
        if len(logits) != len(options) or any(x != x for x in logits):
            raise ValueError("conditional logits length/finiteness mismatch")
        try:
            for x in logits:
                float(x)
        except Exception as e:
            raise ValueError("non-finite logits") from e
    ap = c.get("answerability_p")
    if ap is None or not (0.0 <= float(ap) <= 1.0) or ap != ap:
        raise ValueError("answerability probability must be finite in [0,1]")
    pair_id = c.get("pair_id")
    pair_type = c.get("pair_type")
    if pair_id is not None:
        if not pair_id:
            raise ValueError("empty pair id")
        kind = pair_kind_from_id(pair_id)
        if pair_type is None:
            raise ValueError("paired row must carry an explicit pair_type label")
        if pair_kind_from_label(pair_type) != kind:
            raise ValueError(
                f"pair id suffix {kind} disagrees with pair type label {pair_type!r}"
            )
    elif pair_type is not None:
        raise ValueError("pair_type without pair_id")


def pair_kind_from_id(pair_id):
    if pair_id.endswith("-nuisance"):
        return "nuisance"
    if pair_id.endswith("-causal"):
        return "causal"
    raise ValueError(
        f"pair id {pair_id!r} has no declarative -nuisance/-causal suffix"
    )


def pair_kind_from_label(label):
    if label == "nuisance":
        return "nuisance"
    if label in ("causal_flip", "causal"):
        return "causal"
    raise ValueError(f"unknown declarative pair type {label!r}")


def match_pairs(cases):
    """Strict matcher. Returns (eligible dict, ineligible dict with reasons)."""
    for c in cases:
        validate_case(c)
    by_pair = {}
    for c in cases:
        if c.get("pair_id") is not None:
            by_pair.setdefault(c["pair_id"], []).append(c)
    eligible = {}
    ineligible = {}
    # Global duplicate case detection.
    case_to_pair = {}
    for pid, members in by_pair.items():
        for m in members:
            if m["case_id"] in case_to_pair and case_to_pair[m["case_id"]] != pid:
                ineligible[pid] = (
                    f"duplicate case {m['case_id']} also in {case_to_pair[m['case_id']]}"
                )
            else:
                case_to_pair[m["case_id"]] = pid
    for pid, members in by_pair.items():
        if pid in ineligible:
            continue
        try:
            kind = pair_kind_from_id(pid)
        except ValueError as e:
            ineligible[pid] = str(e)
            continue
        unique = {m["case_id"] for m in members}
        if len(members) != 2 or len(unique) != 2:
            ineligible[pid] = (
                f"pair must have exactly two unique case ids "
                f"(got {len(members)} rows, {len(unique)} unique)"
            )
            continue
        a, b = members
        if a["leakage_group"] != b["leakage_group"]:
            ineligible[pid] = "pair spans leakage groups"
            continue
        if a["split"] != b["split"]:
            ineligible[pid] = "pair crosses splits"
            continue
        if a["family"] != b["family"]:
            ineligible[pid] = "pair spans families"
            continue
        if (
            a.get("rule_digest")
            and b.get("rule_digest")
            and a["rule_digest"] != b["rule_digest"]
        ):
            ineligible[pid] = "pair spans rules"
            continue
        try:
            if pair_kind_from_label(a["pair_type"]) != kind:
                ineligible[pid] = "pair type label mismatch"
                continue
        except ValueError as e:
            ineligible[pid] = str(e)
            continue
        if b["pair_type"] != a["pair_type"]:
            ineligible[pid] = "pair members disagree on pair_type"
            continue
        if set(a["option_ids"]) != set(b["option_ids"]):
            ineligible[pid] = "mismatched option identity sets"
            continue
        if kind == "nuisance":
            if a["target"] != b["target"]:
                ineligible[pid] = "nuisance pair targets differ (accidental relabel)"
                continue
            if (
                a.get("semantics_digest")
                and b.get("semantics_digest")
                and a["semantics_digest"] != b["semantics_digest"]
            ):
                ineligible[pid] = "nuisance pair changed candidate semantics"
                continue
        else:  # causal
            none_count = sum(1 for m in (a, b) if m["target"] is None)
            if none_count != 1:
                ineligible[pid] = (
                    "causal candidate-flip pair must have exactly one "
                    f"no-answer member (got {none_count})"
                )
                continue
            if (
                a.get("context_digest")
                and b.get("context_digest")
                and a["context_digest"] != b["context_digest"]
            ):
                ineligible[pid] = "causal pair changed context (must hold context fixed)"
                continue
            if (
                a.get("semantics_digest")
                and b.get("semantics_digest")
                and a["semantics_digest"] == b["semantics_digest"]
            ):
                ineligible[pid] = "causal pair preserved candidate semantics (no declared flip)"
                continue
            if a["option_ids"] != b["option_ids"]:
                ineligible[pid] = "causal pair changed option order"
                continue
        eligible[pid] = members
    return eligible, ineligible


def _splitmix(state):
    state = (state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    z ^= z >> 31
    return state, z


def grouped_bootstrap_ci(observations, seed=SEED, replicates=REPLICATES, confidence=CONFIDENCE):
    """Cluster bootstrap over leakage groups. Sorted inputs, sorted replicates.

    observations: list of (group_id, value). Returns dict or None when no groups.
    """
    if not 100 <= replicates <= 100_000:
        raise ValueError("invalid replicates")
    if not 0.5 <= confidence < 1.0:
        raise ValueError("invalid confidence")
    groups = {}
    for g, v in observations:
        if not g or v != v:
            raise ValueError("invalid bootstrap observation")
        s, n = groups.get(g, (0.0, 0))
        groups[g] = (s + float(v), n + 1)
    if not groups:
        return None
    # Stable sorted group order.
    values = [groups[k] for k in sorted(groups)]
    state = seed
    means = []
    for _ in range(replicates):
        s, n = 0.0, 0
        for _ in range(len(values)):
            state, z = _splitmix(state)
            gs, gn = values[z % len(values)]
            s += gs
            n += gn
        means.append(s / n)
    means.sort()
    alpha = (1.0 - confidence) / 2.0

    def at(p):
        x = p * (len(means) - 1)
        lo = int(x // 1)
        hi = int(-(-x // 1))
        if lo == hi:
            return means[lo]
        return means[lo] + (means[hi] - means[lo]) * (x - lo)

    return {
        "lower": at(alpha),
        "upper": at(1.0 - alpha),
        "confidence": confidence,
        "groups": len(values),
        "replicates": replicates,
        "seed": seed,
        "method": METHOD,
    }


def _estimate(correct, total, groups):
    if total == 0:
        return {
            "value": None,
            "eligible_cases": 0,
            "eligible_groups": groups,
            "status": "insufficient_support",
        }
    return {
        "value": correct / total,
        "eligible_cases": total,
        "eligible_groups": groups,
        "status": "ok",
    }


def evaluate(cases):
    """Versioned v2 evaluator. Empty strata are insufficient_support."""
    for c in cases:
        validate_case(c)
    ordered = sorted(cases, key=lambda c: (c["leakage_group"], c["case_id"]))
    groups = {c["leakage_group"] for c in ordered}
    answerable = [c for c in ordered if c["target"] is not None]
    no_answer = [c for c in ordered if c["target"] is None]
    agroups = {c["leakage_group"] for c in answerable}
    ngroups = {c["leakage_group"] for c in no_answer}

    def obs(rows, fn):
        return [(c["leakage_group"], float(fn(c))) for c in rows]

    final_acc = _estimate(
        sum(1 for c in ordered if final_correct(c["target"], c["predicted"])),
        len(ordered),
        len(groups),
    )
    ans_acc = _estimate(
        sum(1 for c in answerable if final_correct(c["target"], c["predicted"])),
        len(answerable),
        len(agroups),
    )
    false_abst = (
        _estimate(
            sum(1 for c in answerable if is_false_abstention(c["target"], c["predicted"])),
            len(answerable),
            len(agroups),
        )
        if answerable
        else {"value": None, "eligible_cases": 0, "eligible_groups": 0, "status": "insufficient_support"}
    )
    # Coverage uses same denominator as answerable accuracy.
    if answerable:
        answered = sum(1 for c in answerable if c["predicted"] is not None)
        coverage = {
            "value": answered / len(answerable),
            "eligible_cases": len(answerable),
            "eligible_groups": len(agroups),
            "status": "ok",
        }
    else:
        coverage = {"value": None, "eligible_cases": 0, "eligible_groups": 0, "status": "insufficient_support"}
    no_rec = _estimate(
        sum(1 for c in no_answer if final_correct(c["target"], c["predicted"])),
        len(no_answer),
        len(ngroups),
    )
    raw_acc = _estimate(
        sum(
            1
            for c in answerable
            if conditional_argmax(c["option_ids"], c["conditional_probs"]) == c["target"]
        ),
        len(answerable),
        len(agroups),
    )
    answered_rows = [c for c in answerable if c["predicted"] is not None]
    answered_groups = {c["leakage_group"] for c in answered_rows}
    selective = _estimate(
        sum(1 for c in answered_rows if final_correct(c["target"], c["predicted"])),
        len(answered_rows),
        len(answered_groups),
    )

    # Pair metrics.
    eligible, ineligible = match_pairs(cases) if cases else ({}, {})
    causal = {k: v for k, v in eligible.items() if k.endswith("-causal")}
    nuisance = {k: v for k, v in eligible.items() if k.endswith("-nuisance")}

    def pair_both(pairs):
        if not pairs:
            return {"value": None, "eligible_cases": 0, "eligible_groups": 0, "status": "insufficient_support"}
        groups_p = {v[0]["leakage_group"] for v in pairs.values()}
        both = sum(1 for v in pairs.values() if all(final_correct(m["target"], m["predicted"]) for m in v))
        return _estimate(both, len(pairs), len(groups_p))

    def pair_consistency(pairs):
        if not pairs:
            return {"value": None, "eligible_cases": 0, "eligible_groups": 0, "status": "insufficient_support"}
        groups_p = {v[0]["leakage_group"] for v in pairs.values()}
        same = sum(1 for v in pairs.values() if v[0]["predicted"] == v[1]["predicted"])
        return _estimate(same, len(pairs), len(groups_p))

    def pair_preserving(pairs):
        if not pairs:
            return {"value": None, "eligible_cases": 0, "eligible_groups": 0, "status": "insufficient_support"}
        groups_p = {v[0]["leakage_group"] for v in pairs.values()}
        pres = sum(
            1
            for v in pairs.values()
            if v[0]["predicted"] == v[1]["predicted"]
            and all(final_correct(m["target"], m["predicted"]) for m in v)
        )
        return _estimate(pres, len(pairs), len(groups_p))

    out = {
        "contract": CONTRACT,
        "eligible_cases": len(ordered),
        "eligible_groups": len(groups),
        "answerable_cases": len(answerable),
        "no_answer_cases": len(no_answer),
        "dev_final_action_accuracy_v2": final_acc,
        "dev_answerable_final_accuracy_v2": ans_acc,
        "dev_false_abstention_rate_v2": false_abst,
        "dev_answerable_final_coverage_v2": coverage,
        "dev_no_answer_final_recall_v2": no_rec,
        "dev_conditional_argmax_accuracy_v2": raw_acc,
        "dev_answered_conditional_accuracy_v2": selective,
        "causal_both_final_correct_v2": pair_both(causal),
        "nuisance_both_final_correct_v2": pair_both(nuisance),
        "nuisance_consistency_v2": pair_consistency(nuisance),
        "nuisance_preserving_v2": pair_preserving(nuisance),
        "eligible_pairs": {"causal": len(causal), "nuisance": len(nuisance)},
        "ineligible_pairs": ineligible,
        "bootstrap": {"seed": SEED, "replicates": REPLICATES, "confidence": CONFIDENCE, "method": METHOD},
    }
    if ordered:
        out["dev_final_action_accuracy_v2_ci"] = grouped_bootstrap_ci(
            obs(ordered, lambda c: final_correct(c["target"], c["predicted"]))
        )
    else:
        out["dev_final_action_accuracy_v2_ci"] = None
    return out
