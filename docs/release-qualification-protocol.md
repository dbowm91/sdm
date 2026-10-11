# M011 synthetic release qualification protocol v1

Status: this protocol snapshot and the M011 v2 generator/membership files are committed before v2 held-out inference. Earlier v1 runs are development evidence and are excluded from v2 gates.

## Scope and limitations

This protocol qualifies only reproducible standalone mechanics on generated data. It does not estimate application performance, CodeGG effectiveness, safety, or deployment readiness. M010's six small fixtures and reports are development evidence and are excluded from M011 gate decisions.

## Frozen comparisons and gates

- Run the same train/dev/test membership and feature schema for each available architecture within a task. Training and normalization may read train only; thresholds may read dev only. Test labels are read once for final reports.
- Compare each trained head with a majority/constant baseline for Binary, a majority-choice baseline for answerable Choice plus always-abstain baseline for no-choice examples, and a train-mean baseline for Score. Report abstentions separately; never count an abstention as a correct answer.
- Positive mechanics gate: all test decisions validate against their original request, exact caller IDs/bounds are preserved, artifacts reload, and no generated test row is present in train or dev. Quality gate: report both task metrics and baseline deltas; classify positive only when the preregistered paired 95% group-bootstrap interval for the primary metric excludes zero in the favorable direction and each supported slice has at least 20 independent groups. Otherwise classify negative or indeterminate; low support is indeterminate.
- Primary metrics: Binary Brier score, Choice exact accuracy on answerable rows with no-choice abstention recall, Score MAE on rubric units, Rank NDCG and Recall@5. Secondary loss metrics and all case counts remain visible.
- Negative controls: constant predictions must fail the mechanics quality gate when feature-dependent examples are present; held-out-only label mutation must leave model and calibration digests unchanged. A counterfactual with changed target features must change the expected target while retaining its declared group; paired rows may not cross partitions.
- Resource gate is descriptive, not a quality gate: record trained model SHA, artifact bytes, parameter count, cold load, peak process RSS, invalid-artifact rejection, and p50/p95 at 1/16/64/128/256 candidates on Linux x86_64, Linux ARM64 and Apple Silicon. No cross-OS RSS comparison.
- Rust support gate: `rustc 1.89.0` runs locked workspace tests, strict Clippy, and runtime-only check. Stable CI independently runs on all three hosted platforms.

## Data generation and report identity

M011 data must use a new generator version and seed, fresh case IDs/groups, explicit synthetic-only provenance, train/dev/test group disjointness, whole-family exclusions, a test-only out-of-distribution family, and paired counterfactuals. Store dataset, split, protocol, model, calibration, artifact and report SHA-256 identities. New generators and membership files are committed before test inference. Generated values and metrics are never represented as human or application evidence.

## Disposition rules

Mechanics success and predictive quality are separate. A valid but weak or underpowered result remains reportable as negative/indeterminate. Release readiness additionally requires the Rust 1.89 check, three-host trained artifact run, external consumer example, documentation and dependency/license/format audit. A failure registers a corrective plan instead of changing thresholds after the result.
