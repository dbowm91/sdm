# SDM Planning Registry

Status: M013d **ready** (bootstrap safety and M013–M013d source integration), M013/M013a/M013b/M013c conditionally closed on unmerged development stack; original Binary negative and Choice indeterminate evidence preserved; crates.io legal gate separate
Governance: plans/003-planning-process.md
Current planning baseline: work/plans-sdm-m013c-qualification-gate-hardening@03c4a982219ffa830b7c0aba9dbb19a541cae56c (main currently 2bd0d5af16d143828dcbce77f411b8f3b675e7be)
Accepted architecture: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md

States: proposed, ready, active, blocked, closing, closed, conditionally closed, superseded, archived.

## Active subsystem roadmaps

| Subsystem | Status | Next handoff | Blockers |
| --- | --- | --- | --- |
| Standalone general decision-model framework | M013/M013a/M013b/M013c conditionally closed; **M013d ready** | Repair legacy quantile; reproduce pinned SHA history; reviewed main-targeted PR for M013–M013d | Source unmerged; M013b quantile still unsafe; crates.io legal review separate |
| CodeGG consumer-specific effectiveness (M005) | deferred / indeterminate | independent CodeGG-owned evidence, unscheduled | No approved corpus; does not block M008-M011 |

## Registered milestone plans

| Milestone | Status | Class | Implementation plan | Hard blockers |
| --- | --- | --- | --- | --- |
| M001 | closed | infrastructure | plans/implementation/general-decision-model-framework/001-versioned-feature-artifact-runtime-contracts.md | none |
| M002 | conditionally closed | infrastructure | plans/implementation/general-decision-model-framework/002-dataset-provenance-and-split-integrity.md | M001 closure |
| M003 | conditionally closed | capability | plans/implementation/general-decision-model-framework/003-semantic-evaluation-and-qualification.md | M002 closure |
| M004 | conditionally closed | capability | plans/implementation/general-decision-model-framework/004-nonlinear-architecture-and-rust-training.md | M003 closure |
| M005 | conditionally closed | capability/evidence | plans/implementation/general-decision-model-framework/005-codegg-first-consumer-qualification.md | M004 closure; accepted fixture/interface evidence |
| M006 | conditionally closed | corrective infrastructure/capability | plans/implementation/general-decision-model-framework/006-qualification-and-portability-corrective.md | residual qualification depth registered as M007; CodeGG corpus is external to generic closure |
| M007 | closed | capability/evidence | plans/implementation/general-decision-model-framework/007-qualification-depth-and-trained-ablations.md | none; M005 remains externally gated |
| M008 | closed | capability/infrastructure | plans/implementation/general-decision-model-framework/008-standalone-experiment-pipeline.md | none (M005 not a dependency) |
| M009 | closed | infrastructure/capability | plans/implementation/general-decision-model-framework/009-typed-feature-model-ingress.md | M008 accepted closure |
| M010 | closed | capability | plans/implementation/general-decision-model-framework/010-generic-decision-task-heads.md | none; mechanics closure in plans/closure/general-decision-model-framework/010-status.md |
| M011 | closed | capability/release infrastructure | plans/implementation/general-decision-model-framework/011-standalone-release-qualification.md | M008-M010 accepted closures; evidence in plans/closure/general-decision-model-framework/011-status.md |
| M012 | **conditionally closed** (PR #1 merged) | corrective release infrastructure | plans/implementation/general-decision-model-framework/012-post-m011-release-reconciliation-corrective.md | Source merged; crates.io publication blocked pending human/legal license review |
| M013 | **conditionally closed** | capability / evidence corrective | plans/implementation/general-decision-model-framework/013-predictive-quality-corrective-and-independent-qualification.md | Bounded Choice cross architecture implemented; original prospective corpus invalid; see 013-status.md |
| M013a | **conditionally closed** | evidence corrective | plans/implementation/general-decision-model-framework/013a-independent-quality-suite-integrity-rerun.md | Valid independent suite; negative Binary result, indeterminate Choice and three under-supported Choice OOD accuracy slices in plans/closure/general-decision-model-framework/013a-status.md |
| M013b | **conditionally closed** (mechanically passed, unmerged) | infrastructure / evaluation-integrity corrective | plans/implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md | Hosted CI 38107890553 green; outstanding reusable gate defects now M013c; see plans/closure/general-decision-model-framework/013b-status.md |
| M013c | **conditionally closed** (hosted CI green, unmerged) | infrastructure / evidence-integrity corrective | plans/implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md | CI-bound decisions, support-bounded critical negatives, complete family/control coverage implemented; CI run 38109417539 green at 8dd8a21; reviewed main merge outstanding; see plans/closure/general-decision-model-framework/013c-status.md |
| M013d | **ready** | infrastructure / evidence integrity and source integration | plans/implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md | M013c CI complete; M013b quantile unsafe; reviewed PR merge is operational gate |

## Interface and operational dependencies

CodeGG historically pins SDM commit 8139b064bdcf3212e8f6fd912e801a479b55751c per the recorded interface dependency; verify the live CodeGG pin before changing it. Do not retarget CodeGG until a separate consumer-side plan and exact SHA compatibility qualification. Existing 12/11 fixtures measure shape/identity, not model usefulness. M005 is indeterminate and does not authorize live tool promotion. M006 and M007 generic infrastructure and qualification work are complete as recorded in their closure files. A new approved independent CodeGG corpus and consumer-owned adapter remain external gates for CodeGG effectiveness claims.

## Standalone successor handoff

Accepted boundary: plans/adrs/ADR-0002-standalone-framework-before-consumer-qualification.md. M008-M011 are closed in plans/closure/general-decision-model-framework/. All four are SDM-only and independent of the unavailable CodeGG corpus; no change to CodeGG's immutable SDM pin or production policy is authorized. M011 provides a reviewable release candidate, not automatic merge, publication or deployment. **M012 remains conditionally closed** for release/publication qualification, but its source PR #1 is now merged into main. Crates.io publication is blocked pending human/legal license review. **M013 and M013a are conditionally closed**; see their closure records for the invalid M013 suite and M013a's valid negative/indeterminate evidence. These milestones do not rewrite M011's positive, negative, or indeterminate model evidence. M005 continues to await an approved independent CodeGG corpus and consumer-owned evidence.

## M013d final bootstrap/source integration handoff

Ready plan: plans/implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md; audit: docs/m013d-final-corrective-audit.md. Baseline work/plans-sdm-m013c-qualification-gate-hardening@03c4a982219ffa830b7c0aba9dbb19a541cae56c; planning branch work/plans-sdm-m013d-bootstrap-source-integration. Repair M013b unsorted bootstrap; verify ORIGINAL M013b/M013c hashes at pinned old commits, and separately record necessarily changed regenerated source-hash-bearing sidecars. Open ONE reviewed main PR for all M013–M013d source. Mechanical closure + reviewable PR permits conditional closure; full integration requires approved merge and merged-main CI. No CodeGG promotion, crates.io publish or new holdout.

## M013c evaluation-gate-hardening handoff

Plan: plans/implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md. Planning source: work/plans-sdm-m013b-quality-gates-diagnostics@11ea106c9af3b1ec362a98e709b530cc0fa137d0. Implementation branch: work/plans-sdm-m013c-qualification-gate-hardening. Closure evidence: plans/closure/general-decision-model-framework/013c-status.md.

M013c is **conditionally closed**, green on hosted CI run [38109417539](https://github.com/dbowm91/sdm/actions/runs/38109417539) at `8dd8a21`; only the reviewed main merge remains outstanding. It hardens the reusable gate logic: decisions come from the 95% paired-group interval bounds rather than a point mean, a critical negative requires the preregistered minimum of eligible independent groups, the declared Binary required families and Choice required OOD families are enumerated from the protocol rather than from whatever the report happens to contain, and all five declared negative controls are measured separately on the same answerable population with real paired learned-minus-control intervals. It also repaired a latent unsorted-quantile defect inherited from the M013b bootstrap without altering any frozen M013b file or recorded M013a/M013b result.

**Defect-E follow-up (registered, not closed).** The M013b `group_bootstrap`/`quantile` ordering defect remains in `scripts/m013b_evaluator.py` because that file is frozen evidence and is hashed by the M013b sidecar. It is inert for every recorded M013a/M013b interval (the frozen M013a analyzer sorts correctly and the affected intervals are degenerate), but it is recorded here as a live defect in the reusable M013b module and must be fixed by a separate corrective before any new experiment relies on that module.

Keep frozen M013a evaluation unchanged. No M013d/M014 model experiment is ready. Source integration PR after review, no auto-merge.

## M013b corrective handoff

Plan: plans/implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md. Planning branch: work/plans-sdm-m013b-quality-gates-diagnostics; source predecessor work/plans-sdm-m013-predictive-quality-corrective@694da1a002cf29c62724be6ba881240f43aac9c2. Scope: corrected fixed-option counterfactual responsiveness, executable mandatory positive-quality gates, a source-backed M013a erratum sidecar, and train/dev-only Binary and Choice diagnostics. M013b corrected evaluation integrity and isolated both root causes; it did NOT qualify any candidate. Closure evidence: plans/closure/general-decision-model-framework/013b-status.md. No new qualifying held-out experiment is authorized. Source integration remains unmerged and requires a separately reviewed PR.

## Future-plan readiness after M013c

M013c is **conditionally closed** — the four gate defects plus one latent bootstrap defect are closed on the source branch, but hosted CI has passed 10/10 jobs on 38109647535 and the reviewed main merge remains outstanding. M013b remains **conditionally closed** and its reusable evaluator still carries the unsorted-quantile defect recorded above.

**A successor predictive-quality milestone (M014 or later) is NOT unblocked and is NOT registered ready.** M013d is the ready engineering bootstrap/source-integration corrective, not a model experiment. Three things must happen first, in order:

1. **A reviewed main-targeted merge.** Hosted CI run [38109417539](https://github.com/dbowm91/sdm/actions/runs/38109417539) is already green on `8dd8a21`; what remains is the human-reviewed PR merge. Until that lands the stack is branch-verified, not main-verified.
2. **The M013b quantile-ordering defect corrected** under its own narrow corrective. A new protocol may reuse `scripts/m013c_evaluator.py`, which sorts correctly; it may not reuse the M013b bootstrap path for a non-degenerate interval.
3. **Prospective freeze before inference**: new independent frozen test groups, numeric thresholds and an alpha/multiple-comparison policy declared BEFORE the data are seen, and `scripts/validate_future_support.py` passing on the eligible subgroups.

What M013c does unblock is *trustworthy gate machinery*: a future protocol can now be written against CI-bound, support-bounded, completeness-checked gates. That is a necessary precondition, not an authorization. M013b's train/dev diagnostics isolated two testable mechanisms — a constant-feature hidden bias in Binary and a truth-independent interaction offset in Choice — and either could seed a successor design, but selecting a remedy requires prospective evidence this repository does not yet have.

No M013a test row is qualification-eligible, no CodeGG model promotion is authorized, and crates.io publication stays behind its human/legal gate.

## M013 quality-corrective handoff controls

M013 implementation and original corpus freeze are at `c56f442fae14ede38fd1cd6e0eccf61315df96da`; closure evidence is `plans/closure/general-decision-model-framework/013-status.md`. Preserve its reports only as invalid diagnostics. M013a froze new data and protocol at `4768716d97cc58ea338d8099bfe09a1e57d0d8f9` before one-time held-out inference; see `plans/closure/general-decision-model-framework/013a-status.md` for exact evidence. No M013 or M013a result promotes a model or lifts the crates.io legal gate.

## M012 release-reconciliation handoff controls

Planning baseline: work/plans-sdm-standalone-framework-m008-m011@f9ce89765a1cb07ce23100177d8f56c30e52777d; main@8139b064bdcf3212e8f6fd912e801a479b55751c at planning, revalidate before implementing. Source planning branch: work/plans-sdm-m012-release-reconciliation. A newly reviewed main-targeted PR, not a direct main push, is the expected integration handoff. Do not merge, tag, publish any crate or retarget CodeGG as part of planning. Closure belongs at plans/closure/general-decision-model-framework/012-status.md with verified evidence and separately recorded merge/publication decisions.

Historical M012 planning text above describes its original pre-merge handoff; live PR #1 is merged as recorded in the active status.
