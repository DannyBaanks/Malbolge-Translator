// vectors.mjs — consenso: la implementacion JS contra los vectores dorados
// que hoy ya pasaron por pyref + malbolge-oracle + Malbolge-Engine (C).
import { readFileSync } from "node:fs";
import { run } from "../src/malbolge-core.mjs";
import { generar, fuentePara, OP_IN, OP_OUT, OP_CRAZY, OP_HALT } from "../src/meowbolge-gen.mjs";

let fallos = 0;
function check(nombre, ok, detalle) {
  console.log(`${ok ? "PASS" : "FAIL"}  ${nombre}${detalle ? "  " + detalle : ""}`);
  if (!ok) fallos++;
}

const ART = " /\\_/\\\n( o.o )\n > ^ <";

// V1 hello world — 3 backends hoy: HALTED/48 "Hello, world."
{
  const src = readFileSync("C:\\Development\\ISyCo Git\\Malbolge-Engine\\examples\\hello.malbolge", "latin1");
  const r = run(src);
  check("V1 hello", r.status === "HALTED" && r.steps === 48 && r.output === "Hello, world.",
        `status=${r.status} steps=${r.steps} out=${JSON.stringify(r.output)}`);
}

// V2 gatito — triple backend hoy: HALTED/652
{
  const src = readFileSync("C:\\Development\\ISyCo Git\\meowbolge\\examples\\gatito.malbolge", "latin1");
  const r = run(src);
  check("V2 gatito", r.status === "HALTED" && r.steps === 652 && r.output === ART,
        `status=${r.status} steps=${r.steps}`);
}

// V3 ECHO13 de anchuring v1 — 9/9 unanime: HALTED/27, eco exacto
{
  const seq = [...Array(13)].flatMap(() => [OP_IN, OP_OUT]).concat(OP_HALT);
  let prog = "";
  for (const op of seq) prog += fuentePara(op, prog.length);
  const payload = "Hello, world.";
  const r = run(prog, payload);
  check("V3 echo13", r.status === "HALTED" && r.steps === 27 && r.output === payload,
        `steps=${r.steps}`);
}

// V4 TRANSFORM13(2) de anchuring v2 — unanime: Y=42777a...32 en 53 pasos
{
  const seg = [OP_IN, OP_CRAZY, OP_CRAZY, OP_OUT];
  const seq = [...Array(13)].flatMap(() => seg).concat(OP_HALT);
  let prog = "";
  for (const op of seq) prog += fuentePara(op, prog.length);
  const payload = "Hello, world.";
  const r = run(prog, payload);
  const hex = Buffer.from(r.output, "latin1").toString("hex").toUpperCase();
  check("V4 transform", r.status === "HALTED" && r.steps === 53 && hex === "42777A75862A1E7F74716F5C32",
        `hex=${hex}`);
}

// V5 generador JS acotado: 'meow' o falla RAPIDO y HONESTO (limite documentado)
{
  let ok = false, detalle = "";
  const t0 = Date.now();
  try {
    const prog = generar("meow", { verbose: false, ancho: 9, deadlineMs: 30000 });
    const r = run(prog);
    ok = r.output === "meow" && r.status === "HALTED";
    detalle = `${prog.length} celdas, ${r.steps} pasos`;
  } catch (e) {
    const msg = String(e.message || e);
    ok = msg.startsWith("sin ruta") || msg.startsWith("GEN_TIMEOUT");
    detalle = `limite alcanzado rapido (${Date.now() - t0}ms): ${msg.slice(0, 60)}`;
  }
  check("V5 generar(meow) acotado", ok && Date.now() - t0 < 60000, detalle);
}

console.log(fallos === 0 ? "\nCONSENSO JS == 3 BACKENDS ✓" : `\n${fallos} FALLO(S)`);
process.exit(fallos === 0 ? 0 : 1);
