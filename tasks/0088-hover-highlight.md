# 0088 – Hover highlight when picking an axis (face, hole, shaft light up under the mouse)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0088-hover-highlight` (or the session's own branch)
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

- [ ] Tests: for spots on the test crane (a hole, a shaft, a flat face, the floor, empty space) the hover gives the right
      CAD face (triangle range) and the same axis as the click; nothing is drawn after Esc / finish / file load; the
      overlay never appears in a render; a real-app test (`event_simulate` mouse moves during Add joint) checks the
      highlight state and the status text; the existing joint, cylinder and double-arm real-app tests still pass.
- [ ] Time per mouse move (test crane, Heavy scaled down) in the report; screenshots of a highlighted hole and face
      checked (cropped small).
- [ ] PC-check line, guide, tooltips strict; GitHub green incl. Windows; merged to `main` with the next free version,
      released.
- [ ] Report filled in; `TASKS.md`: 0088 done.

## Not in this task

The same highlight in the other click pickers – tool-changer pockets (`ops_gcode.py`, Machining lane), the sharp spot
(`ops_scene.py`, 0087), labels, decals, trail points, coolant nozzles, toolpath parts: a short follow-up once those lanes
are free (the lead plans it after 0061 and 0087; `hover.py` should make it a few lines per picker). Hovering to select
whole subassemblies in the tree or the view (outside a pick).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
