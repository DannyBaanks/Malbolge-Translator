#!/usr/bin/env python3
"""Transport the complete Project Gutenberg Don Quijote body via MALRT1."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from malbolge_translator.multiprogram_roundtrip import (
    load_symbol_dictionary,
    transport_text,
    verify_symbol_dictionary,
)


URL = "https://www.gutenberg.org/ebooks/2000.txt.utf-8"
HERE = Path(__file__).resolve().parent
DICTIONARY = HERE / "symbol_dictionary.json"
EVIDENCE = HERE / "full_quijote_evidence.json"
SUMMARY = HERE / "FULL_QUIJOTE.md"
IMPLEMENTATION = HERE.parents[1] / "malbolge_translator" / "multiprogram_roundtrip.py"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_body(text: str) -> str:
    start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
    end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        raise ValueError("Project Gutenberg body markers not found")
    start = text.find("\n", start)
    if start < 0:
        raise ValueError("Project Gutenberg start marker has no following newline")
    body = text[start + 1 : end]
    return body.strip("\r\n") + "\n"


def main() -> int:
    print(f"[1/4] downloading {URL}")
    request = urllib.request.Request(URL, headers={"User-Agent": "Malbolge-Translator-evidence/1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
    text = raw.decode("utf-8-sig")
    body = extract_body(text)
    if "En un lugar de la Mancha" not in body:
        raise ValueError("canonical opening not found in extracted body")
    print(f"[2/4] body: {len(body.encode('utf-8'))} bytes")

    dictionary = load_symbol_dictionary(DICTIONARY)
    dictionary_verified = verify_symbol_dictionary(dictionary)
    print(f"[3/4] dictionary re-execution: {dictionary_verified}")
    if not dictionary_verified:
        raise SystemExit("dictionary re-execution failed")

    result = transport_text(body, dictionary)
    evidence = {
        "schema": "malrt1-full-quijote-evidence/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "command": "py -m evidence.multiprogram.run_full_quijote",
        "exit_status": 0,
        "implementation": {
            "path": "malbolge_translator/multiprogram_roundtrip.py",
            "sha256": sha256(IMPLEMENTATION.read_bytes()),
        },
        "script_sha256": sha256(Path(__file__).read_bytes()),
        "source": {
            "url": URL,
            "download_bytes": len(raw),
            "download_sha256": sha256(raw),
            "extraction": "UTF-8 body between Project Gutenberg START/END markers",
            "body_bytes": len(body.encode("utf-8")),
            "body_sha256": sha256(body.encode("utf-8")),
        },
        "dictionary": {
            "path": "symbol_dictionary.json",
            "sha256": sha256(DICTIONARY.read_bytes()),
            "reexecuted_all_symbols": dictionary_verified,
        },
        "roundtrip": result.to_dict(),
        "claims": {
            "FULL_DON_QUIJOTE_UTF8_ROUNDTRIP": (
                "DEMONSTRATED_MULTIPROGRAM_DICTIONARY"
                if result.roundtrip_pass and dictionary_verified
                else "NOT_DEMONSTRATED"
            ),
            "SINGLE_PROGRAM_FULL_DON_QUIJOTE": "NOT_DEMONSTRATED",
        },
    }
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY.write_text(
        "# Full Don Quijote Multiprogram Roundtrip\n\n"
        f"- Source: `{URL}`\n"
        f"- Download SHA-256: `{evidence['source']['download_sha256']}`\n"
        f"- Extracted body bytes: `{result.source_bytes}`\n"
        f"- Extracted body SHA-256: `{result.source_sha256}`\n"
        f"- MALRT1 payload chars: `{result.payload_chars}`\n"
        f"- Dictionary re-executed: `{dictionary_verified}`\n"
        f"- Payload match: `{result.payload_match}`\n"
        f"- UTF-8 bytes equal: `{result.bytes_equal}`\n"
        f"- Verdict: `{'PASS' if result.roundtrip_pass else 'FAIL'}`\n\n"
        "Scope: full Gutenberg body transported through references to independently "
        "executed pure Malbolge symbol programs. This does not claim one monolithic "
        "Classic Malbolge program contains the book.\n",
        encoding="utf-8",
    )
    print(
        f"[4/4] payload={result.payload_chars} chars "
        f"bytes_equal={result.bytes_equal} PASS={result.roundtrip_pass}"
    )
    print(f"[OK] wrote {EVIDENCE}")
    return 0 if evidence["claims"]["FULL_DON_QUIJOTE_UTF8_ROUNDTRIP"].startswith("DEMONSTRATED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
