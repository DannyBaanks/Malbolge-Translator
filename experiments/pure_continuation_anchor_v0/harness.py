# SPDX-License-Identifier: MIT
"""
PURE_CONTINUATION_ANCHOR_V0 harness.

Question under test:
    Can legal residual state produced by Classic Malbolge execution serve as an
    intentional causal anchor for a later, DIFFERENT output phase within the
    SAME uninterrupted execution?

Steps:
  1. validate()   - cross-check the vendored interpreter against the known
                    Hello World authority (both ISyCo-style and canonical).
  2. audit()      - mutation-path table + cross-interpreter divergence.
  3. ladder()     - Gate 1..5 (A / AA / AB / ABC / perturb-S1).
  4. search()     - bounded, structured search for cyclic continuation programs.

Run from repo root:
    py -m experiments.pure_continuation_anchor_v0.harness --all
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.pure_continuation_anchor_v0 import classic_malbolge as cm

HELLO_WORLD_SRC = (
    '(=<`#9]~6ZY327Uv4-QsqpMn&+Ij"' + "'" + 'E%e{Ab~w=_:]Kw%o44Uqp0/Q?xNvL:'
    '`H%c#DD2^WV>gY;dts76qKJImZkj'
)


def validate() -> dict:
    """Cross-check the vendored interpreter against the classic authority."""
    isyco = cm.run_traced(HELLO_WORLD_SRC, max_steps=200_000)
    canon = cm.run_canonical_reference(HELLO_WORLD_SRC, max_steps=200_000)
    return {
        "source_len": isyco.program_len,
        "isyco_status": isyco.status,
        "isyco_output": isyco.output,
        "isyco_steps": isyco.steps,
        "isyco_hello_ok": isyco.status == "HALTED" and "Hello" in isyco.output
        and "world" in isyco.output.lower(),
        "canon_status": canon.status,
        "canon_output": canon.output,
        "canon_steps": canon.steps,
        "outputs_match": isyco.output == canon.output,
        "steps_match": isyco.steps == canon.steps,
    }


def audit() -> dict:
    """Mutation-path table + cross-interpreter divergence (section 1-2)."""
    return {
        "mutation_paths": {
            "encryption": {
                "target": "mem[c]",
                "condition": "33 <= value <= 126",
                "can_touch_nonprintable": False,
                "can_touch_tail": "only if a tail cell value is printable",
                "verdict": "ENCRYPTION_IMMUNE for non-printable",
            },
            "crazy_op (op 62 p)": {
                "target": "mem[d]",
                "condition": "unconditional on d",
                "can_touch_nonprintable": True,
                "can_touch_tail": True,
                "verdict": "MUTATES any cell d points at",
            },
            "rotate (op 39 *)": {
                "target": "mem[d]",
                "condition": "unconditional on d",
                "can_touch_nonprintable": True,
                "can_touch_tail": True,
                "verdict": "MUTATES any cell d points at",
            },
            "initialization": {
                "target": "tail cells",
                "condition": "program source then crazy_op recurrence",
                "can_touch_nonprintable": True,
                "can_touch_tail": True,
                "verdict": "fills tail with mostly non-printable values",
            },
        },
        "conclusion": (
            "ENCRYPTION_IMMUNE != MUTATION_IMMUNE. A non-printable cell is never "
            "auto-encrypted, but crazy_op/rotate can still rewrite it through d. "
            "The tail is a STABLE substrate only against encryption, not against "
            "deliberate writes."
        ),
        "cross_interpreter_divergence": {
            "canonical_reference_interpreter.c:82": (
                "non-printable mem[c] -> `continue` -> SPINS (no c/d advance)"
            ),
            "isyco_classic_family": (
                "non-printable mem[c] -> NOP -> advances c/d normally"
            ),
            "implication": (
                "For a CLASSIC claim, c must never land in a non-printable tail "
                "cell; the tail may be read/written via mem[d] but not executed."
            ),
        },
    }


def _encode_opcodes(opcodes: str) -> str:
    """Encode opcode chars ('i','<','/','*','j','p','o','v') to a source."""
    # reverse_normalize equivalent: source char at index i for opcode c is
    # chosen so (src + i) % 94 == opcode_value(c).
    opval = {"i": 4, "<": 5, "/": 23, "*": 39, "j": 40, "p": 62, "o": 68, "v": 81}
    out = []
    for i, ch in enumerate(opcodes):
        need = opval[ch]
        for k in range(33, 127):
            if (k + i) % 94 == need:
                out.append(chr(k))
                break
        else:
            raise ValueError("no printable source char for opcode at index %d" % i)
    return "".join(out)


def _opcode_of(value: int, index: int) -> str:
    """Decode the opcode a cell value produces at a position (ISyCo convention)."""
    op = (value + index) % 94
    return {
        4: "i", 5: "<", 23: "/", 39: "*", 40: "j", 62: "p", 68: "o", 81: "v",
    }.get(op, ".")


def run_gate(opcodes: str, label: str, max_steps: int = 2_000_000) -> dict:
    src = _encode_opcodes(opcodes)
    t = cm.run_traced(src, max_steps=max_steps)
    c = cm.run_canonical_reference(src, max_steps=max_steps)
    out = {
        "label": label,
        "opcodes": opcodes,
        "source_len": len(src),
        "output": t.output,
        "steps": t.steps,
        "status": t.status,
        "halted": t.status == "HALTED",
        "memory_in_range": t.memory_in_range,
        "write_counts": t.write_counts(),
        "canon_status": c.status,
        "canon_output": c.output,
    }
    return out


def ladder() -> dict:
    """Gates 1-5. For gates 2+ we attempt a cyclic construction (see search())."""
    gate1 = run_gate("i" + "o" * 40 + "<" + "v", "gate1_A_baseline")
    return {"gate1": gate1, "notes": "gates 2-5 require cyclic programs; see search()"}


# ---------------------------------------------------------------------------
# Cyclic continuation search (section 7-8): structured, bounded.
#
# Strategy: use explicit jumps to keep c inside the printable program region
# (required for a CLASSIC claim, since canonical spins on non-printable tail).
# The program is a small circuit:
#     [payload cell A] [payload cell B] [payload cell C]
#     [loop back to a payload cell] [halt]
# Each executed cell gets ENC-encrypted, so revisiting it yields a DIFFERENT
# instruction: that is the continuation-anchor substrate we probe.
# ---------------------------------------------------------------------------


def _search_cyclic_short(
    target: str,
    region: int = 5,
    max_steps: int = 50_000,
    attempts_cap: int = 60_000,
) -> dict:
    """Bounded brute-force over short programs with at least one jump back.

    Uses the fast runner. We probe the cyclic family (jumps) because that is the
    only path to a CLASSIC continuation anchor (canonical spins on non-printable
    tail execution, so c must stay in the program region via jumps).
    """
    alphabet = "i</*j"
    found = None
    attempts = 0
    best_len = 0
    for length in range(3, region + 1):
        for ops in itertools.product(alphabet, repeat=length):
            opcodes = "".join(ops)
            if "j" not in opcodes and "i" not in opcodes:
                continue  # require a jump so c can loop within the program
            attempts += 1
            src = _encode_opcodes(opcodes)
            out, steps, status = cm.run_fast(src, max_steps=max_steps)
            if len(out) > best_len and out == target[: len(out)]:
                best_len = len(out)
            if out == target and status == "HALTED":
                found = {"opcodes": opcodes, "src": src, "steps": steps}
                return {
                    "target": target,
                    "found": True,
                    "result": found,
                    "attempts": attempts,
                    "best_longest_prefix": best_len,
                }
            if attempts >= attempts_cap:
                return {
                    "target": target,
                    "found": False,
                    "attempts": attempts,
                    "best_longest_prefix": best_len,
                }
        if found:
            break
    return {
        "target": target,
        "found": False,
        "attempts": attempts,
        "best_longest_prefix": best_len,
    }


def straight_line_baselines() -> dict:
    """Generate A/AA/ABC with the canonical generator and run through classic."""
    results = {}
    try:
        from malbolge import ProgramGenerator
    except Exception as exc:  # pragma: no cover
        return {"available": False, "error": str(exc)}
    g = ProgramGenerator()
    for tgt in ["A", "AA", "ABC"]:
        r = g.generate_for_string(tgt)
        src = _encode_opcodes(r.opcodes)
        out, steps, status = cm.run_fast(src, max_steps=2_000_000)
        results[tgt] = {
            "opcodes_len": len(r.opcodes),
            "status": status,
            "output": out,
            "steps": steps,
            "exact": out == tgt,
            "via_residual_state": False,  # straight-line, no re-executed cells
        }
    return {"available": True, "programs": results}


def run_all() -> dict:
    search = _search_cyclic_short("ABC")
    report = {
        "PURE_CONTINUATION_ANCHOR_V0": "FINAL",
        "generated_at_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "validation": validate(),
        "audit": audit(),
        "straight_line_baselines": straight_line_baselines(),
        "cyclic_search": search,
        "core_question": (
            "Can legal residual state produced by Classic Malbolge execution "
            "serve as an intentional causal anchor for a later, different output "
            "phase within the SAME uninterrupted execution?"
        ),
    }
    return report


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--all"
    if mode == "--validate":
        print(json.dumps(validate(), indent=2))
    elif mode == "--audit":
        print(json.dumps(audit(), indent=2))
    elif mode == "--gate1":
        print(json.dumps(ladder()["gate1"], indent=2))
    elif mode == "--search":
        target = sys.argv[2] if len(sys.argv) > 2 else "A"
        print(json.dumps(_search_cyclic_short(target), indent=2))
    elif mode == "--all":
        report = run_all()
        print(json.dumps(report, indent=2))
    elif mode == "--report":
        report = run_all()
        out = Path(__file__).resolve().parent / "evidence" / "report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("wrote", out)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())