"""Preflight for one self-contained Classic Malbolge program.

This is intentionally not a synthesizer.  It records the two prerequisites a
single ``.mal`` must satisfy before expensive search begins: the source has a
fixed 3^10-cell ceiling, and any compressed payload still needs a Classic
Malbolge decompressor.  Passing the size checks is never evidence that such a
decompressor or program exists.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import zlib


CLASSIC_TAPE_CELLS = 3**10
PRINTABLE_SOURCE_ALPHABET = 94


@dataclass(frozen=True)
class SingleProgramPreflight:
    source_utf8_bytes: int
    source_sha256: str
    zlib_bytes: int
    tape_cells: int
    direct_payload_fits: bool
    compressed_payload_fits: bool
    verdict: str
    scope: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def preflight_single_program(text: str) -> SingleProgramPreflight:
    """Measure necessary conditions for a standalone Classic Malbolge source.

    The result is deliberately conservative.  A direct payload larger than the
    source ceiling cannot be embedded verbatim.  A compressed payload that fits
    remains ``NOT_DEMONSTRATED`` until a self-contained Classic decompressor and
    a full execution proof exist.
    """
    data = text.encode("utf-8")
    packed = zlib.compress(data, level=9)
    direct_fits = len(data) <= CLASSIC_TAPE_CELLS
    compressed_fits = len(packed) <= CLASSIC_TAPE_CELLS

    return SingleProgramPreflight(
        source_utf8_bytes=len(data),
        source_sha256=hashlib.sha256(data).hexdigest(),
        zlib_bytes=len(packed),
        tape_cells=CLASSIC_TAPE_CELLS,
        direct_payload_fits=direct_fits,
        compressed_payload_fits=compressed_fits,
        verdict="NOT_DEMONSTRATED",
        scope=(
            "Necessary size checks only. A fitting compressed payload does not "
            "demonstrate a Classic Malbolge decompressor, synthesis, or execution."
        ),
    )
