# 0327 – Lower clash-check memory

**Who:** worker · **Status:** done · **Branch:** `task/0327-lower-clash-memory`
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

**Chat / date:** Claude Code on the web (worker), 25 Nov 2026. Released as **0.2.260**.

**Where the memory went** (stress model, 11,228 placed / 1,995 unique parts, 13.9 M triangles; the check alone, project
opened from a saved .blend, process memory sampled every 50 ms; 4-core web machine, 16 GB, no graphics card):

| stage | before | after |
| --- | --- | --- |
| set-up: a float64 `Mesh` for **every** unique mesh, oriented – which builds a BVH tree per closed mesh | +2,290 MB, 15.3 s | +390 MB (Blender's float32 / int32 numbers only), 2.8 s |
| reading the motion + rigid bodies: (P, T, 4, 4) motion of every part, copied 3–4 times, twice | +1,480 MB on top | +480 MB (the matrices themselves, 361 MB) |
| the check (pairs, meshes and trees of the ~270 pairs tested) | below the peak | +30 MB |
| **peak above the open project** | **3,772 MB** | **997 MB** (−74 %) |
| time | 71.6 s | 58.8 s (−18 %) |
| answer | 791 moments, 42 clashes | the same rows (parts, frames, deepest moment, depth to the µm) **and the same statistics** (pairs, narrow tests, held parts, windows …) |

**What changed:**
- `blender/clash.py`: `_Meshes` – the check's mesh dict keeps each mesh as `_mesh_arrays` (float32 corners, int32
  triangles) read at the set-up and makes the `Mesh` (float64 / int64, orientation, trees) the first time a test asks
  for it. Boxes come from the same numbers, so every box and every mesh is bit for bit what it was. Only a few hundred
  of the 1,995 meshes are ever made on the stress model.
- `core/clash.py`: `rigid_groups_of(mats, reach)` = `rigid_groups(deltas(mats), reach=reach)` worked out 512 parts at a
  time (the tolerance, the parts that never move); only the moving parts' motion is kept. `rigid_groups` shares the
  grouping (`_group_moving`) and is unchanged for its callers (the windows child, tests).
- Tests: `test_rigid_groups_in_chunks_give_the_same_groups` (chunk sizes 1 … 5,000, far from the origin, a late and a
  creeping part), `test_meshes_are_made_only_when_a_test_needs_them` (made meshes equal the whole ones, boxes equal,
  never-tested ones not made). CLAUDE.md section 8: one line. CHANGELOG 0.2.260.

**Tested and measured** (4-core web machine, Intel Xeon 2.1 GHz, 16 GB, Linux, real Blender 5.2.3 in the background):
- The table above (same saved stress project, before and after, run one after the other).
- The real PC-check line, after: `stress.clash` **66.4 s, 791 moments, 42 clashes, peak 2,659 MB** with the project at
  ~1.7 GB (0315's run on this kind of machine: 53.7 s, peak 7,509 MB after the Solid view and Live preview lines had
  raised the session to ~4.3 GB; this run did only model, import, build and clash, so its time is not comparable with
  53.7 s – the A/B above is).
- All clash test files locally (`test_clash_core`, `test_clash`, `_faster`, `_rim`, `_tag`, `_turning`: 68 passed,
  every expected clash unchanged); GitHub: lane run green (incl. `test_tour_clash`, `test_clash_windows`, the demo),
  then the full run of 0.2.260.
- Runs: 3 (lane run while building, full run with the version, and again after 0.2.258 and 0.2.259 took the version numbers meanwhile).

**Owner's re-check:** after the update, Help > Fresing Render PC check… > **Stress**, then in the table the line
**stress.clash**: same 791 moments and 42 clashes, peak memory expected about 3 GB lower than your 7,024 MB of 25 Nov
(the rest is the open project after the Solid view and Live preview lines), time about the same or a little less than
37.9 s.

**Open points / follow-up tasks:**
- What is left is mostly the matrices of every part at every moment (361 MB, float64). They could be kept as float32
  (Blender's own precision, so no loss) and turned into float64 where used – about 180 MB more; not done (30 places
  use them, little gain).
- Not measured on a 16 GB laptop: the expectation is the open project (4–6 GB with the stress model) + ~1 GB.
