# M011 qualification status

M011 v1 results were exploratory and were discarded after counterfactual and
family-exclusion design changes. The final v2 suite uses generator seed 11012,
400 rows per task, paired counterfactuals grouped together, a whole synthetic
family excluded from every partition, and a separate out-of-distribution family
routed entirely to test.

The v2 generator and split manifests are being committed before any v2 test
inference, as required by the release protocol. The checked-in CI workflow runs
the four v2 train/reload/infer/evaluate workflows on Linux x86_64, Linux ARM64,
and Apple Silicon, then generates a machine-readable baseline and grouped
bootstrap report at `target/m011-v2/qualification-report.json`.

M011 remains active until the committed-data runs finish and their baseline,
platform, MSRV, dependency/license, compatibility, and release audit evidence is
recorded. Synthetic mechanics outcomes do not establish application effectiveness.
