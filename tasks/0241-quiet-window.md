# 0241 – A quiet window: the 3D view header, top bar and splash without Blender's editing parts (0222 package A)

**Who:** worker · **Status:** done (0.2.183) · **Branch:** `task/0241-quiet-window`
**Started by:** lead, 20 Nov 2026 (study 0222 package A; owner's answers 20 Nov 16:22: order A → B → C, a Fresing-menu
switch back to all of Blender, splash with Fresing's lines only, the view's grey text kept) · **Model:** Opus · effort
Medium
**Area:** Start & learn lane – a **new** `blender/quiet.py` (all patches of Blender's draw functions in this task);
`blender/lock.py` **only** `blender_ui()` (one call into `quiet.py`, so Full access switches everything at once);
`blender/welcome.py` **only** the splash part (`_draw_splash` and its registration); `blender/ui_header.py` only the
layout tidy (the tool header row, next to 0221's code); `blender/ui_topbar.py` **only** one Fresing-menu entry right below
0221's "Show / Hide Blender's editors" + `entries()` (0230 adds its own "Learn…" entry elsewhere in the same menu –
whoever merges second merges `main`); `blender/ops_workspace.py` / `workspaces.py` only if the switch needs a
"previous workspace" field; `core/functions.py` (new entries, `since=`), the PC-check line, `docs/USER-GUIDE.md`
(+ pictures via `tools/guide_screens.py`), real-app test, tests.

## Goal

A user who does not know Blender sees a quiet window: the 3D view header has only what views the model (View menu,
shading, overlays, X-ray, gizmos) and the app's own Make / Fresing buttons; Blender's editing menus and modelling
settings, the tool header row and the Scene / View Layer selectors are gone; the splash offers Fresing's own lines
(New project, Open…, Recover, recent files, test tour, demo, guide) instead of Blender's templates and links; File > New
gives only **New project**. **Workspace > Full access** and a new Fresing-menu entry **Show all of Blender** bring
everything back in one click.

## Background

- Study 0222's report (`tasks/0222-study-blender-parts-new-users.md`, table rows 3, 4 Select / Add / Object, 5, 6
  selectability, 8, 14, 16, the splash rows, File > New) has the what and why of every part; pictures in
  `tasks/img/0222/`. The measured harm: the splash's **New File > General** opens a scene in metres and EEVEE with
  Blender's layout, while the Fresing panel still loads – it looks like the app but measures and renders wrong.
- The pattern to follow is already in `lock.py`: `_patch` / `_unpatch` swap a Blender class's `draw` /
  `draw_left`; `blender_ui(on)` hides Blender's workspace tabs and folds the toolbar unless the workspace shows
  Blender's UI (`workspaces.blender_ui(scene)` – Full access). Hook this task's patches into that same switch, not a
  new handler or timer.
- **Appended draw functions must survive.** `ui_header.py` appends Make / Fresing to `VIEW3D_HT_header`, `welcome.py`
  prepends the welcome / What's new box to `WM_MT_splash`, `ui_topbar.py` appends the Fresing menu to
  `TOPBAR_MT_editor_menus`. Blender keeps appended / prepended functions on the wrapped `draw` (`draw._draw_funcs`):
  a patched `draw` must still call them in order (or patch only the part that draws Blender's items). Check it with a
  test, also after a patch → unpatch → patch round, and with a second add-on's appended item (a dummy in the test).
- Base the new header / splash / top-bar-right drawing on **Blender 5.2.3's own source** of those `draw` functions
  (read it in the installed Blender's `scripts/startup/bl_ui/`), keeping exactly the items the table says to keep.
- 0221's lesson (CLAUDE.md section 8): changing a 3D view's settings right after a screen change can crash Blender
  5.2.3 – the tool header flag goes through 0221's `settled()` wait / timer, never inside `load_post`.
- The welcome / What's new box stays at the top of the splash (on a real PC it sits on top; under simulated events
  `welcome.py` switches it off on purpose).
- 0230 (lessons) will make the test tour start from a Learn window: the splash's "Take the test tour" line calls the
  **same operator** the Fresing menu's test-tour entry uses, so a later change happens in one place. Likewise the
  "Demo project" line calls the operator behind Help > Make demo project… (0226 package 2 changes what that demo is).

## What to do

1. **3D view header** (outside Blender's-UI workspaces, every 3D view): drop the Object Mode menu, the Select / Add /
   Object menus, transform orientation, pivot, snapping, proportional editing and the "Selectability & visibility"
   drop-down. Keep the View menu, the shading buttons (Solid / Material / Live preview), overlays, gizmos, X-ray and
   the app's appended Make / Fresing buttons. In Edit Mode or any other mode a user reached in Full access, draw
   Blender's own header (never leave a user without the mode menu while in another mode).
2. **Tool header row** (the select-box buttons and Options) off in every 3D view outside Full access, in the same
   layout tidy as 0221; Full access shows it again with the toolbar (`blender_ui(True, toolbar=True)`).
3. **Top bar right part:** the Scene and View Layer selectors not drawn outside Full access; anything an add-on
   appended there still drawn.
4. **Splash:** below the welcome / What's new box, Fresing's lines only: **New project**, **Open…**, **Recover Last
   Session**, the recent files (as Blender lists them), **Take the test tour**, **Demo project**, **User guide**.
   Blender's New File templates, Getting Started links, What's New and Donate are not drawn. The first-start quick
   setup (`WM_MT_splash_quick_setup`) stays as it is. A start whose default workspace shows Blender's UI gets
   Blender's splash.
5. **File > New** (and Ctrl+N, which opens the same list): only **New project** outside Full access. New project =
   exactly what a fresh app start gives (the app template's start: mm, Cycles, the app's layout) – check units, engine
   and layout after it in the real-app test. The Client view's short File menu (`lock._file_menu_locked`) uses the
   same New list and so gets this too.
6. **Fresing menu > Show all of Blender** (owner's answer 1), right below 0221's "Show / Hide Blender's editors":
   switches the project to Workspace **Full access** and remembers the workspace it came from; then the entry reads
   **Back to the Fresing window** and switches back to that workspace (or the default workspace if none is
   remembered, e.g. the user picked Full access in the panel). Greyed in the Client view (tooltip: "Not in the Client
   view – Workspace > Full access unlocks it"). Tooltip: what comes back (Blender's menus, tools, tabs, keys), that the
   project is not changed by it, and how to go back. Icon e.g. `BLENDER`. In `entries()`.
7. **Full access** (panel or menu) brings back **everything** of 1–5 at once; leaving it hides it all again. No restart,
   no reload; the header redraws at once in every window.
8. Guide: the chapter on the window – a short paragraph "What is hidden and how to get it back" + the window picture
   and a new splash picture (`tools/guide_screens.py`); function-list entries (`since=`) for the quiet window and the
   menu entry; PC-check line ("the 3D view header shows View, shading and Make, no Object / Add menus; the splash
   shows Fresing's lines; Fresing > Show all of Blender brings Blender's menus back, Back to the Fresing window hides
   them"). No new tour set unless the precheck asks for one – then a new small set of its own; **do not edit other
   tour sets** (0230, 0231, 0233–0235, 0240 own them).

## Done when

- [ ] New project, the test tour project, the demo and an old own project (saved with Blender's full header) open with
      the quiet header, no tool header row, no Scene / View Layer selectors; Make and Fresing still in the header
- [ ] Splash: Fresing's lines only, every line works (New project gives mm + Cycles + the app layout; Open, Recover,
      a recent file, the tour, the demo, the guide); the welcome / What's new box still on top; screenshot in the report
- [ ] File > New and Ctrl+N: New project only; in Full access Blender's list again
- [ ] Full access and Fresing > Show all of Blender / Back to the Fresing window: everything back and away again,
      repeatedly, the previous workspace restored; greyed in the Client view; a mode other than Object Mode reached in
      Full access keeps Blender's header
- [ ] Appended draw functions kept (Make, Fresing, the welcome box, a dummy add-on item) – unit test + real-app check;
      patch / unpatch / patch round clean
- [ ] Nothing in background runs (queue render, PC check, self-test, kit) patches or draws anything
- [ ] Header width freed at 1920 and 2560 px measured (px) and named in the report; screenshots checked with
      `tools/ui_screens.py` (crop small)
- [ ] Real-app test (new or in `tools/ui_test_layout.py`; a new one goes into `TESTS`, `MIN_CHECKS` and the lightest
      `GROUPS`), pytest for `quiet.py`; guide, function list, PC-check line; precheck green
- [ ] Report filled in, merged, released

## Not in this task

Package **B** (Blender's harmful keys swallowed, F12 / Ctrl+F12 → the app's renders, the short right-click menu) and
package **C** (shorter File / Edit / Render / Window menus, Blender's Help lines into a sub-menu, the side panel's
Tool / View / Animation / Item / glTF Variants tabs) – both come next in this lane. Package D (timeline header, the
view's grey text – owner: keep it for now). The cluttered top of the Fresing side panel (a later study). The lock's
key list (`lock._KEYS`), the Client view's rules, 0221's editors code beyond calling it. The What's new call in
`welcome.py` (0236's).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 20 Nov 2026 (branch `task/0241-quiet-window`).

**What changed:**
- New `blender/quiet.py`: outside Full access the 3D view header draws only the editor-type button, View, gizmos,
  overlays, X-ray and shading (based on Blender 5.2.3's `VIEW3D_HT_header.draw`); in any mode but Object Mode it draws
  Blender's own header. Top bar's right part without Scene / View Layer (`draw_right` replaced like lock.py's
  `draw_left`). Splash: Start (New project, Open…, Recover Last Session, Take the test tour = `fresing.tour_take`,
  Demo project = `fresing.demo_make`, User guide) + Recent Files; the welcome / What's new box stays on top; the
  first-start quick setup untouched. File > New and Ctrl+N (same menu): New project = `wm.read_homefile` with the app
  template (mm, Cycles, app layout – checked in the real app). The Client view's File menu uses the same list.
- Appended functions survive: only Blender's own entry in `cls.draw._draw_funcs` is swapped (`quiet.swap`), so Make,
  the Fresing button, the welcome box and any add-on's items keep their place; also after patch → unpatch → patch.
- Tool header row off in every 3D view (not the Set-up window) from a timer that waits for `editors.settled()` and
  `not editors.busy()` (0221's lesson), never inside load_post. Full access (panel or menu) shows it again with the
  toolbar.
- One switch: `lock.blender_ui()` calls `quiet.apply(not on, toolbar=…)` (the only lock.py change). At the start the
  default workspace decides (`quiet._first`, a timer). Nothing is patched in a background Blender.
- Fresing > **Show all of Blender** / **Back to the Fresing window** (`fresing.blender_all`, icon BLENDER), right below
  Show / Hide Blender's editors: switches to Full access and keeps the workspace it came from (name, own-workspace
  data and family ticks) in `scene["fr_ws_before_all"]` – no props.py change; Back restores it, or the default
  workspace when nothing is remembered. In the Client view the lock greys it (not on the allow-list) and the tooltip
  says "Not in the Client view – Workspace > Full access unlocks it". `ui_test_start.py`'s "every menu entry allowed"
  check now makes that one exception and checks the grey and the reason.
- Function list `help.quiet_window` (headline, short "Quiet window") and `help.blender_all`; PC-check line `app.quiet`
  (MIN_LINES_FULL 111); guide section "A quiet window: what is hidden and how to get it back" + Fresing menu line;
  pictures `quiet_header.png`, `quiet_splash.png`, `app_after_import.png` new (`guide_screens.py` window mode makes
  them); CLAUDE.md layout + a section-8 lesson.

**Tested and measured** (4-core web machine, Blender 5.2.3 under xvfb, no graphics card):
- New real-app test `tools/ui_test_quiet.py` (group pccheck-b, MIN_CHECKS 78): 78/78, 0.6 min – start, splash at
  start, Ctrl+N, File > New, the splash's lines, New project (mm, Cycles, Fresing tab, toolbar folded), Show all /
  Back ×4 with the previous workspace, Edit Mode keeps Blender's header, Client view greyed, Full access from the
  panel and Back to the default, patch/unpatch/patch, an old own project saved with the tool header, a tour and a
  demo project open quiet, a dummy add-on's header / top-bar / splash / File > New items drawn throughout.
- Header width freed (screenshot, header columns with nothing drawn): **465 px** at a 1920 px window (1916 px header)
  and **465 px** at 2560 px (2556 px header); also 465 px at the CI's 1800 px. The dropped items have fixed widths.
- Also run locally: layout 69/69, start 65/65, lock 19/19, clientkeys 12/12; pytest test_quiet (11), functions,
  editors, user guide, about, start, workspaces (+ independent), pccheck, learning, highlight; PC-check lines
  app.quiet + app.editors OK; tooltip report 877 ok; precheck green.
- Screenshot of the splash: `docs/img/quiet_splash.png` (Start column + Recent Files under the Fresing picture).
- No helper agents (no Windows-only code; the change is drawing code checked by the real-app test).

**Open points / follow-up tasks:**
- The welcome box (the first starts) sits above the splash's Fresing picture as before; under simulated events it is
  off, so the real-app test sees only the lines below it – the owner sees both on his PC.
- `fresing.blender_all` remembers the previous workspace in the project; picking another workspace in the panel
  while in Full access does not clear it (Back then goes to the remembered one).
- Packages B and C of 0222 next in this lane.
