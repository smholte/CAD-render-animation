# 0092 – Clash check: fast with parts that turn in place (rollers, drums, a coil)

**Who:** worker · **Status:** running · **Branch:** `task/0092-clash-turning-parts`
**Started by:** lead chat, 12 Nov 2026 (0077's open point)
**Lane:** Clash – `core/clash.py`, `blender/clash.py`, `ops_clash.py`, `ui_clash.py`; tests
**Model:** Opus · effort High (algorithm + speed) · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner can run the clash check on the whole cable-lay demo (and his own offshore models) in minutes, not hours, while
rollers, sheaves, drums and the coil turn – without missing a real clash.

## Background

0077 measured on the full-size demo (4-core web machine): with the 300 turning rollers, the coil and the support
rollers in the check it was stopped after 47 min, not done; with them left out 12.5 min (1,839 moments + 32,870
between, 355,868 narrow tests). Why: a part turning about its own round axis keeps moving its box corners, so every
pair near it is tested again at every moment, plus many moments between frames. The static cable lying on the rollers
is another costly contact (touching all the time).

## What to build

- **Turns in place:** a rigid body whose motion over a stretch of frames is a turn about an axis that stays put relative
  to the other body, and whose shape is round about that axis (check it: the mesh's distance to the axis per ring of
  points, within a tolerance), gives the same overlap with that other body at every angle. Test such a pair once per
  stretch instead of per moment; no moments between frames for it. A part that turns about its axis **and** moves (a
  roller on a moving carriage) is treated as a body that moves with its carrier only.
- A part that turns about its axis but is not round (a cam, a sprocket with teeth, a drum with a groove shape) keeps the
  full check unless its shape's turn changes nothing measurable (say how you decide; teeth of a sprocket meshing with a
  chain must still be checked).
- **Resting contact:** a pair touching from the start (the cable on its rollers) keeps today's rule (only depth beyond the
  start overlap counts) and should cost little: say what you did.
- The result rows of every existing test model stay the same (tour animations 0 rows; the clash model 6.0 mm; the 0065 /
  0067 / 0072 tests unchanged).

## Done when

- [ ] Tests: a round roller turning beside a fixed frame (0 rows, tested once per stretch), the same roller with a
      flat cut on it (still checked fully, a real clash found), a roller on a moving carriage, a sprocket with teeth.
- [ ] Measured on the full-size demo (Help > Make demo project, or `blender/demo.py` from a script) **with** the turning
      parts: time, moments, narrow tests; before (0077's numbers) and after. Target: about the 12.5 min of 0077 or less.
- [ ] The PC check Heavy line for clash (exists) still passes; its time before/after.
- [ ] GitHub green; merged to `main` with the next free version; report filled in; `TASKS.md` updated.

## Not in this task

The demo model itself (0091), joints (0093), hoses (0058, which may add its own bodies later through `HOOKS`).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
