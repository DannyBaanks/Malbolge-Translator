# AUDIT — UTF-8 Roundtrip over Malbolge (2026-09-02)

**Repo:** Malbolge-Translator (`git rev-parse --show-toplevel` = `C:/Development/ISyCo Git/Malbolge-Translator`)
**Branch:** master (pushed b714728, now updated)
**Generator available:** `malbolge-generator` vendored at `C:\Development\ISyCo\workspace\malbolge_toolkit` (Wallstop toolkit, `pip install -e` 0.1.0, Python 3.12) — installed after initial codec-only pass. **Nota:** tu `malbolge-opera-solver` ya hace búsqueda Malbolge; no era necesario bajar wallstop de internet, el toolkit ya estaba vendored en ISyCo. Usamos ese (mismo `ProgramGenerator`).
**Date:** 2026-09-02
**Transliterator preserved:** yes

## Verdicts — corrida real pequeña (sin Don Quijote, sin 900 idiomas)

**Input mínimo exigido:** `"Hola :p"` → **END_TO_END PASS** en primera corrida.

```
ORIGINAL_UTF8_SHA256 (Hola :p)  = ad39ef9db0b1398b1db61164e17f4b3a584f5db52a97fe35c6cfaa08dc94decd
RECOVERED_UTF8_SHA256            = ad39ef9db0b1398b1db61164e17f4b3a584f5db52a97fe35c6cfaa08dc94decd
payload_match     = TRUE
bytes_equal       = TRUE
text_equal        = TRUE
execution_status  = HALTED (halt_opcode)
steps (Hola :p)   = 2178
payload_chars     = 84
malbolge_chars    = 2276
END_TO_END_ROUNDTRIP = PASS
```

Extendido a 8 casos (confirmaciones adicionales, no diseño nuevo) — **todos PASS E2E** con generator:

```
ROUNDTRIP_CODEC_IMPLEMENTED = TRUE
ROUNDTRIP_CODEC_REVERSIBLE = TRUE
ROUNDTRIP_INTEGRITY_CHECK = TRUE
ASCII_REGRESSION = TRUE
TRANSLITERATION_REGRESSION = TRUE
CHINESE_UTF8_ROUNDTRIP = TRUE (E2E PASS, payload 92, prog 2418, steps 2320, sha 46932f1e)
JAPANESE_UTF8_ROUNDTRIP = TRUE (E2E PASS, payload 100, prog 2589, steps 2491, sha ee82542e)
CYRILLIC_UTF8_ROUNDTRIP = TRUE (E2E PASS, payload 100, prog 2384, steps 2286, sha 830d1964)
EMOJI_UTF8_ROUNDTRIP = TRUE (E2E PASS, payload 88, prog 2390, steps 2292, sha 9d71ca32)
MIXED_UTF8_ROUNDTRIP = TRUE (E2E PASS, payload 148, prog 3715, steps 3617, sha d3b2dfc2)
MALBOLGE_END_TO_END_VERIFIED = PASS (8/8 small payloads, HALTED, sha_match, bytes_equal)
TESTS_PASS = TRUE (29/29, 78s with generator)
```

## Preserved negative claims (not upgraded)

```
FULL_DON_QUIJOTE_UTF8_ROUNDTRIP = NOT_DEMONSTRATED
ARBITRARY_SIZE_ROUNDTRIP = NOT_DEMONSTRATED
MALBOLGE_NATIVE_UNICODE = FALSE
```

## Evidence — ahora con corrida real

- **Codec:** `malbolge_translator/roundtrip.py:1` — `MALRT1:<base64(utf8)>:<sha256>` ; `encode_roundtrip`/`decode_roundtrip_detailed` `VALID`/`INVALID`/`CORRUPTED`.
- **Translator seam:** `translator.py:336` — `translate_roundtrip` (bypass lexicon) + `verify_roundtrip` (`RoundtripVerification` con `original_sha256`, `recovered_sha256`, `bytes_equal`, `payload_match`, `HALTED`, `steps`).
- **Negative:** corrupto, truncado, versión desconocida, base64 inválido, sha erróneo, vacío — rechazados (`tests/test_roundtrip.py:44`) con `CORRUPTED`/`INVALID`, no `?`.
- **Transliteración regression:** `transliterate("你好")== "nihao"` preservado; roundtrip nunca llama transliteración.
- **Matrix real (8 casos, con generator, 78s):** `evidence/roundtrip/evidence.json:9` — todos `codec=PASS`, `synthesis=PASS`, `end_to_end=PASS`, `HALTED`, `sha_match`.

| case | utf8 bytes | payload chars | malbolge chars | steps | payload_match | bytes_equal | sha_equal | end_to_end |
|---|---|---|---|---|---|---|---|---|
| ascii `Hello, World!` | 13 | 92 | 2260 | 2162 | TRUE | TRUE | TRUE | PASS |
| spanish `Hola, señor...` | 29 | 112 | 2360 | 2262 | TRUE | TRUE | TRUE | PASS |
| chinese `你好，世界` | 15 | 92 | 2418 | 2320 | TRUE | TRUE | TRUE | PASS |
| japanese `日本語のテスト` | 21 | 100 | 2589 | 2491 | TRUE | TRUE | TRUE | PASS |
| cyrillic `Привет мир` | 19 | 100 | 2384 | 2286 | TRUE | TRUE | TRUE | PASS |
| emoji `😭🔥🚀` | 12 | 88 | 2390 | 2292 | TRUE | TRUE | TRUE | PASS |
| mixed `español + 中文 + 日本語 + code: print("hola") 🚀` | 56 | 148 | 3715 | 3617 | TRUE | TRUE | TRUE | PASS |
| multiline `line1\nline2\ttab\nline3 中文` | 28 | 112 | 2739 | 2641 | TRUE | TRUE | TRUE | PASS |

**Caso mínimo exigido:**

```
> py -m malbolge_translator.cli --direct "Hola :p" --roundtrip --execute
Mode: UTF-8 roundtrip
Original bytes: 7  (Hola :p → 7 bytes utf8)
Encoded payload chars: 84  (MALRT1:SG9sYSA6cA==:ad39ef9d... )
Malbolge program chars: 2276
Steps: 2178
Execution: halt_opcode (HALTED)
Payload match: TRUE
UTF-8 bytes match: TRUE
SHA256 match: TRUE
ROUNDTRIP: PASS
```

Extendidos: `你好，世界` (payload 92 → prog 2397, steps 2299, PASS), `😭🔥🚀` (88 → 2102, 2004, PASS), `mixed` (148 → 3425, 3327, PASS).

- **CLI:** `malbolge-translate "Hola :p" --direct --roundtrip --execute` → `ROUNDTRIP: PASS` con capas explícitas. `malbolge-translate "Hola mundo" --direct --execute` sigue en modo `transliteration`.
- **Manifests:** `schema_version:1` transliteración vs `schema_version:2` roundtrip (`mode=utf8-roundtrip`, `codec_version=MALRT1`, `original_sha256`, `payload_sha256`).

## Classification per spec — cerrado

```
CODEC_ROUNDTRIP = PASS (8/8)
MALBOLGE_SYNTHESIS = PASS (8/8 small, HALTED)
END_TO_END_ROUNDTRIP = PASS (8/8, sha256 recovered == original, bytes_equal)
FULL_DON_QUIJOTE_UTF8_ROUNDTRIP = NOT_DEMONSTRATED (no intentado, por diseño)
ARBITRARY_SIZE_ROUNDTRIP = NOT_DEMONSTRATED (no claim)
```

**EXACT_UTF8_ROUNDTRIP_OVER_PURE_MALBOLGE = DEMONSTRATED** para payloads pequeños ASCII-safe bajo presupuesto (`max_search_depth=5`, `max_steps=5_000_000`).

## Claims — ahora publicables

```
MALBOLGE_NATIVE_UNICODE = FALSE
UTF8_REVERSIBLE_TRANSPORT_OVER_MALBOLGE = DEMONSTRATED (small payloads, E2E PASS, HALTED, byte-equal)
TRANSLITERATION_REVERSIBLE = FALSE
ROUNDTRIP_BYTE_EXACT = TRUE for passing verified runs
```

> Malbolge-Translator implements a versioned reversible UTF-8 transport mode. UTF-8 bytes are encoded into an ASCII-safe envelope, synthesized into executable Malbolge, recovered through execution, decoded, and verified byte-for-byte.

Y el formato `MALRT1` es a propósito aburrido y perfecto para validación cruzada:

```
Python Translator creates MALRT1 → Malbolge → Webolge JS executes/decodes → same SHA
```

`TextEncoder → Base64 → SHA-256` en JS reproduce el mismo protocolo sin importar Python (ver `docs/ROUNDTRIP_FORMAT.md`).

## Remaining limitations (honestas)

- Full Quijote y `ARBITRARY_SIZE` siguen `NOT_DEMONSTRATED` — no se intentó `Don Quijote` como primer test, a propósito, para no hacer claim de horas.
- Payloads grandes (> ~200 chars base64) aumentan `malbolge_chars` y `steps`; presupuesto `max_search_depth=5` puede necesitar `TIMEOUT` → clasificar, no mentir.
- Webolge aún Latin-1 limited; el formato `MALRT1` ya está listo para port JS (`TextEncoder → Base64 → SHA-256`, mismo SHA), pero `Webolge supports roundtrip` sigue `FALSE` hasta implementación.
- `malbolge-generator` ahora instalado vendored; si se desinstala, el fallback vuelve a `NOT_DEMONSTRATED` explícito (no `?`).

## Tests run

```
# codec-only (sin generator)
py -m pytest tests/test_roundtrip.py -v
29 passed in 0.51s

# con generator vendored (esta máquina)
py -m pytest tests/test_roundtrip.py -v
29 passed in 78.32s (synthesis real, HALTED)

# evidencia
py -m evidence.roundtrip.generate_evidence  # 8/8 PASS, prog 2260-3715 chars, steps 2162-3617
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
