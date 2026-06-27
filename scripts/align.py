#!/usr/bin/env python3
"""
Genera timestamps por palabra a partir del audio. Dos modos:

  CON texto (recomendado para muletillas):
    Forced alignment del texto verbatim (p.ej. de Descript) contra el audio.
    Resultado: TODOS los "eh"/muletillas quedan con timestamp exacto.

  SIN texto (automático):
    Whisper transcribe directo. No necesitas pasar nada, pero Whisper tiende
    a "limpiar" algunas muletillas (los silencios detectados las recuperan).

Uso:
  python3 scripts/align.py --audio audio.wav --out words.json [--texto t.txt] [--modelo small]
"""
import json, re, argparse

ap = argparse.ArgumentParser()
ap.add_argument("--audio", required=True)
ap.add_argument("--out",   required=True)
ap.add_argument("--texto", default=None, help="transcripción verbatim; si se omite, transcribe solo")
ap.add_argument("--modelo", default="small", help="tiny|base|small|medium|large-v3")
args = ap.parse_args()

import stable_whisper
print(f"Modelo: {args.modelo}  | audio: {args.audio}")
print("Cargando modelo (la primera vez se descarga)...")
model = stable_whisper.load_model(args.modelo)

if args.texto:
    text = open(args.texto, encoding="utf-8").read()
    print(f"Modo: ALINEACIÓN con texto ({len(text.split())} palabras)")
    result = model.align(args.audio, text, language="es")
else:
    print("Modo: TRANSCRIPCIÓN automática (sin texto)")
    result = model.transcribe(args.audio, language="es")

words = []
for seg in result.segments:
    for w in seg.words:
        token = w.word.strip()
        if token:
            words.append({"word": token,
                          "start": round(float(w.start), 3),
                          "end": round(float(w.end), 3)})

json.dump(words, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
ehs = sum(1 for w in words if re.sub(r"[^a-zñáéíóú]", "", w["word"].lower()) == "eh")
print(f"\nOK -> {args.out}")
print(f"  palabras: {len(words)}   |   'eh' con timestamp: {ehs}")
print(f"  duración: {words[-1]['end'] if words else 0:.1f}s")
