# 0289 – Import: a dropped file shows in 1 Import like the button; "Imported models" fold with Import again; Up axis changeable after import

**Who:** worker · **Status:** open – can start · **Branch:** `task/0289-import-drop-cache-up-axis`
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

- [ ] Tests for all three (a drop through the FileHandler path in a 3D-view context; Import again from the cache with
      and without a changed file; up axis Z → Y → Z with joints, pose, Build, save + reopen, model update)
- [ ] Real-app test of the drop and of Import again; PC check line(s) `import.drop`, `import.again`, `import.up_axis`;
      tour stop; function entries + guide anchors (`since=`); guide text + pictures of 1 Import
- [ ] Tooltips on every new button; full suite + GitHub run green; report filled in; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
