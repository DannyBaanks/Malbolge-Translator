"""malbolge_translator/conveyor.py - High-Performance Constructive Malbolge Synthesizer.

Integrated from Autobolge 2.0 (ISyCo Labs).
Synthesizes autonomous, self-contained Classic Malbolge programs that print
text specifications in O(N) time with ZERO brute-force search.

Architecture (Conveyor Synthesis):
1. High-Memory Quantum Jump:
   Algebraic jump c=0 -> 98 -> 99..107 computing target 3312 via
   crazy(rot^2(80), 72) = 3312, landing on c=3315 with d=121.
2. Conveyor Invariant (Delta c == Delta d):
   - Code segment: c in [3315, ...]
   - Data segment: d in [121, ...]
   - Sterile gap: 3,194 cells (C_START - D_START). Data must fit before 3315.
3. Constructive Emission Matrix:
   - 12 bytes (including '\\n'): 2 opcodes ('* <', V).
   - 83 printable bytes: 3 opcodes ('* p <', V1, V2).
   - '+' (ASCII 43): 4 opcodes ('* p p <', V1, V2, V3).
4. Clean termination 'v' (opcode 81) on exit with zero stdin reads.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

XLAT1 = (
    "+b(29e*j1VMEKLyC})8&m#~W>qxdRp0wkrUo[D7,XTcA\"lI"
    ".v%{gJh4G\\-=O@5`_3i<?Z';FNQuY]szf$!BS/|t:Pn6^Ha"
)
XLAT2 = (
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1C"
    "B6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
)

MEM_SIZE = 59049
POW9 = 19683
C_START = 3315
D_START = 121
STERILE_GAP = C_START - D_START  # 3,194 cells

_CRAZY_TRITS = (
    (1, 0, 0),
    (1, 0, 2),
    (2, 2, 1),
)


def crazy_op(x: int, y: int) -> int:
    """Classic Malbolge ternary crazy operator."""
    res = 0
    p = 1
    for _ in range(10):
        res += _CRAZY_TRITS[y % 3][x % 3] * p
        x //= 3
        y //= 3
        p *= 3
    return res


def rot_op(x: int) -> int:
    """Ternary right-rotate 10-trit word."""
    return (x // 3) + (x % 3) * POW9


def char_for(op_char: str, c: int) -> int:
    """Finds ASCII character at address c that decodes to op_char."""
    idx = XLAT1.index(op_char)
    return ((idx - (c % 94) + 94) % 94) + 33


# Build emission recipe dictionary for all printable ASCII + newline
RECIPES: Dict[int, Tuple] = {
    10: ("rot", 118),
    43: ("rot_crazy_crazy", 33, 54, 60),  # '+'
}

# Precompute single rotation and rot+crazy pairs (Autobolge constructive matrix)
for _v1 in range(33, 127):
    _r1 = rot_op(_v1)
    _b1 = _r1 % 256
    if _b1 not in RECIPES:
        RECIPES[_b1] = ("rot", _v1)
    for _v2 in range(33, 127):
        _b2 = crazy_op(_r1, _v2) % 256
        if _b2 not in RECIPES:
            RECIPES[_b2] = ("rot_crazy", _v1, _v2)


@dataclass
class ConveyorSynthesisResult:
    target: str
    program: str
    program_bytes: bytes
    opcode_count: int
    data_cells: int
    steps: int
    output: str
    elapsed_ms: float
    sha256: str
    verified: bool


def can_conveyor_fit(target: str) -> bool:
    """Checks if target text fits within Autobolge's sterile gap without search."""
    try:
        target_bytes = target.encode("latin-1")
    except UnicodeEncodeError:
        return False

    data_count = 0
    for b in target_bytes:
        if b not in RECIPES:
            return False
        rec = RECIPES[b]
        kind = rec[0]
        if kind == "rot":
            data_count += 2
        elif kind == "rot_crazy":
            data_count += 3
        elif kind == "rot_crazy_crazy":
            data_count += 4

    return (D_START + data_count) <= C_START


def conveyor_capacity() -> int:
    """Returns the maximum sterile gap cell count."""
    return STERILE_GAP


def run_classic_vm(
    program: bytes | str,
    stdin_input: bytes = b"",
    max_steps: int = 500_000,
) -> Tuple[str, int, bool]:
    """Pure-Python execution of Classic Malbolge VM.

    Returns:
        (stdout_str, steps, halted_cleanly)
    """
    if isinstance(program, str):
        prog = [ord(c) for c in program]
    else:
        prog = list(program)

    mem = [0] * MEM_SIZE
    for i in range(len(prog)):
        mem[i] = prog[i]
    for i in range(len(prog), MEM_SIZE):
        mem[i] = crazy_op(mem[i - 1], mem[i - 2])

    a = 0
    c = 0
    d = 0
    output = bytearray()
    steps = 0
    in_idx = 0
    halted = False

    while steps < max_steps:
        op = (mem[c] + c) % 94
        jumped = False
        c_target = 0

        if op == 81:  # halt
            halted = True
            break
        elif op == 4:  # jump
            c_target = mem[d]
            jumped = True
        elif op == 5:  # out
            output.append(a % 256)
        elif op == 23:  # in
            if in_idx < len(stdin_input):
                a = stdin_input[in_idx]
                in_idx += 1
            else:
                a = 59048  # EOF
        elif op == 39:  # rotr
            a = mem[d] = rot_op(mem[d])
        elif op == 40:  # mov d
            d = mem[d]
        elif op == 62:  # crz
            a = mem[d] = crazy_op(a, mem[d])
        elif op == 68:  # nop
            pass

        if jumped:
            c = c_target
        enc = mem[c]
        if 33 <= enc <= 126:
            mem[c] = ord(XLAT2[enc - 33])
        c = (c + 1) % MEM_SIZE
        d = (d + 1) % MEM_SIZE
        steps += 1

    return output.decode("latin-1", errors="replace"), steps, halted


def synthesize_conveyor(target: str, verify: bool = True) -> ConveyorSynthesisResult:
    """Synthesizes a standalone Classic Malbolge program using Autobolge conveyor layout.

    Runs in O(N) algebraic time (~2-4 ms).
    Raises ValueError if target cannot fit in sterile gap.
    """
    t0 = time.perf_counter()

    target_bytes = target.encode("latin-1")
    for b in target_bytes:
        if b not in RECIPES:
            raise ValueError(f"Byte {b} ({chr(b)!r}) is not in the emission recipes")

    code_ops: List[str] = []
    data_bytes: List[int] = []

    for b in target_bytes:
        rec = RECIPES[b]
        kind = rec[0]
        if kind == "rot":
            code_ops.extend(["*", "<"])
            data_bytes.extend([rec[1], ord("o")])
        elif kind == "rot_crazy":
            code_ops.extend(["*", "p", "<"])
            data_bytes.extend([rec[1], rec[2], ord("o")])
        elif kind == "rot_crazy_crazy":
            code_ops.extend(["*", "p", "p", "<"])
            data_bytes.extend([rec[1], rec[2], rec[3], ord("o")])

    code_ops.append("v")  # Clean HALT

    TOTAL_LEN = C_START + len(code_ops)
    data_cells = D_START + len(data_bytes)

    if data_cells > C_START:
        raise ValueError(
            f"target too long for conveyor layout: data needs {len(data_bytes)} cells from "
            f"D_START={D_START} (reaches {data_cells}), but code starts at C_START={C_START}. "
            f"Sterile gap is {STERILE_GAP} cells; reduce target length."
        )

    if TOTAL_LEN > MEM_SIZE:
        raise ValueError(f"Synthesized program length {TOTAL_LEN} exceeds {MEM_SIZE} Classic limit")

    prog = [ord("o")] * TOTAL_LEN

    # Portal jump from c=0 -> 98 (landing on 99):
    prog[0] = ord("b")
    prog[98] = ord("o")

    # Low-memory data pointers:
    prog[1] = 93
    prog[94] = ord("P")  # 80: Y1
    prog[95] = 93
    prog[96] = 73
    prog[74] = ord("H")  # 72: Y2 (crazy produces 3312)
    prog[75] = 73
    prog[76] = D_START - 1  # 120: target for j at c=3314 to initialize d=121!

    # Discriminator / jump sequence at c=99..107:
    prog[99] = char_for("j", 99)
    prog[100] = char_for("*", 100)
    prog[101] = char_for("j", 101)
    prog[102] = char_for("*", 102)
    prog[103] = char_for("o", 103)
    prog[104] = char_for("j", 104)
    prog[105] = char_for("p", 105)
    prog[106] = char_for("j", 106)
    prog[107] = char_for("i", 107)

    # Cushion and bridge at c=3312..3314:
    prog[3312] = ord("o")
    prog[3313] = char_for("o", 3313)
    prog[3314] = char_for("j", 3314)

    # Place data segment:
    for idx, db in enumerate(data_bytes):
        prog[D_START + idx] = db

    # Place code segment:
    for idx, opc in enumerate(code_ops):
        prog[C_START + idx] = char_for(opc, C_START + idx)

    prog_bytes = bytes(prog)
    prog_str = prog_bytes.decode("latin-1")

    actual_output = ""
    step_count = 0
    is_verified = False

    if verify:
        actual_output, step_count, halted = run_classic_vm(prog_bytes, max_steps=500_000)
        if actual_output != target or not halted:
            raise RuntimeError(
                f"Verification failed: expected {target!r}, got {actual_output!r}, halted={halted}"
            )
        is_verified = True

    elapsed = (time.perf_counter() - t0) * 1000.0
    sha256 = hashlib.sha256(prog_bytes).hexdigest()

    return ConveyorSynthesisResult(
        target=target,
        program=prog_str,
        program_bytes=prog_bytes,
        opcode_count=len(code_ops),
        data_cells=len(data_bytes),
        steps=step_count,
        output=actual_output,
        elapsed_ms=elapsed,
        sha256=sha256,
        verified=is_verified,
    )
