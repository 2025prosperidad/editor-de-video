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

# muletillas "fuertes": casi siempre son relleno
STRONG = {"eh", "em", "ehm", "mmm", "mm", "ah", "este", "esto", "pues", "osea"}
# "debiles": dependen del contexto, se marcan suave y desactivadas por defecto
WEAK   = {"como", "entonces", "bueno", "tipo", "digamos", "verdad", "vale",
          "basicamente", "obviamente", "literal", "nada"}
# muletillas VOCALIZADAS que se auto-marcan para cortar (sonidos de relleno)
AUTO_FILLER = {"eh", "em", "ehm", "mmm", "mm", "ah", "osea"}

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
  .app{display:grid;grid-template-columns:360px minmax(0,1fr) 340px;grid-template-rows:auto 1fr auto;
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
  .bottombar{grid-column:1/4;grid-row:3;display:flex;align-items:center;gap:10px;padding:10px 22px;
             background:var(--panel);border-top:1px solid var(--line)}
  button{padding:8px 16px;border:none;border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;color:#fff}
  .b-play{background:#33333f}.b-play:hover{background:#41414f}
  .b-export{background:#10b981}.b-export:hover{background:#0e9e74}
  .b-undo{background:#52525f}.b-undo:hover{background:#62626f}
  .b-clear{background:#7a2230}.b-clear:hover{background:#922636}
  .b-render{background:var(--accent)}.b-render:hover{filter:brightness(1.12)}
  .b-render:disabled{opacity:.6;cursor:progress}
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
    <div class="leftnote" id="leftnote">Haz <b style="color:var(--accent)">click</b> en una palabra o pausa del texto para ver su forma de onda y ajustar el corte aquí.</div>
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
let undoStack = [];
let wordEls = [];
let cuts = [];           // rangos [s,e] fusionados que se SALTAN al reproducir
const SKIP_BRIDGE = 0.35;// fusiona cortes separados por menos de esto
let userMuted = false;   // si el usuario silenció a propósito, no lo tocamos

// puntos medios de los silencios (donde es más limpio cortar/empalmar)
const SIL_MID = SILENCES.map(s=>({a:s[0], b:s[1], mid:(s[0]+s[1])/2}));
const SEARCH = 1.3;  // ventana (s) para buscar el silencio que bordea la palabra

// dada una palabra, calcula el rango de corte pegado a los silencios vecinos:
// del medio del silencio anterior al medio del silencio siguiente.
function snapWordCut(i){
  const w=WORDS[i];
  const c=(w.s+w.e)/2;
  // silencio anterior: el de mayor 'mid' que esté antes del centro
  let before=null;
  for(const s of SIL_MID){ if(s.mid < c) { if(!before || s.mid>before.mid) before=s; } }
  // silencio siguiente: el de menor 'mid' que esté después del centro
  let after=null;
  for(const s of SIL_MID){ if(s.mid > c) { if(!after || s.mid<after.mid) after=s; } }
  let start = (before && (c-before.mid) <= SEARCH) ? before.mid : (w.s - Math.min(Math.max(w.g||0,0),0.18));
  let end   = (after  && (after.mid-c) <= SEARCH) ? after.mid  : w.e;
  if(end <= start) end = Math.max(w.e, start+0.08);
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
  if(wd){ const i=+wd.dataset.i; selectWord(i); vid.currentTime=WORDS[i].s; }
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
  undoStack.push({d:[...delSet], c:JSON.stringify(customCut), g:[...gapSet], gc:JSON.stringify(gapCut)});
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
  applyClasses(); updateDelStats(); if(selIdx>=0) updateInspector();
}
function toggleDel(i){
  snapshot();
  if(delSet.has(i)){ delSet.delete(i); wordEls[i].classList.remove('del'); }
  else{ delSet.add(i); wordEls[i].classList.add('del'); }
  updateDelStats();
}
function updateDelStats(){
  rebuildCuts();
  document.getElementById('s-del').textContent=delSet.size+gapSet.size;
  const t=cuts.reduce((a,c)=>a+(c.e-c.s),0);
  document.getElementById('s-time').textContent=t.toFixed(1)+'s';
  if(typeof refreshFindingMarks==='function') refreshFindingMarks();
  if(typeof renderRemovedList==='function') renderRemovedList();
  if(typeof renderPauseBuckets==='function') renderPauseBuckets();
  if(typeof drawWave==='function' && selIdx>=0) { updateInspector(); }
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
  if(!delSet.size)return;
  if(confirm('¿Quitar todas las marcas de eliminación?')){
    snapshot();
    delSet.forEach(i=>wordEls[i].classList.remove('del'));
    delSet.clear();updateDelStats();
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
});
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
fetch('peaks.json').then(r=>r.ok?r.json():null).then(j=>{ if(j){PEAKS=j.peaks;PPS=j.pps; if(selIdx>=0)drawWave();} }).catch(()=>{});
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
    .sort((a,b)=>a.c.s-b.c.s);
  document.getElementById('rmCount').textContent=items.length;
  removedList.innerHTML=items.map(it=>
    '<div class="rm" data-k="'+it.k+'" data-i="'+it.i+'" data-seek="'+it.c.s.toFixed(3)+'">'+
    '<span class="tm">'+fmt(it.c.s)+'</span><span class="w">'+escapeHtml(it.label)+'</span><span class="x">✕</span></div>'
  ).join('');
}
removedList.addEventListener('click',e=>{
  const r=e.target.closest('.rm'); if(!r)return;
  const i=+r.dataset.i, gap=r.dataset.k==='gap';
  if(e.target.closest('.x')){ gap?toggleGapDel(i):toggleDel(i); return; }
  gap?selectGap(i):selectWord(i); vid.currentTime=parseFloat(r.dataset.seek);
});

// ---- auto-marcar muletillas vocalizadas (eh, em, mmm, ah, o sea) al cargar ----
// Se puede desactivar con la casilla, y "Deshacer/Limpiar" lo revierte.
function autoMarkFillers(){
  snapshot();   // permite deshacer el auto-marcado (volver a cero)
  WORDS.forEach((w,i)=>{ if(w.f && !delSet.has(i)){ delSet.add(i); wordEls[i].classList.add('del'); } });
  updateDelStats();
}
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
