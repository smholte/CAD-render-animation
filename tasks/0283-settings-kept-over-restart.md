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

**Chat / date:** Claude Code on the web, 22 Nov 2026 (branch `ccr-8c41bd11-e81xe9` – the session's own branch name
instead of `task/0283-settings-file`). Version **0.2.206**.

**What changed:**
- `core/settings_file.py` (no Blender): the file `<config>/fresing_settings.json` =
  `{"format": "fresing-settings", "version": 1, "settings": {...}}`, only the values that differ from the defaults (a
  setting never changed follows a later default). Read never fails: missing → nothing; damaged (not JSON, NaN, not
  ours, no version, wrong shape) → defaults, a copy `fresing_settings.broken-<time>.json`, one plain note (the
  technical reason goes to the console only); a value of the wrong kind / out of range → left at its default with a
  note naming it; a newer file's unknown settings are kept and written back. Write = temp file + fsync + rename.
- `blender/settings_store.py`: the spec is read from the registered `FRESING_AP_prefs` (a new setting in `prefs.py`
  is kept with no further change). `register()` loads at once (start-up code reads the settings), a 1 s timer saves
  when a value differs from what was written (one small write a second at most while a slider is dragged); `atexit`
  and `unregister` write the last change. Nothing runs in a background Blender unless `FRESING_SETTINGS_FILE` is set.
- **Moving old values:** no file at the first start → written from what Blender has (a run without the template).
- **0278's files stay separate:** `left_folded`, `left_width`, `next_folded` stay in `fresing_left.json` (it also holds
  each left section's fold, which is no preference); `fresing_layout.json` (editors' column) stays too. One file per
  value, no double source.
- Settings > General: "Your settings are kept for you: nothing to save" on top, the note in red when the file was
  damaged (guide picture `settings_general.png` made again).
- **Update / uninstall:** nothing to change in `installer/` – the installer moves the old `portable` folder (with
  `config\`) into a new install, Update now does not touch `config\`; `Uninstall.bat` removes the install folder
  with `config\`, as the other user files there (usage, layout, left). Written in `docs/COMPANY-USE.md` (+ how IT
  copies the file).
- PC-check line `settings.kept` (Full; `MIN_LINES_FULL` 121), named by `help.settings` in the function list; guide
  (Settings chapter), CHANGELOG.

**Tested and measured** (4-core web machine, Linux, Blender 5.2.3):
- `tests/test_settings_file.py` 29 tests (missing, round trip with accents, only changed values, 9 damaged forms each
  with one copy and one note, 11 wrong values, newer file, BOM, a failed write leaves the old file).
- `tests/test_settings_store.py` 8 tests (bpy module): every preference in the spec but the three of
  `fresing_left.json`; a setting of each tab survives a "restart" (defaults put in, file read); back to default;
  the timer; moving old values; damaged file + the note drawn on General; a wrong value; nothing in a background run.
- Real app `ui_test_settings.py` (now 50 checks, was 34) with `--app-template fresing_render`: 8 settings of the tabs
  General / Side panel / Lessons / Backups / Updates + the window's tab changed → written by the timer without Save
  Preferences → a second app started in the same settings folder (`ui_test_settings_restart.py`, 6 s) has every value;
  a damaged file → that app starts, defaults, one note, a copy. 50/50 locally (81 s).
- Update test (`update_test_blender.py`): a settings file written before Update now; after it the file is there and,
  in the window run, the two values are in use (GitHub's Linux update test and Windows A).
- PC check `settings.kept` + `app.settings` OK locally (bpy module).
- GitHub: see the run below.

**Subagents / review:** none (no Windows-only code; the independent helper was skipped to save usage).

**Open points / follow-up tasks:**
- 0272 can put its locations into this file (the spec is read from `prefs.py`; nested values like a list of locations
  need a new kind in `core/settings_file.py` and `VERSION` 2 with a move from 1).
- The note in Settings > General is one label: on a narrow window its end (the copy's name) may be cut off; the full
  text is in the console.

**Owner's check on your PC:**
1. Update to 0.2.206 (Fresing tab > **Update now**), the app starts again.
2. **Fresing > Settings…**, tab **Lessons**: set **Part** to **Glow**; tab **Backups**: **Every (minutes)** to 10.
3. Close Fresing Render (the X of the window), start it again from the Desktop.
4. **Fresing > Settings…**: Lessons shows **Glow**, Backups **10** – and General says "Your settings are kept for you".
