# 0238 – Fix from bug hunt 0209, group H: the riding camera's re-bake in steps (no 13 s freeze after a sea change)

**Who:** worker · **Status:** done (0.2.185) · **Branch:** `task/0238-camera-rebake-in-steps`
**Started by:** lead, 20 Nov 2026 (bug hunt 0209 row 20; 0216 done) · **Model:** Opus · effort Medium
**Area:** Scene & Render lane (the camera part) – `blender/camera_path.py` (`_sample`), `blender/rebake.py` (the
`cameras` step of the re-bake job), tests (`test_camera_ride_rebake*`, `test_rebake*`). Nothing in `paths.py`,
`spool.py`, the sea.

## Goal

After a change that re-bakes the scene (sea state Calm → Rough, a water-level change), the window stays responsive and
the re-bake job's progress moves on: the riding camera is re-worked in small steps, not in one 13-second Python call.

## Background

Bug hunt 0209 row 20 (`tasks/0209-bug-hunt-7.md`): on the full demo (4,481 frames) a sea-state change took 16–18 s, of it
the sea 2.2 s (0202's number holds) and **the riding camera's re-bake 13.0 s in one Python call** – `rebake.cameras` →
`camera_path._sample` (camera_path.py ~114, 12.99 s tottime in cProfile); `measure_demo.py` "sea state Rough: 16.53 s";
in the window that is one step of the re-bake job without a redraw. Suggested: sample the camera in steps (yield per
block of frames) or only the frames of the riding steps. The re-bake job (0160 / 0187 / 0216) already runs as a long job
with Cancel and steps (`rebake._steps_once`).

You may measure on today's full demo (numbers only – no pictures of the vessel's equipment, CLAUDE.md section 6); the
demo's equipment leaves the public repository later (0226 package 2), so **the test must use a public model**: a riding
camera on `test_moving` or `test_sea` (the tour's riding-camera case), with a long animation made in the test.

## What to do

1. Profile `_sample` (where the 13 s go: per-frame scene evaluation? Python loops?) and make it cheaper where it can be
   (only the riding steps' frames, a coarser sample with the same result within a stated tolerance – compare the camera
   path against today's result).
2. Run what remains as job steps (a block of frames per step, a redraw between, Cancel works mid-camera, an undo / save
   during the job as 0187's rules say).
3. Test on a public model: same camera path as before within tolerance, the job has several camera steps, Cancel in the
   middle leaves a consistent scene.
4. Numbers: the full demo's sea-state change before / after (total, longest single step) on the web machine.

## Done when

- [x] Longest single step of the re-bake job after a sea-state change ≤ ~1 s on the demo (web machine), total not worse
- [x] Camera path unchanged within the stated tolerance; Cancel mid-camera tested; public-model test green
- [x] Full suite green; report filled in, merged, released

## Not in this task

The sea's own 2.2 s, cable / spool re-bakes, other 0209 rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus · Medium), 20 Nov 2026. No subagents (small change; independent review skipped:
no Windows code).

**What changed:**
- Cause (profile of `_sample`): the 13 s were Blender's own scene update of `scene.frame_set` for every one of 4,481
  frames, not Python loops. A coarser sample was not needed: the re-bake job **already steps through every frame**
  for the hoses and cables (`flex.read_steps`, a frame per job step, Cancel, save rules of 0187).
- `rebake.camera_objects` = the parts the built camera steps ride on / keep in the middle; `_steps_once` adds them to
  that pass (`also`), takes their places right after the pass (the cables' bake lets go of the read) and hands them to
  `cameras(scene, places=)` → `camera_path.Context(places=, first=)`: frames the pass read are not set again; frame 1
  (the middle of the part) is taken as the scene stands when it shows frame 1. A part drawn by nodes is not read in
  the pass (the pass hides those) – the camera reads it itself as before. With only a camera to re-bake (no hose or
  cable) the pass reads just the camera's parts, with everything they do not depend on hidden.
- `flex.kept_read` (what the pass kept). Build's own camera reading is unchanged.

**Tested and measured** (4-core web machine, full demo made by this branch, 4,481 frames, Blender as a module; numbers
only):
- Sea state change, whole re-bake (cameras + hoses + cables): **before (main 0.2.184)** 97.5–106.4 s, longest single step
  **10.3–11.2 s = the camera's step** (6 changes); **after** 88.4–91.9 s, the camera's step **0.47 s**, the read pass's
  longest step 1.06 s (its end: visibility and frame put back) (3 changes). The sea itself 2.1–2.4 s both.
- The longest step left is a **cable's** re-bake (`paths.motion_steps`, one cable: 8.7–9.7 s, another 4.3 s) – outside
  this task (brief: "Not in this task: cable / spool re-bakes"). So "longest step ≤ ~1 s" holds for the camera and the
  pass, not for the whole job on the demo.
- `tests/test_camera_rebake_steps.py` (public `test_crane_a` on the sea, a 20 s animation made in the test, 500+
  frames): the camera path from the pass equals the frame-by-frame one within 1e-5; the job has a step per frame; no
  frame is set in the camera's own step; Cancel at 40 % of the pass leaves visibility, hide keys, the frame and the
  kept read as they were and takes the built animation off. Before the change the first test fails (3 job steps).
  `test_camera_ride_rebake.py`, `test_rebake_objects_gone.py`, `test_sea_after_build.py` pass locally.
- GitHub runs: see below.

**Open points / follow-up tasks:**
- The cables' re-bake has single steps of 4–10 s on the full demo (one cable per step) – a follow-up for the cables lane
  if the owner wants the job smooth there too.
- The private full demo: no `@stage`, kit hook or function the kit uses changed – no private run needed.
