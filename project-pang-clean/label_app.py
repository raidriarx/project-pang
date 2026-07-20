#!/usr/bin/env python3
"""Human labeling app for Project Pang — review every photo one at a time.

Run:  python3 label_app.py   → open http://localhost:8765

7 decisions per photo: 5 pang / trash / later. Labels persist to
human_labels.json (atomic write per label, resumes where you left off).
Queue is priority-tiered (broken rare classes → uncertain → unknown →
exclude → healthy spot-check) and grouped by temple within each tier.
AI pre-labels are hidden unless you press A (peek is logged, for the paper's
independence story)."""
import csv, json, os, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

WORK = Path(__file__).resolve().parent  # portable: run from any clone
RAW = WORK / "raw"
EXAMPLES = WORK / "examples"  # book crops: <pang>.jpg (Fine Arts Dept, reference only)
OUT = WORK / "human_labels.json"   # pose labels (one annotator)
BOXOUT = WORK / "boxes.json"       # statue boxes (separate file → no merge conflicts)
PORT = 8765

LABELS = ["marawichai", "samathi", "nakprok", "prathanphon", "saiyat", "other", "trash", "later"]
# lower tier = reviewed first
TIER = {"samathi": 0, "nakprok": 0, "prathanphon": 0, "uncertain": 1,
        "unknown": 2, "exclude": 3, "marawichai": 4, "saiyat": 4}
TIER_NAMES = ["rare classes (broken)", "uncertain pile", "unknown", "exclude", "healthy spot-check"]


def load_rows():
    rows = list(csv.DictReader(open(WORK / "labeled_clean.csv", encoding="utf-8")))
    rows = [r for r in rows if (RAW / f"{int(r['_row']):05d}.jpg").exists()]
    for r in rows:
        r["_row"] = int(r["_row"])
        r["tier"] = TIER.get(r["ai_pang"], 4)
        r["group"] = r["wat"] or ("[" + r["seed_category"] + "]")
    rows.sort(key=lambda r: (r["tier"], r["group"], r["_row"]))
    return rows


def _load(path):
    if path.exists():
        return json.load(open(path, encoding="utf-8"))
    return {}


def _save(path, obj):
    fd, tmp = tempfile.mkstemp(dir=WORK, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)


def save_state(state):
    _save(OUT, state)


ROWS = load_rows()
STATE = _load(OUT)   # {"<row>": {"label":..., "ts":..., "peeked":bool}}
BOXES = _load(BOXOUT)  # {"<row>": {"box":[x,y,w,h], "ts":..., "by":...}}
# one-time migration: boxes stored inside label entries move to boxes.json
_migrated = False
for _k, _v in STATE.items():
    if "box" in _v:
        BOXES.setdefault(_k, {"box": _v.pop("box"), "by": "labeler", "ts": _v.get("ts")})
        _migrated = True
if _migrated:
    _save(OUT, STATE)
    _save(BOXOUT, BOXES)

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Pang Labeler</title>
<style>
:root{--bg:#16161a;--panel:#232329;--ink:#f4f4f0;--ink2:#a8a8a0;--acc:#3987e5;--warn:#e34948}
*{box-sizing:border-box;margin:0}body{background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#watbar{padding:10px 18px;background:var(--acc);color:#fff;font-weight:700;font-size:17px;display:flex;justify-content:space-between;align-items:center}
#watbar small{font-weight:400;opacity:.85}
#tierbar{padding:4px 18px;background:var(--panel);color:var(--ink2);font-size:12.5px;display:flex;justify-content:space-between}
#main{flex:1;display:flex;min-height:0}
#imgwrap{flex:1;display:flex;align-items:center;justify-content:center;background:#000;position:relative;min-width:0;cursor:crosshair}
#photo{max-width:100%;max-height:100%;object-fit:contain;user-select:none;-webkit-user-drag:none}
#dragrect,#boxrect{position:absolute;display:none;pointer-events:none;border:2px dashed var(--acc);background:rgba(57,135,229,.12)}
#boxrect{border:2.5px solid #1baf7a;background:rgba(27,175,122,.08)}
#pendchip{position:absolute;top:12px;left:12px;display:none;background:var(--acc);color:#fff;padding:7px 13px;border-radius:8px;font-size:13.5px;font-weight:600;pointer-events:none;z-index:4}
#goto{position:fixed;top:18%;left:50%;transform:translateX(-50%);display:none;z-index:9;background:var(--panel);border:1px solid #444;border-radius:10px;padding:14px 16px}
#goto input{background:#16161a;border:1px solid #3a3a42;border-radius:7px;color:var(--ink);font-size:15px;padding:7px 10px;width:130px}
#peek{position:absolute;bottom:12px;left:12px;background:rgba(20,20,24,.92);border:1px solid #444;border-radius:8px;padding:10px 14px;font-size:13.5px;display:none;max-width:70%;pointer-events:none}
#peek b{color:var(--acc)}
#side{width:290px;background:var(--panel);padding:14px;display:flex;flex-direction:column;gap:8px;overflow-y:auto}
button.lab{display:flex;justify-content:space-between;align-items:center;width:100%;padding:10px 12px;border:1px solid #3a3a42;border-radius:9px;background:#2b2b33;color:var(--ink);font-size:15px;cursor:pointer;text-align:left}
button.lab:hover{border-color:var(--acc)}
button.lab.picked{background:var(--acc);border-color:var(--acc);color:#fff}
button.lab kbd{background:#16161a;border-radius:5px;padding:1px 8px;font-size:12.5px;color:var(--ink2)}
button.lab.picked kbd{color:#dfe9ff}
button.lab img{width:54px;height:54px;object-fit:cover;border-radius:6px;background:#111}
button.lab .bl{display:flex;align-items:center;gap:10px}
#cheat img{height:260px;border-radius:8px;background:#111}
#expreview{position:fixed;top:50%;right:305px;transform:translateY(-50%);z-index:7;display:none;pointer-events:none;background:var(--panel);border:1px solid #444;border-radius:12px;padding:10px;text-align:center}
#expreview img{max-height:72vh;max-width:44vw;border-radius:8px}
#expreview div{color:var(--ink2);font-size:13px;padding-top:6px}
#exstrip{position:fixed;inset:3%;background:var(--panel);border:1px solid #444;border-radius:14px;z-index:8;display:none;padding:18px;gap:14px;overflow-x:auto;align-items:center;justify-content:center}
#exstrip figure{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:0}
#exstrip img{max-height:78vh;max-width:100%;object-fit:contain;border-radius:10px;background:#111}
#exstrip figcaption{font-size:15px;font-weight:600}
.sep{border-top:1px solid #3a3a42;margin:4px 0}
#meta{font-size:12.5px;color:var(--ink2)}
#hint{font-size:12px;color:var(--ink2);margin-top:auto;line-height:1.7}
#cheat{position:fixed;inset:8% 12%;background:var(--panel);border:1px solid #444;border-radius:12px;padding:24px 28px;display:none;z-index:9;overflow:auto;font-size:14px}
#cheat h3{margin-bottom:10px}#cheat td{padding:4px 10px 4px 0;vertical-align:top}#cheat td:first-child{color:var(--acc);font-weight:600;white-space:nowrap}
#toast{position:fixed;top:14px;right:14px;background:#2b2b33;border:1px solid #444;padding:8px 14px;border-radius:8px;font-size:13px;opacity:0;transition:opacity .25s;z-index:10}
#progress{height:4px;background:#2b2b33}#progfill{height:100%;background:var(--acc);width:0}
#newwat{position:absolute;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,.72);z-index:5;pointer-events:none}
#newwat div{background:var(--acc);color:#fff;padding:22px 40px;border-radius:14px;font-size:24px;font-weight:700}
#trashpick{position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,.6);z-index:8}
#trashpick .tp{background:var(--panel);border:1px solid #444;border-radius:12px;padding:20px 24px;display:flex;flex-direction:column;gap:9px;width:430px}
#trashpick button{padding:10px 14px;border:1px solid #3a3a42;border-radius:9px;background:#2b2b33;color:var(--ink);font-size:14px;cursor:pointer;text-align:left}
#trashpick button:hover{border-color:var(--warn)}
#trashpick b{color:var(--warn);margin-right:8px}
#trashpick small{color:var(--ink2)}
</style></head><body>
<div id="watbar"><span id="watname">…</span><small id="watpos"></small></div>
<div id="progress"><div id="progfill"></div></div>
<div id="tierbar"><span id="tiername"></span><span id="counts"></span></div>
<div id="main">
  <div id="imgwrap"><img id="photo"><div id="boxrect"></div><div id="dragrect"></div><div id="pendchip"></div><div id="peek"></div><div id="newwat"><div id="newwatname"></div></div></div>
  <div id="side">
    <button class="lab" data-l="marawichai"><span class="bl"><img src="/ex/marawichai.jpg">marawichai</span> <kbd>1</kbd></button>
    <button class="lab" data-l="samathi"><span class="bl"><img src="/ex/samathi.jpg">samathi</span> <kbd>2</kbd></button>
    <button class="lab" data-l="nakprok"><span class="bl"><img src="/ex/nakprok.jpg">nakprok</span> <kbd>3</kbd></button>
    <button class="lab" data-l="prathanphon"><span class="bl"><img src="/ex/prathanphon.jpg">prathanphon</span> <kbd>4</kbd></button>
    <button class="lab" data-l="saiyat"><span class="bl"><img src="/ex/saiyat.jpg">saiyat</span> <kbd>5</kbd></button>
    <div class="sep"></div>
    <button class="lab" data-l="other">other (Buddha, not our 5) <kbd>O</kbd></button>
    <button class="lab" data-l="trash">trash <kbd>T</kbd></button>
    <button class="lab" data-l="later">later <kbd>L</kbd></button>
    <div class="sep"></div>
    <div id="meta"></div>
    <div id="hint"><b>drag on photo</b> = box the statue (optional — the boxer does these)<br>←/→ move · <b>A</b> peek AI · <b>Z</b> undo · <b>G</b> go to row<br><b>E</b> big examples · <b>H</b> cheat-sheet · <b>N</b> next unlabeled<br>hover a pang button = large preview<br>labels auto-save & auto-advance</div>
  </div>
</div>
<div id="cheat"><h3>Cheat sheet — book plates (Fine Arts Dept) + the ONE cue per class</h3><table>
<tr><td>marawichai</td><td><img src="/ex/marawichai.jpg"></td><td>seated · right hand over right KNEE, palm/fingers DOWN to the earth</td></tr>
<tr><td>samathi</td><td><img src="/ex/samathi.jpg"></td><td>seated · BOTH hands stacked palm-UP in the lap, nothing on the knee</td></tr>
<tr><td>nakprok</td><td><img src="/ex/nakprok.jpg"></td><td>seated · serpent hood above the head (naga beats hands!) — must be a THAI statue</td></tr>
<tr><td>prathanphon</td><td><img src="/ex/prathanphon.jpg"></td><td>seated: right hand palm-UP on knee · standing: arm lowered, palm OUT (raised palm = abhaya = trash). Book plate = seated form (ลักษณะที่ ๒) — palm-up mirror of marawichai</td></tr>
<tr><td>saiyat</td><td><img src="/ex/saiyat.jpg"></td><td>reclining on the RIGHT side, head on pillow</td></tr>
<tr><td>other</td><td></td><td>a REAL Thai Buddha statue, but a different pang — abhaya (raised palm), walking, alms bowl, fasting, Palelai… photo is fine, pose just isn't one of our 5</td></tr>
<tr><td>trash</td><td></td><td>T then degree: <b>1</b> bad angle (pose not visible) · <b>2</b> bad quality (color/blur/light) · <b>3</b> literally trash (not a Thai Buddha statue: relief, amulet, sign, non-Thai, people)</td></tr>
<tr><td>later</td><td></td><td>you want another look — parks it in the Later queue</td></tr>
</table><p style="margin-top:12px;color:#a8a8a0">Palm DOWN = marawichai, palm UP = prathanphon — the #1 confuser. Press H to close.</p></div>
<div id="expreview"><img id="expimg"><div id="expname"></div></div>
<div id="exstrip">
  <figure><img src="/ex/marawichai.jpg"><figcaption>1 · marawichai — palm DOWN on knee</figcaption></figure>
  <figure><img src="/ex/samathi.jpg"><figcaption>2 · samathi — hands stacked in lap</figcaption></figure>
  <figure><img src="/ex/nakprok.jpg"><figcaption>3 · nakprok — naga hood</figcaption></figure>
  <figure><img src="/ex/prathanphon.jpg"><figcaption>4 · prathanphon — right palm UP on knee (vs marawichai's palm DOWN)</figcaption></figure>
  <figure><img src="/ex/saiyat.jpg"><figcaption>5 · saiyat — reclining right side</figcaption></figure>
</div>
<div id="trashpick"><div class="tp">
  <h3>🗑 why trash?</h3>
  <button data-d="1"><b>1</b> bad camera angle — pose not visible (back / crop / too far)</button>
  <button data-d="2"><b>2</b> bad quality — color / blur / lighting ruined</button>
  <button data-d="3"><b>3</b> literally trash — not a Thai Buddha statue at all</button>
  <small>Esc = cancel</small>
</div></div>
<div id="goto"><input id="gotoin" placeholder="go to row #"></div>
<div id="toast"></div>
<script>
let Q=[],S={},B={},i=0,lastWat=null;
let unsavedBox=null,drag=null;const touched=new Set();
const PANG=['marawichai','samathi','nakprok','prathanphon','saiyat'];
const BOXABLE=PANG.concat(['other']);
const PARAMS=new URLSearchParams(location.search);
let MODE=PARAMS.get('rows')?'rows':(PARAMS.get('mode')||'normal');
if(MODE==='needsbox')MODE='boxer';
const $=id=>document.getElementById(id);
function isDone(q){
  if(MODE==='rows')return touched.has(q.row);
  if(MODE==='boxer')return !!B[q.row];
  return !!S[q.row];}
async function boot(){
  const d=await (await fetch('/api/state')).json();
  Q=d.queue;S=d.labels;B=d.boxes;
  if(MODE==='rows'){const want=PARAMS.get('rows').split(',').map(Number);const by=new Map(Q.map(r=>[r.row,r]));Q=want.map(w=>by.get(w)).filter(Boolean);}
  else if(MODE==='boxer'){Q=Q.filter(r=>{const e=S[r.row];return e&&BOXABLE.includes(e.label)&&!B[r.row];});}
  if(!Q.length){$('watname').textContent=(MODE==='boxer'?'no photos waiting for boxes 🎉 — pull the latest human_labels.json or wait for more labels':'queue empty 🎉 (mode: '+MODE+')');$('watpos').textContent='';return;}
  i=Q.findIndex(r=>!isDone(r));if(i<0)i=0;
  show(true);
}
function counts(){
  if(MODE==='boxer')return Q.filter(r=>B[r.row]).length;
  if(MODE==='rows')return touched.size;
  return Object.keys(S).length;}
function show(first){
  const r=Q[i];if(!r)return;
  $('photo').src='/img/'+r.row;
  const nxt=Q[i+1];if(nxt){(new Image()).src='/img/'+nxt.row;}
  $('watname').textContent=r.group;
  const inWat=Q.filter(x=>x.group===r.group);
  $('watpos').textContent='photo '+(inWat.findIndex(x=>x.row===r.row)+1)+' / '+inWat.length+' from this temple · queue '+(i+1)+' / '+Q.length;
  $('tiername').textContent='tier: '+r.tierName;
  $('counts').textContent=counts()+' / '+Q.length+' labeled';
  $('progfill').style.width=(100*counts()/Q.length)+'%';
  $('meta').innerHTML='row '+r.row+'<br>'+(r.file||'');
  $('peek').style.display='none';
  unsavedBox=null;paintPend();paintBox();
  document.querySelectorAll('.lab').forEach(b=>b.classList.toggle('picked',S[r.row]&&S[r.row].label===b.dataset.l));
  if(!first&&r.group!==lastWat){$('newwatname').textContent='📍 '+r.group;$('newwat').style.display='flex';setTimeout(()=>$('newwat').style.display='none',900);}
  lastWat=r.group;
}
async function setLabel(l,degree){
  if(MODE==='boxer'){toast('boxer mode — labels are locked');return;}
  const r=Q[i];
  const entry={label:l,peeked:$('peek').style.display==='block'};
  if(degree)entry.degree=degree;
  S[r.row]=entry;touched.add(r.row);
  await fetch('/api/label',{method:'POST',body:JSON.stringify({row:r.row,label:l,degree:degree||null,peeked:entry.peeked})});
  toast(l+(degree?'·'+degree:'')+' ✓');
  let j=i+1;while(j<Q.length&&isDone(Q[j]))j++;
  if(j>=Q.length){toast('🎉 queue complete!');show();return;}
  i=j;show();
}
function imgMap(){const im=$('photo');const r=im.getBoundingClientRect();
  const s=Math.min(r.width/im.naturalWidth,r.height/im.naturalHeight)||1;
  const w=im.naturalWidth*s,h=im.naturalHeight*s;
  return{x:r.left+(r.width-w)/2,y:r.top+(r.height-h)/2,w,h,s};}
function paintBox(){const bx=$('boxrect');const r=Q[i];if(!r){bx.style.display='none';return;}
  const b=unsavedBox||(B[r.row]&&B[r.row].box);
  if(!b||!$('photo').naturalWidth){bx.style.display='none';return;}
  const m=imgMap(),wr=$('imgwrap').getBoundingClientRect();
  bx.style.display='block';
  bx.style.left=(m.x-wr.left+b[0]*m.s)+'px';bx.style.top=(m.y-wr.top+b[1]*m.s)+'px';
  bx.style.width=(b[2]*m.s)+'px';bx.style.height=(b[3]*m.s)+'px';}
function paintPend(){const p=$('pendchip');
  if(MODE==='boxer'&&Q[i]){const l=S[Q[i].row]?S[Q[i].row].label:'?';
    p.innerHTML=(PANG.includes(l)?'<img src="/ex/'+l+'.jpg" style="height:64px;border-radius:6px;vertical-align:middle;margin-right:10px">':'')+'box the <b>'+l+'</b> statue';
    p.style.display='block';}
  else p.style.display='none';}
$('photo').onload=paintBox;
window.addEventListener('resize',paintBox);
const IW=document.getElementById('imgwrap');
IW.addEventListener('mousedown',e=>{if(e.button!==0)return;const m=imgMap();
  if(e.clientX<m.x||e.clientX>m.x+m.w||e.clientY<m.y||e.clientY>m.y+m.h)return;
  drag={x0:e.clientX,y0:e.clientY};e.preventDefault();});
window.addEventListener('mousemove',e=>{if(!drag)return;const wr=IW.getBoundingClientRect(),d=$('dragrect');
  const x=Math.min(drag.x0,e.clientX),y=Math.min(drag.y0,e.clientY);
  d.style.display='block';d.style.left=(x-wr.left)+'px';d.style.top=(y-wr.top)+'px';
  d.style.width=Math.abs(e.clientX-drag.x0)+'px';d.style.height=Math.abs(e.clientY-drag.y0)+'px';});
window.addEventListener('mouseup',e=>{if(!drag)return;const m=imgMap();
  const x1=Math.max(m.x,Math.min(drag.x0,e.clientX)),y1=Math.max(m.y,Math.min(drag.y0,e.clientY));
  const x2=Math.min(m.x+m.w,Math.max(drag.x0,e.clientX)),y2=Math.min(m.y+m.h,Math.max(drag.y0,e.clientY));
  drag=null;$('dragrect').style.display='none';
  if(x2-x1<8||y2-y1<8)return;
  const nb=[Math.round((x1-m.x)/m.s),Math.round((y1-m.y)/m.s),Math.round((x2-x1)/m.s),Math.round((y2-y1)/m.s)];
  const r=Q[i];B[r.row]={box:nb,by:MODE==='boxer'?'boxer':'labeler'};unsavedBox=null;paintBox();
  fetch('/api/box',{method:'POST',body:JSON.stringify({row:r.row,box:nb,who:MODE==='boxer'?'boxer':'labeler'})});
  if(MODE==='boxer')boxUndo.push(i);
  toast('box ▣ saved');
  if(MODE==='boxer'){let j=i+1;while(j<Q.length&&isDone(Q[j]))j++;
    if(j>=Q.length){toast('🎉 all boxes done!');show();return;}
    i=j;show();}});
$('gotoin').addEventListener('keydown',e=>{
  if(e.key==='Enter'){const n=parseInt($('gotoin').value,10);const j=Q.findIndex(r=>r.row===n);
    $('goto').style.display='none';
    if(j<0){toast('row '+n+' not in this queue');return;}
    i=j;show();}
  else if(e.key==='Escape'){$('goto').style.display='none';}
  e.stopPropagation();});
function toast(m){const t=$('toast');t.textContent=m;t.style.opacity=1;clearTimeout(t._h);t._h=setTimeout(()=>t.style.opacity=0,900);}
let undoStack=[],boxUndo=[];
function openTrash(){$('trashpick').style.display='flex';}
function closeTrash(){$('trashpick').style.display='none';}
document.querySelectorAll('#trashpick button').forEach(b=>b.onclick=()=>{closeTrash();undoStack.push(i);setLabel('trash',+b.dataset.d);});
document.addEventListener('keydown',e=>{
  if(e.metaKey||e.ctrlKey)return;
  if(e.target.tagName==='INPUT')return;
  const k=e.key.toLowerCase();
  if($('trashpick').style.display==='flex'){
    if(k>='1'&&k<='3'){closeTrash();undoStack.push(i);setLabel('trash',+k);}
    else if(k==='escape'||k==='t'){closeTrash();}
    e.preventDefault();return;
  }
  if($('exstrip').style.display==='flex'){
    if(k==='e'||k==='escape'){$('exstrip').style.display='none';}
    e.preventDefault();return;
  }
  if(k>='1'&&k<='5'){undoStack.push(i);setLabel(['marawichai','samathi','nakprok','prathanphon','saiyat'][k-1]);}
  else if(k==='t'){if(MODE==='boxer'){toast('boxer mode — labels are locked');}else openTrash();}
  else if(k==='o'){undoStack.push(i);setLabel('other');}
  else if(k==='l'){undoStack.push(i);setLabel('later');}
  else if(k==='e'){$('exstrip').style.display='flex';}
  else if(k==='arrowright'){if(i<Q.length-1){i++;show();}}
  else if(k==='arrowleft'){if(i>0){i--;show();}}
  else if(k==='a'){const r=Q[i];$('peek').innerHTML='AI: <b>'+r.ai+'</b> ('+r.conf+') — '+r.note;$('peek').style.display='block';}
  else if(k==='z'){
    if(MODE==='boxer'){if(boxUndo.length){i=boxUndo.pop();const r=Q[i];delete B[r.row];fetch('/api/box',{method:'POST',body:JSON.stringify({row:r.row,box:null})});show();toast('box removed');}}
    else if(undoStack.length){i=undoStack.pop();const r=Q[i];delete S[r.row];touched.delete(r.row);fetch('/api/label',{method:'POST',body:JSON.stringify({row:r.row,label:null})});show();toast('undone');}}
  else if(k==='h'){const c=$('cheat');c.style.display=c.style.display==='block'?'none':'block';}
  else if(k==='n'){let j=Q.findIndex(r=>!isDone(r));if(j>=0){i=j;show();}}
  else if(k==='g'){$('goto').style.display='block';$('gotoin').value='';$('gotoin').focus();}
  else if(k==='escape'){unsavedBox=null;paintBox();}
});
document.querySelectorAll('.lab').forEach(b=>{
  b.onclick=()=>{
    if(b.dataset.l==='trash'){openTrash();return;}
    undoStack.push(i);setLabel(b.dataset.l);
  };
  if(b.querySelector('img')){
    b.onmouseenter=()=>{$('expimg').src='/ex/'+b.dataset.l+'.jpg';$('expname').textContent=b.dataset.l+' — book plate (hover to view, E for all 5)';$('expreview').style.display='block';};
    b.onmouseleave=()=>{$('expreview').style.display='none';};
  }
});
boot();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            q = [{"row": r["_row"], "group": r["group"], "tier": r["tier"],
                  "tierName": TIER_NAMES[r["tier"]], "ai": r["ai_pang"],
                  "conf": r["ai_confidence"], "note": r["ai_note"],
                  "file": r["file_name"][:60]} for r in ROWS]
            self._send(200, json.dumps({"queue": q, "labels": STATE, "boxes": BOXES}, ensure_ascii=False).encode())
        elif self.path.startswith("/ex/"):
            name = self.path[4:-4]
            if name in LABELS[:5] and self.path.endswith(".jpg"):
                try:
                    self._send(200, (EXAMPLES / f"{name}.jpg").read_bytes(), "image/jpeg")
                except Exception:
                    self._send(404, b"nope", "text/plain")
            else:
                self._send(404, b"nope", "text/plain")
        elif self.path.startswith("/img/"):
            try:
                row = int(self.path[5:])
                data = (RAW / f"{row:05d}.jpg").read_bytes()
                self._send(200, data, "image/jpeg")
            except Exception:
                self._send(404, b"nope", "text/plain")
        else:
            self._send(404, b"nope", "text/plain")

    def do_POST(self):
        if self.path == "/api/box":
            n = int(self.headers.get("Content-Length", 0))
            d = json.loads(self.rfile.read(n))
            key = str(d["row"])
            box = d.get("box")
            if box is None:
                BOXES.pop(key, None)
            else:
                ok = (isinstance(box, list) and len(box) == 4
                      and all(isinstance(v, (int, float)) and v >= 0 for v in box)
                      and box[2] > 0 and box[3] > 0)
                if not ok:
                    self._send(400, b'{"err":"bad box"}')
                    return
                from datetime import datetime
                BOXES[key] = {"box": [int(v) for v in box], "by": d.get("who") or "labeler",
                              "ts": datetime.now().isoformat(timespec="seconds")}
            _save(BOXOUT, BOXES)
            self._send(200, b'{"ok":true}')
            return
        if self.path == "/api/label":
            n = int(self.headers.get("Content-Length", 0))
            d = json.loads(self.rfile.read(n))
            key = str(d["row"])
            if d["label"] is None:
                STATE.pop(key, None)
            else:
                if d["label"] not in LABELS:
                    self._send(400, b'{"err":"bad label"}')
                    return
                from datetime import datetime
                entry = {"label": d["label"], "peeked": bool(d.get("peeked")),
                         "ts": datetime.now().isoformat(timespec="seconds")}
                if d["label"] == "trash":
                    deg = d.get("degree")
                    if deg not in (1, 2, 3):
                        self._send(400, b'{"err":"trash needs degree 1-3"}')
                        return
                    entry["degree"] = deg
                box = d.get("box")
                if box is not None:
                    ok = (isinstance(box, list) and len(box) == 4
                          and all(isinstance(v, (int, float)) and v >= 0 for v in box)
                          and box[2] > 0 and box[3] > 0)
                    if not ok:
                        self._send(400, b'{"err":"bad box"}')
                        return
                    entry["box"] = [int(v) for v in box]
                STATE[key] = entry
            save_state(STATE)
            self._send(200, b'{"ok":true}')
        else:
            self._send(404, b"nope", "text/plain")


if __name__ == "__main__":
    print(f"queue: {len(ROWS)} photos · already labeled: {len(STATE)}")
    print(f"open →  http://localhost:{PORT}")
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
