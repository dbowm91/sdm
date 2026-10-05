#!/usr/bin/env python3
"""Export frozen sanitized CodeGG Rank fixtures to generic SDM case JSONL."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/codegg-compatibility-v1.jsonl"
OUTPUT = ROOT / "fixtures/compatibility-rank-cases-v1.jsonl"

def main():
    rows=[]
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        fixture=json.loads(line)
        req=fixture["request"]
        if req["spec"]["kind"] != "rank" or fixture.get("source_case_id") is None:
            continue
        if fixture.get("expect_request_valid") is False:
            continue
        response=fixture.get("response")
        if response is None:
            continue
        group=re.sub(r"-variant-[0-9]+$", "", fixture["source_case_id"])
        rows.append({"schema_version":1,"case_id":fixture["fixture_id"],"leakage_group":group,
                     "request":req,"response":response})
    OUTPUT.write_text("\n".join(json.dumps(row,sort_keys=True,separators=(",",":")) for row in rows)+"\n",encoding="utf-8")
    print(f"wrote {len(rows)} sanitized cases to {OUTPUT.relative_to(ROOT)}")

if __name__ == "__main__": main()
