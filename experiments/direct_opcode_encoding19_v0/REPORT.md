# Direct Opcode Encoding 3^19 V0

## Formula auditada
r=(op-c-offset(c))mod94; if r<33: r+=94; char=chr(r)
decode19(ch,c)=(ord(ch)+c+offset(c)) mod 94

## Variables
op: opcode decodificado {4,5,23,39,40,62,68,81}; c: posicion de celda (0..3^19-1);
offset(c): OFFSETS[region] con OFFSETS=(0,117,140) replicas exactas de bolge19 offs[].

## Evidencia
- test_direct_encoder19.py: 6 tests OK (boundaries, 10k seeded sample, start_c, domains)
- Exhaustiva 0..99999 x 8 ops: 800000 roundtrips PASS
- case [23,5,81] -> 'ubO' -> decode [23,5,81] PASS
- Oracle bolge19 in_out_end19.mal + input Z: exit 0, stdout_hex=5a, HALT 2 pasos

## Excepciones
El cifrado XLAT corre despues de ejecutar (bolge19 main.zig:363-400), no afecta el opcode
ejecutado. La formula r<33->+94 no puede salir de 33..126 (r en 0..32 -> 94..126; resto
ya esta en 33..93). offset solo depende de region; sin excepcion por c.

## Primera divergencia Classic vs 19 (traza first_divergence.py)
step=3, c=101, d=3. OPCODE COINCIDE: 62 en ambos (Classic (55+101)%94=62; 19 (55+101+0)%94=62).
classic crazy(0,65)=29552 vs 19 mcrz(0,65)=581130761 -> primera divergencia es SEMANTICA
(crazy base-3 10 trits vs mcrz), no de encoding. CAUSE crazy_vs_mcrz. FIRST_DIVERGENCE_STEP 3.
