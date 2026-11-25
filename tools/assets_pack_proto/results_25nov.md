# Results of run_proof.py – 25 Nov 2026, 4-core web machine (Intel Xeon 2.1 GHz, 16 GB, no graphics card), Blender 5.2.3 Linux

Made-up test pack 1.0.0: 5 items, 67.8 MB on disk (pictures at 1k + 2k + 4k; the 4k normal map alone 37 MB because the made-up pattern is noisy).

| Method | bring ms | save ms | project kB | open ms (pack) | client: missing libs / pictures / placeholders | client render magenta / mean | update ms | after update kB |
|---|---|---|---|---|---|---|---|---|
| append_ext | 41.1 | 18.8 | 99 | 11.9 | 0 / 5 / 0 | 0.0 / [0.478, 0.356, 0.386] | 49.8 | 12824 |
| append_packed | 40.8 | 37.0 | 12725 | 53.8 | 0 / 0 / 0 | 0.0 / [0.491, 0.465, 0.424] | 56.5 | 12824 |
| link | 46.2 | 9.9 | 88 | 40.9 | 5 / 0 / 5 | 0.0 / [0.0, 0.0, 0.0] | 27.9 | 88 |
| link_packed | 34.1 | 7.0 | 102 | 11.4 | 0 / 8 / 0 | 0.0 / [0.478, 0.356, 0.386] | 29.7 | 88 |

| Pictures | mode | render ms | Cycles memory MB (its stats line) | .tx kB | project kB |
|---|---|---|---|---|---|
| 1k | ext | 1858.3 | 30.0 | 0 | 88 |
| 1k | tx | 2127.0 | 25.0 | 5798 | 88 |
| 1k | packed | 1949.6 | 30.0 | 0 | 3238 |
| 2k | ext | 1939.4 | 66.0 | 0 | 88 |
| 2k | tx | 2294.4 | 43.0 | 22620 | 88 |
| 2k | packed | 1685.8 | 66.0 | 0 | 12578 |
| 4k | ext | 2267.9 | 210.0 | 0 | 88 |
| 4k | tx | 2353.7 | 43.0 | 89286 | 88 |
| 4k | packed | 2309.5 | 210.0 | 0 | 49871 |

## Extras (--extras)

Pack variant with the pictures packed inside each .blend: 26.2 MB of .blend files.

| Method (packed-pictures pack) | bring ms | project kB | client: missing libs / pictures / placeholders | update ms | updated project on a client |
|---|---|---|---|---|---|
| link_packed | 92.7 | 25219 | 0 / 0 / 0 | 82.5 (pack_libraries: Cannot pack absolute file) | 5 / 0 / 5, mean [0.0, 0.0, 0.0] |
| append | 101.5 | 12725 | 0 / 0 / 0 | 86.7 (objects ok) | 0 / 0 / 0, mean [0.497, 0.467, 0.426] |

4k pictures packed, then render.generate_texture_cache: 0 .tx files made, Cycles memory 210.0 MB (same as packed without it).

Blender's reuse_local_id on two appends of the same file: {'reuse_local_id=False': ['FRP paint_satin', 'FRP paint_satin.001'], 'reuse_local_id=True': ['FRP paint_satin']}
