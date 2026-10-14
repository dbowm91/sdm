#!/usr/bin/env python3
"""Verify the M017 two-phase freeze WITHOUT running final inference.

Checks (fail-closed, suitable for CI):
- preliminary manifest: all recorded file SHAs match the working tree; no
  placeholder; cohort SHAs reproduce by regeneration; support minimums met
  from ID/group/family metadata (labels never consulted for selection);
- final configs: reference the real preliminary SHA (never a placeholder or
  the binding digest); cohort SHAs match;
- binding: digest valid and distinct; final_status == FINAL_NOT_YET_RUN;
  acyclic (nothing references the binding digest);
- overlap: no m015- case/group/pair IDs; option IDs disjoint from all
  committed M015 corpora + M016 parity sample; nuisance vocab distinct;
- evaluator: `experiment evaluate` rejects training-shaped misuse
  (tinymlp via `experiment run` fails; covered by unit tests).

Writes a verdict JSON to --out (default target/m017-freeze-verify.json).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import generate_m017_suite  # noqa: E402

PLACEHOLDER = "sha256:" + "1" * 64
# Tier-2 (regenerated, linux-x64 only): M015 corpus produced by the M016 step.
M015_CORPORA = [
    "target/m016/baselines/corpus/train.jsonl",
    "target/m016/baselines/corpus/dev.jsonl",
]
# Tier-1 (committed, every host): M015 nuisance literals must not reappear.
M015_NUISANCE_NOTES = {"routine status record", "quartz basalt record"}


def sha_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fail(msg):
    raise SystemExit(f"M017 FREEZE INVALID: {msg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "target/m017-freeze-verify.json")
    ap.add_argument("--workdir", type=Path, default=ROOT / "target/m017-freeze-check")
    args = ap.parse_args()

    prelim = json.loads((ROOT / "docs/m017-preliminary-v1.json").read_text())
    binding = json.loads((ROOT / "docs/m017-binding-v1.json").read_text())
    protocol = json.loads((ROOT / "docs/m017-protocol-v1.json").read_text())
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            fail(f"{name}: {detail}")

    # 1. File SHAs.
    check("generator_sha", sha_file(ROOT / "scripts/generate_m017_suite.py") == prelim["generator_sha256"])
    check("materializer_sha", sha_file(ROOT / "scripts/materialize_m017.py") == prelim["materializer_sha256"])
    check("protocol_sha", sha_file(ROOT / "docs/m017-protocol-v1.json") == prelim["protocol_sha256"])
    for rel, sha in prelim["evaluator_sources"].items():
        check(f"evaluator_src:{rel}", sha_file(ROOT / rel) == sha, f"expected {sha}")
        check(f"no_placeholder:{rel}", sha != PLACEHOLDER)
    check("tinymlp_fixture_sha",
          sha_file(ROOT / prelim["frozen_models"]["typed-choice-tinymlp"]["artifact_path"])
          == prelim["frozen_models"]["typed-choice-tinymlp"]["artifact_file_sha256"])

    # 2. Cohort regeneration + support (metadata only).
    args.workdir.mkdir(parents=True, exist_ok=True)
    for cohort in ("canary", "final"):
        manifest = generate_m017_suite.generate(args.workdir, cohort)
        check(f"cohort_sha:{cohort}",
              manifest["output_sha256"] == prelim["cohorts"][cohort]["output_sha256"],
              f"{manifest['output_sha256']} vs {prelim['cohorts'][cohort]['output_sha256']}")
        rows = [json.loads(l) for l in (args.workdir / f"{cohort}.jsonl").open()
                if l.strip()]
        fams = {}
        for r in rows:
            fams.setdefault(r["family"], set()).add(r["group_id"])
        # Support minimums: final cohort needs powered families (150); the
        # public canary only needs every family present (>= 5 groups).
        minimum = prelim["support_minimum_groups_per_family"] \
            if cohort == "final" else 5
        for fam, groups in sorted(fams.items()):
            check(f"support:{cohort}:{fam}", len(groups) >= minimum,
                  f"{len(groups)} groups < {minimum}")
        check(f"no_train_partition:{cohort}",
              all(r["split"] == cohort for r in rows))

    # 3. Overlap audit.
    # Tier 1 (committed bytes, every host): namespace + parity-sample option
    # IDs + nuisance-vocab literals.
    parity = json.loads((ROOT / "fixtures/m016-parity-sample.json").read_text())
    parity_opts = set()
    for row in parity["rows"]:
        for o in row["request"]["spec"]["options"]:
            parity_opts.add(o["id"])
    for cohort in ("canary", "final"):
        for line in (args.workdir / f"{cohort}.jsonl").open():
            r = json.loads(line)
            for key in ("case_id", "group_id", "pair_id"):
                check(f"no_m015_id:{cohort}:{key}",
                      r[key] not in parity_opts and not r[key].startswith("m015-"),
                      r[key])
            for o in r["options"]:
                check(f"parity_option_disjoint:{cohort}", o["id"] not in parity_opts, o["id"])
            if r["pair_type"] == "nuisance":
                check(f"nuisance_vocab:{cohort}",
                      r["context"].get("note") not in M015_NUISANCE_NOTES,
                      str(r["context"].get("note")))
    # Tier 2 (regenerated M015 bytes, linux-x64 only): full option-ID
    # disjointness. Records a skip elsewhere (never a silent pass).
    tier2 = [ROOT / rel for rel in M015_CORPORA if (ROOT / rel).exists()]
    if tier2:
        m015_opts = set()
        for p in tier2:
            for line in p.open():
                for o in json.loads(line)["options"]:
                    m015_opts.add(o["id"])
        for cohort in ("canary", "final"):
            bad = 0
            for line in (args.workdir / f"{cohort}.jsonl").open():
                for o in json.loads(line)["options"]:
                    if o["id"] in m015_opts:
                        bad += 1
            check(f"m015_option_disjoint:{cohort}", bad == 0, f"{bad} collisions")
    else:
        checks.append({"check": "m015_option_disjoint:SKIPPED",
                       "ok": True,
                       "detail": "regenerated M015 corpus absent on this host; "
                                 "tier-1 committed checks still enforced"})

    # 4. Final configs reference the true preliminary SHA.
    # NOTE: preliminary file bytes are canonical (written by freeze_m017).
    prelim_file_sha = sha_file(ROOT / "docs/m017-preliminary-v1.json")
    prelim_canonical = (json.dumps(prelim, indent=2, sort_keys=True) + "\n").encode()
    check("preliminary_canonical_bytes",
          hashlib.sha256(prelim_canonical).hexdigest() == prelim_file_sha[7:])
    check("binding_prelim_sha", binding["preliminary_sha256"] == prelim_file_sha,
          f"{binding['preliminary_sha256']} vs {prelim_file_sha}")
    for rel, sha in binding["final_configs"].items():
        cfg = json.loads((ROOT / rel).read_text())
        check(f"config_prelim_sha:{rel}", cfg["preliminary_sha256"] == prelim_file_sha)
        check(f"config_no_placeholder:{rel}", sha != PLACEHOLDER)
        check(f"config_no_binding_ref:{rel}",
              binding.get("binding_sha256", "") not in json.dumps(cfg),
              "config must not reference the binding digest")
        check(f"config_cohort_sha:{rel}",
              cfg["cohort_output_sha256"] == prelim["cohorts"]["final"]["output_sha256"])

    # 5. Binding digest valid, distinct, acyclic, NOT_YET_RUN.
    recorded = binding.pop("binding_sha256", None)
    recomputed = "sha256:" + hashlib.sha256(
        (json.dumps(binding, indent=2, sort_keys=True) + "\n").encode()).hexdigest()
    check("binding_digest", recorded == recomputed, f"{recorded} vs {recomputed}")
    check("binding_distinct", recorded != prelim_file_sha and recorded != PLACEHOLDER)
    check("final_not_yet_run", binding["final_status"] == "FINAL_NOT_YET_RUN")

    # 6. Protocol sanity: tracks partition the family taxonomy, and the
    # taxonomy matches the generator's rule families.
    check("protocol_tracks_cover_families",
          sorted(protocol["tracks"]["fixed_rule"] + protocol["tracks"]["rule_conditioned"])
          == sorted(protocol["family_taxonomy"]))
    check("protocol_families_match_generator",
          sorted(protocol["family_taxonomy"])
          == sorted(f"m017-{name}-v1" for name in generate_m017_suite.RULES))

    verdict = {"schema": "sdm-m017-freeze-verify-v1", "ok": True, "checks": checks,
               "preliminary_sha256": prelim_file_sha, "binding_sha256": recorded}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    print(json.dumps(verdict, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
