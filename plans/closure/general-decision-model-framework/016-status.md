# SDM M016 — TinyChoice compact Choice/answerability head and baseline comparison: closure

Status: **CLOSING (implementation + DEV evidence complete on `work/plans-sdm-m016-tinymlp`;
branch CI + review + merged-main CI pending)**.
Plan: `plans/implementation/general-decision-model-framework/016-tinychoice-mlp-and-baseline-comparison.md`.
Planning baseline: `main@0dd2ff470285c09309e3c823fb07dcb76efea229` (M015a merge).

## 1. Disposition

**Positive DEV-only.** The selected TinyMLP candidate (`h=32, seed=16016, lr=0.2,
l2=0.0`, 20 epochs, DEV-balanced threshold 0.63) scores on the authoritative
v2 final-action replay over M015 DEV (720 rows / 200 groups, same bytes and
contract as M015a): conditional argmax 1.0, answerable final 1.0, false
abstention 0.0, no-answer recall 0.9875, causal both-final 0.9812 (157/160),
nuisance both-final 1.0. All three legacy heads and the isolated tree score
final 2/3 with false abstention 1/3 and causal both-final 0.0 on the same
inputs. Paired leakage-group bootstrap diffs (TinyMLP minus each baseline)
for final accuracy are +1/3 with 95% CIs excluding zero.

This is a **synthetic DEV-only** result. It does not qualify the model for any
consumer, publication, or promotion use. M017 readiness: **GO for a new
prospective cohort** (mechanical gates pass; candidate frozen as the fixture
below; no FINAL has been observed).

## 2. Frozen inputs and identity

- Dataset SHA: `sha256:f0d614db315836c41f2a79f998aed47331f0fc234c0e2a3b516638d9ebd702a9`
  (M015 TRAIN/DEV only, 7200 train rows / 2000 groups, 720 DEV rows / 200
  groups, 200 nuisance + 160 causal DEV pairs, 480 answerable DEV rows).
- Split fingerprint: `sha256:7f0e872990247cd21a45a6f7d3c2f08728272fc99763fa7c886eda53dd008e69`
  (empty test partition enforced in code).
- Generator: `scripts/generate_m015_suite.py` groups=2000 seed=150015
  (`sha256:18a4d27cca57c639696bad560302549e837152968b2861ccf23a92e6f4ff57f9`).
- Selected artifact tensor SHA:
  `sha256:58abde027b419fe5a8bb9d106701c3aad0ffde5fa308d49fe1e9cebc492739a9`
  (fixture `fixtures/m016-tinymlp-selected.artifact.json`, 104545 bytes,
  file SHA `sha256:2761dab57ecb5c01350c01c309091dde41e60d9e8e74473cce3d46479c2e66d2`).
- Calibration SHA:
  `sha256:89405fd2e7d489eb178e11bb5a54a63684b48ca3c64090cbaacaabd134c1e32e`.
- Model ID: `tinymlp-choice:sha256:4b4f33…ede843` (training fingerprint over
  TRAIN rows).
- v2 sidecar report SHA:
  `sha256:99e2c929685642bd5635c6dcfe069ecdd3cae9ce09417481ce038b49da7eccbd`.
- Authoritative evidence: hosted linux-x86_64 release run (CI
  `run_m016_comparison.py --out target/m016 --epochs 20`, 36 configs);
  local macOS-arm64 release run selects the identical config with
  identical metrics to 4 decimals (see platform note in M16-7).
- Evidence produced from the M016 working branch at the merged commit;
  release profile (`build_profile=release` in the train report).

## 3. M16-1..8 evidence

| Gate | Verdict | Evidence |
| --- | --- | --- |
| M16-1 additive contract + legacy compat | PASS | `sdm-typed-choice-tinymlp-v1` dispatch in `load_artifact`; `sdm-typed-task-v1`/cross/compositional bytes untouched; `sdm-check-compat` 12/11 green; Rank path rejects TinyMLP (`ExperimentError`, unit-tested) |
| M16-2 shared scorer + separate answerability, 2..128, None | PASS | `tinymlp.rs`: SAME tanh layer, no position/ID input; symmetric mean/max head; 0/1 fail closed; `Choice(None)` only for 2+ options; order-equivariance + ID-rename tests |
| M16-3 finite-diff, determinism, train/runtime parity | PASS | `finite_diff_error < 1e-6` (h=32, 64); seed-identical retrain byte-equal, seed change diverges; loss strictly decreases (new test); `run_m016_train` enforces 1e-9 train-vs-runtime logit parity fail-closed; `decide_typed` argmax regression test (see defects) |
| M16-4 bounded v2 artifact, tamper/size/finite | PASS | Envelope caps (16 MiB, 1M params, 128 candidates) + SHA-before-alloc + declared-count==bytes + finite/dtype/shape checks; hostile tests (shape, oversize, task, category, corruption, drift, ID mismatch) |
| M16-5 same-input comparison + legitimate tree | PASS | `scripts/run_m016_comparison.py`: same dataset/split/encoder bytes for 3 legacy heads (20-epoch `experiment run`), 36-config TinyMLP grid, isolated histogram-GBDT tree (depth 3, 30 estimators, lr 0.1, 32 bins, min-leaf 20, no RNG) on the exact exported vectors; paired diffs with 95% CIs |
| M16-6 DEV-only metrics, CIs, negative controls | PASS | AUROC 0.9997 / AP 0.9999 / ECE 0.0113 / NLL 4e-6; per-family final 1.0 (5/5); per-option-count final 1.0 (k=2..8, support 51..84); group bootstrap CIs in every sidecar; context-only ablation 0.29 vs candidate-only 1.0 (candidate projections embed context+rule by M015 construction — disclosed, same for all heads); tree as independent control |
| M16-7 capacity, resources, ≥2 hosts + third | PASS | h=32: 1607 params / 104545 bytes; h=64: 3143 params (below the provisional 5k–50k: encoder dim is 23, no padding per plan); release latency encode+infer 0.2µs (2 opts) … 9.1µs (128 opts), sub-ms on all counts; training host linux-x86_64 release (authoritative); inference parity test runs on all CI hosts over committed bytes (decisions exact, probs 1e-9). PLATFORM FINDING (M014c precedent): macOS-arm64 release training selects the identical config with identical metrics but differs in last-ulp weight bytes (fixture `453f9ea7…` macOS vs `2761dab5…` linux); CI asserts hosted byte-reproducibility and failed once on the macOS bytes (retained failure) before the fixture was re-frozen to the hosted bytes |
| M16-8 no bleed, no scope creep, honest closure | PASS (pending merge) | `cargo tree -p sdm-runtime` shows no training/eval/Python/GPU/network deps; no CodeGG/corpus/publisher changes; no FINAL observed; this file; branch CI + merged-main CI pending |

## 4. Full grid (36 configs, 20 epochs, release)

Selection (predeclared): max DEV answerable final accuracy → smaller
(width, seed) → min DEV conditional NLL → smaller (lr, l2). Winner h=32 /
seed=16016 / lr=0.2 / l2=0.0. 32 of 36 configs reach final 1.0; the four
shortfalls are seed=16018 + lr=0.05 (final 0.9938–0.9979, FAb 0.002–0.006).
Width 64 shows no DEV gain over 32 at 2× parameters. l2=1e-4 is NLL-neutral
to slightly worse. Mild seed sensitivity at low lr is disclosed; the selected
operating point is not a narrow optimum (28/36 configs are within 0.005 of
it on final accuracy).

## 5. Comparison (authoritative v2 replay, paired diffs)

| Model | Cond argmax | Final ans. | False abst. | No-ans recall | Causal both | Nuisance both |
| --- | --- | --- | --- | --- | --- | --- |
| typed-choice | 1.0 | 0.6667 | 0.3333 | 1.0 | 0.0 | 1.0 |
| typed-choice-cross | 1.0 | 0.6667 | 0.3333 | 1.0 | 0.0 | 1.0 |
| typed-choice-compositional | 1.0 | 0.6667 | 0.3333 | 1.0 | 0.0 | 1.0 |
| shallow GBDT tree (research-only) | 1.0 | 0.6667 | 0.3333 | 1.0 | 0.0 | 1.0 |
| **typed-choice-tinymlp (selected)** | **1.0** | **1.0** | **0.0** | **0.9875** | **0.9812** | **1.0** |

The tree is a legitimate contender (conditional choice perfect, no-answer
recall perfect) whose answerability boundary coincides with the legacy
context-only profile on this DEV cohort; TinyMLP beats it by +1/3 final
(95% paired CI excludes zero) while trading 3 no-answer false positives
(recall 0.9875 vs 1.0). The oracle ceiling (1.0 everywhere by construction,
oracle disagreements 0) is stated, not contended.

## 6. Defects found and fixed (no evidence from buggy code)

1. **Trainer SGD sign**: `train_tinymlp` applied `w += lr*(g − l2·w)`
   (ascent). Caught by the new loss-decrease test; fixed to descent
   `w −= lr*(g + l2·w)` before any evidence run.
2. **Runtime argmax inversion**: `TinyMlpChoiceRuntime::decide_typed` used a
   manual loop updating on `Less`, returning the MINIMUM-score option while
   `choice_probabilities` was correct — caught because the authoritative v2
   replay contradicted trainer-internal eval (final 0.0 vs 1.0). Fixed with
   the legacy `max_by` pattern plus a dedicated regression test
   (`tinymlp_decide_picks_maximum_score_option`); existing equivariance tests
   could not catch it (min is also equivariant). Scratch trial outputs from
   buggy builds were discarded and are not referenced anywhere.

## 7. Stopped / negative alternatives

- Width 64: no DEV gain (documented, not promoted).
- l2=1e-4: neutral-to-worse (not adopted).
- Always-answer threshold policy: degenerate (no-answer recall 0); rejected
  in favor of the legacy balanced-accuracy policy, shared by all heads.
- Full final-action tree parity: the tree is research-only (libm `pow`
  byte-identity is host-local); only the Rust artifact claims cross-host
  byte parity, and only for inference on committed bytes.

## 8. Security / resource matrix

No artifact code execution, no remote input, no telemetry, no external
teacher; local synthetic paths only; atomic no-overwrite outputs under
`target/m016/`; interrupted runs leave no accepted partial (writes are
create-new + link). Peak RSS recorded where available (null on macOS).
16 MiB / 1M-param caps enforced in code, not just documentation.

## 9. M017 readiness

GO: one frozen primary (`fixtures/m016-tinymlp-selected.artifact.json`,
SHA above, DEV threshold 0.63 bound in calibration), prescribed baselines
(the three legacy artifacts regenerate deterministically; tree is
research-only and must be refit only on TRAIN/DEV), v2 contract frozen,
parity harness committed. M017 must not reuse M015 case/group IDs and must
preregister before observing any final labels.
