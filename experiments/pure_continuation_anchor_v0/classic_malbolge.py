# SPDX-License-Identifier: MIT
"""
Instrumented Classic Malbolge interpreter (authoritative semantics).

Faithfully reproduces the canonical Classic Malbolge execution model used by
the ISyCo classic interpreter family (workspace/assembly/malbolge,
CoEvoLang, bridge_core, walbolge_holo):

    op = (mem[c] + c) % 94
    execute instruction
    if jumped: c = mem[d]
    if 33 <= mem[c] <= 126: mem[c] = _ENC[mem[c]]   # self-modification
    c = (c + 1) % 59049
    d = (d + 1) % 59049

The tape is FIXED at 3^10 = 59049 cells and BOTH pointers wrap modulo 59049.
The tail (cells after the program source) is filled by the crazy_op recurrence
in load_memory.

This instrumented variant additionally records, for every step:
  * registers (a, c, d)
  * the decoded instruction
  * every memory WRITE with its attribution:
      - "enc"   : post-instruction self-encryption (only if value in 33..126)
      - "crazy" : op 62 (p) writes mem[d] = crazy_op(a, mem[d])
      - "rotate": op 39 (*) writes mem[d] = rotate(mem[d])
  * whether the written cell value was printable (33..126) or not

It exists purely to build reproducible evidence (PURE_CONTINUATION_ANCHOR_V0);
it does NOT alter semantics in any way.

Vendored source hash (classic authority, sha256):
    e51f493c350c5a77...  (workspace/assembly/malbolge/malbolge_interpreter.py)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

MEM_SIZE = 3 ** 10  # 59049

_ORIGINAL = r"""!"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~"""
_TRANSLATED = r"""5z]&gqtyfr$(we4{WP)H-Zn,[%\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G"i@"""
_ENC = {ord(o): ord(t) for o, t in zip(_ORIGINAL, _TRANSLATED)}

# Canonical instruction-lookup table (reference_interpreter.c `xlat1`).
# Instruction char at position c is xlat1[(mem[c] - 33 + c) % 94].
_XLAT1 = (
    "+b(29e*j1VMEKLyC})8&m#~W>qxdRp0wkrUo[D7,XTcA\"lI"
    ".v%{gJh4G\\-=O@5`_3i<?Z';FNQuY]szf$!BS/|t:Pn6^Ha"
)
assert len(_XLAT1) == 94
# Canonical encryption table (reference_interpreter.c `xlat2`) == _TRANSLATED.
_XLAT2 = _TRANSLATED

_CRAZY = (
    (1, 0, 0),
    (1, 0, 2),
    (2, 2, 1),
)

INSTRUCTION_NAMES = {
    4: "jump",
    5: "out",
    23: "in",
    39: "rotate",
    40: "dload",
    62: "crazy",
    68: "nop",
    81: "halt",
}

# In classic Malbolge, opcodes whose (mem[c]+c)%94 value falls in this set are
# the real instructions; everything else is a NOP.
_REAL_OPCODES = frozenset((4, 5, 23, 39, 40, 62, 68, 81))


def crazy_op(x: int, y: int) -> int:
    res = 0
    p = 1
    for _ in range(10):
        res += _CRAZY[y % 3][x % 3] * p
        x //= 3
        y //= 3
        p *= 3
    return res


def load_memory(source: str) -> list:
    chars = [c for c in source if not c.isspace()]
    mem = [0] * MEM_SIZE
    for i, c in enumerate(chars):
        v = ord(c)
        if not (33 <= v <= 126):
            raise ValueError("non-printable source char at %s: %s" % (i, v))
        mem[i] = v
    for i in range(len(chars), MEM_SIZE):
        mem[i] = crazy_op(mem[i - 1], mem[i - 2])
    return mem


@dataclass(slots=True)
class MemoryWrite:
    """A single mutation to the tape, attributed to its mechanism."""

    step: int
    kind: str  # "enc" | "crazy" | "rotate"
    index: int
    old: int
    new: int
    target_printable_before: bool  # old in 33..126
    target_printable_after: bool   # new in 33..126


@dataclass(slots=True)
class StepRecord:
    step: int
    a: int
    c: int
    d: int
    op: int
    instruction: str
    cell: int            # mem[c] read this step
    jump_applied: bool
    output_byte: Optional[int]  # emitted this step, if any


@dataclass(slots=True)
class TraceResult:
    source: str
    program_len: int
    output: str
    steps: int
    status: str  # HALTED | MAX_STEPS | INVALID
    records: list[StepRecord] = field(default_factory=list)
    writes: list[MemoryWrite] = field(default_factory=list)
    initial_memory_hash: str = ""
    final_memory_hash: str = ""
    memory_in_range: bool = True
    peak_touched_index: int = 0

    def write_counts(self) -> dict[str, int]:
        counts = {"enc": 0, "crazy": 0, "rotate": 0}
        for w in self.writes:
            counts[w.kind] = counts.get(w.kind, 0) + 1
        return counts

    def nonprintable_write_counts(self) -> dict[str, int]:
        counts = {"enc": 0, "crazy": 0, "rotate": 0}
        for w in self.writes:
            if not w.target_printable_before:
                counts[w.kind] = counts.get(w.kind, 0) + 1
        return counts


def _sha256(mem: list) -> str:
    h = hashlib.sha256()
    for v in mem:
        h.update(v.to_bytes(2, "little"))  # values 0..59048 fit in uint16
    return h.hexdigest()


def run_traced(
    source: str,
    max_steps: int = 2_000_000,
    capture_writes: bool = True,
) -> TraceResult:
    """Run Classic Malbolge with full per-step trace and write attribution.

    Semantics are identical to the authoritative classic interpreter; the only
    addition is recording, never mutating state beyond the interpreter's own
    instructions.
    """
    try:
        mem = load_memory(source)
    except ValueError as exc:
        return TraceResult(source, 0, "", 0, "INVALID:%s" % exc)

    program_len = len([c for c in source if not c.isspace()])
    initial_hash = _sha256(mem)

    a = 0
    c = 0
    d = 0
    out: list[int] = []
    records: list[StepRecord] = []
    writes: list[MemoryWrite] = []
    steps = 0
    status = "MAX_STEPS"
    peak_touched = 0

    while steps < max_steps:
        steps += 1
        cell = mem[c]
        op = (cell + c) % 94
        instr = INSTRUCTION_NAMES.get(op, "nop")
        jumped = False
        c_target = 0

        if op == 4:  # jump
            c_target = mem[d]
            jumped = True
        elif op == 5:  # out
            out.append(a % 256)
        elif op == 23:  # in (no input provided -> -1 like classic EOF)
            a = -1
        elif op == 39:  # rotate
            v = mem[d]
            nv = (v // 3) + (v % 3) * (3 ** 9)
            if capture_writes:
                writes.append(
                    MemoryWrite(
                        steps, "rotate", d, v, nv,
                        33 <= v <= 126, 33 <= nv <= 126,
                    )
                )
            mem[d] = nv
            a = mem[d]
        elif op == 40:  # d = mem[d]
            d = mem[d]
        elif op == 62:  # crazy
            v = mem[d]
            nv = crazy_op(a, v)
            if capture_writes:
                writes.append(
                    MemoryWrite(
                        steps, "crazy", d, v, nv,
                        33 <= v <= 126, 33 <= nv <= 126,
                    )
                )
            mem[d] = nv
            a = mem[d]
        elif op == 68:  # nop
            pass
        elif op == 81:  # halt
            status = "HALTED"
            # record the step, then break
            records.append(
                StepRecord(steps, a, c, d, op, instr, cell, jumped,
                           out[-1] if out and op == 5 else None)
            )
            break
        # else: invalid opcode -> NOP (per spec)

        peak_touched = max(peak_touched, c, d, c_target if jumped else 0)

        records.append(
            StepRecord(steps, a, c, d, op, instr, cell, jumped,
                       out[-1] if out and op == 5 else None)
        )

        if jumped:
            c = c_target
        # self-modification: only if printable
        if 33 <= mem[c] <= 126:
            old = mem[c]
            nv = _ENC[mem[c]]
            if capture_writes:
                writes.append(
                    MemoryWrite(steps, "enc", c, old, nv, True, 33 <= nv <= 126)
                )
            mem[c] = nv
        c = (c + 1) % MEM_SIZE
        d = (d + 1) % MEM_SIZE

    final_hash = _sha256(mem)
    mem_in_range = all(0 <= v < 3 ** 10 for v in mem)
    return TraceResult(
        source=source,
        program_len=program_len,
        output="".join(chr(b) for b in out),
        steps=steps,
        status=status,
        records=records,
        writes=writes,
        initial_memory_hash=initial_hash,
        final_memory_hash=final_hash,
        memory_in_range=mem_in_range,
        peak_touched_index=peak_touched,
    )


def memory_state_at(trace: TraceResult, up_to_step: int) -> list:
    """Reconstruct the tape state at a given step boundary by replaying writes."""
    mem = load_memory(trace.source)
    for w in trace.writes:
        if w.step > up_to_step:
            break
        mem[w.index] = w.new
    return mem


def memory_hash_at(trace: TraceResult, up_to_step: int) -> str:
    return _sha256(memory_state_at(trace, up_to_step))


def run_fast(
    source: str,
    max_steps: int = 2_000_000,
    tail_filler: bool = True,
) -> tuple[str, int, str]:
    """Minimal classic runner for search loops: returns (output, steps, status).

    Semantics identical to run_traced but with no per-step recording and no
    tape hashing, so the brute-force search can evaluate many candidates.
    """
    chars = [c for c in source if not c.isspace()]
    mem = [0] * MEM_SIZE
    for i, c in enumerate(chars):
        mem[i] = ord(c)
    if tail_filler:
        for i in range(len(chars), MEM_SIZE):
            mem[i] = crazy_op(mem[i - 1], mem[i - 2])

    a = 0
    c = 0
    d = 0
    out: list[int] = []
    steps = 0
    while steps < max_steps:
        steps += 1
        cell = mem[c]
        op = (cell + c) % 94
        jumped = False
        c_target = 0
        if op == 4:
            c_target = mem[d]
            jumped = True
        elif op == 5:
            out.append(a % 256)
        elif op == 23:
            a = -1
        elif op == 39:
            v = mem[d]
            mem[d] = (v // 3) + (v % 3) * (3 ** 9)
            a = mem[d]
        elif op == 40:
            d = mem[d]
        elif op == 62:
            mem[d] = crazy_op(a, mem[d])
            a = mem[d]
        elif op == 81:
            return "".join(chr(x) for x in out), steps, "HALTED"
        if jumped:
            c = c_target
        if 33 <= mem[c] <= 126:
            mem[c] = _ENC[mem[c]]
        c = (c + 1) % MEM_SIZE
        d = (d + 1) % MEM_SIZE
    return "".join(chr(x) for x in out), steps, "MAX_STEPS"


# ---------------------------------------------------------------------------
# Canonical C reference semantics (reference_interpreter.c), reproduced for
# cross-interpreter comparison.
#
# Key divergence from the ISyCo classic family:
#   if (mem[c] < 33 || mem[c] > 126) continue;   <-- SPINS, does NOT advance
# The ISyCo classic family instead treats non-printable cells as NOP and
# advances c/d normally.
# ---------------------------------------------------------------------------


def run_canonical_reference(
    source: str,
    max_steps: int = 2_000_000,
    spin_detection_limit: int = 1_000_000,
) -> TraceResult:
    """Reproduce reference_interpreter.c semantics (spin on non-printable)."""
    mem = load_memory(source)
    program_len = len([c for c in source if not c.isspace()])
    initial_hash = _sha256(mem)
    a = 0
    c = 0
    d = 0
    out: list[int] = []
    writes: list[MemoryWrite] = []
    steps = 0
    status = "MAX_STEPS"

    while steps < max_steps:
        steps += 1
        v = mem[c]
        if not (33 <= v <= 126):
            # canonical: continue -> no advance, no encryption, re-read same cell
            if steps > spin_detection_limit:
                status = "SPIN_NONPRINTABLE"
                break
            continue
        idx = (v - 33 + c) % 94
        instr_char = _XLAT1[idx]
        if instr_char == "j":
            d = mem[d]
        elif instr_char == "i":
            c = mem[d]
        elif instr_char == "*":
            old = mem[d]
            mem[d] = mem[d] // 3 + (mem[d] % 3) * (3 ** 9)
            writes.append(
                MemoryWrite(steps, "rotate", d, old, mem[d],
                            33 <= old <= 126, 33 <= mem[d] <= 126)
            )
            a = mem[d]
        elif instr_char == "p":
            old = mem[d]
            mem[d] = crazy_op(a, mem[d])
            writes.append(MemoryWrite(steps, "crazy", d, old, mem[d], 33 <= old <= 126, 33 <= mem[d] <= 126))
            a = mem[d]
        elif instr_char == "<":
            out.append(a % 256)
        elif instr_char == "/":
            a = 59048  # EOF -> 59048
        elif instr_char == "v":
            status = "HALTED"
            break
        # 'o' and other chars: no-op, fall through to encryption

        mem[c] = ord(_XLAT2[mem[c] - 33])
        c = 0 if c == 59048 else c + 1
        d = 0 if d == 59048 else d + 1

    final_hash = _sha256(mem)
    mem_in_range = all(0 <= x < 3 ** 10 for x in mem)
    return TraceResult(
        source=source,
        program_len=program_len,
        output="".join(chr(x) for x in out),
        steps=steps,
        status=status,
        records=[],
        writes=writes,
        initial_memory_hash=initial_hash,
        final_memory_hash=final_hash,
        memory_in_range=mem_in_range,
        peak_touched_index=c,
    )