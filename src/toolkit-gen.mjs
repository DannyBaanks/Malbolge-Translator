// SPDX-License-Identifier: MIT
// Browser/JS port of the ProgramGenerator strategy from wallstop/malbolge-toolkit.
// Original project: https://github.com/wallstop/malbolge-toolkit
// Original copyright: Copyright 2023 Eli Pinkerton (wallstop).
// See THIRD_PARTY_NOTICES.md in this repository.

import { run } from "./malbolge-core.mjs";

const NORMAL_TRANSLATE =
  "+b(29e*j1VMEKLyC})8&m#~W>qxdRp0wkrUo[D7,XTcA\"lI.v%{gJh4G\\-=O@5`_3i<?Z';FNQuY]szf$!BS/|t:Pn6^Ha";
const ENCRYPTION_TRANSLATE =
  "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";

const VALID = "i</*jpov";
const MAX_PROGRAM_LENGTH = 59049;
const SIGNATURE_TAPE_WIDTH = 8;

export class ToolkitTimeout extends Error {
  constructor(message = "GEN_TIMEOUT") {
    super(message);
    this.name = "ToolkitTimeout";
  }
}

export class ToolkitPaused extends Error {
  constructor(payload = {}) {
    super("GEN_PAUSED");
    this.name = "ToolkitPaused";
    this.payload = payload;
  }
}

function reverseNormalize(opcodes, startIndex = 0) {
  if (startIndex + opcodes.length > MAX_PROGRAM_LENGTH) {
    throw new Error("programa excede 59049 celdas");
  }
  let out = "";
  for (let offset = 0; offset < opcodes.length; offset++) {
    const opcode = opcodes[offset];
    const tableIndex = NORMAL_TRANSLATE.indexOf(opcode);
    if (tableIndex < 0 || !VALID.includes(opcode)) {
      throw new Error(`opcode normalizado invalido: ${JSON.stringify(opcode)}`);
    }
    const index = startIndex + offset;
    out += String.fromCharCode(((tableIndex - index) % 94 + 94) % 94 + 33);
  }
  return out;
}

function crazy(x, y) {
  const table = [[1, 0, 0], [1, 0, 2], [2, 2, 1]];
  let result = 0;
  let power = 1;
  for (let i = 0; i < 10; i++) {
    result += table[y % 3][x % 3] * power;
    x = Math.floor(x / 3);
    y = Math.floor(y / 3);
    power *= 3;
  }
  return result;
}

function rot10(value) {
  return Math.floor(value / 3) + (value % 3) * 19683;
}

function cloneMachine(machine) {
  return {
    tape: machine.tape.slice(),
    a: machine.a,
    c: machine.c,
    d: machine.d,
    halted: machine.halted,
  };
}

function ensureCapacity(machine, index) {
  if (index >= MAX_PROGRAM_LENGTH) throw new Error("limite de memoria Malbolge excedido");
  while (machine.tape.length <= index) {
    const n = machine.tape.length;
    let next;
    if (n >= 2) next = crazy(machine.tape[n - 2], machine.tape[n - 1]);
    else if (n === 1) next = crazy(machine.tape[0], machine.tape[0]);
    else next = 0;
    machine.tape.push(next);
  }
}

function instructionAt(machine, index) {
  ensureCapacity(machine, index);
  const value = machine.tape[index];
  return NORMAL_TRANSLATE[((value - 33 + index) % 94 + 94) % 94];
}

function executeLoaded(machine, programLength, maxSteps = 2_000_000) {
  machine.halted = false;
  let output = "";
  let steps = 0;

  while (!machine.halted) {
    if (steps++ >= maxSteps) throw new Error("limite de pasos del generador excedido");
    if (machine.c >= programLength) {
      machine.halted = true;
      break;
    }

    ensureCapacity(machine, machine.c);
    const instruction = instructionAt(machine, machine.c);

    if (instruction === "i") {
      ensureCapacity(machine, machine.d);
      machine.c = machine.tape[machine.d];
      ensureCapacity(machine, machine.c);
    } else if (instruction === "<") {
      output += String.fromCharCode(machine.a % 256);
    } else if (instruction === "/") {
      throw new Error("el generador no usa entrada stdin");
    } else if (instruction === "*") {
      ensureCapacity(machine, machine.d);
      machine.a = rot10(machine.tape[machine.d]);
      machine.tape[machine.d] = machine.a;
    } else if (instruction === "j") {
      ensureCapacity(machine, machine.d);
      machine.d = machine.tape[machine.d];
      ensureCapacity(machine, machine.d);
    } else if (instruction === "p") {
      ensureCapacity(machine, machine.d);
      machine.a = crazy(machine.a, machine.tape[machine.d]);
      machine.tape[machine.d] = machine.a;
    } else if (instruction === "v") {
      machine.halted = true;
    }
    // "o" is the generator's NOP/advance placeholder.

    ensureCapacity(machine, machine.c);
    const cell = machine.tape[machine.c];
    if (cell >= 33 && cell <= 126) {
      machine.tape[machine.c] = ENCRYPTION_TRANSLATE.charCodeAt(cell - 33);
    }
    machine.c += 1;
    machine.d += 1;
  }

  return { output, machine: cloneMachine(machine), steps };
}

function executeNormalized(opcodes) {
  const source = reverseNormalize(opcodes);
  const machine = {
    tape: [...source].map((ch) => ch.charCodeAt(0)),
    a: 0,
    c: 0,
    d: 0,
    halted: false,
  };
  return executeLoaded(machine, opcodes.length);
}

function extendState(state, suffix) {
  if (state.opcodes.length + suffix.length > MAX_PROGRAM_LENGTH) {
    throw new Error("programa generado excede 59049 celdas");
  }
  const machine = cloneMachine(state.machine);
  const prefixLength = machine.tape.length;
  const asciiSuffix = reverseNormalize(suffix, prefixLength);
  for (const ch of asciiSuffix) machine.tape.push(ch.charCodeAt(0));
  const result = executeLoaded(machine, prefixLength + suffix.length);
  return {
    opcodes: state.opcodes + suffix,
    output: state.output + result.output,
    machine: result.machine,
  };
}

function stateSignature(machine, fullA = false) {
  const tail = machine.tape.slice(-SIGNATURE_TAPE_WIDTH);
  return [
    machine.tape.length,
    fullA ? machine.a : machine.a % 256,
    machine.c,
    machine.d,
    ...tail,
  ].join(",");
}

function seededRandom(seed = 42) {
  let x = seed | 0;
  return () => {
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    return (x >>> 0) / 0x100000000;
  };
}

/**
 * Generate one printable Malbolge program whose exact output is `target`.
 *
 * The search operates on normalized Malbolge opcodes using a snapshot-based
 * generator, then the final printable program is verified again with Webolge's
 * independent canonical JS core before being returned.
 */
export function generateToolkit(target, opts = {}) {
  if (!target.length) throw new Error("texto vacio");
  if ([...target].some((ch) => ch.codePointAt(0) > 255)) {
    throw new Error("fuera de rango: el generador actual emite bytes Latin-1 (0..255)");
  }

  const {
    maxDepth = 5,
    randomSeed = 42,
    deadlineMs = 20_000,
    onProgress = null,
    shouldPause = null,
  } = opts;

  const started = Date.now();
  const expired = () => Date.now() - started > deadlineMs;
  const checkControl = (index) => {
    if (shouldPause?.()) throw new ToolkitPaused({ nextIndex: index });
    if (expired()) {
      throw new ToolkitTimeout(`GEN_TIMEOUT: ${target.length} bytes tras ${deadlineMs} ms`);
    }
  };

  const rng = seededRandom(randomSeed);
  const choices = "op*";
  const bootstrap = "i" + "o".repeat(99);
  const initial = executeNormalized(bootstrap);
  let state = { opcodes: bootstrap, output: initial.output, machine: initial.machine };

  const seenFallback = new Map([[stateSignature(state.machine, true), state.output.length]]);
  const seenCanonical = new Map([[stateSignature(state.machine, false), state.output.length]]);

  for (let index = 0; index < target.length; index++) {
    checkControl(index);
    const targetPrefix = target.slice(0, index + 1);
    let found = false;
    let combinations = [...choices];
    let depth = 0;

    while (!found) {
      checkControl(index);
      depth += 1;

      for (const candidate of combinations) {
        checkControl(index);
        const combined = extendState(state, candidate + "<");
        const fallback = stateSignature(combined.machine, true);
        const canonical = stateSignature(combined.machine, false);
        const outputLength = combined.output.length;
        const knownFallback = seenFallback.get(fallback);
        const knownCanonical = seenCanonical.get(canonical);
        const isNew = knownFallback === undefined || outputLength > knownFallback;
        const isNewCanonical = knownCanonical === undefined || outputLength > knownCanonical;
        const validPrefix = target.startsWith(combined.output) && outputLength <= target.length;

        if (validPrefix && combined.output === targetPrefix) {
          seenFallback.set(fallback, Math.max(knownFallback ?? 0, outputLength));
          seenCanonical.set(canonical, Math.max(knownCanonical ?? 0, outputLength));
          state = combined;
          found = true;
          break;
        }

        if (validPrefix && isNew) {
          seenFallback.set(fallback, outputLength);
          if (isNewCanonical) seenCanonical.set(canonical, outputLength);
        }
      }

      if (found) break;

      const next = [];
      for (const base of combinations) {
        for (const opcode of choices) next.push(base + opcode);
      }
      combinations = next;

      if (depth >= maxDepth && combinations.length) {
        const randomChoice = combinations[Math.floor(rng() * combinations.length)];
        const randomState = extendState(state, randomChoice);
        const fallback = stateSignature(randomState.machine, true);
        const canonical = stateSignature(randomState.machine, false);
        const outputLength = randomState.output.length;
        const knownFallback = seenFallback.get(fallback);
        const knownCanonical = seenCanonical.get(canonical);

        if (knownFallback === undefined || outputLength > knownFallback) {
          seenFallback.set(fallback, outputLength);
          if (knownCanonical === undefined || outputLength > knownCanonical) {
            seenCanonical.set(canonical, outputLength);
          }
          state = randomState;
        }
        combinations = [...choices];
        depth = 0;
      }
    }

    onProgress?.({ i: index + 1, total: target.length, cells: state.opcodes.length });
  }

  state = extendState(state, "v");
  const source = reverseNormalize(state.opcodes);

  // Independent acceptance gate: printable source must halt and emit exact bytes.
  const verification = run(source, "", 5_000_000, { maxOutput: target.length + 1 });
  if (verification.status !== "HALTED" || verification.output !== target) {
    throw new Error(
      `verificacion final fallo: status=${verification.status} output=${JSON.stringify(verification.output)}`,
    );
  }
  return source;
}
