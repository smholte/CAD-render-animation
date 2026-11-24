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

- [ ] Tests of the naming rule (Inventor versions, forbidden characters, numbering past an existing "(1)"), of the
      backups' name, of the setting
- [ ] Real-app test: new project + test crane → Save shows the crane's name; Save as on it → "(1)" selected
- [ ] Guide (Saving), tooltips, PC check line `files.name`, function entry; full suite + GitHub run green; report;
      merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
