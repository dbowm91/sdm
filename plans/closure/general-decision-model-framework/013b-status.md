# M013b closure — Evaluation-gate integrity and model-failure diagnostics

Status: **conditionally closed** — the corrective is mechanically complete and both failure mechanisms are isolated. No model is qualified or promoted. The historical Binary negative and Choice indeterminate dispositions are unchanged.

Plan: `plans/implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md`
Planning baseline: `dbowm91/sdm@694da1a002cf29c62724be6ba881240f43aac9c2` (`work/plans-sdm-m013-predictive-quality-corrective`; main remains `2bd0d5af16d143828dcbce77f411b8f3b675e7be`)
Implementation branch: `work/plans-sdm-m013b-quality-gates-diagnostics`, branched from the registered planning commit `6c78731e21a56fb6bb1582ea101577a82f3b0d63`
Implementation commit: recorded below in §Merge and source status
Closure destination status: `closing` in `plans/registry.md`; promoted to `closed` once this commit is verified on hosted CI
Class: infrastructure / evaluation-integrity corrective

## 1. What changed and what did not

M013b is purely additive. It changed no Rust source, no fixture, no split, no frozen protocol, no artifact, no report and no historical closure record.

```
 M .github/workflows/ci.yml
 M .gitignore
 M README.md
 M plans/README.md
 M plans/registry.md
 M plans/subsystems/general-decision-model-framework-roadmap.md
 A scripts/m013b_evaluator.py
 A scripts/m013b_protocol_v1.json
 A scripts/m013b_audit_m013a.py
 A scripts/m013b_diagnostic_runtime.py
 A scripts/m013b_diagnostics.py
 A scripts/validate_future_support.py
 A scripts/test_m013b_evaluator.py
 A scripts/test_m013b_future_support.py
 A plans/closure/general-decision-model-framework/013b-status.md
```

`git diff --stat HEAD -- Cargo.toml Cargo.lock crates/ examples/` is empty. No Python file is included in any published crate: `docs/package-files.json` lists only Rust sources, `Cargo.toml` files and lockfiles.

## 2. Requirement-to-evidence matrix

| Requirement (plan §4) | Evidence | Disposition |
| --- | --- | --- |
| **A1** Extract pure deterministic functions into a versioned evaluator; historical analyzer and archived outputs stay reproducible | `scripts/m013b_evaluator.py` (`EVALUATOR_VERSION = "m013b-evaluator-v1"`); `scripts/analyze_m013a_quality.py` unmodified | Pass. `python3 scripts/analyze_m013a_quality.py` still emits `target/m013a/quality-analysis.json` at `411ac091…6d6e`, byte-identical to the M013a closure record. |
| **A2** Compare the SAME option identity; orient by the causal `active` field; keep target-relative margin only as a label-alignment metric | `build_pairs` (orients on `causal_active`), `validate_option_identity`, `evaluate_pair`, `summarize_pairs`; `label_alignment.interpretation = "label_alignment_only_not_input_sensitivity"` | Pass. Proven on real frozen pairs in §4. |
| **A3** Stable ties, epsilon, finite/score-range checks, correct denominators, explicit rejection | `argmax_identity` (lexicographic tie-break), `EQUALITY_EPSILON`, `require_finite`, `require_probability`, `M013bInvalid` codes | Pass. Absent/mismatched option IDs, inconsistent projection roles, duplicate pairs, empty probabilities, non-finite values and unanswerable cases all return deterministic safe results or explicit rejection. |
| **A4** Tests prove label-independence, permutation invariance, threshold separation, safe edge cases | `scripts/test_m013b_evaluator.py::FixedOptionSensitivityTests`, `MalformedInputTests` | Pass — 37 evaluator tests. |
| **B1** Executable per-gate `pass/fail/insufficient_support/invalid` with evidence count, threshold, reason and task verdict; empty gate array never passes | `Gate`, `support_gate`, `threshold_gate`, `invalid_gate`, `evaluate_gates` | Pass. `evaluate_gates([], …)` raises `empty_gate_set`; documented priority invalid → negative → indeterminate → positive. |
| **B2** Preserve the frozen M013a protocol; do not add favorable post-test thresholds | `scripts/m013b_protocol_v1.json` | Pass. `counterfactual_both_correct_min_rate`, `counterfactual_response_min_rate`, `answerability_no_answer_recall_min` and `calibration_max_conditional_brier` are all `null`; `unmet_threshold_consequence = "indeterminate"`. Positive eligibility is explicitly marked as not establishable retrospectively. |
| **B3** Count support in the eligible population for the exact metric; do not substitute total slice groups | `answerable_groups::{family}` and `critical_ood_support::{family}` gates in `m013b_audit_m013a.py` | Pass. The three OOD slices have 67/67/66 total groups but only 44/44/45 answerable groups, and are reported insufficient. |
| **B4** Enforce case/group alignment; negative controls may not qualify as learned improvements | Alignment checks in `paired_accuracy_delta`; `negative_controls_do_not_qualify` gate | Pass. |
| **B5** Adversarial gate tests including exact 49/50 and 19/20 boundaries and a constructed positive | `GateVerdictTests`, `SupportGateTests`, `ProtocolSourceTests` | Pass. 47 M013b tests total, all green. |
| **B6** Named M013a audit/erratum sidecar with old field, why misleading, corrected values, gate-by-gate verdict and input SHAs; labelled post-hoc; history never modified | `scripts/m013b_audit_m013a.py` → `target/m013b/m013a-audit-erratum.json` (`07fb99f1…5901`) | Pass. `status = "post_hoc_semantic_erratum_only"`, `frozen_inputs_modified = false`. |
| **C1** Binary train/dev-only diagnostics: vocabulary coverage, per-coordinate weights, note/label association, load scaling, label-preserving one-factor probes | `scripts/m013b_diagnostics.py` → `target/m013b/m013b-diagnostics.json` (`3b489c25…8da4`) | Pass. Root cause isolated — §5.1. |
| **C2** Choice diagnostics: reconstructed option logits, answerability, thresholded decisions on constructed truth tables and train/dev examples | Same file, `choice_score_gap_decomposition`, `choice_truth_table`, `choice_argmax_vs_abstention` | Pass. Root cause isolated — §5.2. |
| **C3** No M013a test feedback may guide masking, regularization, architecture, cutoff or hyperparameters | `evidence_policy.partitions_used = ["train","dev"]`, `partitions_forbidden = ["test"]`; enforced in CI | Pass. Every hypothesis records `would_be_falsified_by`; two were falsified. `no_remedy_selected: true`. |
| **C4** Summarize one bounded next prospective experiment | §9 successor registration | Recorded as a recommendation only; it does not register M013c/M014 as ready. |
| **D1** Reconcile registry, roadmap, plans README and README | All four updated; contradictory "M013b ready"/"M012 PR pending" phrasing removed | Pass. |
| **D2** Pre-freeze support validator for future protocols; never reclassify old frozen cohorts | `scripts/validate_future_support.py` + `scripts/test_m013b_future_support.py` | Pass. Refuses the real M013a corpus by digest. |
| **D3** Reuse hosted CI matrix; add quick evaluator tests without another expensive held-out selection loop | `.github/workflows/ci.yml` step `Verify M013b evaluation-integrity evaluator`, guarded by `hashFiles('target/m013a/*.report.json')` | Pass. Runs the existing MSRV and 3-target matrix unchanged. |
| **D4** Reviewable main-targeted PR containing M013/M013a/M013b; no automatic merge, tag, publish or CodeGG pin change | §8 | Outstanding — requires human review. |

## 3. Corrected metric and the preserved independent observation

The frozen M013a value `raw_target_margin_changes_sign = 276/276 (1.0)` is a **label-alignment sign measure, not proof of counterfactual sensitivity**. `target_index` moves when the label flips, so an unchanged score vector yields `+1` then `-1`.

Recomputed over the same unchanged saved reports:

| Head | Pairs | Answerable pairs | Pairs with ANY same-option logit response | Response rate | Identity-normalized argmax change | Both-final-correct | Label-alignment sign flip |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `choice-legacy` | 415 | 276 | 0 | **0.0** | 0.0 | 0.0 | 1.0 |
| `choice-cross` | 415 | 276 | 415 | **1.0** | 0.0072 | 0.0 | 1.0 |

Two facts the old metric hid:

1. The legacy diagonal head is **numerically frozen** — mean max |Δlogit| `2.79e-15`, i.e. float noise, not a model response.
2. The cross head genuinely responds (415/415, mean max |Δlogit| `0.0534`) but that response **almost never changes a decision**: the identity-normalized argmax moves in 0.72% of pairs and the final decision in 0.24%.

The `0/276` both-final-correct observation is preserved unchanged and remains an independent unfavorable finding. It is not erased by this relabeling.

## 4. Old-vs-new proof on real frozen data

Pair `m013a-choice-pair-0002`, from the unchanged `target/m013a/choice-legacy.report.json`:

| | Before | After |
| --- | --- | --- |
| raw logits | `[-0.406209514367968, +0.406209514368068]` | `[-0.406209514367971, +0.406209514368065]` |
| raw probabilities | `[0.307375255, 0.692624745]` | `[0.307375255, 0.692624745]` |
| **OLD** target-relative margin | `+0.812419` | `-0.812419` → **sign flip counted as "sensitive"** |
| **NEW** fixed-option input response | `max|Δlogit| = 2.78e-15` | **responded: false** |
| **NEW** identity-normalized argmax change | — | **false** |

The scores are identical to 15 significant figures. The old metric called this a counterfactual success; the corrected metric reports zero response to the manipulated input. Pair `m013a-choice-pair-0005` reproduces it in the opposite orientation.

## 5. Root-cause diagnostics (train/dev only, no M013a test feedback)

The diagnostic reimplementation of the Rust encoder and typed-task scorer was validated against all 2,458 frozen report rows: max |Δprobability| ≤ `2.22e-16`, max |Δlogit| ≤ `2.22e-16`, zero abstention mismatches, zero prediction mismatches. Every finding below derives from `train`/`dev` rows and fitted artifacts only.

### 5.1 Binary — root cause isolated

**Mechanism.** The fitted head encodes the declared truth rule (`active` = active AND available) correctly in distribution: `active=true` carries `+16.83` and `available=true` carries `+16.08`. But it *also* assigns `note~routine`, `note~service` and `note~record` a weight of `-4.4812` each, total **`-13.4437`**. Those three tokens are present in **100% of the 1,888 training rows**, so their contribution is constant and unidentifiable from the fit — it acts as a hidden bias. The ID families use `"routine service record N"`, which carries all three; the text-shift families use `"quartz nebula payload N"`, which carries none. When they disappear the whole offset vanishes and the logit rises.

**Quantified on train/dev** (label-preserving probes):

| Probe | Mean Δprobability (train) |
| --- | --- |
| unseen note only | **+0.4968** |
| load only (0–10 → 15) | `-1.43e-5` |
| combined text + load | `+0.4966` |
| identity control | `0.0` exactly |

Mean predicted probability rises from `0.3375` to `0.8339` while the mean true label rate stays at `0.3375` — the decision inverts.

**Hypotheses and outcomes:**

| Hypothesis | Status | Falsified by |
| --- | --- | --- |
| B1 — large negative weight on fit-constant note tokens is a hidden bias that vanishes under unseen notes | **supported** | — |
| B2 — numeric load scaling is an independent additive failure mode | **falsified** | The load-only probe moves the probability by `1.4e-5`, three orders of magnitude below the text offset. Combined ≈ text-only. |
| B3 — the truth rule itself is unrepresented | **falsified** | The dominant weights are exactly the declared rule and in-distribution calibration matches (mean p `0.3375` vs mean y `0.3375`). |

**Correction to the planning hypothesis.** The M013b audit doc and the plan both suspected that an unseen note would produce *zero* response (a dead channel). The first probe **falsified that form**: movement is large (+0.50), not zero. The correct mechanism is an unidentifiable constant offset, not a missing channel. The recorded finding reflects the corrected mechanism.

### 5.2 Choice — root cause isolated (optimization, not capacity)

The cross head **does** train the interaction terms the rule needs: `active=true × task_kind=yes/no` (`±0.0534`) and `rule_family=a/b × task_kind=yes/no` (`±0.1215 / ±0.1078`), 100 declared cross terms with 12 nonzero. Capacity was not the blocker.

Decomposing the yes-minus-no score gap across the four constructed quadrants:

| active | rule | gap (yes−no) | truth-dependent interaction | constant interaction |
| --- | --- | --- | --- | --- |
| false | a | -1.6237 | -0.2431 | **-0.9219** |
| false | b | -1.5962 | -0.2156 | **-0.9219** |
| true | a | -1.5170 | -0.1363 | **-0.9219** |
| true | b | -1.4895 | -0.1088 | **-0.9219** |

The rule requires the gap to **change sign** between quadrants. It never does: the truth-dependent component spans only `0.134` while the truth-independent component contributes an identical `-0.9219` in every quadrant and dominates it. Truth-independent terms (`load × role`, `available × role`, `task_kind=choice × role`) form a constant offset. The argmax never moves (response rate `0.0`) and raw accuracy sits at chance (`0.5`).

The legacy diagonal head cannot express the interaction at all: 0 declared cross terms, zero nonzero weights in the context and interaction blocks, `max|active/rule weight| = 5.27e-15`.

**Hypotheses and outcomes:**

| Hypothesis | Status | Falsified by |
| --- | --- | --- |
| C1 — the legacy diagonal head cannot express rule × active × role | **supported** | — |
| C2 — the cross head is representationally capable | **supported** | — |
| C3 — truth-independent interaction terms create a constant offset that dominates, so the gap never changes sign | **supported** | — |
| C4 — a correct raw argmax is suppressed by the answerability cutoff | **falsified** | Final accuracy **equals** raw argmax accuracy on train (0.5000) and dev (0.5000); suppression count is 0. The ranking itself is wrong; the abstention question is downstream. |

## 6. Gate verdicts (fail-closed)

Re-derived from the unchanged M013a reports with the M013b evaluator:

- **Choice → `indeterminate`.** The paired primary CI is exactly `[0.00, 0.00]`, so the primary gate fails; **10 mandatory gates block a positive verdict**: the primary gate, three under-supported OOD answerable-group slices (44/44/45 < 50), two critical-OOD support gates, and four gates whose success threshold M013a never declared (`counterfactual_both_correct_rate`, `counterfactual_fixed_option_response_rate`, `answerability_no_answer_recall`, `calibration_max_conditional_brier`).
- **Binary → `negative`.** `combined-shift` fails its critical gate at `-0.2699` with 66 independent groups, i.e. a supported critical regression.

Historical dispositions are preserved verbatim: Binary negative, Choice indeterminate, three OOD Choice accuracy slices insufficient.

## 7. Adversarial test evidence

`python3 -m unittest discover -s scripts -p 'test_m013b_*.py'` → **47 tests, OK**.

Properties proven rather than asserted:

- Unchanged logits + swapped target ⇒ `responded: false` while the label-alignment margin still flips sign.
- A metric cannot report successful responsiveness merely because labels differ.
- Option-list permutation yields identical identity-normalized comparison (`per_option` deltas agree to 12 places).
- Threshold-only abstention change is separated from raw option change; ε near-equality counts as unchanged; ties resolve deterministically to the lexicographically smallest identity.
- Unanswerable pairs are excluded from answerable denominators (`denominator: 1`, not 2).
- Every mandatory gate swept to `fail` / `insufficient_support` / `invalid` in turn ⇒ `positive` is unreachable.
- Empty gate set raises `empty_gate_set` rather than passing through a vacuous `all()`.
- Exact boundaries 49/50 and 19/20; 67 total groups never substitutes for 44 answerable groups.
- Always-abstain with perfect no-answer recall is never positive; unsupported or empty CI is indeterminate; an explicit all-pass fixture does yield positive.
- `validate_future_support.py` refuses the real M013a corpus by digest and reports the genuine 44/45 answerable shortfall.

## 8. Verification actually run

| Command | Result |
| --- | --- |
| `cargo fmt --all -- --check` | Pass |
| `cargo test --workspace --all-features --locked` | Pass (39 tests across crates, 0 failed) |
| `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` | Pass, no warnings |
| `cargo check -p sdm-runtime --locked` | Pass |
| `cargo tree -p sdm-runtime --locked` | Pass; runtime-only graph, no sdm-training, no GPU/remote IO |
| `cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked` | Pass |
| `cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json` | Pass — 12 frozen fixtures, 11 runtime executions, runtime 0.1.0 |
| `python3 -m unittest discover -s scripts -p 'test_m013b_*.py'` | 47 tests, OK |
| `python3 scripts/generate_m013a_quality_suite.py` + `git diff --exit-code` | Pass — regenerated corpus byte-identical |
| `python3 scripts/validate_m013a_freeze.py` | Pass — 3,064 cases / 1,532 groups per task; OOD 67/67/66 groups; Choice no-answer 23/22/22 |
| `python3 scripts/analyze_m013a_quality.py` | Pass — output byte-identical (`411ac091…6d6e`) |
| `python3 scripts/m013b_audit_m013a.py` | Pass — sidecar `07fb99f1…5901`; Binary `negative`, Choice `indeterminate` |
| `python3 scripts/m013b_diagnostics.py` | Pass — `3b489c25…8da4`; both root causes isolated |
| `python3 scripts/check_staged_consumer.py` | Pass — consumer compiled against extracted package archives |
| `python3 scripts/audit_cargo_licenses.py` + `diff -u docs/third-party-license-inventory.json` | Pass — no diff |
| `python3 scripts/check_m011_frozen_reports.py` | Binary and choice identities preserved. **Score differs locally** (`6ab8093b…` vs `1a62724e…`) — this is the pre-existing host float difference already recorded in the M013a closure; the check is gated to `linux-x64` in CI and no Linux fingerprint was substituted. |
| `cargo package --workspace --locked --no-verify` | **Blocked in this environment.** Fails with `no matching package named sdm-core found; location searched: crates.io index`. Verified **pre-existing and unrelated**: the identical failure reproduces on a clean worktree of the untouched planning baseline, and M013b changes no packaging-relevant file. Local `crates.io` API access returns HTTP 403. CI is the authoritative check. |

Hosted CI (Rust 1.89 MSRV job; linux-x64, linux-arm64, macos-arm64; cross-Choice artifact portability; frozen SHA checks; staged consumer; license and package audits) has **not** been run for this commit at the time of writing. Run 38105314254 belongs to the M013a baseline and is not M013b evidence. The status stays `closing` until hosted CI is green.

## 9. Compatibility, security, privacy and resource audit

- **Runtime/ABI:** unchanged. No Rust file touched; `cargo check`/`test`/`clippy` green; the v1 `LinearArtifact`, `sdm-typed-task-v1`, additive `sdm-typed-choice-cross-v1`, artifact schema and fingerprints are untouched. The 12/11 CodeGG compatibility fixtures pass.
- **Historical integrity:** every frozen M013a dataset, split, report, artifact and analyzer output retains its recorded SHA-256. `frozen_inputs_modified: false` is asserted in the sidecar and re-checked in CI.
- **Failure handling:** all M013b output is staged to a temporary file and atomically renamed (`atomic_write_json`), so an interrupted run cannot leave accepted partial evidence.
- **Security/privacy:** synthetic MIT-only fixtures; offline runtime; no network, user corpus, CodeGG content, secret or teacher. The diagnostic runtime reads only local frozen artifacts. `.gitignore` now excludes `__pycache__/` and the standalone-consumer target so no build residue is committed.
- **Resource:** unit tests are constructed fixtures with no training; diagnostics reuse already-fitted artifacts and run in seconds; CI adds no new model-selection loop.
- **Storage:** the large checked-in generator fixtures were reviewed as a nonblocking storage/packaging consideration only. No immutable fixture identity was rewritten.

## 10. Disposition, remaining risks and successor registration

M013b is **conditionally closed**. It restores trust in the M013a evaluation; it does not qualify Binary, Choice, Rank or Score. Nothing is promoted.

Remaining limitations by severity:

1. **High — no qualified predictive model.** Binary remains negative under text/combined shift; Choice remains indeterminate. Both root causes are now understood but **no remedy was selected, by design**: choosing one would require evidence M013b is forbidden from using.
2. **Medium — positive eligibility is not establishable for M013a.** The frozen protocol named counterfactual, critical-OOD, answerability and calibration gates without numeric thresholds. These stay `null`; a favorable primary CI can never promote on the M013a cohort.
3. **Medium — the source stack is still unmerged.** M013/M013a/M013b require a separately reviewed main-targeted PR (§8 D4).
4. **Medium — crates.io publication remains blocked** on human/legal license sign-off. Not addressed or bypassed here.
5. **Low — CodeGG M005 remains externally deferred** on an approved corpus and consumer-owned evidence; no SDM change unblocks it and no CodeGG pin was altered.
6. **Low — packaging verification unconfirmed locally** per §8; CI is authoritative.

**Successor readiness.** M013b is mechanically closed, so a new plan may now be *registered*. It is not unblocked for execution: any successor must (a) prospectively seal new independent frozen test groups — **no M013a test row is qualification-eligible**, (b) declare numeric thresholds for every gate in advance, (c) pass `scripts/validate_future_support.py` **before** any final inference, and (d) verify eligible-subgroup support for each metric in its own eligible population. The two isolated mechanisms give directly testable, bounded remedy categories:

- **Binary — constant-feature nuisance regularization.** The `-13.4437` offset comes from fit-constant tokens. A preregistered remedy category is to constrain or exclude fit-invariant encoded features so a constant cannot masquerade as signal.
- **Choice — interaction/optimizer diagnostics.** Capacity is sufficient; the truth-independent interaction offset dominates the truth-dependent terms. A remedy category is to make the yes-minus-no gap sign-changing on constructed truth tables as a *training-time* diagnostic, before any held-out evaluation.
- **Answerability threshold robustness** is *not* implicated: C4 was falsified.

Writing this recommendation does not register M013c or M014 as ready. No CodeGG model promotion, release, publish, tag or automatic merge is authorized.

## 11. Merge and source status

Implementation branch: `work/plans-sdm-m013b-quality-gates-diagnostics`, branched from registered planning commit `6c78731e21a56fb6bb1582ea101577a82f3b0d63`. Implementation commit SHA and hosted CI run URL are recorded here once the branch is pushed and CI completes. Main remains `2bd0d5af16d143828dcbce77f411b8f3b675e7be`; no main merge, tag or publication is authorized by this closure.

## 12. Input and output provenance

| Artifact | SHA-256 |
| --- | --- |
| `scripts/m013b_evaluator.py` | `161b1881efeb7750d8b5308d603cf318f5f16579d1db8d51739bbb8ba356cedb` |
| `scripts/m013b_protocol_v1.json` | `2de34fb710d352201ca1efbac173a384836186896063bd93fbeed1811ee6b790` |
| `scripts/m013b_audit_m013a.py` | `28f811df2de73e86089c425d48aab338441f7eeed374f2edc857cf8b856fcac9` |
| `scripts/m013b_diagnostic_runtime.py` | `40df9326c17487629e3356aee44bafbbc80a9f5fec3de063bb90246d1fc5ffee` |
| `scripts/m013b_diagnostics.py` | `bc9fb8f5ef094604d69a27635e931cff8391a92001cf60440bffc4ba345d86f6` |
| `scripts/validate_future_support.py` | `221e110c553e8a5d71687e859daee8c400bf1a2722a09ae60ef647b55dce9f41` |
| `scripts/test_m013b_evaluator.py` | `d6cef6b6dfc54ad98948c2eb9ee8b98266c4224fca4ac10962d61a6d840c78f8` |
| `scripts/test_m013b_future_support.py` | `b8241c62470664cbd1a82882d4b8fa01e3db885951fee62254fcc37cf02fa030` |
| `target/m013b/m013a-audit-erratum.json` | `07fb99f1e984354a6746f3645f893beadfbbb3fd40ce4e37d4b6a834a0e15901` |
| `target/m013b/m013b-diagnostics.json` | `3b489c25eb0fcd51b7dc08d7e9e7a1e1a45a6f16e244cf5a8173e8aceb728da4` |
| `target/m013a/quality-analysis.json` (unchanged) | `411ac0915a0dd6ae94710271b1b23bbad830732762b956dcca71500b6f592d6e` |

Frozen M013a dataset, split, report and artifact digests are recorded in `docs/m013a-protocol-v1.md` and `plans/closure/general-decision-model-framework/013a-status.md` and are unchanged by M013b.