# Results of web3d_measure.py + web3d_views.py – 25 Nov 2026, 4-core web machine (Intel Xeon 2.1 GHz, 16 GB, no graphics card)

Blender 5.2.3 as a Python module with the app of this branch (0.2.257 + main of 25 Nov); pages shot in headless Chromium (software GL), all at page level Best, auto off, 960 x 540. Made-up pictures (drawn by the scripts).

## 1 · Background: a made-up photo-like 360° picture, 4096 x 2048 EXR (20.1 MB), as the test crane's background and light

| Export quality | background in the page | light in the page | whole page | export | look cost vs Best, level view: sky area / whole picture (0-255, PSNR) |
|---|---|---|---|---|---|
| BEST | JPEG 4096 x 2048, 905 KB | HDR 256 x 128, 131 KB | 2.65 MB | 8.5 s | – |
| BALANCED | JPEG 2048 x 1024, 236 KB | HDR 256 x 128, 131 KB | 1.75 MB | 3.2 s | 1.72 / 1.49 (37.7 / 39.8 dB) |
| PHONE | JPEG 1024 x 512, 75 KB | HDR 128 x 64, 33 KB | 1.41 MB | 2.0 s | 2.76 / 2.29 (33.3 / 35.7 dB) |

Same page shot twice (noise floor): 0.0. From the export's own first view (looking down at the ground): Balanced 1.25, Phone 1.87 mean.

## 2 · Pictures: the pack's concrete (2k colour, roughness, relief; one picture per 0.2 m) on the base plate, baked at the export's texture size

| Texture size (px per 0.2 m tile) | largest baked picture | .glb | whole page | export (all looks) | look cost vs 2048, 0.8 m from the plate: middle / whole (0-255, PSNR) | pack files inside |
|---|---|---|---|---|---|---|
| 2048 | webp 2048 x 2048, 2322 KB | 3.04 MB | 5.18 MB | 43.9 s | – | none |
| 1024 | jpeg 1024 x 1024, 491 KB | 0.81 MB | 2.20 MB | 9.7 s | 0.56 / 0.47 (49.8 / 50.7 dB) | none |
| 512 | jpeg 512 x 512, 114 KB | 0.34 MB | 1.63 MB | 2.9 s | 1.29 / 1.06 (43.6 / 44.6 dB) | none |

Noise floor (same page twice): 0.0. "Pack files inside": the first 4 KB of each original picture searched in the .glb.
