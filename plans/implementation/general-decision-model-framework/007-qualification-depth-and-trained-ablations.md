# SDM General Framework M007 — Qualification depth and trained ablations

Status: closed
Primary class: capability/evidence
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md
Dependencies: M006 conditional closure; no CodeGG corpus required for synthetic work

## Objective

Complete reusable generic qualification gaps left by M002-M006: slice-aware calibration,
frozen synthetic examples across all request semantics, and trained nonlinear capacity
and feature-ablation evidence. Keep synthetic mechanics separate from CodeGG effectiveness.

## Non-goals

No CodeGG data import, production model promotion, upstream candidate-recall claims,
provider use, or deployment qualification. Synthetic results do not satisfy M005.

## Work packages

1. Add deterministic per-slice calibration reports with explicit minimum support and
   undefined results for undersized/empty slices; bind report inputs to existing
   artifact and protocol identities.
2. Check in a small redistributable synthetic qualification bundle covering Binary,
   Choice, Score and Rank, with provenance and frozen expected metrics. Verify input
   order and that fitting/calibration cannot read test labels through the supported API.
3. Extend nonlinear experiment tooling to train at two bounded capacities on a synthetic
   interaction task; compare context-masked and permuted-context ablations on identical
   frozen examples and report parameter utilization without a promotion gate.
4. Consume hosted benchmark artifacts for Linux x86_64, Linux ARM64 and Apple Silicon;
   retain exact toolchain, model and artifact digests. Missing runner evidence remains
   explicitly pending.

## Verification and acceptance

Run formatting, all-feature workspace tests, strict all-target Clippy, runtime example
checks, dependency graph checks and frozen CodeGG compatibility. Acceptance requires
deterministic fixtures/reports, minimum-support behavior, training/runtime parity and
reproducible ablation outputs. An inconclusive synthetic result is valid evidence.

## Failure, privacy and compatibility

All datasets remain local and synthetic; no network import or telemetry. Legacy v1
artifacts and frozen fixtures remain unchanged. Reports reject identity mismatches.
Temporary artifacts are atomically finalized; incomplete runs cannot be presented as
qualification results.

## Closure record

Evidence: `plans/closure/general-decision-model-framework/007-status.md`.
Implementation commits: `39c7af1c6baebfde8ac720ee35e6105fdca86a4c`,
`699d972c6f80b027517a4ab68c521e718181d102`.
All generic work packages are complete. M005 remains indeterminate until CodeGG supplies
an approved independent corpus and consumer-owned adapter; that external gate does not
block M007 closure.
