# Small Decision Model (SDM)

SDM is the independent home for generic bounded decision semantics, local artifact
inference, and reproducible training/evaluation. CodeGG-specific authority, tool
projection, disclosure, capture consent, and causal-frontier behavior stay in CodeGG.

## Repository policy

- License: MIT, preserving the Anomalyco copyright notice from the CodeGG source.
- Visibility: public; immutable full-SHA downstream consumption remains the release policy.
- Consumption/release policy: downstream projects pin an immutable full Git commit
  SHA. Branch names and floating tags are not runtime dependencies. A source revision
  is usable only after CI and the CodeGG compatibility fixture command pass.
- This repository performs no implicit network access or model download.

## Workspace

- `sdm-core`: semantic request/response types and validation, no application authority.
- `sdm-runtime`: validated offline artifact loading and bounded inference. It has no
  dependency on `sdm-training`.
- `sdm-training`: generic decision-case dataset validation, deterministic group
  splitting, model fitting, dev-only threshold selection, and test evaluation.
- `sdm-data`: provenance-bearing labels and frozen leakage-aware group splits.
- `sdm-eval`: algorithm-neutral semantic metrics and preregistered offline reports.
- `sdm-nonlinear`: optional bounded nonlinear CPU scorer and deterministic local SGD.
- `sdm-experiment`: explicit-input Rank orchestration, frozen-split training,
  dev-only threshold selection, runtime reload and held-out reporting.

Publication-facing package metadata is set per crate with the verified
repository/homepage and crate-specific docs.rs destinations. The checked-in
[standalone quickstart](docs/standalone-quickstart.md) covers the experiment,
packaged consumer boundary, compatibility and quality limits. The locked
[third-party inventory](docs/third-party-license-inventory.json) is metadata
evidence only; see its [review status](docs/third-party-licenses.md) before any
registry distribution.

Legacy linear and pairwise Rank artifacts remain supported. Additive typed artifact
versions also serve Binary, Choice, Score, and typed Rank heads. Multiple relevant
Rank candidates remain independent labels. Applications still own policy, authority,
and abstention handling.

## Build and qualify

```sh
cargo test --workspace --locked
cargo check -p sdm-runtime --locked
cargo check -p sdm-runtime --examples --locked
cargo tree -p sdm-runtime --locked
cargo run -p sdm-training --bin sdm-check-compat -- \
  fixtures/codegg-compatibility-v1.jsonl path/to/artifact.json
cargo run -p sdm-training --bin sdm-train -- \
  fixtures/compatibility-rank-cases-v1.jsonl artifacts/compatibility-rank-v1.json 127 100
```

The compatibility fixture file is a sanitized, frozen copy of CodeGG's
`assets/decision-runtime/compatibility-v1.jsonl` at source revision
`aec30ebbaada172cd2915b3fb068f828a8fc6709`. The authoritative fixtures and historical
training/qualification evidence remain in CodeGG. No user session data was copied.
`scripts/import-codegg-compat-fixtures.py` regenerates the small Rank training set from
only the frozen source fixtures. `artifacts/compatibility-rank-v1.json` is a reproducible
baseline artifact, not a qualified or production-promoted model.
`cargo run -p sdm-runtime --example benchmark -- fixtures/benchmark-rank-request.json
artifacts/compatibility-rank-v1.json` emits cold load, artifact bytes, peak resident
memory after warming, p50/p95 latency for 16/64/128/256 candidates, and malformed
artifact rejection latency. The RSS number is the process high-water mark, so report it
as a conservative peak rather than an isolated runtime allocation measurement.

## Provenance

The semantic core originated in CodeGG commit
`aec30ebbaada172cd2915b3fb068f828a8fc6709`, file
`crates/codegg-core/src/decision.rs`. It is carried with its MIT license and source
attribution. The runtime and generic trainer in this repository are new implementations
that preserve the published semantic contract; they do not claim experiment-result or
model-weight provenance from CodeGG.

See [`docs/extraction-inventory.md`](docs/extraction-inventory.md),
[`docs/artifact-format.md`](docs/artifact-format.md), and
[`docs/reproducibility.md`](docs/reproducibility.md), plus the
[`docs/benchmark-baseline.md`](docs/benchmark-baseline.md) runtime snapshot.


## Planning record (October 2026)

SDM M001-M007 historical implementation and qualification outcomes are available in
[the planning registry](plans/registry.md) and
[closure records](plans/closure/general-decision-model-framework/).
The standalone framework successor work completed M008 through M011. Historical
conditional closures and the external M005 gate remain visible in the registry.

Completed milestones: [M008](plans/closure/general-decision-model-framework/008-status.md),
[M009](plans/closure/general-decision-model-framework/009-status.md),
[M010 Binary/Choice/Score trainable model heads](plans/closure/general-decision-model-framework/010-status.md), and
[M011 standalone held-out release qualification](plans/closure/general-decision-model-framework/011-status.md).
**M012 source/review handoff (historical record):** [M012 post-M011 release reconciliation](plans/closure/general-decision-model-framework/012-status.md) is conditionally closed and [PR #1](https://github.com/dbowm91/sdm/pull/1) is merged into main. Source is integrated but unpublished; crates.io publication is blocked pending human/legal license sign-off. M005 remains externally deferred until an approved CodeGG corpus and consumer-owned evidence exist.
[ADR-0002](plans/adrs/ADR-0002-standalone-framework-before-consumer-qualification.md)
defers CodeGG-specific effectiveness (M005) until an approved independent corpus exists;
**M008-M011 do not require CodeGG data or a CodeGG checkout**.

Run the reproducible standalone Rank examples with:

```sh
mkdir -p target/experiments
cargo run -p sdm-experiment --locked -- experiment run --config fixtures/standalone-rank-linear.experiment.json
cargo run -p sdm-experiment --locked -- experiment run --config fixtures/standalone-rank-nonlinear.experiment.json
cargo run -p sdm-experiment --locked -- experiment run --config fixtures/standalone-typed-rank.experiment.json
cargo run -p sdm-experiment --locked -- experiment run --config fixtures/synthetic-binary-typed-v1.experiment.json
cargo run -p sdm-experiment --locked -- experiment run --config fixtures/synthetic-choice-typed-v1.experiment.json
cargo run -p sdm-experiment --locked -- experiment run --config fixtures/synthetic-score-typed-v1.experiment.json
```

These configs use redistributable synthetic corpora and frozen group splits. The
M008/M009 Rank corpus has 36 examples; M011 adds fresh 400-example-per-task suites
with counterfactual pairs, held-out-family exclusions, and a test-only shifted family. Results establish mechanics
only and make no real-world quality claim. The CLI reads only named paths and refuses to overwrite
artifact/report outputs. Legacy `sdm-train`, `sdm-dataset`, and `sdm-qualify`
commands remain available. The typed Rank path demonstrates train-only numeric
scaling and text vocabulary, declared categories, boolean inputs, and runtime
schema checks. Binary, Choice, and Score have separate bounded typed heads and
task-specific metrics. Their synthetic runs establish pipeline mechanics only;
no CodeGG model is promoted.

Task feature, abstention, and artifact behavior is described in
[`docs/typed-task-heads.md`](docs/typed-task-heads.md).
M011's preregistered protocol is in
[`docs/release-qualification-protocol.md`](docs/release-qualification-protocol.md),
with local and hosted synthetic outcomes in [`docs/m011-local-results.md`](docs/m011-local-results.md)
and the numbered closure record in
[`plans/closure/general-decision-model-framework/011-status.md`](plans/closure/general-decision-model-framework/011-status.md).
A separate consumer crate can be compiled with
`cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked`.

## Predictive-quality corrective

[M013 predictive-quality corrective](plans/implementation/general-decision-model-framework/013-predictive-quality-corrective-and-independent-qualification.md) added the bounded `sdm-typed-choice-cross-v1` architecture while preserving the legacy diagonal head. Its first prospective corpus failed paired integrity and OOD-split checks. A separately frozen [M013a integrity rerun](plans/implementation/general-decision-model-framework/013a-independent-quality-suite-integrity-rerun.md) found negative Binary text/combined-shift results and indeterminate Choice results; three OOD Choice accuracy slices also lacked preregistered answerable-group support. No learned model is qualified or promoted. CodeGG M005 remains deferred on an approved corpus.

## M013b evaluator-integrity corrective (mechanically complete; unmerged)

[M013b evaluation-gates and failure-diagnostics corrective](plans/implementation/general-decision-model-framework/013b-evaluation-gates-and-failure-diagnostics.md) is implemented and verified on hosted CI (run [38107604379](https://github.com/dbowm91/sdm/actions/runs/38107604379)); closure evidence is recorded in [013b-status.md](plans/closure/general-decision-model-framework/013b-status.md).

It repaired two evaluation-integrity defects without touching any frozen M013a input. First, the historical "raw target margin changes sign" counterfactual statistic was a label-alignment artifact — an unchanged score vector yields +1 then -1 when the label flips — so M013b computes sensitivity from the *same physical option identity* on both sides of a pair and keeps the old quantity only as an explicitly labelled `label_alignment` metric. Second, the historical Choice classifier assigned its verdict from the primary confidence interval alone; M013b makes every preregistered support, counterfactual, critical-OOD, answerability and calibration gate executable and fail-closed, so a `positive` verdict is unreachable while any mandatory gate fails or is underpowered. Where M013a declared no numeric threshold, the gate stays `insufficient_support` rather than gaining a favorable post-hoc one.

Using train/dev data only, M013b isolated both root causes. Binary: the head encodes the truth rule correctly (`active` +16.83, `available` +16.08) but assigns a large negative weight to note tokens that are constant across every fit row; that unidentifiable offset vanishes under unseen test notes and moves the probability by about +0.50. Choice: the cross head *does* train the needed `active × role` and `rule × role` terms, so capacity was not the blocker — truth-independent terms contribute a constant offset in every quadrant that dominates them, so the yes-minus-no gap never changes sign and raw accuracy stays at chance. The answerability cutoff is not the bottleneck. Both alternatives tested (load scaling, cutoff suppression) were falsified.

The historical Binary negative and Choice indeterminate dispositions are unchanged, no model is qualified or promoted, and no M013a test row was used to select anything. `scripts/validate_future_support.py` lets a future protocol verify eligible-subgroup support *before* final inference. M013/M013a/M013b source is still outside main; crates.io publication and CodeGG promotion remain separate decisions.

The M013b capacity statement above is superseded for the complete two-rule target by the M014 four-quadrant proof: the existing pairwise Choice margin is affine in the two causal bits and cannot represent XOR/XNOR. M014 adds a separately identified compositional Choice architecture; it does not rewrite the M013b/M013a historical measurements.

## M013c qualification-gate hardening (mechanically complete; unmerged)

[M013c](plans/closure/general-decision-model-framework/013c-status.md) is implemented on the `work/plans-sdm-m013c-qualification-gate-hardening` branch and is **conditionally closed**: the gate defects are closed and hosted CI is green on all 10 jobs (run [38109417539](https://github.com/dbowm91/sdm/actions/runs/38109417539), commit `8dd8a21`), with the reviewed main merge still outstanding. It closes the reusable quality-gate defects M013b left behind, with [source audit](docs/m013c-gate-hardening-audit.md) and [implementation plan](plans/implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md).

Four defects are closed. Binary primary and critical decisions now come from the 95% paired-group **interval bounds**, never a point mean: a negative mean with a straddling interval is indeterminate, and a positive mean with a straddling interval cannot qualify. A critical regression requires the preregistered minimum of 50 eligible independent groups, carried as an explicit `minimum_group_support` field cross-validated against the same slice's support gate — n=1 can no longer assert a supported negative. The declared Binary `required_families` and Choice `required_ood_families` are enumerated from the protocol rather than from whatever the report contains, so a missing family is `invalid` instead of silently skipped. And all five declared Choice negative controls are measured separately on the same answerable population, groups and option identities, each with a real paired learned-minus-control interval; `always_answer` is the candidate's own argmax and so is recorded without carrying evidence, while `always_abstain` must genuinely be beaten on answerable accuracy and its perfect no-answer recall is never read as learned answerability.

M013c also found and repaired a **latent bootstrap defect** inherited from M013b: `m013b_evaluator.quantile` indexes its argument as if sorted while `group_bootstrap` passes replicate values in draw order, so a non-degenerate interval through that path was not a true percentile. The frozen M013a analyzer sorts correctly and the affected recorded intervals are degenerate, so **no recorded M013a or M013b result changes** — all three archived outputs still reproduce byte-identically (`411ac091…`, `07fb99f1…`, `3b489c25…`). M013c implements its own sorted-quantile bootstrap and leaves the frozen M013b files untouched; the defect remains live in that module and is registered for its own corrective.

Historical Binary `negative` and Choice `indeterminate` are preserved exactly under the hardened semantics. No model is qualified or promoted, no M013a test row was used to select anything, and crates.io publication and CodeGG promotion remain separate decisions. M013/M013a/M013b/M013c source is still outside main, and **no successor predictive milestone is registered or unblocked** — a successor additionally needs its own corrective for the M013b bootstrap defect plus a prospective freeze of new test groups and numeric thresholds.

## M013d bootstrap repair and source integration

[M013d](plans/implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md) is **conditionally closed** for mechanics and source handoff. It preserves the original pinned reports and model verdicts, with current provenance hashes recorded in its [closure](plans/closure/general-decision-model-framework/013d-status.md). The single main-targeted source PR [#2](https://github.com/dbowm91/sdm/pull/2) is open for review; hosted CI run [38111257896](https://github.com/dbowm91/sdm/actions/runs/38111257896) passed all ten jobs on implementation head `ffe295b`. The source is not yet integrated into main. Binary remains negative, Choice remains indeterminate, no model is qualified, and no CodeGG pin change or crates.io publication is authorized.

## Current milestone: M014 standalone predictive-quality recovery (active implementation)

Source stack M013–M013d **merged** in [PR #2](https://github.com/dbowm91/sdm/pull/2) at `0e6c3cae5911681b18185673a30484a976cb3821`; [merged-main CI 38112863529](https://github.com/dbowm91/sdm/actions/runs/38112863529) passed all ten jobs. Older pre-merge text above is archival context, not current status. M013a still reports Binary negative on text/combined OOD and Choice indeterminate. M014's source-derived representability proof, opt-in Binary mask, and compositional Choice implementation are recorded in [M014 research](docs/m014-model-quality-research.md). The independent synthetic suite, split membership, support, train/dev candidates, and prospective protocol are now frozen in [M014 freeze manifest](docs/m014-freeze-v1.json); its verifier checks SHA-256 inputs and confirms candidate reports did not evaluate test. The one-time final held-out evaluation and closure remain outstanding. M015 general architecture comparison is future work; CodeGG M005 and crates.io legal approvals remain separate.
