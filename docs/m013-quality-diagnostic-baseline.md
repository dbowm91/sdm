# SDM M013 — Frozen Quality Failure Diagnostic Baseline

Status: planning analysis only; hypotheses need independent implementation tests
Source: dbowm91/sdm@2bd0d5af16d143828dcbce77f411b8f3b675e7be on 2026-10-10 (America/New_York)
Prior evidence: docs/m011-local-results.md and plans/closure/general-decision-model-framework/011-status.md
Implementation handoff: plans/implementation/general-decision-model-framework/013-predictive-quality-corrective-and-independent-qualification.md

## What was observed

M011 tested new 400-example-per-task synthetic suites, grouped paired counterfactuals and frozen OOD families. Binary had overall Brier delta +0.0045 (95% grouped interval crosses zero), but OOD Brier improvement -0.2589, CI [-0.2825,-0.2356]. Choice's answerable accuracy tied the majority baseline, and 0 of 35 target-changing pairs changed the *final* Choice prediction; 8/22 no-answer decisions abstained. These are known negative/indeterminate outcomes, not tuning data. Score and Rank had positive synthetic aggregate metrics; no real-world qualification exists.

## Likely Choice representation failure (to prove)

Current training builder in crates/sdm-experiment/src/lib.rs typed_task_vector concatenates context, item and only same-coordinate elementwise products (context[i]*item[i]). Choice inference in crates/sdm-runtime/src/lib.rs score constructs identical coordinates. In scripts/generate_m011_synthetic_suite.py the candidate projections have context values active, available, load and note copied into BOTH options, with task_kind changed to the option identity. The Choice context has task_kind=choice; item categories are yes or no. This makes context-active/available effects largely shared between options. A diagonal product cannot express cross-coordinate active(context) × yes(item) versus active(context) × no(item); context.task_kind=choice and candidate.task_kind=yes/no one-hot slots also do not overlap. Constant option preference can persist while context active flips the target. This is a representability hypothesis, not proof that training is otherwise correct.

Use a four-quadrant truth table and the raw logit DIFFERENCE between yes and no to prove/disprove the limitation, then a bounded new cross-coordinate candidate-conditioned architecture. If candidate-specific original features actually survive or another component creates a cross-coordinate mapping, revise the hypothesis based on executable evidence.

## Likely Binary nuisance/shift failure (to prove)

Binary label in the M011 generator is (active AND available). OOD cases change load to roughly 12–20 from the non-OOD 0–10 range and replace note tokens with unseen terms, despite unchanged label rule. The typed encoder uses train-fitted numeric center divided by max-absolute scale with a [-5,5] clamp; unseen text coordinates encode as zero. A linear head trained on 120 epochs of deterministic SGD may overfit nuisance features, extrapolate or be miscalibrated under shift. Use load-only, note-only and joint counterfactual ablations and label-stratified residuals. Distinguish incorrect probabilities from dev confidence abstention; do not assume any particular single cause without observed feature-level tests.

## Metric/reporting mismatch to audit

scripts/analyze_m011_qualification.py calculates Choice correctness from the final runtime prediction (which can be null due to abstention), while crates/sdm-experiment/src/lib.rs evaluate_choice receives raw option probability vectors only for answerable cases. Both are useful but distinct estimands. M013 should report option quality conditional on answerability, answerability separation, realized selection coverage, no-answer recall, false abstention, and selective risk. A model that always abstains must not appear artificially accurate by avoiding answers.

The current analysis script reports 'counterfactual_prediction_changed' on final decision equality; add separate underlying raw-logit, conditional-probability, final-answer, and target-correctness diagnostics. Bootstrap group units must be independent leakage groups, not individual paired rows.

## Preserved evidence / prospective design

Do not edit M011 generator, original dataset, split, protocol, reports or SHA baselines. Freeze a new M013 dataset/protocol/membership commit before the final unseen evaluation. At least 50 independent groups per primary comparison/slice are requested to avoid the underpowered M011 Choice OOD/no-answer partitions; maintain a smaller explicitly indeterminate slice if unavoidable. Preregister baseline, primary metric, grouped confidence intervals, selection budget, stop criteria and shift type. Keep CodeGG excluded because no provenance-approved corpus currently exists.

Literature orientation (methodology, not framework dependency): Liang, Peng, Sun, Selective Classification Under Distribution Shifts, Transactions on Machine Learning Research (2024), https://mlanthology.org/tmlr/2024/liang2024tmlr-selective/ . Risk-coverage and fixed-selector comparisons are informative when an abstention head may fail under shift. The paper does not validate SDM or imply a chosen policy should succeed.

## Why this is a bounded corrective

M013 should minimally fix a demonstrably insufficient Choice representation, diagnose Binary shift failure, clarify calibrated abstention, and obtain a new prospective comparison. It should not adopt a general neural trainer, introduce mandatory tensor runtimes, change CodeGG permissions, fetch third-party datasets implicitly, or claim synthetic positive results imply production usefulness.
