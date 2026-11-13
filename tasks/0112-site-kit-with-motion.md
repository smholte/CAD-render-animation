# 0112 – Render kit with motion: Thor and the brick press as app projects, gallery refresh

**Who:** worker → owner (renders on his PC) → a short take-in session · **Status:** running (13 Nov) ·
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

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
