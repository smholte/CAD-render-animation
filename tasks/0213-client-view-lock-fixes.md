# 0213 – Client view and side-panel fixes (bug hunt 0209 group A)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0213-client-view-lock-fixes`
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

- [ ] Each row's repeat case is a test that failed before (real-app test where the row is about clicks).
- [ ] Row 2: a list in the report of every route tried and how it is closed.
- [ ] Guide's Client view section says what is locked; tooltips; full run green.
- [ ] Report filled in.

## Not in this task

Level b of 0062 (edits in the Properties editor / Python console – owner's pick stays); usage lane rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
