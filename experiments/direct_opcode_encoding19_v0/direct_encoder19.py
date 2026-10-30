"""Deterministic opcode-to-source assembler for fixed-width Malbolge 3^19."""
from __future__ import annotations

END = 3**19
THIRD = 3**18
VALID_OPCODES = frozenset((4, 5, 23, 39, 40, 62, 68, 81))

A1_OFF = 94 - ((END - 1) // 6 - 29524) % 94
A2_OFF = 94 - ((END - 1) // 3 - 59048) % 94
OFFSETS = (
    0,
    ((A1_OFF - THIRD) % 94) + 94,
    A2_OFF - ((2 * THIRD) % 94) + 94,
)


def region(c: int) -> int:
    if not 0 <= c < END:
        raise ValueError(f"c must be in 0..{END - 1}")
    return c // THIRD


def offset(c: int) -> int:
    return OFFSETS[region(c)]


def encode19(op: int, c: int) -> str:
    if op not in VALID_OPCODES:
        raise ValueError(f"op must be one of {sorted(VALID_OPCODES)}")
    residue = (op - c - offset(c)) % 94
    ascii_code = residue if residue >= 33 else residue + 94
    return chr(ascii_code)


def decode19(source_character: str, c: int) -> int:
    if len(source_character) != 1:
        raise ValueError("source_character must contain exactly one character")
    ascii_code = ord(source_character)
    if not 33 <= ascii_code <= 126:
        raise ValueError("source_character must be printable ASCII 33..126")
    return (ascii_code + c + offset(c)) % 94


def assemble19(ops, start_c: int = 0) -> str:
    ops = list(ops)
    if start_c < 0 or start_c + len(ops) > END:
        raise ValueError("opcode plan exceeds the 3^19 address space")
    return "".join(encode19(op, start_c + index)
                   for index, op in enumerate(ops))


def disassemble19(source: str, start_c: int = 0) -> list[int]:
    if start_c < 0 or start_c + len(source) > END:
        raise ValueError("source exceeds the 3^19 address space")
    return [decode19(char, start_c + index)
            for index, char in enumerate(source)]
