# 0271 – Fresing Settings: one window with tabs along the top (My usage becomes one of them)

**Who:** worker · **Status:** running · **Branch:**
`claude/kind-ramanujan-ad52mb`
**Started by:** lead, 21 Nov 2026 (owner 17:27: "there should be a Fresing settings menu – also My usage would be a
part of this; you should be able to select between the different settings pages on the top of the menu") ·
**Model:** Opus · effort Medium
**Area:** Settings lane (new) – `blender/prefs.py` (draw code only: the properties stay where they are), a **new**
`blender/ui_settings.py` + `blender/ops_settings.py`, `blender/ui_usage.py` / `ops_usage.py` (My usage drawn as a tab;
Usage lane), one entry in `blender/ui_topbar.py`'s Fresing menu and one gear button on 0260's left panel (additive),
their tests, a real-app test, the guide, CHANGELOG. May run beside 0253 (it only adds the menu entry in `ui_topbar.py`).
**Not:** what the settings do (no setting changes meaning here); file locations (0272 adds the Locations and Exports
tabs); the material picker (0273).

## Goal

All of Fresing Render's own settings in **one window, "Fresing Settings"**, with a row of tabs along its top. The
user clicks a tab to change page. Today they are spread over Edit > Preferences > Add-ons > Fresing Render (where a
non-Blender user never looks), the Help menu's **My usage…** dialog (the owner's screenshot) and a few side-panel
switches.

## What to do

1. **The window** – built like 0260's output windows / the Set-up window (`ops_setup.py`, `ui_setup.py`): a small app
   window that can be dragged (also to a second monitor), stays open when the user clicks elsewhere, opens tidy (no
   Blender header / editors, 0221), opening it again brings it to the front, remembers its size, place and **last
   tab**. Title "Fresing Settings".
2. **The tab row at the top** (one row of buttons, the open one highlighted; wraps to a second row only when the
   window is narrow). Pages – start with these and say in the report if a split reads better:
   - **General** – default template, default rule set, workspace for new projects, hover highlight, the shared library
     folder (until 0272 replaces it with Locations);
   - **Side panel** – keep sections as I left them, keep How it works open, Favourites bar on / buttons (from My
     usage), offer to hide unused panels / teach unused functions / suggest what to learn next (from My usage);
   - **Lessons** – highlight button / section / part look, colour, Play on;
   - **Backups** – today's box (`draw_backups`);
   - **Updates** – today's box (`draw_updates`);
   - **My usage** – the rest of today's My usage dialog as it is (counts, favourites list with pins, where your time
     goes, time saved, learning list, profile export / import, back to the workspace as it came, clear my usage data);
   - **About** – 0206's About content (version, © Fresing, GPL, Licence / Third-party / Company use buttons).
   Leave a clear place (and a test that lists the tabs) for 0272's **Locations** and **Exports** tabs and 0273's
   **Materials** tab.
3. **Ways in:** Fresing menu > **Settings…** (with a gear icon); a gear button on the left panel (0260); Help >
   **My usage…** opens the window on the My usage tab (the old dialog goes); Edit > Preferences > Add-ons > Fresing
   Render shows one line and a button **Open Fresing Settings** (the properties stay registered there so old projects,
   scripts and tests keep working).
4. **My usage's time counts only real presence** (owner 21 Nov 17:39: "does it measure time when I'm AFK?"). Today
   (`blender/usage.py`, 0181) a gap of more than 2 min (`core.usage.IDLE`) is left out, but the marks that say "the
   user is here" include **any project change (`depsgraph_update_post`) and any redraw of the favourites bar** – both
   also happen with nobody at the PC: playback looping, Live preview / a render updating the view, the queue, a re-bake,
   timers. Lead's reading of the code, **not measured**: an AFK owner with playback or a render running may be counted
   as working. Check it (play an animation, start a long render, leave a Live preview on – no input for 10 min – and read
   the stages), then make only **the user's own input** count: a click, a key, mouse movement over an app window,
   opening a panel, a change the user made. Time while the app renders or plays by itself with no input counts nowhere
   (or, if you think it is useful, under its own line "Rendering / playing (not your time)" – say which). The trailing
   up-to-2-min after the last input stays as it is. Add a test with simulated playback and no input; one line on the
   My usage tab: "Counts only while you use the app; away more than 2 min is left out".
5. **Client view:** the window opens; anything that is refused there today stays refused (0213).
6. **The guide:** one chapter "Settings" with a picture of each tab; the old "Edit > Preferences > Add-ons > Fresing
   Render" sentences in the guide and `docs/COMPANY-USE.md` point to the new place.

## Done when

- [ ] Fresing > Settings… opens the window; every tab draws (real-app test clicks each tab and checks the window keeps
      its last tab after closing and reopening)
- [ ] My usage lives in the window; Help > My usage… opens that tab; nothing of the old dialog lost (counts, pins,
      export / import, clear)
- [ ] My usage counts no time while the app plays or renders by itself with no input (test + the owner's check)
- [ ] Add-ons page shows Open Fresing Settings; old preferences values kept after the update (test with a settings file
      from 0.2.19x)
- [ ] Function list (`core/functions.py`), PC-check line, guide pictures, CHANGELOG; `since=` on new entries
- [ ] Report filled in (owner's check steps, numbered, click by click), merged, released

## Not in this task

New settings; locations (0272); materials (0273); the side-panel look of study 0244.

---

## Design (worker, 21 Nov 2026)

- **Window (as built, after the owner's check of 21 Nov 20:30):** the output-window pattern of 0260 –
  `ops_setup.open_window(mark="fr_settings", size=(440, 640))` – but the page is drawn in the copy's **toolbar region**
  (the region of 0260's left panel), not its side panel. `ops_setup._dress` turns the side panel, header, tool header,
  gizmos and overlays off and the toolbar on; `ops_settings._settle` makes the toolbar as wide as the window once it
  was drawn (`ui_left.fit_width`: 0260's stored-width writer, scaled by the region's own pixels / stored width);
  Blender's tool buttons (`VIEW3D_PT_tools_active`, the toolbar's only panel of Blender's) get a `poll` that hides them
  in this window (`ops_settings.quiet_panels`, registered again). Places on Windows: `ops_make.place_key` = "settings".
  `panels.SIDE_MARKS` and `ops_setup.tab_of` know the mark.
- **Pages:** `ui_settings.TABS` (key, title, icon, draw); `LATER` names 0272 / 0273's pages. Last tab =
  `prefs.settings_tab` (hidden, kept in the user's preferences). Drawing only: `prefs.draw_general / draw_side_panel /
  draw_lessons / draw_backups / draw_updates`, `ops_usage.draw_window` (My usage) + `draw_panel_switches` (Side
  panel), `about.draw_about`.
- **Presence:** `ops_settings.FRESING_OT_presence` in the add-on keymap "Window" (MOUSEMOVE, clicks, wheel; returns
  PASS_THROUGH) → `usage.presence` (a move counts only when the mouse is somewhere else; at most once a second). The
  old marks (`depsgraph_update_post`, the favourites bar's draw) are gone.

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 21 Nov 2026 – 0.2.201

**What changed:**
- **Where the page lives (owner's check 21 Nov 20:30: only the page, no tabs, no view, no headers).** First built in
  a 3D view's side panel: Blender's tabs Tool / View / Animation stood beside ours. Tried next: a **Text editor's
  sidebar** (its two Blender panels hidden) – it still drew a tab strip, "Text", and even with our page alone one tab
  "Misc": Blender 5.2.3 draws a tab strip on every sidebar. Console, Info and Outliner have no sidebar; the Spreadsheet's
  has a Filters tab made in C. **Picked: the 3D view's toolbar region** (where 0260's left panel lives): it has no tab
  strip at all, its only Blender panel (the tool buttons) is hidden there, and with header, side panel and overlays off
  and the region as wide as the window, nothing of the 3D view shows. Left: Blender's two tiny arrows that every hidden
  header / sidebar gets (top right, right edge).
- **Fresing Settings** window (`ops_settings.py`, `ui_settings.py`): tabs General · Side panel · Lessons · Backups ·
  Updates · My usage · About (4 + 3 on two rows at 440 px; one row from ~620 px). Ways in: Fresing > Settings…, a gear
  on the left panel (also in its folded strip), Fresing / Help > My usage… (on My usage; the old dialog is gone), and
  Edit > Preferences > Add-ons > Fresing Render (one line + **Open Fresing Settings**; every property is still
  registered there with the same name and default – `tests/test_settings_blender.py` holds the 0.2.198 list).
- Split I chose: the favourites bar's switch / size and the three question switches went to **Side panel**; My usage
  keeps tracking, the counts with pins, time per stage, time saved, the learning list's days + My learning list…,
  Back as it came, export / import, clear. About keeps its own window too (Fresing > About…).
- **Presence:** only the user's own input counts (above). Time while the app plays or renders by itself counts
  **nowhere** (no extra "not your time" line). My usage says "Counts only while you use the app; away more than 2 min
  is left out".
- Function `help.settings` (since 0.2.199), `usage.my_usage` changed; PC-check line `app.settings`; tour stop
  `settings` (crane set changed); guide chapter "Fresing Settings" with 6 pictures + the My usage picture; the guide's
  and `docs/COMPANY-USE.md`'s "Edit > Preferences > Add-ons" sentences point to the window.

**Tested and measured** (4-core web machine, real Blender 5.2.3 under xvfb):
- `tools/ui_test_settings.py` (new, 34 checks): each tab clicked with a simulated mouse click, page shown; the window
  stays open after a click in the main window; a second press gives no second window; closed and opened again it is
  on the last tab; My usage… opens it on My usage; Client view opens it; a workspace change with it open; and (the
  owner's check) **the window shows only the page**: no side panel / tab strip, no header, tool header, overlays or
  gizmos, no other panel in its region, the page fills the window (458 of 463 px) – at its first and second opening. `ui_test_usage.py` (31/31) and `ui_test_left.py` (31/31) still pass.
- **The AFK check** (step 4, measured with no input, the idle limit set to 4 s for the test): playing a 60-frame
  animation 9.2 s fired the old marks 1 + 1 times (one project change, one left-panel draw), Live preview (Cycles
  viewport) 9.4 s fired 0 + 1. So on this machine the old code would mostly **not** have counted an idle playback or
  Live preview either – the lead's worry was not confirmed for those two; what does fire changes by itself is the
  app's own timer work (queue, re-bake, a render job), which the pytest simulates. Now: 0 presence marks and 0 s
  added in both cases; mouse moves every ~0.2 s for 3 s added 2.3 s. A render (F12) was not measured.
- pytest: `test_settings_blender.py` (12, incl. 10 min of frame changes + project changes with no input → 0 s), and
  the files of the touched areas (398 + fixes). Test tour (`test_tour.py`): see below.

**Runs on GitHub:** (filled in below)

**Open points / follow-up tasks:**
- Keyboard-only work (no mouse move for over 2 min while typing shortcuts) is not seen as presence: Blender gives an
  add-on no key events without a modal handler. Mouse moves are almost always there.
- The window's size on Linux/macOS is fixed at 463 x 664 px (UI scale 1); on Windows it reopens where and as big as
  it was left. A window made wider or narrower by hand keeps its page width until it is opened again (then empty
  space or a cut page at the right; not tested on Windows).
- Blender's two tiny arrows of the hidden header and sidebar stay at the window's edges (Blender draws them for any
  hidden region).
- The owner's check on his PC (below).

**Owner's check on your PC:**
1. Install the update (Update now), start Fresing Render.
2. Click the menu **Fresing** (top bar, after Help) > **Settings…** – a window "Fresing Settings" opens with seven
   tabs at its top.
3. Click each tab: General, Side panel, Lessons, Backups, Updates, My usage, About – each shows its page.
4. Drag the window to your second screen, click in the main window: it stays open. Click **Lessons**, close it with
   the **X** at its top right, then click the **gear** at the top of the left panel: it opens again on Lessons, where
   you left it.
5. **Help > My usage…**: the same window, on My usage. Note the time next to **Render & export** (or the stage you
   used last).
6. Build & play an animation, then leave mouse and keyboard alone for 10 minutes. Come back, open My usage again: the
   stage's time has grown by at most 2 minutes.
7. **Edit > Preferences > Add-ons**, open Fresing Render: one line and the button **Open Fresing Settings**; your
   earlier settings (e.g. Backups' numbers) are unchanged in the window.
