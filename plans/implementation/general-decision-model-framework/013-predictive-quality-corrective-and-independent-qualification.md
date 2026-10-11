# SDM M013 — Predictive-Quality Corrective and Independent Qualification

Status: ready (planning only; no implementation or model promotion performed)
Class: capability / evidence corrective
Planning baseline: dbowm91/sdm@2bd0d5af16d143828dcbce77f411b8f3b675e7be; implementation agent must re-audit HEAD and main CI
Work branch: work/plans-sdm-m013-predictive-quality-corrective
Governance: plans/003-planning-process.md
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md
Architecture: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md; ADR-0002-standalone-framework-before-consumer-qualification.md
Evidence: plans/closure/general-decision-model-framework/011-status.md; plans/closure/general-decision-model-framework/012-status.md; docs/m011-local-results.md; docs/m013-quality-diagnostic-baseline.md
Hard prerequisites: M010/M011 closures; M012 integration already merged into main at this planning baseline
External operational gates: no CodeGG dataset, provider service, external teacher, network access or legal publication clearance required
Parallel work: M014 broader generic architectures is future research, not a dependency or permission to expand this pass

## 1. Objective and success boundary

Diagnose and correct the demonstrable limits of the current typed Binary and Choice models, including the negative Binary OOD Brier result and Choice's complete failure to respond to target-flipping synthetic counterfactuals. Build an independently frozen and repeatable quality-qualification experiment that separates model representability, optimizer behavior, calibration/abstention, distribution shift, and benchmark construction.

The milestone succeeds as an HONEST model-quality corrective only when it produces reproducible diagnoses, bounded and backward-compatible improvements or rigorously documented negative findings, and preregistered evaluations that report unfavorable outcomes without changing gates. A new model artifact is not production-approved merely because a synthetic quality gate passes. If quality does not improve, close as negative/indeterminate with exact blockers and register a separately scoped successor; do not describe that as positive quality closure.

## 2. Baseline and hypotheses, not yet proven root causes

M011 frozen v2 qualification: Binary overall Brier improvement +0.0045, group-bootstrap 95% CI [-0.0643,+0.0704], OOD improvement -0.2589 [-0.2825,-0.2356]; Choice answerable accuracy delta 0 [0,0], no-answer recall 8/22, and 0 prediction changes across 35 target-changing counterfactual pairs. Choice OOD and no-answer slices were underpowered, and M011 is now a *seen* test; neither its seeds, data nor metrics may be reused for selecting new architectures or thresholds.

Concrete code hypothesis: crates/sdm-experiment/src/lib.rs typed_task_vector uses [context, option, context[i]*option[i]] for Choice; crates/sdm-runtime/src/lib.rs reconstructs the same diagonal interactions. The M011 generator copies a shared active/available/load projection into BOTH options and varies their task_kind category. The context task_kind is choice while the candidate category is yes/no. The target needs a context-active × candidate-kind cross-coordinate term, which this diagonal-only projection does not encode. Separability may therefore make the observed flip unattainable irrespective of epochs. Prove this with finite-difference score tests and a tiny four-quadrant truth table before choosing a fix. Also verify candidate identity, feature schema ordering, dev threshold, and whether the observed 0/35 refers to final decisions versus unthresholded option probabilities.

Binary is a logistic head trained without explicit regularization/early stopping; M011 OOD simultaneously changes load range and text tokens although its Boolean target rule stays fixed. Possible nuisance-feature sensitivity, extrapolation, representation bias or calibration must be isolated by one-factor ablations. Do not infer covariate versus label shift from the OOD name: inspect the actual generator and conditional label mechanism. Training loop uses deterministic in-order SGD and a seed argument that is currently unused; assess reproducibility and ordering separately from quality.

Observed artifacts, protocols, scripts, frozen v1 and M011 fixture SHA identities are immutable historical evidence. No rewriting old reports, retroactive thresholds, or relabeling failures.

## 3. Ownership, invariants, dependency readiness

SDM owns data provenance, offline model training, fixed candidate/option semantics, typed feature encoding, artifact validation, runtime inference, and qualification. CodeGG retains tool admission, provenance/consent, safety policy, fallback, actuation, and consumer effectiveness; M005 remains deferred until a provenance-approved independent corpus exists. The M013 implementation can start with entirely standalone synthetic data.

Keep legacy LinearArtifact v1 and preexisting v2 artifact load paths byte/behavior compatible. Any new Choice cross-feature form needs an ADDITIVE architecture identifier and explicit validated payload/feature contract; do not silently reinterpret existing sdm-typed-task-v1 weights, its 3*D shape, or frozen calibration policy. Preserve exact provided option IDs and ordering-independent decision semantics. Never permit a decision to invent candidates or grant execution permission. No implicit collection, downloads, external teacher calls, GPU/runtime optimizer dependency or broad new model platform.

Keep per-architecture strict limits on input bytes, features, terms, weights, finite values, compute, and candidate count. Maintain Rust 1.89 MSRV, runtime-only dependency independence, x86_64/Linux ARM64/Apple Silicon CPU support and offline-only loading.

## 4. Ordered work packages

### A. Forensic reproduction and representability tests — MUST PRECEDE optimization

1. Pin source/toolchain/host, verify recent main CI, rerun exact archived M011 fixtures *for reproduction only* and record model/artifact/protocol fingerprints and observed negative outcomes unchanged. Create M013 diagnostic outputs under target/; do not overwrite checked-in fixtures or reports.
2. Add narrow unit/integration diagnostics: Choice option logit differences and option probabilities with identical candidate set under active false/true; answerability logits/thresholds; per-example raw probability, final selected option, abstention and eligibility. Distinguish no-answer failures from wrong-option failures.
3. Construct an independent minimal two-option truth table with context active false/true, available true/false, option identity yes/no and controlled candidate projections. Establish analytically and in code whether the legacy diagonal interaction head can express the target mapping; test invariance to option order, option ID relabeling, identical features and schema permutation. Do not present hand-inspected M011 tests as future holdout evidence.
4. Binary diagnostics: freeze baseline prediction vectors, plot/report residuals by true Boolean label, load bins, text vocabulary coverage, OOD family, and group; run controlled transformations that change only load, only note, and both while leaving target unchanged; assess numeric encoder extrapolation (center/max-absolute scale, [-5,5] clip), spurious feature weights and calibration. If the measured failure is not explained, record it as unresolved rather than selecting a convenient cause.
5. Produce a concise root-cause decision record with falsifiable evidence and a fix/no-fix decision BEFORE training a new final candidate. No change to production runtime in this phase.

### B. Minimal representation and learning corrective (Choice and Binary separately)

1. Implement the smallest justified repair for Choice: first validate representability; if diagonal interactions are the defect, add explicit bounded context-coordinate × option-coordinate crosses or an equivalently bounded candidate-conditioned representation. Predeclare allowed feature-coordinate pairs; avoid an unbounded dense D×D expansion of text vocabularies. Use deterministic ordering, shape checks, stable softmax and strict term/tensor/byte limits. An illustrative budget is at most 4,096 declared cross terms subject to existing tighter artifact/parameter caps; adjust only via measured, documented architectural limits.
2. Give the corrected model an additive architecture/model contract (for example sdm-typed-choice-cross-v1), a corresponding explicit experiment selector, and matching training/runtime feature constructors. Keep the old sdm-typed-task-v1 Choice loader and its artifacts operational. New payloads encode cross-coordinate specification, version, feature-schema digest, finite weights, and provenance; malformed/mismatched or oversized coordinates fail closed. Verify that shared context-only contributions cancel from option softmax as expected and cannot masquerade as cross-item interactions.
3. Add a positive control capable of learning the four-quadrant Choice rule on train/dev, a feature-shuffle negative control, an option permutation/metamorphic test, and a controlled counterfactual test on BOTH raw probabilities and final decisions. Record convergence curves and train/dev loss with immutable configuration; separate representability from optimizer failure. If a smaller feature-contract change is sufficient, document why and preserve the additive compatibility boundary.
4. For Binary, isolate the actual failure before changing training. Compare the current head with simple dev-selected regularization/early stopping, nuisance-feature exclusion or constrained feature handling ONLY when those strategies follow the diagnosis. Keep the same bounded logistic baseline and preserve artifact provenance for optimizer/configuration choices. Do not hardcode an OOD-family string, label rule, or test-set-specific parameter to force success. No broad MLP/transformer framework belongs in M013.
5. Confirm finite-difference numerical behavior, stable sigmoid/softmax, deterministic training with explicit seed semantics, non-finite/overflow rejection, strict schema identity, candidate limits and artifact size ceilings. Do not weaken v1/v2 parser validation or broaden the runtime-only dependency graph.

### C. Choice abstention and calibration semantics

1. Treat (a) answerability probability, (b) probability over provided options conditional on being answerable, and (c) final abstained/answered decision as separate outputs with coherent report identities. Keep Choice(None) excluded from option log-loss, but included in answerability, no-answer and risk/coverage metrics.
2. Audit the dev threshold selector in train_typed_task and the runtime answerability cutoff; preregister any replacement calibration/selection policy using ONLY the dev partition. Do not force a target recall of 0.95 by changing test-dependent thresholds. A changed serialized policy gets a new validated policy/version; old artifacts retain old semantics.
3. Report answerable accuracy, conditional choice log-loss/Brier (where mathematically defined), answerability AUROC/PR where support exists, no-answer recall, false abstentions on answerable cases, overall coverage, selective error/risk at coverage and risk-coverage curves (AURC where well-defined), plus calibration by family/slice. Give confusion/support counts and cluster-aware intervals. Always-abstain and always-answer controls must not be credited as successful selection models.
4. Ensure evaluations use ACTUAL runtime decisions rather than threshold-free option probabilities substituted for abstaining predictions. Record both scores and final decisions and avoid double-counting abstentions as correct.

### D. Independent M013 quality corpus and preregistration — FROZEN BEFORE FINAL TEST

1. Add a new clearly named M013 suite (new generator version, seed, IDs, groups, schema/configs, provenance, protocol and split manifests). Keep every M011 v2 file and metric frozen; M011 is retrospective diagnosis only. Generate at least two structurally distinct truth-function templates, not only resamples of the M011 template, with balanced Choice yes/no and sufficient no-answer cases. Prevent an option-ID or input-order shortcut from solving the task.
2. Separate ID, nuisance-only load shift, nuisance-only text shift, combined nuisance shift, option/category permutation, and genuinely changed rule/structural OOD (if implemented). Define which shifts preserve the conditional target and which require a new decision rule. Counterfactual pairs change one causal field, remain in one leakage group/partition, and are counted once in clustered uncertainty. Ensure train/dev/test/family holdouts have disjoint groups; no test-only vocabulary/labels enter the fitted encoder.
3. Predefine test sizes from independent GROUP counts, not raw paired rows. Minimum 50 independent groups per declared primary ID/OOD slice and at least 20 groups per no-answer slice, with stratified class/answerability support; if unsupported, mark that slice indeterminate. Use a preregistered fixed number of bootstrap replicates and confidence interval definition, with deterministic seeds. Track class balance, group counts, excluded families and integrity hashes in a machine-readable manifest.
4. Before running FINAL held-out inference, commit generator and generated membership files and a frozen protocol specifying candidate architectures, budgeted hyperparameter search space, dev selection rule, exact primary metric and baselines per task, paired uncertainty, necessary counterfactual behavior, OOD slices, fallback/no-answer policy and positive/negative/indeterminate criteria. Record the freeze SHA separately. Implementers may iterate only on train/dev; after test is observed, no more selection against that same partition. A failed fresh test is a reported failure; any subsequent attempt requires a new independently sealed future test and a named follow-up milestone.
5. External real-world datasets are OPTIONAL, never fetched implicitly or treated as a closure prerequisite. If used, require an explicit version, permissive redistributable license or approved local-only non-redistributed process, provenance/consent, no sensitive user content, fixed task semantics, independent holdouts and recorded audit. No CodeGG corpus is needed.

### E. Paired quality analysis and CI evidence

1. Compare original Binary/Choice heads, the narrowly corrected candidates and declared simple baselines on identical splits, schema/eligible option sets and metric definitions. Use train-prior/constant and legacy logistic for Binary; train-majority, always-abstain, context-only, legacy diagonal and corrected interaction head for Choice. Where no-answer cases exist, report their contribution separately. Negative controls must fail positive quality qualification on feature-dependent cases.
2. Evaluate true-label and predicted-decision counterfactual sensitivity, but do not define 'prediction changed' alone as correctness. Record whether the CORRECT target was selected after flipping, with and without abstention. Test label-preserving nuisance invariance in Binary and OOD sensitivity. If an architecture passes ID but fails a designated critical OOD slice, the overall predictive-quality verdict is not positive.
3. Use paired group bootstrap confidence intervals on per-group metric deltas (95% CI) and preregister positive only if the primary improvement interval excludes zero in the favorable direction and all required support/behavior gates are met; negative if significantly worse or a preregistered critical failure occurs, otherwise indeterminate. Report raw effect sizes and intervals, not only pass/fail. Secondary metrics and any multiplicity/selection effects remain visible. Never gate on test-selected hyperparameters.
4. Preserve reports in target/ with dataset/split/protocol/feature/model/calibration/artifact/code commit digests and per-case diagnostics appropriate for synthetic-only data. Add new M013 scripts/configs and CI jobs without replacing historical M011 checks or their expected hashes. Cross-platform runtime tests and one trained artifact portability check run on Linux x86_64, Linux ARM64 and Apple Silicon; locally measured training timings on Apple Silicon are useful but not a training requirement for other platforms.
5. Benchmark cold load, artifact bytes, parameter/term count, process peak RSS, malformed rejection and p50/p95 under identical 1/16/64/128/256 candidate workloads where semantics permit (Binary remains single-context); compare to the appropriate M011/M012 baseline with host/compiler/workload caveats. Measure memory/time impact before approving cross-term budget. Rust 1.89 and runtime-only builds remain mandatory.

### F. Closure, documentation, and review handoff

1. Update docs/typed-task-heads.md, docs/artifact-format.md, docs/standalone-quickstart.md, README and the roadmap to reflect only actual implementation. Document old/new Choice architecture dispatch, new evaluation metrics, OOD limitations and unqualified artifact status.
2. Create plans/closure/general-decision-model-framework/013-status.md with exact implementation SHAs, observed CI URLs, source and protocol freeze SHAs, fixture fingerprints, root-cause evidence and alternative hypotheses, acceptance matrix, failure/negative controls, per-task effect sizes/group CIs, train/dev-only search record, resource/security/privacy/ABI review, and external publication/CodeGG gate statement.
3. Only after evidence is complete update plans/registry.md state from ready to closing/closed or conditionally closed as justified. If the corrective fails, document negative/indeterminate findings and register a bounded successor; no silent reopening/rewriting M011 or historical closure status.

## 5. Failure, interruption, rollback and storage requirements

No default promotion of model weights. All experiment outputs must be explicitly named, atomic or written to a staging path then verified and renamed, refusing overwrite of validated prior outputs; an interrupted experiment cannot leave an accepted partial artifact/report. Resuming is allowed only with identical code/config/dataset/split/protocol fingerprints or an explicitly new experiment identity. Malformed data, schema mismatch, duplicate candidate IDs, invalid indices or excessive cross-term counts return a bounded error. Keep default behavior loading old artifacts; if a new architecture is unavailable, report unsupported instead of coercing. Caller handles fallback and authority. No CodeGG dependency change, external service call, registry publish, branch auto-merge or release tagging.

## 6. Focused tests and broad verification

Run and record actual command/host output (do not preclaim success):

- cargo fmt --all -- --check
- cargo test --workspace --all-features --locked
- cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
- cargo check -p sdm-runtime --locked; cargo tree -p sdm-runtime --locked
- cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked
- cargo run -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json
- cargo package --workspace --locked; staged package consumer/license/manifest checks already required by CI
- Baseline M011 reproduction and NEW M013 diagnostic/quality CLI commands, named in documentation after they exist; historical fixture/digest comparison and held-out-only label mutation tests
- Targeted correctness tests for Choice cross-coordinate construction and serialization, option-ID permutation, context-active flip, no-answer/coverage, Binary one-factor nuisance OOD, encoder train-only fitting, malformed/oversize artifacts, and stable old v1/v2 artifact inference
- Hosted Rust 1.89 MSRV plus stable Linux x86_64, Linux ARM64 and Apple Silicon, same exact trained candidate artifact where applicable

## 7. Explicit gates and stop conditions

Mechanical pass: frozen M011 baseline remains reproducible, all legacy compatibility and artifact tests pass, new candidate inference/training agree, ID/candidate bounds and privacy are preserved, and an independent consumer can load the new supported architecture. Quality assessment: preregistered final held-out metric, slice support and counterfactual gates determine positive/negative/indeterminate separately for Binary and Choice. Report all outcomes; do not claim an overall positive quality corrective if a primary task remains negative or a critical OOD/counterfactual gate fails. Publication/legal approval and CodeGG M005 are explicitly out of scope.

Stop and register a new corrective if the intended task is unrepresentable with the proposed head, any train/test group leakage or post-test model selection is found, test corpus is insufficient for preregistered minimum support, old artifact compatibility breaks, runtime graph pulls in trainer/network/GPU deps, an unbounded interaction matrix is introduced, or source/protocol fingerprints cannot be reconstructed. Preserve the negative evidence.

## 8. Successor boundary

M013 repairs and qualifies the CURRENT bounded typed model line. M014, if later approved, may compare generalized MLP, bilinear/low-rank, tree and embedding architectures via a reusable training interface; do not build that generalized framework as an opportunistic M013 change. CodeGG M005 continues to wait on an independent approved corpus. M013 does not require M005, nor does it authorize a CodeGG pin change.
