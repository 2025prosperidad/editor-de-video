#!/usr/bin/env python3
"""
Panel web del Editor de Muletillas — todo sin línea de comando.

Levanta un servidor que sirve la raíz del proyecto y muestra un dashboard donde:
  • Eliges el video y el rango (desde/hasta)
  • Pegas la transcripción de Descript (una vez por video; se recuerda)
  • Procesa el segmento solo (recorte → audio → match → alineación → editor)
  • Lista los segmentos ya hechos: Abrir editor / Borrar

Uso:
  python3 scripts/panel.py [puerto]
  -> abre http://localhost:8777/
"""
import http.server, socketserver, os, re, sys, json, subprocess, shutil, threading, uuid, time, urllib.parse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)          # raíz del proyecto
WORK = os.path.join(ROOT, "work")
PY = sys.executable

os.makedirs(WORK, exist_ok=True)

# jobs en curso: id -> {status, step, total, log[], work, error, url}
JOBS = {}


def list_segments():
    out = []
    if not os.path.isdir(WORK):
        return out
    for name in sorted(os.listdir(WORK)):
        d = os.path.join(WORK, name)
        if not os.path.isdir(d):
            continue
        has_editor = os.path.exists(os.path.join(d, "editor.html"))
        meta = {}
        mp = os.path.join(d, "meta.json")
        if os.path.exists(mp):
            try: meta = json.load(open(mp))
            except Exception: pass
        out.append({
            "name": name,
            "listo": has_editor,
            "desde": meta.get("desde"), "hasta": meta.get("hasta"),
            "video": meta.get("video"),
            "final": os.path.exists(os.path.join(d, "final.mp4")),
        })
    return out


def run_job(job_id, video, desde, hasta, nombre, descript_text, modelo):
    job = JOBS[job_id]
    work = os.path.join(WORK, nombre)
    os.makedirs(work, exist_ok=True)
    job["work"] = nombre
    # guardar transcripción + metadatos
    desc_path = os.path.join(work, "descript_full.txt")
    open(desc_path, "w", encoding="utf-8").write(descript_text)
    json.dump({"video": video, "desde": desde, "hasta": hasta},
              open(os.path.join(work, "meta.json"), "w"))
    cmd = [PY, os.path.join(ROOT, "segmento.py"), video,
           "--desde", str(desde), "--hasta", str(hasta),
           "--descript", desc_path, "--nombre", nombre,
           "--modelo", modelo, "--no-serve"]
    job["status"] = "procesando"
    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1, env=env)
        for line in p.stdout:
            line = line.rstrip()
            if not line:
                continue
            job["log"].append(line)
            job["log"] = job["log"][-60:]
            m = re.search(r"\[(\d+)/(\d+)\]", line)
            if m:
                job["step"] = int(m.group(1))
                job["total"] = int(m.group(2))
                job["stepmsg"] = line.split("]", 1)[-1].strip()
        p.wait()
        if p.returncode == 0 and os.path.exists(os.path.join(work, "editor.html")):
            job["status"] = "listo"
            job["url"] = f"/work/{nombre}/editor.html"
        else:
            job["status"] = "error"
            job["error"] = "\n".join(job["log"][-8:]) or "Falló el procesamiento"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass

    # ---------------- POST ----------------
    def do_POST(self):
        path = self.path.rstrip("/")
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}
        if path == "/api/procesar":
            return self.api_procesar(body)
        if path == "/api/borrar":
            return self.api_borrar(body)
        if path == "/render":
            return self.api_render(body)
        self.send_error(404)

    def api_procesar(self, body):
        try:
            video = (body.get("video") or "").strip()
            video = os.path.abspath(os.path.expanduser(video))
            if not os.path.exists(video):
                raise RuntimeError(f"No encuentro el video: {video}")
            desde = (body.get("desde") or "").strip()
            hasta = (body.get("hasta") or "").strip()
            nombre = re.sub(r"[^A-Za-z0-9_-]", "_", (body.get("nombre") or "").strip())
            if not nombre:
                raise RuntimeError("Falta el nombre del segmento.")
            descript = body.get("descript") or ""
            if len(descript.split()) < 20:
                raise RuntimeError("Pega la transcripción de Descript (texto muy corto).")
            modelo = body.get("modelo") or "small"
            job_id = uuid.uuid4().hex[:8]
            JOBS[job_id] = {"status": "iniciando", "step": 0, "total": 7,
                            "stepmsg": "", "log": [], "work": nombre,
                            "error": None, "url": None}
            threading.Thread(target=run_job, daemon=True,
                             args=(job_id, video, desde, hasta, nombre, descript, modelo)).start()
            self._json({"ok": True, "job": job_id})
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 400)

    def api_borrar(self, body):
        try:
            nombre = re.sub(r"[^A-Za-z0-9_-]", "_", (body.get("nombre") or "").strip())
            d = os.path.join(WORK, nombre)
            if nombre and os.path.isdir(d):
                shutil.rmtree(d)
                self._json({"ok": True})
            else:
                self._json({"ok": False, "error": "No existe"}, 404)
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)

    def api_render(self, body):
        # deducir la carpeta de trabajo desde el Referer: /work/<name>/editor.html
        try:
            ref = self.headers.get("Referer", "")
            m = re.search(r"/work/([^/]+)/editor\.html", ref)
            if not m:
                raise RuntimeError("No pude identificar el segmento (recarga el editor).")
            work = os.path.join(WORK, m.group(1))
            fillers = body.get("fillers", [])
            crf = str(body.get("crf", 18))
            video = json.load(open(os.path.join(work, "source.json")))["video"]
            if not os.path.exists(video):
                raise RuntimeError(f"No encuentro el video: {video}")
            cuts_path = os.path.join(work, "cortes.json")
            json.dump({"fillers": fillers}, open(cuts_path, "w"))
            out = (body.get("out") or "").strip() or "final.mp4"
            if os.path.isabs(out):
                target = out
            elif os.sep in out or "/" in out:
                target = os.path.abspath(os.path.expanduser(out))
            else:
                target = os.path.join(work, out)
            if not target.lower().endswith((".mp4", ".mov", ".mkv")):
                target += ".mp4"
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            r = subprocess.run([PY, os.path.join(SCRIPTS, "cut.py"), cuts_path, video, target, crf],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(r.stderr[-500:] or "ffmpeg falló")
            absdir = os.path.abspath(work)
            if os.path.commonpath([os.path.abspath(target), absdir]) == absdir:
                served = os.path.relpath(target, work)
            else:
                shutil.copy(target, os.path.join(work, "final.mp4"))
                served = "final.mp4"
            self._json({"ok": True, "file": served, "path": os.path.abspath(target), "crf": crf})
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)

    # ---------------- GET ----------------
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path == "" or path == "/panel" or self.path == "/":
            return self.serve_panel()
        # URLs viejas que ya no viven en la raíz -> mandar al panel
        if path in ("/editor.html", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if path == "/api/segmentos":
            return self._json({"ok": True, "segmentos": list_segments()})
        if path == "/api/elegir-video":
            return self.api_elegir_video()
        if path == "/api/estado":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            job_id = (q.get("job") or [""])[0]
            job = JOBS.get(job_id)
            if not job:
                return self._json({"ok": False, "error": "job desconocido"}, 404)
            return self._json({"ok": True, **{k: job[k] for k in
                              ("status", "step", "total", "stepmsg", "error", "url", "work")}})
        return super().do_GET()

    def api_elegir_video(self):
        try:
            r = subprocess.run(
                ["osascript", "-e",
                 'set f to choose file with prompt "Selecciona el video" '
                 'of type {"public.movie","public.mpeg-4","com.apple.quicktime-movie"}\n'
                 'POSIX path of f'],
                capture_output=True, text=True, timeout=120)
            path = r.stdout.strip()
            if r.returncode != 0 or not path:
                return self._json({"ok": False, "error": "No se seleccionó archivo"})
            return self._json({"ok": True, "path": path})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)

    def serve_panel(self):
        data = PANEL_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---- Range para que el <video> del editor pueda hacer seek ----
    def send_head(self):
        p = self.translate_path(self.path)
        if os.path.isdir(p):
            return super().send_head()
        try:
            f = open(p, "rb")
        except OSError:
            self.send_error(404, "File not found"); return None
        size = os.fstat(f.fileno()).st_size
        ctype = self.guess_type(p)
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            start = int(m.group(1)) if m and m.group(1) else 0
            end = int(m.group(2)) if m and m.group(2) else size - 1
            end = min(end, size - 1)
            if start > end:
                self.send_error(416); f.close(); return None
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            f.seek(start); self._range = end - start + 1
            return f
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_range", None)
        try:
            if remaining is None:
                super().copyfile(source, outputfile)
            else:
                while remaining > 0:
                    chunk = source.read(min(65536, remaining))
                    if not chunk: break
                    outputfile.write(chunk); remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


PANEL_HTML = r"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Editor de Muletillas — Panel</title>
<style>
  :root{--bg:#0e0e12;--panel:#16161d;--panel2:#1d1d27;--line:#2a2a36;--txt:#d7d7e0;
        --dim:#8b8b9a;--accent:#6366f1;--ok:#22c55e;--del:#ef4444;--amber:#f59e0b}
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:var(--bg);color:var(--txt);min-height:100vh;padding:28px}
  .wrap{max-width:880px;margin:0 auto}
  h1{font-size:22px;color:#fff;margin-bottom:4px}
  .sub{color:var(--dim);font-size:13px;margin-bottom:24px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
        padding:20px 22px;margin-bottom:20px}
  .card h2{font-size:15px;color:#fff;margin-bottom:16px;display:flex;align-items:center;gap:8px}
  label{display:block;font-size:12px;color:var(--dim);margin:12px 0 5px}
  input,textarea{width:100%;background:var(--panel2);border:1px solid var(--line);
        border-radius:8px;color:var(--txt);padding:10px 12px;font-size:14px;font-family:inherit}
  input:focus,textarea:focus{outline:none;border-color:var(--accent)}
  textarea{min-height:120px;resize:vertical;line-height:1.5}
  .row{display:flex;gap:14px}.row>div{flex:1}
  .btn{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:11px 18px;
       font-size:14px;font-weight:600;cursor:pointer;margin-top:16px}
  .btn:hover{filter:brightness(1.1)}.btn:disabled{opacity:.5;cursor:not-allowed}
  .btn.sm{padding:6px 12px;font-size:12px;margin:0}
  .btn.ghost{background:transparent;border:1px solid var(--line);color:var(--txt)}
  .btn.danger{background:transparent;border:1px solid var(--del);color:var(--del)}
  .seg{display:flex;align-items:center;gap:12px;padding:12px 14px;background:var(--panel2);
       border:1px solid var(--line);border-radius:8px;margin-bottom:10px}
  .seg .nm{font-weight:600;color:#fff}.seg .meta{color:var(--dim);font-size:12px}
  .seg .sp{flex:1}
  .badge{font-size:11px;padding:2px 8px;border-radius:20px;background:#2a2a36;color:var(--dim)}
  .badge.ok{background:rgba(34,197,94,.15);color:var(--ok)}
  .hint{font-size:11px;color:var(--dim);margin-top:4px}
  #prog{margin-top:16px;display:none}
  .bar{height:8px;background:var(--panel2);border-radius:6px;overflow:hidden;margin-top:8px}
  .bar>i{display:block;height:100%;background:var(--accent);width:0;transition:width .3s}
  .pmsg{font-size:13px;color:var(--txt);margin-top:8px}
  .err{color:var(--del);font-size:13px;margin-top:10px;white-space:pre-wrap}
  .empty{color:var(--dim);font-size:13px;text-align:center;padding:20px}
</style></head><body><div class="wrap">
  <h1>🎬 Editor de Muletillas</h1>
  <div class="sub">Procesa un segmento del video sin tocar la terminal.</div>

  <div class="card">
    <h2>➕ Nuevo segmento</h2>
    <label>Video original (.mp4)</label>
    <div style="display:flex;gap:8px;align-items:center">
      <input id="video" placeholder="Selecciona el video..." style="flex:1" readonly>
      <button class="btn sm" id="pick" type="button">📂 Elegir...</button>
    </div>
    <div class="row">
      <div><label>Desde (mm:ss)</label><input id="desde" placeholder="0:00 (vacío = inicio)"></div>
      <div><label>Hasta (mm:ss)</label><input id="hasta" placeholder="(vacío = final)"></div>
      <div><label>Nombre</label><input id="nombre" placeholder="parte2"></div>
    </div>
    <label>Transcripción de Descript (todo el video)</label>
    <textarea id="descript" placeholder="Pega aquí el texto completo de Descript…"></textarea>
    <div class="hint">Se guarda en tu navegador: la próxima vez se rellena sola. Sirve para todo el video.</div>
    <button class="btn" id="go">⚙️ Procesar y abrir editor</button>
    <div id="prog">
      <div class="bar"><i id="barfill"></i></div>
      <div class="pmsg" id="pmsg">Iniciando…</div>
    </div>
    <div class="err" id="err"></div>
  </div>

  <div class="card">
    <h2>📂 Segmentos procesados</h2>
    <div id="list"><div class="empty">Cargando…</div></div>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
// botón para elegir video con diálogo nativo del sistema
$('pick').onclick=async()=>{
  $('pick').disabled=true;$('pick').textContent='Abriendo...';
  try{
    const r=await fetch('/api/elegir-video');const j=await r.json();
    if(j.ok&&j.path){$('video').value=j.path;localStorage.setItem('em_video',j.path);}
  }catch(e){}
  $('pick').disabled=false;$('pick').textContent='📂 Elegir...';
};
// recordar el texto de Descript y el video
for(const k of ['descript','video']){
  const v=localStorage.getItem('em_'+k); if(v)$(k).value=v;
  $(k).addEventListener('input',()=>localStorage.setItem('em_'+k,$(k).value));
}
async function loadSegs(){
  const r=await fetch('/api/segmentos');const j=await r.json();
  const L=$('list');
  if(!j.segmentos.length){L.innerHTML='<div class="empty">Aún no hay segmentos.</div>';return;}
  L.innerHTML='';
  for(const s of j.segmentos){
    const el=document.createElement('div');el.className='seg';
    const rng=s.desde&&s.hasta?`${s.desde}–${s.hasta}`:'';
    el.innerHTML=`<div><div class="nm">${s.name}</div><div class="meta">${rng}</div></div>
      <span class="sp"></span>
      ${s.final?'<span class="badge ok">render ✓</span>':''}
      ${s.listo?`<a class="btn sm" href="/work/${s.name}/editor.html" target="_blank">Abrir</a>`
               :'<span class="badge">incompleto</span>'}
      <button class="btn sm danger" data-del="${s.name}">🗑</button>`;
    L.appendChild(el);
  }
  L.querySelectorAll('[data-del]').forEach(b=>b.onclick=async()=>{
    if(!confirm('¿Borrar el segmento "'+b.dataset.del+'"? (no afecta el video original)'))return;
    await fetch('/api/borrar',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({nombre:b.dataset.del})});
    loadSegs();
  });
}
loadSegs();

$('go').onclick=async()=>{
  $('err').textContent='';
  const payload={video:$('video').value,desde:$('desde').value,hasta:$('hasta').value,
                 nombre:$('nombre').value,descript:$('descript').value};
  $('go').disabled=true;$('prog').style.display='block';$('barfill').style.width='5%';
  $('pmsg').textContent='Iniciando…';
  const r=await fetch('/api/procesar',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload)});
  const j=await r.json();
  if(!j.ok){$('err').textContent=j.error;$('go').disabled=false;$('prog').style.display='none';return;}
  poll(j.job);
};
async function poll(job){
  const r=await fetch('/api/estado?job='+job);const j=await r.json();
  if(j.ok){
    const pct=Math.max(5,Math.round((j.step/(j.total||7))*100));
    $('barfill').style.width=pct+'%';
    $('pmsg').textContent=`[${j.step}/${j.total}] ${j.stepmsg||j.status}`;
    if(j.status==='listo'){
      $('barfill').style.width='100%';$('pmsg').textContent='✅ Listo, abriendo editor…';
      $('go').disabled=false;loadSegs();
      window.open(j.url,'_blank');
      setTimeout(()=>{$('prog').style.display='none';},2000);
      return;
    }
    if(j.status==='error'){
      $('err').textContent=j.error||'Error';$('go').disabled=false;$('prog').style.display='none';return;
    }
  }
  setTimeout(()=>poll(job),1200);
}
</script></body></html>"""


if __name__ == "__main__":
    with Server(("", PORT), Handler) as httpd:
        print(f"Panel en http://localhost:{PORT}/   (Ctrl+C para parar)")
        httpd.serve_forever()
