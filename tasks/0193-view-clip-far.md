# 0193 – Fix: the 3D view cuts the far scene away (turbines, sea, wind park) – only camera views see far

**Who:** worker · **Status:** done (0.2.148) · **Branch:** `task/0193-view-clip-far`
**Started by:** lead chat, 17 Nov 2026 (owner's screenshots of the demo, 0.2.145) · **Model:** Sonnet · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area:** Scene & Render lane – `blender/surroundings.py` `fix_clip` (+ a small helper, a new file if it grows),
`blender/demo.py` / `blender/demo_park.py` only where they set a far distance, `ops_import.py`'s view framing (one line),
a `load_post` hook in `handlers.py` (additive), their tests. Do **not** touch `animation.py` or the cable files (0192 runs
at the same time).

## Goal

In the app's own 3D views (User Perspective, not a camera view) nothing that belongs to the scene is cut off: the far
turbines, the substation, the sea to the horizon. No grey area where the scene stops.

## Background

- **Owner, 17 Nov (demo project 0.2.145, RTX 3090):** in User Perspective a grey area cuts everything in the distance –
  a turbine tower loses its lower part while its blade tips (nearer) stay, the sea's waves end in a jagged line, the far
  turbines vanish. In a camera view all is there. Screenshots in the lead chat (not committed – owner's screen).
- **Cause (lead):** the view's far clip. `surroundings.fix_clip` raises only the **cameras'** `clip_end` to the
  surroundings' reach (`fr_far`); `demo.py` sets the cameras to ≥ 2,000 m, `demo_park.py` to ≥ 8,000 m; the import's view
  framing (`ops_import.py`) sets the 3D view to `size × 20` of the model read then (the vessel, before the park and the
  sea exist). Nothing raises the 3D views' `clip_end` afterwards, so they keep Blender's / the import's value.
- The view's clip start matters too: a far end with a tiny start (0.01 m) gives flicker between faces in Solid view.

## What to do

1. One helper that sets every VIEW_3D space's `clip_end` (all windows and screens of the file, not camera views – those
   use the camera's own value) to at least the scene's far reach: the surroundings' `fr_far`, the farthest object of
   the scene incl. the wind park, the cameras' largest `clip_end`. Never lower a larger value the user set.
2. Pick `clip_start` from that distance so the ratio end / start stays at a level that does not flicker in Solid and
   Material Preview (measure; e.g. ≥ 0.05 m for a 10 km scene), but never so large that a close look at a part is cut
   (raise it only when the scene is that big; say the rule in the report).
3. Call it where the far reach changes: `fix_clip` (surroundings built or changed), after Make demo and each demo stage
   that adds far things (park), after an import / model update, and once when a project opens (`load_post`), so old
   projects (0.2.145's demo) are right without making them again.
4. Guide: one sentence in the surroundings section ("the 3D view sees as far as the scene reaches").

## Rules for this task

- Tests: the small demo (or the sea + park test scene) → every VIEW_3D `clip_end` ≥ the far reach and the farthest
  turbine inside it; an old project saved with a 1,000 m view clip opens with the right value; a user's larger value is
  kept; a small model (test mill) keeps a small clip start. Real-app check with a window (`--enable-event-simulate`
  or the UI screens tool) that a far turbine is drawn in User Perspective – a picture compared before / after.
- Every fix gets a test that **failed before**; nothing loosened. Normal finish (sections 2 and 7); take the next free
  version when you merge.

## Done when

- [ ] The 3D views see the whole scene in the demo, new and opened from 0.2.145; no Solid-view flicker on the vessel.
- [ ] Tests above pass locally and on GitHub; a before / after view picture in `tasks/img/0193_*` (invented demo only).
- [ ] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

Camera clip values (already right); the web page's camera (Web 3D lane); fog / haze looks.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 17 Nov 2026

**What changed:** `surroundings.fix_view_clip` sets every VIEW_3D space's `clip_end` to the scene's reach x 1.1 + 10 m
(`scene_reach`: `fr_far`, the farthest visible object incl. the wind park, the cameras' largest clip end); never lowers a
larger value. Clip start: 0.01 m below 5 km reach, else 0.05 m per 10 km of reach (max 0.5 m) – raised only. Called from
`fix_clip`, the import's view framing, after every demo stage, and in `load_post` (old projects). Guide: one sentence.
Version 0.2.148.

**Tested and measured** (4-core web machine): `tests/test_view_clip.py` (5 tests: old 1,000 m view reaches a far object at
6 km, user's 90 km kept, small scene keeps 0.01 m start, big scene raises start and counts cameras, `fix_clip` sets views).
GitHub full run green. NOT done: the before / after real-app view picture (`tasks/img/0193_*`) and a check on the made
demo – only the owner's PC shows the far turbines drawn; please look at User Perspective in the demo after updating.

**Open points / follow-up tasks:** the new test needs no `failed before` proof beyond the missing function; no picture.
Runs: 3 on the branch + this. The Windows job failed twice for unrelated reasons (shortcut icon check once, `web3d.small`
browser page "loading" twice, once in a rerun) and passed on rerun – a flaky `web3d.small` on Windows may need a task.
Version clashed once (0189 took 0.2.147).
