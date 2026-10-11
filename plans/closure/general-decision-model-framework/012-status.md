# M012 closure — Post-M011 release reconciliation

Status: **conditionally closed** — source integration and review handoff complete; crates.io publication blocked pending human/legal license review.

Implementation commit: `8b1fb5616ef6adb0dcd947a78776a1b93831ea62` (`feat: complete M012 release reconciliation`).
Planning commits retained in ancestry: `b0c591c` and `810864c`.
Planning baseline: M011 source `f9ce89765a1cb07ce23100177d8f56c30e52777d`.
Integration base and merge-base: `main@8139b064bdcf3212e8f6fd912e801a479b55751c`.
Live `origin/main` was rechecked at closure and remained `8139b064bdcf3212e8f6fd912e801a479b55751c`.
Pull request: [#1 — M012: reconcile SDM release metadata and packaging](https://github.com/dbowm91/sdm/pull/1), open and mergeable at closure; base SHA `8139b064bdcf3212e8f6fd912e801a479b55751c`, head SHA `8b1fb5616ef6adb0dcd947a78776a1b93831ea62`.
Hosted verification: [CI run 38098107759](https://github.com/dbowm91/sdm/actions/runs/38098107759), completed successfully; PR check summary was 14 passed, 0 failed, 1 skipped/neutral. The earlier push-triggered run 38098086554 also completed successfully.

## Requirement-to-evidence matrix

| Requirement | Evidence | Disposition |
| --- | --- | --- |
| A. Branch and history reconciliation | The current branch descends from the complete M008–M011 work line, which itself descends from M001–M007; no duplicate implementation commits were cherry-picked. `git merge-base HEAD origin/main` is the unchanged main SHA above. PR #1 presents the complete source integration diff. | Pass; main remains unchanged pending review. |
| B. Seven package manifests, contents, dependency order, and consumer boundary | All seven crates inherit verified GitHub homepage/repository metadata and define a crate-specific description and docs.rs destination. Clean `cargo package --workspace --locked` passed without metadata warnings. [`package-files.json`](../../../docs/package-files.json) records each crate's packaged paths; no fixtures, model artifacts, build outputs, credentials, or private user datasets are included. `scripts/check_staged_consumer.py` extracts all seven `.crate` archives and compiles the standalone consumer with internal crates resolved by package name/version. Future publication order is recorded in the standalone quickstart. | Pass for source/package verification; no registry operation performed. |
| C. License and artifact trust review | [`third-party-license-inventory.json`](../../../docs/third-party-license-inventory.json) inventories all 34 locked workspace/transitive packages, their Cargo SPDX expressions, and SDM's metadata-only MIT-branch choice for OR expressions. CI regenerates and compares the inventory and rejects missing, unsupported, or ambiguously selected expressions. The review limits and inherited Anomalyco MIT attribution are documented in [`third-party-licenses.md`](../../../docs/third-party-licenses.md). SHA-256 is documented as byte identity/integrity, not publisher authentication; source/artifact consumers require a trusted channel and immutable source SHA. | Inventory and disclosure pass. Actual package license texts, attribution obligations, and compatibility have **not** received qualified human/legal sign-off. Registry publication is blocked until that review is recorded. No artifact-signing capability is claimed. |
| D. Documentation, interfaces, correctness, and authority boundary | [`standalone-quickstart.md`](../../../docs/standalone-quickstart.md) covers synthetic experiment train/package/reload/evaluate flow, runtime artifact dispatch, unsupported combinations, bounded errors/abstention, public API/version boundary, and reproducibility scope. README, planning README/registry, and roadmap now reflect M012's observed state. Legacy v1, additive typed v2, offline-only loading, runtime dependency boundary, and M011 negative/indeterminate results are retained. | Pass. No application authority, implicit data import, runtime training dependency, or compatibility change was introduced. |
| E. Local, package, compatibility, and hosted verification | Rust 1.89.0 local format, all-feature workspace tests (34 passed), strict Clippy, and runtime-only check passed. Clean locked workspace package verification, all seven package file-list audits, the 34-package license inventory check, and staged consumer compile passed. CI run 38098107759 passed Rust 1.89 MSRV and stable Linux x86_64, Linux ARM64, and Apple Silicon jobs, including six documented experiment configs, M011 generator/split/protocol checks, runtime graph and CLI compatibility checks, package/license checks, and staged consumer compile. | Pass for source release-readiness evidence. |

## Package, compatibility, and qualification evidence

Clean local `cargo package --workspace --locked` completed for all seven crates, with no Cargo publication-metadata warning. Cargo's current archive sizes were: sdm-core 52.1 KiB; sdm-data 38.9 KiB; sdm-eval 40.0 KiB; sdm-nonlinear 28.9 KiB; sdm-runtime 67.8 KiB; sdm-training 29.7 KiB; and sdm-experiment 70.3 KiB (uncompressed package contents). These figures describe package verification only, not registry publication.

The frozen CodeGG v1 compatibility command passed on local Rust 1.89.0 and all hosted stable targets: 12 validated requests, 11 runtime executions. The legacy artifact remains `sha256:b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597e`. No fixture, compatibility contract, consumer pin, or artifact bytes changed.

The hosted portability jobs loaded the same Linux-trained nonlinear Rank artifact on all three targets. Artifact SHA-256 was `sha256:4d2c426e5db76116caf034c70352edb9baff27ca4f5f3793fe2f76440cd0eefb`; model SHA-256 was `sha256:57bd4e5298cb37cd6f513734dd9d5af9889dd7962c6b1a71c6ee95adff1b8d71`. Invalid artifact rejection passed on every target. Latencies are p50/p95 microseconds from 500 warmed samples; RSS is process high-water memory, not model-only allocation.

| Target | Cold load µs | Peak RSS bytes | 16 candidates | 64 candidates | 128 candidates | 256 candidates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Linux x86_64 | 674 | 46,018,560 | 219 / 226 | 879 / 894 | 1,776 / 1,812 | 3,532 / 3,624 |
| Linux ARM64 | 2,190 | 45,641,728 | 518 / 522 | 2,071 / 2,078 | 4,210 / 4,222 | 8,353 / 8,374 |
| Apple Silicon | 1,848 | 2,768,896 | 345 / 410 | 1,410 / 1,643 | 2,791 / 3,026 | 5,572 / 7,035 |

The M011 generator, split fingerprints, frozen protocol SHA `sha256:f563e89dc7a2165edf4e48bffdd669db0337a2cdbf2b760d54713558d78c05d2`, and qualification report SHA `sha256:b338774e9f4dbcc247ac44eb5f7413c5d4f27ee0eeef4abd294723ddde2170d6` match the checked-in M011 closure evidence. The fresh hosted run's qualification report had that same SHA. Current hosted task report identities were:

| M011 task report | SHA-256 |
| --- | --- |
| Binary | `9e1af745541f2a739fe924f3dda4bd189080d205099a46bd259b7fe9acad9346` |
| Choice | `d5c1b2a024bfaa22f2c0cc5f24a6a565b1785b7c0ff0eba56329a7d3093fc53c` |
| Score | `1a62724e7355b9f8acfdb3d1025db8c63d023bd7f34d4dc44aa079818c3273ef` |
| Rank | `b4751ae08c996a7cca767e83dcc5e90346627a1177e0c0afbbe2be0c883128a6` |
| Rank linear ablation | `e29c24b0967705540b774ce16731e17327262396c5860e719d8a66ae13b57c98` |
| Rank nonlinear ablation | `9085a29adf90b0d923b9c6e34b86cb9ffff5c42ee93d4f42fdac1db5df3d831a` |

M011 predictive outcomes remain unchanged and are not release qualification claims: Binary OOD is negative (`-0.2589` Brier improvement); Choice ties the majority baseline, changes zero predictions across 35 target-flipping counterfactual pairs, and has no-answer recall `8/22`; Choice and Rank OOD support remains below the 20-group threshold. Only synthetic Score and Rank primary metrics were positive. No application-data usefulness or production fitness is inferred.

## Security, privacy, and open risks

- **High, application use:** M011's negative/indeterminate Binary and Choice results remain unsuitable as evidence for real decisions. They are retained in the M011 closure and current docs.
- **High, registry distribution:** Legal review of exact package license texts, selected dual-license terms, notices, attribution, and compatibility is outstanding. Publication is blocked until a qualified human/legal reviewer records sign-off.
- **Medium, merge:** PR #1 is open and mergeable but has no merge decision. Human review is pending. This closure does not merge it.
- **Low, artifact trust:** Artifacts remain unsigned. SHA-256 checks identity/integrity only. Consumers must verify immutable source provenance through a trusted delivery channel.
- **Privacy/authority:** No user dataset or CodeGG corpus was imported. SDM remains offline, does not download models, and does not grant candidate, permission, disclosure, fallback, or actuation authority to applications.
- **ABI/migration:** No v1 schema, API, dependency, or CodeGG compatibility migration occurred. Internal dependencies remain versioned path dependencies in the workspace and normalize to version dependencies in packaged archives.

## Decisions and successor eligibility

- **Source integration:** reviewable through PR #1; merge decision pending human review. No merge, tag, crates.io publish, release, or CodeGG pin update was performed.
- **Publication:** blocked pending the human/legal review described above. The metadata audit is not legal clearance.
- **M011 evidence:** historical positive, negative, and indeterminate results remain unchanged; this corrective is not a model-quality milestone.
- **Future implementation plans:** no further ready/eligible implementation plan is registered after M012. M001–M011 retain their recorded closures. M005 remains conditionally closed/indeterminate and externally deferred until an approved independent CodeGG corpus and consumer-owned evidence exist; that hard external dependency prevents starting it. No new successor plan is unblocked by this source/release corrective.
