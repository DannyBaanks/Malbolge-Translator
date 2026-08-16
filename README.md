# Malbolge Translator

**Generate pure Malbolge programs that print arbitrary text exactly.**

![Malbolge Translator Session](malbolge_session.gif)

This tool uses incremental machine-state synthesis with periodic anchor resets to make Malbolge text generation practical for arbitrarily long texts.

## How It Works

Malbolge is a self-modifying, counter-machine language where every instruction depends on the complete machine state. Traditional approaches try to generate the entire program at once, which is infeasible for long texts.

This translator decomposes the problem:

```
[Bootstrap: i + o*99] → Anchor State (clean memory, no output)
        ↓
[Word 1 continuation] → [Word 2 continuation] → ... → [Word N + halt]
        ↓                    ↓
   (machine state    (machine state
    advances)           advances)
        ↓
[Every N words: Bridge → Reset to Anchor → Continue]
```

- **Anchor**: A canonical machine state reached by a fixed bootstrap sequence. Identified by a hash of (A, C, D, tape[:100]).
- **Continuation**: Opcodes that, when executed *from a specific machine state*, produce the next word.
- **Word Bank**: Cache of (anchor_hash, word) → continuation. Only valid when machine state matches the anchor.
- **Linear Chaining**: Each word's continuation executes from the previous word's final state.

The result is **one linear opcode stream** with **one final halt** (`v`).

## Installation

```bash
# Requires Python 3.10+
pip install malbolge-generator
pip install -e .
```

Or from source:

```bash
git clone <this-repo>
cd Malbolge-Translator
pip install -e .
```

## Quick Start

```bash
# Translate and execute
malbolge-translate "Hola mundo" --execute

# Translate file
malbolge-translate input.txt --output-dir out --execute

# With custom lexicon mappings
malbolge-translate "Hola 世界" --lexicon-add 世 shi --lexicon-add 界 jie --execute

# Pre-populate word bank for speed
malbolge-translate --populate-bank "Your text here" --execute
```

## Generate Don Quijote (Demo Artifact)

```bash
# Downloads from Project Gutenberg, generates full .mal
malbolge-quijote --output-dir artifacts/quijote --execute
```

This creates:
- `artifacts/quijote/quijote_full.mal` — pure Malbolge program (~50 MB)
- `artifacts/quijote/quijote_full.op` — raw opcodes
- `artifacts/quijote/quijote_manifest.json` — metadata

## Architecture

### Core Components

| Module | Purpose |
|--------|---------|
| `translator.py` | Main translation pipeline: lexicon → split → synthesize → chain |
| `anchor.py` | AnchorManager, WordBank — canonical states & continuation cache |
| `lexicon.py` | User-extensible character mappings (transliteration/encoding) |
| `cli.py` | Command-line interface |
| `render_session.py` | Session GIF renderer (like FLOW's session.gif) |

### Public API

```python
from malbolge_translator import MalbolgeTranslator, Lexicon

# Basic usage
translator = MalbolgeTranslator(anchor_interval=50)
result = translator.translate("Hello world")
translator.execute(result)  # verifies exact output

# Custom lexicon
lex = Lexicon()
lex.add("ñ", "ny")
lex.add("中", "zhong")
translator = MalbolgeTranslator(lexicon=lex)

# Save/load caches
translator.save_cache()
```

## Lexicon / Encoding

The tool includes a built-in lexicon with 300+ mappings:

- Spanish: `áéíóúñ` → `aeiouny`
- French: `àâäçèêë` → `aaceee`
- German: `ßäöü` → `ssaeoeue`
- Greek/Cyrillic/Chinese/Japanese/Korean
- Symbols, math, arrows, box drawing, emoji

**Important**: The lexicon performs **transliteration**, not reversible encoding. Original bytes are not preserved. For exact byte preservation, implement a reversible encoding layer (not included).

Add custom mappings:
```bash
malbolge-translate "text" --lexicon-add 世 shi --lexicon-add 界 jie
```

## Exact Output Guarantee

Every `--execute` run performs:

```
synthesize → canonical interpreter → exact comparison → MATCH / MISMATCH
```

The canonical interpreter is the standard Malbolge interpreter (3^10 memory, crazy-op, self-encryption). No custom extensions.

## Requirements

- Python 3.10+
- `malbolge-generator` package (provides ProgramGenerator, MalbolgeInterpreter)

## Testing

```bash
# Run basic tests
malbolge-translate "Hola mundo" --execute
malbolge-translate "The quick brown fox" --execute
malbolge-translate "def foo(): return 42" --execute
```

## License

MIT