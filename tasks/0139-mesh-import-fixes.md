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

- [ ] Every row above fixed, each with a test that failed before the fix (the row's proof as a test).
- [ ] Tooltips, guide sentence where the owner sees a change, function list / PC-check / tour stop only if something
      visible changes; GitHub run green; merged; version (CLAUDE.md section 7); report (short list for the owner).

## Not in this task

Other rows of 0131 (they have their own tasks: 0136–0140); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
