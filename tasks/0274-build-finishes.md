# 0274 – Build the new finishes from study 0270: knurls, spun, moulded, fabric, plate patterns, blasted, paints, grains

**Who:** worker · **Status:** done (0.2.227) · **Branch:** `task/0274-build-finishes`
**Started by:** lead, 24 Nov 2026 (owner's picks from the 0270 page, 24 Nov 00:45: **all 27 ticked**) ·
**Model:** Opus · effort High
**Area:** Looks lane – `core/materials_lib.py` (new looks + their settings), `blender/materials.py` (the face data hook
in `assign` / `ensure_axes`, the pixel-angle input), a new `blender/finishes.py` (the node builders, ported from the
study), `importer` only if needed for the face data, the camera code for the pixel angle (one scene property kept up
to date – additive in `cameras.py`), `reimport.py` (additive: face data again after a model update), the 3 Looks
group box (the finish's own settings), web 3D bake values (additive in `core/web3d.py`), tests, guide, tour, PC check.
**Not:** carbon fibre on curved parts, perlage, the Rust slider, spheres in the importer, improving existing looks
(all **0318**); welds (**0319**); the picker window (0273); Adjust sliders (0314); painted steel from CAD colours (0287).

## Goal

The owner's 23 picked finishes are in the app as ready-made looks, look as good as the study's pictures on real CAD
parts with no UV maps and no set-up, follow every copy and model update, fade calmly far away, and cost no more render
time than the study measured (less where the study said how).

## Background

- Study **0270** (branch `task/0270-study-finishes`, report in `tasks/0270-study-finishes.md` there – read its report
  and the pick page `tasks/0270_page/index.html`): every finish is prototyped in `fresing_render/blender/finishes_proto.py`
  with `prepare_faces` (four FACE attributes from the CAD face's own axis: `fr_fx_o`, `fr_fx_d`, `fr_fx_r`, `fr_fx_k`)
  and `set_pixel_angle` (the far-away fade). Study shapes: `tools/finish_shapes.py`; sheet: `tools/finish_sheet.py`.
  Port them – do not merge the study branch.
- The owner ticked **all 27**. Split: this task builds the 23 below; 0318 does carbon fibre (with a fix for the seam at
  45° on curved parts – the owner asked for it), perlage, the Rust slider and improvements to existing looks; 0319 does
  welds (the owner wants them as a picked seam, Inventor-like).
- Owner's standard (23 Nov): **looks must be very good with no set-up**; every function must suit sales people, CAD
  engineers and skilled animators.

## What to build (the study's proposed order)

1. **Face data + fade**: `prepare_faces` where `ensure_axes` runs today (`materials.assign`) and again after a model
   update; the pixel angle as a scene property kept up by the camera code (as the tool marks' "Pixel angle"); a pattern
   finer than ~2 px fades to its average. Divide by the object's scale only if a scaled part shows up wrong (say so).
2. **Face-axis finishes**: diamond knurl (#1, pitch 0.5–1.6 mm, 30° / 45°), straight knurl (#2), rubber grip (#26, the
   knurl at 3 mm), spun aluminium (#3), faced spiral (#4, add-on to spun), honed bore (#24, add-on to the turned marks).
3. **Box-axis finishes**: moulded cross-hatch (#5), woven fabric / speaker cloth (#6), fine plastic grille (#7), tread
   plate (#14), perforated round / slotted (#15), expanded metal (#16), scraped ways (#25).
4. **Grain finishes** (cheap noise below ~0.3 mm, Voronoi only where the size shows – the study's cost note): soft-touch
   (#8), bead-blasted (#9), shot-blasted Sa 2½ (#10), hammertone (#11), wrinkle paint (#12), anti-skid deck paint
   (#13), VDI 3400 classes (#18), leather grain (#19), galvanised spangle (#20, a second look of Hot-dip galvanized),
   as-cast aluminium / iron (#22).
5. Each finish: an entry in `materials_lib` with label, category, the materials it is offered with (the study's
   "Offered with"), its few settings in the group box (Pitch, Angle, Size, Class …), sensible part-kind defaults where
   the study says so (e.g. knobs → knurl is NOT automatic; only offered), the web 3D model value the study measured
   (average / alpha / normal tile). Tooltips on every setting.
6. **Cost**: measure each finish on the study's product shot against plain (CPU, web machine – say so); where the study
   measured > +30 % (blasted, shot-blasted, hammertone, VDI, spangle, as-cast, grille, expanded) try the cheaper build
   and report before / after. Nothing may look worse to save time without saying so.
7. Guide (Looks: the new finishes, with close-up pictures from the sheet), function entries (`since=`), one tour stop
   with an invented part set showing them, a Full PC-check line (a knurled test knob gets its face data; the fade
   value changes with the camera distance).

## Done when

- [x] 23 finishes in the app, close-up + product pictures as good as the study's (sheet in the report)
- [x] Face data written on import and after a model update; copies / turned / mirrored parts identical (test)
- [x] Fade far away (4 m / 15 m sheet: no moiré, no sparkle)
- [x] Cost table before / after; the cheaper builds where they hold the look
- [x] Web 3D model: each finish exports as the study says (test)
- [x] Tests added/updated; full suite passes; screenshots checked with `tools/ui_screens.py`; version fields
- [x] Owner's test steps in the report; merged, version, release

## Not in this task

Carbon fibre, perlage, the Rust slider, spheres in the importer, existing looks (0318); welds (0319); the picker window
and thumbnails (0273 – but leave the study's swatch idea in your report for it); Adjust (0314); painted steel (0287).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 24 Nov 2026. Branch `task/0274-build-finishes`, version
0.2.227.

**What changed:**
- **23 finishes** as library materials (`core/materials_lib.py`, numbers 62–84) with a `finish` key; their table, settings,
  metal bases and kinds in `core/finishes.py` (no Blender), their nodes in `blender/finishes.py` (ported from the study's
  `finishes_proto.py`, not merged). Carbon, perlage, Rust and welds stay out (0318 / 0319).
- **Face data** `fr_fx_o/d/r/k` (FACE attributes, `core.finishes.face_frames`): written by `materials.assign` (and
  `faces.assign` for painted faces) only for a face-axis finish, and again when the mesh's signature (counts, sum of
  points, CAD axes) changed – so after a model update. Copies share their mesh: identical.
- **Far-away fade**: every finish reads the scene property `fr_pixel_angle` with an Attribute node (View Layer), kept up
  by `cameras.update_pixel_angle` from render_init / depsgraph / load handlers (set only on a change of > 1 %). Nothing is
  rebuilt when the camera or picture size changes. Not divided by the object's scale (no scaled part showed up wrong).
- **Group settings** `fin_size / fin_angle / fin_amount / fin_base / fin_kind` on `FRMaterialGroup`, drawn under the
  material only where the finish has them (Metal, Kind, Pitch / Feed / Hole size …, Angle, Strength); a new finish
  starts at its defaults; Size held at each finish's limits. Materials carry `fr_finish_set` (the settings text) and are
  rebuilt when it changes (`materials.group_material`, `is_current`).
- **Web 3D model**: `fr_finish_web` on the material; `web3d.Look` takes an "average" finish (knurls, spun, faced, honed,
  fabric, soft-touch, blasted, VDI) as numbers (colour, roughness, metallic, open share), a "tile" finish is baked with the
  fade off in the bake scene (test: the tread plate's lenses are in the tile).
- Tread plate and scraped ways snap their period to divide the web model's 0.2 m tile (25 → 25 mm, 12 → 11.8 mm).
- 8 finishes in **Ready-made material…**; the material sheet (PC check looks.materials) leaves the finishes out (they need
  CAD faces; their own picture is in looks.finishes).
- Test model `test_finishes.step` (`tools/make_test_finishes.py`, the study's invented shapes: 23 samples + a
  headphone-like set), tour set + stop **finishes**, PC-check line **looks.finishes**, function `looks.finishes`, guide
  3 Looks > Finishes with `docs/img/finishes_sheet.jpg`, `tools/ui_screens.py` hook `UISHOT_FINISH`.

**Cheaper builds** (the study measured > +30 %): blasted / shot-blasted / VDI / as-cast use noise instead of Voronoi (the
grain is < 0.3 mm, its cell shape cannot be seen); hammertone's flakes are a random value per 0.15 mm cell and its dents F1
instead of Smooth F1 (the dents now have crisper edges where they meet – still reads as hammertone, a little more
"hammered"); spangle drops the second Voronoi (crystal edges come from the brightness steps); sheet patterns (grille,
perforated, expanded, tread, scraped) work the pattern out once on the face's main axis instead of three blended times.

**Tested and measured** (4-core Claude Code web machine, no graphics card; Cycles CPU, 64 samples, adaptive + denoise,
480 × 270, each sample part close up on the finishes test model; "old" = the study's own build of that finish rendered in
the same scene):

| Finish | plain s | now | old (study build) |
|---|---|---|---|
| Knurl diamond / straight / grip | 10.0 / 9.7 / 10.3 | +23 / +26 / +11 % | |
| Spun / faced / honed | 9.7 / 10.4 / 10.0 | +12 / +8 / +47 % | |
| Cross-hatch / fabric / tread / scraped | 10.3 / 9.9 / 9.4 / 10.3 | +15 / +20 / +15 / +20 % | |
| Grille | 9.8 | +32 % | +66 % |
| Perforated | 9.2 | +44 % | |
| Expanded | 9.3 | +47 % | +63 % |
| Bead-blasted / shot-blasted | 9.7 / 9.9 | +9 / +13 % | +111 / +105 % |
| Hammertone | 9.8 | +38 % | +116 % |
| Wrinkle / anti-skid / leather | 9.3 / 9.8 / 10.2 | +23 / +15 / +30 % | |
| VDI 30 | 10.2 | +4 % | +64 % |
| Spangle | 9.4 | +32 % | +58 % |
| As-cast | 9.5 | +15 % | +111 % |
| Soft-touch | 10.6 | +5 % | |

The close-ups fill the picture with the finish, so these percentages are higher than the study's product shot (its
knurl +6 %, here +23 %). Node counts 15–121. Perforated and expanded stay above +30 %: the cost is the see-through
(Alpha) itself, not the pattern.
- Far away (`tasks/img/0274_far.jpg`): the board at 4 m and 15 m, 960 px, with the fade and with it off – with the fade
  the plates are calm; the denoiser hides most of the "off" sparkle at 32 samples.
- Tests: `tests/test_finishes.py` (16) and `tests/test_finishes_independent.py` (21, written by an independent tester
  subagent that did not write the code). It found 6 faults, all fixed: **round holes doubled** (grille, perforated: the
  study's hex grid put the next row half a row away – 71 % open instead of 35 %), a sheet at exactly 45° drew stripes,
  NaN settings went into the nodes, the pixel aspect halved the pixel angle, a negative start in the importer's
  `fr_axis_faces` was put on the last triangles, wrong-length arrays raised. Locally: the finish tests, the material,
  function, guide tests and test_core / part_types / toolmarks / lightbake / cable_looks (1,505 passed); the tour set
  builds in 4.7 s and its check passes; PC check line looks.finishes OK (8 s, render 5.2 s). UI checked with
  `tools/ui_screens.py` (UISHOT_TAB=3, UISHOT_FINISH=perforated: Metal, Kind, Hole size under the material).
- GitHub: 7 full runs on the branch. Green as 0.2.222, 0.2.223, 0.2.224, 0.2.225 and 0.2.226, but 0302, 0308, 0290, 0298 and 0294 took each number first (merge main, renumber); one red run as 0.2.224 on two test faults the merge brought (test_tour allowed at most 100 stops – 0308 + 0274 make 101 –, and the independent lesson test pressed Next with fast Show me timing, so the lesson moved the crane apart before the test's Ctrl+Z): both tests fixed. Released as 0.2.227.

**Owner's test steps** (after Update now to 0.2.227):
1. Open a project, go to **3 Looks**, click a group in the list.
2. **Material** → in **Metal** pick **Knurled, diamond (knobs, handles)**. Under it you should see **Metal**, **Pitch**
   (0.8 mm) and **Angle** (30°).
3. Switch the view to **Live preview** and zoom in on a round part of that group: fine diamond knurling round its round
   faces, rings on the end faces. Zoom out: it fades to a calm, slightly duller metal.
4. Try **Perforated sheet (see-through)** on a plate: round holes you can see through; **Kind** → **Slotted holes**.
5. Help > **Make test tour project**, stop **Finishes**: the board of 23 samples and the headphone-like set.

**Open points / follow-up tasks:**
- A rule set and a paint scheme keep a group's material and colour only (not Wear either): a finish's own settings
  start at their defaults there (said in the guide). Worth a small follow-up if the owner uses rule sets with finishes.
- The material name in the group box is cut at the default side-panel width for the longer labels ("Perforated…-through)"),
  as for the older long names.
- Hammertone looks a little more "hammered" (crisper dent edges) than the study's build, for −79 points of cost.
- 0273 (thumbnails): the study's swatch idea stands (the chamfered block with a knurled knob on top and a spun cap
  leaning in front, 256 px, 32 samples, ~3.5–5.4 s each on this machine).
- 0318: carbon on curved parts, perlage, Rust slider, spheres in `_face_axis` – not touched.
