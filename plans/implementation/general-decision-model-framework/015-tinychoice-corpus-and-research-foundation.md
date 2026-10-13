# SDM M015 — TinyChoice research protocol and oracle-audited corpus foundation

Status: **ready for implementation** (planning only; not started).
Class: capability / research infrastructure.
Planning baseline: dbowm91/sdm@c048189d7026d723c7da584d7429cb275c714d23 (2026-10-13); re-audit remote main and implementation branch before coding.
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md.
Research: docs/m015-small-model-research.md.
ADRs: ADR-0001 and ADR-0002; CodeGG ADR-0013 governs the external consumer boundary.
Hard predecessor: M014c full integration closed (PR #3, main CI 38426232250 success 11/11); M014b final is consumed/negative and NOT reusable.
External dependency: NONE — no approved CodeGG corpus needed.
Successor: M016 hard depends on an accepted M015 closure; M017 depends on both.

## 1. Objective and experimental scope

Build an independent, bounded, generator-versioned and oracle-checked *training/development* research suite for conditional Choice and abstention. It must support reproducible fixed-rule nuisance OOD, explicitly rule-conditioned compositional transfer, varied candidate sets and leak-safe paired tests without opening a final held-out qualification cohort. Deliver a real experiment harness and data contracts usable by existing models and a later small MLP. Complete infrastructure mechanics and explicit evidence only; **do not qualify any new model**.

Do not use CodeGG conversations, private repositories, model providers, generated human labels, any M013/M014 historical FINAL examples for fitting/tuning, or external network. No new inference architecture, release, pin change or crates.io publication in this milestone.

## 2. Starting evidence and design problems

M011 samples are small (400 examples/task). M013a/M014/M014b are deterministic synthetic conditional tasks with reused templates and high within-family correlation. M014b uses a changed target rule without a new observable rule selector; its old frozen models' negative verdict is not a valid estimate of fixed-rule shift robustness. `sdm-experiment` already supports typed schema contracts, group-aware splits and offline runs; `sdm-data` manages provenance; existing `scripts/validate_future_support.py` checks eligible group counts; the M014a/v2 evaluator is source-hash/freeze bound. Reuse these rather than adding a second leakage or report parser.

Define two orthogonal task tracks:
- **F (fixed conditional):** freeze one mapping Y=f(causal context, candidate semantics, known rule), alter only declared nuisance factors; all nuisance counterfactuals retain exactly the same target and eligible candidates.
- **R (rule-conditioned):** change mappings only with an OBSERVABLE input describing the operative rule (bounded typed categorical/compositional rule descriptor). Train on primitives and supported combinations; structural generalization excludes new compositions but not their component operations. Rule-hidden contradictory-label controls must fail as intentionally unidentifiable, not count as OOD quality loss.

Also maintain `available`/no-answer as a distinct causal factor, not a proxy for option count or family ID.

## 3. Ordered implementation work packages

**A — Specification and oracle.** Add `docs/m015-task-spec-v1.md` (proposed) with causal DAG/target functions, normal form for semantic option roles independent of ID, clearly observable rule selectors, no-answer semantics and exact admissible perturbations. Add `scripts/generate_m015_suite.py` or an equivalent bounded generator, a pure independent oracle/checker (separate implementation from the labeling path) and parser/validator tests. Verify complete truth tables for Boolean/XOR/XNOR and mixed boolean/numeric/categorical cases, including 0/1/2–8 options. A malformed rule descriptor must reject rather than silently default. For 0 candidates answer is always None; two-or-more choice labels must refer to exactly one permitted ID or None.

**B — Data generation.** Introduce several *distinct* rule grammars/families: conjunction/disjunction, exclusive-or and rule-conditioned inversion, bounded numerical thresholds, categorical conjunctions, and a mixed-constraint decision (at least 5 independently described source functions). Create configurable 2k/10k/50k TRAIN-group budgets and disjoint development families; cap generator output size/time/memory after measurement and document any smaller feasible budget. Seeds, case IDs, family IDs, counterfactual pair IDs, provenance, source/oracle fingerprint, membership and split digest must be recorded. Prefer writing large/generated data under `target/m015/`; commit only small reviewable smoke fixtures and immutable generator/protocol definitions. No reused historical final seed/group/row identities.

**C — Experimental design.** Partition by independent task instance/group AND rule template/near-duplicate/counterfactual lineage, not just row. Pair perturbations that should preserve labels; separately pair causal flips that SHOULD alter oracle targets. Introduce ID rename/order reversal, rare categories, uninformative/constant notes, unknown token, shifted load, valid optional-field missingness and variable candidate sizes. Predefine supported/unsupported schema cases. Verify test-only tokens and family IDs cannot enter train encoder fitting. Hold back the *future M017 final cohort*: M015 builds train/dev and a frozen *family-design specification* only; DO NOT generate/inspect M017 final cases or labels.

**D — Development-only harness.** Integrate with `sdm-experiment` and `sdm-eval` (or scripts constrained to their stable manifests). Publish named CLI commands for generator→dataset/split verification→existing linear/compositional dev scoring→metrics report. Baselines use identical typed features, candidate universe and membership. Emit group-level answerable accuracy, no-answer recall, Brier/log loss where defined, calibration bins, group CI and correct-on-both causal counterfactuals, nuisance invariance, exact option ID/order equivalence. Dev-only model/threshold selection; final test never invoked.

**E — Falsification and protection.** Tests must detect swapped/inverted oracle labels, pair changes in undeclared fields, leakage group crossing partitions, reused historical IDs, candidate-role leakage via option ID/order, low support, withheld-family encoder fitting, and an impossible rule-hidden mapping. Label permutation/context ablation should fail expected learning tests or be reported as powerless; never declare them passing by construction. Add source-controlled smoke fixtures, deterministic regeneration/idempotence, resource and time bounds; CI may regenerate train/dev suites but must not run an M017 FINAL.

**F — Documentation and evidence.** Record per-family/group counts, hashes, generator configuration, observed oracle disagreement (must be zero), baseline dev metrics and limitations in `docs/m015-dev-results.md`; update README, typed-task docs and plan registry on closure. The existing M014b negative evidence stays negative, unchanged.

## 4. Interfaces, storage, restart and safety

Preserve existing v1/typed schemas and runtime limits; any extra rule-feature contract is additive and explicitly versioned. No new learned model artifact in M015. Accept only explicit local paths. Synthetic-only redistributable provenance required; no implicit repo scan. Generator uses bounded batch/streaming writes and refuses overwrite of a different digest; stage/fsync/atomic finalize for reports. A cancelled build leaves either last complete versioned train/dev files or no accepted outputs, and never alters historical artifacts. No evaluation may infer executable instructions or authorize candidates. Do not add Python to the runtime dependency graph; generation scripts may use Python stdlib.

## 5. Verification and acceptance

Verify with actual commands and capture outputs:
```sh
cargo fmt --all -- --check
cargo test --workspace --all-features --locked
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo check -p sdm-runtime --locked
cargo tree -p sdm-runtime --locked
cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked
cargo run -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json
python3 -m unittest discover -s scripts
```
Add focused generator/oracle/partition tests and a clean-room reproducible CLI E2E test (exact commands in closure). Report Rust 1.89 job and 3-host hosted CI where available. Do not invent a performance result or successful run.

**Acceptance gates (all required):** M15-1 source-defined causal and observable-rule spec with independent oracle; M15-2 >=5 distinct decision functions, 0/1/2–8 choice cardinalities and explicit no-answer; M15-3 pair and group provenance/no cross-split leakage, deterministic independent seeds and fingerprinted manifests; M15-4 separate fixed-rule vs conditional-rule evaluation semantics and validated unidentifiable control; M15-5 repeatable train/dev-only path with existing baseline and complete group-level diagnostics; M15-6 negative/identity/metamorphic controls detect seeded faults; M15-7 bounded generation, offline/no-telemetry/default runtime isolation, unchanged legacy compatibility; M15-8 current CI and closure evidence, with historical FINAL unmodified. M016 cannot start if any mandatory gate is unproven.

**Stop conditions:** A label changes under a declared nuisance-only perturbation; the target function changes without a corresponding observable rule; any group/near-duplicate leakage; a role or rule can be decoded from arbitrary option IDs/family IDs alone; train pipeline needs hidden final results; the oracle and generator share an unchecked defect; data construction makes resource use unbounded; or an old frozen input is modified.

## 6. Closure record

Write `plans/closure/general-decision-model-framework/015-status.md` with implementation SHA/PR, host/CI evidence, requirement-to-evidence matrix M15-1..8, exact source/protocol/fixture/manifest hashes, independent oracle tests, split/group support, dev-only outputs, rejected alternatives, performance/memory, reproducibility, historical input integrity, API/security/compatibility and honest limitations. Do not mark M016 ready until these are accepted and source is integrated into main.
