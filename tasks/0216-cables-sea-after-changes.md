# 0216 – Cables and the sea after changes (bug hunt 0209 group D)

**Who:** worker · **Status:** done (0.2.168) · **Branch:**
`claude/happy-ritchie-2bilnp` (the session's branch)
**Started by:** lead, 18 Nov 2026 · **Model:** Opus · effort Medium
**Area:** Flex / Sea lanes – `blender/paths.py`, `paths_sea.py`, `vessel_motion.py`, `rebake.py`, `flex.py`,
`spool.py`, `surroundings.py` (+ tests). `camera_path.py` is group H's (after this task).

## Goal

Fix rows **7, 8, 27, 28, 29, 10, 31** of `tasks/0209-bug-hunt-7.md`. Row 7 first (0183 row 4, still open for its own
case): water level 2 → 3 m, re-bake, Undo → water 3.0 and the cable 1 m under the seabed, no re-bake; a copy saved
during it. Then **8** (demo updated with the same geometry: cable lengths change), **10** (a crane hook beside the hull
and a sea change / Fit / update: waterline), **27** (tension labels jump at frames 273–280), **28** (save during the
re-bake reopens at frame 1), **29** (carousel + drum both renamed "": shared tag), **31** (the demo's view clip start
0.29 m).

## Done when

- [x] Each row's repeat case is a test that failed before; the demo's tests and clash check unchanged.
- [x] Full run green; report filled in.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 18 Nov 2026 (one session, no subagents – the rows are small and in different
files; no independent review: no Windows code). Version **0.2.168** (0212 took 0.2.167 while this ran).

**What changed:**
- **Row 7** (`paths.py`, `rebake.py`): a second key `fr_cable_water_key` (water level, sea depth, each enabled sea
  cable's own depth; `paths.water_key`) is remembered with the motion key at Build and at every re-bake;
  `paths.sea_moved` = motion key or water key differs, used by `motion_changed(force=False)` (undo / redo) and
  `rebake._needed`. Old projects have no water key: nothing happens. **Opening** a built project runs the same check
  (`paths._check_opened`: a timer in the window, at once in the background after a `view_layer.update()` – without
  that update the surroundings measured a just-read file wrong and the sea came out 1 m off).
- **Row 8** (`paths.py`, `spool.py`): `before_model_update` also keeps, per cable, the part IDs it depends on (its part,
  ends, contacts' parts and carriers, the members of contacts' joints, its spool's drum and coil) and its CAD-pose
  points. `paths.cable_kept`: none of those changed and no new / changed part's CAD box comes within `ROOM` = 1 m of
  the cable → the cable takes the "same model" route of 0192 (`_keep_after_update`), its spool too. Only cables near
  a change are read again. The read-again route itself is unchanged (still loses hand order for a cable whose own
  parts changed – see open points).
- **Row 10** (`surroundings._model_box`): parts of a model root with `fr_lifting` (placed cranes) are left out (all
  of them only when nothing else is there); `vessel_motion.hull` reads that box, so the beam and pivot follow.
- **Row 27** (`paths_sea.NO_HANG`): 1 mm → 5 mm, clearly above `catenary.BED_GAP`.
- **Row 28** (`flex.at_first_frame` / `read_steps`): the frame shown before `at_first_frame` is kept on a stack; the
  save pause puts that one back.
- **Row 29** (`spool.renamed`): an empty (or blank) name puts the old name back.
- **Row 31** (`surroundings.scene_reach`, `fix_view_clip`): the reach is what is drawn (`fr_far` + objects), not the
  cameras' clip ends; a view whose near clip is exactly the value the app set for its far clip (`_app_start`) gets the
  pair set again, so the made demo opens with 0.156 m / 31.1 km instead of 0.29 m / 58.2 km. A user's own near clip
  stays.
- Guide: model update of cables (one sentence). No new function, PC-check line or tour stop.

**Tested and measured** (4-core web machine, Blender as a Python module):
- New tests, each failing before the fix (checked for rows 7, 10, 29 by running them on the old code; rows 27, 28, 31
  by their assert on the old value): `test_sea_after_build.py` (undo after a water change: −1.0 m → 0; a cable's own
  depth in the key; a copy saved during the job re-baked on opening), `test_paths_sea.py` (no tension at BED_GAP;
  save keeps frame 150), `test_spool.py` (empty name), `test_sea_cranes.py` (crane copy 15 m down beside the hull:
  box, waterline, beam, middle unchanged; control without `fr_lifting` moves it), `test_view_clip.py` (3 new),
  `test_paths_update_same.py` (own part changed / revision B → read again; far part → kept).
- **Row 8 on the made demo** (`test_demo_project_update.py::test_an_update_with_a_far_part_changed_keeps_every_cable`):
  the signature of the part farthest from every cable marked changed (> 3 m away), update + Build = the saved Build
  (every cable's length within 1 mm, contacts, ends, shapes within 2 mm, keys, labels, lay data). Not re-run on the
  old code (10 min); the bug hunt measured the read-again differences 2 of 2. Same-file update test unchanged
  (update 50 s, Build 84 s). Demo test file ~+150 s on GitHub.
- Locally also: test_spool, test_paths_kept, test_sea_change, test_rebake_objects_gone, test_surroundings,
  test_sea_cutaway, test_studio_cameras, test_vessel_work, test_weather_sky, test_cable_renames,
  test_model_update_cables (303 passed). GitHub: 2 full runs, both green (the second only because 0212 took 0.2.167 meanwhile: merge + renumber).

**Open points / follow-up tasks:**
- Row 8's deeper half: a cable whose own parts DID change is still read the old way; the bug hunt's FORCE_READ case
  (same geometry read again) still gives other wraps and follower order. Keeping wraps / follower order / bend
  carriers per contact through `read_cad(update=True)` is a larger change (Flex lane, Opus · High) if the owner sees
  it on real revisions.
- Row 31: the reach still counts object origins, not their size (fine for the demo: the sea's `fr_far` covers it).
- Group H (riding camera re-bake in steps) can start: `camera_path.py` untouched here.
