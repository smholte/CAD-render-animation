# 0240 – Hoses, cables and drag chains placed in the app by clicking points (no CAD part needed)

**Who:** worker · **Status:** open · **Branch:** `task/0240-draw-hoses-cables-chains`
**Started by:** lead, 20 Nov 2026 (owner 16:55: "hoses and cables are usually not included in the cad model, so i want
to place them from inside of fresing render easily, by selecting positions. The same for drag chains, they are often
included but very simplified so not useful for animations so they would most likely be hidden for render") ·
**Model:** Opus · effort High
**Area:** Flex parts lane – `core/flex.py` (only: a hose through clips = segments), `blender/flex.py`, `ops_flex.py`,
`ui_flex.py`; `blender/paths.py`, `ops_paths.py`, `ui_paths.py` (a cable route by clicks); `blender/hover.py` (only if
the picker needs a point-on-face mode it lacks); `props.py` (additive), `reimport.py` (additive: keep drawn items on a
model update – one hook, no change to the matching; 0237 works in `_made_assemblies`), a **new** tour set
`flex_drawn` in `tour.py` (do not edit the sets `hoses`, `chains`, `cables` – 0233 owns them), `core/functions.py`, the
PC check, guide chapters "Hoses and drag chains" + "Cables and paths", tests.

## Goal

A user whose CAD has no hoses or cables (the usual case from Inventor and Fusion) adds them in Fresing Render by
clicking: **Draw hose** – click the fitting at end A, optionally the clips it runs through, then the fitting at end B;
the hose appears with a sensible length and follows the motion like a hose read from CAD. **Draw cable route** – click
where the cable starts (a drum or a part), the sheaves / rollers it runs over in order, and where it ends; it runs and
turns them like a CAD cable. **Draw drag chain** – click the fixed-end bracket and the moving-end bracket, set width,
height, link pitch and bend radius; the app builds a proper chain of links that rolls with the axis. A simplified CAD
hose or chain is **replaced**: one click hides it for good (view, renders, clash check) and the drawn one takes over.

## Background

- **Today everything starts from a CAD part** (guide "Hoses and drag chains", "Cables and paths"): Add hose / Add cable
  / Add drag chain read the part's middle line, diameter, length and the fittings it touches; a chain drawn as **one
  solid** already gets links drawn by the app (width, height in More). The ends sit on the parts they touch, with the
  pipette to re-pick. Not in yet: three-end hoses, hoses pushing on parts, bundles.
- Machinery to reuse: `core/flex.py` (inextensible rod with exact ends, end directions and length; `solve_motion`),
  `core/flex_chain.py` (closed forms for a chain from fixed run, bend, moving end), `core/paths.py` + `blender/paths.py`
  (cable items = contacts in order: SHEAVE / ROLLER / CHUTE / BEND, the tight-string solver, `spool.py` for a drum
  start), `blender/hover.py` (the hover picker: faces, round faces and their axes – `axis_from_hit`), the drawn tube of
  `flex.py` (Geometry Nodes on the hose part – here there is no part: make an app-made object, tagged, in a group
  "Hoses" / "Cables" with a look from 3 Looks).
- **The app's aim (owner 19 Nov):** simple for users who do not know Blender – few clicks, sensible defaults, the
  hover shows what a click will take (a fitting face and its axis, a sheave and its groove).
- 0233 (running or soon) moves the `hoses`, `chains`, `cables` tour sets into a hall; your stops go into a **new set**
  `flex_drawn` (on `test_flex_hoses_a.step` / `test_flex_chains_a.step` / `test_paths_a.step` as fits – one set, a
  fitting environment, e.g. `FACTORY`).

## What to do

1. **Draw hose** (4 Motion > Hoses and drag chains): a click picker – end A on a fitting (a round face: the hose leaves
   along its axis, at its rim / centre; a flat face: along its normal), then **clips** (optional, each a point + direction
   on a part, the hose passes straight through), then end B; Enter / Done. Diameter (default from the fitting's bore,
   else 20 mm), length (default: the shortest that stays within the smallest bend at the CAD pose + a little slack –
   shown, editable), stiffness, sag, smallest bend as today. A hose through clips = one item solved as segments between
   fixed points with matching directions (`core/flex.py`, tested). Each end and clip follows the part it was clicked on.
2. **Draw cable route** (4 Motion > Cables and paths): click the start (a drum / carousel → the spool start of
   `spool.py`, or a point on a part), then each sheave / roller / chute in order (the hover shows the round part and the
   side the cable passes – a second click on the same part flips it), then the end (a point on a part, a hang-off, or
   "free end with a weight"). Diameter, look, speed joint as Add cable. The result is a normal cable item – runs,
   turns its wheels, Build, re-bake, web export work as for a CAD cable.
3. **Draw drag chain**: click the fixed-end bracket (point + the run's direction), the moving-end bracket (on the
   moving part), pick the plane side; width, height, link pitch, bend radius (defaults from the gap between the
   brackets), upper run Straight / Lies on the lower run. The app draws the links (`flex_chain.py`), they roll with the
   axis; "cannot reach" warnings as today.
4. **Replace a CAD part:** on a drawn item, **Replaces CAD part…** (pick the simplified CAD hose / chain): that part is
   hidden in the view and in renders, left out of the clash check and the web export, and shown again when the drawn
   item is removed. Also offered as a first step when the user selects a part named like a hose or chain.
5. **Keep everything:** a model update keeps drawn items on their parts (a part gone → the item says so and keeps its
   last place); save / reopen, undo, Build, the render queue, scripts off, Client view (shows, never edits).
6. Tour set `flex_drawn` with stops for each of the three (and one replace), checks with numbers (length kept, ends on
   their parts within 0.1 mm at three poses, links one pitch apart); 0 clashes. Guide sections with pictures (test models
   only), function-list entries (`flex.draw_hose`, `paths.draw_cable`, `flex.draw_chain`, `flex.replace_cad`, `since=`),
   PC-check lines, tooltips.
7. **Independent tests** by a subagent that did not write the pickers: odd clicks (same face twice, a clip behind end B,
   a fitting on a part that later moves out of reach), undo mid-picking, Esc.

## Done when

- [ ] A hose drawn with two clicks (and with two clips between) follows a joint move and a Build like a CAD hose;
      length kept, ends and clips on their parts (real-app test with clicks where the hover shows them)
- [ ] A cable route drawn over three sheaves from a drum runs, turns them and pays out like a CAD cable on `test_paths_a`
- [ ] A drag chain drawn between two brackets rolls with the axis on `test_flex_chains_a`; a simplified CAD chain
      replaced and hidden in view, render, clash check and web export
- [ ] Model update, save / reopen, undo, queue render keep them; guide, function list, PC-check lines, tour set
      `flex_drawn`, tooltips; precheck, 0 clashes, full suite green; report filled in, merged, released

## Not in this task

Hoses pushing against parts or each other, bundles, three-end hoses (later); the `hoses` / `chains` / `cables` sets (0233);
the cable-lay vessel (private).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
