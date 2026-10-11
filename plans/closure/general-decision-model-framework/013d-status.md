# M013d — Bootstrap safety and M013 source-stack integration

Status: **conditionally closed** — estimator mechanics, provenance replay, and PR handoff are complete; hosted PR CI is green 10/10. Reviewer approval/merge and merged-main verification remain outstanding. No model is qualified or promoted.

Plan: `plans/implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md`  
Closure governance: `plans/003-planning-process.md`  
Planning branch/head: `work/plans-sdm-m013d-bootstrap-source-integration` / `f1b2d4847d70bf762ba84b222007c3c8a8b7778b`  
M013c pre-fix baseline: `03c4a982219ffa830b7c0aba9dbb19a541cae56c`  
Implementation commits: `ca540c2f77917a608f1c2fa2fb01119317bfd3ca` (bootstrap repair and tests), `246ee355031a921d44f7bd69964a477f1831fad7` (atomic M013d audit output), `17089c2ff659a5601e11227bd8710c139d0d4b0e` (host-stable provenance checks), `435cef7f7f6da6a017d33c4e3742e9920b3ec94b` (per-host pinned replay in CI), and `ffe295b6fd9c9bb73291cd9e61f0e935d162bfe0` (interrupted-write regression test)  
Base/main at implementation: `2bd0d5af16d143828dcbce7f411b8f3b675e7be`  
Merge base: `2bd0d5af16d143828dcbce7f411b8f3b675e7be`  
PR: [#2 — M013–M013d: repair bootstrap and integrate evaluator source](https://github.com/dbowm91/sdm/pull/2), targeting `main`; open, review decision pending, not merged.  
Hosted PR CI: run [38111257896](https://github.com/dbowm91/sdm/actions/runs/38111257896) on implementation head `ffe295b6fd9c9bb73291cd9e61f0e935d162bfe0`; **all 10 jobs passed**. It replays pinned outputs on each verification host. Runs 38110937441/38110939912 caught an over-strict assertion of the Mac-specific M013b diagnostics hash on Linux; the check now validates stable policy/verdict fields and same-host pinned/current output equality. The earlier planning baseline run [38109647535](https://github.com/dbowm91/sdm/actions/runs/38109647535) was green 10/10 on `03c4a982219ffa830b7c0aba9dbb19a541cae56c`; it does not validate the M013d implementation.

## 1. Disposition and scope

M013d fixes the reusable M013b `quantile` contract by validating values and probability, sorting an internal copy, and retaining the frozen linear interpolation. `group_bootstrap` now rejects invalid seeds, replicate counts, confidence, group identifiers, and non-finite/failed statistics; it sorts group IDs before resampling and preserves the explicit zero-group result (`groups=0`, `lower=null`, `upper=null`). One-group and constant-population intervals remain degenerate as before. The seed, 10,000 default draws, group resampling definition, 95% interval, output fields, and interpolation do not change.

The original historical reports, M013a protocol/data/splits, trained artifacts, old evaluator commits, M013b/M013c closure records, Rust crates, manifests, runtime-only dependency graph, artifact compatibility, and CodeGG pin are unchanged. No M013a test data was used for tuning, model selection, or new inference. The change does not qualify a model. The M013–M013d source stack is presented in one normal review PR; no direct main push, merge, tag, or publication was made.

## 2. Quantile regression evidence

`scripts/test_m013d_bootstrap.py` calls the actual M013b `quantile` and `group_bootstrap`. Tests cover unordered permutations, input immutability, interpolation boundaries, invalid/non-finite inputs, determinism, sorted group ordering, group support, zero/one-group semantics, constant data, source-hash provenance chaining, and the machine-readable provenance assertion.

| Constructed population | Groups / rows | Corrected lower, upper | Old unsorted lower, upper | Comparison |
|---|---:|---|---|---|
| Skewed values `[0,0,0,1,4,15,40]` | 7 / 7 | `0.7142857142857143`, `19.860714285714234` | `6.767857142856668`, `8.432142857144884` | Matches M013c and frozen M013a sorted bootstrap within 1e-12; old estimator fails |
| Paired rows `[(-3,1),(-1,2),(0,2),(1,4),(2,5)]` grouped in five leakage groups | 5 / 10 | `0.0`, `2.7` | `0.054999999999512106`, `0.7124999999998181` | Matches M013c and frozen M013a sorted bootstrap within 1e-12; old estimator fails |

Both comparisons use seed 14014, 10,000 draws, 95% percentile intervals, and linear interpolation. The paired statistic averages within each leakage group; the support is five independent groups, not ten rows. Repeated runs and input/group order permutations are deterministic.

## 3. Historical and current SHA ledger

The pinned pre-fix checkout at `03c4a982219ffa830b7c0aba9dbb19a541cae56c` reproduced all four original outputs. The M013b source bytes at both `11ea106c9af3b1ec362a98e709b530cc0fa137d0` and `03c4a982219ffa830b7c0aba9dbb19a541cae56c` hash to `161b1881efeb7750d8b5308d603cf318f5f16579d1db8d51739bbb8ba356cedb`. M013c source at pinned commit `8dd8a2151ef0c5b88adf5ce0c164992636bc17ee` and baseline `03c4a982219ffa830b7c0aba9dbb19a541cae56c` hashes to `edab5ff23238b58cb4441aee96d227073bf78911e61b0c97a35c55e36fc68e07`. The current M013b evaluator source at `246ee355031a921d44f7bd69964a477f1831fad7` is `8e92e901837adca64dc4985831a43f400d408c8b094e95be29beb25d1ecfd118`.

| Artifact | Original pinned SHA256 | Current regenerated SHA256 | Result |
|---|---|---|---|
| M013a quality analysis | `411ac0915a0dd6ae94710271b1b23bbad830732762b956dcca71500b6f592d6e` | `411ac0915a0dd6ae94710271b1b23bbad830732762b956dcca71500b6f592d6e` | Byte-identical |
| M013b erratum | `07fb99f1e984354a6746f3645f893beadfbbb3fd40ce4e37d4b6a834a0e15901` | `d0607528d6752e8d3b3c8ec6fa201cb3f59eab084cd632c120923380be82f3bc` | Expected source fingerprint change; semantic projection identical |
| M013b diagnostics | `3b489c25eb0fcd51b7dc08d7e9e7a1e1a45a6f16e244cf5a8173e8aceb728da4` | `3b489c25eb0fcd51b7dc08d7e9e7a1e1a45a6f16e244cf5a8173e8aceb728da4` | Byte-identical on this Mac replay; per-host CI verifies same-host identity |
| M013c decision audit | `6560052ba93445288d1b7577c475d0fcaec12035d9838c8c955a91ced2801edf` | `f482c84587c12a37213ecdbcb6f133acedec029ede8b76666e7fe8cd33c6e3ce` | Expected dependent source fingerprint change; semantic projection identical |

The M013b diagnostics SHA `3b489…` reproduces in the pinned/current Mac replay. The first Linux CI attempt produced a different host-specific digest (`d418bf…`) and exposed an invalid cross-host byte-hash assertion. The final CI step regenerates both pinned and current diagnostics on the same host, asserts equality there, and compares stable policy/verdict fields; it does not assume a Linux artifact has the Mac digest. All four report outputs are therefore either byte-identical on the same host or semantically identical with the expected source-hash-only difference.

`target/m013d/bootstrap-provenance-audit.json`, generated by `scripts/m013d_provenance_audit.py`, records `historical_preserved=true`, `model_qualifications_unchanged=true`, both source hashes, old/current sidecar hashes, and per-artifact causal explanations. It asserts semantic equality after excluding only `input_sha256`. M013b embeds the evaluator source hash; M013c hashes the M013b sidecar, so these two dependent digest changes are required and are not evidence changes.

Retained dispositions are Binary **negative** and Choice **indeterminate**. Every recorded interval that traversed the defective M013b helper was degenerate, so its old numeric bounds remain unchanged. The historical Binary text/combined-shift negative intervals, M013a held-out CI bounds, Choice fixed-option comparisons, M013c support-bounded gates, and named controls remain semantically equivalent. No positive model qualification is asserted.

## 4. Verification record

Local verification completed on the implementation worktree:

- `python3 -m unittest discover -s scripts -p 'test_m013d_*.py'` — 9 tests passed, including an injected interruption that preserves the old accepted audit and removes the temp file.
- `python3 -m unittest discover -s scripts -p 'test_m013b_*.py'` — 47 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_m013c_*.py'` — 71 tests passed.
- `python3 scripts/validate_m013a_freeze.py` — passed; dataset and split hashes match the frozen manifest.
- `python3 scripts/analyze_m013a_quality.py` — regenerated the original quality-analysis SHA exactly.
- `python3 scripts/m013b_audit_m013a.py`, `python3 scripts/m013b_diagnostics.py`, and `python3 scripts/m013c_qualification_audit.py` — completed; new sidecars retain the original verdicts and semantic fields.
- Pinned replay at M013c baseline `03c4a982219ffa830b7c0aba9dbb19a541cae56c` reproduced all four expected original SHA256 values exactly.
- M013a binary and Choice dataset splits were regenerated and byte-compared with the frozen split fixtures.
- `cargo fmt --all -- --check` — passed.
- `cargo test --workspace --all-features --locked` — passed all workspace tests and doc tests.
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — passed.
- `cargo check -p sdm-runtime --locked` and `cargo tree -p sdm-runtime --locked` — passed; runtime graph remains isolated to the existing workspace dependencies.
- `cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked` — passed.
- `cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json` — validated 12 frozen CodeGG fixtures (11 runtime executions).
- `git diff --check` — passed.
- Full source-stack diff reviewed against `main`: 64 tracked paths before closure-status documentation; large M013/M013a synthetic fixtures remain in their established paths. No `target/`, virtual environment, or Cargo manifest/lockfile changes are included. Hosted package-file and third-party-license inventory jobs passed in run 38111257896.

The source changes are Python evaluator/audit/tests and the existing CI workflow. No Rust crate or manifest changed. Hosted PR run 38111257896 is the required implementation-head check and replays the pinned pre-fix checkout inside each verification host. All job logs are linked from that run:

| Hosted job | Result |
|---|---|
| `msrv` (Rust 1.89) | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114387128541) |
| `verify (linux-x64)` | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114387128556) |
| `verify (macos-arm64)` | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114387128601) |
| `verify (linux-arm64)` | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114387128616) |
| `portability (linux-x64)` | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114388180142) |
| `portability (linux-arm64)` | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114388180129) |
| `portability (macos-arm64)` | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114388180111) |
| `choice-portability (linux-x64)` | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114388180071) |
| `choice-portability (linux-arm64)` | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114388180128) |
| `choice-portability (macos-arm64)` | [success](https://github.com/dbowm91/sdm/actions/runs/38111257896/job/114388180124) |

## 5. G1–G10 acceptance matrix

| Gate | Evidence | Status |
|---|---|---|
| G1 legacy estimator safe | M013b quantile sorts validated values; non-degenerate grouped tests fail the old implementation | Pass |
| G2 exact reproducibility | Fixed seed/count/confidence/interpolation and same-group M013a/M013c comparison within 1e-12 | Pass |
| G3 historical provenance | Pinned outputs reproduced; source and current dependent hashes recorded separately | Pass |
| G4 model verdict preservation | Binary negative; Choice indeterminate; semantic audit confirms no qualification changes | Pass |
| G5 CI platforms and runtime | Rust fmt/test/Clippy/runtime checks locally and all ten hosted jobs green on 38111257896, including per-host pinned replay | Pass |
| G6 security/storage | No new external/data imports; existing M013b/M013c atomic output retained; M013d JSON writer uses fsync + atomic rename + cleanup | Pass |
| G7 source PR | Single PR #2 includes the complete M013–M013d stack against `main` | Pass; review pending |
| G8 merged-main verification | No merge exists; main SHA remains `2bd0d5a…` | Pending reviewer approval/merge |
| G9 planning consistency | Registry, roadmap, README, plan status and this closure are updated together | Pass |
| G10 gate separation | No publication, tag, CodeGG pin change, promotion, or new held-out inference | Pass |

## 6. Compatibility, privacy, resources, and release gates

This change does not touch Rust MSRV 1.89, the three-host target matrix, 16 MiB model bound, v1/v2 artifact formats, offline runtime dependency graph, trained artifacts, input fixtures, tool/candidate authorization, or CodeGG's immutable SDM pin. The M013b evaluator remains pure; the new provenance audit reads local source/artifact files and writes only under `target/m013d/`. No CodeGG content or user content was ingested.

M013b and M013c audit writers already stage a complete temporary JSON file, flush/fsync, atomically replace the destination, and remove the temporary on `BaseException`. Their behavior is unchanged. The new M013d provenance writer uses the same failure/cancellation behavior, so an interrupted run leaves no accepted partial audit.

Standalone consumer compilation passed locally. Hosted CI run 38111254600 includes staged package and license inventory jobs; result pending. This is not a license publication decision. No `cargo publish`, release tag, or crates.io operation was performed. Human/legal license review remains required before publication. CodeGG M005 remains deferred pending an independently approved corpus and consumer-owned qualification.

## 7. Integration status and successor readiness

M013d is **conditionally closed** for mechanics, evidence, and PR handoff. PR #2 is open, targets `main`, and has no recorded reviewer decision or merge. Do not describe the source stack as integrated on main and do not claim merged-main CI. A human reviewer must approve and merge the PR; then verify exact `merged_at`, main SHA, merged-main CI, and file ancestry before changing this status from conditional to fully integrated.

No further implementation plan is currently eligible. M014 or a later predictive milestone is **not registered ready**: it requires the reviewed M013–M013d merge, a separate prospective protocol with new independent test groups and numeric thresholds, and a passing pre-inference eligible-support audit. No M013a test row is eligible for selection. M005 remains externally deferred. The crates.io legal gate is independent and remains outstanding.
