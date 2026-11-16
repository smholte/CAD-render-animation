# 0156 – Manual tool change: a realistic hand, and a full human doing the change

**Who:** worker · **Status:** done 16 Nov (0.2.132) · **Branch:** `claude/affectionate-archimedes-rugvto` (the session's name)
**Started by:** lead chat, 16 Nov 2026 (owner: props, hand and human more detailed and realistic; a full human doing a
manual tool change) · **Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation".
Subagents allowed (CLAUDE.md section 2).
**Area:** Tool-change lane: `blender/toolchange.py` (the hand "FR hand", manual changes), `core/toolchange.py` (the timed phases), the operator's figure from 0155 posed with 0157's rig (read-only use of `core/person_rig.py`, `blender/person_rig.py`, `core/people.py`; a needed parameter there is additive), `ui_gcode.py` (its settings), their tests, the guide's tool-change section.
**Do not edit:** milling / material removal (`machining.py`, `core/heightmap.py`: 0167 may run), the ATC code paths unless shared helpers need a parameter, the surroundings (0155 done before), the Web 3D lane.

## Goal

A manual tool change looks like a real operator doing it: a detailed gloved hand (as today, but realistic), or – a new choice – a whole person who steps to the machine, opens the door, holds the tool holder, releases it with the drawbar button, puts the new tool in, closes the door and steps back.

## What to build

1. **Hand:** the app-made gloved hand (`HAND_NAME = "FR hand"`, `GRIP_BELOW_GAUGE`, `PULL`) made realistic: glove
   shape and material, fingers that close round the holder, the other hand at the drawbar button optional.
2. **Full human** (new choice next to *Hand* / *None*): the 0155 figure with an animation built from the change's
   timed phases (`core/toolchange.py`): walk in from a set spot, open the machine's door if it has one (a joint the
   owner picks, else skip), reach, grip, press the release, pull the tool down, put it in the rack / on a table, take
   the new one, insert, release, close, step back. **Use 0157's rig** (lead, 16 Nov – API in tasks/0157's report): arms by
   `person_rig.arm_ik` on the holder's place, keys by `person_rig.key_poses` (tagged `fr_anim`, baked at Build, works
   with scripts off), the walk in / out by 0157's walk paths (`core/people.py`); no Blender IK constraints, no second rig. The pause length (manual-change pause, 0–5 s) grows
   automatically to what the person needs, and the report says the time per change.
3. The person never walks through the machine or the table: a clear path to a stand spot in front of the spindle
   (the owner can move the spot); the clash check knows the person (0 clashes on the tour's tool-change set).
4. Works with the queue, saved scenes, the product video; the person can be hidden for a shot.

## Rules

- **Licences:** only models you make in code, or openly licensed bases that allow redistribution in a GPL app and a
  public repository – e.g. Blender Studio's *Human Base Meshes* bundle (CC0) or MakeHuman exports (CC0); check and
  name the licence in `site/CREDITS.md` / the extension's credits. No real person's likeness, no branded clothing or
  tools (no logos), no downloaded manufacturer models (CLAUDE.md section 6).
- Keep the shipped size small: measure what the extension zip grows by (aim ≤ +5 MB); light meshes (props are seen
  from afar; the hand / human close up only in tool changes).

## Done when

- [x] Tests (hand grip place on the holder, phases in order, IK reaches within a few mm, walking path clear, 0 clashes,
      the pause grows); a short clip of one change with the full human (test mill), cropped small.
- [x] Tooltips, guide (with new pictures of its section), PC-check line / tour stop, function list; GitHub run green;
      merged; version (CLAUDE.md section 7); report with small before/after pictures in `tasks/img/0156_*`, triangles
      and zip size before/after.

## Design (worker, 16 Nov – the brief of the independent tester)

The person is built with 0157's rig (`core/person_rig.py`: `Figure.arm_ik`, `look`; `blender/person_rig.py`:
`key_poses`) and walks with `core/people.py` (`plan`, `_sample_person`), not with Blender IK constraints.

- `core/toolchange.py`: `Changer.person` / `Changer.door` (seconds the door takes); `PERSON_MOVES`, `person_moves(door)`,
  `person_min(door)`, `person_keys(t0, length, door)` → [(start, end, move)], `person_events` → (old tool out = end of
  "release", new tool in = end of "clamp"). The pause grows to `person_min` (`Changer.operator_min`). `Change.person`,
  `Change.door`; `Change.hand` = (start, length) of the pause also for the person.
- `core/tc_person.py` (no Blender): `Floor` (occupancy grid + 10 cm height slices; `add_triangles`, `free(r)`,
  `clear_at(p, r, half_h)`, `way(a, b, r)` = A* pulled tight), `way_to`, `walkable`, `stand_spot` (in front of the holder,
  `WORK_ROOM`), `trolley_spot`, `place_tools` (tools lying across the trolley), `Door` (SLIDE/ROTATE, `move(v)`, `at`),
  `Station` (one change: pause, holder frame `spindle` 4x4 with z into the spindle, tool copies' world matrices, the
  button), `Trolley`, `grip_hand` / `press_hand` (hand frames), `Operator(height, start, stand, way, stations, trolley,
  floor_z, door, floor=)`: `plan()` (walk in so it stands at the machine `ARRIVE` s before the first pause, stays,
  walks out after the last), `sample(times)` → [(root, Pose, {T: carried tool world 4x4}, door value)], `misses`.
- `blender/tc_person.py`: the operator object (person prop of 0155 in collection "FR operator", tag `fr_tc_operator`),
  the trolley, the tool copies (carried: `fr_cnc_hold`, lying: `fr_cnc_trolley`), `start_step` / `change` (called from
  `toolchange.tool_keys_plain`: visibility keys + the door joint's keys), `bake` (end of Build: reads the holder per
  pause, the floor, plans, keys), `apply_visible` (`scene.fresing.operator_visible`, saved with a shot), the clash hook
  (the body without arms: `clash.CLASH_MESH`), `show_spots` (empties "FR operator stand" / "FR operator start").
- Settings: step `gcode_operator` (NONE / HAND / PERSON over the stored `gcode_hand` + `gcode_person`), CNC
  `op_height`, `op_outfit`, `op_helmet`, `op_door`, `op_door_open`, `op_door_angle`, `op_trolley_side`, `op_button`.
- Test model `tests/data/test_mill_cabinet.step` (`tools/make_test_mill_cabinet.py`): the test mill on a cabinet, an
  enclosure with a sliding door (joint "Door" in the tour set) and a release button on the head. Tour set `operator`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026 (branch `claude/affectionate-archimedes-rugvto`, the session's
name instead of `task/0156-…`). Version **0.2.132**.

**What changed:**
- **A whole person changes the tool** (step choice **Changed by: Nobody / Hand / Person**, `gcode_operator` over the
  stored `gcode_hand` + new `gcode_person`, so old projects keep their hand). Built with 0157's rig and walking, no
  Blender IK constraints: `core/tc_person.py` (no Blender: floor map with 10 cm height slices, A* way round everything,
  stand spot, trolley spot, the change's moves with `Figure.arm_ik` on the holder / button / trolley / door handle, a
  lean that keeps the head and chest out of the machine, the carried tools' world matrices) and `blender/tc_person.py`
  (operator in collection "FR operator", tool trolley, tool copies in the hand and on cradles on the trolley, door joint
  keys, keyed at the end of Build with `person_rig.key_poses`). The person walks in so it stands at the machine 0.4 s
  before the first pause, stays through all changes and walks out after the last; too early a first change → it stands
  there from the start (Build says so).
- **Timing** (`core/toolchange.py`): `PERSON_MOVES` (reach, grip, release, pull, away, set, wait, take, fetch, insert,
  clamp, leave; door: to_door, open, let_go … to_close, close, let_go2), the pause grows to `person_min(door)` (5.95 s
  without a door, 9.7 s with the test door); old tool out at the end of "release", new one in at the end of "clamp".
  The spindle is read twice per change: when the old tool comes out and when the new one goes in (it rises for a
  longer tool in between – found while testing).
- **Door**: a slide or rotate joint picked in the panel (`op_door`, `op_door_open` / `op_door_angle`); the handle is
  found on the door's front edge; the hand follows it while it reaches, a door that slides further runs on.
- **Release button**: the left index finger presses a face of the head beside the spindle (found by rays); none found →
  the left hand stays down.
- **Realistic glove** for the Hand choice (`core/glove.py`): jointed fingers with knuckles, thumb, gauntlet cuff,
  nitrile material with sheen and grain; shape key "Open" driven by a keyed `fr_open` (simple expression) – open while
  reaching, closed round the holder. 570 → 1,288 points (2,528 triangles).
- Settings in 4 Motion > CNC machine > Tool changes > **Person at the machine** (height, clothes, helmet, door, release
  button, **Show the spots** = two empties to move the stand / start spot, **Show the operator** = `operator_visible`,
  saved with a scene). The step's Details say the time per change.
- Clash check: the operator's body without arms (`clash.CLASH_MESH`, a small additive hook in `blender/clash.py`);
  the arms are checked posed in the tests.
- New test model `test_mill_cabinet.step` (`tools/make_test_mill_cabinet.py`): the test mill on a cabinet with an
  enclosure, a sliding door, a release button, the head 80 mm higher with T1 in a BT30-like holder. Tour set and stop
  `operator`, PC-check line `toolchange.person`, function `cnc.toolchange_person`, guide section "A person changes the
  tool" (`toolchange_person.jpg`, `toolchange_person_trolley.jpg`, re-shot `panel_4_toolchange_manual.png`,
  `panel_6_gcode_toolchange.png`, `view_toolchange_hand.png`; mode `operator` in `tools/guide_screens.py`).

**Tested and measured** (4-core web machine, no graphics card; test mill in its cabinet):
- `tests/test_tc_person.py` (16, mine), `tests/test_tc_person_blender.py` (5, mine: posed person vs every machine part
  every 3rd frame of the change – only the held tool and the door handle may be touched –, tools where the hand takes
  them, clash check 0, hide for a shot, Clear keys, Hand instead), `tests/test_tc_person_independent.py` (69) and
  `tests/test_tc_person_blender_independent.py` (17) by the independent tester. `test_tour.py` (with the new stop),
  `test_user_guide.py`, `test_functions.py`: 115 passed;
  `test_tour_clash.py` operator + tools sets: 0 clashes. PC-check line OK.
- Build 2.1 s, frame time with the operator 1.0 ms, draft render 2.1 s (PC-check line). Hands/head move at most 7 cm per
  frame at 25 fps outside the walk (no jumps).
- Extension zip (sources + data, deflated): 6.91 → 7.21 MB (+0.30 MB, mostly the 1.8 MB test model).
- Clip `tasks/img/0156_operator.mp4` (480×270, 12.5 frames/s, Cycles on the processor, 8 samples); pictures
  `tasks/img/0156_hand_before_after.jpg` (old ring fingers / new glove), `tasks/img/0156_operator.jpg`.

**Subagents:** one independent tester (worktree, wrote the two `*_independent` files from the brief). It found 9 real
faults, all fixed by me and now covered: the fist closed 45 mm below the tool on the tour model (no holder on the
CAD tool, grip from a fixed depth – now the model has T1 in a holder and the grip is read from the tool's own holder,
`grip_depth`); a sign error put a Ø50 holder through the palm; the hand went 22 mm into the trolley top (tools now lie
on cradles); a trolley on the left was out of the right hand's reach (the trolley now stands on the right only, the
choice removed); a 1.85 m operator and a far-sliding door gave misses and a 0.15 m jump (lean now follows the door
hand, misses warned only where the hand must be exact); a start spot beyond the floor map found no way; too many tools
lay in each other (now left over with a warning). Its tests were adjusted where my design changed (the grip, the
cradles, the right-only trolley) – marked "(worker: …)" in the files. My own fixes afterwards: the thumb along the
holder went up into the spindle (palm-forward grip now), the left elbow folded through the opening's edge.

**GitHub runs:** 2 full runs. Run 1 (a work-in-progress push, before the review's fixes) was not used. Run 2
(43956757465, the finished code with version 0.2.132) green, 25.6 min; then a docs run for the report and guide
numbers, and main fast-forwarded to that commit (reuse).

**Open points / follow-up tasks:**
- The person changes tools only on manual machines and for ATC tools without a pocket; on a double-arm changer a tool
  without a pot still gets the hand (`core/toolchange.plan_arm`).
- The trolley always stands on the operator's right; with no room there the tools are not laid down (warned).
- The stand spot is found on the machine's −Y side (as the hand of 0041); other machines: move the arrow.
- The clash check moves the operator's body without its arms; the arms are only checked by the tests.
- The tour's "Three tools" set changes tools at Z10: the gloved hand dips into the stock there (as before 0156) – a
  higher change position in that program would fix it (tour/test-model lane).
- The person is 0155's lofted figure (0157's open point: creases at deep bends).
