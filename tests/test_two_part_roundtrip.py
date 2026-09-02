from pathlib import Path

import pytest

from malbolge_translator import MalbolgeTranslator
from malbolge_translator.two_part_roundtrip import run_two_part_roundtrip, split_utf8_halves


def test_split_utf8_halves_preserves_bytes_and_boundary():
    text = "ab😭中文e\u0301"
    first, second = split_utf8_halves(text)
    assert first + second == text
    assert first.encode("utf-8") + second.encode("utf-8") == text.encode("utf-8")


def test_two_part_limit_rejects_before_output(tmp_path):
    output = tmp_path / "too_large"
    with pytest.raises(ValueError, match="refusing part"):
        run_two_part_roundtrip("abcdef", output, MalbolgeTranslator(), max_part_bytes=2)
    assert not output.exists()


def test_two_independent_roundtrips_are_byte_exact(tmp_path):
    manifest = run_two_part_roundtrip(
        "Hi :p",
        tmp_path / "independent",
        MalbolgeTranslator(),
        mode="independent",
    )
    assert manifest["whole_roundtrip_pass"] is True
    assert len(manifest["parts"]) == 2


def test_verify_first_reopens_part_one_evidence(tmp_path):
    manifest = run_two_part_roundtrip(
        "Hola",
        tmp_path / "verify_first",
        MalbolgeTranslator(),
        mode="verify-first",
    )
    assert manifest["whole_roundtrip_pass"] is False
    assert manifest["claim"] == "PART_1_ROUNDTRIP_ONLY"
    assert manifest["phase_2"]["source_sha_match"] is True
    assert manifest["phase_2"]["roundtrip_pass"] is True
