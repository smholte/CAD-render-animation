# 0238 – Fix from bug hunt 0209, group H: the riding camera's re-bake in steps (no 13 s freeze after a sea change)

**Who:** worker · **Status:** running · **Branch:** `task/0238-camera-rebake-in-steps`
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

- [ ] Longest single step of the re-bake job after a sea-state change ≤ ~1 s on the demo (web machine), total not worse
- [ ] Camera path unchanged within the stated tolerance; Cancel mid-camera tested; public-model test green
- [ ] Full suite green; report filled in, merged, released

## Not in this task

The sea's own 2.2 s, cable / spool re-bakes, other 0209 rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
