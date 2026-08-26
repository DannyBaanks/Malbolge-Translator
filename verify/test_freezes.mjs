import { run } from "../src/malbolge-core.mjs";
import { generar, GenTimeout } from "../src/meowbolge-gen.mjs";

// CASO 1: "hola" — antes congelaba la UI
{
  const t0 = Date.now();
  let msg = "", ok = false;
  try {
    const prog = generar("hola", { ancho: 10, deadlineMs: 15000 });
    const r = run(prog);
    ok = r.output === "hola";
    msg = `generado! ${prog.length} celdas -> ${r.steps} pasos`;
  } catch (e) {
    ok = e instanceof GenTimeout && (Date.now() - t0) < 20000;
    msg = `timeout honesto en ${Date.now() - t0}ms: ${String(e.message).slice(0, 70)}`;
  }
  console.log(`${ok ? "PASS" : "FAIL"} CASO-hola (${Date.now() - t0}ms) ${msg}`);
}

// CASO 2: programa del usuario que emitia sin parar
{
  const t0 = Date.now();
  const r = run("**oo*o**oo*oo*ppp<", "", 2_000_000, { maxOutput: 300_000 });
  const dt = Date.now() - t0;
  const ok = dt < 10000 && ["MAX_OUTPUT", "MAX_STEPS", "HALTED"].includes(r.status);
  console.log(`${ok ? "PASS" : "FAIL"} CASO-ppp< status=${r.status} pasos=${r.steps} out=${r.output.length}B (${dt}ms)`);
}
