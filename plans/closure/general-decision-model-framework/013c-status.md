# M013c closure — Qualification-gate hardening corrective

Status: **conditionally closed** — the four preregistered gate defects and one latent bootstrap defect are closed on the source branch and verified locally. Hosted CI and the main-targeted merge are outstanding, so the status is conditional. **No model is qualified or promoted.** The historical Binary `negative` and Choice `indeterminate` dispositions are unchanged.

Plan: `plans/implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md`
Planning baseline: `dbowm91/sdm@11ea106c9af3b1ec362a98e709b530cc0fa137d0` (`work/plans-sdm-m013b-quality-gates-diagnostics`; main remains `2bd0d5af16d143828dcbce77f411b8f3b675e7be`)
Implementation branch: `work/plans-sdm-m013c-qualification-gate-hardening`
Implementation commit: recorded in §8 below
Closure file: `plans/closure/general-decision-model-framework/013c-status.md`
Class: infrastructure / evidence-integrity corrective

## 1. What changed and what did not

M013c is additive. It changed no Rust source, no fixture, no split, no frozen protocol, no artifact, no report, no historical closure record and no M013a/M013b script.

```
 M .github/workflows/ci.yml
 M README.md
 M plans/README.md
 M plans/registry.md
 M plans/subsystems/general-decision-model-framework-roadmap.md
 A scripts/m013c_evaluator.py
 A scripts/m013c_protocol_v1.json
 A scripts/m013c_qualification_audit.py
 A scripts/test_m013c_gates.py
 A plans/closure/general-decision-model-framework/013c-status.md
```

`git diff --stat HEAD -- Cargo.toml Cargo.lock crates/ examples/ fixtures/ docs/` is **empty**. No Python file is in any published crate: `docs/package-files.json` lists only Rust sources, `Cargo.toml` files and lockfiles, and M013c adds no crate.

## 2. Requirement-to-evidence matrix

| Requirement (plan §4) | Evidence | Disposition |
| --- | --- | --- |
| **A1** Additive versioned gate builder; preserve M013b entrypoints and archived output; no silent redefinition of the M013b analyzer format | `scripts/m013c_evaluator.py` (`M013C_EVALUATOR_VERSION = "m013c-evaluator-v1"`), `scripts/m013c_protocol_v1.json`; M013b files untouched | Pass. `m013b_evaluator.py`, `m013b_audit_m013a.py`, `m013b_diagnostics.py`, `analyze_m013a_quality.py` all unmodified; the three archived outputs reproduce byte-identically (§5). |
| **A2** Accept a provenance-validated effect estimate, CI bounds and group count; reject malformed/mismatched CI or method metadata as invalid; missing estimability/support is indeterminate | `IntervalEstimate` (`__post_init__`, `from_report`), `M013cInvalid` codes | Pass. Non-finite, reversed bounds, mean-outside-interval, wrong method/seed/replicates/confidence, incomplete report metadata and report-vs-protocol disagreement are all `invalid`. Unestimable evidence is `indeterminate`, never `invalid`. |
| **A3** Three-way Brier decision from interval bounds; favorable only when `lower > 0`, unfavorable only when `upper < 0`, straddling is indeterminate; no point-mean shortcut | `confidence_gate` | Pass. Proven on constructed fixtures (§6) and on the frozen M013a data (§4). |
| **A4** Choice paired accuracy needs `lower > 0` **and** adequate independent group support, in addition to every OOD/answerability/calibration/counterfactual/control gate; M013a null thresholds stay indeterminate | `build_choice_gates`, `_rate_gate` | Pass. 13 mandatory Choice gates block a positive verdict (§4). No threshold was invented. |
| **A5** `minimum_group_support` is an explicit immutable field of every supported critical statistical gate, cross-validated against the protocol/family support gate; n=1 is never enough; priority invalid > supported negative > insufficient > positive | `Gate.minimum_group_support`, `support_gate`, `evaluate_gates` | Pass. A critical failure below its own minimum degrades to `indeterminate`; a critical failure with **no attached minimum** is also `indeterminate`, never negative. |
| **B1** Enumerate protocol-declared Binary `required_families` and Choice `required_ood_families` in deterministic order; missing mandatory family is invalid; unexpected families rejected or declared diagnostic-only | `validate_protocol`, `completeness_gates`, `m013c_protocol_v1.json` `diagnostic_only_families` | Pass. Enumeration is from the protocol, not the report. The two in-distribution Choice ID families are declared diagnostic-only: measured, recorded, excluded from qualification, never rejected as unexpected. |
| **B2** Validate `critical_families ⊆ required_families`, no duplicates, no contradictory configuration; abort on missing keys, empty mandatory arrays, invalid thresholds, non-finite intervals | `validate_protocol`, `_declared_names` | Pass. `critical_not_required`, `duplicate_declared_name`, `empty_mandatory_array`, `contradictory_family_configuration`, `missing_protocol_key`, `malformed_support_threshold` all enforced. |
| **B3** Evaluate all five Choice negative controls as separate versioned measurements on the SAME answerable cases/groups/option IDs; define the real model-minus-control effect; a candidate must satisfy the preregistered comparison; always-abstain's no-answer recall alone is never sufficient; shuffled/context-only never replaced by a zero baseline or omitted | `evaluate_controls`, `ControlMeasurement`, `control_discriminates`, `measure_controls` | Pass. All five measured with paired grouped intervals over the same 276 answerable groups (§3). Omission is `invalid`. |
| **B4** M013a declares no numeric threshold for some controls/gates — record as insufficient; never backfill favorable post-test thresholds | `learned_beats_control_min_delta: null`, four null Choice thresholds, `unmet_threshold_consequence: "indeterminate"` | Pass. Verified by `FrozenProtocolReplayTests` — even maximally favourable evidence cannot reach positive under the frozen protocol. |
| **B5** Control inventory and comparison are explicitly task-scoped; include per-gate denominator, statistic, interval, protocol hash, rationale, population hash and status | `Gate.as_dict`, `IntervalEstimate.as_dict`, `input_sha256` in the sidecar | Pass. Every serialized gate carries denominator, bounds, statistic, provenance and an explicit status. |
| **C1** Constructed-only adversarial tests around the actual builder, with the plan's named interval/support edge cases | `scripts/test_m013c_gates.py` | Pass — every named case, §6. |
| **C2** Missing family, missing noncritical OOD, duplicate family, duplicate IDs, critical not in required list, omitted control, invalid candidate set ⇒ never positive | `RequiredSetCompletenessTests`, `NegativeControlTests`, `ProtocolValidationTests` | Pass. |
| **C3** Fully populated constructed positive under an explicitly prospective mock protocol; removing ONE gate or dropping ONE group's support makes positive unreachable; the legacy M013a protocol can NEVER produce positive | `ConstructedPositiveTests`, `prospective_protocol`, `FrozenProtocolReplayTests` | Pass. |
| **C4** Rerun the archived scripts mechanically; assert exact previously recorded output hashes; save a NEW M013c audit as a retrospective semantics correction with old-vs-new comparison and provenance | `scripts/m013c_qualification_audit.py` → `target/m013c/m013c-decision-audit.json` (`6560052b…01edf`) | Pass. `status = "retrospective_gate_semantics_correction_only"`, `frozen_inputs_modified = false`, old-vs-new block per family and per control (§4). |
| **C5** Tests run in seconds with constructed fixtures; add a focused test command and CI step that fails if a mandatory gate can be skipped, a critical n<minimum labels negative, or a point mean masquerades as an interval | `.github/workflows/ci.yml` step `Verify M013c qualification-gate hardening` | Pass. 71 tests in 0.11 s. CI asserts both verdicts, the critical-support invariant and the five-control measurement invariant. |
| **D1** Reconcile M013b "closed" vs "conditionally closed" using the historic closure header as authoritative | `plans/registry.md`, roadmap, `plans/README.md`, `README.md` | Pass. All current-facing records now read **conditionally closed**; the archived M013b closure file was not edited. |
| **D2** Register M013c as the only ready corrective; state that the prior speculative M013c label is superseded; do NOT register a successor as ready | `plans/registry.md` | Pass. M013c is now conditionally closed and **no successor milestone is registered or unblocked** (§7). |
| **D3** Record commit SHA, tests, baseline hashes, old/new comparison, host CI, ancestry and risks; prepare the stack for a reviewed MAIN-targeted PR; do not push directly to main | §8 | Partially complete — PR not yet opened; §8 states the disposition explicitly. |
| **D4** Keep external gates explicit; document package staging truthfully | §9 | Pass. No merge, publication or promotion claimed. |

## 3. Defect E — a latent bootstrap defect found during implementation

While writing the M013c bootstrap the implementation found a **fifth defect that the plan did not anticipate**, in the shared M013b helper:

`m013b_evaluator.quantile(sorted_values, probability)` indexes its argument as if it were already sorted. Its only caller, `m013b_evaluator.group_bootstrap`, passes `replicates_values` in **random draw order**. Any non-degenerate interval computed through that path is therefore an interpolation between two arbitrary adjacent draws, not a true percentile. Measured on a constructed non-degenerate population: shipped `[0.491842, 0.510375]` vs correct `[0.482667, 0.515667]`.

**Impact on recorded evidence: none.**

- The frozen M013a analyzer has its own `quantile(xs, p)` that sorts (`xs=sorted(xs)`) before interpolating, so every recorded M013a interval is correct.
- Every M013b interval computed over the frozen M013a rows is **degenerate** — the Choice paired delta and the counterfactual both-correct rate are identically zero, so any ordering yields the same `[0.0, 0.0]`.
- All three archived outputs reproduce byte-identically after M013c (§5).

**Handling.** `scripts/m013c_evaluator.py` implements its own `_quantile` and `grouped_bootstrap` that sort explicitly, and M013c uses only those. The defect in `scripts/m013b_evaluator.py` was **not** fixed, because that file is frozen evidence hashed into the M013b sidecar (`input_sha256`) — editing it would invalidate the M013b closure record, which the plan forbids. The live defect is registered in `plans/registry.md` and requires its own narrow corrective before any new experiment reuses the M013b bootstrap path.

This is a registered follow-up, not a closed item. It does not block M013c's own gate logic, which is correct.

## 4. Old-vs-new gate decisions on the unchanged frozen evidence

All five Binary family decisions are **unchanged** — the M013b point-estimate shortcut happened to agree with the interval bounds here, because every M013a Binary family interval lies wholly on one side of zero. That is a coincidence of this dataset, not a general property of the old gate.

| Family | Point estimate | 95% paired group CI | n / min | M013b | M013c |
| --- | --- | --- | --- | --- | --- |
| `binary-id-a-v1` | +0.2115 | [+0.1962, +0.2269] | 105 / 50 | pass | **pass** (favorable) |
| `binary-id-b-v1` | +0.2280 | [+0.2125, +0.2417] | 94 / 50 | pass | **pass** (favorable) |
| `binary-load-shift-v1` | +0.2207 | [+0.2014, +0.2375] | 67 / 50 | pass | **pass** (favorable) |
| `binary-text-shift-v1` | −0.2696 | [−0.2893, −0.2522] | 67 / 50 | fail | **fail** (unfavorable, critical) |
| `binary-combined-shift-v1` | −0.2699 | [−0.2875, −0.2522] | 66 / 50 | fail | **fail** (unfavorable, critical) |

**Binary → `negative`.** Both critical regressions are now supported by their interval bounds *and* by 67 and 66 eligible independent groups, exceeding the preregistered minimum of 50. Under the old code the same conclusion rested on a negative point mean with `evidence_count > 0`.

**Choice → `indeterminate`**, with 13 mandatory gates blocking positive:

- the primary paired accuracy interval is exactly `[0.0, 0.0]` over 276 groups — it spans zero, so it decides nothing;
- three required OOD answerable-group slices are under-supported (44/44/45 < 50);
- four gates have no preregistered numeric threshold in the frozen protocol;
- all five control comparisons are undeclared retrospectively.

**The negative-control defect, measured.** The old gate compared a nonnegative accuracy against zero with `>=` — a tautology that could never fail — and reported only `max(train_majority, always_answer)` as a single scalar. M013c measures all five on the same 276 answerable groups:

| Control | Control accuracy | Learned accuracy | Paired learned−control 95% CI | Discriminates |
| --- | --- | --- | --- | --- |
| `train_majority_option_id` | 0.5000 | 0.5000 | [+0.000000, +0.000000] | yes |
| `always_abstain` | 0.0000 | 0.5000 | [+0.500000, +0.500000] | yes |
| `always_answer` | 0.5000 | 0.5000 | [+0.000000, +0.000000] | no — the candidate's own argmax |
| `shuffled_score` | 0.4746 | 0.5000 | [+0.022147, +0.048777] | yes |
| `context_only_..._min_id` | 0.5000 | 0.5000 | [+0.000000, +0.000000] | yes |

The learned candidate beats no discriminating control except `always_abstain`, whose zero answerable accuracy is structural — exactly the degenerate case that must not count as evidence of learned improvement. `shuffled_score` at 0.4746 shows the only non-trivial margin (+0.022 to +0.049), and it is not a preregistered criterion. This is an independent unfavourable observation, consistent with the existing indeterminate disposition, and it is **not** reclassified as a positive finding.

## 5. Historical identity preservation

Rerun after the M013c changes; all three reproduce **byte-identically** to the hashes recorded in `plans/closure/general-decision-model-framework/013a-status.md` and `013b-status.md`:

| Command | Recorded hash | After M013c |
| --- | --- | --- |
| `python3 scripts/analyze_m013a_quality.py` | `411ac0915a0dd6ae94710271b1b23bbad830732762b956dcca71500b6f592d6e` | **identical** |
| `python3 scripts/m013b_audit_m013a.py` | `07fb99f1e984354a6746f3645f893beadfbbb3fd40ce4e37d4b6a834a0e15901` | **identical** |
| `python3 scripts/m013b_diagnostics.py` | `3b489c25eb0fcd51b7dc08d7e9e7a1e1a45a6f16e244cf5a8173e8aceb728da4` | **identical** |

`python3 -m unittest discover -s scripts -p 'test_m013b_*.py'` → **47 tests, OK**, unchanged. `python3 scripts/validate_m013a_freeze.py` → pass; the frozen split/provenance is untouched.

New M013c artifact: `target/m013c/m013c-decision-audit.json` at `6560052ba93445288d1b7577c475d0fcaec12035d9838c8c955a91ced2801edf`, written to a temp file, validated, then atomically renamed. A partial or interrupted run leaves no accepted artifact.

## 6. Adversarial test evidence

`python3 -m unittest discover -s scripts -p 'test_m013c_*.py'` → **71 tests, OK** in 0.11 s, constructed fixtures only.

Every plan-named case is covered, and the properties are proven rather than asserted:

- **Interval-bound decisions.** Point +0.02 with CI [−0.04, +0.08] at n=67 → indeterminate. Point −0.02 with CI [−0.08, +0.04] at n=67 → **not negative**. CI [−0.20, −0.04] at n=1 and n=49 → `insufficient_support`, and the task verdict is `indeterminate`, never `negative`; at n=50 and n=67 → supported negative. CI [+0.01, +0.13] → favorable at n=50, insufficient at n=49. Touching zero, [−0.08, 0.00] and [0.00, +0.06] → indeterminate. A point mean of ±0.049 inside [−0.05, 0.05] still decides nothing.
- **Malformed evidence is invalid, never coerced.** Reversed bounds, NaN/±Inf in any position, a mean outside its own interval, the wrong-sign mean versus its claimed bounds, an unrecognised bootstrap method, a changed seed/replicate count/confidence, an empty population, missing report metadata, and a report whose replicates or confidence disagree with the protocol — all rejected with a specific code.
- **Group identity.** Several cases per leakage group collapse to one row per group; duplicate case ids, malformed group ids and non-finite deltas are rejected; the interval's `groups` counts independent groups, not rows; a non-preregistered replicate count is refused.
- **Bootstrap ordering (defect E).** The quantile is order-independent and matches the sorting M013a definition exactly; a degenerate constant population yields a point interval.
- **Completeness.** Each required Binary family is enumerated in protocol order; a missing required family, a missing **noncritical** Choice OOD family and an undeclared family are all `invalid`; a declared diagnostic-only family is recorded and excluded without blocking.
- **Protocol integrity.** Critical-not-required, duplicate declared names, empty mandatory arrays, a family both required and diagnostic-only, a missing protocol key and a non-positive support minimum all abort.
- **Controls.** All five are required by name; omitting `always_answer`, `shuffled_score` or `context_only_...` is `invalid`; a duplicate measurement is rejected; a straddling control delta does not pass; a control favouring the control **fails**; one group below minimum is insufficient; with no preregistered threshold all five comparisons are insufficient.
- **Positive reachability.** One fully populated constructed gate set under an explicitly prospective protocol reaches `positive`. Sweeping **any mandatory gate** to fail/insufficient/invalid makes positive unreachable; dropping one group's support or one family interval does the same. The mandatory-only sweep is deliberate: the non-discriminating `always_answer` comparison is recorded and cannot block, while its *measurement* gate stays mandatory so it can never be omitted.
- **Frozen protocol replay.** Given maximally favourable evidence, the frozen M013a protocol still yields `indeterminate`, never positive.
- **Verdict priority.** Invalid outranks a supported critical negative; a supported critical negative outranks indeterminate; a critical failure with no attached support minimum is indeterminate; an empty gate set raises `empty_gate_set`; duplicate gate names are rejected.

## 7. Successor-plan readiness — M013d / M014 remain NOT unblocked

Closing the gate defects makes the machinery trustworthy; it does not authorize an experiment. Per the planning process, a future predictive milestone requires more than a green local run. The registry and roadmap now state the three preconditions and **no successor is registered or ready**:

1. **Hosted CI green** on the M013/M013a/M013b/M013c stack, followed by a separately reviewed main-targeted PR merge. Until then the stack is locally verified only.
2. **A corrective for the M013b quantile-ordering defect** (§3). A future protocol must use `scripts/m013c_evaluator.py`, which sorts correctly; it must not reuse the M013b bootstrap path for a non-degenerate interval.
3. **Prospective freeze before inference**: new independent frozen test groups, numeric thresholds and an alpha/multiple-comparison policy declared *before* the data are seen, and `scripts/validate_future_support.py` passing on the eligible subgroups.

M013b's train/dev diagnostics isolated two testable mechanisms — a constant-feature hidden bias in Binary and a truth-independent interaction offset in Choice — that could seed a successor design. Selecting a remedy would require prospective evidence this repository does not have, and M013a test rows remain permanently ineligible.

## 8. Verification actually run

Run locally on the M013c implementation branch (hosted CI not yet executed for this commit).

| Command | Result |
| --- | --- |
| `cargo fmt --all -- --check` | Pass |
| `cargo test --workspace --all-features --locked` | Pass — 39 tests across crates, 0 failed |
| `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` | Pass — no warnings |
| `cargo check -p sdm-runtime --locked` | Pass |
| `cargo tree -p sdm-runtime --locked` | Pass; runtime-only graph, no sdm-training, no GPU/remote IO |
| `cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked` | Pass |
| `cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json` | Pass — 12 frozen fixtures, 11 runtime executions, runtime 0.1.0 |
| `python3 -m unittest discover -s scripts -p 'test_m013b_*.py'` | 47 tests, OK |
| `python3 -m unittest discover -s scripts -p 'test_m013c_*.py'` | **71 tests, OK** |
| `python3 scripts/analyze_m013a_quality.py` | Output byte-identical (`411ac091…6d6e`) |
| `python3 scripts/m013b_audit_m013a.py` | Output byte-identical (`07fb99f1…5901`); Binary negative, Choice indeterminate |
| `python3 scripts/m013b_diagnostics.py` | Output byte-identical (`3b489c25…8da4`) |
| `python3 scripts/validate_m013a_freeze.py` | Pass — frozen split/provenance unchanged |
| `python3 scripts/m013c_qualification_audit.py` | Pass — sidecar `6560052b…01edf`; Binary negative, Choice indeterminate, both unchanged |
| CI M013c assertion block (run locally against the sidecar) | Pass — verdicts, critical-support invariant and five-control measurement invariant |
| `python3 scripts/audit_cargo_licenses.py` + `diff -u docs/third-party-license-inventory.json` | Pass — no diff |
| `python3 scripts/audit_package_contents.py docs/package-files.json` | Pass — no Python file in any published crate |
| `cargo package --workspace --locked --no-verify` | **Blocked in this environment.** Fails with `no matching package named 'sdm-core' found; location searched: crates.io index`. Pre-existing and unrelated: M013c changes no Cargo or Rust file, and the identical failure is recorded in the M013b closure. Hosted CI is the authoritative check. |
| `python3 scripts/check_m011_frozen_reports.py` | Not run locally — gated to `linux-x64` in CI. M011 evidence is untouched by M013c. |
| Hosted 10-job matrix (MSRV 1.89, linux-x64/arm64, macOS arm64, portability, choice-portability) | **Not yet run for this commit.** Outstanding gate on full closure. |

Source ancestry: `work/plans-sdm-m013c-qualification-gate-hardening` descends from the M013b stack (`99c5d51` → `11ea106` → …), **not** from M012-only main. main remains `2bd0d5af16d143828dcbce77f411b8f3b675e7be`.

Integration disposition: **no main-targeted PR has been opened.** Opening it, merging it, and crates.io legal sign-off are three separate human-reviewed actions; none is performed here, and nothing was pushed to main.

## 9. Compatibility, security, privacy and resource audit

- **Runtime/ABI:** unchanged. No Rust file touched; `fmt`/`test`/`clippy`/`check` green; the v1 `LinearArtifact`, `sdm-typed-task-v1`, additive `sdm-typed-choice-cross-v1`, artifact schema and fingerprints are untouched. All 12 CodeGG compatibility fixtures pass.
- **Historical integrity:** every frozen M013a dataset, split, report, artifact and analyzer output retains its recorded SHA-256 (§5). `frozen_inputs_modified: false` is asserted in the sidecar and re-checked in CI.
- **Fail-closed behaviour:** malformed intervals, non-finite numbers, reversed bounds, missing metadata, duplicate identities, absent required families, unmeasured controls and incomplete gate sets all fail closed. An empty gate set raises rather than passing through a vacuous `all()`.
- **No favourable post-test criteria:** every threshold the frozen M013a protocol left undeclared stays `null`. M013c's only protocol additions are structural (which families may be qualified) and restrictive (how controls are compared). `learned_beats_control_min_delta` remains `null`.
- **Security/privacy:** synthetic MIT-only fixtures; offline runtime; no network, user corpus, CodeGG content, secret, teacher or external model. No application data is captured and no candidate is auto-selected.
- **Resource:** 71 constructed tests in 0.11 s with no training; the audit reuses already-fitted artifacts and frozen reports; no new model-selection loop is added to CI.
- **Application authority:** unchanged. SDM grants no permission, widens no eligible-candidate set, and promotes nothing. CodeGG M005 remains indeterminate with no approved corpus.
- **Bounds preserved:** Rust 1.89 MSRV, runtime-only dependency graph, Linux x86_64/ARM64 and Apple Silicon, 16 MiB typed v2 artifact bound and 4,096 Choice cross-term limit all intact.

## 10. Disposition, remaining risks and open items

M013c is **conditionally closed**. Conditional on hosted CI being green and the stack being merged through review.

Remaining limitations by severity:

1. **High — no qualified predictive model.** Binary remains negative under text/combined shift; Choice remains indeterminate and now additionally shows it beats no discriminating control except the structural `always_abstain`. No remedy was selected, by design: M013c is forbidden from using observed M013a test evidence to choose one.
2. **Medium — the M013b quantile-ordering defect is live in `scripts/m013b_evaluator.py`** (§3). Inert for all recorded evidence, but any future experiment reusing that bootstrap path on a non-degenerate interval would be wrong. Requires its own corrective.
3. **Medium — positive eligibility is not establishable for the M013a cohort.** Four Choice gates and all five control comparisons have no preregistered numeric threshold and cannot be backfilled.
4. **Medium — the source stack is still unmerged.** M013/M013a/M013b/M013c require a separately reviewed main-targeted PR; hosted CI for this commit is outstanding.
5. **Medium — crates.io publication remains blocked** on human/legal license sign-off. Not addressed or bypassed here.

Open items carried forward: the M013b bootstrap corrective (§3), the main-targeted integration PR (§8), crates.io legal sign-off, and an approved independent CodeGG corpus for M005.
