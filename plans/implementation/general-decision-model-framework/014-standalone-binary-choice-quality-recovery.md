# SDM M014 — Standalone Binary/Choice Predictive-Quality Recovery

Status: **ready** (planning-only implementation handoff; no model or prospective final test run)
Primary class: capability / prospective qualification
Workstream: general-decision-model-framework
Baseline: `dbowm91/sdm@0e6c3cae5911681b18185673a30484a976cb3821` (`main`, PR #2 merged 2026-10-11)
Planning branch: `work/plans-sdm-m014-standalone-quality-recovery`
Governance: `plans/003-planning-process.md`; accepted ADR-0001 and ADR-0002; CodeGG ADR-0013 remains external ownership authority
Hard predecessors: M013–M013d source integrated into main, [merged-main CI 38112863529](https://github.com/dbowm91/sdm/actions/runs/38112863529) passed ALL 10 jobs; historical qualifications remain Binary negative and Choice indeterminate
External dependencies: NONE (no CodeGG corpus, external model service or publisher approval)
Review material: `docs/m014-model-quality-research.md`, M013a/M013b/M013c closures and `docs/m013a-protocol-v1.md`
Closure: `plans/closure/general-decision-model-framework/014-status.md`

## 1. Outcome, success definition, and non-goals

Deliver a narrowly bounded, independently testable Binary and Choice quality correction in the STANDALONE SDM framework. Fix training-invariant text nuisance behavior without loss of causal Binary signal; prove/disprove the *full* M013a Choice rule's representability under pairwise features and, if needed, add the smallest bounded compositional context/option interaction. Perform ONE newly preregistered final held-out evaluation using the hardened M013c gates (plus M014-specific prospective thresholds) and report positive, negative or indeterminate per task without relabeling unfavorable evidence.

**Important finding missed in prior closure:** M013a has two context bits/fields with an XOR/XNOR-style joint rule: for available cases, `yes = active` under `rule_a`, `yes = !active` under `rule_b`. Current `typed-choice-cross` supports context coordinate × candidate coordinate, but each option copies both `active` and `rule_family` from context and differs only by option `task_kind`. Thus a yes-minus-no logit gap is, subject to exact encoded design, an ADDITIVE function of `active` and `rule_family` and lacks the essential joint `active × rule_family × option_role` (or an equivalent context conjunction × option role). A positive representability demonstration for `active × option_role` with rule fixed, present in M013, does NOT establish representability for BOTH rule families. This is a *source-derived mathematical hypothesis*, not an already-tested empirical diagnosis: **prove it with a full truth-table and rank/separability test before any optimizer work**. If the hypothesis is falsified by another feature actually encoding the conjunction, report that and use a narrower optimizer-only remedy, not the proposed architecture by default.

M014 is NOT a generic tiny-MLP/trees/transformer platform, not a CodeGG adapter, not a crate publication or model-promotion milestone. Broader model-family benchmarking should remain an optional M015 successor.

## 2. Baseline concrete evidence and mechanics

### Binary
M013b diagnosis: Boolean truth weights around +16.83 (`active`) and +16.08 (`available`), but three fit-constant text tokens have weights -4.4812 each (sum -13.4437), creating an unidentifiable hidden bias. All three tokens occur in 100% of 1,888 training rows. Removing them under unseen-note shift raises predicted p by ~+0.497 despite unchanged label; load-only perturbation is ~-1.43e-5. On valid M013a, Binary Brier improvement vs constant prior was +0.2115 ID-a, +0.2280 ID-b, +0.2207 load, **-0.2696 text and -0.2699 combined**. Changing training regularization alone may or may not cure the exact confounding; require an explicit train-constant-feature ablation and provenance.

### Choice
M013a: legacy and `typed-choice-cross` answerable accuracy each 0.50, paired effect 0, raw argmax not suppressed by abstention, and zero correct-on-both target-flip counterfactual pairs. M013b measured truth-dependent terms but a -0.9219 constant interaction offset dominated. The source `scripts/generate_m013a_quality_suite.py` defines active/rule reversal (`semantic_yes = active if rule_a else !active`); candidate fields otherwise copied from context except role/category. `crates/sdm-experiment/src/lib.rs::prepare_typed_examples` builds concatenated `[context,item,context[c]*item[o]]`; `bounded_nontext_cross_pairs` expands all nontext cross terms but NOT context-context conjunction × option-role. Shared-only option features cancel from the two-option logit gap. Therefore both lack of training and lack of function class capability must be separated before selecting a fix.

M013c provides supported CI-bound gates, complete declared slice/control checks, and corrected 10,000-replicate paired group bootstrap. `scripts/validate_future_support.py` proves per-metric eligible groups. M013d fixed the legacy unsorted percentile. Existing trained artifacts and all M011/M013/M013a historical data and report hashes are immutable.

## 3. Required architecture and ownership constraints

- Rust MSRV 1.89; CPU-only, fully offline, Mac Apple Silicon training suitable for ~24 GiB RAM, Linux x64/ARM64 and macOS ARM64 runtime.
- Preserve v1 LinearArtifact, v2 typed `sdm-typed-task-v1`, `sdm-typed-choice-cross-v1` artifact semantics and hashes; new Choice representation MUST be additive architecture ID (example `sdm-typed-choice-compositional-v1`) with validated declared coordinate interaction list, architecture-specific dimension/term cap, and strict fingerprint. Do not reinterpret existing cross weights.
- Preserve 16 MiB v2 artifact and 4,096 cross-term limit (or stricter explicit cap), 256 candidates / 128 Choice options and documented feature/input ceilings; reject overflow/nonfinite/malformed/duplicate IDs. Never expand dense text vocabulary cubically. Prefer a declared, sparse subset of train-registered **nontext context-context pairs × provided option coordinates**; no literal reliance on schema names `active`/`rule_family`/`yes`/`no` in generic inference. If actual validated representability is established via an even smaller equivalent scheme, prefer that.
- For Binary, avoid changing shared `FittedFeatureEncoderV2` semantics across all heads. Train-only feature variation/mask, intercept and regularization can be implemented inside a versioned opt-in training policy with existing v2 inference weights explicitly zeroed for masked dimensions. If an inference-time feature transformation/mask is needed, use a NEW validated artifact policy/payload; do NOT silently reinterpret old artifacts.
- Explicit caller option IDs are never synthesized, duplicated, extended or permission-granted. Application owns eligibility, consent, fallback, authorization, actuation. SDM is a scoring/research library.
- No new network/model downloads/GPU dependencies, no implicit local corpus scan or CodeGG data collection. Named synthetic inputs/provenance only.

## 4. Ordered implementation (must respect the freeze order)

### A. Prove representability with 4-quadrant mathematical and executable tests — before altering trainer

A1. Construct the COMPLETE answerable truth table at `rule_a/rule_b × active=false/true × role=yes/no` plus `available=false` no-answer controls. Include label-flipping pairs with only causal `active` changed, two option roles present, option order reversed and arbitrary role-to-option-ID permutation. Confirm original feature encoding and each candidate's actual nontext coordinates on all rows. Show and record the yes-minus-no logit `Δ(a,r)`.

A2. For the legacy and pairwise-cross heads, analytically derive whether `Δ(a,r)=c+u*a+v*r` (or an equivalent affine form) over the given frozen schema. Test using a design matrix or directly solve linear feasibility (strict sign inequalities for all four target quadrants) with a deterministic exact or bounded numeric procedure. Since XOR over two bits is not linearly separable, show the contradiction if the reduced design holds. Countercheck with a manually specified four-row target and fixed arbitrary weights; no optimizer/hyperparameter selection can overcome an unrepresentable truth function. A model achieving one-rule active flip does not suffice.

A3. Test proposed minimal expressible representation: `active × rule_b × candidate_role` or general sparse `(context_i*context_j)*option_k` with a declared coordinate map. Demonstrate a fixed set of finite weights yielding correct top-1 on all four quadrants and correct no-answer using the separate answerability head. Assert invariant to option ID renaming/reordering, schema permutation and identities; labels derived from SEMANTIC role, not input order. Both legacy heads still behave byte/decision identically.

A4. Make an explicit decision record in `docs/m014-model-quality-research.md` (or dated implementation evidence) listing proven capacity limitations vs optimizer-specific faults. If old head CAN fit all rows, do not introduce new architecture; select the smaller train/dev-only optimizer correction.

### B. Binary train-only nuisance mitigation; bounded optimization experiment

B1. Add a train-only coordinate variation audit for the actual Binary context feature vector. Explicitly detect near/exact constant encoded fields across TRAIN groups and distinguish intercept-equivalent nuisance coordinates from truly varying signal, absent/missing optional values, categories, sparse text and context/candidate projections. Never fit the mask using dev or test, and never use a TEST family ID/label to choose it. Record masked/retained coordinates and projection/encoder fingerprints; zero any intentionally masked output weight so runtime serialization needs no new feature semantics when possible.

B2. Candidate policies (finite, fixed search budget): legacy SGD as control; legacy with explicit unpenalized intercept and exact constant-feature zeroing; constant-mask + dev-selected L2 weight decay; optionally label-preserving train-time nuisance augmentation ONLY if justified on exploratory train/dev and preregistered before final. Bound combinations (e.g. 3 remedies × at most 3 L2 values × at most 3 fixed seeds, max 27 fits per task) and report ALL train/dev candidates, not just winner. No test-selected hyperparameters. No broad new optimizer library or fitting of target rule from strings.

B3. Compare train/dev one-factor note-only and load-only nuisance perturbation under invariant label, train/dev calibration, per-coordinate contributions and shifted/nonsifted residuals. Demonstrate the corrected candidate's responsiveness to causal field flips, plus lack of large text-only probability swings on a constructed minimal suite. Do not use M013a held-out input/label sets for candidate choice.

B4. Make the policy/config explicit in experiment manifest (version, seed, feature variation threshold, selected coordinates, L2, intercept convention and train fingerprint); preserve old experiment defaults and reproducibility. Detect overflow, exploding logits, invalid gradient update, too-large epoch/search budgets; negative or invalid fits should be visible and not silently returned as accepted artifacts.

### C. Choice minimal compositional representation + optimizer ablations

C1. Only if A proves a representability gap, add the smallest bounded, opt-in `typed-choice-compositional` architecture for a declared sparse nontext context conjunction followed by multiplication by a candidate feature (or equivalent deterministic factorization). Limit/validate feature coordinate triples, record order, refuse out-of-bound or repeated term indices, and exclude text vocabulary from multilinear expansion. Validate new artifact SHA, shape, architecture, feature schema and training fingerprint in `sdm-runtime`; training and inference construct exact identical feature vectors.

C2. Verify the complete XOR/XNOR truth table with manually set test weights BEFORE training, then train on independent toy GROUPS (not M013a test groups) using bounded deterministic seeds and measure raw gap sign by quadrant and target-correctness on both counterfactual sides. Prove optimizer gradient matches finite differences on new features and that train loss descends. Compare old cross, new compositional head with identical SGD, and new head with bounded dev-chosen L2/early stop or weight centering. If the new head is mechanically expressible yet fails training, stop for root-cause diagnosis before prospective final evaluation; do not burn the final holdout.

C3. Keep answerability training, dev threshold, option conditional probabilities and final decisions separately visible. Check `Choice(None)` and 0/1/2+ option edge cases against the existing schema bounds. For no-answer cases, no synthetic sentinel option may be introduced. Metric report includes answerable conditional accuracy, log loss/Brier, answerability AUROC/AP, no-answer recall, false abstentions, coverage, selective risk/AURC, confidence distributions and test-family counts.

### D. Independently seal NEW M014 dataset and qualification protocol — BEFORE final inference

D1. Create NEW `m014` synthetic generator version, source-defined structural truth functions and controlled counterfactual cases that do NOT copy M013a's already-observed test IDs/rows/seed or simply resample its 4-quadrant benchmark. Include at least two independently defined compositional task families, differing option-ID and ordering policies, multiple label-preserving nuisance vocabularies/ranges, and answerable/no-answer examples. Distinguish nuisance-only (conditional label unchanged), changed-rule/structural OOD (target conditional genuinely changes, may be indeterminate), and unrelated unknown-vocabulary shifts. Declare which slices are **critical** and why.

D2. Generator must guarantee each counterfactual pair differs ONLY in a declared causal field; pairs remain in ONE leakage group and ONE split, no overlap between train/dev/test groups or frozen older data. Data provenance records generator source SHA, license=MIT for original generated data, no user data, ground-truth rule definition, seed, schema digest and group assignments. Enforce train-only vocabulary/encoder fit.

D3. **Prevent the M013a support error at generation time:** for each primary/critical family, at least 50 INDEPENDENT *eligible answerable* groups for Choice option accuracy, 20 no-answer groups for recall where applicable, and 50 independent groups for Binary Brier/supported regression; recommend >=80/90 groups per required Choice family where answerable fraction ~2/3. Give exact group counts in a machine-readable pre-freeze report. Invoke existing `scripts/validate_future_support.py` on the actual new frozen split; refuse final execution if any required slice fails. Grouped pairs count once in uncertainty.

D4. Prepare the prospective protocol and registry entry *before any final TEST outputs*: exact candidate set, finite search budget, dev-selection rule and comparison budget, frozen baseline weights/configs, one primary metric per task, OOD critical slices, full negative controls, numeric confidence thresholds and noninferiority margins, 10,000 grouped percentile bootstrap replicates and deterministic seed, multiplicity policy across primary claims, calibration selection, minimum eligible group counts, fixed option/candidate universe, counterfactual correct-on-both gate, no-answer recall/coverage floor, latency/memory/artifact bounds, and positive/negative/indeterminate precedence. No `null` positive threshold can be interpreted as pass; conservative indeterminate is valid if cannot estimate reliably.

D5. Suggested prospective qualifying GATES to ratify BEFORE freeze:
- Binary: each designated critical text-only/combined *label-preserving* shift must have 95% (multiplicity-adjusted if needed) paired grouped CI **lower > 0** for Brier improvement versus frozen train-prior constant AND versus frozen incumbent head; on each ID slice new-vs-incumbent Brier improvement CI lower >= -0.02 (predeclared noninferiority margin). Must pass label-preserving invariance stress case and sufficient support. If an intended effect gate is infeasible at pre-freeze, mark indeterminate and document rather than weakening it after observation.
- Choice: on all declared primary answerable ID/critical label-preserving OOD slices, positive paired grouped CI lower > 0 versus the frozen legacy/current-cross head and against the strongest **discriminating** declared control on the same eligible groups. A nontrivial counterfactual cohort must reach >=80% pairs with BOTH correct target decisions (and lower 95% bound >=70%); zero score sensitivity alone never passes. Numeric no-answer recall and coverage floors must be frozen (proposed >=0.80 recall point with lower interval >=0.65, and >=0.60 coverage on all answerable test rows); if support/metric cannot justify floors, qualify indeterminate, not positive. `always_abstain` and `always_answer` cannot qualify.
- State exact per-family critical gate priority and multiple-testing adjustment method (e.g. Holm/Bonferroni across the nominated two-task family claims) in the frozen document; explicitly distinguish estimator sign/uncertainty direction. Do NOT treat these illustrative suggested numbers as already-preregistered, and do not change them after test labels become visible.

D6. Freeze generator/config/data or deterministic generation recipe, split membership and integrity digests, protocol, gate-manifest, candidate/model training code and planned final execution under a pinned commit. Preserve the public SHA and separate CLOSED test-member listing. Any modifications to models/gates after test observation require a NEW later independent test and named future milestone. Do NOT mutate the committed M011/M013/M013a fixtures, reports or experiment digests.

D7. To avoid another +2 million lines of frozen JSON: commit deterministic generator, small sample fixtures, exact split/test membership manifests and source/config hashes, plus hash-verified generated corpus (e.g. compressed content-addressed artifact or CI-generated `target/` data); ensure offline reproducibility from tracked sources and all hash proofs on each host. Never claim that a recipe hash alone proves the output: CI must regenerate and verify full per-dataset SHA. Freeze manifests even when bulk JSON is untracked. No network fetches or downloaded private data.

### E. Single final test, honest qualification, resource tests, closure

E1. After A–D pass and prospective freeze SHA is committed, load old/frozen candidates and NEW selected candidates, run the M014 final test once; evaluate IDENTICAL groups/option IDs/slice definitions. Use M013c hardening and fixed M013d sorted bootstrap, report detailed support and CI for every required family, all named controls and group counterfactual correctness. No test-based model selection; no extra holds/re-sampling until it passes.

E2. Dispositions independently for Binary and Choice: `positive` only when ALL frozen primary/OOD/control/support/counterfactual/abstention gates pass; `negative` for preregistered adequately supported critical failure; otherwise `indeterminate`. Mechanical/compatibility acceptance is separate from quality. Positive synthetic result is a *synthetic task qualification*, NOT real-world generalization and NOT CodeGG promotion. Negative/indeterminate is an HONEST accepted experiment outcome, but not positive model-quality closure.

E3. Test CPU load, cold load, artifact bytes and p50/p95 inference for Binary and Choice, bounded 1/2/16/64/128 option populations within task semantics; report memory and comparison to M012/M013a on same host/compiler rather than claiming cross-host speed deltas. Check malformed artifact, schema permutation, unsupported payload, duplicate IDs, over-budget interactions, nonfinite values, corrupted digests and old artifacts. **Same new trained artifact** must load and yield equivalent decisions on Linux x86_64, Linux ARM64 and Apple Silicon. Neither runtime graph nor consumer API may import trainer, network, GPU dependencies.

E4. Keep full workspace fmt/test/Clippy/MSRV and package/staged consumer/third-party license audit; add small targeted A/B/C unit tests and one hash-verified M014 generator/qualification CI job, avoiding repeated multi-million-line source commits. Preserve M011/M013/M013a CI checks as frozen mechanical regressions.

E5. Write exact closure at `plans/closure/general-decision-model-framework/014-status.md`: code SHA, initial source/freeze SHA and SHA of the first test observation, generator/split/protocol/test fingerprint, all pre-registered gates with PASS/FAIL/INSUFFICIENT SUPPORT, primary/OOD CIs, sample and GROUP counts, old/new comparator, truth-table representability proof, per-policy train/dev curves and budget, cross-host artifact tests, memory/latency, privacy/security/compatibility/manifest diffs, output hash ledger and actual CI URLs. Update plans/registry.md only AFTER results. A review PR is distinct from a merged main source; no branch auto-merge, tag, publish or downstream pin.

## 5. Failure, cancellation, restart and rollback

- Frozen files are read-only; artifacts/reports written to unique `target/m014/` paths via temporary write + fsync/atomic rename; refuse overwrite of accepted prior output. Crash/interrupt leaves no accepted partial artifact, a prior accepted report remains intact. Resuming permitted only with identical code, train/dev/test IDs, protocol and model/artifact SHA; otherwise new run identity.
- If A finds old head already representable, stop new-architecture work, document proof and narrow to optimizer improvement. If C fails exact truth-table or finite-difference/optimizer positive control on exploratory data, STOP before final TEST. If D finds insufficient eligible support or nonempty split intersections, STOP before freeze/final inference. If E yields negative/indeterminate, do NOT retune against it. If CI fails malformed/inference/security tests or old ABI, STOP/rollback new architecture without modifying prior artifact dispatch.
- Do not hide missing test families, change gates post-hoc, select best model using held-out test results, invent missing research data, or loosen CodeGG's application-owned safety boundary.

## 6. Verification and explicit acceptance gates

Run and record actual commands/results (not claims of current plan):
- `cargo fmt --all -- --check`
- `cargo test --workspace --all-features --locked`
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`
- `cargo check -p sdm-runtime --locked`; `cargo tree -p sdm-runtime --locked`
- `cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked`
- `cargo run -q -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json`
- `python3 -m unittest discover -s scripts -p 'test_m013b_*.py'`, analogous M013c and M013d existing tests
- New `test_m014_*.py` (minimum constructed truth-table separation, train-constant detection, group support, freeze/negative-control/adversarial gates; exact names when implemented)
- `python3 scripts/validate_future_support.py --dataset <new-dataset> --split <new-split> --task choice --required-family <each-family> ...` and analogous Binary, **before** final test
- New pinned offline generator replay and SHA-check command, split/label mutation anti-leakage tests, inference artifact portability, and hosted 10-job matrix including Rust 1.89 and three target platforms

Gates:
- G1 old/current Choice exact 4-quadrant representability proposition proven/falsified **before** candidate design
- G2 Binary nuisance failure demonstrably addressed on train/dev with fit-only preprocessing/policy, no change to legacy encoder semantics
- G3 Choice candidate manually scores full compositional truth table and trains with validated gradients on toy groups, or documented optimizer-only alternative when A refutes gap
- G4 old artifacts and candidate identity/authority invariants preserved; new artifact exact validation/rejection, CPU bounds
- G5 new source/data/split/protocol frozen and per-eligible-slice group counts certified before first TEST observation
- G6 test observed once; all mandatory gates/negative controls/intervals report actual values; positive requires ALL proposed *frozen* thresholds, else accurately negative/indeterminate
- G7 three-host, MSRV, standalone consumer, package/license and runtime graph tests pass on actual implementation
- G8 group counts and confidence intervals correct, old historical fingerprints intact; output has atomic recovery/rollback proofs
- G9 docs/registry reflect actual branch CI and qualification result, not a synthetic performance claim for CodeGG
- G10 no implicit external data, no network or publisher/deployment authority

Mechanical acceptance: G1–G5 and G7–G10; quality acceptance separately based on G6. If G6 quality fails, record negative/indeterminate instead of creating a train-again loop on the same cohort.

## 7. Successor and publication boundary

M014 supplies task-specific model-quality corrective evidence only. M015 generalized decision-model architecture comparisons (bounded MLP, low-rank interactions, trees) are research/soft successors, NOT prerequisites and NOT registered ready by this plan. An optional release/publication track needs its own human/legal approval; CodeGG M005 corpus and consumer policy approval are independent and do not block standalone SDM training/evaluation experiments.
