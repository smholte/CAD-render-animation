# 0282 – Function dialogs become windows: they stay open when you click elsewhere and can be dragged to another screen

**Who:** worker · **Status:** open – can start (batch A now; batch B after 0272) · **Branch:** `task/0282-function-windows`
**Started by:** lead, 21 Nov 2026 (owner 22:39, screenshot of **Make a crane** (type, Start from AT-40, folds Crane /
Boom / Carrier / …, Name, Make / Cancel): "when a function menu like Make a crane or other functions are open they
should stay open when you click off the menu and be able to drag to another screen") · **Model:** Opus · effort High
**Area:** a shared helper for "function windows" built on 0271's Settings window (`ops_settings.py`, `ui_settings.py`,
`ops_setup.open_window` – a small window drawn in the 3D view's toolbar region, nothing else in it); the dialogs that
today use `invoke_props_dialog` / `invoke_popup` (about 30 in `ops_rule_sets.py`, `ops_workspace.py`, `ops_motion.py`,
`welcome.py`, `ops_usage.py`, `ops_tour.py`, `ops_main.py`, `ops_lifting.py`, `ops_learning.py`, `ops_gcode.py`,
`ops_backups.py`, `ops_web3d.py`, `ops_lifting_make.py`, `ops_demo.py`, `about.py`, `pccheck/ops.py`); tests, real-app
test, guide pictures, CHANGELOG.

## What to do

1. **Inventory** (in the report, a table): every dialog / popup of the app – what it is, how long it is, and the
   choice: **window** (a form the user works in: Make a crane, Set up a crane, export / G-code / rule-set / workspace
   forms, Learn…, the PC check's choices…) or **stays a small popup** (a one-line "Are you sure?" or a short message
   that needs one click). Rule: anything with fields or folds becomes a window.
2. **One shared helper** so a dialog becomes a window with a few lines: same window kind as 0271 (title = the
   function's name, only its page, no Blender header / tabs / grid), can be dragged (also to a second monitor), stays
   open when the user clicks in the main window (the 3D view and the side panels keep working beside it), opening it
   again brings it to the front, remembers size and place per function, the page's **Make / OK** and **Cancel** at the
   bottom close it, Esc closes it when the mouse is over it. The values the user typed stay while it is open; what it
   needs from the scene (the selected part, the model) is read when Make is pressed and the window says so if it is gone.
3. **Convert batch A now:** every "window" dialog in files that no running or queued task touches (check TASKS.md and
   the branches before each file). **Batch B** – the files 0272 changes (`ops_lifting_make.py` = Make a crane,
   `ops_main.py`, …) – after 0272 is merged, in this same task if it is still running, else a follow-up the report
   names. Make a crane is the owner's example: if it lands in batch B, say so plainly.
4. Client view: a window that is refused there today stays refused (0213).
5. Real-app test: open Make a crane (or the first batch-A form), click in the main window → still open; move it;
   close / open → same place; two different function windows open at once work.

## Done when

- [ ] Inventory table in the report; every form-type dialog in batch A is a window; batch B listed
- [ ] Shared helper with tests; real-app test as in 5; Windows second-monitor check in the owner's steps
- [ ] Every converted function: tooltip unchanged, guide picture redone, tour stop `changed=`, PC-check line
- [ ] Full suite + GitHub run green; report filled in; merged, version, release (CLAUDE.md section 7)

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
