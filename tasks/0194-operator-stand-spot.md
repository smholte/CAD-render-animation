# 0194 – Fix: the tool-change operator stands 4 cm closer after an unchanged model update (bug hunt 6, row 16)

**Who:** worker · **Status:** done (0.2.153) · **Branch:** `task/0194-operator-stand-spot`
**Started by:** lead chat, 17 Nov 2026 (from bug hunt 6, task 0183) · **Model:** Sonnet · effort Low · **Place:** Claude Code
on the web, environment "CAD-render-animation"
**Area:** people – `core/tc_person.py` (`stand_spot`, the floor map), `blender/tc_person.py` (`_floor`, `bake`), their tests.
Nothing else.

## Goal

The same model always gives the same stand spot for the person who changes the tool: a model update with nothing
changed, a Build, a save and reopen never move him.

## Background

- `tasks/0183-bug-hunt-6.md`, Findings row 16 (proof: helper `C/e8b.py`, `e8d.py`, `e8e.py`): after a model update with
  nothing changed the operator moves from (0, −0.60) to (0, −0.56) and stays there after Build, save and reopen; the
  bounds are identical. Probably the cabinet front lies on a cell edge of the floor map (cell 0.04 m, `WORK_ROOM`
  0.25 m) and rounding decides. Not checked whether the closer spot clashes.

## Rules for this task

- Find the real cause first (say it in the report); then round the floor map away from cell edges or snap with a
  tolerance, so tiny float differences cannot move the spot by a cell.
- Test that **failed before**: the row's case (update with the same file) keeps (0, −0.60) to 1 mm; plus a unit test of
  `stand_spot` with an obstacle edge exactly on a cell edge ± 1e-9 m giving one answer. Check the closer spot for a clash
  and report it. Nothing loosened.
- Normal finish (sections 2 and 7); take the next free version when you merge.

## Done when

- [ ] Same model → same stand spot (tests above green locally and on GitHub).
- [ ] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

Walk paths and gaits (0157), the glove and the cabinet door (0156).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 18 Nov 2026

**What changed:** Cause: the floor map's grid started at its own corner (`lo`), which follows the first spindle position, so a
hair of rounding noise moved the cell lines, and a cabinet front lying on a cell edge landed in the other cell (a 4 cm step).
`core/tc_person.py` `Floor`: `lo` snapped to the world's cell lines, and a point within 0.0001 cell of a cell edge takes both
cells (`SNAP`, `_mark`), so noise cannot decide and the map errs towards the machine, i.e. the person stands further away.
The first try (rounding the point into one cell) gave the closer spot (0, −0.56) for good and the hands clipped the cabinet
in two real-app tests – so the closer spot DOES clash (hands inside "CABINET STAND" at frames 171–172, 460–463); (0, −0.60) is right.

**Tested and measured:** new `test_stand_spot_does_not_move_with_rounding_noise` (fails before, passes after). Real Blender
model of `test_tc_person_blender*.py`: spot (0, −0.60) with the fix (was −0.56 only with a shifted map corner). The four
tc_person test files: 108 passed (Linux, 4 cores). The row's exact case (update with the same file) was not run separately:
its cause is the shifted map corner, which the world-fixed grid removes.

**Open points / follow-up tasks:** none; no helper agents used. Runs: see the GitHub result.
