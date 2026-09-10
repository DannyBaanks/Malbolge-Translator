from malbolge_translator.single_program import CLASSIC_TAPE_CELLS, preflight_single_program


def test_preflight_reports_classic_source_ceiling():
    result = preflight_single_program("a" * (CLASSIC_TAPE_CELLS + 1))

    assert result.source_utf8_bytes == CLASSIC_TAPE_CELLS + 1
    assert not result.direct_payload_fits
    assert result.verdict == "NOT_DEMONSTRATED"


def test_preflight_never_promotes_compression_to_a_program_claim():
    result = preflight_single_program("a" * (CLASSIC_TAPE_CELLS + 1))

    assert result.compressed_payload_fits
    assert result.verdict == "NOT_DEMONSTRATED"
    assert "does not demonstrate" in result.scope
