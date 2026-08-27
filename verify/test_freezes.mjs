import { run } from "../src/malbolge-core.mjs";
import { generateToolkit } from "../src/toolkit-gen.mjs";

let failures = 0;
function check(name, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? "  " + detail : ""}`);
  if (!ok) failures++;
}

// CASO 1: "hola" ya no puede aprobar solo por timeout. Debe GENERAR y verificar.
{
  const t0 = Date.now();
  try {
    const program = generateToolkit("hola", { deadlineMs: 5000 });
    const r = run(program, "", 1_000_000, { maxOutput: 5 });
    check(
      "CASO-hola genera",
      r.status === "HALTED" && r.output === "hola" && Date.now() - t0 < 5000,
      `${program.length} celdas -> ${r.steps} pasos (${Date.now() - t0}ms)`,
    );
  } catch (e) {
    check("CASO-hola genera", false, `${e.name}: ${e.message}`);
  }
}

// CASO 2: un programa que antes podia emitir sin parar debe quedar acotado.
{
  const t0 = Date.now();
  const r = run("**oo*o**oo*oo*ppp<", "", 2_000_000, { maxOutput: 300_000 });
  const dt = Date.now() - t0;
  const ok = dt < 10000 && ["MAX_OUTPUT", "MAX_STEPS", "HALTED"].includes(r.status);
  check("CASO-ppp< acotado", ok, `status=${r.status} pasos=${r.steps} out=${r.output.length}B (${dt}ms)`);
}

process.exit(failures === 0 ? 0 : 1);
