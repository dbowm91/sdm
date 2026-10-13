# M015 — TinyChoice corpus and research foundation

Status: **conditionally closed on implementation branch; integration pending**.

Plan: [015-tinychoice-corpus-and-research-foundation.md](../../implementation/general-decision-model-framework/015-tinychoice-corpus-and-research-foundation.md)  
Branch: `work/plans-sdm-m015-m017-tinychoice-research`  
Base: `main@c048189d7026d723c7da584d7429cb275c714d23`  
Implementation commit: to be recorded after implementation commit is created.  
Integration PR: [#4](https://github.com/dbowm91/sdm/pull/4), open; final hosted CI and reviewed merge pending.

M015 provides bounded synthetic TRAIN/DEV research infrastructure and evidence for existing Choice heads. It does not add a runtime architecture, qualify a model, or establish CodeGG effectiveness. M016 cannot start until this closure is accepted and source is merged to main with green main CI. M017 remains blocked on M015 and M016.

## Requirement evidence

| Gate | Evidence and disposition |
| --- | --- |
| M15-1: causal contract and independent oracle | `docs/m015-task-spec-v1.md`; separate `rule_label` oracle; generator tests cover all five rules, XOR/XNOR tables, malformed-rule rejection and hidden-rule contradictory labels. |
| M15-2: rule and Choice coverage | Five source-defined functions; generated option cardinalities 2–8; explicit no-answer; family answerability support verified in 200 DEV groups. Existing core continues to reject invalid 0/1-option requests. |
| M15-3: deterministic split and counterfactual provenance | Generator seed, group/case/pair IDs, source hashes, split membership and output hashes are in the manifest; 2,000 TRAIN groups / 200 DEV groups, 7,200 / 720 rows; analyzer rejects group crossing and undeclared pair changes. |
| M15-4: distinct estimands | Fixed-rule track has 160 DEV groups across four rules; rule-conditioned track has 40 groups with observable XOR/XNOR selector; hidden contradictory-rule control is explicitly unidentifiable. |
| M15-5: existing-model path and diagnostics | `scripts/run_m015_baselines.py` materializes the same typed schema and group membership, then runs typed-choice, cross and compositional heads. Reports include group bootstrap, answerability calibration/Brier/log loss, conditional Choice NLL/Brier, no-answer recall and paired causal/nuisance metrics. Each report is train/dev-only with no test IDs or inference. |
| M15-6: fault and identity controls | Ten focused Python tests cover swapped labels, malformed oracle rules, group leakage, pair changes, candidate ID sets and order reversal, oracle agreement and the hidden-rule control. Successful baselines show 1.0 nuisance-pair prediction agreement; no quality claim is inferred. |
| M15-7: bounds and compatibility | Generator streams to unique `target/` paths and refuses differing-output overwrite. Baseline adapter enforces the existing 64 MiB typed-data cap and supports the measured 2,000-group baseline budget. Runtime dependency graph contains no training framework or Python; frozen CodeGG compatibility check validates 12 fixtures / 11 executions. |
| M15-8: CI and closure | Local full verification passes (see below). CI has M015 generator/analyzer checks on all verify hosts and existing-model baseline training on Linux x86_64. Final hosted CI, reviewer merge, and merged-main CI are still pending; therefore this is conditional closure only. |

## Immutable run identity and results

The evidence run uses seed `150015` and ignored output `target/m015-baselines-v7/`:

- Generator SHA-256: `18a4d27cca57c639696bad560302549e837152968b2861ccf23a92e6f4ff57f9`.
- Task spec SHA-256: `905441b3f25344cdbe0708538ad44b2005506b602019693da530b82893c2613c`.
- TRAIN JSONL: 7,200 rows, 2,000 groups, SHA-256 `6d1910242f885fff1d67802952a28783ca6c20304363d56befd8f7d117cd9743`.
- DEV JSONL: 720 rows, 200 groups, SHA-256 `e2c9b5b137506b13ef9b40f0b7ed8f8c6f9a89e2de1b16ef2d667c51de04e9db`.
- Dataset SHA-256: `bef4c9a8260950bed5430066c11602f481ae66ad4ff6498d55beaac1c12e53e9`; split fingerprint `7f0e872990247cd21a45a6f7d3c2f08728272fc99763fa7c886eda53dd008e69`.
- Independent analyzer: zero oracle disagreements; 200 nuisance and 160 causal-flip DEV pairs; 40 DEV groups per family with 32 answerable / 8 no-answer groups.
- Learned DEV baselines: all three existing heads achieved answerable accuracy 1.0 (group bootstrap 95% CI `[1.0, 1.0]`), no-answer recall 1.0, causal-pair correct-on-both 1.0, and nuisance prediction agreement 1.0. Shared answerability Brier was `0.1055939`, log loss `0.289023`, and ECE `0.0471949`. Conditional Choice NLL/Brier and artifact hashes are recorded in [M015 development evidence](../../../docs/m015-dev-results.md).

The synthetic tasks are intentionally deterministic. These scores do not establish generalization, superiority, or deployment suitability. No threshold/candidate was selected, no M015 final partition or M017 cohort was constructed, and no historical M014 final config was executed or changed.

## Verification run

Local commands completed on this branch:

```text
cargo fmt --all -- --check                                    PASS
cargo test --workspace --all-features --locked                46 passed
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings  PASS
cargo check -p sdm-runtime --locked                            PASS
cargo tree -p sdm-runtime --locked                             PASS; no training framework / Python
cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked  PASS
cargo run -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json  12 fixtures, 11 executions
python3 -m unittest discover -s scripts                            175 passed, 2 host-specific skips
python3 -m unittest discover -s scripts -p 'test_m015_*.py'           10 passed
```

The 2,000-group baseline run took about 4m26s; the typed dataset occupied 58.6 MB (under 64 MiB). Peak process RSS during training was approximately 1.6 GB on this host. This measures the research trainer, not runtime inference. An earlier attempt exposed unbounded random nuisance-note vocabulary; the source now uses a finite nuisance vocabulary, and only the corrected run above is evidence. Superseded outputs remain under unique ignored `target/m015*` directories.

## Integration and disposition

The implementation branch is pushed for PR #4. The branch CI must complete green and receive review before merge; main CI must pass after merge. These integration gates are intentionally outstanding here. M016 remains blocked on M015 accepted closure and merge. M017 remains blocked on both M015 and M016, including its own prospective freeze requirements. M005 remains externally blocked on approved CodeGG-owned data; crates.io publication remains separately human/legal gated. No plan in another work line became eligible from this conditional branch closure.
