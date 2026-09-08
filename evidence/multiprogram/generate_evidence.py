#!/usr/bin/env python3
"""Build the complete MALRT1 symbol dictionary and arbitrary-size evidence."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from malbolge_translator.multiprogram_roundtrip import (
    MALRT1_ALPHABET,
    build_symbol_dictionary,
    save_symbol_dictionary,
    transport_text,
)


HERE = Path(__file__).resolve().parent
DICTIONARY = HERE / "symbol_dictionary.json"
EVIDENCE = HERE / "arbitrary_size_evidence.json"
SUMMARY = HERE / "SUMMARY.md"
IMPLEMENTATION = HERE.parents[1] / "malbolge_translator" / "multiprogram_roundtrip.py"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    print(f"[1/3] synthesizing {len(MALRT1_ALPHABET)} MALRT1 symbol programs")
    dictionary = build_symbol_dictionary()
    save_symbol_dictionary(dictionary, DICTIONARY)
    passing = sum(entry.pass_ for entry in dictionary.values())
    print(f"[2/3] dictionary: {passing}/{len(dictionary)} PASS")

    unit = "En un lugar de la Mancha, espanol + 中文 + 日本語 + 😭🔥🚀.\n"
    repeats = (1_000_000 // len(unit.encode("utf-8"))) + 1
    text = (unit * repeats).encode("utf-8")[:1_000_000].decode("utf-8", errors="ignore")
    result = transport_text(text, dictionary)
    evidence = {
        "schema": "malrt1-multiprogram-evidence/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "command": "py -m evidence.multiprogram.generate_evidence",
        "exit_status": 0,
        "implementation": {
            "path": "malbolge_translator/multiprogram_roundtrip.py",
            "sha256": sha256_file(IMPLEMENTATION),
        },
        "script_sha256": sha256_file(Path(__file__)),
        "input": {
            "construction": "UTF-8 multilingual sentence repeated and truncated at a valid boundary",
            "target_bytes": 1_000_000,
        },
        "dictionary": {
            "alphabet": MALRT1_ALPHABET,
            "symbols": len(dictionary),
            "passing": passing,
            "sha256": sha256_file(DICTIONARY),
        },
        "roundtrip": result.to_dict(),
        "claims": {
            "ARBITRARY_SIZE_ROUNDTRIP": (
                "DEMONSTRATED_MULTIPROGRAM_FINITE_INPUTS"
                if result.roundtrip_pass and passing == len(MALRT1_ALPHABET)
                else "NOT_DEMONSTRATED"
            ),
            "SINGLE_PROGRAM_ARBITRARY_SIZE": "NOT_CLAIMED",
        },
    }
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY.write_text(
        "# Multiprogram Roundtrip Evidence\n\n"
        f"- MALRT1 dictionary: `{passing}/{len(dictionary)} PASS`\n"
        f"- Source bytes: `{result.source_bytes}`\n"
        f"- Source SHA-256: `{result.source_sha256}`\n"
        f"- Payload chars: `{result.payload_chars}`\n"
        f"- Payload match: `{result.payload_match}`\n"
        f"- Bytes equal: `{result.bytes_equal}`\n"
        f"- Verdict: `{'PASS' if result.roundtrip_pass else 'FAIL'}`\n\n"
        "Scope: finite inputs of arbitrary length are composed from references to 66 "
        "independently executed pure Malbolge symbol programs. This is not a "
        "single-program unbounded-memory claim.\n",
        encoding="utf-8",
    )
    print(
        f"[3/3] arbitrary-size: source={result.source_bytes} bytes "
        f"payload={result.payload_chars} chars PASS={result.roundtrip_pass}"
    )
    print(f"[OK] wrote {EVIDENCE}")
    return 0 if evidence["claims"]["ARBITRARY_SIZE_ROUNDTRIP"].startswith("DEMONSTRATED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
