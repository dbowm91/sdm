#!/usr/bin/env python3
"""M016 DEV-only TinyMLP vs baseline comparison (TRAIN/DEV only, no FINAL).

Pipeline (all inputs SHA-bound before inference, all outputs atomic):
1. M015 corpus + typed dataset + three legacy Choice baselines
   (reuses run_m015_baselines.run: same bytes, same split, same encoder path).
2. Bounded TinyMLP grid (<=36 configs) via `sdm experiment m016-train`
   (release profile by default); DEV-only selection on the predeclared
   objective; winning envelope artifact + train report.
3. Isolated shallow-tree baseline (m016_tree_baseline, pure stdlib) on the
   exact exported TinyMLP feature vectors; exported tree model JSON.
4. v2 final-action replay (m015a-replay, include_cases) for the three legacy
   heads + TinyMLP through the real runtimes; tree cases evaluated with the
   same m015a_final_metrics contract in-process.
5. Paired leakage-group bootstrap diffs (TinyMLP minus each baseline) for
   final/conditional/answerability/pair metrics; oracle ceiling stated.
6. m016-comparison.json with gate assertions (fail-closed).

Never trains on test, never evaluates test, never rewrites history or any
M015/M015a frozen file. Outputs only under --out.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import m015a_final_metrics as v2
import m016_tree_baseline as tree
import run_m015_baselines

LEGACY_ARCHS = ("typed-choice", "typed-choice-cross", "typed-choice-compositional")
SELECTION_OBJECTIVE = ("max DEV answerable final-action accuracy, then smaller "
                         "(width, seed), then min DEV conditional NLL")


def sha_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_write(path, payload: bytes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            return digest
        raise FileExistsError(f"refusing to overwrite different M016 output: {path}")
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
    return digest


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def canonical_sha(value):
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode()).hexdigest()


def run_cargo(args, cwd=ROOT):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"{' '.join(args)} failed: {proc.stderr.strip()[-2000:]}")
    return proc.stdout


def paired_bootstrap_diffs(units, val_a, val_b, seed=150015, replicates=2000):
    """Paired bootstrap CI over resampled units (groups or pairs).

    units: sorted list of unit ids; val_a/val_b: {unit: (correct, total)}.
    Returns {metric-free diff CI}: point diff of pooled means + percentile CI.
    """
    pooled_a = sum(v[0] for v in val_a.values())
    total_a = sum(v[1] for v in val_a.values())
    pooled_b = sum(v[0] for v in val_b.values())
    total_b = sum(v[1] for v in val_b.values())
    point = pooled_a / total_a - pooled_b / total_b
    order = sorted(units)
    state = seed
    diffs = []
    for _ in range(replicates):
        sa = ta = sb = tb = 0.0
        for _ in range(len(order)):
            state, z = v2._splitmix(state)
            u = order[z % len(order)]
            ca, na = val_a.get(u, (0, 0))
            cb, nb = val_b.get(u, (0, 0))
            sa += ca
            ta += na
            sb += cb
            tb += nb
        if ta == 0 or tb == 0:
            # Degenerate resample (no eligible rows for one side): no
            # information, record zero diff. Unreachable on powered cohorts.
            diffs.append(0.0)
        else:
            diffs.append(sa / ta - sb / tb)
    diffs.sort()
    alpha = 0.025

    def at(p):
        x = p * (len(diffs) - 1)
        lo = int(x // 1)
        hi = int(-(-x // 1))
        if lo == hi:
            return diffs[lo]
        return diffs[lo] + (diffs[hi] - diffs[lo]) * (x - lo)

    return {"value": point, "ci_lower": at(alpha), "ci_upper": at(1.0 - alpha),
            "replicates": replicates, "seed": seed,
            "method": "paired_unit_bootstrap_percentile_sorted_v1"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "target/m016")
    ap.add_argument("--groups", type=int, default=2000, choices=(2000,))
    ap.add_argument("--seed", type=int, default=150015)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--widths", type=int, nargs="+", default=[32, 64])
    ap.add_argument("--train-seeds", type=int, nargs="+", default=[16016, 16017, 16018])
    ap.add_argument("--lrs", type=float, nargs="+", default=[0.05, 0.1, 0.2])
    ap.add_argument("--l2s", type=float, nargs="+", default=[0.0, 0.0001])
    ap.add_argument("--cargo-profile", default="release", choices=("release", "debug"))
    ap.add_argument("--skip-baselines", action="store_true",
                    help="reuse existing out/baselines (same SHAs enforced)")
    args = ap.parse_args()

    grid = len(args.widths) * len(args.train_seeds) * len(args.lrs) * len(args.l2s)
    if grid > 36:
        raise SystemExit(f"grid {grid} exceeds 36-config bound")
    out = Path(args.out)
    base = out / "baselines"
    train_out = out / "train"

    # 1. Baselines on identical bytes.
    if args.skip_baselines:
        summary = json.loads((base / "baseline-summary.json").read_text())
        assert summary["mode"] == "TRAIN/DEV only"
    else:
        summary = run_m015_baselines.run(base, args.groups, args.seed)
        atomic_write(base / "baseline-summary.json",
                     (json.dumps(summary, sort_keys=True, indent=2) + "\n").encode())
    dataset = base / "typed-choice.json"
    split = base / "typed-choice.split.json"
    corpus_train = base / "corpus/train.jsonl"
    corpus_dev = base / "corpus/dev.jsonl"
    bundle = json.loads(dataset.read_text())
    provenance = bundle["provenance"]
    sample_report = json.loads((base / "typed-choice.report.json").read_text())
    exp_dataset, exp_split = sample_report["dataset_sha256"], sample_report["split_fingerprint"]

    # Census gates before any training.
    train_rows = read_jsonl(corpus_train)
    dev_rows = read_jsonl(corpus_dev)
    assert len(train_rows) == 7200 and len({r["group_id"] for r in train_rows}) == 2000
    assert len(dev_rows) == 720 and len({r["group_id"] for r in dev_rows}) == 200
    assert len({r["pair_id"] for r in dev_rows if r["pair_type"] == "nuisance"}) == 200
    assert len({r["pair_id"] for r in dev_rows if r["pair_type"] == "causal_flip"}) == 160
    assert sum(1 for r in dev_rows if r["label"] is not None) == 480
    assert json.loads(split.read_text())["test"] == []

    # 2. TinyMLP bounded grid.
    train_spec = {
        "dataset_path": str(dataset), "split_path": str(split),
        "provenance": provenance,
        "expected_dataset_sha256": exp_dataset,
        "expected_split_fingerprint": exp_split,
        "output_dir": str(train_out), "epochs": args.epochs,
        "hidden_widths": args.widths, "seeds": args.train_seeds,
        "learning_rates": args.lrs, "l2_values": args.l2s,
        "lambda_answerability": 1.0,
        "export_features_path": str(train_out / "features.json"),
    }
    spec_path = out / "m016-train-spec.json"
    atomic_write(spec_path, (json.dumps(train_spec, indent=2) + "\n").encode())
    cargo = ["cargo", "run", "-q", "-p", "sdm-experiment", "--locked"]
    if args.cargo_profile == "release":
        cargo.append("--release")
    cargo += ["--", "experiment", "m016-train", "--config", str(spec_path)]
    train_stdout = run_cargo(cargo)
    train_report = json.loads(train_stdout)
    assert train_report["grid_size"] == grid
    assert train_report["partition"] == "TRAIN/DEV only"
    assert train_report["dataset_sha256"] == exp_dataset
    sel = train_report["candidates"][train_report["selected_index"]]
    assert 0.0 < sel["dev_threshold"] < 1.0
    assert sel["parameter_count"] <= 1_000_000
    assert Path(train_report["selected_artifact_path"]).stat().st_size <= 16 * 1024 * 1024
    artifact_path = Path(train_report["selected_artifact_path"])

    # 3. Tree baseline on the exact exported vectors.
    tree_model, tree_aux = tree.train_from_export(str(train_out / "features.json"))
    atomic_write(out / "tree-baseline.json",
                 (json.dumps(tree_model, indent=2) + "\n").encode())

    # 4. v2 replays (real runtimes, per-case emission for pairing).
    corpus_meta = {
        "generator_sha256": sha_file(ROOT / "scripts/generate_m015_suite.py"),
        "task_spec_sha256": sha_file(ROOT / "docs/m015-task-spec-v1.md"),
        "corpus_train_sha256": sha_file(corpus_train),
        "corpus_dev_sha256": sha_file(corpus_dev),
    }
    sidecars = {}
    for arch in LEGACY_ARCHS + ("typed-choice-tinymlp",):
        art = (base / f"{arch}.artifact.json") if arch != "typed-choice-tinymlp" \
            else artifact_path
        replay = {
            "dataset_path": str(dataset), "split_path": str(split),
            "artifact_path": str(art),
            "corpus_train_path": str(corpus_train),
            "corpus_dev_path": str(corpus_dev),
            "generator_path": "scripts/generate_m015_suite.py",
            "task_spec_path": "docs/m015-task-spec-v1.md",
            "output_path": str(out / f"{arch}.sidecar.json"),
            "expected_artifact_sha256": sha_file(art),
            "expected_dataset_sha256": exp_dataset,
            "expected_split_fingerprint": exp_split,
            "architecture": arch, "provenance": provenance,
            "include_cases": True,
            **{f"expected_{k}": v for k, v in corpus_meta.items()},
        }
        replay_path = out / f"{arch}.replay.json"
        atomic_write(replay_path, (json.dumps(replay, indent=2) + "\n").encode())
        replay_out = run_cargo(
            ["cargo", "run", "-q", "-p", "sdm-experiment", "--locked",
             "--", "experiment", "m015a-replay", "--config", str(replay_path)])
        sidecar = json.loads((out / f"{arch}.sidecar.json").read_text())
        assert sidecar["partition"] == "DEV only"
        assert sidecar["cases"], f"{arch} replay must emit cases"
        sidecars[arch] = sidecar

    # 5. Tree v2 cases (same contract, joined metadata).
    dev_by_case = {r["case_id"]: r for r in dev_rows}
    feat_by_case = {r["case_id"]: r for r in tree_aux["dev_rows"]}
    tree_cases = []
    for i, frow in enumerate(tree_aux["dev_rows"]):
        case_id = frow["case_id"]
        corpus = dev_by_case[case_id]
        sorted_ids = sorted(o["id"] for o in corpus["options"])
        assert len(sorted_ids) == len(frow["candidates"])
        order = [o["id"] for o in corpus["options"]]
        pos_of = {oid: i for i, oid in enumerate(order)}
        probs_sorted = tree_aux["dev_choice_probs"][i]
        # Map sorted-order probs to corpus order.
        idx_sorted = {oid: k for k, oid in enumerate(sorted_ids)}
        probs = [probs_sorted[idx_sorted[oid]] for oid in order]
        s = sum(probs)
        probs = [p / s for p in probs]
        target_idx = frow["target"]
        target = sorted_ids[target_idx] if target_idx is not None else None
        a = tree_aux["ans_dev_p"][i]
        predicted = None
        if a >= tree_model["dev_threshold"]:
            predicted = v2.conditional_argmax(order, probs)
        available = corpus["context"]["available"]
        satisfying = corpus["oracle"]["satisfying_option_count"]
        if target is not None:
            origin = None
        elif not available:
            origin = "unavailable_context"
        elif satisfying == 0:
            origin = "zero_satisfying_candidates"
        else:
            raise RuntimeError(f"tree case {case_id}: inconsistent no-answer origin")
        sem_map = {o["id"]: o["semantics"] for o in corpus["options"]}
        tree_cases.append({
            "case_id": case_id, "leakage_group": corpus["group_id"],
            "family": corpus["family"], "split": "dev",
            "pair_id": corpus["pair_id"], "pair_type": corpus["pair_type"],
            "target": target, "option_ids": order, "predicted": predicted,
            "conditional_probs": probs, "conditional_logits": None,
            "answerability_p": a, "no_answer_origin": origin,
            "context_digest": canonical_sha(corpus["context"]),
            "semantics_digest": canonical_sha(sem_map),
            "rule_digest": canonical_sha(corpus["rule"]),
        })
    for c in tree_cases:
        v2.validate_case(c)
    tree_report = v2.evaluate(tree_cases)
    atomic_write(out / "tree-report.json",
                 (json.dumps(tree_report, indent=2) + "\n").encode())

    # 6. Paired diffs (TinyMLP minus each baseline) on shared DEV cases.
    def case_outcomes(cases):
        final, cond, ans, fa, cov = {}, {}, {}, {}, {}
        for c in cases:
            g = c["leakage_group"]
            tgt, pred = c["target"], c["predicted"]
            answerable = tgt is not None
            answered = pred is not None
            argmax = v2.conditional_argmax(c["option_ids"], c["conditional_probs"])
            final.setdefault(g, [0, 0])
            cond.setdefault(g, [0, 0])
            if answerable:
                final[g][1] += 1
                cond[g][1] += 1
                if answered and pred == tgt:
                    final[g][0] += 1
                if argmax == tgt:
                    cond[g][0] += 1
                fa.setdefault(g, [0, 0])
                fa[g][1] += 1
                if not answered:
                    fa[g][0] += 1
                cov.setdefault(g, [0, 0])
                cov[g][1] += 1
                if answered:
                    cov[g][0] += 1
            else:
                ans.setdefault(g, [0, 0])
                ans[g][1] += 1
                if not answered:
                    ans[g][0] += 1
        return {"final": final, "cond": cond, "no_answer_recall": ans,
                "false_abstention": fa, "coverage": cov}

    outcomes = {"typed-choice-tinymlp": case_outcomes(sidecars["typed-choice-tinymlp"]["cases"])}
    for arch in LEGACY_ARCHS:
        outcomes[arch] = case_outcomes(sidecars[arch]["cases"])
    outcomes["tree"] = case_outcomes(tree_cases)

    def pair_outcomes(cases, kind):
        units = {}
        by_pair = {}
        for c in cases:
            if c["pair_type"] != kind:
                continue
            by_pair.setdefault(c["pair_id"], []).append(c)
        for pid, members in by_pair.items():
            if len(members) != 2:
                continue
            ok = all(v2.final_correct(m["target"], m["predicted"]) for m in members)
            units[pid] = ([1, 1] if ok else [0, 1])
        return units

    comparisons = {}
    for arch in LEGACY_ARCHS + ("tree",):
        comp = {}
        for metric in ("final", "cond", "no_answer_recall", "false_abstention", "coverage"):
            a, b = outcomes["typed-choice-tinymlp"][metric], outcomes[arch][metric]
            comp[f"{metric}_diff"] = paired_bootstrap_diffs(
                sorted(set(a) | set(b)), a, b)
        for kind in ("causal_flip", "nuisance"):
            a = pair_outcomes(sidecars["typed-choice-tinymlp"]["cases"], kind)
            b = pair_outcomes(
                sidecars[arch]["cases"] if arch != "tree" else tree_cases, kind)
            comp[f"{kind}_both_final_diff"] = paired_bootstrap_diffs(
                sorted(set(a) | set(b)), a, b)
        comparisons[arch] = comp

    # 7. Summary + disposition.
    def scalar(report, key):
        node = report
        for part in key.split("."):
            node = node[part]
        return node["value"] if isinstance(node, dict) else node

    models = {}
    for arch, sc in sidecars.items():
        rep = sc["report"]
        models[arch] = {
            "artifact_sha256": sc["artifact_sha256"],
            "artifact_architecture": sc["artifact_architecture"],
            "dev_conditional_argmax_accuracy_v2":
                scalar(rep, "dev_conditional_argmax_accuracy_v2"),
            "dev_answerable_final_accuracy_v2":
                scalar(rep, "dev_answerable_final_accuracy_v2"),
            "dev_false_abstention_rate_v2": scalar(rep, "dev_false_abstention_rate_v2"),
            "dev_no_answer_recall_v2": scalar(rep, "dev_no_answer_final_recall_v2"),
            "causal_both_final": rep["causal"]["both_final_correct"]["value"],
            "nuisance_both_final": rep["nuisance"]["both_final_correct"]["value"],
        }
    models["tree"] = {
        "artifact_sha256": "n/a-research-only",
        "artifact_architecture": "shallow-gbdt-research-only",
        "dev_conditional_argmax_accuracy_v2":
            tree_report["dev_conditional_argmax_accuracy_v2"]["value"],
        "dev_answerable_final_accuracy_v2":
            tree_report["dev_answerable_final_accuracy_v2"]["value"],
        "dev_false_abstention_rate_v2":
            tree_report["dev_false_abstention_rate_v2"]["value"],
        "dev_no_answer_recall_v2":
            tree_report["dev_no_answer_final_recall_v2"]["value"],
        "causal_both_final": tree_report["causal_both_final_correct_v2"]["value"],
        "nuisance_both_final": tree_report["nuisance_both_final_correct_v2"]["value"],
    }
    tiny = models["typed-choice-tinymlp"]
    disposition = (
        "positive-dev-only"
        if tiny["dev_answerable_final_accuracy_v2"] == 1.0
        and tiny["dev_false_abstention_rate_v2"] == 0.0
        and tiny["causal_both_final"] > 0.9
        else "needs-review"
    )
    comparison = {
        "schema": "sdm-m016-comparison-v1",
        "contract": v2.CONTRACT,
        "partition": "DEV only",
        "test_evaluation_performed": False,
        "dataset_sha256": exp_dataset,
        "split_fingerprint": exp_split,
        "grid_size": grid,
        "selection_objective": SELECTION_OBJECTIVE,
        "train_report": train_report["selected_artifact_sha256"],
        "build_profile": train_report.get("build_profile"),
        "oracle_ceiling": {
            "note": "oracle defines synthetic truth, not an ML contender; "
                    "M015 DEV oracle disagreements == 0 (see dev-report)",
            "dev_conditional_argmax_accuracy": 1.0,
            "dev_answerable_final_accuracy": 1.0,
            "dev_no_answer_recall": 1.0,
        },
        "models": models,
        "paired_diffs_tinymlp_minus_baseline": comparisons,
        "negative_controls": {
            "context_only_conditional_accuracy":
                sel["ablation_context_only_conditional_accuracy"],
            "candidate_only_conditional_accuracy":
                sel["ablation_candidate_only_conditional_accuracy"],
            "candidate_projections_embed_context_and_rule_by_construction": True,
            "note": "candidate projections carry context+rule fields by M015 "
                    "materialization (same for all heads); the scored task is "
                    "selecting among candidates, and answerability is the "
                    "separating head vs legacy context-only",
        },
        "resources": {
            "tinymlp_parameters": sel["parameter_count"],
            "tinymlp_artifact_bytes":
                Path(train_report["selected_artifact_path"]).stat().st_size,
            "tinymlp_latency_ms_by_options": train_report["latency_ms_by_options"],
            "tinymlp_peak_rss_bytes": train_report["peak_rss_bytes"],
            "tree_model_bytes": Path(out / "tree-baseline.json").stat().st_size,
        },
        "disposition": disposition,
    }
    atomic_write(out / "m016-comparison.json",
                 (json.dumps(comparison, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps(comparison, indent=2, sort_keys=True))
    print(f"M016 comparison complete: disposition={disposition}", file=sys.stderr)


if __name__ == "__main__":
    main()
