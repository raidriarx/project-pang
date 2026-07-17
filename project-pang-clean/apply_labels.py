#!/usr/bin/env python3
"""Fan out unit labels (labels.json: idx->[label,conf,note]) to all images,
write labeled_clean.csv, and copy images into images/<label>/ folders."""
import csv, json, shutil
from pathlib import Path
from collections import Counter

WORK=Path("/Users/admin/project-pang-clean")
RAW=WORK/"raw"; IMG=WORK/"images"
index=json.load(open(WORK/"index.json",encoding="utf-8"))
labels=json.load(open(WORK/"labels.json",encoding="utf-8"))
rows=list(csv.DictReader(open(WORK/"manifest.csv",encoding="utf-8")))
for i,r in enumerate(rows): r["_row"]=i

def unit_key(r):
    sc=r["seed_category"]
    if sc.startswith("Statues of the Buddha"):
        return "wat:"+r["wat"] if r["wat"] else "file:"+r["file_name"]
    return "cat:"+sc

unit_label={}
for e in index:
    lab=labels.get(str(e["idx"]))
    if lab: unit_label[(e["candidate"],e["unit"])]=lab

out=[]
for r in rows:
    lab=unit_label.get((r["pang_candidate"],unit_key(r)),["uncertain","low","no rep"])
    r["ai_pang"],r["ai_confidence"],r["ai_note"]=lab
    out.append(r)

cols=["_row","file_name","seed_category","pang_candidate","wat","ai_pang","ai_confidence","ai_note","license","author","url"]
with open(WORK/"labeled_clean.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore"); w.writeheader(); w.writerows(out)

# organize copies into images/<label>/
for r in out:
    lab=r["ai_pang"]
    d=IMG/lab; d.mkdir(parents=True,exist_ok=True)
    src=RAW/f"{r['_row']:05d}.jpg"
    if src.exists(): shutil.copy(src, d/f"{r['_row']:05d}.jpg")

print("labeled",len(out),"images\n")
for k,v in Counter(r["ai_pang"] for r in out).most_common(): print(f"  {k:12s} {v}")
u=[r for r in out if r["ai_pang"] in {"marawichai","samathi","nakprok","prathanphon","saiyat"} and r["ai_confidence"] in {"high","medium"}]
print(f"\nusable(5-class hi+med): {len(u)}")
for k,v in Counter(r["ai_pang"] for r in u).most_common(): print(f"  {k:12s} {v}")
