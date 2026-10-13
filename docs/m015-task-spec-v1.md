# M015 TinyChoice task specification v1

Status: development-only corpus contract. This file defines synthetic targets; it is not a quality claim or an M017 holdout.

## Causal variables and targets

Each instance is one bounded Choice request with an observable typed rule descriptor, causal context, a set of 2–8 candidates, and a separate `available` bit. The target is either the ID of the uniquely satisfying candidate when available, or `null` when unavailable. Candidate IDs and input order are randomized independently of semantic candidate roles. The target never depends on IDs, order, nuisance text, load, group number, or family identifier.

The causal graph is `rule + context + candidate semantics -> candidate satisfaction -> target`, and `available -> answerability -> target/null`. Nuisance fields (`note`, `load`, optional `memo`) have no path to the target. In fixed-rule experiments the rule and causal mapping stay constant while nuisance values, IDs, order and valid optional-field presence change. In rule-conditioned experiments the mapping may change only when the observable rule descriptor changes. An identical context/candidate observation with a hidden changed rule is not identifiable and is an explicit negative control.

## Rule grammar

The independent checker and labeling implementation support five source-defined rule families: `all_required` (conjunction), `any_required` (disjunction), `exclusive` (exactly one required feature), `threshold` (numeric feature at or above a bounded threshold), and `category_and_flag` (categorical equality and a boolean flag). Each rule descriptor names the rule and its required operands/threshold. Unknown names, missing operands, extra operands, invalid types, and out-of-range thresholds are errors; there is no default rule.

The corpus includes both positive and negative candidates, randomized candidate cardinalities from 2 through 8, answerable and unavailable instances, candidate ID renaming/order reversal controls, nuisance-preserving counterfactuals, and causal flips. Groups and paired instances stay wholly in TRAIN or DEV. Group membership is determined before rows are emitted.

## Bounds and exclusions

The CLI accepts only 2,000, 10,000, or 50,000 independent groups, explicit seed, and an explicit output path. It streams bounded JSONL, writes through a temporary file and atomically replaces only an absent output or an output with the same digest. It does not construct any M017 final cohort. Historical M013/M014 data and identifiers are not inputs.
