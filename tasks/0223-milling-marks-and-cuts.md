# 0223 – Milling: every cut gets the tool-mark look, every cutting move cuts

**Who:** worker · **Status:** open – can start (Machining lane) · **Branch:** `task/0223-milling-marks-and-cuts`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
