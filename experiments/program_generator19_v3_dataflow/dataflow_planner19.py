"""Parallel dataflow beam planner for straight-line Unshackled 3^19 code."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

V0 = Path(__file__).resolve().parents[1] / "program_generator19_v0"
sys.path.insert(0, str(V0))
from program_generator19 import (  # noqa: E402
    Interpreter19, XLAT, encode_opcode, lower, mcrz, mrot,
)

OPS = ("o", "p", "*")
OPCODE = {"o": 68, "p": 62, "*": 39, "<": 5, "v": 81}


@dataclass(frozen=True, slots=True)
class Node:
    a: int
    queue: tuple[int, ...]
    path: str


def encrypted_source(op: str, c: int) -> int:
    raw = encode_opcode(OPCODE[op], c)
    return ord(XLAT[raw]) if raw < len(XLAT) else raw


def step(node: Node, op: str, c: int) -> Node:
    operand = node.queue[0]
    if op == "p":
        new_a = mcrz(node.a, operand)
    elif op == "*":
        new_a = mrot(operand)
    else:
        new_a = node.a
    queue = node.queue[1:] + (encrypted_source(op, c),)
    return Node(new_a, queue, node.path + op)


def expand_chunk(payload):
    nodes, c = payload
    return [step(node, op, c) for node in nodes for op in OPS]


def score(node: Node, target: int) -> tuple[int, int, str]:
    def delta(value: int) -> int:
        value &= 255
        return min((value - target) & 255, (target - value) & 255)

    current = node.a & 255
    distance = delta(current)
    operand = node.queue[0]
    lookahead = min(
        distance,
        delta(mcrz(node.a, operand)),
        delta(mrot(operand)),
    )
    return lookahead, distance, node.path


def chunks(items: list[Node], count: int):
    size = max(1, (len(items) + count - 1) // count)
    return [items[i:i + size] for i in range(0, len(items), size)]


def apply_output(node: Node, c: int) -> Node:
    return Node(node.a, node.queue[1:] + (encrypted_source("<", c),), "")


def synthesize(target: str, workers: int, beam: int, max_depth: int):
    vm = Interpreter19()
    bootstrap = "i" + "o" * 99
    result = vm.execute(bootstrap, capture_machine=True)
    machine = result.machine
    assert machine is not None and machine.c - machine.d == 98
    state = Node(machine.a, tuple(machine.tape[machine.d:machine.c]), "")
    program = bootstrap
    trace = []
    total_expanded = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for index, char in enumerate(target):
            wanted = ord(char)
            frontier = [state]
            found = None
            for depth in range(1, max_depth + 1):
                c = len(program) + depth - 1
                batches = [(part, c) for part in chunks(frontier, workers * 2)]
                expanded = []
                for batch in pool.map(expand_chunk, batches):
                    expanded.extend(batch)
                total_expanded += len(expanded)
                reduced = {}
                for node in expanded:
                    key = (node.a, node.queue)
                    previous = reduced.get(key)
                    if previous is None or node.path < previous.path:
                        reduced[key] = node
                hits = [node for node in reduced.values() if node.a & 255 == wanted]
                if hits:
                    found = min(hits, key=lambda node: node.path)
                    break
                frontier = sorted(reduced.values(), key=lambda n: score(n, wanted))[:beam]
            if found is None:
                raise RuntimeError(f"no path for byte {index}={wanted} at depth {max_depth}")
            program += found.path
            output_c = len(program)
            program += "<"
            state = apply_output(found, output_c)
            trace.append({"index": index, "char": char, "byte": wanted,
                          "depth": len(found.path), "frontier": len(frontier),
                          "cells": len(program)})
            print(json.dumps(trace[-1], ensure_ascii=False), flush=True)

    program += "v"
    return program, trace, total_expanded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--output", type=Path, default=Path("generated_dataflow19.mal"))
    parser.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    parser.add_argument("--beam", type=int, default=20000)
    parser.add_argument("--max-depth", type=int, default=256)
    args = parser.parse_args()
    program, trace, expanded = synthesize(
        args.target, args.workers, args.beam, args.max_depth)
    args.output.write_bytes(bytes(lower(program)))
    print(f"target={args.target!r}")
    print(f"workers={args.workers}")
    print(f"cells={len(program)}")
    print(f"expanded={expanded}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
