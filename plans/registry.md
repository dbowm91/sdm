# SDM Active Planning Registry

Status: planning foundation registered on 2026-10-10
Governance: plans/003-planning-process.md
Current code baseline: main@8139b064bdcf3212e8f6fd912e801a479b55751c
Accepted architecture: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md

States: proposed, ready, active, blocked, closing, closed, conditionally closed, superseded, archived. Status in this file is prospective; no milestone implementation was performed by the planning commit.

## Active subsystem roadmaps

| Subsystem | Status | Next handoff | Blockers |
| --- | --- | --- | --- |
| General decision-model framework and CodeGG first consumer | ready | M001 versioned feature/artifact/runtime contracts | Existing CodeGG compatibility fixture is a fixed interface, not a blocker |

## Registered milestone plans

| Milestone | Status | Class | Implementation plan | Hard blockers |
| --- | --- | --- | --- | --- |
| M001 | ready | infrastructure | plans/implementation/general-decision-model-framework/001-versioned-feature-artifact-runtime-contracts.md | none |
| M002 | blocked | infrastructure | plans/implementation/general-decision-model-framework/002-dataset-provenance-and-split-integrity.md | M001 closure |
| M003 | blocked | capability | plans/implementation/general-decision-model-framework/003-semantic-evaluation-and-qualification.md | M002 closure |
| M004 | blocked | capability | plans/implementation/general-decision-model-framework/004-nonlinear-architecture-and-rust-training.md | M003 closure |
| M005 | blocked | capability/evidence | plans/implementation/general-decision-model-framework/005-codegg-first-consumer-qualification.md | M004 closure; accepted fixture/interface evidence |

## Interface and operational dependencies

CodeGG pins SDM commit 8139b064bdcf3212e8f6fd912e801a479b55751c. Do not retarget CodeGG until a separate consumer-side plan and exact SHA compatibility qualification. Existing 12/11 fixtures measure shape/identity, not model usefulness. Positive offline M005 will not authorize live tool promotion. SDM M005 may close negatively without provider access, provided preregistration and held-out evaluation are complete. No open corrective or closure record exists at registration.
