"""ripple_counter.py - XLAT2 Nested Ripple Counter Synthesizer for Malbolge Classic.

Generates autonomous zero-stdin programs that achieve positive expansion
(output_bytes > source_chars) with clean HALT by cascading independent
XLAT2 cycle-5 cells (Nop/Nop/Nop/Nop/MovD) in series.
"""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Default tool paths in the ISyCo / Malbolge research workspace
LMAO_CANDIDATE_PATHS = [
    Path("/home/danny/Development/ISyCo Git/MALBOLGE-MB-DATABASE/third_party/lmao/lmao"),
    Path("/usr/local/bin/lmao"),
    Path("/usr/bin/lmao"),
]

ORACLE_CANDIDATE_PATHS = [
    Path("/home/danny/Development/ISyCo/workspace/assembly/malbolge/reference_interpreter_classic"),
    Path("/home/danny/Development/ISyCo Git/BolgeForge/artifacts/mb_ref"),
]


def find_lmao() -> Optional[Path]:
    for p in LMAO_CANDIDATE_PATHS:
        if p.exists() and p.is_file():
            return p
    return None


def find_oracle() -> Optional[Path]:
    for p in ORACLE_CANDIDATE_PATHS:
        if p.exists() and p.is_file():
            return p
    return None


@dataclass
class RippleCounterResult:
    stages: int
    expected_outputs: int
    source_bytes: int
    output_bytes: int
    ratio: float
    exact_match: bool
    halted_cleanly: bool
    sha256: str
    program_path: Path


def generate_ripple_counter_hell(num_stages: int, char_to_print: str = "A") -> str:
    """Generates HeLL source code for an N-stage nested LOOP5 ripple counter.
    
    Total outputs emitted = 5^num_stages.
    """
    if num_stages < 1:
        raise ValueError("num_stages must be >= 1")
    if len(char_to_print) != 1:
        raise ValueError("char_to_print must be a single ASCII character")

    target_ascii = ord(char_to_print)
    # V = rotl(target_ascii) so that rotr(V) == target_ascii
    v_load = ((target_ascii * 3) % 59049) + (target_ascii // 19683)

    lines = [
        "/* HeLL Nested LOOP5 Ripple Counter */",
        f"/* Stages: {num_stages}, Total Outputs: {5**num_stages} */",
        ".CODE",
        "ROT:",
        "\tRot/Nop",
        "\tJmp",
        "",
        "OUT:",
        "\tOut/Nop",
        "\tJmp",
        "",
        "MOVD_INIT:",
        "\tMovD",
        "\tJmp",
        "",
        "MOVD_LOOP:",
        "\tMovD/Nop",
        "\tJmp",
        "",
    ]

    for i in range(1, num_stages + 1):
        lines.append(f"LOOP5_{i}:")
        lines.append("\tNop/Nop/Nop/Nop/MovD")
        lines.append("\tJmp")
        lines.append("")

    lines.append("HALT:")
    lines.append("\tHlt")
    lines.append("")
    lines.append(".DATA {")
    lines.append("loop:")
    lines.append("\tR_MOVD_LOOP")
    lines.append("loop_start:")
    lines.append("\tOUT ?-")
    lines.append("\tR_OUT")

    # First stage check
    if num_stages == 1:
        lines.append("\tLOOP5_1 exit_all")
    else:
        lines.append("\tLOOP5_1 check_stage2")
    lines.append("\tMOVD_LOOP loop")
    lines.append("")

    # Intermediate stages
    for i in range(2, num_stages + 1):
        lines.append(f"check_stage{i}:")
        if i == num_stages:
            lines.append(f"\tLOOP5_{i} exit_all")
        else:
            lines.append(f"\tLOOP5_{i} check_stage{i+1}")
        lines.append("\tMOVD_LOOP loop")
        lines.append("")

    lines.append("exit_all:")
    lines.append("\tHALT")
    lines.append("")
    lines.append("ENTRY:")
    lines.append(f"\tROT {v_load} R_ROT")
    lines.append("\tMOVD_INIT loop_start")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def compile_and_verify_ripple_counter(
    num_stages: int,
    char_to_print: str = "A",
    out_dir: Optional[Path] = None,
) -> RippleCounterResult:
    """Compiles the HeLL ripple counter via LMAO and verifies execution under the C oracle."""
    lmao_bin = find_lmao()
    if lmao_bin is None:
        raise RuntimeError("LMAO assembler binary not found.")
    oracle_bin = find_oracle()
    if oracle_bin is None:
        raise RuntimeError("Reference C oracle binary not found.")

    if out_dir is None:
        out_dir = Path("/tmp/malbolge_ripple")
    out_dir.mkdir(parents=True, exist_ok=True)

    hell_path = out_dir / f"ripple_{num_stages}stages.hell"
    mb_path = out_dir / f"ripple_{num_stages}stages.mb"

    src = generate_ripple_counter_hell(num_stages, char_to_print)
    hell_path.write_text(src, encoding="ascii")

    cmd_comp = [str(lmao_bin), "-o", str(mb_path), str(hell_path)]
    p_comp = subprocess.run(cmd_comp, capture_output=True, text=True)
    if p_comp.returncode != 0:
        raise RuntimeError(f"LMAO compilation failed:\n{p_comp.stderr or p_comp.stdout}")

    source_bytes = mb_path.stat().st_size
    sha256 = hashlib.sha256(mb_path.read_bytes()).hexdigest()

    cmd_run = [str(oracle_bin), str(mb_path)]
    p_run = subprocess.run(cmd_run, capture_output=True)

    output_bytes = len(p_run.stdout)
    expected_outputs = 5 ** num_stages
    exact_match = (output_bytes == expected_outputs) and (
        p_run.stdout == (char_to_print * expected_outputs).encode("ascii")
    )
    halted_cleanly = (p_run.returncode == 0)
    ratio = output_bytes / source_bytes if source_bytes > 0 else 0.0

    return RippleCounterResult(
        stages=num_stages,
        expected_outputs=expected_outputs,
        source_bytes=source_bytes,
        output_bytes=output_bytes,
        ratio=ratio,
        exact_match=exact_match,
        halted_cleanly=halted_cleanly,
        sha256=sha256,
        program_path=mb_path,
    )
