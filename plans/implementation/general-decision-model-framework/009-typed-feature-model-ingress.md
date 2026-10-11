# SDM M009 — Task-Neutral Typed Feature Ingress

Status: closed; see plans/closure/general-decision-model-framework/009-status.md
Class: infrastructure/capability
Planning baseline: 319a05805f3a8383574d0d0712ca5975d16546ff; refresh at start
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md
ADRs: ADR-0001 and ADR-0002
Unblocks: M010

## Objective

Make sdm-core's validated FeatureSchemaV2/FeatureProjectionV2 (Text, Number, Boolean, Category) feed real training AND local runtime inference through one canonical encoder. Support non-text-only, non-CodeGG tasks; preserve v1 request and lexical Rank paths with explicit version negotiation.

## Verified gap

Current sdm-data DatasetExample stores DecisionRequest with string state, not a linked typed feature projection. Nonlinear Rank runtime concatenates state text/candidate labels and generates ctx/cand/both token features via PairwiseModel::rank_features. Merely validating FeatureProjectionV2 does not make numerical or categorical learning functional.

## Work packages

A. Define and document a versioned typed model input binding: validated context projection, optional candidate-specific projection for Rank/Choice, stable candidate IDs, schema/encoder version and identity. Choose an additive request/feature extension or explicit v2 adapter; never reinterpret DecisionRequest v1 fields silently. Define ownership of canonical feature coordinates, required/missing feature policy, categorical unknown policy and semantics-specific admissibility.

B. Implement one bounded deterministic vectorizer in a training/runtime-neutral crate/module. Encode finite numerics with train-only scaling/clipping, Booleans, bounded categorical vocab or declared hashing, and text with declared tokenization/limits. Bind feature ordering, scalers, dictionaries, imputation policy and bounds to model artifact manifest hash. Explicitly reject dimension, input-type and coordinate mismatches.

C. Extend sdm-data and M008 training to bind each label to a typed input plus schema; fit preprocessing only on train. Keep split group isolation and the freeze/hash policy. Ensure candidate-per-option typed values cannot synthesize candidate IDs or elevate eligibility. Version the dataset contract and retain legacy dataset reader.

D. Extend sdm-runtime versioned inference interface to accept typed projection and reuse precisely the trained feature encoder. Preserve both existing linear and nonlinear lexical Rank artifact behavior; do not make unsupported architecture/semantic requests silently coerce to text.

E. Add a non-CodeGG synthetic typed problem with numeric magnitude/range, categorical profile and boolean flag. Demonstrate end-to-end train -> model -> reload -> typed infer -> held-out evaluate, including numerical counterfactuals where text token overlap is not sufficient. This is mechanics-only usefulness evidence.

F. Update docs, examples and static dependency guards. Keep preprocessing metadata bounded and verifiable before allocation; no new trainer/network/GPU dependency in sdm-runtime.

## Focused failure/regression matrix

Missing required/optional fields, extra feature ID, wrong schema hash, unknown category, NaN/inf, numeric overflow/extreme finite values, shuffled supplied fields, coordinate-order changes, candidate-specific ID injection, schema-hash tamper, corrupted normalization, unchanged input cross-crate parity. Verify that changing test-only features/labels does not refit vocabulary/scalers/weights or alter model identity. Verify original 12/11 compatibility fixture and v1 score parity.

Run standard workspace fmt/test/strict Clippy, runtime-only cargo tree, M008 end-to-end command, and hosted CPU matrix with explicit architecture/capability errors.

## Acceptance and stop

A user can supply genuine numeric, categorical and boolean features without ad hoc string conversion and obtain train/runtime parity through one documented schema-bound interface. Non-CodeGG example runs with frozen splits and a genuinely reloaded model. Do not close on data structure existence without successful inference. Stop if train and inference disagree, test is used to fit preprocessors, runtime gains training deps, or v1 compatibility changes.

Closure: plans/closure/general-decision-model-framework/009-status.md with hashes, typed golden vectors and perturbation tests, trained/reloaded traces, compatibility, resource and dependency evidence. Only then mark M010 ready.
