# Small Decision Model (SDM)

SDM is a Rust workspace for bounded decision requests, local model inference, and
reproducible training and evaluation. Applications provide the candidate set and
retain control of eligibility, policy, abstention handling, and any action. SDM does
not grant permissions or make application decisions on its own.

## Requirements

Rust 1.89 or newer. The runtime uses local artifacts and does not download models or
call remote services.

## Quickstart

See the [standalone quickstart](docs/standalone-quickstart.md) to run the checked-in
synthetic Binary, Choice, Score, and Rank examples and load an artifact from Rust.
These examples demonstrate mechanics only. They do not establish real-world model
quality.

## Workspace

| Crate | Purpose |
| --- | --- |
| `sdm-core` | Request, response, feature schema, and validation types |
| `sdm-runtime` | Bounded local inference with no training dependency |
| `sdm-data` | Dataset provenance and leakage-aware split manifests |
| `sdm-eval` | Metrics and offline evaluation contracts |
| `sdm-training` | Generic Rank training and compatibility tools |
| `sdm-nonlinear` | Optional nonlinear CPU Rank model and trainer |
| `sdm-experiment` | Explicit-config training, evaluation, and replay commands |

## Development checks

```sh
cargo test --workspace --locked
cargo check -p sdm-runtime --locked
cargo check -p sdm-runtime --examples --locked
cargo tree -p sdm-runtime --locked
cargo run --locked -p sdm-training --bin sdm-check-compat -- \
  fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json
```

The compatibility fixture is a sanitized, frozen copy of CodeGG's
`assets/decision-runtime/compatibility-v1.jsonl` at source revision
`aec30ebbaada172cd2915b3fb068f828a8fc6709`. No user session data was copied. The
fixture check verifies the response contract, not model quality. The checked-in Rank
artifact is a reproducible baseline, not a qualified or production-approved model.

## Documentation and status

- [Standalone quickstart](docs/standalone-quickstart.md)
- [Typed task heads](docs/typed-task-heads.md)
- [Artifact formats](docs/artifact-format.md)
- [Reproducibility](docs/reproducibility.md)
- [Benchmark baseline](docs/benchmark-baseline.md)
- [Third-party license review](docs/third-party-licenses.md)
- [Planning registry and milestone evidence](plans/registry.md)

M014, M014b, and M017 final cohorts have been consumed. Do not rerun them or modify
their frozen inputs. M017's result is synthetic-only negative. No model is qualified
for CodeGG. CodeGG M005 remains deferred, and crates.io publication remains blocked
pending human and legal review.

## Provenance

The semantic core originated in CodeGG commit
`aec30ebbaada172cd2915b3fb068f828a8fc6709`, file
`crates/codegg-core/src/decision.rs`, and retains its MIT attribution. The runtime and
generic trainer are new implementations. See the
[extraction inventory](docs/extraction-inventory.md) for provenance details. The
[third-party license inventory](docs/third-party-license-inventory.json) is metadata
evidence, not legal clearance.
