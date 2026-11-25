# 0366 – Faster model build after the import (0301 #1) + where the import time goes

**Who:** worker · **Status:** running · **Branch:** `task/0366-faster-model-build`
**Started by:** lead, 25 Nov 2026 23:5x (owner allowed extra code tasks for the night; study 0301's first proposal)
· **Model:** Opus · effort Medium
**Area:** Import lane –
- `blender/build.py`: meshes through the attribute API, bounds in NumPy.
- `blender/props.py`: **only** `_group_look_changed` (one walk over the parts instead of one per group). This is the only
  non-additive change in this shared file. 0348 and 0352 add to `props.py` too – whoever merges second updates its branch.
- `importer/step_reader.py` (and `importer/mesh_reader.py` if it writes the same stats): stage seconds in `tree.json`
  stats.
- `pccheck/heavy.py`: one new Heavy line `heavy.import_stages`.
- Their tests, CHANGELOG, the PC-check guide line.

**Not:**
- `pccheck/checks.py` and `pccheck/stress.py` (0348 adds to `checks.py`).
- `blender/ops_import.py`, `blender/reimport.py`, `core/part_types.py`, `core/cad_materials.py`, `importer/step_meta.py` –
  0340 starts there on Monday.
- The cache format (stats are free-form – no format change).
- 0301's #2 (split transfer) and #3 (update reads only changed parts).
- `handlers.py` / `joints.py` (0326).

**Must be merged before 0340 starts (Monday 30 Nov morning).** 0340 changes `build.py` next (finish per colour). If you
cannot merge by Sunday 29 Nov evening, push your branch and write "WAITING FOR YOU:" with where it stands.

## Goal

Every import and every model update of a big machine is about 5–6 s faster: the same model, built faster in Blender.
A new Heavy PC-check line shows, on the owner's 24-core PC, how long each import stage takes. That tells the lead
whether 0301's bigger change (#2) is worth its risk.

## Background

- Study 0301 is on branch `task/0301-study-faster-import`, file `tasks/0301-study-faster-step-import.md` (not on
  `main`). Read it with `git show origin/task/0301-study-faster-import:tasks/0301-study-faster-step-import.md`. Read
  "B. Options" item 1, "C. Ranked proposals" row 1 and "PC-check Heavy line (in #1)". Its prototypes are on the same
  branch.
- Measured there on the Big model's cache (4-core web machine):
  - meshes through `attributes["position"]` / `attributes[".corner_vert"]` with `foreach_set`: **0.5 s instead of
    3.1 s**. `update(calc_edges=True)` stays (0.7–0.8 s).
  - sorting: one walk instead of one per group in `_group_look_changed`: expected −2 s of 2.4 s.
  - bounds from the cache's bounding boxes × matrices in NumPy: expected −1 s of 1.2 s.
  - Copies already share one mesh (2,401 meshes for 12,081 objects) – nothing to gain from instancing.
- Since the study: 0324 (model update reuses unchanged parts, 0.2.243) and 0325 (lighter long cables, 0.2.260) changed
  the import and update path. **Measure again on today's `main` before changing anything.**
- **The owner's Stress run, 25 Nov 21:06, 0.2.257 (Ryzen 9 9900X, 24 cores):** import Draft 48.8 s (4.13 M triangles) /
  Normal 55.3 s (13.9 M; from the cache 16.3 s); model update 70.2 s. Draft ≈ Normal, so the one-core STEP read
  dominates on his PC.

## What to do

1. Measure today's `main` on the Big / Heavy model (`pccheck/heavy_scene.py`; the study's script) and the Stress model
   (`tools/make_test_stress.py`): the Blender build stages (meshes, objects, sorting, structure, bounds) and the whole
   import. Write the numbers in the report.
2. Meshes through the attribute API, `_group_look_changed` in one walk, bounds in NumPy – as in the study. Normals, UVs
   (`fr_*` layers), face-colour data and everything else the build writes must stay exactly as today.
3. The reader writes `seconds_parse`, `seconds_transfer` and `seconds_biggest_part` into the `tree.json` stats.
4. The Heavy line `heavy.import_stages`, "Big machine: where the import time goes": imports the Heavy machine once with
   the normal helper count and records each stage (parse, transfer + names / tree, copy, meshing wall time,
   part-seconds, biggest part, helpers used, cache write, then in Blender: meshes, objects, sorting, structure, bounds,
   surroundings and **first draw**). Use the study's definitions. It also states plainly which stages run on one core.
5. Model update: measure the Stress model's update before and after (it uses the same build). Say what it gained.

## Done when

- [ ] The same model as before: a test compares the built meshes (positions, triangles, normals, UV layers, face data),
      the group sorting and the bounds with today's build, on the Heavy model and on at least one test-tour model.
- [ ] Blender build stages about −5 s on Big on the web machine (study: −5 to −6 s of ~39 s), the before / after table in
      the report. Model update on the Stress model measured before / after.
- [ ] `heavy.import_stages` runs in the PC check's Heavy mode (and in its CI check, as the other Heavy lines); the guide's
      PC-check list has its line.
- [ ] Tests added / updated; full suite passes; GitHub run green; CHANGELOG.
- [ ] Report filled in, with **the owner's line**: "PC check > Heavy – the line 'Big machine: where the import time
      goes'; paste its numbers to the lead". Merged and released before Monday 30 Nov.

## Not in this task

0301's #2 split transfer and #3 partial re-read (the lead decides #2 from the owner's numbers of the new line); the
import popup (0340); anything in `ops_import.py` / `reimport.py`.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
