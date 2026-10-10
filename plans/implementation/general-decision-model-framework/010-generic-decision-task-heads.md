# SDM M010 — Trainable Binary, Choice and Score Decision Heads

Status: blocked (hard M009)
Class: capability
Planning baseline: 319a05805f3a8383574d0d0712ca5975d16546ff; re-audit when ready
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md
ADRs: ADR-0001 and ADR-0002
Hard dependencies: M008 pipeline and M009 typed feature ingress closed
Unblocks: M011

## Objective

Establish complete train/calibrate/package/infer/evaluate verticals for the three semantics already present as validated labels and metrics but not yet as learned local decisions. Use simple bounded heads over M009's task-neutral typed inputs; leave Rank working. A generic model framework must not pretend that having metric functions alone means a semantic has a usable runtime head.

## Starting point

sdm-core DecisionSpec supports Binary, Choice, Score, Rank. sdm-data TargetLabel includes all four. sdm-eval has evaluate_binary, evaluate_choice, evaluate_score and evaluate_rank, but its CLI currently reports only Rank predictions. sdm-runtime's two trained architecture paths return Unsupported for non-Rank semantics. Linear and nonlinear training is currently Rank-only. This plan requires no new CodeGG data.

## Ordered work packages

A. Introduce declarative task/head capabilities with architecture ID, input dimensionality, label rules, calibration version and immutable artifact digest. Use additive artifact versioning, preserve explicit Unsupported for old Rank-only artifacts, and keep policy/actuation in caller.

B. Binary: train lightweight bounded logistic or small MLP head on validated Binary targets. Output a finite calibrated probability for true/false, validated DecisionAnswer and explicit dev-chosen threshold/abstention policy; evaluate Brier, NLL, confusion/F1, calibration by slice where defined. No test-driven tuning.

C. Choice: learn a small bounded mutually exclusive head with normalized probabilities over exactly the approved option IDs, variable K within request limit; decide no-choice only when independently specified and calibrated. Reject missing/duplicate/unknown options, invalid probability sums and forced conversion of multi-relevant Rank to Choice. Evaluate accuracy/top-k and proper loss where available.

D. Score: train bounded regression/ordinal output with stated rubric min/max and deterministic range handling; use original scale for MAE/RMSE and define abstention when model cannot represent the input. Reject malformed bounds, nonfinite score and out-of-rubric answers.

E. Generalize M008 CLI and sdm-eval reporting to route all four semantic families with semantically valid prediction structures. Freeze metrics/gates/normalization before final-test inspection; compare to constant/class-prior/heuristic baselines under exactly the same partitions. Support honest indeterminate when few samples.

F. Include synthetic independent non-CodeGG tasks for each head with disjoint train/dev/test examples, normal and failure cases, unknown categorical values, no-answer/abstain and counterfactuals. Train actual artifacts, reload through sdm-runtime and produce algorithm-neutral qualification reports. Document how future applications add features without changing core.

## Safety and compatibility

Input/candidate IDs and option lists remain caller-controlled. No decision authorizes tool usage, safety bypass, model routing provider calls or other external actions. No network, downloads or large training backend. Versioned artifact validators enforce size, feature schema, architecture, task semantics and calibration provenance before allocation. Crash/restart and immutable output policies are inherited from M008. Preserve linear v1 artifact checksum, Rank predictions and 12/11 fixture behavior. Do not fit on test or claim synthetic generalization to production.

## Verification and closure

Test output validity and loss goldens across Binary/Choice/Score/Rank, invalid/empty options, no-choice policy, all-negative Binary, numerical edges, malformed artifacts and unsupported semantics. Run four end-to-end train->save->reload->infer->evaluate workflows from local synthetic input using the same CLI, with dev-only tuning and held-out mutation tests. Run workspace fmt/test/all-target strict Clippy, runtime dependency graph, frozen compatibility and three hosted CPU targets where possible.

Close only once all four semantic families have actual supported end-to-end *mechanics* paths; failed synthetic quality gates may remain valid negative evidence, but missing serving heads or CLI paths do not close. If a task family cannot fit coherently in one agent pass, stop and register a named M010 corrective/split rather than silently shrinking acceptance.

Closure: plans/closure/general-decision-model-framework/010-status.md including heads, schema/model/calibration digests, exact commands, numerical tests, negative cases, compatibility, resource impact, CI and registry update. M011 only after accepted closure.
