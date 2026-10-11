#!/usr/bin/env python3
"""Deterministic, grouped M013 quality analysis over frozen runtime reports."""
import json
import math
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
OUT = ROOT / "target/m013"
REPS = 10_000
SEED = 13013

def read(path): return json.loads(path.read_text())

def percentile(xs, p):
    xs = sorted(xs)
    at = (len(xs)-1)*p
    lo, hi = math.floor(at), math.ceil(at)
    return xs[lo] + (xs[hi]-xs[lo])*(at-lo)

def group_bootstrap(rows, metric, reps=REPS):
    groups = defaultdict(list)
    for row in rows: groups[row["leakage_group"]].append(row)
    vals = {g: metric(v) for g,v in groups.items() if metric(v) is not None}
    rng = random.Random(SEED)
    samples=[]
    keys=list(vals)
    for _ in range(reps): samples.append(sum(vals[keys[rng.randrange(len(keys))]] for _ in keys)/len(keys))
    return {"groups":len(keys),"replicates":reps,"confidence":0.95,"lower":percentile(samples,.025),"upper":percentile(samples,.975)}

def average(rows, fn): return sum(fn(row) for row in rows)/len(rows) if rows else None

def roc_auc(rows):
    pos=[r for r in rows if r["target"] is not None]
    y=[r["target"] for r in pos]
    scores=[r["answerability_probability"] for r in pos]
    positives=[s for s,t in zip(scores,y) if t is not None]
    negatives=[s for s,t in zip(scores,y) if t is None]
    if not positives or not negatives:return None
    return sum(1 if p>n else .5 if p==n else 0 for p in positives for n in negatives)/(len(positives)*len(negatives))

def choice_metrics(rows):
    answerable=[r for r in rows if r["target"] is not None]
    noanswer=[r for r in rows if r["target"] is None]
    answered=[r for r in answerable if not r["abstained"]]
    def correct(r): return (not r["abstained"]) and r["prediction"]==r["target"]
    ll=[]; brier=[]
    for r in answerable:
        p=r["raw_probabilities"]; target=next((i for i,o in enumerate(r["raw_logits"] or []) if False),None)
        # Dataset label is an option ID; recover its position from report option order,
        # stored alongside the raw vector in the cases manifest below.
        index=r["target_index"]
        q=p[index]
        ll.append(-math.log(max(q,1e-15)))
        brier.append(sum((x-(1.0 if i==index else 0.0))**2 for i,x in enumerate(p)))
    coverage=len(answered)/len(rows) if rows else None
    risk=1-average(answered,correct) if answered else None
    return {"cases":len(rows),"answerable":len(answerable),"no_answer":len(noanswer),
            "answerable_accuracy_including_abstentions":average(answerable,correct),
            "conditional_option_log_loss":sum(ll)/len(ll) if ll else None,
            "conditional_option_brier":sum(brier)/len(brier) if brier else None,
            "no_answer_recall":sum(r["abstained"] for r in noanswer)/len(noanswer) if noanswer else None,
            "false_abstention_rate":sum(r["abstained"] for r in answerable)/len(answerable) if answerable else None,
            "coverage":coverage,"selective_risk_answerable":risk,"answerability_auroc":roc_auc(rows)}

def main():
    choice_data=read(FIX/"m013-choice-v1.json")
    binary_data=read(FIX/"m013-binary-v1.json")
    choice_split=read(FIX/"m013-choice-v1.split.json")
    binary_split=read(FIX/"m013-binary-v1.split.json")
    choice_examples={e["case_id"]:e for e in choice_data["examples"]}
    binary_examples={e["case_id"]:e for e in binary_data["examples"]}
    reports={n:read(OUT/f"{n}.report.json") for n in ("choice-legacy","choice-cross","binary")}
    crows={n:r["outcomes"] for n,r in reports.items() if n.startswith("choice")}
    for rows in crows.values():
        for row in rows:
            example=choice_examples[row["case_id"]]
            options=example["request"]["spec"]["options"]
            row["target_index"]=next((i for i,o in enumerate(options) if o["id"]==row["target"]),None) if row["target"] is not None else None
            row["family"]=example["family"]
    choice={}
    for name,rows in crows.items():
        choice[name]={"overall":choice_metrics(rows),"slices":{}}
        for family in sorted({r["family"] for r in rows}):
            slice_rows=[r for r in rows if r["family"]==family]
            item=choice_metrics(slice_rows)
            item["independent_groups"]=len({r["leakage_group"] for r in slice_rows})
            item["no_answer_groups"]=len({r["leakage_group"] for r in slice_rows if r["target"] is None})
            item["support_sufficient"]=item["independent_groups"]>=50 and (not item["no_answer"] or item["no_answer_groups"]>=20)
            choice[name]["slices"][family]=item
        choice[name]["correctness_ci"]=group_bootstrap(rows,lambda g:choice_metrics(g)["answerable_accuracy_including_abstentions"])
    legacy={r["case_id"]:r for r in crows["choice-legacy"]}
    cross={r["case_id"]:r for r in crows["choice-cross"]}
    paired=[]
    for case_id,a in legacy.items():
        b=cross[case_id]
        if a["target"] is not None:
            ac=float((not a["abstained"]) and a["prediction"]==a["target"])
            bc=float((not b["abstained"]) and b["prediction"]==b["target"])
            paired.append({"case_id":case_id,"leakage_group":a["leakage_group"],"delta":bc-ac})
    choice["cross_minus_legacy_answerable_correctness"]={"mean":average(paired,lambda r:r["delta"]),"ci":group_bootstrap(paired,lambda g:average(g,lambda r:r["delta"]))}
    b_rows=reports["binary"]["outcomes"]
    for r in b_rows:r["family"]=binary_examples[r["case_id"]]["family"]
    train_ids=set(binary_split["train"])
    train_prior=average([binary_examples[i] for i in train_ids],lambda e:float(e["label"]["value"]))
    binary={"train_prior":train_prior,"overall":{},"slices":{}}
    def brier_row(r):return (float(r["target"])-float(r["score"]))**2
    def prior_delta(group):return average(group,lambda r:((float(r["target"])-float(r["score"]))**2)-((float(r["target"])-train_prior)**2))
    for family in sorted({r["family"] for r in b_rows}):
        rows=[r for r in b_rows if r["family"]==family]
        n_groups=len({r["leakage_group"] for r in rows})
        labels=[bool(r["target"]) for r in rows]
        result={"cases":len(rows),"independent_groups":n_groups,"positive":sum(labels),"negative":len(labels)-sum(labels),
                "brier":average(rows,brier_row),"brier_improvement_vs_train_prior":-average(rows,lambda r:brier_row(r)-((float(r["target"])-train_prior)**2)),
                "improvement_ci_vs_train_prior":group_bootstrap(rows,prior_delta),
                "support_sufficient":n_groups>=50}
        binary["slices"][family]=result
    binary["overall"]=binary["slices"].get("m013-binary-id-a-v1")
    output={"protocol":"docs/m013-protocol-v1.md","source_freeze":"c56f442fae14ede38fd1cd6e0eccf61315df96da",
            "choice":choice,"binary":binary,
            "note":"Final runtime decisions, scores, abstention, and family slices are evaluated from frozen M013 held-out reports. Synthetic-only."}
    (OUT/"quality-analysis.json").write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print(json.dumps(output,indent=2,sort_keys=True))

if __name__=="__main__":main()
