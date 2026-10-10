# SDM Planning Registry

Status: M001-M005 outcomes recorded on 2026-10-10
Governance: plans/003-planning-process.md
Current code baseline: main@8139b064bdcf3212e8f6fd912e801a479b55751c
Accepted architecture: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md

States: proposed, ready, active, blocked, closing, closed, conditionally closed, superseded, archived.

## Active subsystem roadmaps

| Subsystem | Status | Next handoff | Blockers |
| --- | --- | --- | --- |
| General decision-model framework and CodeGG first consumer | conditionally closed | none currently eligible | Cross-platform runtime registration and newly approved CodeGG corpus remain follow-ups |

## Registered milestone plans

| Milestone | Status | Class | Implementation plan | Hard blockers |
| --- | --- | --- | --- | --- |
| M001 | closed | infrastructure | plans/implementation/general-decision-model-framework/001-versioned-feature-artifact-runtime-contracts.md | none |
| M002 | conditionally closed | infrastructure | plans/implementation/general-decision-model-framework/002-dataset-provenance-and-split-integrity.md | M001 closure |
| M003 | conditionally closed | capability | plans/implementation/general-decision-model-framework/003-semantic-evaluation-and-qualification.md | M002 closure |
| M004 | conditionally closed | capability | plans/implementation/general-decision-model-framework/004-nonlinear-architecture-and-rust-training.md | M003 closure |
| M005 | conditionally closed | capability/evidence | plans/implementation/general-decision-model-framework/005-codegg-first-consumer-qualification.md | M004 closure; accepted fixture/interface evidence |
| M006 | blocked | corrective infrastructure/capability | plans/implementation/general-decision-model-framework/006-qualification-and-portability-corrective.md | approved independent CodeGG corpus; Linux ARM64 runner; stable projection/parity contract |

## Interface and operational dependencies

CodeGG pins SDM commit 8139b064bdcf3212e8f6fd912e801a479b55751c. Do not retarget CodeGG until a separate consumer-side plan and exact SHA compatibility qualification. Existing 12/11 fixtures measure shape/identity, not model usefulness. M005 is indeterminate and does not authorize live tool promotion. Requirement-to-evidence records and remaining limitations are in plans/closure/general-decision-model-framework/; M006 is blocked on named external evidence.
