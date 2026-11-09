# 0054 – Render queue and video fixes from the bug hunt

**Who:** worker · **Status:** done (0.2.46, 9 Nov) · **Branch:**
`claude/friendly-cerf-hn6s1i` (the session's branch)
**Started by:** lead chat, 9 Nov 2026 (bug hunt 0045 rows 7, 8, 9, 10, 17, 18, 20b)
**Lane:** Motion (panel 7 Render queue) – `blender/queue.py`, `blender/ops_motion.py` (queue operators),
`blender/states.py` (`save_shot`), `blender/animation.py` (`CamState.of`, `bake`); additive `blender/callouts.py`
(row 20b only); tests; guide "Render queue"
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

What the queue renders is what the owner sees, an overnight queue stays in its own project, stopped jobs never mix
old frames into a new video, and videos keep the sharp spot on a moving part.

## Background (proof and suggested fixes: `tasks/0045-bug-hunt.md`)

- **Row 7** – "Add image" while scrubbed in a built animation queues a different picture (visibility and camera).
- **Row 8** – a stopped or failed animation job reuses old frames, even past the new end (fingerprint + encode only
  `frame_0001 … frame_<end>`).
- **Row 9** – a running queue leaks into any project opened afterwards (key the runtime state by the project file).
- **Row 10** – videos use a stale sharp distance when the sharp-spot part moved.
- **Row 17 a–e** – five small queue faults (remove while running, hidden "Queue …" scenes, rename drops
  "(with watermark)", deleted saved scene, runner dies before status.json).
- **Row 18** – paths typed as `//…` break in the queue's copy (360° photo, logo, font, music, picture cards). The
  G-code file and tool table were done in 0051.
- **Row 20b** – the labels pass reads every part's box on every frame (50 ms per frame on the Heavy machine).

Owner's later wish 0050 ("Start queue in …") is in the same panel; it may be added here only if the owner asks
before this task starts.

## Done when

- [x] Every row fixed with a test from its proof (17c–e and 18 may be by reading + test).
- [x] Row 20b: frame time with labels on the Heavy machine before/after.
- [x] Guide "Render queue"; tooltips if anything visible changed.
- [x] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [x] Report filled in; `TASKS.md`: 0054 done.

## Not in this task

Tool changes (0041). Milling (0051). Model update (0052).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 9 Nov 2026 – version **0.2.46**, branch `claude/friendly-cerf-hn6s1i` (the
session's own branch, not `task/0054-…`).

**What changed:**
- **Row 7** – `states.capture_visibility` reads keyed hiding (`fr_anim_hide` → `hide_render` of the frame; only the top of
  a hidden branch is stored). "Add image" stores a still copy of the animation camera at that frame
  (`queue.view_camera`: "Queue camera", hidden, `fr_queue_only`, not in camera pickers) via `save_shot(camera=…)`;
  `queue.tidy_queue_only` removes the hidden scene and camera with their last job.
- **Row 8** – `queue.fingerprint` (size, quality, length, render engine, world settings and group looks, every key of the
  built animation, place/hiding/material of every object at frame 1, the camera) in `fingerprint.txt` in the frames
  folder; `keep_frames` deletes all frames when it changed (message "rendering all N frames again") and frames past the
  end otherwise; `encode_mp4(last=)` takes exactly frame 1..end and fails when one is missing.
- **Row 9** – `_RUNTIME` remembers the project file; `current()` uses it only for that project (or a scene that still
  names its folder); `sync` never adopts another queue's jobs nor clears another project's runtime; the load handler
  syncs a reopened project whose queue this session started.
- **Row 10** – `animation.bake` runs `cameras.update_blur` on the start camera and the Move-to/Cut cameras after the start
  scene; when all cameras of the move share one sharp-spot marker the animation camera gets it as `focus_object` (sharp
  on every frame, also while the part moves) instead of focus-distance keys.
- **Row 17** – (a) skip file `skip_<id>` written on remove while running; the runner reports it "Removed from the queue",
  `sync` does not bring it back. (b) Every saved scene leaves out `fr_queue_only` scenes. (c) `queue.relabel` for adds and
  renames (animation and saved scene). (d) a deleted saved scene raises "The saved scene '…' was deleted". (e) jobs of the
  queue still WAITING when the runner is gone without a status fail with the log tail.
- **Row 18** – `queue._absolute_paths`: `//` in 360° photo, light photo, logo, font, music, picture cards and the saved
  scenes' world JSON made absolute (ID-property writes: no world rebuild) only for the saved copy, then put back.
- **Row 20b** – `callouts.PartBoxes`: part boxes once per video, `foreach_get` of matrices and hiding per frame.
- PC check line `queue.frame_shown` (Full; `MIN_LINES_FULL` 44); guide "7 Render queue"; tooltips of Current view and −.

**Tested and measured** (name the machine and the model):
- `tests/test_queue_fixes.py`: 15 tests (crane A), all failed on the old code, pass now. Locally also `test_phase2`,
  `test_studio_cameras`, `test_video`, `test_video_labels`, `test_gcode`, `test_pccheck`, `test_user_guide`,
  `test_updates`; PC check lines `import.crane` + `queue.frame_shown` with the bpy module (queued picture vs Render
  image: mean difference 0.0001).
- **Row 20b, Heavy machine** (`pccheck/heavy_scene.py`, 2,992 parts / 3,050 objects, 4-core web session, bpy module, 100
  frames, 1920×1080, two labels, orbit camera), two runs each: labels pass **77.7 / 73.8 → 8.6 / 8.7 ms per frame**
  (the frame change alone ~3 ms of that); the outline itself 62–65 → 3.7 ms. A 500-frame video: ~37 s → ~4 s.
- GitHub: **2 full runs** on the branch. Run 1 red: three more tests (milling, chips, air blast) counted every file in
  the frames folder and saw the new `fingerprint.txt` (fixed: they count frames only). Run 2 green (14.3 min), then
  `main` fast-forwarded to that commit (mode reuse) and released as 0.2.46.

**Open points / follow-up tasks:**
- The fingerprint does not see changes Blender keeps outside the app's settings (a material edited by hand in
  Blender's own editors, a mesh edited in Edit mode): such a change keeps old frames. Everything done in the side panel
  is seen.
- Two projects may now each run a queue at the same time (before, the second was blocked by mistake); both share the
  graphics card.
- Seen while testing (not changed): a still re-places the floor under the model's lowest point, an animation keeps the
  floor of frame 1; a part that swings below the floor during a video is cut by the floor in the video but not in a
  queued still of that frame.
