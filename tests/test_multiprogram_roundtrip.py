import pytest

from malbolge_translator.multiprogram_roundtrip import (
    MALRT1_ALPHABET,
    SymbolProgram,
    build_symbol_dictionary,
    transport_text,
    verify_symbol_dictionary,
)
from malbolge_translator.roundtrip import encode_roundtrip


def _identity_dictionary() -> dict[str, SymbolProgram]:
    return {
        symbol: SymbolProgram(
            symbol=symbol,
            opcodes="v",
            program="v",
            output=symbol,
            steps=1,
            halt_reason="halt_opcode",
            deterministic=True,
        )
        for symbol in MALRT1_ALPHABET
    }


def test_alphabet_covers_every_possible_malrt1_payload_symbol():
    text = "ASCII espanol 中文 日本語 Привет 😭🔥🚀\n" * 100
    assert set(encode_roundtrip(text)).issubset(set(MALRT1_ALPHABET))


def test_large_finite_input_roundtrips_by_dictionary_construction():
    text = ("En un lugar de la Mancha, 中文, 😭🔥.\n" * 30_000)[:1_000_000]
    evidence = transport_text(text, _identity_dictionary())
    assert evidence.source_bytes >= 1_000_000
    assert evidence.dictionary_complete
    assert evidence.payload_match
    assert evidence.bytes_equal
    assert evidence.roundtrip_pass
    assert evidence.source_sha256 == evidence.recovered_source_sha256


def test_missing_symbol_fails_closed():
    dictionary = _identity_dictionary()
    del dictionary[":"]
    try:
        transport_text("hello", dictionary)
    except ValueError as exc:
        assert "missing MALRT1 symbols" in str(exc)
    else:
        raise AssertionError("missing symbol must fail closed")


def test_real_malbolge_symbol_programs_execute_deterministically():
    entries = build_symbol_dictionary("M:Az+/=1")
    assert all(entry.pass_ for entry in entries.values())
    assert all(entry.output == symbol for symbol, entry in entries.items())


def test_full_dictionary_reverification_fails_closed_on_incomplete_dictionary():
    dictionary = _identity_dictionary()
    del dictionary[":"]
    assert not verify_symbol_dictionary(dictionary)


def test_codec_only_mode_keeps_transport_but_rejects_synthesis(monkeypatch):
    import malbolge_translator.multiprogram_roundtrip as multiprogram

    monkeypatch.setattr(multiprogram, "_MALBOLGE_AVAILABLE", False)

    evidence = transport_text("codec only", _identity_dictionary())

    assert evidence.roundtrip_pass
    assert not verify_symbol_dictionary(_identity_dictionary())
    with pytest.raises(RuntimeError, match="malbolge-generator is required"):
        build_symbol_dictionary("A")
