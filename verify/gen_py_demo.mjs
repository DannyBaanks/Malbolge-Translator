import { run } from "../src/malbolge-core.mjs";
import { generar } from "../src/meowbolge-gen.mjs";

const CODIGO = 'print("hola")';
const t0 = Date.now();
try {
  const prog = generar(CODIGO, { verbose: true, ancho: 10 });
  const r = run(prog);
  const ok = r.output === CODIGO && r.status === "HALTED";
  console.log(`GEN_CLIENTE ok=${ok} celdas=${prog.length} pasos=${r.steps} t=${Date.now() - t0}ms`);
  if (ok) {
    const fs = await import("node:fs");
    fs.writeFileSync("C:\\Users\\progr\\AppData\\Local\\Temp\\opencode\\py_print.mal", prog, "latin1");
    console.log("GUARDADO py_print.mal");
  }
  process.exit(ok ? 0 : 2);
} catch (e) {
  console.log(`GEN_CLIENTE fallo rapido (${Date.now() - t0}ms): ${e.message.slice(0, 80)}`);
  process.exit(1);
}
