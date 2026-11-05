# 0026 – G-code drives the machine: CNC programs as animations

**Who:** worker · **Model:** Opus · effort High · **Status:** waiting (0014 – owner wants cylinders and linkages first) · **Branch:** `task/0026-gcode-motion`
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

- [ ] Reader tests: every supported code, arcs in all planes against hand-calculated points,
      incremental mode, work offsets, drilling cycles, unknown codes reported with line numbers
- [ ] A generic test machine (`tools/make_test_*.py`: gantry with X/Y/Z slides) runs a test
      program; tool tip positions at sampled frames match the program within 0.01 mm
- [ ] Bake time for a long program measured (lines, frames, seconds) on the test machine
- [ ] Owner's real program tried locally if he attached one (numbers only in the report)
- [ ] Real-app click test step, screenshots, full suite, GitHub run green; merged and released

## Not in this task

- Removing material and chips (0027, 0028 – Machining lane). Rotary axes A/B/C (0029).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
