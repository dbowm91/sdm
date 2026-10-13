# M014c — Qualification Closure, CI and Evidence Reconciliation

Status: **closed — FULL integration closure (C1–C12 pass; merged-main CI green)** — no model promotion, no final rerun.
Plan: `plans/implementation/general-decision-model-framework/014c-closure-evidence-reconciliation.md`
Governance: `plans/003-planning-process.md`, ADR-0001/0002, M014a/M014b plans and closure records
Planning audit: `docs/m014c-closure-audit.md`
Evidence ledger: `docs/m014c-evidence-ledger.json`
Implementation branch: `work/plans-sdm-m014c-closure-evidence-reconciliation`
Main at planning: `7b9bb3c929db2c9d492a1b86b54a4f57c61a9e37`

## 1. Source identity (exact SHAs)

- Planning baseline (M014a/b source): `c27724746ebc674919aff32a93d6baf74e104e13` on `work/plans-sdm-m014a-m014b-qualification-recovery`
- Planning registration: `7c0990a498d52f8a574e89537de88a81ee006a4c` (docs(plans): register M014c)
- M014a implementation: `61398069f0536d132ec45e2c44d035ec724bf201`
- M014a closure: `08ed483cdf2f1218d979741350fc4f5b48d639c0`
- M014b freeze (prospective, before final): `9cc80f0fc228e3a5f910723fa9420465f5cbeb30`
- M014b observation/closure: `c27724746ebc674919aff32a93d6baf74e104e13`
- M014c implementation (code): `af74c01e3c26a502f31d64d268f69166d9ac1be2` — feat(m014c): ordered CI, measured parity attestation, lineage validator, evidence ledger
- M014c parity fix: `d60d9c0bd07b4dbe525d9f167720095bb88cfd10` — fix(m014c): parity uses SAME committed bytes on all hosts (retraining diverges)
- M014c closure (this file + registry/docs): _this commit_ (see `git log` for exact SHA; branch HEAD at push)
- Hosted green: [38418968150](https://github.com/dbowm91/sdm/actions/runs/38418968150) at `d60d9c0bd07b4dbe525d9f167720095bb88cfd10`: SUCCESS 11/11 (msrv + 3 verify + 3 portability + 3 choice-portability + canary-parity); see §7.
- Integration PR: [#3](https://github.com/dbowm91/sdm/pull/3) (M014a–M014c stack, `7b9bb3c..3d8db08`) — OPEN/MERGEABLE at review, PR run [38422712418](https://github.com/dbowm91/sdm/actions/runs/38422712418) SUCCESS 11/11 on `3d8db08`; branch run [38421173295](https://github.com/dbowm91/sdm/actions/runs/38421173295) SUCCESS 11/11 on `3d8db08`.
- Merge: `91b0c3ba2f576f4967729d9c2b52355784bcc9b5` (Merge PR #3 into main).
- Merged-main CI: [38424519807](https://github.com/dbowm91/sdm/actions/runs/38424519807) SUCCESS 11/11 on merge; no publish/pin/model promotion.
- Merge-base with main: `7b9bb3c929db2c9d492a1b86b54a4f57c61a9e37` (main unchanged at baseline; no main push, no auto-merge)
- Freeze manifest `docs/m014b-freeze-v1.json` SHA-256: `sha256:859f2f42716c0a8d997530ac5554aefa2f4aec5a81388a2790ec8d3fa5bfd743` (identical at `9cc80f0` and `c277247`; no rewrite)
- Five final configs SHA-256 (at freeze and now, unchanged):
  - `fixtures/m014b-final-binary-baseline.evaluate.json`: `sha256:611555e489c45bfb0585dd6bf6e41b3c8e7b525c9cdae9ca0d4a9f4abf835cc4`
  - `fixtures/m014b-final-binary-mask.evaluate.json`: `sha256:7d9f82dd65a6b419fda936f6cdffddf06e79ff02683e232eaf62b68b5c76f7f0`
  - `fixtures/m014b-final-choice-legacy.evaluate.json`: `sha256:09f183a44e216f1d0caca48f1bc5e0598a90230613b95ff18d8b4e9773c3ac61`
  - `fixtures/m014b-final-choice-cross.evaluate.json`: `sha256:2c38d6068ed044749dc6cecdf434c90192ee3dcdc37a8a5b371618d69e774eef`
  - `fixtures/m014b-final-choice-compositional.evaluate.json`: `sha256:2782677d50c60677c8dfbc1fc5d8dda02dfa2ecf340ffeff0a569fec133de678`
- Each final config embeds `freeze_sha256 = sha256:1111111111111111111111111111111111111111111111111111111111111111` (64 literal `1` digits) — recorded as `placeholder_unbound` defect, never passed.

## 2. Old hosted evidence (retained, not described as pass)

- Run [38408167153](https://github.com/dbowm91/sdm/actions/runs/38408167153) at source `c27724746ebc674919aff32a93d6baf74e104e13`: COMPLETED FAILURE.
  - `linux-x64` verify FAILED at `Verify M014a frozen-artifact evaluator and DEV-CANARY`: `python3 -m unittest discover -s scripts -p 'test_m014a_*.py'` ran BEFORE `python3 scripts/run_m014a_dev_canary.py`. Hosted clean workspace lacks `target/m014a/canary/manifest.json`, qualification and evaluate reports → 1 failure + 4 errors out of 30 (reproduced locally §3).
  - `linux-arm64` and `macos-arm64` verification CANCELLED after matrix failure (not passed, not skipped-as-pass).
  - Rank and Choice portability SKIPPED (not passed).
  - MSRV job SUCCEEDED (only passing job; does not qualify implementation).
  - Prior successful plan-only run `38399878048` is NOT implementation evidence.
- Local reproduction (clean checkout, `target/m014a/canary/` absent):
  - `test_m014a_analyzer.py`: 21 passed (pure, no canary dependency).
  - `test_m014a_canary.py`: 1 failure + 4 errors / 9 (missing `manifest.json`; `FileNotFoundError` on canary paths) — exact 5 failing tests from hosted run.
  - Proves the five failing tests depend on generated canary files; cancelled jobs are not passes.

## 3. Work A — Portable CI ordering and failure isolation (C1, C2, C10)

- Refactored `.github/workflows/ci.yml` (all three verify hosts, enforced order):
  1. `Verify M014 representability proof (pure, no canary artifacts)`: explicit `test_m014_representability.py` + `test_m014_suite.py` + `test_m014a_analyzer.py` (21 pure; never the broad `test_m014_*.py` wildcard which also matches dependent canary tests).
  2. `Generate M014a DEV-CANARY (provision artifacts before dependent tests)`: `run_m014a_dev_canary.py` (deterministic; fails job before dependent tests on any error); asserts `qualification.json` Binary positive / Choice indeterminate / overall indeterminate; logs per-host manifest/report/qualification SHAs, source HEAD and toolchain to distinguish source-test vs workload failure.
  3. `Verify M014a artifact-backed canary tests (requires generated canary)`: `test_m014a_canary.py` (9 tests) only after provisioning.
  4. `Enforce M014a CI ordering (regression)`: `scripts/check_m014a_ci_order.py` — parses `ci.yml` as text (comment-stripped), requires pure < gen < dependent, rejects `test_m014a_*.py` or `test_m014_*.py` wildcards before provisioning. Fails future reordering that would reproduce 38408167153.
  5. `Verify M014c lineage (read-only, no final rerun)` + `Generate M014c parity evaluations (SAME committed bytes)` + `Generate M014c per-host canary attestation --parity` (see §4).
- Clean-checkout verification (local, Darwin ARM64, Rust 1.89.0, Python 3.14):
  - Absent `target/m014a/canary/`: pure 21 pass, dependent 5 fail (above); then `run_m014a_dev_canary.py` exit 0 from clean, Binary positive / Choice indeterminate, deterministic rerun `report_sha` identical.
  - Present `target/m014a/canary/`: rerun exit 0 with identical machine-readable verdicts; no stale-file false positives.
  - Canary runner regenerates safely and only deletes its own `target/m014a/canary/*` (candidates, eval specs/reports, manifest, qualification, resource-evidence); NEVER touches `target/m014b/final/`, `target/m014/final/` or any M014 paths (verified by source inspection + `git status` shows no frozen modifications; `target/m014b/final/` mtimes/SHAs unchanged).
- Old M011/M013a/b/c/d/M014 frozen guards continue: `test_m013b_*` 47 pass, `test_m013c_*` 71 pass, `test_m013d_*` 9 pass (2 skipped host-specific), `test_m014_representability` 3 pass, `test_m014_suite` 5 pass, `cargo fmt/test/clippy/check/tree/consumer/compat` pass (see §7).

## 4. Work B — Real cross-host parity (C3, C4)

- Defect closed: `run_m014a_dev_canary.py` previously wrote `"three_host_parity": true` as a literal and `qualify_semantic_v2.evaluate_resources` trusted it. A single-host rerun is NOT portability. Now writes `"three_host_parity": false` with note `UNVERIFIED single-host (M014c B4) — real parity requires downstream three-host attestation aggregation, never a single-host literal`. Analyzer remains fail-closed (missing/false parity → `fail`/`invalid`, never synthetic pass). Canary qualification stays Binary positive / Choice indeterminate (provisional indeterminate due to unverified parity is correct; Binary unaffected as resources gate only Choice).
- New `scripts/m014c_canary_attestation.py` (`--parity` mode for CI): each host evaluates SAME committed `artifacts/m014/*` bytes on canary data (via `m014c_parity_evaluate.py`), exports bounded per-case `case_id`, family, leakage_group, target, prediction, abstained, architecture, artifact SHA, plus dataset/split/test-membership SHAs, report SHAs, source commit, host/build metadata and integrity `attestation_sha256`. Covers Binary (948 cases) and compositional Choice (926 cases) plus legacy/cross compact decisions. No raw feature text or user data. Default (non-parity) mode attests canary-trained reports for single-host determinism ONLY.
  - Finding that forced the fix: canary-retrained Choice bytes are NOT bit-identical across OSes (run 38413896571: linux-x64 and linux-arm64 agree — e.g. compositional `a271622c…` — but macos-arm64 differs — `5acb2c7e…`; binary retraining IS identical across all three). Comparing retrained floats is NOT same-artifact parity (plan B2); the aggregator correctly FAILED with `parity artifact bytes differ (3 artifacts)`, 0 decision divergences. Fixed by parity evaluations on committed bytes (`d60d9c0`).
  - Parity artifact SHAs are committed bytes, identical on all hosts (e.g. compositional `e77d44a0…`, cross `ba17c929…`, legacy `e512cb53…`, mask `19c2a340…`, baseline `3d3c1a14…`); aggregator verifies these plus committed SHAs before comparing decisions.
- New `scripts/verify_m014c_parity.py` aggregator + new `canary-parity` CI job (needs `verify`, runs on `ubuntu-24.04`) + `scripts/m014c_parity_evaluate.py` (5 committed-artifact parity reports under `target/m014a/canary/parity-*`, never FINAL paths):
  - Downloads three `canary-attestation-{linux-x64,linux-arm64,macos-arm64}` artifacts; requires exactly three with platforms `{linux-x86_64,linux-aarch64,macos-aarch64}` (missing/duplicate blocks pass); verifies identical `source_commit`, test-membership/dataset/split SHAs, manifest/evaluator SHAs and case-set equality; requires parity + committed artifact SHAs identical; flags artifact divergence separately.
  - Compares actual decisions by fixed `case_id`: `prediction` and `abstained` must match exactly; numerical probability deltas recorded separately (`prob_tolerance 1e-9`) but NEVER allow changed action to pass under tolerance. Host timings/RSS labeled host-specific, never compared.
  - Local: 3-label simulation on identical bytes → `verdict pass` (948+926 cases); single input → `fail (requires exactly three)`; mutated prediction → `fail` with minimal reproducible difference.
  - Hosted (run 38418968150): `verdict pass` — `same-artifact decisions agree across ['linux-aarch64','linux-x86_64','macos-aarch64'] (948 binary + 926 choice cases)`, 0 decision divergences, `max_probability_delta 8.673617379884035e-19` (f64 noise, recorded separately, no action change).
  - A single-host JSON can never satisfy parity (aggregator requires 3); same-artifact agreement or explicit divergence is the only pass/fail.
- Scope (B5): parity proof covers DEV-CANARY and committed/frozen artifacts via current runtime verification ONLY; never reprocesses M014b exposed FINAL cohort. It is NOT proof of historical M014b FINAL case-by-case cross-host parity (stated explicitly; historic parity remains unverified).

## 5. Work C — Immutable freeze identity (C5, C6)

- Original bytes unchanged in PR diff: `git diff 9cc80f0 HEAD -- docs/m014b-freeze-v1.json docs/m014b-protocol-v1.json fixtures/m014b-final-*.evaluate.json fixtures/m014b-*.split.json scripts/generate_m014b_suite.py scripts/qualify_semantic_v2.py` is empty (no rewrite). `git diff` for M013a/M014 freeze/protocol/reports/status/analyzer likewise clean.
- New read-only `scripts/verify_m014c_lineage.py` (`--freeze-commit 9cc80f0… --observed-commit c277247… --out target/m014c/lineage-verdict.json`):
  - Verifies generator `5167a16d…`, protocol `3cea1831…`, evaluator `7b91dda8…`, five candidate byte SHAs, two split file SHAs and five final-config SHAs match `docs/m014b-freeze-v1.json`.
  - Flags each final config's `freeze_sha256 == sha256:111…1` as `placeholder_unbound` defect, never passed; verifies `protocol_sha256` in same specs DOES match freeze (valid binding).
  - Validates `git merge-base --is-ancestor 9cc80f0 c277247` (ancestry, not author times); verifies `git show 9cc80f0:<path>` SHA-256 equals current file for freeze manifest, protocol, generator, splits and final configs (no post-freeze rewrite); differentiates Git blob SHA-1 (`git hash-object`/`ls-tree`) from SHA-256 file bytes in output.
  - Performs no writes to freeze/outputs or `target/m014b/final/` (out only under `target/m014c/`; refuses historical paths); contains no `experiment evaluate` / inference call and no historical write (verified by inspection).
  - Local: `verified_with_known_defect` (freeze `9cc80f0`, observed `c277247`, placeholder defect); one-byte corruption of `fixtures/m014b-final-binary-mask.evaluate.json` → `fail: SHA mismatch …` exit 2; restored file → pass.
- Scope/severity recorded in attestation: offline lineage proves which files were committed before local claims, not when uncommitted scores were first observed; hosted CI before observation is NOT verified (implementation CI absent/failed after final); no backdating. Future wholly prospective experiments MUST use a two-phase/non-self-referential freeze-binding contract (core freeze digest sealed before EvaluateSpecs; config binds to core digest; sealed bundle hashed) — required, not implemented here; current M014b hash-cycle cannot claim embedded linkage from 64 hex digits.

## 6. Work D — Historical report evidence (C7, C8)

- Original bytes recovered locally (ignored `target/m014b/final/`, never uploaded, never rerun). Machine-readable ledger `docs/m014c-evidence-ledger.json` grounds every digest to original bytes (file SHA-256 + inner `report_sha256` + size/mtime/host) or marks `unavailable` (none missing locally; future loss must be marked, never regenerated):
  - `binary-baseline.report.json`: file `722d799b…`, 331044 B, 2026-10-13T13:45:15Z, inner `7d11ac57…`, 924 rows, artifact `3d3c1a14…`
  - `binary-mask.report.json`: file `0983660f…`, 333868 B, 13:45:16Z, inner `1047eba8…`, 924 rows, artifact `19c2a340…`
  - `choice-legacy.report.json`: file `4495f922…`, 492325 B, 13:45:19Z, inner `330b7d0f…`, 926 rows, artifact `e512cb53…`
  - `choice-cross.report.json`: file `84bf41b5…`, 490406 B, 13:45:21Z, inner `9872b6d2…`, 926 rows, artifact `ba17c929…`
  - `choice-compositional.report.json`: file `85cf7058…`, 491746 B, 13:45:24Z, inner `62d75903…`, 926 rows, artifact `e77d44a0…`
  - `qualification.json`: file `93eb9978…`, 74722 B, 13:46:19Z, Binary negative / Choice negative / overall negative, evaluator `7b91dda8…`
  - `manifest.json`: file `f783ee7e…`, 3470 B; `resource-evidence.json`: file `07d83f83…`, 564 B (single-host `three_host_parity:true` assertion superseded per §4; real numbers 45529 B/2 opts/p95_128 17552/RSS 59277312/cold 7704/Darwin ARM64/rustc 1.89.0 preserved as host-specific).
  - How obtained: local original host bytes; chain of custody stated; no trusted CI artifact with authoritative SHAs exists (outputs ignored/uncommitted); no guessed digits.
- Read-only verification (no inference): each report parsed, `evaluated_partition=test` + explicit `true` + `sdm-semantic-evaluate-v2` + `artifact_sha == loaded_artifact_sha` + test-membership/protocol SHAs match freeze + case counts match splits. No new gate adjudication over old FINAL for promotion; new evaluation for promotion is NOT performed.
- Historic outcome retained as historic local observation (not overwritten, cohort never rerun/retuned): Binary negative (`brier_improvement_vs_prior::m014b-binary-text-shift-v1 [-0.4018,-0.0962]`, 75≥50), Choice negative (`accuracy_vs_legacy::m014b-choice-text-shift-v1 [-0.5,-0.5]`, 50≥50), overall negative. Design meaning: M014b intentionally changed the TRUE rule (Binary `(active AND available) XOR rule_b` vs M014 AND-only; Choice XNOR `active==rule_b` vs M014 XOR), not mere nuisance — negative establishes fixed-model inability to transfer under changed conditional rule; does NOT refute capacity to learn old rule nor ordinary OOD robustness; MUST NOT be used to select a model for M015.
- Append-only erratum `2026-10-13` in ledger (original `014a-status.md`/`014b-status.md` statements kept intact as historical claims): hosted Q8/G9 was FAILED not green; `three_host_parity=true` was single-host literal not measurement; final SHAs were `to be recorded`/ambiguous not complete; freeze SHA is placeholder defect; `CI green before final` is NOT verified. Current corrected CI/parity/lineage documented here, not by replacing prior records.

## 7. Verification (E1, C9–C10 local)

Local host Darwin 25.6.0 ARM64, rustc 1.89.0, Python 3.14.2 (same toolchain family as CI MSRV 1.89):

- `cargo fmt --all -- --check` — pass
- `cargo test --workspace --all-features --locked` — pass (incl. 5 new `m014a_*` + all workspace crates)
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — pass
- `cargo check -p sdm-runtime --locked` — pass; `cargo tree -p sdm-runtime --locked` — pass (isolated to `serde/serde_json/sha2/thiserror` + `libc` dev for RSS; no training/GPU/remote/model-service)
- `cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked` — pass
- `cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json` — 12 fixtures, 11 executions (unaffected)
- `python3 -m unittest discover -s scripts -p 'test_m014a_analyzer.py'` — 21 pass (pure)
- `python3 -m unittest discover -s scripts -p 'test_m014a_canary.py'` — 9 pass (after provisioning; 1+4 fail without provisioning as in §2)
- `test_m013b_*` 47 pass; `test_m013c_*` 71 pass; `test_m013d_*` 9 pass (2 skipped); `test_m014_representability` 3 pass; `test_m014_suite` 5 pass
- `python3 scripts/run_m014a_dev_canary.py` — exit 0 clean and rerun, Binary positive / Choice indeterminate / overall indeterminate, deterministic `report_sha` identical, real resources (41267 B/2 opts/p95_128 22019/RSS 59015168/cold 7249/host/build recorded; parity `false`/unverified per §4)
- `python3 scripts/check_m014a_ci_order.py` — pass (`pure < gen < dependent`)
- `python3 scripts/verify_m014c_lineage.py` — `verified_with_known_defect`; one-byte mutation fails
- `python3 scripts/m014c_canary_attestation.py --parity` + `verify_m014c_parity.py` — local 3-label simulation passes (948+926 cases); single-host rejected, mutated action rejected; hosted run 38418968150 passes (0 divergences, max prob delta 8.67e-19)
- `python3 scripts/m014c_parity_evaluate.py` — 5 committed-artifact parity reports on canary data exit 0 (948/926 rows, SHAs match committed bytes; never FINAL paths)
- `python3 scripts/generate_m014b_suite.py` + `sdm-dataset split` + `cmp` + `validate_future_support` — deterministic regen matches frozen splits/fingerprints; freeze SHAs match; support pass (no final inference; `fixtures/m014b-final-*.evaluate.json` NEVER executed)
- Package/license audit (CI): `cargo package`, `audit_package_contents`, `check_staged_consumer`, `audit_cargo_licenses` (no manifest/lock changes; `Cargo.lock` untouched)
- No network, user data, external provider, GPU dependency. Datasets synthetic-only MIT. Runtime offline, bounded (16 MiB, ≤128 options, finite checks, atomic writes, named paths only, refuse overwrite).

Hosted verification (C9, E2) — GREEN:

- Run [38418968150](https://github.com/dbowm91/sdm/actions/runs/38418968150) at `d60d9c0bd07b4dbe525d9f167720095bb88cfd10`: **SUCCESS 11/11** (created 2026-10-13T15:05:02Z).
  - `msrv` success; `verify (linux-x64)`, `verify (linux-arm64)`, `verify (macos-arm64)` success (ordered pure→gen→dependent, lineage, parity-evaluate, `--parity` attestation); `portability ×3` success; `choice-portability ×3` success; `canary-parity` success.
  - Cancelled/skipped is NOT a pass (none occurred); plan-only `38399878048` is NOT evidence (not cited as such).
  - Parity verdict artifact (`canary-parity-verdict`): all five parity SHAs identical across hosts, 948 binary + 926 choice cases, 0 decision divergences, max prob delta 8.67e-19.
- Prior run [38413896571](https://github.com/dbowm91/sdm/actions/runs/38413896571) at `5d4c559` (11 jobs, 10 pass + `canary-parity` fail on retrained-Choice divergence) is retained as evidence for the fix; NOT described as a pass. Original failure [38408167153](https://github.com/dbowm91/sdm/actions/runs/38408167153) likewise retained.
- Merged-main CI (C12): [38424519807](https://github.com/dbowm91/sdm/actions/runs/38424519807) SUCCESS 11/11 on merge `91b0c3b` — full integration claimed (see §8 C12, §9).

## 8. Acceptance matrix C1–C12

| Gate | Non-negotiable evidence | Status |
| --- | --- | --- |
| C1 | CI ordered: canary before artifact-backed tests or tests provision fixtures; clean target pass on all 3 hosts | **Pass** — pure 21 pass clean, dependent 5 fail without canary (reproduces 38408167153), clean generation + rerun identical, order enforced on all matrix hosts via `ci.yml`, regression `check_m014a_ci_order.py` passes; hosted 3-host verify SUCCESS in 38418968150 |
| C2 | Pure Python unit tests independent of prior local target cache; deterministic repeat and fail-closed fixtures | **Pass** — `test_m014a_analyzer.py` 21 constructed-fixture only (no `target/` import), deterministic repeat, fail-closed (`None` threshold → insufficient, straddling → indeterminate, missing evidence → invalid) |
| C3 | Real three-host *same-artifact* case-by-case action/abstention parity, source/case/host SHAs matched; missing host blocks pass | **Pass** — `--parity` attestation on SAME committed bytes (948+926 decisions, SHA-hashed) + aggregator (exact platforms, source/case equality, exact action match); local simulation + hosted 38418968150 `verdict pass` (0 divergences, max prob delta 8.67e-19); single/mutated rejected |
| C4 | No hardcoded three_host_parity=true masquerades as measurement; resource gate remains fail-closed | **Pass** — single-host literal removed (`false`/unverified with explicit note); `evaluate_resources` still requires `true` to pass (missing/false → fail/invalid); canary Choice stays indeterminate (correct provisional) |
| C5 | Historical M014b freeze/configs/inputs unchanged; placeholder SHA identified and detached pretest Git chain recorded accurately | **Pass** — frozen diff empty; placeholder `sha256:111…1` in all five configs flagged `placeholder_unbound`; Git/SHA-256 lineage (`9cc80f0` ancestor of `c277247`, committed-bytes equality, blob-SHA1 vs file-SHA256) verified |
| C6 | Read-only reproducible lineage validator rejects one-byte mutation, has no final inference call or historical write | **Pass** — `verify_m014c_lineage.py` read-only (out only `target/m014c/`), no `evaluate`/inference, no historical write; one-byte corruption fails exit 2, restored passes |
| C7 | Five ORIGINAL final reports and qualification/manifest/resource file SHAs recorded from existing bytes OR individually declared unavailable; no guessed digits | **Pass** — all eight files available locally, file SHA + inner `report_sha256` + size/mtime/host recorded in `docs/m014c-evidence-ledger.json` from original bytes (read-only, no rerun); none marked unavailable; no digits guessed |
| C8 | Historic Binary/Choice/overall negative outcome retained as historic local observation; final cohort never rerun/retuned | **Pass** — negative/negative/negative retained with intervals and rule-change scope; `fixtures/m014b-final-*.evaluate.json` never executed in M014c; cohort consumed, no tuning/retry/threshold change |
| C9 | Hosted Rust 1.89, 3-host verify + Rank/Choice portability and new parity aggregator SUCCESS on implementation SHA | **Pass** — [38418968150](https://github.com/dbowm91/sdm/actions/runs/38418968150) at `d60d9c0` SUCCESS 11/11 (msrv + 3 verify + 3 portability + 3 choice-portability + canary-parity); cancelled/skipped none |
| C10 | Repository planning/closure truth reconciled, old failed CI and unresolved provenance evidence limitation visible; regression/size/license/privacy checks pass | **Pass** — erratum `2026-10-13` keeps originals intact, corrects Q8/G9/parity/digest/placeholder/`CI-green-before-final` claims; failed runs 38408167153 + 38413896571 retained with fix narrative; size (≤45529 B ≪16 MiB, 2 ≤128), license (`audit_cargo_licenses` unchanged), privacy (synthetic-only, redacted), runtime isolation pass |
| C11 | ONE main-targeted reviewable PR includes M014a–M014c stack and all code/plan/errata | **Pass** — [PR #3](https://github.com/dbowm91/sdm/pull/3) (`7b9bb3c..3d8db08`, 39 files, stack only, no unrelated/ignored changes); MERGEABLE at review; PR run 38422712418 + branch run 38421173295 SUCCESS 11/11 on `3d8db08`; no main push, no auto-merge, no M014b rerun in checks |
| C12 | Reviewer-approved merge and merged-main CI SUCCESS, no publish/pin/model promotion | **Pass** — user-authorized merge `91b0c3b` (Merge PR #3); merged-main [38424519807](https://github.com/dbowm91/sdm/actions/runs/38424519807) SUCCESS 11/11; no crates.io publish/tag, no CodeGG pin change, no model promotion |

`C1–C12` all pass (implementation-hosted 38418968150 + PR 38422712418 + branch 38421173295 + merged-main 38424519807, all SUCCESS 11/11). Full integration closure is complete. If original M014b output bytes are later lost, ledger incomplete-provenance status persists even after mechanical gates.

## 9. Integration, rollback, non-goals

- Integration: DONE via [PR #3](https://github.com/dbowm91/sdm/pull/3) (M014a–M014c stack `7b9bb3c..3d8db08`: `crates/sdm-experiment` evaluate path, `qualify_semantic_v2`, canary/parity generators/runners/validators, freeze scripts, CI, docs/plans/closures/ledgers; no unrelated changes; ignored `target/` excluded; legacy compatibility preserved per §7). No direct main push for the stack (single reviewable PR, user-authorized merge `91b0c3b`); no auto-merge; no M014b rerun in PR checks. PR diff + CI (38422712418 + 38421173295 SUCCESS) verified before merge; merge SHA + merged-main CI 38424519807 SUCCESS confirmed after. No publish/pin/promotion.
- Rollback: discard `target/m014a/canary/` (regenerable DEV-CANARY, incl. `parity-*`) and `target/m014c/` (lineage/parity outputs, regenerable) without touching freeze; `target/m014b/final/` is ignored original observation — rollback by discarding would lose original bytes (hashes preserved in ledger; bytes must be retained on original host). Immutable pretest commits (`9cc80f0`, `c277247`, `af74c01`, `d60d9c0`) allow source rollback by ref.
- Non-goals kept: no new model architecture/trainer/optimizer, no artifact ABI reinterpretation, no CodeGG pin/tool authorization or production change, no crates.io publish/tag, no imported corpus or network dependency. Rust 1.89, Linux x64/ARM64 + macOS ARM64, offline runtime-only isolation, 16 MiB bounds retained. Current `main` unchanged; no fabricated CI success or parity claim.
- Four verdicts kept separate: (a) infrastructure/source correctness (this closure, C1–C12 pass with merged-main green), (b) historical M014b synthetic model result (negative, local only), (c) evidence/provenance completeness (verified detached chain + original-byte ledger + measured 3-host parity; embedded placeholder defect retained as defect; failed runs retained), (d) reviewed main integration (PR #3 merged `91b0c3b`, merged-main 38424519807 green; M005 deferred, M012 publication human/legal-gated). Never infer one from another.

## 10. Requirement-to-evidence matrix (plan §3–7)

| Plan req | Evidence | Location |
|---|---|---|
| A1 failing logs + 5 dependent tests, job IDs, no conflation | 38408167153 Linux-x64 FAILED (1+4/30), ARM64/macos CANCELLED, portability SKIPPED, MSRV passed; local clean reproduction (21 pure pass, 9 dependent 1+4 fail) | §2 + CI logs + `target/m014a/canary/` absent test |
| A2 pure → gen → dependent order on all hosts, fail-closed provisioning, no target-cache dependence | `ci.yml` pure/gen/dependent steps + `check_m014a_ci_order.py`; pure uses constructed fixtures only | `.github/workflows/ci.yml`, `scripts/check_m014a_ci_order.py`, `test_m014a_analyzer.py` |
| A3 clean vs present identical verdicts, safe regen, never remove finals | Clean generation exit 0 + rerun identical (Binary positive/Choice indeterminate, `report_sha` equal); only own DEV-CANARY paths deleted; finals untouched | `run_m014a_dev_canary.py`, §3 |
| A4 source vs workload distinguished, no historic overwrite on retry | Per-host manifest/report/qualification SHAs + HEAD/toolchain logged; uploads `target/m014a/` + attestations; retries use NEW CI runs, never overwrite historic records | `ci.yml` gen step, §7 |
| A5 old guards continue + ordering regression | M011/M013a/b/c/d/M014 suites pass (§7); `check_m014a_ci_order.py` fails future misordering | scripts + §7 |
| B1 parity `true` literal declared unverified | `resource-evidence.json` now `false`/unverified with explicit note; analyzer still requires `true` | `run_m014a_dev_canary.py`, `qualify_semantic_v2.evaluate_resources` |
| B2 same committed bytes, bounded per-case attestation, no raw text | `m014c_parity_evaluate.py` (5 committed-artifact parity reports on canary data) + `m014c_canary_attestation.py --parity` (948+926 decisions, artifact/dataset/split SHAs, source/host/build, `attestation_sha256`) | scripts + §4 |
| B3 downstream aggregator verifies platforms/source/cases/decisions, tolerances separate, host timings not compared | `verify_m014c_parity.py` + `canary-parity` job (exact platforms, source/case equality, exact action match, prob tolerance separate, timings not compared; duplicate/missing/mismatch fail); hosted 38418968150 pass | scripts + `ci.yml` + §4 |
| B4 no single-host `true`; provisional indeterminate correct; pure units separate; fail-closed kept | Single-host `false`; canary Choice indeterminate (recall + parity); pure analyzer tests separate; missing-evidence gate still fail-closed | §4 |
| B5 M014b current verification via archived/DEV-CANARY only, never FINAL | Parity covers DEV-CANARY + committed artifacts only; FINAL never reprocessed (no `m014b-final-*` run) | §4, §6 |
| C1 freeze/observed SHAs, placeholder content, valid bindings | §1 + ledger + `verify_m014c_lineage.py` output (placeholder `111…1` in all five; valid: protocol/candidate/dataset/split/generator/evaluator/commit) | §1, §5, ledger |
| C2 append-only erratum, non-self-referential lineage, Git-SHA1 vs SHA-256, no retroactive repair | This §5 + ledger `erratum_2026_10_13` + `verify_m014c_lineage.py` attestation (detached chain, placeholder still visible) | §5, `docs/m014c-evidence-ledger.json` |
| C3 read-only validator, precise failures, no writes/final calls, one-byte fails, ancestry without timestamps | `verify_m014c_lineage.py` (see §5 tests) | scripts + §5 |
| C4 scope/severity, no backdating | §5 scope paragraph + ledger; historic `CI-green-before-final` marked NOT verified | §5 |
| C5 next-experiment two-phase contract | §5 future requirement (core digest → config binding → sealed bundle); not implemented here | §5 |
| D1 original bytes or trusted CI SHAs with custody | §6 ledger (8 files, SHAs/sizes/mtimes/host/inner digests, local original bytes, no CI artifact) | `docs/m014c-evidence-ledger.json` |
| D2 missing → unavailable, never manufacture | None missing locally; rule recorded (mark unavailable, never `evaluate`/reconstruct/relabeled) | ledger note + §6 |
| D3 read-only parse/SHA/case-ID annotation, no new adjudication for promotion | §6 verification (partition/flag/schema/artifact/membership/counts); no new qualification of FINAL | §6 |
| D4 machine-readable/Markdown ledger + dated erratum, originals intact, current CI separate | Ledger JSON + §6 erratum list; originals untouched; corrected CI here | ledger + §6 |
| D5 rule-change vs nuisance, transfer vs capacity, no M015 selection | §6 scope (AND-XOR/XNOR rule change; transfer inability, not capacity refutation; not for M015) | §6 |
| E1 local clean-room + Rust/toolchain/consumer checks, no final configs run | §7 (fmt/test/clippy/check/tree/consumer/compat + Python suites + benchmarks + package/license; no `m014b-final-*` run) | §7 |
| E2 hosted 3-host + portability + parity SUCCESS on implementation SHA, no conflation | §7 hosted paragraph (38418968150 SUCCESS 11/11 on `d60d9c0`; 38413896571 retrained-divergence fail retained; cancelled/skipped none; `38399878048` not evidence) | §7 |
| E3 one main PR, diff review, no direct push/merge/rerun, merge+main-CI confirm | §9 integration paragraph | §9 |
| E4 this closure + registry/roadmap/README updates; M014a/b restored only after C1–C9; limited grade if originals missing | This file + registry/roadmap/README/plans updates (see §11); M014a/b `closing → mechanically closed (negative)` conditional on C1–C9; originals available so grade is `original-byte ledger`, not limited | §11 |
| E5 no M015/M005/M012 unblock | §11 future-plan decision (M015 unregistered, M005 deferred, publication gated) | §11 |

## 11. Planning updates and future-plan readiness

- Registry (`plans/registry.md`): M014c `ready → mechanically closed (C1–C8+C10 local pass; C9/C11/C12 pending push/review/merge)`; M014a `closing (CI/evidence blocked) → mechanically closed; negative predictive result (canary Binary positive/Choice indeterminate; historic M014 indeterminate unchanged)` conditional on C1–C9; M014b `closing → mechanically closed; negative predictive result (Binary/Choice/overall negative, local, consumed)` conditional on C1–C9 with original-byte ledger; M015 remains UNREGISTERED (not ready); M005 deferred/indeterminate (no approved corpus); crates.io publication blocked (human/legal); M012 conditionally closed (publication gated). No future plan is unblocked by this pass: explicit later separate question is learning vs transfer across different conditional rules and answerability on vocabulary shift (requires own corrective + prospective freeze + thresholds); M005 needs independent CodeGG-owned corpus; publication needs human/legal signoff.
- Roadmap (`plans/subsystems/general-decision-model-framework-roadmap.md`): M014a/b `closing → mechanically closed (negative, honest, original-byte ledger)`; M014c `ready → mechanically closed (integration pending)`; M015 unregistered.
- `plans/README.md`: start-here now points to M014c closure (mechanically closed, integration pending); M014a/b historical closing superseded for CI/evidence purposes.
- `README.md`: M014c section added (mechanically closed, hosted/integration pending; never rerun FINAL; M015 unregistered).
- `docs/artifact-format.md`: M014c note (no new architecture; evaluate/attestation/lineage additive; placeholder defect not repaired in place).
- `docs/typed-task-heads.md`: M014c note (no head/training/threshold change; parity/provenance only).
- No successor model research M015 registered ready; no CodeGG corpus/model-service/crates.io/external publication dependency added.

## 12. Reproducibility (do NOT rerun final)

Safe (no test scores; no `fixtures/m014b-final-*.evaluate.json` execution):

```sh
cargo fmt --all -- --check
cargo test --workspace --all-features --locked
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo check -p sdm-runtime --locked
cargo tree -p sdm-runtime --locked
cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked
cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json
python3 -m unittest discover -s scripts -p 'test_m014a_analyzer.py'
python3 scripts/run_m014a_dev_canary.py
python3 -m unittest discover -s scripts -p 'test_m014a_canary.py'
python3 scripts/check_m014a_ci_order.py
python3 scripts/verify_m014c_lineage.py --out target/m014c/lineage-verdict.json
python3 scripts/m014c_canary_attestation.py --platform macos-aarch64 --out target/m014a/canary/attestation-macos-arm64.json
python3 scripts/verify_m014c_parity.py --inputs a.json b.json c.json --out target/m014c/parity-verdict.json
python3 scripts/generate_m014b_suite.py
# M014b split/support regen + freeze SHA checks (no final inference) — see ci.yml `Verify M014b prospective freeze`
```

One-time final (ALREADY CONSUMED — DO NOT RERUN; for record only; see `014b-status.md` §9): `experiment evaluate` on `fixtures/m014b-final-*.evaluate.json` + `qualify_semantic_v2` on `target/m014b/final/*` MUST NEVER be executed again. Ledger SHAs above are the only evidence.

End condition met (modulo hosted/integration pending): hosted-green-ready (locally proven, CI ordered), three-host-attested (mechanics proven, aggregation job defined), source-reviewable pipeline; historic M014b negatives preserved with provenance limitations disclosed; ready-for-merge integration is the only pending operational step.
