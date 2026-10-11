# SDM General Framework M001 — Versioned Feature, Artifact and Runtime Contracts

Status: closed
Primary class: infrastructure
Repository baseline: dbowm91/sdm@8139b064bdcf3212e8f6fd912e801a479b55751c
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md#m001--versioned-featureartifactruntime-contracts
Accepted ADR: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Hard dependencies: none
Interface dependencies: pinned CodeGG v1 compatibility fixtures and immutable baseline artifact
Output consumer: M002 dataset schema; M004 architecture runtime; existing CodeGG unchanged

## 1. Objective

Establish additive typed feature projection and generic architecture/artifact dispatch, with exact v1 compatibility and bounded runtime-only dependencies. The milestone creates a usable schema/runtime contract without promising a new model, improved predictions or CodeGG activation.

## 2. Audit evidence

- crates/sdm-core/src/lib.rs: DecisionRequest/DecisionSpec/DecisionResponse v1; string StateField, textual candidates; validates Binary, Choice, Score, Rank.
- crates/sdm-runtime/src/lib.rs: LinearArtifact v1, hard-coded sdm-binary-linear-v1, MAX_ARTIFACT_BYTES = 4 MiB, max weights 100k; only Rank; Runtime::from_bytes and Runtime::decide validate request/response.
- crates/sdm-training/src/lib.rs imports sdm_runtime::features_for, coupling training feature extraction to this one runtime implementation.
- artifacts/compatibility-rank-v1.json is frozen, unqualified; expected SHA-256 full artifact b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597e; 12 frozen fixtures, 11 valid requests.
- codegg consumer pins full commit 8139b064bdcf3212e8f6fd912e801a479b55751c; no modifications to that checkout are authorized in M001.

## 3. Invariants

- Preserve all existing public v1 Rust APIs, JSON shapes, semantic meanings, v1 digest algorithm and fixture results. Do not rewrite the frozen v1 artifact or compat dataset.
- Runtime-only builds have no training dependency, GPU/Metal requirement, Python/network client, or implicit model download.
- A feature ID/field is data, never tool execution authority. No arbitrary script, dynamic library, symlink traversal or uncontrolled allocation from an artifact.
- Reject non-finite numbers, unknown required feature types, unsupported version/architecture, duplicate IDs, malformed/oversized tensor declarations and inconsistent capabilities.
- Immutable validated artifact state after load. Explicit Unsupported for a valid-but-unsupported semantic/feature profile; invalid artifacts fail load, never partially initialize.
- Keep CodeGG candidate IDs exactly as supplied and do not synthesize new candidates.

## 4. Expected changes

- sdm-core: additive FeatureSchemaV2, typed bounded FeatureValue (text, finite numeric, bool, bounded categorical), FeatureProjectionV2, stable feature IDs, required/optional semantics and schema fingerprint. Define explicit adaptation from old state fields only when semantics are unambiguous. Do not retroactively reinterpret v1 text as numeric. Retain all four decision semantics.
- sdm-runtime: versioned ArtifactEnvelope/manifest (new v2 path, separate from LinearArtifact v1); architecture identity, required schema hash and capability set, per-architecture maxima for artifact bytes/parameters/tensor dims/state/candidates, calibration identity and source/license metadata.
- Dispatch: explicit enumerated architecture loader and bounded Engine interface, with v1 linear adapter first. Do not implement dynamic loading, runtime external plugin execution or a second learned architecture in this milestone. Preserve Runtime::from_bytes and Runtime::decide for existing callers.
- Shared feature computation: identify which lexical feature functions are reusable between trainer and runtime and move them to a neutral shared module/crate without changing v1 scores; retain compatibility reexports as needed. Do not import sdm-training into runtime.
- Docs: update docs/artifact-format.md, docs/reproducibility.md and README with version migration and capability/size matrix. v1 uses its original 4 MiB limit; v2 has explicit per-architecture limits, not one raised global cap.

## 5. Ordered work packages

A. Freeze compatibility evidence. Record v1 artifact raw SHA, v1 request/response golden examples, all malformed fixtures, public source exports and cargo tree before any code modification. Add tests that replay the exact compat corpus.

B. Specify contract. Introduce FeatureSchemaV2 and FeatureProjectionV2 structs; specify canonical serialization/fingerprinting, max lengths, duplicate handling, missing-value rules, categorical vocabulary and version semantics. Prefer explicit constructor validation over partially valid deserialization.

C. Artifact v2 and dispatch. Implement bounded, fail-closed version differentiation, immutable snapshot and an architecture registry that initially dispatches only the existing linear model. Distinguish corruption, Unsupported architecture and Unsupported request semantics. Ensure digest checks cover serialized weight bytes and schema/calibration identity; record that hashes are identity, not authenticity.

D. Separate shared feature transformation from architecture-specific runtime code. Prove v1 feature/score parity across independent inputs and adversarial edge cases.

E. Update docs, add static dependency guards and capture resource delta compared with docs/benchmark-baseline.md.

## 6. Storage, restart and concurrency

No database migration. Old artifact JSON continues to load byte-for-byte with existing Runtime entrypoints. New envelope uses a new explicit schema version; do not mutate or auto-rewrite old files on load. File loading uses bounded reads and rejects truncation or trailing unsupported fields as required by the explicit schema. A running engine holds a validated immutable snapshot; replacing a path affects only a newly loaded engine. No stateful background jobs or cancellation owner is added.

## 7. Failure and security tests

- Serialization roundtrips for every new feature type; reject NaN, ±inf, precision/overflow pitfalls, duplicate IDs, oversized text, unknown required field/type and mismatched schema hashes.
- Malformed/bomb-sized array dimensions, unknown architecture, unknown artifact version, forged model/calibration hashes, capabilities not supported by engine and invalid UTF-8 JSON.
- Property/golden cases preserving v1 candidate identity/response/provenance; randomized ordering stability where semantics allow.
- Runtime-only cargo tree must exclude sdm-training, sdm-data, ML training frameworks, HTTP clients, and model downloader; no machine-specific platform APIs on baseline CPU path.
- Cold load and candidate scaling benchmark unchanged workload, record new-vs-old numbers without asserting regression budgets that were never agreed.

## 8. Verification

Existing commands (must run on implementation revision):

~~~sh
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo check -p sdm-runtime --locked
cargo check -p sdm-runtime --examples --locked
cargo tree -p sdm-runtime --locked
cargo run -p sdm-training --bin sdm-check-compat -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json
cargo run -p sdm-runtime --example benchmark -- fixtures/benchmark-rank-request.json artifacts/compatibility-rank-v1.json
~~~

Add focused commands/tests for v2 schema, invalid envelope and v1/v2 engine dispatch. If running against CodeGG checkout, use its scripts/check_sdm_compatibility.sh with full immutable existing SDM revision for old baseline; do not change CodeGG's pinned runtime in this milestone.

## 9. Acceptance and stop conditions

Close only when an independent program can construct a typed feature projection, match it to a manifest and select a compatible runtime; old public v1 API still accepts the frozen artifact; all 12/11 fixture checks pass; corruption and unsupported cases fail closed; runtime-only graph is clean; docs show exactly which semantics are implemented. Tests must prove no CodeGG source/config change is required.

Stop and register a corrective if v1 digests or predictions drift, the new schema requires silently coercing old text fields, runtime-only deps pull in training or network, artifact dimensions can exhaust memory before validation, or capability declarations imply unsupported semantics.

## 10. Closure evidence

Create plans/closure/general-decision-model-framework/001-status.md with SHA/PR, schema compatibility matrix, artifact hashes, golden test results, dependency trees, host/resource measurements, security negatives, documentation delta, migration/no-migration evidence, outstanding risks and registry status transition. M002 becomes ready only after positive M001 closure.
