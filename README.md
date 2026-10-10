# Small Decision Model (SDM)

SDM is the independent home for generic bounded decision semantics, local artifact
inference, and reproducible training/evaluation. CodeGG-specific authority, tool
projection, disclosure, capture consent, and causal-frontier behavior stay in CodeGG.

## Repository policy

- License: MIT, preserving the Anomalyco copyright notice from the CodeGG source.
- Visibility: public; immutable full-SHA downstream consumption remains the release policy.
- Consumption/release policy: downstream projects pin an immutable full Git commit
  SHA. Branch names and floating tags are not runtime dependencies. A source revision
  is usable only after CI and the CodeGG compatibility fixture command pass.
- This repository performs no implicit network access or model download.

## Workspace

- `sdm-core`: semantic request/response types and validation, no application authority.
- `sdm-runtime`: validated offline artifact loading and bounded inference. It has no
  dependency on `sdm-training`.
- `sdm-training`: generic decision-case dataset validation, deterministic group
  splitting, model fitting, dev-only threshold selection, and test evaluation.
- `sdm-data`: provenance-bearing labels and frozen leakage-aware group splits.
- `sdm-eval`: algorithm-neutral semantic metrics and preregistered offline reports.
- `sdm-nonlinear`: optional bounded nonlinear CPU scorer and deterministic local SGD.

Initial runtime architecture is a sparse binary relevance model applied independently
to Rank candidates. The semantic core supports Binary, Choice, Score, and Rank; the
first trainer/runtime artifact supports Rank and returns explicit Unsupported for the
other semantics. Multiple relevant Rank candidates remain independent labels.

## Build and qualify

```sh
cargo test --workspace --locked
cargo check -p sdm-runtime --locked
cargo check -p sdm-runtime --examples --locked
cargo tree -p sdm-runtime --locked
cargo run -p sdm-training --bin sdm-check-compat -- \
  fixtures/codegg-compatibility-v1.jsonl path/to/artifact.json
cargo run -p sdm-training --bin sdm-train -- \
  fixtures/compatibility-rank-cases-v1.jsonl artifacts/compatibility-rank-v1.json 127 100
```

The compatibility fixture file is a sanitized, frozen copy of CodeGG's
`assets/decision-runtime/compatibility-v1.jsonl` at source revision
`aec30ebbaada172cd2915b3fb068f828a8fc6709`. The authoritative fixtures and historical
training/qualification evidence remain in CodeGG. No user session data was copied.
`scripts/import-codegg-compat-fixtures.py` regenerates the small Rank training set from
only the frozen source fixtures. `artifacts/compatibility-rank-v1.json` is a reproducible
baseline artifact, not a qualified or production-promoted model.
`cargo run -p sdm-runtime --example benchmark -- fixtures/benchmark-rank-request.json
artifacts/compatibility-rank-v1.json` emits cold load, artifact bytes, peak resident
memory after warming, p50/p95 latency for 16/64/128/256 candidates, and malformed
artifact rejection latency. The RSS number is the process high-water mark, so report it
as a conservative peak rather than an isolated runtime allocation measurement.

## Provenance

The semantic core originated in CodeGG commit
`aec30ebbaada172cd2915b3fb068f828a8fc6709`, file
`crates/codegg-core/src/decision.rs`. It is carried with its MIT license and source
attribution. The runtime and generic trainer in this repository are new implementations
that preserve the published semantic contract; they do not claim experiment-result or
model-weight provenance from CodeGG.

See [`docs/extraction-inventory.md`](docs/extraction-inventory.md),
[`docs/artifact-format.md`](docs/artifact-format.md), and
[`docs/reproducibility.md`](docs/reproducibility.md), plus the
[`docs/benchmark-baseline.md`](docs/benchmark-baseline.md) runtime snapshot.


## Active development planning

The next framework workstream is registered under [plans/](plans/README.md).
Its [roadmap](plans/subsystems/general-decision-model-framework-roadmap.md) separates
versioned contracts (M001), generic data and split provenance (M002),
independent evaluation/qualification (M003), a second trainable architecture
(M004), and CodeGG as the first application-level experiment (M005).

[M001 is ready for implementation](plans/implementation/general-decision-model-framework/001-versioned-feature-artifact-runtime-contracts.md);
M002-M005 have explicit dependency blockers in the [active registry](plans/registry.md).
This planning work does not qualify any new model or alter CodeGG's current
pinned SDM runtime. Details and negative historical model evidence are preserved
in [the research note](docs/general-framework-research-2026-10.md).

New offline data/evaluation commands are `sdm-dataset validate`, `sdm-dataset split`,
and `sdm-qualify`. They consume explicit local files and do not access network sources.
The nonlinear CPU Rank engine is registered in v2 runtime dispatch. It remains an
unqualified framework architecture and does not promote a CodeGG model.
