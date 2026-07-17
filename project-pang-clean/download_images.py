#!/usr/bin/env python3
"""Download all manifest images at 1024px into ~/project-pang-clean/raw/{rownum}.jpg.
rownum = manifest CSV row order (0-based), so labels map back by index."""
import csv, json, time, urllib.parse, urllib.request
from pathlib import Path

WORK=Path("/Users/admin/project-pang-clean")
RAW=WORK/"raw"; RAW.mkdir(exist_ok=True)
UA="ProjectPang-clean/1.0 (academic; lnwniorxd@gmail.com)"
rows=list(csv.DictReader(open(WORK/"manifest.csv",encoding="utf-8")))

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=120) as r: return r.read()

ok=fail=skip=0; failed=[]
for i,r in enumerate(rows):
    dest=RAW/f"{i:05d}.jpg"
    if dest.exists() and dest.stat().st_size>0: skip+=1; continue
    url=r["thumb_url"]+"?width=1024"
    try:
        data=fetch(url); dest.write_bytes(data); ok+=1
        time.sleep(0.2)
    except Exception as e:
        fail+=1; failed.append((i,r["image_id"],str(e)[:60]))
    if (i+1)%100==0: print(f"{i+1}/{len(rows)}  ok={ok} skip={skip} fail={fail}",flush=True)

json.dump(failed,open(WORK/"download_failures.json","w"))
print(f"\nDONE ok={ok} skip={skip} fail={fail}  total_files={len(list(RAW.glob('*.jpg')))}")
sz=sum(f.stat().st_size for f in RAW.glob('*.jpg'))/1e6
print(f"raw/ size: {sz:.0f} MB")
