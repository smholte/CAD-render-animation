# 0263 – Real size, category C: the winch model's A-frame ×2.5, the spool model's carousel ×2 (rope parts kept)

**Who:** worker · **Status:** running (23 Nov 2026, Claude Code on the web) · **Branch:**
`task/0263-winch-spool-real-size`
**Started by:** lead, 21 Nov 2026 (owner 14:20: every model at a realistic scale, one fix task per type; study **0258**
category C) · **Model:** Opus · effort High
**Area:** Test models lane – `tools/make_test_paths.py` (`test_paths_a` + `_b`), `tools/make_test_spool.py`, the cable part
of `tools/make_test_flex.py` if `flex_drawn`'s cable needs it, their `tests/data/` files + `fresing_render/data/` copies,
maker tests; every place that holds their numbers: `blender/tour.py` – the sets `cables`, `spool`, `served` and the
cable part of `flex_drawn` (**numbers, cameras and framing only**, not surroundings), `pccheck/checks.py` (their lines),
the tests and tools that read them (`grep -rln "test_paths\|test_spool" tests tools fresing_render`; 0258: expected
lengths and turns in ~30 tests), real-app scripts, `tools/guide_screens.py` + guide pictures and texts,
`tools/tour_versions.py`'s record.
**Not:** app code – the cable, spool and catenary solvers (`core/paths.py`, `core/spool.py` …) stay as they are (a fault
found → report it); the public demo; `test_tracks`, `test_swivel`, the offshore models (already real).
**Private vessel:** no – public test models only (CLAUDE.md section 6).

## Why

Study 0258 (`tasks/0258-study-real-sizes.md`, `tasks/img/0258/3_winches_spools.jpg`): the rope parts are real already
(drum Ø0.60, sheaves Ø0.53 / 0.39, wire Ø20–24, D/d 22–30), but the A-frame is 2.1 m tall and the carousel Ø2.0 with a
core too small for its Ø40 cable – beside people they look like models of models.

## The sizes (0258's proposal – lead's decision)

- **`test_paths_a`** (+ `_b`): the **A-frame and base frame ×2.5** (clear height ~5 m, inside 3–8 m); **drum, sheaves,
  wire, chute keep their size and names** – the rope route gets longer, the sheaves sit higher. The deck winch stays.
- **`test_spool`**: the **carousel ×2** (Ø ~4.0, core Ø ≥ 1.0–1.6 for the Ø40 cable's bend radius); the **level-wind
  winch stays** as it is (real). Coil, layers and cable Ø kept; more cable fits – say how much the test length changes.
- **The rule (0258):** scale the layout, never the parts with a real size. Same part names, tree, colours, joints,
  revisions; variants follow their `_a`.

## Watch

- **Expected numbers:** cable lengths, payouts, turns, layer counts, leave angles and fleet angles change for a real
  reason now (longer routes, a bigger core) – not "old × k". Work each new expected value out from the geometry (or the
  solver's own closed form) and say in the report how; never copy what the code prints into the test.
- **Triangles:** 0258 measured **+51 %** for `test_paths_a` at ×3 (the big round parts reach the 0.5 mm facet cap). Keep
  the rope parts at their size and measure again; if it is still large, say so and propose before touching the importer.
- The spool's carousel layers alternate (CLAUDE.md section 8): with another core / layer count keep the partly
  paid-out top layer the right way round – check the guide cage / leave point stays on its rollers.
- Every tour animation 0 clashes, every stop's check, framing again, `changed=` + `python3 tools/tour_versions.py
  --record` after merging `main` once; tests' total time within about +15 %.
- A change the private demo kit could feel (none expected – only test models change) → say so in the report.

## Done when

- [ ] The makers make the new sizes (both copies, variants); maker tests green
- [ ] Every test, tour stop, real-app script and PC-check line green; every changed expected number listed with how it
      was worked out
- [ ] Sets framed again, 0 clashes, `changed=` + the record; guide pictures and texts updated
- [ ] Triangles / import times before–after; tests' total time within about +15 %
- [ ] A line-up picture (person 1.75 m + IBC, test models only) in `tasks/img/0263/`
- [ ] Report filled in, merged, released

## Not in this task

Arms / hoses (0261), routers / chains / way covers (0262), mechanisms (0264), the solvers, the public demo, surroundings.
**Never the cable-lay vessel's equipment, never the Fresing 400.**

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
