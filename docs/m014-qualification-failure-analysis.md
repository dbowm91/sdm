# M014 qualification failure — source findings and corrective design

Status: planning audit, not a new experiment.
Repository baseline: main@7b9bb3c929db2c9d492a1b86b54a4f57c61a9e37; 10-job CI 38117915516 passed.
Historical evidence: plans/closure/general-decision-model-framework/014-status.md, docs/m014-freeze-v1.json, docs/m014-protocol-v1.json, artifacts/m014/final-v1/.
Action: M014a exact-artifact evaluator correction (ready), then M014b fresh qualification (blocked).

### Frozen artifact mismatch
crates/sdm-experiment/src/main.rs supports only experiment run. crates/sdm-experiment/src/lib.rs::run_semantic always invokes train_typed_task then serializes a new artifact even when evaluate_test=true. Compared full serialized payloads: Binary baseline 38/100 f64 weights different with max abs delta 3.55e-15; Binary constant mask 41/100 weights and tiny intercept delta with max abs 1.07e-14. Schema, encoder and training fingerprints matched. The exact artifact SHA is NOT the frozen candidate SHA. Float tolerance must never replace byte SHA validation. Choice artifacts happened to match, but the same retraining hazard applies. Fix must create evaluate-only path that never touches trainer and loads byte-exact artifacts.

### Frozen analysis failure
SemanticExperimentRunManifest serializes test_evaluation_performed=true by omitting the field (serde default true, skip if true). The original Python analyzer treats missing as false; a new analyzer needs versioned schema/partition verification. It also stores one Binary tuple per leakage group, silently discarding one counterfactual row, then iterates that tuple as if it were a list of cases. Must retain full per-group case list and bootstrap groups rather than rows. Its original incomplete controls and resource evidence cannot establish positive qualification.

### Source history and no-rerun boundary
Original M014 produced one-time synthetic aggregate: Binary 0.7839 vs constant-mask 1.0000; Choice legacy and cross 0.5000, compositional 1.0000. Descriptive ONLY; not accepted preregistered quality. Original docs and hashes remain unchanged and test cohort cannot be retried or relabeled.

### Why two independent implementation plans
M014a is an infrastructure correctness milestone: exact SHA frozen artifact inference, complete group/ser-de/control gate machinery and a synthetic DEV-CANARY prove end-to-end functioning before new unseen test construction. M014b depends HARD on this closure, seals a distinct cohort with all required eligible group counts, fixed candidate bytes and numeric protocol, then performs exactly one final inference. Only M014a is ready. This enforces SDM planning governance instead of reopening M014's observed test.

References: plans/003-planning-process.md; docs/m014-protocol-v1.json; scripts/analyze_m014_qualification.py; scripts/m013c_evaluator.py (paired-gate methodology); scripts/validate_future_support.py (eligible subgroup proof). Neither plan authorizes CodeGG promotion or crates.io publication.
