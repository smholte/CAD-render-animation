# 0011 – Several joints on one subassembly (moves add up)

**Who:** worker · **Status:** done (0.2.10) · **Branch:** `task/0011-stacked-joints`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Motion · **Area:** `blender/joints.py`,
`blender/states.py`, `blender/animation.py`, `blender/ops_motion.py`, `blender/ui_motion.py`,
`blender/reimport.py` (joint part only), `blender/props.py` (joint properties only, additive), `tests/`.

## Goal

A part or subassembly can be moved by more than one joint, and the moves add up. Owner's example:
joint 1 slides the subassembly 1000 mm in Y, then joint 2 slides it 500 mm in X – afterwards it
sits at X +500 / Y +1000 from where it started. This works together with all other joints
(chains, poses, animations, model updates).

## Background

- How a joint is built: see the docstring of `blender/joints.py` (base → frame → motion → moving
  subassemblies; value in `fr_value` with a driver; chains through "Sits on" = the frame's parent).
- Today the moving objects are re-parented under one joint's motion empty, so a second joint on
  the same object takes it away from the first.
- "Sits on" (`j.base`) only accepts model objects (`_model_object_poll`), and `to_specs` /
  `rebuild_from_specs` store the base by part ID – a joint sitting on another joint's motion
  empty has no part ID yet.
- Owner's decision (4 Nov 2026): fine to proceed with the lead's proposal below.

## What to build

1. **Stacking.** Adding a joint to objects that already move with joint A: the new joint B sits on
   A's motion (B's frame is parented to A's motion) and the chosen objects move to B's motion.
   Other members of A stay with A. Works for any mix of rotate and slide, and for more than two.
2. **Order.** With rotations the order matters ("turn, then slide" ≠ "slide, then turn"). Default:
   the newer joint rides on the older one (its axis moves with it – like a crane: slew, then
   luff). The joint details show "Rides on: Joint A"; a button swaps the order of two stacked joints
   (rebuild in the CAD pose, keep values). Optional, only if simple: "axis stays fixed in the
   world" for a stacked joint – leave it out and say so in the report if it is not simple.
3. **Saved data.** Specs store "sits on joint <name>" next to "sits on part <ID>"; model updates
   (`reimport.update_model` → `dissolve_all` / `rebuild_from_specs`) rebuild stacks in the right
   order. Old projects keep opening unchanged.
4. **Everything else keeps working with stacks:** poses (store each joint's value), "Back to CAD
   position", Explode, free moves, animation steps (one step per joint; steps in sequence and in
   parallel), Fit camera to the whole motion, limits, flip, joint types, removing a joint from the
   middle of a stack (the joints above it move down onto what it sat on), undo.
5. **UI (4 Motion):** when the selection already moves with a joint, Add joint says it adds a
   joint on top ("Adds a second joint on top of 'Joint A'"); the joint list shows stacked joints
   indented under the one they ride on. Follow the layout rules in `blender/ui.py`.

## Done when

- [x] Owner's example as a test: Y +1000 mm then X +500 mm → offset exactly (500, 1000, 0) mm;
      also rotate-on-slide and slide-on-rotate against hand-calculated positions
- [x] Stacks survive: pose save/apply, animation bake (both steps in one animation), model update
      (`tests/data` crane revisions), save + reopen, undo; removing the middle joint of three
- [x] Real-app click test step added (`tools/ui_test_app2.py`): add two joints on one subassembly
      through the buttons; screenshots of 4 Motion checked with `tools/ui_screens.py`
- [x] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- Couplings, motors, cylinders, linkages: tasks 0012–0014 (same lane, after this one).
- Anything in 3 Looks, rules, materials, the importer (task 0008/0010 lane).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 4 Nov 2026 (evening).

**What changed:**
- `blender/joints.py`: a joint added to objects that already move *directly* with joint A rides on
  A (frame parented to A's motion; the objects move to the new joint). Nothing new is stored:
  "B rides on A" is `B.frame.parent is A.motion`, so older projects open unchanged. New helpers
  `rides_on`, `riders`, `depth`, `moved_objects`, `tree_order`, `stack_info`, `swap_check`/`swap`.
  `remove`: what the joint moved goes back onto the joint under it (or the CAD parent); joints
  riding on it go down onto what it sat on. `remove_members` likewise. `set_axis`/`flip` keep the
  joints riding on it in place. A mixed selection (one part moves with a joint, another not, or
  with another joint) is refused with an explanation. `sync_base`: a stacked joint sits on no part
  ("Sits on" empty, hidden in the panel).
- Model updates: specs carry `base_joint`; `rebuild_from_specs` builds stacks bottom first
  (also after Swap order, when the bottom joint is newer in the list), rebuilds a bottom joint that
  moves nothing itself, puts the joint list back in its old order, and passes the whole axis
  matrix (`create(frame_world=...)`). Found on the way: a vertical axis rebuilt from point +
  direction could come back turned about its own axis, which turned the joint riding on it
  (test `test_model_update_rebuilds_stacks[True]` failed before the fix). `dissolve_all` removes
  the top of each stack first.
- `blender/ops_motion.py`: new `fresing.joint_swap` (Swap order; greyed out with the reason in
  its tooltip when the lower joint also moves other parts); Remove reports which joints moved
  down; Add joint / pick tool refuse a mixed selection before the pivot click; "Select" selects
  everything a joint moves through its stack.
- `blender/ui_motion.py` (4 Motion): "Adds a joint on top of '…': the moves add up" above the Add
  buttons; joint list shows a stack indented under its bottom joint (`filter_items` order);
  value field narrower so names fit; details: "Rides on '…'" + Swap order; Set-up: "Moves:"
  (through the stack) and "Carries:".
- Not done (optional in the brief): "axis stays fixed in the world" for a stacked joint. It needs
  a counter-motion (constraints or extra drivers) and is not simple; Swap order covers the usual
  case (slide-then-turn vs turn-then-slide).
- Tools: `ui_test_app2.py` stack steps; both click tests close Blender's splash and start the
  import one step later (with no splash open, the Esc reached the running import and cancelled
  it); `ui_screens.py` `UISHOT_STACK=1` / `bottom`. Docs: README-install, CLAUDE.md section 8.

**Tested and measured** (2-core Linux test machine, test crane `tests/data`, no EGR model):
- 17 new tests (`tests/test_stacked_joints.py`), all against hand-calculated positions: owner's
  example Y +1000 then X +500 → (500.0, 1000.0, 0.0) mm, also when the second joint is added
  with the first at 0 or at 1000; rotate-on-slide (axis picked in the moved pose rides along);
  slide-on-rotate; Swap order both ways; two slides swapped = no change; mixed selections
  refused; three-joint stack, remove the middle, then the bottom, then the top; taking the part
  off the top joint puts it on the one under it; flip / type change / limits in a stack; pose
  save/apply, "Everything back to CAD position", Explode and back; free move survives a third
  joint; animation with three steps (two together, one after) checked at five frames; save +
  reopen; model update A → B with a 4-joint set-up (stack of three + boom luff), normal and
  swapped order; a stack whose parts are gone.
- Full suite on the branch after merging main 0.2.8 and the review fixes: 1,272 passed (an earlier run:
  1,269 passed before the review fixes (the render-queue test timed
  out once while two real-app Blenders shared the CPU; passed alone, 6 min).
- Real app (Blender 5.2.3 Linux, virtual screen, packaged extension): `ui_test_app2.py` 39/39
  (new: first joint with Add slide joint, second joint with Add rotate joint + a click on the
  moved trolley's top face, axis through the clicked point, moves add up, undo/redo, Swap order
  button, Remove the bottom joint); `ui_test_app.py` 22/22.
- Screenshots of 4 Motion (150 % UI scale, default side-panel width, all folds open) checked:
  top joint selected and bottom joint selected; no cut-off labels after narrowing the value field.
- No speed numbers: stacking adds no work to playback or rendering (plain parenting and drivers);
  the joint list does one pass over the joints per redraw.

**Independent review** (a separate agent that did not write the code; joint diff, scratch runs):
- Fixed, each with a test that failed before: (1) a model update left out a bottom joint whose
  "Sits on" was cleared (it moves nothing itself), so the joint on top lost its move – the update
  now judges a joint by everything it moves and never splits a stack from below; (2) Swap order
  crashed when the joint below was broken (arrow deleted) – now greyed out with the reason;
  (3) removing a broken bottom joint left the joint on top hanging in the world – it now goes onto
  the CAD parent at the place its parts say; (4) Add on a bottom joint took the part off the joint
  on top (losing that move) – refused with the reason; Remove there says where to remove it.
- Checked fine by the review: no list items held across list changes, CAD-pose maths of take-out,
  swap and axis changes, `frame_world` rebuild, `filter_items` order, loops, old projects.
- Left as is: with a filter text typed in the joint list, a joint on top whose bottom joint is
  filtered out still draws indented (cosmetic).

**Open points / follow-up tasks:**
- Joints whose moving parts come from two different models (possible since phase 2): a model
  update of one model drops the other model's parts from the joint (before stacks too), and a
  stack spanning both models is rebuilt only partly. Rare; a follow-up if the owner ever does it.
- Owner test on his PC: two joints on one subassembly of a real machine (steps in the chat).
- "Axis stays fixed in the world" for a stacked joint, if the owner ever needs it.
- Swap order only works when the lower joint moves nothing but the upper one; a "split" (move the
  lower joint's other parts to their own joint first) could be added if that comes up.
