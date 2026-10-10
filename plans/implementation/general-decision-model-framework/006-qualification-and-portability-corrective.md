# SDM General Framework M006 — Qualification and Portability Corrective

Status: blocked (operational evidence and consumer-data prerequisites)  
Primary class: corrective infrastructure/capability  
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md  
Related closures: M002, M003, M004, M005

## Objective

Close the evidence gaps explicitly retained by M002-M005 without weakening their
acceptance criteria or rewriting historical results.

## Hard start conditions

- An explicitly approved, sanitized, independently held-out CodeGG dataset with
  provenance, redistribution/retention scope, and an owner-approved candidate adapter.
- A reproducible Linux ARM64 CPU runner (plus x86_64 and Apple Silicon host records)
  for the required runtime and resource matrix.
- A stable typed feature projection from the M001 contract for nonlinear trainer to
  standalone inference parity.

No CodeGG corpus is available in the current workspace and the current host does not
provide the full platform matrix. Until those conditions are met, this plan is not
eligible to start; existing fixture evidence remains compatibility-only.

## Work packages after unblock

1. Add explicit duplicate/near-duplicate leakage audits and bounded streaming JSONL
   import; record temporal/family/pair limitations.
2. Add grouped uncertainty intervals, per-slice calibration, and a frozen synthetic
   multi-semantic qualification bundle with test-label access-order checks.
3. Register the nonlinear architecture behind a runtime-only inference path with
   validated tensor/schema identity, fixed trainer/runtime parity vectors, atomic
   checkpoint finalization, and resume identity checks.
4. Measure two trained capacity points, context-masked/permuted ablations, CPU latency,
   load behavior and RSS on each available target without substituting host results.
5. On the approved CodeGG export, preregister a fresh family-excluded holdout, compare
   deterministic/linear/nonlinear systems on identical candidate sets, and close with
   a positive, negative, or indeterminate verdict. Do not change CodeGG.

## Acceptance and closure

Close only when all prior conditional requirements are evidenced, CodeGG offline
qualification is defensible or correctly indeterminate, and compatibility remains
green. Record exact source/data/split/protocol/model digests, commands, host limitations,
privacy review, negative results and follow-up owner in
`plans/closure/general-decision-model-framework/006-status.md`.
