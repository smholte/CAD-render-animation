# 0026 – G-code drives the machine: CNC programs as animations

**Who:** worker · **Model:** Opus · effort High · **Status:** done (0.2.29) · **Branch:** `task/0026-gcode-motion`
**Started by:** lead chat, 5 Nov 2026 · **Lane:** Motion · **Area:** new `blender/gcode.py` and
`core/gcode.py` (parser, no Blender), `blender/animation.py` (one new step type), `blender/joints.py`
(only if needed), `ui_motion.py` (panels 4/6), `blender/props.py` (additive), `docs/USER-GUIDE.md`
chapters 4 and 6, `tests/`.

## Goal

The owner's main product is a CNC milling machine (Fresing 400). He sets up three slide joints
for X, Y and Z (plus the spindle as a motor), loads a G-code program – the one his CAM (Fusion 360
Manufacture) writes for the real machine – and the animation moves the machine exactly as the
program would, at a speed he chooses.

## Background

- Joints: slide/rotate, stacked (0011, so X can ride on Y and Z on X, matching the machine),
  couplings and motors (0012: the spindle is a motor at the program's S rpm). Animation steps are
  baked to keyframes (`blender/animation.py: bake`). Read the reports of 0011 and 0012 first.
- Fusion 360's post-processors usually write the tool list as comments at the top of the program
  (tool number, diameter, corner radius, type) – read them when present (the material removal of
  task 0027 uses them).
- **The owner's machines run LinuxCNC** (5 Nov 2026). He is building a new version of his mill
  with an automatic tool changer (ATC); the older, smaller one has none. He has **no real
  program yet**: the tests use G-code the worker writes in LinuxCNC style. Later he can make one
  with Fusion's LinuxCNC post-processor for any test part, and attach it with the machine's STEP
  (chat only, **never committed**).
- LinuxCNC's dialect (RS274NGC) adds to plain G-code: `#` parameters and `[ ]` expressions,
  O-word subroutines, loops and if/else, `G43` tool length offset with a tool table
  (`tool.tbl`: tool number, diameter, length), `G41`/`G42` cutter compensation (CAM programs
  usually leave it off), `G64` path blending. Support what CAM posts and hand-written programs
  commonly use; report the rest with line numbers.

## What to build

1. **Reader** (`core/gcode.py`, pure Python, tested without Blender): G0/G1, G2/G3 (I/J/K and R,
   all three planes G17/G18/G19), G20/G21, G90/G91, G90.1/G91.1, G54–G59 work offsets, G28/G53,
   F (per minute; G93/G94/G95 if simple), S, M3/M4/M5, M6 + T, M30, drilling cycles G81/G82/G83
   (expanded into moves), comments and the Fusion tool comments, line numbers, blocks it does not
   understand reported with line number (never silently skipped). Output: a timed list of moves
   (start/end, arc centre, feed, rapid or not, spindle, tool).
2. **Machine set-up** (4 Motion, new fold "CNC machine"): which joint is X, Y, Z (and later A/B/C),
   direction (+/–), the machine's rapid speed per axis, and the **work zero**: click the point on
   the workpiece that is the program's zero (as in the CAM set-up). Saved with the project.
3. **Animation step "Run G-code program"** (6 Animation): file, from/to line, speed (real time,
   ×N faster, or "fit into N seconds"; rapids may be shown faster), spindle follows S/M3/M4/M5,
   tool changes: M6 shows the tool of that T number (from the model, or a simple tool shape
   made from the tool table) and can play a saved motion sequence for the **ATC** (tool-changer
   arm/carousel moving) – the owner's new machine has one. The step's
   length follows from the program; arcs are smooth (sampled per frame, not per G-code line).
4. **Toolpath preview:** the path as a line in the view (rapids dashed), optional in renders,
   with the part already milled shown in a colour (for presentations).
5. Long programs: a 30-minute program at 25 fps must bake in reasonable time; measure.
6. Tooltips; user guide chapters 4 and 6.

## Done when

- [x] Reader tests: every supported code, arcs in all planes against hand-calculated points,
      incremental mode, work offsets, drilling cycles, unknown codes reported with line numbers
- [x] A generic test machine (`tools/make_test_*.py`: gantry with X/Y/Z slides) runs a test
      program; tool tip positions at sampled frames match the program within 0.01 mm
- [x] Bake time for a long program measured (lines, frames, seconds) on the test machine
- [ ] Owner's real program tried locally if he attached one (numbers only in the report)
- [x] Real-app click test step, screenshots, full suite, GitHub run green; merged and released

## Not in this task

- Removing material and chips (0027, 0028 – Machining lane). Rotary axes A/B/C (0029).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (Opus), 6 Nov 2026. Version 0.2.29 (0.2.27 and 0.2.28 went to tasks 0025 and 0034 meanwhile).

**What changed:**
- `core/gcode.py` (no Blender): the LinuxCNC reader – G0/G1/G2/G3 (IJK and R, all three planes, helical, P
  turns), G4, G17–G19, G20/G21, G90/G91, G90.1/G91.1, G93/G94/G95, G54–G59.3 + G10 L2/L20, G92/G92.1/.2/.3,
  G28/G28.1/G30, G53, cycles G81 G82 G83 G73 G85 G86 G89 (G98/G99, L, any plane), F S T M3 M4 M5 M6 M61 M0/M1
  M2/M30, `#` numbered/named/global parameters, `[ ]` expressions and functions, O-word sub/call/return,
  if/elseif/else, while, do-while, repeat, break/continue, subroutine files next to the program; Fusion tool
  comments and `tool.tbl`. Everything else is reported with its line numbers (G41/G42, A/B/C/U/V/W, G33, G76,
  G5.x, G38.x, G96, M100–M199, unknown codes, broken lines). Output in machine coordinates (mm) with times
  (rapids per-axis limited, feeds capped by the axes' rapid speeds; no acceleration). `Schedule`: program time
  -> video time (real / ×N / fit, rapids faster, tool-change pauses, line range), key samples, toolpath.
- `blender/gcode.py`: CNC machine set-up (`scene.fresing.cnc`): X/Y/Z joints (each moves tool or workpiece,
  sign picked from the model's axes, Reverse), spindle motor, tool tip (milling's bit detection), work zero
  (box corners/centres in the machine's axes, clicked point snapping to a vertex, shift; marker "FR work
  zero" parented to the workpiece), machine zero (CAD or "here"), tools list. Bake of the new step: a key on
  X/Y/Z at every move's start and end (fractional frames) and along arcs (every frame + chord error 0.002 mm),
  spindle angle keys (slowed to 1/7 turn per frame by default), tool copies at M6 (part copy or a turned mesh
  from the sizes; carousel part hidden while loaded), tool-changer animation played at each M6 (its steps are
  added shifted; X/Y/Z moves in it are refused), soft-limit warnings with line numbers, program copy kept in a
  Text block (used when the file is gone), model update and joint rename hooks. Toolpath: edges + a Geometry
  Nodes modifier (tubes; orange to cut, green once cut by Scene Time, rapids dashed blue).
- `animation.py`: step kind GCODE (length from the program, tool-changer steps, frame_end stretched to the
  last key). `props.py` (additive): FRCnc, FRCncTool, step settings. `ops_gcode.py`, `ui_gcode.py` (4 Motion >
  CNC machine; the step in 6 Animation), `ops_motion.py` (new step default), `logic.py` (CNC objects are not
  CAD), `reimport.py` hooks.
- **Joint fix (all joints):** Blender 5.2.3 writes 0 for a driver result that is a small positive number
  (≤ 1e-4): a slide joint within 0.1 mm of its CAD position jumped to it. Motion drivers now work out value + 2
  and a generator modifier takes the 2 off (still no Python); followers' expressions too; older projects are
  upgraded on load (`joints.upgrade_drivers`). CLAUDE.md section 8.
- Test gantry `tools/make_test_gantry.py` → `tests/data/test_gantry.step` (+ copy in `fresing_render/data/`):
  Y gantry, X carriage, Z head with a flat Ø6, carousel with a ball Ø4 and a drill Ø5.
- PC check line `motion.gcode`; real-app test `tools/ui_test_gcode.py` (in `ci_real_app.py`, MIN 23 checks);
  tooltip report knows the CNC panel and the step; user guide: "CNC machine (G-code)" in chapter 4, "Run a CNC
  program" in chapter 6.

**Tested and measured** (4-core cloud machine, Linux, bpy 5.2.3 as a module):
- `tests/test_gcode_core.py` 51 tests: arcs in G17/G18/G19 against hand-worked points, R both signs, full
  circles, helix, turns, G90.1, inch, G91, G54 + G53, G10 L2/L20, G92, G28 (+ intermediate point), G93/G95,
  spindle/tools/M30, every cycle step by step (G81 G98/G99, G82, G83 pecks, G73, G85, G91 + L3, G18 plane),
  tool comments + table, unknown codes with line numbers, expressions, o-words, subroutine files, loop guard,
  timing modes, key samples within 0.002 mm of arcs. 60,000 lines read in 0.8 s.
- `tests/test_gcode.py` 21 tests on the test gantry and the test mill (table moving Y): the tip against the
  program on every frame and at sub-frames: worst < 0.01 mm (PC check line: < 0.0001 mm); speed modes; spindle
  angle; limits and unknown codes in the warnings; tool changes (copies, carousel part, Clear keys); tool-changer
  animation; toolpath; save + reopen with the file deleted; model update; joint rename; panels draw; tooltips;
  joint small-value fix and upgrade.
- Bake time (in the test): 20,005 lines, about 30 minutes on the machine, 45,349 frames at 25 fps: 2.2–3.1 s
  including reading the program and the toolpath.
- Owner's real program: none attached – not tried.
- Real-app test `ui_test_gcode.py` on GitHub (download.blender.org is blocked in this session): 23/23 – clicks
  on tool, block and carousel tool, clicked work zero snapping to the corner, tip on the path, T2 after M6,
  toolpath, playback, reopen with the program file gone, Clear. The two guide pictures were taken there and read
  back from the job log (printed as base64, since the chats cannot download the run's files). The first picture
  showed three labels cut off at the default side-panel width; fixed.
- Full suite locally 2,246 passed (before merging main); GitHub runs of the branch green (Linux suite, real
  app, Windows install + self-test).

**Open points / follow-up tasks:**
- Milling (0027) with tool changes: milling's bits are fixed parts; the tool copies shown at M6 do not cut.
  A follow-up in the Machining lane could switch the cutting bit at the swap moments (the shapes are known).
- Acceleration is not simulated (short moves are a little faster than on the machine); G64 blending not shown.
- Rotary axes A/B/C (task 0029).
- Followers' value copies (the coupling driver on `fr_value`, only for the panel) still have Blender's
  small-number problem; motion is fixed.
