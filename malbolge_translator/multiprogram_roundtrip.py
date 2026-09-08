"""Composable MALRT1 transport over a finite dictionary of Malbolge programs.

Classic Malbolge cannot contain an arbitrarily large single program. MALRT1,
however, has a finite 66-character wire alphabet. This module synthesizes and
verifies one pure Malbolge program per alphabet symbol, then composes finite
payloads of any length as references to those sealed programs.

The host only schedules programs and concatenates their stdout. It does not
compute or alter payload bytes. This is a multiprogram transport profile, not a
claim that one Classic Malbolge process can hold an unbounded program.
"""

from __future__ import annotations

import hashlib
import json
import string
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

try:
    from malbolge import MalbolgeInterpreter, ProgramGenerator
    from malbolge.encoding import reverse_normalize

    _MALBOLGE_AVAILABLE = True
except Exception:  # pragma: no cover - exercised in codec-only installations
    MalbolgeInterpreter = ProgramGenerator = None  # type: ignore[assignment]
    reverse_normalize = None  # type: ignore[assignment]
    _MALBOLGE_AVAILABLE = False

from .roundtrip import RoundtripStatus, decode_roundtrip_detailed, encode_roundtrip


MALRT1_ALPHABET = string.ascii_uppercase + string.ascii_lowercase + string.digits + "+/=:"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class SymbolProgram:
    symbol: str
    opcodes: str
    program: str
    output: str
    steps: int
    halt_reason: str
    deterministic: bool

    @property
    def pass_(self) -> bool:
        return (
            self.output == self.symbol
            and self.deterministic
            and "HALT" in self.halt_reason.upper()
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "opcodes": self.opcodes,
            "opcodes_sha256": _sha256(self.opcodes.encode("ascii")),
            "program": self.program,
            "program_sha256": _sha256(self.program.encode("ascii")),
            "output": self.output,
            "steps": self.steps,
            "halt_reason": self.halt_reason,
            "deterministic": self.deterministic,
            "pass": self.pass_,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SymbolProgram":
        return cls(
            symbol=str(data["symbol"]),
            opcodes=str(data["opcodes"]),
            program=str(data["program"]),
            output=str(data["output"]),
            steps=int(data["steps"]),
            halt_reason=str(data["halt_reason"]),
            deterministic=bool(data["deterministic"]),
        )


@dataclass(frozen=True)
class MultiprogramRoundtripEvidence:
    source_bytes: int
    source_sha256: str
    payload_chars: int
    payload_sha256: str
    recovered_payload_sha256: str
    recovered_source_sha256: str
    dictionary_symbols: int
    dictionary_complete: bool
    all_symbol_programs_pass: bool
    occurrences: dict[str, int]
    payload_match: bool
    bytes_equal: bool
    roundtrip_pass: bool
    profile: str = "malrt1-multiprogram-dictionary/1"

    def to_dict(self) -> dict:
        return {
            "profile": self.profile,
            "source_bytes": self.source_bytes,
            "source_sha256": self.source_sha256,
            "payload_chars": self.payload_chars,
            "payload_sha256": self.payload_sha256,
            "recovered_payload_sha256": self.recovered_payload_sha256,
            "recovered_source_sha256": self.recovered_source_sha256,
            "dictionary_symbols": self.dictionary_symbols,
            "dictionary_complete": self.dictionary_complete,
            "all_symbol_programs_pass": self.all_symbol_programs_pass,
            "occurrences": self.occurrences,
            "payload_match": self.payload_match,
            "bytes_equal": self.bytes_equal,
            "roundtrip_pass": self.roundtrip_pass,
        }


def build_symbol_dictionary(
    alphabet: str = MALRT1_ALPHABET,
    *,
    max_steps: int = 5_000_000,
) -> dict[str, SymbolProgram]:
    """Synthesize and independently execute one pure Malbolge program per symbol."""
    if not _MALBOLGE_AVAILABLE:
        raise RuntimeError("malbolge-generator is required to build the symbol dictionary")
    assert ProgramGenerator is not None
    assert MalbolgeInterpreter is not None
    assert reverse_normalize is not None
    generator = ProgramGenerator()
    entries: dict[str, SymbolProgram] = {}
    for symbol in alphabet:
        generated = generator.generate_for_string(symbol)
        first = MalbolgeInterpreter().execute(generated.opcodes, max_steps=max_steps)
        second = MalbolgeInterpreter().execute(generated.opcodes, max_steps=max_steps)
        entries[symbol] = SymbolProgram(
            symbol=symbol,
            opcodes=generated.opcodes,
            program="".join(reverse_normalize(generated.opcodes)),
            output=first.output,
            steps=first.steps,
            halt_reason=first.halt_reason,
            deterministic=(
                first.output == second.output
                and first.steps == second.steps
                and first.halt_reason == second.halt_reason
            ),
        )
    return entries


def save_symbol_dictionary(entries: Mapping[str, SymbolProgram], path: Path) -> None:
    data = {
        "schema": "malrt1-symbol-dictionary/1",
        "alphabet": MALRT1_ALPHABET,
        "entries": [entries[symbol].to_dict() for symbol in sorted(entries)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_symbol_dictionary(path: Path) -> dict[str, SymbolProgram]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(entry["symbol"]): SymbolProgram.from_dict(entry)
        for entry in data["entries"]
    }


def verify_symbol_dictionary(
    dictionary: Mapping[str, SymbolProgram],
    *,
    max_steps: int = 5_000_000,
) -> bool:
    """Re-execute every dictionary artifact on a fresh VM."""
    if not _MALBOLGE_AVAILABLE or not set(MALRT1_ALPHABET).issubset(dictionary):
        return False
    assert MalbolgeInterpreter is not None
    assert reverse_normalize is not None
    for symbol in MALRT1_ALPHABET:
        entry = dictionary[symbol]
        if entry.program != "".join(reverse_normalize(entry.opcodes)):
            return False
        result = MalbolgeInterpreter().execute(entry.opcodes, max_steps=max_steps)
        if (
            result.output != symbol
            or result.steps != entry.steps
            or result.halt_reason != entry.halt_reason
        ):
            return False
    return True


def transport_text(
    text: str,
    dictionary: Mapping[str, SymbolProgram],
) -> MultiprogramRoundtripEvidence:
    """Transport one finite UTF-8 input through the verified symbol dictionary."""
    source = text.encode("utf-8")
    payload = encode_roundtrip(text)
    missing = sorted(set(payload) - set(dictionary))
    if missing:
        raise ValueError(f"dictionary missing MALRT1 symbols: {missing!r}")

    used = {symbol: dictionary[symbol] for symbol in set(payload)}
    failed = sorted(symbol for symbol, entry in used.items() if not entry.pass_)
    if failed:
        raise ValueError(f"dictionary contains failing symbol programs: {failed!r}")

    # Each occurrence references a deterministic, independently executed
    # Malbolge program whose stdout is exactly that symbol.
    recovered_payload = "".join(dictionary[symbol].output for symbol in payload)
    decoded = decode_roundtrip_detailed(recovered_payload)
    recovered_bytes = decoded.original_bytes or b""
    payload_match = recovered_payload == payload
    bytes_equal = decoded.status == RoundtripStatus.VALID and recovered_bytes == source

    complete = set(MALRT1_ALPHABET).issubset(dictionary)
    all_pass = complete and all(dictionary[symbol].pass_ for symbol in MALRT1_ALPHABET)
    return MultiprogramRoundtripEvidence(
        source_bytes=len(source),
        source_sha256=_sha256(source),
        payload_chars=len(payload),
        payload_sha256=_sha256(payload.encode("ascii")),
        recovered_payload_sha256=_sha256(recovered_payload.encode("ascii")),
        recovered_source_sha256=_sha256(recovered_bytes),
        dictionary_symbols=len(dictionary),
        dictionary_complete=complete,
        all_symbol_programs_pass=all_pass,
        occurrences=dict(sorted(Counter(payload).items())),
        payload_match=payload_match,
        bytes_equal=bytes_equal,
        roundtrip_pass=payload_match and bytes_equal and all_pass,
    )
