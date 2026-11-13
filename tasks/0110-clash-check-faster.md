# 0110 – Clash check faster on big moving machines

**Who:** worker · **Status:** running · **Branch:** `claude/charming-gates-tvqfs2` (the web session's branch)
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
