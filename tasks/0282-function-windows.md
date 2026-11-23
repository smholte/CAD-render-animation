# 0282 – Function dialogs become windows: they stay open when you click elsewhere and can be dragged to another screen

**Who:** worker · **Status:** done (0.2.217) · **Branch:** `task/0282-function-windows`
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

- [x] Inventory table in the report; every form-type dialog in batch A is a window; batch B listed (done too)
- [x] Shared helper with tests; real-app test as in 5; Windows second-monitor check in the owner's steps
- [x] Every converted function: tooltip unchanged, guide picture redone, tour stop `changed=`, PC-check line
- [x] Full suite + GitHub run green; report filled in; merged, version, release (CLAUDE.md section 7)

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026 (batch A and batch B in one go: 0272 was merged).

**What changed:**
- **One shared helper, `blender/form_window.py`.** A dialog becomes a window by changing the last line of its
  `invoke`: `return form_window.open(self, context, width=…, height=…, title=…, confirm="Make")` (`confirm=None`: only
  Close). The operator keeps its properties, `draw` and `execute`. The values live in a property group made from the
  operator's own properties on the window manager (same names, defaults, choices, hidden flags); the operator's own
  `draw` draws them in the window (a stand-in hands Blender the group where the draw names the operator). **Make / OK**
  runs `execute` with those values in the main window, as the dialog's OK did, with its undo step – so the selected
  part and the model are read when it is pressed; refused (its poll: no model, a job running, the Client view) or
  failed: the window stays open and says why in red. Done: it closes. Cancel / X / **Esc over the window** close it
  (the operator's own `cancel` runs, as for a dialog); **Return over the window** is its button. Pressing the
  function's button again brings its window to the front and keeps what was typed, unless it is about something else
  now (a hidden property differs: Note for another stop). Two different function windows can be open at once.
  Another project closes them.
- **The window** is 0271's kind (page in the 3D view's toolbar region made as wide as the window, nothing else):
  `ops_setup.FORM_MARK` (`fr_form` = the operator id), `PAGE_MARKS`, `is_page_window`; `panels.SIDE_MARKS`; Blender's
  tool buttons hidden there too (`ops_settings._in_settings`).
- **Size and place per function** – and of the Settings and Make windows – are kept **in the settings file**
  (`prefs.window_places`, one JSON string; `ops_make.remember` / `kept_size` / `kept_place`); the size on every PC, the
  place on Windows (winplace as before). The old `fresing_make_windows.json` is read once and moved over. Fresing
  Settings opens at its kept size too.
- **Client view:** `fresing.form_*` is allowed; Make runs the function's own poll, so a refused function stays refused
  (its button never opens the window). The window's buttons are not counted by the usage tracker.
- **Found on the way:** Program details crashed in its window once its step was gone – it now says to select a step.

**Inventory** (also in code: `form_window.WINDOWS` / `POPUPS`; `tests/test_form_window.py` fails on a dialog that is in
neither list):

| Dialog | File | Size | Now |
| --- | --- | --- | --- |
| Make a crane (the owner's example) | ops_lifting_make.py | form with folds | **window** (batch B) |
| Box… (box load) | ops_lifting.py | 2 fields | **window** |
| Save pose · Save visibility set · Save scene | ops_motion.py | 1–4 fields | **window** |
| New group · Save paint scheme | ops_main.py | 1 field | **window** (batch B) |
| Save as new rule set · New, empty rule set · Rename rule set | ops_rule_sets.py | 1–2 fields + lines | **window** |
| Save as my own workspace · Rename my workspace | ops_workspace.py | 1–3 fields | **window** |
| Export profile | ops_usage.py | 2 fields | **window** |
| Make the Learning hub · Note for this stop | ops_tour.py | folder / note | **window** |
| Make demo project | ops_demo.py | choice + folder | **window** |
| Fresing Render PC check | pccheck/ops.py | choices + file | **window** |
| Program details · Go to line | ops_gcode.py | long list · 1 field | **window** |
| Learn · My learning list | ops_learning.py | long, buttons | **window** (Close only) |
| Restore a backup | ops_backups.py | long list | **window** (Close only) |
| About Fresing Render | about.py | long | **window** (Close only) |
| A newer backup (at load) | ops_backups.py | question | popup (one click) |
| Lifting: I understand | ops_lifting.py | one click | popup |
| Update the set-up? · Show changes | ops_locations.py | question · short list | popup |
| Switch rule set? | ops_rule_sets.py | question with preview | popup |
| Clear my usage data? | ops_usage.py | "are you sure" + one tick | popup |
| Baked shadows will not move | ops_web3d.py | question before the file browser | popup |
| Hide a family in use? | ops_workspace.py | question | popup |
| Welcome · What's new | welcome.py | – | popup for now: **welcome.py belongs to 0276** (first-start set-up) |
| ~20 `invoke_confirm` (Remove / Delete / Reset …), 5 search lists (RAL, HDRI, template, spool follower), 4 `popup_menu` messages | various | one click | popup |

**Tested and measured** (4-core web machine, Linux, Blender 5.2.3 under xvfb):
- `tests/test_form_window.py` (new, 41): the inventory, the values mirror every window operator's properties, each
  form draws (23), Make runs with the window's values, a refused / failing Make says why, Cancel runs `cancel`, opening
  again keeps what was typed unless about something else, sizes / places in the settings file and the old file moved
  over, a damaged value gives nothing. Plus 275 tests of the touched areas (settings, usage, rule sets, workspaces,
  learning, backups, about, set-up window …): all pass.
- Real app `ui_test_forms.py` (new, 29 checks, group "tour"): Make a crane opens a window with only its form; a click in
  the main window leaves it open; its button again: no second window, typed name kept; Save as my own workspace opens
  beside it; Esc over it closes that one only; size kept and used again (560 × 640 → 564 × 637); Return saves a pose,
  Ctrl+Z takes it back; Save with no name: window stays, "Give the workspace a name"; Client view: Save pose refused
  (no window), Save scene opens; another project closes them. 29/29.
- Real-app tests changed for windows: liftingmake 25/25 (Return over the window starts Make in 0.4 s, the window
  closes), rulesets 19/19, backups, demokits 25/25, lesson 41/41, usage 33/33, start 72/72.
- PC check line `app.windows` (Full) OK locally (bpy module).
- Guide pictures redone from the real app: `dialog_8_make_crane.png`, `backups_window.png`, `learning_list.png`,
  `learn_window.png`, new `form_workspace_save.png`.

**GitHub runs:** 6 full runs. Red twice for real (an independent test caps the Client view's allow list – +3 for the
window's buttons; the left-panel order test had to leave the window's page out) and once at the PC check's 15-minute
limit (its first half had been at 15.0 min – the turntable line moved to the second half, as 0217 / 0279 did). Three
renumberings: 0264, 0265, 0262 and 0307 took 0.2.213–0.2.216 while the runs went. Released as **0.2.217**
(run 45267937288: publish, Windows update check, offered to the apps; the landing-page job failed on GitHub's artifact
fetch and was re-run).
**Subagents:** none; no Windows-only code was written (the window places use 0260's reviewed `winplace.py` unchanged).

**Open points / follow-up tasks:**
- **Place on Windows only.** Blender has no way to move a window on Linux; on Windows the window opens where it was
  (0260's `winplace.py`, unchanged). The second-monitor check is the owner's (steps below).
- A second function window opens on top of the first (both are split from the top left of the 3D view); drag it
  aside – on Windows it then opens there next time. Opening it offset would be Windows-only code (a follow-up if wanted).
- 0276 owns `welcome.py`: the welcome and What's new stay Blender popups until its first-start set-up replaces them.
- 0273's material picker window can use `form_window.open` (or its own window as Settings does).
- Return over a field of the window starts typing in that field (as in a Blender dialog); over the window's free space
  it is the button.

**Owner's check on your PC:**
1. Update (Fresing tab > **Update now**), the app starts again.
2. Open a project with a model. **8 Lifting plan > Equipment > Make a crane…** – a window "Make a crane" opens.
3. Click in the 3D view of the main window, turn the view: the Make a crane window **stays open**.
4. Drag the window by its title bar onto your **second screen**, make it a bit bigger. Click **Cancel**.
5. Press **Make a crane…** again: it opens **on the second screen, at that size**.
6. With it open, **Fresing > Learn…**: a second window opens. Move the mouse over it, press **Esc**: only that one closes.
7. In Make a crane press **Make**: the window closes and the crane is made as before.
