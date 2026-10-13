# SDM M015a — Choice development-evaluation integrity corrective

Status: **CLOSING (branch implementation complete; review/merge/merged-main CI pending)**. Not yet merged; no production model qualifies. See closure `plans/closure/general-decision-model-framework/015a-status.md`.
Class: corrective infrastructure / evaluation integrity.
Source audit baseline: `dbowm91/sdm@e7655429b0695177a30a56aaeaeea8c83abfbe55` (2026-10-13), merged M015 PR [#4](https://github.com/dbowm91/sdm/pull/4).
Source predecessor: M015 implementation merged; its PR-head CI [38438937445](https://github.com/dbowm91/sdm/actions/runs/38438937445) passed all 11 jobs. M015 historical closure file is pre-merge; main-post-merge CI/closure reconciliation is an operational check, **not** a claimed completed gate.
Planning branch: `work/plans-sdm-m015a-choice-evaluation-integrity`.
Normative precedence: ADR-0001, ADR-0002, `plans/subsystems/general-decision-model-framework-roadmap.md`, `plans/003-planning-process.md`.
Hard successor: **M016 BLOCKED until M015a is reviewed, merged, and closed on green main CI**. M017 remains blocked on M016 and its own prospective freeze. Neither M015a nor M016 depends on a CodeGG dataset.

## 1. Objective and boundaries

Repair a demonstrable M015 TRAIN/DEV Choice diagnostic inconsistency *before* fitting a new M016 neural head or claiming a comparative advantage. Make **final-action** correctness, answerable coverage, abstention, candidate-only no-answer transitions, pair identity, independent-group confidence intervals and raw conditional ranking **distinct executable estimands**. Retain a trusted, fixed-interface diagnostic baseline with negative/false-abstention controls.

M015a is **not** M016: it does not implement the TinyMLP, alter model weight fitting, change eligibility or authorization, add an M017 cohort, retroactively turn development results into final qualification, retune M015 historical candidates from newly exposed metrics, publish crates, or change CodeGG's pinned SDM revision. Any new results are retrospective **TRAIN/DEV diagnostic** findings, not prospective held-out evidence. Do not mutate M011/M013/M014/M014b FINAL evidence or their frozen evaluators.

## 2. Source-derived defect ledger (validate line locations against current HEAD)

D1 — **Raw argmax is incorrectly counted as answered accuracy.** In `crates/sdm-experiment/src/lib.rs`, the `quality_diagnostics` Choice loop near `run_semantic` computes `dev_answerable_accuracy` by comparing `choice_probabilities` argmax with the true ID without requiring the actual `decide_typed` answer to be that ID. A request whose model abstains can be counted correct. `dev_answerable_coverage` exists in the Rust map but is omitted from `scripts/run_m015_baselines.py`'s published `required_metrics` subset.

D2 — **Mixed decision semantics in counterfactual pair scoring.** The same diagnostic loop appends raw argmax correctness for answerable causal-pair members and actual `predicted_id.is_none()` for no-answer members. `dev_counterfactual_correct_on_both` therefore need not mean both **final** actions are correct. `dev_nuisance_correct_on_both` similarly uses raw conditional correctness on answerable rows, and nuisance prediction agreement alone considers double-abstention “stable” without demonstrating usefulness. These historical names MUST NOT silently acquire new meanings in pre-existing reports; use new versioned diagnostic names/namespace and a source-backed erratum.

D3 — **Context-only answerability has a representational impossibility.** `TypedTaskRuntime::answerability` in `crates/sdm-runtime/src/lib.rs` consumes encoded context only; `choice_answerability_probability` and final `decide_typed` therefore apply the same answerability threshold to two requests with the same context and changed candidates. The source-defined M015 `causal_flip` pair (`scripts/generate_m015_suite.py`) has one answerable side and one `None` side while context/`available` remain fixed. Such a pair cannot have both final actions correct under this head. Raw candidate ranking can remain correct on the answerable side; it is NOT final-action success. This is an expected limitation of the baseline, not a directive to change historical runtime semantics.

D4 — **No-answer subtypes and denominators are obscured.** M015 includes `None` from explicit unavailable context and from “available but no candidate satisfies the rule.” Report each separately as well as in aggregate. The existing `max(1)` denominator pattern must never synthesize meaningful accuracy/support on an empty subgroup. Counts must be explicit: valid, eligible, ignored and malformed group/pair counts; absent mandatory support is `insufficient_support` or invalid, not favorable zero/one.

D5 — **The all-perfect M015 summary is not a final-action quality result.** `docs/m015-dev-results.md` records 1.0 answerable accuracy, no-answer recall, nuisance-pair agreement and causal-pair correct-on-both for the existing heads, alongside finite answerability Brier/log loss; that statement describes the *historical implemented metric definitions*, not a qualified all-action outcome. Preserve it as frozen historical development evidence. An append-only **erratum/interpretation document** must bind exact source, labels, counts, result digests and the corrected retrospective report separately.

Expected invariant to test (not an already measured new score): there are 160 M015 DEV candidate-flip causal pairs across 200 groups in the seed-150015 2k/200 corpus. The before/after members have the same context and therefore identical predicted answerability under the current head. If all 160 candidate-absent after rows are correctly abstained on, their 160 answerable before rows must be falsely abstained upon; the 480 answerable DEV rows imply answerable final-action coverage no greater than 320/480 under those assumptions. Never present this bound as a directly observed baseline metric until measured.

## 3. Ordered implementation work

### A. Immutable evidence census and reproducibility gate

1. Refresh main HEAD and M015 source provenance; record `e7655429` ancestry, M015 generator/spec hashes, fixed seed 150015, 2,000 TRAIN groups/200 DEV groups, 7,200 TRAIN rows/720 DEV rows, 200 nuisance pairs and 160 candidate-flip causal pairs, original DEV artifact/report SHA ledger. Audit whether all pair/row counts remain identical on regeneration; do not silently change the generator.
2. Snapshot existing metric semantics and sample cases **in tests** using a fixed pair with one correct option then candidate mutation removing all satisfying options. Re-run existing model artifacts only through the named TRAIN/DEV pipeline or evaluation-only API; treat historical baseline output as read-only. Never overwrite `docs/m015-dev-results.md`, historical closure `015-status.md`, existing `target/m015*` outputs, or artifact/report identities; use new uniquely named `target/m015a/*` and fingerprint sources and parameters.
3. Check M015 PR #4 integration and the missing/current merged-main CI. Reconcile public planning status/closure through an additive integration sidecar; do not modify historical pre-merge closure content.

### B. Canonical final-action metrics without changing runtime behavior

1. Implement a reusable typed Choice diagnostic evaluator working from per-case target, complete permitted option identity set, runtime final `DecisionResponse`, conditional probability/logit vector and explicit `P(answerable)`. Define final-action correctness as:
   - truth `Some(id)`: only an **answered** `Choice(id)` is correct; any abstention is false abstention; any other ID is wrong choice.
   - truth `None`: only a **final abstention/no-option decision** is correct under the existing Choice interface; any chosen ID is a false positive. Do not conflate an unsupported/invalid request with valid `Choice(None)`.
2. Version new keys (e.g. `dev_final_action_accuracy_v2`, `dev_answerable_final_accuracy_v2`, `dev_false_abstention_rate_v2`, `dev_no_answer_final_recall_v2`, `dev_answerable_final_coverage_v2`). Keep raw `dev_conditional_argmax_accuracy_v2`, conditional NLL/Brier, answerability Brier/log loss/ECE, final action, selected ID, coverage and answered-only conditional accuracy separately. Explicitly define answered-only selective risk, with denominator and insufficient-support handling.
3. Preserve old response/serialized default M011 results and old diagnostic field meanings; an additive opt-in diagnostic version or sidecar is preferable. No changes to historical calibration thresholds, ranker weights, fitted encoders, `sdm-runtime` behavior, `DecisionSpec::Choice` 2..=128 semantics, or frozen evaluate schemas. Include typed request validation and exact ID membership in any new helper.

### C. Counterfactual, nuisance and no-answer integrity

1. Pair matcher must consume declarative pair type (`-nuisance` / `-causal`; no ad-hoc “any other suffix means causal”), same leakage group, exactly two unique case IDs, compatible task/rule/option identity sets, same split, expected causal- or nuisance-change contract, and explicit targets. Require exactly one no-answer and one answerable member for M015 candidate-flip pairs. Preserve order-reversal and renamed-ID controls in separate eligible pair classes. Missing, duplicate, three-member, split-crossing, accidentally relabeled nuisance, changed-context causal and mismatched-option pair MUST fail closed.
2. Compute **both final actions correct** for causal pairs, **both final actions correct** for nuisance pairs, nuisance final-decision identity consistency, nuisance correctness-preserving agreement, and optional raw-score invariance as distinct metrics. An invariant double abstention is “consistent” but cannot independently pass a robustness gate if either side is incorrect; distinguish false abstention from harmless stable abstention.
3. Derive no-answer target origin from source-defined case provenance/causal rule, not by inferring from prediction or an arbitrary `None` label. Separate `available=false` from `available=true, zero satisfying candidates` (and any future no-answer cause); report recall, support and false positives by origin.
4. For each estimator report eligible case count, independent group count, pair count, family counts, and grouped bootstrap seed/replicates/interval method. Draw leakage **groups** (not individual duplicate rows) with stable, sorted inputs; use a sorted replicate array for percentile CIs. Missing or underpowered required family/pair strata must be `insufficient_support`, never 0/0→0, and cannot drive an accepted positive quality claim. No post-hoc numerical acceptance threshold is introduced under M015a; prerequisite verdict is mechanical integrity, not candidate promotion.

### D. Adversarial tests, retrospective analysis and interpretation

1. Unit tests must seed an intentionally wrong abstention on the answerable causal member with a correct `None` after mutation, assert that historical mixed raw metric could report success and **new final pair correctness rejects it**. Test opposite false positive, two wrong selections, both correct, context invariance of legacy answerability, empty strata, missing pair member, duplicated member, malformed target, swapped ID, pair label/split leakage, nuisance label mutation and changed family.
2. Add a source-backed DEV-only replay/sidecar (suggested `scripts/analyze_m015a_final_actions.py` and `docs/m015a-evaluation-erratum.md`) using the existing three Choice heads and actual final `decide_typed` outputs. Produce complete per-family metric/support and effect tables; old 1.0 conditional-ranking values may remain correct. Explicitly label the old `dev_counterfactual_correct_on_both` as **mixed raw/final**, not final pair success.
3. Sidecar must include generator/task-spec/dataset/split/artifact/source SHAs and no test membership, capture output bytes/digests in a new location, and reproduce deterministically. Do not use the corrected DEV data to retune these historical candidates or to claim a novel M016 architecture benefit. Leave M015 history intact, including negative/indeterminate downstream results.

### E. Integration and handoff to M016

1. Extend focused tests and the existing `.github/workflows/ci.yml` pure→generator→dependent order; ensure correction can run from a clean checkout on Rust 1.89. CI must not run M014/M014b/M017 FINAL, pull external data, retrain CodeGG, or modify frozen protocol reports.
2. The M016 comparison **must consume the v2 final-action metric contract**, pair-support and count semantics, group CIs and answerability distinctions. M016's new candidate-set-aware answerability head is justified by D3 but does not belong in this corrective.
3. Record a closure document `plans/closure/general-decision-model-framework/015a-status.md` with exact implementation/source/replay digests, all tests and failures, local/hosted CI, unchanged historic hashes, observed revised DEV results, resource and dependency impact, risk assessment and truthful `ready/blocked` disposition. M016 only unblocks after reviewed merge, merged-main CI, closure acceptance, and a demonstrated fail-closed v2 contract.

## 4. Acceptance gates (all mandatory)

| Gate | Independently checkable acceptance |
| --- | --- |
| M15a-1 Evidence | Full original M015 source/seed/group/pair/report fingerprint inventory; history immutable; no FINAL accessed. |
| M15a-2 Final action | Correct `Choice(id)` versus `None` semantics on all rows; false abstentions and wrong IDs counted as errors, raw conditional argmax separate. |
| M15a-3 Pair integrity | Strict exactly-two pairing, expected causal/nuisance changes and distinct complete final correctness; deliberate mixed-metric false positive rejected. |
| M15a-4 Representability | Tested identical-context candidate flip proves old head cannot distinguish opposite answerability; report as known baseline limitation, not a surprising neural gain. |
| M15a-5 Support/statistics | Declared eligible case/group/pair counts; sorted group-level 95% CI; underpowered/empty/missing family cannot become positive or zero-by-default. |
| M15a-6 Diagnostics | DEV-only actual-runtime replay of all 3 prior heads, new sidecars/erratum and historical field glossary, separate no-answer origins, exact SHA trace. |
| M15a-7 Compatibility | Unchanged historical artifacts, old report encoding/default, Choice 2..128 rule, no runtime/trainer dependency change, 12 frozen CodeGG fixtures/11 executions and standalone consumer pass. |
| M15a-8 Closure | Rust 1.89 and normal Rust/Python verification plus ordered three-host hosted CI (or named unverified limitations), reviewed PR, merged-main CI, `015a-status.md` and registry/roadmap M016 gate update. |

Run, record outcomes and diagnose failures; **do not claim these passed from this planning document**:

```sh
cargo fmt --all -- --check
cargo test --workspace --all-features --locked
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo check -p sdm-runtime --locked
cargo tree -p sdm-runtime --locked
cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked
cargo run -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json
python3 -m unittest discover -s scripts
python3 -m unittest discover -s scripts -p 'test_m015_*.py'
```

Additional required tests: one fixture each for false abstention/mixed-counterfactual reporting, pair mismatch/absence, context-only impossibility, nuisance double-abstain disambiguation, group-bootstrap nondegeneracy and empty-stratum failure; DEV-only E2E deterministic evidence rerun; CI canary ordering. Record exact observed 200/160 support before declaring success, not merely assuming it.

## 5. Stop, restart, storage, privacy, and compatibility

**Stop immediately** if a proposed “correction” changes historical evidence bytes, treats a `None` as an extra candidate, silently changes a legacy metric name's meaning, introduces DEV-derived learned candidate retuning, reads consumed M013/M014 FINAL as a validation source, requires unspecified corpus/provider access, weakens mandatory support checks, or grants SDM application/tool execution authority.

An interrupted audit may leave only partial, uniquely named `target/m015a/` temp outputs. Accepted output uses non-overwriting atomic finalize and explicit input SHA binding; no mutation of `target/m015-baselines-v7` or previously sealed outputs. Retained source fixtures contain only synthetic labels; no user session data, telemetry, network use, or automatic external training. No incompatible artifact migration, no new runtime architecture, no release tag, no crates.io/CodeGG pin change.

**Handoff condition:** M015a engineering/integration closed with corrected truthful DEV measures; then and only then may M016 begin its architecture and baseline comparisons, with the scaling/data-loader work separately planned within M016. The corrected M015 dataset remains *development evidence*, never the M017 held-out final cohort.
