#!/usr/bin/env python3
"""Pre-inference integrity gate for the frozen M013a data and split files."""
import copy,json,hashlib
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; FIX=ROOT/"fixtures"; OUT=ROOT/"target/m013a"
EXPECTED={
 "choice":{"data":"52189cafbe52f5dbca66f286257cf91a5c961e06029e8a92a5013ee46257e586","split":"5c00db7cd2e31ca1864f885eeea57a59a06a952de1307d94f8f1f0b76f92fea4"},
 "binary":{"data":"edc857be6cc0b06e21b81df77f62a4bc261befa6f7adc58abf4788e6b842c1da","split":"97d86626281429236ece128c513878e2b54a984935cde9014876db278d1f5c21"}}
OOD=("load-shift","text-shift","combined-shift")

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify_pairs(examples):
 groups=defaultdict(list)
 for e in examples:groups[e["counterfactual_pair"]].append(e)
 for key,rows in groups.items():
  if len(rows)!=2 or rows[0]["leakage_group"]!=rows[1]["leakage_group"]:raise ValueError(f"invalid pair cardinality {key}")
  normalized=[]
  for row in rows:
   x=copy.deepcopy(row);x["case_id"]="<case>";x["request"]["request_id"]="<request>";x["label"]["value"]="<target>"
   for p in [x["typed_rank_features"]["context"],*x["typed_rank_features"]["candidates"].values()]:
    for f in p["fields"]:
     if f["id"]=="active":f["value"]["value"]="<active>"
   normalized.append(x)
  if normalized[0]!=normalized[1]:raise ValueError(f"pair changes a field besides active/target {key}")
 return groups

def main():
 result={}
 for task in ("binary","choice"):
  dp=FIX/f"m013a-{task}-v1.json";sp=FIX/f"m013a-{task}-v1.split.json"
  if sha(dp)!=EXPECTED[task]["data"] or sha(sp)!=EXPECTED[task]["split"]:raise ValueError(f"frozen {task} hash mismatch")
  bundle=json.loads(dp.read_text());split=json.loads(sp.read_text());examples=bundle["examples"]
  groups=verify_pairs(examples);byid={e["case_id"]:e for e in examples}
  parts={p:set(split[p]) for p in ("train","dev","test","excluded")}
  if any(parts[a]&parts[b] for a,b in (("train","dev"),("train","test"),("dev","test"))):raise ValueError("case split overlaps")
  if parts["excluded"]:raise ValueError("M013a excludes rows unexpectedly")
  group_parts={p:{byid[i]["leakage_group"] for i in ids} for p,ids in parts.items()}
  if any(group_parts[a]&group_parts[b] for a,b in (("train","dev"),("train","test"),("dev","test"))):raise ValueError("leakage groups cross split boundaries")
  family_counts={}
  for suffix in OOD:
   family=f"m013a-{task}-{suffix}-v1"
   if any(byid[i]["family"]==family for i in parts["train"]|parts["dev"]):raise ValueError(f"OOD family leaked into fit/dev: {family}")
   rows=[byid[i] for i in parts["test"] if byid[i]["family"]==family]
   count=len({e["leakage_group"] for e in rows})
   no_answer_groups=len({e["leakage_group"] for e in rows if e["label"]["value"] is None}) if task=="choice" else 0
   if count<50 or (task=="choice" and no_answer_groups<20):raise ValueError(f"insufficient {family}: groups={count}, no-answer={no_answer_groups}")
   family_counts[family]={"test_groups":count,"no_answer_groups":no_answer_groups,"cases":len(rows)}
  id_groups={}
  for suffix in ("id-a","id-b"):
   family=f"m013a-{task}-{suffix}-v1"; rows=[byid[i] for i in parts["test"] if byid[i]["family"]==family]
   count=len({e["leakage_group"] for e in rows})
   if count<50:raise ValueError(f"insufficient ID test support: {family} has {count} groups")
   id_groups[family]={"test_groups":count,"cases":len(rows)}
  test_rows=[byid[i] for i in parts["test"]]
  if task=="binary" and {bool(e["label"]["value"]) for e in test_rows}!={False,True}:raise ValueError("Binary test lacks class support")
  if task=="choice" and not {e["label"]["value"] is None for e in test_rows}=={False,True}:raise ValueError("Choice test lacks answerability support")
  result[task]={"dataset_sha256":"sha256:"+EXPECTED[task]["data"],"split_sha256":"sha256:"+EXPECTED[task]["split"],
                "cases":len(examples),"groups":len(groups),"split_cases":{p:len(v) for p,v in parts.items()},"id_slices":id_groups,"ood_slices":family_counts}
 OUT.mkdir(parents=True,exist_ok=True)
 path=OUT/"freeze-validation.json";path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":main()
