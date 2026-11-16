# 0156 – Manual tool change: a realistic hand, and a full human doing the change

**Who:** worker · **Status:** running (16 Nov) · **Branch:** `claude/affectionate-archimedes-rugvto` (the session's name)
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

- [ ] Tests (hand grip place on the holder, phases in order, IK reaches within a few mm, walking path clear, 0 clashes,
      the pause grows); a short clip of one change with the full human (test mill), cropped small.
- [ ] Tooltips, guide (with new pictures of its section), PC-check line / tour stop, function list; GitHub run green;
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
