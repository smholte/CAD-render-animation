# 0159 – Full carousel and faster cables: measure and speed up cables, paths and spools

**Who:** worker · **Status:** waiting – starts after 0145 is merged (it splits the demo tests this task changes) · **Branch:** `task/0159-full-carousel-cable-speed`
**Started by:** lead chat, 16 Nov 2026 (owner, with photos of a real cable – described below in words; the photos are
**not** committed: CLAUDE.md section 6) · **Model:** Opus · effort High · **Place:** Claude Code on the web, environment
"CAD-render-animation". Subagents allowed (CLAUDE.md section 2).
**Area:** Flex parts lane: `core/paths.py`, `core/spool.py`, `blender/paths*.py`, `blender/spool.py`, `blender/flex.py` (only where shared), `cable_looks.py` only for cost, the demo's coil parameter (`demo_model/params.py` `coil_layers` – the one line), their tests.
**Do not edit:** the demo vessel's shapes (0153 owns the rest of `demo_model/`), the sea code (0148/0154), the Web 3D lane (0142/0143), the new cable look (0158).

## Goal

The demo's carousel is completely full of cable at the start, and cables, paths and spools stay fast with it – live posing, Build, playback and renders – after a measured look at where the time goes today.

## Background

- The demo's carousel (`params.py`: Ø 24 m, `coil_layers = 15` full flat layers, the top one partly paid out; 28.8 km)
  looks part-filled in the owner's renders; he wants it full to the top.
- Known costs from earlier reports: tracks +8.1 ms per frame on the demo (0079, aim +2 ms); a GN modifier costs per
  object even when idle (CLAUDE.md section 8); 0141: a Build re-solve of sea cables; the coil's stripes and the full
  layers drawn as one solid scaled by a step table (0080); `paths.solve_frames`, `spool` trim lengths per frame; the
  demo tests grew to 22 min (0145).

## What to build

1. **Measure first** on the demo (4-core web machine; name it): Make demo time, Build time split by stage and by module
   (paths / spool / flex / tracks / clash), playback frame time (live view, EEVEE), memory, triangles of the coil and
   the cable tubes, render time of one Cycles frame, the live handler's cost while posing. A table in the report.
2. **Fill the carousel:** the coil fills the carousel to its rim (layers up to the coaming, or the length that fits),
   the top layer as today; the demo's stages still start and end right (cable lengths shift – check every shot and the
   demo tests).
3. **Speed up** the top costs found in step 1, for example: draw the full layers as one light solid with the look's
   pattern (no per-turn geometry), only the active top layer and the leaving cable as real tube; fewer points where
   a cable is straight; solve frames once and reuse across Build / web export; cache the wound path; vectorise remaining
   Python loops; skip live solves when nothing that a cable touches moved.
4. Nothing loosened: the same tests pass; clash rows unchanged; looks unchanged (pixel compare of a still).

## Done when

- [ ] Before/after table (step 1's numbers) with the full carousel: Make demo, Build, playback, render, memory;
      target – the full carousel costs no more than today's part-filled one in playback and Build.
- [ ] Render of the full carousel (invented demo) in `tasks/img/0159_*`.
- [ ] Tooltips, guide (pictures of the cable looks from the test model / the invented demo only), PC-check line / tour
      stop, function list for anything the owner sees; GitHub run green; merged; version (CLAUDE.md section 7); report.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
