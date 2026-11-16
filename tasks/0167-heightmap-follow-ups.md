# 0167 – Height-map cutter follow-ups: fewer faces on walls, true steep flanks, the five known faults

**Who:** worker · **Status:** open · **Branch:** `task/0167-heightmap-follow-ups`
**Started by:** lead chat, 16 Nov 2026 (open points of 0146) · **Model:** Opus · effort High · **Place:** Claude Code on
the web, environment "CAD-render-animation". Subagents allowed (CLAUDE.md section 2).
**Area:** Machining lane: `core/heightmap.py`, the map side of `core/machining.py` (`_MapSide`, the tile join),
`tests/test_heightmap*.py`, `tools/bench_milling_dense.py`, the guide section "Long programs: Fast 3-axis".
**Do not edit:** the tool-change files (0156 runs: `blender/toolchange.py`, `core/toolchange.py`, `ui_gcode.py`), the
people files (0157), the Web 3D lane (0135 runs), the ATC / G-code reading paths.

## Goal

Fast 3-axis (0146, 0.2.117) cuts long finishing programs 40 × faster, but walls cost more faces than the exact cut,
steep rounded flanks are up to 0.2 mm off and a little streaky, and five faults are held by tests marked KNOWN FAULT.
After this task the map's result is as clean as the exact cut wherever a viewer can see it, with fewer faces, and every
KNOWN FAULT is gone.

## Background

Read `tasks/0146-heightmap-cutter.md` (Design + Report: open points 1–6) and the KNOWN FAULT comments in
`tests/test_heightmap_independent.py` (lines with "KNOWN FAULT"). Bench: `tools/bench_milling_dense.py` (M1, the dome,
`--fast`). 0146's numbers (4-core web machine): M1 3.5 s / 29,540 triangles; dome 1.6 s / 21,006; the toolpath test
model 7.5 s / **145,146 faces against 96,588 exact**; ~35–40 ms per frame whatever the program.

## What to do

1. **Faces on walls and steps (open point 1).** The thinning is isotropic (right triangles). Make it follow the
   surface: long thin triangles along walls and step edges (anisotropic thinning or wall strips meshed on their own).
   Aim: the toolpath test model at or below the exact cut's 96,588 faces, M1 and the dome not above 0146's counts,
   same deviation or better.
2. **Steep rounded flanks (open point 2).** Ball deeper than 2/3 R and corner-radius fillets: today up to 0.2 mm off
   (0.16 measured) and streaky in close-ups. Aim: ≤ 0.05 mm at Normal and no visible streaks – e.g. normals taken from
   the tool's own shape on such faces, and/or a finer grid next to steep strips. Same check for island corners
   (0.169), two bits crossing (0.109) and flat ramps (0.138) from 0146's deviation list: say per case what you reached.
3. **The five KNOWN FAULT marks (open point 3; four faults, the first in two tests):** wall on a grid line + tile
   border (faces twice); folded wall faces of small plunged holes; wall without a move where a through hole crosses a
   tile border (no tool marks there); the 0.04 mm rib lost between two grooves (fix if cheap, else state why the
   stated 0.3 mm bound stays). Each fixed fault: its test goes back to the **stated** bound and the KNOWN FAULT mark goes. Nothing loosened.
4. **Tile corners (open point 4):** tiles meet vertex for vertex near a corner forced by a third tile.
5. **Per-frame cost (open point 5), if time allows:** a fast path without a boolean for tiles inside a plain block
   (0146 expected about half of the 35–40 ms). Measure before/after on M1 and the toolpath model.
6. Detail Fine and Fast measured once each on M1 (open point 6).

## Rules

- Speed and face counts measured before and after with `tools/bench_milling_dense.py`, machine named (CLAUDE.md
  section 6). Volumes stay within 0146's 0.6 %; the tour's toolpath stop and `test_tour_clash.py` (toolpath set) stay
  0 clashes; PC-check lines `milling.fast_map` and `heavy.milling_finish` keep passing.
- An **independent tester** (a subagent that did not write the change) re-runs 0146's deviation cases and the KNOWN
  FAULT cases against the stated bounds, both ways, and tries to break the new thinning (thin slots, walls on tile
  borders, a 1 × 0.8 m block).
- No new function the owner sees, so no new tour stop or function-list entry; the guide section "Long programs: Fast
  3-axis" and the tooltip get the new numbers if they change. CHANGELOG + version (section 7).

## Done when

- [ ] Points 1–4 done (5 and 6 measured or stated), every KNOWN FAULT gone or explained, nothing loosened
- [ ] Before/after table (time, faces, deviation per case, per-frame ms) and a small before/after close-up of a steep
      flank in `tasks/img/0167_*`
- [ ] Tests added/updated; GitHub run green; merged; version; report filled in

## Not in this task

V-bit and drill programs (cut exactly on purpose: their grooves are narrower than a cell); rotary / 4th-5th axis;
#11 deviation colours.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
