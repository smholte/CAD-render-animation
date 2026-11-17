# 0192 – Fix: a model update to the same file keeps cable routes; re-bake also redoes riding cameras; seabed follows "Vessel at work"; one-pass background re-bake (bug hunt 6, rows 1, 7, 8, 10)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0192-cable-routes-update`
**Started by:** lead chat, 17 Nov 2026 (from bug hunt 6, task 0183; after 0187) · **Model:** Opus · effort Medium · **Place:**
Claude Code on the web, environment "CAD-render-animation"
**Area:** Flex parts lane – cables (`blender/paths.py` `_merge` / `read_cad` / `_ends`, `blender/rebake.py`,
`blender/flex.py` `_motion_bake`, `blender/paths_sea.py` `sync_bed` / `_speed_ms` / `moves_by_time`, their tests).
Row 7 may *call* the camera-key build in `animation.py`; do not change `animation.py`, `cameras.py` or `surroundings.py`
(0193 works on the 3D view's clip there at the same time). Reads `vessel_work` (0154), does not change it.

## Goal

Updating a model with the **same** file changes nothing in the cable work; a re-bake gives exactly what a Build gives,
cameras included; a sea cable's seabed moves with the vessel's real speed; the background re-bake is one pass.

## Background

- Each row's proof, numbers, helper scripts and suggested fix are in `tasks/0183-bug-hunt-6.md` (Findings table, rows 1,
  7, 8, 10). Read those rows first.
- **Row 1 (lost work / wrong result, the big one):** `paths._merge` keeps no list of removed read contacts; `read_cad`
  rewrites every wheel's `wrap_cad` from its CAD-pose solve, also user-added ones; the demo's tipping-wire ends change
  (`_ends(keep_user=)`). Small case: test_paths_a, remove CHUTE from "Wire rope", update with the same file → CHUTE is
  back (6.490 → 6.645 m). Demo: A&R wire 2.82 → 74.92 m after Build, "cannot go round HANDLER TOP PULLEY …". The demo has
  no model-update test.
- **Row 7:** `rebake.steps` redoes hoses and cables but not the camera track: a camera that RIDEs the hull keeps the old
  heave (up to 1.48 m off).
- **Row 8 (new with 0154):** the seabed under a sea cable sails at one constant `weather.vessel_speed`, and only with
  Weather & time on; it ignores "Vessel at work" steps (Still / Ahead x kn).
- **Row 10:** the background re-bake route (scripts, tests, PC check, queue) takes 606 s on the small demo vs 221 s for a
  Build (`flex._motion_bake` drops its kept read in `finally`); the window's job blocks 20.4 s in the final cable solve.
- 0187 (0.2.146, done) changed the re-bake around save / undo (`flex.pause_read_for_save`, `motion_changed` after undo):
  build on it. Its open point: a file saved mid-job is right, but the re-bake is not in it.

## Rules for this task

- Every fix gets a test that **failed before** (CLAUDE.md section 6); nothing loosened.
- Row 1: remember removed read contacts (by part id) and keep stored `wrap_cad` and ends of user-set contacts through
  `read_cad`. **New test: the demo (small form) updated to its own file, then Build = identical** (cable lengths, keys,
  lay labels within 1 mm / 0.01°) – put it in the demo test group and keep the file inside the time rules of CLAUDE.md
  section 5. Find out why the tipping-wire ends change and say it in the report.
- Row 7: when a step RIDEs / follows a PATH / AIMs at a moving part, the re-bake rebuilds those camera keys (preferred)
  or takes the Build off with "Build again" – compare re-bake vs Build at ROUGH: all arrays equal.
- Row 8: drive the bed from the keyed `fr_vw_ahead` channel (or `vessel_work.speed_now`), with or without Weather & time;
  the tooltip and guide say what drives it. Test: the row's Still / Ahead → Still / Ahead 1 kn cases.
- Row 10: the background route goes through one pass (`rebake.run_now`), and the final cable solve is split into steps
  so the window's job redraws (no block > ~2 s on the small demo). Measure before / after on the small demo.
- An independent tester subagent re-runs the row cases from the bug-hunt helper scripts after your fix.
- Normal finish (sections 2 and 7); another task may take a version first – take the next free one when you merge.

## Done when

- [ ] Rows 1, 7, 8, 10 fixed, each with its failing-before test; the demo model-update test green.
- [ ] Measurements (row 10, and Make demo / Build times before / after) in the report.
- [ ] Guide / tooltips updated where the behaviour is described (re-bake, seabed speed).
- [ ] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

Row 16 (people → 0194); the 3D view's clip distance (0193); 0172's and 0174's older open points (slack cable on a
gutter, drum layers crossing).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
