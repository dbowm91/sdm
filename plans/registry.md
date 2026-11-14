# SDM Planning Registry

Status: the standalone SDM milestone line through M017 is integrated. M014's consumed final remains indeterminate; M017's consumed final is synthetic-only negative. CodeGG M005 and crates.io publication remain separately gated.

Governance: [003-planning-process.md](003-planning-process.md)
Current baseline: `main@f73d909d24af7957aaa62fc7ef213202de371cee` (M017 closeout, 2026-10-14)
Accepted architecture: [ADR-0001](adrs/ADR-0001-general-framework-and-model-boundaries.md)
Roadmap: [general decision-model framework](subsystems/general-decision-model-framework-roadmap.md)

States: proposed, ready, active, blocked, closing, closed, conditionally closed, superseded, archived.

## Active subsystem roadmaps

| Subsystem | Status | Next handoff | Blockers |
| --- | --- | --- | --- |
| Standalone general decision-model framework | M015 source merged; M015a, M016, and M017 closed | Follow-up requires a new milestone | No CodeGG corpus dependency |
| CodeGG consumer-specific effectiveness (M005) | Deferred / indeterminate | Independent CodeGG-owned evidence | No approved corpus |

## Registered milestone plans

| Milestone | Status | Class | Implementation plan | Hard blockers |
| --- | --- | --- | --- | --- |
| M001 | closed | infrastructure | [plan](implementation/general-decision-model-framework/001-versioned-feature-artifact-runtime-contracts.md) | none |
| M002 | conditionally closed | infrastructure | [plan](implementation/general-decision-model-framework/002-dataset-provenance-and-split-integrity.md) | M001 closure |
| M003 | conditionally closed | capability | [plan](implementation/general-decision-model-framework/003-semantic-evaluation-and-qualification.md) | M002 closure |
| M004 | conditionally closed | capability | [plan](implementation/general-decision-model-framework/004-nonlinear-architecture-and-rust-training.md) | M003 closure |
| M005 | conditionally closed | capability/evidence | [plan](implementation/general-decision-model-framework/005-codegg-first-consumer-qualification.md) | M004 closure; accepted fixture/interface evidence |
| M006 | conditionally closed | corrective infrastructure/capability | [plan](implementation/general-decision-model-framework/006-qualification-and-portability-corrective.md) | Residual qualification depth registered as M007; CodeGG corpus external to generic closure |
| M007 | closed | capability/evidence | [plan](implementation/general-decision-model-framework/007-qualification-depth-and-trained-ablations.md) | none; M005 remains externally gated |
| M008 | closed | capability/infrastructure | [plan](implementation/general-decision-model-framework/008-standalone-experiment-pipeline.md) | none; M005 is not a dependency |
| M009 | closed | infrastructure/capability | [plan](implementation/general-decision-model-framework/009-typed-feature-model-ingress.md) | M008 accepted closure |
| M010 | closed | capability | [plan](implementation/general-decision-model-framework/010-generic-decision-task-heads.md) | none |
| M011 | closed | capability/release infrastructure | [plan](implementation/general-decision-model-framework/011-standalone-release-qualification.md) | M008–M010 accepted closures |
| M012 | conditionally closed; PR #1 merged | corrective release infrastructure | [plan](implementation/general-decision-model-framework/012-post-m011-release-reconciliation-corrective.md) | Crates.io publication pending human/legal review |
| M013 | conditionally closed | capability/evidence corrective | [plan](implementation/general-decision-model-framework/013-predictive-quality-corrective-and-independent-qualification.md) | Original prospective corpus invalid; see closure |
| M013a | conditionally closed | evidence corrective | [plan](implementation/general-decision-model-framework/013a-independent-quality-suite-integrity-rerun.md) | Negative Binary; indeterminate Choice; see closure |
| M013b | conditionally closed | infrastructure/evaluation-integrity corrective | [plan](implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md) | Mechanics/source merged; model quality unqualified |
| M013c | closed | infrastructure/evidence-integrity corrective | [plan](implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md) | Evaluation integrity only |
| M013d | closed | infrastructure/evidence integrity/source integration | [plan](implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md) | none |
| M014 | blocked; consumed final, indeterminate | capability/prospective quality corrective | [plan](implementation/general-decision-model-framework/014-standalone-binary-choice-quality-recovery.md) | Candidate identity mismatch and evaluator failure; any new attempt requires an independent cohort |
| M014a | closed; source merged | infrastructure/evidence-integrity corrective | [plan](implementation/general-decision-model-framework/014a-frozen-artifact-and-evaluator-integrity.md) | Negative predictive result; see closure |
| M014b | closed; source merged | capability/prospective qualification | [plan](implementation/general-decision-model-framework/014b-independent-frozen-qualification.md) | Negative final consumed once; do not rerun |
| M014c | closed; C1–C12 passed | infrastructure/evidence-integrity corrective | [plan](implementation/general-decision-model-framework/014c-closure-evidence-reconciliation.md) | none |
| M015 | source merged | capability/research infrastructure | [plan](implementation/general-decision-model-framework/015-tinychoice-corpus-and-research-foundation.md) | Research infrastructure, not model qualification |
| M015a | closed | infrastructure/evaluation-integrity corrective | [plan](implementation/general-decision-model-framework/015a-choice-development-evaluation-integrity-corrective.md) | none |
| M016 | closed | capability | [plan](implementation/general-decision-model-framework/016-tinychoice-mlp-and-baseline-comparison.md) | DEV-only comparison; no qualification claim |
| M017 | closed; synthetic-only negative | capability/prospective evidence | [plan](implementation/general-decision-model-framework/017-tinychoice-prospective-qualification-and-portability.md) | none; see closure and final ledger |

## Current controls

- Preserve all frozen inputs, historic reports, and [closure records](closure/general-decision-model-framework/).
- M014/M014b and M017 final cohorts have been consumed. Do not rerun their final configs or modify their frozen inputs. See [M014 closure](closure/general-decision-model-framework/014-status.md), [M014 freeze](../docs/m014-freeze-v1.json), [M017 closure](closure/general-decision-model-framework/017-status.md), and [M017 final ledger](../docs/m017-final-ledger.json).
- No result here promotes a model for CodeGG. M005 requires approved independent consumer-owned evidence; crates.io publication requires separate human/legal review.

Detailed rationale and historical evidence remain in each milestone's implementation plan, closure record, and linked research/audit documents. This registry is the concise status index.
