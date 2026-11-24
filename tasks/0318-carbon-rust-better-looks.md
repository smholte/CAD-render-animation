# 0318 – Carbon fibre on curved parts without the 45° seam, perlage, a Rust slider, and better existing looks

**Who:** worker · **Status:** waits for 0274 · **Branch:** `task/0318-carbon-rust-better-looks`
**Started by:** lead, 24 Nov 2026 (owner 24 Nov 00:45: "for the carbon fibre could the worker find a fix for the weave
at 45° (a seam you can see). And improve other materials as seen fit.") · **Model:** Opus · effort High
**Area:** Looks lane – `blender/finishes.py` (0274's), `blender/materials.py`, `core/materials_lib.py`,
`props.py` (a group **Rust** value next to Wear, additive), the 3 Looks group box, the importer's `_face_axis`
(spheres, `CACHE_VERSION` 7), `blender/marine_looks.py` (one rust, not two), web 3D values, tests, guide, tour, PC check.
**Not:** welds (0319 – but see "Welds" below), the picker (0273), Adjust sliders (0314), painted steel from CAD colours
(0287).

## Goal

Carbon fibre looks right on any part, flat or curved; perlage reads as real engine-turned spots; bare steel and cast
iron can rust from flash to heavy with one slider; and the existing looks the owner has used since 0.2.x get the same
quality step as the new finishes.

## Background

- Study **0270** (branch `task/0270-study-finishes`; report + page): **#17 carbon twill 2×2** reads on flat faces, but
  on the curved cup the part's box projection switches at 45° and the weave breaks there – a seam you can see.
  **#27 perlage** reads more as scales than as overlapping brushed circles. **#23 rust** works as a slider like Wear
  (patches 10–40 mm, flakes ~3 mm, AO build-up in corners), cost +98 % / +78 % – the AO should be shared with Wear's.
  Open point: `_face_axis` knows no spheres (a domed cap gets its axis from the part's box).
- **0274** (merged first) brings the face data (`fr_fx_*`), the fade, and the 23 other finishes in `blender/finishes.py`.

## What to do

1. **Carbon fibre, no visible seam.** Try at least three ways and show them side by side on the study's cup, a
   revolved part (tube / cone), a double-curved free-form shell and a flat panel with a fold: (a) a blend that keeps
   the weave whole across the projection switch (narrow band, blend in the weave's own coordinates, not colours);
   (b) on round parts the face's own axis from 0274 (weave in θ·r and along the axis, a whole number of tows round –
   seamless like the knurl); (c) an automatic UV unwrap made once when carbon is chosen (Blender's unwrap, seams where a
   real layup would have a ply joint), redone after a model update. **A seam where a real part would have a ply joint is
   fine; one it would not have is not.** Pick the best per shape (or a combination), say why, keep the cost table.
   Also: 2×2 twill and plain weave, tow width, gloss / matte clear coat, and the alternating sheen kept.
2. **Perlage** that reads as overlapping brushed circles (each spot's swirl anisotropy, laid row after row so later
   spots cover earlier ones), spot size; offered with stainless and aluminium.
3. **Rust slider** per group next to Wear (0 = none … 1 = heavy), only where it is logical: bare carbon steel and cast
   iron rust; **painted** steel rusts only where Wear has taken the paint off (edges, scratches), with short run-down
   streaks below; galvanised steel only where the zinc is worn; stainless and aluminium never get red rust (no slider,
   or a tooltip saying why). Share the AO with Wear (the study's cost note). Make it the same rust as `marine_looks`'
   streaks (one look, not two). The 3D page: the colour holds.
4. **Spheres** in `_face_axis` (`GeomAbs_Sphere` → its axis; `CACHE_VERSION` 7) so domed caps get the right axis.
5. **Improve existing looks as you see fit.** Render the material sheet of every look (`tools/material_sheet.py`),
   compare each with what the real material looks like, and improve the weakest (start with the ones machine builders
   use most: painted steel / RAL paint, cast iron, stainless brushed / polished, aluminium anodised, rubber, plastics,
   glass / polycarbonate, chrome, hydraulic rod, galvanised, wire rope). Before / after pairs in the report; no look may
   get much slower without saying so. **Existing projects change look after the update** – list every changed look in
   What's new so the owner knows why an old render differs.
6. **Welds:** if 0319 is merged before you, its welds follow the group's Rust slider (bare steel welds and their heat
   zone rust first); if not, leave the Rust value readable for 0319 (one named node group) and say so in the report.
7. Guide (carbon, perlage, Rust), function entries (`since=` / `changed=`), the tour stop of 0274 extended, a Full
   PC-check line (`looks.rust`: the slider changes the node value; stainless shows no slider).

## Done when

- [ ] Carbon on cup / tube / free-form / folded panel without a seam a real part would not have (pictures)
- [ ] Perlage reads as overlapping brushed spots (picture)
- [ ] Rust slider: bare / painted / galvanised / stainless / aluminium behave as above (pictures, tests)
- [ ] Spheres give their axis (test with a domed cap); `CACHE_VERSION` 7
- [ ] Existing looks improved, before / after pairs, What's new lists them
- [ ] Tests added/updated; full suite passes; screenshots checked; version fields; owner's test steps; merged, release

## Not in this task

The 23 finishes of 0274 (only fix them if you find a fault – say so), welds (0319), the picker (0273), Adjust (0314),
painted steel from CAD colours (0287).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
