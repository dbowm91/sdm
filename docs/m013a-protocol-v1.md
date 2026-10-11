# M013a prospective quality protocol v1

Status: frozen before M013a held-out inference. Synthetic-only; no production or consumer qualification.

## Frozen corpus and membership

| Input | SHA-256 |
| --- | --- |
| Choice corpus | `sha256:52189cafbe52f5dbca66f286257cf91a5c961e06029e8a92a5013ee46257e586` |
| Choice group split | `sha256:5c00db7cd2e31ca1864f885eeea57a59a06a952de1307d94f8f1f0b76f92fea4` |
| Binary corpus | `sha256:edc857be6cc0b06e21b81df77f62a4bc261befa6f7adc58abf4788e6b842c1da` |
| Binary group split | `sha256:97d86626281429236ece128c513878e2b54a984935cde9014876db278d1f5c21` |
| Generator/split seed | `14014 / 14014` |

Each task contains 1,532 independent leakage groups and two rows per group. The generator proves that pair members are equal after replacing request/case IDs, targets, and active values with a sentinel. Load, note text, availability, rule family, candidate identities and ordering, all non-active projections, and family are identical. The frozen Choice test has 830 rows: ID-a 101 groups, ID-b 114, load shift 67, text shift 67, combined shift 66. Binary has 798 rows: ID-a 105 groups, ID-b 94, load shift 67, text shift 67, combined shift 66. OOD families are `--test-family` holdouts only; they are absent from train/dev and no rows are excluded. Test-only text tokens do not enter the train-fitted encoder. Every OOD family has at least 22 no-answer groups.

## Fixed candidates and training

Choice candidates are the current `typed-choice` diagonal head and additive `typed-choice-cross` head; Binary candidate is current `typed-binary`. Fixed settings: seed 14014, 120 epochs, learning rate 0.2, SplitMix64 Fisher-Yates epoch order, train-only preprocessing, and existing dev-only answerability cutoff. The candidate set and settings are frozen. No test-informed selection is permitted. M013 reports are invalid and are not used as selection evidence.

## Metrics and decision rules

Choice primary: answerable final-choice accuracy, with abstentions counted as errors, paired by independent leakage group. Report conditional option log-loss and Brier; answerability AUROC and average precision; no-answer recall; false abstentions; coverage; risk-coverage/AURC; raw logits and probabilities; final runtime answers; active-flip raw-score and correct-target behavior; and family support. Report fixed train-majority, context-only (legacy head with candidate values made identical), always-answer, always-abstain, and shuffled-score negative controls. Controls cannot qualify a model.

Binary primary: Brier improvement over the train-prior constant baseline, reported per ID and OOD family. Also report label-stratified probability residuals, one-factor load and note transformations, combined nuisance shift, accuracy, calibration, and abstentions. M011 and invalid M013 are not tuning data.

Uncertainty: 10,000 paired percentile bootstrap replicates over leakage-group means, seed 14014, 95% interval. Each counterfactual pair is sampled once. Positive requires the primary CI to exclude zero favorably and every required support, counterfactual, and critical OOD gate to pass. Significant regression or a preregistered critical failure is negative; otherwise indeterminate. Any primary slice below 50 groups or no-answer slice below 20 groups is indeterminate.

The experiment and analyzer run once after the freeze commit. Any post-test architecture, threshold, or model-selection change requires a newly scoped milestone and fresh sealed test groups. No external data, CodeGG corpus, publication, artifact promotion, or deployment authorization is in scope.
