#!/usr/bin/env python3
"""M017 two-phase prospective freeze (no backwards self-hash).

Phase 1 (preliminary manifest): generator, materializer, protocol, analyzer,
evaluator source files, frozen DEV models (tinymlp fixture SHA + legacy DEV
metric pins), cohort cohort SHAs (regenerated deterministically, never
committed with labels in-repo). Written to docs/m017-preliminary-v1.json.

Phase 2 (final configs): one `experiment evaluate` config per architecture
(typed-choice-tinymlp + three legacy heads) binding the preliminary SHA,
test membership, model/provenance SHAs. Written to
fixtures/m017-final-<arch>.evaluate.json.

Phase 3 (binding manifest): docs/m017-binding-v1.json enumerates final
config SHAs + the preliminary SHA with its own distinct digest and
final_status=FINAL_NOT_YET_RUN. The DAG is acyclic: configs reference the
preliminary SHA; the binding references configs; nothing references the
binding. Placeholders (sha256:111...) and stale SHAs fail closed.

Run BEFORE any final inference. Re-run is byte-identical or fails.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import generate_m017_suite  # noqa: E402

PLACEHOLDER = "sha256:" + "1" * 64

# Evaluator source files pinned by the freeze (trainer-visible inference path).
EVALUATOR_SOURCES = [
    "crates/sdm-experiment/src/lib.rs",
    "crates/sdm-experiment/src/main.rs",
    "crates/sdm-experiment/src/m016.rs",
    "crates/sdm-experiment/src/m015a.rs",
    "crates/sdm-runtime/src/lib.rs",
    "crates/sdm-runtime/src/tinymlp.rs",
    "scripts/analyze_m017_final.py",
    "scripts/materialize_m017.py",
]

FINAL_ARCHS = ("typed-choice-tinymlp", "typed-choice", "typed-choice-cross",
               "typed-choice-compositional")


def sha_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, payload: bytes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() == hashlib.sha256(payload).hexdigest():
            return
        raise FileExistsError(f"refusing to overwrite different frozen file: {path}")
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        import os

        with open(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        json.loads(payload)
        os.replace(tmp, path)
    finally:
        import os as _os

        if _os.path.exists(tmp):
            _os.unlink(tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", type=Path, default=ROOT / "target/m017-freeze")
    ap.add_argument("--comparison", type=Path, default=ROOT / "target/m016/m016-comparison.json",
                    help="authoritative M016 comparison (model SHAs + DEV pins)")
    ap.add_argument("--tinymlp-artifact", type=Path,
                    default=ROOT / "fixtures/m016-tinymlp-selected.artifact.json")
    args = ap.parse_args()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    comp = json.loads(Path(args.comparison).read_text())
    assert comp["schema"] == "sdm-m016-comparison-v1"
    assert comp["partition"] == "DEV only" and comp["test_evaluation_performed"] is False

    def relpath(path):
        # Committed references must be repo-relative (absolute local paths
        # break verification on any other machine — fail-closed by design).
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        try:
            return str(p.resolve().relative_to(ROOT.resolve()))
        except ValueError:
            raise SystemExit(f"freeze input outside repo: {path}")

    # Regenerate cohorts deterministically; bind output SHAs (labels stay local).
    cohorts = {}
    for cohort in ("canary", "final"):
        manifest = generate_m017_suite.generate(workdir, cohort)
        manifest.pop("generator_sha256", None)
        cohorts[cohort] = {
            "groups": manifest["groups"], "rows": manifest["rows"],
            "seed": manifest["seed"],
            "output_sha256": manifest["output_sha256"],
            "path": str(workdir / f"{cohort}.jsonl"),
        }
        assert manifest["output_sha256"] != PLACEHOLDER

    generator_sha = sha_file(ROOT / "scripts/generate_m017_suite.py")
    materializer_sha = sha_file(ROOT / "scripts/materialize_m017.py")
    protocol_sha = sha_file(ROOT / "docs/m017-protocol-v1.json")
    evaluator = {rel: sha_file(ROOT / rel) for rel in EVALUATOR_SOURCES}
    for rel, sha in evaluator.items():
        assert sha != PLACEHOLDER, rel

    tinymlp_file_sha = sha_file(args.tinymlp_artifact)
    assert comp["models"]["typed-choice-tinymlp"]["artifact_sha256"] != PLACEHOLDER

    # Legacy DEV pins (functional, not byte: regenerated at final time).
    legacy_pins = {}
    for arch in ("typed-choice", "typed-choice-cross", "typed-choice-compositional"):
        m = comp["models"][arch]
        legacy_pins[arch] = {
            "dev_conditional_argmax_accuracy_v2": m["dev_conditional_argmax_accuracy_v2"],
            "dev_answerable_final_accuracy_v2": m["dev_answerable_final_accuracy_v2"],
            "dev_false_abstention_rate_v2": m["dev_false_abstention_rate_v2"],
            "dev_no_answer_recall_v2": m["dev_no_answer_recall_v2"],
            "causal_both_final": m["causal_both_final"],
            "nuisance_both_final": m["nuisance_both_final"],
        }
    tinymlp_pin = {
        k: comp["models"]["typed-choice-tinymlp"][k]
        for k in ("dev_conditional_argmax_accuracy_v2",
                  "dev_answerable_final_accuracy_v2",
                  "dev_false_abstention_rate_v2", "dev_no_answer_recall_v2",
                  "causal_both_final", "nuisance_both_final")
    }

    preliminary = {
        "schema": "sdm-m017-preliminary-v1",
        "generator": "scripts/generate_m017_suite.py",
        "generator_sha256": generator_sha,
        "materializer": "scripts/materialize_m017.py",
        "materializer_sha256": materializer_sha,
        "protocol": "docs/m017-protocol-v1.json",
        "protocol_sha256": protocol_sha,
        "evaluator_sources": evaluator,
        "m016_comparison": relpath(args.comparison),
        "m016_disposition": comp["disposition"],
        "frozen_models": {
            "typed-choice-tinymlp": {
                "artifact_path": relpath(args.tinymlp_artifact),
                "artifact_file_sha256": tinymlp_file_sha,
                "artifact_tensor_sha256":
                    comp["models"]["typed-choice-tinymlp"]["artifact_sha256"],
                "dev_threshold": 0.63,
                "dev_pins": tinymlp_pin,
            },
            "legacy_dev_pins": legacy_pins,
            "legacy_regeneration": {
                "procedure": "run_m016_comparison.py baselines on M015 bytes "
                             "(same code commit + dataset SHAs as M016); functional "
                             "DEV pins must match within 1e-9 or fail closed",
                "dataset_sha256": comp["dataset_sha256"],
                "split_fingerprint": comp["split_fingerprint"],
            },
        },
        "cohorts": cohorts,
        "support_minimum_groups_per_family": 150,
    }
    prelim_bytes = (json.dumps(preliminary, indent=2, sort_keys=True) + "\n").encode()
    prelim_sha = "sha256:" + hashlib.sha256(prelim_bytes).hexdigest()
    assert prelim_sha != PLACEHOLDER
    write_new(ROOT / "docs/m017-preliminary-v1.json", prelim_bytes)

    # Phase 2: final configs reference the preliminary SHA (never the binding).
    config_shas = {}
    for arch in FINAL_ARCHS:
        cfg = {
            "preliminary": "docs/m017-preliminary-v1.json",
            "preliminary_sha256": prelim_sha,
            "note": "exact artifact/dataset/split/provenance SHAs bound at final "
                    "materialization time; this config binds the frozen preliminary "
                    "inputs and the cohort/test-membership SHAs",
            "expected_architecture": arch,
            "cohort": "final",
            "cohort_output_sha256": cohorts["final"]["output_sha256"],
        }
        cfg_bytes = (json.dumps(cfg, indent=2, sort_keys=True) + "\n").encode()
        cfg_sha = "sha256:" + hashlib.sha256(cfg_bytes).hexdigest()
        path = ROOT / f"fixtures/m017-final-{arch}.evaluate.json"
        write_new(path, cfg_bytes)
        config_shas[f"fixtures/m017-final-{arch}.evaluate.json"] = cfg_sha

    binding = {
        "schema": "sdm-m017-binding-v1",
        "preliminary": "docs/m017-preliminary-v1.json",
        "preliminary_sha256": prelim_sha,
        "final_configs": config_shas,
        "final_status": "FINAL_NOT_YET_RUN",
    }
    binding_bytes = (json.dumps(binding, indent=2, sort_keys=True) + "\n").encode()
    binding_sha = "sha256:" + hashlib.sha256(binding_bytes).hexdigest()
    assert binding_sha != prelim_sha
    assert binding_sha != PLACEHOLDER
    binding["binding_sha256"] = binding_sha
    write_new(ROOT / "docs/m017-binding-v1.json",
              (json.dumps(binding, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({"preliminary_sha256": prelim_sha,
                      "binding_sha256": binding_sha,
                      "final_configs": config_shas}, indent=2))


if __name__ == "__main__":
    main()
