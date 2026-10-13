# M014c closure audit — source-grounded, no historical rerun

Status: planning audit for M014c; NOT implementation, CI verification or model qualification.
Baseline: `c27724746ebc674919aff32a93d6baf74e104e13` on `work/plans-sdm-m014a-m014b-qualification-recovery`.
Main at planning: `7b9bb3c929db2c9d492a1b86b54a4f57c61a9e37`
Plan: `plans/implementation/general-decision-model-framework/014c-closure-evidence-reconciliation.md`

## Latest hosted verification

[Actions run 38408167153](https://github.com/dbowm91/sdm/actions/runs/38408167153) COMPLETED FAILURE at source `c27724746ebc674919aff32a93d6baf74e104e13`; Linux x64 verify failed, Linux ARM64 and macOS ARM64 verification cancelled after detecting the failing prerequisite-dependent test step; Rank and Choice portability skipped. MSRV job succeeded. Plan-only prior run 38399878048 success does not qualify implemented code.

In `.github/workflows/ci.yml`, the step `Verify M014a frozen-artifact evaluator and DEV-CANARY` runs `python3 -m unittest discover -s scripts -p 'test_m014a_*.py'` **before** `python3 scripts/run_m014a_dev_canary.py`. `test_m014a_canary.py` expects `target/m014a/canary/manifest.json`, five evaluated reports and `qualification.json`. Hosted clean workspaces lack them, giving 1 failure + 4 errors out of 30. This is a deterministic CI orchestration defect, not evidence that the Rust evaluate-only path failed (its five M014a Rust tests passed in the logs). No positive hosted closure claim is warranted.

## Historical M014b freeze/reference mismatch

`scripts/freeze_m014b.py` uses `dummy_freeze = "sha256:" + "1" * 64` in all five `fixtures/m014b-final-*.evaluate.json`, while `docs/m014b-freeze-v1.json` holds an actual independently committed prospective manifest. The dummy makes the *embedded freeze binding unverified*. Existing final outputs cannot be rewritten; use non-self-referential detached historical Git/SHA-256 attestation, describe scope as detached rather than embedded, and leave the placeholder visible.

The closure text `plans/closure/general-decision-model-framework/014b-status.md` supplies candidate and generated-data digests plus truncated/placeholder final-output references, but not all original final report and qualification SHA-256 values. Final outputs are under ignored `target/m014b/final/`. Recover original bytes only if available, otherwise report each digest unavailable. Never generate replacement evidence from a new inference on the consumed cohort.

## Hardcoded portability gate

`scripts/run_m014a_dev_canary.py` writes `"three_host_parity": True` to its local resource JSON, while `scripts/qualify_semantic_v2.py::evaluate_resources` trusts this flag to pass mandatory parity. A local deterministic rerun is NOT proof of Linux x64 / Linux ARM64 / macOS ARM64 matching output. Implement independent per-host same-artifact per-case digests and an aggregator with host-set checking; a new CI run, not the failed one, must supply true parity evidence. If code changes to the historical M014b-frozen analyzer are required, do not modify that file: version the new analyzer.

## Historical model outcome and boundary

M014b's new synthetic cohort used Binary `(active AND available) XOR rule_b` and Choice XNOR (opposite M014 XOR), using already-frozen M014 artifacts. Historical local result: Binary negative with text-shift Brier vs prior CI roughly [-0.4018,-0.0962] and Choice negative with answerable text-shift accuracy difference vs legacy [-0.5,-0.5], overall negative. Those claims should be labeled local historical evidence until source/provenance audit; the test cannot be rerun to fix CI or digests.

No CodeGG model promotion, no new M014b final evaluation, no general-architecture M015 registration, no cargo publish or legal approval implied.
