#!/usr/bin/env python3
"""
Corta DE VERDAD las muletillas del video con ffmpeg.
Lee el JSON exportado por el editor (rangos a eliminar) y produce un mp4 nuevo
sin esos trozos (recorta video + audio y los concatena).

Uso:
  python3 scripts/cut.py [fillers.json] [video_entrada] [video_salida] [crf]
Defaults:
  fillers.json  = ~/Downloads/fillers-manual-5min.json
  video_entrada = public/assets/video-5min.mp4
  video_salida  = out/video-sin-muletillas.mp4
  crf           = 18   (menor = más calidad; 14 ≈ casi sin pérdida, 0 = lossless)
"""
import sys, os, json, subprocess, shutil, tempfile

HOME = os.path.expanduser("~")
FILLERS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HOME, "Downloads", "fillers-manual-5min.json")
VIDEO   = sys.argv[2] if len(sys.argv) > 2 else "public/assets/video-5min.mp4"
OUT     = sys.argv[3] if len(sys.argv) > 3 else "out/video-sin-muletillas.mp4"
CRF     = sys.argv[4] if len(sys.argv) > 4 else "18"
PAD     = 0.02  # segundos extra recortados a cada lado para no dejar restos

def dur(path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                        "-of","default=nk=1:nw=1", path], capture_output=True, text=True)
    return float(r.stdout.strip())

if not os.path.exists(FILLERS):
    sys.exit(f"No encuentro el JSON exportado: {FILLERS}\n"
             f"Exporta primero desde el editor (botón 'Exportar cortes').")
if not os.path.exists(VIDEO):
    sys.exit(f"No encuentro el video: {VIDEO}")

data = json.load(open(FILLERS))
removed = sorted([[max(0,s-PAD), e+PAD] for s,e in data["fillers"]])
# fusionar solapados
merged=[]
for s,e in removed:
    if merged and s <= merged[-1][1]: merged[-1][1]=max(merged[-1][1],e)
    else: merged.append([s,e])

D = dur(VIDEO)
# segmentos a CONSERVAR = complemento de los eliminados
keep=[]; prev=0.0
for s,e in merged:
    if s>prev: keep.append((prev,min(s,D)))
    prev=max(prev,e)
if prev < D: keep.append((prev,D))
keep=[(s,e) for s,e in keep if e-s > 0.02]

print(f"Video: {VIDEO}  ({D:.1f}s)")
print(f"Eliminar: {len(merged)} trozos ({sum(e-s for s,e in merged):.1f}s)")
print(f"Conservar: {len(keep)} segmentos ({sum(e-s for s,e in keep):.1f}s)")

# construir filter_complex
parts=[]
for i,(s,e) in enumerate(keep):
    parts.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}];")
    parts.append(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS[a{i}];")
concat="".join(f"[v{i}][a{i}]" for i in range(len(keep)))
filt="".join(parts)+f"{concat}concat=n={len(keep)}:v=1:a=1[v][a]"

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

fd, script_path = tempfile.mkstemp(suffix=".filter.txt", prefix="cut_")
try:
    with os.fdopen(fd, "w") as f:
        f.write(filt)
    cmd=["ffmpeg","-y","-i",VIDEO,"-filter_complex_script",script_path,
         "-map","[v]","-map","[a]","-c:v","libx264","-preset","slow","-crf",str(CRF),
         "-pix_fmt","yuv420p","-c:a","aac","-b:a","256k",OUT]
    print(f"Renderizando con ffmpeg (CRF {CRF})...")
    r=subprocess.run(cmd)
finally:
    if os.path.exists(script_path):
        os.remove(script_path)

if r.returncode==0:
    print(f"\n✅ Listo -> {OUT}  ({sum(e-s for s,e in keep):.1f}s, sin muletillas)")
else:
    sys.exit("ffmpeg falló")
