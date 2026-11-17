# 0194 – Fix: the tool-change operator stands 4 cm closer after an unchanged model update (bug hunt 6, row 16)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0194-operator-stand-spot`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
