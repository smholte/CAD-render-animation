# 0136 – Fix: web 3D export crashes with a moving cable not built; marine growth follows the sea

**Who:** worker · **Status:** open – can start now · **Branch:** `task/0136-export-crash-waterline`
**Started by:** lead chat, 15 Nov 2026 (rows of bug hunt 0131, report in `tasks/0131-bug-hunt-4.md`) ·
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Web 3D lane + one call in Scene & Render):** `blender/web3d.py` (the Baker), `blender/handlers.py` or a small shared helper for pausing the live handlers, `blender/surroundings.py` (one call), their tests.
**Do not edit:** `paths*.py`, `demo_model/`, `demo.py` (0126 runs there) – so no guard inside `paths.py`; `marine_looks.py`, `site/`, `tools/site_projects/` (0128); `house_*` (0130).

## Goal

Export web 3D model never crashes Blender (row 1 – a crash that loses unsaved work), and the marine growth band stays at the sea's waterline (row 12).

## Background

The rows below are from bug hunt 0131 (report on `main`): each row has the place in the code, how to repeat it
("Proof") and a suggested fix. Read those rows first; repeat each one before fixing it.

- **Row 1 (crash):** the bake scene is a copy that still carries `scene.fresing`; the cables' depsgraph handler runs for it during `bpy.ops.object.bake` → segfault. Since `paths.py` is busy (0126), fix it on the Baker's side: the copy carries no project data the live handlers act on (empty its `fresing` lists or tag it) **and** the live handlers (paths, flex, vessel, spool, tracks, linkages, section) are paused while the bake runs – one shared helper the Baker calls, a `try/finally`. Test: `test_moving.step` + `paths.set_up_moving_model`, not built, export → a file, no crash (in a separate process, so a crash fails the test instead of killing pytest); the same after `animation.clear_keys` on a built model. Note in the report the one-line guard `paths._follow` should still get later (0137).
- **Row 12:** call `marine_looks.sync(scene)` at the end of `surroundings.ensure` (and wherever the sea is built or moved); test: water level 3 m and Vessel deck → the waterline follows.

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
