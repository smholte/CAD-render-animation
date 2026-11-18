# 0213 – Client view and side-panel fixes (bug hunt 0209 group A)

**Who:** worker · **Status:** done (0.2.164) · **Branch:** `claude/busy-edison-v4v77x`
**Started by:** lead, 18 Nov 2026 · **Model:** Opus · effort Medium
**Area:** Start & learn lane – `blender/lock.py`, `blender/workspaces.py`, `core/workspaces.py`, `blender/ops_setup.py`
(+ their tests). Not `core/functions.py` entries of others, not the usage files (0209 group F, later).

## Goal

Fix rows **2, 9, 24, 23, 35** of `tasks/0209-bug-hunt-7.md` (each row has its repeat case and numbers). Row 2 first:
the Client view is a lock that does not lock – the editor-type menu brings the Outliner back and the whole model can be
deleted. A company may use the Client view (owner 18 Nov), so it must hold.

- **2** Outliner back through the editor-type menu of the area that replaced it → Select all → Delete deletes the model.
  Close every route Blender offers to change an area's type or open an Outliner / Properties while locked (also the
  area's header menu, a new window, Ctrl+Space maximise), or make the deletion impossible whatever editor is open.
- **9** Import + an undoable action that adds no object + Ctrl+Z: camera and floor come back unmarked (lock leak).
- **24** functions with greyed buttons shown in the Client view (`scene.camera`, `scene.save`, `queue.schemes` …).
- **23** Ctrl+Z of an unrelated action throws the Set-up window back a step (keep the step out of undo's reach).
- **35** an older test-tour project opens locked when the default workspace is Client view (tour / demo / PC-check
  projects always open in All functions – `workspaces.use_all`).

## Done when

- [x] Each row's repeat case is a test that failed before (real-app test where the row is about clicks).
- [x] Row 2: a list in the report of every route tried and how it is closed.
- [x] Guide's Client view section says what is locked; tooltips; full run green.
- [x] Report filled in.

## Not in this task

Level b of 0062 (edits in the Properties editor / Python console – owner's pick stays); usage lane rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 18 Nov 2026 – version 0.2.164.

**What changed:**
- **Row 2** (`lock.py`): while locked, a guard timer (every 0.1 s, `GUARD_EVERY`) and a msgbus watch on
  `Area.ui_type` / `Area.type` turn every Outliner area of every window back into Info (indices added to the
  screen's mark, so the unlock puts them back). The Outliner is the only editor that selects parts the lock made
  unclickable (checked in Blender: 3D-view Select All / Select Pattern / By Type / Camera select nothing). Routes tried
  in the real app, each followed by Outliner > Select all > Delete:
  | Route | Before | Now |
  | --- | --- | --- |
  | editor-type menu of the Info area that replaced it | Outliner, 26 → 0 objects | Info again, 26 kept |
  | Shift+F9 over it | Outliner | Info |
  | Ctrl+Page Up to another Blender workspace (Scripting) | its Outliners | Info |
  | Window > New Window, an area set to Outliner | Outliner | Info |
  | Ctrl+Space (area maximised), then the editor menu | Outliner | Info; Ctrl+Space back to the normal layout |
  | Delete / X in the Outliner (keys) | already swallowed (0062) | same |
  Not closed, by the owner's level b: the Properties editor and the Python console.
- **Row 9** (`lock.relock`, `workspaces._after_undo`): after an undo with the lock on, objects without the mark are
  marked (as made while locked) and the selection is cleared; `_after_change` uses the same (a new camera no longer
  stays selected).
- **Row 24**: `fresing.camera_add`, `shot_save`, `queue_schemes`, `queue_schemes_tick` allowed (the Client view's own
  description promises camera views and saved scenes; a new camera is locked like the rest). Test: every function a
  locked built-in shows has an allowed button.
- **Row 23** (`ops_setup.py`): the kind and step picked last are kept per scene outside undo and put back in
  `undo_post` / `redo_post`; still saved with the project; cleared at a load.
- **Row 35** (`workspaces.ensure`, `app_made`): a project with the tour or demo mark and no workspace gets All
  functions. Old PC-check projects are temporary (made fresh each run): left as they are.
- Guide: Client view section says what stays locked and what gets through on purpose.

**Tested and measured** (4-core web machine, test crane):
- New real-app test `tools/ui_test_lock.py` (group pccheck-b, `MIN_CHECKS` 19, ~0.5 min): 19/19 now; on the old code
  6/24 – row 9 (FR Floor and Iso front-right freed), row 24, every row-2 route (26 → 0 objects) failed.
- New pytests (failed before, pass now): `test_an_older_tour_or_demo_project_opens_unlocked_whatever_the_default`
  (tour + demo), `test_an_undo_to_before_the_lock_marked_new_objects_locks_them_again`,
  `test_every_function_a_locked_workspace_shows_has_a_button_that_works_there`, `test_undo_keeps_the_step`.
- Locally: `test_workspaces.py`, `test_workspaces_independent.py` (allow-list size < 95, four names added to its ok
  list), `test_setup_window.py`, `test_user_guide.py`; real app `panel` 37/37, `setup` 46/46; tooltips 865 ok.
- GitHub: 1 full run, green (run 44379524044, 31.7 min – the queue was shared with other tasks); `main` fast-forwarded,
  reuse run 44385099284: release v0.2.164 published, the old-version update check and the offer green.

**Open points / follow-up tasks:**
- The Set-up window's Back / Next are still refused in the Client view (the Set-up is hidden there; not changed).
- Subagents: none (Medium task; the independent check of row 2 is the real-app test run before and after).
