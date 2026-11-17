# 0186 – Fix: Fast 3-axis leaves a square hole through the workpiece (bug hunt 6, row 2)

**Who:** worker · **Status:** done (0.2.145) · **Branch:** `task/0186-fast-3axis-hole`
**Started by:** lead chat, 17 Nov 2026 (from bug hunt 6, task 0183) · **Model:** Opus · effort Medium · **Place:** Claude Code on the
web, environment "CAD-render-animation"
**Area:** Machining lane (`core/machining.py` `_MapSide._below` / `_piece`, its tests)

## Goal

A milling animation with **Fast 3-axis** (on by default) never shows a hole that the program did not cut.

## Background

- Row 2 of 0183: tour set "toolpath", the toolpath's own default settings (4,480 moves), Detail Normal, Fast 3-axis
  on, Build → at frames 241 and 251 one 6.4 × 6.4 mm map tile is dropped: its mesh is not manifold
  (`Error.NotManifold`, 821 vertices), `Manifold(mesh)` is empty, `t.solid ^ below` is empty. `_column` already checks
  the status and falls back to a box; `_below` does not. New in 0.2.134 (0167); 0.2.125 has no hole. Deterministic.

## Rules for this task

- Each row's proof, numbers and suggested fix are in `tasks/0183-bug-hunt-6.md` (Findings table): read only those rows.
- Every fix gets a test that **failed before** (CLAUDE.md section 6); nothing loosened.
- Normal finish (CLAUDE.md sections 2 and 7): own branch, area tests locally, version raised last, CHANGELOG in plain
  words, green GitHub run, merge, release. Other fix tasks of bug hunt 6 run at the same time: take the next free
  version when you merge.
- A row you cannot reproduce or fix: say so in the report with what you saw; do not guess.

## Done when

- [x] `_below` (and any other place that builds a `Manifold` from a map tile) checks the status: not NoError or empty →
      the tile's 0146 right-triangle mesh, else a box as `_column` does; say in the report which tiles took which way.
- [x] Test: on the row's case a ray from above through every map tile meets a face at every frame of the cut (the
      exact cut has 0 such columns). Plus a unit test with a made non-manifold tile.
- [x] The height-map tests of 0146/0167 still pass; KNOWN FAULT markers unchanged unless fixed (say which).
- [x] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

The other 0183 rows; tool marks; the toolpath maker.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 17 Nov 2026 · version 0.2.144

**What changed:**
- **Cause, deeper than the brief said:** the bad tile (row's case: map tile (5, 5), frames 241 and 251) has a wall on
  its border with two of 0167's extra vertices at one place (the wall's top, z 62.08 mm, and its foot, 60.60 mm, at
  x −28.47, y −7.77). `HeightMap._ring_extras` sorts the border ring by place only, so their order was chance; the
  top surface ran foot → top, the side top → foot: one edge used twice the same way, `NotManifold`.
- `core/heightmap.py`: `HeightMap._ring_walk` – where two ring vertices stand at one place, the ring follows the top
  surface's own border loop (edges with no twin); left unchanged when no such pair exists or the border is not one
  clean loop through exactly the ring. `mesh(J, I, plain=True)` – the tile with 0146's right triangles only (no strips,
  no extra vertices), not cached, the normal mesh's serial.
- `core/machining.py`: `_MapSide._below` checks the solid (`_solid`: status not NoError or empty → None): then the plain
  mesh, then the tile's box (= block uncut there, as `_column` does). Counted in `tl.stats.extra["map_tiles_plain"]`,
  `["map_tiles_box"]`.
- **Which tiles took which way:** on the row's case with the fix, every tile takes its own mesh (0 plain, 0 box, at all
  276 frames). With `_ring_walk` switched off, tile (5, 5) took the plain mesh at frames 241/251 (1 plain, 0 box) and
  the hole was gone too.

**Tested and measured** (4-core web machine, Blender as a Python module, toolpath test model):
- Row's case reproduced before the fix: toolpath Detail Draft with its defaults (4,541 moves here; the row said 4,480),
  milling Normal, Fast 3-axis, step fitted to 10 s: frames 241 and 251 had 157 rays (0.5 mm grid) from above that
  missed the block. After: 0.
- New `tests/test_fast3axis_hole.py`: every frame 1–276, rays from above every 0.5 mm all hit, every cut map tile's
  mesh a closed solid, no fallback used (310 s here – the slowest new test).
- New in `tests/test_heightmap.py`: the ring order with two border vertices at one place; a made non-manifold tile
  (one top triangle left out) → plain mesh (same volume in the tile within 0.2 %), and with the plain mesh broken too →
  the box (the block uncut in that tile). Before the fix these fail (`_ring_walk`, the fallback and counts did not exist;
  the row's case gave 157 misses).
- `test_heightmap.py`, `test_heightmap_independent.py`, `test_heightmesh.py`, `test_heightmesh_independent.py`: 181
  passed; the KNOWN FAULT markers unchanged (none fixed by this).
- GitHub: 2 full runs. Run 44141651360 green (0.2.144); task 0188 took 0.2.144 meanwhile, so main merged and renumbered
  to 0.2.145: run 44147293452 green (29.6 min), `main` fast-forwarded to that commit (700bfbe).

**Open points / follow-up tasks:**
- None for this row. The independent review was skipped (core Python only, no Windows code).
