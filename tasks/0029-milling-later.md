# 0029 – Milling without a CAM program: the app makes the toolpath

**Who:** worker · **Model:** **Opus · effort High** · **Status:** open – start now (Wed 11 Nov); **merged before
Thursday 12 Nov 08:00** (0061 starts in the same lane then) · **Branch:** worker's own
**Started by:** lead chat, 5 Nov 2026; brief written out 11 Nov (owner's priority 8; 1–7 are done or set for Thursday,
4 motion paths waits for 0058). 4th/5th axis was split off into 0066 (done, 0.2.52).
**Lane:** Machining – new `core/toolpath.py` (no Blender), new `blender/toolpath.py` + `ops_toolpath.py`, a part of the
Milling panel in `ui_machining.py`; `blender/props.py` (additive); reads (does not change) `core/machining.py`,
`core/tools.py`, `core/gcode.py`; adds a G-code step through the existing step code in `ops_gcode.py` (a few lines);
tests, PC check, test tour, guide "Milling > Make a toolpath"
**Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0067** (Clash lane + the test-model makers `make_test_atc/gantry/linkage.py`). Do not touch
those, nor `handlers.py`, `animation.py`, `reimport.py` (0058 Thursday). Two releasing tasks at once: take the version
number last; whoever finishes second merges `main` once and renumbers.
**If it cannot be green and merged by Wednesday 22:00:** push the branch, fill in the report and stop; the lead then
lets 0061 go first on Thursday and this task merges `main` after it.

**Defaults the lead chose (owner can change them before or after):** the app writes a **LinuxCNC G-code program**
(`.ngc`, next to the project like the other programs) and adds a normal "Run G-code program" step for it – so the
spindle, tool changes, coolant, air, chips, toolpath drawing and later 0061's tool marks all work without new code.
**3-axis, from the top (+Z of the work zero) only**; undercuts stay (reported). No OpenCAMLib: a drop-cutter in NumPy
(OpenCAMLib has no Python 3.13 wheels).

## Goal

For a marketing video the owner wants a block turning into the finished part without first programming it in Fusion
CAM. He picks the stock and the finished CAD part (both already known to the Milling set-up, 0027 "finish at the CAD
part"), picks a roughing and a finishing tool from the tool library (0040), presses **Make toolpath**, and gets a
believable roughing + finishing program that cuts the block into the part – never into the part.

## What to build

1. **Panel** (Milling > Make a toolpath): Stock (the workpiece) and Finished part (shown, from the set-up), Roughing
   tool, Finishing tool (from the tool list; flat, bull or ball – say which kinds you allow), leave stock (0.3 mm),
   step-down, stepover (% of Ø), finishing stepover from a **scallop height** (0.01 mm) for ball/bull tools, pass
   direction (angle), feeds and speeds (from the tool if set, else defaults per stock material: aluminium, steel,
   POM), coolant/air (M8/M7 as in 0042/0039), **Make toolpath** (with progress + Cancel), a result line (moves,
   length, machining time at the feeds, the time "Fit into" would squeeze it to). Every button a tooltip.
2. **Paths** (`core/toolpath.py`, tested without Blender):
   - **Drop-cutter**: the lowest Z the tool's shape (flat / ball / bull, from `core/machining.tool_profile`) can
     reach at an X/Y without going into the finished part – on a grid, vectorised (NumPy), plus a top-face test so
     nothing is milled above the stock.
   - **Roughing**: Z levels by step-down down to the part (+ leave stock); per level, the area of stock outside the
     part (from the drop-cutter field at that level) cleared **contour-parallel** (offset rings inwards from the
     stock edge) or zigzag – your choice, say why – with linking moves that stay above the material (retract, and
     ramp or helix into material: no flat mill plunging straight down).
   - **Finishing**: a parallel (raster) pass at the chosen angle following the drop-cutter surface, segments
     simplified to the detail level's tolerance; optional waterline contour pass for steep walls (≥ 60°), if time.
   - The program: header (G21 G90 G17 G54 G94), T/M6 per tool (with Tn before, so the double arm pre-indexes), S/M3,
     M8/M7 as set, G0 at a safe Z, G1 with F, M5 M9 M30 at the end; comments naming the passes.
3. **Animation**: the program goes in as a "Run G-code program" step (making the toolpath again replaces that step,
   asking first if the program file was edited by hand). Material removal, chips etc. then run as for any program.
4. **Speed** matters: the cut per straight move is a mesh boolean (0027), so a path with 50,000 tiny moves is slow.
   Keep the number of moves reasonable (merge collinear points, simplify to tolerance), give a **Detail** choice
   (Draft / Normal / Fine) if needed, and measure: path making time, moves, "cut to the end" time, scrubbing ms/frame.
   Aim: the test part made in < 30 s and cut to the end in < 60 s on the web machine at Normal.
5. **Test model** `tools/make_test_toolpath.py` → `test_toolpath.step` (tests/data + fresing_render/data): a stock
   block and a finished part with a pocket, a boss with a fillet, a dome or a sloped face (for the ball finish), a
   through hole (left as is – or drilled with G81 if a drill is in the tool list; your choice), and an undercut (must
   be reported, not cut).
6. **Check the result** against the CAD part (the important test): at many points on the finished part, the milled
   mesh is **never inside the part by more than 0.01 mm** (no gouges) and the stock left is ≤ leave stock + scallop
   after finishing (≤ leave stock + step-down cusps after roughing only). Run 0065's clash check on the made program:
   holder and spindle against the stock → 0 rows.
7. PC-check line `milling.toolpath`, test-tour stop "Make a toolpath" (both tools, roughing + finishing), guide
   section with a picture, `CHANGELOG.md`.

## Done when

- [ ] Core tests: drop-cutter for flat / ball / bull against hand-worked shapes (a sphere, a slope, a step); roughing
      levels and leave stock; ramps; the program text reads with our own reader (`core/gcode.py`) without problems.
- [ ] Blender test on `test_toolpath.step`: no gouge > 0.01 mm, stock left within the numbers above, undercut reported,
      save/reopen, scripts off, making the toolpath again replaces its step; an old project without it unchanged.
- [ ] Measured in the report: path making time, moves, cut time, scrubbing, at Draft/Normal/Fine (or what you built).
- [ ] Tour stop, PC-check line, guide + picture, tooltips (strict, 0 missing); GitHub green incl. Windows; merged to
      `main`, next free version, released (CLAUDE.md section 7) – before Thursday 08:00.
- [ ] Report filled in; `TASKS.md`: 0029 done; what the owner should try (his own part from Inventor as the finished
      part and a block round it, his BT30 face mill + end mill).

## Not in this task

- 4th/5th-axis toolpaths (3+2 or simultaneous – later, on top of 0066), adaptive/trochoidal roughing, rest machining,
  pencil passes, threads, cutter compensation; holder collision avoidance in the path itself (the clash check reports).
- Tool marks on the cut faces (0061, Thursday) – leave the cut faces' look as it is.
- Chips on a moving 4th-axis table (0066 follow-up).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
