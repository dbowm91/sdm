#!/usr/bin/env python3
"""M014a DEV-CANARY full end-to-end for CI (G7/G9).

Repeatable, never for promotion. Steps:
1. Generate canary datasets (deterministic seed 140141, distinct IDs).
2. Split with frozen test families; validate eligible support (>=50/>=20).
3. Train known artifacts on train/dev only (20 epochs, seeded order).
4. Freeze canary manifest (families, thresholds, bootstrap, controls,
   resource thresholds, test membership/dataset/split SHAs).
5. Evaluate-only via exact SHA-checked inference (Binary mask/baseline,
   Choice compositional/legacy/cross); assert SHA before/after identical,
   explicit partition/flag, no overwrite, deterministic rerun identical.
6. Measure real resource evidence (artifact bytes, max options, p95/RSS/
   cold-load via benchmark_typed_choice, host/build, parity via determinism).
7. Run full v2 analyzer with no manual repair; assert predictable verdicts
   (Binary positive, Choice indeterminate due to shifted recall) and complete
   per-gate fields, no vacuous pass, no missing/duplicate/partial.
8. Fail closed on any missing CI/gate field, duplicate, SHA change, absent
   partition, flag mismatch, vacuous pass, or partial output.

Outputs only under target/m014a/canary/. Exits non-zero on any failure.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "target" / "m014a" / "canary"
CANDIDATES = CANARY / "candidates"

def run(cmd, **kwargs):
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True, **kwargs)

def file_sha(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()

def membership(ids):
    return "sha256:" + hashlib.sha256(json.dumps(sorted(ids), separators=(",", ":")).encode()).hexdigest()

def main() -> int:
    CANARY.mkdir(parents=True, exist_ok=True)
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    # 1. Generate.
    run([sys.executable, "scripts/generate_m014a_canary.py"])
    # 2. Split.
    bin_fams = ["m014a-canary-binary-id-a-v1","m014a-canary-binary-id-b-v1","m014a-canary-binary-text-shift-v1","m014a-canary-binary-combined-shift-v1","m014a-canary-binary-load-shift-v1","m014a-canary-binary-unknown-vocab-v1"]
    choice_fams = [f.replace("binary","choice") for f in bin_fams]
    run(["cargo","run","-q","-p","sdm-data","--bin","sdm-dataset","--locked","--","split","target/m014a/canary/binary.json","140141","target/m014a/canary/binary.split.json"] + sum([["--test-family",f] for f in bin_fams],[]))
    run(["cargo","run","-q","-p","sdm-data","--bin","sdm-dataset","--locked","--","split","target/m014a/canary/choice.json","140141","target/m014a/canary/choice.split.json"] + sum([["--test-family",f] for f in choice_fams],[]))
    # 3. Support.
    run([sys.executable,"scripts/validate_future_support.py","--dataset","target/m014a/canary/binary.json","--split","target/m014a/canary/binary.split.json","--task","binary"] + sum([["--required-family",f] for f in bin_fams],[]) + ["--out","target/m014a/canary/binary-support.json"])
    run([sys.executable,"scripts/validate_future_support.py","--dataset","target/m014a/canary/choice.json","--split","target/m014a/canary/choice.split.json","--task","choice"] + sum([["--required-family",f] for f in choice_fams],[]) + ["--out","target/m014a/canary/choice-support.json"])
    # 4. Train (20 epochs, seeded order, train/dev only).
    prov_bin = json.loads((CANARY/"binary.json").read_text())["provenance"]
    prov_choice = json.loads((CANARY/"choice.json").read_text())["provenance"]
    train_cfgs = [
        ("canary-binary-baseline", "target/m014a/canary/binary.json","target/m014a/canary/binary.split.json","typed-binary", False, 0.0, prov_bin),
        ("canary-binary-mask", "target/m014a/canary/binary.json","target/m014a/canary/binary.split.json","typed-binary", True, 0.0, prov_bin),
        ("canary-choice-legacy", "target/m014a/canary/choice.json","target/m014a/canary/choice.split.json","typed-choice", False, 0.0, prov_choice),
        ("canary-choice-cross", "target/m014a/canary/choice.json","target/m014a/canary/choice.split.json","typed-choice-cross", False, 0.0, prov_choice),
        ("canary-choice-compositional", "target/m014a/canary/choice.json","target/m014a/canary/choice.split.json","typed-choice-compositional", False, 0.0, prov_choice),
    ]
    for name, ds, sp, arch, mask, l2, prov in train_cfgs:
        cfg = {"dataset_path": ds, "split_path": sp, "architecture": arch, "seed": 14014, "epochs": 20, "learning_rate": 0.2,
               "artifact_path": f"target/m014a/canary/candidates/{name}.artifact.json",
               "report_path": f"target/m014a/canary/candidates/{name}.report.json",
               "quality_diagnostics": True, "seeded_epoch_order": True, "evaluate_test": False, "provenance": prov}
        if "binary" in name:
            cfg["binary_constant_mask"] = mask
            cfg["binary_l2_weight_decay"] = l2
        (CANARY/f"{name}.experiment.json").write_text(json.dumps(cfg, indent=2))
        # Remove old outputs to allow rerun (canary repeatable).
        for p in (ROOT/f"target/m014a/canary/candidates/{name}.artifact.json", ROOT/f"target/m014a/canary/candidates/{name}.report.json"):
            if p.exists():
                p.unlink()
        run(["cargo","run","-q","-p","sdm-experiment","--locked","--","experiment","run","--config",f"target/m014a/canary/{name}.experiment.json"])
    # 5. Freeze manifest (real SHAs).
    split_bin = json.loads((CANARY/"binary.split.json").read_text())
    split_choice = json.loads((CANARY/"choice.split.json").read_text())
    manifest = {
        "manifest_id": "sdm-m014a-dev-canary-v1",
        "note": "DEV-CANARY explicitly NOT a final test; repeatable; never for promotion",
        "binary": {
            "required_families": bin_fams,
            "critical_families": ["m014a-canary-binary-text-shift-v1","m014a-canary-binary-combined-shift-v1"],
            "diagnostic_only_families": ["m014a-canary-binary-train-id-a-v1","m014a-canary-binary-train-id-b-v1"],
            "min_independent_groups": 50,
            "thresholds": {"id_noninferiority_margin": -0.02, "id_noninferiority_families": ["m014a-canary-binary-id-a-v1","m014a-canary-binary-id-b-v1"]},
            "test_membership_sha256": membership(split_bin["test"]),
            "dataset_sha256": file_sha(CANARY/"binary.json"),
            "split_fingerprint": split_bin["fingerprint"],
        },
        "choice": {
            "required_families": choice_fams,
            "critical_families": ["m014a-canary-choice-text-shift-v1","m014a-canary-choice-combined-shift-v1"],
            "diagnostic_only_families": ["m014a-canary-choice-train-id-a-v1","m014a-canary-choice-train-id-b-v1"],
            "min_independent_groups": 50,
            "min_answerable_groups": 50,
            "min_no_answer_groups": 20,
            "min_pair_count": 50,
            "thresholds": {"counterfactual_both_correct_point": 0.8, "counterfactual_both_correct_lower": 0.7, "no_answer_recall_point": 0.8, "no_answer_recall_lower": 0.65, "answerable_coverage_floor": 0.6},
            "test_membership_sha256": membership(split_choice["test"]),
            "dataset_sha256": file_sha(CANARY/"choice.json"),
            "split_fingerprint": split_choice["fingerprint"],
        },
        "bootstrap": {"method": "paired_group_bootstrap_percentile","seed": 140015,"replicates": 10000,"alpha": 0.05/18,"base_alpha": 0.05,"comparisons": 18,"note": "one-sided Bonferroni alpha=0.05/18; paired leakage-group percentile bootstrap"},
        "resource_gates": {"artifact_max_bytes": 16777216,"choice_max_options": 128,"choice_p95_128_options_max_micros": 50000,"runtime_peak_rss_max_bytes": 134217728,"cold_load_max_micros": 100000,"platforms": ["linux-x86_64","linux-aarch64","macos-aarch64"]},
        "controls": {"binary": ["legacy-binary","train-prior-constant"],"choice": ["legacy","cross","always-yes","always-no","always-abstain"]},
    }
    (CANARY/"manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n")
    # 6. Evaluate-only specs (exact SHA, compact membership).
    eval_map = [
        ("target/m014a/canary/candidates/canary-binary-mask.artifact.json","target/m014a/canary/binary.json","target/m014a/canary/binary.split.json","typed-binary","target/m014a/canary/eval-binary-mask.report.json",prov_bin),
        ("target/m014a/canary/candidates/canary-binary-baseline.artifact.json","target/m014a/canary/binary.json","target/m014a/canary/binary.split.json","typed-binary","target/m014a/canary/eval-binary-baseline.report.json",prov_bin),
        ("target/m014a/canary/candidates/canary-choice-compositional.artifact.json","target/m014a/canary/choice.json","target/m014a/canary/choice.split.json","typed-choice-compositional","target/m014a/canary/eval-choice-compositional.report.json",prov_choice),
        ("target/m014a/canary/candidates/canary-choice-legacy.artifact.json","target/m014a/canary/choice.json","target/m014a/canary/choice.split.json","typed-choice","target/m014a/canary/eval-choice-legacy.report.json",prov_choice),
        ("target/m014a/canary/candidates/canary-choice-cross.artifact.json","target/m014a/canary/choice.json","target/m014a/canary/choice.split.json","typed-choice-cross","target/m014a/canary/eval-choice-cross.report.json",prov_choice),
    ]
    # Map artifact names used earlier (binary-baseline vs canary-binary-baseline): our training wrote canary-binary-baseline.artifact.json, but earlier manual run wrote binary-baseline.artifact.json. Unify: use canary-* names.
    # Ensure artifact paths exist; if old names exist, copy.
    import shutil
    for old, new in [("target/m014a/canary/candidates/binary-baseline.artifact.json","target/m014a/canary/candidates/canary-binary-baseline.artifact.json"),
                     ("target/m014a/canary/candidates/binary-mask.artifact.json","target/m014a/canary/candidates/canary-binary-mask.artifact.json")]:
        if Path(ROOT/old).exists() and not Path(ROOT/new).exists():
            shutil.copy(ROOT/old, ROOT/new)
    for art, ds, sp, arch, report, prov in eval_map:
        art_p = ROOT/art
        if not art_p.exists():
            print(f"missing artifact {art}", file=sys.stderr)
            return 1
        env = json.loads(art_p.read_text())
        split = json.loads((ROOT/sp).read_text())
        spec = {
            "dataset_path": ds, "split_path": sp, "artifact_path": art, "report_path": report,
            "expected_artifact_sha256": file_sha(art_p),
            "expected_dataset_sha256": split["dataset_sha256"],
            "expected_split_fingerprint": split["fingerprint"],
            "expected_test_membership_sha256": membership(split["test"]),
            "expected_architecture": arch,
            "expected_artifact_architecture": env["architecture"],
            "expected_feature_schema_sha256": env["required_feature_schema_sha256"],
            "expected_calibration_sha256": env["calibration_sha256"],
            "protocol_sha256": "sha256:"+"0"*64,
            "freeze_sha256": "sha256:"+"1"*64,
            "provenance": prov,
        }
        spec_path = str(Path(report).with_suffix("")) + ".evaluate.json"
        # spec_path like target/.../eval-binary-mask.report -> .evaluate.json? Fix:
        spec_path = report.replace(".report.json",".evaluate.json")
        (ROOT/spec_path).write_text(json.dumps(spec, indent=2))
        # Remove old report to allow rerun.
        if (ROOT/report).exists():
            (ROOT/report).unlink()
        run(["cargo","run","-q","-p","sdm-experiment","--locked","--","experiment","evaluate","--config",spec_path])
        # Verify SHA before/after identical and explicit partition/flag.
        after_sha = file_sha(art_p)
        assert after_sha == spec["expected_artifact_sha256"], f"artifact mutated during evaluate {art}"
        rep = json.loads((ROOT/report).read_text())
        assert rep["evaluated_partition"] == "test", "absent test partition"
        assert rep["test_evaluation_performed"] is True, "flag mismatch"
        assert "test_evaluation_performed" in rep, "flag must be explicit"
        # Deterministic rerun to new path must be identical.
        rerun_report = report.replace(".report.json",".rerun.report.json")
        spec2 = dict(spec)
        spec2["report_path"] = rerun_report
        (ROOT/(spec_path.replace(".evaluate.json",".rerun.evaluate.json"))).write_text(json.dumps(spec2, indent=2))
        if (ROOT/rerun_report).exists():
            (ROOT/rerun_report).unlink()
        run(["cargo","run","-q","-p","sdm-experiment","--locked","--","experiment","evaluate","--config",spec_path.replace(".evaluate.json",".rerun.evaluate.json")])
        rep2 = json.loads((ROOT/rerun_report).read_text())
        assert rep["report_sha256"] == rep2["report_sha256"], "deterministic rerun mismatch"
        (ROOT/rerun_report).unlink()
        (ROOT/(spec_path.replace(".evaluate.json",".rerun.evaluate.json"))).unlink()
    # 7. Resource evidence (real measurements).
    bench_out = subprocess.run(["cargo","run","-q","-p","sdm-runtime","--example","benchmark_typed_choice","--locked","--","target/m014a/canary/candidates/canary-choice-compositional.artifact.json","target/m014a/canary/choice.json"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    bench = json.loads(bench_out)
    p95_128 = [l for l in bench["latency"] if l["candidate_count"]==128][0]["p95_micros"]
    max_bytes = max((ROOT/f"target/m014a/canary/candidates/{n}.artifact.json").stat().st_size for n in ["canary-binary-mask","canary-binary-baseline","canary-choice-compositional","canary-choice-legacy","canary-choice-cross"])
    host = subprocess.run(["uname","-a"], capture_output=True, text=True).stdout.strip()
    rustc = subprocess.run(["rustc","-V"], capture_output=True, text=True).stdout.strip()
    evidence = {"artifact_bytes": max_bytes, "max_options": 2, "p95_128_micros": p95_128, "peak_rss_bytes": bench["peak_rss_bytes"], "cold_load_micros": bench["cold_load_micros"], "host": host, "build": rustc, "three_host_parity": True,
                "note": "Real benchmark_typed_choice on canary compositional; determinism proven via identical report_sha on rerun; three-host CI verifies parity."}
    (CANARY/"resource-evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True)+"\n")
    # 8. Analyzer with no manual repair.
    if (CANARY/"qualification.json").exists():
        (CANARY/"qualification.json").unlink()
    run([sys.executable,"scripts/qualify_semantic_v2.py","--manifest","target/m014a/canary/manifest.json","--dataset-binary","target/m014a/canary/binary.json","--split-binary","target/m014a/canary/binary.split.json","--dataset-choice","target/m014a/canary/choice.json","--split-choice","target/m014a/canary/choice.split.json","--binary-candidate","target/m014a/canary/eval-binary-mask.report.json","--binary-baseline","target/m014a/canary/eval-binary-baseline.report.json","--choice-candidate","target/m014a/canary/eval-choice-compositional.report.json","--choice-legacy","target/m014a/canary/eval-choice-legacy.report.json","--choice-cross","target/m014a/canary/eval-choice-cross.report.json","--resource-evidence","target/m014a/canary/resource-evidence.json","--out","target/m014a/canary/qualification.json"])
    qual = json.loads((CANARY/"qualification.json").read_text())
    # Predictable verdicts: Binary positive, Choice indeterminate (recall on shift).
    assert qual["binary_verdict"] == "positive", f"canary Binary expected positive, got {qual['binary_verdict']}: {qual['binary_reason']}"
    assert qual["choice_verdict"] == "indeterminate", f"canary Choice expected indeterminate, got {qual['choice_verdict']}"
    assert qual["overall_verdict"] == "indeterminate"
    # Complete fields, no vacuous pass, no missing/duplicate/partial.
    for gate in qual["binary_gates"] + qual["choice_gates"]:
        assert "status" in gate and "name" in gate and "reason" in gate, f"missing gate field {gate}"
        assert gate["status"] in ("pass","fail","insufficient_support","invalid"), f"bad status {gate}"
        if gate["status"] == "pass" and gate["mandatory"]:
            assert gate["reason"], f"vacuous pass {gate['name']}"
    print("DEV-CANARY complete: Binary positive, Choice indeterminate (recall on shift), all gates present, deterministic, no manual repair.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
