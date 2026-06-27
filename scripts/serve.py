#!/usr/bin/env python3
"""
Servidor estático con soporte de HTTP Range (206) — necesario para hacer
seek/saltos en el <video>. python -m http.server NO soporta Range.

Uso: python3 scripts/serve.py [puerto] [directorio]
"""
import http.server, socketserver, os, re, sys, json, subprocess, shutil

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
DIRECTORY = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIRECTORY, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    # ---- Renderizar el video final desde la interfaz (botón del editor) ----
    def do_POST(self):
        if self.path.rstrip("/") != "/render":
            self.send_error(404); return
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            fillers = body.get("fillers", [])
            crf = str(body.get("crf", 18))
            srcfile = os.path.join(DIRECTORY, "source.json")
            if not os.path.exists(srcfile):
                raise RuntimeError("No hay source.json (ruta del video original) en la carpeta de trabajo.")
            video = json.load(open(srcfile))["video"]
            if not os.path.exists(video):
                raise RuntimeError(f"No encuentro el video original: {video}")
            cuts_path = os.path.join(DIRECTORY, "cortes.json")
            json.dump({"fillers": fillers}, open(cuts_path, "w"))
            # destino: nombre simple -> carpeta del proyecto; ruta/absoluta -> tal cual
            out = (body.get("out") or "").strip() or "final.mp4"
            if os.path.isabs(out):
                target = out
            elif os.sep in out or "/" in out:
                target = os.path.abspath(os.path.expanduser(out))
            else:
                target = os.path.join(DIRECTORY, out)
            if not target.lower().endswith((".mp4", ".mov", ".mkv")):
                target += ".mp4"
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            r = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "cut.py"), cuts_path, video, target, crf],
                capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(r.stderr[-500:] or "ffmpeg falló")
            # para poder previsualizar/descargar desde el navegador necesita estar dentro de DIRECTORY
            absdir = os.path.abspath(DIRECTORY)
            if os.path.commonpath([os.path.abspath(target), absdir]) == absdir:
                served = os.path.relpath(target, DIRECTORY)
            else:
                shutil.copy(target, os.path.join(DIRECTORY, "final.mp4"))
                served = "final.mp4"
            self._json({"ok": True, "file": served, "path": os.path.abspath(target), "crf": crf})
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, code=500)

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        size = os.fstat(f.fileno()).st_size
        ctype = self.guess_type(path)
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            start = int(m.group(1)) if m and m.group(1) else 0
            end = int(m.group(2)) if m and m.group(2) else size - 1
            end = min(end, size - 1)
            if start > end:
                self.send_error(416)
                f.close()
                return None
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            f.seek(start)
            self._range = end - start + 1
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
                    if not chunk:
                        break
                    outputfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


with Server(("", PORT), RangeHandler) as httpd:
    print(f"Sirviendo {DIRECTORY} en http://localhost:{PORT}  (con soporte Range)")
    httpd.serve_forever()
