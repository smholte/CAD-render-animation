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

- [ ] Tests: the list is built from the live key lists (a new key in `lock.py` shows by itself); a changed key works
      and survives a restart; a clash warns; Reset
- [ ] Real-app test of the tab and a changed key; guide + picture; function entry; PC check line `settings.keys`; full
      suite + GitHub run green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
