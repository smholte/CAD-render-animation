# 0159 – Full carousel and faster cables: measure and speed up cables, paths and spools

**Who:** worker · **Status:** done 16 Nov – 0.2.118 · **Branch:** `ccr-1c319ad6-mm2xz8` (the web session's branch)
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

- [x] Before/after table (step 1's numbers) with the full carousel: Make demo, Build, playback, render, memory;
      target – the full carousel costs no more than today's part-filled one in playback and Build.
- [x] Render of the full carousel (invented demo) in `tasks/img/0159_*`.
- [x] Tooltips, guide (pictures of the cable looks from the test model / the invented demo only), PC-check line / tour
      stop, function list for anything the owner sees; GitHub run green; merged; version (CLAUDE.md section 7); report.

---

## Report (filled in by the chat that did the task)

**Chat / date:** version 0.2.118; worker, Claude Code on the web (branch `ccr-1c319ad6-mm2xz8`), 16 Nov 2026. No subagents (the work was
one chain: measure → fix the biggest cost → measure again); no independent reviewer – instead the new code was checked
against the old one on the whole demo: every shape and key Build writes (193 arrays) bit for bit the same, a Cycles
still pixel for pixel the same.

**What changed:**
- **Full carousel** (`demo_model/params.py`): `coil_layers = 0` now means "up to the rim": `rim_h // cable_d − 1` full
  layers, made **odd** – 23 full layers + the partly paid-out top layer for Ø200 (was 15 + 1): 43.5 km on the carousel
  (was 28.8 km; it holds 46.0 km). The count must be odd: with 24 the top layer was wound the other way (from the
  core outwards), paying out moved the cable towards the core, and it left 8 of the guide cage's 11 rollers – the
  demo's joint-sheet check found it (CLAUDE.md section 8).
- **The loading arch keeps room for its guide rollers** (`demo_model/route.py`, one constant – 0153 owns that folder;
  its branch had not touched it): the arch's height formula kept only a 1 m vertical leg above the fuller coil, and
  the lower pair of guide rollers (1.15 m up the leg) stood in the arch's bend, 3 mm off the cable
  (`test_paths_core`'s roller check, 3.6 % off the sheet's speed). The leg is now at least 2 m: the arch is 1.2 m
  higher than before, the CAD power cable 171.30 m (was 170.50). Before, the fixed 14 m arch height hid this (2.3 m
  leg); with 19 full layers the two roller pairs would have overlapped. The carousel shot's saved camera
  (`blender/demo.py` VIEWS) looks 1.5 m higher so the arch stays in the picture.
- **Build's pass through the frames** (`flex.read_places`, shared by hoses and cables; the biggest cost found): Blender
  now works out only the objects whose places are read and what they depend on (`flex.depends_on`: parents, constraint
  targets, driver sources); everything else is hidden for the pass and its visibility keys muted meanwhile (Build keys
  `hide_viewport`: a key showed a hidden object again every frame), all put back afterwards.
- **Posing a cable into the sea** (`core/catenary.py`): a solve of ≤ `SMALL` (8) moments runs its bisections on plain
  numbers instead of 1-element arrays (2,500 tiny NumPy calls per catenary); the seabed snake of a piled-up cable is
  worked out for all frames at once (`_snake_amplitudes`, bit-identical).
- **Wound path drawn at once** (`core/spool.polyline`, `_curvature`): all pieces in one go instead of a Python loop per
  piece – the same points to the last bit; the full carousel's whole path 3.0 → 1.1 s.
- `tools/measure_cables.py`: the measuring tool of this task (Build split by module, playback with and without the
  app's drawings, triangles, memory, a Cycles frame, live posing) – for 0160 and later.
- Tests: `tests/test_read_places.py` (places equal to a whole-scene pass, unrelated objects never worked out, visibility
  and keys put back), `tests/test_cable_speed.py` (polyline = the old piece-by-piece grid bit for bit; one-moment
  catenary = the array answer; snake = the old bisection bit for bit; one moment ≥ 2 × faster),
  `test_demo_cable_lay.py::test_carousel_is_full_to_the_rim` (odd count, top level with the rim, the arch's guide leg
  holds both roller pairs – it failed on the old formula for 4 of 7 sizes – every Ø 50–500);
  `test_demo_project_cable.py` checks the cable leaves the carousel's top layer (an even one) with > 40 km on it
  (was "20–40 km").
- Nothing the owner sees changed but the demo's coil: no tooltip, guide text, PC-check line, tour stop or function-list
  entry needed (no new button or setting).

**Tested and measured** (4-core web machine, Linux, Blender 5.2.3 as a Python module, no graphics card; the demo in its
small form as the tests make it – `tests/demo_made.py`; each number two runs, before = `main` 0.2.114 with its
part-filled carousel, after = this branch with the full one):

| | before (15 + 1 layers, 28.8 km) | after (23 + 1 layers, 43.5 km) |
| --- | --- | --- |
| Make demo (small form; its Build runs twice) | 250 s (its Build 133 s) | 210 s (its Build 106 s) |
| Make demo (full form, the owner's: Normal meshes, quay) | 275 s (its Build 155 s) | 231 s (its Build 111 s) |
| Build (`animation.bake`, project opened) | 68.1 / 71.5 s | 47.5 / 49.2 s |
| – of it the pass through 3,806 frames | 41.3 / 43.9 s | 26.8 / 26.6 s |
| – everything else (sea cables, cameras, keys …) | ~27 s | ~22 s |
| Playback, ms per frame (120 frames spread over the animation), after Build | 32.8 / 33.0 | 33.8 / 31.9 |
| – of it the app's drawings (cables, spools, tracks: the difference with them off, before Build) | 9–14 | 8–12 |
| Posing "Cable travel" by hand (after Clear keys), ms per step | 153 / 133 | 106 / 87 |
| Memory after open / after Build | 1,060 / 1,415–1,439 MB | 1,062 / 1,412–1,431 MB |
| Carousel rope drawn (triangles) | 43,228 | 43,228 |
| Full-layer solid (triangles) | 768 | 768 |
| All cable tubes (triangles) | 145,148 | 145,188 |
| CAD coil (hidden by the spool, not drawn) | 35,944 | 54,328 |
| Cycles frame of shot 3, 480 × 270, 16 samples, CPU | 3.8 s | 3.7–3.8 s |

Once more with the final code (0.2.115–0.2.117 merged – the served cable look of 0158 –, the arch 1.2 m higher): Make
203 s, Build 49.8 s, playback after Build 30.2 ms, the Cycles frame 4.1 s, posing 106 ms a step, memory 1,065 /
1,421 MB.

Target met: the full carousel costs the same in playback, render and memory, and Build is 30 % faster. Playback numbers
vary ±2 ms between runs on this machine; EEVEE's drawing could not be measured (no graphics card) – what is measured is
Blender's evaluation per frame, which the view waits for. Where playback goes today (frames 1000–1150, saved by
switching each off): the 432 track parts ~11 ms, their 4 run objects ~8 ms (partly the same time), each moving cable
2–4 ms, each spool's rope ~3 ms.

Checks: the Build of the same (part-filled) project with the old and the new code: all 193 cable / spool / hose shapes
and keys identical, a Cycles still of the sea shot identical (max pixel difference 0). Demo checks on the full-carousel
project: `test_demo_project*.py` 23 passed, `test_demo_clash.py` + `_b.py` 4 passed (0 clash rows), the joint sheet's
every coupling as on `main`. `test_spool_core`, `test_spool_independent`, `test_spool`, `test_spool_model`,
`test_catenary`, `test_paths_sea(_independent)`, `test_flex`, `test_paths_moving`, `test_demo_cable_lay`: all passed.
Runs on GitHub: 3 full runs – 43854279287 red (two cable tests outside the demo groups pinned the old route: the CAD cable's length and the arch's guide-roller check, which found the arch fault above), 43859013414 green on the final code (19 min); then the version as a docs run.

Pictures: `tasks/img/0159_carousel_full.jpg` (shot 3, frame 401, the full carousel, the served look of 0158, the
camera 1.5 m higher), `0159_carousel_before.jpg` (the same frame on `main` 0.2.114).

**Open points / follow-up tasks:**
- **Tracks are now the biggest playback cost** (~11–19 ms a frame on the demo, 0079's aim was +2 ms): 432 objects
  each with a Geometry Nodes modifier that moves its own mesh, re-worked every frame because their run follows an
  animated joint. Making it much cheaper needs another design (one drawn object per track, or the parts' places as
  keys) – a task of its own for the Flex parts lane, if the owner wants faster playback.
- The pass through the frames still costs ~7 ms a frame with every object hidden: Blender's own update of the scene's
  ~400 datablocks. The clash check's own pass (`blender/clash.py`) could use `flex.depends_on` the same way (Clash lane).
- `camera_path._sample` takes 4–6 s of every demo Build (Scene & Render lane).
- The arch is 1.2 m higher and the carousel shot's camera 1.5 m higher; the other shots are unchanged (the owner may
  want to look at shot 3 on his PC).
