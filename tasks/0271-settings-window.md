# 0271 – Fresing Settings: one window with tabs along the top (My usage becomes one of them)

**Who:** worker · **Status:** open – waits for 0260 (same window pattern, same menus) · **Branch:**
`task/0271-settings-window`
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
4. **Client view:** the window opens; anything that is refused there today stays refused (0213).
5. **The guide:** one chapter "Settings" with a picture of each tab; the old "Edit > Preferences > Add-ons > Fresing
   Render" sentences in the guide and `docs/COMPANY-USE.md` point to the new place.

## Done when

- [ ] Fresing > Settings… opens the window; every tab draws (real-app test clicks each tab and checks the window keeps
      its last tab after closing and reopening)
- [ ] My usage lives in the window; Help > My usage… opens that tab; nothing of the old dialog lost (counts, pins,
      export / import, clear)
- [ ] Add-ons page shows Open Fresing Settings; old preferences values kept after the update (test with a settings file
      from 0.2.19x)
- [ ] Function list (`core/functions.py`), PC-check line, guide pictures, CHANGELOG; `since=` on new entries
- [ ] Report filled in (owner's check steps, numbered, click by click), merged, released

## Not in this task

New settings; locations (0272); materials (0273); the side-panel look of study 0244.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
