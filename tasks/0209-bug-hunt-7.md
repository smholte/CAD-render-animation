# 0209 – Bug hunt round 7 (findings only): everything merged since 0.2.141 used together

**Who:** worker · **Status:** done (18 Nov, findings only) · **Branch:** none (report on `main`, touching only `tasks/` and `TASKS.md`)
**Started by:** lead chat, 18 Nov 2026 (owner: "more tasks?") · **Model:** Opus · effort High · **Place:** Claude Code on
the web, environment "CAD-render-animation". Findings only: no app code, no version, no test run of its own – it does
not count towards the four code tasks.

## Goal

Find what breaks when the functions of 0.2.142 to the newest are used together – above all the new side panel (0062),
the Fresing menu / welcome / What's new (0199), the usage tracker (0181) and the Lifting plans workspace (0191, 0201,
0204, and 0203 / 0206 / 0208 if merged when you start) – on old projects, the made demo and the test tour. Same method
as 0118 / 0131 / 0147 / 0183 (read 0183's brief and report first).

## What to look at

- Everything in `CHANGELOG.md` from 0.2.142 to the newest: carousel read (0184), smaller web files (0175), mesh update
  of moved groups (0188), Fast 3-axis hole (0186), re-bake save / undo (0187), web export 8× faster (0189), view clip
  (0193), cable routes kept + re-bake fixes (0192), layout kept on open (0198), twelve cranes (0191), the cleaner side
  panel – workspaces, Client view lock, Make, Set-up window, folded sections, section tabs (0062), sea cut-away in the
  view + faster sea change (0196, 0202), stand spot (0194), Fresing menu / welcome / What's new (0199), Lifting plan:
  place, CoG, Hook to here (0201), usage tracker: favourites bar, declutter question, My usage, profiles (0181), Make
  a crane (0204).
- Used together: every workspace (incl. Client view and an own workspace file) with every section; the Client view
  with Build, render queue, web export, model update, undo, save / reopen; a personal hide (0181) against a workspace
  and against what the project uses; What's new after an update from 0.2.141 (the update test's old build is fine);
  Lifting plans on the demo (a crane on the quay, Hook to here to a demo part, a made crane, save / reopen, model
  update of the demo, undo); the Set-up window on the second monitor stand-in (two windows) with undo and save.
- Old projects saved by 0.2.135, 0.2.145 and 0.2.151 opened in the newest version: layout, workspace, panels open,
  everything builds the same.
- 0183's rows: re-check that each fix holds (0186–0189, 0192, 0194). Open points of 0062 (end of its report) and 0201:
  note only what you see.
- Speed: side-panel redraw with all sections open on the demo, a click to select, Build, playback, a sea change –
  against 0195's numbers (`tools/measure_demo.py`; name the machine).

## Rules

Public repository (CLAUDE.md section 6). Each row: what you did, what happened, what should happen, how often, the
smallest repeat case, severity (crash / lost work / wrong result / small), the lane and a proposed task grouping (two
fix tasks never share a file). Push only `tasks/0209-bug-hunt-7.md` (+ `tasks/img/0209_*` if a picture is needed,
small) and `TASKS.md`.

## Done when

- [x] Report: "In short (for the owner)" (≤ 8 lines), the rows, a grouping into fix tasks by lane for the lead.
- [x] Pushed to `main` touching only `tasks/` and `TASKS.md`; then check that main really contains your commit.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 18 Nov 2026. Hunted on `main` = 0.2.159 (3ba640b).
0208 (0.2.160) and 0203 (0.2.161) merged while the hunt ran: every row below was checked to still stand in their code
by reading (0208 changed the declutter question but not row 13's rule; 0203 changed `lifting.py` only for the
import's up axis, `sheet.py` still clears a crane pose's places). **No app code, test or tool changed**; scratch
scripts lived outside the repository (named per row, gone with the session – each row gives its numbers). Three
helper agents hunted one area each (**A** side panel / workspaces / lock / start / usage, real app; **B** Lifting plans
on the demo and the test crane; **C** 0183's rows and 0.2.142–0.2.157 together); the main session did the old
projects, What's new, the speed and re-ran the worst row of each helper. **(re-run)** = run again in the main session.

### In short (for the owner)

- **Nothing crashes, and old projects are safe:** the test tour made with 0.2.135, 0.2.145 and 0.2.151 (131 projects,
  131 animations) opens and builds the same in 0.2.159, with the Fresing tab, folded sections and its workspace right.
- **Client view is not locked tight:** one click brings Blender's object list back and the whole model can be deleted
  (row 2); after an import + undo a camera can be moved (row 9).
- **Make > 3D page** shows half its settings and **no Export button** (row 6).
- **Lifting plans:** a model update (even the same file) loses the load and puts its CoG near the origin (row 1);
  Build after Hook to here puts the crane back (row 3); placing a crane with vessel motion on sinks it 0.34 m (row 11).
- **Cables:** an undo after a water-level change still leaves the cable 1 m under the seabed (row 7, 0183 row 4).
- Most of 0183's fixes hold (list below); the web export of the demo now takes 506 s instead of 2,174 s.

### Findings (worst first)

| # | Severity | Where | What happens and when | Proof | Suggested fix | Lane |
|---|---|---|---|---|---|---|
| 1 | **lost work** | `reimport.py` `_put_together` (~427) has no lifting hook: the update makes new objects, `FRLiftLoad.parts[].obj` / `carrier` become None, the CoG marker loses its parent and `cog_local` is read as world (`lifting.cog_world` ~801) | **A model update – even with the same file – loses every load on that model.** Test crane, "20 parts kept, 0 new, 0 missing": load 3 parts → 0, CoG (0.81, 0.30, 0.40) → (0.29, 0.02, 0.08); Above the load: "The load has no parts"; the readout keeps the entered mass and shows crane use 8.5 % as if valid; a CoG set by hand stays marked "by hand" at a wrong place. Demo: vessel updated with its own file ("1425 kept"): winch load 20 parts → 0, CoG (44.5, −3.9, 4.2) → (0.27, −0.09, 0.63). The update report says nothing. 5 of 5 runs. | **(re-run)** B/`s1_update_load.py A` (3 → 0 parts, CoG to (0.29, 0.02, 0.08)); B/`d2_update.py` | `lifting.after_model_update(mapping, by_uid)`: re-point parts, carrier and marker, keep a hand-set CoG; name lost parts in the report. Test: same-file update = identical load, CoG and use. | Lifting (+1 hook line in `reimport.py`) |
| 2 | **lost work** (lock bypassed) | `lock.py` `_swap_outliners` (~195) swaps the Outliner once, when the lock goes on; nothing stops the area being switched back; `_KEYS` (~296) | **Client view: pick "Outliner" in the editor-type menu of the Info area that replaced it → Select all → right-click > Delete deletes the whole model** while the lock is on (26 → 0 objects). Ctrl+Z restores; a Save keeps the loss. 3 of 3 runs. | **(re-run)** A/`a13_client_outliner.py` (26 → 0) | While locked, put Outliner areas back to Info (`_after_change` or a msgbus on `Area.ui_type`), or refuse `outliner.delete` / `outliner.id_operation` (poll / keymap). Real-app test: switch the area, try to delete. | Side panel (lock) |
| 3 | **lost work** | `animation.bake` → `clear_keys(restore=True)` (~397–404) puts back the pose of the previous Build; `lifting.set_values` / `apply_pose` (~510–550) neither take the Build off nor update `anim_restore_pose` | **Build, then Hook to here (or a crane pose button), then Build again: the crane jumps back.** Test crane with a Hide step: Hook to here → use 2 %; after Build 2 all 6 driven joints are back, readout 8.5 %. Move… is kept. 2 of 2. | B/`s7_build_restore.py hook\|pose\|move` | Hook to here / pose / Above the load take the Build off (`clear_keys(restore=False)`) or write the crane's joints into `anim_restore_pose`. | Lifting |
| 4 | **lost work** | the crane is found only through `crane.root` (`lifting.active_crane` ~223); "Update to new revision…" on the crane's own model (offered in 1 Import for every root) replaces the root | **Update a crane's model, or delete its objects: the crane drops out of the plan** ("No crane yet", Remove greyed) and leaves 19–22 joints, 4 poses, a cylinder and the hoist-rope cable; every later Build warns "Cable 'AT-40 · Hoist rope': its part is gone"; a new crane is named "AT-40 2". 1 of 1 per route. | B/`s4_crane_update.py update\|delete` | Hide "Update to new revision" for crane roots (`fr_lifting`) or re-point `crane.root`; let Remove clean up a crane whose root is gone (by name prefix). | Lifting |
| 5 | **lost work** | `reimport._made_assemblies` (~253): every voting part's box-middle shift must equal the group's shift within 5 mm | **Mesh (glTF) update, unnamed group B moved 100 mm and one of its parts 20 mm wider:** "6 parts kept" but the Hide step's target and the eye's hide are lost; with unnamed parts: "4 kept, 2 new, 2 missing", joint deleted. 0183 row 5's own case (move only) holds. | C/`r5_mesh.py`, `r5b.py` | Vote by median / majority shift (or part origins); pair unnamed parts by shape + the group's common shift. | import |
| 6 | **wrong result** (since 0.2.152) | `ui_top.py` `_Popover.draw` (~253) runs `panels.body_of(FRESING_PT_web3d)` with `self` = the popover; `ui_web3d.py` ~58–60 calls `self.draw_surroundings / draw_light / draw_player`, which only the side-panel class has | **Make > 3D page stops after "Include animation"**: AttributeError at every draw, no Surroundings / Light / Player settings and **no Export… button**, in every workspace that lists it. 22 of 22 draws; the other 5 Make popovers draw fine in all 11 workspaces. | A/`a16_make_popovers.py`, `a17_make_web.py` (+ code read in the main session) | Make the three methods module functions `(panel, context, layout, w)` or call them on `FRESING_PT_web3d`. Test: draw every Make popover and find its Make button. | Web 3D (+ `ui_top.py`) |
| 7 | **wrong result** (0183 row 4 not fixed for its own case) | `vessel_motion.motion_key` (~572) leaves out water level and water depth; their re-bake runs only by `force=True` from `paths_sea` (~947); `paths._on_undo` (~4220) checks `moved_since` only; `paths._on_load` (~4149) checks nothing | (1) **Real app: water level 2 → 3 m, re-bake done, Undo → water 3.0 with the cable at −14.976 (1 m under the seabed), no re-bake**, 3 of 3 runs. (2) A copy saved during the job opens with the new water and the old cable, never re-baked (6 of 6). (3) Same with a sea-state change: `moved_since` True on opening but nothing asks (2 of 2). The fix of 0187 covers the settings in the key only (vessel speed, sea state with vessel motion on). | **(re-run)** C/`r4_undo.py` R4_MODE=water (−14.976 after undo, 0 re-bakes); C/`r3_save.py` + `r3b_reopen.py`, `r3_save_sea.py` | Water level, water depth and each sea cable's own depth into the key (or a second key checked alike); run the check on `load_post` too. | cable paths |
| 8 | **wrong result** | any demo update that is not bit-identical takes the "read again" route (`paths.after_model_update` ~4067); 0192 fixed only `same_model` | **Demo vessel updated and read again (same geometry, forced; also at Normal quality), then Build:** power cable 263.216 → 263.142 m, Second end 221.234 → 221.154 m, fairlead sheave wraps 1.849 → 2.344 rad, tipping foot sheaves 1.415 → 1.573 rad, new warning "A&R winch fleet angle 38.7°" (was 13.6°), lay labels Layback 33.0 → 31.6 m, top tension 20.3 → 19.5 kN. Contacts and ends unchanged. 2 of 2. | C/`d2_update.py` (FORCE_READ=1) | "Read again" keeps user-set and set-up state per contact (wraps, follower order, bend carriers). Test: demo update with one unrelated part changed, Build = saved Build within mm. | cable paths |
| 9 | **wrong result** (lock leak) | an import pushes its undo step before `depsgraph_update_post` marks the new objects; `workspaces._after_undo` (~541) re-locks only when `marked()` is 0 or the state changed; `lock._after_change` (~185) only when the object count changed | **Client view → Import STEP → an undoable action that adds no object (a family tick) → Ctrl+Z:** the camera "Iso front-right" and "FR Floor" come back unmarked; the camera can be selected and moved with G (0.5 m) while locked. 2 of 2. | A/`a8_client_undo.py` | In `_after_undo`, when locked, `_lock_object(ob, new=True)` over all objects (it skips marked ones). | Side panel (lock) |
| 10 | **wrong result** | `surroundings._model_box` (~268) counts every part, placed cranes too; `_build` (~285) places the sea / deck from it; cranes are `vessel_motion.followers` (~358) and set `hull()` | **A crane on the demo with its hook lowered beside the hull (Hook to here at z −15 m), then a sea-state change, Fit surroundings or a model update:** waterline 6.46 m lower (the vessel floats 6.5 m higher), vessel beam for the motion 27.3 → 39.0 m, pivot y 0 → −5.82. Without the crane nothing changes. 2 of 2. | B/`d3_sea_bounds.py crane`, `d3b_sea_change.py crane` (control `none`) | Leave crane roots (`fr_lifting`) and load boxes out of `_model_box` and `vessel_motion.hull`. | Sea / scenes (surroundings) |
| 11 | **wrong result** | `lifting.place_at` (~364) sets `root.matrix_world` while its "FR vessel motion" Child Of is active (the vessel's move counted twice); the click lands on the moving deck | **Place (or Move…) with vessel motion on puts the crane into the deck:** Rough, click on the deck at frame 60 → crane origin 0.335 m below the deck at every frame; at frame 1 0.05 m. 2 of 2. | B/`s5b_vessel_click.py 60 \| 1`, `s5_vessel.py DECK 60` | Place inside `vessel_motion.at_rest`, the click turned back through the inverse vessel matrix. | Lifting |
| 12 | **wrong result** | `sheet.make_poses` (~204) clears `pose.places`; `states.apply_pose_data` (~103, `reset_others=True`) and the POSE step (`animation.py` ~913) read a missing place as "back to CAD" | **A crane's pose used from 4 Motion > Poses ("Use pose") or as a Go to pose step moves every hand-moved sub-assembly of the other models back to CAD** (BOOM.ASM moved 0.5 m → back). The crane's own pose button is fine. 1 of 1. | B/`s3_pose_freemove.py` | Mark crane poses joints-only and honour it in `apply_pose_data` and the POSE step, or hide crane poses from 4 Motion's list. | Lifting (+ states / animation) |
| 13 | wrong result (confusing) | `core/usage.py` `declutter_candidate` (~360): a function never used counts as unused from session 0; nothing knows when it first appeared (unchanged by 0208) | **The first start after an update asks to hide a panel What's new is advertising:** a 0.2.150 user updates to 0.2.159: the splash says "What's new since 0.2.150 – 24 new functions" and the side panel asks "You haven't used Equipment recently. Hide it…?" (Equipment is from 0.2.156); also in the Lifting plans workspace. Real app 1 of 1; the rule is deterministic. | A/`a6_declutter_new.py`, `a5_one_start.py` | Count "not used" from the session a function was first offered (skip functions newer than `whats_new.from` until `threshold` sessions passed). | Usage |
| 14 | wrong result | `lifting` joints and poses found by name prefix (`own_joints` ~406, `values` ~519, `set_values` ~530); a missing rig joint is never reported | **Rename one crane joint in 4 Motion > Joints ("AT-40 · Luff" → "Luff"):** Hook to here says ok ("radius 3.00 m, use 1 %") with the hook 12.29 m from the target; Remove leaves the renamed joint. 1 of 1. | B/`s10_rename.py` | Refuse a rename inside a crane's prefix, or check every rig joint exists before Hook to here / the readout. | Lifting |
| 15 | wrong result | `lifting.file_changed` (~198) compares only `chart_hash`; `rig_of` / `_hook_block_world` read today's file, not the one the placed model came from | **Make a crane, place it, Make again with Replace and another hook block height (1400 → 2400 mm), charts unchanged:** no warning, rig check passes, Hook to here leaves the hook **1.000 m** above the point. With changed charts it is noticed. 1 of 1 each. | B/`s6_replace.py block_h 2400` | Hash the rig too (or keep the rig in the project at placing); on a mismatch "place it again". | Lifting (make) |
| 16 | wrong result | `lifting.new_box` (~867) puts a box load in `scene.collection`, not in `vessel_motion.followers` | **A box load on a moving deck does not ride:** gap to the deck +0.25 / +0.46 / +0.49 / +0.26 / −0.44 m at frames 1 / 30 / 60 / 90 / 150. 1 of 1. | B/`s12_box_vessel.py` | Box loads to the followers, or parented to the clicked part. | Lifting |
| 17 | wrong result (crane models) | the built-in crane models of 0191 | **Animating a built-in crane's own poses (Travel → Set up → Working → Long reach) gives clash rows on the crane itself:** AT-40 4 rows (hook block through the cab 142 mm; tyre × outrigger beam RL 47 mm, also at rest); AT-100 8 rows (chassis × stage-2 outrigger beams 190 mm, cab × hook 80 mm); KB-20 outer boom × extension 1 17 mm. 3 of 3 classes tried. | B/`s2_poses_clash.py <class>`, `s2b_static.py` | Fix the models (beam inside the tyre, stage-2 beams through the chassis, KB extension); a mid pose so the hook clears the cab. Test: each class's poses animated = 0 rows. | Lifting (crane makers) |
| 18 | wrong result | `core/tc_person.py` ~129: the floor grid is fixed to world cell lines (0194), so where the cabinet edge falls depends on the model's world place; `stand_spot` (~410) has no margin for the arms | **Tour set "operator" with the model moved 1 cm … 25 cm:** the person stands at −0.56 instead of −0.60 and the hands go into "CABINET STAND" at frames 172, 460, 463. 6 of 6 moved placements. 0183 row 16's own case holds. | C/`r16_stand.py`, `r16b_hands.py` | Grid relative to the machine plus a one-cell margin (or check the arms' reach). Test: moved by fractions of a cell = same relative spot, no hand clash. | people |
| 19 | wrong result | `ops_usage.export_profile` (~217) puts the personal hides into the workspace's `hide` and switches the project to it; `usage.reset` clears only `state["hidden"]` | **After Export profile, "Back to the workspace as it came" says "Your hidden panels show again" but they stay hidden** until another workspace is picked; a colleague importing the profile gets them as workspace hides his reset cannot undo. | A/`a7_profile_reset.py` | Keep a profile's hides apart (a personal-hide key the importer adds to the user's hides), or let reset drop them from `ws_data`. | Usage |
| 20 | slow | full demo (4,481 frames): a sea-state change re-works the riding camera in one call, `rebake.cameras` → `camera_path._sample` (camera_path.py ~114) | **Sea state Calm → Rough on the full demo: 16–18 s, of it the sea 2.2 s (0202's number holds) and the riding camera's re-bake 13.0 s in one Python call** (cProfile). In the window that is one step of the re-bake job without a redraw (by reading `rebake._steps_once`; not timed in the window). 3 of 3 changes. | main/`sea_prof.py` (17.6 / 15.9 / 15.8 s; `_sample` 12.99 s tottime); `measure_demo.py` "sea state Rough: 16.53 s" | Sample the camera in steps (yield per block of frames), or only the frames of the riding steps. | Scenes (camera_path) |
| 21 | slow | `web3d._marine_estimate` (~1965) reads every shared bake group's mesh (`lightbake._read_mesh` ×69); `_kept` (~91) recomputes at every scene change and frame | **Web 3D panel open on the small demo: each draw after a click, a selection or a frame change 135–378 ms** (`marine_estimate` 167–285 ms; 0183: 28–30 ms; repeated draws 0.16 ms). 10 of 10 frame changes, 5 of 5 selections (under load ~13). | C/`r17_panel.py`, `r17b_prof.py` | Frame out of the key; per-mesh areas cached by mesh name + vertex count; recompute only on geometry / material changes. | Web 3D |
| 22 | small | `usage.apply_personal` (~322) runs only on load, Hide and reset | A personally hidden panel (Trail lines) stays hidden when the project starts using it in the same session; the Workspace row meanwhile says the Animation family is hidden although the workspace shows it. Shown again after reopening. | A/`a10_personal_stale.py` | `apply_personal` when `used_functions` changes (after Build / undo / model update, or in the Workspace panel's draw). | Usage |
| 23 | small | `ops_setup.py` ~427 / ~443: `setup_kind` / `setup_go` and the window button push no undo step; memfile undo restores `setup_kind` / `setup_step` | **Ctrl+Z of an unrelated action throws the Set-up window back** (Mechanism step 3 → CNC step 1) and it stays so after save / reopen. 1 of 1 (by design of memfile undo). | A/`a18_setup_undo.py` | Keep kind and step out of undo (window-manager / screen property) or push an undo step on them. | Side panel (Set-up window) |
| 24 | small | `lock.ALLOWED` against `core/workspaces.BUILTIN["client"]` | The Client view shows functions whose buttons are greyed: `scene.camera` (camera_add), `scene.save` (shot_save), `queue.schemes` (queue_schemes – `queue_add` is allowed); a favourite "Save scene" jumps to a greyed button; an open Set-up window's Back / Next are refused. | A/`a1_client_buttons.py` (36 shown, 3 refused) | Allow them, or hide the three functions in the Client view; a precheck: every function shown in a locked built-in has an allowed button. | Side panel (lock) |
| 25 | small | `core/start.py` ~77, ~93 `int(w.get("later", 0))`; `load()` (~59) keeps any type | **A damaged start file** (`"later": "two"`, null, 1e400) gives a traceback at every start; neither welcome nor What's new ever shows; never repaired. A junk `last_run` ("0.2.x") makes What's new list all 137 functions. 2 of 2. | A/`a11_junk_files.py`, `a19_junk_start.py` | Clean the types in `load` as `core/usage.clean` does. | Start (0199) |
| 26 | small | `welcome.py` What's new (~401) shows the 8 newest functions; only 1 function in `core/functions.py` has `changed=` | **What's new after an update from 0.2.141 to 0.2.159** ("What's new since 0.2.141", 25 functions) lists Make a crane, chart entry, four usage lines, Lifting first use and Place – the **workspaces, Client view, folded sections and Fresing menu are in "… and 17 more"**, although the folded side panel and the hidden Blender tabs are the first thing such a user sees. Fixes and speed-ups (Fast 3-axis hole, web export 8×, sea 3×) never show as "improved". Test tour: 2 new, 3 changed sets (right). | main/`core.new_functions(…, "0.2.141", "0.2.159")` | Pick by weight (a `headline` flag) or one line per version; set `changed=` on functions a release made visibly better. | Start (0199) |
| 27 | small (wrong text) | `paths_sea.numbers` (~991): `height < NO_HANG` (1e-3) while `core/catenary.BED_GAP` = 1e-3 keeps a resting bend at exactly 1 mm | test_moving + Sea, Build: frames 273–280 show Top/Bottom 21.5, 22.6, 17.0 … 5.0 kN in panel and labels (0.11–0.34 kN just before), then "–" (0183 row 14: the 16,802 kN is gone). | C/`r14_tension.py` | `NO_HANG` clearly above `BED_GAP` (5 mm), or `<=` with a tolerance. | cable paths |
| 28 | small | `rebake` / `flex.read_steps`: `keep_at` is taken inside `at_first_frame` | A save during the re-bake job reopens at frame 1, not the frame the user had (150). 5 of 5 copies (0183 row 3's visibility part holds). | C/`r3_save.py` | Keep the frame from before `at_first_frame` for the save pause. | cable paths |
| 29 | small | `spool.renamed` (~162) skips the free-name check for "" | Carousel and drum both renamed to "": they share the tag (19 objects); removing one leaves 2 of the other's 9 objects undrawn, also after a Build. | C/`r15_spool_name.py` | Refuse an empty name (put the old one back). | Flex parts |
| 30 | small | `web3d.SeaRest` (~1880) blends by `surroundings.seabed_z`, not the cable's own bottom (`paths_sea.bottom_z`) | test_moving cable with its own depth 15 m (sea 30 m), animated page without vessel motion: page cable 0.17–0.65 m off the app's; with vessel motion on the page ≤ 5 cm (0183 row 6 holds for test_sea). | C/`r6_web_sea.py`, `r6b_probe.py` | Blend between the cable's own bottom and the water. | Web 3D |
| 31 | small (cause unsure) | `surroundings.view_clip_start` (~366) takes the reach from the cameras' clip ends (52 km) | The demo's 3D views: clip end 58,187 m, **clip start 0.29 m**; a close look under ~29 cm is cut, while the farthest thing drawn is at 28.3 km. | C/`r_clip.py` | Reach from what is drawn, or a lower floor for clip_start. | Sea / scenes (surroundings) |
| 32 | small | `ops_lifting._hook` (~612) / `lifting.hook_to` (~592) | Hook to here at radius 55.6 m (longest chart radius 48 m) reports INFO "radius 55.61 m, hook at −7.02 m…" with no use and no warning; "−7.02 m" is from the crane's base on the bridge and reads as under the sea. | B/`d5_readout.py` | "Outside the chart (longest radius 48 m)" as a WARNING; "X m below / above the crane's base". | Lifting |
| 33 | small | `lifting._draw_cog` (~1091) checks only that loads exist | The CoG symbol is drawn in every workspace (Client view too), in camera view, and at the stray place of row 1 (by reading). | code read (B) | Draw only where the Lifting family shows and the load has parts. | Lifting |
| 34 | small | `usage.label` (~253) | Favourites bar at the default width: "Update to new revi…", "The same STEP twi…" cut off; a favourite "Hide" sits right above the declutter question's own "Hide". | A/`out/a5_new_q.png` | A short label per function, or one column for long ones. | Usage |
| 35 | small | `workspaces.ensure` (~410): a project without a workspace gets the user's default, Client view included; only tour / demo projects made since 0.2.152 call `use_all` | With the default workspace "Client view", a **test-tour project made by an older version** opens locked (0 of 43 parts clickable, the motion / offshore families hidden). The user's own old projects lock too – by design. | main/`ui_old.py` with DEFAULT_WS (7 of 7 files) | A tour / demo project (tour TAG, demo mark) gets `use_all` in `ensure`. | Side panel (workspaces) |
| 36 | small (text) | `core/lifting_reach.py` ~749 | "No chart for **a outrigger** spread of 3.11 m or less" (pose Travel, AT-100, KB-50). | B/`s9_charts.py AT-100` | `words` a / an. | Lifting |

**Seen in passing, not checked:** 0183 row 12 (phone, part tools' panel) overlapped in 2 of 8 runs at 932×430 (once a
hint blocked the Cutaway button, once a message lay over the panel) – cause unsure, maybe timing under load (C/`r12_phone.py`).
The animated-label fix (0183 row 13) also drops constant fields ("Water depth {depth} m"). A queued render started by
helper A in the Client view was left running by it and stopped by the main session (no app fault).

**0183's rows re-checked** (C, own repeat cases): 1 holds for the same file (test_paths_a: CHUTE stays off,
6.8671 m, also after save / reopen and revision B → A) – not for a changed model (row 8); 2 holds (0 misses through
every map tile, 4 variants); 3 holds for visibility (0 objects differ in copies saved at 10–90 %), the frame does not
(row 28) and the copy is not re-baked (row 7); **4 does not hold** for its own case (row 7); 5 holds for its case (row
5 is a variant); 6 holds for test_sea (row 30 is a variant); 7 holds (camera within 3–7 mm, was 1.48 m; 278 of 280 key
arrays identical); 8 holds (re-bake = Build, 0.000 m, three cases); 9 holds (demo web export 506 s vs 2,174 s, 69
shared bakes for 264 parts, 11.2 MB; the estimate said 164 s); 10 holds (background re-bake 223 s vs Build 220–247 s;
0183: 606 s); 11 holds (saved file has 0 solids); 12 mostly (above); 13 holds; 14 partly (row 27); 15 holds for its
case (row 29); 16 holds for its case (row 18); 17 holds for repeated draws only (row 21).

**Old projects (main session):** the test tour made with **0.2.135 (43 files), 0.2.145 (44) and 0.2.151 (44)**, each
file opened and every animation built once with its own code and once with 0.2.159 (131 animations); every object's
place, hiding and evaluated vertex count compared at 4 frames per animation, and every collection of settings counted.
**Identical** except the moving cable's 26,260 instead of 24,920 points in 0.2.135's "A cable on a moving part" (as
0183 found; a new project has the same). No warnings, no errors. In the **real app** (xvfb) 7 projects of 0.2.135, 3 of
0.2.151 and the made demo open with the side panel shown, toolbar folded, the Fresing tab, sections 1–8 folded,
Blender's tabs hidden, workspace "All functions" and nothing used hidden; with the default workspace "CNC & machining"
the offshore / house projects get their families ticked on (nothing used hidden); with "Client view": row 35.

**Speed** (main session, 4-core web machine, **quiet** – helpers done, load 1.7–5; full demo made by 0.2.159 in 635 s,
258 MB, as 0195's): Blender as a module (`tools/measure_demo.py`): playing **55.4 ms** a frame (0195: 55), scrubbing
58.8 (65–69), handlers 0.1 ms (0.13), FR track modifiers 17 ms (15), **select 251 ms** headless (0195: 180–260), first
hover 5.3 ms median / 109 worst, a live joint step 11.7 ms (7–13), save a copy 1.4 s, 1,872 MB. Real app under xvfb
(`--quick`, software drawing): **side panel with every Fresing panel open 12.4 ms of Python** per redraw (0195: 81 ms –
0062 + 0189 took it off; but row 21 after a change), select 140 ms with the redraw (150–180), undo step 0.11 s, Undo
0.70 s. **Sea state change 16.5 s** (0195: 5.8–6.4; the sea part alone 2.2 s – row 20). Build: the small demo's Build
inside its make (made in 611 s here); C measured a Build 220–247 s under load (0183: 221 s).

**What changed:** only this report and `TASKS.md` (0209 → done, its rows listed under "Problems found"). No app code,
test or tool; no version; no test run.

Subagents: three helpers (Opus) – A (side panel, workspaces, Client view, Set-up window, Fresing menu, What's new,
usage tracker; real app), B (Lifting plans on the demo and the test crane), C (0183's rows + 0.2.142–0.2.157 together);
each read and ran its area and returned rows with scripts. The main session re-ran rows 1, 2 and 7 with their scripts
(same numbers), read the code of row 6, did the old projects (bpy module and real app), What's new from 0.2.141
(row 26), row 35, the speed (row 20). Not re-run here: the other rows.

**Not tried:** a real Windows PC, a graphics card, the Set-up window of 0203 (merged after the hunt began), Dope Sheet /
Properties edits in the Client view (0062 open point), the web export / queue copy / full-demo clash check with a crane
in the project, a real changed demo STEP (row 8 forced a read-again), autosave during the re-bake, the animated demo web
export, the full test tour's automatic run, Material Preview (EEVEE crashes under software drawing).

**Open points / follow-up tasks – proposed grouping for the lead** (two tasks never share a file; the shared file of
two is named):
- **A – Client view and side-panel faults** (side panel lane, Opus · Medium): rows 2, 9, 24, 23, 35 (`lock.py`,
  `workspaces.py`, `core/workspaces.py`, `ops_setup.py`). First: row 2 is a lock that does not lock.
- **B – Lifting plans with the rest of the app** (Lifting lane, after 0203 – done, Opus · Medium): rows 1, 3, 4, 11, 12,
  14, 15, 16, 32, 33, 36 (`lifting.py`, `ops_lifting.py`, `sheet.py`, `states.py`, `core/lifting_reach.py`, one hook
  line in `reimport.py`; row 3 may touch `animation.py`). Rows 1 and 3 first.
- **C – Built-in crane models clash** (Lifting lane, Sonnet · Medium or with B's worker): row 17 (`lifting_model/`).
- **D – Cables and sea after changes** (cable paths / sea lane, Opus · Medium): rows 7, 8, 27, 28, 29, 10, 31
  (`paths.py`, `paths_sea.py`, `vessel_motion.py`, `rebake.py`, `flex.py`, `spool.py`, `surroundings.py`). Row 7 first
  (0183 row 4 still open).
- **E – Web 3D follow-ups** (Web 3D lane, Sonnet · Medium): rows 6, 21, 30 (`ui_web3d.py`, `web3d.py`). Row 6 first – a
  one-line fault with a visible effect (no Export in Make).
- **F – Usage and start** (usage lane, Sonnet · Medium): rows 13, 19, 22, 25, 26, 34 (`core/usage.py`, `usage.py`,
  `ops_usage.py`, `core/start.py`, `welcome.py`, `core/functions.py`).
- **G – Import: mesh update of a changed, moved group** (import lane, Opus · Medium): row 5 (`reimport.py` – shares it
  with B's hook line: run after B, or B's worker leaves the hook to G).
- **H – Riding camera re-bake in steps** (scenes lane, Sonnet · Medium): row 20 (`camera_path.py`; `rebake.py` is D's:
  run after D).
- **I – Tool-change operator spot** (people lane, Sonnet · Low): row 18 (`core/tc_person.py`).
Order: E row 6 and A row 2 (small, visible), B rows 1 + 3, D row 7, the rest. Leftover: no branches pushed, no
worktrees; old versions were unpacked with `git archive` in the scratch folder.
