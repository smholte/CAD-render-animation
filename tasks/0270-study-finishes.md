# 0270 – Study + look sheet (findings only): new material finishes – knurled, spun, moulded textures, fabric, blasted, tread plate and more

**Who:** worker · **Status:** running · **Branch:** `task/0270-study-finishes` (branch only, never merged;
every push `[skip ci]`)
**Started by:** lead, 21 Nov 2026 (owner 17:27, with a photo of a headphone render: a diamond-knurled knob, a spun
aluminium cap with concentric rings, a cross-hatch moulded texture on a curved blue shell, soft matte plastic –
"materials like this take a lot of extra work and skill to set up") · **Model:** Opus · effort High
**Area:** Looks lane – prototype code in **new files only** on the branch (e.g. `blender/finishes_proto.py`,
`tools/finish_sheet.py`); reads `core/materials_lib.py`, `blender/materials.py` (`part_axes`, `_marks`) and
`blender/material_sheet.py`, changes none of them. Pictures and the page in `tasks/0270_page/`.

## Goal

The owner sees ~20 new finishes rendered on realistic shapes, side by side, and ticks the ones he wants in the app
(page with pick ticks + a Copy line, like 0168). The report says for each pick how it is built, what it costs and
which settings a user gets, so the build task (0274) is a straight job.

## Background

- All looks are procedural (`core/materials_lib.py`, built by `blender/materials.py`): STEP parts have **no UV maps**,
  long thin triangles and sharp edges. Machining marks (0046, 0098) already find their direction from the part's own
  axes (`part_axes`: longest side, round axis) so every copy of a part looks the same – reuse that idea.
- `blender/material_sheet.py` / `tools/material_sheet.py` already render every material on a block, a disc and a shaft
  (bpy as a module, Cycles and EEVEE) – start from it.
- Decals (0024) already put printed text and logos on parts: markings are **not** part of this study.
- Every look is clean by default; wear is a separate slider. A colour comes from the group (`needs_color`) where a
  finish is a paint or a coloured plastic.

## Candidates (render each; add others you find worth it, drop any that cannot look right – say why)

From the owner's photo:
1. **Diamond knurl** (knobs, thumb screws, handles) – pitch 0.6–1.6 mm, 30° / 45°, only on the round faces.
2. **Straight knurl.**
3. **Spun / concentric aluminium** (caps, discs, end faces): fine rings round the face's own centre and the radial
   highlight that moves round as the light moves; also the **faced end of a turned part** (a spiral).
4. **Moulded cross-hatch texture on a curved shell** (the blue cup): a fine raised grid that follows a double-curved
   surface without stretching or visible seams.
5. **Woven fabric / speaker cloth** and **fine plastic mesh grille**.
6. **Soft-touch matte plastic / rubber** (the headband): no pattern, the right soft sheen.

For machines (the owner's field):
7. **Bead- / sand-blasted** metal (steel, stainless, aluminium). 8. **Shot-blasted steel** before paint.
9. **Hammertone paint.** 10. **Wrinkle paint.** 11. **Anti-skid deck paint** (grit). 12. **Tread / checker plate**
(raised diamonds or bars – relief only or real raised look). 13. **Perforated sheet** (round / slotted holes; compare
with `wire_mesh`'s hole grid). 14. **Expanded metal.** 15. **Carbon fibre twill.** 16. **Moulded grain on plastic
housings** – leather grain and spark-eroded VDI 3400 levels (e.g. VDI 24 / 30 / 36). 17. **Hot-dip galvanised
spangle** (large crystals). 18. **Weld bead + heat tint** on stainless (only if it can sit on a seam the user points
at; else drop). 19. **As-cast surface** (sand-cast aluminium / iron). 20. **Light flash rust** / heavy rust (as a wear
layer, not a material?). 21. **Honed cross-hatch** in a bore. 22. **Scraped / frosted machine ways** (the
half-moon flaking on a mill's ways). 23. **Rubber with a moulded grip pattern.**

## What to find out per finish

- **How it finds its direction and size without UV maps** on a STEP part: part axes, the face's own centre, a
  triplanar box blend in the part's own space, … – and what happens on a part that is **copied, turned, scaled,
  mirrored**, and on a **model update** (must look the same).
- **Real size** of the pattern (mm) and how it looks at **4 distances** (close-up, product shot, whole machine,
  far): no moiré, no sparkle; far away it fades into the right average roughness / colour.
- **Cost**: render time against the plain material (Cycles, 64 samples, 1920 × 1080, on the 4-core web machine – say
  so), node count, EEVEE look; whether the **Web 3D bake** (`lightbake`, 0099) can hold it at its texel budget or should
  fall back to the average.
- **User settings** it needs (scale, strength, angle, direction picker…) – as few as possible; one sensible default.
- Which existing materials it should be offered with (e.g. knurl on steel, stainless, aluminium, brass).
- **Thumbnail cost for the material picker (0273):** one 256 px picture of a material on a fixed swatch shape – time
  in Cycles on the 4-core CPU (and EEVEE), and a proposal for that swatch shape (it must show marks, rings, knurl and
  textures: e.g. a rounded block with a knurled knob and a spun disc).

## Shapes (invented, generic – no brands, no logos)

A knob (Ø 20 × 15 mm), a disc cap (Ø 40 mm, slightly domed), a double-curved shell (Ø 70 mm cup), a block with
chamfers, a shaft, a 300 × 300 mm plate, and one **invented headphone-like assembly** built from those shapes (no maker,
no name) for a side-by-side "like the owner's photo" picture. Mesh them coarsely like STEP parts (`material_sheet.py`'s
way). Studio light of the app, one HDRI.

## Done when

- [ ] Every candidate rendered (Cycles) on the fitting shapes at close-up + product-shot distance, + one far shot of the
      plate set; the headphone-like picture with the best picks
- [ ] Page `tasks/0270_page/index.html`: one card per finish (pictures, real size, cost, settings), a pick tick per card,
      a Copy line at the top ("0270 picks: 1, 3, 4, …") – same way as 0168's page; published by the lead
- [ ] Report: a table (finish · how it is built · direction source · cost · bake · settings · verdict), the ones you
      dropped and why, the thumbnail measurement + swatch proposal, a proposed order for 0274
- [ ] Nothing merged; every push `[skip ci]`

## Not in this task

Changing `materials_lib.py` / `materials.py` (0274 builds the picks); the material picker and own materials (0273);
decals and printed text; image textures from files (keep everything procedural unless one finish truly cannot be –
then say so and what an image would cost).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 21 Nov 2026. Branch `task/0270-study-finishes`, every push
`[skip ci]`, nothing merged. (Setting the task to "running" on `main` was refused in this session, so `TASKS.md` on
`main` still says "open – can start": the lead sets it.)

**What changed (branch only):**
- `tools/finish_shapes.py` – the invented study shapes as ONE STEP (knob Ø20 × 15, domed cap Ø40, cup shell Ø70, block
  80 × 50 × 40 with chamfers, shaft with a shoulder, plate 300 × 300 × 5, half bushing, way, grip, weld T-joint, a
  headphone-like set). They come in through the app's own importer (`quality="normal"`): coarse CAD meshes, no UVs.
- `fresing_render/blender/finishes_proto.py` – 27 finishes as node builders + `prepare_faces` (the face data) +
  `set_pixel_angle` (the far-away fade). Reads `materials.py` (`_Nodes`, `part_axes`), changes nothing in it.
- `tools/finish_sheet.py` – stages and renders every finish (close-up, product shot, cost, far set, headset, copies,
  thumbnails); `tools/finish_page.py` – the pick page `tasks/0270_page/index.html` (+ `img/`, JPG).

**How the patterns find direction and size without UV maps (the core finding):**
1. **The CAD face's own axis** – the importer already stores every round face's axis (`fr_axes` + `fr_axis_faces`, cache
   3; used today only for joint picking). `prepare_faces` turns it into four FACE attributes on the mesh: `fr_fx_o`
   (point on the axis), `fr_fx_d` (direction), `fr_fx_r` (the face's OWN radius = median distance of its points – the
   stored radius is the largest on that axis line), `fr_fx_k` (1 round outside, −1 bore, 2 end face on an axis, 0
   other). End faces find their axis by "mean normal ∥ an axis of the part and the face centred on it"; faces with no
   axis of their own fall back to the part's round axis. Knurl, straight knurl, spun, faced spiral, honed bore and the
   rubber grip use it. A whole number of teeth round each face (`round(2πr·cosβ / p)`) → no seam. Cost to write the
   data: numpy over the mesh, a few ms per part. A shader reads them with an Attribute node (GEOMETRY), Cycles + EEVEE.
2. **The part's own box axes** – triplanar in object space (`_tri`): exactly one projection on flat faces, a blend of
   three on curved ones (tread plate, perforated, expanded, carbon, scraped ways, perlage, weave, grille, cross-hatch).
3. **Nothing** – 3-D noise / Voronoi in object space (blasted, hammertone, wrinkle, anti-skid, VDI, leather, spangle,
   as-cast, rust).
4. **A seam the user points at** (weld) – the line kept as OBJECT properties `fr_weld_a/b` on each part it touches (a
   material reads them per copy) + a bead object.
- **Copies, turned, mirrored**: the pattern sits the same on every copy (picture on the page). **Scaled** ×1.5: the
  pattern grows with the part (object space); 0274 can divide by the object's scale if ever needed (Inventor parts are
  not scaled). **Model update**: the same STEP imported again gives the same face data, number for number (knob, cap,
  bushing: max difference < 1e-7). 0274 must write the face data where `ensure_axes` runs today (`materials.assign`)
  and again after a model update.
- **Far away** (`_lod`): one pixel on the part = distance from the camera × pixel angle (a value node per material, set
  from the camera; in 0274 a scene property kept up by the camera code, as the tool marks' "Pixel angle" input). A
  pattern whose period covers < ~2 px fades to its average roughness / colour / open area. Shown on the page: the
  plate set at 4 m and 15 m with the fade and with it switched off (the "off" pictures sparkle).

**The table** (cost = product shot, Cycles CPU, 64 samples, adaptive + denoise, 4-core web machine, pattern vs the same
material without the pattern; at 960 × 540 for all, At 1920 × 1080 (the brief's size; 130–240 s a picture, so 8 finishes only), the same percentages: knurl +5 % (146 vs
139 s), spun +8 %, cross-hatch +9 %, tread +11 %, perforated +13 %, carbon +13 %, spangle +38 %, hammertone +69 %
(236 vs 139 s). The plain product shot itself: 130–140 s. at 1920 × 1080 for 8):

| # | Finish | How it is built | Direction from | Cost (960 × 540) | Web 3D model | Settings | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Diamond knurl 0.8 mm 30° | two groove families, pyramids, tips flat; spun rings on the end faces | face axis + own radius | +6 % | average | Pitch, Angle | ★ build |
| 2 | Straight knurl 1.0 mm | one groove family | face axis | +14 % | average | Pitch | ★ build (same code) |
| 3 | Spun aluminium | 1-D noise of the distance from the face's axis, anisotropy across the rings | face axis | +3 % | average (no anisotropy) | Strength | ★ build |
| 4 | Faced spiral 0.25 mm | spiral groove ρ/f + θ/2π | face axis | +5 % | average | Feed | add-on to 3 |
| 5 | Moulded cross-hatch 0.9 mm | raised 45° grid, triplanar | part box axes | +9 % | 2048 px tile | Pitch, Angle | ★ build |
| 6 | Woven fabric 0.5 mm | plain weave, sheen | part box axes | +8 % | average colour | Thread size | ★ build |
| 7 | Plastic mesh grille Ø1.1/1.6 | hex holes (alpha) | part box axes | +52 % | alpha holds | Hole, Pitch | ★ build |
| 8 | Soft-touch | numbers only + micro grain | none | −3 % | factors | none | ★ build |
| 9 | Bead-blasted | 3-D Voronoi dimples ~0.1 mm | none | +40 % | average | Coarseness | ★ build |
| 10 | Shot-blasted Sa 2½ | Voronoi ~0.3 mm + colour | none | +69 % | average | none | ★ build |
| 11 | Hammertone | Voronoi dents 5 mm + flakes, coat | none | +74 % | holds | Mark size | ★ build |
| 12 | Wrinkle paint | ridges of a warped noise | none | +4 % | 2048 px | Size | optional |
| 13 | Anti-skid deck paint | grit (Voronoi) ~1.2 mm | none | +14 % | holds | Grit | ★ build |
| 14 | Tread plate (lens) | lenses 22 × 6 mm on 25 mm, bump | part box axes | +11 % | holds (8 per tile) | Pitch | ★ build |
| 15 | Perforated Rv 5-8 / slotted | hex holes (alpha) | part box axes | +15 % | alpha holds* | Hole, Pitch, Round/Slot | ★ build |
| 16 | Expanded metal 43 × 13.5 | two staggered diamond grids, strand slope | part box axes | +37 % | roughly | Size | ★ build |
| 17 | Carbon twill 2×2, 2 mm | twill parity, tangent per tow, clear coat | part box axes (dominant) | +11 % | colour + normal | Tow | flat parts only |
| 18 | VDI 3400 24 / 30 / 36 | fine Voronoi + roughness per class | none | +32…41 % | average | Class | ★ build |
| 19 | Leather grain 1.6 mm | Voronoi edges, warped | none | +6 % | holds | Grain | ★ build |
| 20 | Galvanised spangle 9 mm | Voronoi crystals, own roughness/brightness/sheen | none | +28 % | colour + rough | Crystal size | ★ build |
| 21 | Weld bead + heat tint | line on the parts + bead object | picked seam | 0 % | own bake | Pick seam, Size | own task (L) |
| 22 | As-cast | Voronoi grain + waviness + blotches | none | +41 % | holds | Al / Fe | ★ build |
| 23 | Rust (flash / heavy) | noise + AO mask, flakes | none | +98 % / +78 % | colour only | Rust slider | ★ as a slider |
| 24 | Honed bore 50° | two helical scratch families inside bores | face axis (k = −1) | +17 % | average | Angle | add-on to turned |
| 25 | Scraped ways | half-moons, 12 mm checker | part box axes | +11 % | holds | Cell | ★ build |
| 26 | Rubber grip 3 mm | the knurl at 45°, flat tops | face axis | +7 % | average | Pitch | add-on to 1 |
| 27 | Perlage (extra) | overlapping spots, swirl tangent | part box axes | +9 % | sheen lost | Spot size | drop for now |

\* hex rows do not divide the 0.2 m web tile: a square pitch for the web model, or an own bake.

At 1920 × 1080 (the brief's size; 130–240 s a picture, so 8 finishes only), the same percentages: knurl +5 % (146 vs
139 s), spun +8 %, cross-hatch +9 %, tread +11 %, perforated +13 %, carbon +13 %, spangle +38 %, hammertone +69 %
(236 vs 139 s). The plain product shot itself: 130–140 s.

**Why some cost more:** every 3-D Voronoi (blasted, hammertone, VDI, as-cast) and the AO lookup (rust) is evaluated at
every sample even where the pattern has faded. 0274: switch the grain off below its size (a mix that skips the node
does not save time in Cycles – use cheaper noise for the sub-millimetre grains, keep Voronoi for hammertone / spangle),
and rust's AO only with wear's AO (shared). Node counts 11–115 (page). The EEVEE look matches; EEVEE times here are
software OpenGL on the web machine and say nothing about the owner's RTX 3090.

**Dropped / held back and why:** perlage (reads as scales, niche); weld bead + heat tint (it LOOKS right – see the
picture: rippled bead, straw → purple → blue tint – but it needs a seam picker, a bead that follows the line and
model-update care: a task of its own, not a finish); carbon on
curved parts (the box projection breaks the weave at 45°); wrinkle (only up close). Flash / heavy rust is not a
material but a slider like Wear.

**Thumbnails for 0273:** swatch = the chamfered block with the knurled knob on top and the spun cap leaning in front
(shows marks, rings, knurl, holes and grain at once). 256 × 256 px, Cycles CPU, 4-core web machine: 2.4–3.3 s at 16 samples, 3.5–5.4 s at 32 samples (+ denoise; plain 3.5 s,
knurl 3.9, perforated 4.0, hammertone 5.1, rust 5.4); EEVEE 1.9–3.0 s (software OpenGL here). 32 samples look clean. A
library of ~70 materials: ~5 min once on this machine, far less on the RTX 3090; make them once per app version and
ship / cache them (not per project).

**Proposed order for 0274** (one task, Opus · High for step 1, the rest along its pattern):
1. Face data (`prepare_faces` → `materials.assign` / model update) + the pixel angle (scene property, camera code) +
   knurl (diamond, straight, grip) + spun / faced + honed on the turned marks.
2. Box-axis patterns: tread plate, perforated (round / slotted), expanded metal, grille, scraped ways, cross-hatch,
   fabric.
3. Grain patterns (cheap noise below 0.3 mm): bead / shot blasted, VDI classes, leather, as-cast, anti-skid, hammertone,
   spangle, soft-touch.
4. Rust as a group slider next to Wear.
5. Later / own tasks: weld seams (picker + bead), carbon on curved parts, perlage.

**Tested and measured:** all on the 4-core Claude Code web machine, no graphics card, Blender 5.2.3 as a Python module,
Cycles on the CPU; invented shapes only. Debug passes at 480–640 px, final pictures 960 × 540 at 64 samples (≈ 30–60 s
each), the far set and the headset at 1920 × 1080. Re-import check: face data identical. No pytest added (prototype).

**Open points / follow-up tasks:**
- `_face_axis` in the importer knows no spheres: a domed cap or cup gets its axis from the part's box (works for
  revolved parts, not for a dome on a bigger part). 0274 (or the importer lane): add `GeomAbs_Sphere` (its axis) –
  needs `CACHE_VERSION` 7.
- `part_axes` calls a square plate "round" (box test): harmless for these finishes, worth a note in 0274.
- The grille on a thick part shows its back face through the holes; real holes would need walls (not possible as a
  material).
- Tread plate / expanded metal are bump only: plate edges stay flat in silhouette (real raised geometry would need
  displacement on a fine mesh – not worth it from 0.3 m on).
