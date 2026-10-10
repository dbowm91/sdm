# M008 closure — Standalone reproducible Rank experiment pipeline

Status: closed for end-to-end mechanics; no predictive-quality or CodeGG claim
Implementation commit: `6c49fedfcf8f8711ce8fe5079553f4328b95e730`
Baseline: M008 handoff baseline `319a05805f3a8383574d0d0712ca5975d16546ff`; source head re-audited at branch head before implementation

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Reusable orchestration API and discoverable CLI | `sdm_experiment::run(ExperimentSpec)` plus `sdm experiment run --config PATH`; legacy binaries are untouched. | Pass |
| Explicit provenance-bearing Rank data and frozen, group-disjoint split | `fixtures/standalone-rank-v1.json` has 36 deterministically generated examples, explicit synthetic-only provenance and 36 leakage groups. `fixtures/standalone-rank-v1.split.json` pins dataset digest `sha256:a540da906d9d0454477dc4203bcdc51bbd57489b2f27cb2df10dbe40cf9d6494`, seed 42 and split fingerprint `sha256:495d840c5e16d0e1a22d88da5e6afa807c28da2c79c72fd0dd1801d34ce7e17b`. Actual membership is 22 train, 5 dev and 9 test. | Pass |
| Train linear and nonlinear Rank directly from Rank labels | New crate adapters consume the manifest-selected `DatasetExample` partitions and fit on train only. They do not synthesize legacy `DecisionResponse` values or resplit. | Pass |
| Dev-only calibration and held-out invariance | Threshold search receives dev only. `held_out_label_changes_do_not_change_model_or_dev_calibration` mutates a test label, rebinds the immutable split to the changed dataset, and confirms model and calibration digests are unchanged. | Pass |
| Safe packaging and actual runtime inference | Both architectures are serialized, passed through `load_artifact`, and inferred via `sdm-runtime`. Candidate identities are carried through evaluation and exact-universe coverage is 1.0. Atomic create-new output refuses overwrite. | Pass |
| Held-out report and synthetic controls | Both end-to-end runs report held-out Rank metrics, dataset/split/model/calibration/artifact/report fingerprints, partition IDs, and the explicit `synthetic-mechanics-only` disposition. No real-world effectiveness is inferred. | Pass with documented scope |
| Documentation and automated end-to-end CI | README quickstart and separate checked-in configs; CI runs both architecture commands. | Pass |

## Observed local results

Both runs use identical frozen data and partitions. Linear and nonlinear each report test MRR, Recall@5 and NDCG of 1.0 on this deliberately small synthetic corpus. These figures establish pipeline mechanics only; they are not quality evidence. Linear artifact digest: `sha256:c519f30fd13052090c66df452bb445bf00b17048d369107cef1da08910b042f3`. Nonlinear artifact digest: `sha256:fc672bc9fb9657ac6741eebe93f1feff78a11c487c2608b64df92e1f5600b1e0`.

## Verification

- `rtk cargo fmt --all` — pass.
- `rtk cargo test --workspace --all-features --locked` — pass, 26 tests across 19 suites.
- `rtk cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — pass.
- `rtk cargo check -p sdm-runtime --locked` — pass.
- `rtk cargo tree -p sdm-runtime --locked` — pass; no experiment/training/evaluation/data dependency in runtime graph.
- `rtk cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json` — pass, 12 fixtures and 11 runtime executions; frozen runtime artifact digest `sha256:b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597e`.
- Linux x86_64 local end-to-end invocations for both configs — pass.
- Hosted Linux ARM64 and Apple Silicon execution are configured in CI but have not been observed for this implementation revision yet.

## Compatibility, privacy, and open risks

The runtime-only dependency graph and v1 artifact/fixture results remain unchanged. Input paths are explicit and bounded; no network or implicit project scanning is used. The data and model are synthetic and local. Config/report/artifact digests establish identity, not authenticity. The small corpus provides mechanics evidence only; larger independent synthetic coverage and hosted trained-artifact resource measurements remain M011 work.

Disposition: accepted closure for M008's orchestration gate. M009 is ready. M005 remains externally gated and unchanged.
