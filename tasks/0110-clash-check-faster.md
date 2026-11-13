# 0110 – Clash check faster on big moving machines

**Who:** worker · **Status:** done (0.2.90) · **Branch:** `claude/charming-gates-tvqfs2` (the web session's branch)
**Started by:** lead chat, 13 Nov 2026 (open point of 0092; the owner wants tasks to finish sooner)
**Lane:** Clash: `core/clash.py`, `blender/clash.py`, `ops_clash.py`, `ui_clash.py`, `tests/test_clash*.py`. Not
`tests/test_demo_project.py` (0108 may be splitting its clash test – coordinate through `main`: merge it once before you
measure). Runs beside 0107 (Web 3D), 0108 (test machinery), 0109 (weather) – none of them edits these files.
**Model:** **Opus · effort High** (performance + geometry) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

## Goal

6 Animation > Clash check takes **at most half the time** on big moving machines – the demo vessel's animation first
(today ~12 min on the 4-core web machine, ~13 min as the CI test `test_no_clash_in_the_animation`) – and finds exactly
the same clashes: every test and every tour animation gives the same rows as today.

## Background

- 0065 built it (rigid bodies from the motion, boxes then BVH, screw motion between frames, tool zones); 0067, 0072
  (milling tile by tile), 0077 (`split_long` strips, `MESH_BUDGET`), 0091 (float32 `screw_between` note), 0092 (round
  parts that turn in place held on their carrier `_hold_still`, spoked sheaves checked once per turn `_still_pairs`, big
  parts look for a gap first `separation`, box trees by median halving): demo 12.4 min, 0 rows; Heavy clash 90 → 75 s.
- 0092's report: **the carousel's rim fence (posts, not round) sweeping past its drive gearboxes and brackets is the
  biggest remaining cost (~4 min of the 12)** – genuinely close parts, checked in full every frame.
- The demo since then has more motion (0102 tensioners lift/tilt, 0080 spooling, 0079 tracks: 432 pads/links moving).
  Flex parts (hoses, cables, spool ropes) stay out of the check (`clash.HOOKS`); track pads too? Decide and say.

## Scope

1. **Measure first** (profile the demo's check: per pair kind, per phase – boxes, gap search, BVH depth, between-frame
   steps; which 20 pairs cost most) and write it in the report before changing anything.
2. **Speed-ups that keep every clash** – your design, measured; candidates:
   - pairs that move about one common axis (rim fence × gearboxes on a turntable): the swept volume of the turning
     part's features, or once per turn like `_still_pairs`, where that is exact;
   - **time coherence**: a pair found far apart need not be checked again until the frames its relative speed needs
     to close the gap (a safe bound from the keyed motion), instead of every frame;
   - reuse of trees and transforms between frames; fewer between-frame steps where the motion is slow;
   - the work spread over the cores (processes per frame range or per pair batch) if the rest is not enough – Windows
     too (no console windows, CLAUDE.md section 8), so then a review by an agent that did not write it.
3. Same answers: `tests/test_clash*.py` unchanged in what they expect (new tests for each speed-up: a case where the
   skipped frames would have hidden a clash must still find it), every tour animation 0 rows, the demo 0 rows, the
   Heavy clash line the same rows.
4. Numbers in the report: demo, Heavy (scaled down and full if it fits), the test models – before/after, same machine.
   Update the PC check Heavy's `expected` time if it changes a lot; record CI times if the CI test got faster.

## Done when

- [ ] Scope 1–4; demo check at most half of today's time on the web machine (or the report says what stands in the way,
      with numbers).
- [ ] GitHub green incl. Windows; report filled in (runs, subagents); merge to main and release when green, then check
      that main really contains your commit.

## Not in this task

Flexible parts in the clash check; the float32 `screw_between` note (0091) unless it is on the way; a new clash UI.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (4 cores), 13 Nov 2026. Branch `claude/charming-gates-tvqfs2` (the web
session's own branch; the brief's `task/0110-clash-check-faster` was not used).

**Measured first** (the demo in the CI test's form – `build_project(small=True)`, Draft meshes –, sea at rest, Blender
as a module, old code, cProfile): 952 s with the profiler (835 s without), 1,853 moments + 39,365 between, 430,928
point tests (narrow, 676 s), 15,702 gap searches (103 s). **90 % of the time in the extra moments between frames**
(794 s), `_moment` 75 s, reading the frames 45 s. 729 of the 779 s spent on pairs involve a part that turns and is
not round. Three kinds of pair cost it all (each up to 13,000+ tests, 48 between every two frames):
1. **Small parts far apart inside a big part's box**, never looking for a gap (only pairs over 20,000 faces did):
   tensioner sprockets 1.0 m from their base frame (4 × 31 s), the handler's top pulley 12.9 m from the bulwark (28 s),
   the cable end clamp 9 m from the hull (22 s) and 1 m from the carousel well (12 s), sprockets 0.6 m from the top
   track frame (4 × 13 s).
2. **A part turning against another while the thing carrying both moves**: the tipping sheave on its pin and in its
   head while the head tips over (frames 1,667–1,853: 2 × 38 s + 2 × 25 s). `_hold_still` picks one carrier per body
   (here the swivel bearing), so `_still_pairs` only covered the stretch before the tip.
3. **The carousel's rim fence (47 posts, 47,000 faces) turning past its 12 drive parts** (4 gearboxes 28 s, 4 brackets
   24 s, 4 motors 24 s of gap searches each): 0092's open point. The motors have no fence surface near them at all –
   `unround_band`'s grid (cells 0.4 m on a 24 m part) could not tell; the gearboxes and brackets are passed by the
   posts at 6 mm.

**What changed** (Clash lane only: `core/clash.py`, `blender/clash.py`, tests; guide; CLAUDE.md):
- **A gap for every pair** (`_look_for_gap`, `_between`): small pairs look for a gap too, once testing them has cost
  `SEP_AFTER` (20,000 points looked up + 100 per test – counted, not timed, so a scene always gives the same rows); a
  search that spared fewer than 8 tests makes that pair wait 4 × longer for its next (`SEP_PAID`). Between frames the
  gap found last time, less the motion since, is reused without a new search; a search that stopped at the bound it
  was asked for is widened once when that bound is not enough.
- **Once per turn, pair by pair** (`_maybe_window`, `_pair_spins` per pair of bodies): when one part turns against the
  other about an axis that stays put in their *relative* motion (whatever carries them) and is round wherever the
  other can come, the pair is left for the rest of that stretch – opened only after a test with no clash or near miss,
  closed by a hit (`_hit`). "Round where the other can come" first by 0092's grid, else finely: the turning part's
  surface inside the other's box tree seen along the axis (`core.footprint`, `local_points`: corners + points 4 mm
  apart on the faces, ≤ 50,000), turned by 0092's four angles, must land within 0.05 mm + the facets' sag (≤ 0.25 mm).
- **Once per step of angle** (`_period_done`): when the turning part is not round there but repeats after 1/n turn
  (`core.symmetry_order` from its sharp corners; the rim fence: n = 47, `repeats` with ±2π/47), the pair is left once
  it has been checked over a whole step of relative angle with no clash or near miss since.
- **Found on the way:** a part turned by a small angle lands near itself whatever its shape. My first period test took
  the roller with a flat and the wheel off its centre for "repeating after 1/720 turn" and missed their clashes (caught
  by `test_clash_turning.py`); turned points must land within 2 % of how far they moved (`PERIOD_REL`). And a gap search
  costs 5–30 ms against 0.2–2 ms for testing two small parts: a search for every pair made the Heavy machine 7 × slower
  (400 s) before the cost gate. Both in CLAUDE.md section 8.
- **Track pads** stay out of the check: task 0079 already leaves the parts of a track out (their motion is drawn by
  Geometry Nodes, not keyed); nothing changed there.
- Tests: `tests/test_clash_faster.py` (new, 7: far arm left alone / still found when it reaches the fence; sheave on its
  pin while the head tips – pair windows, a bolt in the spokes' way still found; rim fence of 24 posts past a bracket –
  one post step, every post through the bracket found, one odd post found every turn – each compared with a *thorough*
  run without the shortcuts); `tests/test_clash_core.py` +2 (symmetry order of a 12-tooth wheel / round / off-centre
  wheel; the points where another part comes). The tests the brief names are unchanged in what they expect.

**Tested and measured** (4-core web machine, Blender 5.2.3 as a module, nothing else running unless said):
- **Demo, CI form** (Draft, 794 parts, 1,853 frames, sea at rest): **before 835 s (13.9 min), after 203 s (3.4 min) =
  24 %**, both 0 rows. After: 118,214 point tests (431k), 15,705 between (39,365), 54 pair windows, 8 period windows
  (the fence's gearboxes and brackets), reading the frames 46 s, 15 s holding parts. The CI test
  `test_demo_project.py::test_no_clash_in_the_animation` (bake + check): 235 s (5.6 min with its 97 s set-up).
- **Demo, full size** (Normal meshes, as Help > Make demo project; 983 parts checked): **before 1,248 s (20.8 min), after 261 s (4.4 min) = 21 %**, both 0 rows (1,853 moments; 39,378 →
  16,029 between; 430,927 → 117,270 point tests).
- **PC check Heavy `heavy.clash`** (full size: 2,992 parts, 251 frames + 2,016 between): before 51.8 s, after 54.3 s,
  **the same 1,667 rows** (row texts compared); scaled down: 5 frames, 0.7 s both. `expected` (60 s) left as it is.
- **Test models** (`tests/test_clash.py`, 20 tests: every tour animation, the test crane, CNC gantry, scissor lift …):
  before 214 s in all (the tour animations 166 s), after the tour animations 153 s – small models were fast already.
- Local tests: the four clash test files 59 passed; the independent tester's 33 (26 scenes) passed again on the final
  code; `test_demo_project.py -k clash` passed; guide and update tests 49 passed.
- **Subagent:** one independent tester (Sonnet, did not write the code) wrote 21 adversarial scenes – fence reversing
  and speeding up, a fence at 10 turns in 40 frames, posts not evenly spaced, a 1 mm key on a round wheel 0.4 mm from
  a block, a turn that later also slides along its axis, a part scaled while it spins, a bracket hidden part-way or
  sliding into the posts after the window opened, near misses at 1–6 mm – each against the thorough check: no
  difference (it ran on the code before the 2 % rule; rerun on the final code: all pass). No code was re-done after it.
  No Windows-only code: no Windows review needed.
- **GitHub runs:** one full run on the branch after merging `main` (run 43509697209, green, 20.9 min – test suite 9
  20.4 min because of `test_render_kit.py`, 548 s, new on `main` from task 0112, not this task). The split demo clash
  test of task 0108 (`tests/test_demo_clash.py`, four processes over windows of frames) took 267 + 103 s set-up there;
  recorded before: 464–533 s. Test times not recorded again (`tools/ci_times.json` would start another full run; the
  groups stay balanced enough). `main` fast-forwarded to the branch (code commit deb1115 + the task files): run
  43513068535 – all tests green, **v0.2.90 published**, the Windows update-from-the-release check passed, offered to
  the apps; only the landing page's deploy step failed ("no artifacts named github-pages", a GitHub hiccup): run again
  by hand (Actions → Landing page), green. Leftover branch: `claude/charming-gates-tvqfs2`.

**Open points / follow-up tasks:**
- Reading the frames (`frame_set` per frame, ~25 ms each on the demo) is now 23 % of the demo's check (46 of 203 s);
  the rest is spread thin (the top pair 4 s). Spreading over the cores was not needed.
- The float32 `screw_between` note (0091) is untouched; the demo's test still checks with the sea at rest.
