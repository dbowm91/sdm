# M014b — New independent qualification with frozen artifact inference

Status: **blocked**; registered prospective milestone, NOT eligible to start
Primary class: capability / prospective synthetic qualification
Planning baseline: dbowm91/sdm@7b9bb3c929db2c9d492a1b86b54a4f57c61a9e37
Hard predecessor: M014a must CLOSE with all G1–G10 and development canary proof
Closure path: plans/closure/general-decision-model-framework/014b-status.md
Authority: ADR-0001 / ADR-0002 and existing M014 protocol as historical evidence only
No CodeGG corpus/provider/release dependency.

## Objective

Once exact-artifact inference and the complete analyzer are mechanically proven, qualify existing Binary constant-feature mask and bounded compositional Choice on ONE new, independently generated and preregistered final cohort. The previously consumed M014 test cannot be rerun, resplit, reused for model selection or claimed as unseen. M013a is also historical only. A new M014b program must keep frozen candidates exactly identical in bytes through inference and issue fully supported positive/negative/indeterminate task verdicts.

M014b does NOT add a new model architecture, adjust M014's historic candidate based on test observations, introduce general MLP/trees (future M015), ship models to CodeGG, publish crates or fetch sensitive/external datasets.

## A. Dependency and candidate qualification before cohort construction

A1. Verify M014a closure matrix G1–G10 and latest main/branch CI, and require the DEV-CANARY analyzer to produce every preregistered report field. If absent, stop; M014b remains blocked.
A2. Select a model set strictly from existing exact frozen M014 TRAIN/DEV-screened candidate artifact bytes (preferred) or from a newly preregistered bounded train/dev-only sweep; no M014 final test observations used to choose. Record actual byte SHA256 (not tensor-normalized), model architecture, schema, encoder, training fingerprint, calibration threshold, license and runtime version. Freeze legacy incumbent and all declared baseline models/controls too. The M014 final-v1 output artifacts are historical exposed outputs and cannot silently become newly selected candidates.
A3. Fixed candidate/algorithm identities must be declared before test and kept across every family/ablation; no retrospective replacing the weakest comparator or changing best-model selection.

## B. Prospective distinct cohort and protocol

B1. Implement new generator version, seed, CASE/GROUP IDs, heldout memberships and nuisance vocabularies not overlapping M014/M013a FINAL groups. Must not merely repackage/resplit historical rows. Include at least two structural label functions distinct from prior exact test pattern, stable label-preserving OOD text-only/load-only/combined, unknown vocab, counterfactual flips affecting ONLY active causal field, option order/identity permutations, and answerable vs no-answer Choice support.
B2. Confirm no group crosses train/dev/test, pair members share group and all noncausal fields, context/candidate IDs are valid, and no test only token enters train encoder. Label rules/code and schema provenance recorded; synthetic-only license, no user data. Store generator code/hash, full generated dataset SHA, split/test-member SHA and programmatic replay, rather than millions of duplicated JSON rows.
B3. Before freeze verify actual metric-eligible support: >=50 independent Binary groups per primary/critical slice, >=50 answerable Choice groups in EACH primary/critical family, >=20 no-answer groups in each no-answer family, >=50 correctly paired answerable counterfactual groups. Count GROUPS, not paired rows or total OOD groups. Validate with scripts/validate_future_support.py and new M014a gate input validator.
B4. Prospectively specify and seal numeric protocol: exact model/control set, family names and primaries, metric denominators, paired group resampling, 10k replicates and seed, one-sided adjusted CI bounds, multiplicity policy/#comparisons, all thresholds, answerable coverage/recall floors, both-correct pair gate, group-support minima, latency/RSS/three-host resource criteria and verdict precedence. A missing nonnumeric gate cannot pass.
B5. Suggested boundaries to ratify BEFORE freeze: Binary required text/combined shifts beat BOTH prior and legacy at adjusted CI lower >0; ID families noninferior to legacy at lower >= -0.02. Choice on each nominated ID/critical shift beats frozen legacy/cross and discriminating controls at adjusted CI lower >0; pair both-correct >=0.80 with lower >=0.70; no-answer recall >=0.80 with lower >=0.65; answerable coverage >=0.60. Do not weaken thresholds once any FINAL outcomes are observed; M014b is free to preregister stricter equivalent rules before freeze.
B6. Freeze in an actual committed hash/protocol/candidate-artifact manifest BEFORE any final inference, including code/CI build, output digests regenerated in CI and exclusion digest of known M014/M013a test groups. Validate frozen artifact bytes load on all three platforms and have same decision results.

## C. Canary, one-time final and qualification

C1. Run full DEV-CANARY on NEW pipeline and intentionally failing inputs using M014a exact-artifact evaluate-only command and analyzer. Force wrong artifact SHA, duplicate case, incomplete group, unsupported OOD, missing control, absent no-answer slice, always-abstain false positive attempt, and interruption; CI must fail closed. Any repair made prior to FINAL needs a new freeze SHA committed before observing final scores.
C2. Execute ONE coordinated final inference-only evaluation over ALL FROZEN candidate/control models against the sealed NEW test cohort; artifacts MUST NOT be retrained or reserialized. A failed attempt after any final label/score exposed consumes cohort; no adaptive retry after results. Each report includes dataset/split/test-member/artifact/protocol/evaluator SHA.
C3. Collect complete family-level adjusted group CI, primary effects, no-answer/coverage/selective-risk, correct-both final counterfactual response, negative-control comparisons, platform/latency/memory and same-artifact integrity. No missing mandatory gate can become positive.
C4. Classify separately per task: positive only all fixed primary+OOD+support+calibration+counterfactual+resources pass; negative if preregistered supported critical regression; indeterminate/invalid otherwise. Synthetic task quality NEVER means real-world generalization or CodeGG readiness. Report failed tests and uncertainty without changing cohorts/weights/thresholds.

## D. Verification and closure

Record SHA-ledger, full group support and first final-observation SHA/time, input artifact SHA before/after for ALL models, control comparisons, adjusted 10k group bootstrap results, complete gate matrix, negative controls, three-host Rust 1.89 and portability checks, exact package/license/independent consumer tests, immutable old source evidence, security/privacy/cancellation and honest disposition in plans/closure/general-decision-model-framework/014b-status.md. Review and merge is separate from experimental quality; no crates.io publication, CodeGG model pin or promotion.

**Ten acceptance gates:** Q1 M014a closed; Q2 genuinely fresh frozen groups/provenance; Q3 eligible per-family support accepted before FINAL; Q4 all exact artifacts frozen pre-test; Q5 DEV-CANARY complete; Q6 one inference-only coordinated test campaign; Q7 all required control/CI/coverage/counterfactual/resource results with explicit verdict; Q8 3-target/MSRV/compat CI; Q9 atomic/no-overwrite and hash audit; Q10 no historical corruption or external approval bypass. Mechanical closure requires Q1–Q10, while quality may legitimately be negative or indeterminate.

## Cancellation, rollback and future scope

When any prefreeze gate fails, stop BEFORE FINAL and repair using dev canary only. Once test scores/labels exposed, stop and preserve failure even if the analyzer is wrong; no post-hoc tuning or replay. Use unique atomic output files and immutable pretest commits. M015 broader architectures is a soft successor, NOT ready by virtue of M014b plan registration.
