#!/usr/bin/env python3
"""Offline, standard-library image cropper for Project Pang."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

HOST, PORT = "127.0.0.1", 8770
POSES = ("marawichai", "samathi", "nakprok", "prathanphon", "saiyat")
BATCH_RE = re.compile(r"^to-crop-batch(\d+)$")
ROOT = Path(__file__).resolve().parent
CROPS_FILE = ROOT / "crops.json"
SKIPPED_FILE = ROOT / "skipped.txt"
LOCK = threading.RLock()
HISTORY: list[str] = []


def load_crops() -> dict[str, list[int]]:
    try:
        value = json.loads(CROPS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def load_skipped() -> set[str]:
    try:
        return {line.strip() for line in SKIPPED_FILE.read_text(encoding="utf-8").splitlines() if line.strip()}
    except OSError:
        return set()


def atomic_json(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def scan() -> list[dict[str, str]]:
    items = []
    batches = []
    for folder in ROOT.iterdir():
        match = BATCH_RE.match(folder.name) if folder.is_dir() else None
        if match:
            batches.append((int(match.group(1)), folder))
    for number, folder in sorted(batches):
        for pose in POSES:
            pose_dir = folder / pose
            if not pose_dir.is_dir():
                continue
            for photo in sorted(pose_dir.iterdir(), key=lambda p: p.name.casefold()):
                if photo.is_file() and photo.suffix.lower() in {".jpg", ".jpeg"}:
                    key = f"batch{number}/{pose}/{photo.name}"
                    items.append({"key": key, "batch": f"batch{number}", "pose": pose,
                                  "name": photo.name, "url": "/image?path=" + urllib.parse.quote(key)})
    return items


def key_parts(key: str) -> tuple[int, str, str]:
    path = PurePosixPath(key)
    if len(path.parts) != 3 or path.is_absolute() or ".." in path.parts:
        raise ValueError("invalid path")
    batch, pose, name = path.parts
    match = re.fullmatch(r"batch(\d+)", batch)
    if not match or pose not in POSES or Path(name).name != name or Path(name).suffix.lower() not in {".jpg", ".jpeg"}:
        raise ValueError("invalid path")
    return int(match.group(1)), pose, name


def paths_for(key: str) -> tuple[Path, Path]:
    number, pose, name = key_parts(key)
    source = ROOT / f"to-crop-batch{number}" / pose / name
    output = ROOT / f"cropped-batch{number}" / pose / name
    if not source.is_file():
        raise FileNotFoundError(key)
    return source, output


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Project Pang Cropper</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif}*{box-sizing:border-box}body{margin:0;background:#111;color:#eee;height:100vh;overflow:hidden;display:grid;grid-template-rows:auto 1fr auto}
header{padding:10px 18px;background:#1b1b1b;display:grid;grid-template-columns:1fr auto;gap:5px 20px;align-items:center;border-bottom:1px solid #333}.pose{font-size:1.45rem;font-weight:700;text-transform:capitalize}.meta,.count{color:#aaa;font-size:.9rem}.count{text-align:right}.bar{grid-column:1/-1;height:3px;background:#333}.fill{height:100%;background:#5bc07b;transition:width .2s}
main{position:relative;min-height:0;display:flex;align-items:center;justify-content:center;padding:10px;user-select:none}.stage{position:relative;display:inline-block;line-height:0;max-width:100%;max-height:100%}img{display:block;max-width:100%;max-height:calc(100vh - 128px);object-fit:contain;-webkit-user-drag:none}.selection,.saved{position:absolute;pointer-events:none}.selection{border:2px dashed #fff;background:#ffffff18}.saved{border:2px solid #52d678;background:#52d67812}
footer{padding:9px;text-align:center;color:#aaa;background:#1b1b1b;border-top:1px solid #333;font-size:.85rem}kbd{background:#333;border:1px solid #555;border-radius:4px;padding:1px 5px;color:#eee}.empty{font-size:1.3rem;color:#aaa}.toast{position:fixed;left:50%;bottom:50px;transform:translateX(-50%);background:#eee;color:#111;padding:8px 14px;border-radius:6px;opacity:0;transition:opacity .15s;z-index:5}.toast.show{opacity:1}.busy{cursor:wait}
</style></head><body>
<header><div><div class="pose" id="pose">Cropper</div><div class="meta" id="meta"></div></div><div class="count" id="count"></div><div class="bar"><div class="fill" id="fill"></div></div></header>
<main id="main"><div class="stage" id="stage"><img id="photo" draggable="false"><div class="saved" id="saved" hidden></div><div class="selection" id="selection" hidden></div></div><div class="empty" id="empty" hidden></div></main>
<footer><kbd>←</kbd>/<kbd>→</kbd> navigate · drag to crop · <kbd>Z</kbd> undo · <kbd>S</kbd> skip · <kbd>Esc</kbd> cancel</footer><div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);let state={items:[],crops:{},skipped:[]},index=0,drag=null,busy=false;
function toast(s){$('toast').textContent=s;$('toast').classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>$('toast').classList.remove('show'),1300)}
async function api(url,opt){const r=await fetch(url,opt);const j=await r.json();if(!r.ok)throw Error(j.error||r.statusText);return j}
function completed(){return state.items.filter(x=>state.crops[x.key]||state.skipped.includes(x.key)).length}
function firstPending(){const i=state.items.findIndex(x=>!state.crops[x.key]&&!state.skipped.includes(x.key));return i<0?state.items.length:i}
function render(){cancel();const n=state.items.length,c=completed();$('count').textContent=`${c} / ${n}`;$('fill').style.width=(n?100*c/n:0)+'%';
 if(!n||index>=n){$('stage').hidden=true;$('empty').hidden=false;$('empty').textContent=n?'All photos are cropped or skipped.':'No input photos found. Unzip to-crop-batch1.zip beside crop_app.py.';$('pose').textContent=n?'Done':'Cropper';$('meta').textContent='';return}
 $('stage').hidden=false;$('empty').hidden=true;const it=state.items[index];$('pose').textContent=it.pose;$('meta').textContent=`${it.batch} · ${it.name}`;$('photo').src=it.url;$('photo').onload=()=>{showSaved();preload()};$('saved').hidden=true}
function preload(){if(index+1<state.items.length){const x=new Image();x.src=state.items[index+1].url}}
function imageBox(){const im=$('photo');return {w:im.clientWidth,h:im.clientHeight,nw:im.naturalWidth,nh:im.naturalHeight}}
function showSaved(){if(index>=state.items.length)return;const rect=state.crops[state.items[index].key],el=$('saved'),b=imageBox();if(!rect||!b.nw){el.hidden=true;return}const sx=b.w/b.nw,sy=b.h/b.nh;Object.assign(el.style,{left:rect[0]*sx+'px',top:rect[1]*sy+'px',width:rect[2]*sx+'px',height:rect[3]*sy+'px'});el.hidden=false}
function cancel(){drag=null;$('selection').hidden=true}
function point(e){const r=$('photo').getBoundingClientRect();return{x:Math.max(0,Math.min(r.width,e.clientX-r.left)),y:Math.max(0,Math.min(r.height,e.clientY-r.top))}}
$('photo').addEventListener('pointerdown',e=>{if(busy)return;e.preventDefault();$('photo').setPointerCapture(e.pointerId);drag={start:point(e),end:point(e)};$('selection').hidden=false;draw()});
$('photo').addEventListener('pointermove',e=>{if(drag){drag.end=point(e);draw()}});$('photo').addEventListener('pointerup',async e=>{if(!drag)return;drag.end=point(e);const d=drag;cancel();const x=Math.min(d.start.x,d.end.x),y=Math.min(d.start.y,d.end.y),w=Math.abs(d.end.x-d.start.x),h=Math.abs(d.end.y-d.start.y);if(w<8||h<8)return toast('Selection too small');await saveCrop(x,y,w,h)});
function draw(){const x=Math.min(drag.start.x,drag.end.x),y=Math.min(drag.start.y,drag.end.y);Object.assign($('selection').style,{left:x+'px',top:y+'px',width:Math.abs(drag.end.x-drag.start.x)+'px',height:Math.abs(drag.end.y-drag.start.y)+'px'})}
async function saveCrop(x,y,w,h){const it=state.items[index],im=$('photo'),b=imageBox(),sx=b.nw/b.w,sy=b.nh/b.h;const rect=[Math.round(x*sx),Math.round(y*sy),Math.round(w*sx),Math.round(h*sy)];rect[2]=Math.min(rect[2],b.nw-rect[0]);rect[3]=Math.min(rect[3],b.nh-rect[1]);
 const cv=document.createElement('canvas');cv.width=rect[2];cv.height=rect[3];cv.getContext('2d').drawImage(im,...rect,0,0,rect[2],rect[3]);busy=true;document.body.classList.add('busy');try{const blob=await new Promise((ok,no)=>cv.toBlob(x=>x?ok(x):no(Error('JPEG export failed')),'image/jpeg',.95));const q=new URLSearchParams({path:it.key,rect:rect.join(',')});await api('/api/save?'+q,{method:'POST',body:blob,headers:{'Content-Type':'image/jpeg'}});state.crops[it.key]=rect;state.skipped=state.skipped.filter(x=>x!==it.key);toast('Crop saved');index=firstPending();render()}catch(e){toast(e.message)}finally{busy=false;document.body.classList.remove('busy')}}
async function skip(){if(index>=state.items.length||busy)return;try{const key=state.items[index].key;await api('/api/skip?path='+encodeURIComponent(key),{method:'POST'});if(!state.skipped.includes(key))state.skipped.push(key);toast('Skipped');index=firstPending();render()}catch(e){toast(e.message)}}
async function undo(){if(busy)return;try{const j=await api('/api/undo',{method:'POST'});delete state.crops[j.path];const i=state.items.findIndex(x=>x.key===j.path);if(i>=0)index=i;toast('Last crop undone');render()}catch(e){toast(e.message)}}
addEventListener('keydown',e=>{if(e.key==='Escape')cancel();else if(e.key==='ArrowLeft'&&index>0){index--;render()}else if(e.key==='ArrowRight'&&index<state.items.length-1){index++;render()}else if(e.key.toLowerCase()==='s')skip();else if(e.key.toLowerCase()==='z')undo()});addEventListener('resize',showSaved);
api('/api/state').then(s=>{state=s;index=firstPending();render()}).catch(e=>{$('empty').hidden=false;$('empty').textContent=e.message});
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    server_version = "PangCropper/1.0"

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def json_response(self, value: object, status: int = 200) -> None:
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def fail(self, message: str, status: int = 400) -> None:
        self.json_response({"error": message}, status)

    def query(self) -> dict[str, str]:
        values = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        return {key: vals[0] for key, vals in values.items() if vals}

    def do_GET(self) -> None:
        route = urllib.parse.urlsplit(self.path).path
        if route == "/":
            data = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif route == "/api/state":
            items, crops, skipped = scan(), load_crops(), load_skipped()
            self.json_response({"items": items, "crops": crops, "skipped": sorted(skipped)})
        elif route == "/image":
            try:
                source, _ = paths_for(self.query().get("path", ""))
                data = source.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(source.name)[0] or "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (ValueError, FileNotFoundError, OSError):
                self.fail("image not found", 404)
        else:
            self.fail("not found", 404)

    def do_POST(self) -> None:
        route, query = urllib.parse.urlsplit(self.path).path, self.query()
        try:
            if route == "/api/save":
                key = query.get("path", "")
                _, output = paths_for(key)
                rect = [int(x) for x in query.get("rect", "").split(",")]
                if len(rect) != 4 or any(x < 0 for x in rect) or rect[2] < 1 or rect[3] < 1:
                    raise ValueError("invalid crop rectangle")
                length = int(self.headers.get("Content-Length", "0"))
                if length < 4 or length > 100_000_000:
                    raise ValueError("invalid image size")
                data = self.rfile.read(length)
                if not data.startswith(b"\xff\xd8"):
                    raise ValueError("body is not a JPEG")
                with LOCK:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    temp = output.with_suffix(output.suffix + ".tmp")
                    temp.write_bytes(data)
                    os.replace(temp, output)
                    crops = load_crops()
                    crops[key] = rect
                    atomic_json(CROPS_FILE, crops)
                    skipped = load_skipped()
                    if key in skipped:
                        skipped.remove(key)
                        SKIPPED_FILE.write_text("".join(x + "\n" for x in sorted(skipped)), encoding="utf-8")
                    HISTORY.append(key)
                self.json_response({"ok": True})
            elif route == "/api/skip":
                key = query.get("path", "")
                paths_for(key)
                with LOCK:
                    skipped = load_skipped()
                    skipped.add(key)
                    SKIPPED_FILE.write_text("".join(x + "\n" for x in sorted(skipped)), encoding="utf-8")
                self.json_response({"ok": True})
            elif route == "/api/undo":
                with LOCK:
                    crops = load_crops()
                    key = next((x for x in reversed(HISTORY) if x in crops), None)
                    if key is None and crops:
                        key = next(reversed(crops))
                    if key is None:
                        raise ValueError("nothing to undo")
                    _, output = paths_for(key)
                    output.unlink(missing_ok=True)
                    del crops[key]
                    atomic_json(CROPS_FILE, crops)
                    while key in HISTORY:
                        HISTORY.remove(key)
                self.json_response({"ok": True, "path": key})
            else:
                self.fail("not found", 404)
        except (ValueError, FileNotFoundError) as exc:
            self.fail(str(exc))
        except OSError as exc:
            self.fail(f"file operation failed: {exc}", 500)


def main() -> None:
    print(f"Project Pang cropper: http://{HOST}:{PORT}")
    print(f"Working directory: {ROOT}")
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
