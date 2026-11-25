# 0326 – Faster joint drag with many parts

**Who:** worker · **Status:** running · **Branch:** `task/0326-faster-joint-drag`
**Started by:** lead, 25 Nov 2026 (0315's slow place 3, the owner's Stress run on his PC) · **Model:** Opus · effort High
**Area:** Motion lane – `blender/joints.py`, `blender/handlers.py` (what runs after a joint moves), and the per-move
hooks they call (hover, cables that follow, live clash, lead motions' "moved by") only where the profile points; their tests,
CHANGELOG.
**Not:** `pccheck/checks.py` and `pccheck/stress.py` (0332 / 0333 / 0325 change them – measure with the existing
`stress.drag` line, do not change it), `ui_motion.py` and `ui_lead_motions.py` (0333 changes them), the clash check itself
(0327), the importer.

## Goal

On a big model, a joint follows the mouse smoothly: the crane slews as you drag, though 11,000 other parts stand still.

## Background

- 0315 (`tasks/0315-stress-model-10k-parts.md`, item 3): 78 ms per step on the 4-core web machine.
- **The owner's Stress run, 25 Nov 21:06, 0.2.257** (Ryzen 9 9900X, RTX 3090): `stress.drag` **51.4 ms per step**, slowest
  57.9 ms – about 19 steps a second; playback of the built animation 13.6 ms/frame on the same model. So moving a
  joint by hand costs about 4× a played frame: something runs per drag step that playback does not need.
- `stress.drag` = `joints.set_value` + a view-layer update, 40 times (`pccheck/stress.py`, "stress.drag").

## What to do

1. **Profile first** (cProfile + a timer per handler) one drag step on the Stress model (`tools/make_test_stress.py`):
   our handlers vs Blender's own depsgraph update. Put the split in the report.
2. Fix what is ours: e.g. handlers that walk every object on each update, work that can wait until the drag ends
   (mouse up), work only for parts the joint moves. If most of it is Blender's own, say which part and what would help.
3. Keep behaviour: cables / hoses that follow, live clash colouring, lock, undo (one step per drag), lead motions'
   "moved by" and the Client view all work as before (their tests stay green).

## Done when

- [ ] `stress.drag` ≤ about 25 ms per step on the web machine (was 78), the profile split before / after in the report
- [ ] A drag on the demo project and the crane test model works as before (tests for followers, clash colour, undo)
- [ ] Tests added/updated; full suite passes; GitHub run green
- [ ] CHANGELOG; the owner's re-check line in the report ("PC check > Stress – the drag line", target ≤ about 16 ms
      on his PC)
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 25 Nov 2026.

**What changed:**
- **The cause (profile of one drag step, stress model 11,228 parts, 4-core web machine):** `joints.set_value` tagged the
  joint's motion empty with a bare `update_tag()`. That tells Blender *everything* of the object changed – its shading
  too – and Blender then went over every object of the scene again: **~65 ms of the 82 ms step**, the same for the
  crane's slew (224 parts under it), the boom (96), the hoist (6) and the davit (4). Our own scene-update handlers were
  only **2.6 ms** of it (vessel motion's name lookup 1.65 ms, the click handler's walk over the updated objects 0.68 ms,
  the other 12 handlers 0.3 ms together).
- `joints.set_value` now tags what Blender's own slider tags when a custom property is dragged: transform + data
  (`joints.tag_moved`, `joints.MOVED`). Everything that calls it gets the speed: poses, lead motions' slider, the PC
  check, scripts.
- `vessel_motion._on_depsgraph`: checks "vessel motion on?" before looking the rig up by name (1.1–1.6 ms per update
  on 11,500 objects).
- `handlers._on_depsgraph`: walks the updated objects only when a part tree is kept (`logic.tree_kept()`); during a
  drag none is, so nothing to drop.
- CLAUDE.md section 8: a line on the bare `update_tag()`.

**Tested and measured** (4-core web machine, no graphics card; stress model at Normal, 11,228 parts, 8 joints made by
the `stress.build` line, saved once and re-opened for each measurement):

| One drag step (`set_value` + view-layer update) | before | after |
| --- | --- | --- |
| `stress.drag` line itself, real Blender 5.2.3 | **74.8 ms** (slowest 97–112) | **16.4 / 16.8 / 21.3 ms** (3 runs) |
| same loop, real Blender, 2 runs x 2 | 67–78 ms | 14.2–16.4 ms |
| same loop, Blender as a Python module | 82.4 ms | 13.2–15.7 ms |
| of which our handlers | 2.6 ms | ~0.2 ms (all handlers paused: the same time) |
| of which Blender | ~75 ms | ~14–15 ms |

- **What is left is Blender's own:** any scene update on this model costs ~15 ms, whatever moves – moving one lone empty
  costs 17 ms, the slew of 224 parts 14–16 ms. Playback of the built animation is the same 14 ms per frame. What would
  help further: fewer objects (e.g. the many bolts as instances of one object per subassembly) – not in this task.
- The interactive drag in 4 Motion > Joints sets the property through Blender's slider, which already tagged only
  transform + data: it was not slowed by this; poses, lead motions and the PC check line were.
- New `tests/test_joint_drag.py` (4 tests; 3 failed before the fix): the drag tags the motion's transform and not its
  shading; parts and a coupled follower move right among 1,500 bystander objects; the click handler and vessel motion
  skip their work. Locally: couplings, table couplings, batches, stacks, mechanisms, lead motions, cylinders, hoses,
  moving cables, rollers, tracks, drums – 219 passed; tree cache, vessel motion, blender, motion fixes, phase 2, hover:
  see below.
- The owner's re-check: **PC check > Stress – the line "Stress model: dragging a joint"**: was 51.4 ms per step on his PC
  (0.2.257); expected about 10–12 ms (scaled by the 4.5x measured here), target ≤ about 16 ms.

**Open points / follow-up tasks:**
- The ~15 ms floor is Blender's per-update cost on 11,500 objects (also playback's 14 ms/frame). Reducing it means fewer
  objects in the scene (instancing repeated bolts / nuts / washers) – a study if the owner wants big models faster.
