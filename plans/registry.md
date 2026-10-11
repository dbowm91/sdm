# SDM Planning Registry

Status: M001-M012 evidence retained; M013 and M013a conditionally closed with invalid/negative/indeterminate quality evidence; registry publication blocked pending human/legal sign-off
Governance: plans/003-planning-process.md
Current planning baseline: main@2bd0d5af16d143828dcbce77f411b8f3b675e7be
Accepted architecture: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md

States: proposed, ready, active, blocked, closing, closed, conditionally closed, superseded, archived.

## Active subsystem roadmaps

| Subsystem | Status | Next handoff | Blockers |
| --- | --- | --- | --- |
| Standalone general decision-model framework | M012 source merged; **M013 and M013a conditionally closed** | no registered eligible implementation plan | M013 invalid suite; M013a Binary negative / Choice indeterminate; crates.io remains separately blocked on human/legal sign-off |
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

## Interface and operational dependencies

CodeGG historically pins SDM commit 8139b064bdcf3212e8f6fd912e801a479b55751c per the recorded interface dependency; verify the live CodeGG pin before changing it. Do not retarget CodeGG until a separate consumer-side plan and exact SHA compatibility qualification. Existing 12/11 fixtures measure shape/identity, not model usefulness. M005 is indeterminate and does not authorize live tool promotion. M006 and M007 generic infrastructure and qualification work are complete as recorded in their closure files. A new approved independent CodeGG corpus and consumer-owned adapter remain external gates for CodeGG effectiveness claims.

## Standalone successor handoff

Accepted boundary: plans/adrs/ADR-0002-standalone-framework-before-consumer-qualification.md. M008-M011 are closed in plans/closure/general-decision-model-framework/. All four are SDM-only and independent of the unavailable CodeGG corpus; no change to CodeGG's immutable SDM pin or production policy is authorized. M011 provides a reviewable release candidate, not automatic merge, publication or deployment. **M012 remains conditionally closed** for release/publication qualification, but its source PR #1 is now merged into main. Crates.io publication is blocked pending human/legal license review. **M013 and M013a are conditionally closed**; see their closure records for the invalid M013 suite and M013a's valid negative/indeterminate evidence. These milestones do not rewrite M011's positive, negative, or indeterminate model evidence. M005 continues to await an approved independent CodeGG corpus and consumer-owned evidence.

## M013 quality-corrective handoff controls

M013 implementation and original corpus freeze are at `c56f442fae14ede38fd1cd6e0eccf61315df96da`; closure evidence is `plans/closure/general-decision-model-framework/013-status.md`. Preserve its reports only as invalid diagnostics. M013a froze new data and protocol at `4768716d97cc58ea338d8099bfe09a1e57d0d8f9` before one-time held-out inference; see `plans/closure/general-decision-model-framework/013a-status.md` for exact evidence. No M013 or M013a result promotes a model or lifts the crates.io legal gate.

## M012 release-reconciliation handoff controls

Planning baseline: work/plans-sdm-standalone-framework-m008-m011@f9ce89765a1cb07ce23100177d8f56c30e52777d; main@8139b064bdcf3212e8f6fd912e801a479b55751c at planning, revalidate before implementing. Source planning branch: work/plans-sdm-m012-release-reconciliation. A newly reviewed main-targeted PR, not a direct main push, is the expected integration handoff. Do not merge, tag, publish any crate or retarget CodeGG as part of planning. Closure belongs at plans/closure/general-decision-model-framework/012-status.md with verified evidence and separately recorded merge/publication decisions.

Historical M012 planning text above describes its original pre-merge handoff; live PR #1 is merged as recorded in the active status.
