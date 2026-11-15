# 0140 – Assembly sequence fixes: nested sequences, stable order, preview not saved, hidden parts left out

**Who:** worker · **Status:** open – can start when a code slot is free · **Branch:** `task/0140-sequence-fixes`
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

- [ ] Every row above fixed, each with a test that failed before the fix (the row's proof as a test).
- [ ] Tooltips, guide sentence where the owner sees a change, function list / PC-check / tour stop only if something
      visible changes; GitHub run green; merged; version (CLAUDE.md section 7); report (short list for the owner).

## Not in this task

Other rows of 0131 (they have their own tasks: 0136–0140); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
