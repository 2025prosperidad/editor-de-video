#!/usr/bin/env python3
"""
Detecta silencios en el audio con ffmpeg silencedetect y guarda los intervalos.
Se usan para "pegar" los cortes de muletillas a los silencios reales.

Uso: python3 scripts/gen-silence.py [audio] [salida] [umbral_dB] [min_dur]
"""
import sys, subprocess, re, json

AUDIO = sys.argv[1] if len(sys.argv) > 1 else "public/assets/audio-5min.wav"
OUT   = sys.argv[2] if len(sys.argv) > 2 else "public/silence-5min.json"
NOISE = sys.argv[3] if len(sys.argv) > 3 else "-30dB"
MINDUR= sys.argv[4] if len(sys.argv) > 4 else "0.10"

cmd = ["ffmpeg","-hide_banner","-i",AUDIO,"-af",
       f"silencedetect=noise={NOISE}:d={MINDUR}","-f","null","-"]
out = subprocess.run(cmd, capture_output=True, text=True).stderr

starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
ends   = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
sil = []
for i, s in enumerate(starts):
    e = ends[i] if i < len(ends) else s
    sil.append([round(s, 3), round(e, 3)])

json.dump(sil, open(OUT, "w"))
print(f"OK -> {OUT}")
print(f"  silencios detectados: {len(sil)}  (umbral {NOISE}, min {MINDUR}s)")
print(f"  primeros: {sil[:4]}")
