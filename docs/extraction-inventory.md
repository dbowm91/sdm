# CodeGG extraction inventory

Inventory source: CodeGG baseline `533be5941ac48334743de555cda96d8695cc6527`;
extraction source/provenance revision `aec30ebbaada172cd2915b3fb068f828a8fc6709`.
Classification follows behavior and ownership, not directory location. This first
revision copies the semantic core and frozen compatibility fixtures; training and
experiment history remain authoritative in CodeGG until M006. No CodeGG production
source or dependency was deleted or switched.

## `src/tool_advisor/*`

| File | Classification | Reason / disposition |
|---|---|---|
| `mod.rs` | CodeGG adapter/policy + obsolete experiment implementation | Host tool catalog, consent/capture, config, and module wiring stay; generic decisions are separated into `sdm-core`. |
| `decision_adapter.rs` | CodeGG adapter/policy — retain | Maps bounded application candidates and state; depends on CodeGG authority/policy. |
| `causal_active.rs` | CodeGG adapter/policy — retain | Causal-frontier application state and actuation. |
| `causal_frontier.rs` | CodeGG adapter/policy — retain | Explicitly CodeGG-specific causal contracts and evaluation. |
| `causal_observe.rs` | CodeGG adapter/policy — retain | Session observation and CodeGG telemetry policy. |
| `context_v2.rs` | CodeGG adapter/policy — retain | Tool-specific context projection. |
| `training_data.rs` | CodeGG adapter/policy — retain | Session event capture, redaction, consent and storage; generic dataset import must be explicit. |
| `contextual.rs` | Shared utility requiring deliberate split | Contains generic linear scoring/training math mixed with advisor context and tool-domain fixtures; reimplement generic trainer in SDM, retain source/history. |
| `training.rs` | Shared utility requiring deliberate split | Optimizer/split/artifact routines mix useful generic pipeline with CodeGG artifact/config structs; reimplemented around generic schema in SDM. |
| `operating_point.rs` | Obsolete experiment implementation — retain until M006 | Candle architecture experiment and qualification history. |
| `sequence_encoder.rs` | Obsolete experiment implementation — retain until M006 | Transformer/tokenizer loading and encoder experiment evidence. |
| `sequence_ranking.rs` | Obsolete experiment implementation — retain until M006 | Sequence ranking experiment implementation and artifacts. |
| `sequence_retrieval.rs` | Obsolete experiment implementation — retain until M006 | Sequence retrieval experiment implementation. |
| `sequence_qualification.rs` | Obsolete experiment implementation — retain until M006 | Frozen qualification harness/results. |
| `order_invariance.rs` | Obsolete experiment implementation — retain until M006 | Experiment-specific architecture and evidence. |
| `retrieval_architecture.rs` | Obsolete experiment implementation — retain until M006 | Candidate architecture search and frozen evidence. |
| `retrieval_projection.rs` | Shared utility requiring deliberate split | Generic projection math is entangled with advisor schema; retain evidence, reimplement only if needed. |
| `retrieval_relevance.rs` | Shared utility requiring deliberate split | Generic ranking metrics mixed with advisor labels; retain until generic metric parity is established. |
| `retrieval_signal.rs` | Obsolete experiment implementation — retain until M006 | Experiment preregistration/results are historical evidence. |
| `retrieval_signal_v2.rs` | Obsolete experiment implementation — retain until M006 | Experiment-specific features/evaluation. |
| `late_interaction.rs` | Obsolete experiment implementation — retain until M006 | Candle late-interaction experiment and negative/qualification evidence. |
| `requalify.rs` | CodeGG adapter/policy — retain | Consumes CodeGG qualification/preregistration records and holdouts. |

## Scripts, assets, features, dependencies

| Source | Classification | Disposition |
|---|---|---|
| `scripts/generate_decision_runtime_fixtures.py` | CodeGG adapter/policy — retain | Authority for frozen fixtures remains CodeGG. |
| `scripts/generate_tool_advisor_corpus.py` | CodeGG adapter/policy — retain | Generates the CodeGG-specific corpus; no implicit dataset export. |
| `scripts/generate_tool_advisor_qualification_holdout.py` | Historical evidence — retain | Qualification holdout provenance remains in place. |
| `scripts/generate_tool_advisor_qualification_v3_holdout.py` | Historical evidence — retain | Qualification holdout provenance remains in place. |
| `scripts/generate_causal_m005_holdout.py` | CodeGG adapter/policy — retain | Frozen CodeGG causal-frontier qualification input. |
| `assets/decision-runtime/compatibility-v1.jsonl` | CodeGG adapter/policy — retain | Authoritative fixtures remain in CodeGG; sanitized copy exported to SDM. |
| `assets/tool-advisor/corpus.jsonl`, `tiny-training.json`, `contextual-*-training.json` | Historical evidence — retain | Domain labels and experiment input; no user data export. |
| `assets/tool-advisor/causal-frontier-v1.jsonl`, `causal-frontier-m00*-*.json`, `causal-frontier-m005-*.json` | CodeGG adapter/policy — retain | Causal-frontier contracts and qualification evidence remain CodeGG-owned. |
| `assets/tool-advisor/downstream-suite.jsonl`, `c004-requalification.json` | Historical evidence — retain | Downstream trajectory qualification and requalification evidence. |
| `assets/tool-advisor/*holdout*`, `*result*`, `*preregistration*`, `*freeze*`, `*selection*` | Historical evidence — retain | Immutable qualification/evidence records; not rewritten or moved. |
| `assets/tool-advisor/*ranking*`, `*retrieval*`, `*reference-models*` | Obsolete experiment implementation — retain until M006 | Model/architecture-specific research evidence remains traceable in CodeGG. |
| Cargo features `tool-advisor`, `tool-advisor-training`, `tool-advisor-encoder-experiment`, `tool-advisor-encoder-training` | CodeGG adapter/policy — retain for now | Removal is explicitly M006 after consumer migration. |
| Optional `candle-core`, `candle-nn`, `candle-transformers` dependencies | Obsolete experiment implementation — retain until M006 | Feature-gated experimental dependency set; not copied into SDM runtime. |
| `serde`, `serde_json`, `sha2`, `thiserror`, `async-trait` | Shared utility requiring deliberate split | Minimal semantic dependencies carried into independent SDM workspace. |
| `anyhow`, `url`, `unicode-normalization` | Shared utility requiring deliberate split | Used by capture and/or CodeGG scoring paths; remain workspace-level or CodeGG-owned, not pulled into SDM runtime. |

## Explicitly retained CodeGG responsibilities

`ResolvedToolSurface`, tool names and candidate eligibility, action/permission
authority, disclosure and promotion budgets, session capture/consent, causal-frontier
contracts/state/evaluation, trajectory qualification, deterministic discovery fallback,
and all negative architecture results remain in CodeGG. M002 extraction is additive;
M003/M006 own production cutover and retirement.
