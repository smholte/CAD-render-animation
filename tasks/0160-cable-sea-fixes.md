# 0160 – Fix: cables and the sea after Build – renamed spools and tracks, old late-built projects, re-bake at any frame, water level, start scene

**Who:** worker · **Status:** waiting – starts **after 0159 is merged** (same files: `paths*`, `spool`, `flex`) ·
**Branch:** `task/0160-cable-sea-fixes`
**Started by:** lead chat, 16 Nov 2026 (rows of bug hunt 0147, report in `tasks/0147-bug-hunt-5.md`) ·
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation". Subagents
allowed (CLAUDE.md section 2), including an independent tester.
**Area (Flex parts lane + scenes):** `blender/joints.py` (`rename` only), `blender/props.py` (an update callback on
`FRCable.name`, additive), `blender/spool.py`, `blender/tracks.py` (`joint_renamed`), `blender/paths.py`,
`blender/paths_sea.py`, `blender/flex.py` (`_motion_bake`), `blender/states.py` (the start scene's Build note only),
`blender/longjob.py` (use), the cable panels' notes, their tests, the guide's cable / sea / start-scene sections.
**Do not edit:** `demo_model/`, `demo.py` (0153), `surroundings.py` / `core/sea.py` (0148, then 0154),
`cable_looks.py` (0158), the Web 3D lane (0161, 0143), `sequence.py` / `reimport.py` (0162).

## Goal

The owner's cable work survives renames and model updates, old projects build right, and what he sees after changing
the sea after Build is what renders – at any frame shown, without a minute-long freeze.

## Background

Read rows 2, 5, 6, 8, 12, 19, 20 and 21a of `tasks/0147-bug-hunt-5.md` first: each has the place in the code, a proof
with numbers and a suggested fix. Repeat each one before fixing it (the bug hunt's scratch scripts are gone; the rows
give enough to rebuild them). 0159 changes the same code first – read its report.

- **Row 2 (lost work):** `joints.rename` does not tell spools and tracks; `FRCable.name` has no update callback. Add
  `spool.joint_renamed` / `tracks.joint_renamed` calls and a cable-name callback that renames `FRSpool.cable` and the
  vessel-motion TAG / STILL lists. Test: rename drum joint, follower joint, track speed joint, drum cable → model update
  → Build: drum, level wind, pulleys still turn; no new "Track Belt" joint.
- **Row 5 (old projects):** a `load_post` step for scenes not stamped by 0.2.113+: anchor every sea cable once at the
  first frame, then stamp (the bug hunt's own suggestion). Test: a project built at a late frame in an old tag (make it
  with the old code in the test, as 0147 did) builds the same as one made in main.
- **Row 6 (wrong result):** `paths._motion_bake` and `flex._motion_bake` read at the frame shown. Show the first frame
  first, as `animation.bake` does since 0138, then put the shown frame back. Test: re-bake at the last frame = Build
  (needs the second end: the small demo form, `demo.build_project(small=True)`; keep the test inside the demo groups
  0145 made, ≤ ~10 min a file).
- **Row 8:** a water level change after Build re-bakes the sea cables (as `paths.motion_changed`), or takes the Build
  off with "Build again" – pick the one that is right at every frame.
- **Row 12 – lead's decision:** Build keeps putting the start scene's sea, weather and vessel speed back (that is what
  a start scene is for), but **never silently**: when Build is about to change a value the owner set after the last
  Build, the Build warning names it ("Sea state ROUGH → CALM from the start scene 'Overview'") and the panel of the
  value offers **Save into start scene**. Tooltip + guide sentence.
- **Row 19 (slow):** the re-bake after a sea change becomes a long job with progress and Cancel (`longjob`); Cancel
  takes the Build off with "Build again". Measure it on the small demo before and after.
- **Row 20:** also stamp unstamped scenes at Build (an appended old scene builds the same in every session).
- **Row 21a:** the let-go settle twitch (a point sliding 0.87 m for one frame) – warm-start the settle from the previous
  frame; two Builds give the same shape.

## Done when

- [ ] Every row above fixed, each with a test that failed before the fix (the row's proof as a test).
- [ ] Nothing loosened in existing tests; the demo tests stay within 0145's groups.
- [ ] Tooltips, guide sentences, function list / PC-check line / tour stop only where something visible changes
      (Save into start scene: a function-list entry and a tour stop).
- [ ] An independent tester (a subagent that did not write the fixes) tries to break them.
- [ ] GitHub run green; merged; version (CLAUDE.md section 7); report with a short list for the owner.

## Not in this task

The other rows of 0147 (0161, 0162, 0163); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026 (branch `claude/epic-babbage-1kvjwd`, the session's branch name;
released as 0.2.123 – 0.2.121 and 0.2.122 were taken by 0161 and 0163 meanwhile).

**In short (for the owner):**
1. A renamed drum, carousel, level wind, arm, track speed joint, track wheel or cable is kept – after a model update
   everything turns exactly as before.
2. Changing the sea, vessel speed or water level after Build now gives what Build gives, whatever frame is shown.
3. That work shows progress in 4 Motion > Cables and paths and can be cancelled (then: Build again).
4. Build names the sea / weather values it puts back from the start scene; "Save into start scene" keeps yours.
5. Old late-built projects repair themselves on opening (Build once more); no more one-frame twitch of a settling cable.

**What changed:**
- Row 2: `joints.rename` → `spool.joint_renamed`, `tracks.joint_renamed`; `FRCable.name` has an update callback
  (`paths.cable_renamed`, old name kept in `FRCable.name_was`) that renames the spools' `cable`, the app-made joints'
  `fr_cable` tag, the riders' run object and the shapes mesh; a name another cable has gets a free one.
- Rows 6 / 8 / 19: `flex.at_first_frame`; `paths._motion_bake` / `flex._motion_bake(kept=)` work from the first frame.
  **Not in the bug hunt's reading:** the sea itself, made again on a sea-state change, measured the model at the frame
  shown (waterline 0.24 m lower, other wave phases at the demo's last frame); `world.apply` now makes a built
  animation's surroundings at its first frame (a small change in `world.py`, outside the brief's file list). New
  `blender/rebake.py` + `fresing.rebake` / `fresing.rebake_cancel` (ops_paths.py): in the window the re-bake is a modal
  job (frame pass by `flex.read_steps`, progress box in the Cables panel and the status bar, Cancel/Esc = `clear_keys` +
  "Build again"); background unchanged. Water level after Build: touch-down from the pose at frame 1 (`anchor(live=)`,
  not the last Build's places – found by the tester) and a re-bake.
- Row 12: `states.start_scene_changes / start_scene_note / save_into_start_scene`, Build warning (only values changed
  since the last Build or scene switch: `fr_world_seen`), box + **Save into start scene** under Sea (Surroundings,
  Vessel motion) and Weather & time; sea state, water level, foam, moving waves and all Weather & time values.
  Function-list entry `scene.start_scene_save`, guide anchor `start-scene`, tour stop `start_scene` (weather set).
- Rows 5 / 20: `paths.version_scene` (load_post and Build): names, anchor once at the first frame (stamp
  `fr_cable_anchor`; at load only a built scene, at Build only a scene older than 0.2.110), settle.
- Row 21a: `core/catenary.hang_off_steady` re-solves lone frames on the other answer from the frame before; a Build
  no longer starts from the last Build's ψ.

**Tested and measured** (4-core web machine):
- New: `tests/test_cable_renames.py` (7), `tests/test_sea_after_build.py` (13), `tests/test_demo_project_rebake.py`
  (3, demo group). 19 of the 20 small-model tests fail on the old code (the 20th guards the new rename callback).
- Row 6 on the small demo: re-bake with the last frame shown = Build with ROUGH, every cable 0 m off (before: power cable
  0.73 m, second end with another point count even after the bake fix alone – the surroundings cause above).
- Row 19 on the small demo: before, one freeze of 61–80 s; now the frame pass runs in 3,834 steps (longest 0.49 s),
  then the solves block **~16 s** in one step (of 65 s in all) – still a freeze, much shorter.
- Row 21a: largest one-frame there-and-back 0.82 m → below 0.3 m (none at the let-go frames); two Builds identical.
- Local: the area tests (build_any_frame, paths_kept, paths_settle, paths_sea, tracks, spool, functions: 94 passed),
  tour stops start_scene / weather / night, tooltip report 757 ok, precheck.
- Subagents: one independent tester (did not write the code), small models only. It found 7 faults, all fixed with a
  test: water change re-anchored from the old seabed; Save into start scene with the weather off saved only the tick;
  a new cable took over an orphaned drum; `hang_off_steady` crashed with 3 moments; opening 0.2.113–0.2.120 projects
  re-set a touch-down kept on purpose; foam / moving waves still silent; a duplicate cable name moved both drums.

**Open points / follow-up tasks:**
- Row 19: the solves after the frame pass still block ~16 s on the small demo (longer on the full demo, not measured):
  splitting the cable solve per cable / per chunk of frames would need `paths._bake` as a generator.
- Build still puts back the start scene's light, background and detail silently (the tester's row 6; out of the
  lead's row-12 scope).
- An old (0.2.104–0.2.112) late-built project saved after Clear keys is not repaired on opening (it cannot be told
  from a touch-down kept on purpose): type its layback again. The guide says so.
- The modal job was not driven in a real window (Esc, clicks during the job); no real-app test for it.
