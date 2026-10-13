# M015a evaluation erratum — Choice DEV final-action interpretation (append-only)

Status: **retrospective TRAIN/DEV diagnostic correction; historical M015 evidence preserved byte-identically**.
This document does not mutate `docs/m015-dev-results.md`, historical closure
`plans/closure/general-decision-model-framework/015-status.md`, existing
`target/m015*` outputs, or artifact/report identities. New outputs live only
under `target/m015a/`. All new results are retrospective TRAIN/DEV diagnostics,
not prospective held-out evidence. Do not use them to retune candidates, claim
an M016 benefit, or qualify a model.

Source baseline: `dbowm91/sdm@e7655429b0695177a30a56aaeaeea8c83abfbe55`
(2026-10-13, merged M015 PR #4). Planning branch at implementation:
`work/plans-sdm-m015a-choice-evaluation-integrity`.
Generator SHA-256: `18a4d27cca57c639696bad560302549e837152968b2861ccf23a92e6f4ff57f9`.
Task-spec SHA-256: `905441b3f25344cdbe0708538ad44b2005506b602019693da530b82893c2613c`.
Seed `150015`: 2,000 TRAIN groups / 7,200 rows; 200 DEV groups / 720 rows;
200 DEV nuisance pairs; 160 DEV candidate-flip causal pairs; 480 answerable DEV
rows (320 nuisance + 160 causal-before); 240 no-answer DEV rows (80
`available=false` + 160 `available=true, zero satisfying` causal-after).
Corpus SHAs: TRAIN `6d1910242f885fff1d67802952a28783ca6c20304363d56befd8f7d117cd9743`,
DEV `e2c9b5b137506b13ef9b40f0b7ed8f8c6f9a89e2de1b16ef2d667c51de04e9db`.
Typed dataset SHA-256 (actual `target/m015-baselines-v7`): `sha256:f0d614db315836c41f2a79f998aed47331f0fc234c0e2a3b516638d9ebd702a9`
(split `sha256:7f0e872990247cd21a45a6f7d3c2f08728272fc99763fa7c886eda53dd008e69`).
Note: `docs/m015-dev-results.md` records dataset `bef4c9a8…` with the same
`7f0e8729…` split fingerprint and v7 artifact/report bytes. That dataset line is
stale (it matches superseded `target/m015-baselines-v2/v3/v4` runs, fingerprint
`62f7f3be…`). The split fingerprint, artifact SHAs (`e9b303ac…`, `b89fd3b4…`,
`01b760d2…`) and report byte SHAs (`0ff40888…`, `109a8999…`, `772216d9…`) in that
document do match `target/m015-baselines-v7`. This erratum records both values
without rewriting history; the v2 replay binds the actual `f0d614db…` digest.

## 1. What the historical 1.0 summary means (frozen)

`docs/m015-dev-results.md` states all three heads reached DEV answerable
accuracy `1.0`, no-answer recall `1.0`, causal-pair correct-on-both `1.0` and
nuisance-pair prediction agreement `1.0`, with answerability Brier `0.1055939`,
log loss `0.289023`, ECE `0.0471949`. That statement describes the **historical
implemented metric definitions** in `crates/sdm-experiment/src/lib.rs`
(`run_semantic` Choice `dev_diagnostics`), not a qualified all-action outcome:

- D1 — `dev_answerable_accuracy` compares `choice_probabilities` argmax with the
  true ID **without requiring the actual `decide_typed` answer to be that ID**.
  An abstained request can be counted correct. `dev_answerable_coverage`
  (`0.666666…` in all three v7 reports) exists in the Rust map but is omitted
  from `scripts/run_m015_baselines.py` `required_metrics` and from the prose
  summary.
- D2 — Counterfactual scoring mixes semantics: raw argmax correctness for
  answerable members, actual `predicted_id.is_none()` for no-answer members.
  `dev_counterfactual_correct_on_both` therefore need not mean both **final**
  actions are correct. `dev_nuisance_correct_on_both` uses raw conditional
  correctness on answerable rows only (160 pairs), while
  `dev_nuisance_pair_prediction_agreement` uses prediction identity over all
  200 pairs; double abstention counts as “stable” without demonstrating
  usefulness. These names keep their old meanings in old reports.
- D3 — `TypedTaskRuntime::answerability` consumes encoded context only, so
  `choice_answerability_probability` and final `decide_typed` apply the same
  threshold to two requests with identical context and changed candidates.
  Source-defined M015 `causal_flip` pairs hold context fixed
  (`load: 3.0, note: causal control`) while flipping one candidate feature and
  the target (`Some` → `None`). Such a pair cannot have both final actions
  correct under this head. Raw ranking on the answerable side can remain
  correct; that is not final-action success. This is an expected baseline
  limitation, not a directive to change runtime semantics.
- D4 — No-answer subtypes and denominators are obscured. The old code lumps
  `available=false` (80 DEV rows, 40 groups) with `available=true, zero
  satisfying` (160 DEV rows, 160 groups) into one recall, reports
  `dev_no_answer_groups: 200` (groups with ≥1 no-answer row, not exclusively
  no-answer groups), uses `max(1)` denominators that would synthesize
  accuracy/support on empty strata, and counts nuisance correctness on 160
  answerable pairs while counting prediction agreement on 200 pairs without
  naming the difference.
- D5 — The all-perfect summary is therefore not a final-action quality result.
  It is preserved as frozen historical development evidence.

The expected invariant (not a previously measured score) holds: 160 DEV
candidate-flip causal pairs share context and therefore identical predicted
answerability. With all 160 causal-after rows correctly abstained, their 160
answerable before rows must be falsely abstained; 480 answerable rows imply
final-action coverage ≤ `320/480`. The v2 replay below measures exactly this.

## 2. Corrected retrospective DEV findings (v2, actual runtime)

Replay: `scripts/analyze_m015a_final_actions.py` invokes additive
`sdm experiment m015a-replay` for each frozen artifact (read-only inference,
DEV partition only, no training, no test, no threshold/weight change). Contract
`choice-final-v2` (Rust `sdm-eval::choice_final_v2`, Python mirror
`scripts/m015a_final_metrics.py`): final correctness requires answered exact ID
for `Some` and abstention for `None`; raw argmax, answerability, coverage and
answered-only selective accuracy are separate; strict exactly-two matcher
(`-nuisance`/`-causal` only, same group/split/family/rule, compatible option
sets, causal requires exactly one `None` + identical context + flipped
semantics + preserved order, nuisance requires identical targets + preserved
semantics); origins from corpus (`available=false` vs `available=true, zero
satisfying`); leakage-group 95% CIs (seed `150015`, 2,000 replicates,
`grouped_bootstrap_percentile_sorted_v1`, sorted inputs/replicates);
empty/missing strata are `insufficient_support`, never `0/0→0`.

All three heads agree exactly (same preprocessing, same answerability weights,
threshold `0.6527825442888768`):

| Estimand (v2) | `typed-choice` | `typed-choice-cross` | `typed-choice-compositional` |
| --- | ---: | ---: | ---: |
| `dev_final_action_accuracy_v2` (720 rows, 200 groups; 95% CI) | 0.777777… `[0.7695, 0.7865]` | 0.777777… | 0.777777… |
| `dev_answerable_final_accuracy_v2` (480 rows, 160 groups) | 0.666666… `[0.6666, 0.6666]` | 0.666666… | 0.666666… |
| `dev_false_abstention_rate_v2` | 0.333333… | 0.333333… | 0.333333… |
| `dev_answerable_final_coverage_v2` | 0.666666… | 0.666666… | 0.666666… |
| `dev_conditional_argmax_accuracy_v2` (raw, separate) | 1.0 `[1.0, 1.0]` | 1.0 | 1.0 |
| `dev_answered_conditional_accuracy_v2` (320 answered, 160 groups) | 1.0 | 1.0 | 1.0 |
| `dev_no_answer_final_recall_v2` (240 rows, 200 groups) | 1.0 `[1.0, 1.0]` | 1.0 | 1.0 |
| └ `available=false` (80 rows, 40 groups) | 1.0 | 1.0 | 1.0 |
| └ `available=true, zero satisfying` (160 rows, 160 groups) | 1.0 | 1.0 | 1.0 |
| Causal `both_final_correct_v2` (160 pairs, 160 groups) | **0.0** `[0.0, 0.0]` | **0.0** | **0.0** |
| Nuisance `both_final_correct_v2` (200 pairs, 200 groups) | 1.0 `[1.0, 1.0]` | 1.0 | 1.0 |
| Nuisance `prediction_consistency_v2` | 1.0 | 1.0 | 1.0 |
| Nuisance `correctness_preserving_agreement_v2` | 1.0 | 1.0 | 1.0 |
| Per-family final accuracy (144 rows, 40 groups each) | 0.777777… | 0.777777… | 0.777777… |
| Per-family answerable-final (96 rows, 32 groups each) | 0.666666… | 0.666666… | 0.666666… |
| Per-family no-answer recall (48 rows, 40 groups each) | 1.0 | 1.0 | 1.0 |

Legacy mixed values for comparison (frozen, unchanged): `dev_answerable_accuracy`
1.0 (raw), `dev_answerable_coverage` 0.666666… (omitted from published subset),
`dev_counterfactual_correct_on_both` 1.0 (**mixed raw/final**, not final pair
success), `dev_nuisance_correct_on_both` 1.0 (160 answerable pairs, raw),
`dev_nuisance_pair_prediction_agreement` 1.0 (200 pairs, identity). Old
`dev_counterfactual_correct_on_both` is hereby labeled **mixed raw/final**.

Calibration (row-averaged v2 vs group-averaged legacy): v2 answerability Brier
`0.11732649`, log loss `0.32104607`, ECE `0.05251996` (720 rows, 200 groups);
legacy group-averaged Brier `0.1055939`, log loss `0.289023`, ECE `0.0471949`.
Conditional NLL/Brier are identical (row-averaged in both): `typed-choice`
`9.4435e-05` / `4.2899e-08`, cross `2.2265e-05` / `2.2512e-09`, compositional
`1.2505e-05` / `7.7325e-10`. The Brier/ECE difference is an averaging
convention, not a runtime change; both conventions are documented with support.

Sidecars: `target/m015a/typed-choice.sidecar.json`,
`typed-choice-cross.sidecar.json`, `typed-choice-compositional.sidecar.json`
plus `m015a-summary.json` carry input SHAs, census, v2 report, legacy glossary,
bootstrap seed/replicates/method, output bytes/digests, and `test_membership:
[]`. No test partition was evaluated; `test_evaluation_performed: false`.

## 3. Glossary and handoff

- Old `dev_answerable_accuracy`, `dev_counterfactual_correct_on_both`,
  `dev_nuisance_correct_on_both`, `dev_nuisance_pair_prediction_agreement` keep
  their historical mixed/raw meanings. Do not silently reinterpret them.
- New `*_v2` keys are the only final-action contract M016 may consume. Raw
  conditional argmax, abstention/coverage, no-answer origins, pair-support
  counts and group CIs stay separate.
- Double abstention is “consistent” but passes robustness only when both sides
  are correct; false abstention is distinguished from harmless stable
  abstention.
- Context-only answerability cannot distinguish M015 candidate-flip pairs; the
  0.0 causal both-final result is the measured baseline limitation that
  justifies (but does not implement) M016’s candidate-aware answerability head.
- No retuning, no new architecture, no threshold/weight change, no FINAL
  access, no CodeGG/data/crates.io change. M016 remains blocked until this
  corrective is reviewed, merged, green on merged-main CI, and accepted via
  `plans/closure/general-decision-model-framework/015a-status.md`.
