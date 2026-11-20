# 0227 – Client view: X and Delete still delete a part on the owner's PC

**Who:** worker (Claude Code on the web) · **Status:** done · **Branch:** `claude/cad-render-animation-0227-p50i7q`
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

- [x] Found why X / Delete reach Blender's delete on the owner's set-up (say which route selected the part and why the
      key got through); a test that failed before for each route found
- [x] In the Client view: no part or sub-assembly can be selected by any route the worker finds (3D view click, box
      select, the Fresing tree, Select All, selected before the switch), and X, Delete and the Object menu's Delete do
      nothing – the real-app test presses them with a part selected the way the owner could, and counts the objects
- [x] Full access afterwards: X and Delete work as before
- [x] Windows: the Windows CI job checks the swallowed keys if it can (else say why not), and the report gives the
      owner numbered steps to confirm on his PC
- [x] Tests added/updated; full suite passes; guide line of the Client view still true
- [x] Report below filled in

## Not in this task

0221's Outliner / Properties hiding and its Fresing-menu entry; the other Blender interface parts of study 0222.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 20 Nov 2026 · branch `claude/cad-render-animation-0227-p50i7q`

**What changed:**
- **Route found (real app, Linux):** Ctrl+Z right after picking the Client view undid the pick itself. The memfile undo
  went back to the step before it: workspace "All functions", the lock off, every part clickable, and the part that
  was selected before the switch selected again – so X opened "Delete selected objects?" and Delete deleted it
  (`tools/ui_test_client_keys.py` on the old code: 4 of 12 checks passed, the part selected, Object > Delete removed
  4 objects). Every other route tried held on the old code: a click, Shift/Alt-click, A, box / circle select,
  select by type / pattern / random / mirror / camera, a project saved in the Client view and opened again, Ctrl+Z
  of a later action, New camera view, Save scene, the turntable; X / Delete / Tab were swallowed whenever the lock
  was on. I could not reproduce "a click selects a part" with the lock on; on the owner's PC the lock was most likely
  already off (Ctrl+Z, or another undo), which also explains why X got through. The owner's steps below confirm it.
- `workspaces.py`: `_before_undo` (undo_pre / redo_pre) remembers a locked workspace; `_after_undo` puts it back when
  the step brought a workspace without the lock. Undo of earlier work still happens (level b); only the Workspace
  switcher leaves the Client view.
- `lock.py`: `hold()` – while locked, an object that can be clicked is made unclickable again and the selection and
  the active object are cleared, at every scene update and in the guard (0.1 s), whatever freed it (script,
  Properties editor, undo). One `foreach_get`: 0.52 ms for 5,000 objects (4-core web machine). X and Delete are
  swallowed with any modifier (Shift+X / Shift+Delete = Blender's Delete globally); the keys are put in place again
  whenever the lock goes on (in case the add-on keymap was not there at start); `SWALLOWED` / `CAUGHT` counters.
- PC check `panel.workspaces`: also an undo to before the pick (stays in the Client view) and a freed, selected part
  (taken back) – so the owner's PC check covers both on Windows. Guide (Client view) and CHANGELOG 0.2.174;
  `panel.client_view` `changed="0.2.174"`.

**Tested and measured** (4-core web machine, test crane):
- `tests/test_workspaces.py` + `test_workspaces_independent.py`: 99 passed; 4 new tests (Ctrl+Z keeps the Client view,
  a freed / selected part taken back, the keys' modifiers, the cost of `hold`), the first three failed on the old code.
- Real app: new `clientkeys` (12 checks, in group pccheck-b): 12/12; old code 4/12. `lock` 19/19 and `panel` 39/39
  with the change. (One local batch first showed 4 Outliner routes of `lock` failing: two leftover background
  renders of my own experiments had the machine at load 10; rerun in the same order without them: 19/19.)
- Full access afterwards: a click selects, Delete deletes (checked in `clientkeys`).
- Windows: the keys cannot be checked on GitHub's Windows machine. Run 44739423914 tried `ui_test_client_keys.py`
  with a window there after the repair install: Blender opened no window (no graphics card), waited until it was
  stopped after 4 minutes, so the step was taken out again. Every other Windows run of Blender is a background run,
  which has no keymaps and no events. What does run on Windows: the PC check's `panel.workspaces` (undo to before the
  pick stays in the Client view, a freed and selected part is taken back) – OK in that run. The keys themselves: the
  owner's steps below.

**Owner's steps to confirm on your PC** (after Update now to 0.2.174):
1. Open a project with a model. At the top of the Fresing tab, Workspace: **All functions**. Click a part: it lights up.
2. Workspace: **Client view**. The part is no longer lit up.
3. Move the mouse over the model and press **Ctrl+Z**. The workspace still says **Client view**; nothing lights up.
4. Click a part, then press **A**: nothing lights up.
5. With the mouse on the model press **X**, **Delete**, **Shift+X**, **Shift+Delete**, **Tab**: no "Delete selected
   objects?" menu, nothing disappears; the bar at the bottom says "Client view: the project is locked …".
6. Workspace: **Full access**. Click a part: it lights up. **Delete**: it is gone. **Ctrl+Z**: it is back.
If any part still lights up in step 3–5, tell the lead exactly what you did just before it.

**Open points / follow-up tasks:**
- The exact clicks on the owner's PC are not known; the steps above confirm or reopen it.
- GitHub runs: 44739423914 (branch, full) – red for two reasons outside this task: (1) `tests/test_toolbox.py`
  `test_the_sample_folders_jobs_are_taken_up_as_the_format_says` failed on `main` too since 19 Nov evening: the inbox
  deletes a job a day after it became final, and the sample's job finished on 18 Nov 20:15 (a date time-bomb of
  0217) – the test now looks at the sample as on that evening and checks the deletion a day later; (2) Windows PC check
  `web3d.small` "the page gave no places of its parts" (the flaky line of CLAUDE.md section 8; passed in 0.2.173's
  run). The Windows window try was in that run too (above).
- 44743465436 (branch, full, 2c1fc91): green, 19.4 min. Then `main` merged in (only task files had moved) and
  fast-forwarded; `main`'s run publishes 0.2.174. Two code runs in all: the first red for the two reasons above.
- No helper-agent review: no Windows-only code shipped (the Windows CI step was tried and taken out again).
- Subagents: none.
