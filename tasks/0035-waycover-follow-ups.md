# 0035 – Way covers: the carriage as last section, 8 sections; missing guide pictures (way covers, labels, pictures & music)

**Who:** worker · **Model:** Sonnet · effort Medium · **Place:** Claude Code on the web · **Status:** open – after 0031
**Branch:** `task/0035-waycover-follow-ups`
**Started by:** lead chat, 6 Nov 2026 · **Lane:** Machining (`waycover.py`, `ops_waycover.py`, `ui_waycover.py`,
their tests) plus `docs/` pictures and guide text. The label/picture/music pictures belong to the Scene & Render lane's
panels, which is free: this task only **photographs** them – no code change in that lane.

## Goal

The open points of tasks 0034 and 0025: a way cover whose last section sits on the carriage works without
tricks, 8 sections are proven in Blender, and the user guide gets the pictures it is missing.

## Background

- Read the reports of `tasks/0034-waycover.md` and `tasks/0025-callouts-pictures-music.md` (open points only).
- **Why after 0031:** guide pictures need the real Blender (`tools/guide_screens.py`). Task 0031 stores Blender in
  every worker session. If it is still not there when you start, do it the way 0026 did: make the pictures in a
  GitHub real-app job and read them back from the job log (see the 0026 report), and say so in the report.
- Refusal today: `waycover.check_section` (around line 125 of `blender/waycover.py`) refuses parts that move with the
  axis joint itself ("pick the parts of the covers, not the carriage"). On many machines the last (biggest) cover
  plate is bolted to the carriage – it already moves 1:1 with the axis.

## What to build

1. **Carriage section:** parts that move with the axis joint itself may be added as the **last** section only. It
   gets share 1 (it moves with the axis already), makes **no** new joint or coupling, and counts in N, so the other
   shares stay k/N (5 sections over 500 mm: 100…400 mm for sections 1–4, section 5 = the carriage). The list shows it
   as "Section 5 – on the carriage". Adding another section after it, or moving it up, is refused with the reason in
   plain words. Housing counts, Flip, Read from the axis, Remove way cover (leaves the axis joint and the carriage
   alone), model update and save/reopen keep working. Tooltip for anything new; PC-check line unchanged unless the
   check can cover it in one line (then raise `MIN_LINES_FULL`).
2. **8 sections in Blender:** the generator `tools/make_test_waycover.py` takes a section count (keep 5 the default
   and the committed model unchanged); a Blender test with 8 sections checks every section's travel against k/8 of
   the axis at a few axis positions, and one with a carriage section.
3. **Guide pictures (docs/img + `docs/USER-GUIDE.md`):** the Way covers panel and a render of the generic way-cover
   test model (chapter 4 "Way covers"); the Labels fold of panel 5 and the Pictures / Music folds of panel 6
   (chapters 5 and 6), plus one still of the test crane with two labels if `guide_screens.py` can make it cheaply.
   Generic test models only (public repository). Add the shots to `tools/guide_screens.py` so they can be made again.

## Done when

- [ ] Carriage section works as described, with tests that failed before; 8-section test passes
- [ ] Guide has the pictures above; `tools/build_guide.py` builds; tooltip check 0 missing
- [ ] GitHub run green; merged; released (version taken last, CLAUDE.md section 2)
- [ ] Report filled in (runs needed and why)

## Not in this task

Label, picture-card or music code (Scene & Render lane); milling's bit switching at tool changes (later, Machining lane);
the owner's way-cover STEP stays as committed.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
