# M009 closure — Task-neutral typed feature ingress

Status: closed for typed Rank train/infer mechanics; no quality or application claim
Implementation commit: `6c49fedfcf8f8711ce8fe5079553f4328b95e730`
Hard predecessor: M008, closed in 008-status.md

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Additive typed dataset binding with exact candidate ownership | `DatasetExample.typed_rank_features` is optional and omitted when absent, preserving legacy row serialization. Typed rows validate schema, projection values, and exact candidate ID set. Typed split manifests use version 3; legacy untyped splits remain version 2. | Pass |
| Canonical train-fitted preprocessing | `FittedFeatureEncoderV2` canonicalizes feature and category order; finite numeric coordinates use train-only centering/scaling and clipping; booleans are scalar; categories use declared one-hot coordinates; text uses a sorted train-only bounded token vocabulary. Missing optional values encode as zeros; missing required values and undeclared categories fail validation. Metadata is fingerprinted and validated before inference. | Pass |
| Training and inference share the same encoder | `sdm-experiment` fits the encoder only from selected train context/candidate projections. `sdm-runtime` stores it in the typed artifact and uses its exact `encode` implementation for typed runtime inference. | Pass |
| Versioned runtime contract, legacy compatibility | New `sdm-typed-linear-rank-v1` envelope is dispatched explicitly as `LoadedArtifact::TypedRankV2`. Legacy v1 linear and lexical nonlinear inference paths are unchanged. Typed projections cannot be passed through the ordinary v1 `decide` path. | Pass |
| Synthetic non-CodeGG numeric/category/boolean example | `fixtures/standalone-typed-rank-v1.json` contains 36 synthetic examples with numeric load, boolean active, declared task category and text note fields. Frozen split v3 fingerprint: `sha256:d4c6345ab3a536705f81a9cadf119cb108ee6823a574b971af9246b3e4f0dbd3`; dataset digest: `sha256:a845b778f7dc6a1a51af1dc1b8b04e8fdf9be46d3fca727e0aa9480ee8af5cd0`. The checked-in experiment config executes train -> artifact -> reload -> typed infer -> held-out metrics. | Pass as mechanics only |
| Perturbation, corruption and identity checks | Tests cover schema-hash mismatch, NaN numeric value, finite extreme numeric clipping, corrupted normalization, held-out label and feature mutation invariance for model/calibration hashes, and rejection of injected candidate IDs. | Pass |
| Dependency and format compatibility | Runtime dependency tree contains only core/runtime support and `sdm-nonlinear`; no data/training/evaluation/experiment dependency. Frozen v1 compatibility command remains 12 validated fixtures, 11 runtime executions with digest `sha256:b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597e`. | Pass |

## Observed typed run

The end-to-end held-out run reports 9 test cases, exact candidate-universe coverage 1.0, MRR/Recall@5/NDCG 1.0, and disposition `synthetic-mechanics-only`. Artifact digest: `sha256:4ebf0c21839e2633fd016c1fe16438998afa49ef5962c01a3b205737b08cd424`; model payload digest: `sha256:b1626109151251f19031df4a8dd81c0816b270ffd1f62b3fb083fe9e7fe7dd57`; calibration digest: `sha256:ba263ca341182964ebb0f1fc6db96c33833fd4c91064109b11367013933389a5`. This small fixed synthetic rule task does not establish generalization.

## Verification

- `rtk cargo fmt --all` — pass.
- `rtk cargo test --workspace --all-features --locked` — pass, 30 tests across 19 suites.
- `rtk cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — pass.
- `rtk cargo check -p sdm-runtime --locked` — pass.
- `rtk cargo tree -p sdm-runtime --locked` — pass; no training, data, evaluation, or experiment crate in runtime graph.
- `rtk cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json` — pass, frozen 12/11 outcome.
- `rtk cargo run -p sdm-experiment --bin sdm --locked -- experiment run --config fixtures/standalone-typed-rank.experiment.json` — pass on local Apple Silicon.
- Hosted Linux x86_64, Linux ARM64 and Apple Silicon typed runs are configured in CI but have not yet completed for this revision.

## Risks and disposition

Numeric preprocessing uses max-absolute train scaling with a fixed [-5, 5] clip. Text vocabulary is capped at 4,096 tokens per declared field; total encoded width is capped at 2,048. These are explicit format behavior and require a new architecture/version to change. Artifact hashes establish identity, not authenticity. No raw user data or network access is involved.

M009 accepted. M010 is ready. M005 remains unchanged and externally gated.
