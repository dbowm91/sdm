# M007 closure — Qualification depth and trained ablations

Status: closed (generic synthetic capability and evidence complete; no CodeGG effectiveness claim)
Implementation commits: `39c7af1c6baebfde8ac720ee35e6105fdca86a4c`, `699d972c6f80b027517a4ab68c521e718181d102`
Hosted benchmark artifacts: [CI run 38084623061](https://github.com/dbowm91/sdm/actions/runs/38084623061)
Final hosted verification after held-out fingerprint correction: [CI run 38084834012](https://github.com/dbowm91/sdm/actions/runs/38084834012)

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Deterministic per-slice calibration with minimum support | `sdm_eval::calibration_by_slice` sorts named slices, reports Brier/log-loss/ECE, preserves undersupported slices with undefined metrics, tags the complete report with protocol/dataset/split/artifact/calibration identities, and rejects test-partition observations. Unit tests cover deterministic ordering, undersupport, artifact mismatch and test-label rejection. | Pass |
| Frozen redistributable synthetic coverage for all semantics | `fixtures/synthetic-qualification-v1.json`; hand-authored MIT synthetic examples, explicit synthetic-only provenance, ordered Binary/Choice/Score/Rank examples. Data and evaluation tests pin order and canonical dataset digest `sha256:8a396c848873025e796833db4f3c20ba470a0ac98db6bb9e5dd7d94d58b62284`. Expected metrics for each semantic are pinned in tests. | Pass |
| Keep fitting/calibration away from test labels | Training test changes only held-out labels and verifies fitted weights, bias, dev-selected threshold, model digest and training fingerprint do not change. The artifact fingerprint is computed from the training partition only. Calibration input has an explicit partition tag and rejects `test`. | Pass for supported training/calibration logic; the dataset identity hash still covers the complete frozen dataset by design. |
| Train two bounded capacities and run context ablations | `cargo run -p sdm-nonlinear --example interaction_ablation --features training --locked`; fixed seed 20261010, 1,200 epochs, learning rate 0.04, 16 frozen context/candidate pairs. Golden report: `fixtures/synthetic-interaction-ablation-v1.json`; input digest `sha256:3d0ecefba761ee616574149218ff0e43ebac33ef61fd1af80f4ffa246e1ecceb`. | Pass as mechanics evidence only |
| Report utilization and ablation outcomes | 4 hidden units: 57/57 train-updated parameters, MSE `1.1510172016834982e-10`; 8 units: 113/113, MSE `6.009754456778443e-11`. Both achieve full-context accuracy 1.0, context-masked 0.75 and permuted-context 0.625. Model digests: `sha256:7113aaad4e7d6c531b7b4ff710afdd2f95db7a7c7bb205fb1028030de98d13a4` and `sha256:b28ea1c07ed303cdccb56ebbba0ac01bfb3e77c27dbc1c6f30772ef5a032a585`. | Pass; task is deliberately tiny and evaluation reuses training examples |
| Retain hosted Linux x86_64, Linux ARM64 and Apple Silicon runtime benchmarks | Hosted CI 38084623061 uploaded three platform reports. All share model digest `sha256:fc3bb30ddbf4f87fd55cb6c60e07cfa0b5946f2f0c3252e3eeb8eccdb1a8e48b`, artifact digest `sha256:fbfa1f9d4fa483ffc19ff6abd9f6e270f0325f36525b1d9b171f7bf76b56eb21`, artifact size 8,675 bytes, 500 samples/candidate count, and malformed-artifact rejection. | Pass |

Hosted runtime p95 latency in microseconds at candidate counts 1/16/64/128/256:

| Runner | p95 (µs) | Cold load (µs) | Peak RSS (bytes) |
| --- | --- | ---: | ---: |
| Ubuntu 24.04 x86_64 | 12 / 201 / 795 / 1,587 / 3,145 | 471 | 25,456,640 |
| Ubuntu 24.04 ARM64 | 25 / 419 / 1,582 / 3,146 / 6,183 | 1,691 | 24,514,560 |
| macOS 15 Apple Silicon | 22 / 405 / 1,894 / 3,205 / 7,509 | 1,210 | 2,703,360 |

The hosted runner toolchain was stable Rust 1.99.0 (`b940084d7`, 2026-09-28), targets `x86_64-unknown-linux-gnu`, `aarch64-unknown-linux-gnu`, and `aarch64-apple-darwin`. RSS conventions vary by OS and should not be compared directly. Hosted performance benchmark model is deterministically initialized, not trained; results establish runtime resource behavior only.

## Verification

- `rtk cargo fmt --all` — pass.
- `rtk cargo test --workspace --all-features --locked` — pass, 24 tests across 16 suites.
- `rtk cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — pass.
- `rtk cargo check -p sdm-runtime --examples --locked` — pass.
- `rtk cargo tree -p sdm-runtime --locked -e features` — pass; runtime includes `sdm-nonlinear` runtime support but not its training feature or training framework.
- `rtk cargo run -q -p sdm-data --bin sdm-dataset --locked -- validate fixtures/synthetic-qualification-v1.json` — pass, four examples and pinned dataset digest.
- `rtk cargo run -q -p sdm-nonlinear --example interaction_ablation --features training --locked` — pass; output matches the pinned golden metrics/digests above.
- `rtk cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json` — pass, 12 fixtures and 11 runtime executions; frozen artifact digest remains `sha256:b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597e`.
- Hosted run 38084623061 — all verification and benchmark steps passed on all three platforms.
- Hosted run 38084834012 — after the final held-out fingerprint correction, all verification and benchmark steps passed on all three platforms.
- `rtk git diff --check` — pass.

## Limits and disposition

The calibration API consumes caller-provided development observations with explicit partition tags; provenance of the tag itself remains the dataset/split producer's responsibility. The synthetic interaction experiment intentionally trains and scores on the same 16 examples. Its perfect full-context accuracy and ablation drops show that the small implementation can learn/use interaction features, not generalization or real-world quality. The hosted nonlinear performance artifact measures the initialized runtime model, not either trained capacity. No CodeGG data, source, pin, fixtures or configuration were changed. M005 remains indeterminate until CodeGG owners provide an approved independent corpus and consumer-owned adapter.

M007 is closed. No generic qualification-depth implementation work remains in this plan. The general framework line remains active only for the external M005 CodeGG evidence/ownership gate; this closure does not authorize model promotion or deployment.
