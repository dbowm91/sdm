# M014 research — Binary nuisance stability and Choice compositional representability

Status: planning research and falsifiable hypotheses (NOT a held-out result).
Baseline: dbowm91/sdm@0e6c3cae5911681b18185673a30484a976cb3821, PR #2 merge, 10-job main CI 38112863529 passed.
Milestone: plans/implementation/general-decision-model-framework/014-standalone-binary-choice-quality-recovery.md

## 1. Source audit and critical new Choice hypothesis

`scripts/generate_m013a_quality_suite.py` sets `semantic_yes = active if rule == "rule_a" else not active` on available cases, with both candidates copying active, rule_family, load, available and note from context, apart from candidate task_kind (yes/no). That is a **two-bit XOR/XNOR** rule. The current feature builder `crates/sdm-experiment/src/lib.rs::prepare_typed_examples` builds `[context,item,(context_i*item_j)]` on the full nontext coordinate pair set. Let `r` be the rule bit, `a` active and `o` candidate role. In the difference `score(yes)-score(no)`, all terms depending only on context cancel; candidate shared-feature differences are zero; all existing cross products involving context and the DIFFERING role coordinate are at most linear in `a` and `r`. Terms like `context.active*item.rule` and `context.rule*item.active` occur but are shared between yes/no candidates, so they cancel too.

Under that projection, the remaining difference is of form `Δ(a,r)=α+βa+γr`, which CANNOT be positive for both (a=0,r=b) and (a=1,r=a) while negative for both opposite quadrants. Adding `a*r*o`, or equivalently a **context conjunction (a*r) then option interaction**, makes this representable. This challenges M013b's "capacity was not blocker" claim, which examined only the trained main effects and existing declared terms. The M013 unit positive control covers active×role with rule fixed, insufficient for the full 4-quadrant target.

A precise rank/separability test on the actual encoded design matrix should adjudicate; if some nonobvious candidate-coordinate difference creates the conjunction, report the counterexample and skip needless architecture work. This is not permission to tune on M013a heldout: use manually constructed truth tables and training/dev-only probes.

## 2. Binary nuisance diagnosis

`plans/closure/general-decision-model-framework/013b-status.md` isolates three always-on training tokens `note~routine`, `note~service`, `note~record`, each with weight ~-4.4812, sum -13.4437. All are present in 100% of train examples; their nonidentifiability relative to intercept allows shifted vocabularies to remove a hidden offset. Note-only perturbation changes probability ~+0.4968 despite unchanged target; load-only perturbation is -1.43e-5. A train-only zero-variance feature mask and explicit unpenalized intercept is the first low-cost test. Regularization and dev-only early stopping are next, but regularization ALONE is not a causal guarantee and should be compared with negative controls. The current shared `FittedFeatureEncoderV2` should not be globally rewritten because previous v2 artifacts require it unchanged.

Literature: zero-variance filtering is a standard unsupervised train-fit procedure (https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.VarianceThreshold.html). For group shifts, Sagawa et al.'s group-DRO work emphasizes regularization and worst-group evaluation (https://arxiv.org/abs/1911.08731). Neither is evidence that a particular SDM candidate succeeds.

## 3. Choice representation, optimization and abstention

Degree-2 interaction-only polynomial features can solve XOR on two Boolean predictors only by including their conjunction (https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.PolynomialFeatures). With candidate-dependent scoring, a context-context conjunction must also influence a DIFFERING candidate coordinate to flip the option ordering; simple context-only conjunction cancels between options. Avoid an unbounded full D^3 tensor: use explicitly registered nontext triples and strict <=4096 interaction terms and <=16MiB artifact.

Then compare feature capacity separately from SGD convergence, weight/init/regularization and dev threshold. M013b showed final argmax equals raw argmax accuracy (0.50), so retuning the no-answer threshold alone will not fix ranking. However no-answer recall under shift remains a separate quality requirement and should be measured by coverage/selective risk rather than conflated with answerable option accuracy. Selective classification under distribution shift recommends explicit risk-versus-coverage assessment (https://pmc.ncbi.nlm.nih.gov/articles/PMC12470254/).

## 4. Dataset integrity, statistics and publication boundary

M013a OOD families contained 67/67/66 total groups but only 44/44/45 answerable groups, below the 50-group primary minimum. `scripts/validate_future_support.py` now checks support in the metric-eligible population; its result must be frozen BEFORE unseen test inference. Pair members need same leakage group, same nuisance and identity/option ordering, only declared causal field changes. Train/dev/test must have disjoint groups; test-only vocabulary cannot enter encoder fitting.

Reuse the M013c CI-bound, full-required-family and named-control evaluator and M013d sorted quantile, but register NEW prospective test and thresholds, including multiple comparisons and proper fallback/abstention floors. Do not reclassify old M013/M013a failed/indeterminate metrics. The full synthetic tests qualify ONLY synthetic generalization; CodeGG M005 requires an independently approved corpus and consumer-owned eligibility/privacy/policy assessment, and crates.io remains separately gated on human/legal review.

## 5. Proposed design decisions

1. First a **representability decision gate** with mathematical proof and fixed manually scored truth table — before running new training.
2. Binary: train-only invariant nuisance mask + intercept; bounded L2/early-stopping comparator if train/dev evidence warrants.
3. Choice: minimum sparse context-conjunction×option feature architecture, additive validated artifact; alternatively optimizer-only correction IF existing head proves fully expressive.
4. One NEW prospective synthetic suite with structurally varied label generators, per-family eligible support, frozen protocol and exact one-time final-test procedure.
5. Explicit task-specific positive/negative/indeterminate with no CodeGG model promotion and no broad architecture framework until M015.
