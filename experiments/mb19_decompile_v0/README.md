# MB19 Decompile V0 — plano estático 3^19 con la fórmula directa

Pregunta: ¿la fórmula `idx=(byte+c+offs[region])%94` decompila imágenes reales
de Malbolge Unshackled (lisp.mb de MalbolgeLISP)?

Herramienta: `decompile19.zig` (Zig 0.16, Win32 directo, patrón de bolge19).
Una pasada, 371M de celdas en ~1 s. El intento previo con numpy fue descartado
por costo (lección: streaming, no vectores de int64).

## Hallazgos (ver raw_*.txt)
- lisp.mb: 371,331,415 celdas; 371,331,414 decodifican a instrucción válida.
  La ÚNICA inválida es la celda 19391 (frontera init→core).
- init_module.mb: 19,391/19,392 válidas — la inválida es esa misma última.
- core.mb solo, con posiciones locales: 150,745,261 "movd" — idéntico al conteo
  de NOP del plano absoluto (150,761,408 − 16,147 del init). Consistencia
  interna exacta: core es una región de DATOS que en reposo todo son NOP.
- generated_A19.mal (artefacto V0): 190/190 válidas, hist compadece con el plan
  (bootstrap 99 nop + 35 opr + 23 rot + jmp/out/end 1 c/u).

## Texto crudo
El código Lisp NO está como ASCII plano dentro de la imagen: grep de "define"/
"lambda"/"(car" = 0 ocurrencias. Está cifrado en la zona de datos; solo se hace
texto al ejecutarse la secuencia de descifrado de MalbolgeLISP. Por tanto:
LISP_SOURCE_PLAINTEXT_VISIBLE = NOT_DEMONSTRATED (requiere correr la imagen).
