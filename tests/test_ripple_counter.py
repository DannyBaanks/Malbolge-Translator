"""Tests for the XLAT2 Nested Ripple Counter Synthesizer."""
import pytest
from pathlib import Path

from malbolge_translator.ripple_counter import (
    find_lmao,
    find_oracle,
    generate_ripple_counter_hell,
    compile_and_verify_ripple_counter,
)


def test_generate_ripple_counter_hell_syntax():
    src = generate_ripple_counter_hell(3, "B")
    assert "LOOP5_1:" in src
    assert "LOOP5_2:" in src
    assert "LOOP5_3:" in src
    assert "Hlt" in src
    assert "ROT" in src
    assert "ENTRY:" in src


def test_generate_ripple_counter_invalid_args():
    with pytest.raises(ValueError):
        generate_ripple_counter_hell(0)
    with pytest.raises(ValueError):
        generate_ripple_counter_hell(2, "AA")


@pytest.mark.skipif(find_lmao() is None or find_oracle() is None, reason="LMAO or Oracle binary missing")
def test_ripple_counter_execution_stages_1_and_2(tmp_path):
    # Stage 1: 5 outputs
    res1 = compile_and_verify_ripple_counter(1, "Z", out_dir=tmp_path)
    assert res1.expected_outputs == 5
    assert res1.output_bytes == 5
    assert res1.exact_match is True
    assert res1.halted_cleanly is True

    # Stage 2: 25 outputs
    res2 = compile_and_verify_ripple_counter(2, "Z", out_dir=tmp_path)
    assert res2.expected_outputs == 25
    assert res2.output_bytes == 25
    assert res2.exact_match is True
    assert res2.halted_cleanly is True


@pytest.mark.skipif(find_lmao() is None or find_oracle() is None, reason="LMAO or Oracle binary missing")
def test_ripple_counter_positive_expansion_demonstration(tmp_path):
    # Stage 6: 15,625 outputs from ~4,984 bytes -> Ratio > 3.0x
    res6 = compile_and_verify_ripple_counter(6, "A", out_dir=tmp_path)
    assert res6.expected_outputs == 15625
    assert res6.output_bytes == 15625
    assert res6.exact_match is True
    assert res6.halted_cleanly is True
    assert res6.ratio > 1.0  # Positive expansion demonstrated!
