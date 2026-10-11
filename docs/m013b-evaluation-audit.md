# M013b evaluation-integrity audit

Source baseline: `dbowm91/sdm@694da1a002cf29c62724be6ba881240f43aac9c2` (work/plans-sdm-m013-predictive-quality-corrective)
Status: **implemented and verified** — closure evidence at `plans/closure/general-decision-model-framework/013b-status.md`
Frozen history: `docs/m013a-protocol-v1.md`, `plans/closure/general-decision-model-framework/013a-status.md` (both unchanged)
Evaluator: `scripts/m013b_evaluator.py` (`m013b-evaluator-v1`) · erratum: `target/m013b/m013a-audit-erratum.json` · diagnostics: `target/m013b/m013b-diagnostics.json`

## Verified: incorrect interpretation of target-relative score sign

`scripts/analyze_m013a_quality.py` derives each half-pair target margin as `logit[target_index] - logit[1-target_index]`. If physical logits remain unchanged for BOTH inputs while the target moves, the values flip sign despite **zero** response to the input. The frozen `raw_target_margin_changes_sign` at 276/276 is a **label-alignment sign** measure, not proof of counterfactual sensitivity.

The corrected evaluator orients pairs by the causal `active` field and compares the **same physical option identity** on both sides. Measured over the unchanged frozen reports:

| Head | Pairs | Answerable | Same-option logit response | Response rate | Argmax change | Both-final-correct |
| --- | --- | --- | --- | --- | --- | --- |
| `choice-legacy` | 415 | 276 | 0 | **0.0** | 0.0 | 0.0 |
| `choice-cross` | 415 | 276 | 415 | **1.0** | 0.0072 | 0.0 |

The legacy diagonal head is numerically frozen (mean max |Δlogit| `2.79e-15`). The cross head genuinely responds (mean max |Δlogit| `0.0534`) but that response changes the selected option in only 0.72% of pairs. The historic zero pairs with both final targets correct is preserved as an independent unfavorable observation.

Concrete proof on frozen pair `m013a-choice-pair-0002`: logits are `[-0.406209514367968, +0.406209514368068]` before and `[-0.406209514367971, +0.406209514368065]` after. The old metric reports margins `+0.812419` → `-0.812419` ("sensitive"); the corrected metric reports `responded: false` with `max|Δlogit| = 2.78e-15`.

## Verified: positive classifier bypass

Choice classification in `scripts/analyze_m013a_quality.py` used the paired cross-minus-legacy final-answerable-accuracy CI for positive/negative/indeterminate, while `unsupported_primary_slices` and counterfactual outcomes were recorded **after**, not enforced. The frozen protocol requires support plus counterfactual and critical OOD gates. M013a Choice OOD answerable-group supports 44/44/45 fall below the preregistered 50 requirement even though total OOD groups are 67/67/66.

`scripts/m013b_evaluator.py` now emits machine-readable per-gate `pass/fail/insufficient_support/invalid` with evidence count, exact threshold and reason, and resolves a task verdict with a documented priority (invalid → negative → indeterminate → positive). An empty gate set raises rather than passing through a vacuous `all()`. Re-derived verdicts over the unchanged reports: **Choice → indeterminate** with 10 blocking mandatory gates; **Binary → negative** (`combined-shift` critical gate fails at `-0.2699` with 66 groups).

`scripts/m013b_protocol_v1.json` declares **no** favorable post-test thresholds: `counterfactual_both_correct_min_rate`, `counterfactual_response_min_rate`, `answerability_no_answer_recall_min` and `calibration_max_conditional_brier` stay `null`, so those gates return `insufficient_support` and positive eligibility is explicitly not establishable retrospectively. A prospective separate experiment must define these **before** final inference. Historical M013a report/protocol/data/closure are unchanged; the erratum is labelled `post_hoc_semantic_erratum_only`.

`scripts/validate_future_support.py` enforces eligible-subgroup support for future protocols and **refuses** to revalidate the frozen M013a corpus, so a historical cohort can never be silently reclassified under stricter rules.

## Verified root causes (train/dev only; no M013a test feedback)

The diagnostic runtime reproduces the Rust encoder and typed-task scorer to `2.22e-16` on all 2,458 frozen report rows with zero abstention or prediction mismatches.

**Binary — fit-constant note-token offset (root cause isolated).** The head encodes the truth rule correctly (`active` `+16.83`, `available` `+16.08`) but assigns `-4.4812` to each of `note~routine`, `note~service`, `note~record`, total `-13.4437`. All three tokens appear in **100% of the 1,888 training rows**, so the offset is constant and unidentifiable, behaving as a hidden bias. A label-preserving unseen-note probe on train/dev moves the probability by **+0.4968**, flipping decisions; mean predicted probability rises `0.3375 → 0.8339` while the true label rate stays `0.3375`. The load-only probe moves it by `1.4e-5` and is **falsified** as a cause; a truth-rule defect is **falsified** by the in-distribution calibration match. This corrects the planning hypothesis, which predicted *zero* response — the probe falsified that form, and the real mechanism is an unidentifiable constant offset rather than a dead channel.

**Choice — truth-independent interaction offset, not capacity (root cause isolated).** The cross head does train the needed `active × role` (`±0.0534`) and `rule × role` (`±0.1215 / ±0.1078`) terms. But truth-independent terms (`load × role`, `available × role`, `task_kind=choice × role`) contribute an identical `-0.9219` to the yes-minus-no gap in **every** quadrant, while the truth-dependent component spans only `0.134`. The gap therefore never changes sign, the argmax never moves (response rate `0.0`) and raw accuracy stays at chance. The answerability cutoff is **not** the bottleneck: final accuracy equals raw argmax accuracy on train and dev, so cutoff suppression is falsified. The legacy diagonal head cannot express the interaction at all (0 cross terms, `max|active/rule weight| = 5.27e-15`).

## Engineering and release observations

M013b is purely additive: no Rust source, fixture, split, protocol, artifact, report or historical closure record was modified, and `python3 scripts/analyze_m013a_quality.py` still reproduces `target/m013a/quality-analysis.json` byte-identically at `411ac091…6d6e`. `scripts/analyze_m013a_quality.py` itself is unmodified and remains the historical analyzer of record.

The M013/M013a/M013b stack still requires a separately reviewed main-targeted PR; no automatic merge, tag, crates.io publication or CodeGG pin change is authorized. Crates.io publication remains blocked on human/legal license sign-off, and CodeGG M005 remains externally deferred on an approved corpus. A successor predictive experiment must seal new independent frozen test groups — no M013a test row is qualification-eligible — declare numeric thresholds in advance, and pass `scripts/validate_future_support.py` before any final inference.