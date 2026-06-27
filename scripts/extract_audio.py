#!/usr/bin/env python3
"""Extrae el audio del video a WAV 16kHz mono (lo que necesita Whisper)."""
import subprocess, argparse

ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True)
ap.add_argument("--out",   required=True)
args = ap.parse_args()

cmd = ["ffmpeg", "-y", "-i", args.video,
       "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", args.out]
subprocess.run(cmd, check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f"OK -> {args.out}")
