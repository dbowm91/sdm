# M013b evaluation-integrity audit — planning evidence

Source baseline: `dbowm91/sdm@694da1a002cf29c62724be6ba881240f43aac9c2` (work/plans-sdm-m013-predictive-quality-corrective)
Status: planning audit only; no new test observation or training
Frozen history: `docs/m013a-protocol-v1.md`, `plans/closure/general-decision-model-framework/013a-status.md`

## Incorrect interpretation of target-relative score sign

`scripts/analyze_m013a_quality.py` derives each half-pair target margin as `logit[target_index] - logit[1-target_index]`. If physical logits remain [2,1] for BOTH inputs while the target changes from option 0 to option 1, the values are [+1,-1] despite **zero** logit/probability or selected-option response to the input. Consequently, the frozen `raw_target_margin_changes_sign` at 276/276 is a **label-alignment sign** measure, not proof of counterfactual model sensitivity.

Corrected diagnostics should compare identity-normalized, SAME-option logits/probabilities and selected option across the two inputs, preserve target-correctness as an independent measure and correctly handle abstentions. The historic zero pairs with both final targets correct is a distinct unfavorable observation that does not become positive by this relabeling.

## Positive classifier bypass

Choice classification in `scripts/analyze_m013a_quality.py` uses the paired cross-minus-legacy final-answerable-accuracy CI for positive/negative/indeterminate, while `unsupported_primary_slices` and counterfactual outcomes are recorded **after**, not enforced as mandatory gates. Frozen protocol requires support plus counterfactual and critical OOD gates. M013a Choice OOD answerable-group supports 44/44/45 fall below 50 even though total OOD groups >=50; thus a favorable primary delta alone must never be promoted.

Do not invent missing frozen numerical thresholds after seeing data. A prospective separate experiment must define these **before** final inference. Keep historical M013a report/protocol/data/closure unchanged and add a clearly labeled analytic erratum.

## Negative evidence / diagnostic hypotheses, NOT causal proofs

Binary Brier improvement over train prior: ID-a +0.2115, ID-b +0.2280, load shift +0.2207, text shift -0.2696, combined shift -0.2699. Text-vocabulary unseen coordinates encode zero; suspect nuisance reliance or dev distribution undercoverage but verify with train/dev source-only one-factor probes and coefficient/contribution inspection. M013a test may not select a fix.

Choice: both legacy/cross final answerable accuracy 0.50, paired delta 0; overall answerability AUROC 1.00 but no-answer recall 0.683, OOD text/combined 0.00. Explicit cross terms are mechanically representable but observed quality did not improve. Train/dev diagnostic truth tables must separate expressivity/optimization, option ID/candidate mapping, raw option scores, calibrated threshold and final abstention. Do not mistake target-relative margin change for learned sensitivity.

## Engineering/release observations

The predecessor branch `work/plans-sdm-m013-predictive-quality-corrective` was at `694da1a002cf29c62724be6ba881240f43aac9c2`, CI run 38105560778 successful. Main remained at M012 merge `2bd0d5af16d143828dcbce77f411b8f3b675e7be`; no M013/M013a PR exists yet. Existing v1 and additive cross model runtime must not change merely to correct an analyzer. The roadmap final readiness text and planning index retain stale "M013 ready" / "M012 PR pending" phrasing. The correct next step is evaluation-integrity testing and source-based diagnosis, then optionally a separately frozen, prevalidated-quality experiment. Do not regenerate observed M013a fixtures as allegedly unseen evaluation data.
