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
