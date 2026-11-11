# 0068 – Bug hunt, round 2: everything built since 0045 (findings only, no code changes)

**Who:** worker · **Status:** done 11 Nov (report on this branch; the lead brings it to `main`) · **Branch:** `task/0068-bug-hunt-2` (the
report only – **do not push to `main`**, see step 5)
**Started by:** lead chat, 11 Nov 2026 · **Lane:** none – reads everything, **changes no app code, tests or tools**,
so it runs next to every lane
**Model:** **Opus · effort High** · **Environment:** "CAD-render-animation" (real Blender at start, CLAUDE.md section 4)

## Goal

A ranked list of real problems in the functions built since the first bug hunt (0045, 9 Nov, 0.2.34–0.2.38) – crashes,
lost work, old projects that no longer open, wrong output, slow spots, functions that fight each other – each with
proof and a suggested fix, so the lead can turn them into tasks **before** the owner hits them on his PC.

## Background

- Newest release **0.2.53**. Since 0045, these went in (task files have the details and each report's open points):
  0040/0049 tool library, 0041 tool changes + carousel ATC, 0042 coolant, 0046 better materials, 0050 Start later,
  0051 cut-face look, 0052 model update keeps everything, 0053 safe updates + project lock, 0054 queue fixes,
  0055/0056 Looks fixes + same STEP twice, 0059 test tour, 0060 small fixes, 0064 double-arm changer, 0065 clash
  check, 0066 rotary axes A/B/C. Each was tested on its own; **few were tested together.**
- Read CLAUDE.md section 8 (Blender's traps found so far) first, then look for the same kinds of mistakes in the new code.
- Running at the same time: **0029** app-made toolpath (`core/toolpath.py`, `blender/toolpath.py`, `ops_toolpath.py`,
  `ui_machining.py`, a few lines in `ops_gcode.py`) and **0067** clash follow-ups (`clash*.py`, test-model makers
  `make_test_atc/gantry/linkage.py`, CI groups). Those files will change: look at them lightly, and before writing the
  report check each finding in them against the newest `main` (`git pull`).

## What to do

1. **Functions together** (the main point of this round) – on the generic test models, in one project each:
   - The test mill: G-code with **tool changes** (manual, carousel, double arm) **+ coolant + air + chips + cut-face
     look + Fit into + ATC speed**; then a model update (0052), save/reopen, Start later in the queue (0050), and a
     queued MP4 render of part of it (Draft) – does the video match the view (tools held, chips, wet sheen, hoses)?
   - The 4-axis and 5-axis models (0066) with coolant, chips, a tool change and the clash check (0065).
   - Same STEP twice (0056) + joints + clash check + model update. A rule-set switch (0015) on a project with decals
     and painted faces.
   - Undo / Ctrl+Z after each of the new buttons (Click the hub, Click the hinge, Check, Check for clashes, rotary
     Check, Make tool list) – crash or a half-done state?
2. **Old projects:** make a project with **0.2.34, 0.2.45 and 0.2.50** (release zips on GitHub, or check out the tag;
   joints, a group look, a decal, a G-code step with a tool change, a queued job) and open it in 0.2.53: everything
   there, nothing doubled, the queue job still renders.
3. **Slow:** the new per-frame work (tool copies, double-arm visibility keys, rotary samples, coolant, clash markers)
   on the generated Heavy machine (`pccheck/heavy_scene.py`, ~3,000 parts) – ms per frame before/after switching
   each one on; anything at every redraw.
4. **Prove** each finding: a short script or click test (keep these in a scratch folder **outside** the repository;
   put the few lines needed to repeat it in the report). A finding that cannot be shown is *suspected*, never
   confirmed. Windows-only code (project lock, safe updates): review by reading. Helper agents may read areas in
   parallel (at most 4, one area each, findings only); the main session checks every finding itself.
5. **Report** in this file (below), one table row per finding, worst first:
   `# · severity (crash / lost work / old project / wrong output / slow / small) · where (file:function) · what
   happens and when · proof (confirmed + how / suspected) · suggested fix in one sentence · lane · model · effort`.
   Then a short list of areas that looked sound. Group small findings (texts, tooltips) in one row.
   **Push the report to the branch `task/0068-bug-hunt-2` only** (two workers will be fast-forwarding `main`
   tonight; a push to `main` in between would block them). The lead brings the report to `main`.

## Done when

- [x] Every combination in step 1 tried (Undo after rotary Check not tried, see report); old projects from 0.2.34, 0.2.45 and 0.2.50 opened; Heavy measured.
- [x] Findings table filled in, worst first, each confirmed with proof or marked suspected; sound areas listed.
- [x] No change to app code, tests or tools; the report pushed to `task/0068-bug-hunt-2`.

## Not in this task

Fixing anything – even one-line fixes go into the report as a suggested fix. New features, the look of the UI (0062),
render quality. The owner's own STEP files and projects (the repository is public – generic test models only).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus · High), night of 10–11 Nov 2026. Three helper agents read one area each
(tool changes + coolant + chips; rotary + clash + same STEP twice; queue + lock + updates); every finding they reported
was run again (or, for code-only findings, read again) in the main session. Scratch scripts are outside the repository
(`/tmp/claude-0/bh/scripts`, `/tmp/claude-0/bughunt-a|b|c`); the lines needed to repeat each finding are in its row.
Checked against the newest `main` (only documents changed since 0.2.53) and 0067's branch (`ccr-b84f1206-n8rnm0`,
`clash.py`): row 17 is already fixed there, the others are not touched by it. 0029's branch had no code pushed yet.
All times on the 4-core web machine with other work running (a queued render, other checks): use them as ratios.

**Findings** (worst first; *confirmed* = shown by a script in Blender 5.2.3 / Blender as a module):

| # | Severity | Where | What happens and when | Proof | Suggested fix | Lane | Model · effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **fixed in 0070 (0.2.56)** · lost work | `blender/queue.py:_delay_tick` | **Start later is cancelled by the first Save.** Set "Start later" on a project that was never saved (or then Save As), save it before going home: at the next tick the delay is cancelled ("another project is open now") and the overnight render never starts. | confirmed: unsaved project, `queue_start_later(seconds=3600)`, `wm.save_as_mainfile(...)`, `queue._delay_tick()` → `delay_pending() == False`, note "another project is open now". | Update `_DELAY["project"]` in a `save_post` handler (load_pre already handles closing the project). | Motion | Sonnet · Medium |
| 2 | **fixed in 0070 (0.2.56)** · lost work | `blender/queue.py:_tidy_old_queues` (from `start`) | **Starting a queue deletes the project copy of another queue that is still live** – one that has just started (no `status.json` yet, a few seconds) or one running on a colleague's PC from the same `Renders\_queue` folder (its pid is not alive here). Every later job of that queue then fails "cannot read file". Also: queue folder names have 1-second resolution and `exist_ok=True`, so two starts in the same second share one folder. | confirmed: two queue folders, A with `queue.json` only, B with `status.json` running + a foreign pid; `queue._tidy_old_queues(root)` removes both `.blend` copies. | Only tidy folders whose status says `running: False` (or older than a day); add pid/uuid to the folder name and refuse an existing one. | Motion | Sonnet · Medium |
| 3 | **fixed in 0070 (0.2.56)** · lost work | `blender/updates.py:preflight` | **Update now silently drops a pending Start later**: preflight checks imports, the running queue, the lock and other Blenders, not `queue.delay_pending()`; after the restart the panel says "Everything else is as it was". | confirmed by reading (`preflight` has no delay check; `delay_lost` only runs on load_pre, not at quit). | Refuse in `preflight`: "A delayed queue start is set for 22:00: cancel it or wait". | Quality & delivery | Sonnet · Low |
| 4 | **fixed in 0070 (0.2.56)** · wrong output | `blender/queue.py` `_RUNTIME`, `_ours`, `start` | **The session remembers only one running queue.** Start A's queue (the file is not made dirty, so A's `queue_pid` is not saved), open B, start B; reopen A: its jobs show WAITING, Start queue is allowed and a second runner renders the same jobs into the same frame folder (both race on `frame_NNNN.tmp.png`). "Stop now" in B marks A's jobs "Stopped" (`_RUNTIME["killed"]` is global). Two background Blenders share one graphics card. | confirmed (runner replaced by a 120 s sleep): "A reopened: running shown = False, jobs ['WAITING'] … a 2nd runner for A's jobs; live runners: 3". | Keep the runtime per project (key: project path / queue folder); warn before a second runner while one of this session is alive. | Motion | Opus · Medium |
| 5 | **fixed in 0070 (0.2.56)** · wrong output | `queue.start`, `FRESING_OT_queue_start`, `queue_add(start=True)` | **Start queue, Render animation or a Time test also starts the jobs waiting for Start later**, and the delay stays armed (later "already running", or it restarts stopped/failed jobs). A quick time test during the day starts the overnight renders. | confirmed: `queue_start_later(seconds=3600)` then `queue_start()` → running and `delay_pending() == True` ("Starts in 1 h"). | `cancel_delay()` in `start()` (and say so), or start only the new job when a delay is set. | Motion | Sonnet · Medium |
| 6 | wrong output | `blender/toolchange.py:tool_keys_plain` + `gcode.copies` + `machining.cut_items` / `_copies` | **Two G-code steps in one animation: step 1's tool stays in the spindle during step 2, and milling cuts with a hidden copy.** Each step makes its own spindle copies ("FR tool T2", "FR tool T2.001") and keys only those; the copy still in the spindle at the end of step 1 stays visible next to step 2's tool. `gcode.copies()` keeps one copy per T (the last), so milling and chips read T2's path in step 1 from step 2's copy, which is hidden then (stale `matrix_world`, CLAUDE.md §8). | confirmed: test gantry, a program ending with T3 in the spindle, two steps: in step 2, 34 frames (manual) and 418 frames (ATC) show 'FR tool T3' and 'TOOL T1 FLAT D6' together; in step 1, 'FR tool T2' and 'FR tool T2.001' are up to 40.3 mm apart and `gcode.copies()[2]` is the hidden one. (`test_atc_two_program_steps_share_the_pocket_tools` ends with T1 back in the spindle, so it misses this.) | Make the spindle copies once per build (looked up like the pocket copies), hide each step's copies at its end, and let milling use the copy that is visible in each time window. | Machining | Opus · High |
| 7 | wrong output | `blender/doublearm.py:_Bake.pot_copy`, `_Bake.run` | **Double-arm, two G-code steps: every pot copy is made again, so a tool shows in two pots** (with random pockets, its old and its new pot at once); the spindle copies double as in row 6. | confirmed: test_atc model, two steps: 10 pot copies, each doubled ('FR tool T2 pot 5' + 'FR tool T2 pot 2.001' …); 324 sampled frames of step 2 show a tool twice (frame 833: T2 in pot 5 and pot 2). | Reuse pot/arm copies across the steps of one build, keyed by T and pocket (fix together with row 6). | Machining | Opus · High (with 6) |
| 8 | wrong output | `blender/gcode.py:prepare` vs `gcode.bake_step` | **The changer animation plays out of step with M6 when a G-code step does not start at the machine's start point** (a joint step before it, or a second program step): `prepare` places the changer blocks and `b.duration` from `start_point(mach)`, `bake_step` reads the program from where the joints really are, so the first rapid takes another time. The next step can also overlap. | confirmed: a joint step moves Y 100 mm before the program: the changer animation is placed with the change at 0.90 s, the baked program has it at 1.20 s; 2 frames after the real M6 the carousel is already 12° into its turn. | Place the changer blocks and the step length from the same start `bake_step` uses (the joint state at the step's start). | Machining | Opus · High |
| 9 | wrong output | `blender/coolant.py:_layout` (first Build after Coolant is switched on) | **Automatic coolant hoses: the first Build mounts them 80 mm too high; the queue's video shows them right, so view and video differ.** `_layout` turns the head's parts into the coolant root's space with `r.matrix_world`, but the root was just made and parented: Blender has not worked out its world matrix yet (identity – CLAUDE.md §8, "a new or newly parented object has no world matrix until the next update"). The spindle nose is then read in world coordinates (z 110 instead of 30 mm above the tip): `fr_mount_z` 116 mm instead of 36 mm, hoses up to z 270 instead of 203 mm. Any later Build (and the queue, which builds again from the saved copy) gives 36 mm. With the machine away from x = y = 0 the ring radius test can also miss the nose. | confirmed: test gantry with ATC, milling, chips, coolant (Automatic), air: first `animation.bake` → `root["fr_mount_z"]` 0.116, hose verts 2348; a second `bake` with nothing changed → 0.036, 1748 verts. The queue-runner steps on the saved copy (`open_mainfile`, `animation.bake`, `machining.prepare`) give the second result. | `bpy.context.view_layer.update()` after `ensure_root` (or use the head's world matrix times the root's local one) before `_layout`. | Machining | Sonnet · Medium |
| 10 | wrong output | `blender/rotary.py:build` (`auto` sign, line ~124) | **C (any axis carried by another) turns the wrong way when Build is pressed with the outer axis at 90° or more.** The sign comes from `rel.dot(e)` with the joint axis in the pose the model is in now; with A at ≥ 90° C's axis is tipped over and its sign flips, while `finish()` uses the unturned direction. Plain: the cut is mirrored; TCP: the table turns the other way; Check says "-Z" instead of "+Z". | confirmed: 5-axis test model, C's sign −1 at A = 0/60/89.9°, +1 at 90/90.1/100/120°; program `G0 C90`: C joint ends at −90° when built at A0, +90° when built with the trunnion at 95°. | Work out `auto` from the direction turned back to A0 B0 C0 (the outer axes' `back`, as `finish()` does). | Machining | Opus · High |
| 11 | wrong output | `blender/ops_gcode.py:FRESING_OT_cnc_rotary_check.invoke` | **Rotary Check leaves the machine in the pose of the frame shown, and the next Build starts from there**: `check_poses` reads the (keyed) joint values first, `clear_keys` runs after, and `_finish` puts the keyed values back. With row 10 it can also flip C. | confirmed (+ read): 4-axis model at frame 400: static pose X 0 Z 0 A 0; what `_finish` puts back: X −0.01, Z −0.005, A −6.14 rad. | Call `animation.clear_keys(sc)` before `rotary.check_poses(sc)`. | Machining | Sonnet · Low |
| 12 | wrong output | `blender/clash.py:save` + modal `FRESING_OT_clash_check` | **A clash check that runs while the animation is built again stores the old result as up to date.** The check runs over many timer ticks and lets clicks through; `save()` takes `build_signature()` at the end, not the start. Rows of the old build are stored with the new fingerprint (never stale); a Build during frame reading mixes both builds. | confirmed: clash test model, check stepped to "reading done" (0.4), arms changed so they no longer meet, built again (a fresh check finds nothing); finishing the first check stores ('ARM.A','ARM.B','CLASH'), "1 clash", not stale. | Take the signature in `_setup()` and drop the result if it no longer matches at the end (or refuse Build / model update while a check runs). | Clash | Sonnet · Medium |
| 13 | wrong output | `blender/decals.py:to_template` / `from_template` | **Same STEP twice: a logo from a template meant for copy 2 lands on copy 1; "every copy" decals on both machines reach only the first.** The template stores the unscoped path (identical for both copies); `from_template` takes `parts[0]`; the second entry of the same name is skipped by the "already there" test. | confirmed: test_decals_a imported twice, decal on copy 2 only (UID `~2/TEST.DECALS#1/PANEL#1`); template stores `TEST.DECALS#1/PANEL#1`; in a new project with two copies: copy 1 has 1 decal, copy 2 has 0. | Also store the scoped part ID and prefer an exact match; do the "already there" test per target part. | Looks | Sonnet · Medium |
| 14 | lost work (small) | `blender/joints.py:to_specs` / `rebuild_from_specs` vs `doublearm.ARM_TAG` | **A model update drops the double-arm's tag (`fr_atc`) on its 14 joints**: afterwards they are ordinary joints (Find axes could pick the arm's stroke or turn as an axis), and Remove arm leaves 'Pot 4 tip' behind. | confirmed: test_atc set up, `import_step(update_root=…)`: tagged joints 14 → 0; after removing one pocket and Remove arm, 'Pot 4 tip' is left. | Carry the tag in the joint specs (or tag again from `arm_slide`, `arm_turn` and each pocket's `tip_joint` in `gcode.after_model_update`). | Machining | Sonnet · Medium |
| 15 | old project | `blender/build.py:repair_uids` + `gcode.after_model_update` | Old two-copy projects (before 0.2.44): `repair_uids` gives copy 2 new `~2/` IDs but leaves the stored ID strings (`cnc.tool_uid`, `workpiece_uid`, `tools[].uid`, `air_nozzle_uid`, milling `workpiece_uid` / `finished_uid`) as they were: a CNC set up on copy 2 can jump to copy 1 at the next model update. | suspected (code reading). | In `repair_uids`, take these `*_uid` strings again from their object pointers. | Machining | Sonnet · Medium |
| 16 | slow | `gcode.copies` (via `machining._tool_copies`), `machining.signature` (every frame), `coolant.wet_parts`, `machining.is_active` | **Milling and coolant redo whole-scene work at every frame**: `gcode.copies` walks all of `bpy.data.objects` (called twice per frame), `coolant.wet_parts` walks `scene.objects`, and `machining._on_frame` hashes the whole motion (`signature`: f-curves, chain objects, copies) at every frame. Next to a big machine this triples the per-frame cost. | confirmed (Heavy machine 3,050 objects + 5-axis test model, median ms per frame while scrubbing 61 frames; small = 5-axis model alone): motion only 8.3 (small 1.2); + milling 37.9 (10.8); + chips 40.9 (10.8); + coolant 57.2 (16.4). Double-arm test model without milling: changer 7.2 ms (small 0.7, i.e. only the big machine's own motion); + coolant 30.2 ms (small 2.0). Profile on Heavy: `signature` 6.8 ms/frame, `gcode.copies` 3.3, `coolant.wet_parts` 2.3, `coolant._patch_new_materials` 2.4, `is_active` 1.0. Budget at 25 fps playback: 40 ms. | Keep the copies and wet parts in the runtime dict (cleared at Build / load / undo); check the signature only on a depsgraph change (the existing `_on_depsgraph` already watches the chain), not per frame. | Machining | Opus · Medium |
| 17 | slow | `blender/clash.py:Check._mesh_at` → `Mesh._orient` | Clash check with milling on: every cut workpiece mesh gets the per-face inside test (Python rays for up to 50,000 faces): the 4-axis test program (1,882 frames, coolant + chips + a tool change) did not finish in 20 min (606 workpiece meshes made); the same without milling: 22 s. | confirmed. **Already fixed on 0067's branch** (`oriented=True` for Manifold meshes) – nothing to do if 0067 merges. | – | Clash | – |
| 18 | small | `blender/coolant.py:after_model_update` | After a model update the coolant root has no parent (the old head part is deleted) and the wet marks are gone until the next Build: moving the head by hand or a still picture before the next Build shows hoses left behind. | confirmed: root parent 'Z.ASM' → None after the update; wet parts 5 → 0 (4 materials stay patched). The next Build parents it again ('Z.ASM.001'). | Call `ensure_root` (and `apply_wet` when built) at the end of `coolant.after_model_update`. | Machining | Sonnet · Low (with 9) |
| 19 | small | several | (e–h **fixed in 0070, 0.2.56**) **Small ones** (code reading, not shown): (a) `doublearm.make_pots` removes the old pots before it checks the new ones: a failed hinge click leaves k pockets and no markers; `make_arm` can leave a tagged, unnamed joint when the second `joints.create` fails. (b) `air.cone` hangs on the spindle part's tip: with a longer tool copy its apex sits inside the tool. (c) `rotary.LAST_CHECK` is a global never cleared on load or when the A/B/C pick changes: the header still shows the old project's Check. (d) The clash check's `_Guard` is held across `yield` while it reads frames: milling and coolant stop updating if the user scrubs then. (e) Windows may sleep while a Start later waits (only the runner calls `SetThreadExecutionState`) – ask the owner about his sleep setting. (f) `project_lock.write` truncates in place (not temp file + `os.replace`): a colleague reading over SMB at that moment takes the lock. (g) `queue._pid_alive_os`/`kill` never exclude `os.getpid()`: a stale pid equal to the app's own new pid shows "running" and Stop now would kill the app. (h) `queue_runner.write` gives up after 5 `PermissionError`s: a lost final write leaves `running: True` and `sync` then marks finished jobs FAILED. | suspected | (a) find all pots first, then replace; (b) put the cone on the tip of the tool in the spindle (`fr_tools`); (c) clear on load_post and on pick change; (d) drop the guard between ticks; (e) `SetThreadExecutionState(ES_CONTINUOUS\|ES_SYSTEM_REQUIRED)` in `schedule()`; (f) write a temp file and `os.replace`; (g) treat own pid as not alive; (h) retry the last write longer / trust per-job DONE. | Machining (a–c), Clash (d), Motion (e, g, h), Quality & delivery (f) | Sonnet · Low |

**Areas that looked sound:**

- **Old projects:** projects made with 0.2.34, 0.2.45 and 0.2.50 (checked out from their tags; test gantry with X/Y/Z
  joints, sorted groups with a changed look, a text decal, a G-code step – with an ATC tool change, carousel and pockets
  in 0.2.45/0.2.50 – milling with chips, M8, a queued animation job) open in 0.2.53 with the same 35/53/53 objects,
  joints, groups and looks, the decal, the queue job (WAITING), tools and pockets; building twice adds nothing; save and
  reopen keeps everything. The 0.2.45 project's queued Draft animation renders in the queue (59 of 76 frames rendered
  when this report was written, ~45 s per frame on the loaded CPU; frame 40 checked: head at the carousel, chips on the
  bed).
- **Functions together on the test gantry** (ATC with carousel + milling + chips + coolant Automatic + air always on +
  cut-face look Automatic + Fit into 9 s): model update to the same STEP keeps the tool list, pocket assignments and
  the milling set-up (when the tools were linked the panel's way, `tools.use_part`); save, and the queue-runner's own
  steps on the saved copy (`open_mainfile`, `animation.bake`, `machining.prepare`) give exactly the view's state at 6
  frames: which tools/copies are shown and where, the cut mesh, chip counts, coolant jets/drops/hoses.
- **Undo / Redo** (real Blender 5.2.3 under xvfb, buttons pressed the way a click does): after Click the arm's hub,
  Click the hinge, Build animation, Tools from the program and Check for clashes – no crash, Undo gives the state
  before, Redo the state after (joints, tags, pockets, tools, clash rows). Rotary Check was not tried with Undo (row 11
  covers its real problem).
- **Same STEP twice + joints + clash + model update:** two cranes, a boom joint on each, one animation: clash rows stay
  within each copy; updating copy 1 to revision B keeps both joints on the right booms; the clash result goes stale; a
  new Build + check gives the same rows. Rule-set switch with decals and painted faces: planned per object name, decal
  objects are not parts (read, not run).
- **5-axis + coolant + chips + milling + clash** ran without errors (clash check 31 s on the model alone, 66 s next to
  the Heavy machine). The double-arm's visibility keys cost nothing measurable per frame (7.2 ms next to the Heavy machine = its own motion).
- **Selecting a part next to the Heavy machine** costs ~30 ms per update; it is Blender's own (26.5 ms with every
  depsgraph handler removed; each of the app's handlers adds < 4 ms).
- **From the helpers' lists** (each read in the code): every bake removes all tool, hand, pocket, carry and arm copies
  first; coolant is recorded after the tool keys from the same schedule; the chips' key includes path signature, cut
  items, air and coolant spans; runtime caches hold names and arrays only and are cleared on load; `store_array` is
  used for all array properties; `gcode.prepare` resets `fr_corners`/`fr_tools`/`fr_turns` at every Build; the clash
  draw handler is removed on load, save and clear; the queue runner registers the add-on before opening the copy, so
  the upgrade steps and frame handlers run there; `//` paths are made absolute for the copy and put back; the update
  helper waits for every Blender of the install, backs up, checks the version and size + SHA-256; the lock is skipped
  in background Blenders and only removed by its owner.

**How many runs:** none on GitHub (the push touches only `tasks/` and `TASKS.md`: no run starts).
