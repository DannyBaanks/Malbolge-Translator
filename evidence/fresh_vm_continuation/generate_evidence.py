#!/usr/bin/env python3
"""Generate evidence for FRESH_VM_CONTINUATION across several strings."""

import json
import platform
import sys
from pathlib import Path

from malbolge import ProgramGenerator

from malbolge_translator.fresh_vm_continuation import run_fresh_vm_continuation

CASES = [
    "Hello, World!",
    "Hola mundo",
    "Bounded continuation over Classic Malbolge",
]

rows = []
for text in CASES:
    opcodes = ProgramGenerator().generate_for_string(text).opcodes
    evidence = run_fresh_vm_continuation(opcodes)
    rows.append(evidence.to_dict())
    print(
        f"{text[:32]!r:36} split={evidence.split_at:4} "
        f"prefix={evidence.prefix_output!r} suffix={evidence.suffix_output!r} "
        f"PASS={evidence.fresh_vm_continuation_pass}"
    )

summary = {
    "tool": "malbolge-translator fresh-VM continuation evidence",
    "environment": {
        "python": sys.version,
        "platform": platform.platform(),
    },
    "cases": rows,
    "claim": {
        "FRESH_VM_CONTINUATION": "DEMONSTRATED"
        if all(r["fresh_vm_continuation_pass"] for r in rows)
        else "NOT_DEMONSTRATED",
    },
}

out = Path(__file__).parent / "evidence.json"
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n[OK] wrote {out}")