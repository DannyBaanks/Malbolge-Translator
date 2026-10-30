"""Versioned Python-search to Zig-execution snapshot contract."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import TYPE_CHECKING

from .fresh_vm_continuation import split_opcodes

if TYPE_CHECKING:
    from malbolge import MalbolgeMachine


MAGIC = b"MBS1"
SCHEMA = "malbolge-snapshot/1"
HEADER = struct.Struct("<4sIIIIB")
MAX_CELLS = 3**10


def encode_machine_snapshot(machine: "MalbolgeMachine") -> bytes:
    """Encode a toolkit machine snapshot for the Zig canonical consumer."""
    tape = machine.tape
    if not tape or len(tape) > MAX_CELLS:
        raise ValueError("snapshot tape length must be in 1..59049")
    if any(not isinstance(value, int) or not 0 <= value < MAX_CELLS for value in tape):
        raise ValueError("snapshot tape contains an invalid Classic Malbolge cell")
    if any(not isinstance(value, int) or not 0 <= value < MAX_CELLS for value in (machine.a, machine.c, machine.d)):
        raise ValueError("snapshot registers must be in 0..59048")
    return HEADER.pack(MAGIC, len(tape), machine.a, machine.c, machine.d, int(machine.halted)) + struct.pack(
        f"<{len(tape)}H", *tape
    )


def export_continuation_snapshot(opcodes: str, path: str | Path, split_at: int | None = None) -> dict:
    """Execute an opcode prefix in Python and export it for ``malbolge-zig resume``."""
    from malbolge import MalbolgeInterpreter

    prefix, suffix = split_opcodes(opcodes, split_at)
    result = MalbolgeInterpreter().execute(prefix, capture_machine=True)
    if result.machine is None:
        raise RuntimeError("Python interpreter did not return a machine snapshot")
    payload = encode_machine_snapshot(result.machine)
    destination = Path(path)
    destination.write_bytes(payload)
    return {
        "schema": SCHEMA,
        "path": str(destination),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "prefix_opcodes": len(prefix),
        "suffix_opcodes": suffix,
        "prefix_output": result.output,
        "snapshot_tape_len": len(result.machine.tape),
    }
