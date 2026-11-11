# 0087 – Camera that rides along, flies a path or keeps a part in the middle (study 0069 #7)

**Who:** worker · **Status:** done (0.2.62) · **Branch:** `task/0087-camera-ride-path` (or the session's own branch)
**Started by:** lead chat, 11 Nov 2026 (lead's pick from the improvement study; the owner can change it)
**Lane:** **Scene & Render lane** – `blender/cameras.py`, `blender/ops_scene.py`, the camera part of
`blender/animation.py` (the CAMERA step's plan and the Animation camera), the Camera step's settings in
`blender/ui_motion.py`, the camera views in 5 Scene & Render (`ui.py`, only that sub-panel); additive: `props.py`;
tests, tour stop, PC-check line, guide
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0085** (vessel motion: `vessel_motion*.py`, the sea), **0086** (cutaway: `section*.py`,
`fade.py`, `materials.py`) and, from Thursday 08:00, **0058** (Flex parts: `flex*.py`, small hooks in `handlers.py`,
`animation.py` `bake`, `reimport.py`) and **0061** (Machining). In `animation.py` keep to the camera code; do not touch
`bake` beyond what the camera needs (0058 hooks it). Several releasing tasks at once: take the version number last;
whoever finishes later merges `main` once and renumbers (CLAUDE.md section 2).

## Goal

Fly along the cable route, ride on the gantry while it cuts, follow a hook – without setting up many cameras. Shots 1,
2b, 4 and 9 of the cable-lay demo video need it (`tasks/0083-cable-lay-reference-study.md`, shot list).

## What to build

1. **Three new Camera step modes** next to Cut / Move to / Orbit (6 Animation > Camera step):
   - **Ride along a part:** the camera keeps its place and view relative to a picked part or subassembly while it
     moves (on the carriage, the boom tip, a carousel's loading arm). Option **Keep level** (a camera riding on
     something that tilts stays upright).
   - **Fly along a path:** a smooth curve through points – *Make path from saved cameras* (in order) or clicked in the
     view – with an even speed and ease in/out; the camera looks ahead along the path, at the model, or at a picked
     part. The path is shown in the view, never in renders.
   - **Keep a part in the middle:** the camera stays where it is (or flies / rides as above) and turns so a picked
     part stays in the middle of the picture (a hook, the tool, the carriage).
2. They work with what is there: the Animation camera and the steps before and after (a ride can start from where the
   camera is and blend in/out), the sharp spot and background blur (focus follows), labels, turntable untouched,
   scripts off, the render queue, Save. Old projects: their camera steps give exactly the same keys as before.
3. **Vessel motion (0085, running now):** "Ride along" must be able to ride the vessel (camera on board). Whoever of the
   two merges second makes the vessel a ride target and tests it; say in the report which way it went.
4. Every button a tooltip; guide section (chapter 6, camera steps); PC-check line `camera.path` (a short ride + fly
   clip as a contact sheet, the camera's error numbers); tour stop "Camera rides and flies" on a test model with a
   moving part; `CHANGELOG.md`.

## Done when

- [x] Tests: riding camera = part's world matrix × the start offset at sampled frames (< 0.01 mm, < 0.01°), Keep level
      upright within 0.01°; path passes through its points, start/end right, speed even within 2 % (ease excluded);
      keep-in-middle: the part's projected centre within 1 % of the picture's middle; blend from the previous camera
      without a jump; scripts off; queue-runner frames = view frames; save/reopen; old camera steps' keys unchanged.
- [x] Screenshots of the changed panels checked (`tools/ui_screens.py`); guide pictures replaced.
- [x] Tour stop, PC-check line, guide, tooltips strict; the all-tour clash test still 0 rows; GitHub green incl.
      Windows; merged to `main` with the next free version, released.
- [x] Report filled in; `TASKS.md`: 0087 done; Scene & Render lane free.

## Not in this task

Motion blur (study #6), steady videos (study #14), a camera shake, the one-click product video (study #18).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 11 Nov 2026. Released as **0.2.62**.

**What changed:**
- Camera step: three new modes on a second row of buttons – **Ride along**, **Fly a path**, **Watch part** (= "keep a
  part in the middle"; the long name was cut off at the default panel width). New `blender/camera_path.py` (the
  plan of each new step, reading the parts per frame, the path line in the view) and `core/camera_path.py` (no
  Blender: smooth centripetal Catmull-Rom path through every point, measured by length; even speed with ramps;
  heading for Keep level). `animation._camera_track` now takes a per-step function; Cut/Move/Orbit maths unchanged.
- Ride along: camera(f) = part(f) × the offset where the camera is when the step starts, or a **Seat camera**
  (own setting `ride_camera`, so a new step's default camera does not change a ride). **Keep level**: follows the
  part's place and its turn seen from above, never its tilt. **Look**: with the part, or at a part.
- Fly a path: **Make path from saved cameras** (list order), **Add this view**, remove last, clear; **From where it
  is** (on by default: no jump); **Look** ahead / at the model / at a part; Motion + **Ramp (s)** = gentle start and
  stop, even in between. The path is a curve object in "FR Cameras" with `hide_render` (removed with its step, own
  copy on Duplicate).
- **Blend in (s)** (all three): the *difference* to where the camera was fades out, so a step that starts where the
  camera is moves exactly as without blend (a ride stays on its part). After the step the camera stays put.
- Focus: when a step watches a part (or the model) the sharp distance is keyed per frame to it.
- Parts are read at every frame of the step by setting the frames once at Build (as trail lines do); the seat
  offset and a part's middle are read at frame 1, so the render queue's copy gives the same keys.
- Model update remaps the watched part (`states.py`). Tour stop "Camera rides and flies" (crane), PC-check line
  `camera.path`, guide section in chapter 6 + 2 pictures, CHANGELOG.

**Tested and measured** (4-core web session, Blender 5.2.3 as module and real app, test crane):
- `tests/test_camera_ride.py` (19 tests): ride error 0.0000 mm / < 0.01°; Keep level upright within 0.01° on a
  tilting boom; path through its points, start/end < 0.01 mm, speed along the path even within 2 % (ramps excluded);
  Watch part: part's middle within 1 % of the picture middle, camera does not move, no roll; blend from an orbit: the
  first ride frame = the orbit's end (place and view); no drivers on the Animation camera (scripts off); save +
  reopen + build again (= the queue copy) gives the same frames; old Cut/Move/Orbit keys identical to a file recorded
  with the code before this task (`tests/camera_golden_0087.py`, `tests/data/camera_keys_0087.json`).
- PC-check line `camera.path` here: OK, ride 0.0000 mm / 0.0000°, path end 0.0000 mm, speed even 0.00 %, trolley
  0.00 % off the middle; 6 small frames in 14 s total.
- `tests/test_tour.py` + all-tour clash test: 48 passed (the new animation has 0 clashes).
- Tooltip report: 567, 0 missing. Panel pictures checked (no cut-off labels after shortening).
- GitHub: 3 full runs. Run 1 red: the panel test's fake layout had no `prop_enum` (added to `tests/test_blender.py`),
  and the PC-check line's `since` was ahead of the version (expected before the bump). Run 2 green (0.2.61), but
  0035 released 0.2.61 meanwhile; run 3 after merging main as 0.2.62 green (11.8 min), `main` fast-forwarded to it.

**Open points / follow-up tasks:**
- **Vessel (0085):** 0085 was not on `main` when this merged, so 0085 (merging second) makes the vessel a ride target
  and tests it. Ride along takes any part/subassembly: if the vessel motion moves the model's root, picking the
  root (or any part on deck) already rides it.
- "Add this view" is not covered by an automatic test (needs a real 3D view); the owner can try it in the tour.
- Reading parts per frame costs one frame change per frame of a ride/watch step; not measured on a big model.
- Orbit's centre is read on the frame shown at Build (old behaviour, kept so old keys stay identical).
