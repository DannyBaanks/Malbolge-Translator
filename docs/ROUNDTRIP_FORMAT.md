# ROUNDTRIP_FORMAT — MALRT1

**Goal:** reversible, byte-exact UTF-8 transport over pure Malbolge.

This document is sufficient for a JS implementation without importing Python internals.

## Invariant

```
original_utf8_bytes == recovered_utf8_bytes
sha256(original_utf8_bytes) == sha256(recovered_utf8_bytes)
```

Malbolge does NOT natively support Unicode. This is `UTF-8 bytes -> ASCII codec -> Malbolge -> ASCII -> UTF-8 bytes`.

```
MALBOLGE_NATIVE_UNICODE = FALSE
```

## Wire format

```
MALRT1:<base64(utf8_bytes)>:<sha256_hex>
```

- `MALRT1` — literal version marker, ASCII.
- `:` — literal colon (`U+003A`) delimiter, exactly two delimiters.
- `<base64(...)>` — standard RFC4648 base64, alphabet `A-Za-z0-9+/=` with `=` padding, `+` and `/` kept (not urlsafe), empty string allowed for empty input. Example: `SGVsbG8=` for `Hello`. No whitespace, no line breaks.
- `<sha256_hex>` — 64 lower hex chars `[0-9a-f]` of `SHA256(utf8_bytes)`. Example: `185f8db32271fe25f561a6fc938b2e264306ec304eda518007d1764826381969` for `Hello`.
- The payload is pure ASCII (bytes 33-126 plus `:` at delimiters). Suitable for Malbolge synthesis (printable ASCII).
- Deterministic, no random, no compression.
- Example empty input: `MALRT1::e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

### Encoding steps (Python reference)

```python
import base64, hashlib
def encode_roundtrip(text: str) -> str:
    b = text.encode('utf-8')
    b64 = base64.b64encode(b).decode('ascii')
    sha = hashlib.sha256(b).hexdigest()  # lower 64 hex
    return f"MALRT1:{b64}:{sha}"
```

```javascript
// JS reference
async function encodeRoundtrip(text) {
  const bytes = new TextEncoder().encode(text); // utf-8
  const b64 = btoa(String.fromCharCode(...bytes));
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  const sha = [...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('');
  return `MALRT1:${b64}:${sha}`;
}
```

### Decoding steps (must distinguish VALID / INVALID / CORRUPTED)

1. Check `payload` is `str`, non-empty.
2. Split on `:` → must be exactly 3 parts `[version, b64, sha]`. If not, `INVALID` (malformed envelope).
3. Version must be `MALRT1` (in `SUPPORTED_VERSIONS`). Else `INVALID` (unknown version).
4. `sha` must be 64 hex `[0-9a-f]` (case-insensitive, normalized lower). Else `INVALID`.
5. Decode `b64` via standard base64 with `validate=True` (reject non-alphabet). Empty allowed. Else `INVALID`.
6. Compute `sha_actual = SHA256(decoded_bytes)` (hex lower). If `sha_actual != sha_expected` (lower), `CORRUPTED` (do NOT invent output).
7. Decode `decoded_bytes` as UTF-8. If fails, `INVALID` (not valid UTF-8).
8. Else `VALID` with `text = decoded_bytes.decode('utf-8')`.

Python:

```python
from malbolge_translator.roundtrip import decode_roundtrip_detailed, RoundtripStatus
result = decode_roundtrip_detailed(payload)
# result.status in VALID / INVALID / CORRUPTED
# result.text, result.error, result.sha256_expected, result.sha256_actual
```

JS:

```javascript
function decodeRoundtrip(payload) {
  const parts = payload.split(':');
  if (parts.length !== 3) return {status: 'INVALID', error: 'malformed'};
  const [ver, b64, shaExp] = parts;
  if (ver !== 'MALRT1') return {status: 'INVALID', error: 'unknown version'};
  if (!/^[0-9a-f]{64}$/i.test(shaExp)) return {status: 'INVALID'};
  let bytes;
  try { bytes = Uint8Array.from(atob(b64), c=>c.charCodeAt(0)); } catch(e){ return {status:'INVALID'}; }
  // compute sha, compare, then TextDecoder
}
```

Policy:

- **No arbitrary code execution** from payload.
- **No fake fallback**: corrupted payload must NOT decode as if valid; `CORRUPTED` ≠ `VALID`.
- **No silent `?`**: roundtrip decoder never substitutes `?` for failed Unicode (unlike transliteration).

### Integrity

SHA-256 is included for evidence before narrative. A `MALRT1` payload without matching SHA is `CORRUPTED`, not `VALID`. Base64 alone would be reversible but integrity-less.

### Size

- Overhead: `7` (prefix+colons) + `~4/3 * len(utf8_bytes)` (base64, padded) + `64` (sha).
- Example: `"你好"` (6 utf8 bytes) → `MALRT1:5L2T5aW9:e...` (~7+8+64=79 chars).

### Compatibility

- Payload chars are `A-Za-z0-9+/=` plus `MALRT1:` and sha hex `0-9a-f`; all are printable ASCII `33-126`.
- Malbolge synthesis for this payload is plain printable text generation; no special Malbolge extensions.
- Porting to JS: use `btoa` (ASCII) + `crypto.subtle.digest('SHA-256', ...)` + `TextEncoder`/`TextDecoder`.

### Manifest fields for roundtrip artifacts

```json
{
  "schema_version": 2,
  "mode": "utf8-roundtrip",
  "codec_version": "MALRT1",
  "original_utf8_bytes": 18,
  "original_sha256": "abc...",
  "encoded_payload": "MALRT1:...:...",
  "encoded_payload_chars": 96,
  "payload_sha256": "def...",
  "malbolge_program_chars": 12450,
  "malbolge_opcodes": 8000,
  "recovered_sha256": "abc...",
  "payload_match": true,
  "bytes_match": true,
  "text_match": true,
  "execution_status": "HALTED",
  "execution_steps": 12345
}
```

Do not overwrite or silently change schema for old transliteration artifacts (v1).

### What this does NOT claim

- Not "Malbolge natively supports Unicode".
- Not "arbitrary-size roundtrip demonstrated" until evidence exists.
- Not Webolge support until actually ported (this doc is prep; Webolge remains Latin-1 limited).
