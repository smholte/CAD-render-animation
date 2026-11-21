# 0260 – Two panels: the steps on the right, everything else on a new left panel; Make as a folding icon row; the Learning hub with a one-click mode switch

**Who:** worker · **Status:** done (0.2.197, 21 Nov) ·
**Branch:** `claude/peaceful-edison-wjm578` (the web session's branch)
**Started by:** lead, 21 Nov 2026 (owner 14:44 with four screenshots, picks 14:50) · **Model:** Opus · effort High
**Area:** Start & learn + Usage lanes –
- `fresing_render/__init__.py` (`_all_classes()` panel order only), `blender/ui_top.py` (Workspace, What's next, tabs,
  Make), `blender/ui_usage.py` (Favourites), `blender/ui_tour.py` (the tour panel), `blender/ui_lesson.py` (Lesson
  panel – placement only), `blender/updates.py`'s notice panel (placement only), `blender/panels.py` /
  `blender/ui.py` only where a panel needs to know which side it is on;
- a **new** `blender/ui_left.py` (the left panel: its region, its order, its fold state) if that is cleaner than
  spreading it over the files above;
- the **visible name** "Test tour" → "Learning hub" everywhere a user reads it: `welcome.py`, `ui_topbar.py` (Fresing
  menu entries), `ops_tour.py` / `ops_learning.py` / `learning.py` / `lesson.py` labels and messages, `core/functions.py`
  titles, the PC-check's visible lines, `docs/USER-GUIDE.md`, the landing page if it names it; in `blender/tour.py`
  **only user-visible strings** (stop texts that say "test tour") – 0234 is running in its own sets there: merge `main`
  first, change only those strings, merge `main` once more at the end;
- real-app tests, tests, guide pictures (`tools/guide_screens.py`), the PC-check line, CHANGELOG, CLAUDE.md section 3.

**Not:** internal names (`tour.py`, `fresing.tour_*` operator ids, `TOUR` constants, file names, test names, the tour
project's file name if a user's old projects depend on it – say in the report what you kept and why); `lock.py` and the
right-click menu (0253, next in this lane); Blender's own top-bar menus and side-panel tabs (0222 package C); the
side-panel *look* of study 0244 (colours, frames, green arrows – it comes after this task and must then cover both
panels); the tour sets themselves (0233, 0234, 0259 own them); the test models.

## Goal

The right-hand Fresing panel shows **only the work**: the section tabs (All 1 … 8), Make, Set-up window… and the steps
1–8. Everything else – the update notice, the workspace switcher, Favourites, the Learning hub, What's next / Next to
learn, the tour's stop list and the Lesson panel – moves to **a second panel on the left side of the 3D view**, so the
first step is always at the top of the right panel. The test tour is called the **Learning hub**, and its three ways to
learn are one click away.

## The owner's picks (21 Nov 14:44–14:50)

The owner's screenshots: everything in the red boxes (update notice, workspace switcher, Favourites, What's next with
Next to learn, and the Make block) leaves the right panel; the left edge of the 3D view (purple, where Blender's folded
toolbar sits) holds the new left panel. Picks from the lead's mock-ups A / B:

1. **Make stays on the right (A), above the steps.** The word **"Make" in white** (not green). **Folded** (the default):
   one row – "Make" and the six icons (Picture, 3D page, Product video, Animation, Turntable, Queue); **each icon opens
   that output's settings in a window of its own** with its own Make button. **Click "Make"** and it folds down into
   today's labelled list (2 × 3, icon + name), each opening the same window. Fold state remembered per user. Every
   icon has a tooltip (name + one line).
   **The output windows (owner 14:57): not popovers.** Today `ui_top.draw_make` opens popovers that close on a click
   elsewhere – the owner wants windows he can **drag around the screen (also to his second monitor) and that stay
   open when he clicks elsewhere** (in the 3D view, the side panels, another output window) until he closes them.
   Build them the way the **Set-up window** is built (`ops_setup.py` / `ui_setup.py`, 0062, study 0200 "float 2": a
   second app window with its own panel tab): one small window per output, titled with the output's name, drawing the
   app's own settings and operators (nothing copied – a change there shows in 5 / 6 / 7 and the other way round).
   Opening the same output again brings its window to the front instead of a second one; a window remembers its size
   and place for the next time; it closes with the project. Mind the known window points: 0213 (Set-up window's Back /
   Next refused in the Client view – the output windows must work in the Client view as far as the output itself is
   allowed there), 0221 (a new window is not tidied until the next load – an output window must open tidy, no
   Blender header / editors). A setting that needs a click in the 3D view starts in the main window, as
   `fresing.setup_in_view` does. The 3D view header's "Make" list opens the same windows.
2. **"Test tour" → "Learning hub"** (visible name everywhere, see Area).
3. **The mode switch at the top of the left panel**, in the Learning hub block: a three-part switch
   **View | Show me | Build it yourself** (0230's three modes), one click:
   - in a Learning hub project: switches the open set to that mode at once (View = the finished set with its stops and
     Go, as today; Show me / Build it yourself = 0230's lesson for this set, the way the Learn window starts it). A
     set without a lesson shows Show me / Build it yourself greyed with "Lesson coming" (0230's wording) and a tooltip.
     If switching opens another project, the usual save question comes first.
   - outside a Learning hub project: the block shows one button **Open the Learning hub** and the same switch; a click
     on a mode opens the Learn window with that mode chosen.
   - the current mode is shown pressed; it survives a reopen of the project.
4. **What's next / Next to learn get a fold arrow** in their title row like every other panel: **open for a new user,
   once folded it stays folded** (remembered per user; the × stays and still hides it as today).
5. **Live preview and Build & play on the left, never more than one click away** (owner 14:54). A small row at the
   very top of the left panel, outside every fold: **Live preview** (the same `fresing.preview` toggle as in 5 Scene &
   Render, showing "Live preview: on" when on) and **Build & play** (the same `fresing.anim_build` as in 6 Animation,
   with play). They also stay where they are today. When the left panel is folded away, a narrow strip keeps these two
   as icons (plus the button that unfolds it) – so one click always reaches them. Build & play with no animation:
   greyed, tooltip "Make an animation first in 6 Animation". Client view: each button does what it does there today.

## Lead's decisions (small follow-ups if the owner disagrees)

- **Left panel order:** Live preview + Build & play row (always) · update notice (only after an update, as today) · Workspace switcher · **Learning hub** (switch;
  in a hub project also its stop list = today's Test tour panel, and the Lesson panel while a lesson runs) · Favourites
  · What's next / Next to learn. Each folds on its own.
- **Right panel order:** Make (folded row) · section tabs All 1 … 8 + its hint · Set-up window… · 1 … 8.
- **Client view:** the left panel shows what the Client view shows today of these parts, nothing more.
- **Full access / Show all of Blender:** Blender's tool buttons come back on the left as they do today; the Fresing
  left panel stays below them or can be folded – the user must still reach both.
- The left panel can be folded away in one click (and back) to a narrow strip with Live preview, Build & play and the
  unfold button – a small button in its own title row and the existing
  header button that brings a hidden Fresing panel back (0198) brings both panels back.
- Default width: as narrow as the content reads at 1920 px (lead's guess 220–260 px); the user can drag it.

## Step 1 – prove the left side first (stop and report if it fails)

Blender has one sidebar per 3D view. The likely way: panels with `bl_region_type = "TOOLS"` in the 3D view's toolbar
region (Blender's own `VIEW3D_PT_tools_active` lives there), widened, with Blender's tool buttons hidden outside Full
access. The fallback: a narrow area of its own on the left of the window. Build the smallest version of each that
works, on Windows too, and measure: does it keep its width on file open / tour open / demo open (0198's layout keeper),
on a second monitor and at 2560 px, after Show all of Blender and Back (0241), in the Client view, and does it scroll
when it is taller than the window? Pick one and say why. If neither holds, **stop, push the findings to the task file,
and say so** – the lead then asks the owner.

## What to do (after step 1)

1. Move the parts to the left panel in the order above; the right panel keeps only its four parts.
2. Make: folded row / unfolded list, white "Make", one draggable output window per icon that stays open, tooltips.
3. The Learning hub block with its switch; the rename everywhere a user reads it; "Learning hub" also on the Favourites
   button that says "Test tour" today.
4. What's next / Next to learn: fold arrow, open by default, remembered.
5. `core/functions.py`: `changed=` on every function whose place or name changed (workspace, favourites, What's next,
   Make, tour, Learn); guide anchors still right. The guide: the "side panel" chapter rewritten for two panels, the tour
   chapter's name, new pictures (test models only) at 1920 px. The tour stop that shows the side panel (the hub's
   `start_here` text, if it describes the panel) updated – text only. PC-check line: both panels there, Make window opens
   and stays open, the mode switch reaches View / Show me / Build it yourself on the crane set.
6. Real-app tests that find panels by their order on the Fresing tab (0062's `panels.open_to()` and the 14 older
   ones): updated, not skipped.

## Done when

- [ ] Right panel = Make row, tabs, Set-up window…, 1–8 only; the first step visible without scrolling at 1920 × 1080
- [ ] Left panel holds every other part, survives every open / switch listed in step 1, scrolls, folds in one click
- [ ] Make folded / unfolded as above; each of the six opens its own window that can be dragged (also to a second
      monitor) and stays open on clicks elsewhere; one window per output; all with tooltips
- [ ] "Learning hub" everywhere a user reads it; the mode switch works in and outside a hub project; greyed sets explained
- [ ] What's next / Next to learn fold and stay folded
- [ ] Live preview and Build & play one click away on the left – also with the left panel folded to its strip
- [ ] Two screenshots in the report (1920 and 2560 px, test models only), before / after
- [ ] Full suite green incl. the Windows install; guide, function list, PC check, CHANGELOG; report filled in, merged,
      released

## Background

- Owner 20 Nov 17:10 ("Top of the side panel too full", TASKS.md "Problems found"): "the menu should be changed very
  much … maybe this should be separated into its own menu." This task is that change; the planned study is replaced by
  the owner's own layout.
- 0062 (`ui_top.py`) built Workspace, What's next, tabs and Make; 0181 Favourites; 0059 the tour panel; 0230 the Learn
  window, lessons and the Lesson panel; 0198 keeps the layout on open and has the header button that brings the Fresing
  panel back; 0221 / 0241 hide Blender's editors and give "Show all of Blender".
- Owner's aim: the app as simple as possible for users who do not know Blender, Blender's tools easy to reach for those
  who do. Every button gets a tooltip.

## Design (worker, 21 Nov – step 1 done)

**Step 1 – the left side: Blender's own toolbar region (TOOLS) of the 3D view, widened.** Measured in the real
Blender 5.2.3 under xvfb at 1920 x 1080 (web machine, 4 cores): a panel with `bl_region_type = "TOOLS"` draws below
Blender's tool buttons; Blender's tool buttons go away when `VIEW3D_PT_tools_active`'s own draw is swapped for an
empty one (`quiet.swap`, as 0241 does for the header), so outside Full access the region holds only Fresing's panels
and in Full access the tools come back above them. A script cannot set a region's width (`Region.width` is
read-only), so the app writes the region's stored width (`ARegion.sizex`, a 16-bit number) itself: it is found by
its neighbours (the region's own width and height as two 16-bit numbers, then region type 5 = TOOLS and alignment
3 = LEFT – nothing is written unless all four match) and the toolbar is switched off and on to take it: 58 -> 250 px
at once, 250 -> 31 px for the folded strip. The width is saved with the project like Blender's own; a user's drag
is kept (the app widens only a region narrower than it reads). Overlap off: a solid panel. The region scrolls like
Blender's toolbar. The fallback (an area of its own) is not needed. Not measurable here: a second monitor (the
left panel belongs to the 3D view of each window, nothing depends on the monitor) and Windows (the same struct on
64-bit Windows; the search refuses to write when the pattern is not found, then the panel keeps Blender's width).

**Files and what goes between them**
- `blender/ui_left.py` (new, worker): `LeftPanel` mixin (VIEW_3D / TOOLS, `_fr_left = True`), the width
  (`sizex_address(region)`, `set_width(area, px)`, `ensure(area)` called by `ui_header.put_layout_right`,
  `strip(context)` = region narrower than `STRIP_BELOW`), `FRESING_PT_left_quick` (Live preview + Build & play + the
  fold button; icons only in the strip), `FRESING_PT_hub` (Learning hub: the switch View | Show me | Build it
  yourself, Open the Learning hub), operators `fresing.left_fold`, `fresing.hub_mode`.
- `blender/ops_make.py` (new, worker): output windows – `fresing.make_window(key)`, `fresing.make_close`,
  `fresing.make_fold`; `FRESING_PT_make_window` (side panel tab "Make" of a window whose screen has
  `fr_output = <key>`). The window is made with the Set-up window's machinery (`ops_setup.open_window(..., mark=,
  value=, tab=)`).
- `winplace.py` (new, worker; Windows only, ctypes): find a Blender window's HWND by its place and size, raise it,
  read / set its rectangle – the output window comes to the front and opens where it was. Independent review.
- `panels.py`: left panels get the app's title row and poll like the right ones (`LEFT`); `side_window(win)` = a
  Set-up or output window (no left panel, not tidied).
- Moved to the left (region only, same class names): `updates.FRESING_PT_update`, `ui_top.FRESING_PT_workspace`,
  `ui_usage.FRESING_PT_favourites`, `ui_tour.FRESING_PT_tour`, `ui_lesson.FRESING_PT_lesson`, `ui_top.FRESING_PT_next`.
- Preferences (per user): `left_folded`, `left_width`, `next_folded`, `make_open`.
- The rename "Test tour" -> "Learning hub" in user-visible strings: a subagent (worktree), every file except
  `ui_left.py`, `ops_make.py`, `ui_top.py`, `ui_tour.py`, `ui_usage.py`, `panels.py`, `__init__.py`, `lock.py`,
  `ops_setup.py`, `ui_header.py`, `quiet.py`, `editors.py`, `prefs.py` (the worker's).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 21 Nov 2026.

**What changed:**
- **Right panel** = Make · tabs All 1 … 8 (+ hint) · Set-up window… · 1 … 8. At 1920 × 1080 with the crane imported the
  first step (1 Import) now starts about 244 px from the top of the window instead of about 610 px (screenshots: `tasks/img/0260_before_after_1920.jpg`, `…_2560.jpg`).
- **Left panel** (new, `ui_left.py`) in the 3D view's toolbar region: Live preview + Build & play + fold (always, also
  in the strip) · update notice · Workspace · **Learning hub** (switch, Open the Learning hub, Learn…) · its stops (in a
  sample project) · Lesson (while one runs) · Favourites · What's next. 240 px wide by default (px at UI scale 1),
  the user's drag is kept; folds to a 34 px strip (▶, Live preview, Build & play) and back; Blender's tool buttons only
  in Full access (above the app's parts). Panels moved by region only, class names kept.
- **Make**: one row "Make" + 6 icons (folded, default) or the labelled 2 × 3 list (click "Make"; kept per user). Each
  output opens its **own window** (`ops_make.py`, built with the Set-up window's machinery: `ops_setup.open_window` got
  `mark` / `value` / `done`), tab "Make", the same settings bodies as 5 / 6 / 7; a second press opens no second window;
  × closes it. Windows only (`winplace.py`): the window comes to the front on a second press and reopens where it was
  (places in `<config>/fresing_make_windows.json`). The 3D view header's Make list: the gear opens the same window.
- **Learning hub**: the switch View | Show me | Build it yourself (`fresing.hub_mode`): in a sample project View opens
  the finished sample, Show me / Build it yourself its lesson (save question first), Show me <-> Build switches the
  running lesson at once; greyed with "Lesson coming" without a lesson; outside a sample project it opens the Learn
  window with that way pressed. Stored in the project (the lesson's own mode key): survives a reopen.
- **"Test tour" -> "Learning hub"** in every user-visible text (a subagent, 20 files: menus, welcome, tooltips,
  messages, PC-check titles, function titles, guide, stop texts). Kept on purpose: internal names (`tour.py`,
  `fresing.tour_*`, `FRESING_PT_tour`, `TOUR`), and every name on disk that old projects and results depend on (the
  folder `Documents\Fresing Render\Test tour`, `Test tour <version>.blend` / `results.json` / `results.txt`, the log
  file, the PC check's work folder) and the "TEST TOUR" watermark / decal text inside the sample models.
- **What's next / Next to learn**: a fold arrow (open for a new user, kept folded per user; × as before).
- `anim_build` says "Make an animation first in 6 Animation" when greyed. Function list: new `panel.left`,
  `learn.hub`; `changed=` on 18 entries whose place or name changed. Guide: "How the app is laid out", new sections
  The left panel and The Learning hub switch, Make, What's next, Set-up window, favourites / update notice places;
  pictures `left_panel.png`, `left_hub.png` (new), `panel_top_make.png`, `panel_top_tabs.png`,
  `sidebar_sections.png`. PC-check line `panel.two`. Tour: texts of the stops setup, workspace, make, panel_back,
  usage, learn, lessons, start_here (sets crane and gantry `changed`). CLAUDE.md section 3 + a lesson learned.

**Step 1 (the left side)** – see Design: the toolbar region works; the fallback was not needed.

**Tested and measured** (web machine, 4 cores, no graphics card, Blender 5.2.3 under xvfb; test crane only):
- `tools/ui_test_left.py` (new, group "ui"): 31 / 31 – width 240 px at the start, after Full access and back, in the
  Client view and after opening a project saved with Blender's 40 px toolbar; strip 34 px and back to 240; Blender's
  tools hidden / back / hidden; the left panel scrolls (a 90-line test panel: view moved 246 px on 6 wheel steps);
  Picture window open in 1.7 s, still open after a click in the main window, tab "Make", no left panel in it, no second
  window on a second press, 3D page opens a second window, Close closes both; Learning hub: own project = not a hub
  project, crane sample = View with a lesson, Show me opens the crane lesson (5.3 s), Build it yourself switches it.
  The output window measured 297 × 581 px.
- pytest locally: test_workspaces_independent, places, functions, quiet, editors, learning_blender, usage_blender (144
  passed); the subagent ran functions, user_guide, tour, learning, learning_blender, places (180 passed).
- Before / after screenshots: `tasks/img/0260_before_after_1920.jpg`, `tasks/img/0260_before_after_2560.jpg` (top =
  0.2.194, bottom = this task).
- Not measurable here: a second monitor (nothing in the code depends on the monitor), Windows (the same region search;
  `winplace.py` – front and place – only runs there), the window title (Blender gives a script no way to set it: the
  window shows the output's name at its top).

**Subagents:** a Sonnet subagent did the rename in its own worktree (merged without conflicts). An independent
reviewer read `winplace.py`, the region-width write and `quiet._no_tools`: nothing can crash Blender or harm memory
(it measured `ARegion` = 320 bytes on 5.2.3, `winx` at byte 184, the scan stays inside it; Windows x64 has the same
layout). Its findings in `winplace.py` were fixed after it: several ways Blender may count y on two monitors of
different heights (`bottoms`), the handle kept per output (a minimised window, two windows opened at the same spot),
a place is used only when the title bar lands on a monitor (not a window hanging 7 px on screen), move first and size
after (a monitor with other scaling made it grow), places watched again after a project opens; `tests/test_winplace.py`
for the plain-number parts. Also: outside Object Mode Blender's tool buttons show (as its header does).

**Open points / follow-up tasks:**
- **GitHub runs:** 7 pushes with a full run. Real failures found and fixed: the Set-up window's side panel squeezed to
  27 px by the left panel in the copied piece (now split with the left panel off for a moment); the old side-panel
  test's Make check (wrapping a plain panel's draw crashed Blender – the test checks Make's poll and place now); the
  usage test's clicks (the lesson highlight now also finds buttons on the left panel); a stop title over 32
  characters; the What's new test before the version was raised. Twice the version was taken meanwhile (0249: 0.2.195,
  0234: 0.2.196): merged and renumbered to 0.2.197. One run's PC check ran out of its 15 min on a slow runner (all its
  jobs were 1.5–2 x slower; the next runs were green).
- Release: https://github.com/smholte/CAD-render-animation/releases/tag/v0.2.197
- Not done (say so to the owner): the output window's title bar cannot be set from a script (it shows Blender's
  title; the output's name is at the top of its panel). "Make" is white because its title is a plain button now
  (the side-panel look of study 0244 comes after and must cover both panels).
- Kept internal names: `tour.py`, `fresing.tour_*`, `FRESING_PT_tour`, and the files on disk ("Test tour" folder and
  result files, the PC check's work folder) so old tours and results still open.
- Owner on his PC: drag an output window to the second monitor, close it with its own ×, press the icon again – it
  should come back there and to the front; fold / unfold the left panel; Full access shows Blender's tools on the left.
