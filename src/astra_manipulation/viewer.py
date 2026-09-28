"""Local live viewer. Reads recorded observations; never feeds evaluation to policy."""
import argparse
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Astra · Robot control</title>
<style>body{background:#10141e;color:#edf2ff;font:16px system-ui;margin:32px auto;max-width:1100px;padding:0 20px}h1{font-size:28px}select{background:#202939;color:white;padding:10px;border:1px solid #45516b;border-radius:8px;min-width:300px}.pill{color:#73eac8}.grid{display:flex;gap:18px;flex-wrap:wrap}.camera{flex:1;min-width:300px;background:#1a2231;padding:12px;border-radius:12px}.camera img{width:100%;image-rendering:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1a2231;padding:16px;border-radius:10px;font-size:14px}.muted{color:#99aac4}#status{padding:14px 0}video{width:100%}</style></head>
<body><h1>Astra <span class="pill">/ live robot control</span></h1>
<p class="muted">Camera pixels + robot proprioception → GPT-6 Astra → numeric actuator commands</p>
<select id="runs"></select><label><input id="follow" type="checkbox" checked> Follow newest trial</label>
<div id="status">Connecting…</div><div class="grid" id="cameras"></div>
<h3>Task instruction</h3><p id="instruction"></p><h3>Latest Astra command</h3><pre id="action">Waiting for model…</pre>
<p class="muted">Simulation pauses during model inference. This page refreshes every 500 ms. Evaluator results below are never sent to Astra.</p>
<pre id="result">Trial in progress</pre><div id="replay"></div>
<script>
const runs=document.getElementById('runs');let rendered='', imageVersion='', replayRun='';
runs.onchange=()=>{document.getElementById('follow').checked=false;rendered='';};
async function tick(){try{
const names=await(await fetch('/api/runs')).json();let old=runs.value;
if(JSON.stringify(names)!==runs.dataset.names){runs.replaceChildren(...names.map(n=>{let o=document.createElement('option');o.value=n;o.textContent=n;return o}));runs.dataset.names=JSON.stringify(names);if(names.includes(old))runs.value=old;}
if(document.getElementById('follow').checked&&names.length)runs.value=names[0];
if(!runs.value)return;const selected=runs.value;
const s=await(await fetch('/api/state?run='+encodeURIComponent(selected))).json();
document.getElementById('status').textContent=s.status+' · decision '+s.call+' · simulation step '+s.step;
document.getElementById('instruction').textContent=s.instruction||'';
document.getElementById('action').textContent=s.response?JSON.stringify(s.response,null,2):'Astra is looking at these images…';
document.getElementById('result').textContent=s.result?JSON.stringify(s.result,null,2):'Trial in progress';
let key=selected+JSON.stringify(s.cameras.map(c=>c.name));
if(rendered!==key){document.getElementById('cameras').replaceChildren(...s.cameras.map(c=>{let d=document.createElement('div');d.className='camera';let p=document.createElement('p');p.textContent=c.name;let im=document.createElement('img');im.dataset.name=c.name;d.append(p,im);return d}));rendered=key;imageVersion='';}
if(imageVersion!==s.version){for(const c of s.cameras){const im=[...document.querySelectorAll('.camera img')].find(i=>i.dataset.name===c.name);im.src=c.url+'&v='+encodeURIComponent(s.version);}imageVersion=s.version;}
if(s.result&&replayRun!==selected){const v=document.createElement('video');v.controls=true;v.src='/file?path='+encodeURIComponent(selected+'/rollout.mp4');document.getElementById('replay').replaceChildren(v);replayRun=selected;}
if(!s.result){document.getElementById('replay').replaceChildren();replayRun='';}
}catch(e){document.getElementById('status').textContent='Waiting for observations: '+e.message;}finally{setTimeout(tick,500)}}tick();
</script></body></html>"""


def serve(root, host="127.0.0.1", port=8765):
    root = Path(root).resolve()

    def read(path):
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            kind = "application/json"
            try:
                if parsed.path == "/":
                    body, kind = HTML.encode(), "text/html; charset=utf-8"
                elif parsed.path == "/api/runs":
                    paths = sorted((p for p in root.iterdir() if p.is_dir() and (p / "config.json").exists()),
                                   key=lambda p: (p / "config.json").stat().st_mtime, reverse=True)
                    body = json.dumps([p.name for p in paths]).encode()
                elif parsed.path in {"/api/state", "/file"}:
                    relative = query.get("run" if parsed.path == "/api/state" else "path", [""])[0]
                    path = (root / relative).resolve()
                    if not path.is_relative_to(root) or path == root:
                        raise ValueError("Invalid path")
                    if parsed.path == "/file":
                        kind = {".png": "image/png", ".jpg": "image/jpeg", ".mp4": "video/mp4"}.get(path.suffix)
                        if kind is None:
                            raise ValueError("Not a visualization")
                        body = path.read_bytes()
                    else:
                        config = read(path / "config.json") or {}
                        result = read(path / "result.json")
                        calls = sorted(path.glob("call_*"))
                        current = calls[-1] if calls else None
                        observation = read(current / "input.json") if current else None
                        response = read(current / "response.json") if current else None
                        if response is None and len(calls) > 1:
                            response = read(calls[-2] / "response.json")
                        live = read(path / "live.json")
                        pictures = sorted(current.glob("*.png")) if current else []
                        if live and (path / "live.png").exists():
                            pictures = [path / "live.png"]
                        body = json.dumps({"status": result["status"] if result else (live or {}).get("phase", "Astra deciding"),
                            "instruction": config.get("instruction"), "call": len(calls),
                            "step": (live or {}).get("step", (observation or {}).get("observation", {}).get("step_index", 0)),
                            "response": response, "result": result,
                            "version": str(max((p.stat().st_mtime_ns for p in pictures), default=0)),
                            "cameras": [{"name": p.stem, "url": "/file?path=" + quote(str(p.relative_to(root)), safe="/")} for p in pictures]}).encode()
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (OSError, ValueError):
                self.send_error(404)

    print(f"Live viewer: http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", default="runs")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.runs, args.host, args.port)


if __name__ == "__main__":
    main()
