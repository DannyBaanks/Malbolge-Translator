import { run } from "./src/malbolge-core.mjs";
import { generar } from "./src/meowbolge-gen.mjs";

const inp = document.getElementById("inp");
const meta = document.getElementById("meta");

document.getElementById("bGen").addEventListener("click", () => {
  meta.textContent = "buscando rutas…";
  setTimeout(() => {
    try {
      const prog = generar(inp.value, { ancho: 9 });
      inp.value = prog;
      meta.textContent = `ok: ${prog.length} celdas`;
    } catch (e) {
      meta.textContent = "sin ruta en modo cliente (texto difícil)";
    }
  }, 20);
});

document.getElementById("bRun").addEventListener("click", () => {
  try {
    const r = run(inp.value, "", 5_000_000);
    inp.value = r.output;
    meta.textContent = `${r.status} · ${r.steps} pasos`;
  } catch (e) {
    meta.textContent = "error: " + e.message;
  }
});
