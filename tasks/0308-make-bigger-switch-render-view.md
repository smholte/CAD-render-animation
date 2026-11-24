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

**Chat / date:** Claude Code on the web, 24 Nov 2026.

**What changed:**
- **Make row** (`ui_top.draw_make`): 1.6 high (was 1.2) with **large icons**. Measured in Blender 5.2.3: no setting makes
  an ordinary icon larger in a button (`scale_y` / `scale_x`, picture icons from `bpy.utils.previews`, expanded enum rows
  – all 16 px; `template_icon(scale=)` and `template_icon_view` draw larger but are a label and a drop-down). Only a
  **geometry icon** (triangles, as Blender's own toolbar uses) is drawn larger – 2x, but started where a 16 px icon starts,
  so it stuck out to the right; with `text=" "` it sits at the button's left edge and shows whole. So the six icons are
  drawn as triangles (`core/make_icons.py`: frame + hills, film strip + play, box on a turning plate, browser + cube,
  clapperboard, job list; one blue detail each), made at registration (`blender/make_icons.py`; Blender's own icons when
  that fails). No two sizes to pick from: the largest that shows whole in a narrow panel at UI scale 1.5 (guide picture
  `panel_top_make.png`) – about 24 px at UI scale 1 instead of 16.
- **Outputs strip** (`ops_make.py`): `FRESING_PT_make_strip` in the output window's toolbar region (left), one button per
  output (the window's own pressed, same order and filter as Make); `fresing.make_switch` switches this window (its kept
  size and, on Windows, its handle move to the new output – `winplace.rekey`); another window already showing that output
  comes to the front instead. One icon wide (46 px) when it opens (`settle_strip`: the side panel is off while the strip,
  copied at the left panel's 240 px, is made narrow – both at once squeezed the settings to 94 px for good); window 58 px
  wider than before. Dragged wider than 100 px: icon + name, and the settings shrink to the room left (`keep_filled` /
  `fill` + `ui_left.fit_side`; a side panel that does not fit is drawn EMPTY by Blender, measured – 12 px are left).
- **Blender's tabs and tools hidden** in output windows (`ops_settings.quiet_panels`): its tool buttons and every
  top-level Python panel of the tabs Item / Tool / View / Animation get a poll that hides them there (their sub-panels
  registered again under them; the inherited poll is kept – the old code dropped a poll that came from a base class).
  **Item stays while an object is active**: its Transform panel is no Python class. Owner's screenshot had Item, Tool,
  View, Animation beside Make; now Make (+ Item with a selection).
- **Render this view** (`ops_render_view.py`, `fresing.render_view`; under the Make row and in the header's Make list;
  allowed in the Client view like Render image). **Frame rule:** same centre and zoom as the view; the Picture's shape
  is fitted **round** the view (`core/view_camera.fit_halves`), so nothing the view shows is cut off – a wider picture
  shows more at the sides, a taller one more above and below. The angle is read from the view's projection matrix (not
  its lens setting), so it is what is on screen. Orthographic views: the camera stands half the clip distance back.
  Camera view renders that camera (local camera first). The temporary camera is deleted and the scene's put back after
  the render, on cancel (`cancel` + Render image's cancelled path), on an error; a leftover after a crash is removed at
  the next load / render. File `<project>_View_<YYYY-MM-DD>_<HHMMSS>.png|jpg` (`render.view_output_path`). Refused with a
  plain line while a render, the queue or a long job runs. Render image's work became a mixin (`ops_main.RenderStill`):
  subclassing the registered operator broke it ("unable to get Python class", its execute did nothing).
- Function entry `scene.render_view` (+ `panel.make` changed), tour stop `render_view` (+ `make` text), PC-check Full line
  `scene.render_view` (MIN_LINES_FULL 132), MIN_LINES_TOUR 101, `MIN_CHECKS["left"]` 55, guide (Make: the strip with a
  narrow and a wide picture, Render this view), CLAUDE.md (layout + two things learned), CHANGELOG 0.2.222.
- No lesson step: Render image (`scene.still`) has none either; Render this view is not a crane-lesson step.

**Tested and measured** (4-core web machine, test crane):
- `tests/test_render_view.py` (26): fit rule (4 shapes), lens / ortho scale from a projection, every icon on its grid,
  **the same picture as Render image from a camera at the same place** (largest difference < 0.02), a 4:3 view in the
  16:9 Picture (wider camera), orthographic stand-back, camera view (no camera made), error / cancel / leftover /
  refusals leave nothing behind, the strip's switch, the handle rekey, Blender's tab panels hidden in output windows only.
- Real app (`tools/ui_test_left.py`, 55/55): strip 46 px, settings 292 px beside it, Blender's tool buttons and tab
  panels not there, a strip button switches the window, dragged to 150 px the names show and the settings shrink to 184
  px (shown), Render this view saves `_View_` and leaves camera count and active camera as they were.
- PC check `scene.render_view` (bpy module): OK, difference 0.004, 0.9 s for a 160 x 90 draft.
- Locally also: test_functions, test_panels, test_places, test_quiet, test_user_guide, test_usage(_blender),
  test_form_window, test_settings_blender, test_workspaces_independent, test_toolmarks, test_left_folds, test_tour.
- Pictures: `docs/img/panel_top_make.png`, `sidebar_sections.png` (guide_screens), `make_strip_narrow.png`,
  `make_strip_wide.png` (ui_test_left with GUIDE_OUT).

**Open points / follow-up tasks:**
- The tab **Item** stays in output windows while an object is active (Blender's Transform panel is C code).
- The strip's width is not remembered: a window opens one icon wide each time.
- With the strip wide, long settings (3D page) wrap narrow; the user can drag the window wider (Blender gives a script
  no way to grow a window).
- `winplace.rekey` is a plain dict change (no Windows call): no separate Windows review.

**Owner's test steps (on your PC, after Update now):**
1. Open any project with a model. At the top of the Fresing panel the Make row is taller, with six larger icons.
2. Click the first icon (Picture). A small window opens; on its left is a strip of six icons, Picture blue.
3. Click the 3D page icon in that strip: the same window now shows the 3D page settings. Click Picture again: back.
4. Drag the strip's right edge (between the icons and the settings) to the right: the names appear beside the icons;
   the settings get narrower. Drag it back.
5. Close the window (× at its top). In the 3D view, turn and zoom to a view you like (no camera needed).
6. Click **Render this view** under the Make row. The render window shows exactly your view; the file name ends in
   _View_ and the date and time (5 Scene & Render > Image size & render: Open / Show in folder).
7. Check 5 Scene & Render > Cameras: no new camera, the active camera is the same as before.
