# 0088 – Hover highlight when picking an axis (face, hole, shaft light up under the mouse)

**Who:** worker · **Status:** done (0.2.63) · **Branch:** `task/0088-hover-highlight` (or the session's own branch)
**Started by:** lead chat, 11 Nov 2026 (owner's wish)
**Lane:** new **Pick & hover lane** – a new `blender/hover.py` (the highlight: what is under the mouse, the drawing);
the click-to-pick operators that give an **axis**: `ops_motion.py` (Add joint / Set axis), `ops_cylinders.py` (the
cylinder's pins), `ops_doublearm.py` (arm hub, pot hinges), `ops_linkages.py` if it has a click pick; read-only use of
`joints.axis_from_hit` and the CAD face blocks (`fr_face_starts`, `faces.py`); tests, PC-check line, guide
**Model:** **Opus · effort Medium** (drawing in the 3D view, speed on big models, several operators) · **Place:** Claude
Code on the web, environment "CAD-render-animation"

Runs at the same time as **0084**, **0085** (vessel motion), **0086** (cutaway: `section*.py`, `fade.py`, `materials.py`,
maybe a hook in `joints.py`), **0087** (camera: `cameras.py`, `ops_scene.py`, the camera part of `animation.py`,
`ui_motion.py`), **0035** (way covers) and, from Thursday 08:00, **0058** (Flex parts) and **0061** (Machining). **Do not
edit `joints.py`, `ops_scene.py`, `ops_gcode.py`, toolchange or any machining file** – the pickers there get the highlight
in a follow-up (see "Not in this task"). Several releasing tasks at once: take the version number last; whoever finishes
later merges `main` once and renumbers (CLAUDE.md section 2).

## Goal

When the owner clicks *Add joint* (or sets a cylinder's pins, the double arm's hub …) and moves the mouse over the model,
the CAD face the click would use **lights up before he clicks**: the whole hole, shaft, cylinder, cone or flat face, with
a preview of the axis it would give. He sees at once whether he is on the hole or on the face next to it, and no longer
has to click, check and redo.

## What to build

1. **The highlight** (`blender/hover.py`, one helper every picker uses): on mouse move during a pick, ray-cast as the
   click does; take the hit part's **whole CAD face** (the triangle block in `fr_face_starts`) and draw it on top of the
   model as a see-through fill with an outline, in one strong colour that reads on any material (e.g. Fresing orange;
   say what you chose). Draw the **axis it would give** – exactly what
   `joints.axis_from_hit` returns for that spot: a line through a hole's or shaft's centre (sticking out a little past
   the part on both ends) or an arrow square to a flat face – plus a short text next to the mouse or in the status bar
   ("Hole Ø20 – axis through its centre", "Flat face – axis at right angles"; the size from the face data where known).
   Floor, surroundings and empty space: no highlight, the status bar says "not a part". Parts that may not be picked
   (e.g. the movers themselves where a picker refuses them) are drawn in a "no" colour with the reason.
2. **Only an overlay:** never in renders, never in the saved file, gone after Esc, right-click, a finished or refused
   pick, an error, undo, or opening another file. Works with every view shading, X-ray look, fades, cutaways (0086),
   decals and painted faces, and with a model of several copies of the same part (each copy has its own place).
3. **Fast on big models:** the work per mouse move must not make the view stutter – cache the drawn face per (part,
   CAD face), only redo when the face under the mouse changes, skip moves while the previous one is still being
   worked out. Measure the time per mouse move on the test crane and on the PC check Heavy model (scaled down) and
   put the numbers in the report; aim for < 15 ms on the Heavy model on the 4-core web machine.
4. **The pickers in this task:** Add joint and Set axis (4 Motion > Joints), the cylinder's pins (4 Motion > Cylinders),
   the double arm's hub and pot hinges (4 Motion > CNC machine > Tool changes > Double arm), and any click pick of the
   mechanisms that picks a hole or axis. Same click result as today (the highlight changes nothing about what a click
   does); a test proves the highlighted face = the face the click then uses.
5. A preference to switch it off (Fresing preferences, on by default) in case it ever gets in the way. Guide: one
   paragraph + a picture in chapter 4 (a hole highlighted with its axis line, test crane); PC-check line `motion.hover`
   (the hover worked out for 20 spots on the test crane: right face, right axis, time per move as a metric);
   `CHANGELOG.md`. A tour stop only if the tour can show it without a real mouse (say in the report why or why not).

## Done when

- [x] Tests: for spots on the test crane (a hole, a shaft, a flat face, the floor, empty space) the hover gives the right
      CAD face (triangle range) and the same axis as the click; nothing is drawn after Esc / finish / file load; the
      overlay never appears in a render; a real-app test (`event_simulate` mouse moves during Add joint) checks the
      highlight state and the status text; the existing joint, cylinder and double-arm real-app tests still pass.
- [x] Time per mouse move (test crane, Heavy scaled down) in the report; screenshots of a highlighted hole and face
      checked (cropped small).
- [x] PC-check line, guide, tooltips strict; GitHub green incl. Windows; merged to `main` with the next free version,
      released.
- [x] Report filled in; `TASKS.md`: 0088 done.

## Not in this task

The same highlight in the other click pickers – tool-changer pockets (`ops_gcode.py`, Machining lane), the sharp spot
(`ops_scene.py`, 0087), labels, decals, trail points, coolant nozzles, toolpath parts: a short follow-up once those lanes
are free (the lead plans it after 0061 and 0087; `hover.py` should make it a few lines per picker). Hovering to select
whole subassemblies in the tree or the view (outside a pick).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (session branch `claude/hopeful-hamilton-985bip`), 11 Nov 2026

**What changed:**
- New `blender/hover.py`: `look()` is the work of one mouse move (the pickers' ray `cast()`, the CAD face from
  `fr_face_starts`, `joints.axis_from_hit`, hole/shaft/flat, the text); `start` / `on_event` / `prompt` / `pick` /
  `end` are the few lines per picker. Drawing: two 3D-view draw handlers (face fill 35 % + outline on a dark line,
  the axis line past the part or an arrow on a flat face; a text box next to the mouse) and the status bar.
- **Colour: magenta** (1.0, 0.1, 0.8), not orange: Blender draws the selection outline in orange and the test crane
  (and many machines) is painted yellow/orange – orange did not read (checked on a screenshot). Refused spots: red
  with the reason.
- Pickers: Add joint / Set axis (`ops_motion.py`), Add cylinder and Pins again (`ops_cylinders.py`), the double arm's
  hub and pot hinge (`ops_doublearm.py`, with refusals worked out while hovering: hub not parallel with the
  spindle; no carousel / no arm yet / pot not on the carousel). Mechanisms (`ops_linkages.py`) have no click pick
  (they use the selection), so nothing to do there.
- Click result unchanged, with one deliberate exception: the click now looks through a logo/sticker to the part under
  it (`decals.through`, as its docstring intended for joint axes); before, it said "missed". `_raycast` itself is
  unchanged (callouts and G-code pickers of other lanes still use it).
- Only an overlay: nothing in `bpy.data`, `fr_face_starts` is not written by a hover (old meshes: worked out in
  memory), no draw handler in background mode. Ends with Esc / right-click / click / refused pick; undo clears it,
  opening another file ends it (`load_pre`), and a pick that died with an error is noticed by the draw callback
  (the freed operator raises) and removed.
- Preference "Highlight the face under the mouse when picking an axis" (on by default). PC-check line `motion.hover`
  (MIN_LINES_FULL 55 after the merges). Guide: paragraph + `view_hover.png` in chapter 4 (new mode `hover` in `tools/guide_screens.py`).

**Tested and measured** (name the machine and the model):
- `tests/test_hover.py` (10 tests, bpy module): shaft (BOOM.PIN, polygons 0–52), hole (PEDESTAL bore Ø40.4, the pin
  moved out), flat face (BASE, arrow up), floor and empty space ("Not a part"), two copies of WHEEL (each its own
  axis, one cached face), a refused spot, highlight = click (same part, face, triangle range, axis), nothing in
  bpy.data changes and a Cycles render is pixel-identical with a hover on, gone after end / undo / file load.
- Real app `ui_test_app.py` (ui1, 27/27 quick locally; +9 checks, MIN_CHECKS 32 / quick 27): mouse moves during Add
  joint – sky says "Not a part", the pin lights up (face 0) with "Shaft Ø40 mm – axis through its centre" in the
  status bar, draw handlers on; the joint the click makes has the highlighted axis; gone after the click; Set axis +
  Esc: gone. `ui_test_cylinder.py` 22/22 and `ui_test_doublearm.py` 19/19 still pass.
- Time per mouse move (`hover.look`, 4-core web machine, bpy module, iso-view rays at random parts, first time on a
  spot / same spot again):
  - test crane: 0.04 ms (PC-check line: median 0.09 ms, slowest 0.54 ms over 20 spots)
  - Heavy scaled down (300 parts, 0.2 M unique triangles): median 0.09 ms, 95 % 1.75 ms, max 12.4 ms (the first
    touch of a big part reads its mesh once) / again: median 0.08, max 0.43 ms – under the 15 ms aim
  - Heavy full size (2,992 parts, 2.3 M unique triangles): median 2.1 ms, 95 % 13.2 ms, max 23 ms / again: median
    2.0, max 4.5 ms (the 2 ms is Blender's own `scene.ray_cast` over 3,000 objects – the click costs the same)
- Screenshots checked (cropped): the pedestal's bore with its axis line (guide picture) and a flat face with its
  arrow (scratch only).
- PC check `motion.hover` run locally: OK, 20 spots (flat, shaft).

**Runs:** 3 full GitHub runs, all green: the first push, then twice a merge of `main` because 0035 and 0087 took
0.2.61 and 0.2.62 in the meantime (renumbered to 0.2.63, PC-check line counts raised with theirs). One local test
(`test_real_app_verdicts`) had the old quick count of ui1 hard-coded: it reads the table now.

**Tour stop:** none. The tour's Go sets up a scene and takes a picture without a mouse; the highlight only exists
while a click picker runs and the mouse moves over the view, so a stop could only show a staged copy, not the real
thing. The PC-check line and the real-app test cover it instead.

**Open points / follow-up tasks:**
- The other click pickers (ATC pockets in `ops_gcode.py`, sharp spot in `ops_scene.py`, labels, decals, trail points,
  coolant nozzles, toolpath parts): each needs `hover.start` in invoke, `hover.on_event` first in modal,
  `hover.pick` for the click and `hover.end` in its end – a few lines per picker.
- Only the owner can see it on the RTX 3090 / Windows: the colour on his own paint schemes and that the view stays
  smooth on his big models.
