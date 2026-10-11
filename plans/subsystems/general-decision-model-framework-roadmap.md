# General Decision-Model Framework and First Consumer Roadmap

Status: M001-M011 evidence retained; M012 release reconciliation ready; M005 deferred
Audit baseline: dbowm91/sdm@8139b064bdcf3212e8f6fd912e801a479b55751c (2026-10-05)
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

Dependency graph: M008 -> M009 -> M010 -> M011 is complete; M012 is ready as a release-process corrective. Existing milestones retain numbered closure evidence and registry state. CodeGG M005 remains deferred on a separate external gate.

### M012 — Release and branch reconciliation corrective
Class: corrective infrastructure/release readiness. Status: **ready**.
Plan: plans/implementation/general-decision-model-framework/012-post-m011-release-reconciliation-corrective.md.
Planning baseline: f9ce89765a1cb07ce23100177d8f56c30e52777d; integration target main at 8139b064bdcf3212e8f6fd912e801a479b55751c (re-audit both).
Scope: review full M001-M011 ancestry into main, resolve all seven crate manifests' missing registry metadata, verify package contents and an independent consumer, record third-party SPDX/license obligations for human review, reconcile documentation and artifact trust boundaries, rerun Rust 1.89/three-platform and frozen compatibility checks, and prepare a reviewable PR. No implicit merge, crates.io publish, tag, or CodeGG pin change.
Retain the synthetic predictive limitations reported by M011, notably negative Binary OOD performance and Choice's zero response changes to its tested target-flipping counterfactuals. Those belong in a separate future model-quality line, not as a premise to weaken release mechanics gates.
Required closure: plans/closure/general-decision-model-framework/012-status.md, including PR URL/state, exact source/head/merge-base, CI logs, package inventory and license-review disposition. A publication blocker can remain when a reviewed source PR is ready; the two decisions must be stated separately.

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

M001-M011 outcomes are retained under plans/closure/general-decision-model-framework/. M005 stays indeterminate because no approved independent CodeGG corpus or consumer adapter exists. The v1 consumer contract remains unchanged and no CodeGG model is promoted. M012 is the next ready SDM-owned handoff for packaging, license review, documentation, and branch integration; it is independent of the unavailable CodeGG corpus. M005 remains externally deferred.
