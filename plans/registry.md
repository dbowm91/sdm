# SDM Planning Registry

Status: **M014c mechanically closed (C1–C8+C10 local pass; C9/C11/C12 pending push/review/merge)**. M014a/M014b restored from **closing/CI-evidence-blocked** to **mechanically closed; negative predictive result** conditional on C1–C9 (original-byte ledger, no rerun). Old hosted run 38408167153 FAILED (retained, not a pass). M015 unregistered; M005 and crates.io separately gated.
Governance: plans/003-planning-process.md
Current planning baseline: M014a/b source branch@c27724746ebc674919aff32a93d6baf74e104e13; main@7b9bb3c929db2c9d492a1b86b54a4f57c61a9e37. M014c implementation af74c01e3c26a502f31d64d268f69166d9ac1be2 on work/plans-sdm-m014c-closure-evidence-reconciliation; closure plans/closure/general-decision-model-framework/014c-status.md. Latest source CI 38408167153 FAILURE (retained); earlier successful 38399878048 was planning-only. M014c hosted 11-job run (verify×3 + portability + choice-portability + canary-parity) pending push.
Accepted architecture: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md

States: proposed, ready, active, blocked, closing, closed, conditionally closed, superseded, archived.

## Active subsystem roadmaps

| Subsystem | Status | Next handoff | Blockers |
| --- | --- | --- | --- |
| Standalone general decision-model framework | M014a/M014b mechanically closed (negative, honest, original-byte ledger); **M014c mechanically closed (integration pending: hosted C9 + PR C11 + merge C12)** | Reviewed M014a–c main PR after hosted green; no M015/M005/publication unblocked | Do not rerun consumed final; embedded freeze placeholder remains defect with detached chain; historic hosted CI NOT verified |
| CodeGG consumer-specific effectiveness (M005) | deferred / indeterminate | independent CodeGG-owned evidence, unscheduled | No approved corpus; does not block M008-M011 |

## Registered milestone plans

| Milestone | Status | Class | Implementation plan | Hard blockers |
| --- | --- | --- | --- | --- |
| M001 | closed | infrastructure | plans/implementation/general-decision-model-framework/001-versioned-feature-artifact-runtime-contracts.md | none |
| M002 | conditionally closed | infrastructure | plans/implementation/general-decision-model-framework/002-dataset-provenance-and-split-integrity.md | M001 closure |
| M003 | conditionally closed | capability | plans/implementation/general-decision-model-framework/003-semantic-evaluation-and-qualification.md | M002 closure |
| M004 | conditionally closed | capability | plans/implementation/general-decision-model-framework/004-nonlinear-architecture-and-rust-training.md | M003 closure |
| M005 | conditionally closed | capability/evidence | plans/implementation/general-decision-model-framework/005-codegg-first-consumer-qualification.md | M004 closure; accepted fixture/interface evidence |
| M006 | conditionally closed | corrective infrastructure/capability | plans/implementation/general-decision-model-framework/006-qualification-and-portability-corrective.md | residual qualification depth registered as M007; CodeGG corpus is external to generic closure |
| M007 | closed | capability/evidence | plans/implementation/general-decision-model-framework/007-qualification-depth-and-trained-ablations.md | none; M005 remains externally gated |
| M008 | closed | capability/infrastructure | plans/implementation/general-decision-model-framework/008-standalone-experiment-pipeline.md | none (M005 not a dependency) |
| M009 | closed | infrastructure/capability | plans/implementation/general-decision-model-framework/009-typed-feature-model-ingress.md | M008 accepted closure |
| M010 | closed | capability | plans/implementation/general-decision-model-framework/010-generic-decision-task-heads.md | none; mechanics closure in plans/closure/general-decision-model-framework/010-status.md |
| M011 | closed | capability/release infrastructure | plans/implementation/general-decision-model-framework/011-standalone-release-qualification.md | M008-M010 accepted closures; evidence in plans/closure/general-decision-model-framework/011-status.md |
| M012 | **conditionally closed** (PR #1 merged) | corrective release infrastructure | plans/implementation/general-decision-model-framework/012-post-m011-release-reconciliation-corrective.md | Source merged; crates.io publication blocked pending human/legal license review |
| M013 | **conditionally closed** | capability / evidence corrective | plans/implementation/general-decision-model-framework/013-predictive-quality-corrective-and-independent-qualification.md | Bounded Choice cross architecture implemented; original prospective corpus invalid; see 013-status.md |
| M013a | **conditionally closed** | evidence corrective | plans/implementation/general-decision-model-framework/013a-independent-quality-suite-integrity-rerun.md | Valid independent suite; negative Binary result, indeterminate Choice and three under-supported Choice OOD accuracy slices in plans/closure/general-decision-model-framework/013a-status.md |
| M013b | **conditionally closed** (mechanics and source merged; model quality unqualified) | infrastructure / evaluation-integrity corrective | plans/implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md | Hosted CI 38107890553 green; outstanding reusable gate defects now M013c; see plans/closure/general-decision-model-framework/013b-status.md |
| M013c | **closed** (source merged; evaluation integrity only) | infrastructure / evidence-integrity corrective | plans/implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md | CI-bound decisions, support-bounded critical negatives, complete family/control coverage implemented; CI 38112863529 passed on merged main; historical closure retained at plans/closure/general-decision-model-framework/013c-status.md |
| M013d | **closed** (source merged; CI 10/10) | infrastructure / evidence integrity and source integration | plans/implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md | PR #2 merged as 0e6c3cae5911681b18185673a30484a976cb3821; main CI 38112863529 passed; publication still separately gated; historical closure remains intact |
| M014 | **blocked; consumed final, indeterminate** | capability / prospective quality corrective | plans/implementation/general-decision-model-framework/014-standalone-binary-choice-quality-recovery.md | Choice capacity gap proven; additive compositional architecture and Binary constant mask implemented. Final run record: plans/closure/general-decision-model-framework/014-status.md. Binary artifact identity mismatch and evaluator failure prevent qualification; new independent cohort required for any further attempt |
| M014a | **mechanically closed; negative predictive result (canary Binary positive/Choice indeterminate; historic M014 indeterminate unchanged)** | infrastructure/evidence-integrity corrective | plans/implementation/general-decision-model-framework/014a-frozen-artifact-and-evaluator-integrity.md | M014c C1–C9 required for restored close; hosted C9 + integration C11/C12 pending; see plans/closure/general-decision-model-framework/014a-status.md + 014c-status.md |
| M014b | **mechanically closed; negative predictive result (Binary/Choice/overall negative, local, consumed; original-byte ledger)** | capability/prospective qualification | plans/implementation/general-decision-model-framework/014b-independent-frozen-qualification.md | Final cohort consumed; NO rerun; M014c evidence/CI closure (014c-status.md + docs/m014c-evidence-ledger.json) |
| M014c | **mechanically closed (C1–C8+C10 local pass; C9/C11/C12 pending push/review/merge)** | infrastructure/evidence-integrity closure corrective | plans/implementation/general-decision-model-framework/014c-closure-evidence-reconciliation.md | Implementation af74c01; closure plans/closure/general-decision-model-framework/014c-status.md; no new experiment; integration requires hosted green + reviewed PR + merge |

## Interface and operational dependencies

CodeGG historically pins SDM commit 8139b064bdcf3212e8f6fd912e801a479b55751c per the recorded interface dependency; verify the live CodeGG pin before changing it. Do not retarget CodeGG until a separate consumer-side plan and exact SHA compatibility qualification. Existing 12/11 fixtures measure shape/identity, not model usefulness. M005 is indeterminate and does not authorize live tool promotion. M006 and M007 generic infrastructure and qualification work are complete as recorded in their closure files. A new approved independent CodeGG corpus and consumer-owned adapter remain external gates for CodeGG effectiveness claims.

## Standalone successor handoff

Accepted boundary: plans/adrs/ADR-0002-standalone-framework-before-consumer-qualification.md. M008-M011 are closed in plans/closure/general-decision-model-framework/. All four are SDM-only and independent of the unavailable CodeGG corpus; no change to CodeGG's immutable SDM pin or production policy is authorized. M011 provides a reviewable release candidate, not automatic merge, publication or deployment. **M012 remains conditionally closed** for release/publication qualification, but its source PR #1 is now merged into main. Crates.io publication is blocked pending human/legal license review. **M013 and M013a are conditionally closed**; see their closure records for the invalid M013 suite and M013a's valid negative/indeterminate evidence. These milestones do not rewrite M011's positive, negative, or indeterminate model evidence. M005 continues to await an approved independent CodeGG corpus and consumer-owned evidence.

## M014c closure corrective (mechanically closed; integration pending)

**Closed (mechanical C1–C8+C10 local pass):** plans/closure/general-decision-model-framework/014c-status.md, ledger docs/m014c-evidence-ledger.json, audit docs/m014c-closure-audit.md. Implementation af74c01 on work/plans-sdm-m014c-closure-evidence-reconciliation from c27724746ebc674919aff32a93d6baf74e104e13; main unchanged. Source CI run 38408167153 FAILED (retained; tests ran before canary inputs) — fixed by pure→gen→dependent order + `check_m014a_ci_order` regression (local: 21 pure pass clean, 5 dependent fail without canary, clean regen identical). Single-host `three_host_parity=true` removed (now false/unverified); real same-artifact attestation (`m014c_canary_attestation`, 948+926 decisions) + aggregator (`verify_m014c_parity`, exact platforms/source/cases/actions) with new `canary-parity` CI job (local 3-label simulation passes; single/mutated rejected). Detached Git/SHA-256 lineage verified (`verify_m014c_lineage`, placeholder_unbound, ancestry 9cc80f0→c277247, one-byte corruption fails); frozen bytes unchanged. Original `target/m014b/final/` bytes ledgered (file+inner SHAs, sizes/mtimes, negative/negative/negative retained, rule-change scope, never rerun). Integration requires hosted 11-job SUCCESS on implementation SHA + ONE reviewed main PR + reviewer merge/merged-main CI (C9/C11/C12 pending); no crates.io/CodeGG or M015 promotion. No future plan unblocked: M015 unregistered (needs own corrective + freeze + thresholds); M005 externally deferred; crates.io human/legal-gated.

## M014a/M014b corrective handoff

**M014a closed, M014b closed (negative, honest):** M014a 6139806 + `014a-status.md` (G1–G10 + DEV-CANARY Binary positive/Choice indeterminate) and M014b freeze `9cc80f0` + one-time final (Binary negative/Choice negative/overall negative on new AND-XOR/XNOR cohort with old bytes, no retuning, no rerun) complete on branch work/plans-sdm-m014a-m014b-qualification-recovery (base main@7b9bb3c). Historical M014 freeze/reports/status immutable; M014b outputs only `target/m014b/final/` (hashes in `014b-status.md`). No future plan unblocked: M015 remains soft unregistered successor (needs own corrective + prospective freeze + thresholds); M005 externally deferred; crates.io human/legal-gated. No CodeGG promotion or publication.

## M014 quality-recovery handoff

Active plan: plans/implementation/general-decision-model-framework/014-standalone-binary-choice-quality-recovery.md; research: docs/m014-model-quality-research.md; freeze: docs/m014-freeze-v1.json; final run record: plans/closure/general-decision-model-framework/014-status.md. The full Choice two-rule XOR-like target is not representable by the old pairwise margin; a source-derived proof and separate compositional architecture exist. Binary has an opt-in train-only exact-constant coordinate mask and bounded L2 policy. Train/dev screening, independent synthetic data, eligible support, protocol, and candidate artifacts were frozen and CI verified before the one-time final run. That run is **indeterminate**: Binary output artifact hashes do not match the frozen candidates, and the frozen evaluator failed to produce valid confidence intervals. Do not rerun this cohort or make post-test model/gate changes; any further qualification requires a new independent cohort and protocol. Do not use M013a test for optimization. M005 and crates.io remain separate external gates.

## M013d final bootstrap/source integration handoff

Implementation is conditionally closed: plan `plans/implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md`; closure `plans/closure/general-decision-model-framework/013d-status.md`; provenance audit `docs/m013d-final-corrective-audit.md`. Baseline `03c4a982219ffa830b7c0aba9dbb19a541cae56c`; implementation head `ffe295b6fd9c9bb73291cd9e61f0e935d162bfe0`; base and merge-base `2bd0d5af16d143828dcbce7f411b8f3b675e7be`. The M013b bootstrap is repaired, pinned original hashes are reproduced, and current source-fingerprint sidecars are separately recorded. One main-targeted source PR, [#2](https://github.com/dbowm91/sdm/pull/2), carries M013–M013d; hosted PR CI [38111257896](https://github.com/dbowm91/sdm/actions/runs/38111257896) passed all ten jobs. Historical pre-merge report only: PR #2 actually merged as 0e6c3cae5911681b18185673a30484a976cb3821 and merged-main CI 38112863529 passed. Original closure files remain immutable. No CodeGG promotion, crates.io publication, or new holdout is authorized.

## M013c evaluation-gate-hardening handoff

Plan: plans/implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md. Planning source: work/plans-sdm-m013b-quality-gates-diagnostics@11ea106c9af3b1ec362a98e709b530cc0fa137d0. Implementation branch: work/plans-sdm-m013c-qualification-gate-hardening. Closure evidence: plans/closure/general-decision-model-framework/013c-status.md.

M013c is **conditionally closed**, green on hosted CI run [38109417539](https://github.com/dbowm91/sdm/actions/runs/38109417539) at `8dd8a21`; only the reviewed main merge remains outstanding. It hardens the reusable gate logic: decisions come from the 95% paired-group interval bounds rather than a point mean, a critical negative requires the preregistered minimum of eligible independent groups, the declared Binary required families and Choice required OOD families are enumerated from the protocol rather than from whatever the report happens to contain, and all five declared negative controls are measured separately on the same answerable population with real paired learned-minus-control intervals. It also repaired a latent unsorted-quantile defect inherited from the M013b bootstrap without altering any frozen M013b file or recorded M013a/M013b result.

**Historical Defect-E follow-up (implemented under M013d, now merged).** M013d repairs the M013b `group_bootstrap`/`quantile` ordering contract in the current source stack and adds non-degenerate regression coverage. Original M013b/M013c commits and historical closure files remain unchanged. PR #2 carried the corrected source and merged as 0e6c3cae5911681b18185673a30484a976cb3821; no active bootstrap defect remains in main.

Keep frozen M013a evaluation unchanged. M014 is ready as an independent quality-recovery implementation plan. M013d was engineering-only and is now integrated.

## M013b corrective handoff

Plan: plans/implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md. Planning branch: work/plans-sdm-m013b-quality-gates-diagnostics; source predecessor work/plans-sdm-m013-predictive-quality-corrective@694da1a002cf29c62724be6ba881240f43aac9c2. Scope: corrected fixed-option counterfactual responsiveness, executable mandatory positive-quality gates, a source-backed M013a erratum sidecar, and train/dev-only Binary and Choice diagnostics. M013b corrected evaluation integrity and isolated both root causes; it did NOT qualify any candidate. Closure evidence: plans/closure/general-decision-model-framework/013b-status.md. No new qualifying held-out experiment is authorized. This statement describes the historical M013b handoff; PR #2 has since merged the source.

## Future-plan readiness after M013d (historical snapshot, superseded)

Source integration was COMPLETED by PR #2, merge 0e6c3cae5911681b18185673a30484a976cb3821, and merged-main CI 38112863529 (10/10 successful). M013c and M013d engineering/integration source is closed. M013a negative/indeterminate model evidence remains unchanged. The historical M013b source commit still contains the defective helper, but main's M013d implementation corrects it.

This section records the pre-merge state only. PR #2 and the prospective M014 freeze are complete; the final M014 run and its indeterminate disposition are recorded above and in `plans/closure/general-decision-model-framework/014-status.md`. The consumed M014 cohort cannot be run again.

What M013c does unblock is *trustworthy gate machinery*: a future protocol can now be written against CI-bound, support-bounded, completeness-checked gates. That is a necessary precondition, not an authorization. M013b's train/dev diagnostics isolated two testable mechanisms — a constant-feature hidden bias in Binary and a truth-independent interaction offset in Choice — and either could seed a successor design, but selecting a remedy requires prospective evidence this repository does not yet have.

No M013a test row is qualification-eligible, no CodeGG model promotion is authorized, and crates.io publication stays behind its human/legal gate. M014 plan and research contain the next bounded standalone work.

## M013 quality-corrective handoff controls

M013 implementation and original corpus freeze are at `c56f442fae14ede38fd1cd6e0eccf61315df96da`; closure evidence is `plans/closure/general-decision-model-framework/013-status.md`. Preserve its reports only as invalid diagnostics. M013a froze new data and protocol at `4768716d97cc58ea338d8099bfe09a1e57d0d8f9` before one-time held-out inference; see `plans/closure/general-decision-model-framework/013a-status.md` for exact evidence. No M013 or M013a result promotes a model or lifts the crates.io legal gate.

## M012 release-reconciliation handoff controls

Planning baseline: work/plans-sdm-standalone-framework-m008-m011@f9ce89765a1cb07ce23100177d8f56c30e52777d; main@8139b064bdcf3212e8f6fd912e801a479b55751c at planning, revalidate before implementing. Source planning branch: work/plans-sdm-m012-release-reconciliation. A newly reviewed main-targeted PR, not a direct main push, is the expected integration handoff. Do not merge, tag, publish any crate or retarget CodeGG as part of planning. Closure belongs at plans/closure/general-decision-model-framework/012-status.md with verified evidence and separately recorded merge/publication decisions.

Historical M012 planning text above describes its original pre-merge handoff; live PR #1 is merged as recorded in the active status.
