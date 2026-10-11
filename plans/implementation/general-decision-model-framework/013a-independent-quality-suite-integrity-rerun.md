# SDM M013a — Independent Quality-Suite Integrity Rerun

Status: active (bounded successor to an invalid M013 held-out corpus)
Class: evidence corrective
Parent: M013 implementation `c56f442fae14ede38fd1cd6e0eccf61315df96da`
Governance: plans/003-planning-process.md
Architecture: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md; ADR-0002-standalone-framework-before-consumer-qualification.md
Evidence: plans/closure/general-decision-model-framework/013-status.md
Hard prerequisites: M013 conditionally closed; additive Choice cross architecture exists and legacy typed artifacts remain supported
External gates: none; synthetic-only

## Objective

Produce a fresh, independently frozen Binary/Choice suite after the M013 generator failed its paired-counterfactual integrity contract. M013's test output was observed, so no M013 held-out row may be reused. Use a new generator version, seed, IDs, group membership, split fingerprints and protocol. Preserve M013's results as invalid diagnostic evidence. Evaluate the existing current and additive cross architectures under fixed, preregistered configurations; do not select hyperparameters from either observed M013 or M013a test results.

## Forensic finding

M013 initialized one RNG per group and advanced it for each paired row. The load draw therefore differed across active=false and active=true rows even though the protocol declared active as the only changed causal field. The split command also received the same families as both `--exclude-family` and `--test-family`; the current splitter gives exclusion precedence, so every designated OOD row was excluded rather than tested. M013 test outcomes cover only ID families. The replacement generator MUST validate normalized pair equality after removing only request ID, case ID, active values and target labels. The split validator MUST confirm test-family rows are in test and absent from train/dev/excluded. No pair may differ in load, text, availability, rule, candidate projections other than the active field, option identity set, or family.

## Work packages

1. Add an M013a generator with a new fixed seed, IDs and files. Emit at least 50 independent test groups per ID and declared nuisance/structural OOD slice and at least 20 no-answer groups for each designated no-answer slice. Preserve two distinct Choice rule templates, random option order and ID relabeling. Generate paired active counterfactuals with all non-causal fields byte-identical after canonicalization.
2. Freeze fresh group membership, dataset, generator, experiment configs and protocol in a commit before final held-out inference. Use `--test-family` for held-out OOD families and do not also pass those families to `--exclude-family`. Protocol retains the M013 candidate set and metric definitions and reports train/dev-only selection. Do not include any M013a test labels in preprocessing, architecture or calibration.
3. Make `seeded_epoch_order` use a deterministic SplitMix64 Fisher-Yates order per epoch, enabled only by explicit M013a configs. Existing configs default to historical manifest-order training so prior suites and outputs remain unchanged.
4. Add opt-in quality diagnostics to semantic reports: raw Choice logits/probabilities, answerability, final runtime prediction and abstention. Default report serialization must preserve M011 report bytes/identities. Binary outcomes must represent abstention as null when diagnostics are enabled.
5. Run frozen Binary, legacy Choice and bounded cross Choice configs once. Report raw option and answerability metrics separately from final selections; include support, correct counterfactual target on both sides, conditional loss/Brier, answerability AUROC/PR, no-answer recall, false abstention, coverage, selective risk/coverage and grouped 95% intervals (10,000 replicates, seed 14014). Include constant/majority, always-answer, always-abstain and shuffled-score negative controls; controls do not qualify a model.
6. Add a deterministic analyzer that verifies the split and one-factor pair invariants, reports ID, nuisance-only load/text/combined and rule-template slices, computes group-bootstrap intervals, and classifies each task positive/negative/indeterminate per the preregistered gates. Binary failure mechanisms remain unresolved unless one-factor evidence isolates them.
7. Add focused runtime/artifact tests: cross-coordinate ordering and shape, schema/digest mismatch, malformed/duplicate/oversized pairs, invalid/non-finite weights, candidate bounds, option permutation and ID relabel invariance, answerability cutoff, legacy typed-task compatibility, and stable sigmoid/softmax behavior. Run full M013/M011 and workspace verification.

## Invariants and non-goals

No M011 or M013 data, split, report, model output or SHA is changed. The v1 LinearArtifact and old `sdm-typed-task-v1` remain readable and retain old semantics. Cross terms are bounded to 4,096 declared pairs and exclude text-vocabulary dimensions; no dense text cross matrix is allowed. No model is promoted, no CodeGG data or user content is used, no runtime trainer/network/GPU dependency is added, and no publication/legal gate changes. M013a does not authorize the broad M014 architecture research plan.

## Acceptance and stop conditions

Close only when the new suite regenerates identically, canonical pair checks pass, train/dev/test group and family memberships are disjoint, support minima hold (or unsupported slices are explicitly indeterminate), final inference occurs after the freeze commit, all outcomes and gates are reported honestly, old M011 baseline report fingerprints match their historical records, the new runtime contract passes focused and broad checks, and the closure captures exact source/protocol/data/split/artifact/report hashes plus local and hosted CI.

Stop and register another bounded successor if a counterfactual invariant fails, any test content leaks into fitting/selection, old model bytes or report fingerprints change, support is below preregistration minima, or an architecture/policy change is required after M013a test observation. A negative or indeterminate quality result is an acceptable honest closure; synthetic evidence never promotes a model.
