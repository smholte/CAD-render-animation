# 0221 – Blender's right-hand column hidden; "Show Blender's editors" in the Fresing menu; a solid side panel

**Who:** worker · **Status:** running (Start & learn lane) · **Branch:** `task/0221-blender-editors-hidden`
**Started by:** lead, 19 Nov 2026 (owner, 00:05: "I want the app as simple as possible, with the needed functions …
most users are not familiar with Blender … but the option to open it easily will be good") · **Model:** Opus · effort
Medium
**Area:** Start & learn lane – `app_template/fresing_render/__init__.py` (`_tidy_screens`, `_after_load`), a new
`blender/editors.py` (hide / show the column, the remembered choice), `blender/ui_topbar.py` (one menu entry +
`entries()`), `blender/welcome.py` only if the choice is kept in its state file; the Client view guard in `lock.py`
(the menu entry refused there – nothing else in the lock); `core/functions.py` (new entry, `since=`), the PC-check
line, `docs/USER-GUIDE.md` (+ picture via `tools/guide_screens.py`), tests.

## Goal

Fresing Render opens with the 3D view filling the window up to the right edge: Blender's **Outliner** (top right) and
**Properties editor** (below it) are gone. Nothing in the app needs them – the Fresing tab has its own parts tree and
every setting the app uses. One click in the top bar's **Fresing** menu, **Show Blender's editors**, brings both back
(the same entry then says **Hide Blender's editors**). The choice is remembered, so a user who wants them keeps them. And the side panel is **solid**, no longer
see-through over the 3D view (owner 19 Nov 00:10: "the UI is now fully see-through, this makes it hard to separate the
different parts of the UI").

## Background

- The app template only tidies the 3D view (`_tidy_screens`: side panel on, toolbar off, Fresing tab, shading,
  clip). The right-hand column is simply Blender's default layout; no code, guide page or tour stop uses it. Owner's
  screenshot (0.2.168, new file): the column takes ~420 of 2560 px.
- 0198 applies the app's layout on every load in the app (new file, tour, demo, own projects – see its report for
  exactly which loads and the *Load UI* handling). Hook the hide into that same place, not a second timer.
- Client view (0062 / 0213, `lock.py`) already swaps any Outliner for Info while the lock is on. 0062's open point:
  "Client view vs Properties editor" – the Properties editor's own settings still get through on purpose
  (`docs/USER-GUIDE.md` line ~209). With the column hidden and the menu entry refused in Client view, a client never
  meets it in the normal layout.
- **See-through side panel:** Blender's preference *Region Overlap* (`preferences.system.use_region_overlap`, on by
  default) draws the side panel over the 3D view, see-through. On a light background (the tour's white solid colour)
  the Fresing panel's texts, boxes and the 3D view run together (owner's screenshots, 0.2.168). The app never set it;
  the guide pictures are already made with it off (CLAUDE.md section 8, "Real-app screenshots").
- The timeline at the bottom stays (Animation uses it). Not this task: the other Blender parts a new user may not
  need – that is study 0222.

## What to do

1. **Hide** (every window's screen that has the default column; in the app only – never in background, PC check,
   self-test, kit or queue runs): close the Outliner and Properties areas that sit to the right of the main 3D view so
   the 3D view takes their room. Blender 5.2: `bpy.ops.screen.area_close()` under `context.temp_override(window=…,
   screen=…, area=…)`; check what Blender does when both are closed (the 3D view should grow, not the timeline) and
   on a screen where the user has split things differently (only close an Outliner / Properties area that borders the
   main 3D view on its right; leave any other layout alone).
2. **Show** brings the column back the way Blender has it by default: split the main 3D view at its right side (about
   the default width – measure Blender's factory layout at 2560 and 1920 px), Outliner on top (about a third), the
   Properties editor below. Second click hides again.
3. **Remembered choice:** one user-level setting (the app's own settings file, like the welcome / What's new state –
   not the project). Default **hidden**. Every load that 0198 tidies follows it. A project saved with the column shown
   by a user who has "hidden" chosen opens hidden – the user's choice wins over the file.
4. **Fresing menu:** one entry next to "Show the Fresing panel": **Show Blender's editors** / **Hide Blender's
   editors** (icon e.g. `PROPERTIES`), tooltip: what the two editors are, that Fresing Render does not need them, that
   they are for users who know Blender, and that the choice is kept. Add it to `entries()`.
5. **Client view:** the column is hidden while the lock is on and the entry is greyed (tooltip says why: "Not in the
   Client view – Full access brings it back"); switching the lock off puts back what the user had chosen.
6. **Solid side panel:** the app switches *Region Overlap* off – at the first start of this version and whenever
   Blender's preferences are reset (`_set_preferences`); remember in the app's settings that it did, so a user who
   turns it on again in Edit > Preferences > Interface keeps it. Check the side panel, the navigation gizmo, the 3D
   view header and the Fresing panel's boxes at 1920 and 2560 px, light and dark backgrounds; the view still frames
   the model in the visible part (View all / camera buttons).
7. Guide (a short paragraph + the cleaner window picture where the guide shows the whole window), function-list entry
   (`since=`), PC-check line ("the 3D view reaches the right edge; Fresing > Show Blender's editors brings the
   Outliner and Properties back; again hides them"). A tour stop only if the precheck asks for one.

## Done when

- [ ] New file, the test tour project, the demo and an old own project (saved with the column) open with no Outliner
      / Properties column and the 3D view to the right edge; the Fresing side panel still on the Fresing tab
- [ ] Show / Hide works both ways, repeatedly, at 1920 and 2560 px; the choice survives a restart (real-app test as
      0198 / 0213 use)
- [ ] Client view: hidden, entry greyed; lock off → the user's choice back
- [ ] Region Overlap off after the update on an existing install and on a fresh one; a user's own "on" kept after a
      restart; the side panel solid on the tour's white background (screenshot in the report)
- [ ] Nothing in background runs touches screens or preferences (queue render, PC check, self-test still green)
- [ ] Screenshots checked with `tools/ui_screens.py`; guide, function list, PC-check line; precheck green
- [ ] Report filled in, merged, released

## Not in this task

Blender's other parts (header menus, Object Mode menu, the splash's Blender items, the timeline) – study 0222 lists
them and the owner picks. The lock's list of allowed editors (`lock.py ALLOWED` / `LOCKED_TYPES`) beyond refusing this
one menu entry. Any panel inside the Fresing tab.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 20 Nov 2026

**What changed:**
- New `fresing_render/blender/editors.py`: finds Blender's column (an Outliner or Properties editor whose left edge
  touches the main – biggest – 3D view's right edge and lies beside it; an Outliner the Client view turned into Info
  counts too), closes it (`screen.area_close`) or splits it off the 3D view again (Blender's factory width, 17.7 % of
  the window, Outliner 18.4 % of the column on top). Any other layout is left alone.
- The choice: `<config>/fresing_layout.json` (`editors` hidden / shown, `overlap_off`), default hidden. Every load
  `ui_header._on_load` tidies follows it; Client view (`lock.apply`) hides it and the entry is greyed with "Not in the
  Client view – Full access brings it back"; lock off → the user's choice back.
- Fresing menu: **Show / Hide Blender's editors** under "Show the Fresing panel" (icon PROPERTIES), in `entries()`.
- Region Overlap off: once in the app (remembered, a user's own "on" is kept) and in the template's `_set_preferences`
  (preferences reset). Never in a background Blender.
- **Blender crash found and avoided:** setting a 3D view's settings (`show_region_toolbar`) right after `area_close`
  segfaults Blender 5.2.3 until the window is drawn again (reproduced in plain Blender; also crashed when closing
  inside `load_post`). Screens are changed from a timer; a POST_PIXEL draw handler marks `settled()`, and
  `put_layout_right` / `apply` wait for it. Lesson added to CLAUDE.md section 8.
- First GitHub run (44765162821) red, three causes, all fixed: (1) `ui_test_tour.py` crashed Blender – the test tour's
  `ops_tour._go_pending` set the side panel right after the column was closed (the same Blender crash); it now waits
  for `editors.busy()`. (2) "Set up a crane": a project opened and the Set-up window split the 3D view at once, before
  the deferred close – the view then grew under it ("the split-off view did not get its size"); `ops_setup.open_window`
  waits for `editors.busy()` and finds the 3D view again. (3) `ui_test_flex.py` / `ui_test_paths.py` /
  `ui_test_spool.py` took the side panel's width off the view's region (right only with Region Overlap on); the flex
  test also looks closer at its 10 mm cable (the view is narrower with a solid side panel).
- Tests: `tests/test_editors.py` (12: column finding on measured factory / shown layouts, other layouts untouched,
  swapped Info, width, settings file, menu, grey, background touches nothing, the Client view's index list);
  `tools/ui_test_layout.py` +28 checks (new, own project saved with the column, old project, tour set, demo: hidden,
  view to the right edge; Show / Hide, five fast clicks, Client view grey and back, Region Overlap off and a user's
  "on" kept); `ui_test_lock.py` (the timeline becomes the Outliner to guard), `ui_test_panel.py` (Client view: no
  column; Full access: the user's "shown" back). PC-check line `app.editors`, function `help.blender_editors`, guide
  section "Blender's Outliner and Properties (hidden)", Client-view text, picture `app_after_import.png` made again.

**Tested and measured** (4-core web machine, real Blender 5.2.3 under xvfb, no model needed):
- Real-app: layout 69/69, panel 39/39, lock 19/19, client keys 12/12, tour 15/15, flex 31/31, cables 36/36,
  set-up crane 32/32, set-up 46/46, highlight 74/74, start 63/63. pytest of the changed areas green.
- Show / Hide at 1920 x 1080: column 337 px (Blender's own 339); at 2560 x 1440: 450 px (453). Hidden: the 3D view
  and the timeline both reach the right edge (1916 / 2556 of 1920 / 2560).
- Side panel on a white viewport background at 2560: solid, the navigation gizmo and the header visible.
- GitHub runs: see below.

**Open points / follow-up tasks:**
- A new window (Window > New Main Window) or switching to another of Blender's workspaces in Full access is not tidied
  until the next load (the Layout workspace is the one the app uses).
- The owner's check on his PC: the update turns Region Overlap off once – a look at 2560 px with his own projects.
