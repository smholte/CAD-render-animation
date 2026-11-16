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

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
