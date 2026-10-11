#!/usr/bin/env python3
"""Check M011's Linux-x64 report identity after an exact reproduction run."""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXPECTED={
 "binary":"9e1af745541f2a739fe924f3dda4bd189080d205099a46bd259b7fe9acad9346",
 "choice":"d5c1b2a024bfaa22f2c0cc5f24a6a565b1785b7c0ff0eba56329a7d3093fc53c",
 "score":"1a62724e7355b9f8acfdb3d1025db8c63d023bd7f34d4dc44aa079818c3273ef",
 "rank":"b4751ae08c996a7cca767e83dcc5e90346627a1177e0c0afbbe2be0c883128a6",
 "rank-linear":"e29c24b0967705540b774ce16731e17327262396c5860e719d8a66ae13b57c98",
 "rank-nonlinear":"9085a29adf90b0d923b9c6e34b86cb9ffff5c42ee93d4f42fdac1db5df3d831a",
}
for name,expected in EXPECTED.items():
 path=ROOT/f"target/m011-v2/{name}.report.json"
 actual=hashlib.sha256(path.read_bytes()).hexdigest()
 if actual!=expected:raise SystemExit(f"M011 {name} report changed: {actual} != {expected}")
 print(f"M011 {name} report identity preserved: sha256:{actual}")
