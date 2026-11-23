# 0274 – Build the new finishes from study 0270: knurls, spun, moulded, fabric, plate patterns, blasted, paints, grains

**Who:** worker · **Status:** open – can start · **Branch:** `task/0274-build-finishes`
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

- [ ] 23 finishes in the app, close-up + product pictures as good as the study's (sheet in the report)
- [ ] Face data written on import and after a model update; copies / turned / mirrored parts identical (test)
- [ ] Fade far away (4 m / 15 m sheet: no moiré, no sparkle)
- [ ] Cost table before / after; the cheaper builds where they hold the look
- [ ] Web 3D model: each finish exports as the study says (test)
- [ ] Tests added/updated; full suite passes; screenshots checked with `tools/ui_screens.py`; version fields
- [ ] Owner's test steps in the report; merged, version, release

## Not in this task

Carbon fibre, perlage, the Rust slider, spheres in the importer, existing looks (0318); welds (0319); the picker window
and thumbnails (0273 – but leave the study's swatch idea in your report for it); Adjust (0314); painted steel (0287).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
