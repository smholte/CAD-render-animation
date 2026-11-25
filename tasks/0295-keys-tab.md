# 0295 – Keys: a Keys tab in Fresing Settings – every key of the app, change Fresing's own, a printable key sheet

**Who:** worker · **Status:** running (25 Nov; 0322 done, 0.2.244) · **Branch:** `claude/elegant-ritchie-mkcgli`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Is there a keybinds menu? Where you can edit and see what
they are, and a Fresing render specific one?" – today: no; Blender's own Preferences > Keymap only, in Full access)
· **Model:** Opus · effort Medium
**Area:** Settings lane – `ui_settings.py` (`TABS`), `ops_settings.py`, `lock.py` (the key lists `APP_KEYS`,
`BLENDER_KEYS`, `_KEYS`, `_wanted` – Fresing's own keys made changeable), the settings file (0283), a printable key
sheet (HTML page), the Fresing / Help menu entry, guide, CHANGELOG.
**Not:** which Blender keys are swallowed (0253's list stays), Blender's own keymap editor.

## What to do

1. **Settings > Keys**: every key and mouse action of the app in groups – **Move the view** (orbit, pan, zoom with mouse
   and touchpad, numpad views, Home, frame the selection – as they work with the app's settings), **Select**,
   **Fresing's own** (F12, Ctrl+F12, right-click menu, Delete / X → Remove… from 0292, Ctrl+C / V if 0293 is merged),
   **Blender keys that still work** outside Full access (G / R / S, H / Alt+H, A, Ctrl+Z, Space, F3, N …), **Blender keys
   that do nothing outside Full access** (greyed, "works in Full access"). Each row: what it does in plain words, the
   key, where it works. A search field.
2. **Change a key:** Fresing's own keys can be changed (click, press the new key; a clash with another app or Blender key
   warns) and Reset; kept over a restart in the settings file (extension preferences are lost – CLAUDE.md 8).
3. **Print key sheet** → one A4 HTML page in the Fresing look, opened in the browser (print / save as PDF).
4. **Blender's own key settings…** opens Blender's Preferences > Keymap (says that it is Blender's).
5. Fresing menu and Help: **Keys…** opens this tab; the guide gets a Keys section (the Learning hub links it later, 0304).

## Done when

- [x] Tests: the list is built from the live key lists (a new key in `lock.py` shows by itself); a changed key works
      and survives a restart; a clash warns; Reset
- [x] Real-app test of the tab and a changed key; guide + picture; function entry; PC check line `settings.keys`; full
      suite + GitHub run green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25 Nov 2026 (branch `claude/elegant-ritchie-mkcgli` – the session's branch,
not `task/0295-keys`). Version **0.2.253**.

**What changed:**
- **Settings > Keys** (new tab after Side panel; `blender/keys.py`, `core/keys.py`): five groups – Move the view (from
  Blender's input preferences: emulated 3-button mouse, number row as numpad), Select, Fresing's own (from
  `lock.app_keys()` = `APP_KEYS` with the user's changes), Blender keys that still work (`keys.KEPT`), Blender keys that
  do nothing outside Full access (from `lock.BLENDER_KEYS`, greyed). A key added in `lock.py` shows by itself (test).
  Search field (`wm.fresing_keys_search`).
- **Change a key:** `core/keys.OWN` = the 8 changeable keys (F12, Ctrl+F12, X, Delete, Ctrl+C, Ctrl+V, M, Alt+M); the
  right-click menu and G / R / S are listed but not changeable. Click → "Press a key…" (modal, Esc / click = not
  changed). Refused: Esc, Return, left / middle mouse, wheel, a modifier alone, a key another Fresing key has. Warned
  (taken): a key in Blender's default keymap of the 3D view (names Blender's operator). A Blender key that was
  swallowed and is given to a Fresing key is no longer swallowed (`lock._wanted`). Kept as JSON in the new preference
  `key_changes` → the 0283 settings file; `lock.refresh_keys()` adds the keys again at once; `settings_store.load`
  refreshes them after reading. Reset one (round arrow) / Reset all. The answer line under "Fresing's own keys" is
  always drawn (the panel stays still).
- **Print key sheet:** one A4 HTML page (Fresing palette, two columns, changed keys "yours; was …") in the temp folder,
  opened with the system's browser. **Blender's own key settings** opens Preferences > Keymap.
- **Ways in:** Fresing > Keys… (after Settings…), Help > Keys…, operator `fresing.keys`.
- Function `settings.keys` (headline, all workspaces), guide section `#keys` + Keys row in the Settings table + 2
  pictures (all Settings pictures re-made: the tab row has Keys now), PC-check line `settings.keys` (MIN_LINES_FULL
  155), tour stop `keys_tab` in the crane set (MIN_LINES_TOUR 117, MIN_CHECKS tour 117, crane `changed=0.2.253`).

**Tested and measured** (4-core web machine, no graphics card):
- `tests/test_keys_core.py` (10, no Blender) and `tests/test_keys_tab.py` (7, bpy module): list from the live lists +
  a key added to `APP_KEYS` / `BLENDER_KEYS` shows; a change goes into the keymap list and the add-on keyconfig; a
  restart (preference cleared, settings file read again) brings it back; clash refused / Blender warns; Reset; sheet.
- Real app `ui_test_settings.py` (65/65, MIN_CHECKS 52 → 64): Fresing > Keys… opens the tab; Measure's key changed by
  pressing Ctrl+Alt+K in the window; Copy on M refused; Ctrl+Alt+K starts Measure in the 3D view, Alt+M no longer; after
  the app is started again (app template, same settings folder) the key is Ctrl+Alt+K in the keymap.
- PC check `settings.keys` alone: OK ("74 keys in 5 groups; 13 Fresing keys"). Test tour: all stops' Go + check pass.
- GitHub runs: see below.

**Open points / follow-up tasks:**
- Only the 8 keys in `OWN` can be changed; a new Fresing key that should be changeable needs an `OWN` entry.
- A key that clashes with a Blender key in Full access: Fresing's key wins only outside Full access (its poll), as the
  warning says. Alt+M's replacement works in Full access too.
- `settings_materials.png` is made by the real-app test but used by no chapter (older than 0295, left out again).
- The Learning hub's link to the Keys section is 0304's.

**Owner's check on your PC:**
1. Fresing > **Keys…** – Fresing Settings opens on **Keys**. Type `render` in the search field: only the render keys.
2. Under **Fresing's own keys** click **F12**, then press **F9**: the line under the title says "Render the picture: now
   F9". Close the window, press **F9** over the model: it renders. **F12** does nothing of the app's.
3. Close the app and start it again: Keys still shows F9. Click Measure's **M** and press **F9**: refused, "already
   Fresing's key for: Render the picture…". **Reset all** puts F12 back.
4. **Print key sheet**: one page opens in the browser; print or save as PDF.
