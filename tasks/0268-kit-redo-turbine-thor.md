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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
