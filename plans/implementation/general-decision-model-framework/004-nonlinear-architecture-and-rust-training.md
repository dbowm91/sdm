# SDM General Framework M004 — Nonlinear Architecture and Rust Training/Inference

Status: conditionally closed (CPU nonlinear scorer and SGD prototype implemented; runtime registration and multi-platform qualification remain follow-up)
Primary class: capability
Repository baseline at planning: dbowm91/sdm@8139b064bdcf3212e8f6fd912e801a479b55751c; re-audit when unblocked
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md#m004--second-trained-architecture-and-portable-inference
ADR: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Hard dependencies: M001 runtime contract, M002 dataset, M003 independent qualification framework closed
Operational dependency: representative Apple Silicon train/test host and ARM64 CPU resource evidence for a portability claim
First consumer: SDM non-CodeGG synthetic decision task; M005 CodeGG offline experiment

## 1. Objective

Implement a *second, genuinely nonlinear* learned decision architecture, locally trainable with Rust and portable to a native CPU inference path, to exercise the generic framework end-to-end. Keep linear baseline intact. A model may close this milestone despite poor predictive quality if architecture, reproducibility and evaluation are truthfully demonstrated; it cannot be called a qualified CodeGG tool selector from this milestone.

## 2. Starting evidence and considered technology

sdm-runtime currently supports one sparse linear Rank architecture and bounded JSON model. Frozen linear compatibility artifact is 2,560 bytes and p95 Rank latency on recorded 16/64/128/256 candidate workloads was 0.291/1.139/2.317/4.624 ms on a Rosetta host. CodeGG prior hand-written-contextual scorers (20.97/62.92/1.31 MB variants) failed clean offline ranking/abstention gates despite valid mechanics. The next model must prove learned task/candidate interactions via counterfactual tests, not infer that from parameter count.

Candidate Rust training technologies: Burn (Rust autodiff/optimization, optional backends), Candle (tensor ops with ML backends), custom compact CPU math; ONNX Runtime/tract are optional future inference alternatives; Safetensors is a tensor container, not a full trust/provenance manifest. Do a tightly bounded dependency + portability spike before selecting anything. No mandate to use Burn if the spike demonstrates unacceptable MSRV, compile footprint or platform constraints.

## 3. Invariants and non-goals

- No GPU/compiler framework in the default/runtime-only dependency graph. Local CPU inference and production artifact parsing must remain standalone; no Python-required path and no implicit downloads/network.
- Do not replace v1 linear artifact, modify CodeGG's pinned SHA or delete historic negative model evidence.
- Rank allows independent multiple positive candidates and explicit none-relevant abstention. Other semantic heads are optional if evidenced, not advertised by architecture name.
- No learned authority to execute tools, relax CodeGG permissions or synthesize candidate IDs.
- No fixed 5–25M-parameter target, pretrained encoder, mandatory transformer, shared online trainer, RL, distillation API, auto-selection of best model from final test.
- Train/checkpoint/artifact can be generated on ~24 GiB Apple Silicon; no inference path may allocate from unchecked tensor dimensions.

## 4. Model and representation

Start with a bounded pairwise MLP or equivalent small nonlinear scoring architecture driven by typed context, candidate and explicit interaction inputs. Include trainable cross-interaction capacity beyond fixed lexical overlap, and frozen ablations for context-masked vs context-permuted pairs. Define stable projection/version and unknown-category handling. Exact layers and sizes are implementation choices, but train at least two capacity points with recorded parameter counts and measured memory. Reject untrained or unused large weight matrices masquerading as capacity.

Versioned architecture ID, model tensor shapes and dtype, weight checksum, tokenizer/feature schema ID (where relevant), calibration bytes/hash and allowed task semantics must be declared in the v2 envelope. Require a deterministically computed hash over the tensor payload; bounded buffer lengths and dimension-product overflow must be validated before allocation. Document small native CPU forward reference and training-to-runtime parity tolerance.

## 5. Ordered work packages

A. Architecture/dep spike: run a minimal forward/backprop/serialization sample for two Rust approaches (e.g., Burn vs compact custom or Candle) under rust-version 1.89 and supported target matrix; record build times, lockfile footprint, implementation complexity, Apple Silicon CPU/accelerator behavior, and decision. No framework selection by popularity alone; optional native Metal backend cannot become the default.

B. Feature/model implementation: add architecture-specific library behind explicit feature (or independent crate) consuming M001 typed projection; expose Rank scoring, true nonlinear interactions, bounded shape and finite output checks. Keep data/label generation separate.

C. Trainer and dev tuning: train on M002 datasets with seeded, explicitly recorded train/development split, optimizer/epoch/batch bounds, dev-only calibration and checkpoint metadata. Explicitly distinguish bitwise reproducibility on supported CPU from numerical reproducibility on nondeterministic GPU.

D. Portable runtime: implement validated v2 weight loader and native CPU inference path, without importing training crate. Check all tensor shapes, dtypes, quantization fields and limits before allocation; reject corrupt/tampered artifacts and unsupported semantics. Compare runtime logits and probabilities with trainer reference on frozen vectors within declared tolerance.

E. Synthetic falsification: produce a non-CodeGG interaction task impossible for a context-independent candidate-only scorer, with counterfactual task wording, multi-positive and none-relevant cases. Report baselines, independent test and learned interaction ablation under M003 protocol. A positive synthetic result is *not* a CodeGG quality claim.

F. Qualify size and latency: benchmark cold load, trained parameters, bytes, process RSS, candidate counts 1/16/64/128/256 p50/p95, batch behavior, model-load failures and artifact rejection; repeat on x86_64 + Apple Silicon ARM64, and Linux ARM64 where available. Fail to claim unsupported platform evidence rather than substitute Rosetta numbers.

## 6. Restart and concurrency

Trainer writes checkpoints in a temporary path with atomic finalize and manifest verification; allow explicit resume only from matching data/split/config/schema/seed identity. Save optimizer state only when needed to resume faithfully. Interruption leaves a verifiable last-complete checkpoint and no partially promoted artifact. Inference model snapshots immutable; concurrency bounded by caller model, no global mutable scorer parameters and no internal unbounded queue.

## 7. Quality and security tests

- Context-swap and candidate-swap counterfactuals, feature ablation, hard negatives, unseen categorical values, missing fields, all-negative/no-candidate and multiple positives.
- Normalization/probability finite and bounded; invalid tensor dimensions, wrong dtype, excessive parameter count, hash mismatch, truncated weights, calibration mismatch, unsupported feature schema and hostile variable-length inputs.
- Test reproducibility by training twice with same CPU seed and frozen splits, state any expected numerical tolerances. Keep test labels unavailable during dev/optimizer iteration.
- Verify default and runtime-only cargo tree excluding neural trainer/backends; test feature-gated train functionality separately.
- Always run existing cargo fmt/check/test/Clippy/compatibility commands; add architecture-specific parity, resume and resource scripts and CI if runner supports them.

## 8. Acceptance

Two independently implemented learned architectures (linear and nonlinear) can fit, save, load, infer and be measured under one semantic/data/evaluation contract. Nonlinear capacity and task-candidate interaction are actually exercised, and the model's generalization result (positive or negative) is reported without changing predeclared gates. An alternate synthetic non-CodeGG task demonstrates reuse. CPU inference is self-contained, safe and bounded. Legacy compatibility remains green.

## 9. Stop conditions

Stop if artifact v2 breaks v1 consumers, trainer dependencies contaminate the runtime-only graph, an accelerator is required on basic x86_64 or ARM64 targets, a tensor shape can OOM before validation, evaluation test cases change after looking at failures, training reproduces only because labels leaked into features, or extra model parameters are largely unused and described as a capacity gain.

## 10. Closure evidence

plans/closure/general-decision-model-framework/004-status.md: architecture choices and rejected alternatives, exact source/seed/data/split/manifest hashes, two capacities and trained-parameter utilization, reproducibility and independent test report, v1 compatibility, CPU reference/parity, resource matrix, dependency tree and platform coverage, errors and security guards, release readiness, and registry transition. M005 becomes ready after positive *framework* closure even if new model's quality verdict is negative.
