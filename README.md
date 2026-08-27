# malbolge·translate / Webolge

Google Translate, pero de **Malbolge**: texto humano ⇄ programa ejecutable.
Todo corre localmente en el navegador; no hay servidor de ejecución.

Sitio: `https://malbolge-translate.pages.dev/`

## Qué hace v0.3

- **Texto → Malbolge (modo rápido):** genera **un programa Malbolge real** para entradas cortas, lo vuelve a ejecutar con el núcleo JS y solo lo muestra si la salida coincide exactamente.
- **Malbolge → texto:** ejecuta el programa con límites de pasos/salida y muestra su output.
- **Automático:** intenta reconocer si la entrada ya es un programa; si no, genera Malbolge.
- **Webolge anti-freeze:** generación en `Worker`, checkpoints en IndexedDB, pausa/reanudación, auto-bisección de chunks y descarga de manifiesto.
- **Lotes:** cada chunk es un programa Malbolge **independiente y verificado**. No se venden como un único stream concatenable.

Prueba mínima:

```text
entrada: hola
modo: texto → Malbolge
Convertir
```

La salida es un programa printable de Malbolge. Antes de mostrar `VERIFICADO`, Webolge exige:

```text
generar → ejecutar → output === "hola" → HALTED
```

## Piezas

| pieza | qué es |
|---|---|
| `src/malbolge-core.mjs` | intérprete canónico JS (`op=(v+c)%94`, crazy-op, cifrado post-ejecución) |
| `src/toolkit-gen.mjs` | generador snapshot/BFS rápido, portado/adaptado a JS |
| `src/meowbolge-gen.mjs` | generador toroidal previo, conservado como fallback |
| `src/gen-worker.mjs` | generación fuera del hilo de UI |
| `app.js` | conversión, verificación, lotes y checkpoints |
| `verify/vectors.mjs` | suite portable de vectores y generación real |
| `verify/test_freezes.mjs` | regresión: `hola` debe generarse, no basta con timeout seguro |

## Verificación

Desde el root del repo:

```powershell
node verify\vectors.mjs
node verify\test_freezes.mjs
```

La suite no depende de rutas privadas de `C:\Development`.

## Alcance honesto

El programa rápido está demostrado para entradas ASCII/Latin-1 comunes y verifica cada resultado antes de mostrarlo. El espacio de búsqueda de Malbolge sigue siendo hostil: algunos bytes pueden agotar el presupuesto y se reportan como fallo, no como traducción inventada.

El modo por lotes sirve para textos largos sin congelar la UI, pero sus chunks son **programas independientes**. Esta versión no afirma producir un único `.mal` continuo arbitrariamente largo.

Caracteres con code point >255 (por ejemplo emoji) todavía no están soportados por el generador actual.

## Página / deploy

Cloudflare Pages, estática, sin build:

```powershell
npx wrangler pages deploy . --project-name malbolge-translate
```

## Licencias / procedencia

`src/toolkit-gen.mjs` es un port/adaptación en JavaScript de la estrategia `ProgramGenerator` de `wallstop/malbolge-toolkit` (MIT). El aviso de licencia original se conserva en `THIRD_PARTY_NOTICES.md`.
