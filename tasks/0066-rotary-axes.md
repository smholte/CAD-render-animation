# 0066 – 4th and 5th axis: rotary axes A/B/C in G-code, joints and milling

**Who:** worker · **Status:** done (10 Nov, 0.2.52, branch `ccr-d3dbbfca-yscg1s`); **must be merged before Thursday 12 Nov 08:00** (0061 starts
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

- [x] Core tests: A/B/C, G93/G94, mixed feed rule, wrapped shortest way, arcs with a rotary word, G28/G53 with A/B/C.
- [x] Blender tests on both test models: the rotary joints follow the program; TCP tip error < 0.01 mm; cut depth
      on the bar measured at a few points (wrapped slot at the right angle and depth); 3+2 pocket on the tilted face;
      save/reopen; scripts off; an old 3-axis project unchanged (same mesh after a cut, same timing).
- [x] Measured in the report: bake time, scrubbing ms/frame on the 4-axis cut, Heavy milling cut before/after.
- [x] Tour stop, PC-check line, guide section + pictures, tooltips (tooltip report strict, 0 missing); GitHub green
      incl. Windows; merged to `main`, next free version, released (CLAUDE.md section 7) – before Thursday 08:00.
- [x] Report filled in; `TASKS.md`: 0066 done; what the owner should try on his PC (tour stop + a Fusion 4-axis post).

## Not in this task

- An app-made toolpath (0029, last). Tool marks on cut faces (0061, Thursday) – leave the cut faces' look as it is.
- TCP for a turning head (head-head or table-head 5-axis): Plain only, noted for later.
- Lathe modes, a C axis as a turning spindle (G33/G76), U/V/W, cutter compensation.
- Clash checking (0065), hoses/cables (0058).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, branch `ccr-d3dbbfca-yscg1s` (the session's designated branch, not
`task/0066-…`), 10 Nov 2026. Version 0.2.52.

**What changed:**
- `core/gcode.py`: A/B/C (degrees, `Move.ra` / `rb`, evenly along a move and along arcs) on G0–G3, G28/G30 (with
  their stored A/B/C), G53, G92, G10 L2/L20; #5164–5166, #5184–5186, #5214–5216, the A/B/C of each work offset and
  #5423–5425. G93/G94 (G93 was already read; now also for rotary-only lines). LinuxCNC feed rule: F along XYZ when
  they move, °/min (combined angle) for rotary-only lines; rotary rapids limit every move. Rotary word on a cycle line:
  reported and left out; U/V/W still "not supported". `Schedule.rot_at`, `turn_spans`, `samples(turn_step=)`,
  `path(turn_step=)`; clean-up moves keep the axes.
- **Wrapped: I followed LinuxCNC, not "shortest way".** The brief says "shortest way"; LinuxCNC's `WRAPPED_ROTARY`
  (its docs and `unwrap_rotary`) goes the way the number's sign says: `A90` the + way to 90°, `A-90` the − way to 90°.
  Since the brief also says "LinuxCNC rules", the app does what the machine does. G28 with A on a wrapped axis goes
  the short way. Say if the owner wants it changed.
- New `blender/rotary.py`: axes from rotate joints; the machine is worked out at A0 B0 C0 whatever the pose (each
  axis' turn undone, inner first); centre K and direction u per axis in machine mm; Plain / TCP; Check; check poses;
  the two test programs and `set_up_test_model`. +A = the tool goes round the part right-handed about +X (ISO; a table
  turns the other way), Reverse flips it.
- `blender/gcode.py`: Machine builds the rotary axes; G54 and the work zero at A0 B0 C0; marker placed turned with
  the part; the bake keys the rotary joints (LINEAR, at every move end), TCP moves X/Y/Z (keys every ~0.9° on the
  trunnion so the tip strays < 0.002 mm between keys; fades in/out over a tool change that goes to the changer, like
  the tool-length lift); warns when the program turns an axis without a joint; limits per rotary joint. Toolpath
  drawn on the part (Plain: T⁻¹ of X/Y/Z, every 2°). `fr_turns` (frames where an axis turns) recorded with the corners.
  Fixed: the tool-tip cache key now includes the mesh (two files with a tool of the same name and vertex count shared
  a tip – found by the PC-check line, which loads both test models).
- Milling: where an axis turns, the path is read with up to 7 halvings per frame (else 4) and a cut piece may turn
  0.5° (else 0.05°); the tip's chord stays within the detail level's tolerance (Normal 0.005 mm). Outside turning
  spans nothing changes (old projects: same signature, same segments).
- Chips: no change needed – chips on the bar ride with it (Copy Transforms of the workpiece), chips on a bed that
  stands still stay (test). Not done: a table that moves *and* carries the rotary (X slide under the 4th axis):
  chips falling past the chuck land on the fixed bed, not on that moving table (two-space chip model; follow-up).
- UI: 4 Motion > CNC machine > **Rotary axes** (A/B/C, Reverse, Wrapped, rapid °/min, Kinematics, Check, results);
  Machine zero also keeps A0 B0 C0. Tooltips: 532 found, 0 missing (strict).
- Test models `tools/make_test_4axis.py` (A table + tailstock + bar Ø50, moving column) and `make_test_5axis.py` (A/C
  trunnion + block 60×60×40), in `tests/data` and `fresing_render/data`.
- PC check line `milling.rotary` (Full, both models, render); tour stops 20 "4th axis: the bar turns" and 21 "5th
  axis: tilt and turn (TCP)"; MIN_LINES_FULL 48, MIN_LINES_TOUR 33, MIN_CHECKS tour 33. Guide "CNC machine > Rotary
  axes (4th / 5th axis)" with `panel_4_rotary.png` and `view_rotary.png` (guide_screens modes rotary / rotary_view).

**Tested and measured** (4-core web session, bpy module, no graphics card):
- `tests/test_gcode_rotary_core.py` (12, hand-worked numbers), `tests/test_rotary.py` (13): joints follow the program,
  wrapped slot 2 deep at the right angle (radius 23.00 at 4 angles), flats 3 deep at A0/A180, other side untouched;
  5-axis: both A30 pockets 3 deep along the tilted tool axis, groove 1 deep along y = 20 cut while C turned 90°; TCP tip
  vs programmed point on the turning block **worst 0.0013 mm over 3,101 samples** (also between frames and keys);
  save/reopen; drivers simple expressions (scripts off); a 3-axis program with and without an A joint gives the same
  joint values, length and **identical cut mesh**; tool change keeps A; toolpath on the bar (radius 23 ± 0.05);
  chips; panel draws; Check (all lines OK on both models, TCP stray 0.0001–0.0002 mm).
- Existing suites of the lane: 256 + 2 passed locally (gcode, machining, toolchange, doublearm, pccheck, guide, CI
  tools); test tour 42 passed.
- **Bake / scrubbing on the 4-axis cut** (FIT 6 s, 151 frames): build 0.02 s, read the path 2.4 s, cut to the end
  2.7–3.1 s (567 cutting pieces); scrubbing with forced refresh 55–270 ms per frame (jumps back and forth).
- **Heavy milling cut** (`heavy.milling`, full size, 121 frames, same 260 faces before and after): per frame without
  chips 3.82 → 3.67 ms, with chips 5.79 → 5.00 ms: no slower.
- PC check line `milling.rotary`: OK in 14 s (cut depths within 0.003 mm, TCP within 0.0017 mm).
- GitHub: 3 full runs on the branch. Run 1 superseded by a fix of my chips test; run 2 red only in "real app machines":
  the tour set titles "4th axis: rotary table" named the tour's project files, and ':' is not allowed in an artifact
  path (nor on Windows) – titles changed, `test_tour.py` now refuses such characters. Run 3 (54413e5) all green in
  11.8 min incl. Windows install + self-test and PC check (suite group 1 took 11.4 min, usually 6.3: test_rotary.py
  joined it – `ci_times.json` not re-recorded). `main` fast-forwarded to 54413e5: mode reuse, release published,
  Windows update-from-release OK, offered to the apps (3.5 min).
- Release: https://github.com/smholte/CAD-render-animation/releases/tag/v0.2.52
- No helper-agent review: no Windows-only code.

**Open points / follow-up tasks:**
- Owner on his PC: test tour stops 20 and 21; then a Fusion 4-axis program (LinuxCNC post, 4th axis about X) on his
  model with Kinematics Plain – press Check first and compare the "A centre from the work zero" with the rotary
  centre in his Fusion machine set-up; tick Reverse if the part turns the wrong way.
- Chips with a 4th axis on a moving table (see above): a third chip space (the rotary's carrier) – small follow-up.
- TCP for a turning head (head-head / table-head): not done (brief).
- Wrapped follows LinuxCNC's sign rule (see above) – lead/owner to confirm.
