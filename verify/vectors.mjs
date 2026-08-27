// Suite portable: no depende de rutas privadas de C:\\Development.
import { readFileSync } from "node:fs";
import { run } from "../src/malbolge-core.mjs";
import { generateToolkit } from "../src/toolkit-gen.mjs";
import { fuentePara, OP_IN, OP_OUT, OP_CRAZY, OP_HALT } from "../src/meowbolge-gen.mjs";

let failures = 0;
function check(name, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  " + detail : ""}`);
  if (!ok) failures++;
}

// V1 artefacto real ya versionado en este repo.
{
  const src = readFileSync(new URL("../examples/python_print.malbolge", import.meta.url), "latin1");
  const r = run(src);
  check(
    "V1 python_print",
    r.status === "HALTED" && r.output === 'print("hola")',
    `status=${r.status} steps=${r.steps} out=${JSON.stringify(r.output)}`,
  );
}

// V2 ECHO13 — construcción determinista de 13 pares IN/OUT + halt.
{
  const seq = [...Array(13)].flatMap(() => [OP_IN, OP_OUT]).concat(OP_HALT);
  let prog = "";
  for (const op of seq) prog += fuentePara(op, prog.length);
  const payload = "Hello, world.";
  const r = run(prog, payload);
  check("V2 echo13", r.status === "HALTED" && r.output === payload, `steps=${r.steps}`);
}

// V3 TRANSFORM13(2) — vector estructural preservado.
{
  const seg = [OP_IN, OP_CRAZY, OP_CRAZY, OP_OUT];
  const seq = [...Array(13)].flatMap(() => seg).concat(OP_HALT);
  let prog = "";
  for (const op of seq) prog += fuentePara(op, prog.length);
  const payload = "Hello, world.";
  const r = run(prog, payload);
  const hex = Buffer.from(r.output, "latin1").toString("hex").toUpperCase();
  check(
    "V3 transform",
    r.status === "HALTED" && hex === "42777A75862A1E7F74716F5C32",
    `hex=${hex} steps=${r.steps}`,
  );
}

// V4 contrato que motivó v0.3: "hola" DEBE convertirse, no solo fallar rapido.
{
  const t0 = Date.now();
  try {
    const prog = generateToolkit("hola", { deadlineMs: 5000 });
    const r = run(prog, "", 1_000_000, { maxOutput: 5 });
    check(
      "V4 generar(hola)",
      r.status === "HALTED" && r.output === "hola",
      `${prog.length} celdas / ${r.steps} pasos / ${Date.now() - t0}ms`,
    );
  } catch (e) {
    check("V4 generar(hola)", false, `${e.name}: ${e.message}`);
  }
}

// V5 una cadena algo mayor: un solo programa, exact match.
{
  const target = "Hello, world.";
  const t0 = Date.now();
  try {
    const prog = generateToolkit(target, { deadlineMs: 5000 });
    const r = run(prog, "", 1_000_000, { maxOutput: target.length + 1 });
    check(
      "V5 generar(Hello, world.)",
      r.status === "HALTED" && r.output === target,
      `${prog.length} celdas / ${r.steps} pasos / ${Date.now() - t0}ms`,
    );
  } catch (e) {
    check("V5 generar(Hello, world.)", false, `${e.name}: ${e.message}`);
  }
}

console.log(failures === 0 ? "\nWEBOLGE PORTABLE SUITE ✓" : `\n${failures} FALLO(S)`);
process.exit(failures === 0 ? 0 : 1);
