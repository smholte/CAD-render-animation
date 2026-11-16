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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
