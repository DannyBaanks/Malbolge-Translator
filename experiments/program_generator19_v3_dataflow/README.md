# ProgramGenerator19 V3 — dataflow workers

Pipeline experimental:

```text
SEED -> EXPAND(workers) -> REDUCE(exact state) -> SCORE/BEAM -> TARGET -> VERIFY
```

El estado transportado es `(a, mem[d:c])`; con el bootstrap actual la cola
tiene 98 celdas. Cada transición consume una celda y agrega el valor cifrado de
la instrucción recién emitida. Los workers solo ejecutan transformaciones
puras; el reducer central hace determinista la deduplicación.

H0: el pipeline no sintetiza `Hola mundo` dentro de `max_depth=256` por byte y
`beam=20000`.

Resultado: el control `H` pasa y el oracle produce `48`; `Hola mundo` no
encuentra el segundo byte (`o`) dentro del presupuesto. Véase `REPORT.md`.
