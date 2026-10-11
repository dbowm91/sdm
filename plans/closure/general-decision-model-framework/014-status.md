# M014 status — indeterminate, not closed

Date: 2026-10-11  
Freeze: `docs/m014-freeze-v1.json`, committed at `6d55112f2cfad1167c3691b1068b03593178588e`  
Hosted freeze CI: [38117443065](https://github.com/dbowm91/sdm/actions/runs/38117443065), all jobs succeeded.

## Final run record

The five frozen final configs were run once, after the freeze commit and green CI. Reports and their exact output artifacts are preserved in `artifacts/m014/final-v1/`. All reports identify the expected frozen test split and say `synthetic-mechanics-only`; the serializer omits `test_evaluation_performed` when its default `true` applies.

Aggregate test metrics below are descriptive only. They mix ID and shifted test families and do not establish the preregistered per-family gates:

| Candidate | Test rows | Accuracy | Brier / log loss |
|---|---:|---:|---:|
| Binary legacy | 1,388 | 0.7839 | Brier 0.21120 |
| Binary constant-mask | 1,388 | 1.0000 | Brier 0.000000814 |
| Choice legacy | 1,438 total; 956 answerable | 0.5000 | log loss 0.70825 |
| Choice cross | 1,438 total; 956 answerable | 0.5000 | log loss 0.86511 |
| Choice compositional | 1,438 total; 956 answerable | 1.0000 | log loss 0.0003521 |

The Choice output artifacts exactly match their frozen candidate artifact hashes. Binary baseline expected `sha256:3d3c1a1453c274d19bdbdd47751c385246f172b5843ad3f5df42e5ddd812e810` but produced `sha256:537ca2ef6dcdfeaa55224efab03973e54eac3ada67af3f89220e7469b7b0f071`; Binary mask expected `sha256:19c2a3406944d19dc9b81aba4647e2c75f87317af2b7d4dd5e8d35129dd83260` but produced `sha256:6e1e9fd20da70588e6c2660a6994d76834a842191486df752cdc2a60f1d8943b`. The Binary final run therefore did not evaluate the exact frozen candidate bytes. No replacement run is allowed on this cohort.

## Qualification disposition

Both tasks remain **indeterminate**. The committed analysis program cannot produce the preregistered report from the serialized outputs: its test flag check does not account for serde's omitted `true` default, and its Binary aggregation assumes one outcome per leakage group although each M014 group contains a counterfactual pair. No confidence intervals, complete negative-control adjudication, or full resource-gate disposition are claimed. This is an evaluator/procedure failure, not a model-quality conclusion.

No model, threshold, protocol, or gate was changed after the test run. Do not rerun any `m014-final-*` config on this cohort. Any corrected qualification requires a new independent cohort, a new freeze and protocol, and a new milestone; M014 remains active pending that work.

## Report SHA-256

| File | SHA-256 |
|---|---|
| `binary-baseline.report.json` | `46a85b408bf45ec64f5bff7aa2f0a6f72a0642dc851c6140d3a34721af51d2f2` |
| `binary-mask.report.json` | `40f72bea597a88eef693a22461f449f4e302e478648098741fee764eb4ab2b44` |
| `choice-legacy.report.json` | `3f7a862bb33e922c6b0504630c611d502b4a47f4eb238ec703e3dfd620bc6c23` |
| `choice-cross.report.json` | `33d216aaeccafaac096f6a184dd39058463a42d992f8b4fc9c65f199d5e838e6` |
| `choice-compositional.report.json` | `9fc0272ac080203b07d8b807bb7cc3c5e7b14d6c91235f5281d724f4f83ff2d4` |
