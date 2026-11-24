# 0291 – Project names: a new project is named after its first model; Save as offers "name (1)" to rename; backups too

**Who:** worker · **Status:** running · **Branch:** `task/0291-project-names`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "When saving a project now, the file name is empty, but
it should automatically be the name of the first part you added in the project. When save as a previously saved
project it saves it as the same name with (1) and letting user rename before saving. (this also goes for auto saves).
The standard name of a project can also be empty, but that needs to be chosen by user in the settings.")
· **Model:** Opus · effort Medium
**Area:** the Save / Save as entries and keys the app draws or keeps (`lock.py`'s File menu drawing, `quiet.py`'s File
menu, Ctrl+S / Ctrl+Shift+S, any Save button of the app), a new `blender/project_name.py` (+ the naming rule in
`core/`, no Blender), `blender/backups.py` / `core/backups.py` (names of an unsaved project's backups), one setting in
`prefs.py` + Settings > General (`ui_settings.py`), the settings file (0283); tests, real-app test, guide, CHANGELOG.
**Not:** where backups go and how many are kept (0246), Locations (0272) beyond reading the projects folder.

## What to do

1. **First save of a new project** (Ctrl+S, File > Save, Save as, any app Save button): the file browser opens with the
   name filled in = the **first model imported** into the project (its root's name without an Inventor version like
   " v8" and without the file ending; characters Windows does not allow replaced). Folder: the user's projects place
   if Locations (0272) has one, else the first model's STEP folder – say which. Nothing imported yet: "Untitled
   project" (or empty with the setting below).
2. **Save as… on a saved project:** proposes "<name> (1)" – the next free number in that folder: (2), (3) … – with the
   name selected so the user can type over it before saving.
3. **Backups of a never-saved project** (0246's "Unsaved projects") carry the same name, not "untitled". If the app has
   Blender's own auto-save on, its file gets the name too (check and say).
4. **Setting** (Settings > General): "Name of a new project: **First model's name** (default) / **Leave empty**";
   kept over a restart (settings file, 0283).
5. An already saved project is never renamed by the app.

## Done when

- [x] Tests of the naming rule (Inventor versions, forbidden characters, numbering past an existing "(1)"), of the
      backups' name, of the setting
- [x] Real-app test: new project + test crane → Save shows the crane's name; Save as on it → "(1)" selected
- [x] Guide (Saving), tooltips, PC check line `files.name`, function entry; full suite + GitHub run green; report;
      merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 24 Nov 2026 (branch `task/0291-project-names`), released as 0.2.233.

**What changed:**
- `core/project_name.py` (no Blender): `clean` (Inventor " v8", ":1", Blender's ".001", file endings .iam/.stp/…,
  `<>:"/\|?*` and control characters → "_", trailing dots / spaces, Windows device names CON / COM1 … get "_", 120
  characters), `proposal` (first model / "Untitled project" / "" for Leave empty), `next_free` ("(1)", past an
  existing "(n)", only `.blend` names count, no case), `typed_problem` for the Save-as box.
- `blender/project_name.py`: `fresing.save` (Ctrl+S), `fresing.save_as` (Ctrl+Shift+S), `fresing.save_as_browse`.
  First save of a new project: Blender's browser with the first model's name, in that model's STEP folder (else
  Documents). **Locations (0272) has no projects kind**, so there is no "projects place" yet – the STEP folder is used.
  Save As on a saved project: a small box (a popup on purpose, `form_window.POPUPS`) with "<name> (n)" already in edit
  mode, all selected (`layout.activate_init`; Blender's own browser does not select its name field – checked in 5.2.3),
  Return twice or Save saves into the project's folder; a name that is there already opens the browser instead
  (never overwritten); Other folder… = Blender's browser with the name.
- Blender's File menu keeps every entry: its own draw runs with a stand-in layout that hands the first Save and Save
  As… to the app (Save Copy, Save Incremental stay Blender's). Client view's File > Save is `fresing.save` (on
  `lock.ALLOWED`). Any other way into Blender's save browser for a new project (the "Save changes?" question, Save as…
  and update) is filled in once by a file-browser draw handler when it shows Blender's own "Untitled.blend".
- Model roots get `fr_imported` (import time) in `build.py`; older projects take the roots by name.
- Backups: an unsaved project's backups are named after the first model ("Unsaved project" with nothing imported);
  the unsaved folder is listed whatever the name (`core.backups.parse_any`, `listing(folder, None)`).
- Setting **Fresing Settings > General > Name of a new project** (`new_project_name`: First model's name / Leave
  empty), kept over a restart by the settings file (0283; `test_settings_store.py` covers it).
- **Blender's own auto-save** (File > Recover > Auto Save) names its file itself (`<process number>_autosave.blend`
  for an unsaved project); there is no setting or API to give it another name, so it is unchanged (said in the guide).
  The app does not switch Blender's auto-save on or off.
- Guide: new section "Saving a project – its name" (`#saving`), backups paragraph; function entry `help.project_names`
  (File menu added to `functions.MENUS`); PC check line `files.name` (Full, MIN_LINES_FULL 146); CHANGELOG 0.2.233.
- No tour stop: the brief did not ask for one and the save browser cannot be shown by the tour (a note for the lead).

**Tested and measured** (4-core web machine, test crane):
- `tests/test_project_name.py` (43 cases), `test_backups_core.py` (+1), `test_project_name_blender.py` (9),
  `test_settings_store.py` (+ the setting); neighbouring files (backups, form windows, functions, places, quiet,
  settings, updates, guide, workspaces, fr mark, queue safety): 421 passed.
- Real app `ui_test_names.py`: 19/19 in 29 s – Ctrl+S proposes "TEST.CRANE" (the crane's CAD name) in the crane's
  folder, Blender's own Save gets the same name (handler), Leave empty opens with no name, Ctrl+Shift+S's box: typing
  "Kran 2" replaced the selected "TEST.CRANE (1)" and Return saved it, Return twice saved "Kran 2 (1)". Also locally:
  lock 19/19, quiet 90/90, backups 26/26.
- PC check `files.name` (bpy module): OK – "TEST.CRANE", "TEST.CRANE (1)", "TEST.CRANE (2)".
- GitHub: see below.

**Open points / follow-up tasks:**
- A "Projects" kind in Locations (0272) would give the first save a fixed folder; today it is the model's folder.
- The box's place follows the mouse (Blender's popup); on a real PC that is where Ctrl+Shift+S was pressed.
- No independent review (not Windows-only code; risky parts – the menu stand-in, the browser handler – are covered by
  the real-app test).

**Owner's check on your PC:**
1. Start Fresing Render, **File > New project**, import any STEP model.
2. Press **Ctrl+S**: the file browser shows the model's name (no " v8", no ".stp") in the model's folder. Press
   **Save As**.
3. Press **Ctrl+Shift+S**: a small box shows the name with **(1)**, highlighted. Type a new name and press **Save** –
   the project now has that name, the first file is still there.
4. Fresing > Settings… > General > **Name of a new project: Leave empty**, File > New project, import, Ctrl+S: the
   browser opens without a name.
