# 0087 – Camera that rides along, flies a path or keeps a part in the middle (study 0069 #7)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0087-camera-ride-path` (or the session's own branch)
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

- [ ] Tests: riding camera = part's world matrix × the start offset at sampled frames (< 0.01 mm, < 0.01°), Keep level
      upright within 0.01°; path passes through its points, start/end right, speed even within 2 % (ease excluded);
      keep-in-middle: the part's projected centre within 1 % of the picture's middle; blend from the previous camera
      without a jump; scripts off; queue-runner frames = view frames; save/reopen; old camera steps' keys unchanged.
- [ ] Screenshots of the changed panels checked (`tools/ui_screens.py`); guide pictures replaced.
- [ ] Tour stop, PC-check line, guide, tooltips strict; the all-tour clash test still 0 rows; GitHub green incl.
      Windows; merged to `main` with the next free version, released.
- [ ] Report filled in; `TASKS.md`: 0087 done; Scene & Render lane free.

## Not in this task

Motion blur (study #6), steady videos (study #14), a camera shake, the one-click product video (study #18).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
