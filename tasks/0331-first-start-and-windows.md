# 0331 – First start stays open; windows open in a good place (0328 F2)

**Who:** worker · **Status:** running · **Branch:** `task/0331-first-start-and-windows`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Opus · effort Medium
**Area:** Start & learn lane – `blender/first_setup.py`, `core/first_setup.py`, `blender/welcome.py` (only for row 1), `blender/ops_setup.py`, `blender/ops_make.py`, `blender/form_window.py`, the product video panel, `blender/ops_backups.py` (words only), their tests, guide, CHANGELOG.
**Not:** `lock.py`, `ops_settings.py`, `ui_settings.py`, `ui_topbar.py` (0295 runs there), `quiet.py` (0332), `ui_web3d.py` (0336).

## Goal

A new user sees "Set up Fresing Render" and it stays until Next / Skip / Close; every function / output window opens beside the side panel or over the middle of the view (the next one a little offset), never empty for seconds, never splitting the main window.

## What to do

Fix 0328's rows **1, 12, 25, 34 + the 0213 open point (Set-up window Back / Next in the Client view) + the "Your PC" words and the backups words of row 32** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Row 1 first (a new user's first minute). **Ask the owner once** to try a fresh first start on his PC: give him steps that do not lose his own settings (or a way to put them back), and the "For the lead chat" text to paste back. Do not wait for his answer to fix row 1.

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

**Chat / date:** Claude Code on the web, 25 Nov 2026 · branch `claude/bold-edison-5jujsc` (the session's branch) · 0.2.250

**What changed:**
- **Row 1** – `first_setup._on_load` closed *every* set-up window a moment after any load, also the start-up file's own
  load at the first start (the set-up opened ~3.5 s later and was closed by that timer). Now it notes the set-up windows
  that are there **at the load** (the opened file's own) and closes only those (`_window_key`, `close_window(only=)`).
  Better than a generation number: a window made after the load is never in the set.
- **Row 12** – `core/window_place.py`: the first place (client top-left just left of the side panel, 36 px under the
  view's top; over the view's middle when it does not fit; each further app window 30 px left and down, 6 places) and
  the turn into a Windows outer rectangle. `ops_setup._finish` → `_first_place_later` (timer, up to 8 tries) →
  `first_place` → `winplace.place`, only when no place is kept (`ops_make.kept_place`). Windows only: Blender gives no
  way to move a window elsewhere; on Linux/xvfb (no window manager) windows stay where X puts them.
- **Row 25** – `ops_setup._tidy`: a job dropped (`not _alive`) or failed closes its split pieces until the main window has
  as many areas as before; `_open_window` refuses while another window is being made.
- **Row 34** – `ui_motion._draw_product_video(window=True)` from the output window: the settings without a fold.
- **0213** – the Set-up window's last line in the Client view: "Client view: set-ups are locked. Workspace > Full access
  unlocks them" (`ui_setup.LOCKED_TEXT`, at the bottom so nothing moves).
- **Row 32 words** – `core/first_setup.window_words` ("The window is drawn by the graphics card …" / "… without a
  graphics card (by the processor) …"); `ops_backups`: "switched off: Fresing Settings > Backups switches them on".
- Guide (App windows' first place, Set-up window in the Client view, Your PC, set-up stays), CHANGELOG, function list
  `changed="0.2.250"` (help.first_setup, panel.setup_window, animation.product_video), PC-check line `app.window_place`
  (MIN_LINES_FULL 156), real-app checks: firstsetup 43, setup 48.

**Tested and measured** (4-core web machine, Linux, Blender 5.2.3 under xvfb; test crane / gantry):
- `ui_test_first_setup.py` **before**: 28/53 – the window closed itself (repeats 0328 row 1). **After:** 43/43, incl. "the
  set-up stays open 4 s after it opened".
- `ui_test_setup.py` 48/48: the first place worked out for a real Set-up window lies beside the side panel; a forced
  failure in `_finish` + a second open meanwhile → no window, main window's areas exactly as before, not busy.
- pytest: `test_window_place.py` (new, 8), `test_first_setup.py` (+6), `test_setup_window.py` (+7: Client-view line,
  `_tidy` with fakes, second open refused, product video without a fold) – 216 passed in the touched files.
- PC check `app.window_place` + `app.first_setup`: OK (bpy module).
- Independent review (helper agent, sonnet) of the Windows-only part: signs right; found three faults – a shared key
  "setup" would have moved the wrong window, no retry while the handle is not found, stale sizes right after the pieces
  close. All three fixed (own key per Set-up window, a timer with retries).
- Not done: screenshots with `ui_screens.py` (the only drawn change is one hint line, checked by the fake-layout test).
- GitHub runs: see below.

**Open points / follow-up tasks:**
- **Owner's PC:** the window placement can only be seen on Windows (steps below).
- Row 12 "draws empty or half-fitted for 1–3 s": not changed – the settle of the page windows is in `ops_settings._settle`
  (not this task's file). Blender's tabs (Item / Tool / View) in the **Set-up** window: hiding them needs
  `ops_settings._in_settings` to include Set-up windows (`ops_setup.is_setup_window`) – for the task that owns
  `ops_settings.py`. The Picture window's "Item" tab is Blender's C panel (0308 note): stays.
- Row 32's other words (context menu, ui_motion, tour.py's backups `where=`, ui_web3d, …) are other tasks' files.
- `ui_top.py`'s Make popover still draws the product video's fold (not this task's file; a popover, small).

**For the owner – try a fresh first start on your PC (your settings stay safe):**
1. Close Fresing Render.
2. Press Windows key + R, type `%LOCALAPPDATA%\FresingRender\blender-5.2.3-windows-x64\portable` and press Enter.
3. Right-click the folder **config** → **Rename** → call it **config my settings**. (Only your settings move aside;
   the app itself stays.)
4. Start **Fresing Render** from the Desktop. You should see **Set up Fresing Render** open and **stay** open; it should
   stand just left of the side panel, not in the top-left corner. Click Next through it, or Skip set-up.
5. Open Fresing > Settings…, then Fresing > Learn…: each opens beside the side panel, the second a little left and lower.
6. Put your settings back: close Fresing Render, delete the new folder **config** in that same place, rename **config my
   settings** back to **config**.
7. Paste to the lead chat: "0331 first start: set-up stayed open YES/NO; set-up window beside the side panel YES/NO;
   Settings and Learn offset YES/NO; anything odd: …"
