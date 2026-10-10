# ADR-0001 — General Decision-Model Framework and Model Boundaries

Status: accepted
Date: 2026-10-10
Decision owner: dbowm91/sdm
Related authority: https://github.com/dbowm91/codegg/blob/main/plans/adrs/ADR-0013-external-decision-model-training-and-runtime-boundary.md

## Context and forces

SDM was extracted from CodeGG to keep reusable model research, training, and local inference outside the agent. At SDM main revision 8139b064bdcf3212e8f6fd912e801a479b55751c, sdm-core exposes Binary, Choice, Score and Rank semantics; only Rank is implemented by one sparse linear inference architecture. sdm-training has four compatibility-rank cases (2 train, 1 dev, 1 test in the pinned report), a rudimentary candidate-accuracy evaluator and a model-specific trainer. sdm-runtime currently reads a single v1 LinearArtifact and caps artifacts at 4 MiB. An opt-in CodeGG consumer pins this revision; its artifact is not production qualified.

Prior CodeGG contextual model experiments failed offline effectiveness gates against linear/BM25, including unknown-tool, abstention, and preselection-recall weaknesses. Larger parameter counts alone are not evidence of improvement.

Design forces: generic reuse across several decision tasks, bounded predictable CPU inference on Mac/Linux/ARM, training on a 24 GiB Apple Silicon host, application-owned security authority, strict versioning and historical negative evidence, meaningful evaluation, and optional acceleration without expanding the default dependency graph.

## Considered alternatives

1. Continue implementing all training/runtime/evaluation inside CodeGG: reject; breaks extraction ownership and couples experimentation to the agent.
2. Immediately build one 5–25M parameter contextual transformer: reject as the framework milestone; past negative qualifications and smoke-sized dataset cannot establish effectiveness, and packaging/runtime contracts are not ready.
3. Make a large general ML platform first: reject; too broad, no initial vertical consumer.
4. Separate semantics, data/provenance, evaluation/qualification, and architecture implementations; preserve a baseline while adding one small genuinely nonlinear model: select.

## Decision

- Keep sdm-core as the typed bounded decision semantic owner, retaining stable v1 requests and CodeGG compatibility. Introduce additive versioned typed feature projections; do not silently change v1 JSON meaning.
- Keep a runtime-only sdm-runtime with explicit architecture dispatch, bounded resource declarations, fail-closed artifact verification, and no trainer/network dependency. No dynamic executable plugins or auto-download.
- Add sdm-data as the owner of dataset manifests, import validation, frozen split assignments and provenance, and sdm-eval as the independent owner of metrics and pre-registered qualification. sdm-training owns optimization, model fitting, calibration on dev only, and checkpoint creation.
- Implement a small nonlinear trainable architecture as a *framework qualification instrument*, alongside sparse linear and deterministic baselines. Investigate Burn as optional trainer; do not hard-wire Burn, Candle, ONNX Runtime or tract into the minimal runtime contract before a measured decision.
- Use a versioned artifact envelope for new architectures. Preserve the existing LinearArtifact v1 API, digest computation and frozen fixture output. Artifact integrity digests prove identity, not the trustworthiness or semantic correctness of external weights.
- Distinguish model correctness (valid finite inference), experimental usefulness (pre-registered held-out gates), and production permission (host's independent explicit policy). No SDM result grants CodeGG tool execution or disclosure rights.
- Cross-application portability is demonstrated with a non-CodeGG synthetic exercise before CodeGG becomes the first qualification target.

## Consequences and tradeoffs

New crates/schemas increase implementation and review cost but prevent experimental and training dependencies from leaking into consumers. Native CPU inference for a tiny MLP keeps initial deployment simple; better-pretrained representations, large encoders, GPU training and ONNX/tract are deferred until evidence justifies them. Frozen schema adapters and explicit model capability negotiation avoid migrating CodeGG prematurely. An unqualified model can close an experiment with a reproducible negative verdict, but can never be advertised as production-promoted.

## Migration and compatibility

Do not rewrite or retrain the frozen v1 artifact or change the immutable SDM SHA consumed by CodeGG. New feature/artifact versions are additive and v1 loading remains supported; incompatible new models must explicitly report Unsupported. SDM M005 may output a candidate new revision and qualification dossier, not update CodeGG dependencies automatically. CodeGG adoption requires its own reviewed interface plan and compatibility evidence.

## Affected work

SDM plans/subsystems/general-decision-model-framework-roadmap.md, milestones M001–M005, plans/registry.md, docs/artifact-format.md and docs/reproducibility.md during implementation. No CodeGG planning history or live authority is amended by this ADR.
