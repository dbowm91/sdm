# SDM M011 — Independent Held-Out Qualification and Release Readiness

Status: blocked (hard M010)
Class: capability/release infrastructure
Planning baseline: 319a05805f3a8383574d0d0712ca5975d16546ff; re-audit at start
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md
ADRs: ADR-0001 and ADR-0002
Hard prerequisites: M008–M010 accepted closures
External dependency: none; no CodeGG corpus required

## Objective

Prove the complete standalone framework on genuinely *unseen* synthetic test scenarios, then create a reviewable Rust library/CLI release candidate. Verify current stable and declared Rust 1.89 MSRV, cross-platform portability of actually trained artifacts, public API/format documentation and no training or network dependencies in runtime-only builds. Do not publish or merge automatically and do not claim application-level model effectiveness.

## Why this remains necessary

M007's 16-example trained ablation assesses the same training examples; its four-semantic fixture contains one example per family, insufficient for learned qualification. Hosted 3-target benchmarks measured initialized nonlinear Rank artifacts, not independently trained artifacts. Existing stable Rust CI was recorded at 1.99.0 despite Cargo.toml declaring MSRV 1.89. README still describes M001 as ready. These are unresolved release-readiness issues even though M007 generic mechanics were closed.

## Ordered work packages

A. Design and freeze redistributable, generator-versioned synthetic data suites for all supported tasks: independent leakage groups, task-family and counterfactual exclusions, train/dev/test partitions with sufficient class support, no-answer and out-of-distribution slices, and different examples at evaluation time. Preregister gate metrics, baselines, grouped uncertainty, minimum slice support, resource targets and artifact/protocol hashes BEFORE test evaluation. Preserve synthetic provenance and explicit non-transferability.

B. Execute trained linear/nonlinear/head comparisons on identical candidate/feature universes and splits; add a failing negative control and a held-out counterfactual. Report positive, negative and indeterminate gates without redefining them after test observation. Validate that train/dev artifacts and normalization are invariant under held-out-only label mutation, while dataset/report lineage may change.

C. Run complete dataset->trained artifact->reloaded runtime->qualification examples as CI integration tests, not only unit/synthetic memorization. Benchmark trained artifacts on hosted Linux x86_64, Linux ARM64 and native Apple Silicon, with toolchain, model SHA, bytes, parameter counts, cold load, process RSS, malformed rejection, p50/p95 at 1/16/64/128/256 candidates, and explicit comparison limits against earlier initialized benchmarks.

D. Add an explicit pinned 1.89 CI check/test job with locked deps and record rustc -Vv; if impossible because of dependency changes, correct the declared MSRV or dependencies and document breakage, rather than claiming unverifiable support. Keep stable full three-platform fmt/test/Clippy. Guard runtime-only graph against sdm-training, sdm-eval, external ML optimizers, GPU runtime, HTTP/download code.

E. Freeze and document user-facing API/CLI and artifact/version contracts, semantic capability matrix, sample standalone Rust consumer, security/error/abort handling, source license/provenance, model selection, extension guide and reproducible Quickstart without hand-editing intermediate prediction JSON. Reconcile README and planning registry to the actual closure states.

F. Build a release-candidate audit: exact commit/tree, cargo package/publish dry-run only if applicable, dependency/license audit, semver/migration and signed/unsigned artifact trust statement (SHA verifies identity, not authenticity), all open defects with severity, reproducibility/report bundle and review PR option. A qualifying commit is not CodeGG deployment permission.

## Failure and stop rules

No implicit collection, downloads, provider calls, CodeGG tests beyond frozen compatibility, execution permissions, or automatic remote model activation. A frozen v1 artifact and 12/11 compatibility remain exact. An interrupted pipeline cannot leave partially accepted trained weights. Undefined low-sample metrics remain indeterminate. Stop if tests leak across partitions, train-set memorization is presented as generalization, MSRV is unverified, artifact is only randomly initialized, CLI task support exceeds actual head support, or format compatibility is broken silently. Register a corrective rather than relaxing a gate.

## Closure and handoff

Release-ready only if independent held-out runs across all supported task families succeed as mechanics, negative controls behave correctly, artifacts reload cross-platform, MSRV assertion is verified and documentation matches code. Predictive quality may still be negative/indeterminate with declared limits. Record plans/closure/general-decision-model-framework/011-status.md with commands, SHAs, train/dev/test dataset/artifact/report/protocol fingerprints, metric intervals, CI links, resource matrix, errors, compatibility, security and migration audit, and disposition. Do not publish, auto-merge to main or alter CodeGG's pin without a separately approved workflow.
