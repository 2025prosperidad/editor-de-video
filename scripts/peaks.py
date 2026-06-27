#!/usr/bin/env python3
"""
Genera la forma de onda (peaks) del audio para dibujarla en el editor.
Salida: {"pps": picos_por_segundo, "peaks": [0..1, ...]}
"""
import subprocess, json, argparse

ap = argparse.ArgumentParser()
ap.add_argument("--audio", required=True)
ap.add_argument("--out",   required=True)
ap.add_argument("--pps", type=int, default=100, help="picos por segundo")
args = ap.parse_args()

SR = 8000
raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", args.audio, "-ac", "1", "-ar", str(SR),
     "-f", "s16le", "-"], capture_output=True).stdout

try:
    import numpy as np
    data = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    bucket = SR // args.pps
    n = len(data) // bucket
    arr = data[:n * bucket].reshape(n, bucket)
    peaks = (abs(arr).max(axis=1)).round(3).tolist()
except ImportError:
    import struct
    data = struct.unpack("<%dh" % (len(raw) // 2), raw)
    bucket = SR // args.pps
    peaks = []
    for i in range(len(data) // bucket):
        seg = data[i * bucket:(i + 1) * bucket]
        peaks.append(round(max(abs(x) for x in seg) / 32768.0, 3))

json.dump({"pps": args.pps, "peaks": peaks}, open(args.out, "w"))
print(f"OK -> {args.out}  ({len(peaks)} picos, {args.pps}/s)")
