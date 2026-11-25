# 0332 – Quiet window and Client view lock (0328 F3)

**Who:** worker · **Status:** done · **Branch:** `task/0332-quiet-window-client-lock`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Opus · effort Medium
**Area:** Start & learn lane (quiet window) – after **0295** (both change `lock.py`) – `blender/quiet.py`, `blender/lock.py` (key lists: F2 / Ctrl+F2 / Ctrl+, and the render key), `blender/ops_settings.py` (`quiet_panels`, its use for the main view only), `blender/ops_workspace.py`, their tests, guide, CHANGELOG.
**Not:** the Keys tab (0295, done before you), menus and side-panel tabs as a whole (0222 package C later).

## Goal

"Back to the Fresing window" always brings the app's layout back; the Client view really locks (no renaming, no Preferences); a rendered picture shows whole and fitted with the app's words; outside Full access no Blender sidebar tabs and no redo panel.

## What to do

Fix 0328's rows **5, 7, 13 (the F12 key in `lock.py` and the image editor's header in `quiet.py`; the Render image button's fit is 0334's, in `ops_main.py`), 27, 28** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Rows 7 and 5 first.

## Watch

- Each row's **repeat case** and **proposed fix** are in `tasks/0328-bug-and-friction-hunt-8.md` ("Rows" table) – read those rows first, repeat the
  case, then fix. The proposed fix is a proposal: a better one is fine, say why in the report.
- Row 32's words: change only the words that are in **your** files (the row lists them by place).
- Every visible change: tooltip, user guide, PC-check line, tour stop / function-list entry with `since=` / `changed=`
  (CLAUDE.md section 2). Real-app check (`tools/ci_real_app.py`) for every row that was seen in the real app.
- Two tasks never share a file: stay inside **Area**; a needed change elsewhere → open point in the report.

## Done when

- [ ] Each row's repeat case now gives "what should happen" (a test per row; real-app check where it was seen there)
- [ ] Tests added/updated; full suite passes; GitHub run green
- [ ] (UI) screenshots checked with tools/ui_screens.py
- [ ] Guide, PC-check line, tour / function-list version fields as CLAUDE.md section 2 asks
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25 Nov 2026 (0.2.258)

**What changed:**
- **Row 5** (`quiet.py`): when Full access begins the main window's Blender workspace is remembered (`LOUD_WS`); when the
  window turns quiet again (Back to the Fresing window, or any workspace but Full access) the main window goes back to
  it – else to "Layout", the app's own (a project opened in Full access remembers nothing). Done from the existing
  tool-header timer, one tick before the views are set. Proposed fix said "in Back"; doing it at the quiet switch also
  covers Workspace > another workspace.
- **Row 7** (`lock.py`): F2, Ctrl+F2 ("Window" keymap) and Ctrl+, ("Screen") join `BLENDER_KEYS`: swallowed outside Full
  access, the lock's message (+ `SWALLOWED`) in the Client view. Quiet **Edit** menu (Undo, Redo, Undo History, Menu
  Search, Fresing Settings…) and **F4** file menu (New, Open, Open Recent) via `quiet.swap`. `keys.py` (0295's, one dict
  line): the Keys tab names Window / Screen keys "everywhere" instead of "3D view".
- **Row 13** (`quiet.py`): `IMAGE_HT_header` swapped for a Render Result: View, Fit, "Saved: <file>", Open, Show in folder,
  Close (`render.view_cancel`); Blender's own header for any other image. Blender's "Frame / Time / Mem" text over a
  finished render (`overlay.show_text_info`) off while quiet, back in Full access. F12 needed no change: it runs
  `fresing.render`, so 0334's fit reaches it (measured: 960×540 at zoom 1.022 in a 991×575 region).
- **Row 27** (`ops_settings.py`): the tab panels' hiding `poll` also returns False in the main window while quiet and in
  Object Mode (`quiet_main`). Blender's **Item** tab still shows with a selected object: its Transform panel is C code,
  no `poll` can be put on it (as in 0308's output windows).
- **Row 28**: workspace_pick, family_toggle, workspace_show_used, workspace_all lose REGISTER (keep UNDO: one undo step,
  tested); every main 3D view's redo panel (`show_region_hud`) off while quiet, on in Full access – covers Build & play
  without touching `ops_main.py`. **Found:** setting `show_region_hud = True` from a timer segfaults Blender 5.2.3 (also a
  plain `--factory-startup` Blender); with the area in `temp_override` it works (`quiet._set_hud`). CLAUDE.md section 8.
- Row 32's words: none of the listed places is in this task's files.
- PC-check line `app.quiet` checks the new swaps, keys, REGISTER and the workspace to go back to; function entries
  `help.quiet_window`, `help.blender_all`, `help.blender_keys`, `panel.client_view` `changed="0.2.258"`; guide sections
  quiet-window, client-view, keys-and-right-click; `MIN_CHECKS["quiet"]` 90 → 125.

**Tested and measured** (4-core web machine, Blender 5.2.3 under xvfb, no graphics card):
- New `tests/test_quiet_client_0332.py` (12 tests, one or more per row) + the quiet / keys / workspaces / render-view /
  guide / functions tests: 257 passed locally.
- Real app `ui_test_quiet.py` with new steps per row (Animation tab → Back → Layout; F2 / Ctrl+F2 / Ctrl+, simulated
  in the Client view: 3 of 3 refused, no window, no rename; Edit menu drawn quiet; F12 on a cube → saved, fitted, app
  header, text info off, Close closes; HUD and side tabs checked at every quiet / Full access state): 129/129.
  `lock`, `clientkeys`, `keys` real-app tests: 12/12, 30/30, 19/19. PC-check lines app.quiet + app.keys: OK.
- Screenshots looked at: the render window (header row as described) and the layout after Back (real-app shots, not
  `ui_screens.py`: no side-panel panel changed). Guide pictures not redone (no panel changed).
- GitHub runs: 2 full runs. The first failed one check in `ui_test_layout.py` (it opened Blender's "View" side-panel tab,
  which the quiet window now hides): it opens the Item tab with an object selected. The second: all green.

**Open points / follow-up tasks:**
- Blender's **Item** tab (C panel "Transform") still shows beside Fresing when a part is selected outside Full access.
- The Keys tab's "Blender's own keymap" button (`keys.py`) still opens Blender's Preferences (Keymap) – also in the
  Client view if Fresing Settings is reachable there; the lead may want it greyed in the Client view (0295's area).
- While a render runs the image editor still shows Blender's progress text (wanted: it is the progress).
