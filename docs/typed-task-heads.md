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
# M014 compositional Choice head

The opt-in `sdm-typed-choice-compositional-v1` runtime adds a bounded conjunction of selected nontext context coordinates, multiplied by each candidate coordinate. It is a distinct artifact architecture; existing typed Choice and cross-feature artifacts retain their prior interpretation. The trainer rejects a design exceeding 4096 conjunction-by-option terms and the runtime enforces the existing 128-option bound. See [artifact-format.md](artifact-format.md) and the M014 research note for the representability proof.

# M014a inference-only evaluation (no head change)

M014a changes no Binary/Choice head, training math, or thresholds. It adds `sdm experiment evaluate --config PATH` for exact frozen bytes (see `artifact-format.md`): SHA-checked read-only loading, pure scoring via the existing `TypedTaskRuntime`, and versioned `sdm-semantic-evaluate-v2` reports that always carry raw probabilities/logits/answerability beside the final thresholded decision. Choice counterfactual success requires **both** finals correct (raw-correct that abstains does not pass); no-answer targets need no extra option. Qualification (paired-group CIs, families/controls, recall/coverage, resources) lives in `scripts/qualify_semantic_v2.py`, proven on DEV-CANARY (Binary positive via OOD gain + ID noninferiority; Choice indeterminate via shifted recall). No model is qualified or promoted.

# M014c closure (no head change)

M014c changes no Binary/Choice head, training math, or thresholds. It orders CI (pure→gen→dependent + ordering regression), replaces single-host `three_host_parity=true` with measured same-artifact attestation + aggregator (`m014c_canary_attestation` / `verify_m014c_parity` + `canary-parity` job; provisional indeterminate for unverified parity is correct), and adds detached lineage + original-byte ledger for the consumed M014b FINAL (placeholder `freeze_sha256` defect preserved, never rerun). See `plans/closure/general-decision-model-framework/014c-status.md`.
