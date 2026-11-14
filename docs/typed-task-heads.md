# Typed task heads

Use `sdm experiment run --config PATH` for typed Binary, Choice, Score, and Rank
experiments. Each config names the dataset, split, architecture, seed, and output paths.
The runtime validates the task, feature schema, candidate identities, tensor shapes,
and resource bounds before inference.

## Supported heads

| Task | `experiment run` architecture | Artifact architecture | Behavior |
| --- | --- | --- | --- |
| Binary | `typed-binary` | `sdm-typed-task-v1` | Logistic probability with a threshold selected on DEV |
| Choice | `typed-choice` | `sdm-typed-task-v1` | Legacy diagonal context and option scorer |
| Choice | `typed-choice-cross` | `sdm-typed-choice-cross-v1` | Adds up to 4,096 declared context and option coordinate pairs |
| Choice | `typed-choice-compositional` | `sdm-typed-choice-compositional-v1` | Adds up to 4,096 nontext `(context_i, context_j, option_k)` terms |
| Score | `typed-score` | `sdm-typed-task-v1` | Logistic output mapped to the request's finite score range |
| Rank | `typed-linear` | `sdm-typed-linear-rank-v1` | Scores each candidate independently; multiple candidates may be relevant |
| Rank | `nonlinear` | `sdm-pairwise-tanh-v2` | Optional bounded nonlinear CPU scorer |

Choice requests require 2 to 128 options. Probabilities are associated with the
caller-supplied option IDs. `Choice(None)` represents no answer; it is not added as a
synthetic option. Legacy Choice uses a DEV-selected confidence threshold for
abstention. The cross and compositional architectures have distinct IDs and do not
reinterpret existing artifacts.

## TinyMLP Choice training

The TinyMLP Choice architecture is `sdm-typed-choice-tinymlp-v1`. It shares a tanh
scorer across candidates and uses a separate answerability head with mean and max
candidate pooling. The pooling is invariant to candidate order. It supports 2 to 128
options and has a 1,000,000-weight limit.

Train it with the dedicated command, not `experiment run`:

```sh
cargo run --locked -p sdm-experiment -- experiment m016-train \
  --config PATH
```

The strict config binds the dataset and split by digest and declares a grid of training
settings. The grid is limited to 36 configurations. Training uses TRAIN; model
selection and threshold calibration use DEV; the command does not evaluate TEST. No
standalone M016 config fixture is checked in. The
[`run_m016_comparison.py`](../scripts/run_m016_comparison.py) helper generates a
complete SHA-bound config for the comparison workflow.

## Shared feature encoding

The fitted encoder is part of the artifact and is identical at training and inference:

- Numeric features are centered and scaled using TRAIN statistics, then clipped to
  [-5, 5].
- Categories use declared one-hot coordinates. Unknown categories are rejected.
- Booleans use 0 or 1. Missing optional values map to zero.
- Text uses a bounded vocabulary fitted on TRAIN. Unseen terms map to zero
  coordinates.

The encoder sorts coordinates by declared feature ID. Model and schema fingerprints
bind the fitted transform to the artifact. See [artifact formats](artifact-format.md)
for the serialized contract and resource bounds.

## Training and evaluation behavior

Training updates weights from TRAIN only. Calibration and threshold selection use DEV.
A configured TEST partition is held out for reporting and must not influence fitting,
selection, or calibration. Use a frozen split and explicit output paths; existing
outputs are not overwritten.

Binary can optionally use `binary_constant_mask`, which masks coordinates that are
constant on TRAIN while retaining a scalar intercept. The option defaults off.

These checked-in task suites use synthetic data and demonstrate mechanics, not
application quality. Current qualification status and evidence are in the
[planning registry](../plans/registry.md).
