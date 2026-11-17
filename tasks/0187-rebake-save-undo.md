# 0187 – Fix: saving or undoing around the cable re-bake; small cable/spool rows (bug hunt 6, rows 3, 4, 11, 14, 15)

**Who:** worker · **Status:** done (0.2.146) · **Branch:** `task/0187-rebake-save-undo`
**Started by:** lead chat, 17 Nov 2026 (from bug hunt 6, task 0183) · **Model:** Sonnet · effort Medium · **Place:** Claude Code on the
web, environment "CAD-render-animation"
**Area:** Flex parts lane – cables (`blender/rebake.py`, `flex.py` `read_steps`, `paths.py` / `flex.py` undo handlers, `queue.busy_job`, `paths_sea.numbers`, `spool.py` `renamed` / `web_end`, their tests)

## Goal

Saving, autosave, the queue or Undo during or after "Working the cables out again" never leaves a project with hidden
parts or a cable for the old water level; small cable/spool faults fixed.

## Background

- **Row 3 (lost work):** Ctrl+S / autosave / an undo step while the re-bake job runs saves the project with most parts
  hidden and at another frame (`flex.read_steps` hides what the read does not need); `queue.busy_job` does not know the
  re-bake, so Save does not warn and the queue would copy that state.
- **Row 4:** after a re-bake, Ctrl+Z brings back the new water level with the cable for the old one (1 m under the
  seabed), still "built", no re-bake starts. Same for sea state / vessel speed. Real-app case in the row.
- **Row 11:** a web export run as a script leaves the hidden "FR spool solid …" objects (`spool.web_end` removes them by a
  timer only when there is a window).
- **Row 14:** lay data after let go shows Top/Bottom tension 16,802 kN (height ≈ 0) → show "–".
- **Row 15:** renaming a drum to another drum's name is accepted (no free name, as `paths.cable_renamed` does).

## Rules for this task

- Each row's proof, numbers and suggested fix are in `tasks/0183-bug-hunt-6.md` (Findings table): read only those rows.
- Every fix gets a test that **failed before** (CLAUDE.md section 6); nothing loosened.
- Normal finish (CLAUDE.md sections 2 and 7): own branch, area tests locally, version raised last, CHANGELOG in plain
  words, green GitHub run, merge, release. Other fix tasks of bug hunt 6 run at the same time: take the next free
  version when you merge.
- A row you cannot reproduce or fix: say so in the report with what you saw; do not guess.

## Done when

- [ ] Row 3: the re-bake is in `busy_job` (Save warns, the queue / a delayed start waits) **and** a `save_pre` (or
      equivalent) puts visibility and frame back for the save, so a save in the job writes the right state. Test: the
      row's case (save a copy at 30 %) reopens with the same hidden objects and frame as before the job.
- [ ] Row 4: after undo/redo, a built animation whose cable inputs moved since the bake re-bakes (or takes the Build
      off with a note) – never shows old shapes with new water. Real-app test (`--enable-event-simulate`, Ctrl+Z).
- [ ] Rows 11, 14, 15 each with a test that failed before.
- [ ] Rows 1, 7, 8, 10 are NOT in this task (a later Flex-lane task).
- [ ] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

Rows 1, 7, 8, 10 (next Flex-lane task); web 3D files other than what row 11 needs in `spool.py`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker (Claude Code on the web, Sonnet), 17 Nov 2026

**What changed:** version 0.2.146.
- Row 3: `queue.busy_job` names the re-bake ("Cable re-bake", so Save warns and the queue / delayed start wait); a
  `save_pre` (`flex.pause_read_for_save`) puts the hidden parts, muted keys and frame back for the save and `save_post`
  (`flex.resume_read`) hides them again.
- Row 4: `flex._on_undo` / `paths._on_undo` call `motion_changed(force=False)` after an undo/redo: when the key of the
  motion the shapes were worked out for differs from the scene's motion, the re-bake is requested (window: the job;
  background: at once).
- Row 11: `spool.web_end` leaves no solids in a saved file: `web_sweep` before every save (the export's own lists still name them when it ends).
- Row 14: `paths_sea.numbers` gives `top` / `bottom` = None when the cable hangs less than 1 mm (height or length);
  the panel and the labels show "–".
- Row 15: `spool.renamed` gives a drum or carousel a free name ("Drum 2") when the new one is taken.

**Tested and measured** (4-core web machine, test_sea.step / test_spool.step): new tests that failed before the fix –
`test_paths_sea.py` (no tension on the seabed, undo brings back a re-bake, save during the read pass + busy_job),
`test_spool.py` (no solids saved, no duplicate drum name); real app `ui_test_undo_rebake.py` (group `undorebake`,
4 checks, in `machines`): real `bpy.ops.ed.undo()` after a re-bake – fails without the fix (key back at the old
speed), passes with it. Note: a simulated Ctrl+Z key press (`event_simulate`) did nothing in the test, so it calls the
undo operator. Not tried: the 3-minute re-bake on the demo with a real Ctrl+S in the job (the read pass is covered by
the unit test with the same objects and handler functions).

**Open points / follow-up tasks:** rows 1, 7, 8, 10 stay for the next Flex-lane task. The save puts the frame back but
does not make the job's partial shapes "built": a file saved mid-job is right but the re-bake is not in it (it is
requested again on opening only if the motion key differs – not checked).

Runs: three on the branch. The Windows job failed on `web3d.small` (and once `web3d.under`: the headless browser's page gave no places) three times in a row without any change of mine near it, then passed on the third re-run – looks like a flaky Windows browser check, worth a look by the lead. Then 0186 and 0188 took 0.2.144 / 0.2.145: merged main, renumbered to 0.2.146, second full run green. Row 11 first removed the solids at once, which broke `test_web3d_moving` (the export's own list still named them): now swept before every save (`spool.web_sweep`).
