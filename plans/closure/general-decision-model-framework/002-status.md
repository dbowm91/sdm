# M002 closure — Dataset provenance and split integrity

Status: conditionally closed  
Implementation commit: `e02fab714540868f5619e2c2dc2c6aaf0549d8eb`

## Requirement-to-evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Separate target labels from runtime responses across all four semantics | `sdm-data::TargetLabel`; validation checks request/label semantics and candidate/option references | Pass |
| Record source, license, consent scope, label lineage and redistribution state | `Provenance`; required nonempty fields | Pass |
| Content fingerprint and bounded local input | `validate_dataset`; 64 MiB/100k case bounds; `sdm-dataset` capped local bundle reader | Pass |
| Freeze group-disjoint train/dev/test assignments and bind to dataset revision | `freeze_splits`, `validate_split`; unit test covers fingerprint drift and exact assignment coverage | Pass |
| Preserve counterfactual-pair cohesion | Pair identifiers must share leakage group; group assignment is indivisible | Pass |
| Detect canonical/near duplicates and perform full leakage audit | Not implemented; only explicit group and pair metadata are checked | Gap |
| Streaming import and atomic split-manifest finalization | Bundle reader is bounded but reads the complete JSON file; split CLI writes a synced temporary file then renames | Partial |
| Synthetic non-CodeGG validation | In-memory generated 100-row Binary dataset exercised in tests; no four-semantics checked-in fixture | Partial |

## Verification and limitations

Workspace tests and Clippy pass. No legacy cases or artifacts were rewritten. Provenance records evidence supplied by the dataset owner; the library does not manufacture or verify consent. The dataset schema does not yet carry temporal boundaries or a complete label-source reference graph. Similarity detection and streaming JSONL import remain corrective work; no generalization claim is made from the synthetic smoke set.

Disposition: conditional because leakage analyses required by the plan are not complete. See M006 follow-up registration in the active registry.
