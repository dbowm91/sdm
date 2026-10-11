# M013c gate-hardening baseline audit

Status: **implemented** — all five defects closed; see plans/closure/general-decision-model-framework/013c-status.md
Baseline: dbowm91/sdm@11ea106c9af3b1ec362a98e709b530cc0fa137d0 on work/plans-sdm-m013b-quality-gates-diagnostics
Recent hosted checks: https://github.com/dbowm91/sdm/actions/runs/38107890553 (all jobs successful, for the M013b planning baseline)
Historical evidence: plans/closure/general-decision-model-framework/013a-status.md and 013b-status.md
Bounded handoff: plans/implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md

## Outcome summary

All four source defects below were confirmed at the baseline and closed. Implementation also found a
fifth defect not anticipated by the plan — a latent unsorted-quantile bootstrap bug in
`scripts/m013b_evaluator.py` — which is documented in closure §3. No recorded M013a or M013b result
changed; the Binary `negative` and Choice `indeterminate` dispositions are preserved exactly.

## Four concrete source defects

1. scripts/m013b_audit_m013a.py::build_binary_gates: success/failure uses Brier point estimate > 0. Frozen protocol requires 95% GROUP bootstrap CI lower > 0 for positive; upper < 0 for significant negative. Code currently cannot discriminate a sign-consistent but non-significant estimate.
2. scripts/m013b_evaluator.py::_supported: evidence_count > 0, not protocol minimum support (50 independent leakage groups per Binary family). A failing critical gate at n=1 may be promoted to negative even when its separate family support gate says insufficient.
3. build_binary_gates iterates reported slices without validating all protocol-declared required/critical families exist. build_choice_gates iterates present Choice slices and only checks missing critical OOD, not every required OOD. Missing families/controls must fail closed.
4. scripts/m013b_audit_m013a.py negative_controls_do_not_qualify checks control_accuracy >= 0.0, tautologically true for normalized accuracy. Only train majority/always-answer are compressed into a single maximal scalar, despite protocol also listing always-abstain, shuffled-score and context-only. Must compare exact declared control coverage and a legitimate paired learned-vs-control metric, where preregistered.

## Existing correct results to preserve

M013a Binary text-shift improvement -0.2696 and combined shift -0.2699 over train-prior baseline have adequately supported negative group-bootstrap CIs. M013b post-hoc corrected Choice metric found legacy 0/415 fixed-option score responses and new cross head 415/415 nonzero score responses, but 0/276 pairs correct on BOTH counterfactual answers. Original Choice quality was indeterminate. There is NO new unseen held-out qualification evidence and no authorization to modify models.

## Planning/status mismatch

The registry and README said M013b closed, while its dated closure header says conditionally closed; the roadmap still called M013b ready. **Resolved** — all current-facing records now read "conditionally closed" with the historic M013b closure file left untouched. No main-targeted PR exists yet; main is still at M012 merge `2bd0d5af16d143828dcbce77f411b8f3b675e7be`.

## Reason for a narrow M013c

The M013b evaluator made the right methodological improvements but the next predictive test would trust its verdict code. Fixing confidence-interval and manifest-integrity logic first is cheaper, safer and more decisive than starting a new candidate model or broad architecture search. M013c is a verification/contract task; further model work should receive a separately numbered future milestone and prospectively frozen gates.

That reasoning held. All four defects were real, and the gate logic had to be trusted before any further experiment could be meaningful. M013d/M014 remains unregistered and **not unblocked** — hosted CI, a reviewed main merge, and a corrective for the M013b bootstrap defect must precede it, and any successor must prospectively freeze new test groups and numeric thresholds.
