import { run } from "./src/malbolge-core.mjs";
import { generar } from "./src/meowbolge-gen.mjs";

const $ = (id) => document.getElementById(id);
const entrada = $("entrada"), salida = $("salida");
const badge = $("badge"), metaIn = $("metaIn"), metaOut = $("metaOut");
const analisis = $("analisis");

function setBadge(ok, txt) { badge.className = `badge ${ok ? "ok" : "err"}`; badge.textContent = txt; }

function parecePrograma(src) {
  // recorta whitespace pegado; un programa real no lleva espacios internos
  const t = src.trim();
  if (t.length < 8) return false;
  for (const ch of t) {
    const v = ch.codePointAt(0);
    if (v === 10 || v === 13 || v === 9 || v === 32 || v < 33 || v > 126) return false;
  }
  return true;
}

function sondeaPrograma(src) {
  // prueba rapida: si HALTA al correr, es programa (aunque su salida sea vacia)
  try {
    const r = run(src.trim(), "", 150_000, { maxOutput: 50_000 });
    return r.status === "HALTED";
  } catch { return false; }
}

function walbolgeLite(r) {
  if (!r.counts) return "—";
  let unicas = 0, maxV = 0, maxIdx = -1;
  for (let i = 0; i < r.counts.length; i++) {
    if (r.counts[i] > 0) {
      unicas++;
      if (r.counts[i] > maxV) { maxV = r.counts[i]; maxIdx = i; }
    }
  }
  const topN = [];
  const copia = Array.from(r.counts).map((v, i) => [i, v]).filter(p => p[1] > 0);
  copia.sort((x, y) => y[1] - x[1]);
  for (let k = 0; k < Math.min(3, copia.length); k++) topN.push(`#${copia[k][0]}×${copia[k][1]}`);
  return `celdas tocadas: ${unicas} | más calientes: ${topN.join("  ")}`;
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
        salida.value = r.output + (r.status === "MAX_OUTPUT" ? "\n…[salida truncada]" : "");
        metaIn.textContent = `${src.length} caracteres`;
        metaOut.textContent = `${r.steps} pasos`;
        setBadge(r.status === "HALTED", r.status);
        analisis.textContent =
          `estado: ${r.status}   pasos: ${r.steps}   salida: ${r.output.length} bytes\n` +
          walbolgeLite(r);
      } else {
        const prog = generar(src, { ancho: 10, deadlineMs: 15000 });
        salida.value = prog;
        metaIn.textContent = `${src.length} caracteres`;
        metaOut.textContent = `${prog.length} celdas`;
        setBadge(true, "PROGRAMA GENERADO");
        const r = run(prog);
        analisis.textContent =
          `verificación post-generación: ${r.status}/${r.steps} pasos\n` + walbolgeLite(r);
      }
    } catch (e) {
      salida.value = "";
      metaOut.textContent = "";
      const timeout = String(e.message || e).startsWith("GEN_TIMEOUT");
      setBadge(false, timeout ? "texto difícil (timeout)" : "sin ruta (modo cliente)");
      analisis.textContent = timeout
        ? "El generador cliente se rindió a tiempo para no congelar la página.\n" +
          "Los caracteres difíciles necesitan el modo servidor (fase 2)."
        : "error: " + (e.message || e);
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
  const esMal = /\.(mal|malb|malbolge|mb)$/i.test(f.name);
  $("modo").value = esMal ? "toText" : "auto";
});
