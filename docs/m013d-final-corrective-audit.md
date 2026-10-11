# M013d final corrective — concrete source and provenance audit

Status: planning evidence only, no corrective code run.
Baseline: dbowm91/sdm@03c4a982219ffa830b7c0aba9dbb19a541cae56c on `work/plans-sdm-m013c-qualification-gate-hardening`
Hosted CI: https://github.com/dbowm91/sdm/actions/runs/38109647535 — passed all ten jobs.
Handoff: plans/implementation/general-decision-model-framework/013d-bootstrap-repair-and-source-integration.md

The one live unsafe bootstrap is `scripts/m013b_evaluator.py::group_bootstrap`: its calls to `quantile(replicates_values,tail)` interpolate RNG-ordered rather than ascending percentile samples. M013c's distinct `scripts/m013c_evaluator.py::_quantile` sorts correctly. A minimal source fix should make direct M013b quantiles safe too; no model changes are warranted. Validate with unsorted permutation, skewed nondegenerate grouped bootstrap, degenerate constant groups, invalid arguments and deterministic seed checks.

Provenance caveat: `scripts/m013b_audit_m013a.py` embeds a SHA256 of `scripts/m013b_evaluator.py` in `input_sha256`, and `scripts/m013c_qualification_audit.py` reads/hashes the M013b sidecar. A source fix necessarily changes the CURRENT regenerated M013b/M013c sidecar bytes and hashes. Historical source/evidence remains immutable at pinned commits and must be replayed there; new source's numerical verdicts should be semantically equal with a new, explicitly documented versioned SHA ledger. Do not require impossible byte identity between differently fingerprinted code.

At planning, main is M012 at `2bd0d5af16d143828dcbce77f411b8f3b675e7be`, and the M013c stack at `03c4a982219ffa830b7c0aba9dbb19a541cae56c` is 15 commits ahead, zero behind. No main PR exists. Source integration is a normal reviewable PR, not a direct main push. Separate green PR/branch from merged-main confirmation and from crates.io human/legal clearance or CodeGG M005 corpus.

The M013a Binary text/combined-shift negatives and Choice indeterminate outcome are retained. No new prospective quality inference is allowed in M013d. Once these integration/estimator corrections are accepted, a future model experiment may be proposed at M014 on a newly preregistered independent suite.
