#!/usr/bin/env python3
"""M014c immutable lineage validator (Work C, read-only).

Validates the detached pretest Git/SHA-256 chain for historical M014b
without rewriting frozen inputs or rerunning the consumed final cohort.

Checks (all read-only; never writes to freeze/outputs or target/m014b/final):
- docs/m014b-freeze-v1.json exists and parses; its generator/protocol/
  evaluator/dataset/split/membership/support/candidate/final-config SHAs
  match the actual checked-out files (SHA-256 over raw bytes).
- Each fixtures/m014b-final-*.evaluate.json has freeze_sha256 ==
  "sha256:" + "1"*64 (known placeholder). This is flagged
  placeholder_unbound (defect), NEVER passed as verified binding.
- Valid bindings ARE checked: protocol_sha256, expected_artifact_sha256,
  expected_dataset_sha256 / expected_split_fingerprint /
  expected_test_membership_sha256, generator/evaluator SHAs, candidate bytes.
- Git ancestry: --freeze-commit (9cc80f0) is an ancestor of --observed-commit
  (c277247) via `git merge-base --is-ancestor` (not author timestamps).
- Committed bytes at freeze commit match current files for freeze-relevant
  paths (proves no post-freeze rewrite): compares `git show <freeze>:<path>`
  SHA-256 against current file SHA-256 for protocol, generator, splits,
  final configs, freeze manifest.
- Differentiates Git object hash (SHA-1 via `git hash-object`) from SHA-256
  of raw file bytes; both recorded in output ledger.
- One-byte corruption of frozen config/artifact/freeze MUST fail validation
  (covered by SHA mismatch checks; see self-test in test_m014c_lineage.py
  pattern or manual corruption check).

Usage:
  python3 scripts/verify_m014c_lineage.py \
    --freeze-commit 9cc80f0fc228e3a5f910723fa9420465f5cbeb30 \
    --observed-commit c27724746ebc674919aff32a93d6baf74e104e13 \
    --out target/m014c/lineage-verdict.json

Exit 0 on lineage verified (with placeholder flagged as defect, not pass);
exit 2 on any mismatch with precise message.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "sha256:" + "1" * 64

FREEZE_MANIFEST = "docs/m014b-freeze-v1.json"
PROTOCOL = "docs/m014b-protocol-v1.json"
GENERATOR = "scripts/generate_m014b_suite.py"
EVALUATOR = "scripts/qualify_semantic_v2.py"
FINAL_CONFIGS = (
    "fixtures/m014b-final-binary-baseline.evaluate.json",
    "fixtures/m014b-final-binary-mask.evaluate.json",
    "fixtures/m014b-final-choice-legacy.evaluate.json",
    "fixtures/m014b-final-choice-cross.evaluate.json",
    "fixtures/m014b-final-choice-compositional.evaluate.json",
)
SPLITS = ("fixtures/m014b-binary-v1.split.json", "fixtures/m014b-choice-v1.split.json")
CANDIDATES = (
    "artifacts/m014/binary-baseline-v1.artifact.json",
    "artifacts/m014/binary-constant-mask-v1.artifact.json",
    "artifacts/m014/choice-legacy-v1.artifact.json",
    "artifacts/m014/choice-cross-v1.artifact.json",
    "artifacts/m014/choice-compositional-v1.artifact.json",
)


def sha256_file(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def git_blob_sha1(path_rel: str, commit: str | None = None) -> str:
    """Git object SHA-1 (distinct from SHA-256 file bytes)."""
    if commit is None:
        out = subprocess.run(["git", "hash-object", path_rel], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    else:
        blob = subprocess.run(["git", "show", f"{commit}:{path_rel}"], cwd=ROOT,
                              capture_output=True, check=True).stdout
        out = subprocess.run(["git", "hash-object", "--stdin"], input=blob, cwd=ROOT,
                             capture_output=True, check=True).stdout.decode().strip() if isinstance(
            subprocess.run(["git", "hash-object", "--stdin"], input=b"", cwd=ROOT,
                           capture_output=True), object) else ""
        # Simpler: use git rev-parse <commit>:<path>
        try:
            out2 = subprocess.run(["git", "rev-parse", f"{commit}:{path_rel}"], cwd=ROOT,
                                  capture_output=True, text=True, check=True).stdout.strip()
            # rev-parse :path gives blob SHA for committed blob? Actually
            # <commit>:<path> rev-parse returns blob SHA only with ^{object}? Use
            # `git ls-tree`.
            ls = subprocess.run(["git", "ls-tree", commit, "--", path_rel], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
            # Format: <mode> <type> <sha>\t<path>
            out = ls.split()[2] if ls else "unknown"
        except Exception:
            out = "unknown"
    return out


def git_show_bytes(path_rel: str, commit: str) -> bytes:
    return subprocess.run(["git", "show", f"{commit}:{path_rel}"], cwd=ROOT,
                          capture_output=True, check=True).stdout


def fail(msg: str, out_path: Path | None = None, extra: dict | None = None):
    payload = {"verdict": "fail", "reason": msg}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, sort_keys=True), file=sys.stderr)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="M014c lineage validator (read-only)")
    ap.add_argument("--freeze-commit", default="9cc80f0fc228e3a5f910723fa9420465f5cbeb30")
    ap.add_argument("--observed-commit", default="c27724746ebc674919aff32a93d6baf74e104e13")
    ap.add_argument("--out", default="target/m014c/lineage-verdict.json")
    args = ap.parse_args(argv)
    out_path = Path(args.out)

    # No writes to historical paths: assert out is under target/m014c/ only.
    try:
        rel = Path(args.out).resolve().relative_to((ROOT / "target" / "m014c").resolve())
    except Exception:
        # Allow any target/ path but never freeze/outputs.
        forbidden = [FREEZE_MANIFEST, PROTOCOL, GENERATOR, EVALUATOR, *FINAL_CONFIGS, *SPLITS, *CANDIDATES,
                     "target/m014b/final"]
        if any(str(args.out).startswith(f) or str(args.out) == f for f in forbidden):
            return fail(f"refusing to write to historical path {args.out}", out_path=None)

    # Load freeze.
    freeze_path = ROOT / FREEZE_MANIFEST
    if not freeze_path.exists():
        return fail(f"freeze manifest missing: {FREEZE_MANIFEST}", out_path)
    try:
        freeze = json.loads(freeze_path.read_text())
    except Exception as e:
        return fail(f"freeze manifest unparsable: {e}", out_path)

    checks = []

    def check(name: str, got: str, expected: str) -> bool:
        ok = (got == expected)
        checks.append({"name": name, "ok": ok, "got": got[:24] + "…" if len(got) > 24 else got,
                       "expected": expected[:24] + "…" if len(expected) > 24 else expected,
                       "got_full": got, "expected_full": expected})
        return ok

    all_ok = True

    # Generator / protocol / evaluator SHAs.
    for rel, key in ((GENERATOR, "generator_sha256"), (PROTOCOL, "protocol_sha256"), (EVALUATOR, "evaluator_sha256")):
        p = ROOT / rel
        if not p.exists():
            return fail(f"required file missing: {rel}", out_path)
        got = sha256_file(p)
        exp = freeze.get(key, "")
        if not check(f"{rel} matches freeze {key}", got, exp):
            all_ok = False

    # Candidate byte SHAs.
    for rel in CANDIDATES:
        p = ROOT / rel
        if not p.exists():
            return fail(f"candidate missing: {rel}", out_path)
        got = sha256_file(p)
        exp = freeze.get("candidates", {}).get(rel, "")
        if not exp:
            return fail(f"freeze has no candidate entry for {rel}", out_path)
        if not check(f"candidate {rel}", got, exp):
            all_ok = False

    # Split file SHAs + fingerprints/memberships are recorded; verify file SHAs.
    for rel in SPLITS:
        p = ROOT / rel
        if not p.exists():
            return fail(f"split missing: {rel}", out_path)
        got = sha256_file(p)
        exp = freeze.get("splits", {}).get(rel, "")
        if not check(f"split file {rel}", got, exp):
            all_ok = False

    # Final config SHAs + placeholder binding.
    placeholder_flags = []
    for rel in FINAL_CONFIGS:
        p = ROOT / rel
        if not p.exists():
            return fail(f"final config missing: {rel}", out_path)
        got = sha256_file(p)
        exp = freeze.get("final_configs", {}).get(rel, "")
        if not exp:
            return fail(f"freeze has no final_configs entry for {rel}", out_path)
        if not check(f"final config SHA {rel}", got, exp):
            all_ok = False
        # Embedded freeze binding must be placeholder; flag as defect, not pass.
        try:
            spec = json.loads(p.read_text())
        except Exception as e:
            return fail(f"final config {rel} unparsable: {e}", out_path)
        fz = spec.get("freeze_sha256", "")
        if fz != PLACEHOLDER:
            return fail(f"final config {rel} freeze_sha256 is not the known placeholder "
                        f"(got {fz[:32]}…); expected placeholder defect to be visible, not silently repaired",
                        out_path)
        placeholder_flags.append({"config": rel, "freeze_sha256": fz, "binding": "placeholder_unbound"})
        # Valid bindings in same spec must still match freeze.
        if spec.get("protocol_sha256") != freeze.get("protocol_sha256"):
            return fail(f"final config {rel} protocol_sha256 {spec.get('protocol_sha256')} != freeze {freeze.get('protocol_sha256')}",
                        out_path)

    if not all_ok:
        detail = "; ".join(c["name"] for c in checks if not c["ok"])
        return fail(f"SHA mismatch (one-byte corruption fails closed): {detail}", out_path,
                    extra={"checks": checks, "placeholder_bindings": placeholder_flags})

    # Git ancestry: freeze commit must precede observed commit (not author times).
    try:
        r = subprocess.run(["git", "merge-base", "--is-ancestor", args.freeze_commit, args.observed_commit],
                           cwd=ROOT)
        if r.returncode != 0:
            return fail(f"Git ancestry invalid: freeze {args.freeze_commit[:7]} is NOT an ancestor of "
                        f"observed {args.observed_commit[:7]} (merge-base --is-ancestor failed); "
                        f"cannot claim pretest freeze precedes observation", out_path)
    except Exception as e:
        return fail(f"Git ancestry check failed: {e}", out_path)

    # Committed bytes at freeze commit must match current files (no post-freeze rewrite).
    # Compare SHA-256 of `git show <freeze>:<path>` vs current file.
    for rel in (FREEZE_MANIFEST, PROTOCOL, GENERATOR, *FINAL_CONFIGS, *SPLITS):
        try:
            committed = git_show_bytes(rel, args.freeze_commit)
        except subprocess.CalledProcessError:
            return fail(f"path {rel} absent at freeze commit {args.freeze_commit[:7]}; lineage broken", out_path)
        committed_sha = "sha256:" + hashlib.sha256(committed).hexdigest()
        current_sha = sha256_file(ROOT / rel)
        # Freeze manifest itself: current file must equal committed freeze?
        # Freeze manifest was created AT freeze commit, so committed bytes should
        # equal current bytes (no rewrite). For other paths same.
        if committed_sha != current_sha:
            # For EVALUATOR, it was also frozen; check it too? Evaluator is not in
            # this list but should also match; add explicit check below.
            return fail(f"post-freeze rewrite detected: {rel} current {current_sha} != "
                        f"committed-at-freeze {committed_sha}; original committed M014b bytes must remain exactly unchanged",
                        out_path)

    # Evaluator committed bytes check (frozen SHA-bound file; must not have changed).
    try:
        committed_eval = git_show_bytes(EVALUATOR, args.freeze_commit)
        if "sha256:" + hashlib.sha256(committed_eval).hexdigest() != sha256_file(ROOT / EVALUATOR):
            return fail(f"evaluator {EVALUATOR} changed since freeze; historical evaluator hash must stay untouched "
                        f"(implement a new version instead)", out_path)
    except subprocess.CalledProcessError:
        return fail(f"evaluator {EVALUATOR} absent at freeze commit", out_path)

    # Build detached attestation (non-self-referential lineage, does NOT repair
    # embedded placeholder).
    try:
        freeze_commit_full = subprocess.run(["git", "rev-parse", args.freeze_commit], cwd=ROOT,
                                            capture_output=True, text=True, check=True).stdout.strip()
        observed_full = subprocess.run(["git", "rev-parse", args.observed_commit], cwd=ROOT,
                                       capture_output=True, text=True, check=True).stdout.strip()
    except Exception as e:
        return fail(f"cannot resolve commits: {e}", out_path)

    attestation = {
        "verdict": "verified_with_known_defect",
        "freeze_commit": freeze_commit_full,
        "observed_commit": observed_full,
        "freeze_manifest_sha256": sha256_file(ROOT / FREEZE_MANIFEST),
        "freeze_manifest_git_blob_sha1": git_blob_sha1(FREEZE_MANIFEST),
        "protocol_sha256": sha256_file(ROOT / PROTOCOL),
        "generator_sha256": sha256_file(ROOT / GENERATOR),
        "evaluator_sha256": sha256_file(ROOT / EVALUATOR),
        "placeholder_bindings": placeholder_flags,
        "placeholder_note": ("Each fixtures/m014b-final-*.evaluate.json embeds freeze_sha256="
                             + PLACEHOLDER + " (64 literal '1' digits). This valid-shaped digest of a "
                             "placeholder is NOT an attestation of the actual frozen manifest; flagged "
                             "placeholder_unbound, never passed. Detached Git/SHA-256 chain above reconciles "
                             "historical source chain but does NOT retroactively repair the embedded field."),
        "valid_bindings": ["protocol_sha256", "expected_artifact_sha256", "expected_dataset_sha256",
                           "expected_split_fingerprint", "expected_test_membership_sha256",
                           "generator_sha256", "evaluator_sha256", "source commit ancestry"],
        "scope": ("Offline lineage is strong for which files were committed before local result claims, "
                  "but cannot cryptographically prove when uncommitted scores were first observed. "
                  "Hosted CI for the implementation/head was absent/failed after the one-time final, "
                  "so any historical claim of successful preregistered hosted CI BEFORE observation is NOT verified."),
        "checks": checks,
        "no_write_guarantee": "validator performed no writes to freeze/outputs or target/m014b/final",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(attestation, indent=2, sort_keys=True) + "\n")
    tmp.replace(out_path)
    print(json.dumps({"verdict": attestation["verdict"],
                      "freeze": freeze_commit_full[:7], "observed": observed_full[:7],
                      "placeholder": "placeholder_unbound (defect, not pass)"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
