#!/usr/bin/env python3
"""
Detecta muletillas vocalizadas ("eh", "em", "ah") por análisis acústico.
Whisper las ignora en español — este script las encuentra por audio y las
inyecta en words.json para que el editor las muestre.

Uso:
  python3 scripts/detect_eh.py work/source/audio.wav work/source/words.json [--sensibilidad alta|media|baja]

Busca segmentos vocálicos cortos en los huecos entre palabras de Whisper:
pitch estable, duración corta, energía sobre el umbral, espectro de vocal.
"""
import sys, os, json, wave, argparse
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("audio")
ap.add_argument("words")
ap.add_argument("--sensibilidad", default="media", choices=["alta","media","baja"])
args = ap.parse_args()

AUDIO_PATH = args.audio
WORDS_PATH = args.words

PROFILES = {
    "alta":  {"min_dur": 0.08, "pitch_std_max": 15, "rms_floor": 0.008, "centroid_max": 1500, "autocorr_min": 0.35},
    "media": {"min_dur": 0.09, "pitch_std_max": 8,  "rms_floor": 0.012, "centroid_max": 1200, "autocorr_min": 0.40},
    "baja":  {"min_dur": 0.10, "pitch_std_max": 4,  "rms_floor": 0.020, "centroid_max": 1000, "autocorr_min": 0.50},
}
P = PROFILES[args.sensibilidad]

MAX_DUR   = 0.6
PITCH_LO  = 75
PITCH_HI  = 200
WIN_SEC   = 0.03
HOP_SEC   = 0.01

wf = wave.open(AUDIO_PATH, "rb")
sr = wf.getframerate()
audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
wf.close()

words = json.load(open(WORDS_PATH))

win = int(WIN_SEC * sr)
hop = int(HOP_SEC * sr)

def pitch_at(chunk):
    rms = np.sqrt(np.mean(chunk**2))
    if rms < P["rms_floor"]:
        return None
    corr = np.correlate(chunk, chunk, 'full')
    corr = corr[len(corr)//2:]
    corr = corr / (corr[0] + 1e-9)
    min_lag = sr // PITCH_HI
    max_lag = min(sr // PITCH_LO, len(corr) - 1)
    if max_lag <= min_lag:
        return None
    search = corr[min_lag:max_lag]
    peak_val = np.max(search)
    if peak_val < P["autocorr_min"]:
        return None
    return sr / (np.argmax(search) + min_lag)

def spectral_centroid(chunk):
    fft = np.abs(np.fft.rfft(chunk))[1:]
    freqs = np.fft.rfftfreq(len(chunk), 1/sr)[1:]
    return np.sum(freqs * fft) / (np.sum(fft) + 1e-10)

def find_voiced_segments(start_s, end_s):
    s0 = int(start_s * sr)
    e0 = int(end_s * sr)
    pitches_by_pos = []
    for p in range(s0, e0 - win, hop):
        f = pitch_at(audio[p:p+win])
        pitches_by_pos.append((p / sr, f))
    segments = []
    cur_start = None
    cur_pitches = []
    for t, f in pitches_by_pos:
        if f is not None:
            if cur_start is None:
                cur_start = t
            cur_pitches.append(f)
        else:
            if cur_start is not None:
                seg_end = t + WIN_SEC
                segments.append((cur_start, seg_end, cur_pitches[:]))
                cur_start = None
                cur_pitches = []
    if cur_start is not None:
        segments.append((cur_start, pitches_by_pos[-1][0] + WIN_SEC, cur_pitches[:]))
    return segments

gaps = []
for i in range(len(words) - 1):
    gs = words[i]['end']
    ge = words[i+1]['start']
    if ge - gs > P["min_dur"]:
        gaps.append((gs, ge, i))
first_start = words[0]['start'] if words else 0
if first_start > P["min_dur"]:
    gaps.insert(0, (0, first_start, -1))

detected = []
for gs, ge, after_idx in gaps:
    segs = find_voiced_segments(gs, ge)
    for seg_s, seg_e, pitches in segs:
        dur = seg_e - seg_s
        if dur < P["min_dur"] or dur > MAX_DUR:
            continue
        if len(pitches) < 2:
            continue
        pmean = np.mean(pitches)
        pstd = np.std(pitches)
        if pstd > P["pitch_std_max"]:
            continue
        if not (PITCH_LO <= pmean <= PITCH_HI):
            continue
        chunk = audio[int(seg_s*sr):int(seg_e*sr)]
        rms = np.sqrt(np.mean(chunk**2))
        if rms < P["rms_floor"]:
            continue
        sc = spectral_centroid(chunk)
        if sc > P["centroid_max"]:
            continue
        detected.append({
            "start": round(seg_s, 3),
            "end": round(seg_e, 3),
            "pitch": round(pmean, 1),
            "pitch_std": round(pstd, 1),
            "rms": round(rms, 4),
            "centroid": round(sc, 0),
            "after_word_idx": after_idx,
        })

detected.sort(key=lambda d: d["start"])
merged = []
for d in detected:
    if merged and d["start"] < merged[-1]["end"] + 0.05:
        if d["end"] > merged[-1]["end"]:
            merged[-1]["end"] = d["end"]
    else:
        merged.append(d)

print(f"Sensibilidad: {args.sensibilidad}")
print(f"Detectados: {len(merged)} muletillas vocalizadas ('eh')")
for d in merged:
    print(f"  {d['start']:7.3f} - {d['end']:7.3f}  ({d['end']-d['start']:.2f}s)  "
          f"pitch={d['pitch']:.0f}±{d['pitch_std']:.0f}Hz  centroid={d['centroid']:.0f}Hz  rms={d['rms']:.4f}")

new_words = []
wi = 0
for d in merged:
    while wi < len(words) and words[wi]['start'] < d['start']:
        new_words.append(words[wi])
        wi += 1
    new_words.append({
        "word": " eh",
        "start": d["start"],
        "end": d["end"],
        "score": 0.5,
        "_acoustic": True,
    })
while wi < len(words):
    new_words.append(words[wi])
    wi += 1

json.dump(new_words, open(WORDS_PATH, "w"), ensure_ascii=False, indent=1)
print(f"\nInyectados {len(merged)} 'eh' en {WORDS_PATH}")
print(f"Palabras total: {len(new_words)} (antes {len(words)})")
