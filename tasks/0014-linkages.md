# 0014 – Mechanisms: scissor lifts, four-bar arms and other linkages

**Who:** worker · **Model:** Opus · **Status:** waiting (0013, and example models from the owner) ·
**Branch:** `task/0014-linkages`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Motion · **Area:** same as task 0011, plus a new
module for the solver.

## Goal

Mechanisms where several links form closed loops move correctly from one input: a scissor lift
(input: height, angle or cylinder stroke), four-bar and parallelogram arms, slider-cranks, toggle
clamps and other geometries – the owner's machines have "a large variety". One animation step
drives the input; every link follows.

## Background

- Builds on 0011 (stacks), 0012 (couplings) and 0013 (cylinders, incl. the exact triangle for
  "stroke drives arm"); read their reports first.
- Closed loops cannot be done with parent/child chains alone: a solver finds the link angles for
  each input value. Planar mechanisms (all pin axes parallel) cover most cases.
- Renders use baked keys (`animation.bake`), so the solver may run in Python at bake time; while
  posing in the viewport it runs when the input changes.
- **Before starting:** ask the owner to attach two or three STEP files of real mechanisms
  (scissor and others) to look at. They must not be committed (public repository): build generic
  test models with `tools/make_test_*.py` instead.

## What to build (the worker may split this into two tasks; say so in TASKS.md)

1. A planar loop solver: links (subassemblies), pins (picked holes), sliders (picked faces/axes),
   one input (a joint, a stroke or a distance). Exact formulas for the common types (four-bar,
   slider-crank, scissor stage); a general iterative solve (starting from the last solution, so
   the mechanism never flips to the other assembly mode) for the rest. Clear message when a
   position cannot be reached (limit), instead of jumping.
2. "Add mechanism" in 4 Motion with a guided set-up per type (scissor: pick the stages; four-bar:
   pick the four pins; general: pins and links one by one), shown as a step list like the rest
   of the panel.
3. Scissor lift: n stages, input height or cylinder stroke (cylinder from task 0013 drives it).
4. Poses, animation steps, model updates, save/reopen as in the earlier motion tasks.

## Done when

- [ ] Generic test models (scissor with 3 stages, four-bar, slider-crank); tests against
      hand-calculated positions over the whole range; no flip between assembly modes
- [ ] Real-app click test step and screenshots checked; owner's example files tried locally
      (numbers in the report, no files or screenshots committed)
- [ ] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- 3D (non-planar) mechanisms, cable/hose routing, gears with teeth – note in the report if the
  owner's examples need them.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
