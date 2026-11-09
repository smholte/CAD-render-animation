# 0045 – Bug hunt across the whole app (findings only, no code changes)

**Who:** worker · **Status:** done (9 Nov 2026) · **Branch:** none – the report goes to `main` (task files only)
**Started by:** lead chat, 8 Nov 2026 · **Lane:** none – reads everything, **changes no app code**, so it runs next to
every lane
**Model:** Opus · effort High · **Environment:** "CAD-render-animation" (real Blender at start, CLAUDE.md section 4)

## Goal

A ranked list of real problems in Fresing Render – crashes, lost work, old projects that no longer open, wrong
output, slow spots – each with proof and a suggested fix, so the lead can turn them into tasks **before** the owner
hits them on his PC (like the milling crash at the end of a 2-hour 4K render, 0037/0038).

## Background

- 0.2.34 on `main`, ~47,000 lines of Python in `fresing_render/`, 1,360+ tests, GitHub runs everything at every push.
  The tests prove what each task thought of; this task looks for what nobody thought of.
- Crashes found so far all came from Blender itself misbehaving, not from Python errors: arrays of another length in
  ID properties (0038), undo after a scripted Build (CLAUDE.md section 8), drivers read one update late (0012), stale
  references to collection items (0034). Section 8 of CLAUDE.md lists them all: **read it first**, then look for
  other places in the code where the same kind of mistake is still possible.
- The owner works with big models (2,800 parts), long queued 4K renders (500 frames, 2+ hours), projects that he
  keeps for weeks and opens in newer versions, and a shared project folder (`project_lock.py`).
- Running at the same time: **0040** tool library (`core/gcode.py`, `blender/gcode.py`, `ui_gcode.py`,
  `machining.py`, `chips.py`), **0043** surroundings re-lay + MP4 encode (`blender/surroundings.py`, `queue.py`
  encode, `video.py`), **0044** guide pictures (`docs/`). Those files will change: look at them lightly, and before
  writing the report check each finding in them against the newest `main` (`git pull`).

## What to do

1. **Read** the code area by area: importer + model update (`importer/`, `reimport.py`, `build.py`), project
   load/save and upgrades of old data (`handlers.py` load_post, every `upgrade_*`), joints / cylinders / mechanisms /
   way covers, animation bake and render queue (`animation.py`, `queue.py`, `queue_runner.py`), milling / chips /
   air, video finishing and labels, updates and the update helper, PC check, the UI's redraw code (`ui*.py`,
   `UIList.filter_items`, handlers that run every frame or every redraw).
   Helper agents may read areas in parallel (at most 4, one area each, findings only); the main session checks
   every finding itself before it goes in the report.
2. **Look for**, in this order of importance:
   - **Crashes and hangs** of Blender (memory, handlers, undo, timers, threads, files closed while a job runs).
   - **Lost work:** an action that silently drops joints, groups, looks, decals, animation steps or queue jobs;
     model update or save/reopen that loses something; the project lock left behind.
   - **Old projects:** make a project with an older version and open it in 0.2.34 – at least 0.2.20 and 0.2.30, with
     joints, a group look, a decal, an animation and a queued job. Old versions: the release zips on GitHub
     (v0.2.16 and newer), or check out the tag and build it (`tools/build_release.py`).
   - **Wrong output:** a render or video that differs from what the view shows (hidden parts, camera, finishing).
   - **Slow:** anything that grows faster than the model (a loop over all parts inside a loop over all parts, work
     at every redraw). Measure on the generated Heavy machine (`pccheck/heavy_scene.py`, ~3,000 parts).
   - **Windows-only code** (paths with spaces/accents, long paths, subprocess flags, the update helper): review by
     reading; it cannot run here.
3. **Prove** each finding: a short script or click test that shows it (keep these in a scratch folder **outside**
   the repository; put the few lines needed to repeat it in the report). A finding that cannot be shown is listed as
   *suspected*, never as confirmed.
4. **Report** in this file (below), one table row per finding, worst first:
   `# · severity (crash / lost work / old project / wrong output / slow / small) · where (file:function) · what
   happens and when · proof (confirmed + how / suspected) · suggested fix in one sentence · lane · model · effort`.
   Then a short list of areas that looked sound. Group small findings (texts, tooltips) in one row.
5. Commit only this file and `TASKS.md` (status running → done) to `main`: task-file-only pushes start no test run.

## Done when

- [x] Every area in step 1 read; old projects from at least two versions opened; the Heavy machine measured.
- [x] Findings table filled in, worst first, each one confirmed with proof or marked suspected; areas that looked
      sound listed.
- [x] No change to app code, tests or tools in the repository (the lead turns findings into tasks).
- [x] `TASKS.md`: 0045 done; findings named under "Problems found, waiting for a task" as one line pointing here.

## Not in this task

Fixing anything – even one-line fixes go into the report as a suggested fix. New features, look of the UI, render
quality. The owner's own STEP files and projects (not attached; the repository is public – generic test models only).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 9 Nov 2026, on `main` at 0.2.37 (`80fddd3`; checked again against `a5c3952`, which
changes only `site/`). Four helper agents read one area each (import/update/load, motion/queue/video,
milling/decals/scene, updates/Windows/UI). The main session ran every proof script again itself; each row marked
*confirmed* reproduced there. No app code, tests or tools were changed. Proof scripts were kept outside the
repository; each row gives the few lines needed to repeat it.

**Findings** (worst first):

| # | Severity | Where | What happens and when | Proof | Suggested fix | Lane | Model · effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | lost work | `blender/reimport.py:update_model` + `joints.py:dissolve_all.belongs` / `rebuild_from_specs` | **Model update deletes a joint whose parts belong to two models.** Example: a crane joint that "sits on" a part of the ship model. Updating the ship removes the joint, with the note "its moving parts are no longer in the model", although they are. The other way round, the joint loses its base ("the part it sat on is gone"). Cylinders and mechanisms use the same pattern; not tested. | confirmed. Import `test_crane_a` and `test_machine`. Make `joints.create(ROTATE, [BOOM.ASM of the crane], base=<a part of the machine>)`. Update the machine with `test_machine.step` (`update_root=` the machine root). Result: `joints == []`, BOOM.ASM still there. | Look the joint's objects up over all models (by object, not only `by_uid_new` of the updated model), and only dissolve joints whose moving parts are in the updated model. | Motion | Opus · Medium |
| 2 | lost work | `blender/reimport.py:update_model` (labels are never remapped) | **Model update cuts every label off its part.** `FRCallout.part` points at the old object, which is deleted: `part` becomes None, `callouts.usable()` False, and the labels silently drop out of renders. No note in the report. The camera's sharp spot behaves the same: the `CHILD_OF` target of the focus marker becomes None, the label still says the part. | confirmed. Crane A, `callouts.add(scene, BOOM, BOOM.location, "Boom")`, update to `test_crane_b` → `c.part is None`, `report_notes == []`. Sharp spot: `cameras.set_focus` on BOOM, update → constraint target None. | In step 6 of `update_model`, re-point `c.part` and the focus marker's constraint target through the uid mapping, and add a note for labels whose part is gone. | Scene & Render (+ `reimport.py`, additive) | Sonnet · Medium |
| 3 | lost work | `blender/machining.py:_take_workpiece` (l. 205–211) + `decals.py:rebuild` / `part_mesh` | **A decal on the milling workpiece is emptied by any edit while milling is on, and stays empty.** `stock.copy()` copies the mesh's decal list, so the decal exists twice (count shows 2). The cut mesh has no `fr_face_starts`, so a change of width, text or fit rebuilds the decal with **0 triangles**. Stop milling then drops the edit, and the decal is still empty. Same for "this copy only" decals. | confirmed. Mill scene (`test_mill`), a TEXT decal on the stock, set up milling, change the decal width → decal mesh 0 triangles. Stop milling → width back to the old value, decal mesh still 0 triangles. | Take decal geometry and settings from `settings.stock_mesh` when the part is the milled workpiece, and clear `fresing_decals` on the cut copy. | Machining (+ Looks for decals) | Opus · Medium |
| 4 | lost work | `blender/updates.py:preflight` (l. 188–212), `finish_update` | **Update now silently saves over a shared project that a colleague has open.** Panel 1 shows "In use by …", and its own advice is "Save As". `preflight` never asks `project_lock`. | confirmed. Write a fresh `.blend.inuse` for another user/PC, open the project → `project_lock.warning()` = "colleague on OTHER-PC since …", and `preflight()` returns `''`. | When `project_lock.warning()` is not empty, refuse with "someone else has this project open: Save As first". | Quality & delivery (updates) | Sonnet · Medium |
| 5 | lost work | `blender/props.py:_group_renamed` (l. 105) | **Paint schemes and saved scenes' own looks do not follow a group rename.** Applying the scheme (or switching to the scene) skips the renamed group, and its colour stays as it is. | confirmed. Save a scheme with group A = #FF0000, rename A, set it to #00FF00, apply the scheme → still #00FF00. | In `_group_renamed`, also rename `look.group` in `s.schemes[*].looks` and in every `shot.own_scheme.looks`. | Looks | Sonnet · Medium |
| 6 | lost work (suspected) | `blender/reimport.py:update_model` | **Model update is not all-or-nothing.** Joints, cylinders and mechanisms are dissolved before `build.build(cache_dir)`. Any error after that (a damaged `meshes.npz`, MemoryError on a big model) leaves the specs lost, the new model half built and the old model still there; the modal `_finish` does not catch it. | suspected, by reading. | Build the new model first and dissolve after, or wrap the update and rebuild from the specs on the old root when it fails. | Motion (+ Looks, shared file) | Opus · Medium |
| 7 | wrong output | `ops_motion.py:FRESING_OT_queue_add` (STILL, ~l. 1200) + `states.save_shot` (l. 284–307) | **"Add image" while scrubbed in a built animation queues a different picture.** The saved scene takes the joint pose of that frame, but visibility from the `fr_hidden` flags (not the keyed hiding) and the camera from `anim_restore_camera`. The runner's `apply_shot` then clears the keys. Render image (not queued) is right. | confirmed. Crane, animation with a Hide COVER step and an Orbit camera, built, frame 40. View: COVER hidden, camera "Animation camera". Queue renders COVER visible from "Iso front-right". | When animation keys exist, capture visibility and camera as evaluated at the current frame (or warn and refuse). | Motion | Sonnet · Medium |
| 8 | wrong output | `queue.py:render_animation` (l. 493, skips existing frames) + `encode_mp4` (l. 587, takes every `frame_*.png`) | **A stopped or failed animation job reuses old frames, even past the new end.** Stop queue → edit or shorten the animation → Start queue: the job keeps its `job_id` and folder, frames from before the edit stay, and extra frames go into the MP4. | confirmed. A 3-frame animation, folder holds 6 frames from an earlier run → "frames in the video: 6 (animation has 3)". | Encode only `frame_0001 … frame_<end>`, and store a fingerprint of the animation and settings in the folder; delete the frames when it changed. | Motion (queue) | Sonnet · Medium |
| 9 | wrong output | `queue.py:current()` (l. 81), `sync()` (l. 314–331), persistent `_poll` timer | **A running queue leaks into any project opened afterwards.** Start an overnight queue in project A, File > Open B: B takes A's `queue_dir`/`queue_pid` and A's jobs, cannot start its own queue ("already running"), and saving B keeps the foreign jobs. | confirmed. Project A, queue one still, start; open project B → after one poll B lists A's job (RUNNING), `queue_dir` = A's folder; B's Start → "The queue is already running". | Key the runtime state by the project file (queue.json "project"); `sync` only adopts jobs when `scene.fresing.queue_dir == qdir`. | Motion (queue) | Opus · Medium |
| 10 | wrong output | `animation.py:CamState.of` (l. 288) | **Videos use a stale sharp distance.** The animation camera copies `dof.focus_distance` without a focus object. When the sharp-spot part has moved (joint, pose, start scene), the view and stills are sharp at the spot, but the video is not. | confirmed. Sharp spot on the boom tip, boom raised 60° → true distance 2.628 m, video camera at frame 1 uses 1.55 m. | In `bake`, call `cameras.update_blur` on the start camera (and Move-to cameras) after `apply_shot` and before `CamState.of`. | Scene & Render | Sonnet · Medium |
| 11 | wrong output | `importer/step_reader.py:add_node` (uid = path of names) + `states.by_uid` (`setdefault`) | **The same STEP imported twice (two cranes on a quay) gives both copies the same part IDs.** Visibility sets, pose free moves and Show/Hide steps of the second copy act on the first. Updating one copy remaps the other's entries too. | confirmed. Import `test_crane_a` twice → both roots `TEST.CRANE#1`, both covers `TEST.CRANE#1/COVER#1`. Hide the second cover, save and apply a visibility set → first cover hidden, second shown. | Make `by_uid` per model root (or put a per-import token in the uid scope); old projects keep their uids. | Looks (importer) | Opus · High |
| 12 | small (updates blocked) | `blender/updates.py:read_status` (l. 427–438) + `update_helper.py:mark_busy` / `pid_alive` | **A helper killed mid-install (power cut, logoff, virus scanner) can block Update now for good.** `installing.json` stays. At every start, if any process has that PID (Windows reuses PIDs; "access denied" counts as alive), the app says "being installed right now", never reads the real status file, and `notice_kind()` stays "status", so Update now never shows. Nothing removes the file. | confirmed (Linux, stale file with PID 1) → notice "status", busy file still there, real status unread, Update now hidden with an update available. Windows PID reuse: by reading. | Write the helper's start time into `installing.json`; ignore and delete it when older than wait + install time × 4, or when the PID is not `python.exe`. | Quality & delivery (Windows code: independent review) | Opus · Medium |
| 13 | crash (suspected) | `blender/machining.py:_on_frame` during Render image (`render.render("INVOKE_DEFAULT")`) and Blender's own Ctrl+F12 | **The milling frame handler runs on the render thread.** Normally it returns at once (frame already shown). If the timeline cache was cleared without the motion fingerprint changing (shortly after a change, before the 0.3 s timer), it writes the cut and chip meshes from the render thread while the UI draws them. | suspected. Off-main-thread confirmed in real Blender under xvfb: a `frame_change_post` probe prints `Dummy-1 NOT MAIN`. No crash reproduced. | Return early in `_on_frame` when not on the main thread, or set `scene.render.use_lock_interface = True` for UI renders. | Machining | Opus · Medium |
| 14 | crash / broken app (suspected) | `update_helper.py:_install_with_retries` (l. 315–329), `run` (l. 289–312) | **A failed swap leaves no extension and no backup.** Blender's own installer removes the old folder before renaming the new one in ("failure here causes the extension to be uninstalled"). If the rename fails 4 times (a virus scanner holding the new folder), the helper still restarts the app. It then opens as plain Blender: no Fresing tab, no message, no Update now; only Install.bat repairs it. | suspected, by reading (Windows only). | Copy `ext_dir` to a backup in `fresing_update/` before installing, and restore it when the version check finds the folder missing. | Quality & delivery (independent review) | Opus · High |
| 15 | slow | `blender/chips.py:_node_group` (l. 428) | **Chips rebuild the whole dependency graph on every frame.** `info.inputs["Collection"].default_value = shapes` is assigned on every `show()` (twice per frame) even when unchanged; each assignment rebuilds all relations, and every object is re-synced. | confirmed (4-core web session, `test_mill` + empties to 3,000 objects): frame change 168 ms with chips, 40 ms milling only, 10 ms milling off. The assignment alone then `view_layer.update()` takes 132–148 ms and lists 525 of 525 objects as updated (a normal mesh update: 2). | Assign only when `default_value is not shapes`. | Machining | Sonnet · Medium |
| 16 | wrong output (panel) | `blender/gcode.py:info` / `_INFO` (l. 58, 596), keyed by `b.as_pointer()` | **G-code step summaries are cached by memory address.** After removing or moving a step (`ops_motion.py` l. 1003 / 1027), the remaining step shows another step's lines, moves and video time; the cache is never cleared on file load either. | confirmed. Two Run G-code steps (5 and 203 lines); remove step 1 → the remaining step shows `lines 5, video 9.7 s`. | Key the cache by program signature + step settings, and clear it on load and on step remove/move. | Machining | Sonnet · Medium |
| 17 | small (queue) | `ops_motion.py:FRESING_OT_queue_remove`, l. 1195 "Every saved scene", `queue.run_job`, `queue.sync`, `props.py` l. 247 | Five small queue faults. **(a)** Remove a waiting job while the queue runs: it is still rendered and comes back (confirmed: both jobs DONE). **(b)** "Every saved scene" also queues the hidden "Queue …" scenes from earlier Add image clicks (confirmed: jobs `['Side', 'Queue Iso front-right']`, user sees only 'Side'). **(c)** Renaming an animation relabels its time-test jobs and drops "(with watermark)" (by reading). **(d)** A queued still whose saved scene was deleted renders whatever the copy shows and reports DONE (by reading). **(e)** A runner that dies before writing status.json leaves its jobs "Waiting" with no error (by reading). | see each | (a) refuse remove while running, or a per-job skip file; (b) skip `fr_queue_only` shots; (c) keep the suffix; (d) fail the job; (e) fail WAITING jobs when the runner is gone. | Motion (queue) | Sonnet · Medium |
| 18 | small (suspected) | `queue.start` (copy saved with `relative_remap`) | **Paths typed as `//…` break in the queue's copy.** Affects 360° photo, logo, font, music, picture cards, G-code file and tool table: the copy lives in `<renders>/_queue/<time>/`, and these string settings are not remapped. The photo silently becomes the studio light; logo and music disappear. The file browsers do not make `//` paths (the settings warn "does not support blend relative"), so only typed or code-made paths. | mechanism confirmed: logo and photo found in the project, not in the queue's copy. Not shown with a normal click. | Make those settings absolute in `start()` before saving the copy. | Motion (queue) | Sonnet · Medium |
| 19 | small | several | Seven small faults. **(a)** Renaming a group to an existing group's name gives two rows with that name; one look wins (`props.py`, confirmed). **(b)** Same user, same PC, same project in two windows: no "in use" warning (`project_lock._is_me` ignores the pid; by reading). **(c)** The update helper waits only for the app's own PID, not for a queue or PC-check Blender of the same install (`update_helper.run` l. 275; by reading; Install.bat does check). **(d)** `pccheck/ops.py:ensure_shortcuts` decodes PowerShell output as UTF-8 without `errors="replace"`: a console-code-page accented path ends the thread with a traceback (console only; by reading). **(e)** `handlers._on_load` runs every upgrade step for every scene inside one `try … except: pass`: one failing step silently skips the rest (by reading). **(f)** Old import caches of an older `CACHE_VERSION` are never deleted (disk). **(g)** The Subassembly pick mode makes a `logic.Tree` per click: 9.4 ms at 3,000 parts, fine. | see each | (a) merge or refuse; (b) compare the pid too; (c) wait for every `blender.exe` under the install folder; (d) `errors="replace"`; (e) one try per scene and step, with a printed reason; (f) prune old cache versions. | various (Looks, Quality & delivery) | Sonnet · Medium |
| 20 | slow (small) | `joints.create` → `cad_pose` + `_update`; `callouts.model_outline`; `machining.workpiece` / `gcode.copies` | Measured on the generated Heavy machine (2,992 parts), none urgent. **(a)** Making a joint takes 0.6–0.8 s: three full view-layer updates of 0.24 s each. **(b)** The labels pass reads every part's box on every frame: `model_outline` 50 ms per frame, about 25 s extra for a 500-frame video with labels. **(c)** The milling frame code checks `name in scene.objects` about 13 times and walks `bpy.data.objects` 3 times per frame: 3–5 ms per frame. | confirmed (measured, cProfile) | (a) one update inside `cad_pose`; (b) one `foreach_get` of the parts' boxes per animation, matrices per frame; (c) cache per frame. | Motion / Scene & Render / Machining | Sonnet · Medium |

**Areas that looked sound:**
- **Old projects:** made with 0.2.20, 0.2.24 and 0.2.30, opened in 0.2.37 with nothing lost (details below).
- **Project lock:** Save As releases the old lock, opening another file or File > New releases it, a crash's lock goes stale after 15 min,
  and background Blender takes no lock.
- **Import:**
  - cancel kills the helper processes (Windows job object, Linux PDEATHSIG);
  - stderr is read in its own thread;
  - finished caches move into place atomically;
  - `CACHE_VERSION` is part of the cache key.
- **Memory:** milling + chips over 3 × 339 frames kept 19 meshes and 29 objects at about 430 MB. 240 Cycles frames with persistent data grew by
  3 MB and left no leaked datablocks.
- **Array ID properties:** every one in milling, chips, air and G-code goes through `store_array`; elsewhere `tolist()`/JSON.
- **Handlers:** none keeps bpy references across frames or undo, all are removed on unregister, and timers stop by themselves or on purpose
  (lock heartbeat, queue poll).
- **Joints:** remove and rename are followed by steps, couplings, cylinders, mechanisms, way covers, poses and scenes.
- **Bake:** restores pose, visibility and camera; Duplicate step tested with 39 copies.
- **Runner:** reopens the project per job; stop and kill work.
- **Labels on 16-bit stills:** keep their colours.
- **UI redraw:** every panel together 7.5–12.7 ms per redraw on 2,992 parts; the tree list's `filter_items` 0.4–0.7 ms.
- **Windows code by reading:**
  - CREATE_NO_WINDOW on every child process (import, queue, helper, self-test, taskkill);
  - the helper runs `-X utf8` and detaches;
  - downloads use a `.part` file with size and SHA-256 checks;
  - the Desktop path comes from the known-folder API (works with OneDrive);
  - paths stay ≤ ~195 characters;
  - `.ps1`/`.bat` are ASCII with CRLF.

**Tested and measured** (4-core Claude Code web session, no graphics card):
- **Old projects:** one project each with **0.2.20, 0.2.24 and 0.2.30** (tags checked out, extension run as the bpy module), on `test_crane_a`:
  - a joint on the boom pin, a group look (stainless, RAL 5010), a decal (0.2.24 and 0.2.30; 0.2.20 has no decals);
  - a pose, a visibility set made the app's way (`logic.set_hidden`), a saved scene using both;
  - an animation, two queued jobs (animation + still).
- **Opened in 0.2.37:** parts, groups and looks, joints, poses, scenes, animation and queue all the same, and the decal is still on its part. The boom
  tip at 30° lands within 0.1 mm of the old version's spot. The saved scene hides the pin. Build animation works ("2.0 s, 51 frames").
  Model update to `test_crane_b` gives "11 kept, 1 new, 1 missing" and keeps the joint. Save and reopen keep everything.
- **Old project, real queue:** the 0.2.20 project's two queued jobs were run in real Blender 5.2.3 (extension + app template installed in a
  fresh settings folder, `queue.start`); result below.
- **Heavy machine** (`pccheck/heavy_scene.py`, 2,992 placed / 600 unique parts, 3,050 objects, bpy module):

  | Action | Time |
  | --- | --- |
  | Import, draft | 15.7 s |
  | Tree walk | 0.009 s |
  | Sort into groups | 0.04 s |
  | Change a group look | < 0.01 s |
  | Hide or show a module | 0.05 s |
  | Hide 300 parts | 0.05 s |
  | 10 joints | 5.9 s (row 20a) |
  | Build animation, 10 steps | 0.67 s |
  | Frame change | 27 ms |
  | Save a scene / apply it | 0.03 s / 0.79 s |
  | Model update, same file (2,992 kept, 10 joints kept) | 17.3 s |
  | Save | 0.2 s |
  | Open | 0.7 s |

  UI redraw and chips per frame: rows 15, 19g, 20 and "looked sound".

**Open points:**
- **Not covered:** undo cases (they need a real UI session); Windows-only rows 12, 14 and 19c–d were reviewed by reading only.
- **Rows 1 and 2:** cylinders, mechanisms, way covers and decals across two models were not tested; probably the same pattern as row 1.
- **Next step:** the lead turns rows 1–20 into tasks. Rows 3, 13, 15 and 16 are in the files of the Machining lane (0049 running); rows 7–9 and
  17–18 are in the queue.
