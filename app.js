import { run } from "./src/malbolge-core.mjs";

const $ = (id) => document.getElementById(id);
const entrada = $("entrada"), salida = $("salida");
const badge = $("badge"), metaIn = $("metaIn"), metaOut = $("metaOut");
const analisis = $("analisis");

const QUICK_MAX = 200;
const QUICK_DEADLINE_MS = 20_000;

function setBadge(ok, txt) {
  badge.className = `badge ${ok ? "ok" : "err"}`;
  badge.textContent = txt;
}

function latin1Representable(text) {
  return [...text].every((ch) => ch.codePointAt(0) <= 255);
}

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
  } catch {
    return false;
  }
}

/* ---------------- worker compartido: rapido + lotes ---------------- */

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
        if (p.kind === "quick") {
          analisis.textContent = `generando… ${d.i}/${d.total} bytes · ${d.charsDone} celdas · ${d.engine}`;
        } else {
          $("loteLabel").textContent =
            `chunk en curso: ${d.i}/${d.total} bytes · ${d.charsDone} celdas · ${d.engine}`;
        }
        return;
      }
      if (d.type === "beat") return;

      pendientes.delete(d.id);
      if (d.type === "done") p.res({ program: d.program, engine: d.engine });
      else if (d.type === "paused") p.res({ paused: true });
      else p.res({ error: d.message, timeout: !!d.timeout });
    };
  }
  return worker;
}

const genEnWorker = (texto, ancho, deadlineMs, kind = "quick") => new Promise((res) => {
  const id = crypto.randomUUID();
  currentId = id;
  pendientes.set(id, { res, kind });
  getWorker().postMessage({ cmd: "gen", id, texto, ancho, deadlineMs });
});

async function generarUno(texto) {
  const generated = await genEnWorker(texto, 10, QUICK_DEADLINE_MS, "quick");
  if (generated.paused) throw new Error("generacion pausada");
  if (generated.error) throw new Error(generated.error);

  const verification = run(generated.program, "", 5_000_000, { maxOutput: texto.length + 1 });
  if (verification.status !== "HALTED" || verification.output !== texto) {
    throw new Error(
      `verification mismatch: ${verification.status} / ${JSON.stringify(verification.output)}`,
    );
  }
  return { ...generated, verification };
}

/* ---------------- modo rapido: ahora SI hace texto -> Malbolge ---------------- */

$("btnConvert").addEventListener("click", async () => {
  const src = entrada.value;
  if (!src.length) return;

  const modo = $("modo").value;
  const btn = $("btnConvert");
  btn.disabled = true;
  setBadge(false, "");
  analisis.textContent = "procesando…";

  try {
    const esProg =
      modo === "toText" ? true :
      modo === "toMal" ? false :
      (parecePrograma(src) ? sondeaPrograma(src) : false);

    if (esProg) {
      const r = run(src, "", 2_000_000, { maxOutput: 300_000 });
      salida.value = r.output + (r.status === "MAX_OUTPUT" ? "\n…[truncada]" : "");
      metaIn.textContent = `${src.length} caracteres Malbolge`;
      metaOut.textContent = `${r.output.length} bytes · ${r.steps} pasos`;
      setBadge(r.status === "HALTED", r.status);
      analisis.textContent =
        `Malbolge → texto\nestado: ${r.status}\npasos: ${r.steps}\nsalida: ${r.output.length} bytes`;
      return;
    }

    if (!latin1Representable(src)) {
      throw new Error("el generador actual emite bytes Latin-1 (0..255); Unicode fuera de ese rango aun no esta soportado");
    }

    if (src.length > QUICK_MAX) {
      await iniciarLoteDesdeTexto(src);
      salida.value = "";
      metaIn.textContent = `${src.length} bytes`;
      metaOut.textContent = "trabajo por lotes";
      setBadge(true, "LOTE");
      analisis.textContent =
        `texto largo (${src.length} bytes): iniciado modo anti-freeze.\n` +
        `Cada chunk se genera y verifica como programa Malbolge independiente.`;
      return;
    }

    const g = await generarUno(src);
    salida.value = g.program;
    metaIn.textContent = `${src.length} bytes`;
    metaOut.textContent = `${g.program.length} celdas · ${g.verification.steps} pasos`;
    setBadge(true, "VERIFICADO");
    analisis.textContent =
      `texto → Malbolge\n` +
      `motor: ${g.engine}\n` +
      `programa: ${g.program.length} celdas\n` +
      `ejecucion: ${g.verification.status} / ${g.verification.steps} pasos\n` +
      `exact match: SI`;
  } catch (e) {
    salida.value = "";
    setBadge(false, "error");
    const msg = String(e.message || e);
    analisis.textContent = msg.startsWith("GEN_TIMEOUT")
      ? `sin ruta dentro del presupuesto actual. No se invento salida.\n${msg}`
      : `error: ${msg}`;
  } finally {
    btn.disabled = false;
  }
});

$("fileIn").addEventListener("change", async (ev) => {
  const f = ev.target.files[0];
  if (!f) return;
  const buf = await f.arrayBuffer();
  const texto = new TextDecoder("windows-1252").decode(buf);
  entrada.value = texto;
  metaIn.textContent = `${f.name} · ${texto.length} caracteres`;
});

/* ---------------- WEBOLGE: lotes con checkpoint ---------------- */

const MIN_CHUNK = 60;

function idbOpen() {
  return new Promise((res, rej) => {
    const r = indexedDB.open("webolge", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("kv");
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}

const dbSet = async (k, v) => {
  const db = await idbOpen();
  return new Promise((res, rej) => {
    const tx = db.transaction("kv", "readwrite");
    tx.objectStore("kv").put(v, k);
    tx.oncomplete = res;
    tx.onerror = () => rej(tx.error);
  });
};

const dbGet = async (k) => {
  const db = await idbOpen();
  return new Promise((res, rej) => {
    const q = db.transaction("kv", "readonly").objectStore("kv").get(k);
    q.onsuccess = () => res(q.result);
    q.onerror = () => rej(q.error);
  });
};

async function sha(s) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

let job = null, jobKey = null, corriendo = false, pausado = false;
const guardar = () => dbSet("job:" + jobKey, job);

function pintarLote() {
  if (!job) return;
  const done = job.chunks.filter((c) => c.status === "done").length;
  const failed = job.chunks.filter((c) => c.status === "failed").length;
  const pct = Math.round(done / Math.max(1, job.chunks.length) * 100);
  $("barra").style.width = pct + "%";
  $("loteLabel").textContent =
    `${done}/${job.chunks.length} chunks verificados · ${failed} fallidos · ${pct}% · tamaño=${job.chunkSize}` +
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
  job.chunks.forEach((x, j) => { x.i = j; });
  return true;
}

async function procesarLote() {
  if (!job || corriendo || pausado) return;
  corriendo = true;
  pintarLote();

  while (true) {
    if (pausado) break;
    const c = job.chunks.find((x) => x.status === "pending");
    if (!c) break;

    c.status = "running";
    pintarLote();
    const texto = entrada.value.slice(c.start, c.end);
    const r = await genEnWorker(texto, 10, 15_000, "batch");

    if (r.paused) {
      c.status = "pending";
      break;
    }
    if (r.error && r.timeout && bisectar(c)) {
      await guardar();
      pintarLote();
      continue;
    }
    if (r.error) {
      c.status = "failed";
      c.error = r.error;
      await guardar();
      pintarLote();
      continue;
    }

    const verification = run(r.program, "", 5_000_000, { maxOutput: texto.length + 1 });
    const verified = verification.status === "HALTED" && verification.output === texto;
    if (!verified) {
      c.status = "failed";
      c.error = `verification mismatch: ${verification.status}`;
      await guardar();
      pintarLote();
      continue;
    }

    c.status = "done";
    delete c.error;
    job.programs = job.programs || {};
    job.programs[c.start] = {
      end: c.end,
      cells: r.program.length,
      verified: true,
      engine: r.engine,
      program: r.program,
    };
    await guardar();
    pintarLote();
  }

  corriendo = false;
  pintarLote();
}

async function iniciarLoteDesdeTexto(texto) {
  if (!texto.length) throw new Error("carga o escribe texto primero");
  if (!latin1Representable(texto)) {
    throw new Error("modo lotes actual: solo bytes Latin-1 (0..255)");
  }

  const size = +$("selChunk").value;
  const hash = await sha(texto);
  jobKey = hash + ":c" + size;
  job = await dbGet("job:" + jobKey);

  if (!job) {
    const total = Math.ceil(texto.length / size);
    job = {
      key: jobKey,
      chunkSize: size,
      textLen: texto.length,
      total,
      chunks: Array.from({ length: total }, (_, i) => ({
        i,
        start: i * size,
        end: Math.min((i + 1) * size, texto.length),
        status: "pending",
      })),
      programs: {},
    };
    await dbSet("job:" + jobKey, job);
  }

  pausado = false;
  pintarLote();
  procesarLote();
}

$("btnLote").addEventListener("click", async () => {
  try {
    await iniciarLoteDesdeTexto(entrada.value);
  } catch (e) {
    setBadge(false, "error");
    analisis.textContent = "error: " + (e.message || e);
  }
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
  if (!job) {
    alert("sin trabajo activo");
    return;
  }

  const man = await dbGet("job:" + jobKey);
  const bundle = {
    schema_version: 2,
    tool: "webolge",
    note: "Cada programa de chunks[] es independiente; no concatenar como un unico .mal.",
    text_len: man.textLen,
    chunk_size: man.chunkSize,
    chunks: man.chunks.map((c) => ({
      start: c.start,
      end: c.end,
      status: c.status,
      error: c.error ?? null,
      verified: man.programs[c.start]?.verified ?? null,
    })),
    programs: Object.entries(man.programs || {}).map(([s, p]) => ({
      start: +s,
      end: p.end,
      cells: p.cells,
      verified: p.verified,
      engine: p.engine,
      program: p.program,
    })).sort((x, y) => x.start - y.start),
  };

  const dl = (blob, name) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  dl(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }), "webolge_job.json");
  const txt = bundle.programs.map((p) =>
    `=== CHUNK ${p.start}..${p.end} (${p.cells} celdas, verified=${p.verified}, engine=${p.engine}) ===\n${p.program}`,
  ).join("\n\n");
  dl(new Blob([txt], { type: "text/plain" }), "webolge_programas.txt");
});
