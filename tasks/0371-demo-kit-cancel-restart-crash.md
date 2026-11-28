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

## Report

**Chat / date:** worker (Claude Code on the web), 28 Nov 2026. `importer/step_reader.py` not touched.

**Findings (step 1).** Not reproduced on the 4-core Linux web machine, with a background Blender started exactly as
Make it starts it (scaled-down form): public demo, Cancel during the import → Make it again: OK (77 s); public demo,
Cancel during the model maker → Make it again: OK; kit 2 (private, scaled-down), Cancel during its first import →
Make it again: OK (367 s). On Linux nothing of the cancelled build was left running (reader helpers stop with their
reader). What the code did allow – and what a Windows PC can hit:
1. **Make it could start while programs of the cancelled build were still running or ending.** The app counted the
   build as over as soon as the background Blender itself had ended. Cancel's forced stop (`taskkill /T`) ran only
   when the build did not stop by itself within 4 s; a build that stopped by itself after Cancel (between stages, in
   the maker's loop) killed only its maker, and nothing checked the rest. `taskkill /T` / `TerminateProcess` also
   return before the processes have ended (memory and files are freed later) – on a 24-core PC a reader with ~20
   helpers. The most likely collision: the new build's reader starting next to the old reader / helpers still
   holding memory, or Windows handing out the same process number again.
2. **The reader's work folder was named `<cache>.partial-<process number>-<job count>`** – Windows reuses process
   numbers quickly, so a new build's job could get the name of an old one's.
3. **The log lost lines:** the owner's log stopped at "Joints 310/319", about ten stage lines before the failing import
   (the stages after "joints" all print a title first) – lines were sitting in a buffer when the build ended.
4. The error named no file (`bpy.ops` turned the operator's report into "Error: Import failed: Reader stopped (code
   3221225477)").
5. `_RestrictData`: `compat.register()` read `bpy.data.filepath` while Blender's data is restricted (add-ons are
   switched on at start) – reproduced on the web machine at the first start of the installed app.

**What changed:**
- New `core/proctree.py` `Tree`: the build and every program it starts as one thing – a **job object** of its own on
  Windows (no limits, no kill-on-close: a build keeps running when the app is closed, as before; the reader's own
  helper job nests inside it), a process group elsewhere. `kill()` stops all of it, `alive()` says whether anything of
  it still runs (Linux: zombies do not count).
- `ops_demo.py`: Make it starts the build as a `Tree`; `end_step()` (the modal's timer) stops it after Cancel's 4 s,
  and once the build's Blender has ended – finished, failed or cancelled – stops whatever of its tree is left and
  **waits until nothing of it runs** (at most 60 s, then a console line). `running()` is true until then: Make it is
  refused with "The last demo project is still stopping: Make it again in a moment", Help shows "Stopping the demo
  project …". A second Cancel no longer puts the forced stop off. A persistent timer (`_watch`) does the same when
  Blender dropped the Make it modal (another project opened while the demo is made) and wraps the build up; the next
  Make it wraps up an ended build nobody has reported yet (both found by the independent review).
- `importer/runner.py`: the work folder name gets a random part; a reader that stops says **which file** and what the
  code means: "Reader stopped while reading demo_park.step (crashed: access violation, code 0xC0000005)." (file name
  only, no path).
- `blender/demo.py` `build_main`: stdout / stderr line-buffered, the build's own lines written straight to the log;
  `ops_import.py`: in a background run each import writes "reading <file> (<detail>)" and, on failure, "Import failed:
  …" to the log at once.
- `blender/compat.py`: the format check is skipped while `bpy.data` cannot be read (`data_readable()`); the load that
  follows checks the project. A format that really cannot be read still prints.
- PC check line **`demo.cancel`** (Full; runs on GitHub's Windows machine too): a reader left running by a program
  that ended is counted, stopped and gone; a whole read inside such a job finishes as usual; on Windows the build must
  get its job object. `MIN_LINES_FULL` 168. Function `help.demo` names it.
- Real-app test `ui_test_demo_kits.py`: Make it → Cancel → Make it again with the real buttons, the second time with
  another project opened meanwhile (`MIN_CHECKS["demokits"]` 30).
- User guide (Make it, step 2), CHANGELOG.
- The kit is unchanged (the cause is not in it).

**Tested and measured** (4-core Linux web machine): `tests/test_demo_cancel.py` (18: a tree with a program left
running, kill stops only the tree, a real STEP reader left running by its parent is stopped with its helpers, a read
cancelled half-way then read again with no `.partial` left, two jobs never share a work folder, exit codes in words,
a crashing reader names its file not its folder, Make it waits until nothing runs, Cancel's forced stop, the timer
without the modal, the log keeps every line when the program ends without flushing); `test_demo_project.py`
`test_cancel_at_the_import_then_make_it_again` (twice Cancel → Make it, no reader left); `test_compat_blender.py`
`test_no_format_line_while_blender_data_cannot_be_read`; the PC check line `demo.cancel` (OK, 1.3 s); the real-app
test `demokits`. Independent review (a subagent that did not write it) of the Windows code: ctypes layout, nesting and
handle use found fine; 7 points, of which the modal-dropped case, the wrap-up by the next Make it, the PC-check line's
pipe race, the silent fallback (now a console line + `in_job` checked by the PC check) and the second Cancel were fixed.

**Open points:**
- The crash itself was not reproduced; the fix removes every overlap between a cancelled and a new build that the code
  allowed. The owner's test below is the proof on Windows.
- If a job object cannot be made (a PC that runs the app inside a job that forbids nesting), the old `taskkill /T`
  path is used and the console says so; the PC check line fails on such a PC.
- Linux only, unlikely: a process group number reused within 0.5 s by another program of the same user.

**Owner's test steps** (your PC, after the update):
1. **Help > Make demo project…**, pick **Demo cable-lay vessel (full) (kit 2)**, click **Make it**.
2. When the bottom line shows "Importing" (after the model is written), **Help > Cancel demo project**. The bottom line
   shows "Stopping the demo project …" for a few seconds, then a line "Demo project cancelled: nothing was left
   behind".
3. Right away **Make it** again. It should finish (about as long as a normal Make it) with the window "The demo project
   is ready".
4. Do 1–3 a second time. Then the same twice with **Vessel in a wind park**.
5. If one fails: send the message and the file "Make demo log.txt" from the demo folder – its last lines now say which
   model was being read.
6. At the app's start the two lines "the project's format could not be read: '_RestrictData' …" should no longer be
   in a log.
