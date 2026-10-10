# SDM Planning and Agent-Handoff Process

Status: normative planning governance
Adopted: 2026-10-10
Source convention: CodeGG plans/003-planning-process.md (https://github.com/dbowm91/codegg/blob/main/plans/003-planning-process.md)

## Purpose and authority

SDM follows CodeGG's separation of durable architecture, subsystem roadmaps, bounded implementation milestones, and evidence-based closure. This file adapts its planning conventions to this small independent repository; it is not a declaration that CodeGG policy is owned by SDM.

Authority order for implementation: accepted SDM ADRs, SDM subsystem roadmap, the single active milestone implementation plan, current source evidence. CodeGG ADR-0013 and its frozen compatibility fixtures govern the cross-repository ownership and consumer-compatibility boundary; a disagreement stops changes to that boundary pending a separately recorded decision.

## Document types and locations

- plans/adrs/: cross-cutting accepted or proposed decisions, including alternatives and consequences.
- plans/subsystems/: long-lived ownership, invariants, milestone DAG, compatibility and risks.
- plans/implementation/<workstream>/NNN-*.md: independently executable single-milestone handoffs against a known commit.
- plans/closure/<workstream>/NNN-status.md: acceptance evidence, commits, verification, provenance, negative findings, and explicit disposition.
- plans/registry.md: compact active control surface. Implementation agents must update it on milestone state changes.
- plans/archive/: superseded or abandoned handoffs retained for traceability; do not rewrite historical records.

States: proposed, ready, active, blocked, closing, closed, conditionally closed, superseded, archived. Only a ready milestone with all hard dependencies closed and interface contracts established can be started.

## Work classes and dependencies

Each milestone has one primary class: invariant, capability, infrastructure, or polish. Mark dependency edges as hard (cannot start), interface (mockable contract), soft (parallelizable), or operational (release/qualification evidence). Work is not closed by compilation alone; infrastructure closure does not imply learned-model effectiveness or production promotion.

## Required plan fields

A milestone handoff must include objective, non-goals, baseline and relevant prior evidence, invariants, expected code changes, ordered work packages, dependency readiness, failure/cancellation/restart semantics, security/privacy, storage/schema/compatibility effects, focused and broad verification commands, documentation/guards, explicit acceptance and stop conditions, and closure evidence.

The agent must inspect the present tree before changing code; preserve unrelated changes and old artifacts; validate default/runtime-only dependency graphs; record all tests actually run rather than claiming unrun checks; and never silently reinterpret archived negative experiment evidence.

## Closure and contention

A closure record must contain implementation SHAs/PRs, requirement-to-evidence matrix, repeatable commands/results and host limitations, compatibility, resource, security, migration, and open risks by severity. If conditions are not satisfied, register a new corrective instead of changing a failed gate or retroactively reclassifying results.

Coordinate cross-repo SDM->CodeGG release with an immutable full commit SHA, not a floating ref. SDM is authoritative for generic modeling; CodeGG remains authoritative for candidate admission, consent, fallback, actuation, and live evaluation of a coding agent.

## Handoff review

Check: scope fits a coherent pass, dependencies correct, ownership and interfaces explicit, versioning and rollback demonstrated, no hidden network/data import, independent held-out evidence, platform test matrix, docs/registry updated, and qualification separate from model correctness. Stop if any of these cannot be defended.
