# SDM M017 — TinyChoice prospective synthetic qualification: closure

Status: **CLOSED (final consumed exactly once; PR #7; disposition
synthetic-only NEGATIVE)**.
Plan: `plans/implementation/general-decision-model-framework/017-tinychoice-prospective-qualification-and-portability.md`.
Planning baseline: `main@c17492a5c6348bab842a6c39650897733eb5c77f` (M016 merge).

## 1. Disposition

**Synthetic-only negative.** On the frozen prospective final cohort (1000
groups / 3560 rows, m017- namespace, unseen surface vocabulary), the frozen
M016 TinyMLP candidate keeps perfect answerable ranking (final 1.0, false
abstention 0.0) and passes the rule-conditioned track (exclusive final 1.0),
but its DEV-calibrated answerability does not transfer: no-answer recall
0.118 (gate ≥ 0.90), causal both-final 0.185 (gate ≥ 0.75), ECE 0.30 (gate ≤
0.05), and no superiority over legacy heads on answerable final (paired diff
0.0). Fixed-rule robustness: FAIL. Rule-conditioned composition: PASS.
Overall: **negative**. No consumer, publication, or promotion consequence;
no CodeGG or crates.io effect.

## 2. M17-1..9 evidence

| Gate | Verdict | Evidence |
| --- | --- | --- |
| M17-1 independent cohort + support | PASS | `generate_m017_suite.py` (seed 170018, m017- IDs); 1000 final groups, 200 per family ≥ 150 minimum; option IDs disjoint from all M015 bytes; nuisance vocab distinct; freeze-verified in CI |
| M17-2 frozen models + DEV threshold | PASS | TinyMLP fixture bytes SHA-bound (`2761dab5…`), threshold 0.63 in calibration; 3 legacy heads regenerated from frozen code+data with DEV v2 pins matching within 1e-9 |
| M17-3 preregistered numbers/gates | PASS | `docs/m017-protocol-v1.json` (P1, S1–S6, N1–N3, Holm, tracks, ceilings) frozen before inference; preliminary `9889a470` |
| M17-4 acyclic two-phase binding | PASS | Preliminary → final configs → binding `919a78a6`, distinct digests, no placeholder/self-hash; stale/placeholder replay fails (unit-tested); `FINAL_NOT_YET_RUN` at freeze |
| M17-5 canary + pre-final green CI | PASS | 60-group public canary; freeze PR CI green incl. generator support proof, hash/shape tests, evaluator checks |
| M17-6 one read-only inference + ledger | PASS | `run_m017_final.py` once locally; 4 manifests (original bytes committed as `fixtures/m017-final-*.manifest.json`); ledger `docs/m017-final-ledger.json`; no-overwrite; never rerun |
| M17-7 paired CIs + two-track verdicts | PASS | 95% paired-group bootstrap (seed 170018); separate fixed-rule / composition verdicts; no unsupported claims |
| M17-8 three-host canary parity | PASS | Same committed bytes on linux-x86_64/linux-aarch64/macos-aarch64: 0 decision mismatches, max prob delta ≤ 1e-9 (`m017-canary-parity` CI job) |
| M17-9 reviewed integration + main green | PASS (pending) | PR #7 carries freeze (reviewed, CI green pre-final); this evidence commit follows; merged-main CI pending |

## 3. Final numbers (frozen protocol)

| Model | Cond argmax | Final ans. | False abst. | No-ans recall | Causal both | Nuisance both |
| --- | --- | --- | --- | --- | --- | --- |
| typed-choice | 1.0 | 1.0 | 0.0 | 0.361 | 0.000 | 1.000 |
| typed-choice-cross | 1.0 | 1.0 | 0.0 | 0.361 | 0.000 | 1.000 |
| typed-choice-compositional | 1.0 | 1.0 | 0.0 | 0.361 | 0.000 | 1.000 |
| **typed-choice-tinymlp** | **1.0** | **1.0** | **0.0** | **0.118** | **0.185** | **0.780** |

Answerability AUROC 0.993 (ranking preserved) with ECE 0.302 (absolute
calibration shifted). P1 paired diffs 0.0 (all CIs contain 0).

## 4. Mechanism (why answerability did not transfer)

Coordinate decomposition of the frozen answerability logit
`z = W·[ctx;mean;max] + b` (bias −5.75) on matched unavailable rows shows
the M015 DEV decision relied on text-vocabulary coordinates 9/14 (and
siblings): M015 surface tokens activate them with large learned weights
(|w| up to 23.6, l2 = 0.0 unregularized winner) contributing ≈ −18 to `z`
(abstain); the M017 novel vocabulary is out-of-vocabulary → those
coordinates read 0.0 → `z` rises ≈ +20 (from −9.4 to +10.5) → always answer.
The `available` flag coordinate does not dominate. The conditional scorer
transfers (shared candidate semantics), but the answerability head overfit
M015 surface text — undetectable on DEV (shared vocabulary), exposed by the
prospective surface shift that independence required. Both legacy heads
(context-only linear) fail the same way, corroborating a distribution
property rather than a TinyMLP-specific defect: no materialization,
threshold, label, support, or leakage defect was found (all fail-closed
checks pass; AUROC preserved; manifests SHA-verified).

Logit-responsiveness note: causal-pair logit vectors move strongly on both
cohorts (median L2 causal 9.1 DEV / 8.5 final vs nuisance 0.27 both) — raw
logits are NOT flip-invariant in the plan's sense. The preregistered N2
control as literally defined (argmax flips > 50%) reads 0.108 on final but
identically 0.106 on DEV, so it cannot discriminate and is recorded as a
failed control with this flawed operationalization noted; it is not part of
either verdict formula. Argmax stability across flips is expected for this
architecture (pair correctness comes via answerability abstention, which is
what failed here).

## 5. Stopped / indeterminate alternatives

None triggered: support powered on all families, no leakage (namespace +
audit), no SHA drift, no interruption, exactly one inference. A
threshold recalibration on final would be a protocol violation and was not
performed (it would also be scientifically meaningless post-hoc). Any
follow-up (regularized retrain, vocab-agnostic answerability, new cohort)
is a NEW milestone, never a reinterpretation of this test.

## 6. Security / resource matrix

Synthetic-only inputs; read-only models and data; no network/telemetry/
external calls; local paths only; atomic single-use ledger; original
manifest bytes committed unmodified. p50 inference and RSS well within
ceilings (µs-scale; see M016 resources).

## 7. Provenance

Freeze: preliminary `sha256:9889a470…`, binding `sha256:919a78a6…`
(`FINAL_NOT_YET_RUN`), 4 final configs in `fixtures/`. Models: tinymlp
fixture file `sha256:2761dab5…`; legacy heads regenerated (DEV pins
1e-9). Analyzer `scripts/analyze_m017_final.py` + `docs/m017-protocol-v1.json`
both SHA-bound. Re-analysis of committed bytes in CI reproduces these
verdicts without re-running inference.
