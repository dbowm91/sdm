# SDM General Framework M002 — Dataset Provenance and Split Integrity

Status: blocked (hard M001)
Primary class: infrastructure
Repository baseline at planning: dbowm91/sdm@8139b064bdcf3212e8f6fd912e801a479b55751c; re-audit when unblocked
Roadmap: plans/subsystems/general-decision-model-framework-roadmap.md#m002--generic-dataset-provenance-and-frozen-splits
ADR: plans/adrs/ADR-0001-general-framework-and-model-boundaries.md
Hard dependency: M001 closed with stable typed-feature/schema identity
Soft dependencies: none
Output consumer: M003 evaluator, M004 trainer, M005 CodeGG dataset adapter

## 1. Objective

Make dataset import, provenance, labeling and split assignment independent of training architecture and application. Produce a usable sdm-data crate and immutable leakage-aware manifests, while maintaining current sdm-training v1 entrypoints.

## 2. Current evidence and motivation

crates/sdm-training/src/lib.rs currently owns DecisionCase (schema 1), read_jsonl, case validation, SHA-256 bucket split at 70/15/15 by leakage_group, model fitting, threshold tuning and evaluate. The example CodeGG-derived compatibility-rank training set contains only four cases; the 12/11 CodeGG fixtures test shape/identity, not generalization. Source data currently represents targets with an entire DecisionResponse, including prediction provenance, which should not be the only representation of ground-truth labels. Historical CodeGG experiments demonstrated family and counterfactual leakage risks and invalidation of quality claims by using contaminated test partitions.

## 3. Non-goals and invariants

Do not create a background CodeGG data collector, scrape local files, train models, generate teacher labels via network, auto-export sessions, assume model-generated labels are human truth, or redesign CodeGG consent. No old fixture or historical result rewrite. No need for a new learned model. Data schema can represent Binary/Choice/Score/Rank even when local artifacts do not implement every inference family. Do not assert meaningful generalization from smoke fixtures.

## 4. Proposed data contract

- New independent crates/sdm-data with a versioned DatasetManifestV2 (dataset ID/revision, source/license/consent scope, intended semantics, feature-schema digest, dataset content hash, count, label lineage, group/temporal/family axes and audit metadata).
- Versioned example record: immutable case ID; bounded validated request/feature projection; target-label type independent of runtime DecisionResponse; label provenance (reviewed/human/synthetic/teacher), source reference, explicit leakage_group; optional family/group/counterfactual pair and temporal boundary; optional split assignment only through frozen manifest.
- Label shapes: Binary truth; Choice one eligible option or documented no-choice; Score finite bounded target; Rank per-candidate relevance set/graded relevance plus explicit no-relevant/abstention ground truth. Independent multi-relevance, no forced exclusive-choice conversion.
- Strict limits on JSONL bytes, case count, per-field sizes, class sizes and label arrays; reject duplicate case IDs, ambiguous candidate identities, broken cross-references, missing license/provenance required for distribution, non-finite values, malformed Unicode, impossible scores.
- Dataset provenance/consent is recorded, not manufactured. Missing permissions to redistribute corpus -> local-only source reference / withheld fixture, not a checked-in copy.
- Existing v1 DecisionCase/reader remains as compatibility adapter; make absence of provenance explicit and prevent legacy smoke data from being promoted to qualification without review.

## 5. Ordered work packages

A. Define source-of-truth schema and golden examples for all four semantics. Keep typed features from M001 and v1 conversion semantics explicit; distinguish labels from model responses.

B. Implement sdm-data import/validation and streaming capped parser with stable hashes. Provide manual local-only import from approved JSONL; never assume a CodeGG checkout exists.

C. Implement immutable seeded split manifests with group-disjointness; separate train/dev/test and deliberately excluded tool-family/task-family domains; optional temporal and counterfactual pair cohesion. Freeze split IDs and content hashes on first accepted manifest and verify fingerprint on every reuse; do not silently resplit when cases change.

D. Introduce leakage analyses: duplicate/near-duplicate canonical case projections, shared family IDs, counterfactual pairs crossing partitions, metadata-based train/test overlap. Do not call near-duplicate detection a perfect semantic leakage guarantee; report what cannot be proven.

E. Update sdm-training to use sdm-data for new cases without breaking read_jsonl public entrypoint or changing v1 reproducibility fixture. Record any old split behavior explicitly in the compatibility path.

F. Document data-capture approval process and create a small *non-CodeGG* synthetic dataset exercising Binary, Choice, Score and multi-relevant Rank; prove portability and split fidelity.

## 6. Storage and failures

JSONL datasets and split manifests are versioned and content-addressed; write with temporary same-directory file + fsync where supported + atomic rename, verify reread before treating finalized. Do not overwrite immutable split manifests when a dataset revision changes. Interrupted import must leave prior usable version intact. No application database changes; no telemetry. Handle invalid path, truncated import, duplicate, permission denial, and size overrun without partial qualified results.

## 7. Verification and guards

- Deterministic split under reordering; group and pair/family holdouts disjoint; no train-to-test reuse of calibration observations.
- Fail when test cases/labels are missing from declared split, source hashes drift, labels reference unknown candidates, or semantic family mismatches.
- CI invokes a deterministic data validate + split audit command (create a CLI/bin or example and document its exact invocation); smoke-scale sets allowed for parser tests but rejected as inferential qualification when thresholds not met.
- Test all four label families on non-CodeGG fixtures. Run legacy 12/11 compatibility and v1 training reproducibility before/after.
- Standard workspace fmt/test/Clippy/runtime-only check, and bound limits against adversarial datasets; avoid implicit model downloads.

## 8. Acceptance

sdm-data loads and validates independent task datasets; frozen manifests prove non-overlapping groups and exact hashes; synthetic non-CodeGG fixtures pass; v1 CodeGG data stays untouched; training dependency graph remains out of sdm-runtime; negative input paths fail without half-written artifacts; limitations and source-license/consent state are disclosed.

## 9. Stop conditions

Stop if new metadata requires inventing consent provenance for existing CodeGG cases, changes historical test assignments, hides mixed-group contamination, silently reassigns partitions, makes SDM responsible for user session capture, or adds training deps to runtime-only graph. Register a separate CodeGG-side capture/export plan if genuinely needed.

## 10. Closure evidence

plans/closure/general-decision-model-framework/002-status.md must record SHA/PR, dataset/schema examples, every provenance axis, frozen hashes/splits, leakage audit, test results, non-CodeGG dataset proof, compatibility outcome, limitations and registry update. M003 becomes ready after accepted closure.
