# M015 development evidence (TRAIN/DEV only)

Status: **implementation evidence complete on the feature branch; reviewed merge and merged-main CI pending**. This is research infrastructure evidence, not model qualification. M016 remains blocked until M015 closure is accepted and merged.

## Corpus and independent checks

Run: `scripts/generate_m015_suite.py`, seed `150015`, 2,000 independent TRAIN groups and 200 disjoint DEV groups, generated under ignored `target/m015-baselines-v7/`. Generator SHA-256: `18a4d27cca57c639696bad560302549e837152968b2861ccf23a92e6f4ff57f9`. Task-spec SHA-256: `905441b3f25344cdbe0708538ad44b2005506b602019693da530b82893c2613c`. The manifest names the five source-defined rules: `all_required`, `any_required`, `exclusive` (observable XOR/XNOR inversion), `threshold`, and `category_and_flag`.

TRAIN contains 7,200 rows / 2,000 groups; its raw JSONL SHA-256 is `6d1910242f885fff1d67802952a28783ca6c20304363d56befd8f7d117cd9743`. DEV contains 720 rows / 200 groups; its raw JSONL SHA-256 is `e2c9b5b137506b13ef9b40f0b7ed8f8c6f9a89e2de1b16ef2d667c51de04e9db`. Each rule has 40 DEV groups (32 answerable and 8 no-answer). Four families / 160 groups / 576 rows form the fixed-rule track; the observable XOR/XNOR family has 40 groups / 144 rows in the rule-conditioned track. Each group has 2–4 rows. All groups and pair members stay within one partition.

The analyzer independently recomputed labels with zero disagreements. DEV includes 200 nuisance pairs that preserve labels, candidate identities, and candidate semantics while perturbing declared nuisance context and reversing option order; it also includes 160 causal-flip pairs that change one declared candidate feature and the target while holding context fixed. The group-bootstrap DEV controls were: always-None accuracy `0.3333` (95% CI `[0.3086, 0.3596]`), first-option accuracy `0.5556` (`[0.5391, 0.5731]`), and semantic-oracle upper bound `1.0` (`[1.0, 1.0]`). The oracle is a test of task representability, not a learned baseline.

## Existing learned heads

`scripts/run_m015_baselines.py` materialized one typed Choice corpus from the same membership, feature schema, candidate universe, and group splits, then ran the existing `typed-choice`, `typed-choice-cross`, and `typed-choice-compositional` architectures for 20 epochs. The adapter supports the measured 2,000-group baseline budget; its typed dataset was 58.6 MB, below the 64 MiB cap. All reports declare `train-dev-only`; each has an empty test membership and `test_evaluation_performed=false`. No candidate or threshold was selected from these results.

All three models reached DEV answerable accuracy `1.0` (2,000-replicate group-bootstrap 95% CI `[1.0, 1.0]`), no-answer recall `1.0`, causal-pair correct-on-both `1.0`, and nuisance-pair prediction agreement `1.0`. Their shared answerability Brier score was `0.1055939`, log loss `0.289023`, and ten-bin ECE `0.0471949`. Conditional Choice NLL / Brier were:

| Architecture | Conditional NLL | Conditional Brier | Artifact SHA-256 | Artifact bytes |
| --- | ---: | ---: | --- | ---: |
| `typed-choice` | 0.00009443 | 4.2899e-8 | `e9b303ac69b71ab8d1503404dc41d28ffb2afb965f4d574ab7f25511950508cb` | 11,963 |
| `typed-choice-cross` | 0.00002226 | 2.2512e-9 | `b89fd3b41ffcf53a24642097b609b1d45436921fe8bcf6137edc7d3e8692be06` | 24,699 |
| `typed-choice-compositional` | 0.00001250 | 7.7325e-10 | `01b760d217f177e8b42a2887c638f6a06de021d377f7ef00b22064433713884b` | 111,055 |

Dataset SHA-256: `bef4c9a8260950bed5430066c11602f481ae66ad4ff6498d55beaac1c12e53e9`. Split fingerprint: `7f0e872990247cd21a45a6f7d3c2f08728272fc99763fa7c886eda53dd008e69`. Report byte SHA-256 values: typed Choice `0ff408887e716fb6aa6a57e6985a404e81d2756a875be9eecb4dbfe73bb84ed4`, cross `109a89990ceb1fdad498bb1b9a3c2b18dacfc39592165c88963835291d69dc5c`, compositional `772216d954046ccf328a2ef094618c01e455713c10cd0d09daa1f2871aa3c2f1`.

These deterministic-task scores do not establish generalization or model superiority. All three models share the same underlying typed preprocessing and synthetic feature contract. M015 adds no runtime architecture and makes no consumer-quality claim.

## Verification and limitations

Commands completed locally on the implementation branch:

- `cargo fmt --all -- --check`
- `cargo test --workspace --all-features --locked` — 46 passed
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — clean
- `cargo check -p sdm-runtime --locked` and `cargo tree -p sdm-runtime --locked` — no training framework or Python dependency in the runtime graph
- `cargo check --manifest-path examples/standalone-consumer/Cargo.toml --locked`
- `cargo run -p sdm-training --bin sdm-check-compat --locked -- fixtures/codegg-compatibility-v1.jsonl artifacts/compatibility-rank-v1.json` — 12 frozen fixtures validated, 11 runtime executions
- `python3 -m unittest discover -s scripts` — 175 passed, 2 host-specific skips
- `python3 -m unittest discover -s scripts -p 'test_m015_*.py'` — 10 passed
- `python3 scripts/analyze_m015_dev.py --train target/m015-baselines-v7/corpus/train.jsonl --dev target/m015-baselines-v7/corpus/dev.jsonl --out target/m015-baselines-v7/analyzer-report-closure.json` — zero oracle disagreements and expected pair/group support

The TRAIN/DEV generation is bounded and streams into unique ignored `target/` outputs. The baseline adapter rejects unsupported larger training budgets before starting because the existing dataset loader is capped at 64 MiB. The 2,000-group run took about 4m26s for data conversion, training, and evaluation; peak process RSS observed during baseline training was approximately 1.6 GB on this host. This is trainer usage, not inference resource evidence. A first baseline attempt exposed unbounded random note vocabulary; the generator now uses a finite nuisance vocabulary and the successful run above was generated from the corrected source. Superseded experiments remain isolated under ignored `target/m015*` paths.

No M017 final cohort or M015 final partition was generated. No M014 final configuration was run or modified. No frozen fixture, split manifest, historical report hash, or closure record was changed. Hosted CI for the final implementation commit and reviewed merge / merged-main CI are still pending; these are required before full integration closure or M016 can begin.
