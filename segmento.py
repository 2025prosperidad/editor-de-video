#!/usr/bin/env python3
"""
Procesa UN segmento del video (p.ej. minutos 5–10) dejándolo listo en el editor,
con los "eh" bien sincronizados desde la transcripción de Descript.

Flujo estándar (todo automático):
  1. Recorta el segmento [inicio, fin] del video original.
  2. Extrae el audio.
  3. faster-whisper transcribe el trozo y localiza la porción correspondiente
     dentro de tu transcripción COMPLETA de Descript (match_descript.py).
  4. stable_whisper hace forced-alignment de esa porción -> "eh" con timestamp exacto.
  5. Detecta silencios, forma de onda y crea el proxy.
  6. Genera el editor HTML y levanta el servidor.

Uso:
  python3 segmento.py VIDEO.mp4 --desde 5:00 --hasta 10:00 \
      --descript transcripcion_completa.txt --nombre parte2

  # minutos en segundos también vale: --desde 300 --hasta 600
"""
import os, sys, subprocess, argparse, threading, time, json, shutil, webbrowser

PY = sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))
S = lambda n: os.path.join(HERE, "scripts", n)


def run(*cmd):
    print("·", " ".join(str(c) for c in cmd))
    subprocess.run([PY, *map(str, cmd)], check=True)


def parse_t(t, default=None):
    """'5:00' -> 300.0 ; '300' -> 300.0 ; '1:02:03' -> 3723.0 ; '' -> default"""
    t = str(t).strip()
    if not t:
        return default
    if ":" in t:
        parts = [float(p) for p in t.split(":")]
        sec = 0.0
        for p in parts:
            sec = sec * 60 + p
        return sec
    return float(t)


def get_duration(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nk=1:nw=1", video], capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--desde", default="", help="inicio del segmento (mm:ss o segundos); vacío = desde el inicio")
    ap.add_argument("--hasta", default="", help="fin del segmento (mm:ss o segundos); vacío = hasta el final")
    ap.add_argument("--descript", required=True, help="transcripción COMPLETA de Descript (.txt)")
    ap.add_argument("--nombre", default=None, help="nombre de la carpeta de trabajo")
    ap.add_argument("--modelo", default="small", help="modelo Whisper para alinear")
    ap.add_argument("--puerto", type=int, default=8777)
    ap.add_argument("--no-serve", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.video):
        sys.exit(f"No existe el video: {args.video}")
    if not os.path.exists(args.descript):
        sys.exit(f"No existe la transcripción: {args.descript}")

    dur = get_duration(args.video)
    t0 = parse_t(args.desde, default=0.0)
    t1 = parse_t(args.hasta, default=dur)
    name = args.nombre or f"seg_{int(t0)}_{int(t1)}"
    work = os.path.join(HERE, "work", name)
    os.makedirs(work, exist_ok=True)

    seg_video = os.path.join(work, "source.mp4")
    audio   = os.path.join(work, "audio.wav")
    texto   = os.path.join(work, "texto_segmento.txt")
    words   = os.path.join(work, "words.json")
    silence = os.path.join(work, "silence.json")
    peaks   = os.path.join(work, "peaks.json")
    proxy   = os.path.join(work, "proxy.mp4")
    html    = os.path.join(work, "editor.html")

    # ruta del video original (recortado) -> la usa el botón "Renderizar"
    json.dump({"video": os.path.abspath(seg_video)}, open(os.path.join(work, "source.json"), "w"))

    is_full = (t0 <= 0.1 and t1 >= dur - 0.1)
    if is_full:
        print(f"\n[1/7] Video completo ({dur:.0f}s), copiando…")
        shutil.copy(args.video, seg_video)
    else:
        print(f"\n[1/7] Recortando segmento {t0:.0f}s–{t1:.0f}s…")
        subprocess.run(["ffmpeg", "-y", "-ss", str(t0), "-to", str(t1), "-i", args.video,
                        "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                        "-c:a", "aac", "-b:a", "192k",
                        "-avoid_negative_ts", "make_zero", "-reset_timestamps", "1",
                        seg_video], check=True)

    print("\n[2/7] Extrayendo audio…")
    run(S("extract_audio.py"), "--video", seg_video, "--out", audio)

    print("\n[3/7] Localizando la porción de Descript que calza con este audio…")
    run(S("match_descript.py"), "--audio", audio, "--descript", args.descript, "--out", texto)

    print("\n[4/7] Alineando texto (forced alignment) — los 'eh' con timestamp exacto…")
    run(S("align.py"), "--audio", audio, "--out", words, "--texto", texto, "--modelo", args.modelo)

    print("\n[5/7] Detectando silencios…"); run(S("silence.py"), audio, silence)
    print("\n[6/7] Forma de onda + proxy…")
    run(S("peaks.py"), "--audio", audio, "--out", peaks)
    run(S("proxy.py"), "--video", seg_video, "--out", proxy)

    print("\n[7/7] Generando editor…")
    run(S("build_ui.py"), "--words", words, "--silence", silence, "--video", "proxy.mp4", "--out", html)

    print(f"\n✅ Listo. Carpeta: {work}")
    if args.no_serve:
        print(f"   Sírvelo con: python3 scripts/serve.py {args.puerto} {work}")
        return
    url = f"http://localhost:{args.puerto}/editor.html"
    print(f"   Abriendo {url} …  (Ctrl+C para parar el servidor)")
    threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
    subprocess.run([PY, S("serve.py"), str(args.puerto), work])


if __name__ == "__main__":
    main()
