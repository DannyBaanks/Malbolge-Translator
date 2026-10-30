"""Formula-directed linear planner for Unshackled 3^19 output programs."""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

V0 = Path(__file__).resolve().parents[1] / "program_generator19_v0"
sys.path.insert(0, str(V0))
from program_generator19 import Interpreter19, lower  # noqa: E402


def recipes(max_transforms: int) -> list[str]:
    # Fixed transform catalogue. Search growth is bounded here, not recursive
    # over the entire generated program.
    return ["" ] + ["".join(p) for n in range(1, max_transforms + 1)
                     for p in itertools.product("p*", repeat=n)]


def plan(target: str, max_nops: int = 4096, max_transforms: int = 4):
    vm = Interpreter19()
    opcodes = "i" + "o" * 99
    base = vm.execute(opcodes, capture_machine=True)
    assert base.machine is not None and base.output == ""
    catalogue = recipes(max_transforms)
    evaluations = 0
    trace = []

    for index, wanted in enumerate(target):
        cursor = base
        chosen = None
        for nops in range(max_nops + 1):
            if nops:
                cursor = vm.execute_from_snapshot(
                    cursor.machine, "o", capture_machine=True)
                assert cursor.machine is not None
            for transform in catalogue:
                result = vm.execute_from_snapshot(
                    cursor.machine, transform + "<", capture_machine=True)
                evaluations += 1
                if result.output == wanted:
                    chosen = (nops, transform, result)
                    break
            if chosen is not None:
                break
        if chosen is None:
            raise RuntimeError(
                f"no recipe for index={index} byte={ord(wanted)} "
                f"within nops={max_nops}, transforms={max_transforms}")
        nops, transform, base = chosen
        opcodes += "o" * nops + transform + "<"
        trace.append({"index": index, "char": wanted, "byte": ord(wanted),
                      "nops": nops, "transform": transform,
                      "program_cells": len(opcodes)})
        print(f"byte[{index}]={ord(wanted):02x} nops={nops} "
              f"transform={transform!r} cells={len(opcodes)}")

    final = vm.execute_from_snapshot(base.machine, "v", capture_machine=True)
    opcodes += "v"
    return opcodes, evaluations, trace, final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--output", type=Path, default=Path("generated_hola19.mal"))
    parser.add_argument("--max-nops", type=int, default=4096)
    parser.add_argument("--max-transforms", type=int, default=4)
    args = parser.parse_args()
    opcodes, evaluations, trace, _ = plan(
        args.target, args.max_nops, args.max_transforms)
    args.output.write_bytes(bytes(lower(opcodes)))
    print(f"target={args.target!r}")
    print(f"opcodes={len(opcodes)}")
    print(f"evaluations={evaluations}")
    print(f"trace={trace!r}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
