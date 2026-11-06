"""Preflight and feasibility analysis for self-contained Classic Malbolge programs.

Epistemological boundaries:
- A known compression size establishes only an empirical upper bound, NOT a demonstrated
  lower bound on Kolmogorov complexity.
- Autonomous zero-stdin monolithic generation of large works (e.g. Don Quijote) remains
  NOT_DEMONSTRATED; neither existence nor general impossibility is formally proved.
- The 66-symbol MALRT1 multiprogram dictionary is an external host-concatenated profile,
  NOT equivalent to a single autonomous .mal program.
- BolgeForge streaming Cat (cat_compact.mal) is a stdin-streaming consumer, not zero-stdin.
- Autobolge conveyor synthesis is DEMONSTRATED for payloads fitting the sterile gap (<= 3,194 cells).
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
    empirical_compression_exceeds_tape: bool
    recommended_strategy: str
    verdict: str
    scope: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preflight_single_program(text: str) -> SingleProgramPreflight:
    """Measure necessary conditions and architecture feasibility for Malbolge programs.

    Evaluates:
    1. Autobolge conveyor synthesis: DEMONSTRATED_CONVEYOR if within sterile gap (<= 3,194 cells).
    2. Zero-stdin monolithic source ceiling: direct embedding requires <= 59,049 cells.
    3. Empirical compression checks: records heuristic compressed size against tape capacity.
       Note: empirical compression does NOT prove a Kolmogorov lower bound.
    4. For large texts where a single autonomous program is NOT_DEMONSTRATED, documents the
       separate verified alternatives: BolgeForge streaming Cat (stdin) and MALRT1 multiprogram
       (host-orchestrated dictionary), emphasizing that neither is equivalent to a single autonomous .mal.
    """
    data = text.encode("utf-8")
    packed = zlib.compress(data, level=9)
    direct_fits = len(data) <= CLASSIC_TAPE_CELLS
    compressed_fits = len(packed) <= CLASSIC_TAPE_CELLS
    conveyor_viable = can_conveyor_fit(text)
    empirical_exceeded = len(packed) > MAX_RAM_ENTROPY_BYTES

    if conveyor_viable:
        rec_strategy = "AUTOBOLGE_CONVEYOR (instant O(N) synthesis, ~2-4 ms)"
        verdict = "DEMONSTRATED_CONVEYOR"
    elif direct_fits:
        rec_strategy = "BEAM_OR_WORD_BANK (fits in 59,049 tape cells; search required)"
        verdict = "FEASIBLE_SEARCH_REQUIRED"
    elif empirical_exceeded:
        rec_strategy = (
            "SINGLE_PROGRAM_AUTONOMOUS is NOT_DEMONSTRATED (empirical compression exceeds 3^10 RAM; "
            "Kolmogorov lower bound unproven). Available verified alternatives: BolgeForge streaming Cat "
            "(requires stdin) or MALRT1 multiprogram dictionary (requires host harness; not equivalent to a single .mal)."
        )
        verdict = "NOT_DEMONSTRATED"
    else:
        rec_strategy = "MALRT1_MULTIPROGRAM_DICTIONARY"
        verdict = "NOT_DEMONSTRATED"

    scope = (
        f"Input: {len(data)} bytes. Autobolge sterile gap: {STERILE_GAP} cells. "
        f"Classic Tape: {CLASSIC_TAPE_CELLS} cells (~{MAX_RAM_ENTROPY_BYTES/1024:.1f} KB max theoretical entropy). "
        f"Strategy: {rec_strategy}. Necessary size checks only. A fitting compressed payload "
        "does not demonstrate a Classic Malbolge decompressor, synthesis, or execution. "
        "Neither existence nor general impossibility of a single autonomous program is demonstrated."
    )

    return SingleProgramPreflight(
        source_utf8_bytes=len(data),
        source_sha256=hashlib.sha256(data).hexdigest(),
        zlib_bytes=len(packed),
        tape_cells=CLASSIC_TAPE_CELLS,
        conveyor_fits=conveyor_viable,
        direct_payload_fits=direct_fits,
        compressed_payload_fits=compressed_fits,
        empirical_compression_exceeds_tape=empirical_exceeded,
        recommended_strategy=rec_strategy,
        verdict=verdict,
        scope=scope,
    )
