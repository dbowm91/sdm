# M013a closure — Independent quality-suite integrity rerun

Status: **conditionally closed** — the independent suite is valid and reproducible; Binary synthetic quality is negative under text/combined shift and Choice quality is indeterminate. Nothing is promoted or qualified for production.

Plan: `plans/implementation/general-decision-model-framework/013a-independent-quality-suite-integrity-rerun.md`  
Freeze commit (before M013a held-out inference): `4768716d97cc58ea338d8099bfe09a1e57d0d8f9`  
Protocol SHA-256: `600bb458ca445660c2021cb2a7f27dbd38815599b8ce1d7a85cfdf1bace64a8e`  
Implementation branch: `work/plans-sdm-m013-predictive-quality-corrective`

## Frozen inputs and execution

| Item | SHA-256 |
| --- | --- |
| Choice dataset | `52189cafbe52f5dbca66f286257cf91a5c961e06029e8a92a5013ee46257e586` |
| Choice split | `5c00db7cd2e31ca1864f885eeea57a59a06a952de1307d94f8f1f0b76f92fea4` |
| Binary dataset | `edc857be6cc0b06e21b81df77f62a4bc261befa6f7adc58abf4788e6b842c1da` |
| Binary split | `97d86626281429236ece128c513878e2b54a984935cde9014876db278d1f5c21` |
| Choice legacy artifact | `160d8c5589ef5641a503b694f0fd33d09f2f4e298ca1431d92ac7d37f3a98310` |
| Choice legacy report | `f7e121572dcbef1b00b97c6d1fe642872a7db8329124793a0bc98529e3820406` |
| Choice cross artifact | `5908d65fe7aaf8d72a5375013fe7b81f548ed9f0c639ea237679a88a21ec9759` |
| Choice cross report | `ace1d48ddc6bf1ddc6da1c0cc5fce70e4d57622a8a0c5f1aaaef51d2bfd492cf` |
| Binary artifact | `a2af9cd5c48ea39ef3e940fb63df05c47c7598384c52505248f3b0b42c55eaad` |
| Binary report | `41da211d3ffd34a77b5519962fe08b5db4abdc2b9bef00a544dac1ca5b28b5ad` |
| Analyzer source | `b9228b6ed8c86248895d790ff6a76e37534c8f1c72d2b256d53ff1f62ea46d3d` |
| Analyzer output | `411ac0915a0dd6ae94710271b1b23bbad830732762b956dcca71500b6f592d6e` |

The corpus and split regenerate byte-identically. Pair validation checks equality after replacing only request/case identifiers, targets, and active values. Group membership is partition-disjoint; OOD families are held out into test only, with zero excluded rows. Each task has 1,532 groups; Choice has 830 test rows and Binary 798. The OOD no-answer slices have 22, 23, and 22 Choice groups. The corrected analyzer additionally counts *answerable* groups for Choice accuracy: the three OOD accuracy slices have 44, 44, and 45 groups, below the preregistered 50-group requirement, and are therefore indeterminate. The suite remains useful and valid; those slice estimates are not treated as qualified evidence.

The three fixed configurations ran once after the freeze commit. The initial invocation stopped at pre-fit provenance validation because the config lineage string did not equal the frozen dataset metadata; it did not train or score test rows. The configs were corrected and included in the amended freeze commit before the successful one-time inference. A post-inference analyzer-only correction interprets omitted false-valued abstention fields as false (historical-compatible serialization) and applies the 50-group threshold to answerable groups. It did not change candidates, training, thresholds, protocol, or test inference.

## Requirement-to-evidence matrix

| Requirement | Evidence | Disposition |
| --- | --- | --- |
| Fresh test groups, one-factor pairs, and correct OOD membership | `scripts/generate_m013a_quality_suite.py`; `scripts/validate_m013a_freeze.py`; hashes and support above | Pass. M013's observed test rows were not reused. |
| Fixed once-only Binary, legacy Choice, and cross Choice evaluation | Configs under `fixtures/m013a-*.experiment.json`; reports under ignored `target/m013a/`; analyzer under `scripts/analyze_m013a_quality.py` | Pass. Seed 14014, 120 epochs, learning rate 0.2, train-only encoder, dev-only cutoff, 10,000 grouped bootstrap replicates. |
| Choice primary result and counterfactuals | Answerable final accuracy is 0.50 for each head; cross-minus-legacy paired difference is 0.00 with 95% interval [0.00, 0.00] over 276 answerable groups. Both heads' raw target margins changed sign across all 276 answerable active-flip pairs, but both final decisions were correct on 0.00 of pairs. Answerability AUROC is 1.00 overall; no-answer recall is 0.683 overall and 0.00 on text/combined OOD. | **Indeterminate** architecture comparison; the cross head has no measured accuracy advantage. All OOD Choice accuracy slices have insufficient answerable-group support and are indeterminate. These synthetic results do not qualify either head. |
| Binary primary and nuisance evidence | Train-prior Brier improvement: ID-a `+0.2115` [0.1962, 0.2269], ID-b `+0.2280` [0.2125, 0.2417], load shift `+0.2207` [0.2014, 0.2375], text shift `-0.2696` [-0.2893, -0.2522], combined shift `-0.2699` [-0.2875, -0.2522]. | **Negative.** Text and combined shifts are significantly worse than the train-prior baseline. No test-selected fix was attempted. |
| Runtime/artifact contract and compatibility | Workspace tests, runtime-only dependency graph, old compatibility fixtures, staged package consumer; cross artifact has 100 declared terms, 334 trainable parameters, and 18,794 bytes in the Linux portability run. | Pass mechanically. Existing v1 and legacy typed artifacts remain supported. |
| M011 history | `scripts/check_m011_frozen_reports.py`; Linux x64 CI | Pass. Frozen report byte identities are checked in CI; local non-Linux score/rank report bytes differ as previously recorded and were not substituted for Linux fingerprints. |
| Platform portability | [CI run 38104943513](https://github.com/dbowm91/sdm/actions/runs/38104943513); stable Linux x64, Linux ARM64, Apple Silicon and Rust 1.89 jobs passed. All three Choice portability jobs consumed the same Linux-trained artifact SHA `91a5581f9a81cf65f7dc1083e36929e17b712ca12d424eb197d801f235a9e2a9`; malformed artifact rejection passed on each. | Pass for tested hosts. The benchmark records host-specific latency and RSS; it is not a production service SLO. |
| Resource, privacy, authority, and publication boundaries | Synthetic MIT-only fixtures; offline runtime; no network, user corpus, CodeGG data, teacher, or deployment | Pass. Crates.io publication remains behind the existing human/legal gate; M005 remains externally gated. |

## Verification

Completed locally:

- `cargo fmt --all -- --check`
- `cargo test --workspace --all-features --locked`
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`
- `cargo check -p sdm-runtime --locked`; runtime example check; runtime dependency tree inspection
- standalone consumer check and frozen CodeGG compatibility fixtures
- M013a corpus regeneration, split regeneration and byte comparisons, freeze validator, one-time inference and deterministic analyzer
- cross-choice benchmark at 2/16/64/128 options; malformed artifact rejection
- staged package consumer against extracted workspace package archives; package inventory and license inventory audits

`cargo package --workspace --locked`'s registry verification resolves the already published `sdm-runtime 0.1.0`, which predates the additive constructor used by the new `sdm-experiment` source. CI therefore uses `cargo package --workspace --locked --no-verify`, then compiles an independent consumer against all freshly extracted workspace archives via `scripts/check_staged_consumer.py`. The staged archive consumer passed; this preserves meaningful package verification without claiming that the unpublished release has already been published.

## Disposition and future-plan readiness

M013a is conditionally closed with valid negative/indeterminate synthetic evidence. Its integrity objective and mechanical acceptance passed; predictive quality did not. Binary's text/combined-shift regression remains unresolved. Choice's pairwise cross head did not outperform the diagonal head, and OOD answerable accuracy support was below threshold. Neither result authorizes promotion or a post-test model change.

No further implementation plan is currently registered as ready or active. M014 is mentioned only as future research and requires separate approval; it is not unblocked or activated by M013a. M005 remains blocked by its unavailable approved CodeGG corpus and consumer-owned evidence. Crates.io publication remains independently gated by human/legal review. The next quality architecture or policy change requires a newly scoped plan, new sealed test groups, and a new preregistration before inference.
