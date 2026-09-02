#!/usr/bin/env python3
import hashlib
import json
import platform
import sys
from pathlib import Path

from malbolge_translator.roundtrip import encode_roundtrip
from malbolge_translator.translator import MalbolgeTranslator

cases = {
    "ascii": "Hello, World!",
    "spanish": "Hola, señor. ¿Cómo estás?",
    "chinese": "你好，世界",
    "japanese": "日本語のテスト",
    "cyrillic": "Привет мир",
    "emoji": "😭🔥🚀",
    "mixed": 'español + 中文 + 日本語 + code: print("hola") 🚀',
    "multiline": "line1\nline2\ttab\nline3 中文",
}

tr = MalbolgeTranslator()
rows = []
for name, text in cases.items():
    result = tr.translate_roundtrip(text)
    ver = tr.verify_roundtrip(result)
    payload = result.encoded_payload
    row = {
        "case": name,
        "original_text_preview": text[:30],
        "utf8_bytes": len(text.encode("utf-8")),
        "payload_chars": len(payload),
        "malbolge_chars": result.malbolge_program_chars,
        "malbolge_opcodes": result.malbolge_opcodes,
        "steps": ver.malbolge_steps,
        "execution_status": ver.malbolge_execution_status,
        "payload_match": ver.payload_match,
        "bytes_equal": ver.bytes_equal,
        "sha_equal": ver.sha_equal,
        "codec_roundtrip": ver.codec_roundtrip,
        "malbolge_synthesis": ver.malbolge_synthesis,
        "end_to_end": ver.end_to_end_roundtrip,
        "roundtrip_pass": ver.roundtrip_pass,
        "original_sha256": ver.original_utf8_sha256,
        "recovered_sha256": ver.recovered_utf8_sha256,
    }
    rows.append(row)
    print(f"{name:10} utf8={row['utf8_bytes']:2} payload={row['payload_chars']:3} malbolge={row['malbolge_chars']:4} synth={row['malbolge_synthesis']:4} codec={row['codec_roundtrip']:4} e2e={row['end_to_end']:15} sha={row['original_sha256'][:8]}")

summary = {
    "tool": "malbolge-translator roundtrip evidence",
    "codec_version": "MALRT1",
    "environment": {
        "python": sys.version,
        "platform": platform.platform(),
        "malbolge_generator_available": False,  # determined by translator fallback
    },
    "cases": rows,
    "claims": {
        "MALBOLGE_NATIVE_UNICODE": False,
        "TRANSLITERATION_REVERSIBLE": False,
    }
}

# Detect if generator available
try:
    from malbolge_translator.translator import _MALBOLGE_AVAILABLE
    summary["environment"]["malbolge_generator_available"] = bool(_MALBOLGE_AVAILABLE)
except Exception:
    pass

out = Path(__file__).parent / "evidence.json"
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n[OK] wrote {out}")

# Markdown table
md = Path(__file__).parent / "summary.md"
lines = ["# Roundtrip Evidence (2026-09-02)", "", "| case | utf8 bytes | payload chars | malbolge chars | steps | byte_equal | sha_equal | end_to_end |", "|---|---|---|---|---|---|---|---|"]
for r in rows:
    lines.append(f"| {r['case']} | {r['utf8_bytes']} | {r['payload_chars']} | {r['malbolge_chars']} | {r['steps']} | {r['bytes_equal']} | {r['sha_equal']} | {r['end_to_end']} |")
md.write_text("\n".join(lines), encoding="utf-8")
print(f"[OK] wrote {md}")
