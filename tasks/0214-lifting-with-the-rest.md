# 0214 – Lifting plans with the rest of the app (bug hunt 0209 groups B + C)

**Who:** worker · **Status:** done 18 Nov (0.2.166) · **Branch:** `claude/dreamy-babbage-55wbpk` (the web session's own branch)
**Started by:** lead, 18 Nov 2026 · **Model:** Opus · effort Medium
**Area:** Lifting lane – `blender/lifting.py`, `ops_lifting.py`, `ui_lifting.py`, `blender/sheet.py`, `blender/states.py`,
`core/lifting_reach.py`, `fresing_render/lifting_model/` (row 17), one hook line in `blender/reimport.py` (leave the rest
of `reimport.py` to 0209 group G), row 3 may touch `animation.py` (additive). Runs before L5 (rigging) in this lane.

## Goal

Fix rows **1, 3, 4, 11, 12, 14, 15, 16, 32, 33, 36** (group B) and **17** (group C) of `tasks/0209-bug-hunt-7.md`.
Rows 1 and 3 first – they lose work:
- **1** a model update (even the same file) loses every load on that model and puts its CoG near the origin.
- **3** Build, Hook to here, Build again: the crane jumps back (Build must keep the plan's pose).
- **4** updating a crane's model or deleting its objects drops the crane from the plan and leaves its joints / poses.
- **11** Place / Move with vessel motion on puts the crane 0.34 m into the deck. **16** a box load on a moving deck
  does not ride.
- **12** a crane pose used from Poses / Go to pose moves other models' hand-moved sub-assemblies back to CAD.
- **14** a renamed crane joint: Hook to here says ok with the hook 12 m off. **15** Make again with Replace and another
  hook block: no warning, Hook to here wrong.
- **17** the built-in cranes' own poses (Travel → Set up → Working → Long reach) give clash rows on the crane itself:
  fix the makers / poses (re-make the files with `tools/make_lifting_cranes.py`), never loosen the clash test.
- **32, 33, 36** small: radius past the chart says nothing; CoG symbol in every workspace / camera view; "a outrigger".

## Done when

- [x] Each row's repeat case is a test that failed before; every built-in crane's pose animation gives 0 clash rows.
- [x] 0201's open point "more counterweight than the chart picked" stays for L6 (say so).
- [x] Guide, tooltips where texts changed; tour sets still 0 clashes; full run green.
- [x] Report filled in.

## Not in this task

L5 rigging; the mesh update of moved groups (row 5, group G).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, branch `claude/dreamy-babbage-55wbpk`, 18 Nov 2026. Version 0.2.166.

**What changed:**
- Row 1: `lifting.after_model_update` (one hook in `reimport._put_together`): load parts re-pointed by part ID, the CoG
  marker re-parented to the new first part, a hand-set CoG kept at its world place, lost parts removed and named in the
  update report.
- Row 3: `lifting.keep_for_build` writes the crane's joint values into the saved Build pose after Hook to here / a pose
  button / Above the load, so the next Build keeps them.
- Row 4: `reimport.update_model` refuses a crane root (`fr_lifting`), 1 Import shows a hint instead of the button; a
  crane whose model is deleted stays in the list (`picked_crane`), Remove cleans it up by its name prefix.
- Rows 11 + 16: `place_at` sets the root's own matrix (not the world matrix, which counted the vessel's motion twice);
  clicks go through `rest_point` (`vessel_motion.to_rest`). Box loads are vessel followers (one line in
  `vessel_motion.followers`), the 3D cursor is taken back to a still sea.
- Row 12: `FRPose.joints_only` (crane poses from `sheet.make_poses`; older projects upgraded at load); honoured by
  `states.apply_pose_data` and the POSE step in `animation.py`; a pose saved from 4 Motion is a full pose again.
- Row 14: `missing_joints` / `check_joints`: Hook to here and the readout stop and name the joint; Remove also takes a
  renamed joint whose empties are inside the crane.
- Row 15: `FRLiftCrane.rig_hash` (rig + hook blocks); a crane made again is named, Hook to here / readout stop.
- Row 32: past the chart Hook to here moves but warns (`Answer.warning`, a WARNING report); "hook X m below/above the
  crane's base". Row 33: `cog_shown` (workspace shows `lifting.load`), not in camera view, not for a load without parts.
  Row 36: "an outrigger spread".
- Row 17 (makers, all 12 classes made again with pictures): chassis frame + outrigger/stabiliser boxes one solid with
  the beams' channels (`common.frame_with_boxes`), deck plate's underside cut by the channels; axles clear of the boxes
  and pads (`classes.box_clear`, AT rear axles, KB truck axles); jack housing clear of stage 1 (AT-250/500); KB outer
  boom foot keeps the retracted extensions' room, the column has a notch for the main cylinder's barrel and its eye,
  wider barrel lugs; crawler jib foot = side plates + hub outside the boom head + cross bar, wider pendant lugs on the
  boom head (CC-1600). Charts and kinematics unchanged; KB-20's cab position kept (moving it put Travel's CoG 0.18 m
  outside its support).

**Tested and measured** (web machine, 4 cores, Blender 5.2.3 as a module):
- `tests/test_lifting_with_rest.py` (11 tests, one per row, ~20 s): all 11 failed on `main` and pass now.
- `tests/test_lifting_cranes_own_poses.py` (14 tests, ~4 min): every class's poses and three points between each pair
  of poses – no pair moving against each other goes > 2 mm deeper in one than in another (`lifting_rig.overlap_changes`);
  plus the app's clash check of the pose animation started in "Set up" for AT-100 and KB-20: 0 rows. On `main` 5 of 6
  classes tried failed (beams 178→190 mm in the chassis, a beam 47 mm in a tyre, KB extension 17 mm, column 89→120 mm,
  jib foot 157→297 mm).
- Note: the pose tour as the made-crane tests run it (starting in Travel, Normal quality) gave 0 rows on `main` too –
  the clash check counts only depth beyond the first frame, so the hunt's rows came from starting elsewhere.
- Lifting tests locally: 1,060+ passed (lifting, cranes, plan, setup, library, reach, make, made cranes AT/KB/CC part a),
  tour lifting/crane-setup stops and their clash check: 9 passed. Tooltip report: 0 missing.

**Open points / follow-up tasks:**
- 0201's open point "more counterweight than the chart picked" stays for L6.
- Static overlaps that never change remain on purpose (pin eyes in lugs, the KB column base in the truck cab by 250 mm,
  the KB column in the load bed by 60 mm): the clash check never reports them, but they show in close-ups (makers lane).
- The hook block × cab rows the hunt saw are not reproduced with the file's poses (the hoist is part of each pose);
  after Hook to here + a pose animation the hook can still pass the cab (plan's own path checks come with L7).
- GitHub runs: 2 full runs of code. Run 44386228223 failed one test: the built-in crane files were 11.52 MB, over
  0191's 11.5 MB budget (the cut shapes made each STEP ~5 % bigger). Fixed without raising the budget: the library
  pictures now use a 128-colour palette (294 → 94 KB, same look), so the total is 11.42 MB. Run 44393146400 green
  (30 min). No subagents were used; no independent review (no Windows-only code).
- Branch `task/0214-lifting-with-the-rest` was never pushed (a web session pushes only to its own branch);
  `claude/dreamy-babbage-55wbpk` can be deleted on github.com after the merge.
