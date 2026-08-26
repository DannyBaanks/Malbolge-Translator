# malbolge·translate

Google Translate, pero de **Malbolge**: texto humano ⇄ programa ejecutable.
Sin servidores para ejecutar — todo corre local en tu navegador.

## Qué hay adentro

| pieza | qué es |
|---|---|
| `src/malbolge-core.mjs` | intérprete canónico portado a JS (`op=(v+c)%94`, XLAT, cifrado post-ejecución, EOF→`a=-1`) |
| `src/meowbolge-gen.mjs` | generador congruencial con traza guiada toroidal (Tier A/B + bruta acotada) |
| `verify/vectors.mjs` | consenso contra vectores dorados triple-backend |
| `manifest.json` + `popup.*` | extensión Chrome MV3 |
| `index.html` + `app.js` | página completa (misma fuente de módulos) |

## El consenso (por qué confiar en este intérprete)

La implementación JS se enfrenta a programas que HOY ya pasaron por tres
backends independientes (intérprete canónico Python, malbolge-oracle,
Malbolge-Engine C):

| vector | esperado | JS |
|---|---|---|
| hello world | HALTED/48 "Hello, world." | ✅ |
| gatito ASCII (750 celdas) | HALTED/652 arte exacto | ✅ |
| ECHO13 (anchuring v1) | HALTED/27 eco exacto | ✅ |
| TRANSFORM13(2) (anchuring v2) | HALTED/53 Y=`42777A75...32` | ✅ |

```powershell
node verify\vectors.mjs   # CONSENSO JS == 3 BACKENDS
```

## Extensión (modo desarrollo)

1. `chrome://extensions` → modo desarrollador
2. "Cargar descomprimida" → esta carpeta
3. Popup: pega texto → `→ Malbolge`, o pega programa → `▶ Ejecutar`

## Página (Cloudflare Pages)

Static, sin build:

```powershell
npx wrangler pages deploy . --project-name malbolge-translate
```

## Límite honesto

El generador cliente cubre un subconjunto de textos (falla rápido y honesto
en caracteres difíciles — mismo límite estructural que meowbolge en Python:
las rutas profundas leen cola de relleno inestable). La ejecución NO tiene
límites prácticos. Fase 2: worker de generación para textos largos.
