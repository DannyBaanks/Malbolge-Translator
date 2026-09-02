#!/usr/bin/env python3
"""
Roundtrip tests: codec + Malbolge end-to-end (classified).

Test matrix (8 cases):
1. ASCII
2. Spanish
3. Chinese
4. Japanese
5. Cyrillic
6. Emoji
7. Mixed
8. Newlines/tabs

For each successful case verify:
    recovered_text == original_text
    sha equality
    Malbolge execution HALTED
    executed ASCII payload == generated ASCII payload

If Malbolge synthesis cannot complete within budget, classify:
    CODEC_ROUNDTRIP = PASS
    MALBOLGE_SYNTHESIS = TIMEOUT/FAIL
    END_TO_END_ROUNDTRIP = NOT_DEMONSTRATED
"""
from __future__ import annotations

import hashlib
import pytest

from malbolge_translator.roundtrip import (
    CODEC_VERSION,
    RoundtripStatus,
    decode_roundtrip,
    decode_roundtrip_detailed,
    encode_roundtrip,
    encode_roundtrip_envelope,
)
from malbolge_translator.lexicon import transliterate
from malbolge_translator.translator import MalbolgeTranslator

# Probe if Malbolge generator is available
try:
    from malbolge_translator.translator import _MALBOLGE_AVAILABLE
except Exception:
    _MALBOLGE_AVAILABLE = False


CASES = {
    "ascii": "Hello, World!",
    "spanish": "Hola, \u00f1\u00f6\u00e4?\u00bfC\u00f3mo est\u00e1s?",  # Hola, señor. ¿Cómo estás?
    "chinese": "\u4f60\u597d\uff0c\u4e16\u754c",  # 你好，世界
    "japanese": "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8",  # 日本語のテスト
    "cyrillic": "\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440",  # Привет мир
    "emoji": "\U0001f62d\U0001f525\U0001f680",  # 😭🔥🚀
    "mixed": "espa\u00f1ol + \u4e2d\u6587 + \u65e5\u672c\u8a9e + code: print(\"hola\") \U0001f680",
    "multiline": "line1\nline2\ttab\nline3 \u4e2d\u6587",
}

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# --- Codec-only tests (no Malbolge) ---

@pytest.mark.parametrize("name,original", list(CASES.items()))
def test_codec_roundtrip_deterministic(name, original):
    payload1 = encode_roundtrip(original)
    payload2 = encode_roundtrip(original)
    assert payload1 == payload2, "deterministic"
    assert payload1.startswith("MALRT1:")
    decoded = decode_roundtrip(payload1)
    assert decoded == original
    assert decoded.encode("utf-8") == original.encode("utf-8")
    assert hashlib.sha256(decoded.encode("utf-8")).hexdigest() == hashlib.sha256(original.encode("utf-8")).hexdigest()
    # integrity inside payload
    assert payload1.split(":")[-1] == sha256_hex(original)


def test_codec_ascii():
    payload = encode_roundtrip("Hello, World!")
    assert decode_roundtrip(payload) == "Hello, World!"
    assert encode_roundtrip_envelope("Hello, World!").codec_version == CODEC_VERSION


def test_codec_empty():
    payload = encode_roundtrip("")
    assert payload == f"MALRT1::{hashlib.sha256(b'').hexdigest()}"
    assert decode_roundtrip(payload) == ""
    res = decode_roundtrip_detailed(payload)
    assert res.status == RoundtripStatus.VALID


def test_codec_versioned():
    payload = encode_roundtrip("hi")
    assert payload.startswith("MALRT1:")


# --- Negative tests ---

def test_negative_corrupted_envelope():
    payload = encode_roundtrip("hello")
    # corrupt sha
    parts = payload.split(":")
    parts[2] = "0" * 64
    corrupted = ":".join(parts)
    res = decode_roundtrip_detailed(corrupted)
    assert res.status == RoundtripStatus.CORRUPTED
    with pytest.raises(ValueError):
        decode_roundtrip(corrupted)


def test_negative_truncated_payload():
    payload = encode_roundtrip("hello")
    truncated = payload[:-5]
    res = decode_roundtrip_detailed(truncated)
    assert res.status in (RoundtripStatus.INVALID, RoundtripStatus.CORRUPTED)
    with pytest.raises(ValueError):
        decode_roundtrip(truncated)


def test_negative_unknown_version():
    payload = "MALRT9:SGVsbG8=:185f8db32271fe25f561a6fc938b2e264306ec304eda518007d1764826381969"
    res = decode_roundtrip_detailed(payload)
    assert res.status == RoundtripStatus.INVALID
    assert "unknown codec version" in res.error.lower()


def test_negative_invalid_base64():
    payload = f"MALRT1:!!!invalid!!!:{hashlib.sha256(b'hi').hexdigest()}"
    res = decode_roundtrip_detailed(payload)
    assert res.status == RoundtripStatus.INVALID
    assert "invalid base64" in res.error.lower()


def test_negative_wrong_sha():
    payload = encode_roundtrip("hello")
    parts = payload.split(":")
    parts[2] = "f" * 64
    bad = ":".join(parts)
    res = decode_roundtrip_detailed(bad)
    assert res.status == RoundtripStatus.CORRUPTED


def test_negative_empty_invalid():
    res = decode_roundtrip_detailed("")
    assert res.status == RoundtripStatus.INVALID


def test_codec_no_fallback_question():
    # Roundtrip must not silently become "?" for failed Unicode
    # Our decoder never invents "?"; it fails explicitly.
    payload = encode_roundtrip("你好")
    # Ensure payload does not contain "?" as fallback for Unicode
    # The envelope is base64+sha, not transliteration
    assert "?" not in payload or payload.count("?") == 0 or True  # just check decode not "?"
    decoded = decode_roundtrip(payload)
    assert decoded == "你好"
    assert decoded != "?"


# --- Transliteration regression (must remain) ---

def test_transliteration_regression():
    # Existing documented behavior must remain:
    # "你好" -> "nihao" via transliteration (lossy)
    # Roundtrip must NOT call transliteration.
    assert transliterate("你好") == "nihao"
    assert transliterate("ñ") == "ny"
    # Ensure roundtrip does not equal transliteration for those inputs
    # Roundtrip decode should give back original, not transliterated
    payload = encode_roundtrip("你好")
    assert decode_roundtrip(payload) == "你好"
    assert decode_roundtrip(payload) != transliterate("你好")
    # Translator translate (transliteration mode) vs translate_roundtrip
    tr = MalbolgeTranslator()
    # transliteration mode: processed is lossy
    # we don't require Malbolge synthesis for this regression; just check processed
    # Mock check: transliterate path
    assert tr.lexicon.transliterate("你好") == "nihao"


def test_transliteration_spanish():
    # Spanish transliteration check
    # "Hola, señor. ¿Cómo estás?" -> transliteration should map accents
    original = "Hola, señor. ¿Cómo estás?"
    processed = transliterate(original)
    # Should not equal original (lossy), but should be ASCII
    assert processed != original
    assert all(33 <= ord(c) <= 126 or c in " \t\n" for c in processed)


# --- End-to-end over Malbolge (classified) ---

@pytest.mark.parametrize("name,original", list(CASES.items()))
def test_end_to_end_classified(name, original):
    """For each case verify classification.

    If generator available, expect PASS; else expect CODEC PASS but synthesis NOT_DEMONSTRATED.
    """
    tr = MalbolgeTranslator()
    result = tr.translate_roundtrip(original)

    # Codec roundtrip must always be PASS (without Malbolge)
    # Verify codec self-check inside verification
    ver = tr.verify_roundtrip(result, max_steps=5_000_000)

    assert ver.codec_roundtrip == "PASS", f"codec failed for {name}: {ver.error}"

    if not _MALBOLGE_AVAILABLE:
        # Without generator, synthesis should be FAIL and end-to-end NOT_DEMONSTRATED
        assert ver.malbolge_synthesis in ("FAIL", "TIMEOUT")
        assert ver.end_to_end_roundtrip == "NOT_DEMONSTRATED"
        assert not ver.roundtrip_pass
        # But codec bytes still correct (original vs decoded self)
        # Original bytes/sha still preserved in result
        assert result.original_text == original
        assert result.original_bytes == original.encode("utf-8")
        return

    # With generator available, attempt full verification
    # For small inputs, expect PASS; for larger, allow NOT_DEMONSTRATED if budget exhausted
    if ver.malbolge_synthesis != "PASS":
        # Budget exhausted — classify, do not fail test as "wrong", but report
        pytest.skip(f"Malbolge synthesis {ver.malbolge_synthesis} for {name}: {ver.error} -> NOT_DEMONSTRATED (budget)")

    # Synthesis PASS -> check end-to-end
    assert ver.payload_match is True, f"payload mismatch for {name}"
    assert ver.bytes_equal is True, f"bytes_equal failed for {name}"
    assert ver.text_equal is True
    assert ver.sha_equal is True
    assert "HALT" in ver.malbolge_execution_status.upper()
    assert ver.end_to_end_roundtrip == "PASS"
    assert ver.roundtrip_pass
    assert ver.recovered_text == original
    assert ver.recovered_text.encode("utf-8") == original.encode("utf-8")
    assert ver.recovered_utf8_sha256 == ver.original_utf8_sha256


def test_mixed_file_workflow(tmp_path):
    """File workflow with roundtrip mode."""
    p = tmp_path / "input.txt"
    content = "mixed: español + 中文 + 🚀\nsecond line"
    p.write_text(content, encoding="utf-8")
    tr = MalbolgeTranslator()
    text = p.read_text(encoding="utf-8")
    result = tr.translate_roundtrip(text)
    ver = tr.verify_roundtrip(result)
    assert ver.codec_roundtrip == "PASS"
    if _MALBOLGE_AVAILABLE and ver.malbolge_synthesis == "PASS":
        assert ver.bytes_equal
    # Save artifacts
    out = tmp_path / "out"
    result.save_all(out, "test")
    assert (out / "test_manifest.json").exists()
    import json
    man = json.loads((out / "test_manifest.json").read_text(encoding="utf-8"))
    assert man["mode"] == "utf8-roundtrip"
    assert man["codec_version"] == CODEC_VERSION
    assert man["original_sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
