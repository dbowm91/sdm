# M013 prospective quality protocol v1

Status: frozen before M013 held-out inference. Synthetic-only; it does not qualify a production model.

## Immutable inputs

| Input | SHA-256 |
| --- | --- |
| Choice corpus | `sha256:5c901ab1a1085f8b3b0a93497b6ee71ee196233e0c61032d5f79aefbef682ace` |
| Choice group split | `sha256:b03e55499f3ad3b23210a2af5cb65c8d9b0eafbf34c68199be747b2c35c3ba6d` |
| Binary corpus | `sha256:d88a7822cfb6982ae237edfd455622256414fc98bd34d824e42f192a71c2f1d2` |
| Binary group split | `sha256:bd96629637b0d40c22728092a2446badcc161aa57521e51aee18ce3e1b373722` |
| Generator seed / split seed | `13013 / 13013` |

Each task has 1,532 leakage groups and two active-state paired cases per group. The split holds out load-only, text-only, and combined nuisance families from fitting and development. Text-shift terms are absent from train/dev. Choice includes two rule templates selected by the explicit `rule_family` feature, shuffled option order, and group-varying relabeled option IDs. `Choice(None)` is produced when `available=false`. The label rule is unchanged by load/text nuisance shifts.

## Candidate set and selection

The only Choice candidates are the frozen `typed-choice` diagonal head and `typed-choice-cross` head. Binary uses the frozen current `typed-binary` head. All use seed 13013, 120 epochs, learning rate 0.2, train-only encoder fitting, and the existing dev-only answerability threshold selector. No hyperparameter or threshold search is authorized. Both Choice architectures are reported side by side; no selection is made from test results. The legacy artifact is a compatibility/control model, not the quality target.

## Metrics and gates

Primary Choice metric: answered-and-correct cases / all answerable cases (abstentions count as errors); compare corrected minus legacy as paired per-group values. Required secondary metrics: conditional option log-loss/Brier; answerability AUROC/PR where class support permits; no-answer recall; false abstention among answerable cases; answer coverage; selective risk at coverage and risk-coverage curve/AURC; per-family support and metrics; raw probabilities and final runtime choices. Always-answer, always-abstain, context-only, and feature-shuffled controls are diagnostics and cannot qualify a model.

Primary Binary metric: Brier score on each test slice, with OOD family results reported separately. Report label-stratified residuals, calibration, error, one-factor nuisance changes and cluster-aware intervals. No M011 family, label, prediction, or threshold may enter tuning.

Uncertainty is a paired nonparametric bootstrap over independent `leakage_group` means, 10,000 replicates, deterministic seed 13013, percentile 95% interval. Each paired counterfactual group is sampled once. Positive quality requires the primary improvement interval to exclude zero favorably and all declared support/counterfactual/critical OOD gates to pass. A significant regression or critical behavioral failure is negative; otherwise indeterminate. Any slice below 50 independent groups, or any no-answer slice below 20 groups, is indeterminate regardless of row count.

## Provenance and boundaries

Only synthetic rows are used. M011 is retrospective diagnosis only and its bytes/reports remain untouched. The test partition is run once after this protocol and the corpus/split were committed. After test observation there is no candidate or threshold selection against this test. Any new attempt requires a separately named milestone and newly generated held-out groups. A passing synthetic result is not consumer effectiveness, deployment fitness, CodeGG approval, or publication/legal clearance.
