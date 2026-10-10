# M011 local held-out results

Run date: 2026-10-10. Generated synthetic data only. The protocol was in the
working tree before held-out evaluation, but was not committed before evaluation;
the audit trail is therefore weaker than the plan requires. The initial generator
run was discarded after fixing counterfactual generation. The results below use
the corrected, frozen manifests.

## Partitions and point comparisons

| Task | Train/dev/test cases | Test result | Simple baseline | Disposition |
| --- | ---: | --- | --- | --- |
| Binary | 219 / 38 / 43 | Accuracy 1.000; Brier 0.00000937; log-loss 0.00250 | Test-majority accuracy 0.605; train-prior Brier 0.24138 | Positive point result; paired grouped interval not calculated |
| Choice | 213 / 37 / 50 | 38 answerable; accuracy 0.500; log-loss 0.6945; 12 abstentions | Answerable majority accuracy 0.500; 12 no-answer examples | Indeterminate on answerable labels; abstention correctness needs row-level audit |
| Score | 195 / 51 / 54 | MAE 0.10979; RMSE 0.14001 | Train-mean MAE 0.83901 | Positive point result; paired grouped interval not calculated |
| Rank | 205 / 51 / 44 | NDCG 0.82572 (95% group-bootstrap interval 0.81546–0.84622); Recall@5 1.0 | Fixed input candidate order NDCG 0.79545 | Indeterminate: interval overlaps baseline point; only 18 groups contributed to the model interval |

Counterfactual rows come in adjacent pairs with the same load/availability and
opposite `active`; each pair has one leakage group, preventing split leakage.
The generated fixtures contain 300 cases per task. Choice includes 12 held-out
no-answer cases. The test partitions contain only 18–27 useful groups, below the
protocol's minimum 20 groups for some metrics/slices; those gates stay
indeterminate.

Dataset digests: Binary `sha256:7da3d69353cf5483bc3d791447fba1f8e971f6b40c8e9a7d275936e637fca715`; Choice `sha256:0ad36b8a2238be77847d7ccb4ca953c80b326bfdc34b9f913bd7859fdbb97053`; Score `sha256:94b64e8d17c68503c633731c9fadd88beba44ce41b6e559d6cc201dd4f5b5325`; Rank `sha256:635c3eb22983f6985c1cc0ad3a3fb4b11afa69bfb31cbeece1b94c63f82038ac`.

Split fingerprints: Binary `sha256:2f11df3a1b2c0216945b72676ae085b47f00399711c66947d51927b5c0c2fcb0`; Choice `sha256:97289087db38cfb72cc87c8a82626446c5fe7901a8149f0a4aa0b73d7ae3333e`; Score `sha256:325d638764619f16a241784d4a7905275bae4b46993ba25fe1dfca3a3e7c817e`; Rank `sha256:d4594f2451792812bccd8be689345d235013dd1a59432757d78eb28877cccc7d`.

Model digests: Binary `sha256:a863c5210a7393a9077364ef76614dac9a00f749949df190a2ae17d684657a06`; Choice `sha256:c74a4ed8805d221a8196952c53f09505c3ae5406caac0f642e5ce38dd3954bbd`; Score `sha256:3bf0dc638e7bc39a1a57da0cc0f2e724c8626626d58daeeb994356f28d0ee4e2`; Rank `sha256:292a8a95ad51428b3ca9f42ce17f845b5e0a03dfe15caf3b3244568c03a4d2c3`.

All four runs completed train -> artifact -> runtime reload -> test inference ->
evaluation locally. A trained nonlinear Rank artifact also reloaded and benchmarked
locally: SHA `sha256:d02df5776c50ceb249f2f583e0f5f9a6299aaa7b5fe6b5077a542e56edc88ae6`,
10,961 bytes, cold load 1,717 µs, peak RSS 4,837,376 bytes, invalid artifact
rejected. At 16/64/128/256 candidates, p50 was 451/1,793/3,631/7,225 µs and
p95 was 460/1,821/3,687/7,320 µs. This is one local host only; hosted trained
artifact runs are pending CI.

## Unresolved release gates

- The evaluator report does not retain per-case outcomes for paired grouped
  bootstrap deltas, score train-mean baselines, or Choice abstention correctness.
- Protocol freeze needs a committed-before-evaluation audit trail.
- Hosted Linux x86_64, Linux ARM64 and Apple Silicon runs have not yet reported
  for this revision.
- Dependency license audit and package dry-run are not yet recorded.

M011 remains active. These data say nothing about human or application tasks.
