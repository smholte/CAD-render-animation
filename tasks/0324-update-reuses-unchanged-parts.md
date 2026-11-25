# 0324 – Faster model update: unchanged parts are kept, only changed parts are meshed and built again

**Who:** worker · **Status:** running · **Branch:** `task/0324-update-reuses-unchanged-parts`
**Started by:** lead, 25 Nov 2026 (owner 00:3x picked "Faster model update" as the first of 0315's four slow places)
· **Model:** Opus · effort High
**Area:** Import lane – `importer/step_reader.py` (a shape hash per part, written into the cache), `importer/runner.py`
(reuse of the old cache's meshes), `blender/reimport.py` (the update's own Blender work), `blender/build.py` (only where
the update builds), new `core/part_hash.py` (no Blender), their tests; additive: `pccheck/stress.py` (the `update`
line's limit and numbers), the guide's model-update section, `core/functions.py` (`changed=`), CHANGELOG.
**Not:** the matching rules (what counts as "the same part" stays exactly as today), mesh import (glTF / OBJ / FBX)
updates, the split transfer and the Blender-build speed-ups of study 0301 (#2, #1 – later tasks), cable meshing (0325).

## Goal

A model update where only a few parts changed takes a fraction of a fresh import, not longer than one. Unchanged parts
are not meshed again and their Blender meshes are reused; the result is the same as today's full update.

## Background

- **0315's Stress run** (4-core web machine, `tasks/0315-stress-model-10k-parts.md`): the full stress topside (11,228
  parts) → `--revision B` (103 changed parts, 0.9 %, same names) – **model update 131 s**, a fresh Normal import
  100 s. Every part is read, meshed and built again, then matched to the old ones (`reimport.update_model` →
  `match`, `_carry_over`). Two kinds of waste: (a) meshing + Blender meshes of the ~99 % unchanged parts, (b) the
  ~31 s the update takes beyond a fresh import (matching, set aside / put back, carry-over, removal of the old
  objects) – not measured per stage yet.
- **Study 0301 #3** (branch `task/0301-study-faster-import`, report `tasks/0301-study-faster-step-import.md` section B
  point 3 and table C; prototype `tools/import_timing/step_hash.py` on that branch – read it, do not merge the branch):
  a hash of each part's shape entities with the entity numbers left out found **600 of 601 parts unchanged** after a
  change that shifted every entity number; 1.8 s per file on Heavy, ~8 s on Big in plain Python (run it in a helper,
  beside the parse). **Risk:** a false "unchanged" keeps an old shape – the hash must cover the whole shape (all
  entities a part's shape reaches, with their numbers), and any doubt means "changed".
- **Not known:** whether Inventor writes an unchanged part's entities the same way in a new export. At the start, ask
  the owner **once** (one line starting "WAITING FOR YOU:", branch pushed first) whether he can attach two STEP
  revisions of one of his own models – **attach only, never committed, nothing of them in the repository or the
  report except counts and seconds**. If not available within ~15 min, go on with the test makers and write a
  check step for him in the report (what to import, what number to paste back).
- Revision makers that exist: `tools/make_test_stress.py --revision B` (also the small model,
  `FRESING_PCCHECK_STRESS_SMALL=1`), and `--revision` in `make_test_crane`, `make_test_cylinder`, `make_test_linkage`,
  `make_test_flex`, `make_test_paths`, `make_test_faces`, `make_test_decals`, `make_test_weldment`, `make_test_mesh`.
  Existing update tests: `tests/test_model_update.py`, `tests/test_model_update_cables.py`.
- The cache key is path + size + mtime + quality + `CACHE_VERSION` (`runner.cache_key`). A new revision gets a new
  cache; the old project knows its old cache folder (find where; if it can be gone, the update falls back to today's
  full path).

## What to do

1. **Measure first:** split the 131 s of the stress A → B update into stages (reader parse / transfer, meshing,
   cache write, Blender build, matching, carry-over, removal of the old, redraw). Write the table into the report
   before changing anything.
2. **Shape hash per part** in the reader (a helper, beside the parse – it must not add to the import's wall time
   on 24 cores by more than ~1 s): stored in the cache (raise `CACHE_VERSION`; an old cache without hashes = today's
   full update, no error). Quality, tessellation options and units are part of the key: a Normal → Fine change or a
   different unit re-meshes everything.
3. **Reuse:** on an update, parts whose hash is in the old cache take the old cache's mesh arrays (no meshing) and,
   where the matched old Blender object already has that mesh, keep the Blender mesh datablock too. Changed and new
   parts go the normal way.
4. **Cut the update's own overhead** from step 1 where it is cheap and safe (e.g. matching only what is not already
   paired by name + hash, no build-then-delete of objects that stay). Bigger redesigns: propose in the report, don't
   build.
5. **Oracle:** a hidden switch `FRESING_UPDATE_FULL=1` keeps today's path. A test runs every revision maker above
   both ways and checks the results are the same: per object the mesh (vertex / face counts, bounds, a hash of the
   arrays), the tree, names, looks and material groups, joints, poses, animation steps, flex parts, welds, decals,
   painted faces, hidden / faded states, the clash check's rows.
6. **A changed part is never kept:** a test changes one face of one part slightly (0.1 mm, same entity count) and
   checks it is re-meshed; one that swaps two identical parts' places; one that changes only a part's colour or
   CAD material (shape same → mesh reused, look updated).
7. Stress line `update`: same name, new limit from your numbers, the line's text shows "N of M parts reused".
   Guide (model update section): one or two sentences – unchanged parts are kept, so updates with few changes are
   fast; `help.<model update anchor>` `changed=`. CHANGELOG, version.

## Done when

- [ ] Report has the stage table before and after (stress full A → B on the web machine; small model too)
- [ ] Stress full A → B update clearly faster than a fresh Normal import – aim ≤ ~45 s on the web machine (today 131 s),
      or the report says why not and what stands in the way
- [ ] A fresh import is not slower than before (± 3 %, Normal and Draft, stress full)
- [ ] Oracle test: both ways give the same result on every revision maker; the "never kept" tests of step 6 pass
- [ ] Old projects (made before this version) update as before, with a full read the first time
- [ ] Owner's two revisions: measured, or a check step for him in the report
- [ ] Tests added/updated; full suite passes; Stress workflow (`stress.yml`, full size) green once
- [ ] Report below filled in, merged, released

## Not in this task

- 0323 (welds from the CAD file, waits for 0320) will later add a hook in `build.py` and in `reimport.py` (model
  update). If it runs beside you, whoever merges second updates their branch to `main`; keep your changes to those two
  files as small and clearly separated as you can.
- 0301 #1 (Blender build via the attribute API) and #2 (split transfer): separate tasks after the owner's Stress / PC
  check numbers. 0325 lighter long cables, 0326 faster joint drag, 0327 clash-check memory: reserved, briefed after the
  owner's Stress run.
- Never the owner's STEP files, part names, renders or numbers that reveal them in the repository.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25 Nov 2026 · branch `task/0324-update-reuses-unchanged-parts` · 0.2.243

**What changed:**
- **Mesh key per unique part** (`core/part_hash.py`, no Blender): blake2b over OpenCascade's binary copy of the part's
  shape (`BinTools`, the bytes the meshing helpers already get – every face, edge, point, surface, tolerance in mm;
  no STEP entity numbers) + Detail (deflection, angle, the facets table, quality name), the standard-part flag, the
  face colours and their appearance names, `CACHE_VERSION`. Stored per mesh in `tree.json` (`key`); **CACHE_VERSION 8**.
  A part with no binary copy gets no key (meshed, never taken). Not in the key: name, part colour, CAD material, place
  (they live on the objects).
- **Reader** (`step_reader.py --reuse <old cache>`): parts whose key is in the old cache take its arrays (points,
  normals, triangles, face colours, face starts, axes) instead of being meshed; the old cache is read lazily and every
  array is checked (shapes, counts) – anything odd = meshed. Stats `parts_reused`, `seconds_hash`. The reader ends with
  `os._exit(0)` once the cache is written (freeing OpenCascade's document took ~3 s on 11,228 parts).
- **Runner / button** (`runner.reuse_dir_for`, `ops_import`): an update passes the old root's `fr_cache` only when it
  is a valid STEP cache of this version and the same Detail; else (old project, cleared cache, mesh model, other
  Detail) the full path as before. `FRESING_UPDATE_FULL=1` (hidden) = today's full path everywhere.
- **Build** (`build.py`): `mesh_pool` collects the old model's part meshes that carry `fr_mesh_key` under the name they
  were made with (a copy – milling's own mesh – or a renamed mesh is left out); a new mesh whose Blender key (reader key
  + the part's dominant copy colour when it has coloured faces) matches takes the old mesh of the same name first, each
  once, after a check of counts and points. `faces.carry_over` and `decals.carry_over` handle a kept mesh (sets and
  decals are already on it; decal objects only for the new parts).
- **Cheap cuts** (step 4): the new revision is built into a collection outside the scene and linked once the old
  model is taken apart (the joints' CAD pose updates the scene several times); the reader's exit; the kept-mesh check
  reads only points. Not done (bigger, below): matching on cache nodes, keeping old objects.
- **Stage clock** on every update (`reimport._Clock`, root `fr_update_stats`), `build.LAST_TIMES`; `tools/update_timing.py`
  (bpy module, or the real app under xvfb with each step in its own timer call). Stress line `stress.update`: text
  "N of M parts reused", metrics parts reused + build new / take apart / remove old, expected 60 s, limit 240 s.
  Guide (Update to a new revision, step 1), `import.update` `changed="0.2.243"`, CHANGELOG.

**Tested and measured** (4-core web machine, Xeon 2.1 GHz; the stress topside made by `tools/make_test_stress.py`,
11,228 placed / 1,995 unique parts, revision B: 103 placed / 96 unique parts changed; Normal; the real app under
xvfb, the reader and the Blender part timed as the button runs them, after the crane / davit / door joints):

| stage (s) | before (full path) | after |
|---|---|---|
| reader: parse + transfer (one core) | 44.7 | 44.8 |
| reader: meshing (3 helpers) | 110.3 (all 1,995) | 20.5 (96; incl. re-routed cables) |
| reader: hash + old cache | – | 0.5 |
| reader: start / exit / polling | 33 | 10 |
| build new (meshes / objects) | 14.1 (8.8 / 5.3) | 7.9 (2.1 / 5.6; 1,899 meshes kept) |
| take apart (joints, cylinders, mechanisms, cables) | 7.8 | 5.1 |
| records + match | 2.1 | 2.1 |
| set aside + joints and set-up | 3.8 | 3.8 |
| **remove old 11,540 objects** | 15.1 | 13.1 |
| sort, structure, bounds, surroundings, rest | 3.2 | 2.5 |
| **model update, total** | **236.0** | **111.5** |
| fresh Normal import of B, same app | 141.4 | 140.2 |

In Blender as a Python module (no event loop) the same update took 221.5 s before (remove old 56 s) and 155.8 s with
reuse before the cheap cuts. Small stress model (1,643 / 332 parts, 14 unique changed), real app: 16.8 s full → 11.9 s
(318 reused); fresh import 13.0 s.
**Fresh import not slower** (the reader alone, the stress model's revision B, old `main` vs new, two rounds each):
Normal 130.2 → 128.4 s, Draft 72.9 → 72.9 s.
**Reader check:** on the small model the 14 parts not reused were exactly the 14 the maker changed; the kept arrays were
bit for bit those of a full read.
**Tests:** `tests/test_update_reuse.py` – the oracle: crane, cylinder, linkage, flex hoses, flex avoid, paths (with
its animation's clash rows), faces, decals, weldment and the glTF crane, each updated the full way and the fast way
from the same project with the same work on it (painted faces, a hidden part, a decal, a joint, the maker's own set-up)
– both the same per object (mesh counts, bounds, a hash of points / triangles / normals, material indices, mesh props,
tree, world matrices, colours, groups, slots, decals) and in joints, states, animations, report, decal objects, hoses,
cables, welds; the never-kept tests (a face 0.1 mm higher with the same entity count → meshed again; two identical
parts swap places → both kept, in their new places; only a part colour changed → kept, look updated); an old cache
without keys / of version 7 and another Detail → everything read; an old project (meshes without keys) → full first
update, reuse on the next. `test_part_hash.py`; `test_model_update.py` + a failure while old meshes are being taken
(project as it was). Waycover's A/B are two different models (nothing to reuse): left out. Locally 293 + 137 + 65 tests
of the touched areas passed.
**GitHub:** branch run 45529614817 green (full mode, first try). **Stress run (stress.yml, full size) 45529613952 green:** `stress.update` model update **70.1 s** (0315 on the same runner type: 131 s), 1,899 of 1,995 unique parts reused, build new 4.9 s, take apart 2.9 s, remove old 9.8 s; a fresh Normal import there 109 s.

**Owner's two revisions:** not attached in this session. Check step for the owner (counts and seconds only):
1. Install 0.2.243 (**Update now**). Open a project of one of your models, imported **before** 0.2.243, and do
   **Update to new revision…** with the same file once (this first update reads every part, as before).
2. Export a new revision of that model from Inventor (change one or two parts), then **Update to new revision…** again.
3. In the side panel's **1 Import** the report says how many parts were kept. Send the lead: the total parts, and the
   number in the status line / PC-check Stress table "parts reused" – or simply how long the second update took and
   how long a fresh import of the same file takes. If "reused" is near the number of unique parts minus the changed
   ones, Inventor writes unchanged parts the same way.

**Open points / follow-up tasks:**
1. **≤ 45 s is not reachable in this task:** the STEP parse + transfer alone is 45 s on this machine (one core) and
   is the same for every update; meshing the 96 changed parts is 20 s, most of it the re-routed B-spline cables (0325).
   After 0301 #2 (transfer only what changed) the read would shrink too.
2. **Deleting the old objects costs 13–15 s, and it is Blender's own:** `bpy.data.batch_remove` of N objects costs
   O(N × objects in the file) – per deleted object Blender walks every object (`libblock_remap_data_postprocess_object_update`,
   the metaball check) and the window manager's queue of notices (`WM_main_remove_notifier_reference`; the queue holds
   ~3 notices per object built in the same operator). Measured: 10,000 objects deleted next to 12,000 others 13–15 s,
   alone 1.3 s; in a background script without an event loop (PC check) the queue is not cleared and the same delete
   took 56 s. Building the 11,228 new objects next to the old ones also costs 5.6 s instead of 1.8 s (unique names).
   **Proposal (a task of its own, Opus · High):** an update that **keeps the old objects of unchanged parts** – match
   cache nodes to old objects first, create objects only for new / changed parts, delete only the missing ones; every
   `after_model_update` hook then gets identity pairs and needs checking; the all-or-nothing rollback becomes an undo of
   in-place changes. Expected: −13 s delete, −6 s build, −3 s records / set aside on the stress model.
3. Smaller, not done: `cad_pose` runs 7 times in the take-apart (each ~0.7 s on 11,000 parts) – one outer CAD pose for
   the whole take-apart; `records` reads every object's box in Python (1.8 s) – NumPy.
4. A whole-model copy (0293) shares meshes with its original; after a fast update both keep sharing the kept meshes (as
   before the update), where the full path gave each its own. Painting a shared part paints both, as it already did.
