"""Verify the committed, pre-test M014 qualification freeze."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = ROOT / "docs/m014-freeze-v1.json"
    manifest = json.loads(manifest_path.read_text())
    errors = []
    for rel, expected in manifest["sha256"].items():
        path = ROOT / rel
        if rel.startswith("target/"):
            path = ROOT / rel
        if not path.is_file() or sha(path) != expected:
            errors.append(f"hash mismatch: {rel}")
    for rel in manifest["candidate_reports"]:
        report = json.loads((ROOT / "target/m014/candidates-v2" / rel).read_text())
        if report.get("test_evaluation_performed") is not False or report.get("outcomes"):
            errors.append(f"candidate report used test data: {rel}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(json.dumps({"verified": True, "manifest_sha256": sha(manifest_path),
                      "files": len(manifest["sha256"]), "test_evaluation": "not performed"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
