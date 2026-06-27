#!/usr/bin/env python3
"""
Crea un proxy ligero (720p, keyframes densos) SOLO para editar fluido en el
navegador: el seek es casi instantáneo. El render final NO usa este proxy,
usa el video original a calidad completa.
"""
import subprocess, argparse

ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True)
ap.add_argument("--out",   required=True)
args = ap.parse_args()

cmd = ["ffmpeg", "-y", "-i", args.video,
       "-vf", "scale=-2:720", "-r", "30",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
       "-g", "6", "-keyint_min", "6", "-sc_threshold", "0",
       "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", args.out]
print("Creando proxy (keyframes densos para seek instantáneo)...")
subprocess.run(cmd, check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f"OK -> {args.out}")
