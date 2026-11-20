# 0244 – Prototype (findings only): steps and their functions look different in the side panel

**Who:** worker · **Status:** done (20 Nov) (findings only: no merge of app code, does not count as a code task) ·
**Branch:** the session's own; prototype code pushed with `[skip ci]`, never merged; report + pictures to `main` as
`tasks/` files only
**Started by:** lead chat, 20 Nov 2026 21:55 (owner 21:02, with a screenshot: "need to easily see where a step ends and a
new one starts, now all functions look alike and the 1–8 tabs"; look picked by the owner 21:02–21:51 from six rounds of
mock-ups) · **Lane:** Start & learn (prototype; the full change is a later task) · **Model:** Opus · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Show the owner, in the real app, his chosen side-panel look for **step 4 Motion and step 5 Scene & Render**: a step and
the functions inside it (Cylinders, Mechanisms … Tracks and belts; Sea, Hall …) must look different, and an **open**
function must stand apart from the step's own buttons. Find out what Blender allows, what it costs per redraw, and write
the plan for the full change of all steps.

## The look the owner chose (version "C2 + green arrows everywhere")

Today every function is a Blender sub-panel (`bl_parent_id = "FRESING_PT_motion"` etc.) and Blender draws it with almost
the same box as the step, so the side panel reads as one long list. The owner wants:

| Part | Look |
| --- | --- |
| **Step title row** (1–8) | grey bar, a little **lighter** than today's panel header; a **3 px Fresing Green edge on the left** (`#479B29`, `highlight.GREEN`); white text; its own icon as now; state on the right as now |
| **Closed function row** | **darker** than the step, **indented** (~10 px); a **green › fold arrow**; its normal icon in white; **white text**; state on the right in grey as now ("1 cylinder", "none") |
| **Open function** | its content in a **grey frame** (1 px, about `#555`) with a **3 px Fresing Green line on the left**; a **green ⌄ arrow**; title and icon **white**; body as dark as a closed row |
| **A fold inside a function** (e.g. Cylinders' *Set-up*) | green › / ⌄ arrow, **no frame**; its body indented with a thin dashed grey line on its left |
| Text | **white everywhere** – the owner tried green titles and turned them down |

The owner turned down: green titles, a green-tinted step bar ("a bit too much green"), lighter greys for the whole
window, number badges, a "More in step 4" divider line. Keep the dark greys. Mock-up colours used (a guide, not a
rule – match the real Blender theme): window `#1d1d1d`, step bar `#3d3d3d`, function row / open body `#262626`, frame
`#555`, buttons `#545454`, green arrows a lighter green (`#8cc46f`) for contrast on dark grey – try both that and `#479B29`.

## What to find out and build (on your branch only)

1. **Functions drawn inside the step.** Draw the functions of steps 4 and 5 as folds inside the step's own body
   instead of separate sub-panels – reuse each sub-panel's own `draw()` with the fold's body as its layout (a stand-in
   `self`, as `highlight.py`'s `_L` does), so no function's code is copied. Try both: (a) Blender's `layout.panel()`
   folds and (b) the app's own fold rows (a BoolProperty + an emboss-free toggle with a custom icon, like `ui.fold`).
   Report which can carry a **green arrow** (Blender draws its own arrow for `layout.panel()` – can it be hidden or
   replaced?), which keeps open / closed per project, and which allows **one function open at a time**.
2. **Greys from Blender's colour settings** – which theme fields (`panelcolors.header` / `back` / `sub_back`,
   `wcol_box`, …) give the lighter step bar and the darker function rows; set them only in the app's own Blender
   config. What else in the window changes with them (3D view header, menus, Blender's own panels in **Show all of
   Blender** / Full access)? A screenshot of each.
3. **Green arrows and icons** – custom icons (`bpy.utils.previews`), sharp at 100 % and 200 % UI scale.
4. **The frame and the green left line** – the frame with `layout.box()`; the green line and the step's green edge:
   Blender cannot colour a single row, so try (a) the lesson highlight's way (`highlight.py`: a marker icon of one
   exact colour, a draw handler of the side panel finds it in the region's pixels and paints over it) and (b) anything
   cheaper you find. **Measure** the side panel's redraw time with and without it: 0, 1 and 3 open functions, 1920 and
   2560 px, scrolling and while a joint is dragged. The highlight today runs only while a lesson points – this would run
   whenever a function is open, so the cost decides. Show the **fallback** without overlay too (box + green arrows only).
5. **One function open at a time** – both ways (on / off), as a prototype preference; which feels better with the
   long step 4 list.
6. **What the full change touches** – list every place that finds a function by its panel id or Blender's panel
   state, with a plan for each: `panels.py` (`open_to()`, `PARENT`), `highlight.py` / the lessons (0230), favourites,
   declutter and hides (`usage.py`, 0181 / 0208 / 0236), `core/functions.py` anchors, the section tabs and
   "Keep sections as I left them", the PC-check lines, the test-tour stops, real-app tests, the guide's pictures. And
   which tasks it must not run beside (all side-panel lanes), the order with 0241 → 0222 packages B and C and the
   "top of the side panel too full" study (TASKS.md "Problems found"), and its size (one task, or one per step).

## Deliver

- Pictures in `tasks/img/0244/` (to `main` as `tasks/` files): the **whole window** and a panel close-up at **1920 and
  2560 px** – today's look; the new look with step 4 open, Cylinders open with Set-up open, the rest closed, step 5
  closed and open; the fallback without the green line; Show all of Blender with the new greys. Use public test models
  only (the test crane of the tour) – never the demo vessel's equipment, never the Fresing 400.
- A short page `tasks/0244_page/index.html` (like 0200's) with the pictures side by side for the owner to pick; the lead
  publishes it.
- The report: the answers to 1–6, the timings, the owner's choices left (arrow green shade, one-open-at-a-time default,
  overlay or fallback), and the brief-ready plan for the full task.

## Done when

- [x] Prototype code on the branch, pushed with `[skip ci]` on every push, **never merged**; no version change
- [x] Pictures + page + report on `main` as `tasks/` files only (a `tasks/`-only push starts no run)
- [x] Timings measured on the 4-core web machine with the real Blender (name it), at both widths
- [x] Report filled in below

## Not in this task

Merging app code; changing any step other than 4 and 5; the top of the side panel (workspace row, favourites,
coaching) – that is the later study; Blender's side-panel tabs (0222 package C).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 20 Nov 2026. Prototype on branch `claude/peaceful-cray-57hntp` (commits with
`[skip ci]`, never merged, no version change). Pictures `tasks/img/0244/` (54 JPEGs + `times_*.json`), page
`tasks/0244_page/index.html` (its own `img/`, ready for the lead to publish).

**What changed (branch only):** `blender/look244.py` (the look, its switches, the overlay, one-open-at-a-time, the two
"inside the step" variants), a few hooked lines in `panels.py` (`_make_draw`, `_make_poll`, the toggle operator),
`ui.py` (`fold`) and `__init__.py`; `tools/proto_0244_shots.py` (pictures + timings). The look is switched at run time
(`look244.set(look="old"|"new"|"fallback", how=, arrow=, one_open=, overlay=)`), so today's and the new look come from
the same app.

**Answers**

1. **Functions drawn inside the step?** Not needed. Since 0062 every Fresing panel already draws its own title row
   (`panels.draw_title`), so the new look is drawn **in that one place** and the functions stay Blender sub-panels:
   panel ids, `PARENT`, `OPEN`, `open_to`, `show_only`, `places.py`, the function list, usage counting, lessons, tour,
   PC check and tests keep working unchanged. Tried both "inside" ways to compare (pictures `fold_cyl`, `lpanel_cyl`):
   (b) the app's own fold rows inside the step body (reusing each sub-panel's `draw` with a stand-in `self`) **looks
   the same** as the sub-panel way – green arrow, frame, one-open all work – but every function would get a new
   address for no gain; (a) Blender's `layout.panel()` draws **its own small white arrow** (cannot be hidden or made
   green), no frame round the open body, Blender keeps its open state per region in the file (only `panel_prop` with
   our own property could set it) and nothing gives one-open-at-a-time. → keep sub-panels, change `draw_title`.
   Open / closed per project: as today (`panels.OPEN`, "Keep sections as I left them").
2. **Greys from Blender's colour settings: they do not work for the Fresing tab.** In 5.2.3 the panel colours are
   global (`user_interface.panel_back / panel_header / panel_sub_back`, no longer per editor), and the app's panels
   (all `HIDE_HEADER` since 0062) **draw no panel background at all** – measured: set loud red / green / blue, the
   Fresing tab did not change by one pixel, only Blender's own Properties panels did (picture `blender_probe_*`). The
   only fills a layout can have are boxes (`wcol_box`, ONE colour for every box) and buttons. So: a lighter step bar
   AND darker function rows AND a dark open body cannot all come from the theme. The prototype changes ONE theme
   field: every box's **outline** #3d3d3d → #575757 (the open function's frame; #555 itself is too close to the
   buttons' #545454 for the overlay to tell apart). That also shows on every other box of the app and on Blender's own
   boxes in Show all of Blender (pictures `blender_new_*` vs `blender_old_*`). The 3D view header and menus do not change.
3. **Green arrows:** custom icons (`bpy.utils.previews`, 32 px PNGs drawn in code, smoothed edges) – sharp at 100 %
   and 200 % (pictures `*_2560s2_*`). Both shades shown (`new_cyl` #8cc46f, `new_cyl_brand` #479B29).
4. **Frame and green line:** the frame is a `layout.box()` round title + body (Blender's box fill already gives the
   dark body). The green lines, the lighter step bar and the darker indented closed rows are drawn **over** the side
   panel after Blender drew it (a POST_PIXEL draw handler): the arrow icons carry a marker bar of one exact colour,
   the handler finds it in the pixels, paints it over and draws: step bar +13 grey (additive, so the white text stays
   white) with a 3 px green edge; closed function row −10 grey from its indent; open function a 3 px green line down
   the frame's left edge (found by walking the frame's outline colour); an open fold inside it a dashed grey line.
   Way (b), cheaper: read only an **80 px strip** on the panel's left instead of the whole panel (everything it looks
   for sits there). Fallback without overlay (pictures `fallback_*`): step bar in a box as today, functions indented,
   open function framed, green arrows – no lighter bar, no green line.
5. **One open at a time:** works (opening one folds the others of that step; Ctrl+click as today). With 11 functions in
   step 4, three open (picture `new_three`) is a long scroll – recommend **on** by default, a preference to turn it off.
6. **The full change** – see the plan below.

**Tested and measured** (4-core web machine, real Blender 5.2.3 Linux under xvfb – software drawing, no graphics card;
test crane `tests/data/test_crane_a.step` with the tour's boom joint + luffing cylinder; UI scale 100 %; side panel
292 px wide, 898 px high at 1920 × 1080 and 1,231 px at 2560 × 1440; median of 2 rounds of 30 redraws of the side
panel with `wm.redraw_timer`; the overlay's own time from its handler in redraws with swap, where it found its 6–11
markers):

| Look | Open functions | 1920: panel redraw ms | 1920: of it the overlay ms | 2560: panel redraw ms | 2560: of it the overlay ms |
| --- | --- | --- | --- | --- | --- |
| Today | 0 | 1.1 | – | 0.9 | – |
| Today | 1 | 1.1 | – | 1.1 | – |
| Today | 3 | 1.1 | – | 1.0 | – |
| New look without the green line (fallback) | 0 | 0.9 | – | 1.0 | – |
| New look without the green line (fallback) | 1 | 1.0 | – | 1.1 | – |
| New look without the green line (fallback) | 3 | 0.8 | – | 1.1 | – |
| New look, green line – reads a 80 px strip | 0 | 1.7 | 1.1 | 2.0 | 1.3 |
| New look, green line – reads a 80 px strip | 1 | 1.8 | 1.3 | 2.0 | 1.6 |
| New look, green line – reads a 80 px strip | 3 | 1.9 | 1.3 | 2.2 | 1.8 |
| New look, green line – reads the whole panel | 0 | 3.1 | 2.5 | 3.7 | 2.9 |
| New look, green line – reads the whole panel | 1 | 3.0 | 3.4 | 3.7 | 3.8 |
| New look, green line – reads the whole panel | 3 | 3.1 | 2.7 | 4.7 | 4.0 |

Scrolling and dragging a joint: the overlay cost the same per redraw (strip 1.4 / 1.4 ms at 1920, 1.8 / 1.9 ms at
2560; whole panel 2.8 / 2.5 and 4.3 / 5.7 ms). The fallback costs nothing measurable (0.8–1.1 ms = today). Expect the
owner's PC to draw faster; the side panel only redraws when something in it changes (hover, scroll, a value).
Found on the way: `wm.redraw_timer(type="DRAW")` draws the side panel but a POST_PIXEL handler then reads a buffer
without the panel in it (0 markers found); `DRAW_SWAP` reads the real one. No pytest run: nothing of the branch is
meant for `main` (GitHub run: none, `[skip ci]` on every push).

**Owner's choices left** (on the page): arrow green (★ light #8cc46f); one open at a time (★ on by default); green line
with the overlay (★, ~1–2 ms per side-panel redraw) or the fallback.

**Plan for the full change (brief-ready):**
- **One task, Opus · Medium, Start & learn lane**, after 0241 and before 0222 B/C and the "top of the side panel too
  full" study (that study then works on the new look); it must not run beside any task in `ui*.py`, `panels.py`,
  `highlight.py`, the lessons (0230) or the guide pictures. All eight steps at once (the look is drawn in one place, a
  task per step would only repeat the tests and pictures); ~1 day of work, most of it pictures and tests.
- **`panels.py`:** `draw_title` gets the new rows (step bar, function row with indent, green arrow icons with markers),
  `_make_draw` frames an open function in a box; keep calling `ui.HOOKS["header"]` (the prototype drops it). Level 2
  sub-panels (CNC machine > Rotary axes …, Milling > Chips) look like folds inside a function: green arrow, no frame.
  `open_to`, `show_only`, `PARENT`, `OPEN`, `only`, `fold_sections`, "Keep sections as I left them", the section tabs:
  **no change**. One-open-at-a-time in `FRESING_OT_panel_toggle` + a preference in `prefs.py` (default from the owner).
- **`ui.fold`:** the app's own fold row (green arrow, body indented) instead of `layout.panel()`, open state in the app
  (like `panels.OPEN`, saved with "Keep sections"); `highlight.fold_open` / `HOOKS["fold"]` asked as today; every
  `fold(...)` id keeps working. "How it works" folds become such rows too.
- **New `blender/side_look.py`** (from `look244.py`): icons, the overlay (strip read, one draw handler, runs while the
  side panel shows the Fresing tab; off in background runs), the one theme field. **The theme field goes into the
  app's own config only**: set at start by the app template (`app_template/…/__init__.py` load_post, like the add-on
  switch) and put back for plain Blender – never in the user's own Blender. If the owner picks the fallback, no
  overlay module, only the box outline.
- **`highlight.py` / lessons (0230):** the marker colours differ (`MARKS` vs the look's), but both read the pixels:
  let the highlight's `_draw_side` and the look's overlay share ONE read per redraw (the highlight already reads the
  whole panel while a lesson points). Section look "4" (a bar on the header's left edge) sits where the green edge is:
  draw it on the right, or use look "5" only. Test `test_highlight.py` with the new rows.
- **Favourites, declutter, hides (`usage.py`, 0181 / 0208 / 0236):** `context.fr_panel` and `panel_opened` stay; a hidden
  function's row simply is not drawn (as today) – no change, only their real-app tests' pixel spots.
- **`core/functions.py` anchors, `places.py`, the PC-check lines, the tour stops:** no change (same panels, titles,
  places). The tour's shots and the PC check's pictures change look (re-record `tools/tour_versions.py` only if a stop's
  check reads pixels).
- **Real-app tests:** the step bar is no box any more (rows ~2 px lower) and function rows start ~10 px further right –
  tests that click fixed spots in the side panel (0197 counted 19 files) re-measure; tests that find a row by text are
  unaffected. Add: a test that the overlay finds its markers and paints them over (no marker colour left in the
  panel), one-open-at-a-time, the theme field set and put back, a fold's open state kept.
- **Guide pictures:** every side-panel picture in `docs/img/` (132 files, most show a panel) – retake with
  `tools/guide_screens.py`; the guide's text about "the fold arrow" stays true.
- **Not in it:** the top of the side panel (the later study), Blender's side-panel tabs (0222 C).

**For CLAUDE.md section 8 (lead):** (1) Blender 5.2.3: panel colours are global (`user_interface.panel_*`), and
`HIDE_HEADER` panels – all of the Fresing tab – draw no panel background: only boxes and buttons have a fill.
(2) `wm.redraw_timer(type="DRAW")` gives a POST_PIXEL handler of a side panel a buffer without the panel; time with it,
but check pixel-reading code with `DRAW_SWAP`. (3) A label's icon is drawn dimmed (a marker icon of one exact colour
came out 61,111,42 instead of 71,155,40); an emboss-free operator button's icon comes out within 1 of its colour.

**Open points / follow-up tasks:** the full change above (after the owner's three choices). The dashed line of an open
fold runs to the bottom of its function's frame (prototype: right when the fold is the last thing in the function –
the full change marks the fold's end). Leftover branch for the owner to delete: `claude/peaceful-cray-57hntp`.
Subagents: none (a prototype of one module). Runs on GitHub: none (`[skip ci]`).
