# SDM Planning Index

This directory follows the CodeGG planning and handoff convention as adapted in [003-planning-process.md](003-planning-process.md).

**Start here:** [Registry](registry.md) -> [Roadmap](subsystems/general-decision-model-framework-roadmap.md) -> **[M014c closure](closure/general-decision-model-framework/014c-status.md) CLOSED (C1–C12 pass; PR #3 merged, merged-main green)**. M014a/b restored from closing to mechanically closed (negative, honest, original-byte ledger) via M014c C1–C9. Old CI 38408167153 FAILED (retained). M014b negative historically reported; consumed final NEVER rerun. **M015 research/corpus foundation is READY; M016 and M017 are blocked**, newly registered for standalone TinyChoice work. See [plan](implementation/general-decision-model-framework/014c-closure-evidence-reconciliation.md), [audit](../docs/m014c-closure-audit.md), [ledger](../docs/m014c-evidence-ledger.json).

## Current standalone TinyChoice research handoff (2026-10-13)

[Research basis](../docs/m015-small-model-research.md) — [M015 oracle-audited corpus and train/dev protocols](implementation/general-decision-model-framework/015-tinychoice-corpus-and-research-foundation.md) **READY** — [M016 native compact Choice/answerability and baselines](implementation/general-decision-model-framework/016-tinychoice-mlp-and-baseline-comparison.md) **BLOCKED on M015** — [M017 independent frozen prospective evaluation and parity](implementation/general-decision-model-framework/017-tinychoice-prospective-qualification-and-portability.md) **BLOCKED on M015/M016**. Choice retains its existing 2..128 valid-option requirement. No CodeGG corpus required and no historical FINAL test is rerun. This is planning-only on a feature branch; no model implementation or quality claim has landed.

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

## Completed M014c closure — merged to main (historical handoff)

[M014c](implementation/general-decision-model-framework/014c-closure-evidence-reconciliation.md) is mechanically closed in [014c-status.md](closure/general-decision-model-framework/014c-status.md) (C1–C12 pass; PR #3 merged 91b0c3b, merged-main 38424519807 green; implementation af74c01 + fix d60d9c0 + docs 3d8db08). It orders canary CI (pure→gen→dependent + regression), replaces asserted with measured same-artifact attestation + aggregator + `canary-parity` job, records detached lineage with placeholder_unbound defect, and ledgers original final-report SHAs from original bytes. No old heldout rerun, no model retraining and no CodeGG change. M014a/b are closed (negative, honest, source merged via PR #3); full integration complete (hosted + PR + merged-main all green). M015 now registered ready (see current handoff); M005 deferred, publication gated.

## Historical handoff (M014)

**[M012 — post-M011 release reconciliation](implementation/general-decision-model-framework/012-post-m011-release-reconciliation-corrective.md)** is conditionally closed: source [PR #1](https://github.com/dbowm91/sdm/pull/1) is merged into main; crates.io publication remains blocked pending human/legal license review. **M013–M013d SOURCE is merged** by [PR #2](https://github.com/dbowm91/sdm/pull/2), main@0e6c3cae5911681b18185673a30484a976cb3821, with 10/10 merged-main CI jobs green [38112863529](https://github.com/dbowm91/sdm/actions/runs/38112863529). Binary remains negative and Choice indeterminate on M013a; no model qualifies for CodeGG. **[M014](implementation/general-decision-model-framework/014-standalone-binary-choice-quality-recovery.md) is READY** for the next independent standalone experiment. CodeGG M005 remains externally deferred.

Research and predecessor evidence are recorded in [docs/general-framework-research-2026-10.md](../docs/general-framework-research-2026-10.md).

Handoff rule: one implementation agent takes one **ready** milestone; re-audit the source head; update registry on state transition; write a requirement-to-evidence closure file in plans/closure/general-decision-model-framework/NNN-status.md before unblocking the next plan. Preserve old CodeGG experiments and existing artifact/fixture digests. Do not update CodeGG or claim neural model promotion from these SDM planning changes.

M013 handoff: [Predictive-quality corrective and independent qualification](implementation/general-decision-model-framework/013-predictive-quality-corrective-and-independent-qualification.md), informed by [diagnostic baseline](../docs/m013-quality-diagnostic-baseline.md). M012 PR #1 has merged; crates.io publication remains separately gated. M013 requires no CodeGG corpus.

M013b handoff: [implementation plan](implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md), [planning audit](../docs/m013b-evaluation-audit.md), [closure evidence](closure/general-decision-model-framework/013b-status.md). No additional prospective inference on the already-seen M013a test is permitted; a successor experiment must seal new independent frozen test groups and pass `scripts/validate_future_support.py` first.

M013c handoff: [implementation plan](implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md), [source audit](../docs/m013c-gate-hardening-audit.md), [closure evidence](closure/general-decision-model-framework/013c-status.md). The historical M013b closure record is left intact; current-facing statuses reflect conditional source integration and the narrowed follow-up. M013c hardens gate mechanics only and is not a model-quality rerun. A successor predictive milestone stays unregistered until the stack is merged through review, the M013b quantile-ordering defect has its own corrective, and a new protocol prospectively freezes test groups and numeric thresholds.

M013d is conditionally closed: [implementation handoff](implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md), [provenance audit](../docs/m013d-final-corrective-audit.md), and [closure evidence](closure/general-decision-model-framework/013d-status.md). It is not a predictive rerun. Historical sidecar hashes are reproduced at the pinned commit; regenerated M013b/M013c hashes are separately recorded with their source-fingerprint cause. PR #2 carries M013–M013d; full integration requires reviewed merge and merged-main CI. No successor predictive plan is ready.

M014 ready: [bounded implementation and exact freeze criteria](implementation/general-decision-model-framework/014-standalone-binary-choice-quality-recovery.md), [source and methods research](../docs/m014-model-quality-research.md). The full Choice two-rule truth table must be proven expressible before optimizer choice. New independent synthetic groups, numeric gates, subgroup support and frozen protocol must precede a one-time final test; M013a final data is historical only. No CodeGG data required.

Current handoff: M014 produced implemented models but its one-time final synthetic cohort was consumed without valid qualification. **M014a is the ONLY ready milestone**, addressing inference-only artifact byte identity, serde's omitted true, full paired-group and control evaluation, and a CI-enforced DEV-CANARY. **M014b is blocked** until M014a closure and will own a NEW prospectively frozen cohort. Plans: [M014a](implementation/general-decision-model-framework/014a-frozen-artifact-and-evaluator-integrity.md), [M014b](implementation/general-decision-model-framework/014b-independent-frozen-qualification.md), [failure audit](../docs/m014-qualification-failure-analysis.md). Never rerun the M014 final configs.
