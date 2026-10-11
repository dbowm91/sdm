#!/usr/bin/env python3
"""Verify and analyze the frozen M013a runtime reports without fitting."""
import copy
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/"fixtures"
OUT=ROOT/"target/m013a"
SEED=14014
REPLICATES=10_000

def read(path): return json.loads(path.read_text())
def mean(xs): return sum(xs)/len(xs) if xs else None
def quantile(xs,p):
    xs=sorted(xs); x=(len(xs)-1)*p; lo=math.floor(x); hi=math.ceil(x)
    return xs[lo]+(xs[hi]-xs[lo])*(x-lo)

def group_bootstrap(rows, value, paired=False):
    groups=defaultdict(list)
    for row in rows: groups[row["leakage_group"]].append(row)
    per_group={g:value(xs) for g,xs in groups.items()}
    per_group={g:x for g,x in per_group.items() if x is not None}
    if not per_group:return {"groups":0,"replicates":REPLICATES,"lower":None,"upper":None}
    keys=list(per_group); rng=random.Random(SEED); sims=[]
    for _ in range(REPLICATES): sims.append(mean([per_group[keys[rng.randrange(len(keys))]] for _ in keys]))
    return {"groups":len(keys),"replicates":REPLICATES,"confidence":0.95,
            "lower":quantile(sims,.025),"upper":quantile(sims,.975)}

def binary_auc(rows):
    positives=[r["answerability_probability"] for r in rows if r["target"] is not None]
    negatives=[r["answerability_probability"] for r in rows if r["target"] is None]
    if not positives or not negatives:return None
    return sum((p>n)+.5*(p==n) for p in positives for n in negatives)/(len(positives)*len(negatives))

def average_precision(rows):
    ordered=sorted(rows,key=lambda r:r["answerability_probability"],reverse=True)
    total=sum(r["target"] is not None for r in ordered)
    if not total or total==len(ordered):return None
    hit=0; area=0.0
    for i,row in enumerate(ordered,1):
        if row["target"] is not None: hit+=1; area+=hit/i
    return area/total

def risk_coverage(rows):
    ordered=sorted(rows,key=lambda r:r["answerability_probability"],reverse=True)
    curve=[]
    errors=0
    for i,row in enumerate(ordered,1):
        pred=row["raw_probabilities"].index(max(row["raw_probabilities"]))
        correct=row["target"] is not None and pred==row["target_index"]
        errors+=not correct
        curve.append({"coverage":i/len(ordered),"risk":errors/i})
    if len(curve)<2:return curve,None
    aurc=sum((curve[i]["coverage"]-curve[i-1]["coverage"])*(curve[i]["risk"]+curve[i-1]["risk"])/2 for i in range(1,len(curve)))
    return curve,aurc

def choice_metrics(rows):
    ans=[r for r in rows if r["target"] is not None]
    noans=[r for r in rows if r["target"] is None]
    answered=[r for r in rows if not r["abstained"]]
    correct=lambda r:(r["target"] is not None and not r["abstained"] and r["prediction"]==r["target"])
    ll=[]; briers=[]
    for r in ans:
        p=r["raw_probabilities"]; ti=r["target_index"]
        ll.append(-math.log(max(p[ti],1e-15)))
        briers.append(sum((x-float(i==ti))**2 for i,x in enumerate(p)))
    curve,aurc=risk_coverage(rows)
    return {"cases":len(rows),"answerable":len(ans),"no_answer":len(noans),
            "final_accuracy_on_answerable_including_abstentions":mean([float(correct(r)) for r in ans]),
            "conditional_option_log_loss":mean(ll),"conditional_option_brier":mean(briers),
            "answerability_auroc":binary_auc(rows),"answerability_average_precision":average_precision(rows),
            "no_answer_recall":mean([float(r["abstained"]) for r in noans]),
            "false_abstention_rate":mean([float(r["abstained"]) for r in ans]),
            "coverage":mean([float(not r["abstained"]) for r in rows]),
            "selective_risk":1-mean([float(correct(r)) for r in answered]) if answered else None,
            "risk_coverage_points":curve,"aurc":aurc}

def brier(r):return (float(r["target"])-float(r["score"]))**2

def verify_pairs(bundle):
    groups=defaultdict(list)
    for e in bundle["examples"]:groups[e["counterfactual_pair"]].append(e)
    for pair,rows in groups.items():
        if len(rows)!=2 or rows[0]["leakage_group"]!=rows[1]["leakage_group"]:raise ValueError(f"bad pair {pair}")
        normalized=[]
        for row in rows:
            x=copy.deepcopy(row); x["case_id"]="<case>"; x["request"]["request_id"]="<request>"; x["label"]["value"]="<label>"
            for p in [x["typed_rank_features"]["context"],*x["typed_rank_features"]["candidates"].values()]:
                for f in p["fields"]:
                    if f["id"]=="active":f["value"]["value"]="<active>"
            normalized.append(x)
        if normalized[0]!=normalized[1]:raise ValueError(f"counterfactual mismatch {pair}")

def main():
    cb=read(FIX/"m013a-choice-v1.json"); bb=read(FIX/"m013a-binary-v1.json")
    cs=read(FIX/"m013a-choice-v1.split.json"); bs=read(FIX/"m013a-binary-v1.split.json")
    verify_pairs(cb); verify_pairs(bb)
    cm={e["case_id"]:e for e in cb["examples"]}; bm={e["case_id"]:e for e in bb["examples"]}
    reports={n:read(OUT/f"{n}.report.json") for n in ("choice-legacy","choice-cross","binary")}
    expected_families={f"m013a-choice-{x}-v1" for x in ("load-shift","text-shift","combined-shift")}
    test_choice=[cm[i] for i in cs["test"]]
    test_families={e["family"] for e in test_choice}
    for family in expected_families:
        if family not in test_families or any(cm[i]["family"]==family for i in cs["train"]+cs["dev"]+cs["excluded"]):raise ValueError(f"OOD family split mismatch: {family}")
    if cs["excluded"] or bs["excluded"]:raise ValueError("unexpected excluded groups in M013a split")
    for rows,examples in ((reports["choice-legacy"]["outcomes"],cm),(reports["choice-cross"]["outcomes"],cm)):
        for r in rows:
            e=examples[r["case_id"]]; options=e["request"]["spec"]["options"]
            r["target_index"]=next((i for i,o in enumerate(options) if o["id"]==r["target"]),None) if r["target"] is not None else None
            r["family"]=e["family"]
            if r["raw_probabilities"] is None or r["raw_logits"] is None or r["answerability_probability"] is None:raise ValueError("quality diagnostics missing")
    choice={}
    for name in ("choice-legacy","choice-cross"):
        rows=reports[name]["outcomes"]; choice[name]={"overall":choice_metrics(rows),"slices":{}}
        for family in sorted({r["family"] for r in rows}):
            rs=[r for r in rows if r["family"]==family]; m=choice_metrics(rs)
            m["independent_groups"]=len({r["leakage_group"] for r in rs})
            m["no_answer_groups"]=len({r["leakage_group"] for r in rs if r["target"] is None})
            m["support_sufficient"]=m["independent_groups"]>=50 and (m["no_answer"]==0 or m["no_answer_groups"]>=20)
            m["accuracy_ci"]=group_bootstrap(rs,lambda g:mean([float(r["target"] is not None and not r["abstained"] and r["prediction"]==r["target"]) for r in g if r["target"] is not None]))
            choice[name]["slices"][family]=m
    leg={r["case_id"]:r for r in reports["choice-legacy"]["outcomes"]}; cross={r["case_id"]:r for r in reports["choice-cross"]["outcomes"]}
    paired=[]
    for case_id,a in leg.items():
        if a["target"] is None:continue
        b=cross[case_id]
        paired.append({"case_id":case_id,"leakage_group":a["leakage_group"],"delta":float(not b["abstained"] and b["prediction"]==b["target"])-float(not a["abstained"] and a["prediction"]==a["target"])})
    choice["cross_minus_legacy_accuracy"]={"mean":mean([r["delta"] for r in paired]),"ci":group_bootstrap(paired,lambda g:mean([r["delta"] for r in g]))}
    pair_rows=defaultdict(list)
    for r in rows:pair_rows[r["leakage_group"]].append(r)
    flips=[]
    for group,rs in pair_rows.items():
        if len(rs)!=2 or any(r["target"] is None for r in rs) or rs[0]["target"]==rs[1]["target"]:continue
        margins=[]
        for r in rs:
            other=1-r["target_index"]
            margins.append(r["raw_logits"][r["target_index"]]-r["raw_logits"][other])
        flips.append({"leakage_group":group,"both_final_correct":all(not r["abstained"] and r["prediction"]==r["target"] for r in rs),
                      "after_flip_correct":not rs[1]["abstained"] and rs[1]["prediction"]==rs[1]["target"],
                      "raw_target_margin_flips":margins[0]*margins[1]<0,
                      "target_margin_after_flip":margins[1]})
    choice["target_flipping_counterfactuals"]={"pairs":len(flips),
        "both_final_decisions_correct":mean([float(x["both_final_correct"]) for x in flips]),
        "second_target_correct_after_flip":mean([float(x["after_flip_correct"]) for x in flips]),
        "raw_target_margin_changes_sign":mean([float(x["raw_target_margin_flips"]) for x in flips]),
        "both_correct_ci":group_bootstrap(flips,lambda g:mean([float(x["both_final_correct"]) for x in g]))}
    # Controls use no fitted selector: fixed option identity, always answer,
    # always abstain, and cross-group shuffled scores are diagnostics only.
    rows=reports["choice-cross"]["outcomes"]
    rng=random.Random(SEED); donors=rows.copy(); rng.shuffle(donors)
    train_target_ids=[cm[i]["label"]["value"] for i in cs["train"] if cm[i]["label"]["value"] is not None]
    majority_id=Counter(train_target_ids).most_common(1)[0][0]
    controls={"train_majority_option_id":majority_id,
              "train_majority_option_id_accuracy":mean([float(r["target"]==majority_id) for r in rows if r["target"] is not None]),
              "always_abstain_accuracy":0.0,"always_abstain_no_answer_recall":1.0,
              "always_answer_accuracy":mean([float(r["target"] is not None and r["raw_probabilities"].index(max(r["raw_probabilities"]))==r["target_index"]) for r in rows if r["target"] is not None]),
              "context_only_identical_option_features_min_id_accuracy":mean([float(r["target"] is not None and min(o["id"] for o in cm[r["case_id"]]["request"]["spec"]["options"])==r["target"]) for r in rows if r["target"] is not None])}
    controls["shuffled_score_accuracy"]=mean([float(r["target"] is not None and d["raw_logits"].index(max(d["raw_logits"]))==r["target_index"]) for r,d in zip(rows,donors) if r["target"] is not None])
    choice["negative_controls"]=controls
    b_rows=reports["binary"]["outcomes"]
    for r in b_rows:r["family"]=bm[r["case_id"]]["family"]
    train_prior=mean([float(bm[i]["label"]["value"]) for i in bs["train"]])
    binary={"train_prior":train_prior,"slices":{}}
    for family in sorted({r["family"] for r in b_rows}):
        rs=[r for r in b_rows if r["family"]==family]
        groups=len({r["leakage_group"] for r in rs})
        result={"cases":len(rs),"independent_groups":groups,"positive":sum(bool(r["target"]) for r in rs),"negative":sum(not bool(r["target"]) for r in rs),
                "brier":mean([brier(r) for r in rs]),"brier_improvement_vs_train_prior":mean([((float(r["target"])-train_prior)**2)-brier(r) for r in rs]),
                "improvement_ci_vs_train_prior":group_bootstrap(rs,lambda g:mean([((float(r["target"])-train_prior)**2)-brier(r) for r in g])),
                "group_support_by_label":{str(y):len({r["leakage_group"] for r in rs if bool(r["target"])==y}) for y in (False,True)},
                "runtime_coverage":mean([float(not r["abstained"]) for r in rs]),
                "runtime_abstention_rate":mean([float(r["abstained"]) for r in rs]),
                "final_accuracy_including_abstentions":mean([float(not r["abstained"] and bool(r["prediction"])==bool(r["target"])) for r in rs]),
                "selective_risk":1-mean([float(bool(r["prediction"])==bool(r["target"])) for r in rs if not r["abstained"]]) if any(not r["abstained"] for r in rs) else None,
                "label_residuals":{str(y):mean([float(r["score"])-float(r["target"]) for r in rs if bool(r["target"])==y]) for y in (False,True)},
                "nuisance_probability_delta":{key:mean([r["nuisance_probabilities"][key]-r["score"] for r in rs]) for key in ("load","text","combined")},
                "support_sufficient":groups>=50}
        binary["slices"][family]=result
    # Each nuisance transformation is label-preserving and changes one feature
    # family at a time; report both mean delta and label-stratified deltas.
    binary["nuisance_label_stratified"]={key:{str(y):mean([r["nuisance_probabilities"][key]-r["score"] for r in b_rows if bool(r["target"])==y]) for y in (False,True)} for key in ("load","text","combined")}
    output={"protocol":"docs/m013a-protocol-v1.md","seed":SEED,"replicates":REPLICATES,
            "choice":choice,"binary":binary,"dataset_sha256":{"choice":reports["choice-cross"]["dataset_sha256"],"binary":reports["binary"]["dataset_sha256"]},
            "note":"All primary metrics use final runtime decisions; option loss/Brier are conditional on answerable cases. Synthetic only; negative controls are not qualification candidates."}
    (OUT/"quality-analysis.json").write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print(json.dumps(output,indent=2,sort_keys=True))

if __name__=="__main__":main()
