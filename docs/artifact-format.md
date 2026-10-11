# Artifact format v1

Artifacts are bounded JSON `LinearArtifact` values with a versioned manifest,
architecture identifier, semantic capability declaration, request limits, model
parameter digest, training fingerprint, MIT license metadata, and source identity.
The manifest pins input-schema and calibration versions; calibration bytes are hashed
separately from the parameters. The model digest is SHA-256 over canonical binary
`f64` parameter bits and length-prefixed sorted feature names;
the runtime artifact digest is SHA-256 over the artifact bytes. Artifact size is
limited to 4 MiB; parameter count is limited to 100,000. Unknown schema/architecture,
invalid capabilities, missing provenance, non-finite parameters, and unsafe limits
fail closed. The runtime reads local bytes only and never downloads artifacts.

Architecture `sdm-binary-linear-v1` declares Rank capability. Rank candidates are
scored independently, allowing multiple candidates to be relevant. Other decision
semantics receive an explicit Unsupported response. Runtime callers must validate
requests and apply their own policy to every response.

The runtime's benchmark example measures cold load, warmed request p50/p95 at the
supported candidate bounds, artifact bytes, malformed-artifact rejection latency, and
process peak RSS after warmup. It uses no training dependency.

## Artifact envelope v2 (additive contract)

`sdm_runtime::ArtifactEnvelopeV2` identifies an architecture and model, required
feature-schema fingerprint, semantic capability set, calibration digest, resource
limits, payload digest, license and source. The v2 payload is capped at 16 MiB and
1,000,000 declared parameters; candidate count remains at most 256. These hashes
detect byte changes but do not authenticate a publisher. `load_artifact` preserves v1
loading and returns a validated `UnsupportedV2` for an architecture without a
registered runtime. `sdm-pairwise-tanh-v2` is registered as a bounded CPU Rank engine;
its ordered feature-coordinate fingerprint, model payload digest, parameter count,
and calibration payload digest are checked before inference. Its training API remains
feature-gated and is not compiled into the runtime dependency graph.

Typed `FeatureSchemaV2` and `FeatureProjectionV2` live in `sdm-core`. Schema
fingerprints use canonical JSON ordering by feature ID and category. Missing required
values, type mismatches, unknown IDs, non-finite numbers and category violations fail
validation. The original v1 textual state projection and artifact remain unchanged.

Typed task v2 registers `sdm-typed-task-v1` for Binary, legacy diagonal Choice,
and Score. `sdm-typed-choice-cross-v1` is an additive Choice-only architecture:
its payload binds the same fitted encoder and schema fingerprint and includes an
explicit bounded list of context/option coordinate pairs. It has a hard 4,096
cross-term cap and excludes text-vocabulary coordinates. Architecture dispatch
preserves the old 3*D diagonal Choice loader and inference behavior. An enabled
quality diagnostic report can record pre-threshold logits and probabilities
without changing the serialized default M011 report format.

`sdm-typed-choice-compositional-v1` is a separate additive Choice-only architecture
for a declared list of up to 4,096 nontext `(context_i, context_j, option_k)`
terms. Context coordinates are canonicalized so `i <= j`; list ordering, uniqueness,
shape, bounds, schema digest and payload digest are validated. Text vocabulary is
excluded from all three positions. The legacy diagonal and pairwise-cross artifact
payloads retain their existing architecture identifiers and feature order.
