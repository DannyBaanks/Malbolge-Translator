import { run } from "./src/malbolge-core.mjs";
import { generar } from "./src/meowbolge-gen.mjs";

const $ = (id) => document.getElementById(id);
const txtHumano = $("txtHumano"), txtMalbolge = $("txtMalbolge"), txtSalida = $("txtSalida");
const btnGen = $("btnGen"), btnRun = $("btnRun"), btnSwap = $("btnSwap");
const genMeta = $("genMeta"), runMeta = $("runMeta"), outBadge = $("outBadge");

function setBadge(el, ok, texto) {
  el.className = `badge ${ok ? "ok" : "err"}`;
  el.textContent = texto;
}

function copiar(texto) { return navigator.clipboard.writeText(texto); }

btnGen.addEventListener("click", () => {
  const texto = txtHumano.value;
  if (!texto) return;
  btnGen.disabled = true;
  genMeta.textContent = "buscando rutas…";
  setBadge(outBadge, false, "");
  setTimeout(() => {
    const t0 = performance.now();
    try {
      const prog = generar(texto, { ancho: 10 });
      txtMalbolge.value = prog;
      const dt = Math.round(performance.now() - t0);
      genMeta.textContent = `${prog.length} celdas · ${dt} ms`;
    } catch (e) {
      genMeta.textContent = "";
      alert("El generador cliente no encontró ruta para este texto.\n\n" +
            "Límite honesto del modo local (los caracteres difíciles requieren el modo servidor).\n\n" + e.message);
    }
    btnGen.disabled = false;
  }, 30);
});

btnRun.addEventListener("click", () => {
  const prog = txtMalbolge.value;
  if (!prog.trim()) return;
  btnRun.disabled = true;
  setTimeout(() => {
    const t0 = performance.now();
    try {
      const stdinData = ""; // v1 sin entrada; fase 2 agrega campo de stdin
      const r = run(prog, stdinData, 5_000_000);
      txtSalida.value = r.output;
      const dt = Math.round(performance.now() - t0);
      runMeta.textContent = `${r.steps} pasos · ${dt} ms`;
      const halted = r.status === "HALTED";
      setBadge(outBadge, halted, halted ? "HALTED" : r.status);
    } catch (e) {
      txtSalida.value = String(e);
      setBadge(outBadge, false, "ERROR");
    }
    btnRun.disabled = false;
  }, 30);
});

btnSwap.addEventListener("click", async () => {
  const t = txtHumano.value;
  txtHumano.value = txtSalida.value || txtHumano.value;
  txtSalida.value = t;
});

// doble-click en programa -> ejecutar rapido
txtMalbolge.addEventListener("dblclick", () => btnRun.click());
