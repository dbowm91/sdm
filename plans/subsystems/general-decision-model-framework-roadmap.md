# General Decision-Model Framework and First Consumer Roadmap

Status: M014c closed and merged (11/11 main CI); **M015 TinyChoice implementation active/incomplete**; M016 architecture/baselines BLOCKED on accepted M015 closure; M017 independent frozen synthetic qualification BLOCKED on M015/M016. M005 and crates.io separately gated.
Audit baseline: original historical audit at 8139b064bdcf3212e8f6fd912e801a479b55751c (2026-10-05); current TinyChoice planning baseline main@c048189d7026d723c7da584d7429cb275c714d23 (2026-10-13).
Planning date: 2026-10-10
Primary decisions: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md; plans/adrs/ADR-0002-standalone-framework-before-consumer-qualification.md
Planning governance: plans/003-planning-process.md
External ownership authority: CodeGG ADR-0013 (https://github.com/dbowm91/codegg/blob/main/plans/adrs/ADR-0013-external-decision-model-training-and-runtime-boundary.md)

## 1. Purpose and ownership

Develop SDM as a reusable small decision-model dataset, training, evaluation and inference framework, starting with CodeGG tool relevance as an independent *qualification target*. Applications own feature eligibility, security policy, permitted candidates, fallback and actuation. SDM owns generic request semantics, portable feature/schema and artifact formats, model/optimizer code, metrics and experiment evidence. CodeGG remains the source of canonical historical agent experiments, candidate-surface projection, consent and production qualification.

## 2. Current implementation evidence

At the original 2026-10-05 baseline, the MIT workspace comprised sdm-core, sdm-runtime and sdm-training at v0.1.0 (declared Rust MSRV 1.89). Core validates Binary, Choice, Score and Rank. Only Rank uses local learned inference via a sparse logistic relevance model with independently relevant candidates. JSON LinearArtifact schema v1 has a 4 MiB cap, 100k parameter cap and SHA-256 integrity/provenance. Training uses seeded group splits; evaluation reports only correct/total candidate predictions. Frozen CodeGG compatibility: 12 validated fixtures, 11 valid executions, contract-shape tolerance only; not a predictive-quality or promotion gate. Benchmark: 2,560-byte model, cold load 510 µs, p95 0.291/1.139/2.317/4.624 ms for 16/64/128/256 candidates on a recorded Rosetta host. Existing main CI is green, but it does not enforce complete qualification or multi-platform performance.

CodeGG negative predecessor evidence: the formerly tested contextual architectures failed the held-out gates against hashed linear and BM25 (see plans/closure/tool-selection-advisor-evidence-integrity-corrective/004-status.md in CodeGG). Initial SDM work must never claim to supersede that result without new independent evaluation.

## 3. Durable invariants

1. No automatic model download, user-session collection, external teacher call or telemetry.
2. No SDM decision ever widens application-supplied candidate identities or grants permission, disclosure or actuation.
3. A codegg checkout pinned to existing SHA and its frozen v1 compatibility contract remains valid across all SDM milestones.
4. sdm-runtime default graph stays free of training frameworks, platform GPU SDK requirements, remote I/O and external model services.
5. Explicit architecture/schema/version negotiation; bounded bytes, tensor shapes, state and candidates; reject invalid/non-finite inputs; immutable artifact snapshots.
6. No evaluation-set leakage into optimization, hyperparameters, model selection or calibration; holdouts and preregistration carry immutable fingerprints.
7. Model results have three separate states: mechanically valid, experimentally qualified, and consumer-approved for deployment. A positive first state does not imply either later state.
8. CPU functionality on x86_64 and ARM64; optional acceleration is measured and isolated, not mandatory.
9. Preserve MIT attribution and historical CodeGG negative/qualification artifacts; license/provenance limitations on imports remain visible.

## 4. Non-goals

No default CodeGG enablement, provider model routing implementation, security-command enforcement, optimizer/transformer platform, high-parameter model guarantee, online RL, remote training backend, autonomous data capture, runtime plugin loading, silent migration of CodeGG configs, or alteration of frozen benchmark labels.

## 5. Target dependency graph

~~~text
M001  versioned typed features + artifact/runtime interface
  |
  v
M002  datasets, provenance, frozen split manifests
  |
  v
M003  evaluator, calibration and preregistered qualification
  |
  v
M004  second learned architecture; optional Rust trainer; CPU runtime
  |
  v
M005  SDM-based CodeGG Rank experiment; no automatic promotion
~~~

M001 also has a cross-repository *interface* dependency on the existing CodeGG v1 compatibility fixtures. M005 has an *operational* dependency on independently approved CodeGG live/integration testing if a candidate advances beyond offline observation; negative offline closure does not require provider expenditure. Optional trainer selection within M004 requires a dependency/runtime-footprint decision documented by evidence.

## 6. Milestones and acceptance summaries

### M001 — Versioned feature/artifact/runtime contracts
Class: infrastructure. Status: closed. Plan: plans/implementation/general-decision-model-framework/001-versioned-feature-artifact-runtime-contracts.md.
Introduce additive typed feature projections, explicit capabilities, model/feature schema identity, architecture-bound artifact resource limits and independent architecture dispatch, preserving v1 byte identity and CodeGG compatibility. No new trainable neural architecture.

### M002 — Generic dataset provenance and frozen splits
Class: infrastructure. Status: conditionally closed. Plan: plans/implementation/general-decision-model-framework/002-dataset-provenance-and-split-integrity.md.
Introduce independent sdm-data and importer/manifests; support labels for all semantics without requiring model implementations for them; frozen group/family/counterfactual splits and leakage tests; explicit provenance and consent.

### M003 — Semantic evaluation and preregistered qualification
Class: capability. Status: conditionally closed. Plan: plans/implementation/general-decision-model-framework/003-semantic-evaluation-and-qualification.md.
Introduce independent sdm-eval with task-specific metrics, no-candidate/abstention and calibration reporting, artifact/split binding, frozen protocol and negative-valid verdicts. Test data cannot influence model or threshold.

### M004 — Second trained architecture and portable inference
Class: capability. Status: conditionally closed (runtime path and local resource benchmark implemented; trained ablations and hosted results remain). Plan: plans/implementation/general-decision-model-framework/004-nonlinear-architecture-and-rust-training.md.
Keep linear model as an honest baseline, add a demonstrably nonlinear pairwise feature-interaction model with local Rust training and bounded native CPU inference; include trainer feasibility spike and host footprint measurements. No assertion of contextual generalization or 5–25M parameters by size alone.

### M005 — CodeGG first-target offline qualification
Class: capability/evidence. Status: conditionally closed — indeterminate without approved independent corpus (hard M004; interface frozen CodeGG consumer contract). Plan: plans/implementation/general-decision-model-framework/005-codegg-first-consumer-qualification.md.
Explicitly import sanitized, provenance-approved fixtures and compare locked candidate sets across deterministic, linear and nonlinear models with frozen preregistration, counterfactual/family-excluded and no-tool slices. Close positive or negative with accurate evidence. Any CodeGG dependency change or active deployment requires separate CodeGG ownership and approval.

### M006 — Qualification and portability corrective
Class: corrective infrastructure/capability. Status: conditionally closed; residual generic evidence work is M007. Plan: plans/implementation/general-decision-model-framework/006-qualification-and-portability-corrective.md.

### M007 — Qualification depth and trained ablations
Class: capability/evidence. Status: closed. Plan: plans/implementation/general-decision-model-framework/007-qualification-depth-and-trained-ablations.md. Generic evidence is recorded in plans/closure/general-decision-model-framework/007-status.md. M005 remains indeterminate pending CodeGG approval.

## Standalone-framework successor M008-M011

Decision: ADR-0002. This workstream is independent of CodeGG and has no requirement for an application-specific corpus. M005 remains deferred/indeterminate, retains its historical closure, and is not a prerequisite for M008-M011. No generated synthetic example is represented as real CodeGG effectiveness evidence.

M008 adds `sdm-experiment`, its frozen synthetic Rank corpus, and `sdm experiment run --config PATH`; closure evidence is in plans/closure/general-decision-model-framework/008-status.md. M007's trained 16-example ablation remains in-sample and its hosted benchmarks use initialized weights. M008 demonstrates held-out synthetic mechanics for both Rank architectures. Typed feature projections do not yet reach learned model ingress directly; non-Rank model heads are absent.

### M008 — End-to-end standalone Rank experiment
Class: capability/infrastructure. Status: closed. Plan: plans/implementation/general-decision-model-framework/008-standalone-experiment-pipeline.md. Evidence: plans/closure/general-decision-model-framework/008-status.md.
Provide a reusable library + one CLI path to validate explicit local data, use frozen splits, train linear/nonlinear Rank, tune on dev only, package and reload verified artifacts, predict exact candidates and evaluate a genuinely held-out synthetic partition.

### M009 — Typed feature model ingress
Class: infrastructure/capability. Status: closed. Plan: plans/implementation/general-decision-model-framework/009-typed-feature-model-ingress.md. Evidence: plans/closure/general-decision-model-framework/009-status.md.
Implement one canonical bounded typed feature encoder for train/infer with real numerical, categorical and boolean inputs, frozen preprocessing and a versioned runtime contract; retain legacy lexical v1 behavior.

### M010 — Learned Binary, Choice and Score heads
Class: capability. Status: closed for mechanics; no quality claim. Evidence: plans/closure/general-decision-model-framework/010-status.md.
Complete train/package/infer/evaluate paths for every declared semantic family using small bounded models, correct abstention and option/score semantics, and independent datasets. Existing Rank continues working.

### M011 — Held-out standalone qualification and release review
Class: capability/release infrastructure. Status: closed; evidence: plans/closure/general-decision-model-framework/011-status.md. Plan: plans/implementation/general-decision-model-framework/011-standalone-release-qualification.md.
Frozen held-out suites, positive/negative/indeterminate gates, the same trained artifact on three targets, Rust 1.89, independent consumer compilation, documentation, dependency/license metadata and package verification are recorded. Binary OOD evidence is negative; Choice quality and some OOD slices are indeterminate. This is a mechanics/release candidate only and does not qualify CodeGG or auto-publish.

Dependency graph: M008 -> M009 -> M010 -> M011 -> M012 source integration is complete; M012 publication qualification remains conditional on human/legal license review. PR #1 is merged. M013 implemented the additive Choice cross architecture but its first independent suite was invalid. M013a used a fresh seed and groups, verified paired integrity and corrected family holds before inference; it found negative Binary text/combined-shift evidence and indeterminate Choice evidence. M013b evaluator mechanics completed with successful hosted CI; its residual gate-implementation defects were closed by M013c on the source branch, which also repaired a latent unsorted-quantile bootstrap defect without altering any frozen M013b file. Neither milestone refits or qualifies new models. Existing M011 evidence remains unchanged. CodeGG M005 remains deferred on a separate external gate.

### M012 — Release and branch reconciliation corrective
Class: corrective infrastructure/release readiness. Status: **conditionally closed**.
Plan: plans/implementation/general-decision-model-framework/012-post-m011-release-reconciliation-corrective.md.
Planning baseline: f9ce89765a1cb07ce23100177d8f56c30e52777d; integration target main at 8139b064bdcf3212e8f6fd912e801a479b55751c (re-audit both).
Scope: review full M001-M011 ancestry into main, resolve all seven crate manifests' missing registry metadata, verify package contents and an independent consumer, record third-party SPDX/license obligations for human review, reconcile documentation and artifact trust boundaries, rerun Rust 1.89/three-platform and frozen compatibility checks, and prepare a reviewable PR. No implicit merge, crates.io publish, tag, or CodeGG pin change.
Retain the synthetic predictive limitations reported by M011, notably negative Binary OOD performance and Choice's zero response changes to its tested target-flipping counterfactuals. Those belong in a separate future model-quality line, not as a premise to weaken release mechanics gates.
Required closure: plans/closure/general-decision-model-framework/012-status.md, including PR URL/state, exact source/head/merge-base, CI logs, package inventory and license-review disposition. A publication blocker can remain when a reviewed source PR is ready; the two decisions must be stated separately.

### M013 — Binary/Choice predictive-quality corrective and independent qualification
Class: capability/evidence corrective. Status: **conditionally closed**; evidence in plans/closure/general-decision-model-framework/013-status.md.
Plan: plans/implementation/general-decision-model-framework/013-predictive-quality-corrective-and-independent-qualification.md.
Research: docs/m013-quality-diagnostic-baseline.md.
Planning source baseline: main@2bd0d5af16d143828dcbce77f411b8f3b675e7be; M011 closure and M012 merged source are hard predecessors.
External dependencies: none for standalone work; no approved CodeGG corpus required.

The diagonal Choice representability failure was demonstrated and repaired with additive `sdm-typed-choice-cross-v1`, retaining the legacy 3*D Choice artifact path. M013's prospective corpus failed counterfactual integrity because load differed within active-flip pairs. Its split also passed OOD families to both `--exclude-family` and `--test-family`; exclusion takes precedence, leaving OOD rows out of test. The M013 held-out quality outcome is therefore invalid and not used for selection. M013a's valid fresh suite found negative Binary text/combined-shift Brier and indeterminate Choice accuracy, including three under-supported OOD answerable slices. Neither closure qualifies a model. M011 negative/indeterminate records remain unchanged; closure does not promote CodeGG models or authorize crates.io publication.

### M013a — Independent quality-suite integrity rerun
Class: evidence corrective. Status: **conditionally closed**. Plan: plans/implementation/general-decision-model-framework/013a-independent-quality-suite-integrity-rerun.md. Closure: plans/closure/general-decision-model-framework/013a-status.md.
The suite used a new deterministic generator seed, IDs, groups and split; verified pair equality; and placed OOD family holds in test without overlapping exclusions. Fixed legacy/cross Choice and current Binary candidates ran once after preregistration. Binary quality was negative for text and combined shifts. Choice was indeterminate; its three OOD answerable-accuracy slices had 44, 44, and 45 independent groups, so those slices are explicitly indeterminate. No M013 held-out output was training or selection evidence. Passing mechanical checks do not establish real-world effectiveness.

### M013b — Evaluation-gate integrity and model-failure diagnostics corrective
Class: infrastructure/evaluation-integrity corrective. Status: **conditionally closed** (mechanical results retained; source merged via PR #2). Plan: plans/implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md. Audit: docs/m013b-evaluation-audit.md.
Hard predecessors: M013/M013a conditionally closed on work/plans-sdm-m013-predictive-quality-corrective@694da1a002cf29c62724be6ba881240f43aac9c2. M013b repairs the target-relative-margin sensitivity interpretation, makes primary/support/OOD/counterfactual quality gates fail closed, preserves unchanged historical evidence, and analyzes Binary text-shift and Choice option/answerability failures from train/dev-only inputs. It cannot select improved models from the observed M013a test. Source remains unmerged pending a review PR. Future prospective experiments need newly sealed tests and preregistration.

### M013c — Qualification-gate hardening corrective
Class: infrastructure/evidence-integrity corrective. Status: **closed** for engineering/source (PR #2 merge 0e6c3cae5911681b18185673a30484a976cb3821). Plan: plans/implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md. Audit: docs/m013c-gate-hardening-audit.md. Closure: plans/closure/general-decision-model-framework/013c-status.md. Hard predecessor: M013b mechanically complete at 11ea106c9af3b1ec362a98e709b530cc0fa137d0, latest CI run 38107890553 green. Closed CI-bound confidence decisions, support-bounded critical negatives, protocol-enumerated required Binary families and Choice OOD families, all five Choice negative controls as separate paired measurements, and the latent unsorted-quantile bootstrap defect. M011/M013/M013a/M013b frozen results and historical closure files are preserved byte-identically. Source stack still unmerged. A new model candidate is OUT OF SCOPE.

### M013d — Bootstrap safety and M013 source-stack integration
Class: infrastructure/evidence-integrity + integration. Status: **closed** (PR #2 merged; main CI 38112863529 success). Plan: plans/implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md; closure: plans/closure/general-decision-model-framework/013d-status.md; audit: docs/m013d-final-corrective-audit.md. Implementation head: ffe295b6fd9c9bb73291cd9e61f0e935d162bfe0; base/main and merge-base: 2bd0d5af16d143828dcbce7f411b8f3b675e7be. PR #2 carries the full M013–M013d source stack. Hosted CI [38111257896](https://github.com/dbowm91/sdm/actions/runs/38111257896) passed all ten jobs and replays pinned history per host. The M013b unsorted quantile is repaired and covered by non-degenerate grouped comparisons; historical hashes and new source-fingerprint sidecar hashes are recorded separately. No main integration, release, model promotion, or new inference is claimed.

### M014 — Binary/Choice standalone predictive-quality recovery
Class: capability/prospective qualification. Status: **blocked after indeterminate consumed FINAL** (model mechanics integrated; next corrective M014a). Plan: plans/implementation/general-decision-model-framework/014-standalone-binary-choice-quality-recovery.md; research: docs/m014-model-quality-research.md. Hard prerequisites: M013–M013d merged in PR #2 (main@0e6c3cae5911681b18185673a30484a976cb3821) and CI 38112863529 passed all 10 jobs. Hypotheses: Binary fit-invariant nuisance tokens act as a hidden bias under vocabulary shift; Choice full rule_a/rule_b active-flip target may require context-context×role interaction and be UNREPRESENTABLE by existing pairwise cross features. Prove full-rule representability first. Then bounded binary feature policy and minimal versioned compositional Choice candidate if required; prospective NEW synthetic dataset, exact prefreeze numerical quality gates, independent eligible OOD group support, one final inference, honest positive/negative/indeterminate outcomes. No CodeGG corpus or general MLP framework needed.

### M014a — Exact-artifact evaluation and analyzer integrity
Class: infrastructure/evidence integrity. Status: **closed (source merged via PR #3; negative predictive result; canary Binary positive/Choice indeterminate)**. Plan: plans/implementation/general-decision-model-framework/014a-frozen-artifact-and-evaluator-integrity.md. See M014c closure plans/closure/general-decision-model-framework/014c-status.md for ordered-CI corrective and hosted/integration pending.

### M014b — Independent prospective qualification
Class: capability/qualification. Status: **closed (source merged via PR #3; Binary/Choice/overall negative, local, consumed; original-byte ledger)**. Plan: plans/implementation/general-decision-model-framework/014b-independent-frozen-qualification.md. See M014c; no rerun.

### M014c — Hosted CI, platform-parity and immutable closure reconciliation
Class: infrastructure/evidence integrity. Status: **closed (C1–C12 pass; PR #3 merged, merged-main green)**. Plan: plans/implementation/general-decision-model-framework/014c-closure-evidence-reconciliation.md; audit: docs/m014c-closure-audit.md; closure: plans/closure/general-decision-model-framework/014c-status.md; ledger: docs/m014c-evidence-ledger.json. Implementation af74c01 from c27724746ebc674919aff32a93d6baf74e104e13; main unchanged. Old CI 38408167153 FAILED (retained). Ordered pure→gen→dependent CI + regression, measured same-artifact attestation + aggregator + `canary-parity` job, detached lineage (placeholder_unbound) + original-byte ledger, no heldout rerun. C9 requires hosted 11-job SUCCESS; C11 one reviewed main PR; C12 reviewer merge + merged-main CI. M015 unregistered.

M014 -> M015 generalized tiny architecture comparisons is a SOFT, unregistered successor. M005 remains independently deferred.

## Independent small-model research successor M015–M017 (2026-10-13)

Research rationale: [docs/m015-small-model-research.md](../../docs/m015-small-model-research.md). M014c closes source/evaluator parity and provenance mechanics, NOT model generalization. M014b tested fixed old AND/XOR candidates against changed AND-XOR/XNOR labels without observably specifying the changed target rule, and therefore cannot decide whether a model is robust to label-preserving nuisance shifts. New M015 research separates these identifiable questions and has no CodeGG-data hard dependency.

Dependency graph (hard): `M014c (closed) → M015 (active/incomplete) → M016 (blocked) → M017 (blocked)`. M005 still externally deferred and publication still legal-gated.

### M015 — Oracle-audited synthetic corpus and prospective design foundation
Class: capability / research infrastructure. Status: **ready**. Plan: [015](../implementation/general-decision-model-framework/015-tinychoice-corpus-and-research-foundation.md).
Build >=5 distinct rule families with independent oracle, reproducible configurable group budgets, leakage/counterfactual support, FIXED-rule nuisance perturbation and OBSERVABLE rule-conditioned compositional experiments. Existing Choice 2..128 options remain valid; 0/1 are negative invalid-request controls. Run only new TRAIN/DEV model baselines and negative controls; preserve all historical FINAL inputs and leave future M017 final ungenerated/unopened. Current code covers the generator, oracle, train/dev partition and basic grouped diagnostics, but existing typed learned baselines are unsupported pending schema/harness integration. See [M015 run evidence](../../docs/m015-dev-results.md); M015 remains incomplete and cannot unblock M016 yet.

### M016 — TinyChoice native-CPU shared scorer and answerability
Class: capability. Status: **blocked** on M015 accepted closure/merge. Plan: [016](../implementation/general-decision-model-framework/016-tinychoice-mlp-and-baseline-comparison.md).
Introduce an **additive** `sdm-typed-choice-tinymlp-v1` optional Choice artifact: shared order-equivariant candidate MLP, separately supervised symmetric answerability head and dev-calibrated conditional score/abstention semantics. Probe 32/64-unit capacities and record actual parameters; evaluate existing linear/legacy/cross/compositional controls and independent shallow-tree benchmark on same feature/candidate universe. Any tree tooling is offline research-only and must not contaminate Rust runtime. Finite gradients, bounds, dependency isolation, metamorphic tests, 2..128 option contract and quantified DEV-only resource/quality evidence are required. No new FINAL evaluation or consumer promotion.

### M017 — Prospective one-time synthetic qualification and portability
Class: capability / prospective evidence. Status: **blocked** on M015/M016 closures. Plan: [017](../implementation/general-decision-model-framework/017-tinychoice-prospective-qualification-and-portability.md).
Freeze new independent test source + protocol + numeric CI-bound gates + frozen candidate artifact bytes in a **non-circular two-phase SHA binding**; verify eligible group support and green CI BEFORE exactly one inference-only final. Report fixed-rule robustness and explicit rule-conditioned transfer separately, with grouped uncertainty, answerability and calibration, unchanged source/control identity and original output byte ledger. Attest same committed model bytes on Linux x86_64/Linux ARM64/macOS ARM64 CANARY, not a replay of historical FINAL. A positive result only establishes narrow synthetic quality; M005 needs newly approved CodeGG data and a separate consumer-owned plan.

Non-goals throughout: no CodeGG pin or tool-policy changes, license publication, full semantic-language model, reinterpretation of M014b negative evidence or reuse of its consumed final test.

## 7. Cross-cutting requirements

- Compatibility: v1 LinearArtifact remains readable; no destructive v1 feature/schema changes. New artifacts identify architecture, model and calibration hashes and required feature schemas. On incompatibility return explicit Unsupported/Unavailable, not guessed coercion.
- Storage/restart: content-addressed manifest data; atomic checkpoint and artifact writes; interrupted training never presents partial files as validated artifacts. Keep old cases immutable.
- Failure/cancellation: training deadline or interruption safely leaves last complete checkpoint; inference has finite input/compute/memory bounds and predictable fallback controlled by caller.
- Security: typed features are only bounded data, never executable code; hostile artifact tensor dims, duplicate IDs, numeric overflow, invalid UTF-8 and path traversal fail closed. No implicit scan of CodeGG project/user paths.
- Performance: Mac Apple Silicon ~24 GiB development target; CPU x86_64/Linux ARM64 deployment evidence; batch and 16/64/128/256 candidate p50/p95; report peak process RSS honestly.
- Observability: fingerprinted artifacts and datasets, architecture/runtime versions, score/abstention and fallback reason; redacted by default with no raw user content.
- Evaluation: compare against BM25/keyword and linear under identical candidate universe, distinguishing first-stage candidate recall from reranker conditional performance.

## 8. Verification and closure policy

Each milestone records cargo fmt --all -- --check, cargo test --workspace --locked, cargo clippy --workspace --all-targets --locked -- -D warnings (after verifying dependency/MSRV compatibility), cargo check -p sdm-runtime --locked, cargo tree -p sdm-runtime --locked, frozen compatibility tool and focused new tests. Add machine-readable qualification reports and hosted CI when feasible; never claim work was run because it is written in a plan. If CI cannot exercise Apple Silicon or ARM64, record this explicitly and require named operational evidence before platform release.

Create plans/closure/general-decision-model-framework/NNN-status.md for each milestone with SHA, requirement-to-evidence matrix, tests and failures, effect on v1 consumer, resource/migration/privacy review, and disposition. Keep plans/registry.md accurate.

## 9. Risks and future work

- Representation limitation: a small MLP built on lexical projections is not a pretrained semantic encoder; negative generalization is legitimate.
- Benchmark contamination: repeated reuse of CodeGG's historical final test would invalidate new optimization claims; fresh holdouts and source lineage are mandatory.
- Quality bottleneck: original codegg BM25 preselection recall ~0.83 for a 64-tool universe; reranking cannot recover candidates already dropped. CodeGG owns fixing shortlist admission in separately planned work.
- Runtime format: a global 4 MiB limit prevents future larger models; raise limits only via architecture-specific manifests and hard caps.
- Training framework choice: Burn, Candle, tract/ONNX runtime and Safetensors are candidates, not preapproved required dependencies; measure compile/runtime cost and availability before locking.
- After M005: pretrained/distilled text-pair encoder experiments; new use cases (model routing and bounded risk advisory) through independent datasets and authority controls; model promotion only following CodeGG's own qualification/policy review.

## 10. Readiness

**Current readiness (2026-10-13):** M014c implementation af74c01 + fix d60d9c0 + docs 3d8db08 is closed (C1–C12 pass; PR #3 merged 91b0c3b, merged-main 38424519807 green; ordered CI, SAME-committed-bytes parity, detached lineage, original-byte ledger; historic negatives retained, no rerun). Old runs [38408167153](https://github.com/dbowm91/sdm/actions/runs/38408167153) (order defect) + [38413896571](https://github.com/dbowm91/sdm/actions/runs/38413896571) (retraining diverges, 0 decision divergences) FAILED and retained. Hosted [38418968150](https://github.com/dbowm91/sdm/actions/runs/38418968150) SUCCESS 11/11 on d60d9c0 (0 divergences, max prob delta 8.67e-19); C11 PR #3 reviewed (39 files, stack only) with PR run 38422712418 SUCCESS; C12 merge 91b0c3b + merged-main 38424519807 SUCCESS. **M014a/b are closed (negative, honest, source merged)** with original-byte ledger. Embedded `freeze_sha256` remains placeholder defect with detached chain. **M014c is the closed corrective**. M015 implementation is active/incomplete; its learned-baseline integration remains outstanding, and M016/M017 are blocked; M005 deferred; publication gated.


**Current (2026-10-13):** main@7b9bb3c929db2c9d492a1b86b54a4f57c61a9e37 and CI 38117915516 (10/10 success). M014 architecture and Binary mask implemented but its once-frozen final cohort consumed; exact Binary candidate SHA mismatch and broken analyzer leave quality INDETERMINATE (unchanged historical status). **M014a READY** for execution/evaluator integrity and DEV-CANARY; **M014b BLOCKED** until G1–G10 closure and NEW prospective sealed test. Older milestone-ready/premerge text below is historical, not current. Publication/CodeGG M005 remain separate.


M001-M011 outcomes are retained under plans/closure/general-decision-model-framework/. M005 stays indeterminate because no approved independent CodeGG corpus or consumer adapter exists. The v1 consumer contract remains unchanged and no CodeGG model is promoted. M012 source was merged via PR #1; its publication/legal qualification remains conditional. M013 and M013a are **conditionally closed**, retaining their invalid and negative/indeterminate evidence. M013b is **conditionally closed** (hosted CI run 38107890553 green; source unmerged): it corrected the M013a counterfactual metric into a target-independent fixed-option comparison, made every preregistered positive-quality gate executable and fail-closed, recorded a source-backed erratum over unchanged frozen reports, and isolated both Binary and Choice root causes using train/dev-only inputs. M013b qualified no model and reused no M013a test row. M013c closed the reusable quality-gate defects and passed all 10 hosted jobs on run 38109647535; its source is conditionally closed pending reviewed main integration. M013d repairs the remaining M013b unsorted quantile on the source stack, reproduces the pinned historical SHA ledger, and carries the full source ancestry in PR #2; implementation-hosted CI and reviewer merge are separate gates. No successor predictive experiment is registered or unblocked. Do not rely on M013b's standalone positive/negative classifier for new model qualification. M013/M013a/M013b/M013c source remains unmerged into main. M005 remains externally deferred. No model or package publication is authorized.
