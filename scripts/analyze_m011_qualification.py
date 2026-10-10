#!/usr/bin/env python3
"""Compare M011 held-out outcomes with frozen simple baselines."""
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ("binary", "choice", "score", "rank")


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def bootstrap(group_deltas, seed):
    values = list(group_deltas.values())
    if not values:
        return {"groups": 0, "lower": None, "upper": None, "mean_delta": None}
    rng = random.Random(seed)
    means = []
    for _ in range(2000):
        means.append(sum(rng.choice(values) for _ in values) / len(values))
    means.sort()
    observed = sum(values) / len(values)
    return {"groups": len(values), "mean_delta": observed,
            "lower": means[int(0.025 * (len(means) - 1))],
            "upper": means[int(0.975 * (len(means) - 1))],
            "confidence": 0.95, "replicates": len(means)}


def ndcg(relevance, ordered_ids):
    def dcg(ids):
        return sum((2 ** relevance.get(cid, 0.0) - 1.0) / math.log2(i + 2)
                   for i, cid in enumerate(ids[:5]))
    ideal = sorted(relevance, key=lambda cid: relevance[cid], reverse=True)
    denominator = dcg(ideal)
    return dcg(ordered_ids) / denominator if denominator else 1.0


def main():
    protocol = (ROOT / "docs/release-qualification-protocol.md").read_bytes()
    results = {"protocol_sha256": sha(protocol), "generator_seed": 11012,
               "synthetic_only": True, "tasks": {}}
    for task in TASKS:
        dataset = read(ROOT / f"fixtures/m011-v2-{task}.json")
        split = read(ROOT / f"fixtures/m011-v2-{task}.split.json")
        report = read(ROOT / f"target/m011-v2/{task}.report.json")
        by_id = {row["case_id"]: row for row in dataset["examples"]}
        train_labels = [by_id[cid]["label"]["value"] for cid in split["train"]]
        outcomes = report["outcomes"]
        group_values = defaultdict(list)
        ood_group_values = defaultdict(list)
        no_answer_groups = set()
        if task == "binary":
            prior = sum(bool(y) for y in train_labels) / len(train_labels)
            for row in outcomes:
                y, p = bool(row["target"]), float(row["score"])
                delta = ((1-prior)**2 if y else prior**2) - ((1-p)**2 if y else p**2)
                group_values[row["leakage_group"]].append(delta)
                if "-ood-v2" in by_id[row["case_id"]]["family"]:
                    ood_group_values[row["leakage_group"]].append(delta)
            baseline = {"train_prior": prior, "metric": "brier", "primary_delta": "baseline_loss-model_loss"}
        elif task == "choice":
            counts = Counter(y for y in train_labels if y is not None)
            majority = sorted(counts, key=lambda y: (-counts[y], y))[0]
            no_answer_correct = no_answer_total = 0
            for row in outcomes:
                y, p = row["target"], row["prediction"]
                if y is None:
                    no_answer_total += 1
                    no_answer_correct += p is None
                    no_answer_groups.add(row["leakage_group"])
                else:
                    delta = float(p == y) - float(majority == y)
                    group_values[row["leakage_group"]].append(delta)
                    if "-ood-v2" in by_id[row["case_id"]]["family"]:
                        ood_group_values[row["leakage_group"]].append(delta)
            baseline = {"majority_option": majority, "metric": "answerable_accuracy", "primary_delta": "model_accuracy-baseline_accuracy",
                        "no_answer_abstention_recall": no_answer_correct / no_answer_total if no_answer_total else None,
                        "no_answer_count": no_answer_total}
        elif task == "score":
            mean = sum(float(y) for y in train_labels) / len(train_labels)
            for row in outcomes:
                y, p = float(row["target"]), row["prediction"]
                delta = abs(y-mean) - abs(y-float(p)) if p is not None else 0.0
                group_values[row["leakage_group"]].append(delta)
                if "-ood-v2" in by_id[row["case_id"]]["family"]:
                    ood_group_values[row["leakage_group"]].append(delta)
            baseline = {"train_mean": mean, "metric": "mae", "primary_delta": "baseline_mae-model_mae"}
        else:
            for row in outcomes:
                relevance = row["relevance"]
                model_order = [item["candidate_id"] for item in sorted(row["prediction"], key=lambda x: -x["score"])]
                example = by_id[row["case_id"]]
                input_order = [item["id"] for item in example["request"]["spec"]["candidates"]]
                delta = ndcg(relevance, model_order) - ndcg(relevance, input_order)
                group_values[row["leakage_group"]].append(delta)
                if "-ood-v2" in by_id[row["case_id"]]["family"]:
                    ood_group_values[row["leakage_group"]].append(delta)
            baseline = {"candidate_order": "request input order", "metric": "ndcg", "primary_delta": "model_ndcg-baseline_ndcg"}
        group_means = {group: sum(values) / len(values) for group, values in group_values.items()}
        interval = bootstrap(group_means, 11011 + TASKS.index(task))
        ood_interval = bootstrap(
            {group: sum(values) / len(values) for group, values in ood_group_values.items()},
            13011 + TASKS.index(task),
        )
        ood_disposition = "indeterminate"
        if ood_interval["groups"] >= 20:
            if ood_interval["lower"] is not None and ood_interval["lower"] > 0:
                ood_disposition = "positive"
            elif ood_interval["upper"] is not None and ood_interval["upper"] < 0:
                ood_disposition = "negative"
        disposition = "indeterminate"
        if interval["groups"] >= 20:
            if interval["lower"] is not None and interval["lower"] > 0:
                disposition = "positive"
            elif interval["upper"] is not None and interval["upper"] < 0:
                disposition = "negative"
        results["tasks"][task] = {
            "dataset_sha256": report["dataset_sha256"],
            "split_fingerprint": report["split_fingerprint"],
            "model_sha256": report["model_sha256"],
            "calibration_sha256": report["calibration_sha256"],
            "artifact_sha256": report["artifact_sha256"],
            "report_sha256": report["report_sha256"],
            "test_cases": len(outcomes), "baseline": baseline,
            "paired_group_bootstrap": interval, "disposition": disposition,
            "ood_slice": {
                "test_cases": sum("-ood-v2" in by_id[cid]["family"] for cid in split["test"]),
                "paired_group_bootstrap": ood_interval,
                "disposition": ood_disposition,
            },
            "test_groups": len({row["leakage_group"] for row in outcomes}),
            "excluded_family_cases": len(split["excluded"]),
            "no_answer_slice_groups": len(no_answer_groups),
        }
        if task == "choice":
            results["tasks"][task]["no_answer_slice_disposition"] = (
                "indeterminate" if len(no_answer_groups) < 20 else
                ("positive" if baseline["no_answer_abstention_recall"] >= 0.95 else "negative")
            )
        test_rows = [by_id[cid] for cid in split["test"]]
        pairs = defaultdict(list)
        for row in test_rows:
            if row.get("counterfactual_pair"):
                pairs[row["counterfactual_pair"]].append(row["case_id"])
        outcome_by_id = {row["case_id"]: row for row in outcomes}
        complete_pairs = [ids for ids in pairs.values() if len(ids) == 2]
        results["tasks"][task]["counterfactual_pairs"] = len(complete_pairs)
        results["tasks"][task]["counterfactual_target_changed"] = sum(
            by_id[ids[0]]["label"]["value"] != by_id[ids[1]]["label"]["value"]
            for ids in complete_pairs
        )
        results["tasks"][task]["counterfactual_prediction_changed"] = sum(
            outcome_by_id[ids[0]]["prediction"] != outcome_by_id[ids[1]]["prediction"]
            for ids in complete_pairs
        )
        if task == "rank":
            comparisons = {}
            for architecture in ("linear", "nonlinear"):
                arch_report = read(ROOT / f"target/m011-v2/rank-{architecture}.report.json")
                arch_deltas = defaultdict(list)
                for row in arch_report["outcomes"]:
                    relevance = row["relevance"]
                    model_order = [item["candidate_id"] for item in sorted(row["prediction"], key=lambda x: -x["score"])]
                    example = by_id[row["case_id"]]
                    input_order = [item["id"] for item in example["request"]["spec"]["candidates"]]
                    arch_deltas[row["leakage_group"]].append(ndcg(relevance, model_order) - ndcg(relevance, input_order))
                interval = bootstrap(
                    {group: sum(values) / len(values) for group, values in arch_deltas.items()},
                    12011 + (0 if architecture == "linear" else 1),
                )
                comparisons[architecture] = {
                    "model_sha256": arch_report["model_sha256"],
                    "artifact_sha256": arch_report["artifact_sha256"],
                    "metrics": arch_report["metrics"],
                    "paired_group_bootstrap_vs_input_order": interval,
                }
            results["tasks"][task]["same_split_architecture_comparisons"] = comparisons
    output = ROOT / "target/m011-v2/qualification-report.json"
    output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
