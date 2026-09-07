# Malbolge Translator

**Genera programas de Malbolge puro que imprimen texto arbitrario exactamente.**

![Malbolge Translator Session](malbolge_session.gif)

Esta herramienta usa sintesis incremental de estado-maquina con resets periodicos de ancla para hacer la generacion de texto de Malbolge practica para textos arbitrariamente largos.

## Como funciona

Malbolge es un lenguaje auto-modificante y counter-machine donde cada instruccion depende del estado completo del maquina. Los enfoques tradicionales intentan generar el programa completo de una vez, lo cual es inviable para textos largos.

Este traductor descompone el problema:

```
[Bootstrap: i + o*99] → Estado Ancla (memoria limpia, sin output)
        ↓
[Continuacion Palabra 1] → [Continuacion Palabra 2] → ... → [Continuacion Palabra N + halt]
        ↓                    ↓
   (estado del maquina    (estado del maquina
    avanza)                avanza)
        ↓
[Cada N palabras: Bridge → Reset a Ancla → Continuar]
```

- **Ancla**: Un estado canonico del maquina alcanzado por una secuencia de bootstrap fija. Identificado por un hash de (A, C, D, tape[:100]).
- **Continuacion**: Opcodes que, cuando se ejecutan *desde un estado especifico del maquina*, producen la siguiente palabra.
- **Banco de Palabras**: Cache de (anchor_hash, word) → continuacion. Solo valido cuando el estado del maquina coincide con el ancla.
- **Cadena Lineal**: La continuacion de cada palabra se ejecuta desde el estado final de la palabra anterior.

El resultado es **un stream lineal de opcodes** con **un halt final** (`v`).

## Instalacion

```bash
# Requiere Python 3.10+
pip install malbolge-generator
pip install -e .
```

O desde fuente:

```bash
git clone <this-repo>
cd Malbolge-Translator
pip install -e .
```

## Inicio Rapido

```bash
# Transliteracion (legible, lossy)
malbolge-translate "Hola mundo" --execute
malbolge-translate "你好" --direct --execute

# Roundtrip UTF-8 exacto reversible (byte-exact)
malbolge-translate "你好，世界 😭🔥" --direct --roundtrip --execute
malbolge-translate "Hola, señor. ¿Cómo estás?" --direct --roundtrip --execute

# Transport UTF-8 bounded de dos partes: dos programas independientes, uno por mitad
malbolge-translate "Hi :p" --direct --roundtrip --two-part --output-dir two_part_out

# Traducir archivo
malbolge-translate input.txt --output-dir out --execute
malbolge-translate input.txt --roundtrip --output-dir out --execute

# Con mapeos de lexico custom (solo modo transliteracion)
malbolge-translate "Hola 世界" --lexicon-add 世 shi --lexicon-add 界 jie --execute
```

## Generar Don Quijote (Demo Artifact)

```bash
# Descarga desde Project Gutenberg, genera .mal completo
malbolge-quijote --output-dir artifacts/quijote --execute
```

Esto crea:
- `artifacts/quijote/quijote_full.mal` — programa de Malbolge puro (~50 MB)
- `artifacts/quijote/quijote_full.op` — opcodes raw
- `artifacts/quijote/manifest.json` — metadata (manifests por capitulo en
  `artifacts/quijote/chapter_NNN/quijote_chNNN_manifest.json`)

## Modos

### Modo A — Transliteracion (lossy, legible)

```
Unicode input → aproximacion ASCII legible → Malbolge → aproximacion
```

Propiedades: legible = usualmente si, reversible = no, byte exact = no.
Ejemplo: `"你好" → "nihao"`, `"ñ" → "ny"`. Util para display pero no byte-exact.

### Modo B — Roundtrip UTF-8 exacto (reversible, byte-exact)

```
TEXTO UTF-8 ORIGINAL → envoltura ASCII reversible (MALRT1) → programa Malbolge puro → ejecucion canonica → payload ASCII → decode → TEXTO UTF-8 ORIGINAL
```

Envoltura: `MALRT1:<base64(utf8_bytes)>:<sha256_hex>`. Deterministica, ASCII-safe, versionada, verificada de integridad.
Propiedades: payload legible = irrelevante, reversible = si, byte exact = si cuando la verificacion pasa.

**Claims (hasta que se demuestre lo contrario):**

```
MALBOLGE_NATIVE_UNICODE = FALSE
TRANSLITERATION_REVERSIBLE = FALSE
ROUNDTRIP_BYTE_EXACT = TRUE solo para runs verificadas que pasan
FULL_DON_QUIJOTE_UTF8_ROUNDTRIP = NOT_DEMONSTRATED
ARBITRARY_SIZE_ROUNDTRIP = NOT_DEMONSTRATED
FRESH_VM_CONTINUATION = NOT_DEMONSTRATED
```

El modo roundtrip puede preservar texto UTF-8 valido arbitrario byte por byte, sujeto a limites de recursos de sintesis/ejecucion de Malbolge.
No reclames "soporta todos los idiomas" — es transporte de bytes, no cobertura linguistica.

### Roundtrip de Dos Partes

`--two-part` divide UTF-8 valido en un byte-safe boundary y aplica el
roundtrip MALRT1 existente a cada mitad. `independent` (el default) sintetiza y
verifica ambos programas; `verify-first` persiste y re-lee prueba solo para la parte uno,
asi que retorna deliberadamente `PART_1_ROUNDTRIP_ONLY` en vez de un claim de
archivo completo. `--max-part-bytes` defaults a 4096 y rechaza partes mas grandes antes de
escribir artifacts.

Este es un convenio de transporte bounded, no continuacion cross-VM ni
evidencia de que el Don Quijote completo pueda generarse o ejecutarse.

```python
from malbolge_translator import MalbolgeTranslator, encode_roundtrip, decode_roundtrip

# Codec solo (sin Malbolge)
payload = encode_roundtrip("你好，世界 😭🔥")
assert decode_roundtrip(payload) == "你好，世界 😭🔥"

# Transport completo sobre Malbolge
translator = MalbolgeTranslator()
result = translator.translate_roundtrip("你好，世界 😭🔥")
verification = translator.verify_roundtrip(result)
# verification.original_utf8_sha256, verification.recovered_utf8_sha256, verification.bytes_equal, verification.sha_equal, verification.malbolge_execution_status, verification.malbolge_steps, verification.encoded_payload
assert verification.roundtrip_pass
```

### Distincion CLI

```bash
# Transliteracion legible
malbolge-translate "你好" --direct --execute

# UTF-8 exacto reversible
malbolge-translate "你好" --direct --roundtrip --execute

# Flujos de trabajo de archivo
malbolge-translate input.txt --output-dir out --execute
malbolge-translate input.txt --roundtrip --output-dir out --execute
```

El output de ejecucion roundtrip distingue capas:

```
Modo: UTF-8 roundtrip
Bytes originales: 18
Chars de payload encoded: 96
Chars de programa Malbolge: 12450
Ejecucion: HALTED
Payload match: TRUE
UTF-8 bytes match: TRUE
SHA256 match: TRUE
ROUNDTRIP: PASS
```

## Arquitectura

### Componentes Centrales

| Modulo | Proposito |
|--------|---------|
| `translator.py` | Pipeline principal de traduccion: lexicon → split → sintetizar → chain + `translate_roundtrip` / `verify_roundtrip` |
| `roundtrip.py` | Codec UTF-8 reversible: `MALRT1:<base64>:<sha256>` (sin logica Malbolge) |
| `two_part_roundtrip.py` | Flujo de trabajo bounded de dos programas MALRT1 y verificacion persistida |
| `anchor.py` | AnchorManager, WordBank — estados canonicos y cache de continuaciones |
| `lexicon.py` | Mapeos extensibles por usuario (transliteracion/encoding) |
| `cli.py` | Interfaz de linea de comandos (`--roundtrip`, `--show-program`) |
| `render_session.py` | Renderer de GIF de sesion (como session.gif de FLOW) |

### API Publica

```python
from malbolge_translator import MalbolgeTranslator, Lexicon, encode_roundtrip, decode_roundtrip

# Transliteracion (existente)
translator = MalbolgeTranslator(anchor_interval=50)
result = translator.translate("Hello world")
translator.execute(result)  # verifica output exacto

# Roundtrip (nuevo)
result = translator.translate_roundtrip("你好，世界 😭🔥")
verification = translator.verify_roundtrip(result)
# o
result, verification = translator.translate_and_verify_roundtrip("Hola, señor", max_steps=5_000_000)

# Lexico custom (solo transliteracion)
lex = Lexicon()
lex.add("ñ", "ny")
lex.add("中", "zhong")
translator = MalbolgeTranslator(lexicon=lex)
```

## Lexico / Encoding

La herramienta incluye un lexico con 300+ mapeos (transliteracion, lossy):

- Espanol: `áéíóúñ` → `aeiouny`
- Frances: `àâäçèêë` → `aaceee`
- Aleman: `ßäöü` → `ssaeoeue`
- Griego/Cirillico/Chino/Japones/Coreano
- Simbolos, matematicas, flechas, box drawing, emoji

**Importante — Modo A (transliteracion)**: aproximacion lossy. `TRANSLITERATION_REVERSIBLE = FALSE`. Los bytes originales no se preservan.

**Modo B (roundtrip)** proporciona preservacion exacta via codec reversible (`roundtrip.py`). No se usa transliteracion ahi; los bytes UTF-8 originales sobreviven exactamente.

Agregar mapeos custom (solo modo transliteracion):
```bash
malbolge-translate "text" --lexicon-add 世 shi --lexicon-add 界 jie
```

## Garantia de Output Exacto

Cada ejecucion `--execute` realiza:

```
sintetizar → interprete canonico → comparacion exacta → MATCH / MISMATCH
```

El interprete canonico es el interprete estandar de Malbolge (memoria 3^10, crazy-op, auto-encriptacion). Sin extensiones custom.

- **Modo transliteracion**: `MISMATCH` vs original es esperado (aproximacion); `MATCH` vs transliterado se verifica.
- **Modo roundtrip**: `verification.bytes_equal` + `sha_equal` + `payload_match` + `HALTED` deben ser todos `TRUE` para `ROUNDTRIP: PASS`. Ver `evidence/roundtrip/` y `docs/ROUNDTRIP_FORMAT.md`.

Artifacts: `*_manifest.json` ahora incluye `mode`, `codec_version`, `original_sha256`, `payload_sha256`, `malbolge_execution_status`, `payload_match`, `bytes_match` etc (schema v2 para roundtrip, v1 para transliteracion — versionado, no sobreescrito).
```
MALBOLGE_NATIVE_UNICODE = FALSE  # Malbolge no tiene Unicode nativo; el transporte UTF-8 es via ASCII codec sobre Malbolge

UTF8_REVERSIBLE_TRANSPORT_OVER_MALBOLGE = DEMONSTRATED solo cuando los tests end-to-end pasan (ver docs/AUDIT_ROUNDTRIP.md)
```

## Requisitos

- Python 3.10+
- Paquete `malbolge-generator` (provee ProgramGenerator, MalbolgeInterpreter)

## Testing

```bash
# Correr tests basicos
malbolge-translate "Hola mundo" --execute
malbolge-translate "The quick brown fox" --execute
malbolge-translate "def foo(): return 42" --execute
```

## Licencia

MIT
