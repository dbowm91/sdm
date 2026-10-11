# M013c gate-hardening baseline audit

Status: planning-only source inspection; no code/evaluation performed
Baseline: dbowm91/sdm@11ea106c9af3b1ec362a98e709b530cc0fa137d0 on work/plans-sdm-m013b-quality-gates-diagnostics
Recent hosted checks: https://github.com/dbowm91/sdm/actions/runs/38107890553 (all jobs successful)
Historical evidence: plans/closure/general-decision-model-framework/013a-status.md and 013b-status.md
Bounded handoff: plans/implementation/general-decision-model-framework/013c-qualification-gate-hardening-corrective.md

## Four concrete source defects

1. scripts/m013b_audit_m013a.py::build_binary_gates: success/failure uses Brier point estimate > 0. Frozen protocol requires 95% GROUP bootstrap CI lower > 0 for positive; upper < 0 for significant negative. Code currently cannot discriminate a sign-consistent but non-significant estimate.
2. scripts/m013b_evaluator.py::_supported: evidence_count > 0, not protocol minimum support (50 independent leakage groups per Binary family). A failing critical gate at n=1 may be promoted to negative even when its separate family support gate says insufficient.
3. build_binary_gates iterates reported slices without validating all protocol-declared required/critical families exist. build_choice_gates iterates present Choice slices and only checks missing critical OOD, not every required OOD. Missing families/controls must fail closed.
4. scripts/m013b_audit_m013a.py negative_controls_do_not_qualify checks control_accuracy >= 0.0, tautologically true for normalized accuracy. Only train majority/always-answer are compressed into a single maximal scalar, despite protocol also listing always-abstain, shuffled-score and context-only. Must compare exact declared control coverage and a legitimate paired learned-vs-control metric, where preregistered.

## Existing correct results to preserve

M013a Binary text-shift improvement -0.2696 and combined shift -0.2699 over train-prior baseline have adequately supported negative group-bootstrap CIs. M013b post-hoc corrected Choice metric found legacy 0/415 fixed-option score responses and new cross head 415/415 nonzero score responses, but 0/276 pairs correct on BOTH counterfactual answers. Original Choice quality was indeterminate. There is NO new unseen held-out qualification evidence and no authorization to modify models.

## Planning/status mismatch

The registry and README say M013b closed, while its dated closure header says conditionally closed; roadmap still calls M013b ready. Reconcile current-facing records to "M013b conditionally closed — mechanics complete; source outside main" without rewriting its closure. No main-targeted PR exists yet; main is still at M012 merge 2bd0d5af16d143828dcbce77f411b8f3b675e7be.

## Reason for a narrow M013c

The M013b evaluator made the right methodological improvements but the next predictive test would trust its verdict code. Fixing confidence-interval and manifest-integrity logic first is cheaper, safer and more decisive than starting a new candidate model or broad architecture search. M013c is a verification/contract task; further model work should receive a separately numbered future milestone and prospectively frozen gates.
