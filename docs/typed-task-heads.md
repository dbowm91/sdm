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
- `typed-choice-compositional` is an opt-in `sdm-typed-choice-compositional-v1`
  contract. It adds an ordered list of at most 4,096 sparse nontext
  `(context_i, context_j, option_k)` terms, with `i <= j`. It supports rules such
  as the two-rule active-flip XOR/XNOR that are not separable by the old additive
  pairwise option margin. Runtime loading validates every coordinate and never
  reads text coordinates in a multilinear term.
- Binary experiments may opt into `binary_constant_mask`. It computes exact
  coordinate variation using train projections only, retains an explicit scalar
  intercept, and holds invariant context weights at zero. The selected encoded
  coordinates are reported with the run manifest; the shared v2 encoder and old
  artifact format are unchanged. The manifest records the exact variation rule,
  encoder and training fingerprints, retained/masked coordinates, zero L2 setting,
  and unpenalized scalar intercept. The option defaults off for historical configs.
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

M014 source-derived truth-table proof and implementation evidence are maintained in
[`docs/m014-model-quality-research.md`](m014-model-quality-research.md). This
mechanical architecture work does not change M013a's negative Binary or
indeterminate Choice dispositions and does not qualify a model.
