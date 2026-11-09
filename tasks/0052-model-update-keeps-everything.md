# 0052 – Model update keeps everything: joints across two models, labels, sharp spot, all-or-nothing

**Who:** worker · **Status:** open – can start · **Branch:** `task/0052-model-update-keeps-everything`
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

- [ ] Rows 1, 2, 6 fixed, each with a test from the row's proof; row 1 also for cylinders, mechanisms, way covers.
- [ ] Update report names labels whose part is gone.
- [ ] Row 20a if small, time before/after.
- [ ] Model update time on the Heavy machine (`pccheck/heavy_scene.py`, was 17.3 s) not slower by more than 5 %.
- [ ] Guide "Update the model" mentions what is kept; tooltips if anything visible changed.
- [ ] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0052 done, 0054 "open – can start".

## Not in this task

Two copies of the same STEP sharing part IDs (row 11 → 0056). The queue (0054). Decals on the milled block (0051).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
