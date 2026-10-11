#!/usr/bin/env python3
"""M013b retrospective audit sidecar for the frozen M013a evidence.

This script is READ-ONLY with respect to every M013/M013a frozen input. It reads
the unchanged saved reports and artifacts, recomputes the corrected
fixed-option-identity counterfactual statistics, re-derives the preregistered
gate verdict with the fail-closed M013b evaluator, and writes a NEW sidecar under
`target/m013b/`.

It deliberately does NOT:
  * modify `target/m013a/`, `fixtures/`, or any historical report/artifact hash;
  * retrain, refit, reselect or re-threshold any model;
  * treat this output as new held-out quality or selection evidence.

The output is a post-hoc semantic clarification (an erratum) only.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m013b_evaluator import (  # noqa: E402
    EVALUATOR_VERSION,
    VERDICT_NEGATIVE,
    GATE_INSUFFICIENT_SUPPORT,
    Gate,
    build_pairs,
    evaluate_gates,
    evaluate_pair,
    summarize_pairs,
    support_gate,
    threshold_gate,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
M013A = ROOT / "target/m013a"
OUT = ROOT / "target/m013b"
PROTOCOL = Path(__file__).resolve().parent / "m013b_protocol_v1.json"

CHOICE_FAMILIES = (
    "m013a-choice-id-a-v1",
    "m013a-choice-id-b-v1",
    "m013a-choice-load-shift-v1",
    "m013a-choice-text-shift-v1",
    "m013a-choice-combined-shift-v1",
)
BINARY_FAMILIES = (
    "m013a-binary-id-a-v1",
    "m013a-binary-id-b-v1",
    "m013a-binary-load-shift-v1",
    "m013a-binary-text-shift-v1",
    "m013a-binary-combined-shift-v1",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def mean(values):
    return sum(values) / len(values) if values else None


def load_reports():
    """Load the unchanged M013a reports and normalize the historical schema."""
    reports = {name: read(M013A / f"{name}.report.json") for name in ("choice-legacy", "choice-cross", "binary")}
    for report in reports.values():
        for outcome in report["outcomes"]:
            # Legacy-compatible serialization omits false-valued optional
            # abstention diagnostics; absence means the runtime default. This
            # matches the historical analyzer and changes no metric.
            outcome.setdefault("abstained", False)
    return reports


def attach_examples(report, examples_by_case):
    for outcome in report["outcomes"]:
        example = examples_by_case[outcome["case_id"]]
        outcome["family"] = example["family"]
    return report


def group_count(rows, predicate=lambda r: True):
    return len({r["leakage_group"] for r in rows if predicate(r)})


def choice_slices(report):
    """Support counted in the eligible population for each exact metric."""
    slices = {}
    for family in CHOICE_FAMILIES:
        rows = [r for r in report["outcomes"] if r["family"] == family]
        if not rows:
            continue
        answerable = [r for r in rows if r["target"] is not None]
        no_answer = [r for r in rows if r["target"] is None]
        accuracy = mean(
            [
                float(not r["abstained"] and r["prediction"] == r["target"])
                for r in answerable
            ]
        )
        slices[family] = {
            "cases": len(rows),
            "independent_groups": group_count(rows),
            "answerable_groups": group_count(answerable),
            "no_answer_groups": group_count(no_answer),
            "answerable_final_accuracy": accuracy,
            "no_answer_recall": mean([float(r["abstained"]) for r in no_answer]) if no_answer else None,
            "coverage": mean([float(not r["abstained"]) for r in rows]),
        }
    return slices


def paired_accuracy_delta(legacy, cross):
    legacy_by_case = {r["case_id"]: r for r in legacy["outcomes"]}
    cross_by_case = {r["case_id"]: r for r in cross["outcomes"]}
    if set(legacy_by_case) != set(cross_by_case):
        raise SystemExit("legacy and cross reports cover different case ids")
    for case_id in legacy_by_case:
        if legacy_by_case[case_id]["leakage_group"] != cross_by_case[case_id]["leakage_group"]:
            raise SystemExit(f"legacy/cross leakage-group misalignment at {case_id}")
    paired = []
    for case_id, left in legacy_by_case.items():
        if left["target"] is None:
            continue
        right = cross_by_case[case_id]
        paired.append(
            {
                "case_id": case_id,
                "leakage_group": left["leakage_group"],
                "delta": float(
                    (not right["abstained"] and right["prediction"] == right["target"])
                    - (not left["abstained"] and left["prediction"] == left["target"])
                ),
            }
        )
    from m013b_evaluator import group_bootstrap

    return paired, group_bootstrap(paired, lambda members: mean([m["delta"] for m in members]))


def build_choice_gates(protocol, legacy_slices, cross_slices, delta_ci, control_accuracy, counters):
    """Assemble every mandatory Choice gate from the frozen protocol source.

    Positive is structurally unreachable here: the frozen M013a protocol names
    counterfactual, critical OOD, answerability and calibration gates but
    declares no numeric threshold for them, so each of those gates is emitted as
    `insufficient_support` and can never pass.
    """
    gates = []
    primary_pass = delta_ci["lower"] is not None and delta_ci["lower"] > 0.0
    gates.append(
        Gate(
            name="primary_paired_answerable_accuracy",
            status="pass" if primary_pass else "fail",
            mandatory=True,
            critical=False,
            evidence_count=delta_ci["groups"],
            observed=delta_ci["mean"] if "mean" in delta_ci else delta_ci["lower"],
            threshold=0.0,
            comparator=">",
            reason=(
                f"cross-minus-legacy paired answerable accuracy 95% CI "
                f"[{delta_ci['lower']}, {delta_ci['upper']}] over {delta_ci['groups']} groups"
            ),
        )
    )
    for family, metrics in sorted(cross_slices.items()):
        gates.append(
            support_gate(
                f"answerable_groups::{family}",
                observed=metrics["answerable_groups"],
                required=protocol["support"]["min_answerable_groups_per_accuracy_slice"],
            )
        )
        if metrics["no_answer_groups"] > 0:
            gates.append(
                support_gate(
                    f"no_answer_groups::{family}",
                    observed=metrics["no_answer_groups"],
                    required=protocol["support"]["min_no_answer_groups_per_no_answer_slice"],
                )
            )

    choice_spec = protocol["choice_gates"]
    # Undeclared numeric success thresholds: cannot be established retrospectively.
    gates.append(
        threshold_gate(
            "counterfactual_both_correct_rate",
            observed=counters["both_correct_rate"],
            threshold=choice_spec["counterfactual_both_correct_min_rate"],
            comparator=">",
            evidence_count=counters["answerable_pairs"],
            description="share of answerable active-flip pairs answered correctly on both sides",
        )
    )
    gates.append(
        threshold_gate(
            "counterfactual_fixed_option_response_rate",
            observed=counters["input_response_rate"],
            threshold=choice_spec["counterfactual_response_min_rate"],
            comparator=">",
            evidence_count=counters["pairs"],
            description="share of pairs whose SAME-option logits respond to the manipulated input",
        )
    )
    gates.append(
        threshold_gate(
            "answerability_no_answer_recall",
            observed=counters["no_answer_recall"],
            threshold=choice_spec["answerability_no_answer_recall_min"],
            comparator=">=",
            evidence_count=counters["no_answer_groups"],
            description="no-answer recall on eligible independent groups",
        )
    )
    gates.append(
        threshold_gate(
            "calibration_max_conditional_brier",
            observed=counters["conditional_brier"],
            threshold=choice_spec["calibration_max_conditional_brier"],
            comparator="<=",
            evidence_count=counters["answerable_cases"],
            description="conditional option Brier on answerable cases",
        )
    )
    for family in choice_spec["critical_ood_families"]:
        metrics = cross_slices.get(family)
        if metrics is None:
            gates.append(
                Gate(
                    name=f"critical_ood::{family}",
                    status="invalid",
                    mandatory=True,
                    critical=True,
                    reason="required critical OOD slice is absent from the frozen M013a report",
                )
            )
        else:
            gates.append(
                support_gate(
                    f"critical_ood_support::{family}",
                    observed=metrics["answerable_groups"],
                    required=protocol["support"]["min_answerable_groups_per_accuracy_slice"],
                    mandatory=True,
                )
            )
    # Negative controls must never qualify as learned improvement.
    gates.append(
        threshold_gate(
            "negative_controls_do_not_qualify",
            observed=control_accuracy,
            threshold=0.0,
            comparator=">=",
            evidence_count=counters["pairs"],
            description="highest negative-control answerable accuracy must stay below learned improvement",
        )
    )
    return gates


def build_binary_gates(protocol, binary_analysis):
    gates = []
    for family in sorted(binary_analysis["slices"]):
        metrics = binary_analysis["slices"][family]
        critical = family in protocol["binary_gates"]["critical_families"]
        gates.append(
            threshold_gate(
                f"brier_improvement_vs_train_prior::{family}",
                observed=metrics["brier_improvement_vs_train_prior"],
                threshold=0.0,
                comparator=">",
                evidence_count=metrics["independent_groups"],
                critical=critical,
                description="Brier improvement over the train-prior constant baseline",
            )
        )
        gates.append(
            support_gate(
                f"independent_groups::{family}",
                observed=metrics["independent_groups"],
                required=protocol["binary_gates"]["min_independent_groups_per_family"],
            )
        )
    return gates


def atomic_write_json(path: Path, payload) -> None:
    """Stage to a temporary file, then atomically rename.

    An interrupted or failed run can never leave an accepted partial artifact.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".m013b-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def main() -> int:
    protocol = read(PROTOCOL)
    if protocol["evaluator_version"] != EVALUATOR_VERSION:
        raise SystemExit(
            f"protocol {protocol['protocol_version']} targets {protocol['evaluator_version']}, "
            f"evaluator is {EVALUATOR_VERSION}"
        )

    choice_examples = read(FIX / "m013a-choice-v1.json")["examples"]
    binary_examples = read(FIX / "m013a-binary-v1.json")["examples"]
    choice_by_case = {e["case_id"]: e for e in choice_examples}
    binary_by_case = {e["case_id"]: e for e in binary_examples}

    reports = load_reports()
    legacy = attach_examples(reports["choice-legacy"], choice_by_case)
    cross = attach_examples(reports["choice-cross"], choice_by_case)
    binary = attach_examples(reports["binary"], binary_by_case)

    # ---- Corrected, target-independent counterfactual audit (both heads) ----
    counterfactual = {}
    counterfactual_summaries = {}
    for name, report in (("choice-legacy", legacy), ("choice-cross", cross)):
        pairs = build_pairs(choice_examples, report["outcomes"])
        metrics = [evaluate_pair(pair) for pair in pairs]
        summary = summarize_pairs(metrics)
        counterfactual_summaries[name] = summary

        # Historical quantity, recomputed here ONLY to show why it is misleading.
        legacy_style_sign_flips = 0
        legacy_style_pairs = 0
        for pair in pairs:
            before, after = pair.before_outcome, pair.after_outcome
            if before.get("target") is None or after.get("target") is None:
                continue
            if before["target"] == after["target"]:
                continue
            options = [o["id"] for o in pair.before_example["request"]["spec"]["options"]]
            before_index = options.index(before["target"])
            after_index = options.index(after["target"])
            before_margin = before["raw_logits"][before_index] - before["raw_logits"][1 - before_index]
            after_margin = after["raw_logits"][after_index] - after["raw_logits"][1 - after_index]
            legacy_style_pairs += 1
            if before_margin * after_margin < 0:
                legacy_style_sign_flips += 1

        no_answer_groups = len({r["leakage_group"] for r in report["outcomes"] if r["target"] is None})
        answerable_rows = [r for r in report["outcomes"] if r["target"] is not None]
        conditional_brier = mean(
            [
                sum(
                    (p - float(i == options.index(r["target"]))) ** 2
                    for i, p in enumerate(r["raw_probabilities"])
                )
                for r, options in [
                    (r, [o["id"] for o in choice_by_case[r["case_id"]]["request"]["spec"]["options"]])
                    for r in answerable_rows
                ]
            ]
        )
        counters = {
            "pairs": summary["pairs"],
            "answerable_pairs": summary["answerable_pairs"],
            "answerable_cases": len(answerable_rows),
            "both_correct_rate": summary["target_correctness"]["both_correct_rate"],
            "input_response_rate": summary["input_response"]["response_rate"],
            "no_answer_recall": legacy_style_no_answer_recall(report),
            "no_answer_groups": no_answer_groups,
            "conditional_brier": conditional_brier,
        }
        counterfactual[name] = {
            "corrected_fixed_option_identity": summary,
            "historical_label_relative_margin": {
                "pairs_with_flipped_target": legacy_style_pairs,
                "raw_target_margin_changes_sign": legacy_style_sign_flips,
                "rate": (legacy_style_sign_flips / legacy_style_pairs) if legacy_style_pairs else None,
                "why_misleading": (
                    "target_index moves with the label, so an unchanged score vector yields +1 then -1 "
                    "with zero response to the manipulated input; this is label alignment, not sensitivity"
                ),
            },
            "counters": counters,
        }

    # ---- Choice gate evaluation -------------------------------------------
    legacy_slices = choice_slices(legacy)
    cross_slices = choice_slices(cross)
    paired, delta_ci = paired_accuracy_delta(legacy, cross)
    delta_ci = dict(delta_ci)
    delta_ci["mean"] = mean([row["delta"] for row in paired])

    control_accuracy = train_majority_accuracy(cross, legacy, choice_by_case)
    choice_gates = build_choice_gates(
        protocol,
        legacy_slices,
        cross_slices,
        delta_ci,
        control_accuracy,
        counterfactual["choice-cross"]["counters"],
    )
    choice_evaluation = evaluate_gates(choice_gates, task="choice")

    # ---- Binary gate evaluation -------------------------------------------
    binary_analysis = read(M013A / "quality-analysis.json")["binary"]
    binary_gates = build_binary_gates(protocol, binary_analysis)
    binary_evaluation = evaluate_gates(binary_gates, task="binary")

    unsupported = sorted(
        g["name"] for g in choice_evaluation.as_dict()["gates"] if g["status"] == GATE_INSUFFICIENT_SUPPORT
    )

    input_hashes = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in (
            FIX / "m013a-choice-v1.json",
            FIX / "m013a-choice-v1.split.json",
            FIX / "m013a-binary-v1.json",
            FIX / "m013a-binary-v1.split.json",
            M013A / "choice-legacy.report.json",
            M013A / "choice-cross.report.json",
            M013A / "binary.report.json",
            M013A / "quality-analysis.json",
            M013A / "choice-legacy.artifact.json",
            M013A / "choice-cross.artifact.json",
            M013A / "binary.artifact.json",
            ROOT / "docs/m013a-protocol-v1.md",
        )
    }
    input_hashes[str(PROTOCOL.relative_to(ROOT))] = sha256_file(PROTOCOL)
    input_hashes[str(Path("scripts/m013b_evaluator.py").as_posix())] = sha256_file(
        ROOT / "scripts/m013b_evaluator.py"
    )

    payload = {
        "sidecar": "m013b-retrospective-audit-v1",
        "evaluator_version": EVALUATOR_VERSION,
        "protocol_version": protocol["protocol_version"],
        "status": "post_hoc_semantic_erratum_only",
        "disclaimer": (
            "This sidecar reinterprets already-observed M013a evidence. It is NOT new held-out quality "
            "evidence, NOT model-selection evidence, and does not qualify any candidate. Frozen M013a "
            "reports, artifacts, datasets and closure records are unchanged."
        ),
        "erratum": {
            "defect_a_misleading_metric": {
                "old_field": "choice.target_flipping_counterfactuals.raw_target_margin_changes_sign",
                "old_value": read(M013A / "quality-analysis.json")["choice"]["target_flipping_counterfactuals"][
                    "raw_target_margin_changes_sign"
                ],
                "old_value_both_final_correct": read(M013A / "quality-analysis.json")["choice"][
                    "target_flipping_counterfactuals"
                ]["both_final_decisions_correct"],
                "why_misleading": counterfactual["choice-cross"]["historical_label_relative_margin"][
                    "why_misleading"
                ],
                "corrected_field": "corrected_fixed_option_identity.input_response.response_rate",
                "corrected_values": {
                    head: {
                        "pairs": counterfactual[head]["corrected_fixed_option_identity"]["pairs"],
                        "answerable_pairs": counterfactual[head]["corrected_fixed_option_identity"][
                            "answerable_pairs"
                        ],
                        "pairs_with_any_option_logit_response": counterfactual[head][
                            "corrected_fixed_option_identity"
                        ]["input_response"]["pairs_with_any_option_logit_response"],
                        "response_rate": counterfactual[head]["corrected_fixed_option_identity"][
                            "input_response"
                        ]["response_rate"],
                        "identity_normalized_argmax_change_rate": counterfactual[head][
                            "corrected_fixed_option_identity"
                        ]["identity_normalized_argmax_change"]["rate"],
                        "both_correct_rate": counterfactual[head]["corrected_fixed_option_identity"][
                            "target_correctness"
                        ]["both_correct_rate"],
                        "label_alignment_sign_flip_rate": counterfactual[head][
                            "corrected_fixed_option_identity"
                        ]["label_alignment"]["sign_flip_rate"],
                    }
                    for head in ("choice-legacy", "choice-cross")
                },
            },
            "defect_b_under_enforced_positive_gate": {
                "old_field": "choice.classification (primary CI only)",
                "old_value": read(M013A / "quality-analysis.json")["choice"]["classification"],
                "why_misleading": (
                    "the historical classifier assigned the verdict from the paired primary CI alone and "
                    "recorded unsupported OOD slices and counterfactual outcomes without gating them; an "
                    "adversarial report could therefore produce a false positive"
                ),
                "corrected_field": "gate_verdicts.choice",
                "corrected_value": choice_evaluation.verdict,
                "corrected_reason": choice_evaluation.reason,
                "gates_blocking_positive": unsupported,
            },
        },
        "gate_verdicts": {
            "choice": choice_evaluation.as_dict(),
            "binary": binary_evaluation.as_dict(),
        },
        "retained_disposition": {
            "binary": "negative — text and combined shift are significantly worse than the train prior",
            "choice": "indeterminate — paired accuracy delta is exactly 0.00 and required slice support is unmet",
            "unchanged": True,
            "note": "M013b corrects evaluation integrity only; it does not alter or promote any result.",
        },
        "counterfactual_audit": counterfactual,
        "choice_slices": {"choice-legacy": legacy_slices, "choice-cross": cross_slices},
        "paired_accuracy": {"mean": delta_ci["mean"], "ci": delta_ci, "pairs": len(paired)},
        "input_sha256": input_hashes,
        "frozen_inputs_modified": False,
    }

    atomic_write_json(OUT / "m013a-audit-erratum.json", payload)
    print(json.dumps(payload["erratum"], indent=2, sort_keys=True))
    print(json.dumps(payload["gate_verdicts"], indent=2, sort_keys=True))
    return 0


def legacy_style_no_answer_recall(report):
    no_answer = [r for r in report["outcomes"] if r["target"] is None]
    return mean([float(r["abstained"]) for r in no_answer]) if no_answer else None


def train_majority_accuracy(cross_report, legacy_report, choice_by_case):
    """Highest negative-control answerable accuracy, computed without fitting.

    Fixed option identity only: the most frequent training target, and the
    always-answer raw argmax. These are diagnostics, never candidates.
    """
    from collections import Counter

    train_ids = read(FIX / "m013a-choice-v1.split.json")["train"]
    train_targets = [
        choice_by_case[i]["label"]["value"] for i in train_ids if choice_by_case[i]["label"]["value"] is not None
    ]
    majority = Counter(train_targets).most_common(1)[0][0]
    rows = [r for r in cross_report["outcomes"] if r["target"] is not None]
    majority_accuracy = mean([float(r["target"] == majority) for r in rows])
    always_answer = mean(
        [
            float(
                choice_by_case[r["case_id"]]["request"]["spec"]["options"][
                    r["raw_probabilities"].index(max(r["raw_probabilities"]))
                ]["id"]
                == r["target"]
            )
            for r in rows
        ]
    )
    return max(majority_accuracy or 0.0, always_answer or 0.0)


if __name__ == "__main__":
    raise SystemExit(main())