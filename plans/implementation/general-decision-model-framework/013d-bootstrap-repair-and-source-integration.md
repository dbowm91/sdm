# M013d — Bootstrap Safety and M013–M013d Source Integration

Status: **ready** (planning handoff only; no code or PR created)
Class: infrastructure / evidence-integrity corrective and release source integration
Baseline: dbowm91/sdm@03c4a982219ffa830b7c0aba9dbb19a541cae56c on `work/plans-sdm-m013c-qualification-gate-hardening`; recheck head and main before execution
Target: `main` (at planning: `2bd0d5af16d143828dcbce77f411b8f3b675e7be`)
Planning branch: `work/plans-sdm-m013d-bootstrap-source-integration`
Governance: `plans/003-planning-process.md`; ADR-0001 / ADR-0002; M013–M013c numbered plans and closures
Hard prerequisite: M013c code complete and latest hosted [CI 38109647535](https://github.com/dbowm91/sdm/actions/runs/38109647535) green (10/10 jobs)
Operational review gate: approved main-targeted PR merge, separate from engineering completion
No external dependency: CodeGG dataset and crates.io publication/legal decision not required
Closure document: `plans/closure/general-decision-model-framework/013d-status.md`

## Objective / exact desired end state

Correct the LAST identified live unsafe estimator in the current SDM evaluator lineage — the **M013b unsorted bootstrap quantile** — and bring the M013, M013a, M013b, M013c and M013d source stack into a normal reviewed main integration path. Preserve original historical experimental evidence while acknowledging new generated sidecar source-hash changes after a safe fix. End the repeated quality-verification corrective loop; prepare a clean base for a NEW prospective modeling milestone, not another trial against the already observed M013a test.

Distinct outcomes MUST remain separate: **(1)** mechanically correct Python evaluator and Rust runtime, **(2)** model quality Binary negative / Choice indeterminate, **(3)** source PR review/merge status, **(4)** legal/publishing readiness, and **(5)** future CodeGG consumer-specific approval. None implies another.

At baseline the M013c branch is 15 commits ahead of main and 0 behind; CI green; no main-targeted PR. The M013b defect is in `scripts/m013b_evaluator.py`: `quantile(sorted_values,p)` expects ascending values, but `group_bootstrap()` passes unsorted RNG draws. M013c's own `_quantile/grouped_bootstrap` sorts correctly; M013a's historical analyzer also sorts. Existing M013a reports are valid; the observed M013b intervals affected by this helper are degenerate and thus numerically unaffected. **Non-degenerate new results from that legacy helper would be wrong.**

## Invariants and non-goals

- Frozen historical evidence is never rewritten: `fixtures/m011*`, `fixtures/m013*`, `docs/m013a-protocol-v1.md`, trained artifact bytes, original M013a analyzer and numbered M013–M013c closure records remain unchanged. Prior Git commits constitute the immutable source archive.
- No model weights/trainer/routing thresholds/data splits/answerability calibration are selected on an already-seen test, and no new final held-out inference is commissioned. No CodeGG content is required or ingested.
- Keep the same group-resampling definition, seed=14014, 10,000 draws, 95% percentile interval, same source group identities, and the same quantile interpolation. Fix only the sort/preconditions/validation in the legacy estimator; do not replace architecture or training design.
- Do not change Rust crates, offline runtime-only dependency graph, 1.89 MSRV, 3-host portability, 16 MiB model bound, v1/v2 artifact compatibility, application-owned tool/candidate authorization or old CodeGG immutable pin.
- No direct main push, force-push, auto-merge, release tag or crates.io publish. A PR open/green is distinct from a human-reviewed merge.
- M013d is hereby the **legacy bootstrap and integration corrective**, not a new predictive experiment. The next prospective experiment should be separately numbered M014 or later and remains unregistered until prerequisites are met.

## Workstream A — Freeze original evidence and exact defect analysis

A1. Verify current `main`, source HEAD, open PRs and ten hosted CI jobs before starting. Record base SHA, source SHA, merge-base and original sha256(`scripts/m013b_evaluator.py`) at pre-fix `03c4a982219ffa830b7c0aba9dbb19a541cae56c`; preserve exact M013b pinned source at `11ea106c9af3b1ec362a98e709b530cc0fa137d0` and M013c at `8dd8a2151ef0c5b88adf5ce0c164992636bc17ee`. Do not rewrite those commits.

A2. Inventory imports/callers of `m013b_evaluator.quantile` and `group_bootstrap`; `scripts/m013b_audit_m013a.py` is a known callsite. Verify whether code expects a presorted argument or old output fingerprint. Document callable contract, old defective numerical example and proposed safe change.

A3. Use a clean pinned checkout/worktree (ideally Linux x64 CI, because M011 host floats can differ) to reproduce ORIGINAL results:
- M013a `target/m013a/quality-analysis.json` SHA256 `411ac0915a0dd6ae94710271b1b23bbad830732762b956dcca71500b6f592d6e`.
- M013b `target/m013b/m013a-audit-erratum.json` SHA256 `07fb99f1e984354a6746f3645f893beadfbbb3fd40ce4e37d4b6a834a0e15901`.
- M013b `target/m013b/m013b-diagnostics.json` SHA256 `3b489c25eb0fcd51b7dc08d7e9e7a1e1a45a6f16e244cf5a8173e8aceb728da4`.
- M013c `target/m013c/m013c-decision-audit.json` SHA256 `6560052ba93445288d1b7577c475d0fcaec12035d9838c8c955a91ced2801edf`.

If the executing host cannot reproduce a host-specific baseline, cite the exact hosted CI platform/artifact; do not substitute a guessed digest. The recorded old hash ledger is fixed by the original commit, not by new output generated with changed source.

**A acceptance:** original commit/history/source and frozen data accessible; at least one pinned reference reproduction with recorded SHA/evidence; callsite inventory complete; exact defect demonstrated by a non-degenerate deterministic constructed example. No time-consuming repetition of unrelated router/consumer tests.

## Workstream B — Minimal safe bootstrap repair

B1. Prefer fixing `quantile(values,p)` to defensively SORT a copy of values internally and adjust its name/docstring, which protects direct imports as well as `group_bootstrap`. Sorting the draws only at the bootstrap callsite is acceptable ONLY if all direct calls are proven to require presorted data and a guard/test prevents new unsafe use. A reusable direct `quantile` that silently computes incorrect values on unsorted data is NOT an accepted final contract.

B2. Keep RNG seed, number and ordering of resamples, group membership, confidence, interpolation and return shape stable. Validate non-empty finite inputs, p within [0,1], invalid group IDs, non-finite statistics and illegal bootstrap arguments (when appropriate) without fabricating a favorable interval. A zero-group data set must retain explicit nonqualification semantics, not a finite interval.

B3. Compare on the SAME independently constructed grouped rows to correct M013c `grouped_bootstrap`, and to the sorting behavior of the historical M013a analyzer. Do not implicitly depend on M013c for M013b import/packaging; use reference only in regression tests.

B4. Add fast `scripts/test_m013d_*.py` tests that execute the actual M013b entrypoint and prevent reintroduction of unsorted percentiles. Ensure deterministic ID ordering is either maintained or explicitly documented as a stable input-order contract. Keep historical v1 archive replay independent of new current working tree.

**B acceptance matrix:**
- B1: `quantile([3,1,2],0)==1`, p=.5 ->2, p=1 ->3; any permutation yields same value.
- B2: `quantile([0,10],.25)==2.5`; .975 ->9.75; exact boundaries 0/1. Caller list is not mutated.
- B3: At least two nondegenerate constructed populations (one skewed, one with paired rows in shared leakage groups) at seed 14014 / 10,000 draws: corrected 95% lower/upper agree with independently sorted M013c/frozen reference within 1e-12 absolute; old version fails at least one case. Record actual numeric examples.
- B4: All-constant/degenerate group data retains exactly the same interval; one-group behavior is explicit; leakage-group support counts groups, not rows.
- B5: Invalid/empty/non-finite statistics, invalid p and invalid bootstrap settings yield bounded documented error/indeterminate, never `positive` or NaN as a legitimate interval.
- B6: Repeated deterministic runs give identical numeric outputs with the same input/source/seed; group-order permutation invariant if canonicalization is part of the contract, otherwise exact ordering explicitly frozen and tested.
- B7: Import/reference audit shows no supported live path still uses unsorted interpolation; M013c tests continue green.
- B8: Cancel/interruption of report output leaves no accepted partial file; atomic write/rename behavior preserved.

## Workstream C — Explicit post-fix provenance and retained verdicts

**Critical trap:** `m013b_audit_m013a.py` embeds sha256 of `scripts/m013b_evaluator.py` in its own sidecar's `input_sha256`. `m013c_qualification_audit.py` then reads/hashes the M013b sidecar. Editing M013b estimator therefore **necessarily changes the newly regenerated sidecar hashes**, even if every numerical metric stays unchanged. An acceptance rule demanding byte-identical new-head M013b/M013c sidecars would be self-contradictory.

C1. Keep original M013a dataset/split/protocol/trained artifacts and official report EXACT (original hashes). Re-run archived M013b/M013c scripts in the PINNED old checkout and assert original historical hashes; do not touch original closure files or pretend current generated outputs are historical snapshots.

C2. At new code HEAD, regenerate into a fresh versioned `target/m013d/` audit/erratum with `old_commit`, `new_commit`, original/new evaluator source hashes, old/new M013b sidecar SHA and M013c sidecar SHA, and per-field semantic comparison. If existing CI produces `target/m013b/` and `target/m013c/` sidecars automatically, permit their new digest only when attributable to expected source provenance and document it; never overwrite stored historical SHA declarations.

C3. Ensure model metrics, M013a held-out CI bounds, Binary `negative` and Choice `indeterminate`, fixed-option counterfactual summaries, M013c CI-bound gates and named controls are equivalent pre- and post-fix. The M013b historical original intervals were degenerate; demonstrate they stay numerically identical. If a new nondegenerate historical interval unexpectedly changes, report it transparently and investigate instead of changing experimental gates.

C4. End with machine-readable audit `historical_preserved=true`, `model_qualifications_unchanged=true` and per-artifact SHA/difference reason, whose accuracy is asserted by CI. No M013a test rows become eligible for new training or selection.

**C acceptance:** old pinned evidence unchanged; no frozen fixtures/protocols/artifacts changed in git diff; clear digest ledger old vs current and reproducible provenance explanation; no test-set leakage or falsely "new" quality result.

## Workstream D — Integration and release-status closure

D1. Run focused `test_m013d_*.py`, existing M013b 47 tests and M013c 71 tests, M013a split/freeze/hash reproduction, frozen v1 CodeGG 12/11 compatibility, and broad Rust fmt/test/Clippy/runtime-only-tree/standalone consumer tests. Run hosted CI on the implementation head (Rust 1.89, Linux x86_64/ARM64, macOS ARM64, same trained artifact portability, staged package/license checks; ten jobs). Record actual run URLs/outcomes. The expensive M013a rerun remains MECHANICAL regression only.

D2. Full diff review against `main` covering all M013–M013d ancestry, roughly 60 current changed files, large generated synthetic fixtures, local `target`/venv exclusion, provenance/licenses, crate packaging inventory, and Rust manifest invariants. Mark exact drift/unrelated work; do not reopen predictive model verification because its negative evidence remains negative.

D3. Open **one** main-targeted, reviewable PR for M013–M013d with head/base/merge-base SHAs, summary by milestone, G1–G10 acceptance table, deterministic old/new bootstrap example, old/new source and report hash ledger, hosted CI, explicit lack of model qualification, no CodeGG pin change, and crates.io legal gate outstanding. Do not merge automatically or push main directly. Treat a review delay as PENDING, not a fresh implementation blocker.

D4. After an actual reviewer-approved merge, recheck exact PR `merged_at`, main SHA and merged-main CI, confirm all plans/code and package checks exist on main and no intended files were omitted. Update current-facing registry, roadmap §10, `plans/README.md` and README to state precise integrated/conditional statuses. Do not mark `main` integrated merely because a green branch CI or PR exists. Do not overwrite M013b/M013c original closure docs.

D5. Keep remaining gates independent: no crates.io publication without human/legal license approval; no CodeGG M005 consumer promotion without an independently approved corpus and consumer-owned qualification; no successor M014 experiment ready before an independent preregistered new test/protocol and eligible support counts.

**D acceptance:** source review PR exists and is accurately linked, full source ancestry present, no hidden modifications/publish/pin, CI 10/10 green for implementation; if PR merged, actual merged-main CI green. If PR awaits review, M013d can be **conditionally closed (mechanics + PR complete, review pending)**, not fully integrated; do NOT create another corrective just for the wait.

## Cross-cutting acceptance gates and stop triggers

| Gate | Proof necessary | Required for mechanical closure |
| --- | --- | --- |
| G1 legacy estimator safe | Correct unordered quantiles + nondegenerate grouped CI | Yes |
| G2 exact reproducibility | New deterministic sorted-group values; no silent changed resampling or shape | Yes |
| G3 historical provenance | Pinned old hash replay and separate new-HEAD source-hash sidecar | Yes |
| G4 model verdict preservation | Binary negative, Choice indeterminate; frozen data/artifact/CI unchanged | Yes |
| G5 CI platforms and runtime | Rust 1.89 and all ten hosted jobs pass; runtime graph still isolated | Yes |
| G6 security/storage | No sensitive imports, no partial accepted report, no old fixture overwrite | Yes |
| G7 source PR | ONE main PR includes M013/M013a/M013b/M013c/M013d; reviewer checklist and SHAs | Yes |
| G8 merged-main verification | If approved/merged, PR merge SHA and main CI passed | For FULL integration closure only |
| G9 planning consistency | registry/roadmap/README precise statuses, no contradictory "ready" claims | Yes |
| G10 gate separation | No publish/tag, CodeGG pin change, model promotion, test-driven tuning | Yes |

STOP and record a specific failure if corrected bootstrap still interpolates unordered draws, historical official M013a evidence or model artifacts change, M013b/M013c report changes are misattributed instead of explained, nondegenerate CI regression test fails, old frozen snapshots cannot be reconstructed, wrong-base PR is created, source stack omitted, or Rust/platform/permission boundary is violated. Revalidate Git refs before writes using expected SHA, never force-push over concurrent changes. A PR review delay, missing CodeGG corpus or legal publication signoff is NOT grounds for looping further on this corrective.

## Verification commands and closure record

Python: `python3 -m unittest discover -s scripts -p 'test_m013d_*.py'`; same patterns for `test_m013b_*.py`, `test_m013c_*.py`; `python3 scripts/validate_m013a_freeze.py`; `python3 scripts/analyze_m013a_quality.py`; `python3 scripts/m013b_audit_m013a.py`; `python3 scripts/m013b_diagnostics.py`; `python3 scripts/m013c_qualification_audit.py`; new M013d audit CLI once authored. Assert original snapshot hashes in a pinned checkout and semantics/new hashes in current HEAD, not contradictory byte-identity for different source.

Rust: `cargo fmt --all -- --check`; `cargo test --workspace --all-features --locked`; `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`; `cargo check -p sdm-runtime --locked`; `cargo tree -p sdm-runtime --locked`; `cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked`; `cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json`. CI staged package/consumer plus license inventory must remain; `cargo package --workspace --locked --no-verify` is NOT proof of publication.

Closure `plans/closure/general-decision-model-framework/013d-status.md` must include exact planning/implementation/head/base/merge SHAs, PR and review status, CI logs for all jobs and merged-main if applicable, G1–G10 matrix with evidence, old and new quantile numeric examples, original/current SHA ledger with causal explanation, positive/negative/indeterminate metric/verdict preservation, compatibility/privacy/resource/license review, reset/partial output behavior, external gates, integration disposition and outstanding items. If source PR is review-pending, close conditionally and do NOT invent its merge. After full integration, no known bootstrap/stack-integration blocker should remain. Future M014 model experiment requires a separate prospectively frozen test and preregistration; this plan does not register it.
