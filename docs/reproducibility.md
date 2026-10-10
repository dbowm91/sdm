# Training and evaluation reproducibility

Generic JSONL decision cases have schema version 1, unique case IDs, leakage-group
identity, and the versioned semantic request/response contract. Dataset bytes and
seed are recorded. A leakage group is assigned wholly to exactly one deterministic
train/dev/test partition; train is 70%, dev 15%, test 15% by seeded SHA-256 bucket.
Training updates parameters from train only. The classification threshold is selected
from dev only. Test cases are held out for explicit evaluation and never tune model
parameters or threshold. Empty training partitions and malformed/oversized datasets
are errors.

The initial trainer is a deterministic sparse logistic rank relevance baseline. Its
report includes seed, dataset fingerprint, split counts, parameter count, chosen
threshold, and artifact digest. Resource bounds cap dataset bytes, case count, epochs,
feature count, and artifact size. Evaluation accepts a separately held-out case set.

Compatibility cases are intentionally CodeGG-specific fixtures, not the generic
training schema's vocabulary. They carry no user session content.

`sdm-check-compat` validates every frozen request/expected response pair and executes
every fixture marked valid. Runtime outputs must pass the same CodeGG response
validator, preserve the exact candidate identity set when answering Rank, use only
Answered/Abstained for the compatible local Rank profile, and identify the actual
artifact digest/runtime version. Frozen advisor relevance and answered/abstained
labels are not used as a production quality claim for this unqualified sparse baseline;
the compatibility tolerance is contract shape, bounded finite values, candidate
identity, and provenance, while predictive quality remains experiment evidence.

## Dataset and qualification contracts

`sdm-data` represents labels independently of runtime responses and records source,
license, consent scope, label lineage and redistributability. `sdm-dataset validate
<bundle.json>` checks a bounded bundle; `sdm-dataset split <bundle.json> <seed>
<manifest.json>` emits a content-bound train/dev/test manifest after group-disjoint
assignment. Reusing a split requires the same dataset digest and exact case coverage.

`sdm-eval` contains independent semantic metrics and frozen protocol identity checks.
`sdm-qualify <frozen-input.json>` validates dataset/split/artifact/calibration hashes,
checks the preregistered minimum sample count, and reports Rank metrics and per-gate
pass/fail/indeterminate outcomes. Unsupported gate names are indeterminate. It never
promotes a model. Binary, Choice and bounded Score metric functions are available to
other adapters; the CLI report currently covers Rank predictions only.

The CPU nonlinear architecture is `sdm-nonlinear`; enable its `training` feature for
deterministic bounded SGD and fingerprint-bound atomic checkpoints. Default runtime
dispatch supports its bounded Rank inference path and validates trainer artifact
identity before use. The training feature is not enabled by `sdm-runtime`.
