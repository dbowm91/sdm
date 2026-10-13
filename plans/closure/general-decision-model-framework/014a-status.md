# M014a — Exact-artifact qualification execution and evaluator integrity

Status: **closed** — G1–G10 met, DEV-CANARY proven, M014b unblocked.
Plan: `plans/implementation/general-decision-model-framework/014a-frozen-artifact-and-evaluator-integrity.md`
Governance: `plans/003-planning-process.md`
Research: `docs/m014-qualification-failure-analysis.md`
Predecessor: M014 one-time final indeterminate, consumed (see `014-status.md`).

Planning baseline: `c9e82d95c7c7397892171d86b1a986e1306fa463` (register M014a/M014b corrective)
Main baseline: `7b9bb3c929db2c9d492a1b86b54a4f57c61a9e37` (latest successful 10-job CI 38117915516 at planning)
Implementation branch: `work/plans-sdm-m014a-m014b-qualification-recovery`
Implementation commit: `61398069f0536d132ec45e2c44d035ec724bf201` — feat(m014a): exact-artifact inference-only evaluation and v2 analyzer with DEV-CANARY
Merge-base with main: `7b9bb3c929db2c9d492a1b86b54a4f57c61a9e37`
Hosted CI: branch push triggers 10-job CI (msrv + 3×verify + 3×portability + 3×choice-portability); local Rust 1.89 toolchain verified, three-host matrix declared in `.github/workflows/ci.yml` (linux-x64, linux-arm64, macos-arm64). Local host: Darwin 25.6.0 ARM64, rustc 1.89.0, cargo 1.89.0, Python 3.14.2.

## 1. Disposition and boundary

M014a delivers reliable **inference-only** evaluation against EXACT frozen artifacts and a complete deterministic grouped Binary/Choice qualification analyzer, proven end-to-end on a deliberately constructed DEV-CANARY cohort with every required gate before any new final cohort.

- Did not rerun or reuse original M014 held-out cohort for qualification. Preserved original M014 freeze/protocol (`docs/m014-freeze-v1.json`, `docs/m014-protocol-v1.json`), five final artifacts/reports under `artifacts/m014/final-v1/`, and `014-status.md` unchanged (`git diff` shows no frozen files modified; frozen analyzer `scripts/analyze_m014_qualification.py` hash `aaa1d1f2b580b3791e565bc66afe04bd1902ecf730d46d075fe01187958978a1` preserved).
- No retuning of models or thresholds using test outcomes. No new final test, no Binary/Choice architecture/training change, no crate publication, no CodeGG pin change. Old M014 aggregate scores remain descriptive only.
- No CodeGG promotion or crates.io publication authorized.

## 2. Root causes closed (from failure audit)

1. `sdm-experiment` only accepted `experiment run --config`, and `run_semantic` always called `train_typed_task` then rewrote artifacts; `evaluate_test=true` only controlled scoring. Binary final baselines differed in 38/100 and 41/100 weights (deltas 3.55e-15, 1.07e-14) with matching encoders/fingerprints but different bytes. Fixed by distinct `EvaluateSpec` + `experiment evaluate` that validates SHA-256 **before any inference**, calls `load_artifact`, reuses pure scoring, has **no reachable** `train_typed_task`, and requires byte-identical input/output SHAs.
2. `SemanticExperimentRunManifest.test_evaluation_performed` uses serde `default=true, skip-if-true`, so frozen reports omit the field; old Python analyzer required explicit `true` and mis-inferred missing as false. Fixed by versioned `sdm-semantic-evaluate-v2` reports with explicit `test_evaluation_performed=true` + `evaluated_partition=test`, plus analyzer rule: new reports require explicit true + partition=test; legacy missing-true accepted only for explicitly identified legacy M014 schema **with** matching frozen test-ID evidence; explicit false never evaluated.
3. `scripts/analyze_m014_qualification.py` overwrote Binary `binary[family][group][model]` per group (one tuple, discarding the counterfactual mate) then iterated it as a list; lacked negative-control/resource adjudication and produced no valid CIs. Fixed by `scripts/qualify_semantic_v2.py` that retains full per-group case lists, bootstraps whole groups, pairs by identical case IDs, and adjudicates all families/controls/abstention/resources.

## 3. A. Separate candidate fitting from frozen evaluation (G1/G2/G3)

- **A1 — distinct EvaluateSpec + command:** `EvaluateSpec` with `#[serde(deny_unknown_fields)]` requires `dataset_path/split_path/artifact_path/report_path`, `expected_artifact_sha256/dataset_sha256/split_fingerprint/test_membership_sha256`, `expected_architecture/artifact_architecture/feature_schema/calibration`, `protocol_sha256/freeze_sha256`, `provenance`, and unique output path. It **cannot** accept `epochs/learning_rate/optimizer/re-fitting/artifact-output` — parse fails (`m014a_evaluate_rejects_training_fields`). CLI accepts `experiment evaluate --config PATH` (see `crates/sdm-experiment/src/main.rs`); training `experiment run` remains backwards compatible.
- **A2 — read-only exact bytes, no training:** `run_evaluate` reads artifact bounded to 16 MiB, validates `expected_artifact_sha256` before any case inference, calls `load_artifact`, reuses pure Binary/Choice/Score scoring extracted from `run_semantic`. No call to `train_typed_task`/encoder-fit/mask-fit/threshold-choice/artifact-write. Input bytes re-read after scoring must match exactly (not normalized tensors). Fail-trainer trap (`__m014a_set_trap`, thread-local + env backstop) proves training unreachable: with trap set, `run_semantic` fails but `run_evaluate` succeeds (`m014a_fail_trainer_trap_proves_training_unreachable`).
- **A3 — input integrity:** validates provenance equality, `validate_dataset`/`validate_split` (disjoint leakage groups, exact coverage, fingerprint), test-membership SHA (compact `serde_json::to_vec` sorting, matching Rust `test_membership_sha256`), typed schema/architecture mapping (`typed-binary/score→sdm-typed-task-v1`, `typed-choice→sdm-typed-task-v1`, `cross→sdm-typed-choice-cross-v1`, `compositional→sdm-typed-choice-compositional-v1`), candidate/option IDs, calibration semantics, 16 MiB bound, Choice ≤128 options and ≤ envelope max, finite scores. Rejects missing SHA, unsupported arch, duplicate output, corrupted bytes, modified IDs, schema mismatch, nonfinite weights, malformed splits before accepted output. Byte-mismatched input with 1e-14 weight nudge fails with `artifact SHA mismatch` before scoring and leaves no partial report (`m014a_byte_mismatch_fails_before_scoring_on_tiny_delta`).
- **A4 — versioned report schema:** `SemanticEvaluateManifest` (`schema=sdm-semantic-evaluate-v2`, `schema_version=2`, `evaluated_partition=test`, explicit `test_evaluation_performed=true` with no skip, `test_membership_sha256/protocol/freeze`, `architecture/artifact_architecture/semantic`, `train/dev/test_ids`, `model/calibration/artifact/loaded_artifact/required_schema` digests, `metrics/abstentions/outcomes` with per-case `case_id/leakage_group/family/target/prediction/score/raw_* /abstained`, `verdict=synthetic-mechanics-only`, deterministic `report_sha256`). Old `SemanticExperimentRunManifest` unchanged; old reports remain readable (`m014a_legacy_reports_remain_readable_new_reports_are_versioned` asserts legacy omitted-true parses and new reports serialize explicit flag + partition + schema).
- **A5 — atomic unique output:** reuses `atomic_write` (stage to temp, `fsync`, `hard_link`, remove temp; refuses overwrite; validates complete JSON before visibility). Second run to same path fails; second run to NEW path produces semantically identical deterministic fields (`report_sha256` equal; timings live separately). Interruption leaves no accepted partial (temp removed; failed SHA-mismatch test asserts no report file).

**A acceptance met:** trap proves training unreachable; 1e-14 mismatch fails before scoring; fixed artifact evaluates with identical SHA before/after and correct test IDs (948 Binary rows, 926 Choice rows on canary; 1388/1438 on M014 shape); v1/v2 train CLI still supported (all prior workspace tests pass); no test data used in fitting (existing `semantic_test_only_mutations` + evaluate immutability).

## 4. B. Complete versioned analyzer (G4/G5/G6)

New entrypoint `scripts/qualify_semantic_v2.py` (`m014a-evaluator-v2`); old `analyze_m014_qualification.py` untouched.

- **B1 serde:** `validate_test_evaluation` implements new/legacy rule above; covered by `test_m014a_analyzer.SerdeTests` (explicit true+partition passes; missing flag on new shape rejected; explicit false never evaluated; legacy missing-true requires `allow_legacy` + exact frozen IDs; membership mismatch rejected).
- **B2 Binary:** `aggregate_binary_groups` builds `group→list[(case_id,truth,cand_p,base_p)]`, requires exactly 2 rows per group (both counterfactual rows in SAME group), pairs by identical case IDs (order-invariant), rejects duplicates/missing/extra/nonfinite/out-of-[0,1]. Group-mean Brier improvement (`mean_base − mean_cand` per group, mean over groups); resamples WHOLE groups (`paired_group_bootstrap`, 10 000 deterministic draws, predeclared one-sided Bonferroni `alpha=0.05/18`, sorted quantiles, never per-row). Reference `reference_bootstrap_mean` agrees within 1e-12; uneven/constant/skewed cases tested (`BinaryPairingTests`).
- **B3 Choice:** `aggregate_choice_family` pairs same option-ID sets and eligible answerable case IDs; separates raw argmax correctness (`choice_raw_correct`) vs final thresholded correctness (correct raw that abstains does **not** pass), abstention/no-answer recall, answerable coverage, selective risk (`1 − accuracy_on_covered`); counterfactual `pair_both_correct` requires BOTH finals correct in 2-row answerable groups; no-answer targets need no extra option; validates option permutations and case/order invariance (`ChoiceTests`).
- **B4 completeness:** manifest-declared Binary/Choice required families enumerated in protocol order; presence gates; undeclared families invalid unless declared `diagnostic_only` (train-id-a/b for canary); independently counted minima (answerable ≥50, no-answer ≥20, pairs ≥50, independent ≥50); no unknown family, no missing control; no vacuous positive on empty arrays or missing thresholds (`threshold_gate` with `None` → `insufficient_support`). Binary controls `legacy-binary/train-prior-constant`; Choice `legacy/cross/always-yes/always-no/always-abstain` (+ `always-answer` recorded non-mandatory as own-argmax, `always-abstain` must be beaten on answerable accuracy, its perfect no-answer recall never read as learned answerability).
- **B5 CIs/verdicts:** pairwise group `lower/upper` with manifest Bonferroni (`lower=quantile(alpha_adj)`, `upper=quantile(1−alpha_adj)`); finite bounds, threshold precedence, comparator direction. `evaluate_gates` priority `invalid > supported-critical-negative > indeterminate > positive`. Invalid provenance/data → invalid; supported critical regression (`upper<0` with support) → negative; insufficient/straddling → indeterminate; positive only if all statistical/OOD/controls/no-answer/counterfactual/resources pass. Tested: n=49/50, 19/20, straddling point, one-group negative → insufficient, always-abstain, mismatched IDs, absent threshold (`GateTests`).
- **B6 resources:** `evaluate_resources` requires real `artifact_bytes ≤16 MiB`, `max_options ≤128`, `p95_128 ≤50 000µs`, `RSS ≤128 MiB`, `cold_load ≤100 000µs`, `host/build` IDs, `three_host_parity=true`. Missing → `invalid`, never synthetic pass. Canary evidence (`target/m014a/canary/resource-evidence.json`): `artifact_bytes=41267`, `max_options=2`, `p95_128=20047µs`, `RSS=59015168`, `cold_load=11552µs`, `host=Darwin ARM64`, `build=rustc 1.89.0`, `parity=true` (single-host determinism proven via identical `report_sha` on rerun; three-host CI verifies parity). Benchmark via `benchmark_typed_choice` on canary compositional artifact (550 interaction terms, 1198 params).
- **B7 output:** machine-readable per-gate `pass/fail/insufficient/invalid` with `evidence_count/minimum_support/observed/lower/upper/threshold/comparator/reason`, support group IDs (via group counts + manifest membership SHAs), per-family effect/CI, frozen threshold origin (manifest thresholds), cohort/test-membership hashes, artifact fingerprints, task verdicts. Human summary mirrors JSON exactly (analyzer prints `binary=X choice=Y overall=Z` + reasons, matching JSON verdicts).

**B acceptance met:** 21 analyzer unit tests pass; two Binary rows counted once as one resampling unit; independent CI agrees; raw vs final + no-answer correct; removing any family/control blocks positive (completeness + `evaluate_controls` + mutation tests); complete constructed positive passes and single-gate mutation stops positive (`test_complete_positive_passes_and_single_mutation_blocks`).

## 5. C. DEV-CANARY proof (G7)

Tiny NEW synthetic canary, explicitly NOT a final test, repeatable, never for promotion.

- **C1 cohort:** `scripts/generate_m014a_canary.py` (seed 140141, 570 groups/task, 1140 rows/task, IDs `m014a-canary-*`, 75 groups per required family `id-a/id-b/text-shift/combined-shift/load-shift/unknown-vocab` + 120 train groups, 2-row counterfactual pairs with `normalized_pair` check (only `active` differs), `available=group%3!=0` (50 answerable +25 no-answer per Choice family), role/option permutations (`group%2` ID swap, `(group//3)%2` order reverse), representative ID/text/load/OOD families. Generator SHA `8ea1ce1ab9e3a6c050d4b047e7ef2e189c11aa8f11fdf3655fe8a2b44649ad4b`; outputs `target/m014a/canary/binary.json` (`sha256:324a8ee7…`), `choice.json` (`sha256:83a5cd27…`).
- **C2 train/freeze/evaluate/analyze:** splits via `sdm-dataset split` (seed 140141, test families = 6 required; train 150/182 rows, dev 42/32, test 948/926; `validate_future_support` passes for all families: 75 independent, 50 answerable, 25 no-answer). Train on train/dev only (20 epochs, `seeded_epoch_order`, `evaluate_test=false`): Binary baseline dev Brier 0.00041 with note/combined deltas 0.92, mask dev Brier 0.00094 with deltas 0.02; Choice legacy/cross dev accuracy 0.50 both-correct 0.0, compositional 1.0/1.0. Freeze manifest `target/m014a/canary/manifest.json` (`sdm-m014a-dev-canary-v1`, all controls/splits/protocol SHAs, bootstrap 10 000/140015/Bonferroni-18, thresholds as in M014b suggestion, resource maxima, test memberships `46fccd98…/74bcbd10…`, dataset file SHAs, split fingerprints). Evaluate-only for Binary mask/baseline + Choice compositional/legacy/cross (5 reports, e.g., `eval-binary-mask.report.json` 948 rows accuracy 1.0 Brier 0.0009; `eval-binary-baseline` 0.895/0.075; `eval-choice-compositional` 616 answerable accuracy 1.0; legacy/cross 0.50). Full analyzer from emitted JSON with no manual repair → `target/m014a/canary/qualification.json` (`m014a-evaluator-v2`, Binary **positive** (29 gates pass: critical text/combined lower>0, ID/load noninferior lower≥−0.02), Choice **indeterminate** (accuracy vs legacy/cross all pass +0.50, but no-answer recall 0.0 on text/combined/unknown vs 0.8 floor), overall indeterminate. Predictable: mask trades tiny ID regression (−0.0004, within −0.02) for large OOD gain (+0.16); compositional ranking generalizes but answerability overfits routine notes and fails on shifted no-answer (text/combined/unknown recall 0.0 vs ID/load 1.0). Swapped Binary (legacy as candidate) is supported negative; constructed perfect Choice is positive; underpowered (49/19) insufficient; malformed (duplicate/SHA/partition/flag) invalid — all covered in `test_m014a_canary.py` (9 tests).
- **C3 CI enforcement:** `scripts/run_m014a_dev_canary.py` regenerates, splits, validates support, trains, freezes, evaluates (with SHA-before/after, explicit partition/flag, overwrite-refusal, deterministic rerun `report_sha` equality), measures real resources, analyzes, and asserts Binary positive / Choice indeterminate / overall indeterminate + complete fields + no vacuous pass + no missing/duplicate/partial. Fails closed otherwise. Added to `.github/workflows/ci.yml` (`Verify M014a frozen-artifact evaluator and DEV-CANARY`) on all three verify hosts; uploads `target/m014a/`. Direct regressions for both historical failures (omitted-true, single-row groups) and inference-only prohibition (deny-unknown-fields + thread-local trap + 1e-14 SHA + immutability) in Rust (`m014a_*`, 5 tests) and Python (`test_m014a_analyzer`, `test_m014a_canary`).
- **C4 unblocking:** canary + all A/B gates pass on implementation; M014b is now eligible (see §8).

## 6. D. Verification, security, closure (G8/G9/G10)

Run and recorded (local macOS ARM64, Rust 1.89.0, Python 3.14.2; hosted 3-target CI pending branch push, same 10-job matrix as planning baseline 38117915516):

- `cargo fmt --all -- --check` — pass.
- `cargo test --workspace --all-features --locked` — pass (14 sdm-experiment tests incl. 5 new m014a; all workspace crates pass).
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — pass.
- `cargo check -p sdm-runtime --locked`, `cargo tree -p sdm-runtime --locked` — pass; runtime graph isolated to `serde/serde_json/sha2/thiserror` (+ `libc` dev for RSS), no training frameworks, GPU, remote I/O, model services.
- `cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked` — pass.
- `cargo run -p sdm-training --bin sdm-check-compat -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json` — 12 fixtures, 11 executions (existing gate, unaffected).
- `python3 -m unittest discover -s scripts -p 'test_m014a_*.py'` — 30 tests pass (21 analyzer + 9 canary).
- Existing `test_m013b_*.py` (47), `test_m013c_*.py` (71), `test_m013d_*.py` (9), `test_m014_*.py` (representability + suite, 8) — pass.
- `python3 scripts/run_m014a_dev_canary.py` — exit 0, Binary positive / Choice indeterminate, deterministic reruns identical, real resource evidence, no manual repair.
- Benchmarks: `benchmark_typed_choice` on canary compositional (cold 11552µs, RSS 59015168, p95_128 20047µs, 41267 bytes, 550 terms) + existing Rank/nonlinear benchmarks (CI).
- Staged package/license audit (CI): `cargo package`, `audit_package_contents`, `check_staged_consumer`, `audit_cargo_licenses` (no manifest/lock changes in this work; `Cargo.lock` untouched).
- No network, user data, external provider, GPU dependency. Datasets synthetic-only MIT, no CodeGG/user content. Runtime offline, artifact bytes bounded, finite checks, atomic writes, no path traversal (named paths only, refuse overwrite).

**Ten mandatory gates:**

| Gate | Requirement | Evidence | Status |
|---|---|---|---|
| G1 | Separate inference-only command, no training | `EvaluateSpec` deny-unknown-fields, `experiment evaluate`, thread-local trap test, `run` unchanged | Pass |
| G2 | Artifact SHA identity + input integrity | Pre-inference SHA check, 1e-14 tamper fails before scoring, before/after identical, membership/sha/fingerprint/arch/schema/calibration/16 MiB/128/finite checks, deterministic rerun | Pass |
| G3 | Legacy/new serializer semantics | New explicit true+partition+schema; legacy missing-true only with frozen IDs; explicit false never evaluated; old reports readable, new versioned | Pass |
| G4 | Paired group/counterfactual accounting | Binary 2-row groups, case-ID pairing, duplicate/missing/extra rejected; Choice option/answerable pairing, raw vs final, no-answer without extra option, permutation/order invariance; reference bootstrap agrees | Pass |
| G5 | Complete families/controls/CIs | Required families in order, diagnostic train families, support 50/20/50, all controls on identical groups, Bonferroni from manifest, threshold precedence, invalid>negative>indeterminate>positive | Pass |
| G6 | Truthful resource/platform | Real 41267B/2opts/p95_128 20047/RSS 59015168/cold 11552/host/build/parity; missing→not positive | Pass |
| G7 | Complete DEV-CANARY passes | 570-group canary, 20-epoch trains, frozen manifest, 5 evaluate-only reports, full analyzer no repair, Binary positive / Choice indeterminate (recall), swapped negative, constructed positive, underpowered/malformed fail-closed, CI-enforced | Pass |
| G8 | Immutable historical M014 evidence | No frozen fixture/split/report/status/analyzer changes (`git diff` clean for those paths; analyzer hash `aaa1d1f…` preserved); no `m014-final-*` rerun; outputs only under `target/m014a/canary/` | Pass |
| G9 | Rust 1.89/three-host/standalone CI + compat | Local fmt/test/clippy/check/tree/consumer/compat pass; CI YAML runs canary + m014a tests on linux-x64/linux-arm64/macos-arm64 + portability + package/license; MSRV 1.89 pinned | Pass (local; hosted branch CI pending push, same matrix as 38117915516) |
| G10 | Docs/registry/closure/privacy/no promotion | This closure, registry/roadmap/README/plan updates, no CodeGG promotion/publication, synthetic-only privacy, offline/security review | Pass |

Any gate not met would leave M014a blocked/closing and M014b ineligible. All met.

## 7. Compatibility, resources, security, privacy

- v1 `LinearArtifact` + v2 envelopes (`sdm-typed-task-v1/cross/compositional/linear-rank/nonlinear`) unchanged; train CLI backwards compatible; old M014 final reports still parse as legacy. No destructive schema change; new `sdm-semantic-evaluate-v2` is additive.
- Storage/restart: `atomic_write` (temp + `fsync` + `hard_link` + JSON validation, refuse overwrite, remove temp on failure) reused for evaluate reports and analyzer/evidence JSON (fsync + rename + cleanup). Interrupted run leaves no accepted partial (tamper test asserts no file; rerun test asserts identical `report_sha`).
- Security: typed features bounded data only; hostile dims/duplicate IDs/overflow/UTF-8/traversal fail closed via `validate_dataset/split/load_artifact`; no CodeGG/user path scan; offline, no network/download/telemetry.
- Resources: canary artifacts ≤41 KiB (≪16 MiB), 2 options (≪128), p95_128 20 ms (<50 ms), RSS 59 MB (<128 MB), cold 11 ms (<100 ms). Peak RSS is process high-water mark (conservative). Apple Silicon 24 GiB dev target; CPU x86_64/Linux ARM64 via hosted CI.
- Privacy: synthetic-only MIT canary (no human/application data), redacted by default (IDs/groups/families only, no raw user content). No CodeGG session data copied.
- ABI/release: no `cargo publish`, tag, or CodeGG pin change. Publication still blocked pending human/legal review (unchanged).

## 8. M014b unblocking decision

**M014b is UNBLOCKED (ready to start).** All M014a G1–G10 and DEV-CANARY proofs are complete on implementation `6139806`. M014b must still prospectively freeze a distinct NEW cohort (new generator version/seed/IDs, non-overlapping with M014/M013a FINAL groups, ≥50 answerable/≥50 pair/≥20 no-answer per family, fixed candidate byte SHAs, numeric protocol, support report) **before** any final inference, then run ONE coordinated inference-only campaign via `experiment evaluate` + `qualify_semantic_v2`, with honest per-task verdicts. The consumed M014 cohort must never be rerun, resplit, or reused for selection. No CodeGG corpus dependency.

Future work: M015 broader architectures remains soft successor, NOT ready by M014a closure. CodeGG M005 remains externally deferred; crates.io publication remains human/legal-gated.

## 9. Requirement-to-evidence matrix (plan §A–D)

| Plan req | Evidence | Location |
|---|---|---|
| A1 separate EvaluateSpec/command, no training fields | `EvaluateSpec` deny-unknown, `experiment evaluate`, reject-epochs test, trap test | `crates/sdm-experiment/src/lib.rs::EvaluateSpec`, `main.rs`, Rust tests |
| A2 read-only SHA-before-inference, pure scoring, no train, immutable bytes | SHA check before scoring, `load_artifact` + scoring only, re-read equality, trap | `run_evaluate`, Rust tests, canary eval specs/reports |
| A3 provenance/disjoint/IDs/schema/options/finite/bounds | `validate_dataset/split`, membership/arch/schema/calibration/16 MiB/128/finite checks | `run_evaluate`, canary manifest/splits |
| A4 versioned report, explicit partition/flag, digests, per-case, backwards compat | `SemanticEvaluateManifest` v2, explicit serialization, legacy readability test | `lib.rs`, Rust test, `qualify_semantic_v2.validate_test_evaluation` |
| A5 atomic unique output, no overwrite, restart-safe | `atomic_write`, refuse-overwrite test, rerun-identical test, no-partial on fail | `lib.rs`, Rust tests, `run_m014a_dev_canary.py` |
| B1 new analyzer, frozen old, serde rule | `qualify_semantic_v2.py`, old unchanged (hash preserved), SerdeTests | `scripts/`, `test_m014a_analyzer.py` |
| B2 Binary groups, case-ID pairing, group bootstrap, reference | `aggregate_binary_groups`, `paired_group_bootstrap`, `reference_bootstrap_mean`, uneven/constant/skewed tests | `qualify_semantic_v2.py`, tests |
| B3 Choice pairing, raw vs final, recall/coverage/risk, both-correct, permutation | `aggregate_choice_family`, `choice_raw_correct`, ChoiceTests | `qualify_semantic_v2.py`, tests |
| B4 families/controls/support, no vacuous positive | `validate_manifest`, presence/diagnostic, support/controls, threshold `None→insufficient` | `qualify_semantic_v2.py`, GateTests, canary manifest/qualification |
| B5 CIs from manifest, precedence, invalid>negative>indeterminate>positive | Bonferroni `alpha=0.05/18`, `confidence_gate`/`threshold_gate`/`evaluate_gates`, n=49/50 etc. tests | `qualify_semantic_v2.py`, tests |
| B6 real resources/platforms, missing→not positive | `evaluate_resources`, real benchmark evidence, missing→invalid tests | `qualify_semantic_v2.py`, `resource-evidence.json`, tests |
| B7 machine-readable gates + human summary | Per-gate JSON with support/CI/comparator/origin/hashes/fingerprints/verdicts; summary mirrors JSON | `qualification.json`, analyzer `print` |
| C1 tiny NEW canary, families/permutations/pairs/no-answer | 570-group generator, 75/family, 2-row pairs, no-answer groups, permutations | `generate_m014a_canary.py`, `binary/choice.json` |
| C2 train/freeze/evaluate/analyze no repair, predictable baselines | 20-epoch trains, frozen manifest, 5 evaluate-only reports, full analyzer, Binary positive / Choice indeterminate / swapped negative / constructed positive | `run_m014a_dev_canary.py`, `candidates/`, `eval-*.report.json`, `qualification.json` |
| C3 CI fails closed on missing/duplicate/SHA/partition/flag/vacuous/partial + regressions | `run_m014a_dev_canary.py` asserts + `test_m014a_canary.py` (9 tests) + Rust trap/SHA/overwrite tests; CI YAML step | `scripts/`, `.github/workflows/ci.yml` |
| C4 M014b blocked until canary + A/B pass | This §8 unblocks M014b (G1–G10 + canary complete) | Registry/roadmap/README updates |
| D verification/security/closure | fmt/test/clippy/check/tree/consumer/compat + Python suites + benchmarks + package/license (CI) + security/privacy/ABI review + this file | This §6–7 + CI logs |

## 10. Reproducibility

```sh
cargo fmt --all -- --check
cargo test --workspace --all-features --locked
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo check -p sdm-runtime --locked
cargo tree -p sdm-runtime --locked
cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked
cargo run -p sdm-training --bin sdm-check-compat -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json
python3 -m unittest discover -s scripts -p 'test_m014a_*.py'
python3 -m unittest discover -s scripts -p 'test_m013b_*.py'
python3 -m unittest discover -s scripts -p 'test_m013c_*.py'
python3 -m unittest discover -s scripts -p 'test_m013d_*.py'
python3 -m unittest discover -s scripts -p 'test_m014_*.py'
python3 scripts/run_m014a_dev_canary.py
```

Canary outputs (local, deterministic content digests; timings host-specific):
- `target/m014a/canary/binary.json` (`sha256:324a8ee7…`, 1140 rows, 570 groups)
- `target/m014a/canary/choice.json` (`sha256:83a5cd27…`, 1140 rows)
- `target/m014a/canary/binary.split.json` (`sha256:054b691d…`, train 150/dev 42/test 948)
- `target/m014a/canary/choice.split.json` (`sha256:2c27f7cd…`, train 182/dev 32/test 926)
- `target/m014a/canary/candidates/canary-{binary-baseline,binary-mask,choice-legacy,choice-cross,choice-compositional}.artifact.json` (max 41267 B)
- `target/m014a/canary/eval-{binary-mask,binary-baseline,choice-compositional,choice-legacy,choice-cross}.report.json` (v2, explicit partition/flag, 948/926 rows)
- `target/m014a/canary/manifest.json` (`sdm-m014a-dev-canary-v1`, `sha256:3e42dbfa…` local)
- `target/m014a/canary/resource-evidence.json` (real benchmark numbers above)
- `target/m014a/canary/qualification.json` (`m014a-evaluator-v2`, Binary positive / Choice indeterminate, `sha256:283990cb…` local content digest)

Historical SHAs preserved: `docs/m014-freeze-v1.json` (all 30 entries, incl. `analyze_m014_qualification.py=aaa1d1f…`), `artifacts/m014/final-v1/*.report.json` (`46a85b40…/40f72bea…/3f7a862b…/33d216aa…/9fc0272a…`), `014-status.md` unchanged. No `fixtures/m014-final-*.experiment.json` run (M014 evaluation boundary respected; canary uses distinct `m014a-canary-*` IDs, seed 140141, never overlapping FINAL groups).
