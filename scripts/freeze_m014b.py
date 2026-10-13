#!/usr/bin/env python3
"""Freeze M014b prospective cohort BEFORE any final inference (Q4/Q6).

Creates final inference-only EvaluateSpecs (fixtures/m014b-final-*.evaluate.json)
and freeze manifest (docs/m014b-freeze-v1.json) with all SHAs, WITHOUT running
final inference or inspecting test outcomes (only group counts via support).

Must be committed before any `fixtures/m014b-final-*.evaluate.json` run.
After freeze commit + green CI, run the frozen final set ONCE via
`experiment evaluate` (outputs only under target/m014b/final/).
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def file_sha(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()

def membership(ids):
    return "sha256:" + hashlib.sha256(json.dumps(sorted(ids), separators=(",", ":")).encode()).hexdigest()

def main():
    # Protocol SHA (real file SHA, finalized before freeze).
    protocol_path = ROOT / "docs/m014b-protocol-v1.json"
    protocol_sha = file_sha(protocol_path)
    generator_path = ROOT / "scripts/generate_m014b_suite.py"
    generator_sha = file_sha(generator_path)
    evaluator_path = ROOT / "scripts/qualify_semantic_v2.py"
    evaluator_sha = file_sha(evaluator_path)
    # Datasets (generated, under target/, SHAs recorded for CI regen check).
    bin_data = ROOT / "target/m014b/binary.json"
    choice_data = ROOT / "target/m014b/choice.json"
    bin_dataset_file_sha = file_sha(bin_data)
    choice_dataset_file_sha = file_sha(choice_data)
    # Splits (committed under fixtures/).
    bin_split_path = ROOT / "fixtures/m014b-binary-v1.split.json"
    choice_split_path = ROOT / "fixtures/m014b-choice-v1.split.json"
    bin_split = json.loads(bin_split_path.read_text())
    choice_split = json.loads(choice_split_path.read_text())
    bin_split_file_sha = file_sha(bin_split_path)
    choice_split_file_sha = file_sha(choice_split_path)
    bin_membership = membership(bin_split["test"])
    choice_membership = membership(choice_split["test"])
    # Support reports (generated, under target/).
    bin_support = ROOT / "target/m014b/binary-support.json"
    choice_support = ROOT / "target/m014b/choice-support.json"
    bin_support_sha = file_sha(bin_support)
    choice_support_sha = file_sha(choice_support)
    # Candidates: existing exact frozen M014 bytes (preferred, no retraining).
    candidates = {
        "binary-baseline": "artifacts/m014/binary-baseline-v1.artifact.json",
        "binary-mask": "artifacts/m014/binary-constant-mask-v1.artifact.json",
        "choice-legacy": "artifacts/m014/choice-legacy-v1.artifact.json",
        "choice-cross": "artifacts/m014/choice-cross-v1.artifact.json",
        "choice-compositional": "artifacts/m014/choice-compositional-v1.artifact.json",
    }
    cand_shas = {k: file_sha(ROOT / v) for k, v in candidates.items()}
    # Exclusion digest of known M014/M013a FINAL test cases (prove distinctness).
    m014_bin = json.loads((ROOT / "fixtures/m014-binary-v1.split.json").read_text())
    m014_choice = json.loads((ROOT / "fixtures/m014-choice-v1.split.json").read_text())
    m013a_bin = json.loads((ROOT / "fixtures/m013a-binary-v1.split.json").read_text()) if (ROOT / "fixtures/m013a-binary-v1.split.json").exists() else {"test": []}
    m013a_choice = json.loads((ROOT / "fixtures/m013a-choice-v1.split.json").read_text()) if (ROOT / "fixtures/m013a-choice-v1.split.json").exists() else {"test": []}
    known = sorted(set(m014_bin["test"] + m014_choice["test"] + m013a_bin.get("test", []) + m013a_choice.get("test", [])))
    exclusion = "sha256:" + hashlib.sha256(json.dumps(known, separators=(",", ":")).encode()).hexdigest()
    # Assert no overlap (fail-closed before freeze).
    assert not (set(known) & set(bin_split["test"])), "M014b binary overlaps FINAL"
    assert not (set(known) & set(choice_split["test"])), "M014b choice overlaps FINAL"
    # Provenance from generated datasets (for EvaluateSpecs).
    bin_prov = json.loads(bin_data.read_text())["provenance"]
    choice_prov = json.loads(choice_data.read_text())["provenance"]
    # Final EvaluateSpecs (inference-only, exact SHA, unique outputs under target/m014b/final/).
    # protocol_sha = real protocol file SHA; freeze_sha = dummy ones (freeze manifest SHA recorded separately in qualification, not circular).
    # This matches M014a canary pattern (dummy freeze) and satisfies C2 via protocol + evaluator SHAs in qualification.
    dummy_freeze = "sha256:" + "1" * 64
    final_map = [
        ("fixtures/m014b-final-binary-baseline.evaluate.json", "target/m014b/binary.json", "fixtures/m014b-binary-v1.split.json", "artifacts/m014/binary-baseline-v1.artifact.json", "target/m014b/final/binary-baseline.report.json", "typed-binary", bin_prov, bin_split),
        ("fixtures/m014b-final-binary-mask.evaluate.json", "target/m014b/binary.json", "fixtures/m014b-binary-v1.split.json", "artifacts/m014/binary-constant-mask-v1.artifact.json", "target/m014b/final/binary-mask.report.json", "typed-binary", bin_prov, bin_split),
        ("fixtures/m014b-final-choice-legacy.evaluate.json", "target/m014b/choice.json", "fixtures/m014b-choice-v1.split.json", "artifacts/m014/choice-legacy-v1.artifact.json", "target/m014b/final/choice-legacy.report.json", "typed-choice", choice_prov, choice_split),
        ("fixtures/m014b-final-choice-cross.evaluate.json", "target/m014b/choice.json", "fixtures/m014b-choice-v1.split.json", "artifacts/m014/choice-cross-v1.artifact.json", "target/m014b/final/choice-cross.report.json", "typed-choice-cross", choice_prov, choice_split),
        ("fixtures/m014b-final-choice-compositional.evaluate.json", "target/m014b/choice.json", "fixtures/m014b-choice-v1.split.json", "artifacts/m014/choice-compositional-v1.artifact.json", "target/m014b/final/choice-compositional.report.json", "typed-choice-compositional", choice_prov, choice_split),
    ]
    for out_rel, ds_rel, sp_rel, art_rel, report_rel, arch, prov, split in final_map:
        art_p = ROOT / art_rel
        env = json.loads(art_p.read_text())
        spec = {
            "dataset_path": ds_rel, "split_path": sp_rel, "artifact_path": art_rel, "report_path": report_rel,
            "expected_artifact_sha256": file_sha(art_p),
            "expected_dataset_sha256": split["dataset_sha256"],
            "expected_split_fingerprint": split["fingerprint"],
            "expected_test_membership_sha256": membership(split["test"]),
            "expected_architecture": arch,
            "expected_artifact_architecture": env["architecture"],
            "expected_feature_schema_sha256": env["required_feature_schema_sha256"],
            "expected_calibration_sha256": env["calibration_sha256"],
            "protocol_sha256": protocol_sha,
            "freeze_sha256": dummy_freeze,
            "provenance": prov,
        }
        (ROOT / out_rel).write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    # Freeze manifest (committed BEFORE final inference).
    freeze = {
        "freeze_id": "sdm-m014b-freeze-v1",
        "status": "prospective-freeze-before-final-test",
        "protocol": "docs/m014b-protocol-v1.json",
        "protocol_sha256": protocol_sha,
        "generator": "scripts/generate_m014b_suite.py",
        "generator_sha256": generator_sha,
        "evaluator": "scripts/qualify_semantic_v2.py",
        "evaluator_sha256": evaluator_sha,
        "datasets": {
            "target/m014b/binary.json": bin_dataset_file_sha,
            "target/m014b/choice.json": choice_dataset_file_sha,
        },
        "splits": {
            "fixtures/m014b-binary-v1.split.json": bin_split_file_sha,
            "fixtures/m014b-choice-v1.split.json": choice_split_file_sha,
        },
        "split_fingerprints": {
            "binary": bin_split["fingerprint"],
            "choice": choice_split["fingerprint"],
        },
        "test_memberships": {
            "binary": bin_membership,
            "choice": choice_membership,
        },
        "support_reports": {
            "target/m014b/binary-support.json": bin_support_sha,
            "target/m014b/choice-support.json": choice_support_sha,
        },
        "candidates": {v: cand_shas[k] for k, v in candidates.items() for k in [k] if True},  # placeholder, fixed below
        "candidate_reports": [
            "binary-baseline.report.json",
            "binary-mask.report.json",
            "choice-legacy.report.json",
            "choice-cross.report.json",
            "choice-compositional.report.json",
        ],
        "final_configs": {},
        "exclusion_digest_known_m014_m013a_final": exclusion,
        "note": "Freeze BEFORE any fixtures/m014b-final-*.evaluate.json run. Run frozen final set ONCE after freeze commit + green CI; outputs only under target/m014b/final/.",
    }
    # Fix candidates dict (above comprehension was convoluted).
    freeze["candidates"] = {v: cand_shas[k] for k, v in candidates.items()}
    # Final config SHAs (with dummy freeze_sha, deterministic).
    for out_rel, _, _, _, _, _, _, _ in final_map:
        freeze["final_configs"][out_rel] = file_sha(ROOT / out_rel)
    # Support verdicts (must be pass before freeze; already validated).
    freeze["support_verdicts"] = {
        "binary": json.loads((ROOT / "target/m014b/binary-support.json").read_text())["verdict"],
        "choice": json.loads((ROOT / "target/m014b/choice-support.json").read_text())["verdict"],
    }
    assert freeze["support_verdicts"]["binary"] == "pass" and freeze["support_verdicts"]["choice"] == "pass", "support must pass before freeze"
    (ROOT / "docs/m014b-freeze-v1.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"freeze": "docs/m014b-freeze-v1.json", "protocol_sha": protocol_sha, "exclusion": exclusion, "final_configs": len(final_map)}, indent=2))

if __name__ == "__main__":
    main()
