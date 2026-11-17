# 0192 – Fix: a model update to the same file keeps cable routes; re-bake also redoes riding cameras; seabed follows "Vessel at work"; one-pass background re-bake (bug hunt 6, rows 1, 7, 8, 10)

**Who:** worker · **Status:** running · **Branch:** `task/0192-cable-routes-update`
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

- **Added 17 Nov 21:25 (owner, 0.2.146, demo project, Solid view) – reaches the worker only if the owner pastes it:**
  the re-bake failed with "The cables could not be worked out again (StructRNA of type Object has been removed):
  Cables and hoses not worked out again for the new sea: the built animation was taken off. Press Build again". A
  Python reference to an object that was deleted meanwhile. Lead's candidates (not checked): (a) the sea rebuilt
  again (a second sea / weather / vessel-at-work change) while the job still holds the old sea's or seabed's objects;
  (b) a save / autosave during the job – `handlers._before_save` runs `spool.web_sweep()` (0187) **before**
  `flex.pause_read_for_save()`, so an object the read pass hid can look like a left-over drum solid; (c) Ctrl+Z during
  the job (undo replaces every datablock). Reproduce, fix the cause (keep names, look objects up again; a job that sees
  its objects gone starts over instead of failing), test that failed before. If the owner said what he did, start
  there.

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

**Chat / date:** Claude Code on the web (Opus, effort Medium), 17 Nov 2026. Version 0.2.148.

**What changed:**
- **Row 1** (`paths.py`, `spool.py`, `reimport.py`, `props.py`, `demo.py`): a read contact the user takes off is
  remembered (`fr_removed`, by part ID; a bend by its place) and stays off through a model update; "From CAD cable
  again" brings it back (as its tooltip says). A hand-set CAD-pose wrap has a flag (`wrap_user`, the demo's top pulley)
  and every reading keeps it. An end keeps the part it rested on when that part has become a cable since. An update
  that brings back **the same model** (every part same place and shape, none new / missing: `paths.same_model`) keeps
  every cable and spool as it was, only hung on the new parts (`_keep_after_update`, `spool.after_same_update`);
  a changed model is read again as before. (Tried and taken back: `spool.add_follower` taking the cable's start again
  as a reading does – it changed the made demo: the Build then took the guide cage's 8 rollers as left by the cable and
  freed them, and shot 11's D came 35 m off; GitHub run 44176599891.) The model update carries `fr_bounds_cad` over (lost
  on every part: the sea and the camera measured the model with the cable down to the seabed).
- **Why the tipping-wire ends changed:** the end rested on the tipping winch's lead (a `WIRE ROPE` part). Stage
  `winch_wires` made that lead a cable afterwards, and cable parts are left out of the touch search (`_read`'s `skip`),
  so a new reading found nothing and made it a free end on the swivel sheave's joint. Other causes of the drift found on
  the way: the carousel's arm follower added after its spool (bends stayed on the root; a reading put them on the arm),
  the A&R pulley's hand-set wrap overwritten by the reading AND by the spool's own `_set_cad_wraps`, the level winds'
  CAD-pose wraps worked out before the follower existed.
- **Row 7** (`rebake.py`, `camera_path.py`, `vessel_motion.py`, `ops_paths.py`): the re-bake re-keys the Animation
  camera when a step RIDEs / flies a PATH / AIMs (`rebake.cameras`: `animation._camera_track` from the camera's frame-1
  state and the Build's model centre, stored by `camera_path.Context`); `vessel_motion.follow` asks for it also with no
  hose or sea cable (`cameras_changed`, motion key `fr_cam_motion_key`). `animation.py` not changed.
- **Row 8** (`paths_sea.py`, `vessel_motion.py`, `props.py`): the bed sails at `vessel_work.speed_now` (Weather & time on
  or off) or, after a Build with Vessel at work steps, by keys of the metres sailed integrated from `fr_vw_ahead`
  (`ahead_keys`, `sailed`). `motion_key` uses `paths_sea.bed_key`. A Vessel at work change syncs the bed. A new speed /
  setting after such a Build takes the Build off ("Build again": the channel keys are written by Build in
  `vessel_work.py`, not this lane). Tooltip of "Vessel speed" and the guide say what drives it.
- **Row 10** (`rebake.py`, `paths.py`, `flex.py`, `props.py`): in the background every re-bake goes through
  `rebake.run_now` (`background`, `gathered`; the sea / vessel / weather property callbacks gather, `_one_rebake`);
  the cables' solve is a step per cable (`paths.motion_steps`, `_bake_steps`).
- **The owner's error "StructRNA of type Object has been removed"** (0.2.146, demo): the read pass kept Python
  references to every object it hid; a second sea / weather / vessel change during the job made the surroundings again
  and deleted them, and putting the visibility back failed. They are kept by name now; an object the pass READS that is
  deleted raises `flex.ReadLost` and `rebake.steps` starts over (3 tries). The owner's "What I did just before" came
  through blank; the lead's candidate (a) was reproduced, (b) (save) checked by the tester: no fault, (c) undo is
  swallowed during the job (0120).
- Guide: Cables (From CAD again / model update), Into the sea (vessel speed), the re-bake paragraph.

**Tested and measured** (4-core web machine, other jobs on it most of the time – seconds inflated, compare ratios):
- New tests, each failing before: `test_paths_update_same.py` (4: CHUTE back 6.490 → 6.645 m before; wrap 0.05 lost),
  `test_demo_project_update.py` (demo group 3), `test_camera_ride_rebake.py` (0.507 m off before),
  `test_paths_seabed_speed.py` (5: all 4 row cases failed before), `test_rebake_objects_gone.py` (2: the owner's
  ReferenceError before). `test_paths_kept.py`: its patch point moved from `paths._bake` to `paths._bake_steps`
  (same check).
- Demo (small form), update of the vessel with its own file then Build, against the saved Build (a fresh Build of it
  is bit for bit the saved one): before A&R wire 2.82 → 74.92 m, tipping wires' Bend 1 back, Power cable / Second end
  0.29 / 2.81 m off, 5 keys off up to 117 m; after: every length, contact, end, key and lay-label within 1 mm / 0.01°,
  shapes within 1.015 mm (one point of 11 M on the second end, the sea solve; the test allows 2 mm for shapes). Model
  update 50–84 s, Build 111–128 s.
- Row 10, small demo, sea CALM → ROUGH at the last frame: background route 176 s → 140 s (the tester: one pass through
  the 4,481 frames, 128 s against a Build of 132 s); the window job's longest step 13.3 s → 8.1 s.
- Make demo: 248 s (old code) / 270–323 s (new) under load – no comparable difference.
- Run here: the paths, spool, flex, tracks, model update, sea, vessel motion, camera ride, demo re-bake tests – pass.
- Subagents: one independent tester (Opus) wrote its own cases from rows 1, 7, 8, 10 and the owner's error (scripts
  gone with the session): rows 1, 7, 8 and the error held; it found F1 (new speed after a Build with steps: seabed 4.6 m
  off – now Build comes off), F2 (name lookups per frame made the read 25–50 % slower – references kept, a deleted one
  caught as ReferenceError), F3 (progress overwritten in the keep-tight rounds) – all fixed in the second commit.

**Open points / follow-up tasks:**
- Row 10's "no block > ~2 s" is **not met**: one sea cable's catenary solve (`paths_sea.solve`, ~7 s for the second end
  over 4,481 moments, each moment starting from the one before) is still one step. Splitting it by frame chunks with the
  state carried needs its own task (Flex / cable paths).
- Vessel at work steps' channels (`fr_vw_*`) are keyed at Build and go stale when the panel changes after it (0154,
  `vessel_work.py`): the wake too. Here only the seabed's case takes the Build off.
- A model update to a *changed* STEP of the demo was not tried (no changed demo model). There the carousel's bends
  move onto the arch (a reading carries them by the arm follower, the made demo has them on the root since its arm
  follower is added after its spool) – the made demo's Build and a read-again one differ; worth its own look.
- GitHub runs: see below.
