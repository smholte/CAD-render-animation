# 0086 – Cutaway / section view (study 0069 #1)

**Who:** worker · **Status:** done (0.2.64) · **Branch:** `claude/serene-noether-vmu9y5`
**Started by:** lead chat, 11 Nov 2026 (lead's pick from the improvement study; the owner can change it)
**Lane:** new **Cutaway lane** – new files `blender/section.py`, `blender/ops_section.py`, `blender/ui_section.py` (a
sub-panel of 3 Looks in its own file), `core/section.py` if useful (no Blender); the material hook next to the Fade
group (`blender/fade.py`, `blender/materials.py` `build_nodes` re-wrap – Looks lane is free); additive only:
`blender/props.py`, `blender/reimport.py` (carry cuts over), `blender/joints.py` only if the app-made cut joint needs a
hook (see 3); tests, tour stop, PC-check line, guide
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0085** (vessel motion: `vessel_motion*.py`, the sea), **0087** (camera rides / flies:
`cameras.py`, the camera part of `animation.py`, `ui_motion.py` camera settings) and, from Thursday 08:00, **0058**
(Flex parts: `flex*.py`, hooks in `handlers.py`, `animation.py`, `reimport.py`) and **0061** (Machining: tool marks on
cut faces). **Do not edit `animation.py`, `ui_motion.py` or any machining, coolant, chips, air, G-code or toolchange
file.** Several releasing tasks at once: take the version number last; whoever finishes later merges `main` once and
renumbers (CLAUDE.md section 2).

## Goal

Show the inside of a machine in one click: a cutting plane (or box) through chosen subassemblies, the cut faces filled
with a cap colour, and the cut can move in an animation ("the housing opens up"). For a winch gearbox, a tensioner, a
spindle – and the cut-away hull of the cable-lay demo video (0083 shot list, shots 9 and 10).

## Read first

`tasks/0069-improvement-study.md` row 1; `tasks/0073-fade-xray-trail.md` report (how the Fade group wraps every material
of a part and reads *object* attributes, so shared materials stay per part); `blender/surroundings.py` `_cutaway`
(the halls' cut-away, a shader trick that already works).

## What to build

1. **3 Looks > Cutaway:** *Add cut* → pick what it cuts (groups, subassemblies, or the whole model), shape **Plane**
   (Flip) or **Box** (a corner cut away / a quarter cut), place it by moving its handle in the view or by numbers,
   **cap colour** (default a strong red, editable; optional hatch lines), on/off per cut, several cuts per project,
   kept with the project, in saved scenes and through a model update. Header state ("2 cuts · 1 on").
2. **The way it renders – the shader way first:** a node group in every material of the cut parts (composed with the
   Fade group: a part can be cut *and* fade), switched per object by an object attribute, cutting by the position in
   the cut object's space (Texture Coordinate > Object); the inside seen through the hole (back faces) drawn in the cap
   colour and lit as if it faced out of the cut. Fast with thousands of parts, Cycles and EEVEE alike, scripts off,
   the render queue. Light passes through the hole as it would through a real cut. Decals, painted faces, glass,
   X-ray and the milled cut-face look keep working; a material rebuilt by a look change is wrapped again (the 0073
   way) – for materials the machining files make, do it generically without editing those files, and report anything
   not covered. Known limit: caps are right only for closed solids – say how many parts of the test models and the
   0076 demo hull are open shells, and how they look. An exact boolean cut only if the shader way fails in a case that
   matters (measure and say).
3. **Moving the cut:** prefer making the cut's place an **app-made slide joint** (as the double arm's joints, 0064, and
   0075's virtual "cable" joint), so the existing *Move joint* step, poses and the queue move it – no new step kind and no
   change in `animation.py`. If that cannot work, stop and write in the report what is needed (the lead plans the step
   after 0058 and 0087 are merged).
4. The clash check ignores cuts (geometry is unchanged); labels and the sharp spot keep their parts.
5. Every button a tooltip; guide section in chapter 3; PC-check line `looks.cutaway` (a picture of a cut model + the
   render time); tour stop "Cutaway" on a test model with something inside (your pick, say which); `CHANGELOG.md`.

## Done when

- [x] Tests: a closed box cut in half renders the remaining half and the cap colour in the right pixels (small Cycles
      and EEVEE renders); Flip; Box cut; a part of the same material not in the cut renders as before; cut + fade
      together; the cut moved by a Move joint step lands at the right place at sampled frames; scripts off; queue-runner
      frame = view frame; save/reopen; model update keeps the cut's parts; an old project renders as before.
- [x] Render time per frame with a cut vs without (Cycles Draft, a test model; and the PC check Heavy model scaled
      down) in the report – a cut must not make every frame much slower.
- [x] The all-tour clash test still 0 rows; tour stop, PC-check line, guide, tooltips strict; GitHub green incl.
      Windows; merged to `main` with the next free version, released.
- [x] Report filled in; `TASKS.md`: 0086 done.

## Not in this task

A new animation step kind (see 3), cut-away of the sea / underwater views (0081), section lines on technical
drawings, measuring tools.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (environment "CAD-render-animation", 4 cores, no graphics card),
11–12 Nov 2026. Branch `claude/serene-noether-vmu9y5`. Version 0.2.64.

**What changed:**
- **3 Looks > Cutaway** (new `blender/section.py`, `ops_section.py`, `ui_section.py`, `core/section.py`): Plane/Box
  choice, **Add cut: the selected** / **This group** / **Whole model**, list of cuts (tick = on/off, name), under it
  Shape, Flip, Cap colour (red by default), Hatch lines + spacing, Box size, what it cuts (× to take one out, Add
  selected / Add group), Select the arrow, To the middle, the Slide value, fold Place by numbers (position and turn
  in model coordinates, drawn size). Header "2 cuts · 1 on". A new cut goes through the middle of what it cuts and
  takes away the side facing the 3D view the button was pressed in (else the scene camera).
- **The shader way:** one node group "FR section" in every material of a cut part, inside the Fade group (cut first,
  then fade: a faded part's cap fades too); `materials.build_nodes` wraps it again after a look change. Per part an
  object attribute `fr_cut_<key>`; the cut's space from Texture Coordinate > Object of the cut's shape object; the
  shape's world turn and size come into the group through AVERAGE drivers with transform variables (no Python:
  scripts off works). Taken-away side transparent for every ray (light falls in). The inside seen through the hole
  (back faces) is drawn in the cap colour with the normal of the nearest cut face; hatch lines are worked out where
  the view ray meets the cut plane. **Found on the way:** the cap is drawn on the solid's far inside wall, and in
  Cycles light reaching that point was blocked by the solid's own walls (the cap rendered almost black): only camera
  and reflection rays see the cap now, light and bounce rays pass the inside walls, so the cap is lit as an open cut
  face. Glass (transmission materials) and decals get no cap.
- **Floor:** the app's floor sits exactly at the model's lowest face; through a cut the floor (a shadow catcher in
  shadow) won against the bottom part's cap and showed as dark patches. Adding the first cut sets 5 Scene & Render >
  Floor gap to 0.1 mm when it was 0 (the user's setting, shown in the panel; said in the guide).
- **Moving the cut:** each cut has an app-made **slide joint** with the cut's name (its frame is the arrow = handle,
  unlocked; the motion carries `fr_section` and `fr_atc = "cut"`, so the G-code set-up never takes it as an axis).
  The shape object follows the motion by a Child Of constraint (no parent: 2 Structure does not list it). Move joint
  steps, poses and the queue move it; **no change in `animation.py`**. Renaming the cut renames its joint.
- **Model update** (`reimport.py`, additive): the cut joints come off before the model's joints are taken apart
  (kept on the cut: place relative to the model, value, limits, name) and are made again on the new revision; part
  targets follow their part ID; groups are synced after the rules ran. **Saved scenes** (`states.py`, 2 lines) keep
  which cuts are on (`FRShot.cuts`; scenes saved before: unchanged).
- New materials on a cut part (a look change, painted faces, the milled block's cut faces) are wrapped by a
  depsgraph handler (a one-shot timer) in the app and by a `render_init` sync before any picture or video (also the
  render queue's background Blender) – the machining files are not edited. Cycles transparent steps raised to 128
  while a cut is on (as the halls).
- Tour: new set "Cutaway" (test crane: a hatched plane cut through the pedestal and the boom, the pin shows inside)
  with stop "Cutaway: the pedestal opens up" (animation: the cut slides in 200 mm with a Move joint step); PC-check
  line `looks.cutaway` (Full); guide section 3 Looks > Cutaway with `panel_3_cutaway.png` and a render
  `cutaway.jpg` (new mode `cutaway` of `tools/guide_screens.py`); `tools/tooltip_report.py` now reads
  `ui_section.py`; CHANGELOG.

**Tested and measured** (this 4-core web machine, no graphics card):
- New `tests/test_section.py` (20 tests): placement maths and header words; objects, joint, attributes, only the
  cut parts' materials wrapped; handle by numbers and slide move the shape; scripts off (6 AVERAGE transform drivers,
  no Python); rebuild by a look change + fade order; a new material wrapped; group / part / whole-model targets,
  on/off, remove; saved scenes on/off; an old project unchanged (no group, no wrapped material, no attribute, floor
  gap 0); **renders** (Cycles, 40 px): the closed 1000 × 600 × 50 mm FRAME of `test_machine.step` cut in half – the
  remaining half orange, the other half gone, the cut face red seen from the side; Flip; Box quarter and Flip (only
  the box stays); bolts of the same material not cut render as before (mean pixel difference < 0.01); cut + fade
  (faded: no cap left); EEVEE in a child process (cap red, half gone; skipped where EEVEE cannot start); Move joint
  step: the shape at frames 1/26/51 within 1e-6 m of linear from 300 mm to 0, and the frame-26 render cut at
  x = 0.35 m; save, reopen, build again (as the queue runner): same places, render with the cap; model update crane
  A → B keeps the joint, its value (0.04 m), place, colour, part target (new uid) and the new revision's lamp in the
  boom; operators with a decal (the sticker cut, no cap); the milled block's cut-face material made later is wrapped
  at render start; a camera made just before is faced (a bug found on the demo vessel: a new camera had no world
  place yet, the box went to the far quarter).
- Locally also green: `test_fade`, `test_model_update`, `test_same_step_twice`, `test_phase2`, `test_queue_fixes`,
  `test_faces`, `test_decals`, `test_materials_look`, `test_pccheck`, `test_tour` (every stop's Go and check),
  `test_user_guide`, `test_ci_tools`, and `test_clash.py::test_every_tour_animation_has_no_clash` (still 0 rows with
  the new set). `tooltip_report.py --strict`: 580 ok. PC check `looks.cutaway`: OK.
- **Render time per frame, with a cut vs without** (Cycles Draft on the processor):
  - test crane, 320 × 180 (PC check line, after a warm-up render): **1.8 s with the cut, 1.8 s without (1.03 ×)**;
  - PC check Heavy model scaled down (300 parts, a whole-model plane cut), 480 × 270: 3.3–3.4 s with vs 3.2–3.3 s
    without; a box cut 3.3 s;
  - Heavy model full size (2,992 parts / 600 unique, written by `heavy_scene.py`), 480 × 270, two runs each:
    **8.1–8.6 s with a whole-model cut vs 7.9–8.3 s without**; a box cut 8.0 s. Adding the whole-model cut took
    3.3 s (0.4 s on the 300-part model, 0.15 s on the crane).
  So a cut costs a few per cent per frame at most.
- **Open shells:** every part of all 27 test models in `tests/data` and the 9 parts of the 0076 demo vessel
  (`demo_vessel.step`, written by `tools/make_demo_cable_lay.py`) are closed after import (no edge with one face) –
  0 open shells, so their caps are right. Rendered on the demo vessel: a box (bow quarter) and a plane (bow half)
  cut show the hull plating, deck and deckhouse cut faces red. An open shell would show its inside face in the cap
  colour (said in the guide).
- Guide pictures made in the real app (Blender 5.2.3 under xvfb): the panel at the default width (two labels that
  were cut off were shortened) and the crane render.
- GitHub runs: 4 full runs on the branch, all green – 43116908780 (20.8 min), then three more only because other
  tasks released first and took the version (0035 → 0.2.61, 0087 → 0.2.62, 0088 → 0.2.63; one run replaced by a
  newer push when 0084 merged): 43121968724 (12.4 min), 43123771450 (13.9 min, the one released). `main`
  fast-forwarded to that commit (mode reuse).

**Open points / follow-up tasks:**
- The arrow (handle) slides the cut along its own direction; a box slides along its Z. A box that should slide
  along X or Y: turn it (or swap its sizes). A choice of slide axis for boxes could follow if wanted.
- The cut's turn is read every frame (drivers), but the cut moves only by its slide joint and by hand; it does not
  ride on another joint (e.g. a cut that turns with a slewing part) – not asked.
- A group target follows its group when the cut is changed, before a picture/video and after a model update; after
  a rules change alone, the rendered view shows the old members until one of those (said nowhere: rarely matters).
- The shadow of a cut part is drawn as if the cut face were open (light that would hit the cut face from the
  taken-away side passes): a thin band at the edge of its shadow; not seen in the test pictures.
- EEVEE: the cap's lighting uses EEVEE's shadow maps from the solid's far inside wall: a cap facing away from the
  sun can look a little darker than in Cycles.
- The PC check has no Heavy line for cuts (measured above instead).
