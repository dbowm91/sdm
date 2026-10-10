# SDM Planning Index

This directory follows the CodeGG planning and handoff convention as adapted in [003-planning-process.md](003-planning-process.md).

**Start here:** [Active registry](registry.md) -> [General decision-model framework roadmap](subsystems/general-decision-model-framework-roadmap.md) -> the first ready implementation milestone. The [framework boundary ADR](adrs/ADR-0001-general-framework-and-model-boundaries.md) governs all five.

## Ready handoff

- [M001 — Versioned features, artifact envelope, and runtime contracts](implementation/general-decision-model-framework/001-versioned-feature-artifact-runtime-contracts.md) — ready against SDM main 8139b064bdcf3212e8f6fd912e801a479b55751c.

## Registered downstream (blocked by earlier closures)

- [M002 — Dataset provenance and split integrity](implementation/general-decision-model-framework/002-dataset-provenance-and-split-integrity.md) — blocked on M001.
- [M003 — Semantic evaluation and qualification](implementation/general-decision-model-framework/003-semantic-evaluation-and-qualification.md) — blocked on M002.
- [M004 — Nonlinear model and portable Rust train/inference](implementation/general-decision-model-framework/004-nonlinear-architecture-and-rust-training.md) — blocked on M003.
- [M005 — CodeGG first-target offline qualification](implementation/general-decision-model-framework/005-codegg-first-consumer-qualification.md) — blocked on M004 and CodeGG fixture contract evidence.

Research and predecessor evidence are recorded in [docs/general-framework-research-2026-10.md](../docs/general-framework-research-2026-10.md).

Handoff rule: one implementation agent takes one **ready** milestone; re-audit the source head; update registry on state transition; write a requirement-to-evidence closure file in plans/closure/general-decision-model-framework/NNN-status.md before unblocking the next plan. Preserve old CodeGG experiments and existing artifact/fixture digests. Do not update CodeGG or claim neural model promotion from these SDM planning changes.
