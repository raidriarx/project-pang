#!/usr/bin/env python3
"""Build labeling montages from downloaded raw/ images: one representative cell
per statue-unit (dataset collapses ~2373 imgs -> ~185 units). Local only, no network."""
import csv, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WORK=Path("/Users/admin/project-pang-clean")
RAW=WORK/"raw"; SHEETS=WORK/"sheets"; SHEETS.mkdir(exist_ok=True)
rows=list(csv.DictReader(open(WORK/"manifest.csv",encoding="utf-8")))
for i,r in enumerate(rows): r["_row"]=i

def unit_key(r):
    sc=r["seed_category"]
    if sc.startswith("Statues of the Buddha"):
        return "wat:"+r["wat"] if r["wat"] else "file:"+r["file_name"]
    return "cat:"+sc

groups={}
for r in rows: groups.setdefault(r["pang_candidate"],{}).setdefault(unit_key(r),[]).append(r)

try:
    fsm=ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf",15)
except Exception: fsm=ImageFont.load_default()

ORDER=["saiyat","nakprok","prathanphon","standing_unknown","seated_unknown"]
CFG={"seated_unknown":(3,520),"prathanphon":(3,520)}  # bigger cells for palm detail
PAD=4; LABELH=34; index=[]
for cand in ORDER:
    units=groups.get(cand,{}); cols,cell=CFG.get(cand,(4,360)); per=cols*3
    reps=[]
    for uk,urows in units.items():
        rep=max(urows,key=lambda r:int(r["width"] or 0)*int(r["height"] or 0))
        reps.append((uk,rep,len(urows)))
    reps.sort(key=lambda x:-x[2])
    for s in range(0,len(reps),per):
        batch=reps[s:s+per]; n=len(batch); rr=(n+cols-1)//cols
        W=cols*(cell+PAD)+PAD; H=rr*(cell+LABELH+PAD)+PAD
        sheet=Image.new("RGB",(W,H),(24,24,28)); d=ImageDraw.Draw(sheet)
        for i,(uk,rep,cnt) in enumerate(batch):
            gi=len(index)
            index.append({"idx":gi,"candidate":cand,"unit":uk,"count":cnt,"rep_row":rep["_row"],"wat":rep["wat"]})
            cx=PAD+(i%cols)*(cell+PAD); cy=PAD+(i//cols)*(cell+LABELH+PAD)
            f=RAW/f"{rep['_row']:05d}.jpg"
            try:
                im=Image.open(f).convert("RGB"); im.thumbnail((cell,cell))
                sheet.paste(im,(cx+(cell-im.width)//2,cy+LABELH+(cell-im.height)//2))
            except Exception as e:
                d.rectangle([cx,cy+LABELH,cx+cell,cy+cell+LABELH],fill=(60,30,30)); d.text((cx+6,cy+LABELH+6),"ERR",font=fsm,fill=(255,180,180))
            d.rectangle([cx,cy,cx+cell,cy+LABELH],fill=(0,0,0))
            d.text((cx+5,cy+6),f"#{gi} [{cand[:5]}] n={cnt} {(rep['wat'] or '?')[:30]}",font=fsm,fill=(255,235,120))
        out=SHEETS/f"sheet_{cand}_{s//per:02d}.png"; sheet.save(out); print("saved",out.name,f"({n})",flush=True)
json.dump(index,open(WORK/"index.json","w"),ensure_ascii=False)
print("units:",len(index))
