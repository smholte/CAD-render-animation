# 0167 – Height-map cutter follow-ups: fewer faces on walls, true steep flanks, the five known faults

**Who:** worker · **Status:** done 16 Nov (0.2.134) · **Branch:** `task/0167-heightmap-follow-ups`
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

- [x] Points 1–4 done (5 and 6 measured or stated), every KNOWN FAULT gone or explained, nothing loosened
- [x] Before/after table (time, faces, deviation per case, per-frame ms) and a small before/after close-up of a steep
      flank in `tasks/img/0167_*`
- [x] Tests added/updated; GitHub run green; merged; version; report filled in

## Not in this task

V-bit and drill programs (cut exactly on purpose: their grooves are narrower than a cell); rotary / 4th-5th axis;
#11 deviation colours.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026 (branch `task/0167-heightmap-follow-ups`). Version **0.2.134**.

**What changed**

- New `core/heightmesh.py`: a tile is thinned either with 0146's right triangles or with long **strips** along x or
  y (rows of nodes kept where needed, nodes along each kept row where needed, the rows zipped together, the zip
  checked against the grid's own finest triangles and refined where it is off; strips that would fold are kept
  finer), whichever has fewer triangles. Strips are worked out only for tiles no later move changes, so scrubbing
  stays on the quick right triangles. A node a neighbour keeps on the shared border is fanned into the side's
  triangle instead of making the tile keep more nodes: **tiles meet vertex for vertex, also at corners** (point 4).
- Thinning tolerance = 2/3 of how far the exact cut's many-sided bit lies inside the round one (Ø10 at Normal
  0.010 mm, Ø6 0.006, never below the detail level's 0.005); fine ridges left out below 2.5 x that.
- "Finish at the CAD part": where the map came down onto the finished part it lies 12.5 µm over it
  (`HeightMap._lift`); the map and the part no longer lie on each other (that made 34,000 sliver triangles).
- Extra vertices on edges (`_snap` → `_lost` → `_extras`, `heightmesh.split_edges` / `insert_points`): the foot of a
  wall over a rounded strip (the node there stays on the rounded strip instead of being pulled onto the foot), and a
  rim no node took (a rib of top thinner than a cell between two grooves; edges where neither surface reaches the
  other node are now looked at). Tiles with such vertices stay in right triangles.
- Faults: two passes on one floor are no crease (the wall on a grid line + tile border was 0.048 mm off); no map
  vertex lies in the block's top plane; along a cell's diagonal a node no longer moves onto the other node itself.
- Tests: `tests/test_heightmesh.py` (10, the worker's), `tests/test_heightmesh_independent.py` (29, the independent
  tester's), the vertex-for-vertex check tightened from "within the thinning tolerance" to 1 nm; KNOWN FAULT marks:
  two gone (rib, wall on a grid line 0.048 mm), three left smaller (below).
- `tools/bench_milling_dense.py --only toolpath` (+ `tools/dump_toolpath_program.py`: the toolpath test model's
  program as a file); guide section "Long programs: Fast 3-axis", the setting's tooltip, CLAUDE.md.

**Tested and measured** (4-core web machine, core only, Detail Normal unless said; "before" = 0146's code run
right before or after on the same machine – the machine's timings drift ±20 % between runs)

| | 0146 | 0167 |
| --- | --- | --- |
| M1 triangles | 29,540 | **24,712** |
| M1 whole cut | 2.9–3.0 s | 3.2–3.5 s |
| M1 one frame forward (marks) | 36–38 ms | 42–48 ms |
| Dome triangles | 21,006 | **17,232** |
| Dome whole cut / one frame | 1.5 s / 42 ms | 2.0 s / 48–52 ms |
| Toolpath test model (with the finished part) triangles | 181,636 | **116,670** (exact cut 95,716) |
| Toolpath test model whole cut | 8.3 s | 9.6 s |
| M1 at Detail Fine: triangles / whole cut | 70,848 / 10.0 s | 61,450 / 10.0 s |
| M1 at Detail Fast: triangles / whole cut | 25,990 / 1.5 s | 10,918 / 1.8 s |

Removed volumes unchanged within 0.01 % (M1 15,158.6 mm³, dome 12,978 mm³, toolpath model 133,241 mm³ fast against
133,191 exact).

Deviation fast ↔ exact (worst, both ways, mm; 0146's scenarios in `tests/test_heightmap_independent.py`):

| case | 0146 | 0167 |
| --- | --- | --- |
| ramps of a flat bit (steep strip) | 0.138 | **0.055** |
| ball grooves, 0.04 mm rib between rims | 0.289 | **0.076** |
| corner-radius pocket (fillet) | 0.110 | **0.075** |
| two bits crossing | 0.109 | 0.094 |
| island corners (sharp outside corners) | 0.169 | 0.169 |
| wall on a grid line + tile border | 0.048 | **0.008** |
| surfaces (ball finish, pockets, steps, arcs, round block) | 0.007–0.026 | 0.007–0.025 (ball finish 0.024) |

Point 2's aim (≤ 0.05 mm on steep strips) is reached on the ramps (0.055 ≈) but not on fillets and grooves' round
ends (0.075): see open points. The close-up `tasks/img/0167_steep_flank.jpg` (the corner-radius pocket's rounded foot
of the wall, Cycles): smooth, no streaks; a first version with vertices halfway along the strip drew a saw-tooth there
and was dropped.

Toolpath test model against the exact cut (all faces sampled both ways, 1.26 M points; measured on an earlier state
of this branch with 110,792 triangles): points more than 0.05 mm apart 2.1 % (0146: 4.4 %), more than 0.2 mm 20
(0146: 209).

Locally: all heightmap tests (178), `test_machining*.py`, `test_toolmarks*.py`, `test_cut_normals.py`, tooltip check.
GitHub: see below.

**Subagents**

- *Independent tester* (did not write the change; `tests/test_heightmesh_independent.py`, 29 tests): tiles closed and
  vertex for vertex in 13 hard cases (fins, walls on borders and grid lines, 45° passes, four tiles' corner, grooves
  whose rims touch), the same mesh however a time is reached, all 0146 deviation cases within their stated bounds.
  Found: (1) with "Finish at the CAD part" up to 37 mm² of the part's faces had lost their move – a regression of my
  join, **fixed** (faces named after the map is taken off, by the nearest cut node); (2) small ball Ø2 slots remove
  0.65 % too little (0146: 1.6 %) – KNOWN FAULT, 0.6 % stated; (3) the 1 × 0.8 m block 0.61 % off on its 2.6 x coarser
  grid – the bound scales with the cell as the Design says; (4) on a smooth groove the thinning is within thin + the
  left-out ridge height, not thin alone (the Design states thin + ridge; my brief said less) – open point.
  Container restarted twice for lack of memory (its tests beside mine); it re-ran alone.

**GitHub runs:** 4 full runs, all green: 43966210343 (first push), 43971629369 (after the tester's findings, 26.8 min), 43975917476 (merge main + version, 24.6 min), then one more because `main` moved again before the fast-forward (task 0170's CI change). The container restarted three times for lack of memory (tests and benchmarks run side by side): measure one thing at a time.

**Open points / follow-up tasks**

1. **Faces on the toolpath test model: 116,670 against the exact cut's 95,716** (aim missed by 22 %; 0146 had
   181,636). Where they go: ~15,000 for the tiles with extra vertices (kept in right triangles – strips there drew a
   streak; those vertices fix flank errors of 0.16 mm median, up to 0.9 mm on the steep ball-finished faces of this
   model) and ~9,000 because the finished part's pieces are rebuilt to carry their moves (naming them when the mesh is
   read instead saved them but left the block's top round a pocket and some tile sides wrongly named). Without the
   rounded-strip vertices: 93,800 triangles, flanks back to 0.11 mm. Owner's/lead's choice.
2. **Steep rounded flanks at 0.075 mm** (fillets, round ends of grooves), not ≤ 0.05: needs either a finer grid next to
   such strips or normals and vertices from the tool's own shape; vertices halfway along the strip came closer
   (0.075 → 0.055 on the bull) but drew a saw-tooth in the shading.
3. Three KNOWN FAULT marks left, all one fault: a wall crossing a tile's border lies partly in the side the two tiles
   share and is there twice / without a move – unlabelled faces at through holes 1.8 mm² (0.05 stated), wall faces on
   the grid-line pocket +1.9 % (1 %), plunged holes' wall area +3.1 % (2 %; was +6.5 %, the folded faces are gone).
   Plus the tester's: ball Ø2 slots −0.65 % volume (0.6 %).
4. Per frame about +5–10 ms (+15–25 %) on M1 and the dome (the extra-vertex search in `_snap`); point 5 (a fast path
   without a boolean for tiles inside a plain block) not done.
5. Telling a smooth surface's curvature from fine ridges (`_ridges`): today up to thin + ridge off on smooth grooves.
