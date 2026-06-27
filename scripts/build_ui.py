#!/usr/bin/env python3
"""
Genera una interfaz estilo Descript (HTML autocontenido) para revisar la
transcripcion palabra-por-palabra y encontrar muletillas con precision.

Entrada : public/transcript-words-5min.json   [{word,start,end}, ...]
Salida  : public/editor-muletillas.html
Video   : assets/video-5min.mp4 (relativo al HTML, dentro de public/)
"""
import json, re, unicodedata, os, argparse

ap = argparse.ArgumentParser(description="Genera el editor de muletillas (HTML autocontenido).")
ap.add_argument("--words",   required=True, help="JSON de palabras alineadas [{word,start,end}]")
ap.add_argument("--silence", required=True, help="JSON de silencios [[start,end],...]")
ap.add_argument("--video",   required=True, help="ruta del video relativa al HTML (p.ej. proxy.mp4)")
ap.add_argument("--out",     required=True, help="ruta del HTML de salida")
args = ap.parse_args()
SRC, SIL_PATH, VIDEO_SRC, OUT = args.words, args.silence, args.video, args.out

words = json.load(open(SRC))

def norm(s):
    s = s.lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)

# muletillas "fuertes": sonidos de relleno + "ah"/"osea" (resaltadas en ámbar).
# OJO: "este"/"esto"/"pues" NO van aquí porque casi siempre son palabras
# legítimas ("todo ESTE paso", "PUES sí") — el detector no entiende el contexto.
STRONG = {"eh", "em", "ehm", "mmm", "mm", "ah", "osea"}
# "debiles": dependen del contexto, se marcan suave y desactivadas por defecto.
# Aquí van los demostrativos/conectores ambiguos para que NO se borren solos.
WEAK   = {"como", "entonces", "bueno", "tipo", "digamos", "verdad", "vale",
          "basicamente", "obviamente", "literal", "nada",
          "este", "esto", "pues"}
# muletillas VOCALIZADAS que se auto-marcan para cortar (sonidos de relleno).
# SOLO sonidos puros que nunca son una palabra real. "ah"/"osea" se resaltan
# pero NO se borran solas: tú decides, porque a veces son legítimas.
AUTO_FILLER = {"eh", "em", "ehm", "mmm", "mm"}

# silencios reales del audio -> para "pegar" los cortes
SILENCES = json.load(open(SIL_PATH)) if os.path.exists(SIL_PATH) else []

PAUSE_THRESHOLD = 0.7   # seg: hueco que probablemente esconde un "eh"
PARAGRAPH_GAP   = 1.2   # seg: hueco que inicia un parrafo nuevo (estilo Descript)

out = []
for i, x in enumerate(words):
    n = norm(x["word"])
    gap_before = x["start"] - words[i - 1]["end"] if i > 0 else 0
    repeated = i > 0 and n and norm(words[i - 1]["word"]) == n
    cat = ""
    if n in STRONG:      cat = "strong"
    elif repeated:       cat = "repeat"
    elif n in WEAK:      cat = "weak"
    out.append({
        "w": x["word"],
        "s": round(x["start"], 2),
        "e": round(x["end"], 2),
        "g": round(gap_before, 2),     # hueco antes de esta palabra
        "c": cat,                      # categoria de muletilla lexica
        "p": 1 if gap_before >= PARAGRAPH_GAP else 0,  # inicia parrafo
        "f": 1 if n in AUTO_FILLER else 0,             # auto-marcar para cortar
    })

DATA = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
SIL  = json.dumps(SILENCES, separators=(",", ":"))

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Editor de Muletillas — estilo Descript</title>
<style>
  :root{
    --bg:#0e0e12; --panel:#16161d; --panel2:#1d1d27; --line:#2a2a36;
    --txt:#d7d7e0; --txt-dim:#8b8b9a; --accent:#6366f1;
    --strong:#f59e0b; --weak:#7c7c33; --repeat:#ec4899; --pause:#38bdf8; --del:#ef4444;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:var(--bg);color:var(--txt);height:100vh;overflow:hidden}
  .app{display:grid;grid-template-columns:360px minmax(0,1fr) 340px;grid-template-rows:auto 1fr auto auto;
       height:100vh;column-gap:0}
  /* ---- HEADER (título + stats + reloj) ---- */
  .topbar{grid-column:1/4;display:flex;align-items:center;gap:24px;padding:10px 22px;
          background:var(--panel);border-bottom:1px solid var(--line)}
  .meta h1{font-size:16px;color:#fff;margin-bottom:3px}
  .meta p{font-size:12px;color:var(--txt-dim);line-height:1.55}
  .meta b{color:var(--accent)}
  .clock{margin-left:auto;text-align:right;flex-shrink:0}
  .clock .t{font-family:'SF Mono',Menlo,monospace;font-size:28px;font-weight:700;color:var(--accent)}
  .clock .d{font-size:12px;color:var(--txt-dim)}
  .stats{display:flex;gap:8px;flex-wrap:wrap;max-width:520px}
  .chip{background:var(--panel2);border:1px solid var(--line);padding:5px 11px;
        border-radius:20px;font-size:11.5px;white-space:nowrap}
  .chip b{color:#fff}
  /* ---- COLUMNA IZQUIERDA: video + inspector ---- */
  .leftcol{grid-column:1;grid-row:2;background:var(--panel);border-right:1px solid var(--line);
           overflow-y:auto;display:flex;flex-direction:column}
  .leftcol video{width:100%;aspect-ratio:16/9;background:#000;display:block;flex-shrink:0}
  .leftnote{padding:22px 18px;font-size:12.5px;color:var(--txt-dim);line-height:1.6;text-align:center}
  /* ---- TRANSCRIPT (centro) ---- */
  .transcript{grid-column:2;grid-row:2;overflow-y:auto;padding:40px 48px 120px;position:relative;scroll-behavior:smooth}
  .para{font-size:21px;line-height:2.1;margin:0 auto 22px;max-width:760px}
  .word{display:inline;padding:2px 2px;border-radius:4px;cursor:pointer;
        color:var(--txt);transition:background .12s,color .12s}
  .word:hover{background:rgba(99,102,241,.22)}
  .word.active{background:var(--accent);color:#fff;font-weight:600}
  .word.sel{outline:2px solid var(--pause);outline-offset:1px;border-radius:3px}
  .pause.sel{outline:2px solid #fff}
  .pause.cutpause{background:rgba(239,68,68,.20);border-color:var(--del);color:var(--del);text-decoration:line-through}
  .word.spoken{color:#f0f0f7}
  /* categorias muletilla */
  .word.strong{color:var(--strong);text-decoration:underline wavy var(--strong) 1.5px;text-underline-offset:3px}
  .word.repeat{color:var(--repeat);text-decoration:underline wavy var(--repeat) 1.5px;text-underline-offset:3px}
  .word.weak{color:var(--weak);border-bottom:1px dotted var(--weak)}
  .word.del{color:var(--del)!important;text-decoration:line-through!important;opacity:.55;background:rgba(239,68,68,.12)!important}
  /* marcador de pausa inline */
  .pause{display:inline-flex;align-items:center;gap:3px;font-size:11px;color:var(--pause);
         background:rgba(56,189,248,.10);border:1px solid rgba(56,189,248,.35);
         border-radius:10px;padding:0 7px;margin:0 4px;cursor:pointer;vertical-align:middle;
         font-family:'SF Mono',Menlo,monospace}
  .pause:hover{background:rgba(56,189,248,.25)}
  /* clase oculta segun filtros */
  .hide-strong .word.strong{text-decoration:none;color:var(--txt)}
  .hide-weak   .word.weak{border-bottom:none;color:var(--txt)}
  .hide-repeat .word.repeat{text-decoration:none;color:var(--txt)}
  .hide-pause  .pause{display:none}
  /* ---- SIDEBAR (derecha) ---- */
  .sidebar{grid-column:3;grid-row:2;background:var(--panel);border-left:1px solid var(--line);overflow-y:auto;
           display:flex;flex-direction:column}
  .side-sec{padding:14px 16px;border-bottom:1px solid var(--line)}
  .side-sec h3{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--txt-dim);margin-bottom:10px}
  .toggle{display:flex;align-items:center;gap:9px;padding:6px 8px;border-radius:6px;cursor:pointer;font-size:13px}
  .toggle:hover{background:var(--panel2)}
  .toggle .sw{width:34px;height:19px;border-radius:10px;background:#3a3a48;position:relative;flex-shrink:0;transition:background .15s}
  .toggle .sw::after{content:'';position:absolute;top:2px;left:2px;width:15px;height:15px;border-radius:50%;background:#fff;transition:left .15s}
  .toggle.on .sw{background:var(--accent)}
  .toggle.on .sw::after{left:17px}
  .toggle .dot{width:9px;height:9px;border-radius:50%}
  .toggle .ct{margin-left:auto;font-size:11px;color:var(--txt-dim);font-family:'SF Mono',Menlo,monospace}
  .findings{flex:1;overflow-y:auto}
  .find{display:flex;align-items:baseline;gap:8px;padding:8px 16px;border-bottom:1px solid var(--panel2);cursor:pointer;font-size:13px}
  .find:hover{background:var(--panel2)}
  .find .tm{font-family:'SF Mono',Menlo,monospace;font-size:11px;color:var(--txt-dim);flex-shrink:0;width:42px}
  .find .lbl{flex:1}
  .find .tag{font-size:10px;padding:1px 6px;border-radius:8px;flex-shrink:0}
  .find.del-row .lbl{text-decoration:line-through;color:var(--del)}
  /* ---- BOTTOM BAR ---- */
  /* ---- LÍNEA DE TIEMPO global (onda de todo el audio) ---- */
  .timeline{grid-column:1/4;grid-row:3;background:var(--panel);border-top:1px solid var(--line);
            padding:7px 14px 9px}
  .tl-bar{display:flex;align-items:center;gap:10px;margin-bottom:6px}
  .tl-bar .tl-title{font-size:11.5px;font-weight:700;color:var(--txt-dim)}
  .tl-bar .sp{flex:1}
  .tl-z{background:#33333f;color:#fff;border:none;width:26px;height:24px;border-radius:6px;
        cursor:pointer;font-size:15px;font-weight:700;line-height:1}
  .tl-z:hover{background:#41414f}
  .tl-zlbl{font-size:11px;color:var(--txt-dim);min-width:42px;text-align:center;font-variant-numeric:tabular-nums}
  .tl-del{background:var(--del);color:#fff;border:none;border-radius:6px;padding:5px 11px;
          font-size:11.5px;font-weight:600;cursor:pointer}
  .tl-del:disabled{opacity:.4;cursor:not-allowed}
  .tl-clr{background:transparent;border:1px solid var(--line);color:var(--txt-dim);border-radius:6px;
          padding:5px 9px;font-size:11.5px;cursor:pointer}
  .tl-sel-info{font-size:11px;color:var(--accent);font-weight:600;font-variant-numeric:tabular-nums;min-width:120px}
  .tl-canvas-wrap{position:relative}
  #tlwave{display:block;width:100%;height:84px;cursor:text;border-radius:6px;background:var(--bg)}
  .tl-scroll{width:100%;margin-top:5px;accent-color:var(--accent);cursor:pointer}
  .tl-scroll.hidden{visibility:hidden}
  .tl-hint{font-size:10px;color:var(--txt-dim);margin-top:2px}
  .bottombar{grid-column:1/4;grid-row:4;display:flex;align-items:center;gap:10px;padding:10px 22px;
             background:var(--panel);border-top:1px solid var(--line)}
  button{padding:8px 16px;border:none;border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;color:#fff}
  .b-play{background:#33333f}.b-play:hover{background:#41414f}
  .b-export{background:#10b981}.b-export:hover{background:#0e9e74}
  .b-undo{background:#52525f}.b-undo:hover{background:#62626f}
  .b-clear{background:#7a2230}.b-clear:hover{background:#922636}
  .b-render{background:var(--accent)}.b-render:hover{filter:brightness(1.12)}
  .b-render:disabled{opacity:.6;cursor:progress}
  /* corte manual */
  .mancut{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:11px 13px;margin-top:10px}
  .mancut-h{font-size:12px;font-weight:700;color:var(--del);margin-bottom:8px}
  .mancut-times{display:flex;gap:12px;font-size:12px;color:var(--txt-dim);margin-bottom:9px;flex-wrap:wrap}
  .mancut-times b{color:var(--txt);font-variant-numeric:tabular-nums}
  .mancut-row{display:flex;gap:7px;margin-bottom:7px}
  .mancut-row button{flex:1;padding:7px 8px;font-size:12px}
  .mc-set{background:#33333f}.mc-set:hover{background:#41414f}
  .mc-set.armed{background:var(--accent)}
  .mc-play{background:#33333f}.mc-play:hover{background:#41414f}
  .mc-del{background:var(--del)}.mc-del:hover{filter:brightness(1.1)}
  .mc-del:disabled{opacity:.4;cursor:not-allowed}
  .mancut-hint{font-size:10.5px;color:var(--txt-dim);line-height:1.4}
  .qsel{font-size:11.5px;color:var(--txt-dim);display:flex;align-items:center;gap:6px}
  .qsel select{background:var(--panel2);color:var(--txt);border:1px solid var(--line);
               border-radius:6px;padding:6px 8px;font-size:12px}
  .search{flex:1;max-width:200px;background:var(--panel2);border:1px solid var(--line);
          border-radius:7px;padding:8px 12px;color:var(--txt);font-size:13px}
  .hint{font-size:11.5px;color:var(--txt-dim)}
  .spacer{flex:1}
  .markbtns{display:flex;flex-direction:column;gap:6px}
  .mk{background:var(--panel2);border:1px solid var(--line);text-align:left;
      font-weight:500;font-size:12.5px;color:var(--txt)}
  .mk:hover{background:#26263200;border-color:var(--accent)}
  .mk.off{color:var(--txt-dim)}
  .find .cut{margin-left:6px;cursor:pointer;opacity:.5;flex-shrink:0}
  .find .cut:hover{opacity:1}
  .find.marked{background:rgba(239,68,68,.10)}
  .find.marked .cut{opacity:1;color:var(--del)}
  mark{background:var(--accent);color:#fff;border-radius:3px}
  .legend{display:flex;gap:14px;font-size:11px;color:var(--txt-dim);flex-wrap:wrap}
  .legend i{font-style:normal;border-bottom:2px solid;padding-bottom:1px}
  /* inspector / waveform */
  .inspector{padding:14px 16px;border-bottom:1px solid var(--line)}
  #inspector h3{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--txt-dim);margin-bottom:10px}
  .insword{font-size:16px;color:#fff;margin-bottom:10px}
  .insword b{color:var(--strong)}
  #wave{width:100%;height:96px;background:#0b0b12;border:1px solid var(--line);
        border-radius:6px;display:block;cursor:ew-resize;touch-action:none}
  .instimes{font-family:'SF Mono',Menlo,monospace;font-size:11px;color:var(--txt-dim);
            margin:8px 0;text-align:center}
  .instimes b{color:var(--pause)}
  .insrow{display:flex;align-items:center;gap:6px;margin-top:6px;font-size:12px;color:var(--txt-dim)}
  .insrow .nb{padding:4px 9px;background:var(--panel);border:1px solid var(--line);
              border-radius:5px;color:var(--txt);font-size:13px;font-weight:700;min-width:30px}
  .insrow .nb:hover{border-color:var(--accent)}
  .insrow .grow{flex:1}
  .ins-act{display:flex;gap:6px;margin-top:8px}
  .ins-act button{flex:1;font-size:12px;padding:7px 6px}
  .b-mark{background:var(--del)}.b-mark.on{background:#3a3a48}
  .b-same{background:var(--panel)}.b-same:hover{filter:brightness(1.3)}
  /* lista de eliminadas */
  .rm{display:flex;align-items:baseline;gap:8px;padding:6px 16px;border-bottom:1px solid var(--panel2);
      cursor:pointer;font-size:13px}
  .rm:hover{background:var(--panel2)}
  .rm .tm{font-family:'SF Mono',Menlo,monospace;font-size:11px;color:var(--txt-dim);width:42px;flex-shrink:0}
  .rm .w{flex:1;color:var(--del);text-decoration:line-through}
  .rm .x{opacity:.5}.rm:hover .x{opacity:1}
</style>
</head>
<body>
<div class="app">
  <!-- HEADER -->
  <div class="topbar">
    <div class="meta">
      <h1>Editor de Muletillas</h1>
      <p><b>Click</b> palabra/pausa = inspeccionar · <b>doble-click</b> = eliminar (se salta de verdad).<br>
      Las pausas <span style="color:var(--pause)">▸azules</span> también se pueden recortar y ajustar.</p>
    </div>
    <div class="stats">
      <span class="chip">Palabras <b id="s-words">0</b></span>
      <span class="chip">Muletillas <b id="s-fillers">0</b></span>
      <span class="chip">Pausas <b id="s-pauses">0</b></span>
      <span class="chip">A eliminar <b id="s-del">0</b></span>
      <span class="chip">Tiempo cortado <b id="s-time">0.0s</b></span>
    </div>
    <div class="clock">
      <div class="t" id="clock">0:00</div>
      <div class="d" id="dur">/ 5:00</div>
    </div>
  </div>

  <!-- LEFT: video + inspector -->
  <div class="leftcol">
    <video id="vid" controls preload="metadata">
      <source src="__VIDEO__" type="video/mp4">
    </video>
    <div class="mancut">
      <div class="mancut-h">✂️ Corte manual (cualquier tramo o silencio)</div>
      <div class="mancut-times">
        <span>Inicio <b id="mcIn">—</b></span>
        <span>Fin <b id="mcOut">—</b></span>
        <span id="mcDur"></span>
      </div>
      <div class="mancut-row">
        <button class="mc-set" onclick="mcSetIn()" title="usa el momento actual del video">⎡ Marcar inicio</button>
        <button class="mc-set" onclick="mcSetOut()" title="usa el momento actual del video">Marcar fin ⎤</button>
      </div>
      <div class="mancut-row">
        <button class="mc-play" id="mcPlayBtn" onclick="mcPreview()">▶ escuchar</button>
        <button class="mc-del" id="mcDelBtn" onclick="mcDelete()" disabled>Eliminar tramo</button>
      </div>
      <div class="mancut-hint">Pausa el video donde empieza el tramo y pulsa «Marcar inicio»; ve al final y pulsa «Marcar fin». Luego «Eliminar tramo».</div>
    </div>
    <div class="inspector" id="inspector" style="display:none">
      <h3>Ajustar corte</h3>
      <div class="insword" id="insWord"></div>
      <canvas id="wave" width="328" height="96"></canvas>
      <div class="instimes"><b id="insStart">0:00.00</b> → <b id="insEnd">0:00.00</b> &nbsp;(<span id="insDur">0.0s</span>)</div>
      <div class="insrow"><span class="grow">Inicio</span>
        <button class="nb" onclick="nudge('s',-1)" title="más atrás">◀</button>
        <button class="nb" onclick="nudge('s',1)" title="más adelante">▶</button>
      </div>
      <div class="insrow"><span class="grow">Fin</span>
        <button class="nb" onclick="nudge('e',-1)" title="más atrás">◀</button>
        <button class="nb" onclick="nudge('e',1)" title="más adelante">▶</button>
      </div>
      <div class="ins-act">
        <button class="b-mark" id="insMark" onclick="toggleSelDel()">Eliminar</button>
        <button class="b-same" id="insSame" onclick="markAllSame()">Marcar todas</button>
      </div>
      <div class="insrow" style="justify-content:center">
        <button class="nb" style="font-size:11px;font-weight:500" onclick="playSel()">▶ escuchar el corte</button>
      </div>
    </div>
    <div class="leftnote" id="leftnote">Haz <b style="color:var(--accent)">click</b> en una palabra o pausa para ver su forma de onda y ajustar el corte aquí.<br><br><b style="color:var(--del)">Cortar un tramo</b> (estilo CapCut): click en la 1ª palabra, luego <b style="color:var(--accent)">Shift+click</b> en la última → se borra todo lo del medio. Doble-click en una palabra la borra/restaura.</div>
  </div>

  <!-- TRANSCRIPT (centro) -->
  <div class="transcript" id="transcript"></div>

  <!-- SIDEBAR (derecha) -->
  <div class="sidebar">
    <div class="side-sec">
      <h3>Mostrar / detectar</h3>
      <div class="toggle on" data-cat="strong"><span class="dot" style="background:var(--strong)"></span>Muletillas léxicas<span class="ct" id="c-strong">0</span><span class="sw"></span></div>
      <div class="toggle on" data-cat="pause"><span class="dot" style="background:var(--pause)"></span>Pausas largas<span class="ct" id="c-pause">0</span><span class="sw"></span></div>
      <div class="toggle on" data-cat="repeat"><span class="dot" style="background:var(--repeat)"></span>Repeticiones<span class="ct" id="c-repeat">0</span><span class="sw"></span></div>
      <div class="toggle" data-cat="weak"><span class="dot" style="background:var(--weak)"></span>Conectores (suave)<span class="ct" id="c-weak">0</span><span class="sw"></span></div>
    </div>
    <div class="side-sec">
      <h3>Marcar para cortar</h3>
      <label style="display:flex;align-items:center;gap:8px;font-size:12.5px;margin-bottom:8px;cursor:pointer">
        <input type="checkbox" id="autoEh" checked> Auto-marcar muletillas (eh, mmm…)
      </label>
      <div class="markbtns">
        <button class="mk" onclick="markCat('strong')">＋ Muletillas (eh…)</button>
        <button class="mk" onclick="markCat('repeat')">＋ Repeticiones</button>
        <button class="mk" onclick="markCat('weak')">＋ Conectores</button>
        <button class="mk off" onclick="unmarkAll()">－ Quitar palabras marcadas</button>
      </div>
    </div>
    <div class="side-sec">
      <h3>Pausas / silencios</h3>
      <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;margin-bottom:8px">
        Recortar pausas ≥ <input id="pauseThr" type="number" step="0.1" min="0.3" value="1.0"
          style="width:54px;background:var(--panel);border:1px solid var(--line);border-radius:5px;color:var(--txt);padding:4px 6px"> s
        <button class="mk" style="flex:0;padding:5px 10px" onclick="markPausesOver()">Aplicar</button>
      </label>
      <div class="markbtns">
        <button class="mk" onclick="markAllPauses()">＋ Recortar TODAS las pausas</button>
        <button class="mk off" onclick="unmarkAllPauses()">－ Quitar todas las pausas</button>
      </div>
      <div id="pauseBuckets" style="margin-top:8px;display:flex;flex-direction:column;gap:5px"></div>
    </div>
    <div class="side-sec" style="padding-bottom:6px">
      <h3>Eliminadas (<span id="rmCount">0</span>) — click salta · ✕ restaura</h3>
    </div>
    <div id="removedList" style="max-height:170px;overflow-y:auto;flex-shrink:0"></div>
    <div class="side-sec" style="padding-bottom:8px">
      <h3>Hallazgos — click salta · ✂ marca</h3>
    </div>
    <div class="findings" id="findings"></div>
  </div>

  <!-- BOTTOM -->
  <!-- LÍNEA DE TIEMPO: onda de todo el audio, con zoom y selección -->
  <div class="timeline">
    <div class="tl-bar">
      <span class="tl-title">🌊 Línea de tiempo — arrastra sobre la onda para seleccionar y borrar</span>
      <span class="tl-sel-info" id="tlSelInfo"></span>
      <span class="sp"></span>
      <button class="tl-del" id="tlDelBtn" onclick="tlDeleteSelection()" disabled>✂️ Eliminar selección</button>
      <button class="tl-clr" onclick="tlClearSelection()">Quitar selección</button>
      <span style="width:8px"></span>
      <button class="tl-z" onclick="tlZoomBy(0.5)" title="alejar">−</button>
      <span class="tl-zlbl" id="tlZoomLbl">1x</span>
      <button class="tl-z" onclick="tlZoomBy(2)" title="acercar">+</button>
    </div>
    <div class="tl-canvas-wrap">
      <canvas id="tlwave" height="84"></canvas>
    </div>
    <input type="range" class="tl-scroll hidden" id="tlScroll" min="0" max="1000" value="0">
    <div class="tl-hint">Click = ir a ese punto · Arrastra = seleccionar tramo · Rueda del mouse = zoom · Las zonas rojas son lo que se elimina</div>
  </div>

  <div class="bottombar">
    <button class="b-play" id="play">▶ / ⏸</button>
    <input class="search" id="search" placeholder="Buscar palabra…">
    <button class="b-undo" onclick="undo()">↶ Deshacer</button>
    <button class="b-clear" onclick="clearAll()">Limpiar</button>
    <span class="spacer"></span>
    <span class="hint" id="renderHint"></span>
    <label class="qsel">Calidad
      <select id="crf">
        <option value="14">Máxima (CRF 14)</option>
        <option value="18" selected>Alta (CRF 18)</option>
        <option value="23">Media (CRF 23)</option>
      </select>
    </label>
    <input class="search" id="outName" style="max-width:230px" placeholder="nombre o ruta de salida"
           title="nombre de archivo (se guarda en la carpeta del proyecto) o ruta absoluta">
    <button class="b-export" onclick="exportJSON()">⬇ Exportar JSON</button>
    <button class="b-render" id="btnRender" onclick="renderVideo()">🎬 Renderizar video</button>
  </div>
</div>

<script>
const WORDS = __DATA__;
const SILENCES = __SILENCES__;   // [[start,end],...] silencios reales del audio
const PAUSE_TH = 0.7;
const vid = document.getElementById('vid');
const transcript = document.getElementById('transcript');
const findings = document.getElementById('findings');

const delSet = new Set();
let manualCuts = [];     // cortes manuales {s,e} hechos sobre la señal (tramos/silencios)
let mcIn = null, mcOut = null;   // marcas in/out del corte manual en curso
let undoStack = [];
let wordEls = [];
let cuts = [];           // rangos [s,e] fusionados que se SALTAN al reproducir
const SKIP_BRIDGE = 0.35;// fusiona cortes separados por menos de esto
let userMuted = false;   // si el usuario silenció a propósito, no lo tocamos

// puntos medios de los silencios (donde es más limpio cortar/empalmar)
const SEARCH = 1.3;  // ventana (s) máx para pegar el corte a un silencio vecino

// dada una palabra, calcula el rango de corte pegado a los silencios vecinos:
// del medio del silencio anterior al medio del silencio siguiente.
// ¿hay alguna palabra (que no sea la i) cuyo inicio caiga en (a,b)?
function wordStartsBetween(a,b,i){
  for(let j=0;j<WORDS.length;j++){ if(j!==i && WORDS[j].s>a+0.02 && WORDS[j].s<b-0.02) return true; }
  return false;
}
function snapWordCut(i){
  const w=WORDS[i];
  let start=w.s, end=w.e;
  // ATRÁS: silencio que TERMINA justo antes del eh, sin palabra entre el silencio y el eh
  let bs=null;
  for(const s of SILENCES){ if(s[1]<=w.s+0.06){ if(!bs||s[1]>bs[1]) bs=s; } }
  if(bs && (w.s-bs[1])<SEARCH && !wordStartsBetween(bs[1], w.s, i)) start=(bs[0]+bs[1])/2;
  else start = w.s - Math.min(Math.max(w.g||0,0),0.18);
  // ADELANTE: silencio que EMPIEZA justo después del eh, sin palabra en medio
  let as=null;
  for(const s of SILENCES){ if(s[0]>=w.e-0.06){ if(!as||s[0]<as[0]) as=s; } }
  if(as && (as[0]-w.e)<SEARCH && !wordStartsBetween(w.e, as[0], i)) end=(as[0]+as[1])/2;
  else end = w.e;
  if(end<=start) end=Math.max(w.e, start+0.06);
  return {s:start, e:end};
}

// ajustes manuales por palabra (override del snap automático)
const customCut = {};
function cutForWord(i){
  if(customCut[i]) return {s:customCut[i].s, e:customCut[i].e};
  return snapWordCut(i);
}

// ---- PAUSAS / SILENCIOS como cortes (id = índice de la palabra siguiente al hueco) ----
const GAP_KEEP = 0.10;          // segundos de silencio que se DEJAN a cada lado
const gapSet = new Set();        // pausas marcadas para recortar
const gapCut = {};               // ajustes manuales de pausas
// el silencio REAL (silencedetect) que más se solapa con el hueco entre las palabras
function silenceInGap(i){
  const a=WORDS[i-1].e, b=WORDS[i].s;
  let best=null, bestOv=0.04;
  for(const s of SILENCES){
    const ov=Math.min(b,s[1])-Math.max(a,s[0]);   // solapamiento con el hueco
    if(ov>bestOv){ bestOv=ov; best=s; }
  }
  return best;
}
function gapDefault(i){
  // pegar el corte al SILENCIO real, no a los límites de palabra (que llevan audio)
  const sil=silenceInGap(i);
  if(sil){
    let s=sil[0]+GAP_KEEP, e=sil[1]-GAP_KEEP;
    if(e<=s){ const m=(sil[0]+sil[1])/2; s=m-0.04; e=m+0.04; }
    return {s,e};
  }
  let s=WORDS[i-1].e+GAP_KEEP, e=WORDS[i].s-GAP_KEEP;
  if(e<=s){ const m=(WORDS[i-1].e+WORDS[i].s)/2; s=m-0.03; e=m+0.03; }
  return {s,e};
}
function gapCutFor(i){ return gapCut[i]?{s:gapCut[i].s,e:gapCut[i].e}:gapDefault(i); }
function ensureGapCustom(i){ if(!gapCut[i]){const c=gapDefault(i);gapCut[i]={s:c.s,e:c.e};} return gapCut[i]; }

// --- selección masiva de pausas (todas / por umbral / por grupos de duración) ---
const PAUSE_IDS = WORDS.map((w,i)=>i).filter(i=>i>0 && WORDS[i].g>=PAUSE_TH);
const PAUSE_BUCKETS = [[0.7,1.0],[1.0,1.5],[1.5,2.0],[2.0,3.0],[3.0,999]];
function pausesIn(lo,hi){ return PAUSE_IDS.filter(i=>WORDS[i].g>=lo && WORDS[i].g<hi); }
function markAllPauses(){ snapshot(); PAUSE_IDS.forEach(i=>gapSet.add(i)); applyClasses(); updateDelStats(); }
function unmarkAllPauses(){ if(!gapSet.size)return; snapshot(); gapSet.clear(); applyClasses(); updateDelStats(); }
function markPausesOver(){
  const thr=parseFloat(document.getElementById('pauseThr').value)||0;
  snapshot(); PAUSE_IDS.forEach(i=>{ if(WORDS[i].g>=thr) gapSet.add(i); }); applyClasses(); updateDelStats();
}
function toggleBucket(lo,hi){
  const ids=pausesIn(lo,hi), allOn=ids.every(i=>gapSet.has(i));
  snapshot(); ids.forEach(i=>{ allOn?gapSet.delete(i):gapSet.add(i); }); applyClasses(); updateDelStats();
}
function renderPauseBuckets(){
  const el=document.getElementById('pauseBuckets'); if(!el)return;
  el.innerHTML=PAUSE_BUCKETS.map(([lo,hi])=>{
    const ids=pausesIn(lo,hi); if(!ids.length) return '';
    const m=ids.filter(i=>gapSet.has(i)).length;
    const lbl=(hi>=999?('≥ '+lo.toFixed(1)):(lo.toFixed(1)+'–'+hi.toFixed(1)))+'s';
    const cls='mk'+(m===ids.length?'':' off');
    return '<button class="'+cls+'" style="font-size:12px" onclick="toggleBucket('+lo+','+hi+')">'+lbl+' &nbsp;<b>'+m+'/'+ids.length+'</b></button>';
  }).join('');
}

// reconstruye los rangos a saltar: palabras marcadas + pausas marcadas
function rebuildCuts(){
  const raw=[];
  delSet.forEach(i=>raw.push(cutForWord(i)));
  gapSet.forEach(i=>raw.push(gapCutFor(i)));
  manualCuts.forEach(c=>raw.push({s:c.s, e:c.e}));   // cortes manuales (tramos/silencios)
  raw.sort((p,q)=>p.s-q.s);
  cuts=[];
  for(const r of raw){
    const last=cuts[cuts.length-1];
    if(last && r.s-last.e < SKIP_BRIDGE){ last.e=Math.max(last.e,r.e); }
    else cuts.push({s:r.s, e:r.e});
  }
}

// ---- construir transcripción en párrafos ----
function build(){
  let html='', paraOpen=false;
  const openPara=()=>{ if(paraOpen) html+='</div>'; html+='<div class="para">'; paraOpen=true; };
  openPara();
  WORDS.forEach((w,i)=>{
    if(i>0 && w.p){ openPara(); }
    // marcador de pausa antes de la palabra (clickable: seleccionar/recortar)
    if(i>0 && w.g>=PAUSE_TH){
      html+='<span class="pause" data-gap="'+i+'" data-seek="'+(WORDS[i-1].e)+'">▸'+w.g.toFixed(1)+'s</span>';
    }
    const cls = 'word'+(w.c?(' '+w.c):'');
    html+='<span class="'+cls+'" data-i="'+i+'">'+escapeHtml(w.w)+'</span> ';
  });
  if(paraOpen) html+='</div>';
  transcript.innerHTML=html;
  wordEls = Array.from(transcript.querySelectorAll('.word'));
}
function escapeHtml(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}

build();

// ---- stats + contadores ----
const counts={strong:0,weak:0,repeat:0,pause:0};
WORDS.forEach((w,i)=>{
  if(w.c==='strong')counts.strong++;
  else if(w.c==='weak')counts.weak++;
  else if(w.c==='repeat')counts.repeat++;
  if(i>0 && w.g>=PAUSE_TH)counts.pause++;
});
document.getElementById('s-words').textContent=WORDS.length;
document.getElementById('s-fillers').textContent=counts.strong+counts.repeat;
document.getElementById('s-pauses').textContent=counts.pause;
['strong','weak','repeat','pause'].forEach(k=>document.getElementById('c-'+k).textContent=counts[k]);

// ---- lista de hallazgos en sidebar ----
function fmt(t){const m=Math.floor(t/60),s=Math.floor(t%60);return m+':'+String(s).padStart(2,'0');}
const findItems=[]; // {time, idx, type}
WORDS.forEach((w,i)=>{
  if(w.c==='strong')findItems.push({t:w.s,i,type:'strong',label:'«'+w.w+'»',tag:'léxica',color:'var(--strong)'});
  else if(w.c==='repeat')findItems.push({t:w.s,i,type:'repeat',label:'«'+w.w+'» (repetida)',tag:'repet',color:'var(--repeat)'});
  if(i>0 && w.g>=PAUSE_TH)findItems.push({t:WORDS[i-1].e,i,type:'pause',label:'pausa '+w.g.toFixed(1)+'s',tag:'pausa',color:'var(--pause)'});
});
findItems.sort((a,b)=>a.t-b.t);
function renderFindings(){
  findings.innerHTML=findItems.map((f,k)=>
    '<div class="find" data-k="'+k+'" data-seek="'+f.t+'" data-i="'+f.i+'" data-type="'+f.type+'">'+
    '<span class="tm">'+fmt(f.t)+'</span>'+
    '<span class="lbl">'+f.label+'</span>'+
    '<span class="tag" style="background:'+f.color+'22;color:'+f.color+'">'+f.tag+'</span>'+
    '<span class="cut" title="marcar/quitar para cortar">✂</span></div>'
  ).join('');
  refreshFindingMarks();
}
function refreshFindingMarks(){
  findings.querySelectorAll('.find').forEach(el=>{
    const i=+el.dataset.i, on=el.dataset.type==='pause'?gapSet.has(i):delSet.has(i);
    el.classList.toggle('marked', on);
  });
}
renderFindings();

// ---- interacciones ----
transcript.addEventListener('click',e=>{
  const p=e.target.closest('.pause');
  if(p){ const g=+p.dataset.gap; selectGap(g); vid.currentTime=Math.max(0,gapCutFor(g).s-0.4); return; }
  const wd=e.target.closest('.word');
  if(wd){ const i=+wd.dataset.i;
    // SHIFT+click = cortar TODO el tramo entre la palabra seleccionada y esta (estilo CapCut)
    if(e.shiftKey && selKind==='word' && selIdx>=0 && selIdx!==i){ deleteRange(selIdx,i); return; }
    selectWord(i); vid.currentTime=WORDS[i].s; }
});
transcript.addEventListener('dblclick',e=>{
  e.preventDefault();
  const p=e.target.closest('.pause');
  if(p){ const g=+p.dataset.gap; selectGap(g); toggleGapDel(g); return; }   // doble-click pausa = recortar
  const wd=e.target.closest('.word'); if(!wd)return;
  const i=+wd.dataset.i; toggleDel(i); selectWord(i);
});
findings.addEventListener('click',e=>{
  const f=e.target.closest('.find'); if(!f)return;
  const i=+f.dataset.i, gap=f.dataset.type==='pause';
  if(e.target.closest('.cut')){ gap?(selectGap(i),toggleGapDel(i)):(toggleDel(i),selectWord(i)); return; }
  gap?selectGap(i):selectWord(i); vid.currentTime=parseFloat(f.dataset.seek);
});

// ---- deshacer por instantáneas (cubre marcar, marcar-todas, nudge, arrastrar) ----
function snapshot(){
  undoStack.push({d:[...delSet], c:JSON.stringify(customCut), g:[...gapSet], gc:JSON.stringify(gapCut), m:JSON.stringify(manualCuts)});
  if(undoStack.length>200) undoStack.shift();
}
function applyClasses(){
  wordEls.forEach((el,i)=>el.classList.toggle('del', delSet.has(i)));
  document.querySelectorAll('.pause').forEach(el=>el.classList.toggle('cutpause', gapSet.has(+el.dataset.gap)));
}
function undo(){
  const s=undoStack.pop(); if(!s)return;
  delSet.clear(); s.d.forEach(i=>delSet.add(i));
  gapSet.clear(); s.g.forEach(i=>gapSet.add(i));
  for(const k in customCut) delete customCut[k]; Object.assign(customCut, JSON.parse(s.c));
  for(const k in gapCut) delete gapCut[k]; Object.assign(gapCut, JSON.parse(s.gc));
  if(s.m!==undefined) manualCuts = JSON.parse(s.m);
  applyClasses(); updateDelStats(); if(selIdx>=0) updateInspector();
}
function toggleDel(i){
  snapshot();
  if(delSet.has(i)){ delSet.delete(i); wordEls[i].classList.remove('del'); }
  else{ delSet.add(i); wordEls[i].classList.add('del'); }
  updateDelStats();
}
// ---- cortar un TRAMO completo (split + borrar, estilo CapCut) ----
// Marca todas las palabras entre a..b y las pausas internas -> un corte limpio.
function deleteRange(a,b){
  const lo=Math.min(a,b), hi=Math.max(a,b);
  snapshot();
  for(let i=lo;i<=hi;i++) delSet.add(i);
  for(let i=lo+1;i<=hi;i++){ if(WORDS[i].g>=PAUSE_TH) gapSet.add(i); }  // pausas dentro del tramo
  applyClasses(); updateDelStats();
  clearSelHighlight(); selIdx=-1;
  const segs=(hi-lo+1);
  flash('✂️ Tramo cortado: '+segs+' palabra'+(segs>1?'s':''));
}
// ---- CORTE MANUAL sobre la señal (tramos/silencios no detectados) ----
function fmtMs(t){ if(t==null)return '—'; const m=Math.floor(t/60),s=(t%60); return m+':'+(s<10?'0':'')+s.toFixed(2); }
function mcRefresh(){
  document.getElementById('mcIn').textContent=fmtMs(mcIn);
  document.getElementById('mcOut').textContent=fmtMs(mcOut);
  const ok=(mcIn!=null&&mcOut!=null&&mcOut>mcIn);
  document.getElementById('mcDur').textContent=ok?('('+(mcOut-mcIn).toFixed(2)+'s)'):'';
  document.getElementById('mcDelBtn').disabled=!ok;
}
function mcSetIn(){ mcIn=vid.currentTime; if(mcOut!=null&&mcOut<=mcIn)mcOut=null; mcRefresh(); flash('Inicio en '+fmtMs(mcIn)); }
function mcSetOut(){ mcOut=vid.currentTime; if(mcIn!=null&&mcOut<=mcIn){flash('El fin debe ir después del inicio');mcOut=null;} mcRefresh(); if(mcOut!=null)flash('Fin en '+fmtMs(mcOut)); }
function mcPreview(){ if(mcIn==null)return; vid.currentTime=Math.max(0,mcIn-0.3); vid.play(); }
function mcDelete(){
  if(mcIn==null||mcOut==null||mcOut<=mcIn)return;
  snapshot();
  manualCuts.push({s:+mcIn.toFixed(3), e:+mcOut.toFixed(3)});
  flash('✂️ Tramo eliminado: '+fmtMs(mcIn)+' → '+fmtMs(mcOut));
  mcIn=mcOut=null; mcRefresh();
  document.getElementById('mcIn').textContent='—'; document.getElementById('mcOut').textContent='—';
  updateDelStats();
}
function removeManualCut(idx){ snapshot(); manualCuts.splice(idx,1); updateDelStats(); }

// aviso breve
let _flashT=null;
function flash(msg){
  let el=document.getElementById('flashToast');
  if(!el){ el=document.createElement('div'); el.id='flashToast';
    el.style.cssText='position:fixed;bottom:70px;left:50%;transform:translateX(-50%);'+
      'background:var(--accent);color:#fff;padding:9px 18px;border-radius:8px;font-size:13px;'+
      'font-weight:600;z-index:9999;box-shadow:0 4px 16px rgba(0,0,0,.4);transition:opacity .3s';
    document.body.appendChild(el); }
  el.textContent=msg; el.style.opacity='1';
  clearTimeout(_flashT); _flashT=setTimeout(()=>{el.style.opacity='0';},1800);
}
function updateDelStats(){
  rebuildCuts();
  document.getElementById('s-del').textContent=delSet.size+gapSet.size+manualCuts.length;
  const t=cuts.reduce((a,c)=>a+(c.e-c.s),0);
  document.getElementById('s-time').textContent=t.toFixed(1)+'s';
  if(typeof refreshFindingMarks==='function') refreshFindingMarks();
  if(typeof renderRemovedList==='function') renderRemovedList();
  if(typeof renderPauseBuckets==='function') renderPauseBuckets();
  if(typeof drawWave==='function' && selIdx>=0) { updateInspector(); }
  if(typeof tlReady!=='undefined' && tlReady){ tlRenderWave(); tlDraw(); }   // refrescar zonas rojas
}
// marcar/desmarcar por categoría
function markCat(cat){
  snapshot();
  WORDS.forEach((w,i)=>{ if(w.c===cat && !delSet.has(i)){ delSet.add(i); wordEls[i].classList.add('del'); } });
  updateDelStats();
}
function unmarkAll(){
  if(!delSet.size)return;
  snapshot();
  delSet.forEach(i=>wordEls[i].classList.remove('del'));
  delSet.clear(); updateDelStats();
}
function clearAll(){
  if(!delSet.size && !gapSet.size && !manualCuts.length)return;
  if(confirm('¿Quitar todas las marcas de eliminación?')){
    snapshot();
    delSet.forEach(i=>wordEls[i].classList.remove('del'));
    delSet.clear(); gapSet.clear(); manualCuts=[];
    applyClasses(); updateDelStats();
  }
}

// ---- filtros (toggles) ----
document.querySelectorAll('.toggle').forEach(t=>{
  t.addEventListener('click',()=>{
    t.classList.toggle('on');
    const cat=t.dataset.cat, on=t.classList.contains('on');
    transcript.classList.toggle('hide-'+cat,!on);
  });
});

// ---- karaoke sync ----
let lastIdx=-1;
function tick(){
  const t=vid.currentTime;
  document.getElementById('clock').textContent=fmt(t);
  if(!vid.paused && selIdx>=0 && document.getElementById('inspector').style.display!=='none') drawWave();
  if(tlReady && !vid.paused) tlDraw();   // mover playhead en la línea de tiempo
  // ---- SALTAR los trozos eliminados: empalme duro instantáneo (sin mute/transición) ----
  // c.s ya viene metido en el silencio previo, así que saltar justo ahí no deja oír nada.
  if(!vid.paused && cuts.length){
    for(const c of cuts){
      if(t>=c.s && t<c.e-0.02){ vid.currentTime=c.e; break; }
    }
  }
  // binary search palabra activa
  let idx=-1,lo=0,hi=WORDS.length-1;
  while(lo<=hi){const m=(lo+hi)>>1;
    if(t>=WORDS[m].s && t<Math.max(WORDS[m].e,WORDS[m].s+0.05)){idx=m;break;}
    else if(t<WORDS[m].s)hi=m-1;else lo=m+1;}
  if(idx!==lastIdx){
    if(lastIdx>=0&&wordEls[lastIdx])wordEls[lastIdx].classList.remove('active');
    wordEls.forEach((el,i)=>el.classList.toggle('spoken',WORDS[i].e<=t));
    if(idx>=0&&wordEls[idx]){
      wordEls[idx].classList.add('active');
      const r=wordEls[idx].getBoundingClientRect(),cr=transcript.getBoundingClientRect();
      if(r.top<cr.top+80||r.bottom>cr.bottom-80){
        transcript.scrollTop+=r.top-cr.top-transcript.clientHeight/2;
      }
    }
    lastIdx=idx;
  }
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

vid.addEventListener('loadedmetadata',()=>{
  document.getElementById('dur').textContent='/ '+fmt(vid.duration);
  tlInit();   // ya conocemos la duración -> ajustar la línea de tiempo
});
vid.addEventListener('seeked',()=>{ if(tlReady) tlDraw(); });
document.getElementById('play').addEventListener('click',()=>vid.paused?vid.play():vid.pause());

// ---- búsqueda ----
document.getElementById('search').addEventListener('input',e=>{
  const q=e.target.value.toLowerCase().trim();
  wordEls.forEach((el,i)=>{
    const hit=q&&WORDS[i].w.toLowerCase().includes(q);
    el.innerHTML=hit?'<mark>'+escapeHtml(WORDS[i].w)+'</mark>':escapeHtml(WORDS[i].w);
  });
});

// ---- export (rangos YA pegados a silencio = lo que se reproduce) ----
function exportJSON(){
  if(!delSet.size){alert('No hay palabras marcadas para eliminar.');return;}
  rebuildCuts();
  const ranges=cuts.map(c=>[+c.s.toFixed(3),+c.e.toFixed(3)]);
  const data={
    fillers:ranges,
    count:ranges.length,
    words_marked:[...delSet].sort((a,b)=>a-b).map(i=>({word:WORDS[i].w,index:i})),
    total_duration:+ranges.reduce((s,r)=>s+(r[1]-r[0]),0).toFixed(2),
    from:'editor-muletillas (snap-silencio)'
  };
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='fillers-manual-5min.json';a.click();
  alert('Exportado: '+ranges.length+' cortes ('+data.total_duration.toFixed(1)+'s)');
}

// ---- RENDERIZAR el video final desde aquí (llama al backend ffmpeg) ----
async function renderVideo(){
  rebuildCuts();
  if(!cuts.length){ alert('No hay nada marcado para cortar.'); return; }
  const crf=document.getElementById('crf').value;
  const btn=document.getElementById('btnRender');
  const hint=document.getElementById('renderHint');
  btn.disabled=true; const t0=Date.now();
  hint.textContent='⏳ Renderizando en calidad…';
  const tick=setInterval(()=>{hint.textContent='⏳ Renderizando… '+Math.round((Date.now()-t0)/1000)+'s';},500);
  const out=document.getElementById('outName').value.trim();
  try{
    const res=await fetch('/render',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({fillers:cuts.map(c=>[+c.s.toFixed(3),+c.e.toFixed(3)]),crf:+crf,out})});
    const j=await res.json();
    clearInterval(tick);
    if(j.ok){
      const secs=Math.round((Date.now()-t0)/1000);
      hint.innerHTML='✅ '+secs+'s · guardado en <code style="color:#10b981">'+(j.path||j.file)+'</code> · '+
        '<a href="'+j.file+'?t='+Date.now()+'" download style="color:#6366f1">descargar</a>';
      window.open(j.file+'?t='+Date.now(),'_blank');
    }else{
      hint.textContent='❌ '+(j.error||'error'); alert('Error al renderizar:\n'+(j.error||''));
    }
  }catch(err){ clearInterval(tick); hint.textContent='❌ '+err.message; }
  btn.disabled=false;
}

// ============ INSPECTOR + WAVEFORM (palabras Y pausas) ============
let PEAKS=null, PPS=100, selIdx=-1, selKind='word';
fetch('peaks.json').then(r=>r.ok?r.json():null).then(j=>{ if(j){PEAKS=j.peaks;PPS=j.pps; if(selIdx>=0)drawWave(); tlInit();} }).catch(()=>{});

// ===== LÍNEA DE TIEMPO GLOBAL (onda de todo el audio, zoom + selección) =====
const tlc = document.getElementById('tlwave');
const tlctx = tlc.getContext('2d');
const tlCache = document.createElement('canvas');   // onda+cortes pre-renderizados
const tlcc = tlCache.getContext('2d');
const tlScrollEl = document.getElementById('tlScroll');
const tlDPR = window.devicePixelRatio || 1;
let tlZoom=0, tlBaseZoom=0, tlOffset=0;     // px/seg, zoom base, segundo en el borde izq
let tlSelA=null, tlSelB=null;                // selección (segundos)
let tlDragging=false, tlMoved=false, tlDownX=0, tlDownT=0;
let tlReady=false;

function tlDur(){ return (vid.duration&&isFinite(vid.duration))?vid.duration:(PEAKS?PEAKS.length/PPS:0); }
function tlViewSec(){ return tlc.clientWidth/tlZoom; }
function tlX(t){ return (t-tlOffset)*tlZoom; }
function tlT(x){ return tlOffset + x/tlZoom; }
function tlFmt(t){ const m=Math.floor(t/60),s=Math.floor(t%60); return m+':'+(s<10?'0':'')+s; }

function tlInit(){
  if(!PEAKS || tlDur()<=0) return;
  const W=tlc.clientWidth, H=84;
  tlc.width=Math.round(W*tlDPR); tlc.height=Math.round(H*tlDPR);
  tlctx.setTransform(tlDPR,0,0,tlDPR,0,0);
  tlBaseZoom = W/tlDur();
  if(!tlZoom) tlZoom=tlBaseZoom;
  tlReady=true;
  tlClamp(); tlRenderWave(); tlUpdateBar(); tlDraw();
}
function tlClamp(){
  const maxOff=Math.max(0,tlDur()-tlViewSec());
  tlOffset=Math.max(0,Math.min(maxOff,tlOffset));
}
function tlUpdateBar(){
  const maxOff=Math.max(0,tlDur()-tlViewSec());
  if(maxOff<=0.01) tlScrollEl.classList.add('hidden');
  else{ tlScrollEl.classList.remove('hidden'); tlScrollEl.value=Math.round(tlOffset/maxOff*1000); }
  const z=tlZoom/tlBaseZoom;
  document.getElementById('tlZoomLbl').textContent=(z<10?z.toFixed(1):Math.round(z))+'x';
}
function tlNiceStep(v){ for(const s of [1,2,5,10,15,30,60,120,300,600]) if(v/s<=12) return s; return 1200; }

// dibuja onda + zonas de corte + marcas de tiempo en el canvas-caché
function tlRenderWave(){
  if(!PEAKS) return;
  const W=tlc.clientWidth, H=84;
  tlCache.width=Math.round(W*tlDPR); tlCache.height=Math.round(H*tlDPR);
  tlcc.setTransform(tlDPR,0,0,tlDPR,0,0);
  tlcc.clearRect(0,0,W,H);
  const mid=H/2+4;
  for(let px=0;px<W;px++){
    const i0=Math.max(0,Math.floor(tlT(px)*PPS)), i1=Math.min(PEAKS.length-1,Math.floor(tlT(px+1)*PPS));
    let peak=0; for(let i=i0;i<=i1;i++){ const v=PEAKS[i]||0; if(v>peak)peak=v; }
    const h=peak*(H*0.78);
    const t0=tlT(px), inCut=cuts.some(c=>t0>=c.s&&t0<c.e);
    tlcc.fillStyle=inCut?'rgba(239,68,68,0.9)':'#566489';
    tlcc.fillRect(px,mid-h/2,1,Math.max(1,h));
  }
  // marcas de tiempo
  tlcc.fillStyle='rgba(180,180,196,0.45)'; tlcc.font='9px -apple-system,sans-serif';
  const step=tlNiceStep(tlViewSec()), first=Math.ceil(tlOffset/step)*step;
  for(let t=first;t<tlOffset+tlViewSec();t+=step){ const x=tlX(t); tlcc.fillRect(x,0,1,4); tlcc.fillText(tlFmt(t),x+3,9); }
}
// dibuja: caché + selección + playhead (barato, se llama cada frame)
function tlDraw(){
  if(!tlReady) return;
  const W=tlc.clientWidth, H=84;
  tlctx.clearRect(0,0,W,H);
  tlctx.drawImage(tlCache,0,0,W,H);
  if(tlSelA!=null&&tlSelB!=null){
    const a=Math.min(tlSelA,tlSelB), b=Math.max(tlSelA,tlSelB), xa=tlX(a), xb=tlX(b);
    tlctx.fillStyle='rgba(99,102,241,0.28)'; tlctx.fillRect(xa,0,xb-xa,H);
    tlctx.fillStyle='#6366f1'; tlctx.fillRect(xa,0,1.5,H); tlctx.fillRect(xb-1.5,0,1.5,H);
  }
  const ph=tlX(vid.currentTime);
  if(ph>=-1&&ph<=W+1){ tlctx.fillStyle='#fff'; tlctx.fillRect(ph-0.75,0,1.5,H); }
}
function tlZoomTo(z, centerT){
  tlZoom=Math.max(tlBaseZoom, Math.min(tlBaseZoom*500, z));
  tlOffset=centerT - tlc.clientWidth/2/tlZoom;
  tlClamp(); tlRenderWave(); tlUpdateBar(); tlDraw();
}
function tlZoomBy(f){ if(tlBaseZoom) tlZoomTo(tlZoom*f, tlOffset+tlViewSec()/2); }
function tlSelInfo(){
  const has=tlSelA!=null&&tlSelB!=null&&Math.abs(tlSelB-tlSelA)>0.05;
  document.getElementById('tlDelBtn').disabled=!has;
  document.getElementById('tlSelInfo').textContent=has?
    (tlFmt(Math.min(tlSelA,tlSelB))+' → '+tlFmt(Math.max(tlSelA,tlSelB))+'  ('+Math.abs(tlSelB-tlSelA).toFixed(1)+'s)'):'';
}
function tlDeleteSelection(){
  if(tlSelA==null||tlSelB==null) return;
  const a=Math.min(tlSelA,tlSelB), b=Math.max(tlSelA,tlSelB);
  if(b-a<0.05) return;
  snapshot(); manualCuts.push({s:+a.toFixed(3),e:+b.toFixed(3)});
  flash('✂️ Tramo eliminado: '+tlFmt(a)+' → '+tlFmt(b));
  tlSelA=tlSelB=null; tlSelInfo(); updateDelStats();
}
function tlClearSelection(){ tlSelA=tlSelB=null; tlSelInfo(); tlDraw(); }

tlScrollEl.addEventListener('input',()=>{
  const maxOff=Math.max(0,tlDur()-tlViewSec());
  tlOffset=(tlScrollEl.value/1000)*maxOff; tlRenderWave(); tlDraw();
});
tlc.addEventListener('mousedown',e=>{
  tlDragging=true; tlMoved=false; tlDownX=e.offsetX; tlDownT=tlT(e.offsetX);
  tlSelA=tlDownT; tlSelB=tlDownT;
});
window.addEventListener('mousemove',e=>{
  if(!tlDragging) return;
  const r=tlc.getBoundingClientRect(); let x=Math.max(0,Math.min(tlc.clientWidth,e.clientX-r.left));
  if(Math.abs(x-tlDownX)>3) tlMoved=true;
  tlSelB=tlT(x); tlSelInfo(); tlDraw();
});
window.addEventListener('mouseup',()=>{
  if(!tlDragging) return; tlDragging=false;
  if(!tlMoved){ vid.currentTime=Math.max(0,tlDownT); tlSelA=tlSelB=null; tlSelInfo(); }
  tlDraw();
});
tlc.addEventListener('wheel',e=>{
  e.preventDefault(); if(!tlBaseZoom) return;
  const tAt=tlT(e.offsetX), f=e.deltaY<0?1.2:1/1.2;
  tlZoom=Math.max(tlBaseZoom,Math.min(tlBaseZoom*500,tlZoom*f));
  tlOffset=tAt-e.offsetX/tlZoom; tlClamp(); tlRenderWave(); tlUpdateBar(); tlDraw();
},{passive:false});
let _tlrz=null;
window.addEventListener('resize',()=>{ clearTimeout(_tlrz); _tlrz=setTimeout(tlInit,150); });
const wave=document.getElementById('wave'); const wctx=wave.getContext('2d');
let viewS=0, viewE=1;
function normw(s){ return (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-z0-9]/g,''); }
function tcf(s){const m=Math.floor(s/60),sec=(s%60);return m+':'+(sec<10?'0':'')+sec.toFixed(2);}
const isGap=()=>selKind==='gap';
function curCut(){
  if(selIdx<0)return null;
  if(isGap()) return gapCutFor(selIdx);
  return customCut[selIdx]?{s:customCut[selIdx].s,e:customCut[selIdx].e}:snapWordCut(selIdx);
}
function ensureCustom(){
  if(isGap()) return ensureGapCustom(selIdx);
  if(!customCut[selIdx]){ const c=snapWordCut(selIdx); customCut[selIdx]={s:c.s,e:c.e}; }
  return customCut[selIdx];
}
function isMarked(){ return isGap()?gapSet.has(selIdx):delSet.has(selIdx); }

function clearSelHighlight(){
  wordEls.forEach(el=>el.classList.remove('sel'));
  document.querySelectorAll('.pause').forEach(el=>el.classList.remove('sel'));
}
function selectWord(i){
  selKind='word'; selIdx=i; clearSelHighlight();
  if(wordEls[i]) wordEls[i].classList.add('sel');
  document.getElementById('inspector').style.display='block';
  document.getElementById('leftnote').style.display='none';
  updateInspector();
}
function selectGap(i){
  selKind='gap'; selIdx=i; clearSelHighlight();
  const el=document.querySelector('.pause[data-gap="'+i+'"]'); if(el) el.classList.add('sel');
  document.getElementById('inspector').style.display='block';
  document.getElementById('leftnote').style.display='none';
  updateInspector();
}
function updateInspector(){
  if(selIdx<0)return;
  const c=curCut();
  document.getElementById('insWord').innerHTML = isGap()
     ? '⏸ <b>pausa</b> ('+(WORDS[selIdx].g||0).toFixed(1)+'s de silencio)'
     : '«<b>'+escapeHtml(WORDS[selIdx].w)+'</b>»';
  document.getElementById('insStart').textContent=tcf(c.s);
  document.getElementById('insEnd').textContent=tcf(c.e);
  document.getElementById('insDur').textContent=(c.e-c.s).toFixed(2)+'s';
  const mk=document.getElementById('insMark'), on=isMarked();
  mk.textContent=on?'Quitar del corte':(isGap()?'Recortar pausa':'Eliminar'); mk.classList.toggle('on',on);
  const same=document.getElementById('insSame');
  if(isGap()){ same.style.display='none'; }
  else{ same.style.display=''; same.textContent='Marcar las '+WORDS.filter(x=>normw(x.w)===normw(WORDS[selIdx].w)).length+' iguales'; }
  drawWave();
}
function drawWave(){
  if(selIdx<0)return;
  const c=curCut(), pad=Math.max(0.8,(c.e-c.s));
  viewS=Math.max(0,c.s-pad); viewE=c.e+pad;
  const W=wave.width,H=wave.height; wctx.clearRect(0,0,W,H);
  const X=t=>(t-viewS)/(viewE-viewS)*W;
  if(PEAKS){
    for(let px=0;px<W;px++){
      const t=viewS+(px/W)*(viewE-viewS), v=PEAKS[Math.floor(t*PPS)]||0, h=v*(H*0.92);
      wctx.fillStyle=(t>=c.s&&t<c.e)?'#ef4444':'#5b6b8c';
      wctx.fillRect(px,(H-h)/2,1,Math.max(1,h));
    }
  }else{
    wctx.fillStyle='rgba(239,68,68,0.18)'; wctx.fillRect(X(c.s),0,X(c.e)-X(c.s),H);
  }
  wctx.fillStyle='#ffd24a'; wctx.fillRect(X(c.s)-1.5,0,3,H); wctx.fillRect(X(c.e)-1.5,0,3,H);
  const ph=X(vid.currentTime); if(ph>=0&&ph<=W){ wctx.fillStyle='#fff'; wctx.fillRect(ph,0,1,H); }
}
let drag=null;
wave.addEventListener('pointerdown',e=>{
  if(selIdx<0)return;
  snapshot();   // una sola instantánea por arrastre
  const rect=wave.getBoundingClientRect();
  const t=viewS+((e.clientX-rect.left)/rect.width)*(viewE-viewS), c=curCut();
  drag=(Math.abs(t-c.s)<Math.abs(t-c.e))?'s':'e';
  wave.setPointerCapture(e.pointerId); applyDrag(e);
});
wave.addEventListener('pointermove',e=>{ if(drag)applyDrag(e); });
wave.addEventListener('pointerup',()=>{ drag=null; updateDelStats(); });
function applyDrag(e){
  const rect=wave.getBoundingClientRect();
  const t=viewS+((e.clientX-rect.left)/rect.width)*(viewE-viewS), cc=ensureCustom();
  if(drag==='s') cc.s=Math.max(0,Math.min(t,cc.e-0.05)); else cc.e=Math.max(cc.s+0.05,t);
  if(!isMarked()){ markSel(true); }
  rebuildCuts(); updateInspector();
}
// marca/desmarca lo seleccionado (palabra o pausa) sin snapshot extra
function markSel(on){
  if(isGap()){
    if(on) gapSet.add(selIdx); else gapSet.delete(selIdx);
    const el=document.querySelector('.pause[data-gap="'+selIdx+'"]'); if(el) el.classList.toggle('cutpause',on);
  }else{
    if(on){ delSet.add(selIdx); wordEls[selIdx].classList.add('del'); }
    else  { delSet.delete(selIdx); wordEls[selIdx].classList.remove('del'); }
  }
}
function toggleGapDel(i){ snapshot(); if(gapSet.has(i)){gapSet.delete(i);} else {gapSet.add(i);} applyClasses(); updateDelStats(); }
function nudge(edge,dir){
  if(selIdx<0)return;
  snapshot();
  const cc=ensureCustom(), step=0.033*dir;
  if(edge==='s') cc.s=Math.max(0,Math.min(cc.s+step,cc.e-0.05)); else cc.e=Math.max(cc.s+0.05,cc.e+step);
  updateDelStats();
}
function toggleSelDel(){
  if(selIdx<0)return;
  if(isGap()) toggleGapDel(selIdx); else toggleDel(selIdx);
  updateInspector();
}
function markAllSame(){
  if(selIdx<0)return;
  snapshot();
  const key=normw(WORDS[selIdx].w);
  WORDS.forEach((w,i)=>{ if(normw(w.w)===key && !delSet.has(i)){ delSet.add(i); wordEls[i].classList.add('del'); } });
  updateDelStats();
}
function playSel(){ if(selIdx<0)return; const c=curCut(); vid.currentTime=Math.max(0,c.s-0.6); vid.play(); }

// ---- lista de Eliminadas ----
const removedList=document.getElementById('removedList');
function renderRemovedList(){
  const items=[...delSet].map(i=>({k:'word',i,c:cutForWord(i),label:WORDS[i].w}))
    .concat([...gapSet].map(i=>({k:'gap',i,c:gapCutFor(i),label:'⏸ pausa'})))
    .concat(manualCuts.map((c,idx)=>({k:'man',i:idx,c:c,label:'✂️ tramo '+(c.e-c.s).toFixed(1)+'s'})))
    .sort((a,b)=>a.c.s-b.c.s);
  document.getElementById('rmCount').textContent=items.length;
  removedList.innerHTML=items.map(it=>
    '<div class="rm" data-k="'+it.k+'" data-i="'+it.i+'" data-seek="'+it.c.s.toFixed(3)+'">'+
    '<span class="tm">'+fmt(it.c.s)+'</span><span class="w">'+escapeHtml(it.label)+'</span><span class="x">✕</span></div>'
  ).join('');
}
removedList.addEventListener('click',e=>{
  const r=e.target.closest('.rm'); if(!r)return;
  const i=+r.dataset.i, k=r.dataset.k;
  if(e.target.closest('.x')){
    if(k==='man') removeManualCut(i);
    else if(k==='gap') toggleGapDel(i);
    else toggleDel(i);
    return;
  }
  if(k==='man'){ vid.currentTime=parseFloat(r.dataset.seek); return; }
  k==='gap'?selectGap(i):selectWord(i); vid.currentTime=parseFloat(r.dataset.seek);
});

// ---- auto-marcar muletillas vocalizadas (eh, em, mmm, ah, o sea) al cargar ----
// Se puede desactivar con la casilla, y "Deshacer/Limpiar" lo revierte.
function autoMarkFillers(){
  snapshot();   // permite deshacer el auto-marcado (volver a cero)
  WORDS.forEach((w,i)=>{ if(w.f && !delSet.has(i)){ delSet.add(i); wordEls[i].classList.add('del'); } });
  updateDelStats();
}
mcRefresh();
if(document.getElementById('autoEh').checked) autoMarkFillers();
document.getElementById('autoEh').addEventListener('change',e=>{
  if(e.target.checked) autoMarkFillers();
  else { snapshot(); WORDS.forEach((w,i)=>{ if(w.f && delSet.has(i)){ delSet.delete(i); wordEls[i].classList.remove('del'); } }); updateDelStats(); }
});
</script>
</body>
</html>"""

HTML = (HTML.replace("__DATA__", DATA)
            .replace("__SILENCES__", SIL)
            .replace("__VIDEO__", VIDEO_SRC))
open(OUT, "w").write(HTML)
print("OK ->", OUT)
print("Palabras:", len(out))
print("Strong:", sum(1 for w in out if w['c']=='strong'),
      "| Weak:", sum(1 for w in out if w['c']=='weak'),
      "| Repeat:", sum(1 for w in out if w['c']=='repeat'),
      "| Pausas>=0.7:", sum(1 for i,w in enumerate(out) if i>0 and w['g']>=0.7))
