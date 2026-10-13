#!/usr/bin/env python3
"""M015a CI ordering regression.

Fails if CI schedules the DEV-only replay before its TRAIN/DEV baselines.

- Parses .github/workflows/ci.yml as text (no yaml dependency).
- Asserts the pure v2 contract step (test_m015a_final.py) appears before
  the baseline generation step (run_m015_baselines.py), which appears before
  the dependent DEV replay step (analyze_m015a_final_actions.py).
- The broad `test_m015_*.py` wildcard matches both pure M015 and pure M015a
  unit tests (neither needs artifacts), so it may appear before provisioning.
  Only the replay script is dependent and must follow baselines.

Usage: python3 scripts/check_m015a_ci_order.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def main() -> int:
    raw = CI.read_text()
    code_lines = []
    for line in raw.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if " #" in line:
            line = line.split(" #", 1)[0]
        code_lines.append(line)
    text = "\n".join(code_lines)

    def pos(pattern: str) -> int:
        m = re.search(pattern, text)
        return m.start() if m else -1

    p_pure = pos(r"discover.*test_m015a_final\.py")
    p_gen = pos(r"python3 scripts/run_m015_baselines\.py")
    p_dep = pos(r"python3 scripts/analyze_m015a_final_actions\.py")

    errors = []
    if p_pure == -1:
        errors.append("pure v2 contract step test_m015a_final.py missing from ci.yml")
    if p_gen == -1:
        errors.append("baseline generation step run_m015_baselines.py missing from ci.yml")
    if p_dep == -1:
        errors.append("dependent replay step analyze_m015a_final_actions.py missing from ci.yml")
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    if not (p_pure < p_gen < p_dep):
        print(
            f"FAIL: CI order must be pure ({p_pure}) < baselines-gen ({p_gen}) < replay ({p_dep})",
            file=sys.stderr,
        )
        return 1
    print(f"CI order OK: pure@{p_pure} < baselines-gen@{p_gen} < replay@{p_dep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
