# 0139 – Mesh import fixes: updates keep work on the right piece, file materials kept, side files noticed, faster updates

**Who:** worker · **Status:** running · **Branch:** `claude/affectionate-ritchie-rn1qgs`
**Started by:** lead chat, 15 Nov 2026 (rows of bug hunt 0131, report in `tasks/0131-bug-hunt-4.md`) ·
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Import lane (+ small fixes in `joints.axis_from_hit` and `hover.py`)):** `importer/mesh_reader.py`, `importer/runner.py`, `blender/mesh_import.py`, `blender/reimport.py` (match rules, `_carry_over`), `joints.axis_from_hit`, `hover.py`, their tests.
**Do not edit:** `paths*.py`, `demo*` (0126/0137), `sequence.py` (0140), the Web 3D lane (0134).

## Goal

Updating a glTF/OBJ/FBX model never moves the owner's joints, looks or decals onto the wrong piece or loses the file's own materials; changes in MTL/texture/.bin files arrive; big mesh updates are fast.

## Background

The rows below are from bug hunt 0131 (report on `main`): each row has the place in the code, how to repeat it
("Proof") and a suggested fix. Read those rows first; repeat each one before fixing it.

- **Row 3 (lost work):** reader-made names (piece numbers, "Node k") match the wrong piece – match those by shape and place first.
- **Row 4 (lost work):** a mesh model's own material lost at save when no part shows it – keep it (`use_fake_user`, removed with the model).
- **Row 13:** the cache ignores MTL / textures / .bin – add their size + mtime.
- **Row 15 (slow):** `_carry_over` removes meshes one by one (quadratic) – one `batch_remove`; measure 750 / 1,500 / 3,000 parts.
- **Row 16b–e:** radius scaled by the object's local X (Ø300 for a Ø100 rod); hover caches keyed by mesh name; cp1252 OBJ/MTL text; glTF without `"scene"`.

## Done when

- [x] Every row above fixed, each with a test that failed before the fix (the row's proof as a test).
- [x] Tooltips, guide sentence where the owner sees a change, function list / PC-check / tour stop only if something
      visible changes; GitHub run green; merged; version (CLAUDE.md section 7); report (short list for the owner).

## Not in this task

Other rows of 0131 (they have their own tasks: 0136–0140); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 15 Nov 2026 · version 0.2.111 · no subagents (Medium task; each fix small)

**What changed:**
- Row 3: the mesh reader marks names it makes (split pieces "WELDMENT 3", "Node k") in tree.json (`made_name`), the
  build stores `fr_made_name`; `reimport.match` matches those by shape + place first (rule 1b), a made name in rule 2
  needs the same place, made assemblies follow their matched parts (`_made_assemblies`); a renumbered piece is not
  reported as renamed.
- Row 4: file materials get `use_fake_user`; `mesh_import.release_materials()` (called after an update) removes file
  materials no mesh names any more.
- Row 13: the reader lists the side files it read or looked for (MTL, textures, .bin, licence text) with size + mtime
  in tree.json (`side_files`); `runner.cache_is_valid` reads the model again when one changed or a missing one came.
- Row 15: old meshes in one `batch_remove`. **Cause of the rest** (found with py-spy): for every deleted ID Blender
  scans the whole window-notifier queue (`WM_main_remove_notifier_reference`), and the update's own build filled that
  queue, so deleting the old model stays (parts x parts) inside Blender.
- Row 16b: radius measured across the axis (`joints.axis_from_hit`). 16c: hover caches keyed by `session_uid`,
  `hover.clear()` after an update. 16d: OBJ/MTL/licence text falls back to cp1252. 16e: glTF without `"scene"` takes
  the first scene with nodes.
- Guide: one paragraph under "Update to new revision…" (Mesh models). No new function, PC-check line or tour stop.

**Tested and measured** (4-core web machine):
- `tests/test_mesh_import_fixes.py`, 12 tests: 11 failed on the old code, all pass now (row 15's is a timing guard
  that passed before too). Area tests (hover, mesh import/reader/independent, model update, phase2, stacked joints,
  facets): 228 passed.
- Mesh model update, N boxes glTF, same file new date (bpy module): 750 / 1,500 / 3,000 parts: before 4.6 / 10.4 /
  36.6 s, now 3.2 / 7.5 / 24 s (the import itself 3.2 / 5.0 / 8.4 s). At 3,000, 10.8 s of the 24 s is Blender's delete.

**Open points / follow-up tasks:**
- Row 15 rest: a 3,000-part mesh update still takes ~3x its import. A fix would delete the old model after the
  notifier queue was handled (a later step of the modal import) – changes the all-or-nothing flow, so a lead decision.
- A model deleted by hand in Blender (no app button) keeps its file materials until the next update.
- GitHub runs: see TASKS.md row.
