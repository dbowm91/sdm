#!/usr/bin/env python3
"""Inventory Cargo's per-crate package lists and reject sensitive paths."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRATES = ("sdm-core", "sdm-data", "sdm-eval", "sdm-experiment",
          "sdm-nonlinear", "sdm-runtime", "sdm-training")
FORBIDDEN = ("/target/", "/fixtures/", "/artifacts/", "/.env", ".pem",
             "id_rsa", "credentials", "secret")


def main():
    if len(sys.argv) not in {2, 3} or (len(sys.argv) == 3 and sys.argv[2] != "--allow-dirty"):
        raise SystemExit("usage: audit_package_contents.py INVENTORY.json [--allow-dirty]")
    output = Path(sys.argv[1])
    allow_dirty = len(sys.argv) == 3
    inventory = {}
    errors = []
    for crate in CRATES:
        result = subprocess.run(
            ["cargo", "package", "--manifest-path", str(ROOT / "crates" / crate / "Cargo.toml"), "--list"]
            + (["--allow-dirty"] if allow_dirty else []),
            cwd=ROOT, check=True, text=True, capture_output=True,
        )
        paths = sorted(line.strip() for line in result.stdout.splitlines() if line.strip())
        if "Cargo.toml" not in paths or not any(path.startswith("src/") for path in paths):
            errors.append(f"{crate}: package is missing its manifest or source tree")
        for path in paths:
            normalized = "/" + path.lower().lstrip("./")
            if any(marker in normalized for marker in FORBIDDEN):
                errors.append(f"{crate}: forbidden package path {path}")
            if path.startswith("/") or ".." in Path(path).parts:
                errors.append(f"{crate}: unsafe package path {path}")
        inventory[crate] = paths
    if errors:
        raise SystemExit("package contents rejected:\n" + "\n".join(errors))
    output.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    print(f"audited Cargo package file lists for {len(inventory)} crates")


if __name__ == "__main__":
    main()
