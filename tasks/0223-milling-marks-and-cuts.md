# 0223 – Milling: every cut gets the tool-mark look, every cutting move cuts

**Who:** worker · **Status:** running (Machining lane) · **Branch:** `task/0223-milling-marks-and-cuts`
**Started by:** lead, 19 Nov 2026 (owner, 00:16, test tour on 0.2.168: "the milling models in the test tours, not all
get the good tool marks texture in cutting material, and not all cutting operations cut even when it shows the
g-code going through the material") · **Model:** Opus · effort High
**Area:** Machining lane – `core/machining.py`, `blender/machining.py`, `core/heightmap.py`, `core/heightmesh.py`,
`core/toolmarks.py`, `blender/toolmarks.py`, `core/cut_normals.py`, `blender/gcode.py` / `core/gcode.py` only where a
move is wrongly treated as not cutting; the machining tour sets in `tour.py` (their builds and checks, `changed=`);
their PC-check lines; tests.

## Goal

In every milling model of the app – each machining set of the test tour, the PC check, a user's own program – the
faces the bit cuts show the tool-mark look of task 0061 (the owner's second picture: scallops, sharp pocket edges,
metal), and every move that goes through material with the spindle on removes it. No milling model left that shows
plain grey, soft or wavy cut faces (the owner's first picture), or a toolpath line running through uncut stock.

## Background

- Owner's pictures (19 Nov, 0.2.168): **good** – a pocket with scallops and sharp walls (looks like the `marks` set);
  **bad** – a block with two shallow, soft-edged dents, plain grey, the green feed path drawn deeper than the cut,
  the blue dashed rapids, the bit inside the material at top right. Which stop it was is not known: go through all of
  them.
- **The checks did not see it:** the owner's PC check in mode Tour on 0.2.168 (19 Nov 00:14, RTX 3090): 83 OK, 0
  failed in 281 s – every machining stop (`gcode`, `accel`, `tools`, `hand`, `marks`, `atc`, `doublearm`, `rotary4`,
  `rotary5`, `toolpath`, `chips`, `air`, `coolant`, `operator`, `cut_look`) passed while he saw missing marks and
  uncut moves. The new checks must fail on exactly that.
- Lead's first look (not proven): the tool-mark attributes `fr_mk_o/d/a/p` are written only by the Manifold route
  (`core/machining.py`, `blender/machining.py` ~line 1195, task 0061). The **height map** for long 3-axis programs –
  "Fast 3-axis" (0146, 0167, 0186) – does not mention them at all: a model on that route would get no marks. The soft
  dents of the bad picture also look like a coarse height map or the quick normals of `refresh(quick=)` that were never
  replaced by the exact ones (`make_fine`).
- Other suspects for "the path goes through but nothing is cut": the bit's cutting length / shank (a cut deeper than
  the flutes), a tool copy after M6 or a tool from the ATC / double arm that is not registered as the cutter, a rotary
  set (4th / 5th axis, TCP) whose workpiece moves while the cut is computed in the wrong frame, a frame range or tile
  limit the cut stops at, the height-map tile edge, moves with the spindle off (M5) – which correctly do not cut but
  should then not be drawn as a feed – and G0 rapids through material (should they cut, warn, or both? say what the
  app does and propose; a rapid through stock is a crash on a real machine).
- Machining sets of the tour (all last changed at 0.2.101 or earlier, except `gantry` 0.2.161): `mill`, `gantry`,
  `atc`, `doublearm`, `rotary4`, `rotary5`, `toolpath`, `tools`, `marks`, `air`, `coolant`, `operator`; the `cut_look`
  stop of the Look group lives in `mill`.

## What to do

1. **Find out first, per set:** for every machining set, Go to each of its stops, play its milling animation and
   record (a) which route cuts it (Manifold / height map / none), (b) whether the cut faces carry `fr_mk_*` and the
   cut-face material, at the first frame, mid-way, at the end and after the frame stands still, (c) the volume the
   program's cutting moves sweep through the stock vs the volume removed (a number per set; a small table in the
   report), (d) a small Material-preview and a Cycles picture of the cut. Write the table into the report **before**
   fixing – it is the evidence.
2. Fix every cause found: marks on the height-map route (the same four attributes and the same look as the Manifold
   route, measured on `marks`'s program run both ways), exact normals reaching the view and renders on every route,
   every cutting move cutting, the feed path not drawn where the bit does not cut.
3. Each machining tour set shows the current best of what it is about: marks on, sharp edges, its own check proving it
   (a check that fails when a set loses its marks or a move stops cutting). `changed=` on the sets and stops whose
   result changed; `tools/tour_versions.py --record`.
4. PC check: one Full line (or a change to an existing one) that fails on a cut without marks or a cutting move that
   does not cut.

## Done when

- [ ] The report's table: every machining set, route, marks yes / no, swept vs removed volume – before and after
- [ ] Every machining tour set shows marks on all cut faces and removes what its cutting moves sweep (within a
      stated tolerance); the height-map route has marks too
- [ ] A test per cause found that failed before; the tour checks catch a lost look or a missed cut
- [ ] Guide's milling pictures replaced where they changed; PC-check line; precheck green; merged, released

## Not in this task

Tour sets outside machining (study 0224 looks at them). New milling features. Deviation colours (#11).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 19 Nov 2026

**What was found** (step 1, before fixing – Linux web machine, 4 cores, Blender 5.2.3 as a module; every machining
tour set built as on 0.2.169, each stop's Go, the program played to its end):

| Set | Route | Milling set up | Cut faces with tool marks | Removed / swept by its moves (mm³) | Tool tips left in material | Drawn feed path in uncut block | Cut-face look |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mill | booleans | yes | 1,435 of 1,435 mm² | 3,391 / 3,391 | 0 of 170 | – (not drawn) | steel, machined |
| gantry | – | **no** | – | **0** / 3,465 | – | **267 of 305 points** | – |
| atc | – | no | – | 0 / 0 (program stays above the block) | – | 0 | – |
| doublearm | – | **no** | – | **0** / 1,035 | – | **176 of 260 points** | – |
| rotary4 | booleans | yes | 3,570 of 3,570 mm² ¹ | 5,187 / 5,187 | 0 of 2,028 | 0 ² | **grey paint** |
| rotary5 | booleans | yes | 907 of 907 | 1,334 / 1,334 | 0 of 465 | 0 | **grey paint** |
| toolpath | booleans (Fast) | yes | 12,409 of 12,409 ¹ | 131,287 / 131,287 | 0 of 36,199 | 0 | **grey paint** |
| tools | booleans | yes | 5,148 of 5,148 | 8,297 / 8,297 | 0 of 528 | 0 | **grey paint** |
| marks | booleans | yes | 4,267 of 4,267 | 6,811 / 6,811 | 0 of 889 | – | aluminium, machined |
| air | booleans | yes | 5,159 of 5,159 | 11,382 / 11,382 | 0 of 627 | – | **grey paint** |
| coolant | booleans | yes | 5,159 of 5,159 | 11,382 / 11,382 | 0 of 627 | – | **grey paint** |
| operator | – | **no** | – | **0** / 1,176 | – | (path hidden; the bit runs 1 mm deep through the block twice) | – |

¹ the faces that close a tile inside the material (7,730 / 7,262 mm², nobody sees them) have no maker and no marks –
not a fault, left out of the count. ² my first count (174 of 419) measured "up" as +z on a turning bar; point by
point at each point's own frame the drawn path is on the bit's tip within 0.001 mm (rotary5, tools 0.0001 mm,
toolpath 0.06 mm max).

The height-map route (Fast 3-axis), which no tour set uses: the `marks` program forced through it gives the same marks
as the booleans – 4,280 mm² cut, 0 without marks (booleans 4,267 / 0), face-mill arcs 0.30 mm apart both ways
(F900 / S3000), 6,820 vs 6,811 mm³; the `toolpath` program 12,514 mm², 0 without marks, 131,543 vs 131,287 mm³. The
lead's first suspect (no marks on the map) does not hold. The exact corner normals are right on every route (walls
lean only round the slot ends, 0 % of the area smoothed across an edge).

So two causes, both outside the cutting core:
1. **Three sets ran their program through a block nothing cut**: gantry (the owner's picture: green feed path, blue
   dashed rapids, the bit in the material), double-arm and operator had a CNC tool and workpiece but no milling
   set-up. A user's own CNC set-up (also the Set-up window's 5 steps) ends the same way – Milling is a separate panel.
2. **Ten of the twelve blocks are painted** (as imported: grey satin paint; only `mill` and `marks` give the block a
   metal). Task 0051's rule "paint stays as the block" made their cuts grey satin paint with paint's faint marks at
   real size: plain grey, soft-looking dents (the owner's first picture). The geometry and normals were right – the
   soft look was the paint (close-up renders before / after in the session).
The old checks could not see either: no stop of gantry / double-arm / operator looked at the block, and the marks
checks only asked whether the attributes and the node exist.

**What changed:**
- `core/machining.cut_look`: a painted block (every paint, and no material at all) cuts to *Aluminium, machined* –
  the metal under the paint, with its crisp marks. Glass, wood, rubber, concrete stay as before. Tooltip of Cut faces
  and two guide paragraphs say so.
- New **Use the CNC tool and workpiece** (`fresing.mill_from_cnc`, `machining.use_cnc`): one click makes the
  spindle's tool the bit and the CNC workpiece the block. Offered in 4 Motion > Milling and under the workpiece in
  4 Motion > CNC machine ("Nothing is cut away yet") whenever the CNC has both and Milling neither
  (`machining.cnc_unused`). Function-list entry `milling.from_cnc`, guide anchor `milling-cnc`, `panel_4_air.png`
  remade (the only guide picture with that state).
- Tour: gantry, double-arm and operator use it (`_mill_with_cnc`), their "what you should see" names the cuts,
  `changed=0.2.NN` on the three sets and their stops.
- The check (`machining.audit` / `audit_problems`, `tour.check_milling`): cut faces seen from outside without marks
  (≤ 1 % allowed, `Timeline.cut_cover`), the cut faces' material draws marks (not the block's own look), every tool
  tip 0.3 mm up its axis, every 0.5 mm along every move through the block, lies outside the material at the end
  (`Timeline.left_in_stock`, the finished part excepted), and with no milling set-up: no feed move of the program
  inside the CNC workpiece (`program_through`). Wrapped round the check of **every stop of the 12 machining sets**
  (`MILLING_SETS`), so the PC check's mode Tour runs it too.
- PC check line **milling.shows_program** (Full): the gantry program – marks everywhere, every move cut, a painted
  block cuts to bare aluminium, then Milling taken off must be found and put right with the button.
  `MIN_LINES_FULL` 105.
- Not done: a Build line for "the program runs through an uncut workpiece" – tried first; the geometric test took
  minutes on long programs (the 20,000-line bake test went 285 s) and 12 motion tests run programs through un-milled
  blocks on purpose. The panels' button is cheap and visible; the check stays in the tour and PC check.

**Tested and measured** (Linux web machine, 4 cores, no graphics card):
- After the fix, every machining stop's check passes with the new part (16 stops, notes like "cut 2,331 mm², all
  with tool marks (booleans); every move through the block cut (742 tip points)"); gantry 2,331 mm² / 3,465 mm³ =
  swept, double-arm 1,321 / 1,035 = swept, operator 1,554 / 1,176 = swept, 0 tips left; on 0.2.169's sets the check
  fails on gantry, double-arm and operator (and on every painted set's look).
- `tests/test_milling_shows.py` (12): marks on both routes, hidden seams not counted, a cut face that lost its maker
  found, every move cut on both routes, four skipped passes found at their frames and place, the finished part not
  counted, the gantry without milling found and fixed by the button, painted blocks cut to aluminium, the tour check
  catches lost marks and skipped moves on the `marks` set, every machining stop carries the check.
- Close-up Cycles renders of gantry, double-arm, tools, rotary5 before / after: plain grey dents → bright machined
  metal with sharp edges.
- PC check lines milling.shows_program, milling.cut, milling.cut_look, milling.rotary: OK in 22 s.
- RUNS_PLACEHOLDER

**Open points / follow-up tasks:**
- G0 rapids and moves with the spindle off (M5) cut like feed moves: the cut follows where the tool went, so the
  picture stays honest, but a rapid through stock is a crash on a real machine. Proposal: a line in the step's
  problems "G0 at line N runs through the workpiece" (the program reader knows rapids; one test per program, not per
  Build), and draw M5 moves as rapids. Not done here (new feature).
- No tour set exercises the height-map route; the `toolpath` set stays on the booleans (cell too coarse at Fast for
  its Ø10 ball). Measured both ways above; a set on the map would need a denser program.
- The tour blocks keep their grey paint outside (only the cuts are metal now). Giving them sawn aluminium in 3 Looks
  would look more like stock – a picture change for 0224's packages, not done.
