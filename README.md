# Malbolge Translator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-44%20passed-brightgreen)](#testing)

**Genera programas de Malbolge puro que imprimen texto arbitrario exactamente.**

![Malbolge Translator Session](malbolge_session.gif)

Esta herramienta usa sintesis incremental de estado-maquina con resets periodicos de ancla para hacer la generacion de texto de Malbolge practica para textos arbitrariamente largos.

---

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

---

## Instalacion

```bash
# Requiere Python 3.10+
pip install malbolge-generator
pip install -e .
```

O desde fuente:

```bash
git clone https://github.com/DannyBaanks/Malbolge-Translator.git
cd Malbolge-Translator
pip install -e .
```

---

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

---

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

---

## Modos

### Modo A — Transliteracion (lossy, legible)

```
Unicode input → aproximacion ASCII legible → Malbolge → aproximacion
```

Propiedades: legible = usualmente si, reversible = no, byte exact = no.
Ejemplo: `"你好" → "nihao"`, `"ñ" → "ny"`. Util para display pero no byte-exact.

### Modo B — Roundtrip UTF-8 exacto (reversible, byte-exact)

```
TEXTO UTF-8 ORIGINAL → envoltura ASCII reversible (MALRT1) → programa Malbolge puro
    → ejecucion canonica → payload ASCII → decode → TEXTO UTF-8 ORIGINAL
```

Envoltura: `MALRT1:<base64(utf8_bytes)>:<sha256_hex>`. Deterministica, ASCII-safe, versionada, verificada de integridad.
Propiedades: payload legible = irrelevante, reversible = si, byte exact = si cuando la verificacion pasa.

**Claims:**

```
MALBOLGE_NATIVE_UNICODE        = FALSE
TRANSLITERATION_REVERSIBLE     = FALSE
ROUNDTRIP_BYTE_EXACT           = TRUE solo para runs verificadas que pasan
FRESH_VM_CONTINUATION          = DEMONSTRATED (snapshot serializado + VM fresca, output byte-identico)
ARBITRARY_SIZE_ROUNDTRIP       = DEMONSTRATED (perfil multiprograma, inputs finitos)
FULL_DON_QUIJOTE_UTF8_ROUNDTRIP= DEMONSTRATED (perfil multiprograma por diccionario)
SINGLE_PROGRAM_FULL_DON_QUIJOTE= NOT_DEMONSTRATED
SINGLE_PROGRAM_ARBITRARY_SIZE  = NOT_CLAIMED
```

El modo roundtrip puede preservar texto UTF-8 valido arbitrario byte por byte, sujeto a limites de recursos de sintesis/ejecucion de Malbolge.
No reclames "soporta todos los idiomas" — es transporte de bytes, no cobertura linguistica.

---

### Continuacion en VM fresca

`malbolge_translator.fresh_vm_continuation` demuestra que un programa Malbolge
puede detenerse a mitad de vuelo, serializar su estado de maquina
(tape + `a`/`c`/`d` + `halted`), y terminar en un `MalbolgeInterpreter()`
**nuevo** produciendo output byte-identico. La propiedad verificada es
`prefijo.output + sufijo.output == corrida.completa.output`, apoyandose en
`MalbolgeMachine.copy()` y `execute_from_snapshot()` del toolkit (que
reverse-normaliza el sufijo en la posicion absoluta correcta).

```python
from malbolge import ProgramGenerator
from malbolge_translator import run_fresh_vm_continuation

opcodes = ProgramGenerator().generate_for_string("Hello, World!").opcodes
evidence = run_fresh_vm_continuation(opcodes)
assert evidence.fresh_vm_continuation_pass
```

Evidencia: `evidence/fresh_vm_continuation/evidence.json` (3/3 PASS).

---

### Roundtrip multiprograma de tamano arbitrario

MALRT1 solo usa 66 simbolos (`A-Z`, `a-z`, `0-9`, `+`, `/`, `=` y `:`).
`multiprogram_roundtrip.py` sintetiza un programa Malbolge puro por simbolo,
lo ejecuta dos veces en VMs frescas y sella sus opcodes/programa con SHA-256.
El harness representa cualquier payload finito como referencias a ese
diccionario y concatena exclusivamente el stdout verificado de esos programas.

```
UTF-8 arbitrario → MALRT1 → referencias a 66 programas .mal
                   → stdout concatenado → MALRT1 decode → UTF-8 original
```

Evidencia ejecutada:

- Diccionario completo: `66/66 PASS`.
- Control grande: `1,000,000` bytes UTF-8 → `1,333,408` chars MALRT1 → bytes y SHA-256 identicos.
- Don Quijote completo en espanol, Gutenberg #2000: `2,205,980` bytes → `2,941,380` chars MALRT1 → bytes y SHA-256 identicos.
- SHA-256 del cuerpo recuperado: `7afbd0f1fa8f2397d280d5fc81ce03e2133ffa34e68251793289861121e03a2c`.

```bash
py -m evidence.multiprogram.generate_evidence
py -m evidence.multiprogram.run_full_quijote
```

Alcance preciso: esto demuestra transporte **multiprograma** de inputs finitos
de longitud arbitraria. No afirma que un unico proceso de Malbolge Clasico
contenga memoria ilimitada ni que exista un `.mal` monolitico con todo el libro.

Ver evidencia completa: `evidence/multiprogram/SHA256SUMS.txt`.

---

### Roundtrip de Dos Partes

`--two-part` divide UTF-8 valido en un byte-safe boundary y aplica el
roundtrip MALRT1 existente a cada mitad. `independent` (el default) sintetiza y
verifica ambos programas; `verify-first` persiste y re-lee prueba solo para la parte uno,
asi que retorna deliberadamente `PART_1_ROUNDTRIP_ONLY` en vez de un claim de
archivo completo. `--max-part-bytes` defaults a 4096 y rechaza partes mas grandes antes de
escribir artifacts.

Este es un convenio de transporte bounded, no continuacion cross-VM ni
evidencia de que el Don Quijote completo pueda generarse o ejecutarse.

---

## Ejemplos de API

```python
from malbolge_translator import MalbolgeTranslator, encode_roundtrip, decode_roundtrip

# Codec solo (sin Malbolge)
payload = encode_roundtrip("你好，世界 😭🔥")
assert decode_roundtrip(payload) == "你好，世界 😭🔥"

# Transport completo sobre Malbolge
translator = MalbolgeTranslator()
result = translator.translate_roundtrip("你好，世界 😭🔥")
verification = translator.verify_roundtrip(result)
assert verification.roundtrip_pass
```

### API completa

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

---

## CLI

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

---

## Arquitectura

### Componentes Centrales

| Modulo | Proposito |
|--------|---------|
| `translator.py` | Pipeline principal: lexicon → split → sintetizar → chain + `translate_roundtrip` / `verify_roundtrip` |
| `roundtrip.py` | Codec UTF-8 reversible: `MALRT1:<base64>:<sha256>` (sin logica Malbolge) |
| `multiprogram_roundtrip.py` | Diccionario MALRT1 (66 programas puros) y composicion multiprograma |
| `two_part_roundtrip.py` | Flujo de trabajo bounded de dos programas MALRT1 y verificacion persistida |
| `fresh_vm_continuation.py` | Serializacion de estado Malbolge y continuacion en VM fresca |
| `anchor.py` | AnchorManager, WordBank — estados canonicos y cache de continuaciones |
| `lexicon.py` | Mapeos extensibles por usuario (transliteracion/encoding) |
| `cli.py` | Interfaz de linea de comandos (`--roundtrip`, `--show-program`) |

---

## Lexico / Encoding

La herramienta incluye un lexico con 300+ mapeos (transliteracion, lossy):

- Espanol: `áéíóúñ` → `aeiouny`
- Frances: `àâäçèêë` → `aaceee`
- Aleman: `ßäöü` → `ssaeoeue`
- Griego/Cirillico/Chino/Japones/Coreano
- Simbolos, matematicas, flechas, box drawing, emoji

**Modo A (transliteracion)**: aproximacion lossy. `TRANSLITERATION_REVERSIBLE = FALSE`. Los bytes originales no se preservan.

**Modo B (roundtrip)** proporciona preservacion exacta via codec reversible (`roundtrip.py`). No se usa transliteracion ahi; los bytes UTF-8 originales sobreviven exactamente.

```bash
malbolge-translate "text" --lexicon-add 世 shi --lexicon-add 界 jie
```

---

## Garantia de Output Exacto

Cada ejecucion `--execute` realiza:

```
sintetizar → interprete canonico → comparacion exacta → MATCH / MISMATCH
```

El interprete canonico es el interprete estandar de Malbolge (memoria 3^10, crazy-op, auto-encriptacion). Sin extensiones custom.

- **Modo transliteracion**: `MISMATCH` vs original es esperado (aproximacion); `MATCH` vs transliterado se verifica.
- **Modo roundtrip**: `verification.bytes_equal` + `sha_equal` + `payload_match` + `HALTED` deben ser todos `TRUE` para `ROUNDTRIP: PASS`. Ver `evidence/roundtrip/` y `docs/ROUNDTRIP_FORMAT.md`.

Artifacts: `*_manifest.json` incluye `mode`, `codec_version`, `original_sha256`, `payload_sha256`, `malbolge_execution_status`, `payload_match`, `bytes_match` (schema v2 para roundtrip, v1 para transliteracion — versionado, no sobreescrito).

```
MALBOLGE_NATIVE_UNICODE = FALSE
UTF8_REVERSIBLE_TRANSPORT_OVER_MALBOLGE = DEMONSTRATED solo cuando los tests end-to-end pasan
```

---

## Testing

```bash
# Suite completa (44 tests, ~77s con generator)
py -m pytest tests -q

# Solo roundtrip codec (sin generator, <1s)
py -m pytest tests/test_roundtrip.py -q

# Multiprograma (requiere malbolge-generator)
py -m pytest tests/test_multiprogram_roundtrip.py -q

# Continuacion en VM fresca
py -m pytest tests/test_fresh_vm_continuation.py -q

# Verificar evidencia
py -m evidence.multiprogram.generate_evidence
py -m evidence.multiprogram.run_full_quijote
```

---

## Requisitos

- Python 3.10+
- Paquete `malbolge-generator` (provee `ProgramGenerator`, `MalbolgeInterpreter`)

---

## Licencia

MIT — ver [LICENSE](LICENSE).
