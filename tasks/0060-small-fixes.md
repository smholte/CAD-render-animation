# 0060 – Small fixes: floor in queued stills vs videos, test-run waiting, Blender folder spellings, black still with logo, test-run time

**Who:** worker · **Status:** open – can start (start now, 10 Nov, with 0050) · **Branch:** `task/0060-small-fixes`
**Started by:** lead chat, 9 Nov 2026 (open points of 0053 and 0054); fixes 4–5 added 10 Nov (0059 review)
**Lane:** Quality & delivery (`tools/ci_status.py`, `update_helper.py`) + Scene & Render (floor placement, the
surroundings code that places the floor; `blender/video.py` `finish_picture` for fix 4; `tools/ci_real_app.py` GROUPS and `tools/ci_times.json` for fix 5; no `animation.py` changes unless the floor of a video is set there – then
only that); tests
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Fixes

1. **Floor (0054 open point):** a still re-places the floor under the model's lowest point, an animation keeps the
   floor of frame 1; a part that swings below the floor during a video is cut by the floor in the video but not in a
   queued still of that frame. Make a queued still of an animation frame use the animation's floor (the frame shown
   = the video's frame), and say in the guide what the floor does. Test with the crane swinging a part below frame 1's
   lowest point.
2. **`tools/ci_status.py --wait` (0053 open point):** on a merge commit whose first parent differs only in the task list
   it says "no test run" although GitHub ran one. Judge by the commit's own run (or both parents). Test with a recorded
   API answer.
3. **Blender folder spellings (0053 open point):** matching other Blenders by path misses 8.3 short names and `subst`
   drives. Compare normalised long paths (`GetLongPathNameW`, case-insensitive) and the file's identity (volume serial
   + file index) where possible. Test with mocks on Linux; the Windows CI job runs the PC check line `updates.safe`.

4. **Still with a logo or watermark is black when the timeline is not on frame 1 (found by the 0059 test tour,
   added by the lead 10 Nov).** `render.render_still` → `video.finish_picture` renders its throw-away sequencer scene
   with `bpy.ops.render.render(scene=enc.name)`, which takes the frame of the scene in the context (frame 26 →
   nothing in the sequencer → black). Repro and details: 0059 report, open point 1. Fix: render inside
   `bpy.context.temp_override(scene=enc)` (the tour's video read-back already does this). Check queued pictures of
   an animation frame (0.2.46) with logo/watermark too. Test that failed before (crane, logo bottom right, timeline at
   26, mean brightness > 0.5). Then switch the still logo **on** in the test tour's "Still picture" stop
   (`blender/tour.py`; 0059 kept it off until this fix).
5. **The GitHub run grew from ~13 to ~20 min with 0.2.47/0.2.48 (lead 10 Nov).** Run 42726152004 on `main`:
   "real app paths-heavy" 18.1 min (usual 8.8: the automatic test tour joined that group), "test suite 2" 15.4 min,
   "test suite 4" 11.2 (usual 6.8). Move `tour` into its own real-app group (or the lightest one) in `GROUPS`
   (`tools/ci_real_app.py`), record the times of a green run (`ci_status.py --run <id> --record`, commit
   `tools/ci_times.json`) so the pytest groups balance again (`tests/test_tour.py` is new). Goal: a full run back
   near 13–14 min; give before/after in the report.

Runs at the same time as **0050** (Motion lane: `blender/queue.py`, queue panel in `ui_motion.py`, queue operators in
`ops_motion.py`). Keep fix 1 out of those files if you can; if it needs `queue.py`, keep it to a few lines and say so
in the report. Take the version number last; whoever finishes second merges `main` once and renumbers.

## Done when

- [ ] Five fixes with tests (fix 5: before/after run times); GitHub green incl. Windows.
- [ ] Guide note on the floor; if the test tour (0059) is merged: nothing to add (no new visible function).
- [ ] Merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0060 done.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
