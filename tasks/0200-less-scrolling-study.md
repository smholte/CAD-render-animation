# 0200 – Study + prototype (findings only): less scrolling – a floating set-up window, and all ways to render side by side

**Who:** worker · **Status:** done 17 Nov 2026 (findings only: no merge of app code, does not count as a code task) ·
**Branch:** the session's own; prototype code pushed with `[skip ci]`, never merged; report + page to `main` as
`tasks/` files only
**Started by:** lead chat, 17 Nov 2026 22:30 (owner's wishes) · **Lane:** Start & learn (study; feeds 0062)
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner (17 Nov, his words): *"All the different ways of rendering – 3D page, turntable, current view and others –
to be close to each other. I want less scrolling in the menu. Possibly a sub-menu or a popup menu that hovers over the
rest, that I can drag around, for the set-up of a CNC mill for example or different mechanisms."*

0062 (the side-panel overhaul, Fable · High, runs alone and without stopping) will build what he picks. This study
finds what Blender 5.2.3 really allows, tries it in the real app, and gives him a page with pictures to pick from –
like study 0197 did (its page: `tasks/0197_page/`; use the same style, ticks and a Copy line).

## Background

- 0197's survey (report in `tasks/0197-panel-survey-for-0062.md`): ~36 sub-panels and 13 folds under 7 sections; the
  side panel all open is ~11,000 px tall at UI scale 1.5; in the real app sub-panels start closed. Ways to make an
  output are spread over **5 Scene & Render** (Image size & render, Turntable video, Web 3D model), **6 Animation**
  (Build, Make a product video, Finishing) and **7 Render queue** (still, video, every paint scheme, Start later).
- Blender's own tools for "a panel somewhere else": popover panels (`layout.popover`, `wm.call_panel` with
  `keep_open`), operator dialogs (`invoke_props_dialog`, `invoke_popup`), a second app window (`wm.window_new`, an
  area turned into a sidebar / Properties editor showing one panel category), splitting the 3D view, pie menus. Which
  of them can be **dragged**, **stay open** while the user clicks parts in the 3D view, and work on Windows is what
  this study measures – no guesses.

## What to deliver

1. **All ways to make an output, together.** An inventory (every button that renders or exports: Render image of the
   current view, Turntable, product video, animation, Web 3D model "3D page", queue still / video, every paint scheme,
   time test …: where it sits, which settings it needs). Then **2–3 layouts** where they sit side by side – e.g. one
   "Make" section with a row of big buttons, each opening its own settings; a "Render" popover in the 3D view header;
   a top-bar menu – each as a picture of the real app (prototype or mock drawn from real screenshots), with what moves
   where and what it costs 0062 (section numbers are written ~230 times in texts: say how a layout avoids renumbering).
2. **The floating set-up window.** For each Blender way above: can it be dragged; does it stay open while the user
   clicks in the 3D view (picking an axis, a part); does it survive a redraw, an undo, a file save; can it sit on a
   second monitor; does it scroll; cost per redraw. Measured in the real app under xvfb (what xvfb cannot show –
   OS window dragging on Windows – say so, and give the owner 3–4 click steps to check it on his PC).
   Then a **prototype on the branch** of the best one or two, with the owner's examples: **"Set up a CNC mill"**
   (the steps of 4 Motion > CNC machine in order: axes, spindle, tool, work zero, then the G-code step) and **"Set up
   a mechanism"** (4 Motion > Mechanisms): one step at a time, Back / Next, the step's buttons only, the 3D view usable
   behind it. Pictures (a short GIF or a strip of stills) on the page.
3. **Less scrolling in the side panel in general:** measured heights (UI scale 1.0 and 1.5) of the sections as they
   start and fully open; 3–4 options – one section open at a time (opening one folds the others), a row of section
   tabs at the top, sub-panels as popovers, rarely used settings in "More" – each with a before / after picture and
   what it breaks (real-app tests and guide pictures that click fixed spots, 0197 lists them).
4. **One page** `tasks/0200_page/index.html` (pictures in `img/`, no external links): the options of 1–3 with ticks,
   a recommended choice marked ★ with one line why, and a Copy line the owner pastes back to the lead (e.g. `0200
   pick: render B, float 2, scroll 1+4`). The lead publishes it.
5. **Report** in this file: the measurements, what was tried, the recommendation, and what 0062 must build for each
   option (files, rough size).

## Done when

- [x] Each Blender way measured on the four questions (drag, stays open while clicking the 3D view, survives
      redraw / undo / save, second monitor) – in the report as a table.
- [x] Prototype of the floating set-up window with the CNC mill and Mechanisms steps, on the branch, pictures on the
      page; Windows check steps for the owner.
- [x] 2–3 "all outputs together" layouts and 3–4 less-scrolling options, each with pictures and cost for 0062.
- [x] Page with ticks + Copy line; report filled in; `TASKS.md` row to done (pushed with `[docs]`).

## Not in this task

Building any of it in the app (0062 does). The top-bar Fresing menu, welcome and What's new (0199). Changing
`ui*.py` on `main`. Nothing of the owner's files in pictures – test models only.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort Medium), 17 Nov 2026. Branch `claude/busy-newton-24qrjk`.

**What changed:** on `main` only `tasks/` files: this report, the page `tasks/0200_page/` (`index.html` + 24 pictures in
`img/`, 1.7 MB, no external links) and the `TASKS.md` row. The prototype is **only on the branch** (`[skip ci]`, never
merged): `tasks/0200_proto/` – `setup_window.py` (the step-by-step set-up, four hosts: popover, sidebar tab "Set-up",
second window, dialog / popup), `layouts.py` (Make panel A, header popover B, top-bar menu C, section tabs T),
`probe.py` (the measurements below), `pictures.py`, `panels.py` + `heights.py` (heights, layout pictures). They run in
the installed real app: `blender --app-template fresing_render --enable-event-simulate --python tasks/0200_proto/<x>.py`
(docstrings). No app code, no version, no test run. **The lead publishes `tasks/0200_page/index.html`** (needs `img/`).

**Tested and measured** (real Blender 5.2.3 with the installed extension, xvfb 1920×1200, web machine 4 cores, no
graphics card; test models `test_gantry.step`, `test_linkage_a.step`, `test_crane_a.step`; simulated mouse and keys):

| Way | Drag | Click a part in the 3D view | Frame change / Ctrl+Z / Ctrl+S | Second monitor | Draw |
|---|---|---|---|---|---|
| Popover `wm.call_panel` (keep_open and not) | yes, by its top edge | closes; the click is used up (nothing selected) | stays / stays, keys do nothing / stays, **not saved** (also with the mouse over the view) | no | 0.5–1.0 ms |
| Dialog `invoke_props_dialog` | yes | closes, click used up | stays / nothing / not saved | no | 0.35 ms |
| Popup `invoke_popup` | yes | closes, click used up | stays / nothing / not saved | no | 0.6 ms |
| Pie menu | no | click used up | Ctrl+S not saved | no | – |
| Sidebar tab "Set-up" | docked | stays, part selected | normal | no | 0.3 ms |
| Left toolbar (TOOLS) | – | – | – | – | refused with a category ("Registering panel class … has category"); 58 px wide without |
| Split 3D view + tab | docked | stays | normal | no | a 2nd 3D view |
| **Second window** (`screen.area_dupli` of a split-off area) | OS title bar (not under xvfb: owner's check) | **stays; the click selects the part in the main window** | stays / stays / **saved**; saved with the file and **reopened with its tab** | an OS window (owner's check) | small window 9.5 ms (panel 0.3 ms); main window 108 ms |

Other facts measured: `Region.active_panel_category` can be set only after the region has drawn its tabs (set at once
on a new window: "read-only"); `area_dupli` gives the window the area's size, and a freshly split area has its size only
after the next redraw (copied at once: a 200×150 window) – the prototype splits, waits 0.1 s, copies, closes the split
again (the main layout comes back exactly: Properties 339, Outliner 339, Dope sheet 1574, 3D view 1574 px wide).
Existing side-panel sub-panels open as popovers unchanged (Turntable, Image size & render, Web 3D model), but need
`bl_ui_units_x` set **before** registration (else ~10 units), and `ui.wrap()` measures the side panel, so hints are cut
with "…" in a popover. A `poll` added to a registered panel class is ignored (Blender records at registration whether
a panel has one; 1 Import has none): section tabs need the poll in the class. `bpy.types.Panel` has no open/closed
property: an add-on cannot fold its panels; Blender's own **Ctrl+click** on a section title folds all others (measured:
on "1 Import" all seven folded; on "4 Motion" only Motion opened).

Heights (px of side panel content; fresh crane project; panel 1,009 px tall at scale 1.0, 962 at 1.5; sections add up
to the whole within 12 px):

| Section | start 1.0 | start 1.5 | all open 1.0 | all open 1.5 |
|---|---|---|---|---|
| 1 Import | 380 | 544 | 461 | 660 |
| 2 Structure | 568 | 812 | 913 | 1,309 |
| 3 Looks | 1,076 | 1,541 | 3,432 | 4,910 |
| 4 Motion | 914 | 1,310 | 7,121 | 10,181 |
| 5 Scene & Render | 1,487 | 2,125 | 4,172 | 5,970 |
| 6 Animation | 28 (folded) | 40 | 1,372 | 1,964 |
| 7 Render queue | 28 (folded) | 40 | 346 | 496 |
| **whole** | **4,479 (4.4 screens)** | **6,406 (6.7)** | **17,811 (17.7)** | **25,478 (26.5)** |

(0197's "~11,000 px at 1.5" was cut at its tool's window height; this one scrolls the region to its end and reads the
view position.)

**Recommendation** (on the page, ★): **render A + B** – a "Make" panel above 1 Import with six big buttons (Picture,
Product video, Turntable, 3D page, Animation, Queue), each opening the app's own settings panel as a popover, and the same
list as a "Make" popover in the 3D view header; no section is renumbered (~510 section references in `fresing_render/`
+ `tools/`, ~150 in the guide stay). **float 2** – a second window "Set-up window": the only way that floats and lets
the user click parts. **scroll 1 + 2 + 4** – teach Ctrl+click, section tabs All·1…7, "More" folds / how-to boxes folded.
Copy line default: `0200 pick: render A+B · float 2 · scroll 1+2+4`.

**What 0062 must build per option** (rough sizes):
- *render A*: new `ui_make.py` (~150 lines: the OUTPUTS table, the Make panel, two small popover panels for the
  animation video and the product video); `bl_ui_units_x` on `FRESING_PT_output`, `_turntable`, `_web3d`, `_queue`;
  `ui.wrap()` / `steps()` take the popover's width (`self.is_popover`, `bl_ui_units_x`); `functions.py` entries keep
  their panels (Make is a second door). Real-app tests: the panel shifts the side panel by ~310 px at 1.5 → start it
  folded or adjust click spots. *B*: +30 lines (`VIEW3D_HT_header.append`). *C*: +25 lines (a menu; or inside 0199's menu).
- *float 2*: new `ui_setup.py` + `ops_setup.py` (~350 lines: a steps table per set-up – CNC mill, mechanism, later
  cylinders, cables –, the "Set-up" tab panel, the window operator: split → timer → `area_dupli` → close, set the tab
  after the first draw); the step number in scene properties (`props.py`, the prototype kept it on the window manager,
  which is not saved); a real-app test `ui_test_setup.py`; a tour stop + PC-check line + `functions.py` entry. The
  owner's Windows check decides whether the window stays in front of the main window.
- *scroll 2*: a property for the chosen section, a `poll` in each of the 7 section classes (Import has none today), a
  tab row panel registered before them; the row moves the panel ~50 px (tests, guide pictures). *1*: a hint line +
  guide text. *4*: per panel, as 0197 items 2 and 12.

**Subagents:** none (a study; one real Blender at a time). **Runs:** none (prototype pushed with `[skip ci]`, the rest is
`tasks/` only).

**Open points / follow-up tasks:**
- Owner's check on Windows (4 steps on the page): dragging the second window onto the second monitor, whether it stays
  in front of the main window, whether it comes back there after reopening.
- **App bug found:** 4 Motion > Mechanisms shows "Links: 7 subassemblys selected" – `core/words.plural("subassembly")`
  adds "s" after a consonant + y. Small fix (and a test) for the next task of the Motion lane or 0062.
- `ui.wrap()` cuts text in popovers (see above) – part of render A.
- Not measured: scrolling inside a popover; dragging an OS window (xvfb has no window manager); a real graphics card.
