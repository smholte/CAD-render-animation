# 0125 – Quadrant and sea follow-ups: the D on the seabed, no lost path, no kink, the bow the right way

**Who:** worker · **Status:** running · **Branch:** `ccr-f499cc61-gp70i0` (the web session's branch)
**Started by:** lead chat, 15 Nov 2026 (owner: "all 5 suggested tasks") · **Model:** Opus · effort High
**Area (Flex parts lane + Demo models lane + the bow in the Scene & Render lane):** `fresing_render/core/paths.py`,
`core/catenary.py`, `blender/paths*.py` (incl. `paths_sea.py`, `paths_riders.py`), `blender/flex.py` only if needed,
`blender/spool.py` only if the keep-tight payout needs it, `blender/demo.py` (stages `sea` and the quadrant stages of
0082), `fresing_render/demo_model/` if a demo part must move, `core/weather.py` (`BOW_AZ`) and the places that read it,
their tests. **Do not edit:** `blender/sequence.py`, `core/sequence.py`, `ui_motion.py` beyond the cable boxes (task
0129); `tools/site_projects/`, `site/` (task 0128); the CPS run (task 0126 comes after this one in the Demo lane).

## Goal

Demo shots 9–12 (the second end over the stern, lowered, tipped, let go, back) look right: the D stands on the seabed
instead of in it, the cable never loses its path, no kink where it leaves the gutter, the wires and swivels follow
what pulls them, and "wind from the bow" / the wake agree with the way the vessel actually points.

## Background

All from the report of task 0082 (`tasks/0082-quadrant-operations.md`, open points 1–7) and 0081 (open points):
1. **The D sinks 0.76 m into the seabed in shot 11** (done so that the cable round its gutter lies on the seabed at
   the let-go); the pull head lies 0.4 m below the seabed line (vessel heave is in the stored let-go places).
   Wanted: let go **at** the seabed and let the cable settle onto it – an app ability: **a let-go cable (or the stretch
   of it that is no longer held) sinks onto the seabed** over a short time and lies there (seabed from 0081).
2. **Frames 1924–1927 of the second end have no path** ("'QUADRANT GUTTER' and 'Bend 1' overlap"; the last good
   shape is kept). Horn A is read as a bend, not a chute.
3. A **~6 cm kink** where the catenary leaves the gutter at the start of the lowering (out of the gutter's plane).
4. The **tipping-wire swivels** follow the handler tilt by ratio (0095), not the wire; a keep-tight sea cable gets a
   **step in its payout** when its hang-off changes.
5. Build warnings that should not show: "Second end piles up 0.00 m"; "A&R wire no longer touches the pulley at
   frame 1" (by design, hidden then – say nothing, or say it only when the wire is visible).
6. 0081: **rollers after a horn's hang-off keep turning** with the cable though it left the horn before them.
7. **The bow:** `core/weather.BOW_AZ = 180` (bow at −x, as the Vessel deck surroundings) drives "wind from the bow";
   the demo vessel (and 0081/0082) have the bow at +x. 0082 made the wake follow the bow; the wind did not follow.
   Make one source of truth for which way the bow points (the vessel's heading / the model) and read it everywhere
   (wind from the bow, wake, anything else that assumes −x). Old projects keep how they look (test with a 0.2.88
   and a 0.2.95 project if the bow source changes saved data).

Rules that bite here: CLAUDE.md section 8 – Blender merges keys closer than 0.01 frame (also on driver F-curves),
float32 joint values, `screw_between` false rows when something turns slowly (0091: the demo clash test runs with the
sea at rest), the demo's clash check is split in windows (`tests/test_demo_clash.py`).

## Done when

- [ ] Shot 11: the D rests **on** the seabed (no part of it more than 5 cm below the seabed line at any frame,
      measured on the D's mesh, with vessel heave on); the pull head on the seabed, not under it; the cable round the
      gutter settles onto the seabed after the let-go (new ability, tested on a small test model too – not only the
      demo).
- [ ] Every frame of the second end has a path (no "overlap" fallback; a test walks frames 1900–1950 of the demo
      animation, or the same moment on a small model); horn A is a chute where it is one.
- [ ] Where the catenary leaves the gutter the cable is smooth: direction change < 1° between neighbouring points, no
      step out of the gutter's plane (measured, before/after in the report).
- [ ] The tipping-wire swivels point along their wires (angle between swivel and wire < 1° over shots 9–12); a
      keep-tight cable's payout has no step at a hang-off change.
- [ ] No "piles up 0.00 m" warning; the A&R pulley note only when the wire is shown.
- [ ] Rollers the cable has left (after a hang-off) stand still.
- [ ] One bow direction used by wind, wake and the rest; the demo's "wind from the bow" blows from +x, the Vessel
      deck surroundings unchanged; old projects open looking the same (test).
- [ ] Demo: 0 clash rows (`test_demo_clash.py`), Make demo time and per-frame cost before/after in the report (no more
      than +1 ms per frame).
- [ ] The new settle ability: tooltip, guide paragraph + anchor, function-list entry (`core/functions.py`), tour stop
      or an extended existing one, PC-check line (CLAUDE.md section 6).
- [ ] Tests added; full GitHub run green; report filled in, with a short owner's check list (shots 10–12 on the RTX
      3090).

## Not in this task

The CPS run from the rack (task 0126, after this one). 0081's touch-down drifting with the deck path length (owner
may prefer re-anchoring – leave as is). Glowing markers, sun rays, sediment specks. The site, the turbine, the
assembly sequence.

## Design (worker, 15 Nov 2026)

Baseline on the small demo (4-core web machine, Blender as a module, before any change): Make demo 166 s (Build 54 s);
second end without a path at frames 1924–1927; in shot 10 the second end is PILED and its leave point on the gutter
flips between "steep" and "short" every few frames (an angle that wraps at ±180°: kinks of 23–69° at frames 2120–2160),
then a steady 3° kink out of the gutter's plane; the D's lowest point 0.97 m under the seabed at the let-go (heave
on), the cable round the gutter 0.38 m under it; tipping wire vs its sheave's plane up to 13.6°.

**Who does what** (one owner per file):

| Piece | Files | Owner |
| --- | --- | --- |
| Bow: one source (`core/weather.bow_az`, `State.bow_az`, `surroundings.bow_az(scene)` + scene key `fr_bow_az`, swell heading turns with it) | `core/weather.py`, `core/vessel_motion.py`, `blender/weather.py`, `surroundings.py`, `vessel_motion.py`, `web3d_env.py` | worker |
| Leaving the hang-off smoothly: the wrap wanted is read nearest the wheel's range (no flip), a **free bend** of the wheel's radius from the wheel's tangent to the catenary's direction (in and out of the wheel's plane) | `core/catenary.py`, `blender/paths_sea.py` | worker |
| A wheel that overlaps the wheel before it is released (the cable hangs from the earlier one) | `blender/paths_sea.py` | worker |
| **Settle** (`FRCable.sea_settle`, s): places let go of a sea cable sink onto the seabed over that time (ends: down to the bed; a wheel: down until its circle lies on the bed, turned flat) | `blender/paths.py` (`_apply_let_go`), props, UI, guide, functions, tour, PC check | worker |
| Warnings: no "piles up 0.00 m"; a cable's notes only for frames where its part is shown | `blender/paths.py`, `paths_sea.py` | worker |
| Keep tight on a sea cable: the payout's step at a hang-off change becomes a short ramp | `blender/paths.py` | worker |
| **Swivel follows its wire** (`FRCableContact.swivel` = rotate joint name): `before_read(scene, first, frames) -> list[str]` keys the swivel joints at Build (one key per frame, tagged, the joint's own coupling put aside and restored by `after_clear(scene)`); `live(scene) -> bool` sets them for the pose shown | new `blender/paths_swivel.py`, `tests/test_paths_swivel.py`, a field in `ui_paths.py` contact details | subagent S |
| **Rollers the cable has left stand still**: `after_bake(scene, first, frames, drawn) -> list[str]` (``drawn``: cable name -> (rel, first, solve result) of this Build); a roller whose joint follows the cable's speed and which no drawn cable touches at a frame does not turn at that frame (keys per frame, coupling put aside, restored by `after_clear(scene)`) | new `blender/paths_rollers.py`, `tests/test_paths_rollers.py` | subagent R |
| Demo: let go with the D on the seabed (heave measured), the settle, swivels on, tests | `blender/demo.py`, `tests/test_demo_*.py` | worker |

Hooks (by the worker): `animation.bake` calls `paths_swivel.before_read` right after the keys are written, before
trails, hoses and cables read the motion (moved there from `paths._bake` on the swivel subagent's advice);
`paths._bake` calls `paths_rollers.after_bake` after every cable is drawn; `after_clear` calls both modules' `after_clear`; `_live` calls
`paths_swivel.live` first.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 15 Nov 2026 (branch `ccr-f499cc61-gp70i0`), version **0.2.102**.

**What changed:**
- **Settle (new ability):** `FRCable.sea_settle` ("Into the sea > Settles in", 4 s; 0 = as before). What a sea cable lets
  go sinks onto the seabed over that time (`paths.settle`, smoothstep): everything let go at one frame moves as one – a
  let-go wheel is turned flat about its centre and lowered until its circle (the cable's middle) lies on the seabed, the
  ends let go with it go along; ends alone sink straight down. An end with a CPS rider rests with the CPS on the seabed
  (`_rider_lift`). Once the hang-off wheel is let go, "piles up", "lifts its end", "bends over the end" and "too flat"
  are not reported (it lies on the seabed). Tooltip, guide section `#settle`, function `offshore.settle`, tour stop and
  PC-check line "A cable on a moving part" extended (the test model settles in 2 s, `MOVING_SETTLE`).
- **Leaving the hang-off smoothly** (`core/catenary.hang_off`): the wrap wanted is read nearest the wheel's range (it
  flipped between "steep" and "short" at ±180°); a **free bend** of the wheel's radius from the wheel's tangent to the
  catenary's direction (in and out of the wheel's plane), the catenary starting where it ends; `paths_sea.solve` draws
  it (a point per 0.5°). No free bend where it would curl into the seabed. A steep leave is only reported when the
  wheel's radius is tighter than the MBR.
- **No lost path:** a wheel that the wheel before overlaps (no straight fits round both: the D's gutter over horn A) is
  released; a wheel lying flat hangs the cable along the lay direction (`paths_sea._away`).
- **Warnings:** a cable's notes only for frames where its part is shown (`paths._shown`); no "piles up" below 5 mm; no
  "no longer touches" for a wheel not touched in the CAD pose (the A&R wire comes onto its pulley later).
- **Keep tight on a sea cable:** the payout's step at a hang-off change is spread over 1 s (`paths.ramp_steps`).
- **Swivel follows its wire** (subagent S, `blender/paths_swivel.py`): `FRCableContact.swivel` (field in the contact
  details); closed form, keyed per frame at Build from the cables' own pass through the frames (the places of what it
  carries corrected, no second pass), live while posing; coupling put aside and back at Clear keys. Guide `#swivel`,
  function `offshore.swivel`.
- **Rollers the cable has left stand still** (subagent R, `blender/paths_rollers.py`): at Build a roller whose joint
  follows the cable's speed turns only at frames where a drawn cable touches it (keys per frame, coupling put aside and
  back at Clear keys).
- **Bow, one source:** `surroundings.bow_az(scene)` (Weather & time > Bow; From the hull: read from the waterline at the
  sea's build, kept on the surroundings' root as `fr_bow_az`; nothing read = -x as before) → `State.bow_az` (wind "from
  the bow"), the wake / bow spray (as 0082), the swell heading of vessel motion (`core.vessel_motion.swell(bow_az=)`,
  key unchanged for -x). The demo's wind from the bow blows from +x; the Vessel deck (as wide at both ends) keeps -x.
- **Demo:** shot 11 sets the D down so its lowest point (mesh, every frame, heave on) comes to 20 mm over the seabed at
  the deepest heave – worked out before Build and checked on the built animation, corrected once if off by > 10 mm
  (the estimate before Build was 0.38 m off: open point 4); the second end is let go 2 s later as the hoist begins and
  settles; the tipping-wire heads turn to their wires (Swivel) instead of following the tilt by ratio. The D's depth is
  now measured on what 'Quadrant lower' carries (it used the bogies' rail wheels before).

**Subagents:** S (swivel module + 9 tests; reworked once on my request to read in the cables' one pass: 48 s → 0 s
extra), R (rollers module + 5 tests). Both reviewed and merged by the worker; the hooks in `paths.py` are the worker's.
No independent tester this time (usage).

**Tested and measured** (4-core web machine, Blender as a module, small demo form):
- Before → after on the demo: second end without a path at frames 1924–1927 → none; kink where it leaves the gutter
  23–69° (frames 2120–2160) and a steady 3° out of the gutter's plane → no point within 2 m of the leave point turns more
  than the gutter's own arc (1.4° a point; the free bend 0.5° a point); the D's lowest point 0.97 m **in** the seabed →
  16 mm over it at the deepest heave (never lower); the cable round the gutter 0.38 m under the seabed → on it (its start
  within 2 cm of the seabed line once settled); pull head under the seabed → 3 cm over it; tipping wire vs its sheave's
  plane up to 13.6° → 0.0°. Build warnings: "0.00 m" and the A&R pulley note gone.
- Make demo 166 s → 213 s; its Build 54 s → 116 s (two Builds: the set-down check; one Build 58–62 s, +2.4 ms per frame of
  Build). Frame change when playing: not changed by this task (nothing new runs per frame; the shapes are baked).
- Tests: new `test_paths_settle.py` (6), `test_paths_swivel.py` (9), `test_paths_rollers.py` (5), bow tests in
  `test_sea.py` (3); 0082's let-go tests set Settles in 0 (they test "stays"); demo tests extended (no lost path, no kink,
  D on the seabed, pull head, swivels, warnings). Cable / sea / moving suites 124 passed; weather/sea 117 passed.

**Owner's check list (RTX 3090):** Help > Make demo project, then play shots 10–12: (1) shot 10: where the cable leaves
the D's gutter into the water it bends smoothly, no corner; (2) shot 11 (camera "At the seabed"): the D comes down and
just touches the seabed, it does not sink into it; (3) the cable end, its loop round the gutter and the CPS stay behind
as the D lifts off and sink onto the seabed within about 4 s, then lie still; (4) the tipping-wire heads on the stern
turn to follow their wires the whole time; (5) Weather & time on, Wind measured "From the bow" 0°: the rain/flag blow
from the bow (+x, the front of the vessel).

**Open points / follow-up tasks:**
1. The second end really piles up in shots 9–10 (0.36 m at frame 1810, growing to ~23 m as the D carries the bight aft
   with nothing hauled in): the warning stays, with its real size. A cable engine / tensioner hauling in during shot 9
   would end it (Demo lane, with 0126).
2. "A&R winch: fleet angle 13.6° at the flange the first layer starts from" (spool) was there before (not this task).
3. Swivel: no tour stop / PC-check line of its own yet (no test model has a swivel head: Test models lane); it is
   tested in `test_paths_swivel.py` and the demo test.
4. The D's depth worked out before Build differs from the built animation by 0.38 m (cause not found; the check after
   Build corrects it at the cost of a second Build, +55 s on Make demo).
5. Rollers: a lifted SHEAVE that the cable runs past still turns with its coupling (subagent R's note).
