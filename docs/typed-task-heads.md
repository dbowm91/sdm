# Typed task heads

`sdm experiment run --config PATH` accepts `typed-binary`, `typed-choice`,
`typed-choice-cross`, and
`typed-score` architectures in addition to the two legacy Rank paths and
`typed-linear` Rank. Each task artifact carries one semantic capability, a
train-fitted `FittedFeatureEncoderV2`, the task head weights, the training input
fingerprint, and a separately hashed dev calibration payload. The runtime rejects
task, schema, option identity, shape, and resource mismatches.

The encoder sorts feature coordinates by declared feature ID, uses numeric
centering and max-absolute scaling fit on train data, maps declared categories to
one-hot coordinates, carries booleans as 0/1, and uses a bounded train-only token
vocabulary for text. It clips scaled numeric values to [-5, 5]. Unknown categories
are rejected; unknown text terms map to all-zero vocabulary coordinates. Missing
optional features map to zeros. This transform is serialized with the artifact and
is shared by training and runtime inference.

- Binary uses a logistic head, reports probability-based binary metrics, and may
  abstain when confidence is below the threshold selected on dev.
- Legacy Choice uses `sdm-typed-task-v1`'s 3*D context, option, and diagonal
  interaction weights. It normalizes probabilities over exactly the
  caller-supplied option IDs and retains its historical dev-selected cutoff.
- `typed-choice-cross` is an additive `sdm-typed-choice-cross-v1` contract. It
  stores an ordered list of up to 4,096 declared context-coordinate ×
  option-coordinate pairs, with bounded finite weights and schema digest
  validation. Text-vocabulary coordinates are excluded. Pair ordering and
  architecture ID are serialized; malformed, duplicate, out-of-range, or
  oversized coordinates fail closed. Old typed Choice artifacts are never
  reinterpreted by this constructor.
- Choice normalizes probabilities over exactly the caller-supplied option IDs.
  A dev-selected confidence threshold may
  abstain. `Choice(None)` labels are never converted into a synthetic option;
  they are excluded from choice log-loss and inform the dev abstention threshold.
- Score maps a logistic output into each request's finite `[minimum, maximum]`
  rubric and reports MAE/RMSE on the original scale.
- Rank continues to score each caller-supplied candidate independently and retains
  multi-relevant labels.

Semantic experiments may set `quality_diagnostics: true` to record raw Choice
logits/probabilities and answerability beside the actual final runtime decision
and abstention. The default remains off to preserve historical M011 report
serialization. The M013 first corpus is retained as invalid diagnostic
evidence: its pair members differed in load as well as active. M013a uses a new
seed, group split and frozen suite; neither result can promote an application
model. The checked-in task suites are synthetic-only and provide no consumer
authority, policy or actuation.
