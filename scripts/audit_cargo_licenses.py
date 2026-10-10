#!/usr/bin/env python3
"""Fail release qualification if Cargo metadata omits a dependency license."""
import json
import sys
from pathlib import Path

source, destination = map(Path, sys.argv[1:3])
metadata = json.loads(source.read_text())
packages = sorted(
    ({"name": p["name"], "version": p["version"], "license": p.get("license")}
     for p in metadata["packages"]),
    key=lambda p: (p["name"], p["version"]),
)
missing = [p for p in packages if not p["license"]]
if missing:
    raise SystemExit(f"packages missing license metadata: {missing}")
destination.write_text(json.dumps({"package_count": len(packages), "packages": packages}, indent=2) + "\n")
print(f"audited license metadata for {len(packages)} locked workspace and dependency packages")
