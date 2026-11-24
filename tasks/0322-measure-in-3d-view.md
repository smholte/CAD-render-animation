# 0322 – Measure in the 3D view: a Measure menu in the top bar and a key

**Who:** worker · **Status:** running · **Branch:** `ccr-b4de08d0-he2cht` (the web session's branch)
**Started by:** lead, 24 Nov 2026 (owner 11:44: "Yes measuring in the 3D viewer. This should open from a separate menu
from the top bar of the app or with a keybind.") · **Model:** Opus · effort High
**Area:** new **Measure lane** – new files `core/measure.py` (no Blender: distances, angles, radius, units),
`blender/measure.py` (snapping on the CAD faces, drawing), `blender/ops_measure.py`, `blender/ui_measure.py` (the
top-bar menu); additive: `ui_topbar.py` (one menu), `lock.py` (the key in the app's key list; allowed in the Client
view), `props.py`, `core/functions.py`, `core/workspaces.py` (add Measure to Reviewer and Welding – if 0321 is merged;
otherwise 0321 adds it); tests, guide, tour, PC check, CHANGELOG. **Reads** the 3D page's measure tool
(`fresing_render/web/fr_tools.js`, `core/web3d_faces.py`) for the snapping rules – one behaviour for both.
**Not:** the 3D page's own tool, 2D drawings, weld symbols.

## Goal

Anyone – a reviewer, a sales person, a welding engineer – can measure the model in the app the way they can on the 3D
page: open **Measure** in the top bar or press a key, click, read the value.

## Background

- The app has no measuring in the 3D view (0294's open point: Reviewer has none). The exported 3D page has one
  (`web.tools`, `fr_tools.js`): learn from its snapping and labels.
- The mesh knows its CAD faces and axes (`fr_face_starts`, `fr_axis_faces`): snap to whole faces, round faces' axes,
  edges and corners.
- 0295 (Keys tab, after 0291) will make the app's keys changeable: register the key so 0295 can list it.

## What to do

1. **Top-bar menu "Measure"** (icon + word): Distance (point to point), Edge length, Face to face (parallel faces:
   the gap), Angle (between two faces / edges / three points), Radius / diameter (a round face), Point to axis, Clear
   all, Units (mm / m / inch). **A key** (propose one that clashes with nothing the app or Blender uses – say which;
   e.g. M), Esc leaves.
2. **Snapping**: corners, edge middles, edge lines, face centres, round faces' axes and their centres; a hover hint
   shows what will be picked; Shift = no snap.
3. **Results**: a label in the 3D view (the app's label style) with X / Y / Z parts for a distance; measurements stay
   until cleared, are saved with the project (switch *Keep measurements*), **never in renders** unless *Show in
   renders* is ticked; copy a value with one click.
4. Works on moved / posed parts (world positions of the current frame), in the Client view (read-only), with a section
   cut (snaps on the cut face).
5. Guide (Measure), function entry `view.measure` (`since=`), a tour stop on a test model, a Full PC-check line (a
   known block measures its known size within 0.01 mm).

## Done when

- [ ] Menu + key; all six kinds; snapping as above; Units (tests with known shapes)
- [ ] Labels kept / cleared / saved; not in renders by default; Client view works
- [ ] Tests added/updated; full suite passes; screenshots checked; version fields; owner's test steps; merged, release

## Not in this task

The 3D page's tool, 2D drawings, weld symbols (0320), the Keys tab (0295).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
