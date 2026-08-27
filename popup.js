import { run } from "./src/malbolge-core.mjs";

const inp = document.getElementById("inp");
const meta = document.getElementById("meta");
const bGen = document.getElementById("bGen");
const bRun = document.getElementById("bRun");

let worker = null;
function getWorker() {
  if (!worker) worker = new Worker("./src/gen-worker.mjs", { type: "module" });
  return worker;
}

function generateInWorker(text, deadlineMs = 10_000) {
  return new Promise((resolve) => {
    const id = crypto.randomUUID();
    const w = getWorker();
    const onMessage = (ev) => {
      const d = ev.data || {};
      if (d.id !== id) return;
      if (d.type === "prog") {
        meta.textContent = `buscando rutas… ${d.i}/${d.total} · ${d.engine}`;
        return;
      }
      if (d.type === "beat") return;
      w.removeEventListener("message", onMessage);
      if (d.type === "done") resolve({ program: d.program, engine: d.engine });
      else resolve({ error: d.message || d.type });
    };
    w.addEventListener("message", onMessage);
    w.postMessage({ cmd: "gen", id, texto: text, ancho: 10, deadlineMs });
  });
}

bGen.addEventListener("click", async () => {
  const target = inp.value;
  if (!target.length) return;
  if ([...target].some((ch) => ch.codePointAt(0) > 255)) {
    meta.textContent = "fuera de rango: generador actual = Latin-1 (0..255)";
    return;
  }

  bGen.disabled = true;
  bRun.disabled = true;
  meta.textContent = "buscando rutas…";
  try {
    const g = await generateInWorker(target);
    if (g.error) throw new Error(g.error);
    const r = run(g.program, "", 2_000_000, { maxOutput: target.length + 1 });
    if (r.status !== "HALTED" || r.output !== target) {
      throw new Error(`verification mismatch: ${r.status}`);
    }
    inp.value = g.program;
    meta.textContent = `VERIFICADO · ${g.program.length} celdas · ${r.steps} pasos · ${g.engine}`;
  } catch (e) {
    meta.textContent = "error: " + (e.message || e);
  } finally {
    bGen.disabled = false;
    bRun.disabled = false;
  }
});

bRun.addEventListener("click", () => {
  try {
    const r = run(inp.value, "", 2_000_000, { maxOutput: 200_000 });
    inp.value = r.output + (r.status === "MAX_OUTPUT" ? "…[truncado]" : "");
    meta.textContent = `${r.status} · ${r.steps} pasos`;
  } catch (e) {
    meta.textContent = "error: " + e.message;
  }
});
