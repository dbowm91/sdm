# M003 closure — Semantic evaluation and preregistered qualification

Status: conditionally closed
Implementation commit: `ee0f613`

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Independent evaluation crate | `sdm-eval` depends on `sdm-data`/core, not training | Pass |
| Binary, Choice, Score, Rank metrics | Binary accuracy/Brier/log loss/precision/recall/F1 and ECE; Choice accuracy/log loss over complete distributions; Score MAE/RMSE; Rank MRR/recall@k/NDCG/precision/recall/F1 | Pass |
| Identity-bound frozen protocol | Dataset/split/artifact/calibration/source, minimum sample size, gates, fingerprint and mismatch rejection | Pass |
| Fixed-prediction offline Rank report | `sdm-qualify` validates identities and emits JSON metrics plus pass/fail/indeterminate gates | Pass |
| Grouped uncertainty intervals | Deterministic grouped bootstrap confidence intervals for rank MRR, recall@k and NDCG; group resampling preserves case weighting | Pass (Rank only) |
| Calibration reports by slice | No per-slice calibration report | Gap |
| CLI reports all semantic families and compares baselines | CLI currently reports Rank; library supports additional families; no comparison framework | Gap |
| Test-label read-order proof and frozen synthetic qualification corpus | Protocol checks hashes before metrics; no checked-in frozen multi-semantic qualification fixture or controlled label store | Partial |

## Verification and limitations

Golden unit checks cover numerical Binary/Choice/Score behavior, protocol fingerprint tampering, grouped rank intervals, and existing workspace regressions. Rank ties are deterministic by candidate ID; invalid/duplicate/unknown candidates fail. `candidate_universe_coverage` means coverage of the submitted candidate universe; it is not upstream shortlist recall. Undefined metrics remain `None`, and unsupported gates are reported indeterminate. No test-label isolation guarantee can be enforced for arbitrary caller-owned in-memory data.

Disposition: conditional pending uncertainty reporting, broader report coverage, and independent fixture qualification. No model promotion or deployment approval is represented.
