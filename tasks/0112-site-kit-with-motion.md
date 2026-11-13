# 0112 – Render kit with motion: Thor and the brick press as app projects, gallery refresh

**Who:** worker → owner (renders on his PC) → a short take-in session · **Status:** done (13 Nov); owner renders next ·
**Branch:** `task/0112-site-kit-with-motion` (or the web session's branch)
**Started by:** lead chat, 13 Nov 2026 (owner's choices 13 Nov, 20:00)
**Area (Site kit lane, new):** `site/render_kit/` (kit script, `models.ini`, README, the .bat), new
`tools/make_site_projects.py` (+ helpers `tools/site_projects/` if it grows), new `tests/test_site_projects*.py`,
`tests/test_render_kit*.py`; `tools/a4_to_step.py` / `tools/fcstd_to_step.py` only for fixes. `tools/build_site.py`
**additively** (only if `--take` needs to learn something for the new clips). **Do not edit** 0107's files
(`blender/web3d*.py`, `blender/lightbake.py`, `fresing_render/web/`) or 0110's (`core/clash.py`, `blender/clash.py`);
0111 comes after you in `site/` and reuses your Thor project.
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner refreshes the landing page's gallery with one double-click on his PC, and the gallery gets **moving
clips**: the brick press's cylinders pressing and the Thor arm moving, made with the app's own one-click product video
(0101). An AI session builds everything; the owner only downloads, runs and uploads the result back.

## Background

- The kit (`site/render_kit`, task 0047): `models.ini` → `make_site_pictures.py` imports each STEP fresh, puts on a
  look and surroundings, renders stills and a turntable, writes `site_pictures.json`; the owner sends the folder and a
  session runs `tools/build_site.py --take <folder> [--keep-old]`. Today it knows **no joints and no animation**.
- Models (CREDITS.md, `site/media/media.json`): EVO, FarmBot, CEB press, Thor, OpenArm. **Thor and OpenArm still wait
  for their second render** (0047 open point: Thor's control-box parts and OpenArm's up axis were fixed after the first
  run). The STEP files are **not** in the repository (licences allow it, but the repo keeps only pictures).
- **Thor:** `tools/a4_to_step.py` builds the whole arm from AngelLM/Thor's FreeCAD Assembly4 files
  (`freecad-src/Assembly*.FCStd`, 522 parts, 82 MB STEP), CC BY-SA 4.0; it has a gripper (`Gripper*.FCStd`). The CEB
  press comes from goscommons/CEB-Press via `fcstd_to_step.py` (246 parts, CC BY-SA 4.0). Both repositories can be
  cloned from a web session.
- App functions to use, never copy: joints (`blender/joints.py`, batch 0093), cylinders (0013), poses, Move joint
  steps, **6 Animation > Make a product video** (0101), weather presets (0109), the render queue, clash check (0065).

## Owner's choices (13 Nov)

- An AI makes the program; the owner runs it on his PC (RTX 3090) and uploads the result back.
- New moving clips: the **brick press** (cylinders) and **Thor**. The demo vessel **not** yet (owner decides later).
- Other models may come from study 0113 (a vessel, machines with moving parts, a truck) – the kit must take a new
  model by adding a section to `models.ini` (+ a project maker when it moves), no other code change.

## Scope

1. **App projects by script** – `tools/make_site_projects.py <id> --out <folder>` builds a saved Fresing Render project
   from the model's source (clone, convert, import with the app's own importer, look/colours from `models.ini`):
   - **thor**: 6 revolute joints on Thor's real axes (from the Assembly4 placements, not guessed; check each turns its
     whole chain with nothing left behind), the gripper fingers (slide or turn, as built), limits like the real arm's
     (Thor's docs if found, else safe ranges with 0 clash rows), 3–4 named poses, and a **seamless 10–12 s loop**
     (first pose = last pose, eased): reach down, close the gripper, lift and turn, put down, open, back. Carrying a
     small block only if the app can already make a part ride the gripper; otherwise leave it out and say so.
   - **ceb_press**: its hydraulic cylinders as app cylinders on their real pins, the press cycle (fill, press, eject)
     as a loop.
   - Clash check: **0 rows** for both animations. The project opens in the app like a user's (old-project rules).
   **0111 reuses the Thor project** for the web 3D model: keep the maker callable from Python.
2. **Kit with motion** – `models.ini` per model: `project = thor` (built by the kit on the owner's PC from the
   bundled source, or shipped ready in the kit zip – pick the faster one for him and say why), `video = turntable |
   product | animation | none`, `weather = <preset>` (0109 presets, e.g. FarmBot outdoors), video length/height as
   now. The clips are made with the app's product video (0101) or the project's own animation, rendered through the
   queue. The kit shows the expected total time before it starts, can be started later (0050 "Start later" or
   equivalent), and continues with the next model when one fails (reason in its log).
3. **Gallery set** (the owner may change it in `models.ini`): EVO 2 stills + turntable; FarmBot 1–2 stills in a
   weather preset; CEB press 2 stills + **product video**; Thor 2 stills + **product video**; OpenArm 2 stills. The
   hero (owner's milling video, `keep`) stays. Never the Fresing 400 (CLAUDE.md section 6). Keep the page light: clips
   ≤ ~5 MB each after `--take`'s compression, posters for every clip.
4. **Hand-over both ways:**
   - The kit zip (scripts + model sources or projects, no Fresing 400, nothing private) goes to a **draft release**
     `site-kit` on the repository (`gh release create --draft`, replace the asset when rebuilt). The owner, signed in
     on github.com, downloads it there. Write a 6-step README.txt (download, unzip, double-click, wait ~N h, find
     `site_pictures_<date>.zip`, upload it to the same draft release with "Edit" → attach).
   - The kit ends by packing everything the take-in needs into **one zip** (`site_pictures.json`, pictures, clips,
     posters, the kit's log with the app version and render times).
   - Make sure `tools/build_site.py --take <zip or folder>` takes clips and posters from the new kit (test with a
     small fake result) so the later take-in session is a few minutes: write its start sentence in the report.
5. Tests: projects build on GitHub at a small size (joints count, axes against the Assembly4 placements within 0.1°,
   loop closes, 0 clash rows), the kit runs end to end on a scaled-down set (Draft, few frames, CPU), `--take` with
   the fake result; CREDITS.md / media.json checks still pass (`tests/test_site.py`).

## Done when

- [ ] Thor and press projects build by script, 0 clash rows, loops close; Thor's joint axes checked against the source
- [ ] Kit: projects + product video / animation clips + weather per model, time estimate, continues past a failure
- [ ] Kit zip on the draft release `site-kit`, README for the owner; result packed in one zip; `--take` tested
- [ ] Tests added; full suite passes; report filled in (incl. the take-in start sentence and the owner's expected
      render time on the RTX 3090, estimated from measured CPU times)
- [ ] No new app function → no tour stop / PC-check line needed; say so in the report if that holds

## Not in this task

The landing page layout and "Turn it yourself" (0111). The web 3D export and baked light (0107). New models from 0113.
The demo vessel (owner decides later). Rendering the final pictures (owner's PC).

---

## Design (worker, 13 Nov)

- **Projects are made on the owner's PC by the kit**, not shipped as .blend: the kit brings `models/thor.step` +
  `models/ceb_press.step` and a small joint sheet per model (`projects/<model>.json`); `projects.py` makes the project
  with the app he has installed (so the project always fits his app version – old-project rules never come in), and
  the download is 28 MB instead of ~300 MB of .blend. Making the motion takes under a second.
- **Sheets come from the sources**: `tools/site_projects/thor.py` (Assembly4 frames → joints; round faces on both sides
  of each hinge check the axis; tooth counts from the parts' spreadsheets → couplings), `ceb.py` (cylinders split into
  barrel and rod, source faults fixed and listed in the sheet's `notes`), `stepout.py` (moving bodies as nested
  sub-assemblies, so joints are made on named sub-assemblies). `tools/make_site_projects.py` is the command line and
  the Python entry for 0111 (`build_project("thor", out)`).
- **Hand-over**: `.github/workflows/site-kit.yml` builds the kit on `main` (and by hand) and replaces the zip on the
  draft release `site-kit`; the kit ends in one `site_pictures_<date>.zip`; `build_site.py --take` reads that zip.

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 13 Nov 2026. No version change (no app code changed).

**What changed:**
- `tools/site_projects/` + `tools/make_site_projects.py` (new): Thor and the CEB press from their repositories at
  pinned commits (clone ~6 s, only the needed folders). **Thor**: 522 parts in 19 nested sub-assemblies; 18 joints –
  Art1–Art6, the gripper's servo arm (0–85°), passive arm, two links and two fingers (parallelograms: fingers stay
  upright), the four motor pinions (Art1 10:50 and Art2 10:60 inside ring gears, Art4 10:20 outside) and the wrist's
  two bevel gears (15:30 against the gear plate) coupled by the tooth counts in Thor's own part files. 7 joints a user
  moves; limits are safe ranges (Thor's repository gives none). 6 poses; loop "Thor at work" 10 s (reach down, grip,
  lift and turn, put down, release, home). No carried block: the app cannot hand a part from the table to the gripper.
  Two parts hidden for good (the app's "excluded"), said in the sheet: the elbow's toothed belt (inside the upper
  arm; a one-piece belt cannot run round its pulleys) and the Art1 pinion's grub screw (it sticks 0.7 mm into the ring
  gear when the pinion turns – in the source). **Press**: 248 parts; slide joints "Press plate" (0 … −200 mm) and
  "Drawer" (−140 … +100 mm, on its rails), two app cylinders in follow mode; loop "Press cycle" 9.5 s (closed, pressed,
  opened, brick up, brick pushed out, fill). Source faults fixed and listed in `projects/ceb_press.json` notes: both
  cylinders were one fused solid each (split into barrel and rod, rods run on inside a bore), the main cylinder sat
  10.8 mm off the compression chamber, the drawer did not fit its way (7 frame plates trimmed by ≤ 3.5 mm).
- `site/render_kit/`: `projects.py` (new: the project from a sheet with the app's own functions + checks), kit script
  (`project`, `video = turntable | product | animation | none`, `weather`, `pose`, `take_apart`, expected time before
  the start and again after the first picture, start later, models found in the first kit's folder, posters, one
  zip with the log), `models.ini` (the owner's set), `.bat` (shows the time, asks now/later), README (6 steps).
- `tools/build_site.py --take`: a zip or a folder, the kit's posters, gallery clips ≤ 5 MB (720 p when 1080 p does
  not fit), no doubles with `--keep-old`, Fresing 400 refused.
- `.github/workflows/site-kit.yml` (new): builds the kit and replaces it on the draft release `site-kit`.
- CLAUDE.md: layout, the workflow, three lessons. `tools/ci_times.json`: first times of the three new test files.

**Tested and measured** (4-core web machine, Draft meshes):
- Thor: STEP 121.6 MB written in 15 s, imported in 25 s; motion made < 1 s; joints on the Assembly4 axes within
  0.1° / 0.1 mm (test); every hinge has round faces on both sides (the wrong vertical elbow axis has 0 on Art2);
  **clash check of the loop: 0 rows in 127 s** (251 frames); loop closes.
- Press: STEP 24.6 MB in 5 s, imported in 7 s; **clash check: 0 rows in 8 s** (239 frames).
- Kit end to end, small (240 px, 8 samples, processor): both projects, stills in a saved pose, weather, Thor's
  product video, the press loop, posters, `site_pictures_<date>.zip` – 0 problems. Product video frames cost 3.8 s
  each here at 240 px (mostly the app's work per frame with 517 moving parts, not the picture).
- Kit zip: 27.7 MB (two STEP files compress 5x). 
- Tests: `tests/test_site_projects.py`, `tests/test_render_kit.py`, `tests/test_site_take.py` (new), `test_site.py`:
  44 pass locally (Thor's project with its clash check 171 s, the kit end to end 179 s). GitHub: 3 full runs, all
  green, none red – branch 43503839179, branch after merging main (0.2.89) 43506551242, `main` 43509333092 (main had
  moved again). The Site kit workflow ran on `main` (43509333140) and put `fresing_site_kit.zip` (27.7 MB) on the draft
  release `site-kit`; "latest" stays v0.2.89. Several pytest groups ran slow (13–16 min) while other tasks' runs
  shared the runners: `tools/ci_times.json` holds estimates for the three new files, not recorded times.
- Subagents: one (Sonnet), the independent review of the `.bat` below; nothing else delegated.
- No tour stop and no PC-check line: no new app function (the kit and the converters are tools, not the app).
- Independent review of the `.bat` (subagent, Sonnet): 2 real faults fixed (an unquoted start time – `23:30 & calc`
  would have run calc, a space split it; a crash during the estimate counted as success); 2 low risks left (a `)` in
  `%TEMP%`, several Blender versions installed).
- **Owner's expected render time on the RTX 3090: about 3 h 20 min** for the whole set (an estimate, not a
  measurement: 0.02 s per megapixel × sample for Cycles on the 3090 + 1 s per video frame for the app's work; stills
  2400 × 1350 Final ≈ 0.5 min each, the two 30 s product videos ≈ 80 min each, EVO's turntable ≈ 30 min). The kit
  measures its own speed on the first still and says the finish time in its window and log.

**Take-in session** (after the owner uploaded `site_pictures_<date>.zip` to the draft release `site-kit`):

> **Claude Code on the web · Sonnet · effort Medium**
> Read CLAUDE.md and TASKS.md in github.com/smholte/CAD-render-animation and take in the owner's site pictures (task
> 0112's take-in): download the newest site_pictures_<date>.zip from the draft release site-kit (`gh api
> repos/smholte/CAD-render-animation/releases`, then the asset with `-H "Accept: application/octet-stream"`), run
> `~/venv/bin/python tools/build_site.py --take <zip>` (add `--keep-old` only if its log.txt says a model was skipped),
> build and check the page (`tools/build_site.py`), look at the contact sheet's clips, and merge.

**Open points / follow-up tasks:**
- The owner renders and uploads (README steps); then the take-in session above.
- 0111 can reuse Thor: `tools/make_site_projects.py thor --out <dir> --project` (or `build_project` from Python).
- OpenArm and FarmBot STEP files are not in their git repositories: the kit takes them (and EVO) from the first kit's
  `models` folder next to it; a later kit could fetch them if the owner wants it fully self-contained.
- Thor's joint limits are safe guesses (0 clash rows in the loop); the product video moves the three longest joints to
  their limits from Home – not clash-checked (only the loops are).
- The kit's time estimate rule (0.02 s per megapixel × sample on the 3090) should be compared with the owner's log.
