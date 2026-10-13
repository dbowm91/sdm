# M015a — Choice development-evaluation integrity corrective

Status: **closing (branch implementation complete; review/merge/merged-main CI pending; conditionally closed for engineering)**.

Plan: [015a-choice-development-evaluation-integrity-corrective.md](../../implementation/general-decision-model-framework/015a-choice-development-evaluation-integrity-corrective.md)
Branch: `work/plans-sdm-m015a-choice-evaluation-integrity`
Base: `main@e7655429b0695177a30a56aaeaeea8c83abfbe55` (M015 PR #4 merge, 2026-10-13)
Planning baseline ancestry verified: `e7655429` is an ancestor of this branch
(`git merge-base --is-ancestor` yes). M015 PR-head CI 38438937445 passed 11/11;
M015 historical closure `015-status.md` predates merge and is preserved
byte-identically; merged-main CI/closure reconciliation remains an operational
check, not a claimed gate.
Implementation: additive v2 final-action contract + DEV-only replay + erratum on
this branch (see SHAs below). Integration PR to be created; reviewer merge and
merged-main CI are outstanding and required before M016.

M015a repairs a demonstrable M015 TRAIN/DEV Choice diagnostic inconsistency
before any M016 head or comparative claim. It makes **final-action**
correctness, answerable coverage, abstention, candidate-only no-answer
transitions, pair identity, independent-group CIs and raw conditional ranking
distinct executable estimands, with a fixed-interface baseline, negative/false-
abstention controls, and immutable history. It is not M016: no TinyMLP, no
weight/threshold/eligibility change, no M017 cohort, no retroactive
qualification, no retuning from new metrics, no crates.io/CodeGG pin change.
All new results are retrospective TRAIN/DEV diagnostics.

## Requirement evidence (M15a-1..8)

| Gate | Evidence and disposition |
| --- | --- |
| M15a-1 Evidence | Census verified on regeneration: seed `150015`, 2,000 TRAIN groups / 7,200 rows, 200 DEV groups / 720 rows, 200 nuisance + 160 causal-flip DEV pairs, 480 answerable (320 nuisance + 160 causal-before) / 240 no-answer (80 `available=false` + 160 `available=true, zero satisfying`). Generator `18a4d27cca57c639696bad560302549e837152968b2861ccf23a92e6f4ff57f9`, task-spec `905441b3f25344cdbe0708538ad44b2005506b602019693da530b82893c2613c`, corpus TRAIN `6d1910242f885fff1d67802952a28783ca6c20304363d56befd8f7d117cd9743`, DEV `e2c9b5b137506b13ef9b40f0b7ed8f8c6f9a89e2de1b16ef2d667c51de04e9db` (manifest `target/m015-baselines-v7/corpus/manifest.json`). Typed dataset `sha256:f0d614db315836c41f2a79f998aed47331f0fc234c0e2a3b516638d9ebd702a9`, split `sha256:7f0e872990247cd21a45a6f7d3c2f08728272fc99763fa7c886eda53dd008e69` (actual v7). `docs/m015-dev-results.md` dataset line `bef4c9a8…` is stale (matches superseded v2/v3/v4, fingerprint `62f7f3be…`); split/artifact/report bytes in that document do match v7 and are recorded as such in the erratum without rewriting history. Artifacts `e9b303ac…` (11,963 B), `b89fd3b4…` (24,699 B), `01b760d2…` (111,055 B); reports `0ff40888…`, `109a8999…`, `772216d9…` (file SHAs verified). History immutable: `git diff --exit-code -- docs/m015-dev-results.md plans/closure/general-decision-model-framework/015-status.md` passes; `target/m015-baselines-v7` untouched; new outputs only `target/m015a/`. No FINAL accessed (`test_membership=[]`, `test_evaluation_performed=false`). **Pass.** |
| M15a-2 Final action | Reusable evaluator `crates/sdm-eval/src/choice_final_v2.rs` (`choice-final-v2`, `CONTRACT_SEED=150015`, `REPLICATES=2000`, `CONFIDENCE=0.95`, `METHOD=grouped_bootstrap_percentile_sorted_v1`) + Python mirror `scripts/m015a_final_metrics.py`. Validates 2..=128 options, exact ID membership, finite probs summing to 1±1e-8, finite logits/answerability, explicit origins; defines `Some(id)`→answered exact ID else false abstention/wrong choice, `None`→abstention else false positive; never synthesizes `Choice(None)` for 0/1 (fail-closed). New keys `dev_final_action_accuracy_v2`, `dev_answerable_final_accuracy_v2`, `dev_false_abstention_rate_v2`, `dev_no_answer_final_recall_v2`, `dev_answerable_final_coverage_v2`, `dev_conditional_argmax_accuracy_v2`, `dev_answered_conditional_accuracy_v2` (selective, denominator + insufficient handling), conditional NLL/Brier, answerability Brier/log-loss/ECE kept separate. Old response/serialization, thresholds, weights, encoders, `sdm-runtime` behavior, frozen schemas unchanged (additive opt-in sidecar). Typed request validation + ID membership in helper. Measured: final 0.777777… (720/200), answerable-final 0.666666… (480/160), false abstention 0.333333…, coverage 0.666666…, raw argmax 1.0, answered-selective 1.0 (320/160), no-answer recall 1.0 (240/200). **Pass.** |
| M15a-3 Pair integrity | Strict `match_pairs` (Rust + Python mirror): declarative `-nuisance`/`-causal` only (unknown suffix fails closed, no “else is causal”), same group/split/family/rule, exactly two unique case IDs, compatible option sets, causal exactly-one-`None` + identical context + flipped semantics + preserved order, nuisance identical targets + preserved semantics; missing/duplicate/three-member/split-crossing/relabeled-nuisance/changed-context-causal/mismatched-option all ineligible with reasons. Computes causal `both_final_correct_v2`, nuisance `both_final_correct_v2`, `prediction_consistency_v2`, `correctness_preserving_agreement_v2` (identical + both correct; double abstention consistent but not preserving when incorrect), `raw_argmax_agreement_v2` separately. Deliberate mixed-metric false positive (raw-correct + abstained before + correct after) rejected: v2 causal 0.0 vs historical mixed 1.0. Measured: causal 160/160 eligible, both-final 0.0 `[0.0,0.0]`; nuisance 200/200 eligible, both-final 1.0, consistency 1.0, preserving 1.0; ineligible 0. **Pass.** |
| M15a-4 Representability | Unit tests seed identical-context candidate flip and assert legacy answerability identical while new final pair rejects; `TypedTaskRuntime::answerability` context-only limitation reported as known baseline, not neural gain. Source causal pairs hold `load:3.0, note:causal control` fixed; 160/160 share context digests and therefore identical `P(answerable)`; threshold `0.6527825442888768` correctly abstains all 160 afters and falsely abstains all 160 befores (coverage 320/480). Raw ranking remains 1.0 on answerable side. **Pass.** |
| M15a-5 Support/statistics | Every estimator reports eligible cases/groups/pairs, family counts, seed/replicates/method; sorted group inputs, sorted replicate arrays, deterministic reruns identical. Origins separated: `available_false` 80/40 recall 1.0, `available_true_zero_satisfying` 160/160 recall 1.0; per-family 144/40 final 0.777…, 96/32 answerable-final 0.666…, 48/40 no-answer 1.0. Grouped 95% CIs: final `[0.7695,0.7865]` (200 groups), answerable `[0.6666,0.6666]` (160), no-answer `[1.0,1.0]` (200), raw `[1.0,1.0]` (160), causal `[0.0,0.0]` (160), nuisance `[1.0,1.0]` (200). Empty/missing strata return `insufficient_support` with `value:null` (tested: empty input, no-answer-only, answered-empty); never `0/0→0`. No post-hoc acceptance threshold; verdict is mechanical integrity, not promotion. **Pass.** |
| M15a-6 Diagnostics | DEV-only actual-runtime replay `crates/sdm-experiment/src/m015a.rs` (`M015aReplaySpec` deny-unknown-fields, SHA-before-inference, DEV-only, empty-test-required, atomic no-overwrite) via `sdm experiment m015a-replay`, orchestrated by `scripts/analyze_m015a_final_actions.py` over all three frozen heads. Sidecars `target/m015a/typed-choice.sidecar.json` (`b7713bd6…`, 11,622 B), `typed-choice-cross.sidecar.json` (`556fa158…`, 11,638 B), `typed-choice-compositional.sidecar.json` (`4122623c…`, 11,652 B), summary `m015a-summary.json` (`68014281…`, 25,417 B) carry generator/spec/dataset/split/artifact/source SHAs, census, per-family/support/effect tables, legacy glossary labeling old `dev_counterfactual_correct_on_both` as **mixed raw/final**, output bytes/digests, deterministic reruns. Old 1.0 conditional values remain correct as raw. `docs/m015a-evaluation-erratum.md` (`6a597258…`) binds sources/labels/counts/digests separately. No retuning, no M016 benefit, M015 history intact including negative/indeterminate downstream. **Pass.** |
| M15a-7 Compatibility | Historical artifacts/reports/encodings, Choice 2..128 rule, runtime/trainer graphs unchanged: `cargo check -p sdm-runtime`, `cargo tree -p sdm-runtime` show no training/Python/GPU/network; `sdm-check-compat` 12 fixtures / 11 executions pass; standalone consumer `cargo check` passes; 12 frozen CodeGG fixtures/11 executions + consumer pass recorded. No new runtime architecture, no release tag, no crates.io/CodeGG pin change. **Pass.** |
| M15a-8 Closure | Rust 1.89 + normal Rust/Python verification below plus ordered CI (`pure→gen→dependent` + `check_m015a_ci_order` regression); reviewed PR + merged-main CI still pending (hence closing, not closed). This file + registry/roadmap/M016-gate update complete. M016 unblocks only after reviewed merge, merged-main CI, closure acceptance, demonstrated fail-closed v2. **Conditionally pass (engineering done, integration pending).** |

## Immutable run identity and revised results

- Evidence run: `target/m015-baselines-v7/` (ignored) + new `target/m015a/` (ignored).
  Replay configs `target/m015a/*.m015a-replay.json` bind dataset/split/artifact/
  corpus/generator/spec SHAs; outputs refuse overwrite of differing digests.
- Revised DEV (all three heads identical): final `0.777777…`, answerable-final
  `0.666666…`, false abstention `0.333333…`, coverage `0.666666…`, raw `1.0`,
  answered-selective `1.0`, no-answer `1.0` (origins `80/40` + `160/160`),
  causal both-final `0.0/160`, nuisance both-final `1.0/200`, families as above.
  Row-averaged v2 answerability Brier `0.11732649` / log-loss `0.32104607` / ECE
  `0.05251996` vs legacy group-averaged `0.1055939` / `0.289023` / `0.0471949`
  (averaging convention documented, not a runtime change); conditional NLL/Brier
  identical to legacy.
- Historical 1.0s retained as mixed/raw meanings with glossary; no silent
  reinterpretation.

## Verification run (local, this branch)

Host: `Darwin 25.6.0 ARM64_T6041 x86_64`, `rustc 1.89.0 (29483883e 2025-08-04)`,
`aarch64-apple-darwin`. All commands executed; no claims from planning text:

```text
cargo fmt --all -- --check                                    PASS
cargo test --workspace --all-features --locked                PASS (8+6+12+16+4+7+3 = 56 Rust tests; sdm-eval 12 incl 8 new v2, sdm-experiment 16 incl 2 new m015a)
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings  PASS
cargo check -p sdm-runtime --locked                            PASS
cargo tree -p sdm-runtime --locked                             PASS (no training/Python/GPU/network)
cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked  PASS
cargo run -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json  PASS (12 fixtures, 11 executions)
python3 -m unittest discover -s scripts                            PASS (182 tests, 2 host-specific skips; incl 7 new test_m015a_final)
python3 -m unittest discover -s scripts -p 'test_m015_*.py'           PASS (10 tests; historical M015 suite)
python3 -m unittest discover -s scripts -p 'test_m015a_*.py'          PASS (7 tests; v2 contract)
python3 scripts/check_m015a_ci_order.py                            PASS (pure < baselines-gen < replay)
python3 scripts/check_m014a_ci_order.py                            PASS (existing order preserved)
python3 scripts/analyze_m015a_final_actions.py --out target/m015a  PASS (deterministic; 720/200, 200/160, 480 answerable; values above)
```

Additional required fixtures all pass in Rust (`sdm-eval::choice_final_v2::tests`)
and Python (`test_m015a_final.py`): false-abstention/mixed-counterfactual,
pair mismatch/absence (missing/duplicate/three-member/split-crossing/relabeled/
changed-context/mismatched-option/swapped-ID), context-only impossibility,
nuisance double-abstain disambiguation, group-bootstrap nondegeneracy + sorted
determinism, empty-stratum `insufficient_support`. DEV-only E2E deterministic
rerun verified (second run identical digests). CI canary ordering verified.

Hosted CI: local only at closure drafting. Branch CI must complete green and
receive review before merge; merged-main CI must pass after merge. These are
intentionally outstanding here.

## Integration and disposition

Engineering is complete on branch `work/plans-sdm-m015a-choice-evaluation-integrity`.
Historical inputs/outputs/closures preserved; new behavior is additive under a
new `choice-final-v2` / `sdm-m015a-dev-final-v1` contract with no runtime,
artifact, threshold, or dependency change.

- Compatibility: v1 LinearArtifact readable; typed `sdm-typed-task-v1`/cross/
  compositional artifacts byte-identical; 12/11 CodeGG fixtures + consumer pass.
- Storage/restart: content-addressed `target/m015a/` sidecars, atomic finalize,
  no-overwrite, interrupted runs leave no accepted partial; `target/m015-baselines-v7`
  never altered.
- Security/privacy: synthetic-only labels, no user/session/telemetry/network/
  external training; no SDM application/tool execution authority; hostile
  shapes/IDs/non-finite inputs fail closed.
- Migration: no artifact migration, no new architecture, no release tag, no
  crates.io/CodeGG pin change.
- Resources: baseline 2,000-group run ~4m26s / 58.6 MB / ~1.6 GB RSS (historical
  trainer evidence, not inference); v2 replay is inference-only over 720 DEV
  rows × 3 heads (seconds, ~11 KB sidecars + 25 KB summary); no new host
  requirement beyond Rust 1.89 + Python stdlib.

Open risks (severity):

- Low: row- vs group-averaged answerability calibration conventions differ
  (0.117 vs 0.105 Brier); documented with support, but a future consumer must
  pick one convention explicitly.
- Low: stale dataset line `bef4c9a8…` in frozen `docs/m015-dev-results.md`
  (actual v7 `f0d614db…`); preserved with erratum note, but readers must use the
  erratum ledger.
- Medium: merged-main CI/closure reconciliation for both M015 and M015a remains
  unverified until hosted runs complete; M016 must not start before then.
- None: no model-quality, promotion, publication, or consumer-policy risk is
  introduced; all new results are explicitly non-qualifying.

Disposition: **conditionally closed for engineering (M15a-1..8 locally pass);
integration pending**. No future plan is unblocked: **M016 remains BLOCKED**
until reviewed merge, merged-main CI, and accepted M015a closure with
demonstrated fail-closed v2 contract; **M017 remains BLOCKED** on M016 and its
own freeze; M005 deferred; crates.io human/legal-gated. This closure does not
promote any model or authorize publication/deployment.
