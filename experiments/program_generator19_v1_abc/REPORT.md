# ProgramGenerator19 V1 — resultado ABC

## Hipótesis nula

H0: el generador no produce dentro del presupuesto un único `.mal` 3^19 cuyo
stdout independiente sea exactamente `414243`.

## Baseline y control

V0 (`A`) necesitó 190 celdas y 5,192 evaluaciones. V1 conserva seed, búsqueda,
VM y oracle; solo cambia el target a tres bytes.

## Resultado

| Claim | Estado | Evidencia |
|---|---|---|
| Síntesis interna de `ABC` | PASS | 9,738 evaluaciones |
| Artefacto determinista | PASS | repetición byte-idéntica |
| Oracle produce `414243` | PASS | `oracle_raw.txt` |
| Oracle termina | PASS | 173 pasos, exit 0 |
| Frase con espacios | NOT_DEMONSTRATED | siguiente experimento |
| Capítulo completo | NOT_DEMONSTRATED | no ejecutado |
| Quijote monolítico | NOT_DEMONSTRATED | no ejecutado |

H0 queda falsada para `ABC`, seed 0. El programa creció de 190 a 272 celdas
(+43.2%) al pasar de 1 a 3 bytes; las evaluaciones crecieron de 5,192 a 9,738
(+87.6%). Esto no prueba escalabilidad asintótica.

## Siguiente experimento

Sintetizar `Hola mundo` para introducir minúsculas y espacio; medir longitud,
evaluaciones, tiempo y paridad con `bolge19.exe`.
