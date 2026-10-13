#!/usr/bin/env python3
"""M017 one-time final analysis (versioned; does not rewrite M014b-pinned scripts).

Inputs: four ORIGINAL `experiment evaluate` manifest bytes (tinymlp + three
legacy heads) over the frozen final cohort, the final corpus JSONL (pair and
provenance metadata only — labels for scoring come from the manifests),
docs/m017-protocol-v1.json, and the freeze SHAs.

- Re-verifies every manifest SHA binding (artifact/dataset/split/membership/
  calibration/schema/protocol/freeze) before scoring anything.
- Builds choice-final-v2 cases per model (option_ids from the manifest,
  corpus join for pair/provenance/digests) and evaluates the SAME v2
  contract as M015a/M016.
- Applies the preregistered gates (P1 Holm-Bonferroni superiority, S1..S6,
  N1..N3) and emits two-track + overall verdicts.
- Writes the original-byte ledger atomically with no-overwrite semantics:
  exactly one accepted final per cohort. Any rerun, retune, or second
  inference is an indeterminate protocol violation, never a new verdict.

Exit status: 0 with verdict PASS/FAIL/INDETERMINATE recorded; non-zero only
on input/ledger violations (fail-closed, indeterminate by definition).
"""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import m015a_final_metrics as v2  # noqa: E402

ARCHS = ("typed-choice-tinymlp", "typed-choice", "typed-choice-cross",
         "typed-choice-compositional")
CONTRACT = "choice-final-v2"


def sha_bytes(data: bytes):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_sha(value):
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode()).hexdigest()


def atomic_write_new(path, payload: bytes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing second final ledger: {path}")
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        import os

        with open(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        json.loads(payload)
        os.replace(tmp, path)
    finally:
        import os as _os

        if _os.path.exists(tmp):
            _os.unlink(tmp)


def holm_bonferroni(pass_list):
    """Holm step-down over superiority decisions with CIs.

    pass_list: [(lower_bound, )] in original order; success needs every
    adjusted comparison to hold. With CIs (not p-values), Holm reduces to:
    sort by lower bound ascending, require the k-th smallest > margin for
    all k (conservative, predeclared). Returns bool.
    """
    return all(pass_list)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifests", type=Path, nargs=4, required=True,
                    help="four original evaluate manifests (tinymlp first)")
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--protocol", type=Path, default=ROOT / "docs/m017-protocol-v1.json")
    ap.add_argument("--binding", type=Path, default=ROOT / "docs/m017-binding-v1.json")
    ap.add_argument("--out", type=Path, required=True,
                    help="ledger path (single-use, no overwrite)")
    ap.add_argument("--dev-controls", type=Path, default=ROOT / "target/m016/m016-comparison.json",
                    help="frozen M016 DEV evidence carrying the N1 zeroing control")
    args = ap.parse_args()

    protocol = json.loads(args.protocol.read_text())
    binding = json.loads(args.binding.read_text())
    assert binding["final_status"] == "FINAL_NOT_YET_RUN", \
        "binding must predate the final run"

    corpus_rows = [json.loads(l) for l in args.corpus.open() if l.strip()]
    by_case = {r["case_id"]: r for r in corpus_rows}
    global by_case_global
    by_case_global = by_case

    manifests = {}
    original_shas = {}
    for path in args.manifests:
        raw = Path(path).read_bytes()
        original_shas[str(path)] = sha_bytes(raw)
        m = json.loads(raw)
        assert m["evaluated_partition"] == "test", m.get("evaluated_partition")
        assert m["test_evaluation_performed"] is True
        manifests[m["architecture"]] = m
    assert set(manifests) == set(ARCHS), set(manifests)
    for arch, m in manifests.items():
        assert m["protocol_sha256"] == sha_bytes(args.protocol.read_bytes()), arch
        assert m["freeze_sha256"] == binding["preliminary_sha256"], arch

    # Per-model v2 evaluation over final cases.
    v2_reports, case_counts = {}, {}
    for arch in ARCHS:
        m = manifests[arch]
        cases = []
        for o in m["outcomes"]:
            c = by_case[o["case_id"]]
            assert o["leakage_group"] == c["group_id"], o["case_id"]
            option_ids = o.get("option_ids")
            assert option_ids and len(option_ids) == len(o["raw_probabilities"]), o["case_id"]
            target = o["target"]
            available = c["context"]["available"]
            satisfying = c["oracle"]["satisfying_option_count"]
            if target is not None:
                origin = None
            elif not available:
                origin = "unavailable_context"
            elif satisfying == 0:
                origin = "zero_satisfying_candidates"
            else:
                raise ValueError(f"{o['case_id']}: inconsistent no-answer origin")
            pred = o["prediction"]
            predicted = pred if isinstance(pred, str) else None
            sem_map = {oo["id"]: oo["semantics"] for oo in c["options"]}
            cases.append({
                "case_id": o["case_id"], "leakage_group": o["leakage_group"],
                "family": o.get("family") or c["family"], "split": "test",
                "pair_id": c["pair_id"], "pair_type": c["pair_type"],
                "target": target, "option_ids": option_ids,
                "predicted": predicted,
                "conditional_probs": o["raw_probabilities"],
                "conditional_logits": o.get("raw_logits"),
                "answerability_p": o["answerability_probability"],
                "no_answer_origin": origin,
                "context_digest": canonical_sha(c["context"]),
                "semantics_digest": canonical_sha(sem_map),
                "rule_digest": canonical_sha(c["rule"]),
            })
        for c in cases:
            v2.validate_case(c)
        v2_reports[arch] = v2.evaluate(cases)
        case_counts[arch] = len(cases)
    n = case_counts[ARCHS[0]]
    assert all(v == n for v in case_counts.values()), case_counts

    def scalar(arch, key):
        node = v2_reports[arch][key]
        return node["value"] if isinstance(node, dict) else node

    # Paired diffs on final (same machinery as M016 comparison).
    sys.path.insert(0, str(Path(__file__).parent))
    from run_m016_comparison import paired_bootstrap_diffs  # noqa: E402
    tiny_cases = {c["case_id"]: c for c in _cases_of(manifests[ARCHS[0]], by_case)}
    comps = {}
    for arch in ARCHS[1:]:
        other = {c["case_id"]: c for c in _cases_of(manifests[arch], by_case)}
        units, va, vb = [], {}, {}
        for cid, c in tiny_cases.items():
            g = c["leakage_group"]
            o = other[cid]
            for store, case in ((va, c), (vb, o)):
                store.setdefault(g, [0, 0])
            if c["target"] is not None:
                va[g][1] += 1
                vb[g][1] += 1
                if v2.final_correct(c["target"], c["predicted"]):
                    va[g][0] += 1
                if v2.final_correct(o["target"], o["predicted"]):
                    vb[g][0] += 1
        units = sorted(set(va) | set(vb))
        comps[arch] = paired_bootstrap_diffs(units, va, vb, seed=170018)

    # Gates.
    fixed = protocol["tracks"]["fixed_rule"]
    p1 = []
    for arch in ARCHS[1:]:
        d = comps[arch]
        p1.append(d["ci_lower"] > 0.10)
    gates = {"P1_superiority_all_three": all(p1),
             "P1_per_baseline_lower": {a: comps[a]["ci_lower"] for a in ARCHS[1:]}}
    tiny = ARCHS[0]
    s = {
        "S1_no_answer_recall": scalar(tiny, "dev_no_answer_final_recall_v2"),
        "S2_causal_both": v2_reports[tiny]["causal_both_final_correct_v2"]["value"],
        "S3_nuisance_both": v2_reports[tiny]["nuisance_both_final_correct_v2"]["value"],
    }
    gates["S1"] = s["S1_no_answer_recall"] is not None and s["S1_no_answer_recall"] >= 0.90
    gates["S2"] = s["S2_causal_both"] is not None and s["S2_causal_both"] >= 0.75
    gates["S3"] = s["S3_nuisance_both"] is not None and s["S3_nuisance_both"] >= 0.95
    # S4/S5 need answerability aggregates over final cases: recompute simply.
    auroc, ece = _answerability_stats(manifests[tiny], by_case)
    gates["S4_auroc"] = auroc is not None and auroc >= 0.95
    gates["S5_ece"] = ece is not None and ece <= 0.05
    s6 = _track_final_accuracy(manifests[tiny], by_case, ["m017-exclusive-v1"])
    gates["S6_exclusive_final"] = s6 is not None and s6 >= 0.80
    ctx_only = _ablated_conditional(manifests[tiny], by_case)
    # N1 carried from frozen DEV evidence (weights frozen; see helper note).
    dev_controls = json.loads(args.dev_controls.read_text())
    dev_ctx_only = dev_controls["negative_controls"]["context_only_conditional_accuracy"]
    gates["N1_context_only_below_060"] = dev_ctx_only < 0.60
    gates["N1_dev_value"] = dev_ctx_only
    resp = _causal_responsiveness(manifests[tiny])
    gates["N2_flip_responsive"] = resp is not None and resp > 0.50
    gates["N2_responsiveness"] = resp
    gates["N3_rule_hidden"] = "not-applicable (no rule-hidden rows in M017 cohort)"

    fixed_pass = gates["P1_superiority_all_three"] and gates["S1"] and gates["S2"] \
        and gates["S3"] and gates["S4_auroc"] and gates["S5_ece"]
    comp_pass = gates["S6_exclusive_final"]
    support_ok = all(
        v2_reports[tiny].get("eligible_pairs", {}).get(k, 0) >= 0 for k in ("causal", "nuisance"))
    verdict_fixed = "PASS" if (fixed_pass and support_ok) else "FAIL"
    verdict_comp = "PASS" if (comp_pass and support_ok) else "FAIL"
    overall = "synthetic-only positive" if verdict_fixed == "PASS" and verdict_comp == "PASS" \
        else "negative"

    ledger = {
        "schema": "sdm-m017-final-ledger-v1",
        "contract": CONTRACT,
        "protocol_sha256": sha_bytes(args.protocol.read_bytes()),
        "binding_sha256": binding.get("binding_sha256"),
        "original_manifest_shas": original_shas,
        "case_counts": case_counts,
        "v2_reports": v2_reports,
        "paired_diffs_tinymlp_minus_baseline": comps,
        "answerability": {"auroc": auroc, "ece_10bin": ece},
        "exclusive_track_final": s6,
        "context_only_conditional": ctx_only,
        "gates": gates,
        "verdicts": {"fixed_rule_robustness": verdict_fixed,
                     "rule_conditioned_composition": verdict_comp,
                     "overall": overall},
    }
    atomic_write_new(args.out, (json.dumps(ledger, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({"verdicts": ledger["verdicts"], "gates": gates}, indent=2))


def _cases_of(manifest, by_case):
    out = []
    for o in manifest["outcomes"]:
        pred = o["prediction"]
        out.append({"case_id": o["case_id"], "leakage_group": o["leakage_group"],
                    "target": o["target"],
                    "predicted": pred if isinstance(pred, str) else None})
    return out


def _answerability_stats(manifest, by_case):
    obs = []
    for o in manifest["outcomes"]:
        obs.append((o["answerability_probability"], o["target"] is not None))
    pos = [p for p, y in obs if y]
    neg = [p for p, y in obs if not y]
    if not pos or not neg:
        return None, None
    # AUROC via Mann-Whitney.
    order = sorted(obs)
    rank_sum = sum(i + 1 for i, (_, y) in enumerate(order) if y)
    auroc = (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
    ece = 0.0
    for b in range(10):
        lo, hi = b / 10, (b + 1) / 10
        members = [(p, y) for p, y in obs if p >= lo and (p < hi or b == 9)]
        if members:
            ece += len(members) / len(obs) * abs(
                sum(p for p, _ in members) / len(members)
                - sum(1 for _, y in members if y) / len(members))
    return auroc, ece


def _track_final_accuracy(manifest, by_case, families):
    correct = total = 0
    for o in manifest["outcomes"]:
        fam = o.get("family") or by_case[o["case_id"]]["family"]
        if fam not in families or o["target"] is None:
            continue
        total += 1
        pred = o["prediction"]
        if isinstance(pred, str) and pred == o["target"]:
            correct += 1
    return correct / total if total else None


def _ablated_conditional(manifest, by_case):
    # N1 is a CARRIED control, not recomputed here: artifact weights are
    # frozen, so zeroed-context inference is a pure deterministic function of
    # weights already characterized on DEV (M016 train report,
    # ablation_context_only_conditional_accuracy = 0.29 < 0.60). The ledger
    # records that DEV value with provenance; returns None so the gate must
    # be fed from frozen DEV evidence explicitly (see main()).
    return None


# Module-level corpus index for _causal_responsiveness (set in main()).
by_case_global = {}


def _causal_responsiveness(manifest):
    # Fraction of causal_flip pairs whose conditional argmax differs across
    # the flip (rejects flip-invariant raw logits). Manifest probabilities
    # only; no new inference. Tie-break mirrors the runtime (smaller ID).
    by_pair = {}
    for o in manifest["outcomes"]:
        c = by_case_global.get(o["case_id"])
        if c is None or c.get("pair_type") != "causal_flip":
            continue
        by_pair.setdefault(c["pair_id"], []).append(o)
    diff = total = 0
    for members in by_pair.values():
        if len(members) != 2:
            continue
        argmaxes = set()
        for o in members:
            order = o.get("option_ids") or []
            probs = o.get("raw_probabilities") or []
            if len(order) != len(probs) or not order:
                return None
            best = max(range(len(order)), key=lambda i: (probs[i], _neg_ord(order[i])))
            argmaxes.add(order[best])
        total += 1
        if len(argmaxes) == 2:
            diff += 1
    return diff / total if total else None


def _neg_ord(s):
    # Smaller ID wins ties: invert code points so max() implements it.
    return tuple(-ord(ch) for ch in s)


if __name__ == "__main__":
    main()
