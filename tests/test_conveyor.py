"""Tests for Autobolge O(N) Conveyor Synthesis and Oracle Integration in Malbolge-Translator."""

import pytest
from malbolge_translator import (
    MalbolgeTranslator,
    can_conveyor_fit,
    conveyor_capacity,
    preflight_single_program,
    run_classic_vm,
    synthesize_conveyor,
)
from malbolge_translator.oracle import find_mb_ref, find_streaming_cat, run_with_oracle


def test_conveyor_capacity_and_fit():
    assert conveyor_capacity() == 3194
    assert can_conveyor_fit("Hello World!\n") is True
    assert can_conveyor_fit("A" * 500) is True
    # Exceeding sterile gap: 2000 A's require > 3194 data cells
    assert can_conveyor_fit("A" * 2000) is False


def test_synthesize_conveyor_hello_world():
    target = "Hello World!\n"
    res = synthesize_conveyor(target, verify=True)
    assert res.verified is True
    assert res.target == target
    assert res.output == target
    assert len(res.program) > 3315
    assert res.elapsed_ms < 200.0  # Fast O(N)


def test_synthesize_conveyor_quijote_opening_paragraph():
    opening = (
        "En un lugar de la Mancha, de cuyo nombre no quiero acordarme, no ha mucho "
        "tiempo que vivia un hidalgo de los de lanza en astillero, adarga antigua, "
        "rocin flaco y galgo corredor."
    )
    assert can_conveyor_fit(opening) is True
    res = synthesize_conveyor(opening, verify=True)
    assert res.verified is True
    assert res.output == opening
    assert res.elapsed_ms < 100.0


def test_conveyor_fails_closed_when_oversized():
    oversized = "A" * 2000
    with pytest.raises(ValueError, match="target too long"):
        synthesize_conveyor(oversized, verify=False)


def test_translator_auto_engine_uses_conveyor():
    translator = MalbolgeTranslator()
    res = translator.translate("Hola Malbolge!\n", engine="auto")
    assert res.stats.get("engine") == "conveyor"
    assert res.processed_text == "Hola Malbolge!\n"
    assert len(res.full_program) > 0

    # Verification via execute()
    out = translator.execute(res)
    assert out == "Hola Malbolge!\n"


def test_preflight_thermodynamic_analysis():
    # Short text: fits conveyor
    p1 = preflight_single_program("Hola mundo")
    assert p1.conveyor_fits is True
    assert p1.verdict == "DEMONSTRATED_CONVEYOR"

    # Giant text (250 KB high-entropy payload): exceeds thermodynamic limit of Malbolge RAM (~117 KB)
    import os
    giant = os.urandom(150_000).hex()
    p2 = preflight_single_program(giant)
    assert p2.conveyor_fits is False
    assert p2.direct_payload_fits is False
    assert p2.thermodynamic_limit_exceeded is True
    assert p2.verdict == "THERMODYNAMIC_BARRIER_EXCEEDED"
    assert "BOLGEFORGE_STREAMING_CAT" in p2.recommended_strategy


def test_oracle_discovery():
    mb_ref = find_mb_ref()
    cat = find_streaming_cat()
    assert mb_ref is not None
    assert mb_ref.is_file()
    assert cat is not None
    assert cat.is_file()
