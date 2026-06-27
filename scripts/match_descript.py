#!/usr/bin/env python3
"""
Encuentra automáticamente la porción de la transcripción de Descript que
corresponde a un segmento de audio, para poder hacer forced-alignment limpio.

El problema: la alineación forzada (stable_whisper.align) asume que el texto
empieza donde empieza el audio. Si pasas la transcripción del video COMPLETO
pero el audio es solo un trozo (p.ej. minutos 5–10), todo se desincroniza.

Solución: este script transcribe el audio con faster-whisper (rápido, buen
timing) para saber QUÉ se dice en ese trozo, luego localiza ese texto dentro
de la transcripción verbatim de Descript (que SÍ tiene los "eh") y recorta la
porción exacta. Esa porción se pasa luego a align.py.

Uso:
  python3 scripts/match_descript.py --audio work/seg/audio.wav \
      --descript transcripcion_completa.txt --out work/seg/texto_segmento.txt
"""
import sys, os, re, json, argparse, unicodedata

ap = argparse.ArgumentParser()
ap.add_argument("--audio", required=True)
ap.add_argument("--descript", required=True, help="transcripción verbatim COMPLETA de Descript")
ap.add_argument("--out", required=True, help="archivo de salida con la porción recortada")
ap.add_argument("--modelo", default="small", help="modelo faster-whisper (small basta para anclar)")
args = ap.parse_args()


def norm(s):
    """Normaliza para comparar: minúsculas, sin tildes, solo letras/números."""
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower())
                if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", s)


# 1) Transcribir el audio para saber qué se dice (sin "eh", pero con buen timing)
from faster_whisper import WhisperModel
print(f"Transcribiendo audio con faster-whisper ({args.modelo}) para anclar…")
model = WhisperModel(args.modelo, device="cpu", compute_type="int8")
segments, _ = model.transcribe(args.audio, language="es", vad_filter=True)
spoken = " ".join(seg.text for seg in segments).strip()
spoken_tokens = norm(spoken).split()
print(f"  audio dice ~{len(spoken_tokens)} palabras")
print(f"  inicio: \"{' '.join(spoken_tokens[:8])}…\"")
print(f"  final:  \"…{' '.join(spoken_tokens[-8:])}\"")

# 2) Tokenizar la transcripción de Descript conservando offsets de caracteres
descript_raw = open(args.descript, encoding="utf-8").read()
# lista de (token_normalizado, char_inicio, char_fin) sobre el texto ORIGINAL
desc_tokens = []
for m in re.finditer(r"\S+", descript_raw):
    nt = norm(m.group())
    nt = nt.strip()
    if nt:
        desc_tokens.append((nt.split()[0] if " " in nt else nt, m.start(), m.end()))
desc_norm_words = [t[0] for t in desc_tokens]


def best_match_index(needle_words, haystack_words):
    """Ventana deslizante: devuelve el índice de inicio en haystack que más
    solapa con needle (cuenta de palabras coincidentes en orden aproximado)."""
    n = len(needle_words)
    best_score, best_i = -1, 0
    needle_set_order = needle_words
    for i in range(0, max(1, len(haystack_words) - n + 1)):
        window = haystack_words[i:i + n]
        score = sum(1 for a, b in zip(needle_set_order, window) if a == b)
        if score > best_score:
            best_score, best_i = score, i
    return best_i, best_score


# 3) Anclar inicio y fin usando los primeros/últimos N tokens del audio
N = min(12, len(spoken_tokens) // 2 or 1)
start_needle = spoken_tokens[:N]
end_needle = spoken_tokens[-N:]

start_i, s_score = best_match_index(start_needle, desc_norm_words)
# buscar el fin SOLO después del inicio
end_offset = start_i
end_rel, e_score = best_match_index(end_needle, desc_norm_words[end_offset:])
end_i = end_offset + end_rel + len(end_needle)
end_i = min(end_i, len(desc_tokens))

print(f"  ancla inicio: token {start_i} (score {s_score}/{N})")
print(f"  ancla fin:    token {end_i} (score {e_score}/{N})")

char_start = desc_tokens[start_i][1]
char_end = desc_tokens[min(end_i, len(desc_tokens)) - 1][2]
portion = descript_raw[char_start:char_end].strip()

ehs = len(re.findall(r"\b[Ee]h+\b", portion))
print(f"\nPorción recortada: {len(portion.split())} palabras, {ehs} 'eh'")
print(f"  INICIO: {portion[:120]}…")
print(f"  FINAL:  …{portion[-120:]}")

open(args.out, "w", encoding="utf-8").write(portion)
print(f"\nOK -> {args.out}")
