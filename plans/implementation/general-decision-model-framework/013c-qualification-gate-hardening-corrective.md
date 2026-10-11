# SDM M013c — Qualification-Gate Hardening Corrective

Status: **ready** (implementation handoff only; no code change or experiment performed by planning commit)
Class: infrastructure / evidence-integrity corrective
Source baseline: dbowm91/sdm@11ea106c9af3b1ec362a98e709b530cc0fa137d0 on work/plans-sdm-m013b-quality-gates-diagnostics; re-audit current branch, CI and open PRs before implementing
Planning branch: work/plans-sdm-m013c-qualification-gate-hardening
Governance: plans/003-planning-process.md
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md
Architectural bounds: ADR-0001 and ADR-0002; CodeGG ADR-0013 for ownership separation
Hard prerequisite: M013b mechanically implemented and CI green, with existing closure at plans/closure/general-decision-model-framework/013b-status.md; M013/M013a are conditionally closed
Merge dependency: M013/M013a/M013b are still outside main; work must descend from this stack rather than M012-only main
External dependencies: none (no CodeGG data, model provider, teacher service or crates.io publication)
Expected closure file: plans/closure/general-decision-model-framework/013c-status.md

## 1. Objective and acceptance boundary

Close four demonstrable defects in the reusable M013b quality-gate pipeline: (1) Binary primary/critical decision gates use point-estimate sign rather than the preregistered confidence-interval boundary, (2) a critical fail with only one observed group can produce a negative verdict without meeting the frozen minimum support, (3) the required Binary family set and all required Choice OOD/negative controls are not checked for complete coverage, and (4) the purported Choice negative-control gate compares a nonnegative accuracy to zero rather than testing a meaningful model-vs-control criterion. Also reconcile milestone status and prepare the existing source stack for an ordinary reviewed integration PR.

Success means the evaluator cannot assert positive OR significant negative without the required statistical evidence and population support; all mandatory families/gates/controls are present, versioned and provenance-bound; historic M011/M013/M013a/M013b artifacts and verdicts remain immutable; and deterministic adversarial tests plus hosted CI pass. **This is not a new model-quality experiment.** No revised weights, train/dev selection, test-based threshold, consumer approval or model promotion is authorized.

## 2. Verified defects in the source at baseline

1. scripts/m013b_audit_m013a.py::build_binary_gates feeds metrics.brier_improvement_vs_train_prior (a mean) into threshold_gate(comparator=">", threshold=0) and marks critical families. Yet scripts/m013b_protocol_v1.json requires positive only when the paired GROUP bootstrap 95% CI lower bound exceeds zero, negative when the 95% CI upper bound is below zero. A negative point mean with a straddling interval must be INDETERMINATE, not negative; a positive point mean with a straddling interval cannot qualify.
2. scripts/m013b_evaluator.py::_supported returns evidence_count > 0 for a critical failure. It is unaware of the protocol minimum 50 eligible independent groups and possible mismatches between a threshold gate and a separate support gate. A critical negative from n=1 must be insufficient support, not significant regression; the support threshold must be attached to the same slice/effect being classified.
3. build_binary_gates iterates sorted(binary_analysis["slices"]) rather than enumerating protocol["binary_gates"]["required_families"]. Missing critical/required OOD slices can be silently skipped. build_choice_gates adds OOD/support from slices present and checks only critical missing families, not the entire required_ood_families set.
4. The Choice negative_controls_do_not_qualify gate uses threshold_gate on control_accuracy, comparator=">=", threshold=0.0; accuracy is naturally nonnegative, so this is not an evidence-bearing control comparison. train_majority_accuracy returns only the max of train-majority and always-answer baselines, while the protocol lists train-majority, always-abstain, always-answer, shuffled-score and context-only controls. Present named controls separately, with matching eligibility/candidate identities, and compare learned-vs-control on the specified primary metric where meaningful.
5. plans/registry.md and README say M013b "closed" while the historical closure header says "conditionally closed", and the roadmap top/section M013b still marks "ready". The source stack has no main-targeted PR; green CI run 38107890553 at 11ea106c9af3b1ec362a98e709b530cc0fa137d0 is branch evidence, not main merge.

Historical observed M013a outcomes are supported and MUST NOT be changed: Binary text and combined shifts have Brier improvements -0.2696 and -0.2699 with group intervals wholly negative and adequate support (67/66); Choice accuracy improvement 0 with [0,0] paired interval, 44/44/45 answerable OOD groups and no prospective numeric thresholds, hence indeterminate. M013b's corrected same-option counterfactual measures remain an interpretive erratum, not a new final holdout.

## 3. Code ownership and invariants

Modify only offline evaluator/report scripts, focused constructed fixtures/tests, their CI invocation and current planning/docs. Candidate runtime, Rust training, feature encoder, artifact payload, version, calibration and default decision outcomes are UNCHANGED. Do not touch historical frozen files under fixtures/m011*, fixtures/m013*, docs/m013a-protocol-v1.md, scripts/analyze_m013a_quality.py or historical M013/M013a/M013b closure/evidence hashes. Preserve old M013b report reproduction and add a separately versioned M013c decision audit if new gate semantics alter serialized gate metadata.

Application authority stays with CodeGG or other consumers; SDM never grants permission, widens eligible candidates, captures application data, downloads external models, or automatically selects a production artifact. No corpus dependency. Rust 1.89 MSRV, runtime-only graph, Linux x86_64/ARM64 and Apple Silicon, 16 MiB typed v2 artifact bound and 4,096 Choice cross-term limit all stay intact.

## 4. Ordered implementation work

### A. Versioned CI-aware uncertainty gate (do FIRST)

1. Introduce an additive versioned quality-gate builder (for example scripts/m013c_evaluator.py / m013c_qualification_audit.py); preserve the old m013b_evaluator.py entrypoints for historical reproduction, or create a compatible thin wrapper with byte-stable archived output. No silent redefinition of the M013b analyzer format.
2. Accept an explicitly provenance-validated effect estimate, 95% grouped CI lower/upper and number of eligible independent groups. Check types and finite numbers; lower <= upper; supported sample count matches the exact reported group support; complete interval metadata (bootstrap method percentile, 10,000 replicates, seed 14014 for retrospective M013a); comparator direction and metric/task identity. Reject malformed or mismatched CI/method metadata as invalid; missing genuine estimability/support is indeterminate.
3. Define the 3-way Brier family confidence decision: lower > 0 with sufficient support => favorable; upper < 0 with sufficient support => unfavorable (critical required family => negative); CI spanning or touching zero => indeterminate. Maintain paired leakage-GROUP bootstrap rather than per-row uncertainty; no point-mean shortcut.
4. For Choice paired answerable accuracy, require lower > 0 and adequate independent eligible group count, *in addition* to every required OOD, answerability, calibration, counterfactual and baseline control gate. Keep current M013a null/unregistered positive thresholds as indeterminate, not invented success criteria.
5. Make minimum_group_support an explicit immutable field of each supported critical statistical gate and cross-validate its value against the protocol/family support gate. Never treat evidence_count=1 as enough. A critical negative with n<required is insufficient-support/indeterminate, while n>=required and upper<0 gives supported negative. If any mandatory data is missing or structurally inconsistent, overall verdict invalid; priorities: invalid > supported critical negative > insufficient/other failure indeterminate > positive.

### B. Required-set completeness, slice alignment and controls

1. Enumerate protocol-declared Binary required_families and Choice required_ood_families (including critical subsets) in deterministic order; assert each exact family exists and is unique, with a matching named report slice and correct task/family/provenance, exactly the expected group membership and candidate universe. Missing mandatory family is invalid, not silently omitted; unsupported present family is insufficient. Unexpected families must be rejected or explicitly identified as declared diagnostic-only and excluded from qualification.
2. Validate critical_families subset of required_families, no duplicates, no contradictory configurations; abort on invalid/missing protocol keys, empty mandatory arrays, invalid thresholds, non-finite intervals or mismatch of group/case identities between reports. Do not allow the gate evaluator to receive an incomplete set and label it positive.
3. Evaluate all five required Choice negative controls as separate, versioned measurements using the SAME answerable cases/group units and option IDs. Define the actual model-minus-baseline effect/CI for comparably scored controls; a selected learned candidate must satisfy the preregistered comparison to the meaningful fixed/deterministic controls before any positive verdict. Always-abstain's perfect no-answer recall alone cannot satisfy a learned improvement requirement. Shuffled-score and context-only controls cannot be silently replaced with a zero baseline or omitted.
4. The M013a original protocol lacks numeric thresholds for some controls and success gates. Record those gates as insufficient/unqualified if they cannot be established from the PREVIOUS frozen protocol. Do not backfill favorable post-test numeric thresholds. Allow future protocols to define comparisons and alpha/multiple-comparison policy BEFORE freezing.
5. Ensure the control inventory and primary comparison are explicitly task-scoped: constant train-prior Brier baseline for Binary and declared Choice deterministic controls; never treat cross-head comparison alone as proof of outperforming every negative control. Include per-gate denominator, statistic name, interval, protocol hash, rationale, population hash and status.

### C. Adversarial and historical-identity verification

1. Add fast constructed-only tests around the actual builder (not merely evaluate_gates() with hand-written Gate objects):
   - point improvement +0.02 but CI [-0.04,+0.08], n=67 => indeterminate;
   - point improvement -0.02 but CI [-0.08,+0.04], n=67 => indeterminate;
   - CI [-0.20,-0.04] at n=1/49 => insufficient, NOT negative; at n=50/67 => supported negative;
   - CI [+0.01,+0.13] at n=50 => favorable, at n=49 => insufficient;
   - zero boundary CI [-0.08,0.00] and [0.00,+0.06] => indeterminate;
   - wrong CI sign versus claimed mean, reversed bounds, NaN/Infinity, missing bootstrap metadata, malformed group ID => invalid.
2. Missing any required Binary family, missing noncritical Choice OOD, duplicate family, duplicate group IDs, critical family not in required list, omitted always-answer/shuffled/context-only control, invalid candidate sets => never positive (invalid if missing).
3. Fully populated constructed positive test requires every mandatory primary, family, support, negative-control, counterfactual, abstention and OOD gate to pass under an explicitly prospective mock protocol with numeric thresholds; remove ONE gate or drop ONE group's support => positive becomes unreachable. Legacy M013a frozen protocol must NEVER produce a positive on replay, even if new audit logic is run against it.
4. Rerun archived scripts/analyze_m013a_quality.py, scripts/m013b_audit_m013a.py and scripts/m013b_diagnostics.py mechanically; assert exact previously recorded output hashes and unchanged Binary negative/Choice indeterminate historical verdicts. Save a NEW named M013c audit as retrospective semantics correction, recording old-vs-new gate interpretation and provenance, not overwrite/falsely requalify previous reports.
5. Ensure tests run in seconds with constructed fixtures; the existing M011/M013a full CI remains mechanical regression, NOT a fresh quality test. Add focused M013c test command and CI step to fail if a mandatory gate can be skipped, a critical n<minimum labels negative or point means masquerade as confidence intervals.

### D. Roadmap, integration and release-state reconciliation

1. Resolve the M013b "closed" versus "conditionally closed" inconsistency using its historic closure header as authoritative: record **conditionally closed — mechanically complete, unmerged** in current-facing registry/roadmap/README. Preserve the original M013b closure file and its immutable SHA/evidence; if its wording needs interpretation, add a dated reconciliation note rather than editing archived results.
2. Register M013c as the ONLY ready corrective, with a hard dependency on existing M013b mechanics but no CodeGG corpus requirement. Its closure file is plans/closure/general-decision-model-framework/013c-status.md. State that prior speculative label M013c for predictive experiments is superseded by gate hardening; the next prospective model-quality plan will be separately numbered, e.g. M013d or M014 after source/qualification integrity. Do NOT register that successor as ready in this planning pass.
3. After implementation, record exact commit SHA, tests, immutable baseline hashes, old/new gate comparison, host CI, source ancestry and remaining risks in closure; update status to closed/conditionally closed only when supported. Prepare the unmerged M013/M013a/M013b/M013c stack as a reviewable MAIN-targeted PR after CI; separate opening the PR from merging it and from crates.io legal sign-off. Do not push directly to main.
4. Keep explicit independent external gates: CodeGG M005 has no approved corpus/consumer evidence, crates.io human/legal sign-off outstanding, no model promoted. Document package staging truthfully (cargo package --no-verify plus staged independent consumer), and keep source merge, publication and predictive effectiveness separate.

## 5. Failure, restart, and storage requirements

Analyzer inputs are read-only, with exact data/split/model/protocol/report SHA checks; new sidecar outputs are uniquely named, written to a temp file, validated then atomically renamed. Abort/mark invalid on missing required family, non-finite CI, duplicate/mismatched case/group, mismatched candidate identity, nonexistent required negative control, or manifest/threshold drift. A partial or interrupted run leaves no accepted report. Same run replay requires identical source, inputs, protocol and audit fingerprint; changed gate semantics must have a NEW evaluator version and must not mutate historic reports.

## 6. Verification to execute and document

Focused:
- python3 -m unittest discover -s scripts -p 'test_m013c_*.py' (new constructed builder/gate tests)
- python3 -m unittest discover -s scripts -p 'test_m013b_*.py' (all prior 47 evaluator/support tests)
- python3 scripts/validate_m013a_freeze.py (frozen split/provenance unchanged)
- python3 scripts/analyze_m013a_quality.py; python3 scripts/m013b_audit_m013a.py; python3 scripts/m013b_diagnostics.py with their target/ output hashes checked against recorded evidence
- new M013c audit CLI (to be named when implemented) asserting unchanged historical outputs, Binary negative and Choice indeterminate and all required gates enumerated

Broad:
- cargo fmt --all -- --check
- cargo test --workspace --all-features --locked
- cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
- cargo check -p sdm-runtime --locked; cargo tree -p sdm-runtime --locked
- cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked
- cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json
- Existing hosted 10-job Rust 1.89, Linux x64/ARM64, Apple Silicon and same trained-artifact portability matrix, package/license audits and staged package consumer. Do not claim local package registry verification if unavailable.

## 7. Closure acceptance and stop conditions

Pass: every required family/control gate exists and has immutable evidenced support; supported negative and positive decisions rely on CI bounds, not means; critical errors require protocol-minimum independent eligible groups; no incomplete/empty list or one-group critical failure can ever qualify; historical frozen output and model SHA identities remain unchanged; evaluator tests/CI green; docs/registry consistent; source integration PR disposition explicit and separate from predictive qualification.

STOP and register a further narrow corrective if the observed M013a test is used to choose thresholds/models, the original frozen protocol/results are rewritten, the historical Binary/Choice verdict flips without an acknowledged evidence-integrity cause, missing required families still pass, critical regression can be assigned with n<minimum, baseline comparison is effectively a nonnegative>=0 tautology, or old v1/runtime compatibility/host CI regresses.

## 8. Closure document obligations

Write plans/closure/general-decision-model-framework/013c-status.md with requirement-to-evidence matrix, exact source/PR/CI SHA and state, adversarial builder tests including CI edge/support cases, protocol/control completeness evidence, old/new decision sidecar hashes, unchanged M011/M013a/M013b identities, compatibility/privacy/security/package findings, negative/indeterminate outcomes and explicit release/merge/CodeGG gates. Only then mark M013c closed/conditionally closed in registry.

No M013d/M014 predictive experiment is approved or unblocked merely by writing this plan.
