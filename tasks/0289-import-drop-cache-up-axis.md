# 0289 – Import: a dropped file shows in 1 Import like the button; "Imported models" fold with Import again; Up axis changeable after import

**Who:** worker · **Status:** running · **Branch:** `task/0289-import-drop-cache-up-axis`
**Started by:** lead, 23 Nov 2026 (owner's list "List of changes to Fresing render", 23 Nov 19:39, three points:
"When drag and dropping a file into the Fresing window, the import menu doesn't show that, but it should. It should
show the same as when you normally import from the import button." – "When in 1. import I want there to be a fold menu
where all the imported cached models are in and each with an import again button." – "When importing a model you can
select y and z, allow a user to change this after import as well for a model.") · **Model:** Opus · effort Medium
**Area:** Import lane – `blender/ops_import.py` (the two FileHandlers, the import operators, `finish_import`), the
1 Import panel (`FRESING_PT_import` in `ui.py` – only that panel), small read-only helpers for the import cache
(`importer/` or a new `core/import_cache.py`), `logic.set_up_axis`, `props.py` additively; tests, real-app test, PC
check line, tour stop, function entries, guide + pictures, CHANGELOG.
**Not:** the STEP reader's reading and meshing (`importer/step_reader.py` – study 0301), 2 Structure and the right-click
menu (0292), `CACHE_VERSION` (unless the cache really changes – then bump it, CLAUDE.md 6).

## What to do

1. **Drop = button.** Dropping a STEP (or mesh) file on the 3D view or the Outliner must look and work exactly like
   Import STEP… in 1 Import: the section opens, the panel's Detail and Up axis are used, the progress line with Cancel
   shows, then the model's line, the same messages and the same undo step. Find why a drop differs today
   (`FRESING_FH_step` → `fresing.import_step` with a file path – probably run without the panel's invoke, or from
   another area so the panel is not told / not redrawn) and fix it for every drop place. Several files dropped at
   once: import them one after another, or say plainly that one at a time is taken – pick one and say it.
2. **"Imported models" fold** in 1 Import (folded by default; header state "N in the cache"): every model in the import
   cache, newest first – name, file, date, parts, size on disk; a file that is gone or moved greyed with "file moved".
   Each row: **Import again** (adds it to this project; unchanged file = from the cache, no reading; changed file =
   reads it again and says so), **Show in folder**, **Remove from cache** (frees the disk space; asks first). A search
   field when there are more than about 10. Say in the guide where the cache lives and how big it may grow.
3. **Up axis after import.** On the model's line (or under More): **Up axis: Z up / Y up** for that model. Changing it
   turns the whole model at its root as the import would have; everything made after the import (joints, cylinders,
   poses, saved scenes, cameras riding on it, labels, cutaway) keeps working – prove it on the test crane with a joint,
   a pose and a built animation: after the change, Build again gives the same motion, turned. One undo step. A built
   animation: the Build is taken off with "Build again" said. A model update (new revision) keeps the chosen axis. The
   panel's own Up axis stays the default for the next import.

## Done when

- [x] Tests for all three (a drop through the FileHandler path in a 3D-view context; Import again from the cache with
      and without a changed file; up axis Z → Y → Z with joints, pose, Build, save + reopen, model update)
- [x] Real-app test of the drop and of Import again; PC check line(s) `import.drop`, `import.again`, `import.up_axis`;
      tour stop; function entries + guide anchors (`since=`); guide text + pictures of 1 Import
- [x] Tooltips on every new button; full suite + GitHub run green; report filled in; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus · Medium), 23 Nov 2026. Version 0.2.216.

**What changed:**
- **Drop = button.** Why a drop differed: the FileHandler's invoke went straight to execute and nothing opened or
  redrew 1 Import – with the sections folded (every start) or another tab chosen, or the side panel hidden, the
  progress, the model's box and the message never showed; the panel also was not redrawn while the job ran (only the
  status bar). Now `ops_import._dropped` → `show_import_panel` (1 Import opened, tab back to All, side panel shown on
  the Fresing tab – only once the view was drawn, `editors.settled`), the modal redraws the panel every tick and at the
  end. Same operator, Detail/Up axis from the panel, same message, same undo step. Several files: **the first is
  imported and the panel says so** (chosen over a queue: one modal job at a time, as today). Both handlers (STEP, mesh)
  and both places (3D view, Outliner).
- **Imported models** fold (`core/import_cache.py`, no Blender: lists `<cache>/*/tree.json` heads, cached per folder by
  the tree's stamp; states ok / changed / moved / old): name, parts, detail, size, date, file; Import again
  (`again=` on `fresing.import_step` / `fresing.import_mesh`: unchanged or moved file = the stored copy, nothing read;
  changed file = read again with the same detail / mesh options, message says so), Show in folder
  (`fresing.cache_show`), Remove from cache (`fresing.cache_remove`, asks; never outside the cache folder); search
  from 11 on; the total on disk. `ui.fold` got `state=` (the title row's grey state).
- **Up axis after import**: Z up / Y up on each model's box (`fresing.model_up_axis`, UNDO; `logic.up_axis_of` reads
  it from the root's rest matrix, so older projects and model updates need nothing stored; `logic.change_up_axis`
  turns the root about its own origin, rest matrix too; with one model in the project its free cameras turn with it;
  a built animation is taken off, "Build again"). Not for a lifting-plan crane, not in the Client view.
- Tests `tests/test_import_again.py` (14), real-app `tools/ui_test_import_again.py` (18 checks, group callouts),
  PC-check lines `import.drop`, `import.again`, `import.up_axis` (MIN_LINES_FULL 126), tour set + stop
  `import` / `import_again` (MIN_LINES_TOUR / tour 98), function entries + guide anchors, guide text, pictures
  `panel_1_import.png` (new) and `panel_1_imported_models.png`.

**Tested and measured** (4-core web machine, test crane): the 14 pytest tests pass – drop with the panel's choices,
two files, Import again unchanged (the reader is never started) / changed / moved / mesh, Remove, Up axis Z → Y → Z
with a joint, a pose and Build (the boom's tip at frames 1/20/40 within 0.1 mm of the turned motion, back the same),
save + reopen + model update to revision B keep Y up. Real-app test 18/18 (16 s): the drop through the real invoke
(RUNNING_MODAL, 1 Import opened, tab All, side panel shown, progress, Draft + Y up, message), Import again, Up axis +
one Undo, Remove. PC check lines 3/3 in 7 s. Cache size: the test crane takes 244–390 KB (5,890 triangles, ~40 bytes
per triangle) – the guide's "1 M triangles ≈ 40 MB" is that ratio, not a measurement on a big model.

**Open points / follow-up tasks:**
- Several dropped files are not imported one after another (the first only, said plainly).
- A real drag from Explorer cannot be simulated under xvfb: the real-app test calls the operator the way the
  FileHandler does. The owner's check below covers the real drop.
- The cache has no size limit of its own (as before); the fold shows the total.
- Cameras do not turn with a model when the project holds two or more models (they may look at the other one).

**Owner's check on your PC:**
1. Start Fresing Render, close the start window. Leave every section folded.
2. Drag a .step file from Explorer onto the 3D view. You should see: the side panel opens on **1 Import** with the
   progress bar, then the model's box and "Imported <file>".
3. In the model's box click **Y up**, then **Z up**: the model lies on its side, then stands again. Ctrl+Z turns it back.
4. Open the fold **Imported models**: your file is at the top. Click **Import again**: a second copy is in at once.
5. Click the bin on a row, then **Remove**: that row is gone.
