# M010 closure — Trainable Binary, Choice and Score heads

Status: closed for end-to-end mechanics; no predictive-quality or application claim
Implementation commit: included in this closure commit
Hard predecessor: M009, accepted in `009-status.md`
Next milestone: M011, active

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Binary train/package/reload/infer/evaluate | `typed-binary` logistic head consumes typed numeric, boolean, categorical and text fields. Its validated Binary response is evaluated with accuracy, Brier, log-loss, precision, recall and F1. | Pass as mechanics |
| Choice with exact option IDs and no-choice behavior | `typed-choice` produces normalized probabilities only over caller-provided option IDs. A separate answerability head trains on `Choice(None)` and chooses its abstention threshold from dev answerability labels. Missing/mismatched option projections are rejected. | Pass as mechanics |
| Score on the caller rubric | `typed-score` predicts within request min/max and evaluates original-scale MAE/RMSE. Non-finite and malformed bounds are rejected by request validation. | Pass as mechanics |
| Typed Rank remains operational | `typed-linear` uses the same encoder and explicit v2 artifact dispatch. Existing lexical linear and nonlinear paths remain available. | Pass |
| Dev-only calibration provenance | Typed v2 calibration payload now carries a non-empty dev partition fingerprint and a task-specific policy ID; runtime validates policy, threshold and digest integrity. The frozen linear v1 artifact format is unchanged. | Pass |
| Disjoint synthetic end-to-end workflows and held-out mutation | Checked-in Binary/Choice/Score data and split manifests feed CLI train -> package -> reload -> infer -> evaluate workflows. Tests mutate test labels/features and verify model/calibration identities remain unchanged. | Pass as mechanics |
| Docs, CLI and CI | README Quickstart lists all six Rank and semantic configs; `docs/typed-task-heads.md` describes task contracts; CI runs the three semantic workflows. | Pass |

## Observed held-out semantic runs

All values below are from small generated corpora and establish mechanics only; they do not imply generalization.

| Task | Dataset SHA-256 | Split fingerprint | Model SHA-256 | Calibration SHA-256 | Test result |
| --- | --- | --- | --- | --- | --- |
| Binary | `sha256:96d255fc752bef3c3ccee074bce93f5d5f65408ebd8b2150da9047d946a8bf84` | `sha256:916d32d34c5d747720b8a2bdd9afa630bb4100be501ec56fb37e300776d949bc` | `sha256:081ed24e42b5066aefef538c761eb6a325b1172396ae9d211d8ff365a19c47f0` | `sha256:3c7914e95e39ac4ecdbd7f054c4fff02a33d50c3e8dda656f037d67df168b1ab` | 6/6 correct; Brier 0.0000591, log-loss 0.00762; 0 abstentions |
| Choice | `sha256:6fe99ce53fb2e1ac6320f5dd3d47314c3dd886eb9e3634d0946af6e087454076` | `sha256:c190e583d117faf909920cb33fbfe6fa1c59d64bbf5214b95fa9b6438b2f99a6` | `sha256:e1feeb94664d9fcbab2d05df9bc526ce876045e44ab0b6ce7498a747daa40d93` | `sha256:0d42b1949984388910861f390293e048b65113c4087b11df2ba12a37095a1b64` | 4 answerable choices correct, log-loss 0.00768; 2 no-choice abstentions |
| Score | `sha256:cca3bf5231db7042c735a642208444e8cbe9827d68c80aa6e9a69727ba78f8f1` | `sha256:60741f6182a206ee3b18c445c1b7a74c788d8773cdc100b1f0fec02ef7eff3ac` | `sha256:fd9f626680cffd15d2820146c2350754ddd41532885ee64633ca9067a605adb1` | `sha256:aff5842201bf8e8c8d18151683d6eb0bcc5063cb80badb995a325805c980fac2` | 5 examples; MAE 0.07655, RMSE 0.09889; 0 abstentions |

Each report and full artifact digest is persisted under `target/experiments/` when run locally; CI reruns the checked-in configs. Held-out partitions are small (5–6 examples), so quality confidence is indeterminate. Choice accuracy omits the two explicit abstentions from the four scored answerable cases.

## Verification

- `rtk cargo fmt --all -- --check` — pass.
- `rtk cargo test --workspace --all-features --locked` — pass, 32 tests across 19 suites.
- `rtk cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — pass.
- `rtk cargo check -p sdm-runtime --locked` and `rtk cargo tree -p sdm-runtime --locked` — pass; runtime-only graph has no data, training, evaluation or experiment crate.
- `rtk target/debug/sdm experiment run --config` for the three semantic configs and three Rank configs — pass locally on Apple Silicon.
- Frozen compatibility command — pass, 12 validated fixtures, 11 runtime executions; artifact digest remains `sha256:b9484ce8b8afe2b345693e084468c89a628462e86faf1e9683c28ee53de6597e`.
- Hosted workflow is configured to run the semantic configs, but hosted results for this revision were not observed during closure.

## Limits and disposition

These compact heads and generated formulas show that typed task data can traverse training, bounded artifact validation, local serving and semantic metrics. They are not useful-quality evidence. Choice abstention is calibrated on dev answerability labels and may under-abstain under distribution shift. SHA-256 fields establish identity and corruption detection, not publisher authenticity. Runtime has no network dependency or external actuation authority. The v1 compatibility result remains exact.

M010 is closed for its mechanics acceptance. M011 is unblocked and active. M005 remains externally gated and unchanged.
