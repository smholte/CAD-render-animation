# 0324 – Faster model update: unchanged parts are kept, only changed parts are meshed and built again

**Who:** worker · **Status:** open · **Branch:** `task/0324-update-reuses-unchanged-parts`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
