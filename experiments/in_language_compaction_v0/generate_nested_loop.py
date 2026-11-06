#!/usr/bin/env python3
"""generate_nested_loop.py - Ripple Counter Expansion Generator for Malbolge Classic.

Generates an N-stage nested LOOP5 ripple counter in HeLL assembly:
  Total outputs = 5^N
  Each stage uses a loop-resistant XLAT2 cycle of length 5 (Nop/Nop/Nop/Nop/MovD).
  Exits cleanly to HALT with zero stdin requirement.
"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

LMAO_PATH = Path("/home/danny/Development/ISyCo Git/MALBOLGE-MB-DATABASE/third_party/lmao/lmao")
ORACLE_PATH = Path("/home/danny/Development/ISyCo/workspace/assembly/malbolge/reference_interpreter_classic")


def generate_hell_source(num_stages: int, char_to_print: str = "A") -> str:
    """Generates HeLL source code for num_stages nested LOOP5 ripple counter."""
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


def compile_and_test(num_stages: int, char_to_print: str = "A", out_dir: Path | None = None) -> dict:
    if out_dir is None:
        out_dir = Path("/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    hell_path = out_dir / f"nested_loop_{num_stages}stages.hell"
    mb_path = out_dir / f"nested_loop_{num_stages}stages.mb"
    
    src = generate_hell_source(num_stages, char_to_print)
    hell_path.write_text(src, encoding="ascii")
    
    # Compile with LMAO
    cmd_lmao = [str(LMAO_PATH), "-o", str(mb_path), str(hell_path)]
    p_comp = subprocess.run(cmd_lmao, capture_output=True, text=True)
    if p_comp.returncode != 0:
        return {
            "stages": num_stages,
            "compiled": False,
            "error": p_comp.stderr or p_comp.stdout,
        }
        
    source_bytes = mb_path.stat().st_size
    
    # Run under C Oracle
    cmd_run = [str(ORACLE_PATH), str(mb_path)]
    p_run = subprocess.run(cmd_run, capture_output=True)
    
    output_bytes = len(p_run.stdout)
    expected_outputs = 5 ** num_stages
    exact_match = (output_bytes == expected_outputs) and (p_run.stdout == (char_to_print * expected_outputs).encode("ascii"))
    halted = (p_run.returncode == 0)
    ratio = output_bytes / source_bytes if source_bytes > 0 else 0.0
    
    return {
        "stages": num_stages,
        "compiled": True,
        "source_bytes": source_bytes,
        "output_bytes": output_bytes,
        "expected_outputs": expected_outputs,
        "exact_match": exact_match,
        "halted_cleanly": halted,
        "ratio": ratio,
        "stdout_sample": repr(p_run.stdout[:20]),
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    res = compile_and_test(n)
    print(res)
