# SDM General Framework M003 — Semantic Evaluation and Preregistered Qualification

Status: conditionally closed (semantic metrics and frozen identity protocol implemented; confidence intervals and calibration reporting remain follow-up)
Primary class: capability
Repository baseline at planning: dbowm91/sdm@8139b064bdcf3212e8f6fd912e801a479b55751c; re-audit when ready
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md#m003--semantic-evaluation-and-preregistered-qualification
ADR: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Hard dependency: M002 closed with frozen dataset and split identity
Interface dependencies: M001 stable semantic/runtime evaluation API; fake scored predictions for unsupported local semantics
Output consumers: M004 architecture qualification, M005 first CodeGG experiment

## 1. Objective

Separate evaluation and qualification from training, support all four semantic families without claiming their inference implementations exist, and make positive/negative outcomes testable under precommitted protocols. Introduce sdm-eval, independent of sdm-training, and a machine-readable report with source/artifact fingerprints.

## 2. Evidence and deficiencies

The current sdm-training::evaluate returns only (correct,total) candidate classification. train() uses seed/group buckets, dev threshold search and held-out test counts but does not expose an independent ranking/abstention/calibration qualification harness. Prior CodeGG contextual architectures passed correctness yet failed MRR, unknown-tool, counterfactual, no-tool and shortlist recall gates. Some prior calibration improved dev scores but worsened test abstention. A qualified protocol therefore must separate policy/mechanics, predictive quality, and task success.

## 3. Invariants

- Only train is used to fit weights and model representations; dev is used for hyperparameter/threshold/calibration choice; test is read *after* the frozen configuration/protocol checks pass.
- The evaluator is algorithm-neutral; may consume full output from a native SDM runtime, deterministic baseline adapter, or frozen prediction file with exact request/candidate identity validation.
- Metrics must state denominator/undefined cases, and must not present no-tool recall or absent positives as perfect performance by default.
- Each run verifies dataset, split, feature schema, artifact, model manifest, protocol and calibration hashes; mismatches abort before reading final labels.
- sdm-eval must not depend on sdm-training and sdm-runtime must not depend on sdm-eval. Reporting must not leak private projected state by default.
- Distinguish correctness pass, effectiveness verdict, and CodeGG/consumer deployment approval.

## 4. Expected implementation

- New crates/sdm-eval: PredictionSet + validated decision-semantic adapters; prepared score/abstention events; metrics and reporting. Keep existing sdm-training::evaluate as a compatibility wrapper, with tests proving unchanged v1 classification counts.
- Rank: MRR, recall@k with candidacy ceiling, precision/recall/F1 for relevance, NDCG with graded labels (when available), unknown/renamed and family-excluded slices, multi-relevance and zero-relevant cases. Normalize ranking-score order/ties and candidate identity deterministically.
- Binary: confusion metrics at dev-selected threshold, Brier/NLL/ECE (binning and bin counts declared), class prior and abstention coverage/risk. Choice: accuracy, top-k, log loss/calibration only where a complete valid probability distribution is provided; Score: MAE/RMSE/ordinal/rubric agreement under legal scale. Unsupported local semantics can be tested via fake validated predictions; do not pretend an inference head exists.
- Selectable preregistered protocol: fixed datasets/partitions, candidate sets, baseline set, metrics/gates, confidence intervals and correlation grouping, resource targets and source revision. Once frozen, no changes to thresholds after looking at final-test failures; follow-up requires new manifest and genuinely fresh test.
- Report: explicit pass/fail/indeterminate per gate, benchmark comparison and metric confidence intervals where sample size supports them, warnings for low-count/undefined slices, counts/fingerprints, model applicability, performance/abstention tradeoff, platform metadata and logs redaction. Resource footprint is a separate field from predictive quality.
- Host-owned decision policy not embedded in reusable metric library. Provide a declarative qualification-policy input rather than declaring a positive model universally safe.

## 5. Ordered work packages

A. Define prediction/label alignment, ranking tie resolution, abstention and no-answer semantics, and metric denominator policy using reviewed golden fixtures.

B. Implement generic metrics for Binary/Choice/Score/Rank, with negative cases (no relevant, no option, partial probability vector, non-finite scores, duplicate candidates). Ensure a Score rubric range is respected, not converted to Binary.

C. Build pre-registered frozen evaluation protocol, digest gates and restricted test-label read ordering. Write protocol mismatch tests and a test that changes a calibration value to prove rejection.

D. Implement dev-only threshold/calibration fitting interface for later training clients; evaluate test with immutable chosen parameters. Report Brier/NLL/ECE by slice and annotate sparse abstention data.

E. Add deterministic baseline scoring adapter (lexical/BM25 where supported via an explicit implementation or imported frozen scores), model-to-model comparison on identical input and candidate coverage ceiling. Distinguish preselector recall from Rank conditional-on-shortlist recall.

F. Generate reproducible human + JSON report on a synthetic non-CodeGG case suite; ensure clear negative verdict for a deliberately bad model and positive only where precommitted gates are met.

## 6. Failure, privacy and contention

No network/teacher calls. Fail fast for missing prereg manifests, train/dev/test contamination, artifact identity drift, invalid per-task scoring semantics and tampered label files. Never cache final labels in a modifiable training config. State is read-only, reports written atomically, and reruns with same input fingerprints produce identical logical verdict (excluding timing). Correlated examples must not be treated as independent in bootstrap/interval calculations. Metrics with insufficient n must be indeterminate, not spuriously green.

## 7. Verification

- Test numerical references for MRR, graded NDCG, F1, Brier, ECE and log loss; adversarial multiple positives, ties, negative scores, NaN, high class imbalance and all-abstained.
- Golden model-metric compare, same-candidate identity verification, threshold/fingerprint-tamper abort, held-out split integrity, repeat runs of negative verdict.
- Run cargo fmt --all -- --check; cargo test --workspace --locked; cargo clippy --workspace --all-targets --locked -- -D warnings; cargo check -p sdm-runtime --locked; cargo tree -p sdm-runtime --locked; legacy sdm-check-compat.
- Add documented CLI command (sdm-eval or sdm-qualify) for independent offline JSON reports. Do not name commands as existing until implemented.

## 8. Acceptance

An independent consumer can evaluate fixed predictions for every semantic family, can fail unqualified models honestly, can compare baselines under a single immutable protocol, and can prove that test data was not used for training/calibration. v1 score/count behavior and CodeGG fixture shape remain compatible. Non-CodeGG evaluation data is sufficient to demonstrate portability.

## 9. Stop conditions

Stop on rank-vs-choice conflation, leaking test cases into dev selection, hidden baseline candidate-set changes, undefined metrics reported as success, a mismatch that only passes by relaxing frozen gates, or a trainer/runtime dependency cycle. Do not permit automatic promotion as a consequence of this evaluator.

## 10. Closure evidence

plans/closure/general-decision-model-framework/003-status.md: SHAs, metric golden proof, protocol manifest and fingerprints, negative and positive synthetic examples, contamination and tamper tests, host limitations, dependency graph, compatibility results, confidence limitations, and registry update. Unblocks M004 only after satisfactory closure.
