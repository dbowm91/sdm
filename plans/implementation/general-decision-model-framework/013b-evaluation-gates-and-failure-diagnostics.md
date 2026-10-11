# SDM M013b — Evaluation-Gate Integrity and Model-Failure Diagnostics Corrective

Status: **conditionally closed** — implemented and verified; hosted CI run [38107604379](https://github.com/dbowm91/sdm/actions/runs/38107604379) green on all 10 jobs; implementation commits `9f68b9b` (corrective) and `b1f196f` (CI fix) on `work/plans-sdm-m013b-quality-gates-diagnostics`. Closure evidence at `plans/closure/general-decision-model-framework/013b-status.md`. This file is retained as the implementation handoff of record and is not rewritten to reflect later results.
Class: infrastructure / evaluation-integrity corrective
Planning baseline: `dbowm91/sdm@694da1a002cf29c62724be6ba881240f43aac9c2` on `work/plans-sdm-m013-predictive-quality-corrective`; implementation agents MUST recheck live head and CI
Planning branch: `work/plans-sdm-m013b-quality-gates-diagnostics`; implementation agents branch from this registered planning commit and preserve prior history
Roadmap: `plans/subsystems/general-decision-model-framework-roadmap.md`
Governance: `plans/003-planning-process.md`
Architectural authority: ADR-0001, ADR-0002, CodeGG ADR-0013 for consumer-owned permissions
Predecessors (hard): M013 and M013a **conditionally closed** on the development branch, not merged into main
External gates: **none** for this corrective; no approved CodeGG corpus, teacher service, human data, publication or release approval
Closure destination: `plans/closure/general-decision-model-framework/013b-status.md`

> **Implementation outcome summary.** The historical "raw target margin changes sign" counterfactual statistic was confirmed to be a label-alignment artifact, and on real frozen pairs the corrected fixed-option metric reports zero input response where the old metric reported a sign flip. The positive-quality gate is now executable and fail-closed; the historical Choice verdict is indeterminate with 10 blocking mandatory gates, and Binary remains negative. Train/dev-only diagnostics isolated both root causes: a fit-constant note-token offset of `-13.4437` for Binary, and a truth-independent interaction offset that stops the Choice gap from ever changing sign for Choice. Two competing hypotheses were falsified. No model is qualified, no frozen input was modified, and no M013a test row informed any decision.

## 1. Objective and success definition

Restore trust in the M013a evaluation by fixing an invalid counterfactual sensitivity statistic, enforcing ALL preregistered positive-quality requirements as executable gates, recording a source-backed erratum for historic M013a reporting, and isolating Binary OOD and Choice selection/abstention failure hypotheses without evaluating new learned candidates against a seen held-out set.

Closure means **evaluation integrity and diagnostics are correct**, NOT that Binary, Choice, Rank or Score has achieved predictive qualification. Existing Binary text/combined shift evidence stays negative, Choice remains indeterminate/not qualified, and CodeGG M005 remains independently deferred. If diagnosis does not isolate the exact predictive failure, document a bounded next hypothesis, not an invented causal explanation.

## 2. Verified baseline and corrective triggers

At planning, `main@2bd0d5af16d143828dcbce77f411b8f3b675e7be` contains M012, while `work/plans-sdm-m013-predictive-quality-corrective@694da1a002cf29c62724be6ba881240f43aac9c2` is six commits ahead and has passed hosted CI [38105560778](https://github.com/dbowm91/sdm/actions/runs/38105560778). No open PR exists. No main merge or crates.io publication should be inferred from green branch CI.

M013a validity/quality record: `plans/closure/general-decision-model-framework/013a-status.md`, `docs/m013a-protocol-v1.md`. The fresh paired corpus and OOD membership are mechanically valid; Binary train-prior Brier deltas: ID-a +0.2115, ID-b +0.2280, load +0.2207, text -0.2696, combined -0.2699. Choice legacy and cross each have 0.50 answerable final-choice accuracy (paired improvement 0.00); answerability AUROC 1.00 overall, no-answer recall 0.683 overall and 0 on text/combined OOD; 44/44/45 eligible answerable groups per OOD accuracy slice violate the frozen 50-group minimum.

**Defect A — misleading counterfactual metric:** In `scripts/analyze_m013a_quality.py`, the pair calculation uses `raw_logits[target_index] - raw_logits[other_index]`. Because `target_index` changes when the label flips, a fixed score vector [2,1] yields +1 then -1 for labels 0 and 1 even with NO model response. Thus reported 276/276 'raw target margin changes sign' cannot prove sensitivity. The 0/276 pairs with BOTH final decisions correct remains a separate observation; inspect its denominator and equality semantics, but do not erase it.

**Defect B — under-enforced positive quality gate:** The Choice classifier uses only the cross-minus-legacy paired final-answerable-accuracy confidence interval to assign positive. It computes the unsupported OOD slices and counterfactual behavior separately, without gating that positive verdict. The frozen M013a protocol requires favorable primary CI *and* support, counterfactual and critical OOD gates. The outcome happens to remain indeterminate, but an adversarial test could produce a false positive.

**Diagnostic unknowns:** Binary shift fails under unseen text despite unchanged synthetic truth rule; causal role of fitted vocabulary, confounding, input scaling and optimizer has not been isolated. The cross-coordinate Choice head is representationally capable on a unit truth table but failed to improve final decisions; separate option quality, score mapping, gradient/optimization and dev cutoff/abstention before proposing a fix.

## 3. Non-goals and hard boundaries

Do not modify M011/M013/M013a frozen dataset, split, protocol, outcomes, artifact, calibration, report hashes or the original closure interpretation in place. Do not refit, tune or reselect models on observed M013a **test** rows or claim replayed tests are unseen evidence. Do not implement new architecture, training policy, revised threshold, new prospective final corpus, CodeGG adapter, inference permissions, or M014's general ML work in M013b. No automatic PR merge, tag, crate publication, telemetry, downloads or user-data ingestion.

Preserve the v1 LinearArtifact and frozen 12/11 CodeGG compatibility, existing `sdm-typed-task-v1`, additive `sdm-typed-choice-cross-v1`, artifact schema and fingerprints. Keep CPU-only/runtime-only graph free of sdm-training, remote IO and GPU dependencies; retain Rust 1.89 and Linux x64/ARM64 and macOS ARM64 verification. Strict bounds on finite weights/probabilities, serialized coordinates, options, memory and 4,096 cross terms remain.

## 4. Ordered work packages

### A. Correct causal sensitivity and target correctness metrics

1. Extract pure, deterministic functions from `scripts/analyze_m013a_quality.py` into a versioned evaluator, leaving historical M013a analyzer and archived outputs reproducible. Pair rows by `leakage_group`/`counterfactual_pair`, validate cardinality=2 and matching schema, fixed option-ID set and physical candidate identity mapping, and explicitly orient before/after by the causal `active` field rather than report order.
2. Compare the SAME option identity across both inputs: per-option delta logit and probability; identity-normalized argmax changes; answerability probability shift; abstention transition; final decision change; correct-target before/after and *both-correct*; no-answer and conditional option metrics remain distinct. Preserve separate *target-relative margin* only as a **label-alignment** metric, NOT proof of input sensitivity. Do not rely on array index across reordered options, group IDs or labels as the candidate identity.
3. Include stable tie handling, epsilon for numeric near-equality, score-range/finite checks and proper denominators; reject absent/mismatched option IDs, inconsistent projection roles, duplicate pairs, empty probabilities, non-finite results or malformed group data explicitly. When the pair's target is None, count appropriate abstention/answerability behavior but exclude from answerable target-correctness denominator.
4. Tests MUST prove: unchanged logits + swapped target => zero input response although target-relative margin sign changes; true logit response => detected; option-list permutation yields identical ID-normalized comparison; threshold-only abstention changes separate from raw option changes; absent, duplicate, tie, malformed and unanswerable cases have deterministic safe results. Assert that a metric cannot report successful counterfactual responsiveness merely because labels differ.

### B. Make preregistered positive-quality gates executable and fail closed

1. Introduce pure evaluator acceptance logic with a versioned protocol/threshold source and machine-readable per-gate `pass/fail/insufficient_support/invalid`, including evidence count, exact threshold, reason and overall task verdict. **Invalid** when required inputs, integrity or provenance are corrupt; **negative** for preregistered supported critical regression; **indeterminate** for missing precision, unsupported slices or absent predeclared quantitative success threshold; **positive** ONLY if the favorable paired primary CI and every mandatory support, negative-control, OOD, correct-counterfactual, answerability/abstention and calibration gate passes. Document priority and conflicting gates. An empty/missing gate array must never pass through vacuous `all()`.
2. Preserve M013a's frozen numeric protocol rather than adding favorable post-test thresholds; if its counterfactual/critical OOD positive criterion lacks a frozen numerical threshold, explicitly mark that positive eligibility cannot be established retrospectively. Later gates can be richer only if they are frozen **before** a distinct future test.
3. Count support with independent leakage-group units *in the eligible population for the exact metric* (Choice answerable accuracy >=50 answerable groups in each required slice; >=20 independent no-answer groups for its recall). Do not substitute 67 total OOD groups when answerable support is only 44/44/45. Bootstrap paired group means (10,000 replicates, deterministic seed 14014) with unchanged M013a protocol; preserve primary effect sizes and intervals.
4. Enforce full case-ID and group alignment between legacy and cross reports; valid fixed candidate option IDs and conditional log-loss/Brier; the conditional option scores may exist on abstentions, but correctness must be from actual runtime answers with abstention counted as error for the frozen primary metric. Require negative controls (constant, majority, always-abstain, shuffled) not to qualify as learned improvements.
5. Adversarial unit tests: favorable CI + low OOD support => never positive; favorable CI + zero counterfactual both-correct => never positive; missing mandatory OOD result => invalid; always-abstain + perfect no-answer recall => never positive; significantly negative Binary text shift => negative; exact-support boundary 49/50 and 19/20; explicit sufficient data, truthful improvement and all frozen gates => positive on a **constructed** fixture; stable abstention/coverage calculations and unsupported/empty CI => indeterminate.
6. Recompute a named M013a audit/erratum *sidecar* from unchanged saved reports where available. Include old field, why it is misleading, corrected fixed-ID sensitivity, gate-by-gate verdict and SHA of inputs and evaluator. Explicitly label this as a post-hoc semantic clarification, not new held-out quality or selection evidence. Never modify historical M013a report/artifact/dataset SHA ledger.

### C. Perform bounded root-cause diagnostics without test-set reuse

1. Binary: from source and fitted train/dev-only data, inspect active/available Boolean fit, fitted token vocabulary coverage, per-coordinate weight contributions, note-vs-label spurious correlation, and numeric load scaling. Run deterministic train/dev-only **label-preserving** one-factor probes that change only unseen text or load, and their combination, computing probability/logit and abstention deltas stratified by label and fitted-feature coverage. No diagnostic run uses labels or scores from M013a held-out examples to choose a new model.
2. Choice: reconstruct separate conditional option logits/probabilities, answerability scores and final thresholded decisions for *constructed* four-quadrant context x rule x option-role truth tables and approved train/dev examples. Confirm whether the rule-family x active x option-role interaction can be expressed AND optimized; analyze training/dev loss, split order, gradients, class balance, ID/role permutation and threshold-distribution shift. Distinguish wrong argmax from correct argmax suppressed by abstention. Explicitly test the case that the target changes but neither fixed-option logit nor top-1 changes.
3. Limit any experimental fit to deterministic dev-only diagnostics or **new exploratory train/dev-only synthetic data**. No frozen M013a test feedback may guide feature masking, regularization, architecture, cutoff or hyperparameter choice. Record competing hypotheses and what evidence would falsify each. If no root cause is established, document "unresolved" and STOP further tuning.
4. Summarize ONE bounded next prospective model-quality experiment, if warranted, specifying candidate remedy categories (e.g. Boolean-vs-text nuisance regularization; Choice interaction/optimizer diagnostics; answerability threshold robustness), train/dev selection budget, a NEW independent frozen test seed/family groups, prospective support counts and uncertainty gates. Merely writing this recommendation does not register M013c/M014 as ready.

### D. Reconcile planning, package/CI and future freeze safeguards

1. Fix current-facing contradictory statuses in `plans/registry.md`, subsystem roadmap §10, `plans/README.md`, and README. M013/M013a are conditionally closed; M013b is ready/active/closed only with evidence; M012 PR #1 is merged into main but its crates.io legal-review gate remains; CodeGG M005 remains externally deferred. Existing M013 stack is NOT merged to main.
2. Add a pre-freeze support validator for *future* protocols: eligible answerable groups, no-answer groups and other required slice populations must meet preregistered support independently. The original M013a hash-only validator may be retained for exact history; new validation must not silently reclassify old frozen cohorts.
3. Reuse the hosted CI Rust 1.89 and 3-target matrix, frozen M011 Linux SHA guard, M013a regeneration/split verifier and cross-artifact portability. Add quick evaluator-specific tests and changed-source checks without invoking another expensive held-out model-selection loop. `cargo package --workspace --locked --no-verify` plus staged unpacked independent consumer remains the accurately documented publication candidate check; do not assert a crates.io registry publish is complete.
4. Prepare a reviewable main-targeted PR containing the existing M013/M013a stack plus M013b corrective after verification. Review the large checked-in generator fixtures as a nonblocking storage/packaging consideration; do not rewrite immutable fixture identities to reduce repository size. No automatic merge/release/tag/publish or CodeGG pin change.
5. Write exact implementation SHA(s) and evidence in `plans/closure/general-decision-model-framework/013b-status.md`. Update the registry to closing/closed **after** evidence is collected, not before.

## 5. Failure, cancellation, restart, security and compatibility

Diagnostics are read-only with respect to frozen inputs. Write new reports only under unique versioned `target/m013b/` (or checked-in **erratum** notes referencing unchanged source hashes), stage to a temporary path and validate/atomically rename; failed/interrupted runs cannot leave "accepted" partial evidence. Replay requires unchanged exact source/config/protocol/dataset/split/artifact hash identities. On malformed report schema, missing gate, ambiguous option identity or NaN/Infinity: reject/invalid, no best-effort coercion. Default old report serialization, artifact dispatch, training runtime, option admission, caller policy and offline privacy remain unchanged. No external CodeGG/user content, secret, network call or teacher is permitted.

## 6. Verification / required test matrix

Run and RECORD actual results, never preclaim CI or local success:

- Focused deterministic Python unit tests under `scripts/test_m013b_*.py`, e.g. `python3 -m unittest discover -s scripts -p 'test_m013b_*.py'`; constructed adversarial counterfactual and gate fixtures must run without training
- `python3 scripts/validate_m013a_freeze.py` with unchanged historic corpus/split digests, plus a new future-only **eligible-subgroup** support test
- `python3 scripts/check_m011_frozen_reports.py` after Linux x64 frozen suite regeneration; hash-check baseline identities
- New read-only retrospective M013a sidecar invocation after CI regeneration; verify SHA of all source reports and preserve original M013a negative/indeterminate disposition
- `cargo fmt --all -- --check`
- `cargo test --workspace --all-features --locked`
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`
- `cargo check -p sdm-runtime --locked`; `cargo tree -p sdm-runtime --locked`
- `cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked`
- `cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json`
- Hosted Rust 1.89 job, Linux x64/ARM64 and macOS ARM64 jobs, exact Linux-trained nonlinear and cross-Choice artifact portability, frozen SHA checks, staged package consumer and license/package audits
- Any existing M013a CI evaluation rerun is for **mechanical regression only**, not independently held-out quality evidence.

## 7. Explicit acceptance and stop gates

Accept M013b only with: (a) target-independent fixed-option sensitivity tested against swapped labels and option permutations; (b) positive quality verdict impossible when ANY mandatory, missing or underpowered gate fails; (c) unchanged historical Binary negative / Choice indeterminate and intact artifact/report hashes; (d) clearly sourced, bounded train/dev-only Binary/Choice diagnostic findings; (e) default ABI/inference and security/privacy invariants preserved; (f) reviewable integration handoff and accurately reconciled docs/registry; (g) separately identified outstanding crates.io and CodeGG external gates.

STOP and record blocked/negative if old reports or test protocols are modified, fit uses M013a test feedback, a gate can return positive with incomplete/miscounted support, group leakage exists, model behavior or v1 ABI silently changes, CI/MSRV/host portability fails, or report digests/identity cannot be reconciled. Do NOT relax quality gates to obtain a pass.

## 8. Closure and successor registration

Produce `plans/closure/general-decision-model-framework/013b-status.md` with source/merge-base and PR SHAs, implementation requirement-to-evidence matrix, CI URLs/commands/outcomes, old/new counterfactual example proof, per-gate adversarial tests, source/protocol/model/report hashes, retained negative/indeterminate synthetic metrics, explicit hypotheses/falsification table, resource/compatibility/operational/security/privacy audit, source merge status and remaining limitations by severity.

Only after M013b is mechanically closed should a new plan register any next independent predictive experiment (M013c) or generalized architectures (M014). Its data/protocol must be prospectively sealed with eligible support verified BEFORE any new final inference; no old M013a test cases are qualification-eligible. No CodeGG model promotion, release/publish or automatic merge is authorized.
