# 0035 – Way covers: several covers per axis, the carriage as last section, 8 sections

> **Lead, 11 Nov 2026:** taken off hold by the owner and re-briefed. The guide pictures of the first brief were done in
> **0044**; this task is only the way-cover code, now with several covers per project (0037 problem 3).

**Who:** worker · **Status:** open – can start · **Branch:** `task/0035-waycover-follow-ups` (or the session's own branch)
**Started by:** lead chat, 6 Nov 2026; re-briefed 11 Nov 2026
**Lane:** new **Way-cover lane** (split off the Machining lane: 0061 does not touch these files) – `blender/waycover.py`,
`blender/ops_waycover.py`, `blender/ui_waycover.py`, `core/waycover.py`, `tools/make_test_waycover.py`, their tests;
additive only: `blender/props.py` (the new list of covers, the old single cover kept for old projects),
`blender/reimport.py` only if the model-update hook needs it; tour stop, PC-check line, guide chapter 4 "Way covers"
**Model:** **Opus · effort Medium** (saved-project data changes: old projects must keep opening) · **Place:** Claude
Code on the web, environment "CAD-render-animation"

Runs at the same time as **0084** (demo model, `tools/demo_cable_lay/`), **0085** (vessel motion), **0086** (cutaway:
`section*.py`, `fade.py`, `materials.py`, maybe a hook in `joints.py`), **0087** (camera: `cameras.py`, the camera part
of `animation.py`, `ui_motion.py`) and, from Thursday 08:00, **0058** (Flex parts: `flex*.py`, hooks in `handlers.py`,
`animation.py`, `reimport.py`) and **0061** (Machining). Touch none of their files beyond the additive lines above.
Several releasing tasks at once: take the version number last; whoever finishes later merges `main` once and renumbers.

## Goal

Way covers as real machines have them: a cover on **each side** of the table on one axis, covers on several axes, the
biggest plate bolted to the carriage, and covers with many sections – without warnings at every Build.

## Background

- Reports of `tasks/0034-waycover.md` (open points) and `tasks/0037-owner-mill-gcode-demo.md` "problem 3": the owner's
  mill has a cover on each side of the table on one axis; the panel holds one cover, so the limits it wrote (7 sections,
  housing counts 0, 33 … 200 mm) did not match the ratios he set by hand (1, 0.75, 0.5, 0.25 per side), and every Build
  warns "Way cover Section 1/2 … goes beyond its own limits". The motion itself was right.
- Today: one cover per project (`scene.fresing.waycover`); `waycover.check_parts` refuses parts that move with the axis
  joint itself ("pick the parts of the covers, not the carriage").

## What to build

1. **Several way covers per project** (4 Motion > Way covers): a list of covers, each with its own axis joint, its own
   sections, Housing counts / Flip / Read from the axis; Add / Remove cover; two covers on the same axis (one each side
   of the table, typically one Flipped) give no warnings at Build. An **old project** opens with its one cover as the
   first item of the list, motion and limits unchanged (test with a project saved by the current release).
2. **Carriage section:** parts that move with the axis joint itself may be added as the **last** section only. It gets
   share 1, makes **no** new joint or coupling, and counts in N, so the other shares stay k/N (5 sections over 500 mm:
   100…400 mm for sections 1–4, section 5 = the carriage). The list shows "Section 5 – on the carriage". Adding a section
   after it or moving it up is refused with the reason in plain words. Remove cover leaves the axis joint and the
   carriage alone.
3. **8 sections:** `tools/make_test_waycover.py` takes a section count (keep 5 the default and the committed models
   unchanged); a Blender test with 8 sections checks every section's travel against k/8 of the axis at a few positions.
4. Model update, save/reopen, poses, G-code runs and the render queue move every cover. Every new button a tooltip; guide
   chapter 4 updated (panel picture replaced); PC-check line `machining.waycover` extended (two covers on one axis) or a
   new line; tour stop "Two way covers on one axis" (a set on the generic way-cover test model); `CHANGELOG.md`.

## Done when

- [ ] Tests that failed before: two covers on one axis build with 0 warnings and each section's travel = its share at
      sampled axis positions; carriage section as described (and the refusals); 8-section test; an old one-cover project
      opens and moves exactly as before; model update and save/reopen keep every cover.
- [ ] Screenshots of the Way covers panel checked; guide picture replaced; tooltip check 0 missing.
- [ ] Tour stop, PC-check line; the all-tour clash test still 0 rows; GitHub green incl. Windows; merged to `main` with
      the next free version, released.
- [ ] Report filled in (runs needed and why); `TASKS.md`: 0035 done.

## Not in this task

Milling's bit switching, anything in the Machining lane; bellows-style or roll-up covers (later, if the owner wants them);
the owner's way-cover STEP stays as committed.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
