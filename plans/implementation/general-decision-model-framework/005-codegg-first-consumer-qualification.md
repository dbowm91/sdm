# SDM General Framework M005 — CodeGG First-Consumer Offline Qualification

Status: conditionally closed (indeterminate: no newly approved independent CodeGG corpus was available)
Primary class: capability/evidence
Repository baseline at planning: dbowm91/sdm@8139b064bdcf3212e8f6fd912e801a479b55751c; refresh CodeGG and SDM heads when ready
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md#m005--codegg-first-target-offline-qualification
ADR: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Hard dependencies: M004, and M003 frozen qualification protocol
Interface dependencies: CodeGG compatibility fixtures and application-owned allowed-candidate projection; CodeGG must approve any new projection format or adapter
Operational dependency: separate CodeGG plan + CI and model approval before changing production pin or executing live trajectories

## 1. Objective

Use codegg tool selection as SDM's first application qualification target without redefining SDM as a codegg-only library. Run reproducible held-out experiments comparing sparse linear, nonlinear and deterministic baselines on a bounded CodeGG-derived corpus, with a valid negative disposition when no model improves. Produce an artifact and interoperability recommendation, not an automatic agent-loop integration.

## 2. Baseline and historical negative evidence

- CodeGG generic train/runtime has been extracted; its tool-advisor policies, candidate surface, BM25 fallback, consent and causal frontier remain host-owned.
- CodeGG runtime consumer pins immutable SDM 8139b064bdcf3212e8f6fd912e801a479b55751c behind optional decision-runtime-sdm. The frozen compatibility interface contains 12 fixtures, 11 valid runtime requests; it proves contract shape and candidate identity, not predictive effectiveness.
- CodeGG C004 evidence-integrity closure found held-out MRR 0.707 for hashed linear, 0.638 BM25 and 0.457/0.595/0.557 for contextual small/medium/compact; no useful contextual gain, no-tool F1/calibration weakness; 64-tool preselection recall ~0.83 when budget 16, compared with 0.98 target.
- These are historical negative benchmarks, not thresholds that can be retroactively tuned from. Source: CodeGG plans/closure/tool-selection-advisor-evidence-integrity-corrective/004-status.md. Any repeated use of that already-inspected final test must be labeled historical/regression only.

## 3. Authority and non-goals

SDM owns generic experiment/import adapter and model metrics. CodeGG owns ResolvedToolSurface, eligibility, candidate projection, current task context, privacy/consent, disclosure budgets, selection and execution policy. Never import raw private sessions by default. No direct Github pull of user data in automated training. No CodeGG config, dependency, feature, agent-loop, permission, or model promotion changes in this milestone. No provider spend/live A/B or claims that an unqualified offline ranker improves user trajectories.

## 4. Dataset and qualification design

A. Use historical CodeGG fixture set only as a compatibility regression, retaining its original source revision/hash. Request newly approved, sanitized datasets through explicit export rather than copying authoritative CodeGG assets wholesale. Split by task family, tool family, near-duplicate group and counterfactual pair; freeze a new *unseen* held-out partition before model comparison.

B. Build a CodeGG-specific adapter outside sdm-core that maps host-approved bounded task description and policy-filtered candidate descriptors to SDM typed features. Do not make CodeGG tool names or permissions part of generic core types. Preserve exact requested candidate identity and multi-relevance labels.

C. Preregister the comparison protocol before reading new final-test labels: candidate universe/surface fingerprint, first-stage shortlist and its recall ceiling, baseline set (keyword/BM25 and linear), rank metrics MRR/recall@k/NDCG, abstention/no-tool F1 and Brier/ECE, unknown/renamed tools, family-excluded retraining, counterfactual pairs, hard negatives, latency/RSS and added tool definition bytes. Declare minimum cell sizes and handling of undefined gates. Include per-slice resource targets and confidence uncertainty.

D. Train only on approved training partition, choose hyperparameters and any operating threshold/calibration only on dev. Benchmark linear and nonlinear on exactly the same frozen candidate identities and context projections. To test whether the new architecture learned interactions, perform context-swapped counterfactuals and comparison to a context-masked ablation. If labels are insufficient for a defensible new test, report blocked/indeterminate; do not reuse old contaminated test as fresh effectiveness evidence.

E. Run M003 qualification, record both conditional-on-shortlist rank quality and first-stage candidate-recall bound. SDM cannot fix a relevant tool excluded before it sees candidates; record this as CodeGG-owned preselection follow-up, not a hidden model failure or a reason to weaken thresholds.

F. Separate decisions: compatibility pass/fail; architecture offline quality pass/fail/indeterminate; operator/CodeGG deployment approval (always false at SDM handoff). Produce immutable candidate model SHA and exact application adapter/profile manifest for later CodeGG review only if offline evidence justifies it.

## 5. Optional downstream CodeGG handoff

If a model earns a positive offline verdict, propose a *separate* CodeGG implementation plan to adapt any new v2 feature projection/runtime artifact, bump full pinned SDM commit, run exact v1 compatibility and CodeGG tests, and conduct shadow/observe-only end-to-end trajectories before requesting explicit promotion qualification. No SDM plan grants authority to change CodeGG's deterministic shortlist or upgrade current feature flags. A negative verdict closes M005 with model rejection and leaves CodeGG untouched.

## 6. Failure/restart/privacy

Importer runs only on explicitly named local corpus paths after provenance/licensing and consent review. Store only sanitized task/candidate descriptors in reviewable fixtures and reports; no credentials, session transcripts, raw tool arguments or chain-of-thought. Fail closed on missing split manifest, provenance, duplicate/cross-split examples, unknown/expanded candidate IDs, surface hash drift, model hash change or below-minimum evidence. Train and qualification reports are content-addressed and can be reproduced without a CodeGG checkout for approved exported static corpora. Never consume the final test for model selection.

## 7. Verification

- Run standard SDM cargo fmt/test/Clippy/runtime-only graph and all M001–M004 focused tests.
- Run sdm-check-compat over frozen 12/11 fixtures using old v1 artifact, and prospective new model's supported semantics without weakening expected identity/status constraints.
- Produce reproducible named commands for train -> dev calibration -> frozen offline qualify -> report (actual CLI names to be implemented by M002/M003/M004).
- Verify old CodeGG compatibility checker against an exact SDM checkout SHA if a CodeGG checkout is available. A new CodeGG pin/feature/agent-loop change is not part of this milestone.
- Report 1/16/64/128/256 candidate cold/warm p50/p95 + RSS on available x86_64/Apple Silicon/ARM64 hosts and state missing platform coverage without extrapolation.
- Include negative test for denied tool injection and candidate-order perturbations at the interface boundary; host owns final actuation validation.

## 8. Acceptance

An independently reproducible offline verdict exists for the codegg target, using a frozen and sufficiently independent held-out set or an explicit indeterminate/block disposition if new labels cannot be approved. The report compares identical universes and documents deterministic/linear/nonlinear outcomes, abstention and generalization, resource costs, privacy/source approval and candidate preselector ceiling. Existing codegg is unchanged; any future deployment requires separately registered downstream work and positive evidence.

## 9. Stop conditions

Stop on any implied authority for SDM to execute/promote tools, ambiguous user-data consent, contaminated split reused as fresh effectiveness evidence, test-gate changes following inspection, incompatible CodeGG contract glossed as model failure, withheld corpus license, or attempt to push an unqualified artifact into production.

## 10. Closure evidence

plans/closure/general-decision-model-framework/005-status.md: data provenance/consent, SHA-pinned CodeGG and SDM revisions, held-out protocol and hashes, per-model per-slice metrics with uncertainties and full negative results, first-stage shortlist ceiling, resource/platform profile, output model digest, compatibility/failure results, explicit positive/negative/indeterminate verdict, CodeGG-owner follow-ups if warranted, and final registry status.
