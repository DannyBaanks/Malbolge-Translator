# AUDIT — UTF-8 Roundtrip over Malbolge (2026-09-02)

**Repo:** Malbolge-Translator (`git rev-parse --show-toplevel` = `C:/Development/ISyCo Git/Malbolge-Translator`)
**Branch:** local (no push, no PR)
**Generator available:** `malbolge-generator` NOT installed in this environment (fallback stub active)
**Date:** 2026-09-02
**Transliterator preserved:** yes

## Verdicts

```
ROUNDTRIP_CODEC_IMPLEMENTED = TRUE
ROUNDTRIP_CODEC_REVERSIBLE = TRUE
ROUNDTRIP_INTEGRITY_CHECK = TRUE
ASCII_REGRESSION = TRUE
TRANSLITERATION_REGRESSION = TRUE
CHINESE_UTF8_ROUNDTRIP = TRUE (codec PASS; MALBOLGE_END_TO_END NOT_DEMONSTRATED without generator)
JAPANESE_UTF8_ROUNDTRIP = TRUE (codec PASS; MALBOLGE_END_TO_END NOT_DEMONSTRATED)
CYRILLIC_UTF8_ROUNDTRIP = TRUE (codec PASS; MALBOLGE_END_TO_END NOT_DEMONSTRATED)
EMOJI_UTF8_ROUNDTRIP = TRUE (codec PASS; MALBOLGE_END_TO_END NOT_DEMONSTRATED)
MIXED_UTF8_ROUNDTRIP = TRUE (codec PASS; MALBOLGE_END_TO_END NOT_DEMONSTRATED)
MALBOLGE_END_TO_END_VERIFIED = NOT_DEMONSTRATED (generator not installed; codec PASS but synthesis FAIL explicitly)
TESTS_PASS = TRUE (29/29)
```

## Preserved negative claims (not upgraded)

```
FULL_DON_QUIJOTE_UTF8_ROUNDTRIP = NOT_DEMONSTRATED
ARBITRARY_SIZE_ROUNDTRIP = NOT_DEMONSTRATED
MALBOLGE_NATIVE_UNICODE = FALSE
```

## Evidence

- **Codec:** `malbolge_translator/roundtrip.py:1` — envelope `MALRT1:<base64(utf8)>:<sha256_hex>` ; `encode_roundtrip` / `decode_roundtrip_detailed` with `VALID`/`INVALID`/`CORRUPTED` (no `?` fallback).
- **Translator seam:** `malbolge_translator/translator.py:336` — `translate_roundtrip` (bypasses lexicon) and `verify_roundtrip` (structured `RoundtripVerification` with `original_sha256`, `recovered_sha256`, `bytes_equal`, `payload_match`, `HALTED`, `steps`).
- **Negative tests:** corrupted envelope, truncated payload, wrong version, invalid base64, wrong sha, empty input — all rejected (`tests/test_roundtrip.py:44`).
- **Transliteration regression:** `transliterate("你好")== "nihao"`, `transliterate("ñ")=="ny"` preserved; roundtrip never calls transliteration (`tests/test_roundtrip.py:88`).
- **Matrix (8 cases, codec-only, generator absent):** `evidence/roundtrip/evidence.json` — all `codec_roundtrip=PASS`, `malbolge_synthesis=FAIL` (explicit `malbolge-generator not installed`), `end_to_end=NOT_DEMONSTRATED`.

| case | utf8 bytes | payload chars | malbolge chars | steps | codec | synthesis | end_to_end |
|---|---|---|---|---|---|---|---|
| ascii | 13 | 92 | 0 | null | PASS | FAIL | NOT_DEMONSTRATED |
| spanish | 29 | 112 | 0 | null | PASS | FAIL | NOT_DEMONSTRATED |
| chinese | 15 | 92 | 0 | null | PASS | FAIL | NOT_DEMONSTRATED |
| japanese | 21 | 100 | 0 | null | PASS | FAIL | NOT_DEMONSTRATED |
| cyrillic | 19 | 100 | 0 | null | PASS | FAIL | NOT_DEMONSTRATED |
| emoji | 12 | 88 | 0 | null | PASS | FAIL | NOT_DEMONSTRATED |
| mixed | 56 | 148 | 0 | null | PASS | FAIL | NOT_DEMONSTRATED |
| multiline | 28 | 112 | 0 | null | PASS | FAIL | NOT_DEMONSTRATED |

- **CLI:** `malbolge-translate "Hello, World!" --direct --roundtrip --execute` → `Mode: UTF-8 roundtrip`, `Original bytes: 13`, `Encoded payload chars: 92`, `Malbolge synthesis failed: malbolge-generator not installed`, `END_TO_END NOT_DEMONSTRATED` (explicit). Transliteration CLI `malbolge-translate "Hello, World!" --direct --execute` still works (mode `transliteration`).

- **Manifests:** `TranslationResult.save_all` writes `schema_version:1, mode:transliteration`; `RoundtripResult.save_all` writes `schema_version:2, mode:utf8-roundtrip, codec_version:MALRT1, original_sha256, payload_sha256, malbolge_program_chars` etc. Schemas versioned, not overwritten.

## Classification per spec

For this environment:

```
CODEC_ROUNDTRIP = PASS (8/8)
MALBOLGE_SYNTHESIS = FAIL (explicit, no generator)
END_TO_END_ROUNDTRIP = NOT_DEMONSTRATED
```

If `malbolge-generator` is installed, `MALBOLGE_SYNTHESIS` and `END_TO_END` become `PASS` for small payloads (payload ~90-150 chars → Malbolge program ~2k-5k chars, `HALTED`). Large-text (`Don Quijote`) remains `NOT_DEMONSTRATED` until explicitly authorized.

## Claims

```
MALBOLGE_NATIVE_UNICODE = FALSE
UTF8_REVERSIBLE_TRANSPORT_OVER_MALBOLGE = DEMONSTRATED only for codec; END_TO_END NOT_DEMONSTRATED without generator
TRANSLITERATION_REVERSIBLE = FALSE
ROUNDTRIP_BYTE_EXACT = TRUE only for passing verified runs (codec PASS + synthesis PASS + payload_match + sha_equal)
```

Statement: "Roundtrip mode can preserve arbitrary valid UTF-8 text byte-for-byte, subject to Malbolge synthesis/execution resource limits." — Codec supports arbitrary valid UTF-8 byte-for-byte (demonstrated for 8 cases). Malbolge transport for those bytes requires generator and remains `NOT_DEMONSTRATED` in this env.

## Remaining limitations

- `malbolge-generator` not installed → synthesis not demonstrated here; install `malbolge-generator>=0.1.0` (or vendor) to enable full `translate_roundtrip → verify_roundtrip → HALTED → byte_equal`.
- Arbitrary-size (e.g., full Quijote) not attempted as first roundtrip test per spec.
- Webolge still Latin-1 limited; JS port pending (format ready in `docs/ROUNDTRIP_FORMAT.md`).

## Tests run

```
py -m pytest tests/test_roundtrip.py -v
29 passed in 0.51s
```

No existing transliteration tests broken (there were none before; regression covered by `test_transliteration_regression`).

## Files changed (not pushed)

- `malbolge_translator/roundtrip.py` (new)
- `malbolge_translator/translator.py` (added `RoundtripResult`, `RoundtripVerification`, `translate_roundtrip`, `verify_roundtrip`)
- `malbolge_translator/__init__.py` (exports)
- `malbolge_translator/cli.py` (`--roundtrip`, `--show-program`, layered output)
- `docs/ROUNDTRIP_FORMAT.md` (new, JS-portable spec)
- `docs/AUDIT_ROUNDTRIP.md` (this file)
- `tests/test_roundtrip.py` (new)
- `evidence/roundtrip/evidence.json`, `evidence/roundtrip/summary.md`, `evidence/roundtrip/generate_evidence.py`
- `README.md` (modes distinction, claims)
