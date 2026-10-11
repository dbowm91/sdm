# SDM General Framework M006 — Qualification and Portability Corrective

Status: conditionally closed (generic infrastructure delivered; further qualification work registered)
Primary class: corrective infrastructure/capability  
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md  
Related closures: M002, M003, M004, M005

## Objective

Close the evidence gaps explicitly retained by M002-M005 without weakening their
acceptance criteria or rewriting historical results.

## External gate for the CodeGG work package

- An explicitly approved, sanitized, independently held-out CodeGG dataset with
  provenance, redistribution/retention scope, and an owner-approved candidate adapter.

This gate applies only to work package 5. It does not block generic correctness,
synthetic qualification, runtime integration, or hosted platform CI. The repository
already has GitHub-hosted Linux ARM64 and Apple Silicon runners available through CI.
The stable nonlinear feature projection is now implemented as an ordered, fingerprinted
coordinate schema tied to artifact identity.

## Work packages and disposition

1. Exact/near duplicate advisory audit and bounded JSONL streaming import implemented.
2. Grouped Rank MRR/recall@k/NDCG intervals implemented. Per-slice calibration and a
   frozen four-semantic synthetic qualification bundle remain in M007.
3. Runtime-only nonlinear v2 dispatch, schema/feature/calibration identity validation,
   scorer parity vector, and atomic fingerprint-bound checkpoints implemented. Resume
   identity is tested; optimizer state persistence is not implemented.
4. Reproducible benchmark and hosted x86_64 Linux, Linux ARM64 and Apple Silicon CI
   jobs implemented. Local benchmark is Rosetta x86_64; hosted results are pending.
   Trained capacity-point and context ablation studies remain in M007.
5. CodeGG qualification remains indeterminate pending the approved independent corpus
   and CodeGG-owned adapter. No CodeGG files or pin changed.

## Acceptance and closure

Conditionally close this corrective when the delivered generic safeguards and runtime
mechanics pass local verification, the CodeGG disposition remains correctly indeterminate,
and residual engineering/evidence work is registered without weakening prior criteria.
Record exact source/data/split/protocol/model digests, commands, host limitations,
privacy review, negative results and follow-up owner in
`plans/closure/general-decision-model-framework/006-status.md`.
