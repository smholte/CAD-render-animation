# 0103 – Cycle time with acceleration: G-code moves timed as the real machine runs them

**Who:** worker · **Status:** done (0.2.83) · **Branch:** `task/0103-cycle-time-acceleration`
**Started by:** lead chat, 13 Nov 2026 (study 0069 #16; owner: "all three" of the free-lane tasks)
**Lane:** Machining (G-code files): `core/gcode.py` (the timing in `Schedule`), `blender/gcode.py` (the keys of the Run
G-code program step), `ui_gcode.py` (4 Motion > CNC machine). Additive: `props.py` (new settings next to `rapid_x …`),
the tour, the PC check, the guide. Runs side by side with 0080, 0101, 0102, 0104, 0105 – none of them edits these files
(0101 may only *use* an existing G-code step).
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

A Run G-code program step plays at the real machine's speed, also for programs with many short moves: every axis speeds
up and slows down with its own maximum acceleration, so the video's length and the step's time match what the owner's
LinuxCNC machine does.

## Background

- Today (`core/gcode.py` docstring, line ~46): a rapid takes as long as its slowest axis needs at that axis' rapid speed,
  a feed move runs at its feed, **acceleration is left out** – short moves come out too fast (the guide, chapter 6, says
  "Moves are timed without acceleration"). The machine's rapid speeds are typed in 4 Motion > CNC machine
  (`rapid_x/y/z` = LinuxCNC `MAX_VELOCITY`, rotary `rot_rapid` in °/min, task 0066). Keys are written at move ends and
  along arcs (`blender/gcode.py`); "Rapids faster" and the step's speed setting scale the time afterwards.
- LinuxCNC's trajectory planner: each joint/axis has `MAX_VELOCITY` and `MAX_ACCELERATION` in the machine's INI
  (`[AXIS_X]` …); `[TRAJ]` has the overall limits; **G61** = exact stop at every corner, **G64** (the default) = path
  blending, **G64 P q** = blend within tolerance P (naive-CAM tolerance Q). A blended corner slows to a speed set by the
  corner's angle and the acceleration; a straight run of short collinear moves does not stop between them. Look it up
  (web search; most pages may not open in a web session – say what was used).
- Owner: the Fresing 400 runs LinuxCNC; **its INI and programs are not committed** (CLAUDE.md section 6) – tests use
  invented values and programs. The owner can time a real program on his machine and compare (owner's check).

## Scope

1. **Settings** (4 Motion > CNC machine, under the rapid speeds, each with a tooltip): max acceleration per axis
   (mm/s², X/Y/Z; °/s² for A/B/C), a switch "Speed up and slow down (acceleration)" (on for new machines; old projects
   keep their timing until it is switched on, or say why not), and **Read from LinuxCNC INI…** (a file picker that
   fills max velocity and max acceleration of every axis it finds; the file itself is not stored or copied).
2. **Timing** (`core/gcode.py`, no Blender): each move gets a trapezoid (or triangle) speed profile limited by every
   axis' acceleration along the move's direction (arcs: the tangential limit plus the centripetal one, v² / r ≤ a);
   **G61** exact stop at every move end; **G64** (default) blending: a corner's speed from its angle and the
   acceleration (LinuxCNC-like, not exact – say the rule), collinear short moves pass without stopping; **G64 P**
   tolerance read. Dwells, tool changes, M-code pauses unchanged. Rotary moves the same with their own limits.
3. **Keys follow the speed:** a move's position along its path follows the profile – not linear in time – so the head
   visibly speeds up and slows down (extra keys inside a move where needed, Bezier handles flat; 0029's rule: keys
   < 0.01 frame apart merged by `FCurve.update()` – `animation._write` sorts and recalculates handles). Milling, chips,
   coolant, air, tool marks read the moves by time and must still line up (same frames for the same program point).
4. **The step shows its time** with and without acceleration ("2 min 14 s – 1 min 51 s without acceleration"); the
   panel's "Rapids faster" and the step's speed keep working on top.
5. Tour stop "Acceleration" (the tour's CNC set: a short program with many short moves, the time with and without),
   PC-check line `gcode.acceleration`, guide (chapter 6: the sentence "Moves are timed without acceleration" replaced
   by how it works and how to read the INI).

## Accuracy and speed (tests)

- A single long move: time = distance / v + v / a within 1 ms; a short move that never reaches v: 2·√(d / a).
- G61 vs G64 on a zigzag of 1 mm moves: G64 shorter, both longer than without acceleration; a straight line cut into
  1,000 collinear pieces takes as long as one move (G64) within 1 %.
- An arc at a feed above √(a·r) is slowed to it.
- The head's place at every frame within 0.01 mm of the profile's place (keys inside moves).
- Timing a 40,000-line program (the tour's or 0029's): say before/after; the step's Build time must not grow by more
  than 30 %.
- Old projects open with the same timing (switch off) and Build the same keys.

## Done when

- [x] Scope 1–5 in the real app (panel screenshot checked), every setting with a tooltip.
- [x] The tests above pass; milling / chips / tool marks tests of the Machining lane still green.
- [x] Guide, tour stop, PC-check line; GitHub green; report filled in (the blending rule used and how far from
      LinuxCNC it is expected to be; a list for the owner: time one program on his machine, compare); merge to main and
      release.

## Not in this task

Jerk limits, spindle acceleration, LinuxCNC's exact planner, servo following error; colour by deviation (#11, later in
this lane); anything outside the G-code files.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 13 Nov 2026 · released as 0.2.83.

**What changed:**
- `core/gcode.py`: `plan_accel(prog, accel, rot_accel)` (called by `read(..., accel=)`): per move a trapezoid/triangle
  profile `Move.prof`, `Move.dur` the new time, `Move.dur0` the old one, `Program.duration_without_accel`. Moves are
  worked in six axes (A/B/C degrees counted as mm): top speed = the old constant speed (feed, or slowest axis at rapid);
  acceleration along the move = the smallest `a_axis · S / |Δ_axis|`; arcs capped at v = √(a_plane · r) (v²/r ≤ a, as
  the brief; LinuxCNC itself gives the normal part only √3/2 of a – real arcs a little slower). Corners: `Move.blend`
  (G61/G61.1 → stop; G64 → blend; G64 P → tolerance, inch converted). **Blending rule:** a circle touching both moves,
  radius ≤ half the shorter move and (G64 P) ≤ P / (1/cos(θ/2) − 1); corner speed √(a·R), capped by both moves' top
  speeds; straight on = full speed, turning back = stop. Stops at dwell, tool change, pause. Look-ahead: backward +
  forward pass. `Move.u_of / tau_of / velocity`; `Schedule.point_at / rot_at / path / samples` follow the profile;
  `Schedule.speed_changes`, `velocity_at`. `read_ini()`: `[AXIS_X]…`, `[JOINT_n]` + COORDINATES, old `[AXIS_n]`, inch.
- `blender/gcode.py`: keys where speeding up ends / slowing down starts; the stretches where the speed changes get
  **Bezier keys with free handles from the exact velocity** (a Bezier segment = the parabola exactly), constant speed
  stays straight keys as before. Rotary/TCP machines take the velocity by a 3-point one-sided difference over a quarter
  of the key gap (mathutils is 32-bit: a 10 µs step gave 0.3 mm). Settings `use_accel`, `accel_x…accel_c`;
  `upgrade_accel` at load: a project without the marker `fr_accel_v` that has a CNC machine gets the switch **off**
  (old timing, same keys); the marker is set on any set-up change/read. `read_ini` operator `fresing.cnc_read_ini`.
- `blender/animation.py`: `_merge` takes handles; `_write` sets interpolation, handle types and handles with
  `foreach_set` (was a Python loop per key) – every Build writes keys faster.
- Panel 4 Motion > CNC machine > Machine (switch, X/Y/Z accel., Read from LinuxCNC INI…), Rotary axes (A/B/C accel.),
  the step's line "… on the machine (… without acceleration)". Tour stop `accel` (gantry set, 2 mm zigzag G64 then G61,
  one long line, in the air), PC-check line `gcode.acceleration` (invented .ini, tip on the profile at frames and half
  frames, switch off = plain time). Guide chapter 4 (settings) and 6 (how moves are timed), two panel pictures.

**Tested and measured** (4-core cloud test machine, test gantry unless named):
- New `tests/test_gcode_accel.py` (15, core): long move = d/v + v/a (exact), short move = 2√(d/a), diagonal rapid,
  G61 > G64 > none on a 1 mm zigzag (G61 = 200 · 2√(1/a) exactly), G64 P tighter = slower, 1,000 collinear pieces =
  one move (< 1 %), dwell / tool change / reversal stop, arc capped at √(a·r), rotary own acceleration, place = profile
  formula (1e-6 mm), u/τ inverse, scaled video keeps the shape, path times, INI variants, 40,000-line planner speed.
- New in `tests/test_gcode.py` (3): keys follow the profile at every frame and at sub-frames 0.37 / 0.5 (< 0.01 mm);
  an old project (marker removed, saved, opened) has the switch off, the same length and **the same keys**; ticking it
  survives save/open; Read from LinuxCNC INI fills values, the step follows, an empty .ini is refused.
- Changed tests: `test_speed_settings` (with acceleration longer, without exactly the feeds), `test_rotary` 4-axis slot
  12.0 s → within 0.01 s (its speed-up). 5-axis TCP tip vs program at 0.37-frame steps: worst 0.0002 mm.
- Machining lane local: test_gcode, rotary, machining, machining_fixes, toolchange, doublearm, toolmarks ×3, toolpath,
  chips, coolant: 228 passed. Animation set (phase2, fade, couplings, same step twice, stacked joints, camera ride,
  cylinders, tour, video): all pass after the tour fixes. Real app `--only gcode`: 29/29. PC check line: OK
  ("6.1 s – 4.3 s without acceleration; tip on the profile to 0.0001 mm"). Tooltip check: 674 ok.
- **Build time**, 20,000-line program (10,000 lines + 10,000 arcs, ~30 min on the machine, `test_bake_time_of_a_long_
  program`): before 2.6 s; after, switch off 1.7–1.8 s (faster key writing), switch on 3.0 s (+15 % on before).
  Reading + timing a 40,000-line program: 0.48 s → 0.71 s.
- GitHub: 3 full runs of the branch, all green (14.6–15.7 min); two were needed only because tasks 0104 and 0105 merged first (version 0.2.81 → 0.2.82 → 0.2.83).

**Expected distance from LinuxCNC:** no jerk limit (LinuxCNC 2.9 is trapezoidal too), corners not rounded in the
picture (time only), blend radius rule simpler than LinuxCNC's tangent/parabolic blends, arcs allowed √(a·r) where
LinuxCNC uses about 0.87·a for the normal part, rapids blended like feeds. Expected within a few percent on CAM programs
with long moves, more (either way) on programs of very short segments. **For the owner:** 1. Read your machine's .ini
with Read from LinuxCNC INI… 2. Time one real program on the Fresing 400 (LinuxCNC shows the run time) 3. Compare with
the step's "… on the machine" line and send both numbers.

**Subagents:** none (independent tester skipped to save usage: no Windows-only code; the brief's numbers are covered by
tests written from the brief).

**Open points / follow-up tasks:** the joint's own G-code speed is the only thing timed (spindle acceleration, servo
error not, as the brief says). The `Rapids faster` and Faster/Fit settings scale the profile in time (shape kept).
