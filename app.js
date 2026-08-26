import { run } from "./src/malbolge-core.mjs";

const $ = (id) => document.getElementById(id);
const entrada = $("entrada"), salida = $("salida");
const badge = $("badge"), metaIn = $("metaIn"), metaOut = $("metaOut");
const analisis = $("analisis");

function setBadge(ok, txt) { badge.className = `badge ${ok ? "ok" : "err"}`; badge.textContent = txt; }

/* ---------------- modo rapido (una caja, como siempre) ---------------- */

function parecePrograma(src) {
  const t = src.trim();
  if (t.length < 8) return false;
  for (const ch of t) {
    const v = ch.codePointAt(0);
    if ((v >= 9 && v <= 13) || v === 32 || v < 33 || v > 126) return false;
  }
  return true;
}

function sondeaPrograma(src) {
  try {
    const r = run(src.trim(), "", 150_000, { maxOutput: 50_000 });
    return r.status === "HALTED";
  } catch { return false; }
}

$("btnConvert").addEventListener("click", () => {
  const src = entrada.value;
  if (!src.trim()) return;
  const modo = $("modo").value;
  const btn = $("btnConvert");
  btn.disabled = true;
  setBadge(false, "");
  analisis.textContent = "procesando…";
  setTimeout(() => {
    const t0 = performance.now();
    try {
      const esProg =
        modo === "toText" ? true :
        modo === "toMal" ? false :
        (parecePrograma(src) ? sondeaPrograma(src) : false);
      if (esProg) {
        const r = run(src, "", 2_000_000, { maxOutput: 300_000 });
        salida.value = r.output + (r.status === "MAX_OUTPUT" ? "\n…[truncada]" : "");
        metaIn.textContent = `${src.length} caracteres`;
        metaOut.textContent = `${r.steps} pasos`;
        setBadge(r.status === "HALTED", r.status);
        analisis.textContent = `estado: ${r.status}   pasos: ${r.steps}   salida: ${r.output.length} bytes`;
      } else {
        alert("Para textos largos usa '🧵 Traducir TODO por pasos' (no se traba y guarda checkpoints).");
        salida.value = "";
        setBadge(false, "usa el modo lotes");
        analisis.textContent = "el boton rapido solo ejecuta programas; generacion grande => lotes.";
      }
    } catch (e) {
      salida.value = "";
      setBadge(false, "error");
      analisis.textContent = "error: " + (e.message || e);
    }
    btn.disabled = false;
  }, 30);
});

$("fileIn").addEventListener("change", async (ev) => {
  const f = ev.target.files[0];
  if (!f) return;
  const buf = await f.arrayBuffer();
  const texto = new TextDecoder("windows-1252").decode(buf);
  entrada.value = texto;
  metaIn.textContent = `${f.name} · ${texto.length} caracteres`;
});

/* ---------------- WEBOLGE: lotes con checkpoint (SEAM case #3) ---------------- */

const MIN_CHUNK = 60;

function idbOpen() {
  return new Promise((res, rej) => {
    const r = indexedDB.open("webolge", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("kv");
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}
const dbSet = async (k, v) => { const db = await idbOpen(); return new Promise((res, rej) => { const tx = db.transaction("kv", "readwrite"); tx.objectStore("kv").put(v, k); tx.oncomplete = res; tx.onerror = () => rej(tx.error); }); };
const dbGet = async (k) => { const db = await idbOpen(); return new Promise((res, rej) => { const q = db.transaction("kv", "readonly").objectStore("kv").get(k); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); }); };
const dbDel = async (k) => { const db = await idbOpen(); return new Promise((res, rej) => { const tx = db.transaction("kv", "readwrite"); tx.objectStore("kv").delete(k); tx.oncomplete = res; tx.onerror = () => rej(tx.error); }); };

async function sha(s) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

let worker = null, currentId = null;
const pendientes = new Map();

function getWorker() {
  if (!worker) {
    worker = new Worker("./src/gen-worker.mjs", { type: "module" });
    worker.onmessage = (ev) => {
      const d = ev.data || {};
      const p = pendientes.get(d.id);
      if (!p) return;
      if (d.type === "prog") {
        $("loteLabel").textContent = `chunk en curso: ${d.i}/${d.total} chars · ${d.charsDone} celdas acumuladas`;
        return;
      }
      if (d.type === "beat") return;
      pendientes.delete(d.id);
      if (d.type === "done") p.res({ program: d.program });
      else if (d.type === "paused") p.res({ paused: true });
      else p.res({ error: d.message, timeout: !!d.timeout });
    };
  }
  return worker;
}

const genEnWorker = (texto, ancho, deadlineMs) => new Promise((res) => {
  const id = crypto.randomUUID();
  currentId = id;
  pendientes.set(id, { res });
  getWorker().postMessage({ cmd: "gen", id, texto, ancho, deadlineMs });
});

let job = null, jobKey = null, corriendo = false, pausado = false;

const guardar = () => dbSet("job:" + jobKey, job);

function pintarLote() {
  const done = job.chunks.filter(c => c.status === "done").length;
  const pct = Math.round(done / job.chunks.length * 100);
  $("barra").style.width = pct + "%";
  $("loteLabel").textContent =
    `${done}/${job.chunks.length} chunks · ${pct}% · tamaño=${job.chunkSize}` +
    (pausado ? " · PAUSADO" : corriendo ? " · corriendo" : "");
}

function bisectar(c) {
  const len = c.end - c.start;
  if (len <= MIN_CHUNK * 2) return false;
  const mid = c.start + Math.floor(len / 2);
  const idx = job.chunks.indexOf(c);
  const a = { i: 0, start: c.start, end: mid, status: "pending" };
  const b = { i: 0, start: mid, end: c.end, status: "pending" };
  job.chunks.splice(idx, 1, a, b);
  job.chunks.forEach((x, j) => x.i = j);
  return true;
}

async function procesarLote() {
  if (!job || corriendo || pausado) return;
  corriendo = true;
  pintarLote();
  while (true) {
    if (pausado) break;
    const c = job.chunks.find(x => x.status === "pending");
    if (!c) break;
    c.status = "running"; pintarLote();
    const texto = entrada.value.slice(c.start, c.end);
    const r = await genEnWorker(texto, 10, 15000);
    if (r.paused) { c.status = "pending"; break; }
    if (r.error && r.timeout && bisectar(c)) {
      await guardar(); pintarLote(); continue;
    }
    if (r.error) { c.status = "failed"; await guardar(); pintarLote(); continue; }
    const verificado = run(r.program).output === texto;
    c.status = "done";
    job.programs = job.programs || {};
    job.programs[c.start] = { end: c.end, cells: r.program.length, verified: verificado, program: r.program };
    await guardar(); pintarLote();
  }
  corriendo = false;
  pintarLote();
}

$("btnLote").addEventListener("click", async () => {
  const texto = entrada.value;
  if (!texto.trim()) { alert("carga o escribe texto primero"); return; }
  const size = +$("selChunk").value;
  const hash = await sha(texto);
  jobKey = hash + ":c" + size;
  job = await dbGet("job:" + jobKey);
  if (!job) {
    const total = Math.ceil(texto.length / size);
    job = {
      key: jobKey, chunkSize: size, textLen: texto.length, total,
      chunks: Array.from({ length: total }, (_, i) => ({
        i, start: i * size, end: Math.min((i + 1) * size, texto.length), status: "pending",
      })),
      programs: {},
    };
    await dbSet("job:" + jobKey, job);
  }
  pausado = false;
  pintarLote();
  procesarLote();
});

$("btnPausa").addEventListener("click", () => {
  pausado = true;
  if (currentId) getWorker().postMessage({ cmd: "pause", id: currentId });
  pintarLote();
});
$("btnReanuda").addEventListener("click", () => {
  if (!job) return;
  pausado = false;
  pintarLote();
  procesarLote();
});
$("btnDescarga").addEventListener("click", async () => {
  if (!job) { alert("sin trabajo activo"); return; }
  const man = await dbGet("job:" + jobKey);
  const bundle = {
    schema_version: 1, tool: "webolge",
    text_len: man.textLen, chunk_size: man.chunkSize,
    chunks: man.chunks.map(c => ({ start: c.start, end: c.end, status: c.status,
                                   verified: man.programs[c.start]?.verified ?? null })),
    programs: Object.entries(man.programs).map(([s, p]) => ({
      start: +s, end: p.end, cells: p.cells, verified: p.verified, program: p.program,
    })).sort((x, y) => x.start - y.start),
  };
  const dl = (blob, name) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name; a.click();
  };
  dl(new Blob([JSON.stringify(bundle, null, 1)], { type: "application/json" }), "webolge_job.json");
  const txt = bundle.programs.map(p =>
    `=== CHUNK ${p.start}..${p.end} (${p.cells} celdas, verified=${p.verified}) ===\n${p.program}`).join("\n\n");
  dl(new Blob([txt], { type: "text/plain" }), "webolge_programas.txt");
});
