# ProgramGenerator19 V3 dataflow — resultado

## Hipótesis nula

H0: cuatro workers con beam 20,000 y profundidad 256 no sintetizan el target
completo `Hola mundo`.

## Baseline y control

- Control funcional: target `H`, validado después con `bolge19.exe`.
- Control de paralelismo: mismo target y artefacto con 1 y 4 workers.

## Claims

| Claim | Estado | Evidencia |
|---|---|---|
| Pipeline EXPAND/REDUCE/TARGET funciona | PASS | genera `H` |
| Oracle independiente produce `48` | PASS | 11 pasos |
| Determinismo 1 vs 4 workers | PASS | artefacto byte-idéntico |
| 4 workers aceleran el control pequeño | FAIL | 606 ms vs 383 ms |
| Sintetiza `Hola mundo` bajo presupuesto | FAIL | segundo byte sin ruta |
| El paralelismo resuelve la escalabilidad | NOT_DEMONSTRATED | beam/alfabeto limitan antes |

El cuello actual no es CPU solamente. La reducción heurística puede descartar
historias necesarias, o el alfabeto rectilíneo `o,p,*` puede requerir una ruta
mayor. Añadir workers no corrige ninguna de esas dos causas.

## Siguiente experimento

Comparar dos controles con igual presupuesto: (A) beam con muestreo diverso de
la cola de 98 celdas; (B) máquina completa que permita `j` (movd). La métrica
primaria será encontrar el segundo byte `o`, no velocidad bruta.
