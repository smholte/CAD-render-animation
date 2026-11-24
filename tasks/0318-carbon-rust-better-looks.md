# 0318 – Carbon fibre on curved parts without the 45° seam, perlage, a Rust slider, and better existing looks

**Who:** worker · **Status:** done (0.2.236) · **Branch:** `task/0318-carbon-rust-better-looks`
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

- [x] Carbon on cup / tube / free-form / folded panel without a seam a real part would not have (pictures)
- [x] Perlage reads as overlapping brushed spots (picture)
- [x] Rust slider: bare / painted / galvanised / stainless / aluminium behave as above (pictures, tests)
- [x] Spheres give their axis (test with a domed cap); `CACHE_VERSION` 7
- [x] Existing looks improved, before / after pairs, What's new lists them
- [x] Tests added/updated; full suite passes; screenshots checked; version fields; owner's test steps; merged, release

## Not in this task

The 23 finishes of 0274 (only fix them if you find a fault – say so), welds (0319), the picker (0273), Adjust (0314),
painted steel from CAD colours (0287).

## Design (worker, 24 Nov 2026)

- **Carbon: the weave per CAD face, continued across edges.** Every CAD face gets its own weave coordinates (metres):
  a plane in its own plane (from the part's origin, so coplanar faces continue), a round face (theta r, z) round its
  axis – a closed ring stretched to a whole multiple of 4 tows round it, so it meets itself –, a sphere draped from its
  pole ((s cos theta, s sin theta), s = R x angle from the pole). Then, largest face first, every face that shares an
  edge with a placed one is turned / mirrored and shifted (2-D Procrustes on the edge's points, handedness from the
  face normals) so its weave continues across the edge when it meets within 20 µm (a fold, a bend, a split face).
  Closed rings and spheres keep their own frame. Python: `core/finishes.weave_frames` (face attributes `fr_cw_a` =
  (cos, sin, mirror), `fr_cw_b` = (shift u, shift v, theta0; -1 = closed)); shader: `blender/finishes.weave_coords`.
- **Spheres** (`core/finishes._sphere`, k = ±3): a round face whose points (corners + triangle middles) lie on one
  sphere centred on its axis, much closer than on a cylinder round it. The importer gives spheres an axis (the CAD's
  pole when it points at the face's middle, else the middle's direction); `CACHE_VERSION` 7.
- **Rust:** `core/materials_lib.rust_kind` (BARE / PAINTED / ZINC / PLATED / none, a finish's Metal / Kind decide),
  `materials._weather` = Wear + Rust with one Ambient Occlusion node; `blender/rust.py` = the one rust colour ramp
  (marine streaks, welds, groups). The group material carries `fr_rust`; welds read it and get new materials
  (`welds.follow_rust` / `restyle`, no new bead).
- **Comparison tool** `tools/carbon_compare.py` (old projection, blend, UV unwrap, per-face; `--diag` black/white
  weave), close-ups `tools/look_shots.py`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 24 Nov 2026. Branch `task/0318-carbon-rust-better-looks`, version
0.2.236.

**What changed:**
- **Carbon fibre** (`carbon_fibre`, UID 85, finish n 17; Kind 2x2 twill / plain, Tow width 1–8 mm, Gloss): the weave per
  CAD face (see Design) – closed rings with a whole multiple of 4 tows round them, domes draped from their pole, flat faces
  in their own plane, faces continued across smooth bends and split faces; sharp edges (a sheet's cut edge, a corner, the
  cup's flat land) meet as a ply joint. Each tow's highlight along its fibres (alternating sheen), fibre streaks, a tone
  per tow, a twill float dips only at its ends, a smooth clear coat over it (its normal not linked).
- **Four ways tried** (`tools/carbon_compare.py`, pictures `tasks/img/0318_carbon_four_ways.jpg`, the weave drawn black /
  white, rows: old projection, (a) blend in the weave's coordinates, (c) Blender UV unwrap, (b) per face): the old one
  breaks at 45° on the cup and the hood; (a) swirls and squeezes (projections cannot unroll a closed surface); (c) is good
  on the folded panel but distorts the tube and needs a stored UV map redone after every model update; (b) per face is
  seamless on all four and needs nothing stored but face data. Chosen: (b) everywhere.
- **Perlage** (`perlage`, UID 86, n 27; stainless / aluminium / brass, Spot size 4 mm): circles on each face's weave
  coordinates, the four nearest in the order they were made (row by row, later on top), scratches as rings round each
  spot's own centre, its tangent round the spot (radial highlight per spot), its own shade, a faint rim.
- **Rust slider** (`FRMaterialGroup.rust`, under Wear): `core.materials_lib.rust_kind` – BARE (bare / ground / turned /
  raw steel, cast iron, black oxide, shot-blasted, a finish on STEEL / CAST_IRON, as-cast iron), PAINTED (all paints but
  the blade's), ZINC (galvanised, zinc plated / yellow / flake, spangle, wire ropes), PLATED (chrome, chrome rod),
  none (stainless, aluminium, brass, bronze, copper, nickel-plated brass, plastics, glass, carbon …: the row says why).
  `materials._weather`: Wear + Rust with ONE ambient occlusion node; painted / zinc rust at worn edges (a higher Rust
  wears a little more), short streaks below the part's top on upright faces (`_below_top`, box stored on the mesh:
  `fr_ax_lo` / `fr_ax_hi`), white rust on zinc. `blender/rust.py` = the one rust ramp, also used by the marine streaks
  and the welds (weld_looks LOOK_VERSION 3). Group material property `fr_rust`; welds follow it (`welds.follow_rust` /
  `restyle`: new materials, no new bead).
- **Spheres:** importer `_face_axis` (CACHE_VERSION 7), `core.finishes._sphere` (k = ±3), spun rings on domes evenly
  along the dome.
- **Existing looks improved** (`materials.LOOK_VERSION` 4, all projects' group materials rebuilt once; before / after
  `tasks/img/0318_looks_before_after.jpg`, the guide's `material_sheet.jpg`): glass, polycarbonate, tinted glass,
  frosted acrylic, PU tube – shadow rays pass through tinted (they rendered dark / cast black shadows); chrome and the
  chrome rod a darker, crisper mirror (reflectance of chrome; it looked like polished stainless); copper, brass, bronze –
  their measured linear reflectances had been written as sRGB (too dark, too orange), now between the measurement and a
  little more colour; yellow zinc – a thin passivation film (300 nm) on bright zinc: gold-green with a rainbow sheen;
  cast iron lighter and more metallic; marine streaks' rust colour. Listed in What's new.
- Test model `test_finishes.step`: two rows added (carbon cup, tube with a cone, U-panel, free-form hood, plate; perlage
  disc; rust: bare steel, cast iron, painted, galvanised, stainless, aluminium). Tour stop **finishes** extended
  ("Finishes, carbon fibre and rust", set changed 0.2.236); PC-check line **looks.rust** (Full; MIN_LINES_FULL 148);
  functions `looks.carbon`, `looks.rust` (new), `looks.finishes`, `looks.materials`, `looks.marine`, `looks.welds`
  (changed); guide sections Carbon fibre and Rust with `carbon.jpg`, `rust.jpg`, a new `panel_3_looks.png` and
  `material_sheet.jpg`; Ready-made material: Carbon fibre, Perlage. Tools: `tools/carbon_compare.py`,
  `tools/look_shots.py`.

**Tested and measured** (4-core Claude Code web machine, Cycles CPU):
- Render cost, 320 x 240, 32 samples, one sample part close up, single runs: carbon plate 4.3 s vs satin paint 3.5 s
  (+23 %), carbon cup +24 %, perlage disc 4.5 vs polished stainless 3.2 (+41 %), bare steel Rust 0.7: 5.4 vs 3.1 s
  (+74 %; the study measured +78–98 % with its own AO), painted Wear 0.5 + Rust 0.8: 6.9 vs 4.7 s (+47 %; the AO is
  shared with Wear). Rust costs nothing at 0 (no nodes). Node counts: carbon 142–166, perlage ~181–200.
- Tests: `tests/test_rust_carbon.py` (12, mine), `tests/test_rust_carbon_independent.py` (53, an **independent tester**
  subagent that did not write the code): it found **6 faults, all fixed** – chamfers and other cones read as spheres
  (changed 0274's knurls on chamfers; now a sphere must fit much better than any straight profile line and its facets'
  normals must meet at the centre), the folded panel's weave jumped 73 mm at the inner bends (it joined across the
  sheet's sharp cut edges; now only smooth edges join), a tube stored as two half faces got two seams (round faces on one
  axis and radius now count as one ring), Rust out of 0 … 1 rebuilt the material at every call, nickel-plated brass got
  red rust; its 6th point (bright steel wire rope should be BARE) I kept as ZINC – the library draws it as bright
  galvanised wires – and changed that test (noted in it). Locally 1,986 tests of the touched areas passed (finishes,
  materials, marine, welds, web 3D, toolmarks, cable looks, guide, functions …), the tour stop's Go + check (3.8 min),
  PC-check lines looks.rust + looks.finishes (OK, 11 s each), the 3 Looks panel picture (real Blender).
- GitHub: the first full run was red on two tests that pinned the import cache's version at 6 (test_facets,
  test_step_meta: now 7); meanwhile 0315 took 0.2.234 and 0276 took 0.2.235 (main merged twice, renumbered to 0.2.236); the second full run was green (as 0.2.235), the third as 0.2.236.

**Owner's test steps** (after Update now to 0.2.236; the first open of a STEP model reads it again once):
1. Help > **Make test tour project**, stop **Finishes, carbon fibre and rust**, **Go**, Rendered view: in front of the
   board the carbon cup, tube, folded U-panel, hood and plate – the weave runs round the curves and across the bends
   without a break –, a perlage disc, and the rust row (rusty bare steel, cast iron, a blue block rusting at its edges
   with streaks, galvanised with white spots, clean stainless and aluminium).
2. In **3 Looks**, click a group, set **Material** to **Carbon fibre** (in Other): **Kind**, **Tow width**, **Gloss**
   under it. Try it on a curved part of your own.
3. Pick a steel group: **Rust** under **Wear** – drag it and look in Rendered view. Pick a stainless group: the row says
   "No Rust: stainless steel does not rust".
4. Open an older project with glass or chrome: glass guards now look clear, chrome is a darker mirror.

**Open points / follow-up tasks:**
- Free-form faces (one B-spline face curving through more than ~60°) take their weave in the face's mean plane: it
  stretches towards their sides (no seam). A true drape would need a per-vertex parameterisation (a UV map) – not needed
  for the test shapes.
- Rust streaks start at the part's top, not at each worn spot (a shader cannot look upwards for exposed metal).
- The web 3D model keeps the rust colour of bare steel; rust at worn edges, corners and streaks, the carbon weave and the
  perlage are exported as their average colour (as for 0274's fine finishes).
- "Steel wire rope" counts as galvanised for Rust (its look is bright galvanised wire) but its label does not say so next
  to "Steel wire rope, galvanised": a rename (e.g. "Steel wire rope, bright galvanised") is a small follow-up (the
  independent tester's point).
- 0273 (material picker) can take the two new materials and the Rust setting into its pictures.

