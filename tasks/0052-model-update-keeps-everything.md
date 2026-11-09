# 0052 – Model update keeps everything: joints across two models, labels, sharp spot, all-or-nothing

**Who:** worker · **Status:** done (0.2.41) · **Branch:** `claude/relaxed-ride-rve378`
**Started by:** lead chat, 9 Nov 2026 (bug hunt 0045 rows 1, 2, 6, 20a)
**Lane:** Motion – `blender/reimport.py` (`update_model`), `blender/joints.py`, cylinders, mechanisms and way-cover
code where they share the "belongs" / rebuild-from-specs pattern; label and focus re-pointing inside `reimport.py`
only (`callouts.py` / `cameras.py` read-only unless a one-line helper is needed); tests; guide "Update the model"
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as 0051 (Machining), 0053 (Quality & delivery) and 0055 (Looks). Do not touch machining,
chips, G-code, decals, `updates.py`, `update_helper.py`, `project_lock.py`, `props.py` `_group_renamed`,
`handlers.py`, `queue.py`, `ops_motion.py` queue code or `animation.py` (0041 and 0054 come later there).

## Goal

Updating a model never silently drops work: joints, cylinders and mechanisms that link two models stay, labels and
the camera's sharp spot stay on their parts, and an update that fails half-way leaves the project as it was.

## Background (proof and suggested fixes: `tasks/0045-bug-hunt.md`, rows 1, 2, 6, 20a)

- **Row 1 – joint across two models deleted.** A crane joint whose base is a part of the ship model: updating the
  ship removes the joint ("its moving parts are no longer in the model"); the other way round the joint loses its
  base. Look the joint's objects up over all models (by object), and dissolve only joints whose moving parts are in
  the updated model. Test the same for cylinders, mechanisms and way covers across two models (not tested in 0045,
  probably the same pattern).
- **Row 2 – labels cut off their parts.** `FRCallout.part` points at the deleted old object → None; labels drop out
  of renders without a note. The sharp spot's `CHILD_OF` target too. Re-point both through the uid mapping in step 6
  of `update_model`; a note in the update report for labels whose part is really gone.
- **Row 6 – not all-or-nothing** (suspected). Joints, cylinders and mechanisms are dissolved before
  `build.build(cache_dir)`; any error after that loses the specs. Build the new model first and dissolve after, or
  wrap the update and rebuild from the specs on the old root when it fails. Test with a forced error (damaged
  `meshes.npz`, or a monkey-patched build that raises) → project unchanged, a clear message.
- **Row 20a – making a joint takes 0.6–0.8 s** (three full view-layer updates). One update inside `cad_pose`, if it
  stays small. Measure on the Heavy machine before/after.

Old projects: the 0045 report opened 0.2.20 / 0.2.24 / 0.2.30 projects fine and updated `test_crane_a` → `b`
keeping the joint; keep that test passing.

## Done when

- [x] Rows 1, 2, 6 fixed, each with a test from the row's proof; row 1 also for cylinders, mechanisms, way covers.
- [x] Update report names labels whose part is gone.
- [x] Row 20a if small, time before/after.
- [x] Model update time on the Heavy machine (`pccheck/heavy_scene.py`, was 17.3 s) not slower by more than 5 %.
- [x] Guide "Update the model" mentions what is kept; tooltips if anything visible changed.
- [x] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [x] Report filled in; `TASKS.md`: 0052 done, 0054 "open – can start".

## Not in this task

Two copies of the same STEP sharing part IDs (row 11 → 0056). The queue (0054). Decals on the milled block (0051).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 9 Nov 2026 (branch `claude/relaxed-ride-rve378`, the session's assigned branch
instead of `task/0052-…`). Version 0.2.41.

**What changed:**
- **Row 1 – links between two models.** Specs name parts outside the updated model by object (`"@<name>"`,
  `joints.spec_key`; looked up by `joints.PartLookup`) – joints (members, base), cylinders (barrel, rod, stages, pin
  carriers), mechanisms (links, base). Every joint/cylinder/mechanism that touches the updated model comes apart and is
  rebuilt; joints of another model riding on one of them come along (whole stack). Way covers follow from the joints.
- **Row 2 – labels and sharp spot.** `reimport._repoint`: `FRCallout.part` and the focus marker's `CHILD_OF` target go
  to the matching new part; for a gone part the label is switched off with a report line ("Label 'X': its part … is
  not in the new model …"), the sharp spot stays where it was (constraint removed, report line).
- **Row 6 – all or nothing.** `update_model` builds the new revision first (fails → partial objects removed,
  "Nothing was changed"). Then the old model is taken apart, matched and carried over; its collection is unlinked
  from the scene but kept until joints, mechanisms, cylinders, milling, CNC, way covers, labels and saved states
  are done on the new one. Any error before that point: what was built on the new model comes apart, the new model is
  deleted, the old collection goes back and the set-up is rebuilt on the old parts (labels/spots pointed back,
  decals made again). `reimport.UpdateFailed`; the import operator shows "Model update failed: …" and returns
  CANCELLED. After the old model is deleted only `apply_rules`/tree/bounds/world remain.
- **Speed.** Rebuilt joints are made in one CAD pose (`joints._batch`) instead of entering and leaving it per joint
  (two full scene updates each).
- **Row 20a not done:** of the three scene updates when making a joint, the middle one costs 0.0 s already (nothing
  changed); the other two are the pose going to CAD and back, needed for correct positions right after. Measured
  0.44 s per joint (main) and unchanged.
- PC check line `model.update_safe` (since 0.2.41, `MIN_LINES_FULL` 39); guide "Update to a new revision" says what
  is kept and what a failed update does; no new buttons (no tooltips).

**Tested and measured** (4-core web session, bpy module):
- New `tests/test_model_update.py`, 14 tests: joint across crane + machine (update either model), a stack across the
  two, cylinder (barrel pin on the machine frame), mechanism (machine lamp on the scissor platform), way cover (machine
  cover on the carriage), labels + sharp spot follow, gone part → note, sharp spot on a gone part stays; forced
  failures half-way through the build, after the joints came apart, during the rebuild, at the last step (project
  snapshot identical: objects, meshes, collections, joints with values/members/bases, cylinders, labels, sharp spots,
  poses), a cylinder in drive mode given back, a damaged cache called directly → `UpdateFailed`. Each then updates
  fine on the next try.
- Existing update tests (phase 2, stacks, couplings, cylinders, mechanisms, way covers, decals, faces, milling, G-code,
  air): 49 + 19 pass. PC check lines `model.update`, `model.update_safe` OK.
- Heavy machine (`pccheck/heavy_scene.py`, 2,992 placed / 600 unique, 10 joints), model update of the same file:
  **main 16.9 / 17.0 s → 14.5 / 14.9 s** (two runs each, same machine). Before the batching it was 22–26 s (old model
  kept during 20 per-joint updates at 0.36–0.42 s each instead of 0.22 s): the batching fixed that.
- GitHub: 1 run on the branch (full, green, 14.1 min; no version clash), then `main` fast-forwarded: reuse run
  42618717594 published v0.2.41, the old-version update check on Windows passed, offered to the apps.

**Open points / follow-up tasks:**
- 0054 is set to wait for 0041 only (both change `animation.py`), not "open – can start" as the Done-when list said: 0041
  has not run yet.
- A failure in the last steps after the old model is deleted (sorting rules, tree, bounds, world) cannot be undone;
  the message says to reopen without saving. These steps did not fail in any test.
- After a rolled-back update, a built animation is off (Build again), as after any model update; the old collection
  is linked back at the end of its parent's list (outliner order).
- Leftover branch for the owner to delete: `claude/relaxed-ride-rve378`.
