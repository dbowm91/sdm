# M004 closure — Nonlinear architecture and Rust training/inference

Status: conditionally closed  
Implementation commit: `e02fab714540868f5619e2c2dc2c6aaf0549d8eb`

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Genuine nonlinear CPU forward path | Bounded tanh hidden layer in `sdm-nonlinear::PairwiseModel`; context/candidate/interaction feature projection | Pass (mechanics only) |
| Rust local training with deterministic initialization and bounded updates | Optional `training` feature, seeded init, capped epoch/example counts and SGD step | Pass (prototype) |
| Model serialization and integrity identity | Bounded JSON serialization, shape/finite checks before use, SHA-256 digest | Pass |
| Two capacity points | Test exercises hidden sizes 4 and 8 | Pass (smoke only; no quality claim) |
| Runtime-only graph excludes training frameworks | Training API is feature-gated; no ML framework, GPU or network dependency | Pass |
| v2 production runtime dispatch/parity and trainer-runtime artifact envelope | Envelope validates but nonlinear architecture is not registered; no trainer/runtime frozen parity vectors | Gap |
| Independent interaction task, ablations, trained-parameter utilization | Not measured; no model quality verdict | Gap |
| Apple Silicon/x86_64/Linux ARM64 resource matrix | Only this host was benchmarked, and benchmark was for v1 linear runtime | Gap |

## Verification and limitations

All-feature workspace tests and Clippy pass. The nonlinear implementation is a compact prototype; the lexical projection is not a semantic encoder. It has no dedicated benchmark, calibration, resumable checkpoint writer, optimizer-state persistence, or artifact registration with `sdm-runtime`. v1 remains unchanged. No CodeGG quality claim is made.

Disposition: conditional pending runtime registration/parity and resource/platform evidence. See follow-up registration in the active registry.
