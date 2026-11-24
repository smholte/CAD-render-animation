# 0308 – Make: a taller row with larger icons, an outputs strip in every output window, and "Render this view"

**Who:** worker · **Status:** running · **Branch:** `task/0308-make-strip-render-view`
**Started by:** lead, 23 Nov 2026 (owner 20:49, with three screenshots: the Make row, the Picture window with its empty
left side marked in purple – one icon per output, names beside them in orange when the strip is dragged wider) ·
**Model:** Opus · effort Medium
**Area:** `blender/ui_top.py` (the Make row `draw_make` / `FRESING_PT_make`), `blender/ops_make.py` (the output
windows), the output window's left region (made by `ops_setup.open_window(mark="fr_output")` – 0282 changes that
helper, so this task starts after 0282 is merged), a new operator for "Render this view" (next to `FRESING_OT_render`
in `ops_main.py`, or its own small file), `core/functions.py`, `tour.py` (one stop), `pccheck/checks.py` (one line),
the guide (Make section), tooltips.
**Not:** the outputs' own settings panels (their bodies stay as they are); Live preview; 0294's workspaces (may run
beside 0294: no shared file – whoever merges second updates its branch).

## Goal

1. **The Make row a little taller, with slightly larger icons** – easier to hit, still one row in the right panel at
   its default width.
2. **Every output window gets a strip on its left with all Make outputs**, so the user switches between Picture,
   Product video, Turntable, 3D page, Animation and Queue in one click without going back to the side panel. Narrow
   (the default): icons only. **When the user drags the strip wider, the names show beside the icons** (the way
   Blender's own toolbar shows its tool names).
3. **"Render this view"** – a button under the Make row: renders exactly what the 3D view shows now (its angle and
   zoom), without having to add or pick a camera.

## Background

- Today (0260): the Make row is `draw_make(..., labelled=False)` with `scale_y = 1.2`; each icon opens the output's own
  window (`fresing.make_window`, `ops_make.py`), drawn in a 3D-view copy's **UI region** (right). The window's left
  part is empty grey, and Blender's own sidebar tabs (Item, Tool, View, Animation) show beside "Make" (owner's
  screenshot). 0271 found that a UI region always draws a tab strip; the toolbar region (TOOLS, left) draws none and
  can be widened (`ui_left.sizex_address`, `fit_width`; CLAUDE.md section 8).
- The list of outputs and their icons: `ui_top.OUTPUTS` (filtered by the workspace with `_outputs(scene)`) – the strip
  must show the same list, in the same order, with the same icons.

## What to do

1. **Make row:** taller (about 1.3–1.5 × today) with icons that look larger. Blender draws icons at a fixed size in a
   normal button – find what really makes them larger (button scale, `template_icon`, the app's own icon images in
   `brand/`…) and pick the cleanest. Show the owner two sizes side by side in the report's pictures if the choice is
   not obvious. The same look in the 3D view header's Make list is not needed.
2. **Outputs strip in the output windows:** in the window's **left (toolbar) region**: one button per output (the
   window's own output shown pressed), a click switches **this window** to that output (title, body, remembered place
   per window as `ops_make` keeps it today – one window, not a new one per click). Narrow = icons only; when the user
   drags the strip wider than about the width of the longest name, icon + name. Blender's tool buttons never show
   there (`quiet._no_tools` does this for the main view). While at it: hide Blender's own sidebar tabs (Item, Tool,
   View, Animation) in output windows, as far as Blender allows (0271: at least one tab may stay).
3. **Render this view:** a button under the Make row (right panel; also in the 3D view header's Make list) –
   `fresing.render_view`: renders with Cycles what the main 3D view shows – its viewpoint, its lens / orthographic
   view; in camera view, that camera – at the **Picture's** format, size, quality, file type and folder, saved like
   Render image (name `<project>_View_<date-time>.png`), the result shown as Render image shows it. It **must not**
   change the active camera, the saved cameras or anything the animation uses (a camera made for the render is
   removed afterwards, also on Cancel or an error). The picture's frame: same centre and zoom as the view, the
   Picture's format fitted so nothing the view shows of the model is cut off – say in the report which rule you chose
   and show it on the test crane. Works with Live preview on or off; refused with a plain line while a queue render
   or a long job runs (as Render image).
4. Tooltips, guide (Make section: the bigger row, the strip with a picture of a wide and a narrow strip, Render this
   view), function entry `scene.render_view` (`since=`), a tour stop (Make set or the crane), a Full PC-check line
   `scene.render_view` (a small picture from a set view of the test crane, compared with Render image from a camera
   placed at the same view – they must match), `MIN_LINES_FULL`, `MIN_CHECKS`.

## Done when

- [ ] Make row taller with larger icons, still one row at the default panel width (screenshot)
- [ ] Output windows: the strip on the left switches the window between outputs; icons narrow, names when wider;
      Blender's tool buttons never there; Blender's sidebar tabs hidden as far as possible (screenshots of both widths)
- [ ] Render this view: same picture as Render image from a camera at the same place (test), no camera or scene
      setting left changed (test), error and cancel leave nothing behind (test)
- [ ] Tests added/updated; full suite passes
- [ ] (UI) screenshots checked with tools/ui_screens.py
- [ ] (tour or functions changed) version fields: `since=` on new entries / stops, `changed=` raised on a changed tour
      set (`python3 tools/tour_versions.py --record`; the precheck says what to write)
- [ ] Owner's test steps (numbered, click by click) in the report; merged, version, release

## Not in this task

The outputs' settings panels themselves, Live preview, the workspaces (0294), the function dialogs' windows (0282 –
start after it is merged and use its helper).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
