#!/usr/bin/env python3
"""Unit tests for the M017 final analyzer (synthetic manifests, no inference).

Builds tiny synthetic evaluate manifests + corpus + protocol/binding and
asserts: SHA bindings enforced fail-closed, v2 cases validate, verdicts
follow the preregistered gates, and the ledger is single-use.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))

WORK = ROOT / "target/m017-analyzer-test"


def sha_bytes(data: bytes):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def make_corpus():
    mk = lambda cid, gid, pid, ptype, fam, avail, sat, opts, label, flip=False: {
        "case_id": cid, "group_id": gid, "pair_id": pid, "pair_type": ptype,
        "family": fam, "context": {"available": avail},
        "oracle": {"satisfying_option_count": sat, "available": avail},
        "options": [{"id": o, "semantics": {"alpha": (o == "a") != flip}}
                    for o in opts],
        "rule": {"name": "all_required", "operands": {"features": ["alpha"]}},
        "label": label, "split": "final"}
    rows = []
    # 20 answerable nuisance groups (fixed-rule track).
    for g in range(20):
        gid = f"t-g{100000 + g:06d}"
        rows.append(mk(f"{gid}-n0", gid, f"{gid}-nuisance", "nuisance",
                       "m017-all_required-v1", True, 1, ["a", "b"], "a"))
        rows.append(mk(f"{gid}-n1", gid, f"{gid}-nuisance", "nuisance",
                       "m017-all_required-v1", True, 1, ["b", "a"], "a"))
    # 5 no-answer nuisance groups.
    for g in range(5):
        gid = f"t-g{200000 + g:06d}"
        rows.append(mk(f"{gid}-n0", gid, f"{gid}-nuisance", "nuisance",
                       "m017-any_required-v1", False, 1, ["a", "b"], None))
        rows.append(mk(f"{gid}-n1", gid, f"{gid}-nuisance", "nuisance",
                       "m017-any_required-v1", False, 1, ["b", "a"], None))
    # 5 exclusive causal pairs (rule-conditioned track).
    for g in range(5):
        gid = f"t-g{300000 + g:06d}"
        rows.append(mk(f"{gid}-causal-before", gid, f"{gid}-causal", "causal_flip",
                       "m017-exclusive-v1", True, 1, ["a", "b"], "a"))
        rows.append(mk(f"{gid}-causal-after", gid, f"{gid}-causal", "causal_flip",
                       "m017-exclusive-v1", True, 0, ["a", "b"], None, True))
    return rows


def make_manifest(arch, corpus, perfect, protocol_sha, freeze_sha):
    outs = []
    for c in corpus:
        order = [o["id"] for o in c["options"]]
        tgt = c["label"]
        if perfect:
            pred = tgt
            a = 0.99 if tgt is not None else 0.01
        else:
            # Mimic DEV legacy profile: abstain everywhere answerable-side
            # wrong, no-answer side right.
            pred = None
            a = 0.01
        if tgt is not None:
            probs = [0.9 if oid == tgt else 0.1 for oid in order]
        elif c["case_id"].endswith("causal-after"):
            probs = [0.2 if oid == order[0] else 0.8 for oid in order]
        else:
            probs = [0.5 for _ in order]
        s = sum(probs)
        probs = [p / s for p in probs]
        outs.append({"case_id": c["case_id"], "leakage_group": c["group_id"],
                     "family": c["family"], "target": tgt, "prediction": pred,
                     "raw_probabilities": probs, "raw_logits": [0.0] * len(order),
                     "answerability_probability": a, "option_ids": order})
    return {"architecture": arch, "evaluated_partition": "test",
            "test_evaluation_performed": True, "protocol_sha256": protocol_sha,
            "freeze_sha256": freeze_sha, "outcomes": outs}


class AnalyzeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if WORK.exists():
            import shutil
            shutil.rmtree(WORK)
        WORK.mkdir(parents=True, exist_ok=True)
        cls.corpus = make_corpus()
        (WORK / "corpus.jsonl").write_text(
            "\n".join(json.dumps(r) for r in cls.corpus) + "\n")
        cls.protocol_src = WORK / "protocol.json"
        cls.protocol_src.write_text(json.dumps(
            json.loads((ROOT / "docs/m017-protocol-v1.json").read_text()),
            indent=2, sort_keys=True) + "\n")
        cls.protocol_sha = sha_bytes(cls.protocol_src.read_bytes())
        cls.freeze_sha = sha_bytes(b'{"preliminary": "test"}')
        (WORK / "binding.json").write_text(json.dumps(
            {"final_status": "FINAL_NOT_YET_RUN",
             "preliminary_sha256": cls.freeze_sha,
             "binding_sha256": sha_bytes(b"binding")}) + "\n")
        cls.dev_controls = WORK / "dev-controls.json"
        cls.dev_controls.write_text(json.dumps({"negative_controls": {
            "context_only_conditional_accuracy": 0.29}}) + "\n")

    def _run_analyzer(self, perfect_tiny, out_name, freeze_ok=True, proto_ok=True):
        paths = []
        for arch in ("typed-choice-tinymlp", "typed-choice",
                     "typed-choice-cross", "typed-choice-compositional"):
            m = make_manifest(arch, self.corpus,
                              perfect=(perfect_tiny and arch == "typed-choice-tinymlp"),
                              protocol_sha=self.protocol_sha if proto_ok else sha_bytes(b"wrong"),
                              freeze_sha=self.freeze_sha if freeze_ok else sha_bytes(b"wrong"))
            p = WORK / f"{out_name}-{arch}.manifest.json"
            p.write_text(json.dumps(m))
            paths.append(str(p))
        out = WORK / f"{out_name}-ledger.json"
        # NOTE: no cleanup here — single-use semantics require the second
        # write to the same path to fail. setUpClass clears WORK once.
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/analyze_m017_final.py"),
             "--manifests"] + paths + [
                 "--corpus", str(WORK / "corpus.jsonl"),
                 "--protocol", str(self.protocol_src),
                 "--binding", str(WORK / "binding.json"),
                 "--dev-controls", str(self.dev_controls),
                 "--out", str(out)],
            capture_output=True, text=True, cwd=ROOT)
        return proc, out

    def test_perfect_tinymlp_passes_gates(self):
        proc, out = self._run_analyzer(True, "pass")
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        ledger = json.loads(out.read_text())
        self.assertEqual(ledger["verdicts"]["fixed_rule_robustness"], "PASS")
        self.assertIn("overall", ledger["verdicts"])

    def test_wrong_freeze_fails_closed(self):
        proc, out = self._run_analyzer(True, "freezefail", freeze_ok=False)
        self.assertNotEqual(proc.returncode, 0)

    def test_wrong_protocol_fails_closed(self):
        proc, out = self._run_analyzer(True, "protofail", proto_ok=False)
        self.assertNotEqual(proc.returncode, 0)

    def test_ledger_is_single_use(self):
        proc, out = self._run_analyzer(True, "single")
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        proc2, _ = self._run_analyzer(True, "single")
        self.assertNotEqual(proc2.returncode, 0)


if __name__ == "__main__":
    unittest.main()
