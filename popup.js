import { run } from "./src/malbolge-core.mjs";
import { generar } from "./src/meowbolge-gen.mjs";

const inp = document.getElementById("inp");
const meta = document.getElementById("meta");

document.getElementById("bGen").addEventListener("click", () => {
  meta.textContent = "buscando rutas…";
  setTimeout(() => {
    try {
      const prog = generar(inp.value, { ancho: 8, deadlineMs: 8000 });
      inp.value = prog;
      meta.textContent = `ok: ${prog.length} celdas`;
    } catch (e) {
      meta.textContent = String(e.message || e).startsWith("GEN_TIMEOUT")
        ? "texto difícil: timeout del modo cliente"
        : "sin ruta en modo cliente";
    }
  }, 20);
});

document.getElementById("bRun").addEventListener("click", () => {
  try {
    const r = run(inp.value, "", 2_000_000, { maxOutput: 200_000 });
    inp.value = r.output + (r.status === "MAX_OUTPUT" ? "…[truncado]" : "");
    meta.textContent = `${r.status} · ${r.steps} pasos`;
  } catch (e) {
    meta.textContent = "error: " + e.message;
  }
});
