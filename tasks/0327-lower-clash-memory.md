# 0327 – Lower clash-check memory

**Who:** worker · **Status:** running · **Branch:** `task/0327-lower-clash-memory`
**Started by:** lead, 25 Nov 2026 (0315's slow place 4, the owner's Stress run on his PC) · **Model:** Opus · effort Medium
**Area:** Clash lane – `core/clash.py`, `blender/clash.py`, `blender/ops_clash.py` (only if the run's progress needs it),
their tests, CHANGELOG.
**Not:** `pccheck/checks.py` and `pccheck/stress.py` (other tasks change them – measure with the existing `stress.clash`
line), `blender/handlers.py` and `blender/joints.py` (0326), the clash panel's looks (`ui_clash.py`).

## Goal

The clash check of a big model fits on an ordinary office PC or a sales person's laptop (16 GB), with the same answer.

## Background

- 0315 (`tasks/0315-stress-model-10k-parts.md`, item 4): peak 7.5 GB on the web machine.
- **The owner's Stress run, 25 Nov 21:06, 0.2.257** (24 cores, 47 GB): `stress.clash` 37.9 s, **791 moments, 42
  clashes, peak 7,024 MB**; the session sits at ~4–6 GB around it (import Normal peak 1,962 MB, solid view 4,136 MB).
  So the clash check itself adds about 3 GB on top of the model.

## What to do

1. **Measure where the memory goes** (tracemalloc + process peak per stage): copies of meshes, BVH trees of standing
   parts, per-moment arrays, pair lists. Report the split.
2. Bring it down without changing the answer, e.g.: one shared tree per unique mesh (the model has 1,995 unique of
   11,228 placed), standing parts far from every moving part's swept box left out, per-moment data freed as you go,
   float32 where float64 is not needed. Your measurements decide.
3. Time must not get worse by more than about 10 %.

## Done when

- [ ] Stress model on the web machine: clash peak at most about half of today's extra (target: session + ≤ 1.5 GB),
      the same 791 moments and 42 clashes, time within +10 %; numbers before / after in the report
- [ ] Every existing clash test gives the same clashes
- [ ] Tests added/updated; full suite passes; GitHub run green
- [ ] CHANGELOG; the owner's re-check line in the report ("PC check > Stress – the clash line")
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
