# 0157 – People in the scene: walk paths, carry items, actions and meetings

**Who:** worker · **Status:** done 16 Nov (0.2.128); was: waiting – starts after 0155 is merged (uses its human figure and rig); may run beside 0156
if their files stay apart (say so in TASKS.md when starting) · **Branch:** `task/0157-people-paths-actions`
**Started by:** lead chat, 16 Nov 2026 (owner) · **Model:** Opus · effort High · **Place:** Claude Code on the web,
environment "CAD-render-animation". Subagents allowed (CLAUDE.md section 2): interfaces first, an independent tester.
**Area (new People lane):** new `core/people.py` (paths, timing, gait, action list – no Blender), new
`blender/people.py`, `ops_people.py`, `ui_people.py` (a sub-panel, e.g. 5 Scene & Render > People or 6 Animation >
People – follow `blender/ui.py`'s layout rules), additive lines in `props.py`, `animation.py` (Build bakes the people),
their tests, the guide, tour stop, PC-check line, function list.
**Do not edit:** `toolchange.py` (0156), `core/surroundings.py` / props' meshes (0155 owns the figure: import and use
it, ask the figure's API only), the Web 3D lane (0142/0143), sea / demo code.

## Goal

The owner places people in a scene and tells them what to do along a path – walk, stop, carry, put down, greet, talk –
and Build turns it into a believable animation, e.g.: *a person walks in carrying a small toolbox, stops next to
another person, puts the box down, greets them (handshake or wave) and starts talking.*

## What to build

1. **People:** add a person (0155's figure: outfit, height, a name the owner gives), as many as wanted; place by
   clicking on the floor / deck (snaps to the surface below, rides on a moving deck with vessel motion – 0085).
2. **Path:** click points on the floor (a curve shown in the view, editable afterwards: move / insert / delete points),
   smooth corners; the person keeps feet on the surface (ray down per step, stairs not needed now – say if a slope
   is too steep).
3. **Actions along the path** – a list per person, in order, each with a place on the path (at a point / at the end) and
   a duration where it applies: *walk* (gaits: **stroll, walk, brisk, carry-walk, run**, each with its speed and
   stride; the stride matches the speed so feet do not slide), *stop*, *turn to face* (a point, another person, a
   part), *pick up* / *put down* (an item), *wave*, *greet* (handshake with another person: both arrive, both reach,
   hands meet – timing worked out together), *talk* (idle gestures, head turns, a slight sway; two people talking face
   each other and take turns), *point at* (a part), *look at*, *idle*, *operate* (hands on a panel / part – reuse
   0156's arm reach if merged, else hands to a point with IK).
4. **Carried items:** a menu of items (from 0155's props + small ones: toolbox, clipboard, tablet, hard hat, cable
   drum, crate, spanner, hose) – carried in one or both hands with the right grip and arm pose, put down where the
   action says (on the floor / a table / a part's top), picked up again later.
5. **Waiting for each other:** an action can wait for another person's action ("greet when Anna arrives") so meetings
   line up whatever the walking times.
6. **Build:** everything baked to keys (works with scripts off, in the queue, saved scenes, product video, test tour);
   the people's paths avoid the machine: a warning when a path runs through a part (the clash check knows people,
   0 clashes on the tour set); a Preview slider like the assembly sequence's.
7. **Speed:** the rig and keys stay light – measure frame time with 1, 5 and 20 people on the demo deck.

## Done when

- [ ] The owner's example works as a test-tour stop (two people, toolbox, stop, put down, greet, talk) and as a test
      that checks the order, the meeting time, feet on the floor (no sliding above a few mm per step), the box on the
      floor after "put down", 0 clashes.
- [ ] Tests for paths (length, smoothing, surface following), gaits (speed ↔ stride), waits between people, carry
      grips, old projects without people unchanged.
- [ ] A short clip of the example (test model or the demo deck) in `tasks/img/0157_*`; frame time with 1 / 5 / 20
      people.
- [ ] Tooltips, guide, PC-check line, function list; GitHub run green; merged; version (CLAUDE.md section 7).

## Not in this task

Crowds / random people, stairs and ladders, sitting, people on the web page (a later Web 3D task), lip-sync / voices.

## Design (worker, 16 Nov 2026)

**The rig (shared with 0156).** `core/person_rig.py` (no Blender) + `blender/person_rig.py`.
- Bones = `props_detail.BONES` (17, same names, same parents). The mesh is made in the rest pose = `POSES["STANDING"]`,
  scaled to the height and lifted onto z = 0 exactly as `props_detail.person()` does; the armature's bones sit on
  `props_detail.skeleton()` of that pose, in the same (scaled, lifted) figure space: the figure faces -y, its right hand
  at -x, z up, metres.
- A pose is `person_rig.Pose`: `local[bone]` = 3×3 turn of the bone against its parent in `props_detail` frames (what
  `props_detail._local` gives), `pelvis` = the pelvis head in figure space, `fingers` / `point` per hand (0 open … 1 fist;
  index finger straight). `Figure(height)`: `rest()`, `from_angles(pose id or angle dict)`, `fk(pose)`,
  `leg_ik`, `arm_ik`, `look`, `blender_quaternion(pose, bone)` (Q = C⁻¹ L_rest⁻¹ L C, C = the fixed turn from a
  props_detail frame to Blender's bone frame, Y along the bone), `blender_location(pose)`.
- Blender: the person object (the prop, `fr_prop = PERSON`) stays the thing that is placed and moved; its armature
  "FR rig <name>" is its child with an identity local matrix; an Armature modifier comes before "FR prop detail".
  Weights: every vertex takes the weights of its loft ring's centre (nearest bone, blended with the parent / child
  bone near a joint); other shapes by their own points. Hand shapes: shape keys `open_l/r`, `grip_l/r`, `point_l/r`
  (same topology, other curl) driven by simple-expression drivers from the armature's custom properties
  `fr_open_l` … (keys live on the armature: Clear keys drops them). `person_rig.ensure(ob)`, `rig_of(ob)`,
  `set_pose(ob, pose)`, `key_poses(ob, frames, poses, roots)`, `remove(ob)`; `props_scale.rebuild` hands a rigged
  person to `person_rig.rebuild` (pose / height / clothes kept working).

**People (0157).** `core/people.py` (no Blender): gaits, the path (smoothed corners, length, point at a length,
ground per step through a `ground(x, y)` callback), footsteps (feet planted in the world, heel and toe roll, the step
length fitted so the walk ends on the point; speed = step × cadence, so feet never slide), the schedule (actions in
order, an implicit walk to an action's point, waits for another person's step, GREET / TALK paired with the other
person's matching action: both start when the later one is ready), then `Plan.sample(name, t)` → root place + Pose,
and the items' states (held by a hand / placed at a world matrix) with their times. `blender/people.py`: settings →
specs, the path curve "FR path <name>" (poly curve, edited with Blender's own edit mode), ground by rays at rest,
items ("FR item …", collection "FR people"; Child Of the hand bone with keyed influence), bake at Build (after
`spool.bake`: keys on the person object, the armature and the items; frame_end stretched to the people's time),
Clear keys puts them back, the Preview slider, the clash hook (people's rest-pose meshes checked as bodies; items left
out), the path warning (rays from the path to the parts at frame 1). `ops_people.py`, `ui_people.py` (6 Animation >
People). Settings: additive lines in `props.py` (`FRPersonSettings`: path, actions, start, carry; `FRPersonAction`).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026 (branch `claude/nifty-darwin-mwn2nz`, the session's assigned name
instead of `task/0157-…`). Version **0.2.128**.

**What changed:**
- **The person's rig (also for 0156)** – `core/person_rig.py` (no Blender) and `blender/person_rig.py`. API below.
- `core/people.py` (no Blender): gaits (stroll 0.9, walk 1.35, brisk 1.75, carry-walk 1.0, run 3.2 m/s), paths
  (corners rounded, a sharp turn-back walked as two walks with a turn), footsteps planted in the world with heel and
  toe roll on the floor's tilt (step length fitted to the walk, speed = step × steps per second), the schedule
  (implicit walks to an action's point, waits for another person's step, Greet / Talk paired: both turn to each other
  in the same time and start together; circles of waits found up front, left out and warned), 12 actions, 8 items
  (grips per hand; the person steps up to an item to pick it up; the bend depth is worked out so the hand is on the item
  at the grab), the frames (`Plan.sample`, `pose_at`).
- `blender/people.py`: settings → plan (rays down for the floor, vessel at rest), Build keys (person object, armature,
  items with keyed Child Of influences; the animation's length includes the people), Clear keys puts everyone back, the
  Preview slider, the path curve "FR path <name>" (Blender's own edit mode), the point numbers drawn in the view, the
  clash hook (acting people checked as bodies), the path warning, the example and its check. `ops_people.py` (12
  operators), `ui_people.py` (6 Animation > People). Additive: `props.py` (`FRPersonAction`, person path / steps /
  start / holds, `people_preview`), `animation.py` (length, bake, clear), `props_scale.rebuild` (a rigged person keeps
  its rig), `props_detail.person()` takes an angle dict as pose (the hand shape keys need it).
- Tour stop `people` (set "People walk and meet"), PC-check line `people.walk`, function entry `animation.people`,
  guide section "People: walk, carry and meet" (`panel_6_people.png`, `people_meet.jpg`; modes `people_panel` and
  `people` in `tools/guide_screens.py`), `tools/measure_people.py`, tooltip report knows the panel (0 missing).

**The rig API (0156: pose and key a person with it)**
- `person_rig.ensure(ob)` → the armature "FR rig <name>" (child of the person object, identity; 17 bones named as
  `props_detail.BONES`; Armature modifier "FR rig" before "FR prop detail"; vertex groups; hand shape keys driven by
  the armature's `fr_open_l/r`, `fr_grip_l/r`, `fr_point_l/r`). `rig_of(ob)`, `figure(ob)` → `core.Figure`, `remove(ob)`.
- `core.person_rig.Figure(height)`: figure space = the person object's local space (metres, z up, faces -y, right hand
  at -x, soles on z = 0). `rest()`, `from_angles(pose id or props_detail angle dict)`, `fk(pose)` → {bone: (head, R,
  tail)}, `frame(pose, bone)`, `palm(pose, side)`, `sole_points(pose, side)`, `leg_ik(pose, side, ankle, foot_R, knee)`,
  `arm_ik(pose, side, wrist, elbow=None, hand_R=None)` (returns the miss in m), `look(pose, direction, amount,
  chest_share)`, `blender_quaternion(pose, bone)`, `blender_location(pose)`. `Pose`: `local[bone]` (3×3 against the
  parent, props_detail frames), `pelvis` (its head), `fingers[s]` 0 open … 1 fist, `point[s]`. `blend(a, b, w)`.
- `person_rig.set_pose(ob, pose)` (now, no keys); `key_poses(ob, frames, poses, roots=None)` (keys tagged `fr_anim`:
  Clear keys drops them; `roots` = (x, y, z, heading) per frame keys the person object too); `bone_world(ob, bone)`.
- Items in a hand: a Child Of on `arm` + subtarget `"<s>_hand"`, inverse identity, its basis = the grip in Blender's
  bone frame (`people._basis_in_bone`, `core.people.hand_in_item`).

**Tested and measured** (4-core web machine, no graphics card; test crane `test_crane_a.step`):
- Tests: `tests/test_people.py` (29, mine), `tests/test_people_independent.py` (136) and
  `tests/test_people_blender_independent.py` (18) by an independent tester; tour (77 incl. the new stop: Go + check),
  `test_tour_clash.py` people set 0 clashes, PC-check line `people.walk` OK.
- The example: Anna walks, puts the box down, they shake hands together (same moment to 1 ms), feet slide ≤ 0.6 mm
  read back from the built keys, the box on the floor; Build 0.8 s, 1.3 ms a frame, render 2.6 s (PC-check line).
- Speed (`tools/measure_people.py`, Vessel deck, calm beam sea, 427 frames): 1 / 5 / 20 people: Build 0.4 / 1.9 /
  7.6 s, frame time 0.9 / 2.0 / 7.5 ms (0.2 / 0.3 / 0.6 ms with the people hidden): about 0.35 ms per person a frame.
- Mesh per rigged person: 4,476 points (both levels); building the rig ~0.3 s.
- Clip: `tasks/img/0157_people_meet.mp4` – the example on the test crane, 480×270, 17 s at 12.5 frames/s, Cycles on
  the processor (8 samples, 4.3 min for 216 frames), 51 KB.

**Subagents:** one independent tester (worktree; wrote the two `*_independent` files from the brief, did not see my
tests). It found 11 real faults, all fixed by me afterwards and now covered: a U-turn path crashed; the swinging foot
snapped down at landing (pelvis limit ignored the swinging foot); feet stayed level on a ramp (21 mm into a 1:10 ramp);
a circle of waits pumped the time to 222 s; waits for a missing step and greeting oneself gave no warning; handshake
hands 115 mm apart for different heights; items jumped 0.2–0.7 m into / out of the hand (the head turn moved the chest
after the arm was solved; the bend was too shallow); an item could be taken from someone holding it, or held by two
people at the start; the toolbox hung 4 cm into the leg. One test helper was adjusted for the tilted feet (it measured
heel/toe as if the foot were flat).

**GitHub runs:** 4. Run 1 red: the real-app test tour's Make failed (`object.mode_set` had no active object when the
rig made its bones in the tour build) – fixed with a context override. Run 2 green; then main had moved (0154 took 0.2.127):
merged, renumbered to 0.2.128, run 3 green; main moved once more (a task file only), so main ran in full (run 4,
43922154105): green, released, the old Windows install updated itself.

**Open points / follow-up tasks:**
- The person is still the 0155 lofted figure: linear-blend skinning shows creases at a deep squat and the shoulders
  when an arm is raised high; fine at the usual distance. A CC0 base mesh with real weights is the step after (0155's
  open point).
- No stairs, ladders, sitting, crowds (as briefed). A path over a part's top is walked on it and warned about.
- The path warning uses the parts' places at the first frame; moving parts are found by the Clash check (people are in
  it, items are not). With vessel motion the path line in the view does not ride with the deck (the people do).
- A put-down spot is where the person stands + a fixed offset; picking up an item lying more than 2.5 m away is warned
  (walk the person closer with a Walk step first).
- 0156 can use `arm_ik` + `key_poses`; its hand "FR hand" is separate.
