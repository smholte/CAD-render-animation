# 0202 – Sea: measure the 3D view's cut-away cleanly (switch to the cheaper way if it costs ≥ 1 ms), and a sea / weather change in ~1–2 s instead of ~6 s

**Who:** worker · **Status:** open – can start · **Branch:** `task/0202-sea-change-faster`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
