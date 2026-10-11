# General Decision Model Framework — Research and Architectural Baseline

Date: 2026-10-10
Status: recorded research, not implementation or model promotion
Source baseline: dbowm91/sdm@8139b064bdcf3212e8f6fd912e801a479b55751c
Planning entry: ../plans/registry.md

## Existing scope and evidence

sdm-core exports bounded, validated Binary / Choice / Score / Rank request-response semantics, but the only trained artifact and runtime family is binary sparse linear relevance applied to Rank candidates. sdm-training combines ingestion, group-based split, optimizer, threshold and a coarse candidate-level correct/total evaluator. sdm-runtime accepts a 4 MiB v1 LinearArtifact and rejects unsupported semantic families. No pretrained contextual model or qualified positive experimental artifact exists in SDM. Its frozen CodeGG v1 compatibility checks validate 12 cases and execute 11 valid requests; these prove only semantic/candidate/provenance compatibility, not predictive quality.

The first baseline training fixture has four cases split 2/1/1 train/dev/test at seed 127, 100 epochs. The checked-in 2,560-byte artifact has 62 parameters. docs/benchmark-baseline.md reports x86_64 via Rosetta: cold load 510 µs; process peak RSS 4,878,336 bytes; p95 0.291/1.139/2.317/4.624 ms for 16/64/128/256 candidates. Do not compare unlike workloads as equivalent speed tests.

CodeGG's independent and completed historical experiments have shown multiple contextual implementations to be mechanically valid but unhelpful on held-out tool selection. Its C004 report gives MRR 0.707 for hashed-linear, 0.638 BM25, and 0.457/0.595/0.557 for contextual small/medium/compact. Contextual calibration generalized poorly to no-tool holdouts, and 64-tool shortlist recall was about 0.829 at candidate budget 16. Source: https://github.com/dbowm91/codegg/blob/main/plans/closure/tool-selection-advisor-evidence-integrity-corrective/004-status.md . The cleaned test partition was already observed; new development must not treat it as a fresh unbiased final test.

## Primary gaps

1. A semantic core exists, but typed numeric/categorical/boolean state and feature schema versions are absent. Converting cost/latency/benchmark values to arbitrary text is fragile for routing or advisory risk experiments.
2. Data provenance, split manifests, corpus permissions and label identity are currently too weak for independent scientific inference.
3. Candidate accuracy cannot adjudicate ranking, abstention, unknown-tool generalization, calibration and conditional-on-shortlist recall.
4. Runtime architecture is hard-coded to LinearArtifact v1; the 4 MiB global cap is not a safe mechanism for larger model weights, and should not be globally lifted.
5. Training and inference have only one architecture. Demonstrating a genuinely learnable interaction before a larger encoder is a more informative framework proof than selecting parameter count.
6. The CodeGG consumer is already pinned to a working SHA, so backward compatibility is a hard constraint rather than a future aspiration.

## Architecture alternatives and rationale

- Keep all modeling inside CodeGG: rejected, crosses the completed extraction boundary and couples research to production agent CI.
- Train a 5–25M-parameter transformer immediately: deferred; smoke-scale labels, negative predecessor evidence and absence of validated packaging/evaluation make size-first work unjustified.
- Implement a full training/serving platform: deferred; no evidence of immediate need for multi-node schedulers, inference servers or generalized distributed optimization.
- Build a versioned core, data/metric boundary, small nonlinear model and first consumer: selected; each contract has independently testable completion.

Rust training research candidates include Burn (native autodiff/optimizer), Candle, or a minimal custom training implementation for very small heads. Runtime candidates for later portability include native CPU math, tract or ONNX Runtime. Safetensors is a potential data container for tensors, not an artifact policy/trust system. Choice is subject to the M004 dependency and MSRV spike; do not imply a framework has already been adopted or its current version qualified. All optional native/GPU backends must be kept out of the default runtime-only graph.

For orientation, 25 million FP32 weights alone occupy approximately 100 decimal MB and 25 million int8 weights about 25 decimal MB, without runtime/activations. Thus any future neural envelope needs per-architecture tensor shape, dtype, weight size and allocation bounds rather than raising v1's global 4 MiB limit. On a 24 GiB Apple Silicon development host, small MLP training is tractable, but host feasibility and ARM64 CPU deployment performance require measurement, not extrapolation.

## Model-development strategy

First introduce a small nonlinear pairwise scorer able to pass synthetic context-swap/counterfactual falsification that a candidate-only lexical baseline cannot. Benchmark two trained parameter budgets. Reuse exactly the same feature/data/evaluation contracts for another synthetic non-CodeGG decision task before accepting the framework boundary.

Do not assume this establishes semantic language understanding. A later text-pair encoder experiment may require pretrained/distilled representations and fresh labels. Every experiment needs train/dev/test isolation, frozen preregistered metrics, explicit no-answer cases, family/generalization exclusions and baseline candidate identity equivalence. A negative generalization result is a valid experimental outcome.

CodeGG remains the first practical consumer and owner of permission, surface eligibility, shortlist construction, capture consent, fallback and actuation. SDM can return scores for *eligible candidates supplied by CodeGG*, but cannot recover an omitted relevant tool or authorize promotion. A downstream CodeGG runtime pin change needs separate codegg-side planning, exact SHA checks and observe-only trajectory qualification.

## Research-to-work traceability

M001 owns schema versioning and artifact envelope; M002 owns provenance and splits; M003 owns independent semantic metrics and qualification; M004 owns training/runtime architecture; M005 owns first targeted offline use case. The accepted ADR and each plan specify stop conditions that prevent conflating compatibility, effectiveness and deployment. No work from this record should be represented as landed code.
