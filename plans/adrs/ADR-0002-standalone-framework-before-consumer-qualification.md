# ADR-0002 — Standalone Framework Before Consumer-Specific Qualification

Status: accepted
Date: 2026-10-10
Baseline: dbowm91/sdm@319a05805f3a8383574d0d0712ca5975d16546ff
Prior decision: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
External authority: CodeGG ADR-0013 (generic model work belongs to SDM; candidate authority and actuation remain in CodeGG)

## Context

The implemented M001–M007 work establishes typed schemas, provenance-bearing datasets and splits, generic metrics, linear and nonlinear Rank trainers/inference, and hosted cross-platform CPU resource evidence. M007 trains and evaluates a tiny synthetic interaction model on the same sixteen examples; this is mechanics evidence, not held-out generalization. The separate current CLIs are not yet a coherent independent dataset -> train -> calibrate -> artifact -> infer -> qualify workflow. The v2 typed feature projection is validated but nonlinear Rank inference still constructs lexical features from string state and candidate descriptions. Binary, Choice and Score have labels/metric code but no trainable and deployable model heads.

There is no suitable CodeGG training or unbiased held-out corpus. Its frozen twelve compatibility fixtures (eleven runnable requests) and four-case training smoke are not predictive-effectiveness datasets. M005 is rightly recorded as indeterminate.

## Alternatives and decision

Waiting for CodeGG data couples the framework to an external application bottleneck and is rejected. Declaring synthetic training-set memorization sufficient is rejected. Jumping to a much larger language model is deferred: it does not solve interoperability, leakage or product contract gaps.

Instead, make SDM independently usable and verifiable first:

1. M008: one reproducible, frozen-split Rank experiment path spanning data, training, dev calibration, artifact, runtime and qualification, with both supported architectures.
2. M009: task-neutral, validated typed-feature ingress shared by the train and infer paths.
3. M010: minimal trained Binary, Choice and Score heads, semantically correct output and evaluation, in addition to existing Rank.
4. M011: independent held-out synthetic datasets, actual trained-artifact cross-platform benchmarks, Rust 1.89 verification, public usage docs and release-candidate gates.

The implementation plans are hard-dependency ordered. M005 remains conditionally closed/indeterminate and externally deferred, not a prerequisite for M008–M011. No data is fabricated on CodeGG's behalf; no new model is promoted there. Existing v1 wire format, linear artifact digest, twelve/eleven compatibility checks, historical negative evidence and explicit Unsupported semantics are permanent invariants.

Libraries own bounded semantics, feature transforms and model construction. An explicit experiment/CLI layer owns file IO, local paths, writing artifacts and reports; the inference-only crate may not depend on training/data/eval crates, network clients, providers or GPU requirements. Fitted model identity excludes final-test labels; dataset-wide provenance may include them for reporting. Model validation, held-out usefulness, and downstream deployment permission are separate decisions.

## Consequences

A small additional CLI/orchestration layer and task-specific heads increase maintenance surface, but allow independent application use and meaningful qualification. Synthetic held-out pass or fail establishes test mechanics and a limited generalization result only for that synthetic distribution, not real-world tool selection. A separate CodeGG-owned adapter, approved dataset and independent tests remain necessary before any model or pin is changed in CodeGG. This ADR supplements, rather than rewrites, ADR-0001 and the M001–M007 closure records.
