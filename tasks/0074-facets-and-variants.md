# 0074 – Smooth big round parts, light small ones; a video in every paint scheme (study 0069 #17 and #12)

**Who:** worker · **Status:** running (web session, 11 Nov); **merged before Thursday 12 Nov 08:00** · **Branch:** `claude/festive-hopper-5bglo9`
**Started by:** lead chat, 11 Nov 2026 (lead's pick from the improvement study – the owner can change it afterwards)
**Lane:** Looks (importer) + Motion (queue) – `importer/step_reader.py` (meshing, `QUALITY`, `CACHE_VERSION`),
`blender/queue.py` / the queue panel in `ui_motion.py` (the queue part only), scheme code in `blender/materials.py`
only if needed; tests, guide
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0073** (Fade step, X-ray look, trail lines: `animation.py`, `ops_motion.py`, the 6 Animation
and 3 Looks panels, `trails.py`). Do not touch its parts of those files, nor machining, clash, `handlers.py`,
`reimport.py`. Take the version number last; whoever finishes second merges `main` once and renumbers.
**If it cannot be green and merged by Thursday 07:00:** push the branch, report, stop.

## Goal

1. Offshore machines have carousels, drums and slewing rings of 2–10 m: at Normal detail a Ø10 m ring shows 3.7 mm
   facets on its outline in close-ups, while an M10 bolt gets 47 segments it can never show (study 0069 M3).
2. The owner wants the same video in every colour option for a customer, rendered overnight in one go.

## What to build

1. **Facets by size** (`step_reader`): keep the relative deflection, but cap the gap between facet and true surface in
   millimetres per Detail (suggestion: Draft 2 mm, Normal 0.5 mm, Fine 0.2 mm) and allow fewer segments for small
   parts (e.g. ≥ 16 round a bolt Ø < 20 mm at Normal). Bump `CACHE_VERSION`. Measure on the test models and a
   generated big ring/drum (Ø2 m, Ø10 m): facet gap, segments, triangles in total, import time – before/after. Total
   triangles of a typical model (EGR-like, many fasteners) must not grow; import time within +10 %.
   An existing project keeps its meshes until a model update (0052) – say what the owner sees then.
2. **Queue in every paint scheme** (7 Render queue, next to "Queue all" of saved scenes): "Queue this animation in…"
   all schemes or ticked ones; one job per scheme, file names with the scheme name, the scheme applied in the job
   only (the open project unchanged), works with Start later (0050/0070). A still in every scheme too, if cheap.
3. Tooltips, guide sections (Import > Detail; Render queue > Every paint scheme), `CHANGELOG.md`; PC-check line for
   the queue variant if one fits.

## Done when

- [ ] Tests: facet gap ≤ the cap on the big ring/drum at each Detail; small bolt segments; cache invalidated; model
      update after the change keeps joints/looks (0052 tests green). Queue: N schemes → N jobs, right names, each
      job's frame shows its scheme's colours, the open project's look unchanged, Start later still works.
- [ ] Numbers in the report (facets, triangles, import time before/after).
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released – before Thursday 08:00.
- [ ] Report filled in; `TASKS.md`: 0074 done.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 11 Nov 2026 · version 0.2.60 · branch `claude/festive-hopper-5bglo9`

**What changed:**
- `importer/step_reader.py`: `FACETS` per Detail and `mesh_params()`. A part whose relative gap could exceed the cap
  (OpenCascade's edge deflection is at most lin_rel × part size / 2) is meshed with the cap in mm (Draft 2, Normal 0.5,
  Fine 0.2), keeping the Detail's angle so its holes keep their segments. **Standard parts** (bolt, nut, washer, pin …
  recognised by `core/fasteners.parse`, biggest side < 200 mm) get 0.7/0.25/0.1 mm and a wider angle: 12/20/32
  segments. Other small parts (end mills, lamps, workpieces) are meshed exactly as before – a first version that
  thinned *all* parts < 100 mm took the test end mill from 28,792 to 984 triangles. `CACHE_VERSION` 6.
  Learned: OpenCascade's angle gives about 4π/angle segments, not 2π/angle (0.3 rad → 42).
- `blender/faces.py`: a model update kept hand-painted faces only when every CAD face had the same triangle count, so
  the new meshing would have dropped paint on big parts and fasteners. `same_faces()` now also accepts the same
  number of faces with about the same area (8 %) and centre (2 % of the part's size).
- Render queue: `FRQueueJob.scheme`, `FRScheme.queue_on`; `queue.add_in_schemes`, the scheme applied in `run_job`
  (after a saved scene, before the bake) only in the background copy; a deleted scheme fails the job; file names get
  the scheme (`<project>_<animation>_<scheme>_<w>x<h>_<quality>_<id>.mp4`, stills `…_<scheme>.png`). New
  `ops_queue_schemes.py` (Animation / Current view, All / None ticks; kept out of 0073's `ops_motion.py`), the fold
  "Every paint scheme" in 7 Render queue. A still in every scheme too (the current view, one hidden saved scene).
- PC-check line `queue.schemes` (MIN_LINES_FULL 51), tour stop `schemes` (MIN_LINES_TOUR / MIN_CHECKS tour 36),
  guide (Import > Detail, Render queue > Every paint scheme, `panel_7_queue.png`), CHANGELOG, CLAUDE.md layout.
- `tools/make_bench_offshore.py`: the invented measuring model (Ø10 m ring with 72 holes, Ø2 m drum, 4 m plate,
  brackets, pins, 1,350 M10–M36 bolts/nuts/washers: 17 unique / 1,369 placed parts).

**Tested and measured** (4-core web session, no graphics card):
- Facet gap on the outline / segments, before → after:

  | | Draft | Normal | Fine |
  | --- | --- | --- | --- |
  | Ø10 m ring outline | 9.9 mm → 0.99 mm | 3.7 → 0.25 mm (82 → 315 seg) | 1.5 → 0.10 mm |
  | Ø2 m drum outline | 2.9 → 0.98 mm | 1.1 → 0.25 mm | 0.45 → 0.10 mm |
  | Ø45 hole in the ring | 26 seg (same) | 42 seg (same) | 70 seg (same) |
  | M10 bolt (standard part) | 29 → 12 seg | 47 → 20 seg (gap 0.06 mm) | 75 → 33 seg |
  | Ø60 pin, end mill, lamp (not standard / middle size) | same | same | same |
- Triangles, bench model, unique / placed: Draft 18,376 / 329,444 → 18,180 / 145,964; **Normal 30,872 / 536,084 →
  31,472 / 240,992 (−55 % placed)**; Fine 54,436 / 876,032 → 55,396 / 413,668. All 27 test models + bench, placed:
  Normal 742,086 → 444,538, Draft 433,634 → 248,594, Fine 1,304,188 → 838,072; unique within ±1 %.
- Import time, all 27 test models + bench in a row, median of 5: Normal 5.21 → 5.18 s, Draft 5.04 → 4.81 s,
  Fine 6.57 → 6.47 s (reading the STEP dominates; meshing is ~0.3 s of the bench's 0.9 s). Not measured on the EGR model
  (not in the repository).
- Tests: `tests/test_facets.py` (8: gap ≤ cap at each Detail on the ring and drum, bolt segments, other parts
  unchanged, rules, cache version 5 refused, painted faces kept through a model update to another Detail and lost when
  a hole moved), `tests/test_queue_schemes.py` (6: ticked/all jobs and names, current view sharing one hidden scene,
  each job's colours at render time, video names, queue.json + Start later, two real Cycles renders red vs blue);
  `test_faces`, `test_model_update`, `test_importer`, `test_step_meta`, queue tests, `test_tour` (45), PC-check lines
  `import.crane` + `queue.schemes` locally OK. GitHub: 3 code runs. The first (16b9486) and the second (c2a9215) had every pytest group, the build
  and the Windows install green, but all real-app jobs failed installing Xvfb/ImageMagick: the runners could not
  resolve *.ubuntu.com for hours on 11 Nov (0073 hit the same). My workflow fallback (archive.ubuntu.com, then the
  runner's own tools) did not help – ImageMagick is not on the runner image; the 7th re-run of c2a9215 went green once
  the mirrors were back. Meanwhile 0073 released 0.2.59 with a kernel.org mirror fallback: merged main once, took
  main's workflow, renumbered to 0.2.60, counts to 52 Full / 37 tour lines (both tasks added one), the tour test
  allows up to 40 stops; the third run (merge commit) is the one main was fast-forwarded to.

**What the owner sees on an existing project:** nothing until **Update to new revision…** (or a fresh import): the
cache of version 5 is not reused, so the next import meshes again; after the update the big round parts are smooth
and the bolts lighter, and painted faces, joints and looks stay.

**Open points / follow-up tasks:**
- The thresholds were tuned on generated shapes and the test models; worth one look on the owner's offshore model
  (Normal: triangles before/after in the 1 Import box).
- Small parts with free names (no DIN/ISO/keyword) keep their 42 segments; a later step could thin plain turned parts
  too, but cutters and workpieces in close-ups must stay.
- No PC-check line for the facets (the owner sees them in renders; the tests cover the numbers).
- Leftover branch on GitHub: `task/0074-facets-and-variants` (pushed at the start by mistake, same commit as main
  then) – please delete it.
