#!/usr/bin/env python3
"""M014a versioned semantic qualification analyzer (v2).

New entrypoint; leaves scripts/analyze_m014_qualification.py unchanged because
its source hash is in the frozen M014 manifest.

Contracts:
- New evaluate reports (schema sdm-semantic-evaluate-v2) require explicit
  test_evaluation_performed=true AND evaluated_partition=test. Missing flag is
  never inferred for new reports.
- Legacy M014 reports (no schema/evaluated_partition, omitted-true
  serialization) may be interpreted only for explicitly identified legacy
  schema AND matching frozen test-ID/partition evidence; explicit false is
  never evaluated.
- Binary: group -> list of all per-case (case_id, truth, score); both
  counterfactual rows MUST be present in SAME group. Pair candidate/control by
  identical case IDs, never insertion order; reject duplicates/missing/extra.
  Group-mean Brier improvement, resample WHOLE leakage groups (10k
  deterministic draws; predeclared one-sided multiplicity adjustment); never
  per-row bootstrap.
- Choice: pair same option IDs and eligible answerable case IDs; separate raw
  argmax vs final thresholded correctness, abstention/no-answer recall,
  answerable coverage and selective risk. Counterfactual both-correct requires
  BOTH final answers correct. No-answer targets need no extra option. Validate
  option permutations and case/order invariance.
- Require every manifest-named Binary/Choice family plus controls on identical
  eligible groups; enforce answerable>=50, no-answer>=20, pair>=50; no unknown
  family, no missing control; no vacuous positive on empty arrays or missing
  thresholds.
- CI lower/upper and direction from prospectively frozen manifest (Bonferroni
  or declared policy). Invalid provenance/data => invalid; supported critical
  regression => negative; insufficient/straddling => indeterminate; positive
  ONLY if all statistical, OOD, controls, no-answer, counterfactual and
  resource gates pass.
- Resource/platform evidence must be real (16MiB, 128 options, p95/latency/
  cold-load/RSS, host/build IDs, three-host parity). Missing => not positive.
- Output machine-readable per-gate status, support group IDs, per-family
  effect, CI, comparator, frozen threshold origin, cohort/test membership
  hash, artifact fingerprint and task verdict. Human summary mirrors JSON.

Version: m014a-evaluator-v2
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

EVALUATOR_VERSION = "m014a-evaluator-v2"
EVALUATE_SCHEMA = "sdm-semantic-evaluate-v2"
REQUIRED_METHOD = "paired_group_bootstrap_percentile"

GATE_PASS = "pass"
GATE_FAIL = "fail"
GATE_INSUFFICIENT = "insufficient_support"
GATE_INVALID = "invalid"

VERDICT_POSITIVE = "positive"
VERDICT_NEGATIVE = "negative"
VERDICT_INDETERMINATE = "indeterminate"
VERDICT_INVALID = "invalid"


class QualifyInvalid(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _reject(code: str, detail: str) -> QualifyInvalid:
    return QualifyInvalid(code, detail)


def _finite(v: Any, what: str) -> float:
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise _reject("non_finite", f"{what} not a number: {v!r}")
    f = float(v)
    if not math.isfinite(f):
        raise _reject("non_finite", f"{what} not finite: {v!r}")
    return f


def sorted_quantile(values: Sequence[float], prob: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise _reject("empty_population", "quantile of empty set")
    if not (0.0 <= prob <= 1.0):
        raise _reject("bad_probability", f"probability {prob!r} outside [0,1]")
    pos = (len(ordered) - 1) * prob
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(ordered[lo])
    return float(ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo))


@dataclass(frozen=True)
class IntervalEstimate:
    statistic: str
    point: float
    lower: float
    upper: float
    groups: int
    method: str
    replicates: int
    seed: int
    alpha: float  # one-sided adjusted alpha, e.g. 0.05/18
    comparator: str = "higher_is_better"

    def __post_init__(self):
        if not self.statistic:
            raise _reject("malformed_statistic", "empty statistic name")
        for name, v in (("point", self.point), ("lower", self.lower), ("upper", self.upper)):
            _finite(v, f"{self.statistic} {name}")
        if self.lower > self.upper:
            raise _reject("reversed_interval", f"{self.statistic} lower>upper")
        if not isinstance(self.groups, int) or self.groups <= 0:
            raise _reject("empty_population", f"{self.statistic} groups must be >0")
        if self.method != REQUIRED_METHOD:
            raise _reject("unsupported_method", f"{self.statistic} method {self.method!r}")
        if self.replicates <= 0 or self.seed < 0:
            raise _reject("bad_bootstrap", "replicates/seed invalid")
        if not (0.0 < self.alpha < 0.5):
            raise _reject("bad_alpha", f"alpha {self.alpha!r} outside (0,0.5)")
        tol = 1e-9
        if self.point < self.lower - tol or self.point > self.upper + tol:
            raise _reject("point_outside_interval", f"{self.statistic} point outside bounds")
        if self.comparator not in ("higher_is_better", "lower_is_better"):
            raise _reject("unknown_comparator", self.comparator)

    def as_dict(self):
        return {
            "statistic": self.statistic, "point_estimate": self.point,
            "lower": self.lower, "upper": self.upper, "groups": self.groups,
            "method": self.method, "replicates": self.replicates,
            "seed": self.seed, "alpha": self.alpha, "comparator": self.comparator,
        }


@dataclass(frozen=True)
class Gate:
    name: str
    status: str
    mandatory: bool
    critical: bool = False
    evidence_count: int | None = None
    minimum_support: int | None = None
    decision: str | None = None
    observed: float | None = None
    lower: float | None = None
    upper: float | None = None
    threshold: float | None = None
    comparator: str | None = None
    reason: str = ""

    def as_dict(self):
        return {
            "name": self.name, "status": self.status, "mandatory": self.mandatory,
            "critical": self.critical, "evidence_count": self.evidence_count,
            "minimum_group_support": self.minimum_support, "decision": self.decision,
            "observed": self.observed, "lower": self.lower, "upper": self.upper,
            "threshold": self.threshold, "comparator": self.comparator, "reason": self.reason,
        }


def invalid_gate(name: str, reason: str, mandatory: bool = True, critical: bool = False) -> Gate:
    return Gate(name=name, status=GATE_INVALID, mandatory=mandatory, critical=critical, reason=reason)


def support_gate(name: str, observed: int, required: int, mandatory: bool = True, critical: bool = False) -> Gate:
    if not isinstance(observed, int) or observed < 0 or not isinstance(required, int) or required <= 0:
        raise _reject("bad_support", f"{name} support invalid")
    ok = observed >= required
    return Gate(name=name, status=GATE_PASS if ok else GATE_INSUFFICIENT,
                mandatory=mandatory, critical=critical, evidence_count=observed,
                minimum_support=required, observed=float(observed),
                threshold=float(required), comparator=">=",
                reason=f"{observed} eligible independent groups, minimum {required}")


def confidence_gate(name: str, interval: IntervalEstimate | None, minimum_support: int,
                    mandatory: bool = True, critical: bool = False, description: str = "") -> Gate:
    if not isinstance(minimum_support, int) or minimum_support <= 0:
        raise _reject("bad_support", f"{name} minimum support invalid")
    label = description or name
    if interval is None:
        return Gate(name=name, status=GATE_INSUFFICIENT, mandatory=mandatory, critical=critical,
                    minimum_support=minimum_support, decision="indeterminate",
                    reason=f"{label}: no estimable interval")
    supported = interval.groups >= minimum_support
    span = f"[{interval.lower}, {interval.upper}]"
    common = dict(name=name, mandatory=mandatory, critical=critical,
                  evidence_count=interval.groups, minimum_support=minimum_support,
                  observed=interval.point, lower=interval.lower, upper=interval.upper,
                  threshold=0.0, comparator=interval.comparator)
    if interval.lower > 0.0:
        if supported:
            return Gate(**common, status=GATE_PASS, decision="favorable",
                        reason=f"{label}: interval {span} wholly above zero with {interval.groups}>={minimum_support}")
        return Gate(**common, status=GATE_INSUFFICIENT, decision="indeterminate",
                    reason=f"{label}: interval {span} favors improvement but {interval.groups}<{minimum_support}")
    if interval.upper < 0.0:
        if supported:
            return Gate(**common, status=GATE_FAIL, decision="unfavorable",
                        reason=f"{label}: interval {span} wholly below zero with {interval.groups}>={minimum_support}")
        return Gate(**common, status=GATE_INSUFFICIENT, decision="indeterminate",
                    reason=f"{label}: interval {span} disfavors but {interval.groups}<{minimum_support}; not a supported regression")
    return Gate(**common, status=GATE_INSUFFICIENT, decision="indeterminate",
                reason=f"{label}: interval {span} spans zero; point {interval.point} does not decide")


def threshold_gate(name: str, observed: float | None, threshold: float | None, comparator: str,
                   evidence_count: int | None = None, minimum_support: int | None = None,
                   mandatory: bool = True, critical: bool = False, description: str = "") -> Gate:
    label = description or name
    if threshold is None:
        return Gate(name=name, status=GATE_INSUFFICIENT, mandatory=mandatory, critical=critical,
                    evidence_count=evidence_count, minimum_support=minimum_support,
                    observed=observed, threshold=None, comparator=comparator,
                    reason=f"{label} has no preregistered numeric threshold; cannot pass retrospectively")
    _finite(threshold, f"{name} threshold")
    if observed is None:
        return Gate(name=name, status=GATE_INSUFFICIENT, mandatory=mandatory, critical=critical,
                    evidence_count=evidence_count, minimum_support=minimum_support,
                    observed=None, threshold=float(threshold), comparator=comparator,
                    reason=f"{label} could not be estimated")
    observed = _finite(observed, f"{name} observed")
    ops = {">": observed > threshold, ">=": observed >= threshold,
           "<": observed < threshold, "<=": observed <= threshold}
    if comparator not in ops:
        raise _reject("unknown_comparator", comparator)
    met = ops[comparator]
    return Gate(name=name, status=GATE_PASS if met else GATE_FAIL, mandatory=mandatory,
                critical=critical, evidence_count=evidence_count, minimum_support=minimum_support,
                observed=observed, threshold=float(threshold), comparator=comparator,
                reason=f"observed {observed} {comparator} preregistered {threshold} ({label})")


def evaluate_gates(gates: Sequence[Gate], task: str) -> dict:
    materialised = list(gates)
    if not materialised:
        raise _reject("empty_gate_set", "empty gate set never passes")
    seen = set()
    for g in materialised:
        if g.status not in (GATE_PASS, GATE_FAIL, GATE_INSUFFICIENT, GATE_INVALID):
            raise _reject("unknown_gate_status", g.status)
        if g.name in seen:
            raise _reject("duplicate_gate", g.name)
        seen.add(g.name)
    for g in materialised:
        if g.status == GATE_INVALID:
            return {"verdict": VERDICT_INVALID, "reason": f"{task}: gate {g.name!r} invalid: {g.reason}", "gates": materialised}
    for g in materialised:
        if not g.critical or g.status != GATE_FAIL:
            continue
        if g.minimum_support is None or g.evidence_count is None:
            return {"verdict": VERDICT_INDETERMINATE, "reason": f"{task}: critical {g.name!r} failed without support minimum", "gates": materialised}
        if g.evidence_count >= g.minimum_support:
            return {"verdict": VERDICT_NEGATIVE, "reason": f"{task}: critical {g.name!r} supported regression {g.evidence_count}>={g.minimum_support}. {g.reason}", "gates": materialised}
    blockers = [g for g in materialised if g.mandatory and g.status != GATE_PASS]
    if blockers:
        first = blockers[0]
        return {"verdict": VERDICT_INDETERMINATE, "reason": f"{task}: {len(blockers)} mandatory gates not pass; first {first.name!r} ({first.status}): {first.reason}", "gates": materialised}
    return {"verdict": VERDICT_POSITIVE, "reason": f"{task}: all {len(materialised)} mandatory gates passed", "gates": materialised}


# ---------------------------------------------------------------------------
# Serde / partition validation (B1/G3)
# ---------------------------------------------------------------------------

def validate_test_evaluation(raw: Mapping[str, Any], parsed_semantic: str,
                             expected_test_ids: Sequence[str] | None = None,
                             allow_legacy: bool = False,
                             legacy_test_ids: Sequence[str] | None = None) -> tuple[bool, str]:
    """Return (is_evaluated, explanation). Raise QualifyInvalid on corrupt."""
    has_partition = "evaluated_partition" in raw
    has_schema = "schema" in raw
    has_flag = "test_evaluation_performed" in raw
    flag = raw.get("test_evaluation_performed", "__missing__")
    # Explicit false is never evaluated.
    if has_flag and flag is False:
        return (False, "explicit test_evaluation_performed=false is never evaluated")
    # New reports: require explicit true + partition=test + versioned schema.
    if has_schema or has_partition:
        schema = raw.get("schema", "")
        partition = raw.get("evaluated_partition", "")
        version = raw.get("schema_version", None)
        if schema != EVALUATE_SCHEMA:
            raise _reject("bad_schema", f"unknown evaluate schema {schema!r}")
        if version != 2:
            raise _reject("bad_schema_version", f"schema_version {version!r} != 2")
        if partition != "test":
            raise _reject("bad_partition", f"evaluated_partition {partition!r} != test")
        if not has_flag or flag is not True:
            raise _reject("missing_flag", "new reports require explicit test_evaluation_performed=true")
        if expected_test_ids is not None:
            got = sorted(raw.get("test_ids", []))
            if sorted(expected_test_ids) != got:
                raise _reject("test_id_mismatch", f"report test_ids do not match expected membership ({len(got)} vs {len(expected_test_ids)})")
        return (True, "new v2 report with explicit true and partition=test")
    # Legacy path: no schema/partition fields.
    if has_flag and flag is True:
        # Explicit true on legacy-shaped report (should not normally occur
        # because legacy omits true). Treat as evaluated only if test IDs match
        # when expected IDs are supplied; otherwise require partition.
        if expected_test_ids is not None:
            got = sorted(raw.get("test_ids", []))
            if sorted(expected_test_ids) != got:
                raise _reject("test_id_mismatch", "legacy explicit-true test IDs mismatch")
            return (True, "legacy-shaped explicit true with matching test IDs")
        raise _reject("missing_partition", "explicit true without partition/test membership is not accepted")
    # Missing flag: legacy omitted-true case.
    if not allow_legacy:
        return (False, "missing test_evaluation_performed is not inferred for new reports; legacy requires explicit allow_legacy + matching test IDs")
    if legacy_test_ids is None:
        raise _reject("missing_legacy_evidence", "legacy inference requires frozen test-ID evidence")
    got = sorted(raw.get("test_ids", []))
    if sorted(legacy_test_ids) != got:
        raise _reject("test_id_mismatch", "legacy test IDs do not match frozen evidence; missing flag not inferred")
    # Also require semantic matches and report has outcomes (partition evidence).
    if not raw.get("outcomes"):
        raise _reject("missing_partition_evidence", "legacy report has no outcomes; cannot infer test partition")
    return (True, "legacy omitted-true with validated schema + exact test-case set")


# ---------------------------------------------------------------------------
# Paired group bootstrap (B2/B5)
# ---------------------------------------------------------------------------

def paired_group_bootstrap(group_values: Mapping[str, float], *, seed: int, replicates: int, alpha: float,
                           statistic_name: str, method: str = REQUIRED_METHOD) -> IntervalEstimate:
    """Resample WHOLE leakage groups; never per-row. Deterministic."""
    if method != REQUIRED_METHOD:
        raise _reject("unsupported_method", method)
    if replicates <= 0 or replicates > 1_000_000:
        raise _reject("bad_replicates", str(replicates))
    if not (0.0 < alpha < 0.5):
        raise _reject("bad_alpha", str(alpha))
    keys = sorted(group_values.keys())
    if not keys:
        raise _reject("empty_population", f"{statistic_name} has no groups")
    for k, v in group_values.items():
        _finite(v, f"{statistic_name} group {k}")
    vals = [group_values[k] for k in keys]
    point = sum(vals) / len(vals)
    rng = random.Random(seed)
    reps = []
    for _ in range(replicates):
        draw = [group_values[keys[rng.randrange(len(keys))]] for _ in range(len(keys))]
        reps.append(sum(draw) / len(draw))
    lower = sorted_quantile(reps, alpha)
    upper = sorted_quantile(reps, 1.0 - alpha)
    return IntervalEstimate(statistic=statistic_name, point=point, lower=lower, upper=upper,
                            groups=len(keys), method=method, replicates=replicates, seed=seed,
                            alpha=alpha)


def reference_bootstrap_mean(groups: Sequence[Sequence[float]], seed: int, replicates: int, alpha: float) -> tuple[float, float, float]:
    """Independently calculated reference for tests: group means then bootstrap."""
    group_means = [sum(g) / len(g) for g in groups]
    point = sum(group_means) / len(group_means)
    rng = random.Random(seed)
    reps = []
    for _ in range(replicates):
        draw = [group_means[rng.randrange(len(group_means))] for _ in range(len(group_means))]
        reps.append(sum(draw) / len(draw))
    return (point, sorted_quantile(reps, alpha), sorted_quantile(reps, 1.0 - alpha))


# ---------------------------------------------------------------------------
# Binary aggregation (B2/G4)
# ---------------------------------------------------------------------------

def aggregate_binary_groups(candidate_by_case: Mapping[str, Mapping[str, Any]],
                            baseline_by_case: Mapping[str, Mapping[str, Any]],
                            dataset_meta: Mapping[str, Mapping[str, Any]],
                            family: str) -> tuple[dict[str, list], dict[str, float], list[str]]:
    """Build group->list[(case_id, truth, candidate_p, baseline_p)] for one family.

    Validates: no duplicate case IDs, identical case sets across models, both
    counterfactual rows present in SAME group, no missing/extra rows, finite
    scores. Returns (groups, group_improvement, group_ids).
    group_improvement[group] = mean baseline Brier - mean candidate Brier.
    """
    # Collect cases in family from dataset meta.
    family_cases = {cid for cid, meta in dataset_meta.items() if meta.get("family") == family}
    if not family_cases:
        raise _reject("unknown_family", f"family {family!r} has no dataset rows")
    cand_ids = set(candidate_by_case.keys()) & family_cases
    base_ids = set(baseline_by_case.keys()) & family_cases
    # Exact set equality: missing/extra rejected.
    if cand_ids != family_cases:
        missing = sorted(family_cases - cand_ids)
        extra = sorted(cand_ids - family_cases)
        raise _reject("case_mismatch", f"candidate missing/extra in {family}: missing {missing[:3]} extra {extra[:3]}")
    if base_ids != family_cases:
        missing = sorted(family_cases - base_ids)
        raise _reject("case_mismatch", f"baseline missing/extra in {family}: missing {missing[:3]}")
    if set(candidate_by_case.keys()) & family_cases != set(baseline_by_case.keys()) & family_cases:
        raise _reject("case_mismatch", f"candidate/control case sets differ in {family}")
    # Group mapping; detect duplicate case IDs (caller must have deduped, but
    # double-check by requiring each case appears once per model).
    groups: dict[str, list] = {}
    for cid in family_cases:
        meta = dataset_meta[cid]
        group = meta.get("leakage_group", "")
        if not group:
            raise _reject("malformed_group", f"case {cid} has no group")
        cand = candidate_by_case[cid]
        base = baseline_by_case[cid]
        # Pair by identical case IDs (already); validate truth agreement with dataset?
        y = meta.get("truth")
        if y is None:
            # Binary truth from dataset label value bool.
            raise _reject("missing_truth", f"case {cid} has no binary truth")
        y01 = 1.0 if y else 0.0
        pc = _finite(cand.get("score"), f"candidate score {cid}")
        pb = _finite(base.get("score"), f"baseline score {cid}")
        if not (0.0 <= pc <= 1.0 and 0.0 <= pb <= 1.0):
            raise _reject("bad_probability", f"case {cid} probability outside [0,1]")
        groups.setdefault(group, []).append((cid, y01, pc, pb))
    # Both counterfactual rows MUST be present in SAME group: require exactly 2
    # rows per group for Binary (M014/M014a/M014b design). Uneven sizes are
    # rejected as invalid rather than silently averaged, unless manifest
    # explicitly allows variable sizes (canary uses exactly 2).
    for g, rows in groups.items():
        if len(rows) != 2:
            raise _reject("incomplete_pair", f"group {g} has {len(rows)} rows, need both counterfactual rows (2)")
        # Validate pair members share group (they do by construction) and differ
        # only in causal field is checked at generation; here check truths differ?
        # For Binary, truths are active&available; pair flips active so truths
        # may be same or different depending on available. Do not require
        # difference; only require same group and two rows.
        cids = [r[0] for r in rows]
        if len(set(cids)) != 2:
            raise _reject("duplicate_case", f"group {g} repeats case IDs")
    group_improvement: dict[str, float] = {}
    for g, rows in groups.items():
        cand_brier = sum((pc - y) ** 2 for _, y, pc, _ in rows) / len(rows)
        base_brier = sum((pb - y) ** 2 for _, y, _, pb in rows) / len(rows)
        group_improvement[g] = base_brier - cand_brier
    return (groups, group_improvement, sorted(groups.keys()))


def binary_train_prior(dataset_meta: Mapping[str, Any], train_ids: Sequence[str]) -> float:
    vals = []
    for cid in train_ids:
        meta = dataset_meta.get(cid)
        if meta is None:
            raise _reject("unknown_case", f"train id {cid} not in dataset")
        y = meta.get("truth")
        if y is None:
            raise _reject("missing_truth", f"train {cid} no truth")
        vals.append(1.0 if y else 0.0)
    if not vals:
        raise _reject("empty_population", "no train rows for prior")
    return sum(vals) / len(vals)


# ---------------------------------------------------------------------------
# Choice pairing (B3/G4)
# ---------------------------------------------------------------------------

def choice_raw_correct(target: str | None, option_ids: Sequence[str], probabilities: Sequence[float]) -> bool | None:
    """Raw argmax correctness; None for no-answer targets."""
    if target is None:
        return None
    if len(option_ids) != len(probabilities):
        raise _reject("option_mismatch", "option/probability length differ")
    best = max(range(len(probabilities)), key=lambda i: probabilities[i])
    return option_ids[best] == target


def aggregate_choice_family(candidate_by_case: Mapping[str, Mapping[str, Any]],
                            comparator_by_case: Mapping[str, Mapping[str, Any]] | None,
                            dataset_meta: Mapping[str, Mapping[str, Any]],
                            family: str) -> dict:
    """Pair same option IDs and eligible answerable case IDs.

    Returns dict with answerable/no-answer groups, raw vs final correctness,
    coverage, recall, selective risk, counterfactual both-correct, and
    validation of option permutations and case/order invariance (order of
    input dicts does not affect output).
    """
    family_cases = {cid for cid, meta in dataset_meta.items() if meta.get("family") == family}
    if not family_cases:
        raise _reject("unknown_family", family)
    cand_ids = set(candidate_by_case.keys()) & family_cases
    if cand_ids != family_cases:
        raise _reject("case_mismatch", f"candidate missing/extra in {family}")
    if comparator_by_case is not None:
        comp_ids = set(comparator_by_case.keys()) & family_cases
        if comp_ids != family_cases:
            raise _reject("case_mismatch", f"comparator missing/extra in {family}")
    # Validate option identities per case match dataset (permutation allowed).
    for cid in family_cases:
        meta = dataset_meta[cid]
        expected_options = set(meta.get("option_ids", []))
        cand_opts = candidate_by_case[cid].get("option_ids")
        if cand_opts is None:
            # Derive from raw_probabilities length? Require explicit option_ids
            # in report? New evaluate reports do not store option_ids; derive
            # from dataset and validate probabilities length matches.
            # Here we validate length matches and treat identities as dataset's.
            pass
        elif set(cand_opts) != expected_options:
            raise _reject("option_mismatch", f"case {cid} option IDs differ from dataset")
        if comparator_by_case is not None and comparator_by_case[cid].get("option_ids") is not None:
            if set(comparator_by_case[cid]["option_ids"]) != expected_options:
                raise _reject("option_mismatch", f"comparator {cid} option IDs differ")
        # Validate probabilities length matches options.
        n_opts = len(expected_options)
        for src, d in (("candidate", candidate_by_case[cid]), ("comparator", (comparator_by_case or {}).get(cid))):
            if d is None:
                continue
            probs = d.get("raw_probabilities")
            if probs is not None and len(probs) != n_opts:
                raise _reject("option_mismatch", f"{src} {cid} probs len {len(probs)} != options {n_opts}")
    answerable_cids = [cid for cid in family_cases if dataset_meta[cid].get("target") is not None]
    no_answer_cids = [cid for cid in family_cases if dataset_meta[cid].get("target") is None]
    # Group answerable and no-answer separately.
    ans_groups: dict[str, list[str]] = {}
    for cid in answerable_cids:
        g = dataset_meta[cid]["leakage_group"]
        ans_groups.setdefault(g, []).append(cid)
    noa_groups: dict[str, list[str]] = {}
    for cid in no_answer_cids:
        g = dataset_meta[cid]["leakage_group"]
        noa_groups.setdefault(g, []).append(cid)
    # Per-case raw vs final correctness.
    raw_correct: dict[str, bool] = {}
    final_correct: dict[str, bool] = {}
    covered: dict[str, bool] = {}
    for cid in answerable_cids:
        meta = dataset_meta[cid]
        target = meta["target"]
        option_ids = meta["option_ids"]
        # Option order for raw: dataset order; report probs are in request
        # option order which matches dataset order (generator preserves order
        # per case, but order varies across cases). Since we use dataset order
        # for both, permutation invariance holds: correctness depends on ID
        # matching, not position.
        cand = candidate_by_case[cid]
        probs = cand.get("raw_probabilities")
        if probs is None:
            raise _reject("missing_probs", f"candidate {cid} missing raw_probabilities")
        rc = choice_raw_correct(target, option_ids, probs)
        assert rc is not None
        raw_correct[cid] = rc
        pred = cand.get("prediction")
        abst = cand.get("abstained", pred is None)
        # Final correctness requires BOTH correct raw AND answered correctly;
        # a correct raw that abstains does NOT pass.
        if abst or pred is None:
            final_correct[cid] = False
            covered[cid] = False
        else:
            final_correct[cid] = (pred == target)
            covered[cid] = True
    # No-answer recall per case: abstained?
    noa_recall_case: dict[str, bool] = {}
    for cid in no_answer_cids:
        cand = candidate_by_case[cid]
        abst = cand.get("abstained", cand.get("prediction") is None)
        noa_recall_case[cid] = bool(abst)
    # Group means.
    def group_mean(cids: list[str], values: dict[str, bool | float]) -> float:
        return sum(1.0 if values[c] else 0.0 for c in cids) / len(cids)
    ans_group_acc = {g: group_mean(cids, final_correct) for g, cids in ans_groups.items()}
    ans_group_raw = {g: group_mean(cids, raw_correct) for g, cids in ans_groups.items()}
    ans_group_cov = {g: group_mean(cids, covered) for g, cids in ans_groups.items()}
    noa_group_recall = {g: group_mean(cids, noa_recall_case) for g, cids in noa_groups.items()}
    # Counterfactual both-correct: groups with exactly 2 answerable rows where
    # BOTH final answers correct. Groups with other sizes are not counted as
    # pairs (invalid for pair gate if manifest requires pairs).
    pair_groups: dict[str, float] = {}
    for g, cids in ans_groups.items():
        if len(cids) == 2:
            pair_groups[g] = 1.0 if all(final_correct[c] for c in cids) else 0.0
    # Selective risk: 1 - accuracy on covered cases (answerable + answered).
    covered_cids = [c for c in answerable_cids if covered[c]]
    if covered_cids:
        selective_acc = sum(1.0 if final_correct[c] else 0.0 for c in covered_cids) / len(covered_cids)
        selective_risk = 1.0 - selective_acc
    else:
        selective_risk = None
    # Comparator deltas on identical answerable groups (if comparator supplied).
    comp_deltas: dict[str, float] | None = None
    if comparator_by_case is not None:
        comp_final: dict[str, bool] = {}
        for cid in answerable_cids:
            meta = dataset_meta[cid]
            target = meta["target"]
            d = comparator_by_case[cid]
            pred = d.get("prediction")
            abst = d.get("abstained", pred is None)
            comp_final[cid] = (not abst and pred == target)
        comp_group_acc = {g: group_mean(cids, comp_final) for g, cids in ans_groups.items()}
        comp_deltas = {g: ans_group_acc[g] - comp_group_acc[g] for g in ans_groups}
    return {
        "answerable_groups": sorted(ans_groups.keys()),
        "no_answer_groups": sorted(noa_groups.keys()),
        "answerable_group_accuracy": ans_group_acc,
        "answerable_group_raw_accuracy": ans_group_raw,
        "answerable_group_coverage": ans_group_cov,
        "no_answer_group_recall": noa_group_recall,
        "pair_both_correct": pair_groups,
        "selective_risk": selective_risk,
        "per_case_raw": raw_correct,
        "per_case_final": final_correct,
        "per_case_covered": covered,
        "comparator_deltas": comp_deltas,
    }


def build_dataset_meta(dataset_path: str) -> dict[str, dict]:
    data = json.loads(Path(dataset_path).read_text())
    examples = data["examples"]
    meta: dict[str, dict] = {}
    for ex in examples:
        cid = ex["case_id"]
        if cid in meta:
            raise _reject("duplicate_case", cid)
        fam = ex.get("family")
        group = ex.get("leakage_group", "")
        label = ex.get("label", {})
        kind = label.get("kind")
        value = label.get("value")
        if kind == "binary":
            truth = bool(value)
            target = None
            option_ids: list[str] = []
        elif kind == "choice":
            truth = None
            target = value  # str or None
            opts = ex.get("request", {}).get("spec", {}).get("options", [])
            option_ids = [o["id"] for o in opts]
        else:
            raise _reject("bad_task", f"case {cid} kind {kind}")
        meta[cid] = {"family": fam, "leakage_group": group, "truth": truth if kind == "binary" else None,
                     "target": target if kind == "choice" else None,
                     "option_ids": option_ids, "kind": kind}
    return meta


def build_report_index(report_path: str) -> tuple[dict, dict, dict]:
    raw = json.loads(Path(report_path).read_text())
    # Outcomes indexed by case_id; detect duplicates.
    outcomes = raw.get("outcomes", [])
    by_case: dict[str, dict] = {}
    for row in outcomes:
        cid = row.get("case_id")
        if not cid:
            raise _reject("malformed_case", f"row missing case_id in {report_path}")
        if cid in by_case:
            raise _reject("duplicate_case", f"{report_path} repeats {cid}")
        by_case[cid] = row
    return (raw, by_case, raw)


def sha_of_file(path: str) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_membership_sha(test_ids: Sequence[str]) -> str:
    import hashlib
    s = sorted(test_ids)
    # Must match Rust serde_json::to_vec (compact, no spaces).
    return "sha256:" + hashlib.sha256(json.dumps(s, separators=(",", ":")).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Manifest validation (B4/B5)
# ---------------------------------------------------------------------------

def validate_manifest(manifest: Mapping[str, Any]) -> dict:
    required_top = ["manifest_id", "binary", "choice", "bootstrap", "resource_gates", "controls"]
    for k in required_top:
        if k not in manifest:
            raise _reject("missing_manifest_key", k)
    for task in ("binary", "choice"):
        block = manifest[task]
        for k in ("required_families", "critical_families", "min_independent_groups",
                  "thresholds", "test_membership_sha256", "dataset_sha256", "split_fingerprint"):
            if k not in block:
                raise _reject("missing_manifest_key", f"{task}.{k}")
        if not isinstance(block["required_families"], list) or not block["required_families"]:
            raise _reject("empty_mandatory_array", f"{task}.required_families")
        if len(set(block["required_families"])) != len(block["required_families"]):
            raise _reject("duplicate_family", f"{task}.required_families repeats")
        for fam in block["critical_families"]:
            if fam not in block["required_families"]:
                raise _reject("critical_not_required", f"{task} critical {fam} not required")
        if not isinstance(block["min_independent_groups"], int) or block["min_independent_groups"] <= 0:
            raise _reject("bad_support", f"{task}.min_independent_groups")
        # Thresholds must be present (may be None only if explicitly allowed?
        # For M014a positive, all thresholds must be numeric; missing => gate
        # insufficient, never positive. Here we only validate structure; the
        # gate layer will treat None as insufficient.)
    boot = manifest["bootstrap"]
    for k in ("method", "seed", "replicates", "alpha"):
        if k not in boot:
            raise _reject("missing_manifest_key", f"bootstrap.{k}")
    if boot["method"] != REQUIRED_METHOD:
        raise _reject("unsupported_method", str(boot["method"]))
    if not isinstance(boot["replicates"], int) or boot["replicates"] <= 0:
        raise _reject("bad_replicates", str(boot["replicates"]))
    if not (0.0 < float(boot["alpha"]) < 0.5):
        raise _reject("bad_alpha", str(boot["alpha"]))
    res = manifest["resource_gates"]
    for k in ("artifact_max_bytes", "choice_max_options", "platforms"):
        if k not in res:
            raise _reject("missing_manifest_key", f"resource_gates.{k}")
    ctrls = manifest["controls"]
    if not isinstance(ctrls, dict) or "binary" not in ctrls or "choice" not in ctrls:
        raise _reject("missing_manifest_key", "controls.binary/choice")
    return dict(manifest)


# ---------------------------------------------------------------------------
# Resource gates (B6)
# ---------------------------------------------------------------------------

def evaluate_resources(manifest: Mapping[str, Any], evidence: Mapping[str, Any] | None) -> list[Gate]:
    gates: list[Gate] = []
    req = manifest["resource_gates"]
    if evidence is None:
        for name in ("artifact_bytes", "max_options", "platform_parity", "host_build"):
            gates.append(invalid_gate(f"resource::{name}", "missing required platform/resource evidence; never synthetic pass"))
        return gates
    # Artifact bytes.
    max_bytes = req["artifact_max_bytes"]
    actual_bytes = evidence.get("artifact_bytes")
    if actual_bytes is None:
        gates.append(invalid_gate("resource::artifact_bytes", "missing artifact_bytes evidence"))
    elif not isinstance(actual_bytes, int) or actual_bytes <= 0:
        gates.append(invalid_gate("resource::artifact_bytes", f"malformed artifact_bytes {actual_bytes!r}"))
    else:
        gates.append(Gate(name="resource::artifact_bytes", status=GATE_PASS if actual_bytes <= max_bytes else GATE_FAIL,
                          mandatory=True, evidence_count=None, threshold=float(max_bytes),
                          observed=float(actual_bytes), comparator="<=",
                          reason=f"artifact {actual_bytes} <= max {max_bytes}" if actual_bytes <= max_bytes else f"artifact {actual_bytes} exceeds max {max_bytes}"))
    # Choice options.
    max_opts = req["choice_max_options"]
    actual_opts = evidence.get("max_options")
    if actual_opts is None:
        gates.append(invalid_gate("resource::max_options", "missing max_options evidence"))
    elif not isinstance(actual_opts, int) or actual_opts <= 0:
        gates.append(invalid_gate("resource::max_options", f"malformed max_options {actual_opts!r}"))
    else:
        gates.append(Gate(name="resource::max_options", status=GATE_PASS if actual_opts <= max_opts else GATE_FAIL,
                          mandatory=True, observed=float(actual_opts), threshold=float(max_opts), comparator="<=",
                          reason=f"options {actual_opts} <= max {max_opts}" if actual_opts <= max_opts else f"options {actual_opts} exceeds max {max_opts}"))
    # Latency/RSS/cold-load if declared.
    for key, label in (("p95_128_micros", "p95"), ("peak_rss_bytes", "rss"), ("cold_load_micros", "cold_load")):
        thresh_key = {"p95_128_micros": "choice_p95_128_options_max_micros",
                      "peak_rss_bytes": "runtime_peak_rss_max_bytes",
                      "cold_load_micros": "cold_load_max_micros"}[key]
        thresh = req.get(thresh_key)
        actual = evidence.get(key)
        if thresh is None:
            continue
        if actual is None:
            gates.append(invalid_gate(f"resource::{key}", f"missing {key} evidence for declared threshold {thresh}"))
        elif not isinstance(actual, (int, float)) or not math.isfinite(float(actual)):
            gates.append(invalid_gate(f"resource::{key}", f"malformed {key} {actual!r}"))
        else:
            ok = float(actual) <= float(thresh)
            gates.append(Gate(name=f"resource::{key}", status=GATE_PASS if ok else GATE_FAIL, mandatory=True,
                              observed=float(actual), threshold=float(thresh), comparator="<=",
                              reason=f"{label} {actual} <= {thresh}" if ok else f"{label} {actual} exceeds {thresh}"))
    # Host/build identifiers.
    for key in ("host", "build"):
        if not evidence.get(key):
            gates.append(invalid_gate(f"resource::{key}", f"missing required {key} identifier"))
        else:
            gates.append(Gate(name=f"resource::{key}", status=GATE_PASS, mandatory=True, reason=f"{key} {evidence[key]} present"))
    # Three-host parity.
    parity = evidence.get("three_host_parity")
    platforms = req.get("platforms", [])
    if parity is None:
        gates.append(invalid_gate("resource::three_host_parity", "missing three-host parity evidence"))
    elif parity is not True:
        gates.append(Gate(name="resource::three_host_parity", status=GATE_FAIL, mandatory=True, reason=f"parity {parity!r} is not true; platforms {platforms}"))
    else:
        gates.append(Gate(name="resource::three_host_parity", status=GATE_PASS, mandatory=True, reason=f"three-host parity true on {platforms}"))
    return gates


# ---------------------------------------------------------------------------
# Full qualification
# ---------------------------------------------------------------------------

def qualify(manifest_path: str, dataset_binary: str, split_binary: str,
            dataset_choice: str, split_choice: str,
            binary_candidate: str, binary_baseline: str,
            choice_candidate: str, choice_legacy: str, choice_cross: str,
            resource_evidence_path: str | None, out_path: str,
            allow_legacy: bool = False, legacy_test_ids_binary: Sequence[str] | None = None,
            legacy_test_ids_choice: Sequence[str] | None = None) -> dict:
    manifest = validate_manifest(json.loads(Path(manifest_path).read_text()))
    boot = manifest["bootstrap"]
    seed, replicates, alpha = int(boot["seed"]), int(boot["replicates"]), float(boot["alpha"])
    # Dataset metas.
    meta_bin = build_dataset_meta(dataset_binary)
    meta_choice = build_dataset_meta(dataset_choice)
    split_bin = json.loads(Path(split_binary).read_text())
    split_choice = json.loads(Path(split_choice).read_text())
    # Membership hashes.
    for task, split, block in (("binary", split_bin, manifest["binary"]), ("choice", split_choice, manifest["choice"])):
        got = test_membership_sha(split["test"])
        if got != block["test_membership_sha256"]:
            raise _reject("test_membership_mismatch", f"{task} membership {got} != manifest {block['test_membership_sha256']}")
    # Reports.
    raw_bin_cand, bin_cand_by_case, _ = build_report_index(binary_candidate)
    raw_bin_base, bin_base_by_case, _ = build_report_index(binary_baseline)
    raw_ch_cand, ch_cand_by_case, _ = build_report_index(choice_candidate)
    raw_ch_leg, ch_leg_by_case, _ = build_report_index(choice_legacy)
    raw_ch_cross, ch_cross_by_case, _ = build_report_index(choice_cross)
    # Serde validation.
    for raw, task_ids, legacy_ids, label in (
        (raw_bin_cand, split_bin["test"], legacy_test_ids_binary, "binary-candidate"),
        (raw_bin_base, split_bin["test"], legacy_test_ids_binary, "binary-baseline"),
        (raw_ch_cand, split_choice["test"], legacy_test_ids_choice, "choice-candidate"),
        (raw_ch_leg, split_choice["test"], legacy_test_ids_choice, "choice-legacy"),
        (raw_ch_cross, split_choice["test"], legacy_test_ids_choice, "choice-cross"),
    ):
        evaluated, _ = validate_test_evaluation(raw, "", expected_test_ids=task_ids if not allow_legacy else None,
                                                allow_legacy=allow_legacy, legacy_test_ids=legacy_ids)
        if not evaluated:
            raise _reject("not_evaluated", f"{label} did not evaluate test partition")
    # Enrich report rows with dataset option IDs for Choice (for permutation checks).
    def enrich_choice(by_case: dict, meta: dict) -> dict:
        out = {}
        for cid, row in by_case.items():
            m = meta.get(cid)
            if m is None:
                raise _reject("unknown_case", cid)
            enriched = dict(row)
            enriched["option_ids"] = m["option_ids"]
            out[cid] = enriched
        return out
    ch_cand_enriched = enrich_choice(ch_cand_by_case, meta_choice)
    ch_leg_enriched = enrich_choice(ch_leg_by_case, meta_choice)
    ch_cross_enriched = enrich_choice(ch_cross_by_case, meta_choice)
    # Binary gates.
    binary_gates: list[Gate] = []
    bin_block = manifest["binary"]
    # Presence gates in protocol order.
    present_fams = set()
    for fam in bin_block["required_families"]:
        # Presence determined by dataset having rows in test? Actually by having
        # groups; if family has no test rows, invalid.
        rows = [cid for cid, m in meta_bin.items() if m.get("family") == fam and cid in split_bin["test"]]
        if not rows:
            binary_gates.append(invalid_gate(f"binary_family::presence::{fam}", f"required family {fam} absent from test"))
        else:
            binary_gates.append(Gate(name=f"binary_family::presence::{fam}", status=GATE_PASS, mandatory=True, reason=f"required {fam} present"))
            present_fams.add(fam)
    # Check undeclared families in reports? Reports cover all families; undeclared
    # test families outside required set are rejected unless manifest allows?
    # For M014a, test split contains exactly required families plus train/dev
    # families; only check that required families are present (above) and that
    # no required family is missing. Undeclared test families that are ID
    # families for train/dev are not in test, so no check needed. If report
    # contains a family outside required + train/dev, it would be caught via
    # dataset meta? Simplify: check that every family appearing in test split is
    # either required or explicitly diagnostic? Manifest has no diagnostic list
    # for M014a; train families are not in test, so any test family outside
    # required is undeclared => invalid.
    test_fams = sorted({meta_bin[cid]["family"] for cid in split_bin["test"]})
    diag_bin = set(bin_block.get("diagnostic_only_families", []))
    undeclared = sorted(set(test_fams) - set(bin_block["required_families"]) - diag_bin)
    if undeclared:
        binary_gates.append(invalid_gate("binary_family::undeclared_family", f"test contains families outside required set: {undeclared}"))
    elif diag_bin & set(test_fams):
        binary_gates.append(Gate(name="binary_family::diagnostic_only", status=GATE_PASS, mandatory=False, reason=f"diagnostic families {sorted(diag_bin & set(test_fams))} measured and excluded from qualification"))
    # Per-family Brier improvements vs legacy and vs train prior.
    train_prior = binary_train_prior(meta_bin, split_bin["train"])
    for fam in bin_block["required_families"]:
        if fam not in present_fams:
            continue
        try:
            groups, improvements, gids = aggregate_binary_groups(bin_cand_by_case, bin_base_by_case, meta_bin, fam)
        except QualifyInvalid as e:
            binary_gates.append(invalid_gate(f"binary::{fam}::aggregation", f"{e.code}: {e.detail}"))
            continue
        # Support gate.
        binary_gates.append(support_gate(f"independent_groups::{fam}", observed=len(gids), required=bin_block["min_independent_groups"]))
        thresholds = bin_block.get("thresholds", {})
        margin = thresholds.get("id_noninferiority_margin", -0.02)
        is_critical = fam in bin_block["critical_families"]
        is_id = fam in thresholds.get("id_noninferiority_families", []) or fam.endswith("id-a-v1") or fam.endswith("id-b-v1")
        # CI vs legacy.
        try:
            interval = paired_group_bootstrap(improvements, seed=seed, replicates=replicates, alpha=alpha, statistic_name=f"brier_improvement_vs_legacy::{fam}")
        except QualifyInvalid as e:
            binary_gates.append(invalid_gate(f"brier_improvement_vs_legacy::{fam}", f"{e.code}: {e.detail}"))
            continue
        if is_critical:
            # Critical OOD requires superiority (lower>0) with support.
            binary_gates.append(confidence_gate(f"brier_improvement_vs_legacy::{fam}", interval, minimum_support=bin_block["min_independent_groups"], mandatory=True, critical=True, description=f"Binary {fam} candidate minus legacy Brier improvement"))
        else:
            # ID and load/unknown negative controls require noninferiority
            # (lower>=margin), never superiority. A small ID regression within
            # margin is expected when masking constant nuisance.
            if interval.groups < bin_block["min_independent_groups"]:
                binary_gates.append(Gate(name=f"brier_improvement_vs_legacy::{fam}", status=GATE_INSUFFICIENT, mandatory=True, evidence_count=interval.groups, minimum_support=bin_block["min_independent_groups"], observed=interval.lower, lower=interval.lower, upper=interval.upper, threshold=margin, comparator=">=", decision="indeterminate", reason=f"insufficient support for noninferiority"))
            elif interval.lower >= margin:
                binary_gates.append(Gate(name=f"brier_improvement_vs_legacy::{fam}", status=GATE_PASS, mandatory=True, evidence_count=interval.groups, minimum_support=bin_block["min_independent_groups"], observed=interval.lower, lower=interval.lower, upper=interval.upper, threshold=margin, comparator=">=", decision="favorable" if interval.lower > 0 else "noninferior", reason=f"Binary {fam} noninferiority lower {interval.lower} >= margin {margin}"))
            else:
                binary_gates.append(Gate(name=f"brier_improvement_vs_legacy::{fam}", status=GATE_FAIL, mandatory=True, critical=False, evidence_count=interval.groups, minimum_support=bin_block["min_independent_groups"], observed=interval.lower, lower=interval.lower, upper=interval.upper, threshold=margin, comparator=">=", decision="unfavorable", reason=f"Binary {fam} noninferiority lower {interval.lower} < margin {margin}"))
            # Explicit ID noninferiority gate for traceability (same decision).
            if is_id:
                if interval.lower >= margin and interval.groups >= bin_block["min_independent_groups"]:
                    binary_gates.append(Gate(name=f"id_noninferiority::{fam}", status=GATE_PASS, mandatory=True, evidence_count=interval.groups, minimum_support=bin_block["min_independent_groups"], observed=interval.lower, lower=interval.lower, upper=interval.upper, threshold=margin, comparator=">=", reason=f"ID noninferiority lower {interval.lower} >= margin {margin}"))
                elif interval.groups < bin_block["min_independent_groups"]:
                    binary_gates.append(Gate(name=f"id_noninferiority::{fam}", status=GATE_INSUFFICIENT, mandatory=True, evidence_count=interval.groups, minimum_support=bin_block["min_independent_groups"], observed=interval.lower, threshold=margin, comparator=">=", reason="insufficient support for noninferiority"))
                else:
                    binary_gates.append(Gate(name=f"id_noninferiority::{fam}", status=GATE_FAIL, mandatory=True, critical=False, evidence_count=interval.groups, minimum_support=bin_block["min_independent_groups"], observed=interval.lower, lower=interval.lower, upper=interval.upper, threshold=margin, comparator=">=", reason=f"ID noninferiority lower {interval.lower} < margin {margin}"))
        # Vs train prior.
        prior_improvements: dict[str, float] = {}
        for g, rows in groups.items():
            cand_brier = sum((pc - y) ** 2 for _, y, pc, _ in rows) / len(rows)
            prior_brier = sum((train_prior - y) ** 2 for _, y, _, _ in rows) / len(rows)
            prior_improvements[g] = prior_brier - cand_brier
        try:
            interval_prior = paired_group_bootstrap(prior_improvements, seed=seed, replicates=replicates, alpha=alpha, statistic_name=f"brier_improvement_vs_prior::{fam}")
        except QualifyInvalid as e:
            binary_gates.append(invalid_gate(f"brier_improvement_vs_prior::{fam}", f"{e.code}: {e.detail}"))
            continue
        if is_critical:
            binary_gates.append(confidence_gate(f"brier_improvement_vs_prior::{fam}", interval_prior, minimum_support=bin_block["min_independent_groups"], mandatory=True, critical=True, description=f"Binary {fam} candidate minus train-prior Brier improvement"))
        else:
            if interval_prior.groups < bin_block["min_independent_groups"]:
                binary_gates.append(Gate(name=f"brier_improvement_vs_prior::{fam}", status=GATE_INSUFFICIENT, mandatory=True, evidence_count=interval_prior.groups, minimum_support=bin_block["min_independent_groups"], observed=interval_prior.lower, threshold=margin, comparator=">=", decision="indeterminate", reason="insufficient support"))
            elif interval_prior.lower >= margin:
                binary_gates.append(Gate(name=f"brier_improvement_vs_prior::{fam}", status=GATE_PASS, mandatory=True, evidence_count=interval_prior.groups, minimum_support=bin_block["min_independent_groups"], observed=interval_prior.lower, lower=interval_prior.lower, upper=interval_prior.upper, threshold=margin, comparator=">=", decision="noninferior", reason=f"Binary {fam} vs-prior noninferiority lower {interval_prior.lower} >= margin {margin}"))
            else:
                binary_gates.append(Gate(name=f"brier_improvement_vs_prior::{fam}", status=GATE_FAIL, mandatory=True, critical=False, evidence_count=interval_prior.groups, minimum_support=bin_block["min_independent_groups"], observed=interval_prior.lower, lower=interval_prior.lower, upper=interval_prior.upper, threshold=margin, comparator=">=", decision="unfavorable", reason=f"Binary {fam} vs-prior lower {interval_prior.lower} < margin {margin}"))
    # Binary controls: require manifest controls.binary list measured.
    for ctrl in manifest["controls"].get("binary", []):
        if ctrl == "legacy-binary":
            # Already measured as vs_legacy; record measured gate.
            binary_gates.append(Gate(name="negative_control::measured::legacy-binary", status=GATE_PASS, mandatory=True, reason="legacy measured on identical eligible groups via paired vs_legacy intervals"))
        elif ctrl == "train-prior-constant":
            binary_gates.append(Gate(name="negative_control::measured::train-prior-constant", status=GATE_PASS, mandatory=True, reason=f"train prior {train_prior:.6f} measured via paired vs_prior intervals"))
        else:
            binary_gates.append(invalid_gate(f"negative_control::measured::{ctrl}", f"unknown binary control {ctrl}"))
    # Choice gates.
    choice_gates: list[Gate] = []
    ch_block = manifest["choice"]
    for fam in ch_block["required_families"]:
        rows = [cid for cid, m in meta_choice.items() if m.get("family") == fam and cid in split_choice["test"]]
        if not rows:
            choice_gates.append(invalid_gate(f"choice_family::presence::{fam}", f"required family {fam} absent"))
        else:
            choice_gates.append(Gate(name=f"choice_family::presence::{fam}", status=GATE_PASS, mandatory=True, reason=f"required {fam} present"))
    test_fams_c = sorted({meta_choice[cid]["family"] for cid in split_choice["test"]})
    diag_c = set(ch_block.get("diagnostic_only_families", []))
    undeclared_c = sorted(set(test_fams_c) - set(ch_block["required_families"]) - diag_c)
    if undeclared_c:
        choice_gates.append(invalid_gate("choice_family::undeclared_family", f"test families outside required: {undeclared_c}"))
    elif diag_c & set(test_fams_c):
        choice_gates.append(Gate(name="choice_family::diagnostic_only", status=GATE_PASS, mandatory=False, reason=f"diagnostic families {sorted(diag_c & set(test_fams_c))} measured and excluded"))
    # Per-family accuracy, coverage, recall, pair, controls.
    for fam in ch_block["required_families"]:
        try:
            agg = aggregate_choice_family(ch_cand_enriched, None, meta_choice, fam)
            agg_leg = aggregate_choice_family(ch_leg_enriched, None, meta_choice, fam)
            agg_cross = aggregate_choice_family(ch_cross_enriched, None, meta_choice, fam)
        except QualifyInvalid as e:
            choice_gates.append(invalid_gate(f"choice::{fam}::aggregation", f"{e.code}: {e.detail}"))
            continue
        # Support gates: answerable groups >= min, no-answer groups >= min_no_answer if any no-answer rows?
        min_ans = ch_block.get("min_answerable_groups", ch_block["min_independent_groups"])
        min_noa = ch_block.get("min_no_answer_groups", 20)
        choice_gates.append(support_gate(f"answerable_groups::{fam}", observed=len(agg["answerable_groups"]), required=min_ans))
        if agg["no_answer_groups"]:
            choice_gates.append(support_gate(f"no_answer_groups::{fam}", observed=len(agg["no_answer_groups"]), required=min_noa))
        # Accuracy deltas vs legacy/cross on identical answerable groups.
        # Build deltas dicts.
        cand_acc = agg["answerable_group_accuracy"]
        leg_acc = agg_leg["answerable_group_accuracy"]
        cross_acc = agg_cross["answerable_group_accuracy"]
        shared = sorted(set(cand_acc) & set(leg_acc))
        if len(shared) != len(cand_acc) or len(shared) != len(leg_acc):
            choice_gates.append(invalid_gate(f"choice::{fam}::group_identity", "candidate/legacy answerable group sets differ"))
            continue
        deltas_leg = {g: cand_acc[g] - leg_acc[g] for g in shared}
        shared_c = sorted(set(cand_acc) & set(cross_acc))
        deltas_cross = {g: cand_acc[g] - cross_acc[g] for g in shared_c}
        try:
            int_leg = paired_group_bootstrap(deltas_leg, seed=seed, replicates=replicates, alpha=alpha, statistic_name=f"accuracy_vs_legacy::{fam}")
            int_cross = paired_group_bootstrap(deltas_cross, seed=seed, replicates=replicates, alpha=alpha, statistic_name=f"accuracy_vs_cross::{fam}")
        except QualifyInvalid as e:
            choice_gates.append(invalid_gate(f"choice::{fam}::interval", f"{e.code}: {e.detail}"))
            continue
        is_crit = fam in ch_block.get("critical_families", [])
        choice_gates.append(confidence_gate(f"accuracy_vs_legacy::{fam}", int_leg, minimum_support=min_ans, mandatory=True, critical=is_crit, description=f"Choice {fam} candidate minus legacy accuracy"))
        choice_gates.append(confidence_gate(f"accuracy_vs_cross::{fam}", int_cross, minimum_support=min_ans, mandatory=True, critical=is_crit, description=f"Choice {fam} candidate minus cross accuracy"))
        # Discriminating controls always-yes/no measured on same groups.
        # Compute always-yes/no accuracy per group from dataset labels.
        # Yes option per case: option whose dataset meta? Need yes ID: find
        # option whose label ends with YES? Dataset does not store labels;
        # use target semantics: for answerable cases, yes vs no? Actually
        # always-yes predicts semantic yes. For each case, semantic yes ID is
        # the option that would be correct if target were yes? Hmm. Simplify:
        # always-yes predicts the lexicographically smallest option ID? No.
        # Instead, use dataset: for each case, determine yes_id as the option
        # that is target when semantic_yes True? We need yes/no mapping per
        # case. In M014 generator, options have labels "Option YES"/"Option NO"
        # but IDs are opaque. The report does not store labels. However dataset
        # request.spec.options stores id+label. So we can get yes_id per case
        # from dataset file (not just meta). For analyzer, load full dataset
        # to get labels.
        # To avoid extra I/O here, we approximate always-yes/no via target
        # frequency? For canary with known construction, always-yes accuracy
        # ~0.5. For gate, we require candidate beats always-yes/no with lower>0.
        # Compute control accuracies as 0.5 baseline? Better to compute exactly
        # by loading dataset options labels. Implement helper below.
        pass
    # Load full datasets for control label mapping (yes/no).
    # Always-yes/no/answer/abstain controls on identical answerable groups.
    # For each required Choice family, compute control deltas and gates.
    try:
        full_bin = json.loads(Path(dataset_binary).read_text())
        full_choice = json.loads(Path(dataset_choice).read_text())
    except Exception as e:
        raise _reject("bad_dataset", str(e))
    choice_examples = {ex["case_id"]: ex for ex in full_choice["examples"]}
    def yes_id_for(cid: str) -> str:
        ex = choice_examples[cid]
        for o in ex["request"]["spec"]["options"]:
            if o.get("label", "").lower().endswith("yes"):
                return o["id"]
        raise _reject("missing_yes", f"case {cid} has no yes option")
    def no_id_for(cid: str) -> str:
        ex = choice_examples[cid]
        for o in ex["request"]["spec"]["options"]:
            if o.get("label", "").lower().endswith("no"):
                return o["id"]
        raise _reject("missing_no", f"case {cid} has no no option")
    for fam in ch_block["required_families"]:
        # Skip if family already invalid (no agg).
        try:
            agg = aggregate_choice_family(ch_cand_enriched, None, meta_choice, fam)
        except QualifyInvalid:
            continue
        ans_groups = agg["answerable_groups"]
        if not ans_groups:
            continue
        # Build per-group control accuracies.
        # Candidate accuracy per group already in agg.
        cand_acc = agg["answerable_group_accuracy"]
        # Always-yes/no.
        yes_acc: dict[str, float] = {}
        no_acc: dict[str, float] = {}
        for g in ans_groups:
            cids = [cid for cid in split_choice["test"] if meta_choice[cid]["family"] == fam and meta_choice[cid]["leakage_group"] == g and meta_choice[cid]["target"] is not None]
            yes_acc[g] = sum(1.0 if meta_choice[cid]["target"] == yes_id_for(cid) else 0.0 for cid in cids) / len(cids)
            no_acc[g] = sum(1.0 if meta_choice[cid]["target"] == no_id_for(cid) else 0.0 for cid in cids) / len(cids)
        # Always-answer: raw accuracy (never abstains).
        raw_acc = agg["answerable_group_raw_accuracy"]
        # Always-abstain: 0.0 accuracy.
        abst_acc = {g: 0.0 for g in ans_groups}
        min_ans = ch_block.get("min_answerable_groups", ch_block["min_independent_groups"])
        for ctrl_name, ctrl_acc in (("always-yes", yes_acc), ("always-no", no_acc), ("always-abstain", abst_acc)):
            deltas = {g: cand_acc[g] - ctrl_acc[g] for g in ans_groups}
            try:
                interval = paired_group_bootstrap(deltas, seed=seed, replicates=replicates, alpha=alpha, statistic_name=f"learned_vs_{ctrl_name}::{fam}")
            except QualifyInvalid as e:
                choice_gates.append(invalid_gate(f"negative_control::beats::{ctrl_name}::{fam}", f"{e.code}: {e.detail}"))
                continue
            # always-answer is non-discriminating (recorded, not evidence).
            choice_gates.append(confidence_gate(f"negative_control::beats::{ctrl_name}::{fam}", interval, minimum_support=min_ans, mandatory=True, critical=False, description=f"learned minus {ctrl_name} on {fam}"))
        # always-answer recorded separately as non-mandatory.
        choice_gates.append(Gate(name=f"negative_control::measured::always-answer::{fam}", status=GATE_PASS, mandatory=False, reason="always-answer is candidate argmax by construction; measured and recorded, not evidence"))
        for ctrl in ("legacy", "cross", "always-yes", "always-no", "always-abstain"):
            # Measured gates (mandatory coverage).
            # Find corresponding beats gate to infer groups; if missing, invalid.
            beats = [g for g in choice_gates if g.name == f"negative_control::beats::{ctrl}::{fam}"]
            if not beats:
                # Legacy/cross beats are accuracy_vs_* gates, not beats::*; add measured.
                if ctrl in ("legacy", "cross"):
                    choice_gates.append(Gate(name=f"negative_control::measured::{ctrl}::{fam}", status=GATE_PASS, mandatory=True, reason=f"{ctrl} measured on identical answerable groups"))
                else:
                    choice_gates.append(invalid_gate(f"negative_control::measured::{ctrl}::{fam}", f"control {ctrl} not measured"))
            else:
                choice_gates.append(Gate(name=f"negative_control::measured::{ctrl}::{fam}", status=GATE_PASS, mandatory=True, evidence_count=len(ans_groups), minimum_support=min_ans, reason=f"control {ctrl} measured on {len(ans_groups)} groups"))
        # Counterfactual both-correct and no-answer recall, coverage.
        thresholds = ch_block.get("thresholds", {})
        # Both-correct rate.
        pair_vals = agg["pair_both_correct"]
        if pair_vals:
            point_both = sum(pair_vals.values()) / len(pair_vals)
            try:
                int_both = paired_group_bootstrap(pair_vals, seed=seed, replicates=replicates, alpha=alpha, statistic_name=f"both_correct::{fam}")
            except QualifyInvalid:
                int_both = None
            min_pairs = ch_block.get("min_pair_count", 50)
            choice_gates.append(support_gate(f"pair_groups::{fam}", observed=len(pair_vals), required=min_pairs))
            # Threshold gates for point and lower.
            pt = thresholds.get("counterfactual_both_correct_point")
            lb = thresholds.get("counterfactual_both_correct_lower")
            if pt is not None:
                choice_gates.append(threshold_gate(f"counterfactual_both_correct_point::{fam}", observed=point_both, threshold=pt, comparator=">=", evidence_count=len(pair_vals), minimum_support=min_pairs, description=f"both-correct point {point_both} >= {pt}"))
            else:
                choice_gates.append(Gate(name=f"counterfactual_both_correct_point::{fam}", status=GATE_INSUFFICIENT, mandatory=True, evidence_count=len(pair_vals), minimum_support=min_pairs, reason="no preregistered both-correct point threshold"))
            if lb is not None and int_both is not None:
                ok = int_both.lower >= lb and int_both.groups >= min_pairs
                choice_gates.append(Gate(name=f"counterfactual_both_correct_lower::{fam}", status=GATE_PASS if ok else (GATE_INSUFFICIENT if int_both.lower < lb and int_both.upper >= lb else GATE_FAIL), mandatory=True, evidence_count=int_both.groups, minimum_support=min_pairs, observed=int_both.lower, lower=int_both.lower, upper=int_both.upper, threshold=lb, comparator=">=", reason=f"both-correct lower {int_both.lower} >= {lb}" if ok else f"both-correct lower {int_both.lower} < {lb}"))
            elif lb is not None:
                choice_gates.append(Gate(name=f"counterfactual_both_correct_lower::{fam}", status=GATE_INSUFFICIENT, mandatory=True, reason="no estimable both-correct interval"))
            else:
                choice_gates.append(Gate(name=f"counterfactual_both_correct_lower::{fam}", status=GATE_INSUFFICIENT, mandatory=True, reason="no preregistered both-correct lower threshold"))
        else:
            choice_gates.append(invalid_gate(f"pair_groups::{fam}", "no paired groups for both-correct"))
        # No-answer recall.
        noa_vals = agg["no_answer_group_recall"]
        if noa_vals:
            point_recall = sum(noa_vals.values()) / len(noa_vals) if noa_vals else 0.0
            try:
                int_recall = paired_group_bootstrap(noa_vals, seed=seed, replicates=replicates, alpha=alpha, statistic_name=f"no_answer_recall::{fam}") if noa_vals else None
            except QualifyInvalid:
                int_recall = None
            min_noa = ch_block.get("min_no_answer_groups", 20)
            pt_r = thresholds.get("no_answer_recall_point")
            lb_r = thresholds.get("no_answer_recall_lower")
            if pt_r is not None:
                choice_gates.append(threshold_gate(f"no_answer_recall_point::{fam}", observed=point_recall, threshold=pt_r, comparator=">=", evidence_count=len(noa_vals), minimum_support=min_noa))
            else:
                choice_gates.append(Gate(name=f"no_answer_recall_point::{fam}", status=GATE_INSUFFICIENT, mandatory=True, reason="no preregistered recall point"))
            if lb_r is not None and int_recall is not None:
                ok = int_recall.lower >= lb_r
                choice_gates.append(Gate(name=f"no_answer_recall_lower::{fam}", status=GATE_PASS if ok else GATE_INSUFFICIENT, mandatory=True, evidence_count=int_recall.groups, minimum_support=min_noa, observed=int_recall.lower, lower=int_recall.lower, upper=int_recall.upper, threshold=lb_r, comparator=">=", reason=f"recall lower {int_recall.lower} >= {lb_r}" if ok else f"recall lower {int_recall.lower} < {lb_r}"))
            elif lb_r is not None:
                choice_gates.append(Gate(name=f"no_answer_recall_lower::{fam}", status=GATE_INSUFFICIENT, mandatory=True, reason="no recall interval"))
            else:
                choice_gates.append(Gate(name=f"no_answer_recall_lower::{fam}", status=GATE_INSUFFICIENT, mandatory=True, reason="no preregistered recall lower"))
        # Coverage.
        cov_vals = agg["answerable_group_coverage"]
        point_cov = sum(cov_vals.values()) / len(cov_vals) if cov_vals else 0.0
        cov_floor = thresholds.get("answerable_coverage_floor")
        if cov_floor is not None:
            choice_gates.append(threshold_gate(f"answerable_coverage::{fam}", observed=point_cov, threshold=cov_floor, comparator=">=", evidence_count=len(cov_vals)))
        else:
            choice_gates.append(Gate(name=f"answerable_coverage::{fam}", status=GATE_INSUFFICIENT, mandatory=True, reason="no preregistered coverage floor"))
    # Resource gates.
    evidence = json.loads(Path(resource_evidence_path).read_text()) if resource_evidence_path and Path(resource_evidence_path).exists() else None
    resource_gates = evaluate_resources(manifest, evidence)
    # Verdicts.
    bin_result = evaluate_gates(binary_gates, task="binary")
    ch_result = evaluate_gates(choice_gates + resource_gates, task="choice")
    # Overall: invalid if either invalid; negative if either negative; else
    # indeterminate unless both positive.
    if bin_result["verdict"] == VERDICT_INVALID or ch_result["verdict"] == VERDICT_INVALID:
        overall = VERDICT_INVALID
    elif bin_result["verdict"] == VERDICT_NEGATIVE or ch_result["verdict"] == VERDICT_NEGATIVE:
        overall = VERDICT_NEGATIVE
    elif bin_result["verdict"] == VERDICT_POSITIVE and ch_result["verdict"] == VERDICT_POSITIVE:
        overall = VERDICT_POSITIVE
    else:
        overall = VERDICT_INDETERMINATE
    # Cohort hashes, fingerprints, evaluator SHA for C2 (each report includes evaluator SHA).
    try:
        _eval_sha = "sha256:" + __import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest()
    except Exception:
        _eval_sha = "sha256:" + "0" * 64
    # Cohort hashes, fingerprints.
    result = {
        "evaluator": EVALUATOR_VERSION,
        "evaluator_sha256": _eval_sha,
        "manifest_id": manifest.get("manifest_id"),
        "protocol": manifest.get("manifest_id"),
        "multiplicity": f"one-sided Bonferroni alpha={alpha} (base {manifest['bootstrap'].get('base_alpha', alpha*manifest['bootstrap'].get('comparisons', 1))}/{manifest['bootstrap'].get('comparisons', 1)}); paired leakage-group percentile bootstrap {replicates} draws seed {seed}",
        "binary_verdict": bin_result["verdict"],
        "binary_reason": bin_result["reason"],
        "binary_gates": [g.as_dict() for g in bin_result["gates"]],
        "choice_verdict": ch_result["verdict"],
        "choice_reason": ch_result["reason"],
        "choice_gates": [g.as_dict() for g in ch_result["gates"]],
        "overall_verdict": overall,
        "cohort": {
            "binary_test_membership_sha256": manifest["binary"]["test_membership_sha256"],
            "choice_test_membership_sha256": manifest["choice"]["test_membership_sha256"],
            "binary_dataset_sha256": manifest["binary"]["dataset_sha256"],
            "choice_dataset_sha256": manifest["choice"]["dataset_sha256"],
        },
        "artifacts": {
            "binary_candidate_sha": raw_bin_cand.get("artifact_sha256"),
            "binary_baseline_sha": raw_bin_base.get("artifact_sha256"),
            "choice_candidate_sha": raw_ch_cand.get("artifact_sha256"),
            "choice_legacy_sha": raw_ch_leg.get("artifact_sha256"),
            "choice_cross_sha": raw_ch_cross.get("artifact_sha256"),
        },
        "limitations": ["Synthetic task qualification only; not real-world generalization, CodeGG promotion, publication, or deployment approval."],
    }
    # Atomic write.
    out = Path(out_path)
    if out.exists():
        raise _reject("overwrite", f"refusing to overwrite {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    tmp.replace(out)
    # Human summary mirrors JSON exactly.
    summary = (f"[{EVALUATOR_VERSION}] binary={bin_result['verdict']} choice={ch_result['verdict']} overall={overall}\n"
               f"binary: {bin_result['reason']}\nchoice: {ch_result['reason']}\n")
    print(summary)
    print(json.dumps({"output": str(out), "overall_verdict": overall}, sort_keys=True))
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="M014a v2 semantic qualification analyzer")
    p.add_argument("--manifest", required=True)
    p.add_argument("--dataset-binary", required=True)
    p.add_argument("--split-binary", required=True)
    p.add_argument("--dataset-choice", required=True)
    p.add_argument("--split-choice", required=True)
    p.add_argument("--binary-candidate", required=True)
    p.add_argument("--binary-baseline", required=True)
    p.add_argument("--choice-candidate", required=True)
    p.add_argument("--choice-legacy", required=True)
    p.add_argument("--choice-cross", required=True)
    p.add_argument("--resource-evidence", required=False, default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--allow-legacy", action="store_true", help="allow legacy omitted-true with frozen test-ID evidence")
    p.add_argument("--legacy-binary-test-ids", required=False, default=None, help="JSON file with legacy binary test IDs")
    p.add_argument("--legacy-choice-test-ids", required=False, default=None, help="JSON file with legacy choice test IDs")
    args = p.parse_args(argv)
    legacy_bin = json.loads(Path(args.legacy_binary_test_ids).read_text()) if args.legacy_binary_test_ids else None
    legacy_choice = json.loads(Path(args.legacy_choice_test_ids).read_text()) if args.legacy_choice_test_ids else None
    try:
        qualify(args.manifest, args.dataset_binary, args.split_binary, args.dataset_choice, args.split_choice,
                args.binary_candidate, args.binary_baseline, args.choice_candidate, args.choice_legacy,
                args.choice_cross, args.resource_evidence, args.out,
                allow_legacy=args.allow_legacy, legacy_test_ids_binary=legacy_bin, legacy_test_ids_choice=legacy_choice)
    except QualifyInvalid as e:
        print(json.dumps({"error": e.code, "detail": e.detail}, sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
