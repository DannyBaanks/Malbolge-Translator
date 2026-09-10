"""RLE expansion ladder for a single Classic Malbolge program.

The vendored toolkit may propose a source, but only the supplied Classic
interpreter decides whether it is valid.  This experiment does not call a
linear repeated-output encoding a decompressor: RLE_PASS requires output bytes
to exceed printable source characters.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from malbolge import GenerationConfig, ProgramGenerator
from malbolge.encoding import reverse_normalize


def load_classic(path: Path):
    spec = importlib.util.spec_from_file_location("classic_malbolge", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Classic interpreter: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def output_epoch_cycle(classic, source: str, max_steps: int = 10_000_000) -> bool:
    """Detect a repeated full state immediately after an OUT instruction.

    The three registers are u16-bounded in Classic Malbolge.  Their equality is
    insufficient because self-modification matters, so the tape SHA-256 is part
    of the epoch signature.  With no input, a repeated signature means future
    execution is deterministic and periodic.
    """
    mem = classic.load_memory(source)
    a = c = d = 0
    seen: set[tuple[int, int, int, bytes]] = set()

    for _ in range(max_steps):
        op = (mem[c] + c) % 94
        emitted = op == 5
        jumped = False
        if op == 4:
            c = mem[d]
            jumped = True
        elif op == 23:
            a = -1
        elif op == 39:
            mem[d] = (mem[d] // 3) + (mem[d] % 3) * (3**9)
            a = mem[d]
        elif op == 40:
            d = mem[d]
        elif op == 62:
            mem[d] = classic.crazy_op(a, mem[d])
            a = mem[d]
        elif op == 81:
            return False

        if 33 <= mem[c] <= 126:
            mem[c] = classic._ENC[mem[c]]
        c = (c + 1) % classic.MEM_SIZE
        d = (d + 1) % classic.MEM_SIZE

        if emitted:
            tape_bytes = b"".join(value.to_bytes(2, "little") for value in mem)
            signature = (a, c, d, hashlib.sha256(tape_bytes).digest())
            if signature in seen:
                return True
            seen.add(signature)
        if jumped:
            # c was already assigned before the mandatory increment above.
            pass
    return False


def run_ladder(classic_path: Path, samples: list[int], seed: int) -> dict:
    classic = load_classic(classic_path)
    generator = ProgramGenerator()
    rows = []

    for count in samples:
        if count < 1:
            raise ValueError("all samples must be positive")
        target = "A" * count
        generated = generator.generate_for_string(
            target, config=GenerationConfig(random_seed=seed)
        )
        source = "".join(reverse_normalize(generated.opcodes))
        output, steps, status = classic.run(source, max_steps=10_000_000)
        exact = output == target and status == "HALTED"
        rows.append(
            {
                "target_bytes": count,
                "source_chars": len(source),
                "output_bytes": len(output),
                "output_over_source": len(output) / len(source),
                "classic_exact": exact,
                "classic_status": status,
                "classic_steps": steps,
                "output_epoch_cycle": output_epoch_cycle(classic, source),
                "toolkit_evaluations": generated.stats.get("evaluations"),
            }
        )

    rle_pass = any(
        row["classic_exact"] and row["output_bytes"] > row["source_chars"]
        for row in rows
    )
    return {
        "experiment": "RLE_DECOMPRESSOR_EPOCH_V0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "classic_interpreter": str(classic_path),
        "seed": seed,
        "criterion": "RLE_PASS iff Classic exact output_bytes > source_chars",
        "rows": rows,
        "verdict": "RLE_PASS" if rle_pass else "NOT_DEMONSTRATED",
        "scope": (
            "Repeated A is a control for output expansion only. A PASS does not "
            "demonstrate a general decompressor or Quijote synthesis."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classic-interpreter", type=Path, required=True)
    parser.add_argument("--samples", default="16,64,256,1024")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    samples = [int(value) for value in args.samples.split(",") if value]
    result = run_ladder(args.classic_interpreter, samples, args.seed)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
