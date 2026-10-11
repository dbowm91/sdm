# M002 closure — Dataset provenance and split integrity

Status: conditionally closed (generic leakage/import safeguards implemented; semantic audit coverage remains bounded)
Implementation commit: `ee0f613`

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Separate target labels from runtime responses across all four semantics | `sdm-data::TargetLabel`; validation checks request/label semantics and candidate/option references | Pass |
| Record source, license, consent scope, label lineage and redistribution state | `Provenance`; required nonempty fields | Pass |
| Content fingerprint and bounded local input | `validate_dataset`; 64 MiB/100k case bounds; `sdm-dataset` capped local bundle reader | Pass |
| Freeze group-disjoint train/dev/test assignments and bind to dataset revision | `freeze_splits`, `validate_split`; unit test covers fingerprint drift and exact assignment coverage | Pass |
| Preserve counterfactual-pair cohesion | Pair identifiers must share leakage group; group assignment is indivisible | Pass |
| Detect exact and near duplicate leakage | `audit_exact_duplicates` canonicalizes requests without request IDs; bounded MinHash/LSH candidate generation applies exact Jaccard verification; unit test checks duplicates, near matches and label conflict | Pass (text/Jaccard only; advisory candidates) |
| Bounded streaming JSONL import and atomic split-manifest finalization | `read_jsonl` streams capped lines; CLI reads cap bundle size and split CLI syncs a unique temporary file before rename | Pass (JSON bundle path remains bounded whole-file input) |
| Synthetic non-CodeGG validation | In-memory generated Binary dataset and focused JSONL/duplicate audit unit tests; no frozen four-semantics qualification corpus | Partial |

## Verification and limitations

`rtk cargo test --workspace --all-features --locked` and strict all-target Clippy pass. No legacy cases or artifacts were rewritten. Provenance records evidence supplied by the dataset owner; the library does not manufacture or verify consent. The dataset schema does not yet carry temporal boundaries or a complete label-source reference graph. Similarity detection is a text-level advisory audit, not semantic/family/pair leakage proof; no generalization claim is made from the synthetic smoke set.

Disposition: conditional because leakage analyses required by the plan are not complete. See M006 follow-up registration in the active registry.
