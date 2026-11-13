# 0103 – Cycle time with acceleration: G-code moves timed as the real machine runs them

**Who:** worker · **Status:** open · **Branch:** `task/0103-cycle-time-acceleration`
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

- [ ] Scope 1–5 in the real app (panel screenshot checked), every setting with a tooltip.
- [ ] The tests above pass; milling / chips / tool marks tests of the Machining lane still green.
- [ ] Guide, tour stop, PC-check line; GitHub green; report filled in (the blending rule used and how far from
      LinuxCNC it is expected to be; a list for the owner: time one program on his machine, compare); merge to main and
      release.

## Not in this task

Jerk limits, spindle acceleration, LinuxCNC's exact planner, servo following error; colour by deviation (#11, later in
this lane); anything outside the G-code files.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
