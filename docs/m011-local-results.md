# M011 v2 synthetic qualification results

These results qualify deterministic standalone mechanics on generated data only.
They do not establish application effectiveness, CodeGG quality, or deployment
readiness. The frozen protocol and v2 generator/membership files were committed
before the v2 held-out inference runs.

## Reproduction

```sh
python3 scripts/generate_m011_synthetic_suite.py
cargo run -p sdm-data --bin sdm-dataset --locked -- split fixtures/m011-v2-binary.json 11012 target/m011-v2/binary.split.json --exclude-family m011-binary-excluded-v2 --test-family m011-binary-ood-v2
# Repeat the split command for Choice, Score, and Rank using their matching
# fixture, split path, and family names.
cargo run -p sdm-experiment --locked -- experiment run --config fixtures/m011-v2-binary.experiment.json
# Repeat the workflow for Choice, Score, Rank, Rank-linear and Rank-nonlinear.
python3 scripts/analyze_m011_qualification.py
```

Each task has an excluded family of 12 examples and a separate OOD family of
48 held-out test examples. Full split memberships, train/dev/test counts, case
outcomes, and uncertainty intervals are in `target/m011-v2/` after reproduction.
The checked-in CI workflow executes all six workflows on three hosted targets.

## Frozen v2 evidence

Protocol SHA-256:
`sha256:f563e89dc7a2165edf4e48bffdd669db0337a2cdbf2b760d54713558d78c05d2`.
The locally reproduced machine report (including the explicit constant-baseline
negative controls) was
`sha256:fa33a0fa2a5b1c347b9576e87f421194dd055e76cf1504b31fa1d72d7337b17d`;
hosted CI regenerates this report for the same frozen data and protocol.

| Task | Held-out cases / groups | Baseline comparison (paired group 95% CI) | OOD disposition | Counterfactual target / prediction changes |
| --- | ---: | --- | --- | ---: |
| Binary | 106 / 53 | Brier improvement +0.0045 `[-0.0643, +0.0704]`, indeterminate | Negative: -0.2589 `[-0.2825, -0.2356]` | 36 / 26 of 53 pairs |
| Choice | 92 / 46 (70 answerable) | Accuracy delta 0.0000 `[0, 0]`, indeterminate | Indeterminate: only 17 supported groups | 35 / 0 of 46 pairs |
| Score | 100 / 50 | MAE improvement +0.6874 `[+0.6532, +0.7232]`, positive | Positive: +0.6015 `[+0.5746, +0.6306]` | 50 / 50 of 50 pairs |
| Rank | 102 / 51 (35 metric-eligible groups) | NDCG delta +0.1423 `[+0.1104, +0.1758]`, positive | Indeterminate: only 17 metric-eligible groups | 35 / 46 of 51 pairs |

Choice no-answer abstention recall is `0.364` (8/22); its 11 independent
groups are below the preregistered 20-group support minimum, so that slice is
indeterminate. The Rank metric excludes all-zero relevance rows as in the
evaluator and ties are broken by candidate ID. Same-split linear and nonlinear
Rank each achieved NDCG `0.8155`, with a +0.0655 paired delta over input order
on 35 eligible groups. No thresholds were changed after observation.

The synthetic counterfactual input pairs preserve all but the designated
boolean feature and stay within one leakage group. A prediction that does not
change when the target changes is reported as observed evidence; it is not
silently treated as a correct prediction. In particular, Choice has no
prediction change in its tested counterfactual pairs and weak no-answer recall.
The machine report also evaluates each frozen no-signal baseline against itself
on those feature-dependent pairs; the paired deltas are zero and the control
does not pass the positive quality gate for any task.

## Limits and gates

All test decisions are validated against their original requests, artifacts are
reloaded, train/dev/test groups are disjoint, and held-out-only label mutation
tests preserve model/calibration digests. The report records negative and
indeterminate predictive-quality outcomes without claiming they passed the
quality gate. Hosted trained-artifact resource results and cross-platform
loading of the same trained artifact are recorded in the numbered M011 closure
after the final CI run completes.
