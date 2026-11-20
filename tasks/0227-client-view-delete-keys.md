# 0227 – Client view: X and Delete still delete a part on the owner's PC

**Who:** worker · **Status:** open · **Branch:** `task/0227-client-view-delete-keys`
**Model:** Opus · effort Medium · **Lane:** Start & learn (before 0221)
**Started by:** lead, 20 Nov 2026 · **Area:** `fresing_render/blender/lock.py` (the Client view's lock), its real-app
test, the PC-check / tour line of the Client view if one checks keys

## Goal

In the Client view nothing in the model can be deleted from the keyboard: X and Delete do nothing (no "Delete
selected objects?" menu, no part gone), on Windows as on Linux.

## Background

- Owner's check on his PC, 20 Nov 2026 (Windows 11, app on 0.2.168 or newer – the worker asks nothing, it tests on the
  newest `main`): in the Client view **G does nothing and Tab does nothing (right), but X opens Blender's small menu
  "Delete selected objects?" with Delete / Cancel, and pressing Delete while a part or a sub-assembly is selected
  deletes it.** **Owner, 20 Nov 13:22: the part was selected by clicking it in the 3D view while in the Client view;
  clicking in the Fresing tab's tree does nothing.** So a 3D-view click still selects a part while locked (the lock
  should make objects unclickable) – start there; still try the other routes.
- `lock.py` says (top docstring, `_KEYS` near line 391): selection and the active object are cleared when the lock goes
  on, objects are made unclickable, and Delete, X, Tab and Ctrl+Shift+S are swallowed by an add-on keymap whose
  operator's `poll` is the lock. So on his PC either a part can still be selected while locked, or the swallowing
  keymap does not win over Blender's own X / Delete, or both. Tab and G being dead suggests the selection was cleared
  once and something selected a part again, while the X / Delete items do not catch.
- Earlier work on the same lock: 0062 (Client view), 0213 (lock holds: 5 Outliner routes, Ctrl+Z, older projects),
  bug hunt 0209 group A row 2 ("Client view lets the whole model be deleted", fixed in 0213 on Linux).
  CLAUDE.md section 8: "A key in an add-on keymap whose operator's poll is False passes on to Blender's own key – a
  lock can swallow Delete / Tab only while it is on." Also check: the user keyconfig / keymap preferences Windows
  saves (`userpref.blend`), the Fresing tab's tree (does a click there select a part while locked?), a project opened
  already in the Client view, a sub-assembly (empty) selected, and the 3D view header's Object menu > Delete.
- 0221 (same lane, not started) hides the Outliner and Properties column in the Client view and greys its menu entry:
  it starts after this task. Do not do 0221's work here.

## Done when

- [ ] Found why X / Delete reach Blender's delete on the owner's set-up (say which route selected the part and why the
      key got through); a test that failed before for each route found
- [ ] In the Client view: no part or sub-assembly can be selected by any route the worker finds (3D view click, box
      select, the Fresing tree, Select All, selected before the switch), and X, Delete and the Object menu's Delete do
      nothing – the real-app test presses them with a part selected the way the owner could, and counts the objects
- [ ] Full access afterwards: X and Delete work as before
- [ ] Windows: the Windows CI job checks the swallowed keys if it can (else say why not), and the report gives the
      owner numbered steps to confirm on his PC
- [ ] Tests added/updated; full suite passes; guide line of the Client view still true
- [ ] Report below filled in

## Not in this task

0221's Outliner / Properties hiding and its Fresing-menu entry; the other Blender interface parts of study 0222.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
