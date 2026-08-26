// malbolge-core.mjs — puerto fiel del interprete canonico in-repo
// (workspace/assembly/malbolge/malbolge_interpreter.py, convencion op=(v+c)%94)
// Cuarta implementacion independiente para el consenso multi-backend.

export const MEM_SIZE = 59049;

const ORIGINAL = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~";
const TRANSLATED = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";

if (ORIGINAL.length !== 94 || TRANSLATED.length !== 94) {
  throw new Error("tablas XLAT corruptas");
}

const ENC = new Map();
for (let i = 0; i < 94; i++) ENC.set(ORIGINAL.charCodeAt(i), TRANSLATED.charCodeAt(i));

const CRAZY = [[1, 0, 0], [1, 0, 2], [2, 2, 1]];

export function crazyOp(x, y) {
  let res = 0, p = 1;
  for (let _ = 0; _ < 10; _++) {
    res += CRAZY[y % 3][x % 3] * p;
    x = Math.floor(x / 3);
    y = Math.floor(y / 3);
    p *= 3;
  }
  return res;
}

export function rot10(v) {
  return Math.floor(v / 3) + (v % 3) * 19683;
}

function isSpaceChar(code) {
  // espejo de str.isspace() para ASCII: espacio, \t \n \v \f \r
  return code === 32 || (code >= 9 && code <= 13);
}

export function loadMemory(source) {
  const mem = new Int32Array(MEM_SIZE);
  let n = 0;
  for (const ch of source) {
    const v = ch.codePointAt(0);
    if (isSpaceChar(v)) continue;
    if (v < 33 || v > 126) {
      return { mem: null, invalidAt: n };
    }
    mem[n++] = v;
  }
  for (let i = n; i < MEM_SIZE; i++) {
    const a = i - 1, b = ((i - 2) % MEM_SIZE + MEM_SIZE) % MEM_SIZE;
    mem[i] = crazyOp(mem[a], mem[b]);
  }
  return { mem, invalidAt: -1 };
}

const OP_JMP = 4, OP_OUT = 5, OP_IN = 23, OP_ROT = 39,
      OP_MOVD = 40, OP_CRAZY = 62, OP_NOP = 68, OP_HALT = 81;

export function encryptCell(v) {
  return (v >= 33 && v <= 126) ? ENC.get(v) : v;
}

export function run(source, stdinData = "", maxSteps = 2000000) {
  const { mem, invalidAt } = loadMemory(source);
  if (mem === null) {
    return { output: "", steps: 0, status: `INVALID:non-printable source char at ${invalidAt}` };
  }
  const stdinCodes = [];
  for (const ch of stdinData) stdinCodes.push(ch.codePointAt(0));
  let si = 0;
  let a = 0, c = 0, d = 0, steps = 0;
  const out = [];

  while (steps < maxSteps) {
    steps++;
    const cell = mem[c];
    const op = (cell + c) % 94;
    let jumped = false;

    switch (op) {
      case OP_JMP: {
        const t = mem[d];
        jumped = true;
        var cTarget = t;
        break;
      }
      case OP_OUT:
        out.push(a % 256);
        break;
      case OP_IN:
        a = si < stdinCodes.length ? stdinCodes[si++] : -1;
        break;
      case OP_ROT:
        mem[d] = rot10(mem[d]);
        a = mem[d];
        break;
      case OP_MOVD:
        d = mem[d];
        break;
      case OP_CRAZY:
        mem[d] = crazyOp(a, mem[d]);
        a = mem[d];
        break;
      case OP_NOP:
        break;
      case OP_HALT:
        return { output: latin1(out), steps, status: "HALTED" };
      default:
        break; // invalido = NOP segun la spec
    }

    if (jumped) c = cTarget;
    if (mem[c] >= 33 && mem[c] <= 126) mem[c] = ENC.get(mem[c]);
    c = (c + 1) % MEM_SIZE;
    d = (d + 1) % MEM_SIZE;
  }
  return { output: latin1(out), steps, status: "MAX_STEPS" };
}

function latin1(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i += 4096) {
    s += String.fromCharCode(...bytes.slice(i, i + 4096));
  }
  return s;
}
