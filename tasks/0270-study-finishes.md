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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
