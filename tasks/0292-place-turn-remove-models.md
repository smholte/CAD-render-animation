# 0292 – Place, turn and remove: move a model, subassembly or parts by X / Y / Z and angles; Remove… with a confirm window

**Who:** worker · **Status:** open – can start (0282 done, 0.2.217; 0307 done, 0.2.216 – read its report and `blender/place.py` first; Place uses 0282's `form_window`; start after 0289 has merged 0.2.218, point 3 changes the tree row in `ui.py`) · **Branch:**
`task/0292-place-turn-remove`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "How to delete an assembly? Only with using cleanup or
also with delete button?" – "How to move around object/assemblies in the scene? I want to move around parts before
animating the scene, move xyz and rotate.") · **Model:** Opus · effort High
**Area:** new **Place lane**: new files `core/place.py` (numbers, snaps, no Blender), `blender/place.py`,
`blender/ops_place.py`, `blender/ui_place.py` (a sub-panel of 2 Structure) and their tests; additive:
`context_menu.py` (right-click entries), the 2 Structure tree row (`ui.py` `FRESING_UL_tree`, point 3 only), `lock.py` (Delete / X outside Full access → the app's Remove window),
`props.py`, `core/places.py`, `core/functions.py`; guide, tour, PC check, CHANGELOG.
**Not:** the 1 Import panel (0289 runs beside this), `joints.py` / `cylinders.py` internals (call them), copy and paste
(0293, next in this lane), Clean-up's behaviour (it stays).

## Background

- Outside Full access Blender's G / R / S still work (task 0253 kept them), so a user can press G or R, then X / Y / Z
  and a number – but nothing in the app says so, there are no fields, and the Move tool's gizmo is gone (the left panel
  took the toolbar region, `quiet._no_tools`). **But on the owner's PC a G / R move jumps back on click / Enter**
  (owner 23 Nov 20:12) – task 0307 finds why and fixes it first; read its report and build Place on that.
- Delete / X do nothing outside Full access (0253, on purpose: nothing lost by accident). **Clean-up** only takes parts
  out of the render (restorable) – it is not a delete. There is no Remove for a model today.
- A model's root is never a free move (CLAUDE.md 8): a model moved by its root keeps its place through Build, poses,
  saved scenes and updates. Parts moved inside a model are "moved parts" that poses and Back to CAD know
  (`fr_rest_basis`, `joints.free_moves`).

## What to do

1. **Place** (2 Structure > Place; also right-click > Move / turn…, as a function window – 0282's `form_window`): for
   the selection – a model, a subassembly or parts:
   - X / Y / Z in mm (world, or the model's own axes – a switch), turn about X / Y / Z in degrees; step buttons
     (± 10 / 100 mm, ± 15 / 90°); **Snap** off / 1 / 10 / 100 mm and 5 / 15 / 45°.
   - **Move with the mouse** / **Turn with the mouse**: Blender's own move / turn with a line on screen saying "X / Y / Z
     locks the axis, type a number, click to place, Esc cancels"; a move gizmo (arrows + rings) while Place is open.
   - **Put on the floor** (lowest point on z = 0 or the surroundings' floor), **Back to the CAD place** (a moved
     subassembly / part), **Back to where it was imported** (a model).
   - Rules to design and state in the report: moving a model moves everything of it (joints, cylinders, mechanisms,
     hoses, cables, labels, cameras riding on it); a subassembly or part moved *inside* a model before animating
     takes its joints' frames with it, and what "CAD place" and "rest place" mean afterwards for poses and Back to CAD.
     A built animation: Place takes the Build off and says "Build again". Client view: refused (locked).
2. **Remove…** for a model (its row in 2 Structure, right-click > Remove…, and the **Delete / X keys outside Full
   access open the same window**): the window lists what goes with it – N parts, its joints, cylinders, mechanisms,
   hoses / cables, labels, decals, steps that only move it; steps that also move other things lose only its part;
   saved scenes keep working. **Remove / Cancel**; one undo step; the import cache stays (0289's Imported models can
   bring it back). Also for a subassembly or selected parts (same window; say what happens to a joint whose parts go).
3. **A lock in every tree row** (owner 23 Nov 22:24, screenshot of 2 Structure on a truck model of his): next to the eye
   and the arrow at the end of each row of the 2 Structure tree, a **lock** – closed = Locked in place, open = free to
   move; one click toggles it for that subassembly or part (the same as the box's Locked in place button and the
   right-click entry, one undo step, tooltip says what it means and that a locked part still moves with its
   subassembly and with joints). Rows inside a locked subassembly show it greyed. No cut-off names at the default
   side-panel width (shorten the ×8 count column if needed). Also check one number in the same screenshot: the header
   said **562 parts**, the selected model's box **564 parts** – find why (hidden / cleaned-up parts, instances?) and make
   them agree or say what each counts in the tooltip.
4. The guide gets "Move, turn and remove" and says the difference with Clean-up; the right-click menu's entries;
   Settings > Keys (0295) will list the keys later.

## Done when

- [ ] Tests: the crane model moved 1 m and turned 90° → Build gives the same motion, moved; the boom subassembly moved
      100 mm before animating → its joint follows; remove a model with joints + a cylinder + a hose → no dangling
      items, save + reopen, undo brings everything back; Delete outside Full access opens the window; Client view refuses
- [ ] An independent tester (a subagent that did not write the code) tries to break Remove (dangling references, a
      model update after a remove, undo / redo) – findings fixed
- [ ] Real-app test; PC check lines `place.move`, `place.remove`; tour stop; function entries + guide anchors; guide
      pictures; tooltips; full suite + GitHub run green; report; merged, version, release

## Design (worker, 23 Nov 2026)

**Files:** `core/place.py` (snap, steps, the Remove window's words), `blender/place.py` (0307's G / R check + Place:
`move`, `back_to_cad`, `carry_over`, the fields' get / set, `numbers`, `delta_for`, `step_delta`, `put_on_floor`),
`blender/remove.py` (`plan`, `lines`, `remove`), `blender/ops_place.py` (operators), `blender/ui_place.py` (the
sub-panel 2 Structure > Place, `draw_place`, the gizmo group `FRESING_GGT_place`); `props.py` `FRPlaceSettings`
(`scene.fresing.place`); hooks: `reimport.py` (`place.carry_over` in step 4), `joints.SPEC_TAGS` (+ `fr_place_frame`),
`lock.py` (Delete / X → `fresing.remove_key`), `context_menu.py` (Move / turn…, Remove…), `ui.py` (lock per tree row,
Remove… in the row box), `ops_panels.py` (`tree_row` action LOCK), `tree.py` (part count).

**Place rules.** Three places of a subassembly / part: *file place* (`fr_file_basis`, stored at its first Place),
*CAD place* (`fr_cad_basis`) and a *free move* (`fr_rest_basis` vs the object's matrix: G / R, exploded views).
**Place moves the CAD place** (and the rest place with it): Build, poses, Reset pose, saved scenes and a model update
keep it; a G / R move stays a pose's free move. A model = its root's matrix (root never a free move; its rest basis =
the import place → "Back to where it was imported"). A joint's member: when the move takes everything the joint
moves, the joint's frame moves along (its old basis on the motion empty, `fr_place_frame`), else the part moves alone
in the motion's coordinates and the axis stays. For a carried part `cad @ rest⁻¹` stays the fixed CAD-parent ↔ motion
relation; after a frame moves the CAD places are worked out again in the CAD pose (`_rederive`). Locked → refused (as
G); built animation → taken off ("Build again"); Client view → refused.
Fields: World = origin and world turn; Model axes = offset from the file place along / about the model's axes. Turns
about the middle of the box. Snap rounds typed / dragged / mouse values; steps are exact.

**Remove.** `plan` counts what goes (parts with a shape, joints whose members all go, cylinders whose barrel or rod
all go, mechanisms with a link that goes, way covers whose section joints all go, hoses / cables / spools / tracks /
trails on a part that goes, labels, decal objects, steps that only move what goes) and what only loses something.
`remove`: (1) those items off by their own Remove; (2) the steps off; (3) per affected model `reimport._take_apart`,
the objects that go out of the scene (kept alive in a collection in no scene), `reimport._put_together` with every
gone uid → "gone:", `_repoint` (labels, sharp spots), `states.remap_uids`, then the objects deleted; tidy as a model
update does. One undo step (the operator's). Import cache untouched.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026 · version 0.2.219

**What changed:**
- **2 Structure > Place** (new sub-panel, `ui_place.py`): the selected model / subassembly / part with its lock,
  World | Model axes, Position (mm) and Turn (°) fields with – / + steps (10 / 100 mm, 15 / 90°), Snap (off, 1 / 10 /
  100 mm, 5 / 15 / 45°), Move with mouse / Turn with mouse (own modal: X / Y / Z, typed number, click, Esc; header +
  status-bar line), Arrows and rings (gizmo group `FRESING_GGT_place`, only while Place – or its window – is open),
  Put on the floor, Back to the CAD place / Back to where it was imported, Remove…. Right-click > **Move / turn…** =
  the same body in a function window (0282's `form_window`).
- **The rules** (in `place.py`'s docstring and the Design above): Place moves the **CAD place** (and the rest place);
  G / R stay a pose's free move. A model = its root. A joint's member moved with everything the joint moves takes the
  joint's frame along (old frame kept on the motion empty, carried by model updates via `joints.SPEC_TAGS`); otherwise
  only the part moves and the axis stays. Built animation → taken off ("Build again"); locked / Client view → refused.
  "CAD place" afterwards = the placed place (Reset pose, poses, Build start there); the file place is kept
  (`fr_file_basis`) for Back to the CAD place; a model update applies the same move to the new file place.
- **Remove…** (`remove.py`, `fresing.remove`): a function window listing what goes and what only loses something;
  Remove = one undo step. Items that live on what goes are taken off by their own Remove (hoses, cables, drums, tracks,
  trails, cylinders incl. pin carriers, mechanisms with their own drive joint, slices, way covers, labels, stickers,
  steps that only move it); the model is rebuilt on what stays through the model update's own path. A partial remove is
  remembered on the model (`fr_removed`): a model update removes those parts again. **Delete / X** outside Full access
  open the window (`fresing.remove_key`, `lock.APP_KEYS`; the Client view's lock still swallows them).
- **A lock in every tree row** (`tree_row` action LOCK): closed / open, greyed under a locked subassembly; works on a
  part row (all its copies) too. Icons a little narrower so names keep their room.
- **Part count**: the model box counted parts without a shape (empties in the STEP file), the header did not – the
  owner's 564 vs 562 is most likely 2 such parts (not seen on his model: it is not in the repository). Both count
  parts with a shape now.
- Function entries `structure.place`, `structure.remove` (+ `structure.move` changed); guide sections "Move, turn and
  remove: Place" and "Remove a model, subassembly or parts" (with Remove vs Clean-up), the keys / right-click list;
  pictures `panel_2_place.png`, `panel_2_structure.png`; PC-check lines `place.move`, `place.remove`
  (MIN_LINES_FULL 130); tour set "Place and remove" with stops `place`, `remove` (MIN_LINES_TOUR / MIN_CHECKS tour 100);
  real-app test `place` (22 checks, group callouts).

**Tested and measured** (web machine, 4 cores, no GPU, test crane `test_crane_a.step` unless named):
- `tests/test_place_remove.py` 13 tests: crane moved 1 m + turned 90° → Build gives the same motion moved (boom,
  trolley, rod, barrel at 3 frames, 0.2 mm); boom subassembly +100 mm → joint axis +100 mm, Build keeps it, the CAD pose
  keeps it, Back to the CAD place puts both back; a placed part survives Reset pose + Go to pose; fields / steps / snap /
  floor; locked + Client view refuse; Remove of the crane (joints, cylinder, label, step) → nothing left, save + reopen
  clean; trolley removed → boom joint and cylinder still work and Build; hoses model removed with its hoses; Delete / X
  bound; a model update keeps a placed part.
- **Independent tester** (subagent, did not write the code): `tests/test_remove_independent.py`, 18 tests; it found 10
  faults – a crash on a model with a Slice (left the project half removed), cylinders removed with their pin carrier
  but not listed, a mechanism listed as going that stayed (and lost its step), a mechanism's drive joint left behind,
  "loses" lines missing (joint on a removed base / ride-on, hose end, cable contact, drum coil, slice target, way
  cover), a drum's coil ID not marked gone, a model update bringing removed parts back, a remove of nothing reporting
  "Removed". All fixed by the author; the tester's 18 tests and the 13 pass.
- Real app `tools/ui_test_place.py` 22/22: the lock button, the gizmo wanted while Place is open, + step moves boom +
  axis and **Ctrl+Z puts both back**, Move with mouse X 100 Enter (100.00 mm), Delete opens the Remove window, Remove,
  **Ctrl+Z brings crane, 2 joints, cylinder back** (joints valid), Client view swallows Delete. 24–28 s.
- PC check `place.move` 3.5 s, `place.remove` 1.7 s (OK); test tour build + Go/check of the two stops; tour clash for
  the set; precheck; tooltip report unchanged (2 old weak rows of `panel_tab`).

**Open points / follow-up tasks:**
- The arrows and rings were not dragged by a test (simulated drags of a gizmo are not reliable here); their drag uses
  the same `place.move` as the fields. Each drag pushes its own undo step from a timer – check on your PC.
- Moving a mechanism's link or a part a cable runs over by Place is not specially handled (mechanisms / cables follow
  their parts live; a Build re-solves them).
- A partial Remove with cables: their contacts on removed parts become plain bends (the window says so).
- 0293 (copy) can reuse `place.move` to put the copy; 0295 lists the Delete / X keys and the mouse keys.

**Owner's check on your PC** (after Update now to 0.2.219):
1. Open a project, or Import STEP… a model.
2. In 2 Structure, look at the end of each tree row: a **lock** next to the eye and the arrow. Click the lock of the
   top row (the model): it opens.
3. Click the model's top row, then open **Place** under the tree. Type **1000** in Position **X** and press Enter: the
   whole model moves 1 m. Click **+** next to Turn **Z** twice (Step 15°): it turns 30°.
4. With Place open, the model shows red / green / blue **arrows and rings**: drag one – it moves or turns.
5. Click **Put on the floor**, then **Back to where it was imported**: it is back.
6. Click **Build & play** after a move: the animation runs where the model now stands.
7. Select a subassembly, press **Delete**: a window lists what goes. Click **Remove**; then **Ctrl+Z**: everything is back.
8. Right-click a part: **Move / turn…** opens Place in its own window; **Remove…** opens the same window as Delete.
9. Check the number in 2 Structure's header against the selected model's box: they should be the same now.
