# ProgramGenerator19 V0 — resultado

## Hipótesis nula

H0: el buscador incremental Classic, conectado a una VM Unshackled 3^19, no
encuentra dentro del presupuesto un programa cuyo stdout sea `A`.

## Baseline y control

- Baseline: el artefacto Classic de 232 celdas imprime `41` (`A`) en 134 pasos.
- Control negativo: los mismos bytes en `bolge19.exe` imprimen `da`, no `41`.
  Esto descarta que el codec posicional por sí solo explique el resultado.

## Experimento

```powershell
py program_generator19.py A --seed 0 --output generated_A19.mal
```

El adaptador conserva el algoritmo de búsqueda de `malbolge-generator`, pero
sustituye ejecución, snapshots, `mcrz`, `mrot`, memoria y XLAT por semántica
3^19. El `.mal` final se valida con `bolge19.exe`, no con la VM usada durante
la búsqueda.

## Resultado

| Claim | Estado | Evidencia |
|---|---|---|
| El buscador produce internamente `A` | PASS | 5,192 evaluaciones |
| El artefacto es determinista con seed 0 | PASS | repetición byte-idéntica |
| Oracle independiente produce `41` | PASS | `oracle_raw.txt` |
| El artefacto termina | PASS | 91 pasos, exit 0 |
| Generación de texto arbitrario | NOT_DEMONSTRATED | solo se probó `A` |
| Capítulo completo | NOT_DEMONSTRATED | no ejecutado |
| Quijote monolítico | NOT_DEMONSTRATED | no ejecutado |

H0 queda falsada para el objetivo `A` y seed 0.

## Siguiente experimento

Ejecutar la misma búsqueda para `ABC`, medir evaluaciones por byte y comparar
el stdout completo con `414243`. Si pasa, probar una frase corta antes de
intentar un capítulo.
