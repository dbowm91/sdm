# SDM Planning Index

This directory follows the CodeGG planning and handoff convention as adapted in [003-planning-process.md](003-planning-process.md).

**Start here:** [Registry](registry.md) -> [General decision-model framework roadmap](subsystems/general-decision-model-framework-roadmap.md) -> the first ready handoff, M010. The [framework boundary ADR](adrs/ADR-0001-general-framework-and-model-boundaries.md) governs the milestone plans.

## Completed handoffs

M001 through M008 have implementation outcomes and requirement-to-evidence records in [closure](closure/general-decision-model-framework/). M002-M004 and M006 are conditionally closed with limitations recorded; M005 is indeterminate because an approved independent CodeGG corpus was unavailable.

M007 is closed with generic synthetic qualification, slice calibration and trained ablation evidence. CodeGG effectiveness remains gated on an approved independent corpus and consumer-owned adapter.

## Standalone framework successor

[ADR-0002](adrs/ADR-0002-standalone-framework-before-consumer-qualification.md) defers CodeGG M005 effectiveness pending an approved corpus. It does not block an independent SDM framework release.

- [M008 — Reproducible Rank experiment pipeline](implementation/general-decision-model-framework/008-standalone-experiment-pipeline.md): closed; [evidence](closure/general-decision-model-framework/008-status.md).
- [M009 — Typed feature training and runtime](implementation/general-decision-model-framework/009-typed-feature-model-ingress.md): closed; [evidence](closure/general-decision-model-framework/009-status.md).
- [M010 — Trainable Binary/Choice/Score heads](implementation/general-decision-model-framework/010-generic-decision-task-heads.md): **ready**.
- [M011 — Standalone held-out/release qualification](implementation/general-decision-model-framework/011-standalone-release-qualification.md): blocked on M010.

All four milestones are SDM-owned, use explicitly provided synthetic data, preserve v1 CodeGG compatibility and require new numbered closure files. No CodeGG corpus or checkout is needed.

Research and predecessor evidence are recorded in [docs/general-framework-research-2026-10.md](../docs/general-framework-research-2026-10.md).

Handoff rule: one implementation agent takes one **ready** milestone; re-audit the source head; update registry on state transition; write a requirement-to-evidence closure file in plans/closure/general-decision-model-framework/NNN-status.md before unblocking the next plan. Preserve old CodeGG experiments and existing artifact/fixture digests. Do not update CodeGG or claim neural model promotion from these SDM planning changes.
