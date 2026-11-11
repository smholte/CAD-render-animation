# 0074 – Smooth big round parts, light small ones; a video in every paint scheme (study 0069 #17 and #12)

**Who:** worker · **Status:** running (web session, 11 Nov); **merged before Thursday 12 Nov 08:00** · **Branch:** `task/0074-facets-and-variants`
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

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
