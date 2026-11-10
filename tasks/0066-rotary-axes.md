# 0066 – 4th and 5th axis: rotary axes A/B/C in G-code, joints and milling

**Who:** worker · **Status:** running (10 Nov, branch `ccr-d3dbbfca-yscg1s`); **must be merged before Thursday 12 Nov 08:00** (0061 starts
in the same lane that morning) · **Branch:** worker's own
**Started by:** lead chat, 10 Nov 2026 (owner's priority 6 of the big features; split off 0029, which keeps only the
app-made toolpath, priority 8). 4 motion paths waits for 0058, 5 double arm is done (0064), 7 clash warning runs (0065).
**Lane:** Machining – `core/gcode.py`, `blender/gcode.py`, `blender/ui_gcode.py`, `blender/ops_gcode.py`,
`core/machining.py`, `blender/machining.py`, `ops_machining.py`, `ui_machining.py`, `chips.py` (only what a turning
part needs), `blender/props.py` (additive), `toolchange.py`/`doublearm.py` only if a change must keep the rotary
axes still; tests, PC check, test tour, guide "CNC machine" + "Milling"
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0065** (Clash lane: `clash*.py`, `ui_clash.py`, a note in `ops_motion.py`). Do not touch
those, nor `handlers.py`, `animation.py`, `reimport.py` (0058 starts there Thursday). Two releasing tasks at once:
take the version number last; whoever finishes second merges `main` once and renumbers (CLAUDE.md section 2).
**If it cannot be green and merged by Wednesday 11 Nov 22:00:** push the branch, fill in the report and stop; the lead
then lets 0061 go first on Thursday and this task merges `main` after it.

**Defaults the lead chose (owner can change them before or after):** LinuxCNC rules; **Plain** kinematics by default
(the CAM post did the maths, A/B/C are just joint angles, like LinuxCNC `trivkins`), **Tool follows the part (TCP)**
as an option for table-table machines; degrees, not wrapped, unless "Wrapped" is ticked per axis; two generic test
models (no owner CAD yet – his new mill is 3-axis first, 4th and 5th axis later).

## Goal

The owner's mill gets a 4th axis (rotary table) and later a 5th (trunnion). He wants to show in a video that a part
turns under the tool and is cut on all sides: the G-code from Fusion (LinuxCNC post) drives X/Y/Z **and A/B/C**, the
rotary table turns, the material comes off in the right places on the turning part, chips and coolant still work.

## What to build

1. **Machine set-up** (4 Motion > CNC machine): **A, B, C** next to X/Y/Z – pick a rotate joint each (any can be
   empty), Reverse, rapid in °/min, "Wrapped" (shortest way, 0–360°, LinuxCNC `WRAPPED_ROTARY`). The machine zero
   / home stores the rotary values too. Kinematics drop-down: **Plain** (default) / **Tool follows the part (TCP)**.
   For TCP the app takes the rotary centres and directions from the joints themselves (no numbers to type); TCP
   only for axes that turn the part (table side) – a turning head stays Plain, say so in the panel.
2. **G-code reader** (`core/gcode.py`): A/B/C words on G0/G1/G2/G3 (no longer "not supported"), G93 inverse-time
   feed and back to G94, LinuxCNC's feed rule for mixed linear + rotary moves (feed applies to XYZ length; a pure
   rotary move uses °/min), arcs with a rotary word (helical-like: the rotary part goes linearly along the arc),
   G28/G30/G53 with A/B/C, the wrapped shortest way. U/V/W stay "not supported" (reported, as now). Core tests
   without Blender, like `test_gcode_core.py`.
3. **Motion**: the step "Run G-code program" drives the rotary joints; with TCP the X/Y/Z joints get the
   compensated values so the tool tip stays on the programmed point on the turning part (measure: tip vs. the
   programmed point in workpiece space, < 0.01 mm at the samples). Indexed (3+2: turn, then cut) and simultaneous
   (turn while cutting) both work. Tool changes (manual, carousel, double arm) keep the rotary axes where they are;
   Fit into and ATC speed unchanged.
4. **Milling on a turning part**: the bits' path is already read relative to the workpiece – check it stays right
   when the workpiece turns, and add samples during rotary moves so the cut is smooth (chord at the tool tip
   ≤ the detail level's tolerance, e.g. ≤ 0.02 mm Normal, or ≤ 1°; say what you chose). A wrapped cut round a
   cylinder (4th axis) and a 3+2 pocket on a tilted face (5th axis) must look right in the view and in the queue.
   Measure scrubbing and bake time on the long 4-axis cut; keep the Heavy milling cut no slower.
5. **What turns with the part**: the toolpath drawn on the block turns with it (drawn in workpiece space); chips
   that landed on the workpiece move with it (chips on the table/bed stay); the milled look, vice and fixture parts
   on the rotary table just follow their joint. Coolant/air aim at the tool as now.
6. **Two generic test models** (`tools/make_test_4axis.py`, `make_test_5axis.py` → `tests/data` + `fresing_render/data`,
   like `test_atc.step`): a small mill with an **A-axis rotary table + tailstock** along X holding a round bar, and
   one with a **trunnion (A tilt, C rotate)** holding a block. Programs in `TEST_PROGRAM` style: a 4-axis wrapped slot
   + a flat round the bar; a 5-axis 3+2 pocket on two tilted faces + one simultaneous move.
7. **Check button** in the rotary part of the panel (like the double arm's): turns each rotary axis through its range
   in the view and reports the axis direction, centre, and (TCP) how far the tool tip would stray – so a wrongly
   picked joint shows at once.
8. Every button a tooltip; guide "CNC machine > Rotary axes (4th/5th axis)" with two pictures; PC-check line
   `milling.rotary`; test-tour stop "4th and 5th axis" (rule from 0059); `CHANGELOG.md`.

## Done when

- [ ] Core tests: A/B/C, G93/G94, mixed feed rule, wrapped shortest way, arcs with a rotary word, G28/G53 with A/B/C.
- [ ] Blender tests on both test models: the rotary joints follow the program; TCP tip error < 0.01 mm; cut depth
      on the bar measured at a few points (wrapped slot at the right angle and depth); 3+2 pocket on the tilted face;
      save/reopen; scripts off; an old 3-axis project unchanged (same mesh after a cut, same timing).
- [ ] Measured in the report: bake time, scrubbing ms/frame on the 4-axis cut, Heavy milling cut before/after.
- [ ] Tour stop, PC-check line, guide section + pictures, tooltips (tooltip report strict, 0 missing); GitHub green
      incl. Windows; merged to `main`, next free version, released (CLAUDE.md section 7) – before Thursday 08:00.
- [ ] Report filled in; `TASKS.md`: 0066 done; what the owner should try on his PC (tour stop + a Fusion 4-axis post).

## Not in this task

- An app-made toolpath (0029, last). Tool marks on cut faces (0061, Thursday) – leave the cut faces' look as it is.
- TCP for a turning head (head-head or table-head 5-axis): Plain only, noted for later.
- Lathe modes, a C axis as a turning spindle (G33/G76), U/V/W, cutter compensation.
- Clash checking (0065), hoses/cables (0058).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
