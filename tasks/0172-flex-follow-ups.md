# 0172 – Flex follow-ups from 0125: shot 11's bend past the gutter, lifted sheaves stand still, the D's depth right before Build, a swivel to test

**Who:** worker · **Status:** done (0.2.138) · **Branch:** `claude/confident-archimedes-takeq0`
**Started by:** lead chat, 16 Nov 2026 (open points 3–6 of task 0125) · **Model:** Opus · effort High · **Place:** Claude
Code on the web, environment "CAD-render-animation". Subagents allowed (CLAUDE.md section 2).
**Area:** Flex parts lane: `core/paths.py`, `core/catenary.py`, `blender/paths*.py` (`paths_sea.py`, `paths_rollers.py`,
`paths_swivel.py`), `ui_paths.py` (only the cables panel), their tests; the demo's sea/quadrant stages in
`blender/demo.py` (`set_down_depth` and the check after Build, shot 11); Test models lane additively: one new test
model maker + its `tests/data/` and `fresing_render/data/` copies, one new tour set; the tour, the PC check, the
function list and the guide sections `#swivel` / the quadrant chapter.
**Do not edit:** the Machining lane (0167 runs: `core/heightmap.py`, `core/machining.py`, milling tests), the CI files
of 0170/0171 (`tools/ci_precheck.py`, `tools/ci_times.json`, `.github/`, the Windows script); only the MIN counts in
`tools/ci_check_pccheck.py` and `MIN_CHECKS` / the lightest group in `tools/ci_real_app.py` (additive). Leave 0152's
demo realism (cable weight in water, lay-data box, ROV) to the next Demo task (0173): it comes after this one.

## Goal

The cable-lay demo's quadrant shots look right to the end: in shot 11 the cable no longer wraps round the gutter's end
in a big free bend, sheaves the cable has left stand still, the D is set down at the right depth with one Build (Make
demo faster), and the swivel head (0.2.103) gets a test model, a tour stop and a PC-check line like every other function.

## Background

Read the report of `tasks/0125-quadrant-sea-follow-ups.md` (Design table, "What changed", open points 3–6). Numbers there
are from the 4-core web machine.

1. **Shot 11 (open point 6).** While the D, tipped flat, comes down its last ~10 m (frames ~2514–2560), the cable has
   to go round past the gutter's end and back down. Since 0125 it does so in a free bend of the gutter's radius of up
   to ~180° (before: a hard kink back). The right behaviour: the hang-off comes off the gutter's **other end** once the
   cable's way down lies beyond it, or the cable lies off the D – decided by the geometry in the solver, not by a
   demo-only rule (a real cable does not wrap round the end of a chute it is not held in).
2. **Lifted sheaves (open point 5).** 0125's `paths_rollers.after_bake` stops ROLLERS the cable has left; a lifted
   SHEAVE that the cable runs past still turns with its coupling (subagent R's note).
3. **The D's depth before Build (open point 4).** The depth `set_down_depth` works out before Build differs from the
   built animation by 0.38 m; the check after Build corrects it with a **second Build: +55 s on Make demo**. Cause not
   found. Since then 0138 (Build starts from frame 1), 0159 (one-moment catenary on plain numbers) and 0160 (re-bake
   reads as Build reads, `catenary.hang_off_steady`, no warm start from the last Build) changed what Build reads – the
   gap may have moved or gone: measure first.
4. **Swivel (open point 3).** `FRCableContact.swivel` (0125, `blender/paths_swivel.py`) has no tour stop and no
   PC-check line: no test model has a swivel head. Its function-list entry `offshore.swivel` names neither.

## What to do

1. **Shot 11:** the cable leaves the gutter at the end where its way down lies; no bend outside the gutter of more than
   the gutter's own arc per point; no frame without a path; no step where the hang-off changes end (measure the
   cable's points over frames 2500–2600 before/after: largest direction change per point and between frames). Check
   shots 9–10 and 12 stay as 0125 left them (0125's numbers: kink at the leave point, D 16 mm over the seabed, pull
   head 3 cm over it).
2. **Lifted sheaves:** a sheave the cable has left (lifted, or no drawn cable touches it at a frame) stands still at
   Build, as rollers do; its own coupling put aside and restored by `after_clear`. Test on a small test model and on
   the demo (name the sheaves that now stand still).
3. **The D's depth:** find why the estimate before Build missed (or show it no longer does), fix it so one Build gives
   the D within `SET_DOWN_TOL` of the seabed, and drop the second Build. Make demo time before/after (same machine).
   Keep the check after Build as a test (it must not fire).
4. **Swivel test model + stop + line:** a small invented test model with a sheave on a swivel head and a wire that
   changes direction (e.g. a davit that slews while the wire runs to a fixed point): maker in `tools/make_test_*.py`,
   copies in `tests/data/` and `fresing_render/data/`, a tour set with a stop "The sheave turns to follow its wire"
   (what you should see, a number `check`, 0 clashes in `test_tour_clash.py`), a PC-check Full line, the function-list
   entry names both; raise the MIN counts (CLAUDE.md section 6).

## Rules

- New behaviour gets a test; a test that fails before the fix for 1, 2 and 3. Nothing loosened; the demo's tests and
  every tour set stay 0 clashes.
- Speed: Build on the demo (`tools/measure_cables.py`) and Make demo before/after, machine named. Build must not get
  slower by more than a few %.
- An **independent tester** (a subagent that did not write the change) tries to break 1–3: a gutter tipped at other
  angles, a D lowered on the other side, a sheave lifted and touched again, a swivel turning past ±180°.
- Guide: the quadrant chapter (shot 11) and `#swivel` get the new behaviour and the tour stop; tooltips if a setting
  changes. CHANGELOG + version last (section 7). Old projects open looking the same (test with a 0.2.103-style
  project if the stored data changes).

## Done when

- [ ] 1–4 done, before/after numbers in the report (bend per point in shot 11, sheaves standing still, D's depth
      after one Build, Make demo time)
- [ ] Swivel test model, tour stop, PC-check line, function-list entry; MIN counts raised
- [ ] Tests added/updated; GitHub run green; merged; version; report filled in

## Not in this task

0152's demo realism (cable weight in water ~38 kg/m at Ø 200, lay-data box + ROV in shot 8, handler tilt caption) →
0173 after this task. Older Flex open points: a cable with a spline/helix stretch (refused), the fleet angle's kink at
a sheave (0078), cables and hoses swaying in wind, tracks' playback cost (0159), the re-bake's 16 s final solve (0160).

## Design (worker, 16 Nov 2026)

Measured first on the small demo (4-core web machine, Blender as a module, made from `main` at 0.2.133):
Make demo 352 s (Build 150 s = two Builds); shot 11's second end: worst turn per point between its start and the
seabed 61.8°, a point jumping 5.2 m between frames, the leave point going from the gutter's far end (180°) to its
middle (90°); the D's depth before Build 21 mm off the built one (no longer 0.38 m), so the second Build still ran.

| Piece | Files | Owner |
| --- | --- | --- |
| 1 Shot 11: the wrap of a wheel lying flat is read from the lay direction (`catenary._way`, blended in below `FLAT` of "down" in the wheel's plane); a free bend that would reach into the seabed turns as far as fits (`_bend_fit`), its plane near the seabed taken from the catenary at the wheel (`BED_BAND`), half steps where the iteration went back and forth | `core/catenary.py`, `tests/test_catenary.py`, `tests/test_demo_project_quadrant.py` | worker |
| 2 Sheaves the cable has left stand still: `paths_rollers` takes `SHEAVE` contacts too (`KINDS`), placed by their own slot | `blender/paths_rollers.py`, `tests/test_paths_rollers.py` | worker |
| 3 The D's depth: the estimate and the check use one window (the set-down step, standing, 1 s of the hoist, `SET_DOWN_AFTER`) and the estimate models the hoist (`set_down_shares`); every mesh point near the lowest; no second Build | `blender/demo.py`, `tests/test_demo_project_quadrant.py` | worker |
| 4a Swivel test model maker: `tools/make_test_swivel.py` → `tests/data/test_swivel.step` + copy in `fresing_render/data/`; `paths_swivel.set_up_test_model(scene) -> dict` (joints, cable, swivel, animation "Davit slews"); `tests/test_swivel_model.py` | those files only | subagent M (worktree) |
| 4b Tour set + stop, PC-check line, function entry, guide, MIN counts | `tour.py`, `pccheck/checks.py`, `core/functions.py`, `docs/USER-GUIDE.md`, `tools/ci_check_pccheck.py`, `tools/ci_real_app.py` | worker |
| Independent tester of 1–3 (gutter tipped at other angles, a D lowered on the other side, a sheave lifted and touched again) | `tests/test_flex_followups_independent.py` | subagent T (worktree) |

---

## Report (filled in by the chat that did the task)


**Chat / date:** Claude Code on the web, 16–17 Nov 2026 (branch `claude/confident-archimedes-takeq0`), version **0.2.138**.

**What changed:**
- **1 Shot 11** (`core/catenary.hang_off`): for a wheel lying (nearly) flat – its plane holds less than `FLAT` (0.2) of
  "down" – the wrap is read from the lay direction (the way the cable lies on the seabed, blended in as the wheel lies
  flatter; `_way`); a piled (slack) cable reads its wrap from straight down, not from its sideways pull to the lay
  line. A free bend that would reach into the seabed turns as far as fits above it (`_bend_fit`) instead of being left
  out; within `BED_BAND` (2 m) of the seabed its plane comes from the catenary at the wheel; half steps where the
  bend's fixed point went back and forth; the loop only works on moments not yet settled. In the demo the cable stays
  in the D's gutter to its far end (180°, the end pointing the way it lies) and bends down onto the seabed. Shot 12:
  it now leaves the let-go gutter at the same end (180°, was 90°) – no jump at the let-go.
- **2 Sheaves** (`blender/paths_rollers.py`): `SHEAVE` contacts too (`KINDS`); a wheel is placed by its own slot (its
  joint's arrow). A sheave the cable is lifted off, runs past or no longer reaches stands still at those frames (keys
  per frame, coupling put aside, back at Clear keys).
- **3 The D's depth** (`blender/demo.py`): **cause found** – before the first Build the scene still runs at Blender's
  24 fps, and `_vessel_at` read the vessel's heave at `scene.render.fps` while the animation runs at 25 fps (heave
  30 mm different at those frames: the D 20 mm off). It now uses the animation's frame rate. The estimate and the
  demo test's check cover the same window (set-down step, standing, 1 s of the hoist, `SET_DOWN_AFTER`), the estimate
  models the hoist (`set_down_shares`, with the steps' frames as Build works them out from their 32-bit start and
  length) and uses every mesh point near the lowest. The second Build is gone; the check after Build is now the demo
  test's (`test_the_quadrant_operation_shots_10_to_12`, within `SET_DOWN_TOL`: it did not fire).
- **4 Swivel:** test model `tools/make_test_swivel.py` → `test_swivel.step` (a deck davit slews ±45°, its wire from a
  fixed fairlead over a sheave on a swivel head and down the swivel's axis into a hook block; Winch keeps it tight),
  `paths_swivel.set_up_test_model`, tour set + stop "Sheave turns to follow its wire", PC-check line `motion.swivel`,
  `offshore.swivel` names both; MIN counts Full 92, Tour 71, `MIN_CHECKS["tour"]` 71. Guide: the quadrant chapter
  (shot 11), "A chute or quadrant lying flat", "Rollers and sheaves the cable has left stand still", the swivel's stop.

**Subagents:** M (swivel model maker, set-up, `tests/test_swivel_model.py`: 8 tests, worst in-plane angle 8.6e-6°,
0 clash rows; merged as is). T (independent tester of 1–3, `tests/test_flex_followups_independent.py`, 20 tests):
found 5 faults – the worker fixed 3 (the bend's end jumping near the seabed: `BED_BAND` 0.5 → 2 m; the same set-up
turned about the vertical gave another answer: a piled cable's wrap from straight down; `set_down_shares` a frame off
for a step starting between frames) and kept 2 as tests that hold today's size (`KNOWN_FAULT`, open points 1–2;
strict xfails count as skipped tests on GitHub, where a group allows one). Sheaves held in every case T tried.

**Tested and measured** (4-core web machine, Blender as a module, the small demo):
- Shot 11 (frames 3341–3590 now: 0153/0166 lengthened the animation since the brief's 2500–2600), from the cable's
  start to where it reaches the seabed: worst turn per point **61.8° → 1.38°** (the gutter's own arc ~1.4°), largest
  move of a point between frames **5.16 m → 0.13 m** (the D comes down ~0.12 m a frame), leave point **89.9…180° →
  177…180°** (no change of end), free bend max 94.8° → 89.9°, frames without a path 0. Shot 10 as before (7.5° at the
  pile's touch-down, 0.37 m), shot 12 1.4° and 0.02 m; 0125's numbers (D on the seabed, pull head) – demo tests pass.
- Sheaves standing still: paths test model with SHEAVE 2 slid away – still while lifted off, turning with the rope
  before and after. **Demo: none** (its tipping sheaves stay touched, the handling winch's fairlead sheave follows
  Cable travel, the A&R top pulley is keyed) – the same was true for its rollers before.
- The D's depth: estimate before Build 37.950 m vs built 37.970 m → now **37.970 m before Build**; built check within
  `SET_DOWN_TOL` (the 0125 note's 0.38 m had already shrunk to 21 mm on `main`).
- **Make demo 352 s → 284–302 s** (one Build 80–87 s instead of two, 150 s). Build with the new code 81 s
  (`tools/measure_cables.py`); the second end's solve 11.1 s → 10.3 s – not slower.
- Tests: cable/sea/moving/settle/kept files 171 passed; `test_catenary.py` +2 and `test_paths_rollers.py` +1 (fail
  before the change), the demo's shot-11 test (fails before); demo files 36 passed; tour 72 + the swivel set's clash
  test; PC-check line `motion.swivel` OK.

**Open points / follow-up tasks:**
1. A gutter tipping through ~6° towards flat with a slack cable can still move its leave point in one step (T's test,
   now `test_KNOWN_FAULT_…` holding today's size: tipped about x 51° / 4.45 m at 6.3°; tipped about y – its downhill
   side away from the lay direction – from the near end to the far end, 7.2 m at 5.8°; before this task 4.95 m at
   8.5°). A slack cable on a gutter that tips through flat has two places to lie; it needs a rule over time (keep the
   end it was at until the other is clearly better), not per moment. Not seen in the demo.
2. Where a free bend is cut at the seabed the cable comes off it onto the seabed with a corner (T's
   `test_KNOWN_FAULT_…`, held at today's 49° for a normal cable; 66° in the demo just before set-down), like a piled cable's touch-down. A reverse bend
   back to the seabed would need the piled hang rounded too to stay continuous (Flex lane).
3. Two cables over one sheave were not tried (no small model has one).
4. `set_down_depth` returns `guess + 20 m` without the joint's limits when nothing reaches the seabed (T, by reading).

**GitHub runs:** 5 full runs on the branch – 1st stopped in the precheck (0.2.135 taken by 0176), 2nd red (a pytest
group allows one skipped test: the tester's two strict xfails counted as skipped → kept as `KNOWN_FAULT` tests), 3rd
green (run 43994355860) but 0.2.137 was taken meanwhile (0178), 4th green (43997157208) but `main` moved by code
(0177), 5th green (run 44000431848, 24.5 min); `main` fast-forwarded to it (reuse). Leftover branches to delete on
github.com: `claude/confident-archimedes-takeq0` once read.
