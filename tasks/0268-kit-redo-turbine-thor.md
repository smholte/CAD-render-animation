# 0268 – Render kit: the turbine still and video without the sea cut-away, Thor's side picture with the corrected model (same camera, light and background), the dropped shots taken out

**Who:** worker → owner (renders on his PC) · **Status:** running · **Branch:** `claude/cool-ramanujan-lzs9ul`
**Started by:** lead, 21 Nov 2026 (owner 16:41: "these need to be redone without the cutout in the ocean: the whole
turbine picture and the offshore turbine video"; "thor_side.jpg needs to be redone with the updated Thor model – I like
the light and position and everything, only in the original model some parts were placed in the wrong position, so keep
the same camera position, background, light, only the updated model") · **Model:** Opus · effort Medium
**Area:** Site kit lane – `site/render_kit/` (`models.ini`, `make_site_pictures.py`, `projects.py`, `kit_run.py` only
if needed), `tools/site_projects/` (the turbine project: `iea15.py`), `tools/make_site_projects.py`, their tests
(`tests/test_render_kit.py`, `tests/test_site_projects.py`, `tests/test_site_turbine*.py`). **Not:** `site/index.html`,
`site/style.css`, `site/media/`, `media.json`, `tools/build_site.py` (task 0267 changes them – the take-in of the new
renders comes after 0267 is merged, see "After this task").

## Goal

The owner runs the kit once on his RTX 3090 and gets exactly three new files for the landing page: the offshore
turbine's **"Whole turbine"** still and its **7.56 rpm animation video**, both **without the cut-away box in the sea**,
and **`thor_side.jpg` again** – same camera, light, background, size and framing as today's picture, but from the
current Thor model (its control-box parts were placed wrong in the first model, fixed after that run – see
tasks/0112's Background). The shots the owner dropped are no longer made.

## What to change

1. **Offshore turbine** (`[iea15_offshore]`): views `Work boat, Whole turbine` (drop `Seabed`). The cut-away box round
   the pile (made for the Seabed view, task 0081 / 0116 / 0128) must be **off in every shot and in the video**: the sea
   surface whole, nothing cut. Check where the cut is made (project, view or step) and that the video's camera never
   shows it. The seabed and scour protection may stay in the model (unseen).
2. **Onshore turbine** (`[iea15_onshore]`): no stills now (owner dropped "From the field" and "At the door"); keep the
   model in the kit for later; the kit must run with no views for it (or leave the model out of the default run –
   your choice, say which).
3. **Thor side picture:** find how `site/media/thor_side.jpg` was made (git history of the file and of `models.ini`;
   task 0047 / 0057 reports; it is the "feature" picture in media.json) – the view, the camera (position, lens), the
   light look (DARK), surroundings (COLOR), the background colour, resolution and samples, the pose. Make the kit render
   **that same shot from today's Thor project** (with its corrected parts). Store the camera exactly (numbers in
   `models.ini` or the project), not "SIDE" re-computed from a changed bounding box if that would move it.
4. **A short run:** a kit choice (window tick boxes or a preset) so the owner can render **only these three jobs**
   (Thor side, turbine Whole turbine, turbine video) without the rest of the kit. Name it plainly ("Redo 21 Nov").

## Proof before the owner renders

- Render a low-sample Thor side picture on the web machine and lay it over today's `thor_side.jpg` (edge overlay or
  50 % blend + a difference picture): camera, framing and background must match; the only differences are the moved
  parts. Put the pictures in the report (`tasks/img/0268_*`), small.
- Render a low-sample "Whole turbine" still and three frames of the video: no cut-away visible anywhere.
- The kit's tests pass; the kit zip is published on the draft release `site-kit` as before (0112 / 0144).

## After this task (owner, then a short take-in)

1. Owner: download the kit, run "Redo 21 Nov" on the RTX 3090, upload the result zip to the `site-kit` draft release
   (as 17 Nov). The report gives him the exact steps in plain words.
2. Take-in (a short worker session the lead starts **after 0267 is merged**): `tools/build_site.py --take <folder>`
   swaps the three files into the new picture / video rows and "Built on Blender".

## Done when

- [ ] Seabed view and the two onshore views no longer made; the cut-away off in the Whole turbine still and the video
- [ ] Thor side shot reproduces today's camera, light, background and size from the corrected model (overlay proof)
- [ ] "Redo 21 Nov" short run in the kit window
- [ ] Tests added / updated; full suite passes; kit on the draft release
- [ ] Report below filled in, with the owner's steps

## Not in this task

The landing page and media.json (0267); the take-in itself; the test models and their web models (0259–0264, later
re-renders); new models from study 0113.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 21 Nov 2026 (branch `claude/cool-ramanujan-lzs9ul`).

**What changed:**
- **Thor side picture** (`[thor_side]` in `models.ini`): found how `site/media/thor_side.jpg` was made – the owner's
  first kit run (8 Nov, app 0.2.36, commit 73cafe5): Thor as drawn (no project, no pose), view LOW, lens 50, space
  NORMAL, DARK look, studio colour, 2400 x 1350 Final, then cut by hand to 1000 x 1350. I rebuilt that day's STEP with
  that day's converter (`tools/a4_to_step.py` at 73cafe5, 82 MB, 522 parts – the misplaced library parts included),
  imported it with today's kit code, and took the LOW camera the app works out for it. It renders the old picture
  with the cut at x = 780 px (mean difference 5 of 255 grey levels, the misplaced parts only). Stored exactly:
  `camera_at = 0.98078, -1.65913, 0.59383` (m), `camera_turn = 82.4523, 0, 32.0054` (degrees), `lens = 50`,
  `crop = 780, 0, 1000, 1350` → a 1000 x 1350 file named `thor_side.jpg`, credited as Thor.
  Colours: exactly Thor's lines (`[thor]`), so the picture has the colours of Thor's other renders on the site –
  orange base and control box, black top (owner 21 Nov, during the task; a first try that copied the old picture's
  grey foot / dark box was dropped). A test keeps the two colour lists equal.
- **The white ring under Thor's head in the old picture was itself a misplaced part** (a second copy of the base's
  foot, 0.385 m up); it is gone, as are the brackets on the head.
- **Offshore turbine**: views `Work boat, Whole turbine` (Seabed dropped). The cut-away came from the turbine sheet's
  `scene.cutaway` (made by `tools/site_projects/iea15.py`, applied by `blender/sheet.apply_scene`): removed, and the
  sheet no longer has the "Seabed" camera (`DROPPED`). The video's camera is "Whole turbine". Seabed and scour
  protection stay in the model, unseen. `site/render_kit/projects/iea15_offshore.json` matches a fresh conversion
  of the owner's STEP (checked here, `test_shipped_sheets_match_a_fresh_conversion`).
- **Onshore turbine**: `views = none` (and video none): the model stays in the kit, a model with nothing to make is
  left out of every run and not listed in the window.
- **Run choices** (`make_site_pictures.py`): a section with `jobs =` and no `file =` is a row of the start window
  that makes only the stills / clips it names; `ticked = yes` makes it the only row ticked when the window opens (and
  the run of the console route). `[Redo 21 Nov]` = `thor_side, iea15_offshore: Whole turbine, iea15_offshore: video`,
  about 31 min on the RTX 3090 by the kit's estimate (an expectation, not measured). A stopped run continues with only
  what it had. The window change is 3 lines in `kit_window.ps1` (a row is ticked when found and, if the row says so,
  ticked); reviewed independently (a Sonnet helper: OK, ASCII + CRLF kept, the CI layout check unaffected).
- New lines in `models.ini` (explained at its top): `camera_at`, `camera_turn`, `crop`, `names`, `model`,
  `views = none`, run choices. README.txt: the Redo row; CLAUDE.md section 3.

**Tested and measured** (4-core web machine, no graphics card):
- Overlay proof, today's corrected Thor through the kit at 1200 x 675 (crop 500 x 675, Preview, processor, 24 s):
  `tasks/img/0268_thor_side_overlay.jpg` (old | new | 50 % blend | difference) and `0268_thor_side_edges.jpg`
  (the old picture's edges in red over the new one). Best fit of the old picture at offset 0 px; camera, framing,
  light and background the same; differences only at the head (misplaced parts gone) and the colours of the base and control box (now as
  Thor's other site pictures).
- "Redo 21 Nov" end to end with the real `models.ini` (`--small`, processor): exactly `thor_side.jpg`,
  `iea15_offshore_whole_turbine.jpg`, `iea15_offshore_loop.mp4` + poster, in 87 s. The saved turbine project has
  `sea_cutaway` off; Whole turbine still and frames 1 / 7 / 13 of the clip at 960 x 540:
  `tasks/img/0268_turbine_no_cutaway.jpg` – the sea whole, no box anywhere.
- New `tests/test_render_kit_redo.py` (14 tests: the shipped choice, run choices and rows, plain problems, the window
  rows + a continued run, a real-Blender run with a stored camera, a crop and own name); `test_render_kit.py`,
  `test_site_turbine.py`, `test_site_turbine_standin.py` (Seabed in the stand-in, left out by the converter) pass
  locally; the owner's STEP sheet check passes. GitHub: see below.

**Open points / follow-up tasks:**
- The kit zip goes onto the draft release `site-kit` by `site-kit.yml` after the merge (it runs on a push to `main`
  that changes `site/render_kit/`).
- Take-in after 0267 (the lead starts it): the result zip holds `thor_side.jpg`, `iea15_offshore_whole_turbine.jpg`,
  `iea15_offshore_loop.mp4` (+ `_poster.jpg`) – the names `tests/test_site.py` REDO already expects.
- The Work boat picture was not asked for again; it may show the edge of the old cut-away (not checked on the
  owner's render).

**Owner's steps (on your PC, RTX 3090):**
1. On github.com (signed in) open the repository's **Releases**, find the draft **"Site kit - pictures and videos for
   the web page"** and click **fresing_site_kit.zip** (the new one, dated today or later).
2. Right-click the zip > **Extract All...** > **Extract** (into Downloads, next to your earlier kit folders).
3. Close Fresing Render. Open the new folder **"Fresing site kit"**, double-click **"Make site pictures.bat"**.
4. In the start window, the top row of the Models list is **"Redo 21 Nov - only Thor side, Whole turbine and the
   turbine video"** – ticked, all others unticked. If it offers **"Continue the run of …"**, untick that. Click
   **Start**. Expected: about half an hour (the window shows its own estimate).
5. When it is done, the **output** folder opens with **site_pictures_<date>.zip** and the contact sheet in your
   browser: you should see three items – Thor upright in the dark studio, the whole turbine at sea without any hole in
   the water, and the turning rotor clip.
6. On the same draft release click **Edit** (pencil), drag the zip onto "Attach binaries by dropping them here", wait,
   click **Save draft** (not Publish). Tell the lead chat: "redo pictures uploaded".
