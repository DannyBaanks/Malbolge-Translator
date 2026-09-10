# Epoch RLE: guia de operacion

```powershell
py experiments\rle_decompressor_v0\run_epoch.py --classic-interpreter "C:\Development\ISyCo\workspace\assembly\malbolge\malbolge_interpreter.py" --samples 16,64,256,1024,4096 --seed 42 --output experiments\rle_decompressor_v0\evidence\epoch_20260909.json
```

## Regla de oro

No llames RLE a una fuente mas larga que su salida. Solo hay `RLE_PASS` si el
interprete Classic produce el objetivo exacto y `output_bytes > source_chars`.

## Resultado real

Comando ejecutado el 2026-09-09 con Python 3.12.4 y el interprete Classic de
`workspace/assembly/malbolge/malbolge_interpreter.py`:

```text
target  source  output  ratio     Classic
16      255     16      0.062745  HALTED exact
64      351     64      0.182336  HALTED exact
256     735     256     0.348299  HALTED exact
1024    2271    1024    0.450903  HALTED exact
4096    8415    4096    0.486750  HALTED exact
verdict: NOT_DEMONSTRATED
```

El recibo completo es `evidence/epoch_20260909.json` y su SHA-256 es
`75BD53565C6BCBCBD5C18E7D8CA8DF2F925916DFFF9858EC620D3835874E1D64`.

La auditoria de ciclo se ejecuto con la misma escalera y encontro
`output_epoch_cycle=false` en los cinco programas. El estado epochal incluye
`a`, `c`, `d` (u16 en Classic) y SHA-256 de las 59,049 celdas justo despues de
cada `OUT`. Recibo: `evidence/epoch_20260909_cycle_audit.json`, SHA-256
`D36B3EE96596B069F73527C0E139A7CB1266650A3CE6791DC08F826AC4FF586E`.

## Como leerlo

| Veredicto | Significado | Que hacer |
|---|---|---|
| `RLE_PASS` | Un programa Classic exacto produjo mas bytes que caracteres de fuente. | Auditar ciclo, contador y terminacion antes de ampliar corpus. |
| `NOT_DEMONSTRATED` | La fuente no expandio, fallo Classic o no emitio el objetivo. | No aumentar el payload; buscar un ciclo con contador `u16`. |

## Trampas

- El toolkit propone fuentes, pero no es la autoridad: el campo
  `classic_exact` debe ser `true`.
- Repetir `A` es solo un control de expansion. Incluso un `RLE_PASS` no prueba
  una descompresion general ni el Quijote.
- Cambiar la semilla cambia la busqueda. Conserva el JSON y su hash por corrida.
- No sobrescribas una evidencia anterior: usa una fecha o identificador nuevo
  para cada corrida.

## Siguiente epoch

El baseline es lineal: `A*4096` necesita 8,415 caracteres de fuente y no tiene
ciclo epochal. La siguiente busqueda debe encontrar una fase que repita output
usando un estado `u16` de contador y que termine de forma controlada. Sin ese
ciclo, no hay RLE.

## Auditor Zig nativo

Para clasificar una fuente sin usar Python como oraculo de ejecucion:

```powershell
zig build
& ".\zig-out\bin\malbolge-epoch.exe" "..\malbolge_output_AA\AA_full.mal"
```

Salida real:

```text
status=halted
steps=121
output_bytes=2
repeated_epoch=false
```

El auditor Zig calcula el estado despues de cada `OUT`: `a`, `c` y `d` (u16),
mas SHA-256 de la cinta de 59,049 celdas. Un `repeated_epoch=true` sin input
seria un ciclo determinista real; los candidatos `A`, `AA`, `AB` y `ABC` dieron
`false`.

## Reductor Zig nativo

```powershell
& ".\zig-out\bin\malbolge-reduce.exe" "..\malbolge_output_AA\AA_full.mal" AA
```

Salida real:

```text
seed_chars=219
reduced_chars=218
removed_chars=1
evaluations=794
output_over_source=0.009174
```

El reductor prueba cada borrado ejecutando una cinta Classic nueva en Zig. La
semilla `AA` solo contenia una celda redundante; no es una ruta hacia RLE.

## Barrido de mutacion Zig

```powershell
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 64 10000
```

Salida real:

```text
NOT_FOUND evaluations=20367
```

El barrido cambia una celda imprimible por vez, ejecuta cada candidato con el
motor Classic Zig y exige al menos 64 bytes `A` antes de pedir al auditor epoch
una repeticion de estado. Este negativo no descarta mutaciones de dos o mas
celdas; descarta solamente el vecindario Hamming-1 de la semilla `AA`.

## Barrido de dos celdas Zig

```powershell
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 64 10000 x --pair 216 217
```

Salida real:

```text
NOT_FOUND evaluations=8649
```

Este ataque cubre todas las parejas imprimibles `94 x 94` en las dos celdas
que cambiaron entre los epochs de `AA`. No encontró un loop de al menos 64
`A` ni un epoch repetido. El argumento `x` es un placeholder porque el modo
par no escribe candidato salvo que encuentre uno.

## Barrido control-flow acotado

El barrido global de toda la fuente (`~191,000` pares) se cancelo por coste: la
reinicializacion de la cinta Classic por candidato supera el limite operativo.
No se cuenta como evidencia positiva ni negativa.

El rango completado, restringido a la ventana final de `AA`, fue:

```powershell
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 64 1000 x --controls-range 200 218
```

Salida real:

```text
NOT_FOUND evaluations=1224
```

Son `18 x 17 x 4` combinaciones: dos posiciones distintas, cada una fijada a
`CHASE` o `MOVD`. No apareció una salida `A` sostenida ni un epoch repetido.

## Barrido CHASE/MOVD por ventanas (semilla `AA`)

Cada ventana se completo con el motor Classic Zig, minimo 16 bytes `A` y
limite de 500 pasos por candidato. Un candidato solo pasa al auditor epoch si
emite al menos 16 `A` puras sin detenerse.

```powershell
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 16 500 x --controls-range 0 64
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 16 500 x --controls-range 64 128
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 16 500 x --controls-range 128 200
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 16 500 x --controls-cross 0 200 200 218
```

Salida real:

```text
NOT_FOUND evaluations=16128   # ventana 0..63
NOT_FOUND evaluations=16128   # ventana 64..127
NOT_FOUND evaluations=20448   # ventana 128..199
NOT_FOUND evaluations=14400   # cruzado 0..199 x 200..217
```

Ningun par `CHASE`/`MOVD` en esas ventanas produjo una racha `A` sostenida con
epoch repetido. Quedan sin barrer los pares cruzados entre ventanas tempranas
`0..63 x 64..199`; ese es el siguiente ataque antes de subir a triples.

## Pares cruzados entre ventanas tempranas (completado)

```powershell
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 16 500 x --controls-cross 0 64 64 128
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 16 500 x --controls-cross 0 64 128 200
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 16 500 x --controls-cross 64 128 128 200
```

Salida real:

```text
NOT_FOUND evaluations=16384   # 0..63 x 64..128
NOT_FOUND evaluations=18432   # 0..63 x 128..200
NOT_FOUND evaluations=18432   # 64..128 x 128..200
```

Con esto queda cubierto todo par `CHASE`/`MOVD` con ambas posiciones en
`0..217`: ventanas internas, ventana final `200..217` y todos los cruces. El
siguiente escalon es triples `CHASE`/`MOVD` sobre la fase `200..217`
(`18 x 17 x 16 x 8 = 39,168` combinaciones) o cambiar de semilla.

## Triples CHASE/MOVD sobre la fase 200..217 (completado)

```powershell
& ".\zig-out\bin\malbolge-mutate.exe" "..\malbolge_output_AA\AA_full.mal" A 16 500 x --controls-triple 200 218
```

Salida real:

```text
NOT_FOUND evaluations=39168
```

Son todos los triples ordenados de posiciones distintas en `200..217`, cada
uno fijado a `CHASE` o `MOVD` (`18 x 17 x 16 x 8`). Ninguno produjo racha `A`
sostenida con epoch repetido. Con esto, la semilla `AA` queda agotada hasta
orden 3 en su fase final; el siguiente ataque es cambiar de semilla
(`AB`, `AAB`, `ABA`) o subir el minimo de salida para buscar loops largos.

## Pipeline gato-Zig: sintesis verificada (2026-09-10)

El `meowbolge` Python se porto fielmente a `zig/src/generator.zig`, con dos
correcciones decisivas encontradas por medicion:

1. **Regla de toque exacta.** La traza `pca` sobre una solucion funcional mostro
   0 `MOVD` y `d` monotono dentro del programa: la solucion real nunca lee la
   cola. El proponente DFS exige `d <= pos` al colocar y base con toques
   `< desde`; bajo esa regla el espejo coincide con la ejecucion real y las
   rutas propuestas verifican (antes: 0/225 en continuaciones).
2. **`fuente = hallado`, no append.** El port hacia `appendSlice` y duplicaba la
   base en cada byte (el Python original reasigna). Por eso el byte 1 funcionaba
   y el 2 salia corrupto.

Resultados reales, 100% Zig (`engine.zig` decide, `ReleaseFast`):

```text
AB:   chars=313 steps=313 out=AB    PASS
ABC:  chars=472 steps=472 out=ABC   PASS
Hola: chars=544 steps=544 out=Hola  PASS
```

Comandos:

```powershell
zig test -O ReleaseFast src\generator.zig   # suite + e2e AB
zig build test                              # suite Debug (e2e exige ReleaseFast)
```

Hallazgo negativo documentado: los programas Malbolge no son composicionales
en general — el prefijo `A` hallado lee mas alla de si mismo (probado por
traza), asi que congelarlo y extenderlo no produce `AB`. La sintesis global
por byte con bases estables es el camino que funciona.

## Hello, World! sintetizado 100% en Zig (2026-09-10)

```powershell
& ".\zig-out\bin\malbolge-gen.exe" generate "Hello, World!" 14 "..\experiments\rle_decompressor_v0\evidence\hello_world_zig.mal"
```

Salida real (determinista, repetible byte por byte):

```text
byte[1/13] H celdas=161
byte[2/13] e celdas=319
byte[3/13] l celdas=450
byte[4/13] l celdas=451
byte[5/13] o celdas=611
byte[6/13] , celdas=767
byte[7/13] ' ' celdas=888
byte[8/13] W celdas=1038
byte[9/13] o celdas=1192
byte[10/13] r celdas=1242
byte[11/13] l celdas=1403
byte[12/13] d celdas=1557
byte[13/13] ! celdas=1565
texto=Hello, World!
celdas=1566
ejecucion=Hello, World! (halted)
```

Notese el byte 4 (`l` repetida): +1 celda por la via directa (`a` ya valia).
Auditoria `malbolge-epoch` sobre el artefacto: `halted`, 1566 pasos
(marcha recta, sin loops), 13 bytes, `repeated_epoch=false`, delta minima de
1 celda entre OUTs.

Evidencia: `evidence/hello_world_zig.mal`, SHA-256
`18637B0D672419D1D5BC36D8E5490992A6CB21B566DF4E53EC5590862747C629`.

## Ley de escala y veredicto para el Quijote monolitico

Costo medido: ~120 celdas por byte (`1566/13`). Proyeccion al Quijote
(2,205,980 bytes): ~265M celdas frente al techo duro de 59,049. Factor ~4500x
por encima. **La sintesis por byte jamas alcanza para un Quijote en 1 `.mal`.**

El unico camino estructural que queda es un loop RLE real (celdas O(1) que
emiten N bytes), que ningun barrido ha encontrado todavia. La sintesis por
byte queda como herramienta para programas cortos y semillas de mutacion, no
como ruta al Quijote.

## Ultimo camino: loop RLE hallado por busqueda aleatoria (2026-09-10)

`malbolge-loop` (nuevo binario Zig) genera programas frescos al azar con
semilla fija y caza repetidores: racha larga de un byte + epoch repetido.

```powershell
& ".\zig-out\bin\malbolge-loop.exe" 42 500000 120 3000 16 "..\experiments\rle_decompressor_v0\evidence\loop_found.mal"
```

Salida real:

```text
best run=479 byte=0x51 n=16999
best run=494 byte=0x0b n=65091
FOUND run=144 byte=0x1d n=163328 steps=1684 status=max_steps
```

El programa 163,329 (120 celdas) cicla emitiendo el byte `0x1d` y el auditor
confirma `repeated_epoch=true`. Mecanismo diseccionado: un OUT en celda 13,
un CHASE en 74 que salta atras, MOVDs en 14/49 que arrojan `d` a la cola, sin
HALT. El ciclo preserva `a=29` como punto fijo (`c=50` en la repeticion).

Evidencia: `evidence/loop_found.mal`, SHA-256
`D89568330087D04824AF6155BC488555B715369B0D03516676CB1F4D0A2FB7F0`.

Direccion del byte (mutaciones de una celda sobre el loop, minimo 64
repeticiones + epoch, 11,160 evaluaciones cada una):

```text
A (0x41): NOT_FOUND
' ' (0x20): NOT_FOUND
e (0x65): NOT_FOUND
```

Veredicto del ultimo camino: mecanismo RLE CONFIRMADO (repetidor infinito
real en Classic Malbolge), direccion del byte NOT_DEMONSTRATED. Sin emision
controlable de bytes arbitrarios no hay descompresor y no hay Quijote en
1 `.mal`. La caceria queda cerrada con numero: 500k programas aleatorios + 33k
mutantes dirigidos.
