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
- `sdm-experiment`: explicit-input Rank orchestration, frozen-split training,
  dev-only threshold selection, runtime reload and held-out reporting.

Publication-facing package metadata is set per crate with the verified
repository/homepage and crate-specific docs.rs destinations. The checked-in
[standalone quickstart](docs/standalone-quickstart.md) covers the experiment,
packaged consumer boundary, compatibility and quality limits. The locked
[third-party inventory](docs/third-party-license-inventory.json) is metadata
evidence only; see its [review status](docs/third-party-licenses.md) before any
registry distribution.

Legacy linear and pairwise Rank artifacts remain supported. Additive typed artifact
versions also serve Binary, Choice, Score, and typed Rank heads. Multiple relevant
Rank candidates remain independent labels. Applications still own policy, authority,
and abstention handling.

M015 TinyChoice task semantics are defined in
[the task specification](docs/m015-task-spec-v1.md). The TRAIN/DEV-only
generator and independent oracle are in `scripts/generate_m015_suite.py`;
partition checks and development diagnostics are in
`scripts/analyze_m015_dev.py`; `scripts/run_m015_baselines.py` projects the same
groups into the existing typed Choice schema and runs the linear, cross, and
compositional baselines with an empty test partition. These are synthetic
research artifacts, not CodeGG evidence or model qualification.

M015–M017 TinyChoice research milestones are complete. The frozen M017 synthetic
evaluation was negative; no model is qualified or approved for CodeGG. See the
[planning registry](plans/registry.md) and [M017 closure](plans/closure/general-decision-model-framework/017-status.md)
for current status and evidence.

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

## Planning status

The [planning registry](plans/registry.md) is the current milestone index; detailed
plans and closure evidence remain under `plans/`. M014/M014b final cohorts have
been consumed and must not be rerun or modified. M017 is closed with a synthetic-only
negative result. CodeGG M005 remains deferred, and crates.io publication remains
blocked pending human/legal review. No milestone result authorizes model promotion.
