#!/usr/bin/env python3
"""Validate Cargo SPDX metadata and emit a reviewable third-party inventory.

This is a metadata gate, not a license-text scanner or legal opinion. For OR
expressions, this project records MIT as its selected branch when available.
"""
import json
import re
import sys
from pathlib import Path


TOKEN = re.compile(r"\s*(\(|\)|AND\b|OR\b|WITH\b|[A-Za-z0-9][A-Za-z0-9.+:-]*)")
KNOWN = {"MIT", "Apache-2.0", "Unlicense", "Unicode-3.0"}


def normalize(expression):
    return expression.replace("MIT/Apache-2.0", "MIT OR Apache-2.0")


def parse_spdx(expression):
    tokens = []
    offset = 0
    while offset < len(expression):
        match = TOKEN.match(expression, offset)
        if not match:
            raise ValueError(f"unrecognized SPDX syntax at {expression[offset:]!r}")
        tokens.append(match.group(1))
        offset = match.end()
    position = 0

    def primary():
        nonlocal position
        if position >= len(tokens):
            raise ValueError("expected license identifier")
        token = tokens[position]
        if token == "(":
            position += 1
            value = disjunction()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError("unclosed parenthesis")
            position += 1
            return value
        if token in {"AND", "OR", "WITH", ")"}:
            raise ValueError(f"unexpected token {token}")
        if token not in KNOWN:
            raise ValueError(f"license identifier {token!r} requires review")
        position += 1
        licenses = {token}
        if position < len(tokens) and tokens[position] == "WITH":
            position += 1
            if position >= len(tokens) or tokens[position] not in KNOWN:
                raise ValueError("unknown or missing SPDX exception after WITH")
            licenses.add(tokens[position])
            position += 1
        return {"alternatives": [{"licenses": licenses}]}

    def conjunction():
        nonlocal position
        value = primary()
        while position < len(tokens) and tokens[position] == "AND":
            position += 1
            right = primary()
            value = {"alternatives": [
                {"licenses": left["licenses"] | branch["licenses"]}
                for left in value["alternatives"]
                for branch in right["alternatives"]
            ]}
        return value

    def disjunction():
        nonlocal position
        value = conjunction()
        while position < len(tokens) and tokens[position] == "OR":
            position += 1
            value["alternatives"].extend(conjunction()["alternatives"])
        return value

    parsed = disjunction()
    if position != len(tokens):
        raise ValueError(f"unexpected token {tokens[position]}")
    return parsed["alternatives"]


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: audit_cargo_licenses.py CARGO_METADATA.json INVENTORY.json")
    source, destination = map(Path, sys.argv[1:])
    metadata = json.loads(source.read_text())
    packages = []
    errors = []
    for package in sorted(metadata["packages"], key=lambda item: (item["name"], item["version"])):
        expression = package.get("license")
        item = {"name": package["name"], "version": package["version"],
                "source": package.get("source") or "workspace", "license": expression,
                "license_file": package.get("license_file")}
        if not expression:
            errors.append(f"{item['name']} {item['version']}: missing license expression")
        else:
            try:
                alternatives = parse_spdx(normalize(expression))
                # MIT is selected for disjunctive grants when available. For
                # conjunctive expressions all listed terms apply.
                mit_branch = next((branch["licenses"] for branch in alternatives
                                   if "MIT" in branch["licenses"]), None)
                if len(alternatives) > 1 and mit_branch is None:
                    raise ValueError("ambiguous OR expression has no configured branch selection")
                selected = mit_branch if mit_branch is not None else alternatives[0]["licenses"]
                item["selected_branch"] = " AND ".join(sorted(selected))
                item["selection"] = "MIT branch selected by SDM policy" if "MIT" in selected else "sole/first SPDX-compatible branch; human review required"
            except ValueError as error:
                errors.append(f"{item['name']} {item['version']}: {error}")
        packages.append(item)
    if errors:
        raise SystemExit("license inventory rejected:\n" + "\n".join(errors))
    report = {
        "package_count": len(packages),
        "policy": "SPDX metadata only; MIT is selected from OR expressions when offered. Human/legal review remains required before registry distribution.",
        "limitations": ["Does not inspect package source or license text.",
                        "Does not prove the declared SPDX expression is accurate.",
                        "Does not establish legal compatibility or satisfy notice obligations."],
        "packages": packages,
    }
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"validated SPDX expressions and inventoried {len(packages)} locked workspace/dependency packages")


if __name__ == "__main__":
    main()
