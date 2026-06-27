# Editor de Muletillas 🎬✂️

Sistema para **detectar y cortar muletillas** ("eh", "mmm", "o sea", repeticiones, pausas)
de un video, con un editor estilo **Descript** que corre en el navegador — pero **offline,
local y gratis**.

- Ves la transcripción palabra por palabra, sincronizada con el video (karaoke).
- Las muletillas vienen **detectadas y pre-marcadas**.
- Al reproducir, **salta los cortes de verdad** (empalme duro, sin oír el "eh").
- Los cortes se **pegan a los silencios reales** del audio → quedan limpios.
- Exportas y renderizas el **video final en calidad original (1080p)**.

---

## ¿Qué tecnologías usa?

| Pieza | Tecnología | Para qué |
|---|---|---|
| Transcripción / alineación | **Whisper** vía [`stable-ts`](https://github.com/jianfch/stable-ts) | timestamps por palabra (incluido cada "eh") |
| Detección de silencios | **ffmpeg** (`silencedetect`) | saber dónde cortar limpio |
| Proxy de edición | **ffmpeg** (720p, keyframes densos) | seek instantáneo en el navegador |
| Corte / render final | **ffmpeg** (`trim`+`concat`) | quitar muletillas, calidad original |
| Editor | **HTML + JS** (un solo archivo, sin frameworks) | revisar y ajustar cortes |
| Orquestación | **Python** | un comando para todo el pipeline |

## ¿Necesita IA?

**Sí, pero local y gratis.** La única "IA" es **Whisper** (modelo de voz a texto de OpenAI)
que corre **en tu máquina** vía `stable-ts`. **No** usa internet, **no** usa API keys, **no**
manda nada a la nube. Todo lo demás (silencios, cortes, render) es **ffmpeg**, sin IA.

## ¿Siempre debo pasarle la transcripción (de Descript)?

**No.** Hay dos modos:

1. **Automático (sin texto):** Whisper transcribe solo.
   ```bash
   python3 pipeline.py mi-video.mp4
   ```
   Cómodo, pero **Whisper "limpia" las muletillas vocalizadas**: no escribe los "eh/mmm".
   En una prueba real de 5 min, el modo automático capturó **0 "eh"**, mientras que con
   texto verbatim capturó **12**. En automático te apoyas en la **detección de silencios/
   pausas** para encontrarlas, pero no tendrás cada "eh" como palabra.

2. **Con transcripción verbatim (máxima precisión):** le pasas un `.txt` con el texto
   literal (p.ej. copiado de Descript, *con* los "eh"). Se hace **forced alignment** y
   **cada muletilla queda con timestamp exacto**.
   ```bash
   python3 pipeline.py mi-video.mp4 --texto transcripcion.txt
   ```

> Recomendación: para limpiar muletillas a fondo, el **modo verbatim** es el mejor. Si solo
> quieres una pasada rápida, el **automático** alcanza. También puedes subir el modelo con
> `--modelo medium` o `--modelo large-v3` para más precisión (más lento).

---

## Requisitos

- **Python 3.9+**
- **ffmpeg** (`brew install ffmpeg` en Mac)
- Dependencias Python:
  ```bash
  pip install -r requirements.txt
  ```
  (La primera vez, Whisper descarga el modelo automáticamente.)

## Pasos para replicar (de cero)

```bash
# 1. Instalar dependencias
brew install ffmpeg
pip install -r requirements.txt

# 2. Procesar tu video (genera el editor y lo abre en el navegador)
python3 pipeline.py mi-video.mp4
#   o, con transcripción verbatim:
python3 pipeline.py mi-video.mp4 --texto transcripcion.txt

# 3. En el editor (navegador):
#    - las muletillas (eh, mmm…) vienen PRE-MARCADAS en rojo
#    - doble-click en una palabra para marcar/desmarcar
#    - botones "Marcar para cortar" (léxicas / repeticiones / conectores) o ✂ en cada hallazgo
#    - dale play: verás que salta los cortes
#    - pausas: recórtalas en grupo por duración, todas, o ≥ X segundos
#    - elige Calidad, el nombre/ruta de salida y pulsa "🎬 Renderizar video"
#      (se guarda en work/<video>/ por defecto, o en la ruta absoluta que escribas;
#       el editor te muestra la ruta exacta donde quedó)

# (alternativa por terminal, sin el botón)
python3 scripts/cut.py ~/Downloads/fillers-manual-5min.json mi-video.mp4 salida.mp4 14
```

## Estructura

```
editor-muletillas/
├── pipeline.py            # orquestador: un comando para todo
├── scripts/
│   ├── extract_audio.py   # video -> audio.wav (16kHz)
│   ├── align.py           # audio (+texto) -> words.json  (Whisper / stable-ts)
│   ├── silence.py         # audio -> silence.json         (ffmpeg silencedetect)
│   ├── proxy.py           # video -> proxy.mp4            (720p, seek rápido)
│   ├── build_ui.py        # words+silence -> editor.html  (el editor)
│   ├── cut.py             # cortes.json + video -> final  (ffmpeg trim/concat)
│   └── serve.py           # servidor local con soporte HTTP Range (seek)
├── work/                  # resultados por video (no se versiona)
├── requirements.txt
└── README.md
```

## Cómo funciona (resumen técnico)

1. **Audio**: se extrae a WAV 16 kHz.
2. **Palabras**: Whisper da el timestamp de cada palabra. Con texto verbatim se usa
   *forced alignment* para clavar cada "eh".
3. **Silencios**: `ffmpeg silencedetect` lista las pausas reales.
4. **Detección de muletillas**: léxicas (eh, mmm, o sea…), repeticiones y pausas largas.
5. **Cortes "pegados a silencio"**: cada corte va del *medio del silencio anterior* al
   *medio del silencio siguiente* → empalma palabra real con palabra real, sin vacío.
6. **Preview**: el editor reproduce el proxy y **salta** los cortes en vivo.
7. **Render**: `ffmpeg` corta y concatena los segmentos a conservar desde el **video
   original** (sin pérdida visible).

---

Hecho con Claude Code · v1
