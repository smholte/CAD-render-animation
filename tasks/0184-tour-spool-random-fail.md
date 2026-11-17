# 0184 – The test tour's `spool` stop fails at random on GitHub: find the cause and fix it

**Who:** worker · **Status:** open – can start · **Branch:** `task/0184-tour-spool-random`
**Started by:** lead chat, 17 Nov 2026 (open point of 0171, 0173 and 0179) · **Lane:** Flex (`core/paths.py`,
`blender/paths.py`, `blender/spool.py` and their tests; `tour.py` only for this stop's set-up)
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

No more random red runs from the tour stop `spool` ("Cable 'Power cable' no longer touches 'GUIDE SHEAVE' at frame
233"). It failed in run 44045080244 (0179's branch, a test-suite-5 job that took 19.4 min instead of 7.8) and on
0173's branch; both passed when run again. Cause from 0173's report: the tight-string solver takes the other branch
round GUIDE SHEAVE at frame 233, where the full spool's leave point (0174) moves on.

## What to do

1. Repeat it: run the stop's Build many times (and under load: `stress` or several processes at once, as a busy runner)
   until it fails; record how often. Find what differs between runs (thread timing, a warm start, float32 rounding, a
   solve order) – never "it is timing" without the case that shows it.
2. Fix the cause in the solver or the spool's leave point so the same Build always gives the same path (the branch
   kept from frame to frame, as `core/flex.solve_motion` keeps one shape). A test that failed before: the repeat case
   in a loop, deterministic.
3. Do not loosen the stop's check or the tour's 0-clash rule.

## Done when

- [ ] Cause named with its evidence; fix + test; the stop passes N times in a row under load (N in the report).
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
