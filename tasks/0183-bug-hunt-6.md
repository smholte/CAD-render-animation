# 0183 – Bug hunt round 6 (findings only): everything merged since 0.2.114 used together

**Who:** worker · **Status:** done (17 Nov, findings only) · **Branch:** none (report on `main`, touching only `tasks/`)
**Started by:** lead chat, 17 Nov 2026 (plan before 0062) · **Model:** Opus · effort High · **Place:** Claude Code on
the web, environment "CAD-render-animation". Findings only: no app code, no version, no test run of its own.

## Goal

Find what breaks when the functions of 0.2.115–0.2.141 are used together, on old projects and on the made demo, before
the big side-panel task 0062 moves every panel. Same method as 0118 / 0131 / 0147 (read their briefs and reports).

## What to look at

- Everything in `CHANGELOG.md` from 0.2.115 to the newest: seabed cut (0148), height-map cutter + follow-ups (0146,
  0167), served cable + spiral bands (0158, 0164), full carousel and full spools + winch wires (0159, 0174), Flex
  follow-ups (0160, 0172), vessel details and water effects (0153, 0154), web export fixes, marine detail, page under
  the sea, web part tools, web player on a phone (0161, 0165, 0143, 0135, 0179), props and people, paths and actions, a
  person changes the tool (0155, 0157, 0156), wind park (0166), demo realism with label fields, ROV and tipping winches
  (0173), logo watermark + brand kit, app icon, Task Manager name (0176, 0169, 0178).
- Used together: Build → model update → re-bake → undo; save / reopen; render queue and every-paint-scheme videos;
  web export of the demo with people, ROV, labels and the sea cut-away; scripts off; the test tour.
- Old projects saved by 0.2.114, 0.2.125 and 0.2.135 opened in the newest version.
- 0147's rows: re-check that each fix holds. The tour stop `spool` that fails at random on GitHub is task 0184 – note
  only what you see.
- Speed: Build, playback and a web export of the demo against the numbers in the reports (name the machine).

## Rules

Public repository (CLAUDE.md section 6). Each row: what you did, what happened, what should happen, how often, the
smallest repeat case, severity (crash / lost work / wrong result / small), the lane and a proposed task grouping.
Push only `tasks/0183-bug-hunt-6.md` (+ `tasks/img/0183_*` if a picture is needed, small) and `TASKS.md`.

## Done when

- [x] Report: "In short (for the owner)" (≤ 8 lines), the rows, a grouping into fix tasks by lane for the lead.
- [x] Pushed to `main` touching only `tasks/` and `TASKS.md`; then check that main really contains your commit.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 17 Nov 2026. Hunted on `main` = ad19393 (0.2.141).
**No app code, test or tool changed**; scratch scripts lived outside the repository (named per row; gone with the
session – each row gives its numbers). Three helper agents hunted one area each (A cables / sea / spools / demo, B web
3D export and page, C sequence / mesh import / height map / people / brand / kit + House); the main session did the old
projects, undo and save in the real app, and re-ran the worst row of each helper. **(re-run)** = run again in the main
session; **(helper)** = run by the helper only.

### In short (for the owner)

- **Nothing crashes**, and **old projects are safe:** the whole test tour made with 0.2.114, 0.2.125 and 0.2.135 (38–43
  small projects each) opens and builds the same in 0.2.141 – only the intended upgrades differ.
- **Milling, Fast 3-axis:** one program leaves a 6 mm square hole straight through the workpiece at the end (row 2).
- **Model update of the same file** changes a cable's route: a contact you removed comes back (row 1); on the demo the
  A&R wire and the tipping wires come out wrong.
- **After a sea or water change on a built animation:** Ctrl+S (or autosave) while the cables are worked out again
  saves the project with most parts hidden (row 3); one Undo afterwards brings back the cable for the old water (row 4).
- **Web 3D page:** exporting the demo takes ~36 min instead of ~1.5 min because every wind-park part gets its own
  marine bake, and the panel says "about 34 s" (row 9); with Vessel motion off the sea cable floats or sinks 0.8 m (row 6).
- **All 0147 fixes still hold** (list below).

### Findings (worst first)

| # | Severity | Where | What happens and when | Proof | Suggested fix | Lane | Model |
|---|---|---|---|---|---|---|---|
| 1 | **lost work / wrong result** (not new: 0.2.114 the same) | `paths._merge` (paths.py:1071) keeps no list of removed read contacts; `read_cad` rewrites every wheel's `wrap_cad` from its CAD-pose solve (paths.py:1174), also user-added contacts; the demo's tipping-wire ends change (`a_part` WIRE ROPE → the swivel sheave's joint, `a_free_end` False → True; `_ends(keep_user=)` paths.py:958, unsure why) | **A model update to the SAME file changes cable routes.** Small: test_paths_a, the user removes CHUTE from "Wire rope", update with the same file → CHUTE is back, length 6.490 → 6.645 m. Demo (small form), update of the vessel root with its own file, then Build: A&R wire length 2.82 → 74.92 m (its kept-tight payout keys up to 117 m off), "cannot go round HANDLER TOP PULLEY at frame 2898 … goes 301° round", "Tipping wire port/stb no longer touches 'Bend 1' at frame 2913" (the maker had removed that bend), Second end up to 2.8 m off, lay label 32.3 instead of 32.0 m, 28 rollers get stand-still keys. The demo has no model-update test. | **(re-run)** A/`s17_contacts_update.py` (6.490 → 6.645, CHUTE back); **(helper)** A/`s14_demo_update.py ref\|update`, `s14_cmp.py`, `s16_settings_diff.py` | Remember removed read contacts (by part id) and keep the stored `wrap_cad` and ends of user-set contacts through `read_cad`. Test: the demo updated to the same file, then Build = identical. | cable paths | Opus · Medium |
| 2 | **wrong result** (new in 0.2.134, task 0167) | `core/machining.py` `_MapSide._below` (~1226–1240), used by `_piece` (~1300): builds `Manifold(mesh)` from a map tile's mesh without checking its status; `_column` (1243) does check and falls back to a box | **Fast 3-axis leaves a square hole straight through the block.** Tour set "toolpath" with the toolpath's own default settings (4,480 moves), milling Detail Normal, Fast 3-axis on (default), Build: at frames 241 and 251 a 6.4 × 6.4 mm tile (x −28.25…−22.25, y −8.25…−2.25 mm) has 168 columns where a ray from above meets no face. Cause: that tile's mesh is not manifold (`Error.NotManifold`, 821 vertices) → empty solid → `t.solid ^ below` is empty → the whole column is dropped. Exact cut: 0 such columns. 0.2.125 (0146 without 0167): no hole. Depends on the program (toolpath Detail Normal, 7,187 moves: no hole). A 0.2.114 milling project opens with Fast 3-axis on and shows it too. | **(re-run)** C/`e6_tile_hole.py <out> NORMAL` (3 of 3 runs, deterministic); C/`e6c.py` prints the tile's status | In `_below`: status not NoError or empty → that tile with the 0146 right-triangle mesh, else a box as `_column`. Test: a ray through every map tile meets a face. | milling | Opus · Medium |
| 3 | **lost work** (saved state wrong) | `queue.busy_job` (queue.py:622) and so `warn_busy_save` / `queue.start` / the delayed start know House bake, web export and clash check, not the re-bake job of 0160 (`rebake.py`, `FRESING_OT_rebake`); `flex.read_steps` (flex.py:1599–1628) hides every object the read does not need and sets the frame while the job runs | **Ctrl+S, autosave or an undo step during "Working the cables out again"** saves the project with most parts hidden in the view and at another frame; nothing restores them on opening. On the demo the job runs ~3 min (A: 193 s), so a save in it is likely. The queue (or a delayed start at night) would copy the same state. A Build pressed during the job came out right (A). | **(re-run)** me/`midjob_mod.py`: test_moving + Sea, Build, water 2 → 3 m, job stepped to 30 %, save a copy: reopened copy has **37 of 62 objects hidden** (3 before), frame 102 instead of 150; A/`s2_rebake_job_overlap.py save` the same (37 of 62, CABLE and FR Sea among them). | Add the re-bake to `busy_job` (`rebake.running(scene)`), so Save warns and the queue waits; better: a `save_pre` handler that puts visibility and frame back for the save. | cable paths | Sonnet · Low |
| 4 | **wrong result** (since 0137; real app) | the re-bake (modal job and the older timer route) changes the cable shapes outside any undo step; `paths._on_undo` / `flex._on_undo` only `forget()`; nothing checks `moved_since` after undo | **Undo after a re-bake brings back the new water level with the cable for the old one.** Real app (xvfb): test_moving + Sea, Build (cable end on the seabed −14.976 m), water level 2 → 3 m, re-bake done (−13.976), any other action, **Ctrl+Z** → water 3.0, cable at −14.976 = **1 m under the seabed again** (0147 row 8's fault back), animation still "built", no re-bake starts (checked 3 s later); a second Ctrl+Z still shows water 3.0 with the old shapes. Redo gives the right state. The same holds for sea state / vessel speed (same route, by reading). | **(main session)** me/`undo_rebake.py` (real Blender under xvfb, `--enable-event-simulate`) | An `undo_post`/`redo_post` check: when built and `moved_since(MOTION_KEY)` → request the re-bake (or take the Build off with a note). Real-app test. | cable paths | Sonnet · Medium |
| 5 | **lost work** (not new: 0.2.114 the same) | `blender/reimport.py` `match` (made-name groups: rules 2/3 use `move_tolerance` on `pos`) and `_made_assemblies` (222: `(ro["pos"] - rn["pos"]).length > tol`) | **Mesh model update: all work on a group without a name in the file is lost once that group moves.** glTF with groups A/B/C, named parts B1, B2; work on B (Hide step, hidden in Structure, joint "B1 turn" on B1); the new revision moves group B by 100 mm: named group → "6 parts kept", all kept; unnamed ("Node 4") → "4 kept, 2 new, 2 missing", Hide step target gone, hidden state lost, **joint deleted**. Also 0162's open point re-measured: only B left → "2 kept, 4 missing", Hide target None. | **(helper)** C/`e3_mesh_groups_moved.py`; C/`e3b.py` with v0.2.114 the same | A part with its own unique name inside a made-name group pairs by name with no place limit; a made-name group pairs through its parts' votes (or their common shift), not its origin. | import | Opus · Medium |
| 6 | **wrong result** (not new; visible since 0.2.129) | `web3d.Job.steps` reads the parts at rest (`vessel_motion.at_rest`) and the cable tube in the cable part's coordinates; only the page's vessel motion puts that back | **Web page with vessel motion off:** "Vessel motion" unticked at export, or the visitor switches it off in the menu → the laid sea cable dips **0.78 m into the seabed** or floats **0.85 m above it**, moving with the pitch (up to 1.14 m from the app; with vessel motion on ≤ 1 mm). test_sea, ROUGH, built, 6 of 6 moments. | **(helper)** B/`e7b_novessel.py ROUGH` + `node vessel_cable.js out/e7/vc_novessel_ROUGH.html out/e7/app_novessel.json`; control `e7_vessel_cable.py` | Without vessel motion on the page, read sea-cable tubes in world coordinates; for the visitor's switch keep the vessel matrix on them (or hide the switch when a sea cable is in the file). | web 3D | Sonnet · Medium |
| 7 | **wrong result** | the re-bake (`rebake.steps`) redoes hoses and cables, not the camera track; 0.2.125's CHANGELOG says the re-bake "gives what Build gives" | **A camera that rides the hull keeps the old sea's heave after a re-bake.** Small demo, CALM → ROUGH at the last frame, compared with a Build at ROUGH: 285 of 292 key/shape arrays identical (every cable, hose, joint key, all 47 lay-label texts); "Animation camera" frames 157–273 (the RIDE on the HULL 6–9 s and the MOVE that starts where it ends) up to **1.48 m** (z) / 0.61 m (x) off. | **(helper)** A/`s9_demo_rebake_all.py rebake\|build`, `s9_cmp.py` | When a step RIDEs / follows a PATH / AIMs at a moving part, the re-bake rebuilds the camera keys too, or says "Build again". | cable paths / scenes | Sonnet · Medium |
| 8 | **wrong result** (new with 0154) | `paths_sea.sync_bed` / `_speed_ms` / `moves_by_time` (paths_sea.py:161–231): one constant `weather.vessel_speed`, and only with Weather & time on | **A sea cable's seabed ignores "Vessel at work".** test_moving, 3 kn: Vessel at work Still → the wake is 0 but the seabed still sails 17.78 m aft in 289 frames; a step Ahead → Still at 4 s → the wake stops, the seabed goes on at 3 kn (6.11 / 9.20 / 12.29 / 17.78 m at frames 100–289); step Ahead 1 kn → wake 1 kn, seabed 3 kn; Weather & time off → wake 3 kn, seabed 0 m (0154's CHANGELOG: the speed works with Weather & time off; the tooltip: "the one the wake shows"). | **(re-run)** A/`s4_work_vs_bed.py` (the numbers above); **(helper)** A/`s4b_weather_off.py` | Drive the bed from the keyed `fr_vw_ahead` channel (or `vessel_work.speed_now`), whether or not Weather & time is on. | cable paths / scenes | Sonnet · Medium |
| 9 | **slow, estimate wrong** (new since 0.2.121 on the demo as built since 0153/0166) | `web3d.py` `_steps_inner` / `Baker.own` (:539) bake marine looks per part; `core/web3d.py` `own_estimate` (:96) shown at `ui_web3d.py`:84 counts texels, not bakes | **Web export of the demo: 2,174 s instead of 96 s.** 264 parts get their own marine bake (~7 s each), mostly wind-park parts baked again for each of the 9 turbines (CLAMP J-TUBE ×36, TP SLEEVE ×9, J-TUBE ×9 …): 802 textures, 22.3 MB glb (10.0 MB without). The panel said "Normal … bake about 34 s (Fine +101 s)". An animated export adds the same ~1,900 s. Machine under load 8–12 on 4 cores: seconds inflated, the ratio 23× is what counts. The page still loads (8.3 s vs 5.5 s, no errors). | **(helper)** B/`e4_demo.py 0 LIVE PROJECT NORMAL 1 0` (log `out/e4_marine_static.log`: "marine own-bake 264", "seconds 1890.6"; main session read the log); `NOMARINE=1` for the comparison; `e6_panel.py` prints the estimate | Copies with the same mesh, looks and world height / turn share one bake; the estimate counts the per-part bake time (or warns above N parts). | web 3D | Opus · Medium |
| 10 | slow | `flex._motion_bake` drops its kept read in `finally` (flex.py ~1830), so `paths._motion_bake` passes through every frame again (reading; not profiled) | **The background re-bake route** (scripts, tests, PC check, the queue) takes **606 s** on the small demo against 221 s for a Build; the window's job 193 s, but one step (the cable solve) blocks **20.4 s** with no redraw (0160's open point measured ~16 s). Same load as row 9. | **(helper)** A/`s9_demo_rebake_all.py`, `out/measure.json` | The background route through `rebake.run_now` (one pass); split the final cable solve into steps. | Flex / cable paths | Sonnet · Low |
| 11 | small (leftover) | `spool.web_end` (spool.py:1245) removes the full-layer solids by a timer, only when Blender has a window | **A web export run as a script** (PC check, `make_site_web_models.py`, the render kit) leaves the hidden "FR spool solid …" objects in the project (2 on test_spool, 7 on the demo, also after Cancel at each of 9 points); the next opening draws every spool again (demo 2.8 s vs 2.1 s). | **(re-run)** B/`e3_spool.py`: "solids now: Carousel, Drum", "upgrade needed after: [True, True]"; B/`e5_cancel.py` | Without a window, remove them at once. | web 3D / Flex | Sonnet · Low |
| 12 | small (layout, since 0.2.131/0.2.140) | `fr_tools.js` `placePanel` (:206) acts only at width ≤ 600; `frPage.layoutCheck` (`fr_player.js`:962) leaves out `#fr-tpanel` | **Phone sideways:** the part tools' panel (Measure + Cutaway) covers the saved-views row: 844×390 and 667×375 on the sea page cover "Iso front-right" and "Under cam" whole, the time line by 14 px; demo page 3–18 px over 3 views. Upright: no overlap. | **(helper)** B/`phone_tools.js out/e2/sea_SOFT_1.html out/seag "soft=0&quality=PHONE&auto=0"` → `out/seag_844x390_s.png` | Place the panel above the stack on a compact screen too; add it to `layoutCheck`. | web 3D | Sonnet · Low |
| 13 | small (wrong text) | `web3d.part_labels` (:749) | On an **animated** page a label's live fields (0173) stay at the exported frame: the demo's cable card reads "Lay speed 0.0 m/min" while the lay plays. | **(helper)** B/the cards in `out/e4/nm_demo_a1_*.glb` | Animated export: drop the field lines or say "at the start". | web 3D | Sonnet · Low |
| 14 | small (not new) | `paths_sea.numbers` (paths_sea.py:867) | **Lay data after let go:** once the cable lies on the seabed (height 0) the panel, labels and videos show Top/Bottom tension **16,802 kN** (frame 260: 0.55 kN). 0.2.114 showed 16,919 kN in the panel; since 0.2.141 it reaches labels. | **(helper)** A/`s5b_numbers_letgo.py`, `s5c_numbers_old.py` | Height ≈ 0 or nothing hanging → "–". | cable paths | Sonnet · Low |
| 15 | small | `spool.renamed` (spool.py:149) does not pick a free name (as `paths.cable_renamed` does) | **Two drums can share a name:** carousel renamed "Drum" → both find all 15 layer objects; removing the carousel deleted the drum's layers too (drawn again at the next update). No lasting damage seen (unsure). | **(helper)** A/`s15_spool_dup_name.py` | Free name on rename. | Flex parts | Sonnet · Low |
| 16 | small (cause unsure) | `tc_person.bake` → `_floor` + `core.stand_spot` (cell 0.04 m, `WORK_ROOM` 0.25 m) | **The tool-change operator stands 4 cm closer after a model update with nothing changed** (0, −0.60) → (0, −0.56), and stays there after Build, save and reopen; bounds identical. Probably the cabinet front lies on a cell edge of the floor map and rounding decides. Not checked whether it clashes. | **(helper)** C/`e8b.py` (+ `e8d.py`, `e8e.py`) | Round the floor map away from cell edges (or snap with a tolerance), so the same model gives the same spot. | people | Sonnet · Low |
| 17 | slow (small) | `ui_web3d.py` estimates: each cache key walks every part (`objects()` with `visible_get()`, `needs_own_bake` per part) | One draw of the Web 3D panel costs ~45–60 ms on the small demo even with cached estimates (`marine_estimate` 28–30 ms, `can_export` 13–17, `light_estimate` 15–17). | **(helper)** B/`e6_panel.py` | Key the caches on a cheap change counter. | web 3D | Sonnet · Low |

**Seen in passing, not checked:** `surroundings.add_prop(…, "PERSON")` on the demo put the person at z −8.57 m (about the
hull bottom on the open sea; people are not on the web page by design). Release 0.2.135 (0176) was never published: its
`main` commit's run failed on a TASKS.md row, the next release was 0.2.136 (the owner's apps skip from 0.2.134 to
0.2.136; nothing is lost – CLAUDE.md section 8 already has the lesson). The tour stop `spool` (task 0184): its set was built
six times here (made by 0.2.114 / 0.2.125 / 0.2.135, built in the old and the new code, Blender as a module, 4 cores
under load) – no "no longer touches GUIDE SHEAVE" warning in any of them.

**0147's rows re-checked – all hold**
- Row 1 (light bake with handlers on): `pause_live` around the bake; Sea + vessel + Soft + marine export: no project
  difference, handler counts unchanged, nothing left after Cancel at 9 points (B).
- Row 2 (renamed drum / cable / joint + update): Build → update → Build → rename all three → update → Build → Clear keys
  → save / reopen → Build: 0 failures, 7 + 8 layer objects each time, drum 284.34 rad at the end each time (A); and in
  the **real app** (main session, `spool_undo.py`): Build, model update, Build, undo ×2, redo ×2, save + reopen – drum
  30.77 rad, level wind −0.104, 19 spool objects at every stage.
- Row 3 (unnamed groups, one removed): holds for its case (C); row 5 above is the moved-group case.
- Rows 5, 8, 20: their tests pass; label fields follow the water level (A). Row 6: the re-bake at the last frame equals a
  ROUGH Build for every cable, hose, joint key and label (A) – only the camera differs (row 7 above).
- Rows 7, 9, 13, 21b, 21c: the 0162 tests pass (C; 0147's own scripts were gone, so not an independent re-run).
- Rows 4, 17, 18, 21g: `tests/test_task0163_fixes.py` passes; zip names with `\` and NUL refused with zipfile acting
  as on Windows (C). PowerShell / .bat not run.
- Rows 10, 11, 14, 15, 16, 21d, 21e, 21f: hold (B: tests pass; "Under cam" stays at eye y −6.00; 13 junk settings +
  13 junk links → pages ready, 0 errors; no `off=shadows` from a software browser; screenshot name kept).
- Row 12: Build names all five values it puts back (A). Row 19: a job now, but one step still blocks 20 s (row 10).
  Row 21a: worst there-and-back 0.085 m (was 0.87 m) (A).

**Old projects (main session):** the test tour made with **0.2.114 (38 files), 0.2.125 (41) and 0.2.135 (43)**; each
file opened and every animation built once with its own code and once with 0.2.141; every object's place, hiding and
evaluated vertex count compared at 4 frames, and every collection of settings counted. Identical except intended
upgrades: spools get their layer objects instead of the solid (0174); the sea material is made again once (MAT_VERSION
4 → 5, 0154: the vessel set's first Build 0.06 → 3.4 s for the 0.2.114 file, 1.8 s for 0.2.125, none for 0.2.135); the moving cable has 26,260 instead of 24,920 points (a new
project made in 0.2.141 has the same); an assembly-sequence rider mid-step 30 mm elsewhere (0162's fix of 0147 row 13;
same end place). Warnings identical. Props and people saved by 0.2.114 open with the new look and walk (C).

**Also run, no fault found:** scripts off (real Blender `-Y` vs on): the small demo (3,269 objects × 9 frames), built
spool, tracks, test_moving and the operator project – 0 differences, every one of the demo's 856 drivers a simple
expression (A, C). Names on hide-names pages: none in the .glb or settings JSON of the crane, sea model and demo (B).
Project after a web export identical (frame, selection, visibility, materials, handlers) apart from row 11 (B). A model
update with spools, then undo / redo / save in the real app (row 2 above). Mesh-group removal (0147 row 3). Watermark
paths in the queue's copy, by reading (C). 0178's Task Manager code read: no fault seen, not runnable here (C).

**What changed:** only this report and `TASKS.md` (0183 → done, its rows listed under "Problems found"). No app code,
test or tool; no version; no test run.

**Tested and measured** (4-core web machine, shared by the main session and three helpers: load average 7–17 most of the
time, so **seconds are inflated** – compare ratios, not the reports' numbers):
- Small demo (`demo.build_project(small=True)`, now 4,481 frames, was 3,806): made in 486 s; Build 221 s; model update
  of the vessel 108 s; re-bake job 193 s (0160: 65 s on 3,806 frames) / background route 606 s (row 10).
  `tools/measure_cables.py`: Build 256 s (0174: 96.7 s), playback after Build 147.7 ms/frame (0174: 38.6), live
  posing 254.5 ms/step (134) – under load, **not comparable**; memory 1,335 / 1,815 MB after opening / Build (0174:
  1,319 / 1,748), saved project 226.5 MB (226.2) – comparable, unchanged.
- Web export of the small demo: static 2,174 s as made (96 s without per-part marine bakes); animated without them
  515 s for 4,481 frames = 0.115 s / frame (0143: 0.121 s / frame); crane Soft + marine 44 s (0161: 25.5 s unloaded).
- Height map (C): toolpath tour model 4,480 moves, cut to the end 17.8 s (exact 123–132 s), 133,950 triangles (exact
  65,406); 0167 reports 9.6 s unloaded for its 7,244-move program.
- A re-measure on a quiet machine is open (a worker alone in a session).

Subagents: three helpers (Opus), each read and ran its area and returned rows with scripts; the main session re-ran
rows 1, 2, 8 and 11 with their scripts (same numbers), proved rows 3 and 4 itself (row 3 also by A), read the code of
every row, and ran the old-project comparison and the real-app undo / save runs. Not re-run here: rows 5–7, 9 (log
read), 10, 12–17.

**Not tried:** the full-size demo; a model update of the demo to a *changed* STEP; Soft light / Everything baked or
Marine detail Fine on the demo (hours under this load); a real queue run with watermark, people and every paint scheme
(read only); a real Windows PC (kit window, Task Manager name), a graphics card, a real phone; the window's modal web
export with Esc; the full test tour's automatic run.

**Open points / follow-up tasks – proposed grouping for the lead**
- **A – Cables after Build: undo, save and model update** (cable paths / Flex lane, Opus · Medium): rows 1, 3, 4, 7, 8,
  10, 14, 15 (row 1 is the big one; rows 3 and 4 are small and share a real-app test).
- **B – Fast 3-axis hole** (milling lane, Opus · Medium): row 2, first – it is new and visible in a render.
- **C – Mesh model update, moved unnamed groups** (import lane, Opus · Medium): row 5 + 0162's open point.
- **D – Web 3D follow-ups** (Web 3D lane, after or with 0175, Opus · Medium): rows 9, 6, 11, 12, 13, 17.
- **E – small people fix** (people lane, Sonnet · Low): row 16, and look at the person's height on the demo.
Order: B (new, visible), A rows 3 + 4 (a saved file with hidden parts), A row 1, D row 9 (the demo's web export), C,
the rest. Leftover: no branches pushed, no worktrees in the repository (old versions were checked out in the scratch
folder and removed).
