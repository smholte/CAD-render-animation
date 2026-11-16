# 0137 – Cable fixes: swivel and let-go kept, renames carried, sea cable re-worked after a vessel change, old projects

**Who:** worker · **Status:** done (0.2.110) · **Branch:** `task/0137-cable-data-kept`
**Started by:** lead chat, 15 Nov 2026 (rows of bug hunt 0131, report in `tasks/0131-bug-hunt-4.md`) ·
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Flex parts lane – cable paths):** `blender/paths.py`, `paths_swivel.py`, `paths_rollers.py`, `paths_sea.py`, `joints.rename`, `vessel_motion.hoses_follow` / `flex.motion_changed`, a `load_post` versioning step, their tests.
**Do not edit:** the Web 3D lane (0134), the Import lane (0139), `sequence.py` (0140).

## Goal

The owner's cable set-up survives model updates, re-reads, added contacts and renames; a built sea cable follows a change of vessel motion; old projects behave as they did.

## Background

The rows below are from bug hunt 0131 (report on `main`): each row has the place in the code, how to repeat it
("Proof") and a suggested fix. Read those rows first; repeat each one before fixing it.

- **Row 2 (lost work):** Swivel and Let go frame dropped whenever the contact list is rewritten.
- **Row 5 (lost work):** joint renames not carried into `contact.swivel`, `contact.joint`, `item.joint` and the `…_was` JSONs.
- **Row 7:** a built sea cable is not worked out again when vessel motion / vessel speed / sea state / preset changes after Build – re-bake (as `flex.motion_changed`) or take the Build off with a note; one route for every vessel/sea change (hoses too).
- **Row 14 (old project):** let-go sea cables of 0.2.95–0.2.102 projects sink over 4 s now – versioning: `sea_settle = 0` for those.
- **Row 16a:** `paths.ramp_steps` slope over changes 1–2 frames apart.
- Plus the guard 0136 leaves for later: `paths._follow` skips scenes that are not a real project scene.

## Done when

- [ ] Every row above fixed, each with a test that failed before the fix (the row's proof as a test).
- [ ] Tooltips, guide sentence where the owner sees a change, function list / PC-check / tour stop only if something
      visible changes; GitHub run green; merged; version (CLAUDE.md section 7); report (short list for the owner).

## Not in this task

Other rows of 0131 (they have their own tasks: 0136–0140); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (scheduled run), 15 Nov 2026 · 0.2.110

**What changed:**
- Row 2: `paths._CONTACT_FIELDS` has `swivel`; `_row_of` / `_write_contact` carry `swivel` and `let_go_frame`; `_merge`
  carries both onto the new reading's matching row. Model update, From CAD cable again, Add contact and a refused change
  keep them.
- Row 5: `joints.rename` calls the new `paths.joint_renamed`: `item.joint`, `contact.joint`, `contact.swivel` and the
  `follows` in `fr_swivel_was` / `fr_roller_was` follow the new name.
- Row 7: one route `vessel_motion.follow(scene, force)` (`hoses_follow` kept as its old name) → `flex.motion_changed`
  and new `paths.motion_changed` (re-bake of the cables when a sea cable exists; timer in the window, at once in the
  background). Build stores a motion key on the scene (`fr_flex_motion_key`, `fr_cable_motion_key`: the vessel rig's
  `fr_key` + Weather vessel speed for the seabed); `after_surroundings` (sea state, bow, preset, wind via
  `world.apply`) and `paths_sea.weather_changed` (vessel speed) call `follow(force=False)`, which re-bakes only when the
  key differs. Projects built before 0.2.110 have no key: the force=False routes do nothing for them until the next
  Build; the explicit vessel-motion settings still re-bake the hoses as before.
- Row 14: no version mark existed in projects, so `paths.version_settle` (load_post) stamps each scene
  (`fr_cable_settle`; also on a new cable); an unstamped scene's let-go sea cables whose `sea_settle` was never set get
  0. Side effect: a 0.2.103–0.2.109 project that used the 4 s default also opens with 0 (said in the CHANGELOG and guide).
- Row 16a: `paths.ramp_steps` reads the trend from frame pairs with no change and every step from the input payout.
- 0136's guard: `paths._follow` skips scenes tagged `fr_bake`.

**Tested and measured** (4-core web machine, Blender as a module): `tests/test_paths_kept.py` (13 tests, each row's
proof; all 13 failed on the old code, pass now; 14–16 s). The area: `test_paths*.py`, `test_flex*.py` (3),
`test_vessel_motion.py`, `test_sea.py`, `test_spool.py`, `test_couplings.py`, `test_tracks.py`: 859 passed (11.8 min).
No visible new function: no tour stop / PC-check line / function-list entry; guide sentences under "A let-go cable
settles onto the seabed". GitHub: 1 branch run, green (43777487903, 27.5 min; suites 3/6 and tour slow on a busy GitHub), main fast-forwarded (reuse). No subagents (Medium task, small changes).

**Open points / follow-up tasks:** the 0.2.103–0.2.109 trade-off above (no way to tell them from 0.2.95–0.2.102);
rows 7's hoses route for projects built before 0.2.110 only re-bakes after one new Build.
