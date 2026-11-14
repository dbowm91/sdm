# Standalone quickstart

SDM runs explicit local configurations over named datasets and split manifests. The
checked-in examples use synthetic data and demonstrate the training and inference
mechanics. They are not evidence of application quality.

## Requirements

Install Rust 1.89 or newer. Run commands from the repository root.

## Run the synthetic examples

```sh
mkdir -p target/experiments
cargo run --locked -p sdm-experiment -- experiment run \
  --config fixtures/synthetic-binary-typed-v1.experiment.json
cargo run --locked -p sdm-experiment -- experiment run \
  --config fixtures/synthetic-choice-typed-v1.experiment.json
cargo run --locked -p sdm-experiment -- experiment run \
  --config fixtures/synthetic-score-typed-v1.experiment.json
cargo run --locked -p sdm-experiment -- experiment run \
  --config fixtures/standalone-typed-rank.experiment.json
```

Each config names its dataset, frozen split, architecture, seed, and output paths.
The command validates those inputs, trains on TRAIN, performs task calibration on DEV,
loads the resulting artifact through the runtime, and reports metrics on TEST.
Existing artifact and report paths are not overwritten. To repeat a run, use a
fresh output path in a copy of the config.

For a nonlinear Rank example, see
`fixtures/standalone-rank-nonlinear.experiment.json`. For the compatibility fixture
check, see the command in the [README](../README.md#development-checks).

## Train the TinyMLP Choice model

TinyMLP uses `sdm experiment m016-train`, not `experiment run`. See
[typed task heads](typed-task-heads.md) for the command and config workflow.

No standalone M016 config fixture is checked in.

## Use an artifact from Rust

The runtime loads local artifact bytes, validates the artifact, and dispatches only
registered architectures. A digest can detect a mismatch against a trusted expected
value, but it does not prove who produced the artifact. Obtain artifacts through a
trusted channel and verify their source.

For complete consumer code, see the
[standalone consumer example](../examples/standalone-consumer/). The application
must still decide which candidates are eligible and what to do with a response or
abstention.

## Limits and next steps

Artifact and request bounds depend on the registered architecture. Unsupported
architectures, malformed artifacts, and invalid requests return errors rather than
being coerced. See [artifact formats](artifact-format.md) and
[typed task heads](typed-task-heads.md) for the contracts.

Seeds and frozen inputs make the procedure repeatable, but independently trained
floating-point artifacts can have host-dependent byte hashes. See
[reproducibility](reproducibility.md). Synthetic results do not qualify a model for
CodeGG or authorize deployment. Current milestone status is in the
[planning registry](../plans/registry.md).
