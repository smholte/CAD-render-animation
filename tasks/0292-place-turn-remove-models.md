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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
