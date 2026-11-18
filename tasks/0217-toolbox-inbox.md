# 0217 – Toolbox inbox: a house from House Planner bakes and goes back by itself

**Who:** worker · **Status:** done (0.2.170, 19 Nov 2026). `toolbox-format` tag `v0.1` exists (18 Nov, commit aa75e85,
MIT licence) and took every point of the lead's review below · **Branch:** `task/0217-toolbox-inbox`
**Started by:** lead, 18 Nov 2026, from the toolbox planning chat's brief (step D of the toolbox plan)
**Model:** Opus · effort Medium (Windows file handling: independent review before merging, CLAUDE.md section 6)
**Area:** new Toolbox lane – new `fresing_render/core/toolbox.py`, `fresing_render/blender/toolbox_inbox.py`,
`ops_toolbox.py`, their tests, `tests/data/toolbox/tbf-v0.1/` (copy of the pinned tag); additive: `ops_house.py` /
`house_bake.py` (a target folder and a progress callback, nothing else), `ui_house.py` (the lines below), the
extension's register, `installer/Install-FresingRender.ps1` + `Uninstall-FresingRender.ps1`,
`tools/ci_windows_install.ps1`, `docs/USER-GUIDE.md`, `docs/COMPANY-USE.md` (+ its copy in `fresing_render/licenses/`).

## Goal

A house sent from House Planner shows up in Fresing Render by itself, and the finished bake goes back to House Planner
by itself. The owner presses one button in House Planner, then **Bake now** once in Fresing Render (see the review,
question 1), and waits – no Save, no Open, no Import dialog.

## Background

- The format: `smholte/toolbox-format` **tag `v0.1`** (aa75e85, MIT), read `README.md`, `FORMAT.md`, `CHANGELOG.md`
  (what the review changed). Its reference code for a native tool, `tbf/folder.py` (`claim`, `unfinished`,
  `is_stalled` / `stalled`, `exclusively`), and `tbf/detect.py` may be copied into `core/toolbox.py` – keep the MIT
  notice with them and add the repository to `THIRD-PARTY-NOTICES.md`. `tools/standin.py` and `trial/` show the other
  side. **Pin the tag** (`v0.1`, made after the
  review below) the way the House lane pins `house-scene-format`: a byte copy of the tag's `FORMAT.md`, `types.json`,
  `schemas/`, `tbf/`, `check.py` and `samples/` in `tests/data/toolbox/tbf-v0.1/` and a test that it is exactly the
  tag (`tests/test_house_pinned.py` is the model). Work from the tag's text, not from the draft branch.
- In short: a folder `C:\Users\<name>\Toolbox` (`TOOLBOX_HOME` overrides it); each tool has a manifest
  `tools/<id>/toolbox.json` and an inbox; a hand-over is a *job* = a folder in the receiver's inbox with the files and
  `job.json` (written last); the receiver writes `status.json`; the result goes back as a new job in the sender's
  inbox (FORMAT.md 2, 6, 7, 8).
- Nothing changes in `house-scene-format` (pinned v1.0.1): `.hpscene` / `.hpbake` are the packages of today. File >
  Import > House Planner scene and Bake and export keep working as they are.
- What exists: `blender/house_import.import_scene(scene, path)` (into the scene, collection "FR House"; importing again
  replaces the house), `blender/house_bake.HouseBake(scene, path).steps()` (a generator 0 … 1 with `.text`, driven by
  the modal `fresing.house_bake`; Cancel = `rt["cancel"]`; `longjob.swallow_undo`), `blender/longjob.py`, the STEP
  import (`fresing.import_step`, the reader runs in its own process).
- **Never attach `smholte/house-planner-dev`.** Tests use only the made-up samples of the two format repositories.
  Note: the `.hpscene` / `.hpbake` in the toolbox samples are only good enough to be *recognised*; the round-trip test
  puts `house-scene-format`'s real sample package (already in `tests/data/house/hsf-v1.0.1`) into a made job.

## Lead's review of toolbox format 0.1 (answers for the toolbox planning chat)

The owner takes this section to the toolbox planning chat. Items marked **format change** need a change to FORMAT.md
before `v0.1` is tagged; the rest is how Fresing Render will do it.

1. **(13.1) Start baking by itself, or ask?** **Ask, once per job, with a "Bake now" button** (as proposed) – for three
   reasons that are Blender's, not taste:
   - The house is imported *into the open project*. The owner may be in the middle of a cable-lay project; a house
     must not land in it unasked. So "Bake now" makes **a scene of its own** in the open project ("House – Sample
     house"), bakes there and removes that scene again once the reply is sent – the owner's project is unchanged (the
     bake operator already promises "the project itself does not change"). *Owner chose this (answer A below).*
   - An operator started from a timer gets no undo step; CLAUDE.md section 8 records a crash on Ctrl+Z after a script
     call without one. A real click on "Bake now" starts the import and bake as a button does.
   - A bake takes the PC for minutes (Cycles, GPU). The owner should choose the moment.
   While it waits, the status is `waiting` with the text "Waiting for you in Fresing Render: press Bake now" – House
   Planner can show that. A Preferences switch "Bake houses from House Planner without asking" can come later, once
   the undo point is proven safe – not in this task.
2. **(13.2) A timer every 2 seconds inside Blender?** Yes – a folder listing costs well under a millisecond. **But
   Blender runs timers only between steps:** one Cycles bake call blocks Blender for seconds (0114: ~15 s a moment at
   Normal on the 4-core web machine without a GPU; less on the RTX 3090, more at Fine). During such a step nothing is
   written: no `alive.json`, no `status.json`. With "alive every 10 s, seen within 30 s" House Planner would sometimes
   say "Open Fresing Render" while it bakes. **Format change:** in 6.4 / 7.1 – a sender whose job is `working` says
   "working" (with the last `text`) and not "not open", until that job's `updated` is older than 5 minutes. (The worker
   also measures whether a Python thread can keep `alive.json` fresh during a bake call; if it can, good, but the
   format must not depend on it.)
3. **(13.4) A day before a finished job is deleted?** Fine for Fresing Render. It deletes the job's files (the
   `.hpscene`) as soon as the status is final, keeps `job.json` + `status.json` for the day. It keeps **no copy** of
   the `.hpbake` it sent (the reply job is the result); only when no reply can be sent does the `.hpbake` stay in
   Fresing Render's own place, and the status `text` says where.
4. **Rules Blender (or Windows) cannot follow as written:**
   - a. **Jobs left from an earlier run are never picked up again.** 6.3 handles only jobs *without* `status.json`. A
     job that was `waiting` when Fresing Render closed, or `working` when it crashed, keeps that status for ever.
     **Format change:** "At its start a tool takes up the jobs of its inbox whose status is not final: `waiting` → it
     asks again; `working` → it ends it (`failed`, code `error`, 'Fresing Render was closed while it worked on this')
     or starts it again."
   - b. **Two copies of one tool.** The owner can have two Fresing Render windows open, and the app itself starts
     Blender in the background (render queue, PC check, site kit). Two watchers would take the same job. **Format
     change:** "A tool that can run more than once takes a job by creating `status.json` only if it is not there yet (an
     exclusive create); a copy that loses leaves the job alone." Fresing Render watches only in a copy with a window
     (`bpy.app.background` off) and deletes `alive.json` on closing only if it wrote the newest one.
   - c. **Windows refuses to replace or delete a file another program has open** (House Planner reading
     `status.json` in Chrome while Fresing Render writes it whole; deleting a job folder House Planner still reads).
     **Format change (one sentence in 7.1 and 7.4):** "A write by rename or a delete that fails is tried again at the
     next look; a reader that finds a file missing or half there tries again." Fresing Render never crashes on it.
   - d. **Cleaning up must never follow a link** out of the Toolbox folder (a job folder that is a junction): delete
     only real folders and files inside the inbox. Worth one line in section 10.
   - e. Small: the sample manifest's `start.program` is `blender.exe` (a console window on Windows). Fresing Render
     writes the target its Desktop shortcut uses (`Fresing Render.exe`, else `blender-launcher.exe`, tasks 0177/0212).
5. **(13.5) Licence.** Fresing Render (GPL-3.0-or-later) will copy `tbf/detect.py`, as the brief allows. Please give
   the repository a licence that allows that (MIT or Apache-2.0 for the code) **before** the tag – `house-scene-format`
   still has none (0205 flagged it).

**Owner's answer (18 Nov 2026, 20:19): A.** When a house arrives and the owner presses Bake now while another project
is open, the house goes into **a scene of its own in that project** and that scene is removed again after the bake is
sent back – the owner's project is unchanged. (Not chosen: B, save and open a new, empty project for the house.)

## The work

1. **Manifest.** The installer, and the app at every start, write `Toolbox/tools/nl.fresing.render/toolbox.json` (the
   sample's actions `import-step` and `bake-house`, `app_version` = the app's version, `start` = the target of the
   Desktop shortcut), and make the Toolbox folder with its `toolbox-folder.json` when it is missing. The uninstaller
   removes `tools/nl.fresing.render/` (only that folder). `TOOLBOX_HOME` overrides the folder (tests). A PC where the
   folder cannot be made (no home folder, no rights): the app works as today, one line in the House panel.
2. **`core/toolbox.py`, pure Python, no Blender:** where the folder is; strict JSON read/write (FORMAT.md 3.4 – no
   duplicate keys, no NaN, no control characters, ≤ 1 MiB, unknown fields refused); the name rules (3.1–3.3); the file
   type (5.3 – copy `tbf/detect.py` of the pinned tag, with its origin in a comment and in THIRD-PARTY-NOTICES only if
   the licence asks); reading and checking a job (6.3); writing `status.json` whole (temp name + rename, retried at the
   next look when Windows refuses); claiming a job (exclusive create, review 4b); writing a reply job (files first,
   `job.json` last, 6.2 step 1 checks the receiver's manifest first); cleaning up (7.4, review 3, never through a link);
   jobs left from an earlier run (review 4a). All of it tested with `TOOLBOX_HOME` in a temp folder.
3. **Watching the inbox** (`blender/toolbox_inbox.py`): `bpy.app.timers` (persistent across file loads), every 2 s;
   `alive.json` at least every 10 s when Blender is free, removed on exit (`atexit` + the app's quit path); only in a
   copy with a window. A bad job never raises out of the timer.
4. **`bake-house`:** check the job (6.3) → status `waiting` + the prompt (below) → on **Bake now**: the scene of its own
   (owner chose A), `house_import.import_scene`, then the existing bake (`HouseBake` driven as `fresing.house_bake`
   drives it, or that operator with a target path and a progress hook – add, do not copy) writing the `.hpbake` to a
   temp folder → reply job to the sender (`action` = the job's `return`, `reply_to`, `title` copied) → status `done`
   with `reply` (reply first, status second, 7.2) → the house scene removed. Progress into `status.json` (`fraction`,
   `text` from `HouseBake.text`) at most once a second. `cancel.json` (or the existing Cancel in the panel) → the bake
   stops as Cancel does today, status `cancelled`, nothing sent. Another long job running (web export, clash check,
   a re-bake, the queue busy – `longjob` / `queue.busy_job`) → stays `waiting` with the text "Fresing Render is busy
   (<what>); the house waits".
5. **`import-step`:** check the job, status `waiting` + the prompt "Import now"; on the click the existing STEP import
   of the file (the same as File > Import), status `done` when the import finished, `failed` with the import's message
   otherwise. (Nothing sends this yet; the later router will.)
6. **A bad job never crashes the app and never opens a file:** wrong type (by content), wrong size, a name with a path
   or a reserved name, a link instead of a file, an unknown action, another version (the clear sentence of 3.5:
   "This job was written by a newer tool (toolbox format 0.2). Update Fresing Render to read it.") – status `failed`
   with the right `code` (`bad-job`, `unknown-action`, `wrong-type`), one line in the panel.
7. **In the app:** in 5 Scene & Render > House from House Planner (and as a popup once per new job if a popup from the
   timer works reliably – else only the panel and Blender's status bar report): one line what arrived and from whom
   ("From House Planner: Sample house – version 3") with **Bake now** (blue, `primary()` of that panel) and **Not
   now** (status `cancelled`, "You said not now in Fresing Render"); while baking the existing progress + Cancel; after
   it "Sent back to House Planner". When nothing is waiting the panel shows nothing new. Tooltips on both buttons.
8. **Project rules:** function-list entry + guide anchor (`since=`), guide section "A house from House Planner by
   itself", a test-tour stop (a made job in a temp Toolbox folder, Bake now, the reply job there), a PC-check line
   `house.toolbox` (Full: a made job through to `done` with a reply job at 4 samples, with `TOOLBOX_HOME` in the check's
   folder – never the owner's real Toolbox folder), `docs/COMPANY-USE.md` (a new folder the app writes in the user's
   home, nothing over the network).

## Done when

- [ ] The pinned copy of `toolbox-format` `v0.1` in `tests/data/toolbox/tbf-v0.1/` and its test; the app's tests run
      against its `samples/Toolbox`
- [ ] Tests: the bake job runs through (import, bake at 4 samples, reply job, status `done`, house scene gone, the
      project unchanged); a cancelled job (`cancel.json` while `working`, and while `waiting`); "Not now"; each kind of
      bad job refused with the right `code`; a job of version 0.2 refused with the clear message; a job left
      `waiting` / `working` from an earlier run; two watchers, one job (only one takes it); a busy app keeps the job
      `waiting`; no House Planner manifest → the `.hpbake` kept and the status says where
- [ ] Everything the app writes into the folder passes `python3 check.py <Toolbox folder>` of the pinned tag (in a test)
- [ ] Windows (GitHub's Windows job): the folder found under `%USERPROFILE%`, a user folder with a space and an accent,
      a file still short is not read early, a status write while another process holds `status.json` open is retried,
      not crashed; install writes the manifest, update keeps it right, uninstall removes only `tools/nl.fresing.render/`
- [ ] Independent review of the Windows parts and an independent tester who breaks the inbox code (CLAUDE.md
      section 2, subagents)
- [ ] Guide, tooltips, tour stop, PC-check line, function entry (`since=`), COMPANY-USE
- [ ] Report: what was measured (how long Blender is silent during one bake call, on which machine), the owner's
      steps below checked against the real app
- [ ] **Steps for the owner** on his PC, click by click, in the report – with House Planner's side only once its own
      task is done; until then with a job made by `python3 tools/toolbox_send.py <file.hpscene>` (a small helper that
      writes a job the way House Planner will; tools/, not shipped)

## Not in this task

Routes and the drop popup, starting Fresing Render from another app, any change to `house-scene-format`, anything in
House Planner (its lead has its own brief), a "bake without asking" switch, other actions (mesh import, renders).
Never attach `house-planner-dev`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 18–19 Nov 2026. Released as **0.2.170**.

**What changed:**
- `core/toolbox.py` (no Blender): the folder (`TOOLBOX_HOME`, else `%USERPROFILE%\Toolbox`), the manifest, strict
  reading of every JSON file field by field as the tag's schemas say (no jsonschema in Blender), checking a job (6.3),
  bad jobs refused with `bad-job` / `unknown-action` / `wrong-type`, the clear sentence for version 0.2, claiming by
  exclusive create, status writes Windows refuses kept and written at the next look, progress at most once a second,
  the reply job (reply first, status second), the result kept in `Documents\Fresing Render\House bakes` when House
  Planner cannot take it, jobs left by an earlier run, two copies (a copy adopts left jobs only while no other copy's
  `alive.json` is fresh), cleaning up never through a link or junction, install / uninstall.
- `core/tbf/`: the tag's `names.py`, `detect.py`, `types.json` byte for byte (one marked line), MIT notice.
- `blender/toolbox_inbox.py` + `ops_toolbox.py`: the timer (2 s, 1 s while a job runs; only with a window), Bake now
  = a scene of its own shown in the window, `house_import.import_scene` into a temp folder, the existing
  `fresing.house_bake` modal (its progress + Cancel); at the end the reply, the owner's scene back, the house scene
  removed, the world rebuilt from the owner's settings (the app's world and floor are shared by name between scenes:
  the first run showed the house's sky leaking into the owner's scene – fixed and tested). Not now, Cancel,
  `cancel.json`, busy text, Import now (`import-step`, file copied to `Documents\Fresing Render\From the Toolbox`).
- Additive in shared files: `ops_house` (`ENDED` hook, hidden `samples` / `photo_samples` / `quick`, `run_at_once`),
  `house_import.import_scene(folder=)` and `remove()` now only this scene's house, `ui_house` lines + poll,
  `ui_top` What's next card shows the job when section 5 is not open (with no model open it does not show at all –
  found from the real-app screenshot), `lock.ALLOWED` + 2, `__init__` register.
- Installer writes the manifest (start = `winexe.app_exe`), the app writes it at every start; uninstaller removes only
  `tools\nl.fresing.render` (links inside removed as links first, never followed).
- `tools/toolbox_send.py` (plays House Planner), `tools/ci_toolbox_windows.py` + `ci_windows_install.ps1`
  (USERPROFILE with a space and an accent, short file, status.json held open, delete refused, junctions, uninstall),
  real-app test `ui_test_toolbox.py` (group tour, 19 checks; the real-app runs now use a `TOOLBOX_HOME` of their own),
  tour stop `house_toolbox`, PC-check line `house.toolbox`, function `house.toolbox`, guide section `house-toolbox`,
  COMPANY-USE, THIRD-PARTY-NOTICES, pin `tests/data/toolbox/tbf-v0.1/`.

**Tested and measured** (4-core web machine, no GPU):
- `test_toolbox.py` 32, `test_toolbox_independent.py` 96 (independent tester), `test_toolbox_pinned.py` 2,
  `test_toolbox_blender.py` 8 (round trip with the real sample house at 4 samples: done, reply passes
  `structure_problems`, house scene gone, owner's project – objects, world nodes, settings – identical; cancel.json while
  baking; a broken house; busy; Not now), everything written passes the pinned `check.py` (see open point 1).
- Real app (`ui_test_toolbox.py`, window path): 19/19 – job waiting 2.1 s after it was written, Bake now switches
  the window, progress reaches the status, sent back, scene back, Cancel by cancel.json. Tour stop and PC-check line
  pass in Blender as a module (bake + send back 34 s).
- **Blender's silence during a bake:** the sample house, one moment, the longest single step was 2.1 s at 4 samples
  and 3.7 s at the recipe's 16 samples (whole moment 26–30 s). A Python thread ran every 0.2 s throughout (Cycles lets
  go of Python while it bakes), so a thread could keep `alive.json` fresh; not used – the format does not depend on
  it (6.4).
- Subagents: an independent tester (core; found 9 faults, all fixed: a second window failing the first window's job,
  a name with a lone surrogate stopping the whole look, a refused exclusive create stopping the look, install/uninstall
  through a `tools` link, a failed keep leaving a job working, case-duplicate reply files, alive.json bytes alike, a
  lowercased app name, `size: 5.0`) and an independent Windows reviewer (fixed: Documents via the shell for OneDrive,
  a busy file at Bake now no longer fails the job, OneDrive reparse points no longer count as links, uninstall with a
  junction inside, empty USERPROFILE, installer's start program, CI junction inside a job, cleanup in `finally`).
- GitHub runs: see below.

**Open points / follow-up tasks:**
1. **For the toolbox-format lead:** the v0.1 checker reports "the file X is missing" for a final job whose files were
   deleted, although FORMAT.md 7.4 allows deleting them at once (the app does, review 3; the tests filter exactly that
   message). Also from the Windows review: `tbf/names.py` misses `CONIN$`, `CONOUT$`, `CLOCK$` and the superscript
   `COM¹–³`/`LPT¹–³` reserved names, and does not strip trailing spaces before comparing.
2. The guide picture `panel_5_house.png` was not redone (the new lines only show while a job waits).
3. Bake now is refused in the Client view (the house bake is not on its allow-list); Not now works there.
4. Two windows: a window started while another is open leaves the other's jobs alone; when both are open and the
   first closes, its waiting jobs are taken up by the other only after its `alive.json` is 35 s old.
5. **Steps for the owner** (until House Planner sends houses itself):
   1. Update Fresing Render (Update now) and start it once – it makes `C:\Users\<you>\Toolbox`.
   2. In a Command Prompt in the repository folder: `python tools\toolbox_send.py "<a .hpscene file>"`
      (or use the test tour's stop "A house arrives by itself": Go makes such a job for you).
   3. In Fresing Render, within a few seconds: the card at the top of the Fresing tab (or 5 Scene & Render > House
      from House Planner) shows "From House Planner: …" with **Bake now** and **Not now**.
   4. Click **Bake now**: the window shows "House – …" with the progress bar; when done it shows your project again and
      says **Sent back to House Planner**. The package is in `C:\Users\<you>\Toolbox\tools\nl.fresing.house-planner\inbox\`.
   5. `python tools\toolbox_send.py --status` lists what happened to each job.
