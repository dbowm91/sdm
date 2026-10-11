# SDM Planning Index

This directory follows the CodeGG planning and handoff convention as adapted in [003-planning-process.md](003-planning-process.md).

**Start here:** [Registry](registry.md) -> [General decision-model framework roadmap](subsystems/general-decision-model-framework-roadmap.md) -> **[M013b evaluation-gates and failure-diagnostics corrective](implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md) (ready)**. CodeGG M005 remains externally deferred. The [framework boundary ADR](adrs/ADR-0001-general-framework-and-model-boundaries.md) governs the milestone plans.

## Completed handoffs

M001 through M011 have implementation outcomes and requirement-to-evidence records in [closure](closure/general-decision-model-framework/). M002-M004 and M006 are conditionally closed with limitations recorded; M005 is indeterminate because an approved independent CodeGG corpus was unavailable.

M007 is closed with generic synthetic qualification, slice calibration and trained ablation evidence. CodeGG effectiveness remains gated on an approved independent corpus and consumer-owned adapter.

## Standalone framework successor

[ADR-0002](adrs/ADR-0002-standalone-framework-before-consumer-qualification.md) defers CodeGG M005 effectiveness pending an approved corpus. It does not block an independent SDM framework release.

- [M008 — Reproducible Rank experiment pipeline](implementation/general-decision-model-framework/008-standalone-experiment-pipeline.md): closed; [evidence](closure/general-decision-model-framework/008-status.md).
- [M009 — Typed feature training and runtime](implementation/general-decision-model-framework/009-typed-feature-model-ingress.md): closed; [evidence](closure/general-decision-model-framework/009-status.md).
- [M010 — Trainable Binary/Choice/Score heads](implementation/general-decision-model-framework/010-generic-decision-task-heads.md): closed; mechanics evidence in [closure](closure/general-decision-model-framework/010-status.md).
- [M011 — Standalone held-out/release qualification](implementation/general-decision-model-framework/011-standalone-release-qualification.md): closed; [qualification and release audit](closure/general-decision-model-framework/011-status.md).

All four milestones are SDM-owned, use explicitly provided synthetic data, preserve v1 CodeGG compatibility, and have numbered closure files. M011 closes their implemented mechanics work; the new M012 workstream handles source-branch and release reconciliation without reopening M011 quality claims. No CodeGG corpus or checkout is needed.

## Current corrective handoff

**[M012 — post-M011 release reconciliation](implementation/general-decision-model-framework/012-post-m011-release-reconciliation-corrective.md)** is conditionally closed: source [PR #1](https://github.com/dbowm91/sdm/pull/1) is merged into main; crates.io publication remains blocked pending human/legal license review. **M013 and M013a are conditionally closed** on an unmerged development branch; their invalid/negative/indeterminate results remain visible. **[M013b](implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md) is now ready** as a bounded evaluator corrective. CodeGG M005 remains externally deferred.

Research and predecessor evidence are recorded in [docs/general-framework-research-2026-10.md](../docs/general-framework-research-2026-10.md).

Handoff rule: one implementation agent takes one **ready** milestone; re-audit the source head; update registry on state transition; write a requirement-to-evidence closure file in plans/closure/general-decision-model-framework/NNN-status.md before unblocking the next plan. Preserve old CodeGG experiments and existing artifact/fixture digests. Do not update CodeGG or claim neural model promotion from these SDM planning changes.

M013 handoff: [Predictive-quality corrective and independent qualification](implementation/general-decision-model-framework/013-predictive-quality-corrective-and-independent-qualification.md), informed by [diagnostic baseline](../docs/m013-quality-diagnostic-baseline.md). M012 PR #1 has merged; crates.io publication remains separately gated. M013 requires no CodeGG corpus.

M013b handoff: [implementation plan](implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md), [evaluation-integrity audit](../docs/m013b-evaluation-audit.md). No additional prospective inference on the already-seen M013a test is permitted.
