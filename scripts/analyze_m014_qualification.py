"""Analyze the single frozen M014 test run using paired group bootstrap bounds."""
import argparse
import json
import random
from pathlib import Path


def lower_bound(values, alpha):
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int(alpha * len(ordered))))]


def choice_top1_correct(target, option_ids, probabilities):
    top = max(range(len(probabilities)), key=probabilities.__getitem__)
    return target is not None and option_ids[top] == target


def bootstrap(groups, statistic, seed, replicates=10_000, alpha=0.05 / 18):
    keys = sorted(groups)
    rng = random.Random(seed)
    samples = []
    for _ in range(replicates):
        draw = [groups[keys[rng.randrange(len(keys))]] for _ in keys]
        samples.append(statistic(draw))
    return {"estimate": statistic([groups[k] for k in keys]),
            "adjusted_lower": lower_bound(samples, alpha), "groups": len(keys)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--binary-candidate", required=True)
    parser.add_argument("--binary-baseline", required=True)
    parser.add_argument("--choice-candidate", required=True)
    parser.add_argument("--choice-legacy", required=True)
    parser.add_argument("--choice-cross", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"refusing to overwrite prior M014 result: {out}")
    data = json.loads(Path(args.dataset).read_text())["examples"]
    meta = {r["case_id"]: r for r in data}
    reports = {k: json.loads(Path(v).read_text()) for k, v in {
        "binary": args.binary_candidate, "baseline": args.binary_baseline,
        "choice": args.choice_candidate, "legacy": args.choice_legacy,
        "cross": args.choice_cross}.items()}
    for name, report in reports.items():
        if report.get("test_evaluation_performed") is not True:
            raise SystemExit(f"{name} report did not evaluate the frozen test partition")

    binary = {}
    train_prior = None
    for key in ("binary", "baseline"):
        rows = {r["case_id"]: r for r in reports[key]["outcomes"]}
        if key == "binary":
            train = set(reports[key]["train_ids"])
            train_prior = sum(bool(meta[c]["label"]["value"]) for c in train) / len(train)
        for case_id, row in rows.items():
            source = meta[case_id]
            family = source["family"]
            group = source["leakage_group"]
            y = bool(source["label"]["value"])
            p = row["score"]
            binary.setdefault(family, {}).setdefault(group, {})[key] = (y, p)
    binary_results = {}
    for family, groups in sorted(binary.items()):
        paired = {g: vals for g, vals in groups.items() if "binary" in vals and "baseline" in vals}
        def brier_diff(gs, control):
            return sum(sum((p-int(y))**2 for y, p in g[control]) -
                       sum((p-int(y))**2 for y, p in g["binary"]) for g in gs) / sum(len(g["binary"]) for g in gs)
        binary_results[family] = {
            "vs_legacy_brier_improvement": bootstrap(paired, lambda gs: brier_diff(gs, "baseline"), 140015),
            "vs_train_prior_brier_improvement": bootstrap(
                {g: {**v, "prior": [(y, train_prior) for y, _ in v["binary"]]} for g, v in paired.items()},
                lambda gs: brier_diff(gs, "prior"), 140015),
        }

    choice_results = {}
    for family in sorted({r["family"] for r in data if r["family"].startswith("m014-choice-")}):
        per_model = {}
        for name in ("choice", "legacy", "cross"):
            rows = {r["case_id"]: r for r in reports[name]["outcomes"]}
            by_group = {}
            for case_id, row in rows.items():
                source = meta[case_id]
                if source["family"] != family:
                    continue
                target = source["label"]["value"]
                options = source["request"]["spec"]["options"]
                probabilities = row["raw_probabilities"]
                by_group.setdefault(source["leakage_group"], []).append({
                    "target": target,
                    "correct": choice_top1_correct(target, [o["id"] for o in options], probabilities),
                    "yes_id": next(o["id"] for o in options if o["label"].lower().endswith("yes")),
                    "prediction": row["prediction"], "abstained": row["abstained"]})
            per_model[name] = by_group
        answerable = {g: vals for g, vals in per_model["choice"].items()
                      if all(v["target"] is not None for v in vals)}
        def accuracy_diff(comparator):
            shared = sorted(set(answerable) & set(per_model[comparator]))
            paired = {g: [sum(x["correct"] for x in per_model["choice"][g]) / len(per_model["choice"][g]),
                          sum(x["correct"] for x in per_model[comparator][g]) / len(per_model[comparator][g])]
                      for g in shared}
            return bootstrap(paired, lambda xs: sum(x[0]-x[1] for x in xs) / len(xs), 140015)
        candidate_rows = list(per_model["choice"].values())
        answerable_count = sum(x["target"] is not None for group in candidate_rows for x in group)
        covered_count = sum(not x["abstained"] for group in candidate_rows for x in group if x["target"] is not None)
        no_answer_groups = {g: vals for g, vals in per_model["choice"].items()
                            if all(x["target"] is None for x in vals)}
        recalls = {g: [float(all(x["abstained"] for x in vals))] for g, vals in no_answer_groups.items()}
        pair_score = {g: [float(all(x["correct"] for x in vals))]
                      for g, vals in per_model["choice"].items()
                      if len(vals) == 2 and all(x["target"] is not None for x in vals)}
        import statistics
        choice_results[family] = {"vs_legacy_accuracy": accuracy_diff("legacy"),
                                  "vs_cross_accuracy": accuracy_diff("cross"),
                                  "answerable_groups": len(answerable),
                                  "coverage_point": covered_count / max(1, answerable_count),
                                  "no_answer_recall": bootstrap(recalls, lambda xs: statistics.mean(x[0] for x in xs), 140015) if recalls else None,
                                  "counterfactual_both_correct": bootstrap(pair_score, lambda xs: statistics.mean(x[0] for x in xs), 140015) if pair_score else None}

    result = {"protocol": "sdm-m014-binary-choice-quality-v1", "status": "analysis-complete-disposition-requires-review",
              "multiplicity": "Bonferroni alpha=0.05/18; paired leakage-group percentile bootstrap",
              "binary_group_brier_improvement": binary_results,
              "choice_answerable_accuracy_differences": choice_results,
              "limitations": ["Resource, latency, and platform bounds must be reported separately.",
                              "Resource, runtime portability, and negative-control thresholds are not fully adjudicated by this script.",
                              "A positive task disposition requires every preregistered gate, control, and support check."],
              "test_runs": 1}
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix(out.suffix + ".tmp")
    temp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temp.replace(out)
    print(json.dumps({"output": str(out), "test_runs": 1}, sort_keys=True))


if __name__ == "__main__":
    main()
