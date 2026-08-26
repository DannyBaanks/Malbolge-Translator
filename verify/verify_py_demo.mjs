import { readFileSync, writeFileSync, copyFileSync } from "node:fs";
import { run } from "../src/malbolge-core.mjs";

const src = readFileSync("C:/Users/progr/AppData/Local/Temp/opencode/py_out/py_print_full.mal", "latin1");
const r = run(src);
const ok = r.output === 'print("hola")' && r.status === "HALTED";
console.log(`JS_CORE: ${r.status}/${r.steps} match=${ok}`);

if (ok) {
  copyFileSync("C:/Users/progr/AppData/Local/Temp/opencode/py_out/py_print_full.mal",
               "C:/Development/ISyCo Git/malbolge-translate/examples/python_print.malbolge");
  writeFileSync("C:/Development/ISyCo Git/malbolge-translate/examples/python_print_salida.txt",
                r.output, "latin1");
  console.log("guardado en examples/");
}
process.exit(ok ? 0 : 1);
