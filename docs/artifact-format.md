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
# M014 architecture compatibility

`sdm-typed-choice-compositional-v1` is separately dispatched and serialized. It stores the selected context conjunction definition and bounded conjunction-by-option weights in its own schema; it does not reinterpret earlier `sdm-typed-choice-v1` or `sdm-typed-choice-cross-v1` payloads. Runtime validation checks feature schema identity, option count/order, interaction bounds, tensor shape and payload fingerprint before scoring. Cross-platform portability is exercised in CI with the committed M014 artifact.

# M014a inference-only evaluation (additive, no new artifact architecture)

M014a adds no new artifact architecture identifier. It adds `sdm experiment evaluate --config PATH` with `EvaluateSpec` (`deny_unknown_fields`; no `epochs/learning_rate/optimizer`): named dataset/split paths + SHA-256, test-membership SHA (compact `serde_json::to_vec` of sorted test IDs), protocol/freeze SHAs, expected artifact byte SHA, exact spec + envelope architectures, feature-schema and calibration SHAs, provenance, and unique report path. The path validates artifact SHA **before any inference**, calls `load_artifact`, reuses pure scoring, never calls training, and requires byte-identical input/output SHAs (16 MiB bound, ≤128 Choice options, finite scores). Reports use `sdm-semantic-evaluate-v2` (`schema_version=2`, explicit `evaluated_partition=test` + `test_evaluation_performed=true`, input hashes, per-case IDs/groups/families/targets/decisions/probabilities/abstention, deterministic `report_sha256`). Legacy `SemanticExperimentRunManifest` (omitted-true) remains readable but is never rewritten; new reports are explicitly versioned. Atomic unique outputs refuse overwrite; interruption leaves no accepted partial.

# M014c closure (additive, no new artifact architecture)

M014c adds no new artifact architecture identifier and changes no head/training math. It orders CI (pure analyzer before canary provisioning before dependent tests + `check_m014a_ci_order` regression), replaces the single-host `three_host_parity=true` literal with measured per-host attestation (`m014c_canary_attestation`: 948 Binary + 926 Choice decisions, artifact/dataset/split SHAs, source/host/build, integrity hash) and aggregator (`verify_m014c_parity`: exact `linux-x86_64`/`linux-aarch64`/`macos-aarch64`, source/case equality, exact action/abstention match; new `canary-parity` CI job), and adds read-only lineage (`verify_m014c_lineage`: detached Git/SHA-256 chain, `freeze_sha256=sha256:111…1` flagged `placeholder_unbound`, ancestry `9cc80f0`→`c277247`, one-byte corruption fails) plus original-byte ledger (`docs/m014c-evidence-ledger.json`). Frozen M014b bytes and embedded placeholder remain unchanged in place; detached attestation does not repair the field. See `plans/closure/general-decision-model-framework/014c-status.md`.

# M015a DEV-only final-action sidecar (additive, no new artifact architecture)

M015a adds no new artifact architecture identifier and changes no head, weight,
threshold, encoder, or `DecisionSpec::Choice` 2..=128 semantics. It adds
`sdm experiment m015a-replay --config PATH` with `M015aReplaySpec`
(`deny_unknown_fields`; no training fields): named typed dataset/split/artifact
+ corpus TRAIN/DEV + generator/task-spec paths, expected artifact/dataset/split/
generator/spec/corpus SHAs, architecture, provenance, and unique output path.
The path validates all input SHAs **before any inference**, loads the frozen
artifact read-only, runs actual `TypedTaskRuntime::decide_typed` +
`choice_probabilities`/`choice_logits`/`choice_answerability_probability` over
the DEV partition only, derives no-answer origins from corpus provenance
(`available=false` vs `available=true, zero satisfying`), and evaluates the
versioned `choice-final-v2` contract. Sidecars use `sdm-m015a-dev-final-v1`
(`schema_version=1`, explicit `partition=DEV only`, `test_membership=[]`,
input SHAs, census, v2 report with support/CIs, legacy mixed-value glossary,
bootstrap seed/replicates/method, deterministic `report_sha256`). Legacy
`run_semantic` diagnostics and M011 serialization are unchanged; new v2 keys
carry a `_v2` suffix. Atomic unique outputs under `target/m015a/` refuse
overwrite; interruption leaves no accepted partial. See
`docs/m015a-evaluation-erratum.md`.

# M016 TinyMLP Choice architecture (additive, new identifier)

`sdm-typed-choice-tinymlp-v1` is a separate additive Choice-only architecture:
shared single-hidden-layer tanh scorer `s_i = W2·tanh(W1·[ctx;cand_i]+b1)+b2`
(same `W1/b1/W2/b2` for every candidate; no position/ID input) plus a separately
supervised symmetric answerability head `a = sigmoid(W·[ctx;mean(cands);
max(cands)]+b)` with mean/max pooling over encoded candidates (permutation
invariant). Payload binds the fitted encoder, schema fingerprint, hidden width
(32/64), tanh activation, training fingerprint/seed, and dev calibration
digest; task is choice-only with `2..=128` options and `Choice(None)` for
no-answer (no synthetic None option). v2 envelope caps apply (16 MiB,
1M params, candidate bound 128, finite weights/outputs); tensor SHA is checked
before allocation/inference and declared parameter count must match payload
bytes. `sdm-typed-task-v1`, cross and compositional artifacts are preserved
byte-for-byte; v1 Rank wire is unchanged. Training (M016, `sdm-experiment`)
is deterministic (seeded init/shuffle, bounded lr/epochs/L2, joint
`CE(answerability)+lambda*CE(choice|answerable)` loss, DEV-calibrated
threshold); runtime (`sdm-runtime::tinymlp`, no training/Python/GPU/network
deps) is inference-only with exact ID membership and fail-closed malformed/
oversized/unsupported/corrupted/drifted/mismatched inputs. See
`plans/closure/general-decision-model-framework/016-status.md` (pending).
