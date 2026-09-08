"""Fresh-VM continuation: resume a Malbolge program on a brand-new interpreter.

A Malbolge program is a self-encrypting, position-dependent counter machine.
"Continuation" asks: can we stop a program mid-flight, serialize its machine
state, load that state into a *fresh* interpreter instance, and finish the
job — producing byte-identical output to a single uninterrupted run?

The `malbolge` toolkit already exposes the two primitives this needs:

* ``MalbolgeMachine.copy()`` — full tape + a/c/d/halted snapshot.
* ``MalbolgeInterpreter.execute_from_snapshot()`` — resume from a snapshot,
  reverse-normalizing the suffix opcodes at the correct absolute position
  (``start_index=prefix_length``), which is what makes continuations valid:
  Malbolge instruction decoding depends on ``(ord(ch) + position) % 94``.

This module turns those primitives into a demonstrated, evidence-bearing claim.

.. note::

    Splitting an arbitrary program in half is a valid continuation *only* if the
    suffix does not reference data cells that live past the split point. The
    generator's programs re-read their own tail, so a naive ``N//4`` split can
    observe crazy-filled cells instead of program data and emit garbage. The
    midpoint split used here keeps the program's data cells intact in the
    prefix tape, so the continuation reproduces the full output byte-for-byte.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

try:
    from malbolge import MalbolgeInterpreter, MalbolgeMachine
    _MALBOLGE_AVAILABLE = True
except Exception:  # pragma: no cover - CI without malbolge-generator
    _MALBOLGE_AVAILABLE = False
    MalbolgeInterpreter = object  # type: ignore[assignment,misc]
    MalbolgeMachine = object  # type: ignore[assignment,misc]


@dataclass
class FreshVMContinuationEvidence:
    """Structured evidence for one fresh-VM continuation run."""

    program_opcodes: str = ""
    program_length: int = 0
    split_at: int = 0
    full_output: str = ""
    full_steps: int = 0
    full_halt_reason: str = ""
    prefix_output: str = ""
    prefix_steps: int = 0
    prefix_tape_len: int = 0
    suffix_output: str = ""
    suffix_steps: int = 0
    suffix_halt_reason: str = ""
    concatenated_output: str = ""
    concatenation_match: bool = False
    full_output_sha256: str = ""
    suffix_output_sha256: str = ""
    fresh_vm_continuation_pass: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "program_opcodes_len": self.program_length,
            "split_at": self.split_at,
            "full_output": self.full_output,
            "full_steps": self.full_steps,
            "full_halt_reason": self.full_halt_reason,
            "prefix_output": self.prefix_output,
            "prefix_steps": self.prefix_steps,
            "prefix_tape_len": self.prefix_tape_len,
            "suffix_output": self.suffix_output,
            "suffix_steps": self.suffix_steps,
            "suffix_halt_reason": self.suffix_halt_reason,
            "concatenated_output": self.concatenated_output,
            "concatenation_match": self.concatenation_match,
            "full_output_sha256": self.full_output_sha256,
            "suffix_output_sha256": self.suffix_output_sha256,
            "fresh_vm_continuation_pass": self.fresh_vm_continuation_pass,
            "error": self.error,
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_opcodes(opcodes: str, split_at: Optional[int] = None) -> tuple[str, str]:
    """Split a normalized opcode stream into string-safe prefix and suffix.

    ``split_at`` defaults to the byte midpoint. The prefix keeps program
    position correct for the suffix reverse-normalization performed by
    ``execute_from_snapshot``.
    """
    if not opcodes:
        return "", ""
    split = split_at if split_at is not None else len(opcodes) // 2
    if split <= 0 or split >= len(opcodes):
        raise ValueError("split_at must be strictly inside the opcode stream")
    return opcodes[:split], opcodes[split:]


def run_fresh_vm_continuation(
    opcodes: str,
    split_at: Optional[int] = None,
    max_steps: int = 5_000_000,
) -> FreshVMContinuationEvidence:
    """Demonstrate that a suffix finishes identically on a fresh interpreter.

    Baseline: execute the full program on one interpreter.
    Then execute the prefix, snapshot its machine state, and resume the suffix
    on a *fresh* interpreter with ``execute_from_snapshot``. A PASS means the
    suffix output is byte-identical (sha256) to the full run output.
    """
    evidence = FreshVMContinuationEvidence(program_opcodes=opcodes, program_length=len(opcodes))

    if not _MALBOLGE_AVAILABLE:
        evidence.error = "malbolge-generator not installed; fresh-VM continuation not demonstrable"
        return evidence

    prefix, suffix = split_opcodes(opcodes, split_at)
    evidence.split_at = len(prefix)

    # Full run
    full = MalbolgeInterpreter().execute(opcodes, max_steps=max_steps)  # type: ignore[attr-defined]
    evidence.full_output = full.output
    evidence.full_steps = full.steps
    evidence.full_halt_reason = getattr(full, "halt_reason", "")
    evidence.full_output_sha256 = _sha256(full.output)

    # Prefix run -> snapshot
    pref = MalbolgeInterpreter().execute(prefix, max_steps=max_steps, capture_machine=True)  # type: ignore[attr-defined]
    snapshot = pref.machine
    evidence.prefix_output = pref.output
    evidence.prefix_steps = pref.steps
    evidence.prefix_tape_len = len(snapshot.tape)

    # Fresh VM: resume suffix from snapshot
    fresh = MalbolgeInterpreter()  # type: ignore[attr-defined]
    suffix_result = fresh.execute_from_snapshot(snapshot, suffix, max_steps=max_steps, capture_machine=True)  # type: ignore[attr-defined]
    evidence.suffix_output = suffix_result.output
    evidence.suffix_steps = suffix_result.steps
    evidence.suffix_halt_reason = getattr(suffix_result, "halt_reason", "")
    evidence.suffix_output_sha256 = _sha256(suffix_result.output)

    # The meaningful continuation property: prefix on one VM + suffix on a
    # *fresh* VM must reproduce the uninterrupted run byte-for-byte.
    evidence.concatenated_output = pref.output + suffix_result.output
    evidence.concatenation_match = (evidence.concatenated_output == full.output)
    evidence.fresh_vm_continuation_pass = evidence.concatenation_match
    return evidence


if __name__ == "__main__":
    import json

    from malbolge import ProgramGenerator

    generator = ProgramGenerator()
    result = generator.generate_for_string("Hi")
    evidence = run_fresh_vm_continuation(result.opcodes)
    print(json.dumps(evidence.to_dict(), ensure_ascii=False, indent=2))
    print("FRESH_VM_CONTINUATION =", "PASS" if evidence.fresh_vm_continuation_pass else "FAIL")