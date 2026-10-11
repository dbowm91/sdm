#!/usr/bin/env python3
"""M013c retrospective gate-decision audit over the frozen M013a evidence.

This script is READ-ONLY with respect to every M013/M013a/M013b frozen input. It
re-reads the unchanged saved reports, artifacts, analysis and protocols, re-derives
every required gate under the M013c confidence-bound semantics, and writes a NEW
sidecar under `target/m013c/`.

It deliberately does NOT:
  * modify `target/m013a/`, `target/m013b/`, `fixtures/`, or any historical
    report/artifact hash;
  * retrain, refit, reselect or re-threshold any model;
  * treat its output as new held-out quality or selection evidence.

The M013b gate semantics are preserved verbatim for reproduction: this script
never rewrites `m013b_evaluator.py`, `m013b_audit_m013a.py` or
`m013b_diagnostics.py`. The sidecar records the *old* M013b decision alongside
the *new* M013c decision for each gate so the change of meaning is auditable.

Every gate a verdict depends on is enumerated from the protocol's declared
required set, never from the reported slices, so a missing family or control is
visible as an `invalid` gate rather than a silently skipped check.

Version: m013c-decision-audit-v1
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m013b_evaluator import mean  # noqa: E402
from m013c_evaluator import (  # noqa: E402
    M013C_EVALUATOR_VERSION,
    REQUIRED_NEGATIVE_CONTROLS,
    GATE_INSUFFICIENT_SUPPORT,
    VERDICT_INDETERMINATE,
    VERDICT_INVALID,
    VERDICT_NEGATIVE,
    VERDICT_POSITIVE,
    ControlMeasurement,
    Gate,
    IntervalEstimate,
    completeness_gates,
    confidence_gate,
    control_discriminates,
    evaluate_controls,
    evaluate_gates,
    gate_status_counts,
    invalid_gate,
    paired_group_interval,
    support_gate,
    threshold_gate,
    validate_protocol,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
M013A = ROOT / "target/m013a"
M013B = ROOT / "target/m013b"
OUT = ROOT / "target/m013c"
M013B_PROTOCOL = Path(__file__).resolve().parent / "m013b_protocol_v1.json"
PROTOCOL = Path(__file__).resolve().parent / "m013c_protocol_v1.json"

AUDIT_VERSION = "m013c-decision-audit-v1"

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


def atomic_write_json(path: Path, payload) -> None:
    """Stage to a temp file, validate, then atomically rename.

    A partial or interrupted run leaves no accepted artifact behind.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    json.loads(text)  # validate before publishing
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".m013c-", suffix=".tmp")
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


# --------------------------------------------------------------------------
# Binary — preregistered CI-bound decisions over the declared required set
# --------------------------------------------------------------------------


def build_binary_gates(protocol, binary_analysis):
    """Enumerate the protocol's declared Binary families, not the reported ones.

    A family present in the report but absent from `required_families` is an
    undeclared family and fails closed. A required family missing from the report
    yields an `invalid` presence gate. A present family's decision comes from its
    own 95% paired group interval, bounded by the preregistered support minimum.
    """
    spec = validate_protocol(protocol, task="binary")
    required = spec["required"]
    minimum = spec["minimum_independent_groups"]
    critical = spec["critical"]
    slices = binary_analysis["slices"]

    gates = completeness_gates(
        required,
        {family: slices[family] for family in slices},
        label="binary_family",
        critical=critical,
        diagnostic_only=spec["diagnostic_only"],
    )

    for family in required:
        metrics = slices.get(family)
        if metrics is None:
            continue
        interval = IntervalEstimate.from_report(
            f"brier_improvement_vs_train_prior::{family}",
            metrics["improvement_ci_vs_train_prior"],
            point=metrics["brier_improvement_vs_train_prior"],
            declared=protocol["bootstrap"],
        )
        gates.append(
            confidence_gate(
                f"brier_improvement_vs_train_prior::{family}",
                interval,
                minimum_group_support=minimum,
                critical=family in critical,
                description=f"Brier improvement over the train-prior constant baseline on {family}",
            )
        )
        # Cross-validate the interval's own group count against the support gate
        # for the same slice; a disagreement is an integrity failure.
        if interval.groups != metrics["independent_groups"]:
            raise SystemExit(
                f"binary family {family}: interval groups {interval.groups} != slice independent groups "
                f"{metrics['independent_groups']}"
            )
        gates.append(
            support_gate(
                f"independent_groups::{family}",
                observed=metrics["independent_groups"],
                required=minimum,
            )
        )
    return gates, spec


# --------------------------------------------------------------------------
# Choice — paired primary, required OOD coverage, real control comparisons
# --------------------------------------------------------------------------


def build_choice_gates(protocol, cross_slices, primary_ci, control_measurements, counters):
    """Assemble every mandatory Choice gate from the frozen protocol source.

    Positive remains structurally unreachable for the frozen M013a protocol: the
    required OOD answerable-group slices are under-supported and the frozen
    protocol declares no numeric counterfactual, answerability, calibration or
    control-comparison threshold.
    """
    spec = validate_protocol(protocol, task="choice")
    required_ood = spec["required"]
    critical_ood = spec["critical"]
    support = protocol["support"]
    choice_spec = protocol["choice_gates"]

    gates = completeness_gates(
        required_ood,
        {family: cross_slices[family] for family in cross_slices},
        label="choice_ood_family",
        critical=critical_ood,
        diagnostic_only=spec["diagnostic_only"],
    )

    # Primary: paired answerable accuracy against the legacy head, CI-bounded.
    gates.append(
        confidence_gate(
            "primary_paired_answerable_accuracy",
            primary_ci,
            minimum_group_support=support["min_independent_groups_per_primary_slice"],
            mandatory=True,
            critical=False,
            description="cross-minus-legacy paired answerable accuracy",
        )
    )

    # Per-slice support for the exact metric, in the eligible population.
    for family in sorted(cross_slices):
        metrics = cross_slices[family]
        gates.append(
            support_gate(
                f"answerable_groups::{family}",
                observed=metrics["answerable_groups"],
                required=support["min_answerable_groups_per_accuracy_slice"],
            )
        )
        if metrics["no_answer_groups"] > 0:
            gates.append(
                support_gate(
                    f"no_answer_groups::{family}",
                    observed=metrics["no_answer_groups"],
                    required=support["min_no_answer_groups_per_no_answer_slice"],
                )
            )

    # Undeclared numeric success thresholds cannot be established retrospectively.
    # Where the frozen protocol declares none, each gate is emitted as
    # `insufficient_support` and can never return pass.
    gates.append(
        _rate_gate(
            "counterfactual_both_correct_rate",
            counters["both_correct_rate"],
            threshold=choice_spec["counterfactual_both_correct_min_rate"],
            comparator=">",
            evidence_count=counters["answerable_pairs"],
            label="share of answerable active-flip pairs answered correctly on both sides",
        )
    )
    gates.append(
        _rate_gate(
            "counterfactual_fixed_option_response_rate",
            counters["input_response_rate"],
            threshold=choice_spec["counterfactual_response_min_rate"],
            comparator=">",
            evidence_count=counters["pairs"],
            label="share of pairs whose SAME-option logits respond to the manipulated input",
        )
    )
    gates.append(
        _rate_gate(
            "answerability_no_answer_recall",
            counters["no_answer_recall"],
            threshold=choice_spec["answerability_no_answer_recall_min"],
            comparator=">=",
            evidence_count=counters["no_answer_groups"],
            label="no-answer recall on eligible independent groups",
        )
    )
    gates.append(
        _rate_gate(
            "calibration_max_conditional_brier",
            counters["conditional_brier"],
            threshold=choice_spec["calibration_max_conditional_brier"],
            comparator="<=",
            evidence_count=counters["answerable_cases"],
            label="conditional option Brier on answerable cases",
        )
    )

    # Critical OOD slices must be present and adequately supported.
    for family in critical_ood:
        metrics = cross_slices.get(family)
        if metrics is None:
            gates.append(
                invalid_gate(
                    f"critical_ood_presence::{family}",
                    f"required critical OOD slice {family} is absent from the frozen M013a report",
                    critical=True,
                )
            )
        else:
            gates.append(
                support_gate(
                    f"critical_ood_support::{family}",
                    observed=metrics["answerable_groups"],
                    required=support["min_answerable_groups_per_accuracy_slice"],
                    mandatory=True,
                )
            )

    # Negative controls: five named, separately measured, paired comparisons.
    gates.extend(
        evaluate_controls(
            control_measurements,
            required=tuple(protocol["negative_controls"]["required"]),
            minimum_group_support=support["min_answerable_groups_per_accuracy_slice"],
            threshold=protocol["negative_controls"].get("learned_beats_control_min_delta"),
            population_hash=None,
        )
    )
    return gates, spec


def _undeclared_gate(name: str, label: str):
    return Gate(
        name=name,
        status=GATE_INSUFFICIENT_SUPPORT,
        mandatory=True,
        critical=False,
        reason=(
            f"{label}: the frozen M013a protocol declares no numeric success threshold; positive "
            "eligibility cannot be established retrospectively"
        ),
    )


def _rate_gate(name, observed, *, threshold, comparator, evidence_count, label):
    """A rate gate with no preregistered threshold is always insufficient.

    A threshold declared by a *future* prospective protocol is honoured here; the
    frozen M013a protocol declares none of these four, so every such gate stays
    `insufficient_support` and positive stays unreachable on this cohort.
    """
    if threshold is None:
        return _undeclared_gate(name, label)
    return threshold_gate(
        name,
        observed=observed,
        threshold=threshold,
        comparator=comparator,
        evidence_count=evidence_count,
        description=label,
    )


# --------------------------------------------------------------------------
# Control measurement from the frozen reports
# --------------------------------------------------------------------------


def choice_slices(report, examples_by_case):
    """Support and accuracy counted in the eligible population per exact metric."""
    slices = {}
    for family in CHOICE_FAMILIES:
        rows = [row for row in report["outcomes"] if examples_by_case[row["case_id"]]["family"] == family]
        if not rows:
            continue
        answerable = [row for row in rows if row["target"] is not None]
        no_answer = [row for row in rows if row["target"] is None]
        slices[family] = {
            "cases": len(rows),
            "independent_groups": len({row["leakage_group"] for row in rows}),
            "answerable_groups": len({row["leakage_group"] for row in answerable}),
            "no_answer_groups": len({row["leakage_group"] for row in no_answer}),
            "answerable_final_accuracy": mean(
                [float(not row["abstained"] and row["prediction"] == row["target"]) for row in answerable]
            ),
            "no_answer_recall": mean([float(row["abstained"]) for row in no_answer]) if no_answer else None,
            "coverage": mean([float(not row["abstained"]) for row in rows]),
        }
    return slices


def paired_primary_delta(legacy, cross):
    """Paired cross-minus-legacy answerable accuracy, grouped and CI-bounded."""
    legacy_by_case = {row["case_id"]: row for row in legacy["outcomes"]}
    cross_by_case = {row["case_id"]: row for row in cross["outcomes"]}
    if set(legacy_by_case) != set(cross_by_case):
        raise SystemExit("legacy and cross reports cover different case ids")
    paired = []
    for case_id, left in sorted(legacy_by_case.items()):
        if left["target"] is None:
            continue
        right = cross_by_case[case_id]
        if left["leakage_group"] != right["leakage_group"]:
            raise SystemExit(f"legacy/cross leakage-group misalignment at {case_id}")
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
    return paired, paired_group_interval(paired, "primary_paired_answerable_accuracy")


def measure_controls(cross, legacy, choice_by_case):
    """Measure every declared negative control on the same answerable population.

    Each control produces its own accuracy and, where the comparison is
    meaningful, its own paired learned-minus-control group interval over exactly
    the same answerable cases, groups and option identities as the candidate.
    """
    import random
    from collections import Counter

    train_ids = read(FIX / "m013a-choice-v1.split.json")["train"]
    train_targets = [
        choice_by_case[i]["label"]["value"] for i in train_ids if choice_by_case[i]["label"]["value"] is not None
    ]
    majority = Counter(train_targets).most_common(1)[0][0]

    answerable = [row for row in cross["outcomes"] if row["target"] is not None]
    groups = sorted({row["leakage_group"] for row in answerable})
    learned_correct = {
        row["case_id"]: float(not row["abstained"] and row["prediction"] == row["target"]) for row in answerable
    }
    learned_accuracy = mean(list(learned_correct.values()))

    def paired(control_correct, statistic: str):
        """Group bootstrap of learned-minus-control on the same answerable rows."""
        rows = []
        by_group: dict[str, list[Mapping[str, float]]] = {}
        for row in answerable:
            by_group.setdefault(row["leakage_group"], []).append(
                {"delta": learned_correct[row["case_id"]] - control_correct[row["case_id"]]}
            )
        for group in sorted(by_group):
            rows.append({"leakage_group": group, "delta": mean([m["delta"] for m in by_group[group]])})
        if not rows:
            return None
        return paired_group_interval(rows, statistic)

    measurements = {}

    # 1. train_majority_option_id — fixed decision rule, model-independent.
    majority_correct = {row["case_id"]: float(row["target"] == majority) for row in answerable}
    measurements["train_majority_option_id"] = ControlMeasurement(
        name="train_majority_option_id",
        control_accuracy=mean(list(majority_correct.values())),
        learned_accuracy=learned_accuracy,
        paired_delta=paired(majority_correct, "learned_minus_train_majority_option_id"),
        groups=len(groups),
        discriminates=True,
        note="fixed train-majority option identity; fully model-independent",
    )

    # 2. always_abstain — never answers; zero answerable accuracy by construction.
    abstain_correct = {row["case_id"]: 0.0 for row in answerable}
    measurements["always_abstain"] = ControlMeasurement(
        name="always_abstain",
        control_accuracy=0.0,
        learned_accuracy=learned_accuracy,
        paired_delta=paired(abstain_correct, "learned_minus_always_abstain"),
        groups=len(groups),
        discriminates=False,
        note="never answers; zero answerable accuracy and perfect no-answer recall are structural",
    )

    # 3. always_answer — the candidate's own unthresholded argmax.
    always_answer_correct = {}
    for row in answerable:
        options = [option["id"] for option in choice_by_case[row["case_id"]]["request"]["spec"]["options"]]
        best = options[row["raw_probabilities"].index(max(row["raw_probabilities"]))]
        always_answer_correct[row["case_id"]] = float(best == row["target"])
    measurements["always_answer"] = ControlMeasurement(
        name="always_answer",
        control_accuracy=mean(list(always_answer_correct.values())),
        learned_accuracy=learned_accuracy,
        paired_delta=paired(always_answer_correct, "learned_minus_always_answer"),
        groups=len(groups),
        discriminates=False,
        note="the candidate's own raw argmax without the abstention cutoff; cannot discriminate",
    )

    # 4. shuffled_score — score vectors permuted across cases, fixed frozen seed.
    rng = random.Random(14014)
    donors = answerable.copy()
    rng.shuffle(donors)
    shuffled_correct = {}
    for row, donor in zip(answerable, donors):
        options = [option["id"] for option in choice_by_case[row["case_id"]]["request"]["spec"]["options"]]
        best = options[donor["raw_probabilities"].index(max(donor["raw_probabilities"]))]
        shuffled_correct[row["case_id"]] = float(best == row["target"])
    measurements["shuffled_score"] = ControlMeasurement(
        name="shuffled_score",
        control_accuracy=mean(list(shuffled_correct.values())),
        learned_accuracy=learned_accuracy,
        paired_delta=paired(shuffled_correct, "learned_minus_shuffled_score"),
        groups=len(groups),
        discriminates=True,
        note="frozen-seed permutation of score vectors across answerable cases",
    )

    # 5. context_only_identical_option_features_min_id — always the minimal option id.
    context_only_correct = {}
    for row in answerable:
        options = [option["id"] for option in choice_by_case[row["case_id"]]["request"]["spec"]["options"]]
        context_only_correct[row["case_id"]] = float(min(options) == row["target"])
    measurements["context_only_identical_option_features_min_id"] = ControlMeasurement(
        name="context_only_identical_option_features_min_id",
        control_accuracy=mean(list(context_only_correct.values())),
        learned_accuracy=learned_accuracy,
        paired_delta=paired(context_only_correct, "learned_minus_context_only_min_id"),
        groups=len(groups),
        discriminates=True,
        note="context-only control answering the lexicographically minimal option identity",
    )

    ordered = [measurements[name] for name in REQUIRED_NEGATIVE_CONTROLS]
    return ordered, learned_accuracy, len(groups)


def main() -> int:
    protocol = read(PROTOCOL)
    choice_examples = read(FIX / "m013a-choice-v1.json")["examples"]
    choice_by_case = {example["case_id"]: example for example in choice_examples}

    cross = read(M013A / "choice-cross.report.json")
    legacy = read(M013A / "choice-legacy.report.json")
    for report in (cross, legacy):
        for outcome in report["outcomes"]:
            outcome.setdefault("abstained", False)

    cross_slices = choice_slices(cross, choice_by_case)
    paired_rows, primary_interval = paired_primary_delta(legacy, cross)
    control_measurements, learned_accuracy, control_groups = measure_controls(cross, legacy, choice_by_case)

    analysis = read(M013A / "quality-analysis.json")
    m013b_erratum = read(M013B / "m013a-audit-erratum.json")
    # Corrected counterfactual counters come from the M013b erratum, which is the
    # authoritative fixed-option-identity recomputation over the same frozen rows.
    # M013c reuses them read-only; it does not recompute or reinterpret them.
    frozen_counters = m013b_erratum["counterfactual_audit"]["choice-cross"]["counters"]
    counters = dict(frozen_counters)

    choice_gates, choice_spec = build_choice_gates(
        protocol, cross_slices, primary_interval, control_measurements, counters
    )
    choice_evaluation = evaluate_gates(choice_gates, task="choice")

    binary_analysis = analysis["binary"]
    binary_gates, binary_spec = build_binary_gates(protocol, binary_analysis)
    binary_evaluation = evaluate_gates(binary_gates, task="binary")

    # ---- Old-vs-new gate decision comparison --------------------------------
    old_binary = read(M013B / "m013a-audit-erratum.json")["gate_verdicts"]

    def old_gate(name: str):
        for gate in old_binary["binary"]["gates"]:
            if gate["name"] == name:
                return gate
        return None

    decision_changes = []
    for gate in binary_gates:
        if not gate.name.startswith("brier_improvement_vs_train_prior::"):
            continue
        previous = old_gate(gate.name)
        decision_changes.append(
            {
                "gate": gate.name,
                "family": gate.name.split("::", 1)[1],
                "m013b_status": previous["status"] if previous else None,
                "m013b_observed_point_estimate": previous["observed"] if previous else None,
                "m013b_used_interval_bounds": False,
                "m013c_status": gate.status,
                "m013c_decision": gate.decision,
                "m013c_interval": {"lower": gate.lower, "upper": gate.upper, "groups": gate.evidence_count},
                "m013c_minimum_group_support": gate.minimum_group_support,
                "m013c_reason": gate.reason,
                "changed": bool(previous and previous["status"] != gate.status),
            }
        )

    control_changes = []
    old_controls = old_binary["choice"]["gates"]
    old_control_gate = next(
        (gate for gate in old_controls if gate["name"] == "negative_controls_do_not_qualify"), None
    )
    for measurement in control_measurements:
        control_changes.append(
            {
                "control": measurement.name,
                "discriminates": measurement.discriminates,
                "control_accuracy": measurement.control_accuracy,
                "learned_accuracy": measurement.learned_accuracy,
                "paired_delta": measurement.paired_delta.as_dict() if measurement.paired_delta else None,
                "note": measurement.note,
            }
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
            M013B / "m013a-audit-erratum.json",
            M013B / "m013b-diagnostics.json",
            ROOT / "docs/m013a-protocol-v1.md",
        )
    }
    input_hashes[str(PROTOCOL.relative_to(ROOT))] = sha256_file(PROTOCOL)
    input_hashes[str(M013B_PROTOCOL.relative_to(ROOT))] = sha256_file(M013B_PROTOCOL)
    input_hashes["scripts/m013c_evaluator.py"] = sha256_file(Path(__file__).resolve().parent / "m013c_evaluator.py")

    payload = {
        "sidecar": AUDIT_VERSION,
        "evaluator_version": M013C_EVALUATOR_VERSION,
        "protocol_version": protocol["protocol_version"],
        "status": "retrospective_gate_semantics_correction_only",
        "disclaimer": (
            "This sidecar reinterprets already-observed M013a evidence under CI-bound, support-bound "
            "gate semantics. It is NOT new held-out quality evidence, NOT model-selection evidence, "
            "and does not qualify any candidate. Frozen M013a/M013b reports, artifacts, datasets and "
            "closure records are unchanged."
        ),
        "gate_verdicts": {
            "choice": choice_evaluation.as_dict(),
            "binary": binary_evaluation.as_dict(),
        },
        "gate_status_counts": {
            "choice": gate_status_counts(choice_gates),
            "binary": gate_status_counts(binary_gates),
        },
        "verdict_priority": [
            VERDICT_INVALID,
            VERDICT_NEGATIVE,
            VERDICT_INDETERMINATE,
            VERDICT_POSITIVE,
        ],
        "declared_required_sets": {
            "binary": {
                "required_families": list(binary_spec["required"]),
                "critical_families": list(binary_spec["critical"]),
                "minimum_independent_groups": binary_spec["minimum_independent_groups"],
            },
            "choice_required_ood_families": list(choice_spec["required"]),
            "choice_critical_ood_families": list(choice_spec["critical"]),
        },
        "old_vs_new_gate_decision": {
            "binary_family_decisions": decision_changes,
            "negative_control_replacement": {
                "old_gate": {
                    "name": "negative_controls_do_not_qualify",
                    "comparator": old_control_gate["comparator"] if old_control_gate else None,
                    "threshold": old_control_gate["threshold"] if old_control_gate else None,
                    "observed": old_control_gate["observed"] if old_control_gate else None,
                    "status": old_control_gate["status"] if old_control_gate else None,
                    "defect": (
                        "compared a nonnegative control accuracy against zero with '>=', a tautology; "
                        "only train-majority and always-answer were measured, and always-answer is the "
                        "candidate's own argmax, so the comparison carried no information"
                    ),
                },
                "new_gates": control_changes,
                "defect_repaired": (
                    "all five declared controls are measured separately on the same answerable "
                    "population, groups and option identities, each with its own paired learned-minus-"
                    "control interval; controls that cannot discriminate by construction are recorded "
                    "and excluded from evidence rather than silently dropped"
                ),
            },
        },
        "negative_controls": [measurement.as_dict() for measurement in control_measurements],
        "choice_primary": {
            "paired_rows": len(paired_rows),
            "learned_answerable_accuracy": learned_accuracy,
            "control_groups": control_groups,
            "interval": primary_interval.as_dict(),
        },
        "retained_disposition": {
            "binary": binary_evaluation.verdict,
            "choice": choice_evaluation.verdict,
            "historical_binary": "negative",
            "historical_choice": "indeterminate",
            "binary_verdict_unchanged": binary_evaluation.verdict == VERDICT_NEGATIVE,
            "choice_verdict_unchanged": choice_evaluation.verdict == VERDICT_INDETERMINATE,
            "note": (
                "M013c hardens gate semantics only; it does not alter or promote any historical result. "
                "The Binary negative and Choice indeterminate dispositions are retained."
            ),
        },
        "input_sha256": input_hashes,
        "frozen_inputs_modified": False,
    }

    atomic_write_json(OUT / "m013c-decision-audit.json", payload)
    print(json.dumps(payload["gate_verdicts"], indent=2, sort_keys=True))
    print(json.dumps(payload["retained_disposition"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
