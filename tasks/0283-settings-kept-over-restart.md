# 0283 – Every Fresing setting is kept over a restart (the app's own settings file)

**Who:** worker · **Status:** running · **Branch:** `task/0283-settings-file`
**Started by:** lead, 23 Nov 2026 (0278's finding: Blender 5.2.3 does **not** keep the extension's preferences over a
restart while the app template is on – a value saved with Save Preferences reads back as its default with
`--app-template fresing_render`. So every Fresing setting in `prefs.py` (keep sections, lesson look, backups, Live
preview's last choice, Settings window's last tab, hover highlight, default template / rule set / workspace …) is
lost at every start. The owner's settings have never stuck.) **Lead's decision:** keep the app's settings in **a
file of its own**, like 0278's `<config>/fresing_left.json` and `fresing_layout.json` – not a `userpref.blend` in the
app template (that would move all of Blender's own preferences and could overwrite a user's). · **Model:** Opus · effort Medium
**Area:** Settings lane – `blender/prefs.py`, a new `core/settings_file.py` (no Blender: read / write / defaults /
versions / a broken file) + `blender/settings_store.py` (load at start, save on change); tests, real-app test, guide,
`docs/COMPANY-USE.md`, CHANGELOG. **Before 0272 and 0282** (both touch settings); 0272 then builds its locations and
`.frsetup` on this file.

## What to do

1. **One settings file per user** in Blender's config folder (e.g. `<config>/fresing_settings.json`), versioned,
   written safely (temp file + rename; a broken file → defaults + a backup copy of the broken one + one plain note).
2. **Every property in `prefs.py`** reads its value from the file at start and writes it back when the user changes
   it (an update callback or one timer – no "Save Preferences" needed, no slowdown when dragging a slider). The
   properties stay registered with the same names (the Settings window and everything that reads them keep working).
3. **Moving the old values:** at the first start of the new version, copy any value Blender still has (e.g. when the
   app ran once without the template) into the file; 0278's `fresing_left.json` and `fresing_layout.json` may stay
   separate or fold in – say which in the report.
4. **Updates and uninstall:** the file survives an update (Update now, the installer); the uninstaller asks or keeps
   it as the other user files today (check `installer/`). `docs/COMPANY-USE.md`: where the file is, that IT can copy
   it (0272's `.frsetup` comes later).
5. Real-app test with `--app-template fresing_render`: change one setting of each Settings tab, quit, start → every
   value is back; a damaged file → defaults + note, app starts.

## Done when

- [ ] Every `prefs.py` setting survives a restart in the app (real-app test, each tab) and an update (update test)
- [ ] Broken / missing / older file handled; tests in `core`
- [ ] Guide (Settings chapter: "kept for you, nothing to save"), COMPANY-USE, PC-check line, CHANGELOG
- [ ] Full suite + GitHub run green; report filled in; merged, version, release (CLAUDE.md section 7)

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
