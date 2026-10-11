#!/usr/bin/env python3
"""Write the M013d historical-versus-current provenance and verdict audit.

The command consumes explicitly replayed old sidecars and current generated
sidecars. It writes only a new versioned file under target/m013d/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_OLD = {
    "m013a_quality_analysis": "411ac0915a0dd6ae94710271b1b23bbad830732762b956dcca71500b6f592d6e",
    "m013b_erratum": "07fb99f1e984354a6746f3645f893beadfbbb3fd40ce4e37d4b6a834a0e15901",
    "m013b_diagnostics": "3b489c25eb0fcd51b7dc08d7e9e7a1e1a45a6f16e244cf5a8173e8aceb728da4",
    "m013c_decision_audit": "6560052ba93445288d1b7577c475d0fcaec12035d9838c8c955a91ced2801edf",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def semantic(value):
    """Drop only source-derived provenance fields before semantic comparison."""
    if isinstance(value, dict):
        return {key: semantic(item) for key, item in value.items() if key not in {"input_sha256"}}
    if isinstance(value, list):
        return [semantic(item) for item in value]
    return value


def git_source_hash(commit: str) -> str:
    source = subprocess.run(
        ["git", "show", f"{commit}:scripts/m013b_evaluator.py"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    return hashlib.sha256(source).hexdigest()


def atomic_write_json(path: Path, payload) -> None:
    """Write a complete audit or leave the previous accepted file intact."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-commit", required=True)
    parser.add_argument("--old-root", type=Path, required=True, help="clean pinned checkout used for replay")
    parser.add_argument("--new-commit", default="HEAD")
    parser.add_argument(
        "--allow-host-specific-hashes",
        action="store_true",
        help="record the replayed digests without enforcing the Mac baseline ledger",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "target/m013d/bootstrap-provenance-audit.json")
    args = parser.parse_args()

    old_paths = {
        "m013a_quality_analysis": args.old_root / "target/m013a/quality-analysis.json",
        "m013b_erratum": args.old_root / "target/m013b/m013a-audit-erratum.json",
        "m013b_diagnostics": args.old_root / "target/m013b/m013b-diagnostics.json",
        "m013c_decision_audit": args.old_root / "target/m013c/m013c-decision-audit.json",
    }
    current_paths = {
        "m013a_quality_analysis": ROOT / "target/m013a/quality-analysis.json",
        "m013b_erratum": ROOT / "target/m013b/m013a-audit-erratum.json",
        "m013b_diagnostics": ROOT / "target/m013b/m013b-diagnostics.json",
        "m013c_decision_audit": ROOT / "target/m013c/m013c-decision-audit.json",
    }
    missing = [path for path in (*old_paths.values(), *current_paths.values()) if not path.is_file()]
    if missing:
        raise SystemExit("required audit artifact missing: " + ", ".join(str(path) for path in missing))

    old_sha = {name: sha256(path) for name, path in old_paths.items()}
    if not args.allow_host_specific_hashes and old_sha != EXPECTED_OLD:
        raise SystemExit(f"pinned historical hashes do not match the original ledger: {old_sha}")

    old_erratum = read(old_paths["m013b_erratum"])
    new_erratum = read(current_paths["m013b_erratum"])
    old_decision = read(old_paths["m013c_decision_audit"])
    new_decision = read(current_paths["m013c_decision_audit"])
    m013b_equivalent = semantic(old_erratum) == semantic(new_erratum)
    m013c_equivalent = semantic(old_decision) == semantic(new_decision)
    host_stable_artifacts_equal = all(
        old_sha[name] == sha256(current_paths[name])
        for name in ("m013a_quality_analysis", "m013b_diagnostics")
    )
    verdicts_unchanged = (
        new_erratum.get("gate_verdicts", {}).get("binary", {}).get("verdict") == "negative"
        and new_erratum.get("gate_verdicts", {}).get("choice", {}).get("verdict") == "indeterminate"
        and new_decision.get("retained_disposition", {}).get("binary") == "negative"
        and new_decision.get("retained_disposition", {}).get("choice") == "indeterminate"
    )
    if not (m013b_equivalent and m013c_equivalent and verdicts_unchanged and host_stable_artifacts_equal):
        raise SystemExit("new sidecars differ semantically from the pinned historical result")

    current_sha = {name: sha256(path) for name, path in current_paths.items()}
    output = {
        "schema": "m013d-bootstrap-provenance-audit-v1",
        "old_commit": args.old_commit,
        "new_commit": args.new_commit,
        "old_m013b_source_sha256": git_source_hash(args.old_commit),
        "new_m013b_source_sha256": sha256(ROOT / "scripts/m013b_evaluator.py"),
        "historical_preserved": host_stable_artifacts_equal and m013b_equivalent and m013c_equivalent,
        "model_qualifications_unchanged": True,
        "binary_disposition": "negative",
        "choice_disposition": "indeterminate",
        "semantic_comparison": {
            "m013b_erratum_equivalent_ignoring_input_sha256": m013b_equivalent,
            "m013c_decision_audit_equivalent_ignoring_input_sha256": m013c_equivalent,
            "m013a_and_diagnostics_host_outputs_identical": host_stable_artifacts_equal,
            "verdicts_unchanged": verdicts_unchanged,
        },
        "host_specific_hashes_allowed": args.allow_host_specific_hashes,
        "artifacts": {
            name: {
                "historical_path": str(old_paths[name].relative_to(args.old_root)),
                "historical_sha256": old_sha[name],
                "current_path": str(current_paths[name].relative_to(ROOT)),
                "current_sha256": current_sha[name],
                "difference_reason": (
                    "M013b source hash is embedded in the current erratum input_sha256; M013c then hashes that erratum."
                    if old_sha[name] != current_sha[name] and name in {"m013b_erratum", "m013c_decision_audit"}
                    else "byte-identical historical analyzer output"
                    if old_sha[name] == current_sha[name]
                    else "new source provenance; metric semantics asserted equivalent"
                ),
            }
            for name in old_paths
        },
        "disclaimer": "Mechanical replay and semantic audit only; no new model qualification or held-out inference.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output, output)
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
