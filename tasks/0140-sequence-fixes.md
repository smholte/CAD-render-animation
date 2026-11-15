# 0140 – Assembly sequence fixes: nested sequences, stable order, preview not saved, hidden parts left out

**Who:** worker · **Status:** done (0.2.106) · **Branch:** `claude/confident-cannon-e9dcg5` (the web session's branch)
**Started by:** lead chat, 15 Nov 2026 (rows of bug hunt 0131, report in `tasks/0131-bug-hunt-4.md`) ·
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Motion lane (assembly sequence)):** `core/sequence.py`, `blender/sequence.py`, `product_video.py` (the start), `trails.py` / `sequence.tidy_trails`, their tests, the guide's sequence section.
**Do not edit:** `paths*.py`, `demo*` (0126/0137), the Import lane (0139), the Web 3D lane (0134).

## Goal

Take apart / Put together give the same, clash-free result in every Build, in the queue and in the product video.

## Background

The rows below are from bug hunt 0131 (report on `main`): each row has the place in the code, how to repeat it
("Proof") and a suggested fix. Read those rows first; repeat each one before fixing it.

- **Row 8:** nested sequences jump (homes kept from the first Take apart) – a stack of homes per part; Put together plans from where the parts are.
- **Row 9:** flush parts swap order by float32 noise – round `out_key` to 1e-6 m.
- **Row 10:** Make a product video (and Save pose / Save scene) while a Preview is above 0 % stores the preview's places – end the preview first.
- **Row 11:** a part hidden in 2 Structure still takes part (and becomes visible with Put together + Hide/Fade) – leave it out.
- **Row 16f, g:** trails of removed parts warn at every Build (drop them silently); `_plan_key` keys on `as_pointer()` and ignores the obstacles (key on `seq_id` + obstacles' names, visibility, places).

## Done when

- [x] Every row above fixed, each with a test that failed before the fix (the row's proof as a test).
- [x] Tooltips, guide sentence where the owner sees a change, function list / PC-check / tour stop only if something
      visible changes; GitHub run green; merged; version (CLAUDE.md section 7); report (short list for the owner).

## Not in this task

Other rows of 0131 (they have their own tasks: 0136–0140); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 15 Nov 2026.

**What changed:**
- Row 8 (nested sequences): `Keys.home` is a stack per part (`sequence.home_top`, `_home_push`, `_home_pop`); a Put
  together is planned where the matching Take apart found the parts and comes in from where they are when it starts
  (no jump). Back to CAD reads the top of the stack (`animation.py`).
- Row 9: `core/sequence.order` rounds the near-end key to 1 µm (`KEY_STEP`); ties fall to the tree order.
- Row 10: `sequence.end_preview` at the start of `product_video.make`, `states.save_pose` and `states.save_shot`.
- Row 11: `movers` leaves out parts hidden in 2 Structure (`fr_hidden` on the part or a parent in the tree);
  new `seq_hidden` count, a line in the step's box ("1 hidden part left out: it stays hidden (2 Structure)").
- Row 16f: `tidy_trails` drops a step's trail line whose part is gone (no warning; Build makes the step's trails again).
- Row 16g: `_plan_key` keys on `seq_id` + the other parts' names, visibility, excluded flag and places.
- Guide: two short paragraphs in the sequence section. No new function, PC-check line or tour stop (nothing new to
  show; the box line is a count).

**Tested and measured** (4-core web machine, test models `test_sequence.step` / `test_sequence_frame.step`):
- 6 new tests in `tests/test_sequence.py`, one per row – all 6 failed before the fix, pass after (row 8: 404 frame
  jumps > 15 mm before, 0 after, clash check 0 rows). `test_sequence.py` 36 passed; product video, functions, guide,
  motion extras/fixes, 0120 fixes, queue fixes, phase 2: 177 passed. GitHub: see the run of the branch.

**Open points / follow-up tasks:**
- A rider (a part a joint carries) in a nested Put together still comes in along the plan's line, not from where it
  is: no jump in the tests here, but a rider whose Take apart settings differ from its Put together could still jump.
- Row 9's rounding leaves ties only at the exact 1 µm half-way point (very unlikely).
- The step's counts (also the new hidden count) update at Build or when the step changes, not when you hide a part.
