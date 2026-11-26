# 0352 – Compatibility kit: a format number on every project, one upgrade chain, test projects that later versions must open

**Who:** worker · **Status:** running · **Branch:** `task/0352-compatibility-kit`
**Started by:** lead, 25 Nov 2026 23:5x (owner 25 Nov 22:4x–22:5x: strict backward compatibility from the baseline) ·
**Model:** Opus · effort High · Claude Code on the web, environment "CAD-render-animation" · **independent review** (a
helper agent that did not write the code tries to break it – section 2, "Subagents")
**Area:** new lane **Compatibility** – new `fresing_render/core/compat.py` (format number, the saved-data list, the
chain of steps – plain Python), new `fresing_render/blender/compat.py` (its own load / save handlers, the message), new
`tools/make_compat_project.py`, new `tests/test_compat*.py`, `tests/data/compat/` (README only for now – see step 5);
additive: `blender/props.py` (the stamp fields), `__init__.py` (register the module), CLAUDE.md sections 6 and 7 (the
rules and the release step), CHANGELOG + version files.
**Not:** `blender/handlers.py` (0326 is running there – register your own handlers in `blender/compat.py`, first in
Blender's lists, as `measure.py` and `welds.py` register their own); **the existing load-time upgrades in ~32 files stay
where they are** – you list them (step 1), you don't move or delete them (pre-baseline ones go with the per-lane cleanups
0350a, b …); 0353's outputs (3D page, House file, Viewer file); the Save / Save As code of 0291 except one call if step 4
needs it.

## Goal

From the **baseline** on (CLAUDE.md section 6), every project saved by Fresing Render keeps opening – with the same data
and the same look – in every later version. This task builds the kit that makes that checkable instead of hoped for: a
**format number** on every save, **one ordered chain** where every future change of saved data gets its upgrade step,
**test projects** that every later version must open, a **plain message** for a project from a newer app, and the
**list of what a project stores** (choices) against what is rebuilt (derived data).

## Background (read first – only the parts named)

- CLAUDE.md section 6: **"Old projects – the baseline"** (before the baseline an older project only has to open without
  a crash; no new upgrade code for pre-baseline projects) and **"Keep saved data small"** (choices are stored; bakes,
  caches, app-made meshes, liquid, cable shapes, baked light are rebuilt, never upgraded); the **assets-pack** rule
  (`fr_asset`, `assets_source` – 0355 adds them).
- TASKS.md rows 0350 (per-lane cleanups) and 0353 (outputs – not this task).
- Today's load-time code: `blender/handlers.py` `_on_load` and `_upgrade_steps` (≈ line 140–215 at 0.2.260) and the
  `load_post` handlers of about 32 files (`grep -rln load_post fresing_render`); `materials.LOOK_VERSION`, the
  surroundings' `MAT_VERSION`, `props_scale.upgrade`, `fr_prop_ver`, the tool-mark / weld version stamps (0344 report
  section 4 lists the look ones).
- The save handlers in `handlers.py` (`_before_save` / `_after_save`), backups (`blender/backups.py`), the queue's copy
  (`blender/queue.py`), project names / Save As (0291).
- `tests/data/old_project_0_2_195.blend` and the tests that open it (52 test files mention old projects – 0350's list).

## What to do

1. **Findings first (in the task file, then go on – no stop):** a table of every load-time action today, one row each:
   file / function, what it does, and its kind – **(a)** upgrades stored data (a choice), **(b)** rebuilds derived data
   (allowed, not versioned), **(c)** only for pre-baseline projects (0350 deletes it in its lane), **(d)** not an upgrade
   (subscriptions, caches, UI). And the **saved-data list**: every property group, custom property and datablock stamp a
   project stores today, marked *choice* or *derived*; derived data that is saved today (and so grows projects or needs
   upgrading) becomes a row for the matching 0350 cleanup. Keep both tables short and exact.
2. **The format number** (`core/compat.py`): `FORMAT` (an integer; start at 1) + the app version, stamped on the scene at
   **every save** (also backups and the queue's copy) by a `save_pre` handler in `blender/compat.py`. A project without
   the stamp = made before the kit. The baseline's format number is written into CLAUDE.md section 6 by the lead when the
   baseline is released; until then the constant `BASELINE_FORMAT` is `None`.
3. **One ordered chain** (`core/compat.py` + `blender/compat.py`): steps registered as `(from_format, to_format, name,
   function)`, run in order on load **before every other Fresing load handler** (insert first in `load_post`), each step
   in its own try / except with one plain line (as `_on_load` does since 0055), the project then stamped with the
   current format in memory. Starts **empty**: at the baseline every kept project is at the baseline format. Below the
   baseline (or no stamp) the chain does nothing – today's per-lane code still runs until 0350 removes it. A test proves
   the order, the one-failing-step rule and that a step runs once.
4. **A project from a newer app** (format above the app's): open it to look at, **never damage it** – a plain message in
   the app's own style ("Saved by Fresing Render 0.2.X, newer than this one (0.2.Y). Update the app to work on it –
   Fresing > Updates. Saving is off so nothing in it is lost.") and saving it refused or turned into a copy with a new
   name – find the safest way the app's save path allows (0291 owns Save / Save As; Blender cannot cancel a save from
   `save_pre`). Also the queue, backups and the model update must not write into it. Tests for each.
5. **Test projects** (`tools/make_compat_project.py`): makes a **small invented project in the running app version**
   that uses every function family that stores data (`core/functions.py` `FAMILIES` – a test fails when a family that
   stores data is missing from the maker), saves it with a JSON summary of its stored choices (the saved-data list of
   step 1) and a small reference picture (Cycles on the processor, tiny, a few samples – as other picture tests do).
   `tests/test_compat_projects.py` opens every project in `tests/data/compat/`, runs the chain, and compares the
   summary (exactly, or by the step's documented change) and the picture (with a tolerance). **One test project per
   format number, not per release** (a release that does not change the format saves the same structures; one per
   release would add tens of MB a month to the repository) – each under ~1 MB, no packed pictures, no bakes. Before the
   baseline nothing is kept: CI runs the maker in the current version and opens its result (save → open → same summary
   and picture), and `tests/data/compat/README.md` says how projects get there. **The release step** (CLAUDE.md section
   7): a release that raises `FORMAT` (from the baseline on) runs the maker and commits `format_<n>.blend` + its
   summary and picture; the precheck fails a raised `FORMAT` without them and without a chain step.
6. **Rules in CLAUDE.md** (section 6, short): a change in what a project stores = raise `FORMAT` + one chain step + the
   test project (from the baseline on); derived data never gets a step; never a new load-time upgrade outside the chain
   once the baseline is set. The lead reviews the wording.
7. **Independent review** before merging: an agent that did not write the code tries to break steps 2–5 (a crash in a
   step, a newer project through backup / queue / model update / Save As, a project without the stamp, two scenes, a
   library-linked scene). Findings back to the author; the report says what it found.
8. CHANGELOG in plain words (the user sees only step 4's message). No guide chapter beyond one short "Projects from a
   newer version" line in the user guide's FAQ / troubleshooting part, with its anchor.

**Running beside you:** 0355 (assets pack P2) adds `assets_source`, `assets_version` and `fr_asset` – whoever merges
second puts them in the saved-data list. 0326 owns `handlers.py`; 0346 / 0348 add load handlers of their own – your
handler must run before theirs.

## Done when

- [ ] Steps 1–6 on `main`; the format number is on every save; the chain runs first and is empty; a newer project is
      never damaged; the maker covers every data-storing family and its result opens the same in CI.
- [ ] The findings tables are in the report, with the (c) rows and the saved derived-data rows grouped by lane for
      0350a, b …
- [ ] The independent review's findings are fixed or listed; the full run on GitHub is green.
- [ ] Report filled in, merged, released (section 7).

## Not in this task

Moving or deleting today's upgrades (0350 per lane); outputs' format numbers (0353); the baseline itself (the lead sets
it when 0344's groundwork, the import lane, 0345 and the other "before the baseline" tasks are in); the assets pack
(0354–0365). Never the owner's files; never his employer's name.

---

## Findings (step 1)

Mapped by a read-only helper agent from the code at 0.2.260, spot-checked by the worker. No row is kind (a): nothing at load upgrades a choice a project of today still needs – every upgrade is (c), for one older version range. Lanes as TASKS.md names them ("Flex parts" = cables, spools, tracks).

All paths are under `fresing_render/blender/`. Kinds: **a** = upgrades stored data still needed for current projects · **b** = rebuilds derived data or view state · **c** = only for projects older than a version (pre-baseline) · **d** = not an upgrade.

### Table 1 – Load-time actions

| file:function | what it does (≤ 15 words) | kind | lane |
|---|---|---|---|
| handlers.py:_on_load → logic.drop_tree_cache, _IGNORE.clear | Forgets the cached part tree and the click-ignore list | d | Looks |
| handlers.py:_on_load → _subscribe | Subscribes the message bus again so a click selects the whole subassembly | d | Looks |
| handlers.py:_upgrade_steps "acceleration" → gcode.upgrade_accel | CNC set-up without `fr_accel_v`: sets `use_accel` off and adds stamp `fr_accel_v=1` | c (< 0.2.83) | Machining |
| handlers.py:_upgrade_steps "matrices" → build.ensure_bases | Parts with no `fr_cad_basis`: stores the current matrix as `fr_cad_basis` and `fr_rest_basis` | c (< 0.2) | Import |
| handlers.py:_upgrade_steps "part IDs" → build.repair_uids | Gives each copy of a STEP imported twice its own `fr_uid` scope | c (< 0.2.44) | Looks |
| handlers.py:_upgrade_steps "paint faces" → faces_off | Sets `face_painting = False` | d | Looks |
| handlers.py:_upgrade_steps "joint drivers" → joints.upgrade_drivers | Adds the small-number BIAS fix to joint motion drivers that do not have it | c (< 0.2.30) | Motion |
| handlers.py:_upgrade_steps "looks" → logic.upgrade_looks | Rebuilds group materials that are not current (`fr_look_version` < 4 or settings differ) | c (comment: < 0.2.39; LOOK_VERSION 4 = < 0.2.237) | Looks |
| handlers.py:_upgrade_steps "rule set" → rule_sets.on_load | No `rule_set` yet: sets the default rules and a rule set, and writes a message | c (< 0.2.13; untouched rules < 0.2.8) | Looks |
| handlers.py:_upgrade_steps "tool changer" → toolchange.upgrade | A G-code step with `gcode_atc` and no `changer` stored: sets `cnc.changer = "ATC"` | c (< 0.2.45) | Machining |
| handlers.py:_on_load → props_scale.upgrade | Props with `fr_prop_ver` < 1 get a two-level mesh (`rebuild`) | c (< 0.2.124) | Scene & Render |
| handlers.py:_on_load → surroundings.fix_view_clip | Sets the clip end and start of the 3D views to the scene's reach | b (view state) | Scene & Render |
| handlers.py:_on_load → surroundings.refresh_view_cuts | Puts the 0.2.153 sea view cut back on the new way and removes the old "FR view cut" group | c (0.2.153 only) | Sea |
| handlers.py:_on_load → queue.take_note | Shows "delayed queue start lost" in `last_message` | d | Motion (queue) |
| handlers.py:_on_load → queue.find_live / sync / ensure_polling | Follows a render queue that is still running and copies its job status into `scene.fresing.queue` | d | Motion (queue) |
| backups.py:_on_load | Restarts the backup clock, records the open time and whether the project is unsaved, starts the restore-question timer | d | Backups |
| cameras.py:_pixel_angle_on_load → update_pixel_angle | Writes the scene's `fr_pixel_angle` from the camera (finishes read it) | b | Looks |
| clash.py:_on_load | Clears the run state, hides the red overlay and stores a cheap key for checked scenes | d | Clash |
| coolant.py:_on_load | Clears the `_HOSE_KEY` and `_WET` caches | d | Machining |
| copy.py:_on_load | Empties the copy clipboard (`CLIP`, `LAST`) | d | Place |
| first_setup.py:_on_load | Closes the first-start set-up windows the opened file brought along (timer) | d | Start & learn |
| flex.py:_on_load → forget | Clears the solver caches (and `flex_avoid`) | d | Flex parts |
| form_window.py:_on_load | Clears form errors and closes form windows the file brought along (timer) | d | Settings |
| hub_progress.py:_after_load | Removes the build-progress card | d | Learning |
| lifting.py:_load_post → forget, `_LIB["items"]=None` | Clears the lifting caches and the library list | d | Lifting |
| lifting.py:_load_post → upgrade | Crane poses with no stored places get `joints_only = True` | c (< 0.2.166) | Lifting |
| linkages.py:_on_load → forget | Clears the mechanism solvers | d | Motion |
| machining.py:_on_load → `_RUNTIME.clear`, chips.forget, gcode.forget | Clears the milling, chips and G-code caches | d | Machining |
| machining.py:_on_load → lock_interface | Turns on `render.use_lock_interface` in scenes where milling is on | c (comment: milled before 0.2.43) | Machining |
| machining.py:_on_load → _schedule → update_if_needed | Timer reads the milling preview again when it is stale | b | Machining |
| measure.py:_after_load | Clears the measure data, the tool state, the rectangles and the batch | d | Measure |
| ops_make.py:_on_load | Clears `winplace` and starts a timer that keeps reading the app windows' sizes and places | d | Start & learn |
| ops_render_view.py:_on_load → remove_leftovers | Deletes temporary view cameras (marked with `VIEW_MARK`) that a crash left behind | b | Start & learn |
| ops_setup_crane.py → setup_crane.forget (load_post) | Clears the part-name lookup cache | d | Lifting |
| ops_tour.py:_after_load | Starts a timer that goes to a pending test-tour stop | d | Quality & delivery |
| paths.py:_on_load → forget | Clears the cable caches (and `paths_sea`) | d | Flex parts |
| paths.py:version_scene → version_names | Cable items with no `name_was` get `name_was = name` | c (< 0.2.125) | Flex parts |
| paths.py:version_scene → version_anchor | Resets a built project's sea-cable touch-down at frame 1 once; stamp `fr_cable_anchor` | c (built by 0.2.104–0.2.112) | Flex parts |
| paths.py:version_scene → version_settle | Let-go sea cables with `sea_settle` never set get 0; stamp `fr_cable_settle` | c (≤ 0.2.109) | Flex parts |
| paths.py:_on_load → _check_opened | In a built project, `vessel_motion.follow` solves hoses and cables again if they are stale | b | Flex parts |
| people.py:_on_load → forget | Clears the people plan cache | d | Scene & Render |
| project_lock.py:_after_load → _take | Writes or reads the project's "in use" lock file | d | Quality & delivery |
| project_name.py:_forget | Forgets the project names already proposed in this session | d | Settings |
| spool.py:_on_load → forget | Clears the spool caches | d | Flex parts |
| spool.py:_on_load → upgrade | Spools with a solid, or `fr_spool_draw` ≠ 2, are drawn again as rope layers | c (< 0.2.139) | Flex parts |
| tracks.py:_on_load → forget (also undo/redo) | Clears the track inputs cache | d | Flex parts |
| ui_header.py:_on_load → put_layout_right + _tab timer | Opens the side panel on the Fresing tab and sets the left panel's width | d | Start & learn |
| ui_header.py:_on_load → _restore_preview | In a tour or demo project, sets Live preview to the user's last choice | d | Start & learn |
| ui_header.py:_on_load → editors.on_load | Turns Region Overlap off and hides Blender's right-hand editor column (timer) | d | Start & learn |
| ui_header.py:_on_load → ops_setup.restore_tabs | Puts Set-up windows back on their "Set-up" tab (timer) | d | Start & learn |
| usage.py:_on_load → project_changed | Applies the personal hides and picks the session's declutter prompt | d | Usage |
| vessel_motion.py:_on_load → sync | Clears the signatures; rebuilds the rig and constraints when `fr_key` differs | b | Sea |
| waycover.py:_on_load → migrate | Moves the old single `waycover` into `waycovers[0]` | c (< 0.2.61) | Way-cover |
| web3d.py:_changed (load_post) | Raises the counter that the panel's estimate cache depends on | d | Web 3D |
| welds.py:_after_load | Clears `_CACHE` | d | Welds |
| workspaces.py:_on_load → on_load → library, ensure | A project with no `ws_name` gets the default workspace (older tour or demo projects: "all") | c (< 0.2.152; tour/demo < 0.2.164) | Start & learn |
| workspaces.py:on_load → take_in | A project saved by someone else opens in the user's own workspace; theirs is kept | d | Start & learn |
| workspaces.py:on_load → apply | Sets the Client-view lock and Blender's own tabs as the workspace says | d | Start & learn |
| workspaces.py:_on_load → panels.on_load | Folds the sections or restores them from `panels_open`; sets the tab to ALL | d | Start & learn |
| materials.LOOK_VERSION = 4 (`fr_look_version` on materials) | Checked at load through logic.upgrade_looks and at every material build | c (< 0.2.237) | Looks |
| surroundings.MAT_VERSION = 5 (`fr_env_version`) | Not at load: environment materials are made again when the surroundings are built | b | Sea |
| props_scale VERSION 1 `fr_prop_ver` / GROUP_VERSION `fr_version` / MAT_VERSION `fr_prop_mat` | `fr_prop_ver` is checked at load (row above); the group and materials are remade when built | b | Scene & Render |
| toolmarks.GROUP_VERSION = 3 (`fr_toolmarks_version`) | Not at load: "FR tool marks" is rebuilt when a material is built (ensure_group) | b | Machining |
| weld_looks.LOOK_VERSION = 3 (`"v"` in `fr_weld_look`) | Not at load: a weld material whose look key differs is made again | b | Welds |
| weather.STEP_VERSION `fr_wx_v` on a step | Not at load: a step without it is read without the 0299 fields | c (< 0.2.228) | Scene & Render |
| fade GROUP_VERSION 4, look_adjust VERSION 1 (`fr_adjust_version`), section GROUP_VERSION 1 | Not at load: the node groups are made again when built | b | Looks / Cutaway |
| paths / tracks / spool node-tree VERSION (2, 2, 2 + LAYER 1), person_rig `fr_rig_ver`, toolchange `fr_glove_ver` | Not at load: the trees, rig or glove are made again when built | b | Flex parts / Scene & Render / Machining |

### Table 2 – What a project saves

| name / where | what it holds (≤ 12 words) | choice / derived | lane |
|---|---|---|---|
| `scene.fresing` import_quality, import_up_axis, import_cache_search | Import settings | choice | Import |
| `scene.fresing` brand_*, still_logo*, wm_* | Brand kit, logo on stills, watermark | choice | Scene & Render |
| `scene.fresing.tree` (FRTreeItem) | Rows of the 2 Structure list | derived, **saved** | Looks |
| `scene.fresing` tree_depth, tree_search, isolated, pick_mode, small_part_mm | Structure view settings | choice | Looks |
| `scene.fresing.groups` (FRMaterialGroup), group_aliases, rules, rule_set, rule_set_data, schemes (FRScheme/FRSchemeLook) | Material groups and their looks, sorting rules, paint schemes | choice | Looks |
| `scene.fresing.project_materials` (FRProjectMaterial) | The project's own material list (0273) | choice | Looks |
| `scene.fresing.found`, find_text, find_in_selected, unmatched | Looks search results and the count of unmatched parts | derived, **saved** | Looks |
| `scene.fresing` face_group, face_only_copy, face_painting | Face painting tool state | choice (face_painting is reset at load) | Looks |
| `scene.fresing` background*, lighting, sky_weather, hdri_path, light_*, sun_elevation, exposure, floor*, env_detail | Light look, 360° photo, floor | choice | Scene & Render |
| `scene.fresing` sea_*, water_level, photo_*, env_show_in_view, operator_visible, props_*, people_preview | Sea and surroundings settings, props shown and their detail | choice | Sea / Scene & Render |
| `scene.fresing` view_*, camera_*, turntable_*, pv_*, out_*, quality, use_gpu | Camera, turntable, product video, output settings | choice | Scene & Render |
| `scene.fresing` last_render, last_message, rendered_once, next_hidden | Last render path, status line, UI flags | derived, **saved** | Start & learn |
| `scene.fresing.joints` (FRJoint) + frame/motion empties, drivers; show_joints | Joints, couplings, limits | choice | Motion |
| `scene.fresing.cylinders` (FRCylinder), cyl_pick_*, mechanisms (FRMechanism/FRMechLink), mech_base, mech_kind | Cylinders and mechanisms | choice | Motion |
| `scene.fresing.poses` (FRPose/FRPoseJoint/FRPlace), visibility_sets (FRVisSet), shots (FRShot), active_shot, explode_* | Poses, visibility sets, saved scenes, explode settings | choice | Motion |
| `scene.fresing.lead_motions` (FRLeadMotion/FRLeadRow), lead_* | Lead motion sliders (`lead_last` = a "moved by" record) | choice | Lead motions |
| `scene.fresing.animations` (FRAnimation → FRAnimBlock, FRPictureCard, FRCamPathPoint) | Animation steps | choice | Motion |
| `scene.fresing` anim_baked; anim_restore_saved/pose/visibility/camera | Build state; the pose, visibility and camera from before Build | anim_baked derived, **saved**; restore = choice | Motion |
| `scene.fresing.callouts` (FRCallout), callouts_on, callout_size, xray_*, trails (FRTrail) | Labels, X-ray, motion trails | choice | Scene & Render |
| `scene.fresing.cuts` (FRCut/FRCutTarget), cut_new_shape | Cutaway slices | choice | Cutaway |
| `scene.fresing.queue` (FRQueueJob), queue_delay_*, queue_at_* | Render queue jobs | choice | Motion (queue) |
| `scene.fresing` queue_dir, queue_pid, job status fields | The running queue's folder, process and status | derived, **saved** | Motion (queue) |
| `scene.fresing` report_new, report_missing, report_notes, report_title | Report of the last model update | derived, **saved** | Motion |
| `scene.fresing.milling` (FRMilling: bits, workpiece, finished, detail, cut_look …) | Milling set-up | choice | Machining |
| milling stock_mesh, cut_mesh, path_sig; ID props `fr_wp_m`, `fr_wp_f0`, `fr_carrier_m`, `fr_air_o/d`; bits `fr_o/fr_d/fr_t`; mesh `fr_milled`, `fr_cut_slot`, `fr_cut_key` | Milled workpiece mesh, CAD copy, sampled paths | derived, **saved** | Machining |
| `scene.fresing.cnc` (FRCnc, FRCncTool, FRCncPocket, zero_empty, changer, use_accel, rotary) | CNC machine, tool library, ATC pockets | choice | Machining |
| cnc ID props `fr_corners`, `fr_feeds`, `fr_turns`, `fr_g43`, `fr_tools`, `fr_air`; step `fr_gc_from` | G-code tables written at Build | derived, **saved** | Machining |
| cnc `fr_gcode_abs`, `fr_tool_table_abs`; `fr_accel_v` | Absolute program and tool-table paths; old-project stamp | choice; stamp | Machining |
| `scene.fresing.coolant` (FRCoolant, FRCoolantNozzle) | Coolant settings | choice | Machining |
| `scene.fresing.toolpath` (FRToolpath) settings; `result`, `program_sig` | Make-toolpath settings; last result as JSON | settings choice; result derived, **saved** | Machining |
| `scene.fresing.waycovers` (FRWayCover/FRWayCoverSection), `waycover` (old single) | Way covers (`waycover` = leftover from before 0.2.61) | choice | Way-cover |
| `scene.fresing.place` (FRPlaceSettings) | Place panel settings | choice | Place |
| `scene.fresing.clash` (FRClash) settings; `rows` (FRClashRow), `signature` | Clash check settings; the last result | settings choice; rows derived, **saved** | Clash |
| `scene.fresing.vessel` (FRVessel/FRVesselStill), vessel_work (FRVesselWork/FRVesselThruster) | Vessel motion, vessel at work | choice | Sea |
| `scene.fresing.flex` (FRFlex/FRFlexClip) | Hoses, cables and drag chains that follow the motion | choice | Flex parts |
| `scene.fresing.cables` (FRCable/FRCableContact/FRCableRider), cable_speed | Cables on their paths | choice | Flex parts |
| `scene.fresing.spools` (FRSpool/FRSpoolFollower), tracks (FRTrack/FRTrackWheel) | Drums, carousels, tracks and belts | choice | Flex parts |
| `scene.fresing.web3d` (FRWeb3D); last_path, last_html, last_text, last_size | Web export settings; record of the last export | settings choice; last_* derived, **saved** | Web 3D |
| `scene.fresing.weather` (FRWeather) | Weather and time of day | choice | Scene & Render |
| `scene.fresing.house` (FRHouse); last_bake, last_seconds, last_problems, last_text | House import; record of the last bake | choice; last_* derived, **saved** | House |
| `scene.fresing.lifting` (FRLifting/FRLiftCrane/FRLiftLoad/FRLiftPoint/FRLiftDensity), crane_setup (FRCraneSetup …) | Lifting plan, cranes, loads, crane set-up and charts | choice (rig_result, volume_mass derived, **saved**) | Lifting |
| `scene.fresing` ws_name, ws_data, ws_ticks, saved_by, panels_open, setup_kind, setup_step | Workspace, last saver, open sections, Set-up step | choice | Start & learn |
| `scene.fresing` model_count, bounds_valid, bounds_min, bounds_max | Number of models and model bounds | derived, **saved** | Import |
| `Mesh.fresing_decals` / `Object.fresing_decals` (FRDecal), `Scene.fresing_decal` | Decals per part and the decal panel settings | choice | Looks |
| `Scene.fresing_welds` (FRWeldSettings/FRWeld/FRWeldSeam); `cad_mesh` | Welds; the CAD bead mesh | choice; cad_mesh derived, **saved** | Welds |
| `Scene.fresing_measure` (FRMeasureSettings/Item/Pick) | Measurements (left out of the save unless Keep is on) | choice | Measure |
| `Object.fresing_person` (FRPersonSettings/FRPersonAction) | A person's pose, height, clothes and actions | choice | Scene & Render |
| `WindowManager.fresing_*` (first_setup, matpick, crane_make, tab, fold_open, keys_search, form groups) | UI state on the window manager | not project data | Start & learn / Settings |
| Part objects `fr_uid`, `fr_uid_scope`, `fr_kind`, `fr_root`, `fr_source`, `fr_imported`, `fr_name`, `fr_instance`, `fr_made_name` | Part identity and the link to the STEP | choice | Import |
| Part objects `fr_color`, `fr_cad_material`, `fr_cad_basis` | CAD colour, material name and matrix from the STEP | derived (STEP), **saved** | Import |
| Part objects `fr_rest_basis`, `fr_cad_parent` | Rest matrix and CAD parent while a joint carries it | choice | Motion |
| Part objects `fr_group`, `fr_group_manual`, `fr_excluded`, `fr_locked`, `fr_hidden`, `fr_tree_open`, `fr_sort_note` | Group, manual group, clean-up, lock, visibility, open rows | choice (`fr_group` from rules) | Looks |
| Roots and objects `fr_copy_group`, `fr_copy_frozen`, `fr_copy_of`, `fr_scenery`, `fr_no_clash`, `fr_clash_mesh` | Copies, scenery, objects left out of the clash check | choice | Place / Clash |
| Imported meshes + `fr_face_starts`, `fr_axes`, `fr_axis_faces`, `fr_mesh_key`, `fr_mesh_of`, `fr_ax_*` | Part meshes and their CAD face and axis data | derived (STEP), **saved** | Import |
| Meshes `fr_face_sets`, `fr_face_groups`, `fr_face_copy` | Painted faces | choice | Looks |
| Model roots `fr_stats`, `fr_import_notes`, `fr_update_stats`, `fr_bounds_cad` | Import and update statistics | derived, **saved** | Import |
| Joint motion empties `fr_value`, `fr_bias`, `fr_table`; tags `fr_cylinder`, `fr_mechanism`, `fr_solved` | Driver value copy, bias, follow tables, solved mechanism keys | derived, **saved** | Motion |
| Group materials + `fr_material`, `fr_color`, `fr_wear`, `fr_rust`, `fr_finish_set`, `fr_adjust`, `fr_look_version`; "FR adjust" group | Built group materials (stamp LOOK_VERSION) | derived, **saved** | Looks |
| Mesh `fr_fx_o/d/r/k`, `fr_ax_lo/hi`; scene `fr_pixel_angle` | Face data for finishes; the camera's pixel angle | derived, **saved** | Looks |
| Material wraps `fr_fade_wrap`, `fr_section_wrap`, `fr_weather_wrap` + "FR fade", "FR section" groups; object `fr_xray_look`, `fr_cut_<key>` | Fade, X-ray and section wraps; X-ray choice, cut membership | wraps derived, **saved**; `fr_xray_look` and `fr_cut_` choice | Looks / Cutaway |
| Build animation keyframes (parts, joints, cameras, weather; `fr_anim`), scene `fr_anim_print`, `fr_jumps`, `fr_weather_keys`, `fr_user_action/slot` | Keys and fingerprints of a built animation | derived, **saved** | Motion |
| "FR flex shapes" (+ `fr_flex_frames/per/first`, `fr_flex_ends*`), "FR flex" modifiers, "FR flex link", `fr_flex_guide_a/b`, `fr_flex_local`, scene `fr_flex_shapes`, `fr_flex_motion_key` | Hose shapes per frame, ends read at Build | derived, **saved** | Flex parts |
| "FR cable shapes <name>" (+ `fr_cable_frames/per/first`, `fr_cable_places*`, `fr_s`), "FR cable" trees, `fr_cable_pay`, `fr_cable_look`, scene `fr_cable_motion_key/water_key`, item `fr_let_go`, `fr_let_go_lay` | Cable shapes and places from Build | derived, **saved** | Flex parts |
| Cable item `fr_removed`, `fr_route`; `fr_drawn`, `fr_drawn_owner`, `fr_replaced_by` | Removed contacts, drawn route, replaced CAD part | choice | Flex parts |
| Spool objects "FR spool <name>", "FR drum rope", layers (`fr_spool`, `fr_spool_role`, `fr_spool_draw`), "FR spools"; "FR track loop <name>", "FR track run <name>" (`fr_c0`, `fr_local`, `fr_m`), "FR track" modifiers | Spool ropes and layers, track loops and runs | derived, **saved** | Flex parts |
| Scene stamps `fr_cable_settle`, `fr_cable_anchor` | Old-project cable stamps | stamp (c helper) | Flex parts |
| "FR Chips" collection, "FR Chips (on the table)/(fallen)", "FR Chip shapes", "FR Chips" group, "FR chips …" materials | Chips point clouds and their instancer | derived, **saved** | Machining |
| "FR CNC" collection: tool copies (`fr_cnc_t`, `fr_spec`, `fr_tip`, `fr_axis`), "FR hand" (`fr_open` keys), "FR toolpath" tubes, "FR air" cone, ATC joints `fr_atc` | Tool copies, gloved hand, toolpath tubes, air cone | derived, **saved** | Machining |
| "FR coolant" root (`fr_spans`, `fr_cut`, `fr_tools`, `fr_rpm`, keyed `fr_wet`), drops, jets, hoses, `fr_coolant_wet` | Coolant liquid drawn per frame and its tables | derived, **saved** | Machining |
| Milled mesh `fr_mk_o/d/a/p` attributes + "FR tool marks" group (`fr_toolmarks_version`) | Tool marks on cut faces | derived, **saved** | Machining |
| "FR Surroundings" (`fr_env`), environment materials (`fr_env_version`), root `fr_seacut_box`, `fr_bow_az`, "FR view cut 3", "FR Floor", "FR Studio"; scene `fr_waterline_z` | Sea, deck, quay, halls, floor and their materials | derived, **saved** | Sea / Scene & Render |
| "FR Props" (`fr_prop`, placement), "FR people" items and paths (`fr_item`, `fr_person_path`) | Props and people the user placed | choice | Scene & Render |
| Prop and person meshes (`fr_lod`, "FR prop detail", `fr_prop_mat`, `fr_prop_ver`, `fr_rig_ver`) | Two-level prop meshes and person rigs | derived, **saved** | Scene & Render |
| "FR Vessel motion" empties (`fr_vessel`, `fr_key`, `fr_peaks`), Child Of "FR vessel motion/still/level", "FR seabed motion" | Vessel motion rig | derived, **saved** | Sea |
| "FR Weather", "FR Weather lights", "FR weather" trees, scene `fr_weather_*` restore keys; step `fr_wx_v` | Weather objects and the state to restore | derived, **saved**; `fr_wx_v` = step data version | Scene & Render |
| Decal objects (`fr_decal`, `fr_off`, `fr_decal_masks`); packed decal pictures | Decal object per copy; the user's pictures | objects derived, **saved**; pictures choice | Looks |
| Weld beads and meshes (`fr_weld`, `fr_weld_end` UVs), weld materials (`fr_weld_look`, `fr_weld_src`) | Weld beads and materials | derived, **saved** | Welds |
| Lifting rigs "FR sling/shackle/spreader/hang/block sheaves/rope", CoG markers (`fr_cog`, `fr_cog_auto`), root `fr_lift_groups` | Rigging and markers made by the app | derived, **saved** | Lifting |
| "FR load box" (`fr_load_box`), placed crane models | Box loads and cranes | choice | Lifting |
| Trail curves + "FR trail" group (`fr_trail_mat`), "FR measurements" render objects | Drawn trails, measurement objects in renders | derived, **saved** | Scene & Render / Measure |
| "FR Cameras" (`fr_anim_camera`, `fr_turntable`, `fr_product_video_cam`) | Cameras | choice | Scene & Render |
| "FR House" (`fr_house`, `fr_house_lamp`) | Imported house | choice (import) | House |
| Scene `fr_tour`, `fr_tour_version`, `fr_demo`, `fr_demo_kit`, `fr_ws_before_all`; screen `fr_cv_areas`, `fr_cv_hide` | Tour/demo marks, workspace before "Show all", Client-view marks | choice (marks); `fr_cv_*` derived, **saved** | Quality & delivery / Start & learn |
| "FR web bake", "FR light bake" images, `fr_bake` working-copy scene | Bake images and the working-copy scene during an export | derived, removed after the export (web3d) | Web 3D / House |

### Lists for the cleanups 0350a, b …

#### (i) Kind (c) rows by lane
- **Machining:** gcode.upgrade_accel (< 0.2.83); toolchange.upgrade (< 0.2.45); machining.lock_interface (< 0.2.43)
- **Import:** build.ensure_bases (< 0.2)
- **Looks:** build.repair_uids (< 0.2.44); logic.upgrade_looks / materials.LOOK_VERSION 4 (< 0.2.237; the comment says 0.2.39); rule_sets.on_load (< 0.2.13, rules < 0.2.8)
- **Motion:** joints.upgrade_drivers (< 0.2.30)
- **Scene & Render:** props_scale.upgrade / `fr_prop_ver` (< 0.2.124); weather `fr_wx_v` (< 0.2.228, read at Build)
- **Sea:** surroundings.refresh_view_cuts (0.2.153)
- **Lifting:** lifting.upgrade (< 0.2.166)
- **Flex parts:** paths.version_names (< 0.2.125); paths.version_anchor (0.2.104–0.2.112; stamp `fr_cable_anchor`); paths.version_settle (≤ 0.2.109; stamp `fr_cable_settle`); spool.upgrade (< 0.2.139)
- **Way-cover:** waycover.migrate (< 0.2.61; plus the leftover `scene.fresing.waycover` group)
- **Start & learn:** workspaces.ensure (< 0.2.152; tour/demo < 0.2.164)

#### (ii) Derived data saved in the .blend today, by lane
- **Looks:** `tree`; `found`/`unmatched`; group materials with the `fr_*` look stamps and "FR adjust"; finish face data `fr_fx_*` and `fr_pixel_angle`; fade/section/weather material wraps; decal objects
- **Import:** `fr_color`, `fr_cad_material`, `fr_cad_basis`; imported meshes with `fr_face_starts`, `fr_axes`, `fr_axis_faces`, `fr_mesh_key`; `fr_stats` and the other statistics; model_count and bounds
- **Motion:** Build keyframes with `fr_anim_print`, `fr_jumps`, `fr_user_action`; `anim_baked`; joint `fr_value`, `fr_bias`, `fr_table`; model-update `report_*`
- **Motion (queue):** queue_dir, queue_pid, job status
- **Machining:** milled `cut_mesh`, `stock_mesh`, `path_sig`, `fr_wp_m`, `fr_carrier_m`, `fr_air_o/d`, bits' `fr_o/d/t`; G-code `fr_corners`, `fr_feeds`, `fr_turns`, `fr_g43`, `fr_tools`, `fr_air`, `fr_gc_from`; toolpath `result`; chips; "FR CNC" tool copies, hand, toolpath tubes, air cone; coolant root and its tables; tool-mark attributes and "FR tool marks"
- **Clash:** `clash.rows`, `clash.signature`
- **Flex parts:** "FR flex shapes" with `fr_flex_ends*`; "FR cable shapes <name>" with `fr_cable_places*`, `fr_let_go`, `fr_let_go_lay`; spool ropes and layers; "FR track loop/run <name>"
- **Sea:** "FR Surroundings" meshes and materials, `fr_seacut_box`, `fr_bow_az`, `fr_waterline_z`; the vessel-motion rig with `fr_key`, `fr_peaks`
- **Scene & Render:** prop and person meshes (`fr_lod`, `fr_rig_ver`); weather objects and `fr_weather_*` keys; trail curves
- **Web 3D:** `web3d.last_*`
- **House:** `house.last_*`
- **Lifting:** rig objects, CoG markers, `fr_lift_groups`, `rig_result`, `volume_mass`
- **Welds:** bead objects, weld materials, `cad_mesh`
- **Measure:** "FR measurements" render objects
- **Start & learn:** last_render, last_message, rendered_once, next_hidden; Client-view marks `fr_cv_*`

#### Handlers inserted at index 0, and the save handlers
- **`.insert(0` on `load_post`:** none. The only `.insert(` on a handler list is `handlers.py:pause_live.__exit__`. It puts the app's depsgraph and frame handlers back at their old index. Every `load_post` handler is added with `.append`.
- **save_pre:**
  - `handlers.py:_before_save`: skipped during a backup. Otherwise `queue.warn_busy_save` (a message when a long job is running), `spool.web_sweep` (removes hidden drum solids a web export left) and `flex.pause_read_for_save` (puts back the visibility and frame from before a re-bake read).
  - `workspaces.py:_on_save`: sets `saved_by` to the current user; `panels.on_save` writes `panels_open`.
  - `measure.py:_before_save`: when Keep is off or the Client view is on, stashes and clears the measurements and removes their render objects.
- **save_post:**
  - `handlers.py:_after_save`: skipped during a backup. Otherwise `flex.resume_read` and `queue.project_saved` (a delayed queue start follows the new file name).
  - `measure.py:_after_save`: puts the stashed measurements back.
  - `usage.py:_on_save`: writes the usage file (skipped during a backup).
  - `backups.py:_on_save`: restarts the backup clock; unsaved backups are marked as handled.
  - `project_lock.py:_after_save`: takes the "in use" lock file; after Save As it frees the old one. Skipped during a backup.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25 Nov 2026 (one session; branch `task/0352-compatibility-kit`, released as
0.2.264).

**What changed:**
- `core/compat.py` (no Blender): `FORMAT = 1`, `BASELINE_FORMAT = None`, the chain `STEPS = ()` as plain data
  (`Step(from, to, name, "module:function", changes)`), `plan` / `run` / `chain_problems`, the newer-project message,
  `aside_name`, `FAMILY_DATA` (all 16 families sorted: 15 store data, Help does not), `compare` / `round_value` /
  `picture_difference` / `NOT_CHOICES` for the test projects.
- `blender/compat.py`: the stamp `fr_format` + `fr_saved_by` on every local scene at every save (backups and the
  queue's copy too) – plain custom properties, not property-group fields, so any version reads them; `_on_load` FIRST
  in `load_post` (put back in front at every `load_pre`; `register()` also looks at the open file, because the app
  template switches the app on during a load). The chain runs once per file from its lowest stamp, each step gets the
  scenes below it; it **stops at a failing step** (one plain line, the project opens) and the scenes keep the format
  they reached, also through a save, so a fixed version tries again. *Decision against the brief's wording "as
  _on_load since 0055": _on_load's upgrades are independent, the chain's steps build on each other – running step n+1
  on data that step n did not convert would damage it.* The lead may want to confirm.
- **A project from a newer app** = look only (`compat.blocked()`): the app's Save (`fresing.save`, one call) refuses
  with the message; Blender's own save (the "Save changes?" question, a script) cannot be cancelled from `save_pre`,
  so any existing file it is about to write over is first kept aside as "<name> (Fresing Render 0.2.X).blend" (copy,
  else hard link, else moved; not again for a file this app wrote a moment ago); stamps are never lowered (what an
  older app saves of it stays "newer"); Save As makes a copy that is look-only too. Kept out: backups
  (`backups.wait_reason`), the render queue (`queue.start`), a model update (`reimport.update_model` and, before the
  STEP is read, `ops_import._locked`), Update now's save (`updates.save_project` skips it).
- `tools/make_compat_project.py`: builds 8 test-tour sets (crane, copies, mill, tools, cylinder, cables, house,
  lifting – they cover every family that stores data; a test works the coverage out again from `core/functions.py`
  and the tour's stops) into `format_<n>/`: `<set>.blend` (compressed), `summary.json`, `<set>.png` (80 × 60 Cycles,
  processor, 4 samples). `tests/data/compat/README.md`; nothing kept before the baseline.
- `tools/ci_precheck.py` `check_compat`: the chain is sound; from the baseline on every format number has its whole
  kept folder (summary with the right number, its .blend files); no kept folder above `FORMAT`.
- PC-check line `project.newer` (Full, `MIN_LINES_FULL` 161), function entry `help.newer_project`, guide section
  "Projects from a newer version" (Troubleshooting, anchor `newer-project`), CLAUDE.md sections 3, 6 (the rule) and
  7 (the release step), CHANGELOG.
- No tour stop: the function only shows with a file from a newer version (the PC check makes one).

**Tested and measured** (4-core web machine, Blender 5.2.3 as a Python module):
- `tests/test_compat.py` 13, `tests/test_compat_blender.py` 10, `tests/test_compat_review.py` 21 (the independent
  tester's), `tests/test_compat_projects.py` 6 + 1 skipped (no kept project yet): all pass. Making the test project
  ~45–50 s, the whole projects file 58–64 s. Sizes: crane 387 KB, copies ~500, mill 463, tools ~430, cylinder 494,
  cables 895, house 183, lifting 939 KB (all under 1 MB; 8 files ≈ 4 MB – one folder per format number).
- The comparison is not blind: a changed joint limit, animation step, lead-motion row, mesh decal, camera lens and a
  changed background are found (tests).
- PC-check lines `project.newer` (0.8 s) and `project.reopen` OK locally; related suites (project names, backups,
  queue, updates, functions, guide) pass.
- **Independent review** (a helper agent that did not write the code, 21 tests): 15 findings – re-registering dropped
  look-only and a save lowered the newer stamp (bug); the aside record outlived the file (bug); a failed copy aside lost
  the file (risk); Save As from a copy back onto the original (risk); the app switched on during a load skipped the
  check (risk); an appended newer scene; a failed step stamped as done; steps run per scene on shared data; four blind
  spots of the summary (lead rows / load charts hidden by a bare name, mesh decals, camera settings) and exact
  datablock counts (false alarm); the precheck too lenient. **All fixed**; its tests are kept in
  `tests/test_compat_review.py` (two rewritten to the decided rules: once per file, stop at a failure). Left as they
  are: a step raising SystemExit / KeyboardInterrupt is not caught (on purpose).
- GitHub runs: see below.

**Open points / follow-up tasks:**
- **The baseline:** the lead sets `BASELINE_FORMAT` and commits `tests/data/compat/format_<n>/` (README step 2) the
  day the baseline is released; until then the chain never runs.
- **0350 cleanups** – the (c) rows and the saved derived data, grouped by lane, are in "Findings" above (lists i, ii).
  Biggest saved derived data: the hose / cable shapes, milling meshes and chips, the surroundings' meshes, Build's keys.
- **0355** (running beside): `assets_source`, `assets_version`, `fr_asset` go into the saved-data list when it merges
  (they are choices; nothing to do in `NOT_CHOICES`).
- **0353** (outputs) can use `core/compat` style: a number and a plain line for a newer reader.
- The newer-project message shows in the status line and once in a small window after the load; the side panel has
  no row for it (a later UI task may add one).
- The chain's "stop at a failing step" differs from the brief's "as _on_load" (see above) – for the lead to confirm.
