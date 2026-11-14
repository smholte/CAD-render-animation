# 0118 – Bug hunt, round 3: everything built since 0068 (findings only, no code changes)

**Who:** worker · **Status:** done – report on `task/0118-bug-hunt-3`, lead review · **Branch:** `task/0118-bug-hunt-3` (the report only – **do not push to
`main`**, see step 5)
**Started by:** lead chat, 14 Nov 2026 · **Lane:** none – reads everything, **changes no app code, tests or tools**,
so it runs next to every lane and starts **no** test run on GitHub
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation" (real Blender
at start, CLAUDE.md section 4)

## Goal

A ranked list of real problems in what was built since the second bug hunt (0068, 11 Nov, 0.2.53) – crashes, lost
work, old projects that no longer open, wrong output, slow spots, functions that fight each other – each with proof
and a suggested fix, so the lead can turn them into tasks **before** the owner hits them on his PC.

## Background

- Since 0068 about forty versions went in, **0.2.54 → 0.2.92**, many on the same day and each tested on its own:
  clash follow-ups and speed (0067, 0072, 0092, 0110), app-made toolpath (0029), machining fixes and tool marks (0071,
  0061, 0096, 0098, 0103 cycle time), Fade / X-ray / trails (0073), facets by size + paint schemes (0074), vessel motion
  (0085), cutaway (0086), camera rides (0087), hover pickers (0088/0089), way covers (0035/0090), joints in a batch
  (0093), the demo project and its stages (0077, 0091, 0095, 0097, 0102), hoses/cables/drag chains (0058), cable paths
  (0078), spooling (0080), tracks (0079), into the sea + riders (0081), assembly sequence (0100), product video (0101),
  web 3D model, smaller files, surroundings, baked light (0099, 0105, 0106, 0107), weather and time of day (0109), House
  import + bake (0114), the render kit with motion (0112). Each task file has its report and open points: read them
  first, do not re-report a known open point (mention it only if it is worse than the report says).
- Read CLAUDE.md section 8 (Blender's traps found so far) and look for the same kinds of mistakes in the new code.
- **Running at the same time** (their files change tonight – look at them lightly and check each finding there
  against the newest `main` before writing it): **0116** turbine (`tools/site_projects/`, `site/render_kit/`, maybe
  `materials_lib.py`), **0082** quadrant (`paths*.py`, `demo.py`, wake in the weather/sea code), **0117** mesh import
  (`importer/`, `ops_import.py`, `build.py`, `faces.py`), **0111** picker (`site/`, `web3d*`).

## What to do

1. **Functions together** (the main point), on the generic test models and the demo project:
   - **Demo project** (Help > Make demo project, Blender as a module or the real app): the whole animation with vessel
     motion on, the weather presets (rain, snow, night), the cut-away under water, a product video, the clash check,
     a web 3D export with surroundings and baked light; save, reopen, Build again – does anything move, double or
     vanish (cable payout, spool layers, track pads, riders, the sea end, seabed)?
   - **Model update** (0052) on projects that use the new kinds of data: a cable with contacts + sea end + riders, a
     spool, a track, a hose, a way cover, an assembly sequence step, decals, a cutaway, a camera ride: all kept, none
     doubled, warnings honest.
   - **Scripts off** ("Auto Run Python Scripts" off, real Blender with `-Y` and the control driver of
     `tools/coupling_check_noscripts.py`): do the new drivers (cables, spools, tracks, weather, vessel motion, riders)
     still move? Any Python driver that slipped in?
   - **The render queue** (background Blender) for a job with weather + vessel motion + a cable in the sea + tracks:
     does the video match the view? Start later; a paint-scheme job (0074).
   - **Undo / Ctrl+Z** after the new buttons (Add cable, Into the sea, Add track, Add spool, Bake light, Make product
     video, House import/bake, Check for clashes) – crash or half-done state?
   - **House import** (0114) with odd but valid `.hpscene` samples from `smholte/house-scene-format` only (never
     `house-planner-dev`).
2. **Old projects:** make projects with **0.2.53, 0.2.70 and 0.2.85** (release zips on GitHub or the tags; joints,
   a look, a decal, a G-code step, a cable, a queued job) and open them in 0.2.92: everything there, nothing doubled,
   the queue job still renders.
3. **Slow:** ms per frame change and per redraw on the demo project and on the Heavy machine
   (`pccheck/heavy_scene.py`) with each new per-frame feature switched on one by one; side-panel redraw time with the
   demo open (anything walking the whole scene at every redraw – CLAUDE.md section 8, `logic.Tree`).
4. **Prove** each finding: a short script or click test (scratch folder **outside** the repository; the few lines
   needed to repeat it go into the report). A finding that cannot be shown is *suspected*, never confirmed.
   Windows-only code: review by reading. Helper agents may read areas in parallel (at most 3, one area each, findings
   only); the main session checks every finding itself.
5. **Report** in this file, one table row per finding, worst first:
   `# · severity (crash / lost work / old project / wrong output / slow / small) · where (file:function) · what
   happens and when · proof (confirmed + how / suspected) · suggested fix in one sentence · lane · model · effort`.
   Then a short list of areas that looked sound. Group small findings (texts, tooltips) in one row.
   **Push the report to the branch `task/0118-bug-hunt-3` only** (several workers fast-forward `main` tonight). The
   lead brings it to `main` and turns rows into tasks.

## Done when

- [x] Step 1 combinations tried (say which were not and why); old projects from 0.2.53, 0.2.70, 0.2.85 opened; speed measured
- [x] Findings table filled in, worst first, each confirmed with proof or marked suspected; sound areas listed
- [x] No change to app code, tests or tools; the report pushed to `task/0118-bug-hunt-3`

## Not in this task

Fixing anything – even one-line fixes go into the report as a suggested fix. New features, the look of the UI (0062),
render quality judgements. The owner's own files (the repository is public – generic test models only). The Fresing
400 (CLAUDE.md section 6).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 14 Nov 2026, on `main` = ec68afe (0.2.92; nothing of the
running tasks 0082/0111/0116/0117 had reached `main` when the findings were checked again at the end). No app code, test
or tool changed. Three helper agents read one area each (A: model update + old projects, B: per-frame/redraw work +
scripts off, C: queue, undo, features together); **every row marked confirmed was run again in the main session**
(their scripts, unchanged, plus my own). Scratch scripts were outside the repository.

**What was tried**
- **Demo project** (full form, 0.2.92, built in 168 s, 2,504 objects, vessel motion on): Build again; save, reopen,
  Build again – nothing moved, doubled or vanished (cable shape, spool layers, track pads, riders, sea end, seabed
  compared at 7 frames; only the cable's ends 4 mm and the animation camera 4 mm differ between the saved build and a
  rebuild, the same on every rebuild after). Weather presets Grey North Sea / Storm / Snow at the quay / Night shift
  + Build: no errors. Web 3D export with surroundings (11 s, 9.3 MB) and with surroundings + soft light baked (109 s,
  13.0 MB): valid glTF, the project unchanged after both. Product video (TENSIONER, 15 steps, 61 s) + Build, then the
  demo animation built again: works (row 16 below). **Not tried on the full demo:** the clash check (13 min on one
  core; `test_demo_clash.py` checks it at every push) and a real queue render (the queue was checked in parts, rows 1,
  6, 11).
- **Model update** with cables + contacts + sea end + riders, spools, tracks, hoses, sequence steps, a second model in
  the project: rows 2, 3, 4, 7, 17. Rollback after a failed update (tracks + cable, spools) was exact.
- **Scripts off:** every driver in all 34 tour projects of 0.2.92 and in the demo: 0 Python-only, 0 invalid (demo:
  682 simple expressions, 95 AVERAGE, 8 MAX). Real Blender 5.2.3 `--factory-startup -Y` (no extension) against the
  same with scripts on, spool / tracks / weather / vessel / sea cable / two way covers at 3 frames: every object place
  and every evaluated mesh identical.
- **Render queue:** paint schemes, stills, start later during a House bake (rows 1, 6, 11); jobs of old projects (below).
- **Undo:** the new add/remove operators all have UNDO; Ctrl+Z inside the long modal jobs is row 13. Not tried by
  hand in the real app for each button (the reviewers' reading + one real-app run for the web 3D export).
- **House import:** only the pinned sample and its bake (agent C); no odd samples beyond those – the 0114 independent
  tester's 133 tests already cover the reader's odd cases.
- **Old projects:** the whole test tour (19 / 23 / 31 sets) made with **0.2.53, 0.2.70 and 0.2.85** (their tags, Blender
  as a module), each set opened in 0.2.92 and every animation built again, places of every object compared at 5
  frames: **nothing missing, doubled or erroring; every collection the same length.** The only differences are
  intended changes: tool changer / double-arm animations 5–10 frames shorter (0103 acceleration) and the spindle 14 mm
  higher in "Three tools" at one tool change (0096: no dive with a new tool). The queued still and video of each old
  hub project set up and start in 0.2.92 (engine, size, bake). Vessel-motion projects: row 9.
- **Speed** (4-core web machine, Blender as a module, no graphics card; medians of 30 random frame changes):
  demo as built 26–34 ms per frame change; vessel motion on/off within the noise (25.6 / 29.4 ms); weather on
  27.8, Clear day 30.1, Grey North Sea 36.1, Snow 34.0, Night 23.1, **Storm 49.4 ms** (rain + spray drawn every frame:
  +~20 ms – noted, not a finding). Real app under xvfb, demo open: a whole-window redraw 91–105 ms with or without the
  side panel (software GL, the 3D view dominates; the panel's own share is below that noise). Per-call costs measured
  in the panels: row 18. Heavy machine: not run again – its `heavy.vessel` / `heavy.weather` / `heavy.web3d*` lines
  measure these at every push.

**Findings** (worst first)

| # | Severity | Where | What happens and when | Proof | Suggested fix | Lane | Model | Effort |
|---|---|---|---|---|---|---|---|---|
| 1 | wrong output | `queue.py:run_job` (948) → `_setup_animation` → `animation.bake` (496) → `states.apply_shot` (393–401) | **"Every paint scheme" animation jobs all render in the same colours** whenever the animation has a start scene – which "New animation" gives it whenever a scene is active, and Product video always. The job's scheme is applied first, then Build puts the start scene's own looks back over it. Time tests the same. | confirmed: crane, schemes Own/Red/Blue, start scene "Start", `run_job` for Red and Blue → colour at render `{'Red': '#F9A800', 'Blue': '#F9A800'}` (`test_queue_schemes.py` has no start scene) | Apply the job's scheme after `animation.bake` inside `_setup_animation` (as the still path does after `apply_shot`) and test with a start scene. | queue / looks | Sonnet | Medium |
| 2 | lost work | `spool.py:after_model_update` (1713–1749) | **Updating one model undoes every drum and carousel of every other model in the project**: tables dropped, cable start set to FIXED, the drawn rope deleted, owner cleared; only the updated model's cables are read again, so the other spools are never set up again. No note, no problem shown. (Demo: updating the quay model would stop the carousel.) | confirmed: test_spool (Drum, Carousel) + test_crane_a, crane updated to rev B → before `a_kind SPOOL, table spool:Drum, made 6`, after `a_kind FIXED, table '', made 0`, `notes []` | Skip spools whose part, coil and cable are not in the updated model (the `concerned()` test paths.py uses). | cable paths | Sonnet | Medium |
| 3 | lost work | `spool.py:after_model_update` (1740) | A drum part whose ID changes in an update (renamed, moved to another subassembly) is found once, but `part_uid` / `coil_uid` keep the old ID: **the next update loses the spool** ("its part is gone"), the cable goes back to a plain wheel. | confirmed: wrapped build so the drum gets a new ID; update 1 OK with stored ID still the old one; update 2 → note "its part is gone", `enabled False`, cable `WHEEL` | Write `sp.part_uid` / `sp.coil_uid` from the new objects (same for flex items whose reading fails). | cable paths | Sonnet | Medium |
| 4 | lost work | `reimport.py:_carry_over` (382, 391, 435) | An **Assembly sequence Preview left above 0 % at a model update becomes permanent free moves**: `clear_keys` does not end the preview, so the parts it moved are taken as free moves and copied onto the new parts, which have no preview tag – the slider back at 0 %, Build and Clear keys all leave them half-way out. | confirmed: test_sequence, step on SPINDLE.UNIT, preview 50 %, update → `free moves 7`; slider 0 → 7; Build + Clear keys → 7 | Call `sequence.end_preview(scene)` at the start of `_carry_over` (and in `clear_keys`). | assembly sequence | Sonnet | Medium |
| 5 | wrong output | `vessel_motion.py:changed` (526) + `flex.py:_follow` (1914) | **Hoses stay where Build left them when a vessel-motion setting changes after Build** (strength, sea state, heading, still/level, on/off): the fittings move, the tube ends do not, and the animation still counts as built. View and stills wrong until Build again (the queue builds again, so videos are right). Cables are not hit (they store shapes in the cable's own coordinates). | confirmed: test_flex_hoses_a, sea + vessel, one step built, strength → 200 %: fitting moved 66.5 mm, tube end 0.0 mm, `anim_baked` still 'Move' | Take the built animation off (or bake the hoses again) in `changed()` when there are hoses; better, store hose shapes relative to a carrier as paths.py does. | flex parts | Opus | Medium |
| 6 | wrong output | `ops_motion.py` "Add image" (1237–1247), `states.save_shot`, `queue.run_job` STILL (928–948) | **Queued stills render at the frame the queue started at**, not the frame they were added at: the saved scene keeps pose, hiding and camera but no frame, and the job sets none. With vessel motion, sea waves, rain or snow (all by frame) every picture shows the queue-start frame's sea. | confirmed: crane on Deck, vessel on, Add image at frame 60, timeline back to 1, `run_job` → heave −0.137 m at Add image, +0.022 m in the job (matrix difference 0.16) | Store `frame_current` on the queue-only (and floor-pin) saved scene and `frame_set` it in `run_job` before rendering. | queue | Sonnet | Medium |
| 7 | wrong output | `paths_riders.py:after_model_update` (588–606) | **A rider part that is gone in the new revision keeps its old object**, which the update then deletes: the rider keeps empty entries, the report says nothing ("its parts are no longer in the model" can never show, as the old model is still alive while riders are read). | confirmed: test_sea set-up, update with two CPS CHOCK parts missing → `2 missing`, `notes []`, rider has 2 `None` parts | Fall back to the old part only when its ID is not in the updated model; for gone IDs drop the part and add a note. | cable paths | Sonnet | Medium |
| 8 | slow | `props._seq_preview_changed` (771) → `sequence.preview` (455–459) → `plan_now` | **Each step of the Assembly sequence Preview slider re-plans the whole step: 2.8–5.1 s per step for 260 parts** (O(n²) pair tests with `np.cross` on single vectors); dragging the slider freezes the window for tens of seconds. The first touch also **throws away the built animation without a word**. | confirmed: demo, a Sequence step on TENSIONER (260 movers), preview 10/20/30/40 % → 5134 / 2828 / 2917 / 2772 ms, `anim_baked` 'What it can do today' → '' | Keep the plan while the slider moves (drop it when parts or settings change), vectorise `_in_way` / `_across`; say so (or ask) before clearing a built animation. | assembly sequence | Opus | Medium |
| 9 | old project | `vessel_motion.py:_sync` (486–493), `core/vessel_motion.key` | **A project with vessel motion from 0.2.65–0.2.87 keeps the rig worked out from the waves before 0109**: the key has no version, so the rig is never rebuilt, while the sea under it is (`MAT_VERSION` 4). The vessel moves differently from the same project made today and out of step with the new sea; changing any vessel setting then rebuilds it and the motion jumps. | confirmed: the 0.2.85 and 0.2.70 tour sets "Vessel motion" (Calm, beam) opened in 0.2.92, rig as opened vs rebuilt: heave up to 33 mm apart, 0.08°; agent A computed up to 0.24 m heave and 0.8° pitch at Rough (old wave table vs new) | Add a version to the rig key so old rigs are rebuilt once on load. | vessel motion | Sonnet | Low |
| 10 | slow | `flex.py:_moved` (1399–1410) / `_live` | **With vessel motion on and the animation not built, every hose is solved again from scratch at every frame** (the ends' world matrices change every frame). +6.6 ms per frame change for 4 hoses; 0058 measured 59 ms for 23 hoses moved at once. | confirmed: test_flex_hoses_a, 60 frames: sea + vessel off 0.56 ms, vessel on 7.10 ms per frame, `_live` 60 of 60 | Compare the ends relative to each other (or a shared carrier, as paths.py `_rel_now`) and move the stored shape when the pair moved rigidly. | flex parts | Opus | Medium |
| 11 | wrong output | `queue._delay_tick` (613–631), `start`; `house_bake.HouseBake.steps` (338) | **Start later firing (or Start queue / Ctrl+S) during a House bake copies the half-baked project**: temporary "FR house bake" objects, the moment's weather, hidden parts, the bake's size and samples. The queue then renders that. (The web 3D export and clash check leave similar half states while they run.) | confirmed: sample house, one still queued, Start later due at bake tick 6 → queue copy 63 objects instead of 55, four "FR house bake" objects in it; the project itself is restored after the bake | While a House bake, web 3D export or clash check runs: `_delay_tick` waits, Start queue refuses, a `save_pre` warns. | queue / house | Sonnet | Medium |
| 12 | small (wrong output) | `sequence.py` (251–254, `_WorldAt`; `_offset_delta` 166) | With vessel motion on, an Assembly sequence step's keys depend on the frame Build is pressed at: places, "up" and the blocked-way rays are measured on the tilted world. | confirmed: test_sequence on Deck, vessel on, UP 0.3 m: Build at 1 twice identical; Build at 1 vs at 70 → keys up to 2.4 mm apart (grows with sea state and size) | Measure inside `vessel_motion.at_rest(scene)`. | assembly sequence | Sonnet | Low |
| 13 | small | `ops_web3d.modal` (122–131), `ops_house.modal` (154–163), `ops_clash.modal` (89–98) | **Ctrl+Z during a long job** passes through: the web 3D export stops with no file and no message; House bake (reading): Ctrl+Z undoes the user's last action, then the bake's restore writes the weather and hiding saved at its start over the undone scene – a mix of two states. | web 3D: confirmed in the real app (crane, Ctrl+Z at 27 % → `running False`, no .glb, message unchanged, no crash); House bake / clash: suspected | Swallow `ed.undo` / `ed.redo` while these run, with "Cancel first" in the status line. | web 3D / house | Sonnet | Low |
| 14 | small | `importer/runner.py:ImportJob` (65, `start` 79–80) | **Two imports of the same new STEP started within about a second** (two app windows; the PC check or Make test tour importing a test model in the background while the owner imports it) share one `.partial` folder: the second deletes the first's half-written cache and one of them fails with "No such file … tree.json". | confirmed: two Blender processes importing one fresh STEP 0 s and 0.5 s apart → the second fails (FileNotFoundError); 3 s and 5 s apart both work. Hit by chance while building two tours at once. | A `.partial` folder per process (`.partial-<pid>`), moved into place as today. Check against 0117 (it works in `importer/` tonight). | import | Sonnet | Low |
| 15 | small (suspected) | `section.py:_on_render_init` (1003–1009) | At render start (in the window: the render job's thread) `sync` builds a `logic.Tree`, may write custom properties, wrap materials and set render settings – writing data off the main thread, the kind of thing that crashed before. Only writes when something differs. | suspected (reading only) | As machining does: no writes off the main thread; sync in the render operators and the queue before rendering. | cutaway | Opus | Medium |
| 16 | small | `animation.bake` → `states.apply_shot` (weather in the start scene) | **Build silently switches the weather off** when the animation's start scene was saved before the weather was on: the demo's own animation does it – weather Grey North Sea on, Build → rain, splash, spray, moonlight objects gone, no warning. By design (CLAUDE.md: Build puts the start scene's weather back), but the owner gets no hint. | confirmed: demo, Grey North Sea on, product video + Build, then the demo animation built again → "FR weather rain / splash / splash sea / tops", "FR Sea: spray", "FR weather moonlight" removed, warnings `[]` | A Build warning when the start scene's weather differs from the panel's ("the start scene has no weather: save it again to keep it"). | weather | Sonnet | Low |
| 17 | small (suspected) | `tracks.py:after_model_update` (1195–1212) | Pads or plates gone in the new revision are dropped without a note; after a wheel's ID changes its "coupled" flag is lost (new ID compared with old IDs). | suspected (reading only) | A note for missing riders; compare through `mapping`. | tracks | Sonnet | Low |
| 18 | small | several | (a) **Per redraw:** `ui_fade.py` 21, 29 call `fade.xray_parts(scene)` twice per redraw (a walk over `scene.objects`: 0.78 ms each on the demo, 1.16 ms on 3,000 objects) whenever "3 Looks" is open, X-ray parts or not; `ui_weather._work_lights` (0.76 ms) runs before its fold check; `ui_section.py` 65 `cut_parts` once per cut – the side panel redraws every frame while playing. Count by a stored number (as `ui_paths.found_count`). (b) `section._cut_objects` (961) has no callers. (c) `weather.after_clear` sets the scene's action to None after the orphan clean-up, so the "FR Scene" action stays as an orphan until the next Clear keys; `animation._channelbag` replaces a scene action the user made himself. (d) Driver results below 1e-4 are written as 0 (Blender 5.2.3, CLAUDE.md section 8): night sky glow, seabed payout, spool end, carousel solid's scale floor – all ≤ 0.1 mm or an invisible glow, no fix needed beyond a comment. | (a) measured per call (agent B, demo); (b)–(d) reading, (d) the 1e-4 limit confirmed | as said per item | looks / cutaway / weather | Sonnet | Low |

**Areas that looked sound**
- Old projects from 0.2.53, 0.2.70, 0.2.85: every tour set opens, builds and keeps its joints, looks, decals, G-code
  steps, cables, queue jobs (row 9 is the only old-project finding).
- Scripts off: no Python driver anywhere; real Blender `-Y` moves spools, tracks, weather, vessel, sea cable, way
  covers exactly as with scripts on. Expression numbers are formatted safely (`float()` before `!r`).
- Demo: rebuild after save/reopen identical; web 3D with surroundings and baked light; product video; weather presets.
- Model update: paths / flex `concerned()`, sea end added again, cutaway park/rebuild, work lights, vessel "still"
  parts, trails, camera ride `aim_uid`, way-cover carriage IDs, rollback after a failed update (tracks, cables, spools);
  property definitions of 0.2.53 / 0.2.70 / 0.2.85 vs now: nothing removed or retyped, no default changed.
- Handlers: depsgraph handlers ≤ 0.001 ms each when idle (vessel 0.024 ms), frame handlers with a built animation
  0.01–0.03 ms; hover draw handlers only while picking, removed on undo and load; `at_rest` restores in `finally`;
  undo_post clears the Python caches of paths, flex, tracks, spool, machining, hover.
- Queue: bake order (weather, flex, paths, spool), load_post resets in the background copy, the vessel rig re-synced,
  the cutaway in the background, absolute paths of programs, the fingerprint includes the weather.

**Leftover:** none in the repository; the scratch worktrees of the three old tags were removed.
