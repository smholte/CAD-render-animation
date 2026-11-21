# 0234 – Learning sets in the full ocean: marine looks, vessel motion, vessel at work, cable into the sea, cable on a moving part

**Who:** worker · **Status:** done (0.2.194) · **Branch:** `task/0234-learning-sets-offshore`
**Started by:** lead, 20 Nov 2026 (study 0224 package B; owner's answers 20 Nov: each set its own fitting environment –
"to a full ocean") · **Model:** Opus · effort Medium
**Area:** `blender/tour.py` – **only** the sets `marine`, `vessel`, `vessel_work`, `sea_cable`, `moving_cable` and their
own helpers / checks; the hull makers `tools/make_test_thrusters.py`, `tools/make_test_sea.py`, `tools/make_test_moving.py`
(+ their `tests/data/*.step` and `fresing_render/data/` copies, their maker tests); `core/functions.py` (`tour=` links);
the guide's tour lines if they name these stops. No app code.

## Goal

The offshore learning sets look offshore: a monopile / TP standing in the real sea, a workboat with a real hull shape
moving on the waves, a vessel at work seen from close by with its wake and thruster jets, the cable going into the sea
from a hull that looks like one – each in the full ocean (sea, sky, seabed and the sea cut-away where the function is
under water).

## Background

- Study 0224 (`tasks/0224-study-tour-sets-up-to-date.md`): `marine` uses none of the sea (primitives on grey, the pile cut
  off top and bottom → the pile standing in the SEA with the sea cut-away, waterline from the sea, the whole pile in
  frame); `vessel` (+ `web3d_env`) a grey deck only → a prop or two on the deck (container, person); `vessel_work` a flat
  blue box seen from 70 m → a hull with a shape (`make_test_thrusters`), camera closer, link `offshore.thrusters`;
  `sea_cable` client-ready with a box hull → link `scene.sea_ground`; `moving_cable` box hull → the hull shape
  (`make_test_moving` / `make_test_sea` share it). The crane hub's `sea` stop is dropped by 0230 (not yours).
- **Never the cable-lay vessel's equipment** (private, CLAUDE.md section 6), and do not reuse the demo ship's hull for
  the test models: they get their own small invented hulls (never `demo_model/` code except the generic shape library
  `geom.py`). The hull is the test models' own: an invented small workboat / barge hull (bow, flat bottom, a
  bilge radius, a simple wheelhouse), made with `demo_model/geom.py`'s shape functions if useful (that library is public
  and shared) – no import of `vessel.py`.
- 0229 runs at the same time and adds tests on `test_sea` / `test_moving` (cases inside tests, no maker change): keep the
  part names, joints, cable routes and sizes those tests and the existing stops read; if a size must change, change the
  numbers the tests expect in the same commit and say so.
- The sea, vessel motion, vessel at work, seabed, cut-away, marine looks exist (0081, 0085, 0109, 0148, 0154, 0196).

## What to do

1. Hull makers: a real hull shape for `test_thrusters`, `test_sea`, `test_moving` (one shared invented hull function in
   `tools/`, sized per model), same part names as today; both `.step` copies; maker tests.
2. Sets: full ocean surroundings (SEA / DECK as fits), sea state and light that read at 400 px, cameras close enough;
   `marine` = pile + TP in the sea with the cut-away showing the pile to its toe and the marine looks at the waterline;
   `vessel` a prop or two on the deck; the `tour=` links above.
3. `changed=` on each set, `tools/tour_versions.py --record`; every stop's Go + check passes; 0 clashes; build time
   before / after (web machine).
4. 400 px pictures per changed stop in `tasks/img/0234/` (test models only).

## Done when

- [x] The five sets in the full ocean with real hull shapes; study 0224's notes for them done; links added
- [x] 0229's tests and every existing sea / moving / thrusters test green on the new hulls
- [x] Build time said; precheck, 0 clashes, full suite green; report filled in, merged, released

## Not in this task

The cable-lay vessel's equipment and the demo ship's hull (`demo_model/` except `geom.py`); the crane hub (0230); other sets; app code (a fault found → report).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort Medium), 21 Nov 2026.

**What changed:**
- `tools/workboat_hull.py` (new): one invented workboat hull for the test models – transom at x 0, a parallel body
  (one section, prism: flat bottom, round bilges, sides leaning out), a bow as a smooth loft of 8 sections that narrows
  and whose forefoot rises towards the stem, optionally a forecastle (higher bow top) and a deckhouse with a window
  band. `Hull.half_at(x, z)` = its half breadth (sizes the bow tunnel lining). No `demo_model/` code but `geom.py`.
- `test_thrusters`: that hull (stem moved 36 → 40 m, the parallel body to 33.5 m so the bow tunnel cuts flat sides – a
  tunnel through the curved bow cost +280 KB; forecastle +1.2 m), the wheelhouse as a deckhouse with windows, the
  tunnel lining sized from the hull. Thruster places (`core/vessel_work.TEST`) unchanged; `TEST["hull_length"]` /
  `["bow_start"]` are no longer read by the maker (app code, left as is).
- `test_sea` / `test_moving` (`make_test_sea.deck_shape`): the box hull became the hull above – working deck, bulwarks,
  rub rail, seams as before, and a 7 m bow with a forecastle and a deckhouse forward of it. Bottom still z -2000 (the
  water level is measured from it), every part name, joint, cable route and place kept.
- **The bow is read from the hull now.** The app's "Bow: from the hull" (`surroundings.stern_side`) needs the waterline
  within 3 m of the bow < 1/1.15 of the stern's: the bows are fine at the waterline (forefoot meets the water at the
  stem; 0.76–0.78 of the stern width; test `test_the_app_finds_the_bow_at_plus_x`). Sea / moving: before, the box hull
  was read as "bow at -x" (wake at the wrong end); now +x.
- Sets: **marine** – a monopile Ø5 m (growth) + transition piece (streaks) + platform + boat landing + concrete scour
  mattress made as model parts (`offshore_structure`; the test crane's parts excluded), 12 m water, 9 m in the seabed,
  sea cut-away from the pile towards the camera with the ground open; check: looks, waterline = the sea's, cut + ground
  on, toe and platform inside the picture. `marine_demo` / `marine_camera` kept for the PC check's `looks.marine`.
  **vessel** – a person and an IBC tank behind the crane (a 20 ft container dwarfed the 2 m test crane), camera fitted
  to crane + props, check: they ride on the vessel. **vessel_work** – camera off the port bow at ~45 m.
  **sea_cable** – lens 22 (the hull shows). **moving_cable** – new hull only. Stop texts and `changed="0.2.194"`;
  `tour_versions.py --record`.
- Links: `offshore.thrusters` → vessel_work, `scene.sea_ground` → marine (the stop that opens the ground; sea_cable
  keeps the seabed closed, so the brief's sea_cable link would not show it), `scene.props` → vessel too.
- Tests: `tests/test_workboat_hull.py` (new, 11), `tests/test_make_test_thrusters.py` (new, 2);
  `test_make_test_sea/moving` size limit 400 → 500 KB (the hull ~85 KB; files 396 / 454 KB, thrusters 295 KB);
  `test_vessel_work.py` numbers for the longer waterline: half length 18 → 20 m, azimuth u -16 → -18, bow thruster
  14 → 12 (as the brief allows).

**Tested and measured** (4-core web machine): the 29 test files that use the three models (incl. 0229's stand-ins):
488 passed. `test_tour.py` + `test_functions.py`: 129 passed. `test_tour_clash.py` for the five sets: 0 clashes. Maker
and hull tests 21 passed. Precheck passed. Build times before → after (s): marine 16.0* → 3.8, vessel 4.7 → 5.2,
vessel_work 7.5 → 8.2, sea_cable 4.6 → 5.7, moving_cable 8.8 → 8.7 (*first set of the run, includes start-up).
Pictures (400 px, Cycles 12 samples, after and `_before`): `tasks/img/0234/`. Runs: see below.

**Open points / follow-up tasks:**
- The PC check's `looks.marine` still uses the plain shapes (`marine_demo`); it could use `offshore_structure`.
- `core/vessel_work.TEST` keeps `hull_length` 36000 / `bow_start` 30000, no longer the model's (app code; harmless).
- The private demo kit is not touched (no function or stage it uses changed).
