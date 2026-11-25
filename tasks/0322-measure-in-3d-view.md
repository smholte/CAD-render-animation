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

- [x] Menu + key; all six kinds; snapping as above; Units (tests with known shapes)
- [x] Labels kept / cleared / saved; not in renders by default; Client view works
- [x] Tests added/updated; full suite passes; screenshots checked; version fields; owner's test steps; merged, release

## Not in this task

The 3D page's tool, 2D drawings, weld symbols (0320), the Keys tab (0295).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 24 Nov 2026 (branch `ccr-b4de08d0-he2cht`, the web session's branch).

**What changed** (0.2.242):

- **Top bar > Measure ▾** (right of Lead motions, every workspace and the Client view; `ui_measure.py`): a big
  **Measure** (result by what you click = the 3D page's `measure(a, b, 'faces')`) and the six kinds Distance (+ X / Y /
  Z), Edge length, Face to face, Angle (two faces / edges, or three points), Radius / diameter, Point to axis; the list
  of measurements (eye, Copy, Remove), Clear all, Units mm / m / inch, Show measurements, Keep measurements, Show in
  renders, Label size.
- **Keys** (`lock.APP_KEYS`, so 0295 lists them): **M** outside Full access – Blender's M ("move to collection") was
  swallowed there already, its entry left `BLENDER_KEYS`; **Alt+M** everywhere (nothing on Alt+M in Blender's Object
  Mode, 3D View, Screen or Window keymaps – checked in the real app's default keymap). Both start the kind last picked.
- **The tool** (`ops_measure.py`, modal in the main 3D view, also when started from the top bar): hovered face lit,
  snapped point as a dot, snapped edge as a line, what the click takes + the value the last click will give next to
  the mouse; red reason for a click that does not fit; a click on a label copies its value; Esc / right mouse drops
  unfinished clicks, a second Esc leaves.
- **Snapping** (`measure.py`, `core/measure.py`): per mesh the CAD faces and edges of `core/web3d_faces.py`
  (`classify` + `edges`, the page's data – one behaviour), worked out once (23 ms for the crane's base); candidates of
  the hovered face: corners, edge / arc middles, face centre (flat: area middle; round: axis middle), round-edge
  centres, edges, the face. Points within 14 px, else edges within 9 px, else the face; Shift = none.
- **Through a slice**: a hit on the side a cut takes away goes on to the cut face; if that point lies inside the part
  (the next hit is a back face of it) the click takes the cut face (flat, normal to the viewer). Welds, the floor and
  the surroundings are looked through.
- **Measurements** (`scene.fresing_measure`, own property group like the welds – `props.py` untouched): picks in the
  clicked part's coordinates, so values follow moves, joints and animations. Saved with the project; Keep off or the
  Client view: left out at save (`save_pre` / `save_post`). Drawn by two 3D-view draw handlers (never in a render);
  **Show in renders**: a tube for the lines and a white-on-dark label per measurement facing the camera, pulled to 20 %
  of their distance towards the camera (same spot on the picture, nothing hides them), moved apart like the view's
  labels, updated at every frame change.
- Function `view.measure` (all workspaces incl. Reviewer – via its own `workspaces=`, so 0321 can add Welding), guide
  section **Measure in the 3D view** + picture, tour set + stop **measure**, PC-check line **view.measure**.

**Tested and measured** (web machine, 4 cores, no graphics card):

- `tests/test_measure.py` (11 tests): the Python maths against `fr_measure.js` in node, 15 pairs + 4 singles, equal
  to 1e-12; units, words, kinds, snapping order; on the test crane's base (5000 x 3000 x 500, Ø33 holes 4500 apart):
  500.00 / Ø 33.00 / 4500.00 mm, Shift, point to axis, edge; a moved and turned base keeps 4500.00; saved file has 1,
  with Keep off 0; Client view never saves; through a slice 1500.00 mm to the back face, cut off = the front face
  again; units / Copy / Remove / Clear all; render objects only when ticked; keys and top bar.
- Real app `tools/ui_test_measure.py` (group callouts, 16/16, 35 s): M over the view starts it, two clicks = 90.00°,
  the label is drawn and a click on it copies "90.00°", Edge length from the top bar = the face data's length, one click
  opens the drop-down, the Client view measures with M, Full access: M is Blender's, Alt+M measures. Screenshots
  checked (view with labels, the drop-down; a Cycles render of the tour set with Show in renders).
- Tour set `measure` builds in 2–4 s, its check passes after save and reopen. PC check `view.measure`: OK, a mouse
  move 0.8 ms (face data cached).
- GitHub: 4 full runs. Run 1 (45501146042) red: M was still in the key tests' and the PC check's "swallowed" lists
  (the keys real-app test then also lost its right-click checks: M had started Measure, whose modal ate them),
  Measure named in the task workspaces broke their "exactly these functions" lists (now in `_COMMON`, as Lead
  motions), the Client view's allow-list bound +5. Run 2 (45509180133) red: my own new PC-check line read Alt+M for M.
  Run 3 (45513891466) green; then 0235 took 0.2.239 on `main`: merged, renumbered. Run 4 (45518630428) red twice
  (also after a re-run of the job): `test_stress.py`'s memory-watch test – its 200 MB peak was a Python bytes object,
  which reused memory the process already held after the tests my new file moved before it in that job; the test now
  maps 200 MB of fresh pages (task 0315's file, a test-only fix). Meanwhile 0320 took 0.2.240 and 0273 0.2.241: merged,
  renumbered to 0.2.242, run 5.

**Open points / follow-up tasks:**

- The labels in renders turn with the camera (Track To), so a camera with roll tilts them; a rolled camera is rare.
- Angle between two flat faces is the angle between their planes (0–90°, "(or 180 − x)" added), as the page.
- A mesh model (glTF / OBJ) has no CAD faces: it measures between points only (as the page).
- No independent review agent ran (no Windows-only code; usage saved) – the 3D page's own maths is the reference.
