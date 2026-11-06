# 0014 – Mechanisms: scissor lifts, four-bar arms and other linkages

**Who:** worker · **Model:** Opus · effort High · **Status:** running ·
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

**Chat / date:** worker, Claude Code on the web, 6 Nov 2026. Not split into two tasks.

**What changed:**
- `core/linkages.py` (no Blender): links, `Pin`, `Slot` (a roller in a track / pin in a slotted hole: the link may
  turn), `Slide` (slider block, never turns); one input (a pin or slide on the base). `plan()` splits the mechanism
  into exact steps – two pins (straight away), pin + track (circle meets line), pin + slotted link, slide + lines,
  and two links joined by a pin each tied to placed links (triangle: two circles meet = four-bar coupler/rocker,
  scissor stage; circle meets line = slider-crank) – and solves what is left (class III groups) with damped Newton
  from the last solution. `Solver.solve(v)` walks in steps of 1° (1 % of the size for a slide); two-answer steps
  keep their branch by prediction from the last two steps (scaled to the step), else the same side as before (CAD
  side at first): no flips, a parallelogram passes the line of its four pins. Unreachable positions raise with a
  reason and keep the last good one. `limits()` (scan + bisection), `value_for(measure, target)` for the platform
  height and a cylinder's pin distance. `find_pins` (shared round-face axes), `rigid_groups`/`merge` (links sharing
  2+ pins are one body: twin side plates), `scissor()` layout (stages, rollers on base/platform, height measure).
- `blender/linkages.py`: mechanism frame empty on the base (Z = pins' direction), one `mech_link` empty per link it
  moves; the input link stays on a normal joint ("<name> drive", or an existing joint that moves exactly that link).
  Pins found from `fr_axes` of the links' and base's parts; the plane = the round-face direction that gives the
  most pins. Depsgraph handler places the links when the drive joint changes (skipped while built keys rule);
  beyond reach the joint is put back with the reason (`status`). Drive-joint limits from the reach; a scissor stops
  at 2 % of its highest height (flat arms are a dead position) and goes up with a positive angle. Height get/set,
  `Drive` for cylinders (pin distance <-> input joint), specs for model updates (pins found again), remove, rename,
  show/hide markers; `cad_enter/leave` hooked into `joints.cad_pose`; `joint_conflict` in `joints.check_members`.
- Panel 4 Motion > **Mechanisms** (Type, Base, Add mechanism, list, Height + Lowest/CAD/Highest, Drive angle, red
  reason, Set-up fold); joint details say "Drives mechanism '…'"; the drive joint's axis/flip/type/remove/members
  are refused while a mechanism uses it. 6 Animation: step **Lift height**; `bake` keys every link on every frame
  its drive joint (or the top of its coupling chain) moves – keys only, no drivers. Cylinders whose pins sit on a
  mechanism's links drive its input (Drives the arm, Move cylinder). Poses / reset refresh mechanisms.
- Fix: `joints.check_members` had two checks after a `return` since 0.2.25 (whole model / carries its own base):
  back, with a test.
- `tools/make_test_linkage.py` (scissor 3 stages + lifting cylinder, four-bar, offset slider-crank; rev. B),
  `tools/ui_test_linkage.py` (24 checks, in `ci_real_app.py`), PC check line `joints.mechanism`
  (`MIN_LINES_FULL` 32, model copied to `fresing_render/data/`), guide chapters 4 and 6, README-install, CHANGELOG,
  CLAUDE.md (layout, real-app list, 3 lessons). 0.2.26.

**Tested and measured** (4-core Claude Code cloud machine, Linux; generic test models only):
- `tests/test_linkages_core.py` (15): four-bar vs Freudenstein's closed form over ±2 turns and a 10-turn jump;
  rocker as input stops where crank and coupler are in line (law of cosines, 1e-6 rad); offset slider-crank vs
  x = r cos t + sqrt(l² − (r sin t − e)²) to 1e-12; 3-stage scissor h = 3 L sin φ, roller x = L cos φ, level
  platform; height input (asin); parallelogram through the in-line position both ways; triad by Newton (residual
  < 1e-10, same branch walked or jumped); cylinder length by law of cosines; state round trip; set-up errors
  (not enough pins, not connected, locked); pins/rigid groups; scissor layout; two walk regressions (below).
- `tests/test_linkages.py` (17, Blender as a module, real import): scissor at 6 angles (platform pin, roller, level,
  height field) to 0.02 mm; limits; Lowest/Highest; long walk; default base with the cylinder in it gives the
  "Base" hint; four-bar vs Freudenstein over 2 turns; slider-crank formula; joints on links refused, drive joint
  locked; pose + CAD pose; bake keys every link with no drivers, frames vs hand values, clear keys; Lift height
  step linear in height + "cannot reach" warning; save + reopen; model update A → B (both mechanisms, drive joint
  kept, value kept, new lamp rides on the platform); remove; cylinder follows and drives the scissor (law of
  cosines in the triangle fixed pin – G – rod pin, 1e-5 rad); Move cylinder through the scissor; panel text.
- Found while testing and fixed (core regressions in the test file): a walk down to 2° and back up folded a stage
  (one step of history took the nearest answer); a half step in a bisection jumped to the folded answer (prediction
  not scaled to the step).
- Neighbouring suites (cylinders, stacked joints, couplings, phase 2, panels, cylinder core): 147 passed.
  Tooltip check: 379 found, 0 missing, 0 weak. PC check line on its own: OK (1.4 s).
- Speed: set-up 26 ms; scissor 0.78 → 1.5 m (height field) 3 ms; one drag step < 1 ms; baking a 10 s Lift height
  step (251 frames, scissor + four-bar in the scene) 314 ms; playback 0.09 ms per frame.
- Real app: blocked here (download.blender.org 403); `ui_test_linkage.py` runs on GitHub (see below).

**Open points / follow-up tasks:**
- The owner's example STEP files were not attached in this session: not tried. When he sends 2–3 (scissor and
  others), a short follow-up: try them, adjust pin finding (tolerance, base parts) if needed. Numbers only.
- Guide picture of the Mechanisms panel: not made (no real Blender in this session); `ui_test_linkage.py` saves
  `panel4_mechanisms.png` in the GitHub run's files (the owner can download it), or the next session with the 0031
  set-up runs `tools/guide_screens.py`.
- Tracks are infinite lines: a roller's real slot length is not a limit (the drive joint's limits are).
- Not in this task (as the brief says): 3D mechanisms, cables/hoses, gears with teeth.
