"""Analyze the single frozen M014 test run using paired group bootstrap bounds."""
import argparse
import json
import random
import statistics
from pathlib import Path


def lower_bound(values, alpha):
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int(alpha * len(ordered))))]


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
    for key in ("binary", "baseline"):
        rows = {r["case_id"]: r for r in reports[key]["outcomes"]}
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
        binary_results[family] = bootstrap(paired,
            lambda gs: statistics.mean((v["baseline"][1]-int(v["baseline"][0]))**2 -
                                       (v["binary"][1]-int(v["binary"][0]))**2 for v in gs), 140015)

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
                by_group.setdefault(source["leakage_group"], []).append(
                    {"target": target, "prediction": row["prediction"], "abstained": row["abstained"]})
            per_model[name] = by_group
        answerable = {g: vals for g, vals in per_model["choice"].items()
                      if all(v["target"] is not None for v in vals)}
        def accuracy_diff(comparator):
            shared = sorted(set(answerable) & set(per_model[comparator]))
            paired = {g: [sum(x["prediction"] == x["target"] for x in per_model["choice"][g]) / len(per_model["choice"][g]),
                          sum(x["prediction"] == x["target"] for x in per_model[comparator][g]) / len(per_model[comparator][g])]
                      for g in shared}
            return bootstrap(paired, lambda xs: statistics.mean(x[0]-x[1] for x in xs), 140015)
        choice_results[family] = {"vs_legacy_accuracy": accuracy_diff("legacy"),
                                  "vs_cross_accuracy": accuracy_diff("cross"),
                                  "answerable_groups": len(answerable)}

    result = {"protocol": "sdm-m014-binary-choice-quality-v1", "status": "descriptive-gates",
              "multiplicity": "Bonferroni alpha=0.05/18; paired leakage-group percentile bootstrap",
              "binary_group_brier_improvement": binary_results,
              "choice_answerable_accuracy_differences": choice_results,
              "limitations": ["Resource, latency, and platform bounds must be reported separately.",
                              "A positive task disposition requires every preregistered gate, control, and support check."],
              "test_runs": 1}
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix(out.suffix + ".tmp")
    temp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temp.replace(out)
    print(json.dumps({"output": str(out), "test_runs": 1}, sort_keys=True))


if __name__ == "__main__":
    main()
