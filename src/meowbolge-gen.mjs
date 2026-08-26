// meowbolge-gen.mjs — puerto del generador meowbolge v2 (via rapida toroidal)
import { run, loadMemory, crazyOp, rot10, encryptCell, MEM_SIZE } from "./malbolge-core.mjs";

export const OP_OUT = 5, OP_IN = 23, OP_ROT = 39, OP_MOVD = 40, OP_CRAZY = 62, OP_HALT = 81;
const CANDIDATAS = [OP_ROT, OP_CRAZY, OP_MOVD];

const PROF_MAX = 20, NODO_MAX = 2_000_000, HAZ_MAX = 60_000, RUTAS_MAX = 500;

export function fuentePara(op, pos) {
  return String.fromCharCode(33 + (((op - pos - 33) % 94) + 94) % 94);
}

export function colaHalt(pos) {
  return fuentePara(OP_HALT, pos);
}

function* combinaciones(largo) {
  if (largo === 0) { yield []; return; }
  const total = Math.pow(CANDIDATAS.length, largo);
  for (let i = 0; i < total; i++) {
    const combo = [];
    let x = i;
    for (let j = 0; j < largo; j++) { combo.push(CANDIDATAS[x % 3]); x = Math.floor(x / 3); }
    yield combo;
  }
}

function proponerRutas(prefijo, objetivo, restrictPast, expirado = () => false) {
  const loaded = loadMemory(prefijo + colaHalt(prefijo.length));
  if (!loaded.mem) return [];
  const mem = loaded.mem;

  let a = 0, d = 0;
  for (let pos = 0; pos < prefijo.length; pos++) {
    const op = (mem[pos] + pos) % 94;
    if (op === OP_ROT) { mem[d] = rot10(mem[d]); a = mem[d]; }
    else if (op === OP_CRAZY) { mem[d] = crazyOp(a, mem[d]); a = mem[d]; }
    else if (op === OP_MOVD) { d = mem[d]; }
    mem[pos] = encryptCell(mem[pos]);
    d = (d + 1) % MEM_SIZE;
  }

  const desde = prefijo.length;
  let presupuesto = NODO_MAX;
  const metas = [];

  let frontera = [[a, d, []]];
  const vistos = new Set([`${a},${d}`]);
  for (let prof = 0; prof <= PROF_MAX; prof++) {
    const nueva = [];
    for (const [aAct, dAct, ruta] of frontera) {
      if (expirado()) return metas;
      const pos = desde + ruta.length;
      presupuesto--;
      for (const op of [OP_OUT, OP_ROT, OP_CRAZY, OP_MOVD]) {
        const ch = fuentePara(op, pos);
        const undo = [[pos, mem[pos]]];
        mem[pos] = ch.charCodeAt(0);
        let a2 = aAct, d2 = dAct, b2 = null;
        if (op === OP_OUT) {
          b2 = aAct % 256;
          if (b2 !== objetivo) { mem[pos] = undo[0][1]; continue; }
        } else if (op === OP_ROT) {
          const v = mem[dAct]; undo.push([dAct, v]);
          a2 = rot10(v); mem[dAct] = a2;
        } else if (op === OP_CRAZY) {
          const v = mem[dAct]; undo.push([dAct, v]);
          a2 = crazyOp(aAct, v); mem[dAct] = a2;
        } else {
          const destino = mem[dAct];
          if (destino >= pos && (restrictPast || destino <= pos + PROF_MAX + 4)) {
            mem[pos] = undo[0][1];
            continue;
          }
          d2 = destino;
        }
        mem[pos] = encryptCell(mem[pos]);
        const dSig = (d2 + 1) % MEM_SIZE;

        if (b2 !== null && b2 === objetivo) {
          metas.push([...ruta, op]);
          mem[pos] = undo[0][1];
          if (metas.length >= RUTAS_MAX) return metas;
          continue;
        }
        const clave = `${a2},${dSig}`;
        if (!vistos.has(clave)) { vistos.add(clave); nueva.push([a2, dSig, [...ruta, op]]); }
        for (let i = undo.length - 1; i >= 0; i--) mem[undo[i][0]] = undo[i][1];
      }
    }
    if (nueva.length === 0) break;
    frontera = nueva.slice(0, HAZ_MAX);
  }
  return metas;
}

function verificarRuta(fuente, ruta, objetivo) {
  let cand = fuente;
  for (const op of ruta) cand += fuentePara(op, cand.length);
  if (ruta[ruta.length - 1] !== OP_OUT) cand += fuentePara(OP_OUT, cand.length);
  return run(cand + colaHalt(cand.length)).output === objetivo ? cand : null;
}

export class GenTimeout extends Error {}
export class GenPaused extends Error {
  constructor(payload) {
    super("GEN_PAUSED");
    this.payload = payload;
  }
}

export function generar(texto, opts = {}) {
  const { rapido = true, ancho = 40, verbose = false, log = console.error,
          deadlineMs = Number.POSITIVE_INFINITY,
          onProgress = null, shouldPause = null } = opts;
  const t0 = Date.now();
  const expirado = () => Date.now() - t0 > deadlineMs;
  let fuente = "";
  for (let i = 0; i < texto.length; i++) {
    if (shouldPause && shouldPause()) {
      throw new GenPaused({ nextIndex: i, fuente });
    }
    if (expirado()) {
      throw new GenTimeout(
        `GEN_TIMEOUT: ${texto.length} chars, rindiendose en el ${i + 1} ` +
        `(${JSON.stringify(texto[i])}) tras ${deadlineMs} ms`);
    }
    const ch = texto[i];
    const objetivo = texto.slice(0, i + 1);
    let hallado = null, metodo = null;

    const candDirecto = fuente + fuentePara(OP_OUT, fuente.length);
    if (run(candDirecto + colaHalt(candDirecto.length)).output === objetivo) {
      hallado = candDirecto; metodo = "directo";
    }

    if (hallado === null && rapido) {
      const byteObj = texto.charCodeAt(i) % 256;
      outer:
      for (const restrict of [true, false]) {
        for (const ruta of proponerRutas(fuente, byteObj, restrict, expirado)) {
          const cand = verificarRuta(fuente, ruta, objetivo);
          if (cand !== null) { hallado = cand; metodo = "rapida"; break outer; }
        }
      }
    }

    if (hallado === null) {
      for (const combo of iterarBruta(ancho)) {
        if (expirado()) {
          throw new GenTimeout(
            `GEN_TIMEOUT: caracter ${JSON.stringify(ch)} (${i + 1}/${texto.length}) ` +
            `excedio ${deadlineMs} ms en modo cliente`);
        }
        let cand = fuente, ok = true;
        for (const op of combo) {
          const c = fuentePara(op, cand.length);
          if (c === null) { ok = false; break; }
          cand += c;
        }
        if (!ok) continue;
        cand += fuentePara(OP_OUT, cand.length);
        if (run(cand + colaHalt(cand.length)).output === objetivo) { hallado = cand; break; }
      }
      if (hallado === null) throw new Error(`sin ruta para ${JSON.stringify(ch)} (caracter ${i})`);
      metodo = "bruta";
    }
    fuente = hallado;
    if (onProgress) onProgress({ i: i + 1, total: texto.length, fuente });
    if (verbose) log(`  [${i + 1}/${texto.length}] ${JSON.stringify(ch)} -> ${fuente.length} celdas (${metodo})`);
  }
  return fuente + colaHalt(fuente.length);
}

function* iterarBruta(ancho) {
  for (let largo = 0; largo < ancho; largo++) yield* combinaciones(largo);
}
