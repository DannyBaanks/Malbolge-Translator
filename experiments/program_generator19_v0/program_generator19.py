"""Experimental ProgramGenerator adapter for Malbolge Unshackled 3^19.

The search algorithm comes from the installed malbolge-generator package; the
machine, snapshots and positional lowering below are independent 3^19 code.
V0 intentionally targets the smallest falsifiable gate: synthesize ``A``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from malbolge import GenerationConfig, ProgramGenerator

END = 3**19
THIRD = 3**18
U32_MASK = 0xFFFF_FFFF
NORMAL_TO_OPCODE = {"i": 4, "<": 5, "/": 23, "*": 39,
                    "j": 40, "p": 62, "o": 68, "v": 81}
XLAT = ("SOMEBODY MAKE ME FEEL ALIVE[hj9>,"
        "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|"
        "jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@AND SHATTER ME")
CRAZY3 = ((1, 0, 0), (1, 0, 2), (2, 2, 1))
CRZ2 = (
    4,3,3,1,0,0,1,0,0,9,9,9,9,9,9,9, 4,3,5,1,0,2,1,0,2,9,9,9,9,9,9,9,
    5,5,4,2,2,1,2,2,1,9,9,9,9,9,9,9, 4,3,3,1,0,0,7,6,6,9,9,9,9,9,9,9,
    4,3,5,1,0,2,7,6,8,9,9,9,9,9,9,9, 5,5,4,2,2,1,8,8,7,9,9,9,9,9,9,9,
    7,6,6,7,6,6,4,3,3,9,9,9,9,9,9,9, 7,6,8,7,6,8,4,3,5,9,9,9,9,9,9,9,
    8,8,7,8,8,7,5,5,4,9,9,9,9,9,9,9,
)


def offsets() -> tuple[int, int, int]:
    a1 = 94 - ((END - 1) // 6 - 29524) % 94
    a2 = 94 - ((END - 1) // 3 - 59048) % 94
    return 0, (a1 - THIRD) % 94 + 94, a2 - (2 * THIRD) % 94 + 94


OFFSETS = offsets()


def encode_opcode(opcode: int, position: int) -> int:
    residue = (opcode - position - OFFSETS[position // THIRD]) % 94
    return residue if residue >= 33 else residue + 94


def lower(opcodes: Sequence[str], start: int = 0) -> list[int]:
    return [encode_opcode(NORMAL_TO_OPCODE[op], start + i)
            for i, op in enumerate(opcodes)]


def mcrz(a: int, d: int) -> int:
    result, place = 0, 1
    for _ in range(9):
        result = (result + place * CRZ2[(a % 9) + 16 * (d % 9)]) & U32_MASK
        a //= 9
        d //= 9
        place *= 9
    return (result + place * CRAZY3[d % 3][a % 3]) & U32_MASK


def mrot(value: int) -> int:
    low = value % THIRD
    return ((low // 3) + (low % 3) * (THIRD // 3) + value - low) & U32_MASK


@dataclass
class Machine19:
    tape: list[int]
    a: int = 0
    c: int = 0
    d: int = 0
    halted: bool = False
    derived: list[int] | None = None

    def copy(self) -> "Machine19":
        return Machine19(self.tape.copy(), self.a, self.c, self.d,
                         self.halted, None if self.derived is None else self.derived.copy())

    def get(self, index: int) -> int:
        if index < len(self.tape):
            return self.tape[index]
        if self.derived is None:
            self.derived = []
        while len(self.tape) + len(self.derived) <= index:
            absolute = len(self.tape) + len(self.derived)
            p1 = self.get(absolute - 1) if absolute else 0
            p2 = self.get(absolute - 2) if absolute > 1 else 0
            self.derived.append(mcrz(p1, p2))
        return self.derived[index - len(self.tape)]

    def set(self, index: int, value: int) -> None:
        if index < len(self.tape):
            self.tape[index] = value & U32_MASK
            return
        self.get(index)
        assert self.derived is not None
        self.derived[index - len(self.tape)] = value & U32_MASK


@dataclass
class Result19:
    output: str
    machine: Machine19 | None


class Interpreter19:
    def execute(self, opcodes: Sequence[str], *, input_buffer: Iterable[str] | None = None,
                max_steps: int | None = None, capture_machine: bool = False) -> Result19:
        machine = Machine19(lower(opcodes))
        return self._run(machine, len(opcodes), input_buffer, max_steps, capture_machine)

    def execute_from_snapshot(self, snapshot: Machine19, suffix_opcodes: Sequence[str], *,
                              input_buffer: Iterable[str] | None = None,
                              max_steps: int | None = None,
                              capture_machine: bool = False) -> Result19:
        machine = snapshot.copy()
        start = len(machine.tape)
        machine.tape.extend(lower(suffix_opcodes, start))
        machine.derived = None
        machine.halted = False
        return self._run(machine, len(machine.tape), input_buffer, max_steps, capture_machine)

    def _run(self, machine: Machine19, program_length: int,
             input_buffer: Iterable[str] | None, max_steps: int | None,
             capture_machine: bool) -> Result19:
        output: list[str] = []
        inputs = iter(input_buffer or ())
        steps = 0
        while not machine.halted and machine.c < program_length:
            if max_steps is not None and steps >= max_steps:
                raise RuntimeError("step limit")
            c0 = machine.c
            value = machine.get(c0)
            op = (value + c0 + OFFSETS[c0 // THIRD]) % 94
            if op == 4:
                machine.c = machine.get(machine.d) % END
            elif op == 5:
                output.append(chr(machine.a & 255))
            elif op == 23:
                item = next(inputs, None)
                machine.a = ord(item[0]) if item else END - 1
            elif op == 39:
                machine.a = mrot(machine.get(machine.d)); machine.set(machine.d, machine.a)
            elif op == 40:
                machine.d = machine.get(machine.d) % END
            elif op == 62:
                machine.a = mcrz(machine.a, machine.get(machine.d)); machine.set(machine.d, machine.a)
            elif op == 81:
                machine.halted = True
            current = machine.get(c0)
            if current < len(XLAT):
                machine.set(c0, ord(XLAT[current]))
            machine.c = (machine.c + 1) % END
            machine.d = (machine.d + 1) % END
            steps += 1
        return Result19("".join(output), machine.copy() if capture_machine else None)


def generate(target: str, seed: int = 0):
    config = GenerationConfig(opcode_choices="op*", max_search_depth=5,
                              random_seed=seed, max_program_length=1_000_000)
    return ProgramGenerator(interpreter=Interpreter19()).generate_for_string(
        target, config=config)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", default="A")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path("generated_A19.mal"))
    args = parser.parse_args()
    result = generate(args.target, args.seed)
    source = bytes(lower(result.opcodes))
    args.output.write_bytes(source)
    print(f"target={args.target!r}")
    print(f"opcodes={len(result.opcodes)}")
    print(f"machine_output={result.machine_output!r}")
    print(f"evaluations={result.stats['evaluations']}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
