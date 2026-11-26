# 0371 – Demo kit: the STEP reader crashes when Make it is started again after Cancel + the "format could not be read" lines

**Who:** worker · **Status:** open · **Branch:** `task/0371-demo-kit-cancel-restart` (public) + a branch in the private
repository only if the kit itself must change
**Started by:** lead, 26 Nov 2026 23:3x (owner's report on his PC, 0.2.270) · **Model:** Opus · effort High
**Private vessel: yes** – this task attaches `smholte/fresing-render-vessel` (private) with **read** access for the
kit; push access only if the kit must change (then follow its `CLAUDE.md`; mind the owner's private GitHub minutes –
no new jobs, one push when ready). Nothing of the kit (code, shapes, numbers of the spread, pictures) goes into the
public repository, its tests, this file or the report – use the public demo "Vessel in a wind park" or a tiny test
kit made in the test for every public test.
**Area:** Demo lane –
- `blender/demo.py` (the build framework: Cancel, clean-up, restart), `blender/ops_demo.py`, `core/demo_kit_run.py`;
- `importer/runner.py` (the reader process: cancel, ending the old process, a new start while one is still ending);
- `blender/compat.py` (the two `print`s "the project's format could not be read" – lines ~189 and ~507);
- their tests, CHANGELOG, the user guide's "Make a demo project" part if a message changes.

**Not:** `importer/step_reader.py`'s reading and meshing (0340 starts in the Import lane on Monday 30 Nov – touch it
only if the cause is there, and then say so at the top of the report), `build.py`, `props.py`, `joints.py`.

## What the owner saw (26 Nov, his PC, 0.2.270, kit 2)

1. **Help > Make demo project… > Demo cable-lay vessel (full) (kit 2) > Make it**, then **Cancel**, then **Make it**
   again → after a few minutes: *"The demo project could not be made (RuntimeError: Error: Import failed: Reader stopped
   (code 3221225477). ). Nothing was left behind except its log: …\Demo\Kits\fresing-vessel\Make demo log.txt"*.
   3221225477 = 0xC0000005 (access violation) in the reader process.
2. The log (owner's copy, lead has read it): the model was written, `demo_cable_lay.step` and
   `demo_quay_loading.step` imported, groups / looks / hold / marks done, then **"Joints 310/319" is the last line** –
   no stage title after it, then the error. The next reader starts in the kit are the wind park and the ROV imports.
3. **A third Make it, without Cancel before it, worked.** So the lead's reading: something from the cancelled run (a
   reader process still running or ending, its helpers, a shared cache / temp folder, a lock, a half-written STEP)
   collides with the new run. Not proven – find it.
4. The log's first two lines, on every start: *"Fresing Render: the project's format could not be read:
   '_RestrictData' object has no attribute 'filepath'"* (twice) – `compat.py` reads `bpy.data.filepath` while Blender's
   data is restricted (register / load time). Harmless today, but it must not print on a normal start.

## Goal

- Cancel, then Make it again (any demo, the public one included) always works, as many times as the user likes.
  Cancel ends the old reader process and its helpers for sure before the next run can start them, and a new run never
  shares a temp folder, cache entry or file name with a run still ending.
- If a reader process does stop, the message says which model it was reading (file name, not a path inside the
  user's folders) and the log gets a line for it – and the log is flushed line by line, so its last line is the last
  thing that happened.
- The `_RestrictData` lines are gone (wait until data can be read, or skip silently when it cannot); a real
  unreadable format still prints.

## Steps

1. Findings first (short, in the report): reproduce on the web machine with the **public** demo (Make it → Cancel at
   the import → Make it) and with the kit (private, scaled-down form). Say what collides. If you cannot reproduce it,
   say what you tried and fix the most likely cause you found in the code, with a test that forces it (for example a
   reader process held alive after Cancel).
2. Fix in the public app. Change the kit only if the cause is in it (then a new `kit_version`, a kit release by hand
   as its `CLAUDE.md` says, and say so under "Owner's test steps").
3. Tests: Cancel + restart (public demo, and a small fake import that is cancelled mid-read); the log's last line;
   no "format could not be read" on a normal start.
4. Report with **Open points** and **Owner's test steps** (on his PC: kit Make it → Cancel → Make it, twice; the public
   demo the same).

## Done when

Tests green on every OS, CHANGELOG + version (CLAUDE.md section 7), report in this file, merged.
