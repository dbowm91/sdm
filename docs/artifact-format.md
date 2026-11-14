# Artifact formats

SDM supports a legacy version 1 linear artifact and an additive version 2 envelope.
Artifacts are bounded JSON values with explicit schemas and architecture identifiers.
The runtime reads local bytes and loads only registered architectures. A digest detects
byte changes relative to a trusted digest; it does not authenticate the publisher.

## Version 1

The legacy `LinearArtifact` uses schema version 1 and architecture
`sdm-binary-linear-v1` for Rank scoring. It scores each caller-supplied candidate
independently, so more than one candidate may be relevant. The runtime limits the
artifact to 4 MiB, the weight map to 100,000 entries, state to 65,536 bytes, and
candidates to 256.

The manifest identifies the input schema, calibration version, capabilities, source,
license, training fingerprint, and model digest. The model digest covers the bias and
canonicalized weight map. Calibration has a separate digest. Invalid versions,
unsupported capabilities, non-finite values, missing provenance, and mismatched
hashes are rejected.

## Version 2 envelope

`ArtifactEnvelopeV2` adds an explicit architecture, model identity, required feature
schema fingerprint, capabilities, candidate bound, calibration payload and digest,
source, license, and architecture-specific payload. The complete artifact is limited
to 16 MiB. The generic envelope also caps its `parameter_count` field at 1,000,000
and candidates at 256.

The meaning of `parameter_count` is architecture-specific. Typed task, typed Rank,
and TinyMLP constructors store serialized payload length in this field; the nonlinear
Rank architecture stores its actual model parameter count. Architecture-specific
validators also check tensor shapes, weight counts, candidate limits, and payload
digests. Do not interpret the envelope field as a universal count of numeric weights.
TinyMLP has a separate 1,000,000-weight limit and supports 2 to 128 options.

Typed feature schemas use canonical fingerprints. Missing required values, type
mismatches, unknown feature IDs, non-finite numbers, and invalid categories fail
validation. The fitted encoder is shared by training and inference. The original
version 1 text projection remains unchanged.

## Registered architectures

| Envelope | Architecture | Task | Notes |
| --- | --- | --- | --- |
| v1 | `sdm-binary-linear-v1` | Rank | Legacy independent candidate scorer |
| v2 | `sdm-typed-task-v1` | Binary, Choice, Score | Typed linear heads, including diagonal Choice |
| v2 | `sdm-typed-linear-rank-v1` | Rank | Typed linear Rank head |
| v2 | `sdm-pairwise-tanh-v2` | Rank | Optional nonlinear CPU scorer |
| v2 | `sdm-typed-choice-cross-v1` | Choice | Bounded declared context and option cross terms |
| v2 | `sdm-typed-choice-compositional-v1` | Choice | Bounded nontext context conjunction terms |
| v2 | `sdm-typed-choice-tinymlp-v1` | Choice | Shared candidate scorer with separate answerability head |

Each architecture has its own validation rules. A valid envelope with an unregistered
architecture is returned as unsupported; the runtime does not reinterpret it as a
known model. See [typed task heads](typed-task-heads.md) for task behavior and training
commands.

## Inference-only evaluation

`sdm experiment evaluate --config PATH` checks the named input and artifact digests
before inference, uses the registered runtime, and does not train or rewrite the
artifact. Its reports use the versioned `sdm-semantic-evaluate-v2` schema. This command
is distinct from `experiment run`, which trains and evaluates according to its config.
