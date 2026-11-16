# 0138 – Fix: the demo's Build gives a different result depending on the frame shown

**Who:** worker · **Status:** done (16 Nov, 0.2.113) · **Branch:** `task/0138-demo-build-any-frame`
**Started by:** lead chat, 15 Nov 2026 (rows of bug hunt 0131, report in `tasks/0131-bug-hunt-4.md`) ·
**Model:** Opus · effort Medium (cause found by study 0141) · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Flex parts lane / Demo models lane):** what the second end, its CPS, the riders and let go read at Build (`paths*.py`, `demo.py` stages only if the cause is there), their tests.
**Do not edit:** the Web 3D lane (0134/0135), the Import lane (0139), `sequence.py` (0140).

## Goal

Build gives the same animation whatever frame is shown when the owner presses it – today shots 9–12 of the demo go wrong (second end and CPS up to 73 m off) when he Builds at a later frame.

## Background

The rows below are from bug hunt 0131 (report on `main`): each row has the place in the code, how to repeat it
("Proof") and a suggested fix. Read those rows first; repeat each one before fixing it.

- **Row 6:** built at frame 1 = what Make demo saved; at 1803 24 objects differ; at 3206 the second end and CPS lie up to 73 m off and Build warns "98 m more cable than the water is deep". Not on the small `test_moving` model – something the demo's second end adds (parts excluded until shot 9, CPS rider, quadrant, let go) reads the pose shown. Find it; Build reads everything at the animation's first frame (or a fixed start pose). Test: the demo (or a small model that repeats it) built at the first and the last frame → identical.

**Cause and fix plan: study 0141** (`tasks/0141-demo-build-frame-study.md`, report sections 2 and 5; scripts on
branch `task/0141-demo-build-frame-study`, `scratch/0141/`): Build's start scene re-sets the water level → every sea
cable's touch-down is worked out again in the pose shown at the frame shown (let go + the clock). Follow its plan:
step 1 (Build shows the first frame before it reads anything), step 2 (`water_changed` leaves a cable alone when
nothing changed; `anchor` works at the animation's first frame), step 3 (the scale's 7th digit), and its tests
(failing first). Check what 0137 changed in the same functions before you start.

## Done when

- [x] Every row above fixed, each with a test that failed before the fix (the row's proof as a test).
- [x] Tooltips, guide sentence where the owner sees a change, function list / PC-check / tour stop only if something
      visible changes; GitHub run green; merged; version (CLAUDE.md section 7); report (short list for the owner).

## Not in this task

Other rows of 0131 (they have their own tasks: 0136–0140); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (scheduled run), 16 Nov 2026. Branch `claude/amazing-heisenberg-en6l3o`
(the session's branch name; the brief's `task/0138-…` was not made). Version 0.2.113.

**What changed** (study 0141's plan, steps 1–3):
- `animation.bake`: shows frame 1 before it reads anything (Build ended there already).
- `paths_sea.water_changed`: a sea cable is left alone when the waterline and its seabed height (`sea_start[2]` =
  `bottom_z`) did not change – a saved scene or Build's start scene with the same water no longer sets the touch-down.
- `paths_sea.anchor` (new `_first_rel`): the touch-down is worked out at the animation's first frame – from the places
  read at Build, or (nothing built) with the timeline on that frame for a moment; let go counts as at that frame.
  So "Go to scene" and a value typed again at a late frame keep it too. "Set the touch-down here" works the same
  (tooltip, message and guide sentence say so).
- `paths._scale`: six significant digits (the 7th followed vessel motion).
- No new function / tour stop / PC-check line (nothing new to see).

**Tested and measured** (4-core web machine, Blender 5.2.3 as a module):
- New `tests/test_build_any_frame.py` (8 tests, 23 s): before the fix 7 failed with study 0141's numbers (touch-down
  moved 21.04 / 3.44 / 17.78 m in cases A / B / C, 21.04 m in F and G built and not built, the same water level
  set again); after: all 8 pass (the 8th, a changed depth still moves the seabed, is a guard).
- `tests/test_demo_project.py::test_save_reopen_and_build_again_gives_the_same_keys` now builds with the last frame
  shown and compares every sea cable's mark and Build's warnings too: passes (388 s incl. making the demo). Not run
  against the old code here (study 0141 measured +114 m / "98 m more cable" on it).
- Cable/sea files: test_paths_moving, _moving_independent, _sea, _sea_independent, _settle, _kept, _swivel,
  test_sea_cutaway: 164 passed. Tooltip check: 741 ok.
- GitHub runs: 3 – branch ffd43a8 green (43797760539); after merging main, 7cda23b green (43800377972); main moved again (a report file), merged once more and fast-forwarded: main 011f2f6 runs full and releases.

**Open points / follow-up tasks:**
- Study 0141's side note stays: after Clear keys past a let-go frame, the live picture shows let-go parts where the
  seabed was (Build replaces it).
- Leftover branches the owner can delete: `task/0141-demo-build-frame-study`, `claude/amazing-heisenberg-en6l3o`.
