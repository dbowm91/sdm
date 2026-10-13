# M015 research — bounded structured decision learning without a CodeGG corpus

Status: research basis for M015–M017 planning; NOT experimental qualification.
Date: 2026-10-13.
Source baseline: dbowm91/sdm@c048189d7026d723c7da584d7429cb275c714d23.
Authority: ADR-0001, ADR-0002, CodeGG ADR-0013; plans/003-planning-process.md.

## Evidence ledger and limits

The existing seven-crate framework has validated typed Binary/Choice/Score/Rank, provenance-aware group splits, offline artifacts and an inference-only runtime. M014c closed its CI/evaluation/three-host canary-parity correction (PR #3, 11-job green main). M013a has 1,532 paired groups/task; M014's synthetic suite has 1,200 groups/task; M014b has 570 groups/task (two rows/group) with 120 generator-designated train groups. M011 uses 400 rows/task; the CodeGG compatibility suite has 12 requests/11 valid executions and is NOT a predictive corpus. Historical final cohorts are exposed and must never become new validation/test or training-selection data. These are deterministic, highly correlated synthetic examples, NOT thousands of independent real-world concepts. The CodeGG corpus required for M005 remains unavailable.

M014b's prior frozen candidates trained on AND/XOR targets were evaluated without refit against AND-XOR/XNOR functions. Failure there demonstrates failure of unconditioned rule transfer, not necessarily a fixed-rule distribution-shift defect or insufficient compositional capacity. For identical observed x with a changed unobserved target function, f_train(x) != f_test(x) is unidentifiable. The next experiment MUST isolate fixed-rule robustness from explicitly rule-conditioned structural generalization, avoid post-hoc changing a held-out task, and report them as separate hypotheses.

The current Choice training obtains abstention by development-set thresholding; Choice(None) does not supervise a separately learned answerability head. Candidate identities and order are arbitrary, caller-controlled, and must not become labels or hidden policy. Existing compositional Choice supports sparse context-context-option interactions but does not learn a reusable low-dimensional nonlinear representation.

## Research question and target

Can a small, completely offline, native-CPU conditional Choice scorer learn task/candidate interactions while retaining calibrated, separately measured answerability? Compare existing linear and compositional heads with a bounded MLP and a credible shallow-tree baseline on the SAME typed feature schemas, candidate universes, source rules, training groups, and dev/test protocol. Do NOT preselect the winner by architecture name or parameter count. Main engineering target is a new optional `sdm-typed-choice-tinymlp-v1` with 32/64-hidden-unit exploratory variants and a provisional 5,000–50,000 trainable-parameter budget (not a performance claim); reference FP32 weights 20–200 KB exclusive of encoder/manifest. Existing hard resource caps still govern the complete artifact.

For answerable observations, learn conditional logits s_i = f_theta(context, candidate_i) with a shared, order-equivariant candidate scorer. A separate answerability head g_phi(context, permutation-invariant candidate summary) estimates a = P(any valid option). Use conditional softmax for P(i | answerable) and combine P(i) = a P(i | answerable), P(None)=1-a. Separate label/feature handling and calibration; no synthetic "none" candidate. Zero-candidate and unsupported-task behavior MUST be well-defined and fail safely.

## Required falsification matrix

1. **Fixed-rule nuisance generalization:** constant P(y | causal fields) with shifted irrelevant text, numeric load, category rarity, missing optional fields (valid only), candidate identity/order. Train/dev on new distinct groups; critical negative shifts are label-preserving and independently supported.
2. **Rule-conditioned structural generalization:** explicitly expose rule identity/operation (or a permitted rule descriptor and sufficient examples) when changing the target mapping; train on primitives and test novel compositions within declared support. No impossible no-rule XOR-to-XNOR test may be counted as a learned-model failure on nuisance robustness.
3. **Answerability:** answerable/nonanswerable groups, 0/1/2–8 candidates, false abstentions vs correct abstentions, no-answer prevalence shifts, correctness conditional on choosing an option.
4. **Baselines/controls:** existing linear/legacy/compositional heads, deterministic oracle (upper bound on defined synthetic tasks), majority/prior, fixed abstain, label permutation, context shuffle, candidate-only, rule-hidden impossibility control, and a shallow boosted-tree comparison (offline optional dependency isolated from runtime). Context/order invariance and ID independence require metamorphic tests.
5. **Statistics:** independent leakage/counterfactual groups, not per-row independence; paired differences, family-specific support/95% group CIs, multiple-comparison controls, proper scoring and calibration, coverage versus selective risk and both-correct counterfactual pairs. Mechanical/quality/deployment verdicts remain distinct.

Prior evidence: Grinsztajn/Oyallon/Varoquaux, *Why do tree-based models still outperform deep learning on tabular data?* (https://arxiv.org/abs/2207.08815); McElfresh et al., *When Do Neural Nets Outperform Boosted Trees on Tabular Data?* (https://openreview.net/forum?id=g62mtufBVA). These support an honest tree/MLP comparison on modest tabular data, not a claim that either wins for SDM.

## Bounded experimental program

M015 constructs an oracle-audited generator and train/dev-only evaluation harness with source-defined causal rules. Start with 2k/10k/50k independently seeded *groups* as configurable learning-curve budgets, subject to measured size/time/RSS caps; never treat duplicated pair rows as independent. Produce separated fixed-rule and explicitly rule-conditioned tasks, OOD nomenclature, meta-validation, and a sequestered final-family design without observing final examples/labels. Outputs are reproducible synthetic fixtures or under target/, not implied CodeGG samples.

M016 implements an optional native-Rust compact Choice/answerability model, baselines/ablations and calibrated dev comparisons. All candidate models and hyperparameters must be selected solely on train/dev; compare dev suites with matching preprocessing/candidate IDs and record any missing external tree benchmark honestly. A trained tree is not mandatory for runtime deployment and must not pull Python or external ML dependencies into sdm-runtime.

M017 separately freezes a wholly new prospective final cohort *after* M016 closes and candidate bytes are fixed; records numeric thresholds, full model baselines, independent eligible-group support and source/evaluator hashes, uses a two-phase non-self-referential freeze binding, verifies CI before one-time final inference, and retains original final report bytes in durable evidence. Results may be positive, negative or indeterminate. No final-test reuse, no CodeGG model promotion, crates.io publication, provider calls, hidden training corpus import, or automatic collection.

## Proposed decision gates before implementing an architecture

- Demonstrate mathematical/finite-weight representation of XOR/XNOR WITH explicit rule input, no-answer and arbitrary candidate permutations; include a truth-table control whose labels do not identify IDs.
- Model-dependent output must actually change when a causal feature changes; raw score ordering and final abstention must be reported separately.
- Predeclare training resource ceilings and check optimizer gradient finite differences, zero/one-option behavior, nonfinite values, malformed artifacts and cutoff boundaries before any new held-out final is consumed.
- If the small MLP fails an easy training/dev representability task, diagnose optimization and schema before scaling parameter count. If a shallow tree wins on independent development tasks, report it and keep tree integration as a separate decision rather than hiding it.

## Ownership and compatibility

Rust MSRV 1.89; offline CPU training; runtime independent of training and Python, network/accelerator SDKs; Linux x86_64/Linux ARM64/macOS ARM64 parity based on SAME committed artifact bytes. Additive architecture identifier only; unchanged legacy SHA/format, CodeGG 12/11 compatibility, original M011/M013/M014 files and CodeGG pin. SDM supplies scores only over caller-supplied candidates; CodeGG remains owner of authorization, shortlist admission, consent, fallback and live validation.
