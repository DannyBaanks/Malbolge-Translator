"""Audit the first Classic/3^19 divergence without implementing another VM."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLASSIC_PATH = Path(r"C:\Development\ISyCo Git\MALBOLGE\malbolge.py")
V0 = ROOT / "experiments" / "program_generator19_v0"
sys.path.insert(0, str(V0))
from program_generator19 import OFFSETS, XLAT, mcrz  # noqa: E402

spec = importlib.util.spec_from_file_location("classic_reference", CLASSIC_PATH)
classic = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(classic)

base = ROOT / "malbolge_output_A"
plan = (base / "A_full.op").read_text(encoding="ascii").strip()
source = (base / "A_full.mal").read_bytes()

classic_mem = list(source)
m19_mem = list(source)
classic_state = {"a": 0, "c": 0, "d": 0}
m19_state = {"a": 0, "c": 0, "d": 0}
events = []

for step in range(16):
    assert classic_state == m19_state, "prestate diverged before recorded step"
    c, d, a = classic_state["c"], classic_state["d"], classic_state["a"]
    before = {"c": c, "d": d, "a": a,
              "mem_c": classic_mem[c], "mem_d": classic_mem[d]}
    decoded_classic = (classic_mem[c] + c) % 94
    decoded_19 = (m19_mem[c] + c + OFFSETS[c // (3**18)]) % 94
    event = {
        "step": step,
        "pre": before,
        "desired_symbol": plan[c],
        "desired_opcode": decoded_classic,
        "source_character": chr(source[c]),
        "source_ascii": source[c],
        "decoded_classic": decoded_classic,
        "decoded_19": decoded_19,
        "instruction_classic": decoded_classic,
        "instruction_19": decoded_19,
        "output_classic_hex": "",
        "output_19_hex": "",
    }
    assert decoded_classic == decoded_19

    if decoded_classic == 4:
        classic_state["c"] = classic_mem[d]
        m19_state["c"] = m19_mem[d]
    elif decoded_classic == 62:
        classic_value = classic.crazy(a, classic_mem[d])
        m19_value = mcrz(a, m19_mem[d])
        classic_mem[d] = classic_state["a"] = classic_value
        m19_mem[d] = m19_state["a"] = m19_value
        event["crazy_effect"] = {
            "classic": classic_value,
            "m19": m19_value,
        }

    classic_encrypt_at = classic_state["c"]
    m19_encrypt_at = m19_state["c"]
    cv = classic_mem[classic_encrypt_at]
    uv = m19_mem[m19_encrypt_at]
    if 33 <= cv <= 126:
        classic_mem[classic_encrypt_at] = classic._ENCRYPT[cv]
    if uv < len(XLAT):
        m19_mem[m19_encrypt_at] = ord(XLAT[uv])

    classic_state["c"] += 1
    classic_state["d"] += 1
    m19_state["c"] += 1
    m19_state["d"] += 1
    event["post"] = {
        "classic": {**classic_state, "mem_d": classic_mem[d]},
        "m19": {**m19_state, "mem_d": m19_mem[d]},
        "encrypted_address_classic": classic_encrypt_at,
        "encrypted_address_19": m19_encrypt_at,
    }
    events.append(event)
    if classic_state != m19_state or classic_mem[d] != m19_mem[d]:
        break

print(json.dumps(events, indent=2))
last = events[-1]
print("FIRST_DIVERGENCE_STEP", last["step"])
print("OPCODE_STILL_MATCHES", last["decoded_classic"] == last["decoded_19"])
print("CAUSE", "crazy_vs_mcrz")
