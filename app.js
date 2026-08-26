import { run } from "./src/malbolge-core.mjs";
import { generar } from "./src/meowbolge-gen.mjs";

const $ = (id) => document.getElementById(id);
const entrada = $("entrada"), salida = $("salida");
const badge = $("badge"), metaIn = $("metaIn"), metaOut = $("metaOut");

function setBadge(ok, txt) { badge.className = `badge ${ok ? "ok" : "err"}`; badge.textContent = txt; }

function parecePrograma(src) {
  if (src.length < 8) return false;
  // sin espacios/saltos y todo imprimible -> candidata a programa
  let raro = 0;
  for (const ch of src) {
    const v = ch.codePointAt(0);
    if (v === 10 || v === 13 || v === 9 || v === 32) return false;
    if (v < 33 || v > 126) raro++;
  }
  return raro === 0;
}

$("btnConvert").addEventListener("click", () => {
  const src = entrada.value;
  if (!src.trim()) return;
  const modo = $("modo").value;
  const btn = $("btnConvert");
  btn.disabled = true;
  setBadge(false, "");
  setTimeout(() => {
    const t0 = performance.now();
    try {
      const esProg =
        modo === "toText" ? true :
        modo === "toMal" ? false :
        parecePrograma(src);
      if (esProg) {
        const r = run(src, "", 5_000_000);
        salida.value = r.output;
        metaIn.textContent = `${src.length} caracteres`;
        metaOut.textContent = `${r.steps} pasos`;
        setBadge(r.status === "HALTED", r.status);
      } else {
        const prog = generar(src, { ancho: 10 });
        salida.value = prog;
        metaIn.textContent = `${src.length} caracteres`;
        metaOut.textContent = `${prog.length} celdas`;
        setBadge(true, "PROGRAMA GENERADO");
      }
    } catch (e) {
      salida.value = "";
      metaOut.textContent = "";
      setBadge(false, "sin ruta (modo cliente)");
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
