# M004 closure — Nonlinear architecture and Rust training/inference

Status: conditionally closed
Implementation commit: `ee0f613`

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Genuine nonlinear CPU forward path | Bounded tanh hidden layer in `sdm-nonlinear::PairwiseModel`; context/candidate/interaction feature projection | Pass (mechanics only) |
| Rust local training with deterministic initialization and bounded updates | Optional `training` feature, seeded init, capped epoch/example counts and SGD step | Pass (prototype) |
| Model serialization and integrity identity | Bounded JSON serialization, shape/finite checks before use, SHA-256 digest | Pass |
| Two capacity points | Test exercises hidden sizes 4 and 8 | Pass (smoke only; no quality claim) |
| Runtime-only graph excludes training frameworks | Training API is feature-gated; no ML framework, GPU or network dependency | Pass |
| v2 runtime dispatch/parity and trainer-runtime artifact envelope | `load_artifact` registers nonlinear v2 dispatch; feature/model/calibration hashes are checked; runtime output agrees with model scorer in a fixed test vector | Pass (mechanics only) |
| Atomic resumable checkpoint and identity | Feature-gated save/load verifies schema fingerprint and seed identity; interrupted writes use temp+rename | Pass (optimizer state is not persisted) |
| Independent interaction task, ablations, trained-parameter utilization | Not measured; no model quality verdict | Gap |
| Apple Silicon/x86_64/Linux ARM64 resource matrix | Same nonlinear artifact benchmarked in GitHub Actions run 38076997293 on all three targets; per-target timings and host caveats in M006 closure | Pass (synthetic initialized model only) |

## Verification and limitations

All-feature workspace tests and strict Clippy pass. The nonlinear implementation is a compact prototype; the lexical projection is not a semantic encoder. Local benchmark uses deterministic initialized parameters, not two trained capacity points; no ablation or independent interaction quality result exists. Checkpoints do not persist optimizer state. v1 remains unchanged. No CodeGG quality claim is made.

Disposition: conditional pending runtime registration/parity and resource/platform evidence. See follow-up registration in the active registry.
