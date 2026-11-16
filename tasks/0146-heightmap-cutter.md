# 0146 – Faster milling for dense 3-axis programs: a height-map cutter (study 0069 #8)

**Who:** worker · **Status:** running (16 Nov) · **Branch:** `ccr-5bfdc6c9-l2tm60` (the session's branch)
**Started by:** lead chat, 16 Nov 2026 (owner: start large tasks, a Fable task) · **Model:** Fable · effort High ·
**Place:** Claude Code on the web, environment "CAD-render-animation". Subagents allowed (CLAUDE.md section 2):
interfaces first; an independent tester that did not write the cutter.
**Area (Machining lane):** `core/machining.py` (+ a new `core/heightmap.py`), `blender/machining.py`,
`core/toolmarks.py` / `cut_normals.py` only where the new mesh feeds them, `ui_machining.py`, their tests, the PC-check
Heavy line for milling. **Do not edit:** the Web 3D lane (0142), `tests/test_demo_*` (0145), `paths*`, `demo*`.

## Goal

A long 3-axis finishing program (CAM output or the app's own raster finishing, 0029) cuts in seconds instead of
minutes, with fewer triangles, looking the same – tool marks (0061) included.

## Background

- Study 0069, M1 (`tasks/0069-*.md`): Manifold booleans per move on a dense finishing program (ball Ø6, 100 × 60 mm,
  0.3 mm step-over, 40,401 points → 13,911 segments): **8.1 → 10.5 ms per segment and rising**, ~2.4 min for the
  program, 189,000 triangles; a dome at 0.5 mm step-over 3,586 s. A height map did the whole program in ~2.8 s.
- Must keep: 0061's per-face "which move made this face" (`fr_mk_o/d/a/p` attributes, `Timeline.moves`), the milled
  mesh's normals (`cut_normals.py`), chips/air reading the cut, the frame handler showing the cut at every frame,
  4-/5-axis staying on Manifold (rotary moves are not a height map), undercuts / side cuts staying on Manifold.

## What to build

1. **Hybrid:** a pass that is pure 3-axis with the tool axis along the block's Z (most finishing and roughing) cuts a
   height map (a grid in the work frame, cell ~ step-over/3 or set by quality; per cell the lowest z the tool reached
   and **which move** reached it); everything else (side walls the map cannot hold, rotary, tilted tools) stays on
   Manifold. Decide per move or per program; say how.
2. **Swept tool shapes** in NumPy: flat, ball, bull nose (as `core/toolpath.py`'s drop-cutter, inverted), a move
   swept as a capsule over the grid, vectorised over many moves at once; arcs as their segments.
3. **Mesh from the map** once per frame (only the changed tiles), merged with the Manifold part where both meet; the
   per-face move id → 0061's attributes, so tool marks look as before.
4. **Speed:** measure M1's program and the dome, before/after, on the web machine; the frame-to-frame cost while
   scrubbing; triangles. Target: the M1 program in seconds.
5. **Same look:** pictures of the M1 part and the test toolpath model before/after (cropped, small), max deviation
   of the surface (mm) between the two methods.
6. A setting only if needed ("Fast height map for 3-axis passes", on by default, tooltip), guide sentence, PC-check
   Heavy line timing it, function list entry if a setting is added.

## Done when

- [ ] Hybrid cutter with tests: map vs Manifold surface within a stated tolerance on flat/ball/bull moves, steps,
      pockets, arcs; move ids right; 4-/5-axis and side cuts unchanged (existing tests pass untouched).
- [ ] Before/after numbers (M1, dome, scrubbing, triangles) and pictures in the report; independent tester's findings
      and what changed because of them.
- [ ] Tooltips, guide, PC-check line, function list; GitHub run green; merged; version (CLAUDE.md section 7).

## Not in this task

A full GPU dexel rewrite (0069 says the hybrid gives most of the gain); steep/shallow toolpath splitting (0029 lane).

## Design (worker, 16 Nov – the brief of the subagents; kept as the record)

**Which moves go to the map (per program, then per move).** `core.Timeline(..., fast=True)` (the app passes the
setting "Fast height map for 3-axis passes", on by default; the core's default stays off). A *program* uses the map
only when it is dense: at least `FAST_MIN_MOVES` (300) cutting moves are *map moves*. A move is a map move when:
its tool axis is one of the workpiece's six axis directions (the direction most cutting moves share; within
`ANGLE_TOL`), its bit is a flat, ball, corner-radius, V or drill shape (or a custom outline that is one convex piece),
and the bit's top stays at or above the stock's top (so the move takes away everything above its bottom: no tunnel).
Everything else – rotary and tilted moves, T-slot / undercut cutters, a tool shorter than the cut is deep, small
programs – stays on Manifold exactly as before. Cuts commute (stock − A − B = stock − B − A), so the two parts are
worked out side by side and joined at the end.

**The map** (`core/heightmap.py`, NumPy only, no Manifold, no Blender). A grid of *nodes* in the map frame (u, v
across, w along the tool axis, a signed permutation of the workpiece's axes): per node the lowest w a map move
reached (`h`, float64) and which move (`owner`, int32, the row in `Timeline.moves` after `moves.owner`; -1 = not cut,
`h = top + PAD`). At equal heights the later move owns the node. Cell by detail (Fine 0.1, Normal 0.2, Fast 0.4 mm),
never more than a quarter of the smallest map bit's radius, grown so the grid stays under a node budget.
- `Shape` = a bit seen from below: `f(r)` height above the tip, `R`. `sweep_height(shape, move, u, v)` = the bottom
  of the bit swept along a straight move (closed forms for level moves, plunges, flat and ball on a slope; a 1-D
  convex minimisation for the rest), `inf` outside its footprint.
- `HeightMap.goto(k, partial)` = the map after the first `k` map moves (+ the part of the current move per bit):
  stamps forward, goes back from kept snapshots (every state is made by the same stamps in the same order).
  It reports the tiles (64 x 64 cells) whose nodes changed.
- **Meshing a tile:** (1) *snap*: where two neighbouring nodes belong to different moves and the true surface between
  them is not the straight line (a wall, a rim, a chamfer edge), the place where the two surfaces meet is found on
  the grid edge (bisection on the exact heights) and the node(s) next to it move there – a wall becomes two nodes at
  one place, so walls are vertical and their outlines exact; nodes on a tile's border only move along it. (2)
  *thin out*: a right-triangle hierarchy (RTIN) keeps a node only where leaving it out would move the surface more
  than the detail level's tolerance (Fine 2, Normal 5, Fast 10 µm) or would join faces whose tool marks differ
  (`mark class`: passes of one ball / V bit along the same line share a class, anything with a flat bottom is its
  own). Border nodes are kept when either neighbour needs them, so tiles meet vertex for vertex. (3) each triangle
  takes the move of its lowest corner. Result per tile: a closed solid "everything below the surface" (top, skirt on
  the tile's box, bottom) with the move per top triangle.
- **Joining with Manifold** (`core/machining.py`): per (Manifold tile, map tile) one boolean `tile ∩ below` (+ the
  finished part's piece when "Finish at the CAD part" is on); tiles the map has not cut are one solid
  `tile − boxes`. The pieces are `Tile`s like before (closed solids), so `Timeline.at`, the clash check, volumes,
  `mesh_at`, `mark_faces`, `cut_normals` and the Blender side work unchanged; the move of a map face rides through
  the boolean as Manifold's face id. Pieces are kept while neither their map tile nor their Manifold tile changes.

**Stated tolerance (map vs Manifold):** the surface and straight / round walls within 0.03 mm at Normal (Manifold's
own 40-sided bit is 0.009 mm off on Ø6); at sharp outside corners and features thinner than a cell up to one cell.

**Files and owners.** Worker: `core/heightmap.py`, `core/machining.py`, `blender/machining.py`, `props.py`,
`ui_machining.py`, PC check, guide, function list, version files. Subagents (never push, never touch `TASKS.md` or
version files): *bench* – `tools/bench_milling_dense.py` (M1 and the dome, before/after numbers, new file only);
*independent tester* – `tests/test_heightmap_independent.py` (new file only), written from this Design and the
brief by an agent that did not write the cutter, findings sent back to the worker.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
