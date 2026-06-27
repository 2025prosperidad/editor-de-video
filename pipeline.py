#!/usr/bin/env python3
"""
Editor de Muletillas — pipeline completo en un comando.

  python3 pipeline.py mi-video.mp4                 # automático (Whisper transcribe)
  python3 pipeline.py mi-video.mp4 --texto t.txt   # con transcripción verbatim (mejor)
  python3 pipeline.py mi-video.mp4 --modelo medium # modelo Whisper más preciso

Pasos: extrae audio -> palabras (alinea/transcribe) -> silencios -> proxy ->
genera el editor HTML -> abre el navegador con soporte de seek.

Después, en el editor: marca/ajusta muletillas y "Exportar cortes".
Para el video final:
  python3 scripts/cut.py work/<nombre>/cortes.json mi-video.mp4 salida.mp4
"""
import os, sys, subprocess, argparse, webbrowser, threading, time

PY = sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))
S = lambda n: os.path.join(HERE, "scripts", n)

def run(*cmd):
    print("·", " ".join(str(c) for c in cmd))
    subprocess.run([PY, *map(str, cmd)], check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--texto", default=None, help="transcripción verbatim (opcional, mejora la precisión)")
    ap.add_argument("--modelo", default="small", help="modelo Whisper: tiny|base|small|medium|large-v3")
    ap.add_argument("--puerto", type=int, default=8777)
    ap.add_argument("--no-serve", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.video):
        sys.exit(f"No existe el video: {args.video}")

    stem = os.path.splitext(os.path.basename(args.video))[0]
    work = os.path.join(HERE, "work", stem)
    os.makedirs(work, exist_ok=True)
    audio   = os.path.join(work, "audio.wav")
    words   = os.path.join(work, "words.json")
    silence = os.path.join(work, "silence.json")
    proxy   = os.path.join(work, "proxy.mp4")
    html    = os.path.join(work, "editor.html")

    print("\n[1/5] Extrayendo audio…");   run(S("extract_audio.py"), "--video", args.video, "--out", audio)
    print("\n[2/5] Palabras + timestamps…")
    align = [S("align.py"), "--audio", audio, "--out", words, "--modelo", args.modelo]
    if args.texto: align += ["--texto", args.texto]
    run(*align)
    print("\n[3/5] Detectando silencios…"); run(S("silence.py"), audio, silence)
    print("\n[4/5] Creando proxy…");        run(S("proxy.py"), "--video", args.video, "--out", proxy)
    print("\n[5/5] Generando editor…")
    run(S("build_ui.py"), "--words", words, "--silence", silence,
        "--video", "proxy.mp4", "--out", html)

    print(f"\n✅ Listo. Editor: {html}")
    if args.no_serve:
        print(f"   Sírvelo con: python3 scripts/serve.py {args.puerto} {work}")
        return
    url = f"http://localhost:{args.puerto}/editor.html"
    print(f"   Abriendo {url} …  (Ctrl+C para parar el servidor)")
    threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
    subprocess.run([PY, S("serve.py"), str(args.puerto), work])

if __name__ == "__main__":
    main()
