# M011 closure — Independent held-out qualification and release readiness

Status: closed as a reviewable standalone release candidate; synthetic mechanics only
Implementation commits: `9a16d35b1513746a4c5c0fe2a01e6522047f2c45`, `bc0b061ee9b94390be67434d550b19606d5abb0a`, `ba1bb6e6339846036e405677d4ccb0d869ecaaa4`, `83b401d0c2faad8c3dddfde832ff982d50868dd4`, `eb49dd3c257712c7884d12e42b5b4ddff4571692`
Planning baseline: `319a05805f3a8383574d0d0712ca5975d16546ff`; M008–M010 accepted closures
Qualification workflow: [CI run 38089476441](https://github.com/dbowm91/sdm/actions/runs/38089476441), commit `eb49dd3c257712c7884d12e42b5b4ddff4571692`
Protocol: `sha256:f563e89dc7a2165edf4e48bffdd669db0337a2cdbf2b760d54713558d78c05d2`
Hosted Linux x86_64 qualification report: `sha256:b338774e9f4dbcc247ac44eb5f7413c5d4f27ee0eeef4abd294723ddde2170d6`
Held-out input/generator freeze commit: `bc0b061ee9b94390be67434d550b19606d5abb0a` (committed before v2 inference)

## Acceptance evidence

| Requirement | Evidence | Disposition |
| --- | --- | --- |
| A. Fresh frozen synthetic suites, family exclusions, counterfactuals, and preregistered gates | Four 400-example suites, generator seed 11012, independent leakage groups, paired counterfactuals, one 12-example excluded family per task, and a distinct 48-example test-only OOD family. Generator self-checks pair identity and that only the declared `active` feature changes. Frozen split files were checked byte-for-byte in all CI targets. Membership totals are recorded below. | Pass as mechanics; synthetic only |
| B. Trained heads/architectures, held-out controls, group uncertainty | Six train/package/reload/infer/evaluate workflows run on each stable target. 2,000-replicate paired group bootstrap compares Binary/Choice/Score/Rank with preregistered baselines; Rank linear and nonlinear use the same split and candidate universe. Held-out-only feature/label mutation tests preserve model and calibration digests. The report asserts each no-signal baseline control has zero paired delta and never passes the positive gate despite feature-dependent pairs. | Pass as qualification mechanics; predictive outcomes vary and include negative/indeterminate results |
| C. Trained artifact portability/resource evidence | CI downloads the exact Linux x86_64 trained nonlinear Rank artifact and loads, validates, rejects malformed bytes, and benchmarks it on Linux x86_64, Linux ARM64, and Apple Silicon. All three report the same artifact/model digests. The resource table records cold load, process high-water RSS, and latency. | Pass |
| D. Rust support and runtime dependency boundary | Rust 1.89.0 locked workspace fmt/test/strict Clippy/runtime-only check all pass. Stable Rust 1.99.0 passed the same full test/Clippy/runtime checks on all three targets. The runtime-only graph contains `sdm-core` and `sdm-nonlinear` plus serialization/hash dependencies; it excludes `sdm-data`, `sdm-eval`, `sdm-training`, and `sdm-experiment`. | Pass |
| E. Public use, formats, and docs | README, `docs/typed-task-heads.md`, `docs/release-qualification-protocol.md`, `docs/m011-local-results.md`, six runnable CLI examples, and `examples/standalone-consumer/` describe and exercise the public library/CLI/artifacts. CI compiles the separate locked consumer on all stable targets. | Pass |
| F. Release candidate audit | `cargo package --workspace --locked --allow-dirty` verified all seven crates; dependency metadata audit covered 34 locked packages; v1 compatibility remains 12 validated / 11 runtime executions with its frozen artifact digest. SHA-256 is documented as identity/integrity, not publisher authenticity. No publish, merge, CodeGG pin change, or deployment occurred. | Pass for review candidate; see open items |

## Frozen data and membership

Each split contains whole leakage groups. OOD cases route to test and excluded-family cases route to no partition. All groups in test are independent of train and dev.

| Task | Train / dev / test / excluded cases | Dataset SHA-256 | Split fingerprint |
| --- | ---: | --- | --- |
| Binary | 224 / 58 / 106 / 12 | `sha256:90a027233da5720112b08ac3170c4d4ab982f8a20cb134137337f0b77985559a` | `sha256:ed6e065fcbb28be2af5ad266b0bfbe11972662eabe9691009243268d08e70642` |
| Choice | 254 / 42 / 92 / 12 | `sha256:c16ff1f6e43a5be9dc9baed736265b7ceedc6ceb4fb958283a68ee06b039044c` | `sha256:9b0170c1bd96da3a3ebc157b4662858ba494750c9e1d465a69576a95104f6a25` |
| Score | 236 / 52 / 100 / 12 | `sha256:94e432876a6176ac713f64862bd03f3b3279a2d4e6db75c3f0b05b9a820226f3` | `sha256:f6f27d5b1b5f8a5c5d5cdc49c216265634e1531b3bd252e7dbb3f17c3b8b9cda` |
| Rank | 236 / 50 / 102 / 12 | `sha256:94a10fef15b2265add8ecea80559ab8c98b972346b947441304c13be4f182a71` | `sha256:a884ec2bea54847d1c1b27df3583e908b6ca80f10e26ac1ac7ec18fc51f34b66` |

The `test` count includes 48 OOD cases per task. Binary, Choice, Score, and
Rank have 53, 46, 50, and 51 test leakage groups respectively. The OOD family
has 24 groups; its supported Rank metric and Choice answerability slices each
have only 17 groups after metric eligibility and therefore remain indeterminate.

## Predictive quality results

All intervals are paired 95% group-bootstrap intervals (2,000 replicates).
Deltas are oriented so positive is favorable. These are generated-mechanics
results, never estimates of performance on application data.

| Task | Test metric | Baseline delta and interval | Primary | OOD slice | Counterfactual target / model-prediction changes |
| --- | --- | --- | --- | --- | ---: |
| Binary | Brier `0.2210` (106 cases) | Improvement `+0.0045 [-0.0643, +0.0704]`, 53 groups | Indeterminate | Negative, `-0.2589 [-0.2825, -0.2356]`, 24 groups | 36 / 26 of 53 pairs |
| Choice | Accuracy `0.5000` (70 answerable cases) | Delta `0.0000 [0, 0]`, 35 answerable groups | Indeterminate (ties majority) | Indeterminate, 17 answerable groups | 35 / 0 of 46 pairs |
| Score | MAE `0.3847`, RMSE `0.6277` (100 cases) | MAE improvement `+0.6874 [+0.6532, +0.7232]`, 50 groups | Positive | Positive, `+0.6015 [+0.5746, +0.6306]`, 24 groups | 50 / 50 of 50 pairs |
| Rank | NDCG `0.8923` (102 cases; 35 metric-eligible groups) | Delta `+0.1423 [+0.1104, +0.1758]`, 35 groups | Positive | Indeterminate, 17 metric-eligible groups | 35 / 46 of 51 pairs |

Choice no-answer abstention recall is `8/22 = 0.364`; its 11 independent groups
are under the preregistered 20-group support floor. This remains indeterminate
and is a prominent weakness. Rank's all-zero relevance rows are excluded from
NDCG comparison to match `sdm-eval`; model-score ties use candidate ID order.
On the same 35 eligible Rank groups, typed linear and nonlinear models each
scored NDCG `0.8155` and had a `+0.0655` delta over input order. The task-level
report records their model, artifact, and report digests.

| Rank architecture | Model SHA-256 | Artifact SHA-256 | CLI report SHA-256 | NDCG | Delta over input order (95% CI) |
| --- | --- | --- | --- | ---: | --- |
| Typed linear | `sha256:0fb2b9667e97a6752998d064efd917a428c2677a1de3cb6149240a548e98d4c7` | `sha256:77ee26b8be8985631152116416e8e4c07c9195d3b4c806db971361b79a15341f` | `sha256:c7a2070707d4e45965ccc891631dc72d08f21acb65661180d902ae0e7991b16c` | 0.8155 | `+0.0655 [+0.0655, +0.0655]` |
| Typed nonlinear | `sha256:88a40eb66efee69a91d7162a7cceb7fa5905635fb225f73222704d7ae9c3bdb1` | `sha256:fc09f6beb6a598028709d5fd04752825cced63de8d1812d3425970d90ac46e17` | `sha256:a04762783b4326eee3ad64b4fb2ed87c2e81eb6c75dc17af1deebc66611aeebb` | 0.8155 | `+0.0655 [+0.0655, +0.0655]` |

The constant-baseline negative control has a zero paired delta and does not pass
the positive quality gate for every task. The v2 generator also verifies that
only the designated boolean feature changes within pairs, while target labels
change in the reported 35–50 pairs per task. A model prediction need not change
for the pair to count as a valid generated counterfactual; the Choice result
shows that the learned head missed every tested target flip.

## Trained artifact portability and resources

The identical Linux-trained nonlinear Rank artifact was used for every row:

- Architecture: `sdm-pairwise-tanh-v2`; parameters: 145; artifact: 10,958 bytes.
- Model SHA-256: `sha256:57bd4e5298cb37cd6f513734dd9d5af9889dd7962c6b1a71c6ee95adff1b8d71`.
- Artifact SHA-256: `sha256:4d2c426e5db76116caf034c70352edb9baff27ca4f5f3793fe2f76440cd0eefb`.
- Invalid artifact rejection: true on all targets. The identical artifact loaded
  and returned the same model identity on each target.
- Latencies are p50/p95 microseconds from 500 warmed inference samples at each
  candidate count. RSS is process high-water memory, not model-only allocation;
  do not compare RSS across operating systems.

| Target | Cold load µs | Peak RSS bytes | 1 candidate | 16 candidates | 64 candidates | 128 candidates | 256 candidates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Linux x86_64 | 1,399 | 45,858,816 | 27 / 31 | 411 / 428 | 1,656 / 1,681 | 3,345 / 3,402 | 6,640 / 6,734 |
| Linux ARM64 | 2,254 | 45,678,592 | 33 / 34 | 515 / 519 | 2,058 / 2,063 | 4,185 / 4,198 | 8,305 / 8,325 |
| Apple Silicon | 2,170 | 2,736,128 | 23 / 75 | 364 / 469 | 1,462 / 1,907 | 2,908 / 4,132 | 5,809 / 9,622 |

The final workflow additionally trained each platform's own artifact and ran
the full task suite and resource benchmark there. Cross-platform model bytes
can differ when independently trained under different target/toolchain floating
point behavior; the shared-artifact matrix above is the portability evidence.
Latency values are descriptive CI observations, not hard pass/fail thresholds.

## Commands, compatibility, dependency, and release audit

Final CI run 38089476441 at `eb49dd3c257712c7884d12e42b5b4ddff4571692` passed:

- Stable Rust `1.99.0 (b940084d7 2026-09-28)`: fmt, all-feature locked
  workspace tests (34 tests), strict Clippy, runtime library/examples, frozen
  compatibility, six M011 workflows, runtime benchmarks, and standalone
  consumer compile on Linux x86_64, Linux ARM64, and Apple Silicon.
- Declared MSRV `1.89.0 (29483883e 2025-08-04)`, host
  `x86_64-unknown-linux-gnu`: fmt, locked all-feature workspace tests, strict
  Clippy, and `sdm-runtime` check all passed.
- Runtime-only graph: `rtk cargo tree -p sdm-runtime --locked`; no data,
  evaluation, experiment, training, network, or GPU crate is present.
- Frozen v1 check: `cargo run -q -p sdm-training --bin sdm-check-compat --locked
  -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json`
  passed: 12 validated, 11 runtime executions. The artifact remains
  `sha256:b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597e`.
- Standalone consumer: `cargo check --manifest-path
  examples/standalone-consumer/Cargo.toml --locked`, also compiled in each
  stable CI target.
- Package verification: `cargo package --workspace --locked --allow-dirty`
  verified all seven crates. Cargo reported missing description, documentation,
  homepage, and repository metadata; add those before a crates.io publication.
- Locked dependency audit: 34 packages have declared license metadata. This
  checks metadata completeness only; it is not a legal compatibility review.
- Artifact SHA-256 detects identity/corruption changes but is unsigned and does
  not authenticate a publisher. Runtime validation rejects malformed/invalid
  artifacts and remains offline. MIT provenance is retained; no consumer data
  was imported. No wire migration or v1 compatibility change was made.

## Open risks by severity

- **High for application use:** Binary's OOD comparison is negative; Choice
  ties its majority baseline, misses all 35 target-changing tested pairs, and
  abstains on only 8/22 no-answer examples. Do not select or promote these
  synthetic-trained models for real decisions. This does not fail the
  standalone mechanics/release-infrastructure acceptance.
- **Medium:** Choice and Rank OOD metric support is below 20 groups, leaving
  those OOD quality conclusions indeterminate. No transfer claim is supported.
- **Medium before registry publication:** Cargo package metadata warnings for
  description/documentation/homepage/repository remain. Package verification
  passed; this work did not publish crates.
- **Medium process limitation:** dependency license strings are present, but no
  human legal license compatibility review was performed.
- **Low / stated trust limit:** artifacts have no publisher signature. Keep
  release delivery pinned and reviewed; SHA-256 alone is not authenticity.

## Other work-line eligibility and disposition

M008, M009, M010, and M011 are closed in the standalone framework line. The
registry contains no other independently eligible implementation line. M001,
M002, M003, M004, and M006 retain their already-closed or conditional historical
dispositions; M007's corrective evidence work is complete. M005 remains
conditionally closed / indeterminate because the independent CodeGG corpus and
consumer-side approval are unavailable. It is an external gate and was not
started or changed.

M011 is closed as a release-readiness and mechanics milestone. The repository
has a reviewable candidate, not evidence for general predictive usefulness or
authorization to publish, merge, pin in CodeGG, or deploy.
