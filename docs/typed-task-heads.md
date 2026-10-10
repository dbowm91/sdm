# Typed task heads

`sdm experiment run --config PATH` accepts `typed-binary`, `typed-choice`, and
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
- Choice uses a context/item interaction head and normalizes probabilities over
  exactly the caller-supplied option IDs. A dev-selected confidence threshold may
  abstain. `Choice(None)` labels are never converted into a synthetic option;
  they are excluded from choice log-loss and inform the dev abstention threshold.
- Score maps a logistic output into each request's finite `[minimum, maximum]`
  rubric and reports MAE/RMSE on the original scale.
- Rank continues to score each caller-supplied candidate independently and retains
  multi-relevant labels.

The checked-in task suites are generated, redistributable mechanics examples, not
application data or effectiveness evidence. They deliberately do not provide
consumer authority, policy or actuation.
