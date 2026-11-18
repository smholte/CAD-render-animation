# 0202 – Sea: measure the 3D view's cut-away cleanly (switch to the cheaper way if it costs ≥ 1 ms), and a sea / weather change in ~1–2 s instead of ~6 s

**Who:** worker · **Status:** done (0.2.157) · **Branch:** `claude/optimistic-clarke-j0pndr` (the web session's branch)
**Started by:** lead chat, 18 Nov 2026 (study 0195 proposal A4 + the two 0196 sessions) · **Lane:** Sea
**Area:** `blender/surroundings.py` – the sea's water material (`_water_material` and the node groups it makes), the view
cut of 0196 (`_view_cut_group`, `_set_view_cut`); if point 1 says so, a new `blender/sea_view_cut.py` taken from branch
`task/0196-sea-cutaway-in-view`; their tests (`tests/test_sea*.py`, `tests/test_surroundings.py`). Not the re-bake of
cables and hoses (`rebake.py`, 0192), not `world.py`'s light looks beyond calling the sea.
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner changes the sea state or the weather on the demo and the sea is ready in about a second, not six; and the sea
cut-away that 0.2.153 opened in the 3D view costs well under 1 ms a frame – proven by a clean measurement.

## Background

- **Task 0196 ran twice by mistake (18 Nov).** Released (0.2.153, on `main`): a Geometry Nodes group "FR view cut" that
  **deletes the faces** inside the box, last modifier, `show_render` off, on the sea, hull foam, seabed + stones. Its
  report measured the sea's evaluation 16.0 ms *with* vs 18.4 ms *without* – noise, not a measurement.
  Not merged (branch `task/0196-sea-cutaway-in-view`, green run, 8 tests in `tests/test_sea_view_cut.py`, report and
  Solid-view pictures in its `tasks/0196-*.md` + `tasks/img/0196_*`): a "FR view cut" that **lets the points inside the
  box down** (depth + 4 m for the sea, 0.3 m for the seabed) on Detailed and cuts a thin slab with a Mesh Boolean on
  Simple; it measured 0–0.5 ms a frame and found that deleting faces cost **+3.5 ms** a frame on the Detailed sea
  (Boolean on Detailed: 400 ms per update – dropped). Its weak points: stones and hull foam not cut in the view, spikes
  along the edge where the sea's radial mesh is stretched.
- **Study 0195, A4** (`tasks/0195-demo-smooth-study.md`, sections on the sea): a sea-state change Calm ↔ Rough takes
  5.8–6.4 s for the sea itself, 4.4 s of it in `surroundings._water_material` making **724 shader nodes** again (3.4 s
  in `math` nodes); a light look 0.4–0.6 s. Proposal: keep the water material and its node groups and change only their
  numbers. The cables' re-bake after a sea change is 0192's and stays as it is.
- `tools/measure_demo.py` (0195) measures the demo per frame and per action on the web machine.

## What to do

1. **Measure the view cut first** on the made demo (Detailed sea, moving waves, ground cut on), the same way for both
   versions: per frame with the modifier on vs off, at least 30 frames × 5 repeats, the sea's evaluation alone and the
   whole frame (median and spread). Say plainly what is noise.
   - **Below 1 ms a frame:** keep 0.2.153's version; add a test that times it (generous bound) so it cannot grow.
   - **1 ms or more:** replace it with the let-down approach from `task/0196-sea-cutaway-in-view` (take its file and
     tests from that branch – never merge the whole branch: it also carries its own version 0.2.153, CHANGELOG and
     TASKS.md lines). Keep what 0.2.153 does better: hull foam and stones cut in the view too, and no spikes on the edge
     (smooth them, e.g. points let down only where the whole face lies inside, or a finer ring near the box). Renders
     unchanged to the last digit (its Cycles test).
2. **Sea / weather change without remaking the material (A4):** the water material and its node groups are made once
   and kept; a change of sea state, weather, water clarity or time of day sets their numbers (inputs, ramp points,
   group inputs). Make the node groups shared where several objects use the same one. Measure before / after on the
   demo (sea state Calm → Rough → Calm, a weather change, a clarity change): target ≤ 1.5 s for the sea itself.
3. **Same picture:** a Cycles render of the demo's shot 8 (small, few samples, fixed seed) and a sea shot before / after
   for each change kind: equal (or a stated tolerance with the reason); old projects (0.2.125, 0.2.141, 0.2.152 demo)
   open and change sea state with the same result as a new build.
4. The usual parts if something visible changes (it should not): guide line on the speed only if it says a number.

## Done when

- [ ] View-cut measurement in the report (both versions if point 1 needed it), the decision and its test.
- [ ] Sea state / weather / clarity change on the demo measured before and after (≤ 1.5 s for the sea, or why not).
- [ ] Renders equal before / after (test), old projects change sea state as before.
- [ ] `test_sea*.py`, `test_surroundings.py`, the demo's sea checks pass; GitHub green incl. Windows; merged, next free
      version, released; report filled in; `TASKS.md` (and say if `task/0196-sea-cutaway-in-view` can now be deleted).

## Not in this task

The cables' re-bake after a sea change (0192 / Flex lane); hull foam made lighter (0195 D3 – waits for the owner's
`measure_demo.py` numbers); the web page's sea; new sea looks.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (branch `claude/optimistic-clarke-j0pndr`), 18 Nov 2026. No subagents.

**What changed:**
- **View cut (point 1 → replaced).** New `blender/sea_view_cut.py` (group "FR view cut 3", modifier still "FR view cut",
  viewport only, last). Three ways: **stored** for the sea and hull foam (the offset worked out once in NumPy, kept as
  point attribute `fr_view_cut`, the modifier adds it: one sum per point; points inside go down under the seabed / the
  pit, points within about one face of the box's outline go onto it → straight edge, straight wall, no spikes);
  **live** for the seabed and stones (they slide aft with the lay: the box brought into their coordinates once, the
  points inside let down); **exact** (slab + Boolean) for the Simple sea and seabed. Hull foam and stones are cut too.
  0.2.153 projects get it on load (`surroundings.refresh_view_cuts`, a step in `handlers._on_load`). 0.2.153's
  `_view_cut_group` / `_set_view_cut` are gone. Taken from branch `task/0196-sea-cutaway-in-view`: the idea and the
  exact branch; its file was rewritten (its per-frame field cost +2.3 ms here, a face-neighbour version +8.7 ms).
- **Sea change (A4).** `surroundings._build_tree` + `_Replay`: a tree is built again through the same code, but the
  n-th `nodes.new` hands out the n-th node of the last build (order kept in `fr_order`), numbers are written only when
  they differ (float32), links compared at the end; any difference → made new as before. Used for the water material
  (an unused water material with the same kind of nodes, `fr_sig`, is renamed and given the new numbers), the Detailed
  waves group (a spare with the same `fr_sig`) and the hull foam group (one per kind of nodes, kept). Each wave now has
  its own fade ramp (before: shared per wavelength band, so Calm and Rough had different nodes; same values).
  Also: the model's box and the hull's waterline measured in one still moment (two scene updates fewer); the sea, hull
  foam and seabed-patch meshes built from NumPy blocks (`_Mesh._add` with an array).
- Found on GitHub: 0199's What's-new checks (PC check line `app.start_here`, tour stop `start_here`) failed for any
  release that brings no new function (0.2.157 brings none): they now look back to the first version then
  (`tests/test_start.py::test_a_release_without_new_functions_passes_the_checks`, fails without the fix). The precheck
  then asked for the tour set Crane (owner of that stop) to be marked `changed="0.2.157"`.
- Guide: the cut-away paragraph (let down, straight wall). CHANGELOG 0.2.157 (0.2.156 was taken by 0201 meanwhile).

**Tested and measured** (4-core web machine; demo = `tests/demo_made.py`'s scaled-down demo, made by 0.2.153's code):
- View cut, demo, Detailed sea + moving waves + ground cut, only the four cut objects re-evaluated, 30 frames × 5,
  on/off interleaved: **0.2.153 +6.4 ms a frame** median (p10 +0.8, p90 +12.3; a first run +6.2); **new +0.35 ms**
  (p10 −4.6, p90 +6.2 = noise). The whole frame varied ±8 ms between runs – noise, not used. Clean numbers on the test
  vessel (best of 10–12 runs): sea + hull foam (every frame) **main +3.3…+4.0 ms → new −0.1…+0.26 ms**; seabed + stones
  (only while the seabed slides with the lay) main +2.3…+2.9 → new +0.6…+0.9 ms. Test `test_cost_of_the_view_cut`
  (bound 1.5 ms over the four objects; 0.3–1.1 ms here).
- Sea change on the demo (world.apply + the scene's update; the cameras' / cables' re-bake stubbed – 0192's): a sea state
  not yet seen in the session **main 6.8–7.4 s → new 2.0–2.5 s** (Simple and Detailed); back to one seen in the session
  main 1.9–2.8 s (its material was still in memory) → 2.0–2.5 s; clarity 1.7–3.0 → 1.5–2.1 s. First change after
  opening a project from before 5.6–8.5 s (its material has no recording: made once).
  **Why not ≤ 1.5 s** (profile of a new-state change, Simple): the material's ~600 changed numbers 0.5–0.7 s (Blender
  re-checks the whole 713-node tree after every single write: 1.5 ms each there vs 0.03 ms on a small tree; Python has
  no way to batch them); vessel motion's rig follows the new waves + its scene update 0.5–0.6 s; the model measured on a
  still sea (two scene updates) 0.4 s; the scene's evaluation 0.4 s; meshes and the rest ~0.3 s. Getting under 1.5 s
  needs a change-in-place path that skips the rebuild (not the whole sea made again): a follow-up if wanted.
- Same pictures: demo, Cycles 160×90, 4 samples, seed 0, shot 8's camera "Into the sea" and "Over the stern", after:
  start, Rough, Calm, clarity change, Wind 4, Wind 5 – **all 12 pictures equal to the last digit, main vs new**. Old
  projects made by 0.2.125 and 0.2.141 (invented vessel, Detailed, cut-away + ground): opened and changed Calm → Rough →
  Calm, main vs new **equal to the last digit**; the 0.2.153 demo as above.
- New tests: `tests/test_sea_view_cut.py` (10: nothing seen in the box Simple/Detailed incl. hull foam + stones,
  straight edge/wall, outside unchanged, follows the panel, ground off, off without the cut-away, cost, Cycles render
  with = without Simple/Detailed, a 0.2.153 project upgraded), `tests/test_sea_change.py` (5: kept nodes = fresh build
  node for node Simple/Detailed, Beaufort 3 → 9 made new, kept nodes render like a fresh build, meshes from arrays);
  `test_sea_cutaway.py`'s 0196 test adapted. Locally: all sea / surroundings tests (164) and the neighbours (vessel
  motion / work, weather look, marine looks, web 3D sea, sea cables, re-bake, view clip: 205) pass.

- GitHub runs: 4 on the branch – a version clash (0201 took 0.2.156), the What's-new checks above (PC check Linux +
  Windows, tour-b), the tour-set mark the precheck asked for, then green.

**Open points / follow-up tasks:**
- ≤ 1.5 s for a sea change needs a change-in-place path (see above). A project from before 0.2.157 pays the old time
  once (its first change).
- A Wind sea crossing about Beaufort 7 (white caps get a meander) or a calm sea that leaves out its shortest waves gets
  other nodes: made new then (once per kind of nodes and session).
- Detailed + ground cut: the plain seabed square 6 cm under the rippled patch is one 2 km face with no point in the
  box, so in the view it still covers the pit (0.2.153 the same). Renders are fine. Fix: split that square (it slides
  with the lay, so its corners would have to follow the box).
- The spray group (weather, Beaufort ≥ 5.5) is still made new at each sea change.
- Material Preview not looked at in the real app (no graphics card); the cut is in the mesh, so it shows there as in
  Solid.
- Branch `task/0196-sea-cutaway-in-view` can now be deleted (its idea and tests are in; its own version/CHANGELOG lines
  never went to `main`).
