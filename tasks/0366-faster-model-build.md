# 0366 – Faster model build after the import (0301 #1) + where the import time goes

**Who:** worker · **Status:** done 26 Nov (0.2.266) · **Branch:** `task/0366-faster-model-build`
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

- [x] The same model as before: a test compares the built meshes (positions, triangles, normals, UV layers, face data),
      the group sorting and the bounds with today's build, on the Heavy model and on at least one test-tour model.
- [x] Blender build stages about −5 s on Big on the web machine (study: −5 to −6 s of ~39 s), the before / after table in
      the report. Model update on the Stress model measured before / after.
- [x] `heavy.import_stages` runs in the PC check's Heavy mode (and in its CI check, as the other Heavy lines); the guide's
      PC-check list has its line.
- [x] Tests added / updated; full suite passes; GitHub run green; CHANGELOG.
- [x] Report filled in, with **the owner's line**: "PC check > Heavy – the line 'Big machine: where the import time
      goes'; paste its numbers to the lead". Merged and released before Monday 30 Nov.

## Not in this task

0301's #2 split transfer and #3 partial re-read (the lead decides #2 from the owner's numbers of the new line); the
import popup (0340); anything in `ops_import.py` / `reimport.py`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 25–26 Nov 2026. No subagents (a small, local change; the independent
review was skipped: no Windows-only code).

**What changed:**
- `blender/build.py`: `_new_mesh` writes points and corners straight into the attributes `position` / `.corner_vert`
  (loop starts and `update(calc_edges=True)` as before); `world_bounds` in NumPy – each mesh's box read once (an object
  with modifiers has its own), all boxes turned into the world at once (R c + t ± |R| e = the 8 corners).
- `blender/props.py`: `_group_look_changed` – inside the new `held_looks()` a changed group look is noted and given to
  the parts in ONE walk at the end (nested: the outermost walks); outside it, at once as before.
  `blender/logic.py`: `apply_rules` (new groups' material + colour) and `apply_scheme` run inside `held_looks()`.
- `importer/step_reader.py`: stats `seconds_parse`, `seconds_transfer`, `seconds_tree`, `seconds_part_total`,
  `seconds_biggest_part`, `seconds_write` (each helper's reply carries its part's seconds as a 7th item; no cache
  format change). `mesh_reader.py` unchanged (it writes no reader stages).
- `pccheck/heavy.py`: Heavy line **`heavy.import_stages`** "Big machine: where the import time goes" (before
  `heavy.import`, which reads again anyway): every reader stage, helpers used, part-seconds, biggest part, the Blender
  stages (meshes, objects, sorting, welds from the file, structure, bounds, surroundings) by clocks wrapped round them,
  the whole import, the time on one core, and the first draw – a Solid-view (Workbench) picture at 1920 × 1080 and the
  mean of the next 3 (the PC check runs without a window, so no draw handler can run; on a PC without a graphics card
  this part is left out with one line, the rest still counts). `MIN_LINES_HEAVY` 19 → 20. Guide: the line in the
  Heavy paragraph.
- `tests/test_build_speed.py` (7 tests): the old build kept in the test as the reference; the tour crane, painted
  faces, an OBJ with UVs and the Heavy machine (scaled down, made at test time) built both ways from the same cache and
  compared exactly – points, corners, loop starts, every attribute (edges, normals …), UV layers, mesh properties,
  groups, slots, face materials, every material, matrices; bounds within 1e-6 of the model's size. A mutation (corners
  turned round) fails it. Plus: an empty part, bounds with turned / scaled / modified / CAD-bounds parts, the one walk.

**Tested and measured** – **4-core web machine** (Intel Xeon 2.1 GHz), Blender 5.2.3 as a Python module, `finish_import`
on the same cache, old = `main` 0.2.261, new = this branch:

| Stage (s) | Big (2,400 / 11,968 parts, 9.5 M tris) old | new | Stress (1,995 / 11,228, 1.2 M) old | new |
|---|---|---|---|---|
| meshes (`_new_mesh`) | 4.51 | **1.80** | 0.92 | 0.31 |
| build (meshes + objects, cache read) | 7.40 | **4.76** | 2.99 | 2.46 |
| sorting (`apply_rules`) | 2.86 | **1.38** | 4.09 | 1.32 |
| bounds (`update_bounds`) | 0.22 | 0.15 | 0.21 | 0.19 |
| structure / surroundings | 0.16 / 0.85 | 0.13 / 0.75 | 0.14 / 0.79 | 0.12 / 0.75 |
| welds from the file (`weld_cad.after_import`, not this task) | 33.6 | 33.0 | 28.4 | 28.4 |
| **Blender side, whole** | **45.7** | **40.7 (−5.0)** | **37.2** | **33.9 (−3.3)** |

Bounds were already fast on today's `main` (0.2 s, the study's 1.2 s included an update since made elsewhere); the gain
is meshes −2.7 s and sorting −1.5 s on Big. Reader on this machine (3 helpers): Big 51.1 s (read 22.1, meshing 27.6),
Stress 65.4 s (read 44.5, meshing 19.3).
**Model update, Stress A → B** (1,899 of 1,995 meshes reused): 128.3 s before, 129.5 s after – no gain (its own build
is 5 s and mostly reused). A profile shows where it goes: **52 s** `weld_cad._parts_of` and **50 s**
`bpy.data.batch_remove` of the old revision's objects in `reimport.py` (see open points).
The Heavy line ran in the PC check's Heavy mode, scaled down (bpy module, no graphics card: the Workbench picture still
rendered, 4.8 s): OK, all metrics written. Tests run locally: `test_build_speed.py`, `test_importer.py`,
`test_faces.py`, `test_rule_sets.py`, `test_copy.py`, `test_blender.py`, `test_material_picker*.py`,
`test_queue_schemes.py`, `test_queue_fixes.py`, `test_fixes_0120.py`, `test_surroundings.py`, `test_pccheck.py` – all
pass; GitHub runs the rest.

**The owner's line:** PC check > Heavy – the line "Big machine: where the import time goes"; paste its numbers to the
lead.

**GitHub runs:** 5 full runs. 1: red – Windows part B: the Solid-view picture of the new line, drawn inside the PC
check's own Blender without a graphics card, crashed Blender (Linux under xvfb drew it fine); fixed: the first draw is
measured only when the check found a graphics card (the owner's PC has one), else one line says so. 2–4: green (or cancelled), but 0326,
0346, 0352 and 0369 took 0.2.262 … 0.2.265 meanwhile; 5: after merging main, 0.2.266.

**Open points / follow-up tasks:**
- **The biggest import cost found is outside this task: the weld check after an import walks the parts with
  `ob.children`, which Blender works out by looking at every object in the file – once per part, so it grows with the
  square of the part count: 28–33 s of the ~35–45 s Blender side on Big and Stress, and 52 s of a 128 s model update.**
  A parent → children map made once (or `children_recursive` of the root) should bring it to well under a second.
  `blender/weld_cad.py` (`_parts_of`) is the Welds lane: for **0368** (running) or a follow-up.
- Model update: `bpy.data.batch_remove` of the old revision's ~11,500 objects took 50 s (2 calls) in
  `reimport.py` (the end of `_carry_over`: objects, then meshes). Worth a look in the Import lane after 0340 (e.g. remove
  the meshes first, or unlink the collection before removing).
- 0301 #2 (split transfer): decide from the owner's numbers of the new line.
- Model-update gains from this task stay small while 0324 reuses most meshes.
