# 0234 – Learning sets in the full ocean: marine looks, vessel motion, vessel at work, cable into the sea, cable on a moving part

**Who:** worker · **Status:** running · **Branch:** `task/0234-learning-sets-offshore`
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

- [ ] The five sets in the full ocean with real hull shapes; study 0224's notes for them done; links added
- [ ] 0229's tests and every existing sea / moving / thrusters test green on the new hulls
- [ ] Build time said; precheck, 0 clashes, full suite green; report filled in, merged, released

## Not in this task

The cable-lay vessel's equipment and the demo ship's hull (`demo_model/` except `geom.py`); the crane hub (0230); other sets; app code (a fault found → report).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
