# 0129 – Motion extras: sequence watches the whole model, riders fly on their own, "Back to CAD" step, close-ups

**Who:** worker · **Status:** running (web session, branch `ccr-006450f6-mv1oyp`) · **Branch:** `task/0129-motion-extras`
**Started by:** lead chat, 15 Nov 2026 (owner: "all 5 suggested tasks") · **Model:** Opus · effort High
**Area (Motion lane):** `fresing_render/core/sequence.py`, `blender/sequence.py`, the product video (task 0101's
files), the pose steps in `blender/animation.py` / `states.py` (additive: a new step kind), `ui_motion.py` (panels 4
Motion, 6 Animation – not the cable boxes), their tests, tour, PC check, guide, function list. **Do not edit:**
`paths*`, `flex*`, `spool.py`, `tracks.py`, `demo*` (task 0125/0126), `tools/site_projects/`, `site/` (task 0128).
`joints.py` only additively – task 0127 may fix a driver race there; whoever merges second updates its branch.

## Goal

The Assembly sequence and the product video handle real models: parts taken out do not fly through the frame they sit
in, a part that rides on a moving part can still be taken off by itself, a pose can be undone in a video with one
step, and the product video's close-ups pick sensible spots.

## Background

Open points of 0100 (`tasks/0100-assembly-sequence.md`) and 0101 (`tasks/0101-product-video.md`):
1. **Blocked way:** only parts of the subassembly are in the blocked-way check; a frame round it (another subassembly)
   shows up only in the Clash check. Wanted: parts outside the subassembly that are near its parts' ways block too
   (rays or boxes against them – do not cast against the whole model per part: use the vectorised plan of 0121,
   `core/sequence` "in the way" / "across" in NumPy). Preview speed on the demo's TENSIONER (260 parts) must stay
   about 0121's (84–90 ms per step).
2. **Riders:** a part that rides on another mover (a joint on a part) only rides along; it does not fly on its own.
   Wanted: it can be taken off like any other part, starting from where its carrier has put it (Thor carrying a
   block – 0112's Thor project is a good real case; a small test model too).
3. "Away from the centre" does not stack: parts going nearly the same way can end close together – stack them as the
   other directions do.
4. **"Back to CAD" step:** a saved pose stays where it ends; add a step (6 Animation) that brings the joints of a
   subassembly or the whole model back to their CAD values over its duration (eased as Go to pose). The product video
   uses it after its pose section.
5. **Close-ups:** the product video's close-ups are just the first two saved cameras. Wanted: when there are no
   saved close-up cameras, pick spots that show something (moving parts, joints, decals/type plates), framed with
   0017's view framing; saved cameras still win.

## Done when

- [ ] 1: a part whose way runs through a part outside the subassembly goes another way or waits (test model with a
      frame round a subassembly: 0 clash rows on the sequence); preview speed measured before/after.
- [ ] 2: a rider taken off from its carried place (test + Thor's block, if Thor's sheet can do it without editing
      `tools/site_projects/` – otherwise only the test model and a note).
- [ ] 3: "Away from the centre" stacks (test: no two parts' end places closer than the others' rule).
- [ ] 4: "Back to CAD" step with tooltip; works with scripts off and in the queue; the product video ends its pose
      section with it.
- [ ] 5: close-ups chosen as above (test on the crane and the demo: the chosen spots frame a moving part).
- [ ] Every visible change: tooltips, guide + anchors, function-list entries (`core/functions.py`), tour stops,
      PC-check lines (CLAUDE.md section 6). Every tour animation 0 clashes.
- [ ] Tests; GitHub run green; report filled in.

## Not in this task

Fly a path instead of the orbit in the product video (later). Contact sheet checks by eye (owner on his PC).

## Design (worker, 15 Nov 2026)

No parallel writers (the pieces share `sequence.py`, `animation.py`, `props.py`, `ui_motion.py`); one independent tester
(subagent, did not write the code) at the end, its findings fixed by the worker.

**core/sequence.py** (no Blender)
- `plan(parts, st, blocked=None, obstacle=None, carried=None)`. `Settings.frame`: the subassembly's 3 axes (world,
  columns) for other ways. `blocked(i, j)` as before (reads `blocked.dirs`, now updated when a part changes its way);
  optional `blocked.hit(i, j, u, dist)` for a part's actual way. `obstacle(i, u, dist) -> bool`: part i, moving
  `dist` m along `u`, runs into a part outside the subassembly.
- Rounds (at most 4): order -> travels -> each part's way checked against the obstacles (its travel) and the parts
  still in place when it leaves; a blocked part takes the next of its other ways (the wanted one, then the
  subassembly's ±X/±Y/±Z and world up, most like the wanted first, the opposite last) that is clear of both; then
  plan again. What is still blocked after that is reported by Blender (as before).
- Distance by size per part along its own way (the same for all when nobody changed way).
- `carried[i]` = parts that ride on part i (a joint on i carries them): i never leaves before them (any order).
- Stacking for every direction: a part ends beyond each part that leaves after it going nearly the same way (cos ≥
  `NEAR` = cos 25°) and whose way (start to end box) lies across its own way. Along an axis / up nothing changes
  (all the same way); "Away from the centre" now stacks too.

**blender/sequence.py**
- `movers`: riders are movers too (`Movers.carried`: index map for core); `Movers.riders` kept for the count.
- `Obstacles`: the model's other visible parts near the subassembly (world boxes, NumPy filter on the region the
  subassembly can reach); per obstacle a BVH of only its triangles in that region; a part's way = its mesh shrunk
  0.1 mm, the start and end copies + its edges swept (exact swept surface), BVH overlap; plus rays from the
  obstacle's points inside the swept box back against the part (an obstacle fully inside the way).
- Riders' keys: x(f) = own offset·s(f) − Σ carriers' offset·s(f) (world), one key per frame inside the windows
  (LINEAR), so the part stays where it flew while its carrier flies out under it (exact at every frame).
- Blocked-way warnings also name parts outside the subassembly.

**"Back to CAD" step** (kind `CAD`, `BLOCK_KINDS`): `cad_whole` (default on) or the picked subassembly (`target_uid`);
its joints (a member in it) to 0 – a motor to the nearest whole turn – and its moved parts to their CAD places, eased
as Go to pose; G-code's joint state follows it (`gcode.py`, additive). Label "Back to CAD" / "Back to CAD <name>".

**Product video**: a Back to CAD step after the saved poses. Close-ups: saved cameras win; else `pick_spots`: type
plates / decals first, then the moving parts of the joints (longest travel first), each framed with
`cameras.add_camera(points=…)` from the iso view that sees most of it (rays from the spot to the camera).

**Test model**: `tools/make_test_sequence.py --frame` -> `test_sequence_frame.step`: a portal frame over a slide unit
(rail block, carriage, gripper block, cover, 4 bolts); the tests add a slide joint on the rail block (carriage +
block) and one on the carriage (block): riders.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
