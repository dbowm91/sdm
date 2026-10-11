#!/usr/bin/env python3
"""M013c versioned qualification-gate evaluator: confidence bounds and support.

M013c is a *narrow, additive* hardening of the M013b evaluator. It changes no
historical file, imports nothing from `analyze_m013a_quality.py`, and leaves
`m013b_evaluator.py`, `m013b_audit_m013a.py` and `m013b_diagnostics.py` byte
identical so the M013a/M013b evidence reproduces unchanged. Only the stable pure
numeric helpers (`mean`, `group_bootstrap`, `is_finite_number`) are imported.

Four defects verified at baseline are addressed here:

A. `build_binary_gates` in the M013b audit fed a *point mean* into a
   `threshold_gate(..., comparator=">")`. A negative mean with a straddling
   interval was labelled a significant negative regression, and a positive mean
   with a straddling interval could qualify. The preregistered rule is the
   paired GROUP bootstrap 95% interval: favorable only when `lower > 0`,
   unfavorable only when `upper < 0`, otherwise indeterminate. There is no
   point-mean shortcut here.
B. The M013b `_supported()` helper accepted `evidence_count > 0`. A critical
   failure at n=1 could therefore assert a negative regression while the
   separate family support gate said "insufficient". Here `minimum_group_support`
   is an explicit immutable field of every statistical gate, cross-validated
   against the protocol support gate, and attached to the *same* slice and
   effect being classified.
C. Gate builders iterated the *reported* slices rather than the protocol's
   declared required sets, so a missing critical family could be silently
   skipped. Here the required family/OOD sets are enumerated in deterministic
   protocol order and completeness is asserted before any verdict is formed.
D. The `negative_controls_do_not_qualify` gate compared a nonnegative accuracy
   against zero (`>= 0.0`), which is a tautology. Here each of the five
   declared controls is a separate, versioned measurement with a paired
   learned-minus-control interval over the same answerable groups and option
   identities, and a positive verdict requires a favorable interval against the
   meaningful controls.

Verdict priority, highest first: `invalid` > supported critical `negative` >
`indeterminate` > `positive`. Missing or structurally inconsistent mandatory
evidence is invalid, never positive.

Version: m013c-evaluator-v1
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from m013b_evaluator import is_finite_number, mean

M013C_EVALUATOR_VERSION = "m013c-evaluator-v1"

#: Interval provenance accepted by this evaluator. A different method, replicate
#: count or seed is a *different* estimator and may not be silently accepted.
REQUIRED_BOOTSTRAP_METHOD = "paired_group_bootstrap_percentile"
REQUIRED_REPLICATES = 10_000
REQUIRED_SEED = 14014
REQUIRED_CONFIDENCE = 0.95

#: Machine-readable gate states. Reused verbatim from the M013b vocabulary so a
#: reader of either evaluator sees the same four states.
GATE_PASS = "pass"
GATE_FAIL = "fail"
GATE_INSUFFICIENT_SUPPORT = "insufficient_support"
GATE_INVALID = "invalid"
GATE_STATUSES = (GATE_PASS, GATE_FAIL, GATE_INSUFFICIENT_SUPPORT, GATE_INVALID)

#: Machine-readable task verdicts.
VERDICT_POSITIVE = "positive"
VERDICT_NEGATIVE = "negative"
VERDICT_INDETERMINATE = "indeterminate"
VERDICT_INVALID = "invalid"
VERDICTS = (VERDICT_POSITIVE, VERDICT_NEGATIVE, VERDICT_INDETERMINATE, VERDICT_INVALID)

#: Three-way confidence decisions derived from the interval bounds.
DECISION_FAVORABLE = "favorable"
DECISION_UNFAVORABLE = "unfavorable"
DECISION_INDETERMINATE = "indeterminate"

#: The five controls the frozen protocol declares. Order is protocol order and
#: is preserved in every serialization.
REQUIRED_NEGATIVE_CONTROLS = (
    "train_majority_option_id",
    "always_abstain",
    "always_answer",
    "shuffled_score",
    "context_only_identical_option_features_min_id",
)

#: Controls whose learned-minus-control comparison can actually carry evidence.
#:
#: `train_majority_option_id`, `shuffled_score` and `context_only_...` are fixed,
#: model-independent decision rules, so beating them is a real requirement.
#: `always_abstain` belongs here too: its answerable accuracy is 0.0 by
#: construction, so requiring the learned candidate to beat it is precisely the
#: requirement that the model answers anything correctly at all. What may never
#: be used is its perfect no-answer recall.
#:
#: `always_answer` is deliberately excluded: it is the candidate's own
#: unthresholded argmax, so learned-minus-always_answer is zero for every
#: candidate by construction. It is still measured and recorded — see
#: `evaluate_controls` — but it can neither carry evidence nor block a verdict
#: that every other mandatory gate has established.
DISCRIMINATING_CONTROLS = (
    "train_majority_option_id",
    "always_abstain",
    "shuffled_score",
    "context_only_identical_option_features_min_id",
)

#: Tolerance for checking that a point estimate lies inside its own interval.
INTERIOR_TOLERANCE = 1e-9


# --------------------------------------------------------------------------
# Paired leakage-group bootstrap
# --------------------------------------------------------------------------


def _quantile(values: Sequence[float], probability: float) -> float:
    """Linear-interpolated quantile over an explicitly sorted sequence.

    Defect E repaired here. `m013b_evaluator.quantile` indexes its argument as if
    it were already sorted, and `m013b_evaluator.group_bootstrap` passes it
    replicate values in random draw order. Any non-degenerate interval computed
    through that path is therefore an interpolation between two arbitrary
    adjacent draws rather than a true percentile.

    The frozen M013a analyzer sorts before interpolating, so every recorded
    M013a/M013b interval is unaffected and stays byte-identical. M013c sorts
    explicitly here and never relies on its caller having done so.
    """
    ordered = sorted(values)
    if not ordered:
        raise _reject("empty_population", "quantile of an empty replicate set")
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(ordered[low])
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def grouped_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    statistic: Callable[[Sequence[Mapping[str, Any]]], float | None],
    *,
    seed: int = REQUIRED_SEED,
    replicates: int = REQUIRED_REPLICATES,
    confidence: float = REQUIRED_CONFIDENCE,
) -> dict[str, Any]:
    """Paired leakage-group bootstrap with correctly ordered percentiles.

    Each independent leakage group is drawn with replacement once per replicate,
    matching the frozen M013a protocol. Resampling never happens per row, and
    the returned ``groups`` count makes the denominator explicit.
    """
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row["leakage_group"]), []).append(row)
    per_group = {}
    for key, members in groups.items():
        value = statistic(members)
        if value is not None:
            per_group[key] = value
    keys = sorted(per_group)
    if not keys:
        return {"groups": 0, "replicates": replicates, "confidence": confidence, "lower": None, "upper": None}
    rng = random.Random(seed)
    replicates_values = []
    for _ in range(replicates):
        replicates_values.append(
            mean([per_group[keys[rng.randrange(len(keys))]] for _ in range(len(keys))])
        )
    tail = (1.0 - confidence) / 2.0
    return {
        "groups": len(keys),
        "replicates": replicates,
        "confidence": confidence,
        "lower": _quantile(replicates_values, tail),
        "upper": _quantile(replicates_values, 1.0 - tail),
    }


class M013cInvalid(ValueError):
    """Raised when evidence, provenance or population identity cannot be trusted.

    Carries a stable machine-readable ``code`` so a caller can map a rejection
    onto the ``invalid`` gate state without string matching.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _reject(code: str, detail: str) -> M013cInvalid:
    return M013cInvalid(code, detail)


def _require_finite(value: Any, code: str, what: str) -> float:
    if not is_finite_number(value):
        raise _reject(code, f"{what} is not a finite number: {value!r}")
    return float(value)


def _require_count(value: Any, code: str, what: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _reject(code, f"{what} is not a non-negative integer count: {value!r}")
    return value


# --------------------------------------------------------------------------
# Interval provenance
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IntervalEstimate:
    """One provenance-validated paired-group interval for a named effect.

    Every field is required. A missing bound, a reversed bound, a point estimate
    outside its own interval, a non-finite number or an unrecognised bootstrap
    method is an integrity failure, not a weak measurement.
    """

    statistic: str
    point_estimate: float
    lower: float
    upper: float
    groups: int
    method: str = REQUIRED_BOOTSTRAP_METHOD
    replicates: int = REQUIRED_REPLICATES
    seed: int = REQUIRED_SEED
    confidence: float = REQUIRED_CONFIDENCE
    comparator: str = "higher_is_better"

    def __post_init__(self) -> None:
        if not isinstance(self.statistic, str) or not self.statistic:
            raise _reject("malformed_statistic", f"statistic must be a non-empty string: {self.statistic!r}")
        if self.comparator not in ("higher_is_better", "lower_is_better"):
            raise _reject("unknown_comparator", f"{self.comparator!r} is not a supported comparator direction")
        _require_finite(self.point_estimate, "non_finite_interval", f"{self.statistic} point estimate")
        _require_finite(self.lower, "non_finite_interval", f"{self.statistic} interval lower bound")
        _require_finite(self.upper, "non_finite_interval", f"{self.statistic} interval upper bound")
        if self.lower > self.upper:
            raise _reject(
                "reversed_interval",
                f"{self.statistic} bounds are reversed: lower={self.lower!r} > upper={self.upper!r}",
            )
        _require_count(self.groups, "malformed_group_count", f"{self.statistic} independent group count")
        if self.method != REQUIRED_BOOTSTRAP_METHOD:
            raise _reject(
                "unsupported_bootstrap_method",
                f"{self.statistic} declares method {self.method!r}; this evaluator only accepts "
                f"{REQUIRED_BOOTSTRAP_METHOD!r}",
            )
        if int(self.replicates) != REQUIRED_REPLICATES:
            raise _reject(
                "bootstrap_replicate_mismatch",
                f"{self.statistic} declares {self.replicates!r} replicates; "
                f"{REQUIRED_REPLICATES} is preregistered",
            )
        if int(self.seed) != REQUIRED_SEED:
            raise _reject(
                "bootstrap_seed_mismatch",
                f"{self.statistic} declares seed {self.seed!r}; {REQUIRED_SEED} is preregistered",
            )
        if float(self.confidence) != REQUIRED_CONFIDENCE:
            raise _reject(
                "bootstrap_confidence_mismatch",
                f"{self.statistic} declares confidence {self.confidence!r}; {REQUIRED_CONFIDENCE} is preregistered",
            )
        if self.groups == 0:
            raise _reject("empty_population", f"{self.statistic} reports zero independent groups")
        # The point estimate must lie inside the interval it is reported with.
        # A mean that contradicts its own bounds cannot come from that estimator.
        if (
            self.point_estimate < self.lower - INTERIOR_TOLERANCE
            or self.point_estimate > self.upper + INTERIOR_TOLERANCE
        ):
            raise _reject(
                "point_estimate_outside_interval",
                f"{self.statistic} mean {self.point_estimate!r} lies outside its own "
                f"[{self.lower!r}, {self.upper!r}] interval",
            )

    @classmethod
    def from_report(
        cls,
        statistic: str,
        payload: Mapping[str, Any],
        *,
        point: Any,
        declared: Mapping[str, Any],
        comparator: str = "higher_is_better",
    ) -> "IntervalEstimate":
        """Build from a frozen ``improvement_ci_vs_train_prior`` style block.

        The frozen report block records the observed bounds, group count,
        replicate count and confidence. The estimator identity itself — method
        and seed — is declared by the frozen *protocol*, because the report is
        produced by a single seeded run. Both sources are therefore required and
        cross-validated: a report whose replicate count or confidence disagrees
        with the protocol is an integrity failure, not a measurement to accept.

        Anything absent from either side is an integrity failure rather than an
        assumed default.
        """
        if not isinstance(payload, Mapping):
            raise _reject("malformed_interval_block", f"{statistic} interval block is not an object")
        if not isinstance(declared, Mapping):
            raise _reject("missing_protocol_key", f"{statistic} has no declared bootstrap provenance")

        missing_report = [key for key in ("lower", "upper", "groups", "replicates", "confidence") if key not in payload]
        if missing_report:
            raise _reject(
                "incomplete_interval_metadata",
                f"{statistic} interval is missing required metadata {missing_report}",
            )
        missing_declared = [key for key in ("seed", "replicates", "confidence") if key not in declared]
        if missing_declared:
            raise _reject(
                "incomplete_interval_metadata",
                f"{statistic} protocol bootstrap declaration is missing {missing_declared}",
            )

        # The report may restate the estimator; when it does, it must agree.
        method = payload.get("method", declared.get("method", REQUIRED_BOOTSTRAP_METHOD))
        seed = payload.get("seed", declared["seed"])
        if payload.get("replicates") != declared["replicates"]:
            raise _reject(
                "bootstrap_replicate_mismatch",
                f"{statistic} reports {payload.get('replicates')!r} replicates but the protocol declares "
                f"{declared['replicates']!r}",
            )
        if float(payload.get("confidence")) != float(declared["confidence"]):
            raise _reject(
                "bootstrap_confidence_mismatch",
                f"{statistic} reports confidence {payload.get('confidence')!r} but the protocol declares "
                f"{declared['confidence']!r}",
            )
        return cls(
            statistic=statistic,
            point_estimate=_require_finite(point, "non_finite_interval", f"{statistic} point estimate"),
            lower=payload["lower"],
            upper=payload["upper"],
            groups=payload["groups"],
            method=method,
            replicates=declared["replicates"],
            seed=seed,
            confidence=declared["confidence"],
            comparator=comparator,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "statistic": self.statistic,
            "point_estimate": self.point_estimate,
            "lower": self.lower,
            "upper": self.upper,
            "groups": self.groups,
            "method": self.method,
            "replicates": self.replicates,
            "seed": self.seed,
            "confidence": self.confidence,
            "comparator": self.comparator,
        }


def aggregate_by_group(
    rows: Sequence[Mapping[str, Any]],
    statistic_name: str,
) -> list[dict[str, Any]]:
    """Collapse per-case paired deltas into one row per independent group.

    Several cases legitimately share a leakage group; the independent unit is the
    group. Duplicate *case* identities are an integrity failure, whereas repeated
    group membership is expected. Group identifiers themselves must be well
    formed, because the bootstrap resamples exactly those identifiers.
    """
    if not rows:
        raise _reject("empty_population", f"{statistic_name} has no paired rows")
    seen_cases: set[str] = set()
    case_group: dict[str, str] = {}
    by_group: dict[str, list[float]] = {}
    for row in rows:
        group = row.get("leakage_group")
        if not isinstance(group, str) or not group:
            raise _reject("malformed_group_id", f"{statistic_name} row has invalid group {group!r}")
        case_id = row.get("case_id")
        if case_id is not None:
            if not isinstance(case_id, str) or not case_id:
                raise _reject("malformed_case_id", f"{statistic_name} row has invalid case id {case_id!r}")
            if case_id in seen_cases:
                raise _reject("duplicate_case_id", f"{statistic_name} repeats case id {case_id!r}")
            seen_cases.add(case_id)
            previous = case_group.setdefault(case_id, group)
            if previous != group:
                raise _reject(
                    "case_group_conflict",
                    f"{statistic_name} case {case_id!r} appears in leakage groups {previous!r} and {group!r}; "
                    "the independent unit of a case must be unambiguous",
                )
        by_group.setdefault(group, []).append(_require_finite(row.get("delta"), "non_finite_delta", f"{statistic_name} paired delta"))
    return [
        {"leakage_group": group, "delta": mean(by_group[group])}
        for group in sorted(by_group)
    ]


def paired_group_interval(
    rows: Sequence[Mapping[str, Any]],
    statistic_name: str,
    *,
    seed: int = REQUIRED_SEED,
    replicates: int = REQUIRED_REPLICATES,
    confidence: float = REQUIRED_CONFIDENCE,
    already_grouped: bool = False,
) -> IntervalEstimate:
    """Compute a grouped interval from per-case paired deltas.

    Resampling stays at the leakage-group level; no per-row uncertainty is used.
    Callers that already hold one row per group pass ``already_grouped=True``.
    """
    grouped = list(rows) if already_grouped else aggregate_by_group(rows, statistic_name)
    interval = grouped_bootstrap(
        grouped,
        lambda members: mean([member["delta"] for member in members]),
        seed=seed,
        replicates=replicates,
        confidence=confidence,
    )
    if interval["groups"] == 0 or interval["lower"] is None or interval["upper"] is None:
        raise _reject("unestimable_interval", f"{statistic_name} could not be estimated from the supplied groups")
    return IntervalEstimate(
        statistic=statistic_name,
        point_estimate=mean([row["delta"] for row in rows]),
        lower=interval["lower"],
        upper=interval["upper"],
        groups=interval["groups"],
        method=REQUIRED_BOOTSTRAP_METHOD,
        replicates=replicates,
        seed=seed,
        confidence=confidence,
    )


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Gate:
    """One machine-readable M013c gate outcome.

    ``minimum_group_support`` is an explicit immutable field. It is never
    inferred from ``evidence_count`` and it always describes the *same*
    population as the effect being classified.
    """

    name: str
    status: str
    mandatory: bool
    critical: bool = False
    evidence_count: int | None = None
    minimum_group_support: int | None = None
    decision: str | None = None
    observed: float | None = None
    lower: float | None = None
    upper: float | None = None
    threshold: float | None = None
    comparator: str | None = None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "mandatory": self.mandatory,
            "critical": self.critical,
            "evidence_count": self.evidence_count,
            "minimum_group_support": self.minimum_group_support,
            "decision": self.decision,
            "observed": self.observed,
            "lower": self.lower,
            "upper": self.upper,
            "threshold": self.threshold,
            "comparator": self.comparator,
            "reason": self.reason,
        }


def _check_gate_status(status: str) -> str:
    if status not in GATE_STATUSES:
        raise _reject("unknown_gate_status", f"{status!r} is not a valid gate status")
    return status


def support_gate(
    name: str,
    *,
    observed: int,
    required: int,
    mandatory: bool = True,
    critical: bool = False,
) -> Gate:
    """Independent-unit support gate for one explicitly named population."""
    _require_count(observed, "malformed_support_count", f"{name} observed support")
    if not isinstance(required, int) or isinstance(required, bool) or required <= 0:
        raise _reject("malformed_support_threshold", f"{name} required support is not positive: {required!r}")
    status = GATE_PASS if observed >= required else GATE_INSUFFICIENT_SUPPORT
    return Gate(
        name=name,
        status=status,
        mandatory=mandatory,
        critical=critical,
        evidence_count=observed,
        minimum_group_support=required,
        observed=float(observed),
        threshold=float(required),
        comparator=">=",
        reason=f"{observed} eligible independent groups, preregistered minimum {required}",
    )


def confidence_gate(
    name: str,
    interval: IntervalEstimate | None,
    *,
    minimum_group_support: int,
    mandatory: bool = True,
    critical: bool = False,
    description: str = "",
) -> Gate:
    """Three-way decision from the interval bounds, bounded by real support.

    Favorable requires ``lower > 0`` *and* at least ``minimum_group_support``
    independent eligible groups. Unfavorable requires ``upper < 0`` *and* the
    same support. An interval that spans or touches zero is indeterminate no
    matter how large its point estimate is.

    A directional result reached with fewer than ``minimum_group_support``
    groups is ``insufficient_support``, never ``fail``: an unsupported critical
    regression must not be recorded as a supported negative.
    """
    if not isinstance(minimum_group_support, int) or isinstance(minimum_group_support, bool) or minimum_group_support <= 0:
        raise _reject("malformed_support_threshold", f"{name} minimum_group_support is not positive: {minimum_group_support!r}")
    label = description or name
    if interval is None:
        return Gate(
            name=name,
            status=GATE_INSUFFICIENT_SUPPORT,
            mandatory=mandatory,
            critical=critical,
            minimum_group_support=minimum_group_support,
            decision=DECISION_INDETERMINATE,
            reason=(
                f"{label}: no estimable interval was supplied; positive or negative eligibility "
                "cannot be established"
            ),
        )

    observed_groups = interval.groups
    supported = observed_groups >= minimum_group_support
    span = f"[{interval.lower}, {interval.upper}]"
    common = dict(
        name=name,
        mandatory=mandatory,
        critical=critical,
        evidence_count=observed_groups,
        minimum_group_support=minimum_group_support,
        observed=interval.point_estimate,
        lower=interval.lower,
        upper=interval.upper,
        threshold=0.0,
        comparator=interval.comparator,
    )

    if interval.lower > 0.0:
        if supported:
            return Gate(
                **common,
                status=GATE_PASS,
                decision=DECISION_FAVORABLE,
                reason=(
                    f"{label}: 95% paired group interval {span} lies wholly above zero with "
                    f"{observed_groups} >= {minimum_group_support} eligible independent groups"
                ),
            )
        return Gate(
            **common,
            status=GATE_INSUFFICIENT_SUPPORT,
            decision=DECISION_INDETERMINATE,
            reason=(
                f"{label}: interval {span} favors improvement, but {observed_groups} < "
                f"{minimum_group_support} eligible independent groups"
            ),
        )

    if interval.upper < 0.0:
        if supported:
            return Gate(
                **common,
                status=GATE_FAIL,
                decision=DECISION_UNFAVORABLE,
                reason=(
                    f"{label}: 95% paired group interval {span} lies wholly below zero with "
                    f"{observed_groups} >= {minimum_group_support} eligible independent groups"
                ),
            )
        return Gate(
            **common,
            status=GATE_INSUFFICIENT_SUPPORT,
            decision=DECISION_INDETERMINATE,
            reason=(
                f"{label}: interval {span} disfavors the candidate, but {observed_groups} < "
                f"{minimum_group_support} eligible independent groups; insufficient support is "
                "not a supported critical regression"
            ),
        )

    return Gate(
        **common,
        status=GATE_INSUFFICIENT_SUPPORT,
        decision=DECISION_INDETERMINATE,
        reason=(
            f"{label}: 95% paired group interval {span} spans zero; the point estimate "
            f"{interval.point_estimate} does not decide the outcome"
        ),
    )


def threshold_gate(
    name: str,
    *,
    observed: float | None,
    threshold: float | None,
    comparator: str,
    evidence_count: int | None = None,
    minimum_group_support: int | None = None,
    mandatory: bool = True,
    critical: bool = False,
    description: str = "",
) -> Gate:
    """Numeric gate for a rate or bounded score that has no interval semantics.

    A missing preregistered threshold can never yield ``pass``: without a
    criterion fixed before the data were seen, the honest state is
    ``insufficient_support``.
    """
    label = description or name
    if threshold is None:
        return Gate(
            name=name,
            status=GATE_INSUFFICIENT_SUPPORT,
            mandatory=mandatory,
            critical=critical,
            evidence_count=evidence_count,
            minimum_group_support=minimum_group_support,
            observed=observed,
            threshold=None,
            comparator=comparator,
            reason=(
                f"{label} has no preregistered numeric threshold; positive eligibility cannot be "
                "established retrospectively"
            ),
        )
    _require_finite(threshold, "non_finite_threshold", f"{name} threshold")
    if observed is None:
        return Gate(
            name=name,
            status=GATE_INSUFFICIENT_SUPPORT,
            mandatory=mandatory,
            critical=critical,
            evidence_count=evidence_count,
            minimum_group_support=minimum_group_support,
            observed=None,
            threshold=float(threshold),
            comparator=comparator,
            reason=f"{label} could not be estimated from the supplied evidence",
        )
    observed = _require_finite(observed, "non_finite_gate_observation", f"{name} observed value")
    met = {">": observed > threshold, ">=": observed >= threshold, "<": observed < threshold, "<=": observed <= threshold}.get(comparator)
    if met is None:
        raise _reject("unknown_comparator", f"{comparator!r} is not a supported comparator")
    return Gate(
        name=name,
        status=GATE_PASS if met else GATE_FAIL,
        mandatory=mandatory,
        critical=critical,
        evidence_count=evidence_count,
        minimum_group_support=minimum_group_support,
        observed=observed,
        threshold=float(threshold),
        comparator=comparator,
        reason=f"observed {observed!r} {comparator} preregistered {threshold!r}" + (f" ({label})" if label else ""),
    )


def invalid_gate(name: str, reason: str, *, mandatory: bool = True, critical: bool = False) -> Gate:
    return Gate(name=name, status=GATE_INVALID, mandatory=mandatory, critical=critical, reason=reason)


# --------------------------------------------------------------------------
# Protocol and required-set completeness
# --------------------------------------------------------------------------


def _declared_names(block: Mapping[str, Any], key: str, label: str) -> tuple[str, ...]:
    values = block.get(key)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)) or not values:
        raise _reject("empty_mandatory_array", f"{label} declares no {key}")
    names = []
    for value in values:
        if not isinstance(value, str) or not value:
            raise _reject("malformed_declared_name", f"{label} {key} entry is not a non-empty string: {value!r}")
        names.append(value)
    if len(set(names)) != len(names):
        duplicates = sorted({name for name in names if names.count(name) > 1})
        raise _reject("duplicate_declared_name", f"{label} {key} repeats {duplicates}")
    return tuple(names)


def validate_protocol(protocol: Mapping[str, Any], *, task: str) -> dict[str, Any]:
    """Validate the declared gate sets before any evidence is considered.

    Aborts on a missing protocol key, an empty mandatory array, a duplicated
    family, a critical family that is not required, or a non-positive support
    minimum. The gate evaluator must never receive a silently incomplete set.
    """
    if not isinstance(protocol, Mapping):
        raise _reject("malformed_protocol", "protocol is not an object")
    if task == "binary":
        block = protocol.get("binary_gates")
        label = "binary_gates"
    elif task == "choice":
        block = protocol.get("choice_gates")
        label = "choice_gates"
    else:
        raise _reject("unknown_task", f"unknown task {task!r}")
    if not isinstance(block, Mapping):
        raise _reject("missing_protocol_key", f"protocol has no {label} block")

    required_key = "required_families" if task == "binary" else "required_ood_families"
    required = _declared_names(block, required_key, label)
    critical = _declared_names(block, "critical_families", label) if block.get("critical_families") is not None else ()
    diagnostic_only = (
        _declared_names(block, "diagnostic_only_families", label)
        if block.get("diagnostic_only_families")
        else ()
    )

    missing = sorted(set(critical) - set(required))
    if missing:
        raise _reject(
            "critical_not_required",
            f"{label} marks {missing} critical but not required; a critical family must be preregistered as required",
        )
    clash = sorted(set(diagnostic_only) & set(required))
    if clash:
        raise _reject(
            "contradictory_family_configuration",
            f"{label} declares {clash} both required and diagnostic-only; a family cannot be qualified and excluded at once",
        )
    overlap = sorted(set(critical) & set(required))
    for family in overlap:
        entry = block.get("family_configuration", {}).get(family, {}) if isinstance(block.get("family_configuration"), Mapping) else {}
        if entry.get("contradicts_critical", False):
            raise _reject("contradictory_family_configuration", f"{label} family {family} configuration contradicts its critical marking")

    minimum = block.get("min_independent_groups_per_family")
    if minimum is None:
        minimum = (protocol.get("support") or {}).get("min_independent_groups_per_primary_slice")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum <= 0:
        raise _reject("malformed_support_threshold", f"{label} declares no positive minimum independent groups")

    return {
        "task": task,
        "label": label,
        "required": required,
        "critical": critical,
        "diagnostic_only": diagnostic_only,
        "minimum_independent_groups": minimum,
    }


def completeness_gates(
    declared: Sequence[str],
    present: Mapping[str, Any],
    *,
    label: str,
    critical: Sequence[str] = (),
    diagnostic_only: Sequence[str] = (),
    population_hash: str | None = None,
) -> list[Gate]:
    """One mandatory presence gate per declared family, in protocol order.

    A declared family that is absent is ``invalid`` — the report is structurally
    incomplete, not merely weak. A declared family that is present but
    under-supported keeps its own support gate. A reported family outside the
    declared set is rejected unless the protocol names it diagnostic-only.
    """
    declared_names = tuple(declared)
    present_names = tuple(sorted(present))
    gates: list[Gate] = []
    for family in declared_names:
        if family not in present:
            gates.append(
                invalid_gate(
                    f"{label}::presence::{family}",
                    f"required {label} {family} is absent from the frozen report; the declared set is incomplete",
                )
            )
            continue
        gates.append(
            Gate(
                name=f"{label}::presence::{family}",
                status=GATE_PASS,
                mandatory=True,
                critical=family in tuple(critical),
                evidence_count=None,
                reason=f"required {label} {family} is present exactly once"
                + (f"; population {population_hash}" if population_hash else ""),
            )
        )
    undeclared = sorted(set(present_names) - set(declared_names) - set(diagnostic_only))
    if undeclared:
        gates.append(
            invalid_gate(
                f"{label}::undeclared_family",
                f"report contains {label} families outside the preregistered required set: {undeclared}; "
                "an undeclared family must never be silently qualified",
            )
        )
    present_diagnostic = sorted(set(present_names) & set(diagnostic_only))
    if present_diagnostic:
        # Recorded explicitly and excluded from qualification, so a declared
        # in-distribution family is never rejected as unexpected and never
        # promoted into the required set.
        gates.append(
            Gate(
                name=f"{label}::diagnostic_only",
                status=GATE_PASS,
                mandatory=False,
                critical=False,
                reason=(
                    f"{label} families {present_diagnostic} are declared diagnostic-only: measured and "
                    "reported, excluded from qualification"
                ),
            )
        )
    return gates


# --------------------------------------------------------------------------
# Negative controls
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ControlMeasurement:
    """One declared negative control measured as a separate, versioned quantity.

    Each control is evaluated on the same answerable cases, the same independent
    leakage groups and the same candidate option identities as the learned model
    it is compared against, so the paired difference is meaningful.
    """

    name: str
    control_accuracy: float | None
    learned_accuracy: float | None
    paired_delta: IntervalEstimate | None
    groups: int
    discriminates: bool
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "control_accuracy": self.control_accuracy,
            "learned_accuracy": self.learned_accuracy,
            "paired_delta": self.paired_delta.as_dict() if self.paired_delta else None,
            "groups": self.groups,
            "discriminates": self.discriminates,
            "note": self.note,
        }


def control_discriminates(name: str) -> bool:
    """Whether learned-minus-control can separate a learned candidate.

    ``always_answer`` is the candidate's own unthresholded argmax, so the paired
    difference is zero for every candidate by construction and it carries no
    information. ``always_abstain`` never answers, so its answerable accuracy is
    0.0 by construction; beating it is a genuine requirement (the candidate must
    answer something correctly), while its perfect no-answer recall must never be
    read as learned answerability. Every control is measured and reported; only
    ``always_answer`` is excluded from carrying evidence.
    """
    return name in DISCRIMINATING_CONTROLS


def evaluate_controls(
    controls: Sequence[ControlMeasurement],
    *,
    required: Sequence[str] = REQUIRED_NEGATIVE_CONTROLS,
    minimum_group_support: int,
    threshold: float | None,
    population_hash: str | None = None,
) -> list[Gate]:
    """Assert declared control coverage and test learned-versus-control.

    A control that is never measured is ``invalid``: it cannot be silently
    replaced by a zero baseline or omitted. A measured control without a
    preregistered comparison threshold is ``insufficient_support``. A measured,
    discriminating control whose paired interval does not favor the learned
    candidate is ``fail``.
    """
    required_names = tuple(required)
    if len(set(required_names)) != len(required_names):
        raise _reject("duplicate_declared_name", f"declared negative controls repeat a name: {required_names}")

    by_name: dict[str, ControlMeasurement] = {}
    for control in controls:
        if control.name in by_name:
            raise _reject("duplicate_control", f"negative control {control.name!r} is reported more than once")
        by_name[control.name] = control

    gates: list[Gate] = []
    for name in required_names:
        measurement = by_name.get(name)
        if measurement is None:
            gates.append(
                invalid_gate(
                    f"negative_control::measured::{name}",
                    f"preregistered negative control {name} was not measured on the same answerable "
                    "population; a control may not be replaced by a zero baseline or omitted",
                )
            )
            continue
        gates.append(
            Gate(
                name=f"negative_control::measured::{name}",
                status=GATE_PASS,
                mandatory=True,
                critical=False,
                evidence_count=measurement.groups,
                minimum_group_support=minimum_group_support,
                reason=(
                    f"control {name} measured on {measurement.groups} eligible independent groups"
                    + (f"; population {population_hash}" if population_hash else "")
                    + f". {measurement.note}"
                ),
            )
        )

    if threshold is None:
        for name in required_names:
            if name not in by_name:
                continue
            gates.append(
                Gate(
                    name=f"negative_control::beats::{name}",
                    status=GATE_INSUFFICIENT_SUPPORT,
                    mandatory=True,
                    critical=False,
                    minimum_group_support=minimum_group_support,
                    reason=(
                        f"control {name}: the frozen protocol declares no numeric learned-versus-control "
                        "threshold; a control comparison cannot be established retrospectively"
                    ),
                )
            )
        return gates

    for name in required_names:
        measurement = by_name.get(name)
        if measurement is None:
            continue
        if not control_discriminates(name):
            # Coverage is mandatory and already asserted by the `measured::` gate
            # above. This comparison is recorded but is NOT a mandatory blocker:
            # a structurally uninformative control must not make `positive`
            # permanently unreachable, nor be dropped from the record.
            gates.append(
                Gate(
                    name=f"negative_control::beats::{name}",
                    status=GATE_INSUFFICIENT_SUPPORT,
                    mandatory=False,
                    critical=False,
                    evidence_count=measurement.groups,
                    minimum_group_support=minimum_group_support,
                    reason=(
                        f"control {name} cannot discriminate a learned candidate by construction "
                        f"({measurement.note}); its measured accuracy is "
                        f"{measurement.control_accuracy}. Measured and recorded on the same answerable "
                        "population, not used as evidence and not a mandatory blocker. Its measurement "
                        "gate is mandatory, so it can never be omitted."
                    ),
                )
            )
            continue
        gates.append(
            confidence_gate(
                f"negative_control::beats::{name}",
                measurement.paired_delta,
                minimum_group_support=minimum_group_support,
                mandatory=True,
                critical=False,
                description=f"learned minus control {name} on answerable groups",
            )
        )
    return gates


# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GateEvaluation:
    verdict: str
    reason: str
    gates: list[Gate] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "gates": [gate.as_dict() for gate in self.gates],
        }

    def gates_by_status(self, status: str) -> list[str]:
        return sorted(gate.name for gate in self.gates if gate.status == status)


def evaluate_gates(gates: Sequence[Gate], *, task: str) -> GateEvaluation:
    """Resolve a complete gate set into a task verdict, failing closed.

    Priority, highest first:

    1. ``invalid``      — corrupt evidence, incomplete declared set, or an empty
                          gate set, which can never pass.
    2. ``negative``     — a *supported* critical regression: the interval lies
                          wholly below zero AND the observed group count meets the
                          gate's own ``minimum_group_support``.
    3. ``indeterminate``— insufficient support, an interval spanning zero, an
                          undeclared threshold, or any mandatory gate not passing.
    4. ``positive``     — only when every mandatory gate passes.

    A critical failure below its own support minimum is explicitly excluded from
    the negative branch; it degrades to ``indeterminate``.
    """
    if task not in ("choice", "binary"):
        raise _reject("unknown_task", f"unknown task {task!r}")
    materialised = list(gates)
    if not materialised:
        raise _reject(
            "empty_gate_set",
            "an empty gate set must never pass; no preregistered gate evidence was supplied",
        )
    seen: set[str] = set()
    for gate in materialised:
        _check_gate_status(gate.status)
        if gate.name in seen:
            raise _reject("duplicate_gate_name", f"gate {gate.name!r} appears more than once")
        seen.add(gate.name)

    for gate in materialised:
        if gate.status == GATE_INVALID:
            return GateEvaluation(
                verdict=VERDICT_INVALID,
                reason=f"{task}: gate {gate.name!r} is invalid: {gate.reason}",
                gates=materialised,
            )

    for gate in materialised:
        if not gate.critical or gate.status != GATE_FAIL:
            continue
        minimum = gate.minimum_group_support
        observed = gate.evidence_count
        if minimum is None or observed is None:
            return GateEvaluation(
                verdict=VERDICT_INDETERMINATE,
                reason=(
                    f"{task}: critical gate {gate.name!r} failed without an attached support minimum; "
                    "a regression cannot be asserted without its preregistered support threshold"
                ),
                gates=materialised,
            )
        if observed >= minimum:
            return GateEvaluation(
                verdict=VERDICT_NEGATIVE,
                reason=(
                    f"{task}: critical gate {gate.name!r} failed with support: {observed} >= {minimum} "
                    f"eligible independent groups. {gate.reason}"
                ),
                gates=materialised,
            )

    blockers = [gate for gate in materialised if gate.mandatory and gate.status != GATE_PASS]
    if blockers:
        first = blockers[0]
        return GateEvaluation(
            verdict=VERDICT_INDETERMINATE,
            reason=(
                f"{task}: {len(blockers)} mandatory gate(s) did not pass; first is {first.name!r} "
                f"({first.status}): {first.reason}"
            ),
            gates=materialised,
        )

    return GateEvaluation(
        verdict=VERDICT_POSITIVE,
        reason=f"{task}: all {len(materialised)} mandatory gates passed on preregistered evidence",
        gates=materialised,
    )


def gate_status_counts(gates: Iterable[Gate]) -> dict[str, int]:
    counts = {status: 0 for status in GATE_STATUSES}
    for gate in gates:
        counts[gate.status] += 1
    return counts
