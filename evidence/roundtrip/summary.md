# Roundtrip Evidence (2026-09-02)

| case | utf8 bytes | payload chars | malbolge chars | steps | byte_equal | sha_equal | end_to_end |
|---|---|---|---|---|---|---|---|
| ascii | 13 | 92 | 2260 | 2162 | True | True | PASS |
| spanish | 29 | 112 | 2360 | 2262 | True | True | PASS |
| chinese | 15 | 92 | 2418 | 2320 | True | True | PASS |
| japanese | 21 | 100 | 2589 | 2491 | True | True | PASS |
| cyrillic | 19 | 100 | 2384 | 2286 | True | True | PASS |
| emoji | 12 | 88 | 2390 | 2292 | True | True | PASS |
| mixed | 56 | 148 | 3715 | 3617 | True | True | PASS |
| multiline | 28 | 112 | 2739 | 2641 | True | True | PASS |