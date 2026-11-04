# 0011 – Several joints on one subassembly (moves add up)

**Who:** worker · **Status:** running · **Branch:** `task/0011-stacked-joints`
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

- [ ] Owner's example as a test: Y +1000 mm then X +500 mm → offset exactly (500, 1000, 0) mm;
      also rotate-on-slide and slide-on-rotate against hand-calculated positions
- [ ] Stacks survive: pose save/apply, animation bake (both steps in one animation), model update
      (`tests/data` crane revisions), save + reopen, undo; removing the middle joint of three
- [ ] Real-app click test step added (`tools/ui_test_app2.py`): add two joints on one subassembly
      through the buttons; screenshots of 4 Motion checked with `tools/ui_screens.py`
- [ ] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- Couplings, motors, cylinders, linkages: tasks 0012–0014 (same lane, after this one).
- Anything in 3 Looks, rules, materials, the importer (task 0008/0010 lane).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
