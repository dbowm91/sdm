# M001 closure — Versioned feature, artifact and runtime contracts

Status: closed  
Implementation commit: `e02fab714540868f5619e2c2dc2c6aaf0549d8eb`

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Add typed, versioned feature schema and projection | `sdm-core::{FeatureSchemaV2,FeatureProjectionV2}`; fingerprint, required/type/category/finite checks; unit test | Pass |
| Add bounded v2 artifact envelope and explicit version dispatch | `ArtifactEnvelopeV2`, 16 MiB and 1M parameter caps, payload digest validation; `load_artifact` returns explicit `UnsupportedV2`; unit test | Pass |
| Keep v1 API and exact artifact compatibility | Frozen artifact SHA remains `sha256:b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597`; 12 fixtures / 11 executions pass | Pass |
| Separate shared lexical features from architecture code | Stable v1 feature functions now live in `sdm-core`; runtime reexports preserve caller API | Pass |
| Keep runtime graph free of training/network/model services | `cargo tree -p sdm-runtime --locked` contains `sdm-core` and serialization/hash/error dependencies only | Pass |
| Document compatibility and resource model | `docs/artifact-format.md`, `docs/reproducibility.md`, README | Pass |

## Verification

- `rtk cargo fmt --all -- --check` — pass.
- `rtk cargo test --workspace --all-features --locked` — pass (15 tests across 16 suites).
- `rtk cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — pass.
- Runtime/example checks — pass.
- Frozen compatibility command — 12/12 fixtures; 11/11 executions; artifact digest unchanged.
- Benchmark on this Apple Silicon host: artifact 2,560 bytes; cold load 482 µs; p95 317/1,221/2,405/4,809 µs for 16/64/128/256 candidates; peak RSS 4,689,920 bytes. These are single-host observations, not release budgets.

## Compatibility and disposition

No v1 artifact, fixture, CodeGG source, pin, or runtime behavior was changed. V2 envelope hashes are corruption/identity checks, not authenticity. A valid v2 envelope without an implemented engine remains Unsupported. No migration or network access was introduced. M001 is closed.
