"""
Malbolge Translator - Generate pure Malbolge programs for arbitrary text.

A standalone tool for translating any text (including Unicode) into
executable Malbolge programs using anchor harness technology and
Autobolge constructive synthesis.
"""

import sys
from pathlib import Path

# Auto-discover vendored malbolge_toolkit from ISyCo monorepo if malbolge is not installed
try:
    import malbolge
except ImportError:
    for candidate in [
        Path(__file__).resolve().parents[2].parent / "ISyCo" / "workspace" / "malbolge_toolkit",
        Path("/home/danny/Development/ISyCo/workspace/malbolge_toolkit"),
    ]:
        if candidate.is_dir() and (candidate / "malbolge").is_dir():
            sys.path.insert(0, str(candidate))
            break

from .conveyor import (
    ConveyorSynthesisResult,
    can_conveyor_fit,
    conveyor_capacity,
    run_classic_vm,
    synthesize_conveyor,
)
from .oracle import (
    OracleResult,
    find_mb_ref,
    find_streaming_cat,
    run_with_oracle,
    stream_through_compact_cat,
)
from .translator import MalbolgeTranslator, TranslationResult, WordResult, RoundtripResult, RoundtripVerification
from .lexicon import Lexicon, transliterate, DEFAULT_LEXICON
from .fresh_vm_continuation import (
    FreshVMContinuationEvidence,
    run_fresh_vm_continuation,
    split_opcodes,
)
from .multiprogram_roundtrip import (
    MALRT1_ALPHABET,
    MultiprogramRoundtripEvidence,
    SymbolProgram,
    build_symbol_dictionary,
    load_symbol_dictionary,
    save_symbol_dictionary,
    transport_text,
    verify_symbol_dictionary,
)
try:
    from .anchor import AnchorManager, AnchorState, WordBank, BankEntry
except Exception:  # malbolge-generator not installed
    AnchorManager = AnchorState = WordBank = BankEntry = None  # type: ignore[assignment]
from .two_part_roundtrip import DEFAULT_MAX_PART_BYTES, run_two_part_roundtrip, split_utf8_halves
from .roundtrip import (
    CODEC_VERSION,
    RoundtripDecodeResult,
    RoundtripEnvelope,
    RoundtripStatus,
    decode_roundtrip,
    decode_roundtrip_detailed,
    encode_roundtrip,
    encode_roundtrip_envelope,
)
from .single_program import SingleProgramPreflight, preflight_single_program
from .ripple_counter import (
    RippleCounterResult,
    generate_ripple_counter_hell,
    compile_and_verify_ripple_counter,
)

__version__ = "2.0.0"
__all__ = [
    "MalbolgeTranslator",
    "TranslationResult",
    "WordResult",
    "RoundtripResult",
    "RoundtripVerification",
    "DEFAULT_MAX_PART_BYTES",
    "run_two_part_roundtrip",
    "split_utf8_halves",
    "Lexicon",
    "transliterate",
    "DEFAULT_LEXICON",
    "AnchorManager",
    "AnchorState",
    "WordBank",
    "BankEntry",
    "CODEC_VERSION",
    "RoundtripEnvelope",
    "RoundtripDecodeResult",
    "RoundtripStatus",
    "encode_roundtrip",
    "encode_roundtrip_envelope",
    "decode_roundtrip",
    "decode_roundtrip_detailed",
    "FreshVMContinuationEvidence",
    "run_fresh_vm_continuation",
    "split_opcodes",
    "MALRT1_ALPHABET",
    "MultiprogramRoundtripEvidence",
    "SymbolProgram",
    "build_symbol_dictionary",
    "load_symbol_dictionary",
    "save_symbol_dictionary",
    "transport_text",
    "verify_symbol_dictionary",
    "ConveyorSynthesisResult",
    "can_conveyor_fit",
    "conveyor_capacity",
    "run_classic_vm",
    "synthesize_conveyor",
    "OracleResult",
    "find_mb_ref",
    "find_streaming_cat",
    "run_with_oracle",
    "stream_through_compact_cat",
    "SingleProgramPreflight",
    "preflight_single_program",
    "RippleCounterResult",
    "generate_ripple_counter_hell",
    "compile_and_verify_ripple_counter",
]
