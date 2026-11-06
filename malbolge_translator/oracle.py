"""malbolge_translator/oracle.py - Unified Oracle and Execution Bridge.

Connects Malbolge-Translator with:
1. Strict Canonical C Oracle: `mb_ref` (from BolgeForge / PureEpoch / ISyCo)
2. Fast Native Engine: `bolge.exe` (from Autobolge / ISyCo)
3. Pure-Python Classic VM runner (zero external dependencies)
4. Streaming Cat Bridge: verified 7,690-cell Cat from BolgeForge for arbitrary streams
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .conveyor import run_classic_vm


@dataclass
class OracleResult:
    stdout: str
    stderr: str
    returncode: int
    steps: Optional[int] = None
    engine: str = "python"


def find_mb_ref() -> Optional[Path]:
    """Finds BolgeForge's strict canonical mb_ref executable."""
    candidates = [
        Path("/home/danny/Development/ISyCo Git/BolgeForge/mb_ref"),
        Path("/home/danny/Development/ISyCo Git/Malbolge-PureEpoch/vendor/mb_ref"),
        Path(__file__).resolve().parents[2] / "BolgeForge" / "mb_ref",
        Path(__file__).resolve().parents[2] / "Malbolge-PureEpoch" / "vendor" / "mb_ref",
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return c
    return None


def find_streaming_cat() -> Optional[Path]:
    """Finds BolgeForge's verified compact streaming Cat artifact."""
    candidates = [
        Path("/home/danny/Development/ISyCo Git/BolgeForge/artifacts/cat_compact.mal"),
        Path(__file__).resolve().parents[2] / "BolgeForge" / "artifacts" / "cat_compact.mal",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def run_with_oracle(
    program: str,
    stdin_input: bytes = b"",
    max_steps: int = 100_000_000,
    prefer_strict: bool = False,
) -> OracleResult:
    """Executes a Malbolge program using the best available oracle.

    If prefer_strict is True, uses mb_ref if available.
    Otherwise uses pure-Python Classic VM.
    """
    if prefer_strict:
        mb_ref = find_mb_ref()
        if mb_ref:
            with tempfile.NamedTemporaryFile("w", suffix=".mal", delete=False) as f:
                f.write(program)
                tmp_path = f.name
            try:
                proc = subprocess.run(
                    [str(mb_ref), tmp_path, str(max_steps)],
                    input=stdin_input,
                    capture_output=True,
                    timeout=60,
                )
                return OracleResult(
                    stdout=proc.stdout.decode("latin-1", errors="replace"),
                    stderr=proc.stderr.decode("latin-1", errors="replace"),
                    returncode=proc.returncode,
                    engine="mb_ref",
                )
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    # Fallback to pure-Python Classic VM
    try:
        out_str, steps, halted = run_classic_vm(program, stdin_input=stdin_input, max_steps=max_steps)
        return OracleResult(
            stdout=out_str,
            stderr="" if halted else "HALT_NOT_REACHED",
            returncode=0 if halted else 2,
            steps=steps,
            engine="python_classic_vm",
        )
    except Exception as e:
        return OracleResult(
            stdout="",
            stderr=str(e),
            returncode=1,
            engine="python_classic_vm",
        )


def stream_through_compact_cat(
    input_bytes: bytes,
    max_steps: int = 500_000_000,
) -> OracleResult:
    """Streams arbitrary input through BolgeForge's 7,690-cell compact Cat under mb_ref.

    Demonstrates full text transport (e.g. 2.2 MB Don Quijote) through a single .mal program.
    """
    mb_ref = find_mb_ref()
    cat_mal = find_streaming_cat()
    if not mb_ref or not cat_mal:
        raise RuntimeError("BolgeForge mb_ref or cat_compact.mal artifact not found")

    proc = subprocess.run(
        [str(mb_ref), str(cat_mal), str(max_steps)],
        input=input_bytes,
        capture_output=True,
        timeout=300,
    )
    return OracleResult(
        stdout=proc.stdout.decode("latin-1", errors="replace"),
        stderr=proc.stderr.decode("latin-1", errors="replace"),
        returncode=proc.returncode,
        engine="bolgeforge_cat_compact",
    )
