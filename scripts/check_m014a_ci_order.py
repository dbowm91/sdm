#!/usr/bin/env python3
"""M014c CI ordering regression (Work A5).

Fails if future CI schedules artifact-dependent unit tests before provisioning.

- Parses .github/workflows/ci.yml as text (no yaml dependency).
- Asserts the pure analyzer step (test_m014a_analyzer.py) appears before
  the canary generation step (run_m014a_dev_canary.py), which appears before
  the dependent canary test step (test_m014a_canary.py) on every verify host.
- Asserts no step runs the wildcard 'test_m014a_*.py' before provisioning
  (that wildcard includes the dependent canary tests and reproduces run
  38408167153: 1 failure + 4 errors on clean checkout).
- Asserts the old broad 'test_m014_*.py' wildcard (which also matches
  test_m014a_canary.py) is not used before provisioning.

Usage: python3 scripts/check_m014a_ci_order.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def main() -> int:
    raw = CI.read_text()
    # Strip YAML comments to avoid matching explanatory text (e.g. comments
    # that mention test_m014a_canary.py as an example of what NOT to do).
    # Keep only code lines: drop full-line comments and trailing comments.
    code_lines = []
    for line in raw.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Remove trailing ` # comment` (naive: split on ' #' — safe for our CI).
        if " #" in line:
            line = line.split(" #", 1)[0]
        code_lines.append(line)
    text = "\n".join(code_lines)

    # Find positions of key commands in file order (code only).
    def pos(pattern: str) -> int:
        m = re.search(pattern, text)
        return m.start() if m else -1

    # Only match actual unittest invocations, not prose.
    p_pure = pos(r"discover.*test_m014a_analyzer\.py")
    p_gen = pos(r"run_m014a_dev_canary\.py")
    p_dep = pos(r"discover.*test_m014a_canary\.py")
    p_wild_m014a = pos(r"discover.*test_m014a_\*\.py")
    p_wild_m014 = pos(r"discover.*test_m014_\*\.py")

    errors = []
    if p_pure == -1:
        errors.append("pure analyzer step test_m014a_analyzer.py missing from ci.yml")
    if p_gen == -1:
        errors.append("canary provisioning step run_m014a_dev_canary.py missing from ci.yml")
    if p_dep == -1:
        errors.append("dependent canary step test_m014a_canary.py missing from ci.yml")
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    # Order: pure before gen before dep.
    if not (p_pure < p_gen < p_dep):
        print(f"FAIL: CI order must be pure ({p_pure}) < canary-gen ({p_gen}) < dependent ({p_dep})", file=sys.stderr)
        return 1

    # Wildcard test_m014a_*.py before provisioning reproduces 38408167153.
    # Allow it ONLY after provisioning (p_gen). If wildcard appears before gen, fail.
    if p_wild_m014a != -1 and p_wild_m014a < p_gen:
        print("FAIL: wildcard test_m014a_*.py scheduled before canary provisioning; "
              "this reproduces hosted run 38408167153 (missing target/m014a/canary/*). "
              "Split into test_m014a_analyzer.py (pure) before gen and test_m014a_canary.py after gen.",
              file=sys.stderr)
        return 1

    # Broad test_m014_*.py also matches test_m014a_canary.py; before gen it fails.
    if p_wild_m014 != -1 and p_wild_m014 < p_gen:
        print("FAIL: wildcard test_m014_*.py (matches test_m014a_canary.py) scheduled before "
              "canary provisioning; use explicit test_m014_representability.py / test_m014_suite.py "
              "for the pure step.", file=sys.stderr)
        return 1

    print(f"CI order OK: pure@{p_pure} < canary-gen@{p_gen} < dependent@{p_dep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
