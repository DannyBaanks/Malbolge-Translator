"""Preflight and feasibility analysis for self-contained Classic Malbolge programs.

Incorporates thermodynamic and architectural boundaries from:
- Autobolge 2.0 (sterile gap conveyor limit: 3,194 cells)
- BolgeForge (strict 3^10 memory bound & 7,690-cell streaming Cat)
- PureEpoch (multi-epoch and loop frontier status)
- Malbolge-Translator MALRT1 (multiprogram dictionary transport)
"""

from __future__ import annotations

import hashlib
import math
import zlib
from dataclasses import asdict, dataclass
from typing import Dict, Any

from .conveyor import can_conveyor_fit, STERILE_GAP

CLASSIC_TAPE_CELLS = 3**10  # 59,049 cells
MAX_RAM_ENTROPY_BITS = CLASSIC_TAPE_CELLS * math.log2(CLASSIC_TAPE_CELLS)  # ~937,902 bits
MAX_RAM_ENTROPY_BYTES = int(MAX_RAM_ENTROPY_BITS / 8)  # ~117,237 bytes (~117.2 KB)


@dataclass(frozen=True)
class SingleProgramPreflight:
    source_utf8_bytes: int
    source_sha256: str
    zlib_bytes: int
    tape_cells: int
    conveyor_fits: bool
    direct_payload_fits: bool
    compressed_payload_fits: bool
    thermodynamic_limit_exceeded: bool
    recommended_strategy: str
    verdict: str
    scope: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preflight_single_program(text: str) -> SingleProgramPreflight:
    """Measure necessary conditions and architecture feasibility for Malbolge programs.

    Evaluates:
    1. Autobolge conveyor synthesis: fits if sterile gap requirements (<= 3,194 cells) are met.
    2. Zero-stdin monolithic source ceiling: requires data <= 59,049 cells.
    3. Thermodynamic / Shannon limit: if compressed text > ~117 KB, monolithic zero-stdin is physically impossible.
    4. Recommends BolgeForge streaming Cat or MALRT1 multiprogram dictionary if text exceeds memory limits.
    """
    data = text.encode("utf-8")
    packed = zlib.compress(data, level=9)
    direct_fits = len(data) <= CLASSIC_TAPE_CELLS
    compressed_fits = len(packed) <= CLASSIC_TAPE_CELLS
    conveyor_viable = can_conveyor_fit(text)
    thermo_exceeded = len(packed) > MAX_RAM_ENTROPY_BYTES

    if conveyor_viable:
        rec_strategy = "AUTOBOLGE_CONVEYOR (instant O(N) synthesis, ~2-4 ms)"
        verdict = "DEMONSTRATED_CONVEYOR"
    elif direct_fits:
        rec_strategy = "BEAM_OR_WORD_BANK (fits in 59,049 tape cells; search required)"
        verdict = "FEASIBLE_SEARCH_REQUIRED"
    elif thermo_exceeded:
        rec_strategy = (
            "BOLGEFORGE_STREAMING_CAT (via stdin) OR MALRT1_MULTIPROGRAM (66 atomic symbol programs). "
            "Zero-stdin monolithic .mal is physically impossible (Kolmogorov entropy > 3^10 RAM capacity)."
        )
        verdict = "THERMODYNAMIC_BARRIER_EXCEEDED"
    else:
        rec_strategy = "MALRT1_MULTIPROGRAM_DICTIONARY"
        verdict = "NOT_DEMONSTRATED"

    scope = (
        f"Input: {len(data)} bytes. Autobolge sterile gap: {STERILE_GAP} cells. "
        f"Classic Tape: {CLASSIC_TAPE_CELLS} cells (~{MAX_RAM_ENTROPY_BYTES/1024:.1f} KB max theoretical entropy). "
        f"Strategy: {rec_strategy}. Necessary size checks only. A fitting compressed payload "
        "does not demonstrate a Classic Malbolge decompressor, synthesis, or execution."
    )

    return SingleProgramPreflight(
        source_utf8_bytes=len(data),
        source_sha256=hashlib.sha256(data).hexdigest(),
        zlib_bytes=len(packed),
        tape_cells=CLASSIC_TAPE_CELLS,
        conveyor_fits=conveyor_viable,
        direct_payload_fits=direct_fits,
        compressed_payload_fits=compressed_fits,
        thermodynamic_limit_exceeded=thermo_exceeded,
        recommended_strategy=rec_strategy,
        verdict=verdict,
        scope=scope,
    )
