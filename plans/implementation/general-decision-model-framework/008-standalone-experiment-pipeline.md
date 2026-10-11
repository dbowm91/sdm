# SDM M008 — Standalone Reproducible Rank Experiment Pipeline

Status: ready
Class: capability/infrastructure
Baseline: 319a05805f3a8383574d0d0712ca5975d16546ff
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md
ADRs: ADR-0001 and ADR-0002
Hard prerequisites: none; implemented M001–M007 interfaces available; CodeGG data is NOT required
Unblocks: M009

## Objective

A fresh user checkout must support one documented experiment workflow from explicitly supplied local, provenance-bearing Rank dataset through validation, immutable group-aware train/dev/test split, fitting a linear or nonlinear model, dev-only calibration, safe artifact packaging, actual runtime inference, and a fingerprinted held-out qualification report. Expose a reusable Rust orchestration API and a discoverable CLI entrypoint. Retain the existing legacy CLIs and original v1 artifact.

## Existing code evidence

- sdm-data: DatasetExample/TargetLabel, provenance, bounded import, group-disjoint frozen SplitManifest, sdm-dataset validate/split.
- sdm-training: legacy DecisionCase JSONL, internal hash split and linear trainer; sdm-train uses fs::write and does not consume sdm-data split manifests.
- sdm-nonlinear: seeded PairwiseModel training and bounded v2 model/runtime; example interaction_ablation trains and scores on the same 16 synthetic pairs.
- sdm-eval: protocol identity, semantic metrics, RankPrediction; sdm-qualify currently expects precomputed Rank predictions.
- sdm-runtime: v1 linear and v2 nonlinear loading; original compatibility suite is 12/11.

## Work packages

A. Specify ExperimentSpec and ExperimentRunManifest. Include dataset/provenance digest, split fingerprint, architecture, feature schema and preprocessing identity, source revision, seed, hyperparameters, dev calibration policy, frozen qualification gates, output paths and explicit train/dev/test roles. Freeze protocol before test labels are used.

B. Add a reusable orchestration layer (small sdm-experiment crate if needed) and library training adapters. Train linear and nonlinear Rank directly from sdm-data Rank target labels using the exact supplied SplitManifest. Avoid synthesizing CodeGG DecisionResponse labels or accidentally using the legacy trainer's own hash partitioning. Maintain old sdm-training::train behavior as a compatibility wrapper.

C. Fit weights from train only; select threshold/calibration on dev only. Bind model identity to train inputs/config and calibration to dev; changing only test labels cannot affect either. Create both architecture-specific immutable artifacts and load the newly trained weights through sdm-runtime, not a second ad hoc scorer. Generate predictions for exactly the original candidate IDs.

D. Provide a documented command such as sdm experiment run --config PATH, with final spelling fixed by tests. Keep existing sdm-dataset, sdm-train, sdm-qualify syntax functional. Use bounded local reads, temp file plus verified atomic finalization, no implicit scanning, overwrite protection, fingerprint validation, clear nonzero operational failure and separate pass/fail/indeterminate quality verdict.

E. Check in a redistributable non-CodeGG Rank corpus with sufficient disjoint groups for train/dev/test, multiple relevant candidates, zero-relevant/abstain, hard negatives and counterfactual pairs. Include deterministic baseline, deliberately bad negative control, and documented positive *mechanics* control. New held-out examples cannot be the same 16 training interactions; results do not claim real-world quality.

F. Publish CLI and library quickstart; CI executes both model architectures end-to-end from dataset to loaded artifact to metrics, not simply calls the existing example. Document fingerprints, allowed inputs, failure handling, no-network and resource caps.

## Security, restart and invariants

No CodeGG corpus, session capture, provider calls or runtime decision authority. A frozen split may not silently resplit when source changes. Fit APIs must prevent reading held-out test labels; use partition-aware types and test mutation evidence, not trusting a free-form string. On cancellation or crash, retain last fully verified artifact/checkpoint only. Model snapshots are immutable. Keep sdm-runtime dependency tree free of sdm-training/sdm-data/sdm-eval and network/optimizer dependencies. Preserve original LinearArtifact v1 bytes and fixture outcomes.

## Verification

Standard cargo fmt --all -- --check, cargo test --workspace --all-features --locked, strict all-target Clippy, cargo check -p sdm-runtime --locked, cargo tree -p sdm-runtime --locked, sdm-check-compat with frozen 12/11. Add CLI integration tests: repeated deterministic artifact hash, train/dev/test group disjointness, corrupted split/hash/candidates, interrupted file output, all-negative data, unknown architecture, and changing test labels without changing model/calibration. Compare trainer direct scores to reloaded artifact scores within declared tolerances. Run the full command in Linux x64/ARM64/macOS ARM64 hosted CI where feasible.

## Exit and closure

Close on a repeatable real trained artifact and frozen held-out report for both Rank architectures, unchanged compatibility, exact candidate identity and no data leakage. Negative or indeterminate synthetic predictive quality is acceptable; incomplete orchestration is not. Stop on test contamination, runtime dependency graph violation, implicit CodeGG requirement, or artifact identity drift.

Closure: plans/closure/general-decision-model-framework/008-status.md, including commit SHA, exact end-to-end commands, dataset/split/train/dev/model/protocol digests, outcomes, CI, dependency checks, compatibility and residual failures. Register M009 ready only after accepted closure.
