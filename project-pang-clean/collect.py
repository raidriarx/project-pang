#!/usr/bin/env python3
"""Rebuild the CLEAN Project Pang dataset by crawling Wikimedia category trees
(same seeds as the original vault crawl). Metadata only -> manifest.csv.
Saved OUTSIDE ~/Documents to avoid the macOS Documents permission block."""
import csv, json, re, time, urllib.parse, urllib.request
from pathlib import Path

API="https://commons.wikimedia.org/w/api.php"
UA="ProjectPang-clean/1.0 (academic; lnwniorxd@gmail.com)"
OUT=Path("/Users/admin/project-pang-clean/manifest.csv")

SEEDS={
 "Category:Statues of the Buddha reclining in Thailand":("saiyat","thailand"),
 "Category:Statues of the Buddha seated in Thailand":("seated_unknown","thailand"),
 "Category:Statues of the Buddha standing in Thailand":("standing_unknown","thailand"),
 "Category:Mucilinda":("nakprok","global"),
 "Category:Vārada mudra":("prathanphon","global"),
}
MAXDEPTH={"thailand":3,"global":2}
RATE=0.4

def api(params):
    data=urllib.parse.urlencode({**params,"format":"json"}).encode()
    req=urllib.request.Request(API,data=data,headers={"User-Agent":UA})
    time.sleep(RATE)
    return json.load(urllib.request.urlopen(req,timeout=60))

def walk(cat,pang,scope,maxd,depth=0,seen=None,out=None):
    if seen is None: seen=set()
    if out is None: out=[]
    if cat in seen or depth>maxd: return out
    seen.add(cat); cont={}
    while True:
        d=api({"action":"query","list":"categorymembers","cmtitle":cat,
               "cmtype":"file|subcat","cmlimit":500,**cont})
        for m in d.get("query",{}).get("categorymembers",[]):
            if m["ns"]==6: out.append((m["title"],cat,pang,scope))
            elif m["ns"]==14: walk(m["title"],pang,scope,maxd,depth+1,seen,out)
        if "continue" in d: cont=d["continue"]
        else: break
    return out

WAT=re.compile(r"(Wat\s+[A-Z][\w']*(?:\s+[A-Z][\w']*){0,3}|วัด[^\s,\(\)]+)")
def resolve_wat(cat,fn,desc):
    for t in (cat.replace("Category:",""),fn,desc or ""):
        m=WAT.search(t)
        if m: return m.group(1).strip()
    return ""
def strip(s): return re.sub(r"<[^>]+>","",s or "").strip()

collected=[]
for seed,(pang,scope) in SEEDS.items():
    print("crawl",seed,scope,flush=True)
    rows=walk(seed,pang,scope,MAXDEPTH[scope]); print("  ",len(rows),flush=True)
    collected.extend(rows)

by_title={}
for title,cat,pang,scope in collected:
    by_title.setdefault(title,(cat,pang,scope))
titles=list(by_title)
print("unique files:",len(titles),flush=True)

meta={}
props="ImageDescription|Artist|LicenseShortName|GPSLatitude|GPSLongitude"
for i in range(0,len(titles),50):
    b=titles[i:i+50]
    d=api({"action":"query","titles":"|".join(b),"prop":"imageinfo",
           "iiprop":"url|size|sha1|mediatype|extmetadata","iiextmetadatafilter":props})
    for p in d.get("query",{}).get("pages",{}).values():
        meta[p["title"]]=(p.get("imageinfo") or [{}])[0]
    print("meta",min(i+50,len(titles)),"/",len(titles),flush=True)

seen_sha=set(); rows_out=[]; skipped=0
for title,(cat,pang,scope) in by_title.items():
    ii=meta.get(title,{})
    if not ii or ii.get("mediatype")!="BITMAP": skipped+=1; continue
    w,h=ii.get("width",0),ii.get("height",0)
    if min(w,h)<256: skipped+=1; continue
    sha=ii.get("sha1","")
    if sha and sha in seen_sha: skipped+=1; continue
    seen_sha.add(sha)
    em=ii.get("extmetadata",{})
    desc=strip(em.get("ImageDescription",{}).get("value",""))
    rows_out.append({"image_id":title,"file_name":title.replace("File:",""),
        "seed_category":cat.replace("Category:",""),"pang_candidate":pang,"scope":scope,
        "wat":resolve_wat(cat,title.replace("File:",""),desc),
        "license":em.get("LicenseShortName",{}).get("value",""),
        "author":strip(em.get("Artist",{}).get("value","")),
        "width":w,"height":h,"url":ii.get("url",""),"sha1":sha,
        "thumb_url":"https://commons.wikimedia.org/wiki/Special:FilePath/"+urllib.parse.quote(title.replace("File:",""))})

cols=["image_id","file_name","seed_category","pang_candidate","scope","wat",
      "license","author","width","height","url","thumb_url","sha1"]
with open(OUT,"w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows_out)
from collections import Counter
print("\nwrote",len(rows_out),"rows (skipped",skipped,")")
for k,v in Counter(r["pang_candidate"] for r in rows_out).most_common(): print(f"  {k:18s} {v}")
# rough size estimate
avg_mb={'512':0.15,'1024':0.45}
print(f"\nEST download @512px ~{len(rows_out)*0.15:.0f} MB ; @1024px ~{len(rows_out)*0.45:.0f} MB")
