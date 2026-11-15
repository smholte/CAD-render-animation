# 0129 – Motion extras: sequence watches the whole model, riders fly on their own, "Back to CAD" step, close-ups

**Who:** worker · **Status:** done (15 Nov 2026, 0.2.102; web session, branch `ccr-006450f6-mv1oyp`) · **Branch:** `task/0129-motion-extras`
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

**Chat / date:** Claude Code on the web (Opus), 15 Nov 2026 – version 0.2.102

**What changed:**
- `core/sequence.py`: `plan(..., obstacle=, carried=)`; a part whose way runs into a part outside the subassembly
  takes another way (`other_ways`: the subassembly's axes, sideways before backwards) clear of it and of the parts
  still in place, up to `ROUNDS` plans; riders never leave before their carrier (any order); stacking for every
  direction with `NEAR` (cos 25°) and the later part's whole way (start + end box) – "Away from the centre" stacks.
- `blender/sequence.py`: riders are movers (`Movers.carriers`); their keys are written per frame inside their own and
  their nearest carrier's windows (exact on every frame; LINEAR between); the preview does the same. `Obstacles`:
  NumPy box filter over the model's other visible parts, then the swept surface of the part (back faces at the start,
  front faces at the end, silhouette edges swept; mesh 0.1 mm inside) against their triangles near the subassembly
  (BVH overlap) + rays back from their points. Ray points of `Rays` 0.1 mm inside too (a part sliding along the face
  it sits on grazed the chamfer and was "blocked"). The preview's kept plan compares places within 1 µm (float32 noise
  made it plan twice – also in 0.2.101).
- New step **Back to CAD** (`CAD`, `cad_whole`, `animation.cad_targets`, G-code `_walk` follows it), panel box,
  tooltip. Product video: Back to CAD after the poses; steps on whole frames; close-ups from saved cameras that do
  not show the whole model (`shows_whole_model`: the import's camera counted as a "close-up" before), else
  `pick_spots` (decals – type plate first –, then the moving parts round each joint, the iso view that sees most).
- Test model `test_sequence_frame.step` (`tools/make_test_sequence.py --frame`), tour stops `sequenceframe` and
  `backtocad` (set "Round a frame, back to CAD"), PC-check lines `animation.sequence_frame`, `animation.back_to_cad`,
  function list, guide (sequence, new Back to CAD section, product video), pictures `panel_6_back_to_cad.png`,
  `panel_6_product_video.png`.

**Tested and measured** (4-core web machine, Blender 5.2.3 as a module):
- New tests: 9 in `test_sequence.py` (core: centre stacking, riders' order, obstacles, other ways; Blender: the frame
  model – parts under the beam sideways, bolts up, back home within 0.01 mm, **0 clash rows** –, the same parts go up
  with the frame hidden, riders exact on every frame, preview with riders, Back to CAD whole/subassembly/motor/operator,
  saved + reopened + built through the queue's own set-up with every driver a simple expression), 3 in
  `test_product_video.py` (Back to CAD after the pose, close-ups frame a moving part, saved close cameras win, the
  crane: framed at the boom's hinge). `test_motion_fixes.py`'s pair-by-pair reference follows the new stacking rule.
- Locally: sequence + product video + motion fixes + independent 82 passed; tour + functions + guide + every tour
  animation 0 clashes 111 passed (11.7 min); the four PC-check lines OK (8 s).
- **Preview, demo TENSIONER** (small demo, 264 movers – 260 + 4 riders), old 0.2.101 vs new, same file: per slider
  step after the first two **84–95 ms → 83–106 ms** (unchanged). A fresh plan (first touch; the first touch also
  clears the demo's keys, ~3.3 s, as before): AXIS 3.7 + 0.31 s → 5.5 + 0.12 s, CENTRE 0.27 + 0.29 → 3.2 + 0.14 s,
  UP 0.31 + 0.31 → 1.9 + 0.09 s (the old code planned twice). Going up, 93 of the 264 parts now go another way (the
  cable runs through the tracks: the parts under it go sideways); checking 264 ways against 974 parts outside costs
  1.5–2.5 s.
- **Close-ups on the demo** (no automated test: `demo*` is task 0125/0126's): `pick_spots` 0.08 s, "Quadrant tip" (42
  parts) and "Handler tilt", fully in frame, seen 100 %; its product video keeps its own saved cameras.
- Independent tester (subagent, did not write the code): 28 tests in `tests/test_motion_extras_independent.py`, three
  faults found and fixed by the worker (last round's way kept the old way's order and distance – a part flew through a
  part in place; the obstacle cache answered for 1.2 × the asked distance; float32 put Back to CAD one frame into the
  pose: false warning).

**Open points / follow-up tasks:**
- Thor's block (0112's Thor project) not tried: its STEP needs the site kit's pinned sources; the frame test model
  covers riders two levels deep.
- Back to CAD right after a Take apart flies all parts home at once on straight lines: bolts pass through the cover
  (tester, 4–7 mm). Use Put together for that; a Back to CAD that plays a sequence backwards could follow.
- A Put together with no Take apart before it jumps its parts out at its first frame; the clash check reads that jump
  as motion (older than 0129).
- Obstacles and rays read the parts' CAD meshes: parts that the app draws elsewhere by Geometry Nodes (track pads)
  are seen where their mesh is.
- A fresh preview plan on big subassemblies with many blocked ways takes seconds (above).
- GitHub runs: 3 – one cancelled by my own next push, one red (my new guide picture not used in a chapter; plus the
  spool real-app test that failed at random, fixed by task 0127 on main meanwhile), one green (7305df0, 20 min);
  `main` fast-forwarded to it. Leftover branch to delete on github.com: `ccr-006450f6-mv1oyp`.
- The progress note `claude/render-app-progress.md` is in the claude.ai project: this session cannot reach it (lead).
