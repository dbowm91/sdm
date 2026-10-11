# SDM Planning Registry

Status: M001-M011 evidence retained; M012 post-M011 release reconciliation corrective active (2026-10-11)
Governance: plans/003-planning-process.md
Current code baseline: main@8139b064bdcf3212e8f6fd912e801a479b55751c
Accepted architecture: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md

States: proposed, ready, active, blocked, closing, closed, conditionally closed, superseded, archived.

## Active subsystem roadmaps

| Subsystem | Status | Next handoff | Blockers |
| --- | --- | --- | --- |
| Standalone general decision-model framework | M001-M011 complete for mechanics; **M012 active** | M012 release reconciliation, packaging, license evidence and review PR | No CodeGG corpus required; release/publish/merge still requires independent review |
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
| M012 | **active** | corrective release infrastructure | plans/implementation/general-decision-model-framework/012-post-m011-release-reconciliation-corrective.md | M011 closure complete; legal review and merge/publish decisions are operational gates, not planning blockers |

## Interface and operational dependencies

CodeGG pins SDM commit 8139b064bdcf3212e8f6fd912e801a479b55751c. Do not retarget CodeGG until a separate consumer-side plan and exact SHA compatibility qualification. Existing 12/11 fixtures measure shape/identity, not model usefulness. M005 is indeterminate and does not authorize live tool promotion. M006 and M007 generic infrastructure and qualification work are complete as recorded in their closure files. A new approved independent CodeGG corpus and consumer-owned adapter remain external gates for CodeGG effectiveness claims.

## Standalone successor handoff

Accepted boundary: plans/adrs/ADR-0002-standalone-framework-before-consumer-qualification.md. M008-M011 are closed in plans/closure/general-decision-model-framework/. All four are SDM-only and independent of the unavailable CodeGG corpus; no change to CodeGG's immutable SDM pin or production policy is authorized. M011 provides a reviewable release candidate, not automatic merge, publication or deployment. **M012 is the active ready corrective handoff** for branch/packaging/license/documentation/release preparation; it does not rewrite M011's positive, negative, or indeterminate model evidence. M005 continues to await an approved independent CodeGG corpus and consumer-owned evidence.

## M012 release-reconciliation handoff controls

Planning baseline: work/plans-sdm-standalone-framework-m008-m011@f9ce89765a1cb07ce23100177d8f56c30e52777d; main@8139b064bdcf3212e8f6fd912e801a479b55751c at planning, revalidate before implementing. Source planning branch: work/plans-sdm-m012-release-reconciliation. A newly reviewed main-targeted PR, not a direct main push, is the expected integration handoff. Do not merge, tag, publish any crate or retarget CodeGG as part of planning. Closure belongs at plans/closure/general-decision-model-framework/012-status.md with verified evidence and separately recorded merge/publication decisions.
