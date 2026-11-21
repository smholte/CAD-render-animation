# 0255 – Coolant liquid A: the liquid core (`core/liquid.py`) – shallow-liquid height field, fast enough for a 10-minute program

**Who:** worker · **Status:** open – can start · **Branch:** `task/0255-liquid-core`
**Started by:** lead, 21 Nov 2026 (study 0251, build task A; owner 20 Nov 23:45–23:50: coolant liquid that collects in
the cut slots, moves with the machine and runs down a drain – study first, then build) · **Model:** Opus · effort High
**Area:** Machining lane – **new files only:** `fresing_render/core/liquid.py` (no Blender), its helper-process runner
if it needs one (`fresing_render/core/liquid_pool.py` or similar), `tests/test_liquid*.py`, CLAUDE.md section 3 (one
line per new file), `THIRD-PARTY-NOTICES.md` only if a library is added (none expected: NumPy only).
Start from the prototype on branch `task/0251-study-coolant-pools` (`tools/proto_0251/liquid.py`, `standalone.py`).

**Not:** anything in `blender/` (that is task B), the coolant jets (0042, `blender/coolant.py` and friends), the
test mills (0249 is running in the Test models lane), the tour, the PC check, the guide. No version raise unless the
precheck needs one for a new `core/` file (a `core/` module the app does not import yet ships but does nothing –
say in the report what the precheck asked).

## Goal

A tested, fast, deterministic liquid solver without Blender that task B can hang on the machine: per surface a grid
("chart") of bed heights and liquid depths, stepped through the frames of an animation from the carriers' matrices,
the pours and the drains – with exact volume bookkeeping, the six stand-alone tests as pytest, and the speed to bake
the 0249 VMC's 10-minute program in under 10 minutes at Normal on the owner's PC.

**Owner's picks (21 Nov 13:59, 0251's page):** method **a**; settings = one tick "Liquid on the machine" + Detail tied
to Draft / Normal / Final; **chips carried by the liquid** and **the air blast pushes the liquid out of pockets** – both
wanted as later steps (after B). So keep the API open for them now: **per-cell flow velocity out** (for chips) and **an
extra push per cell in** (the air jet's wall jet of `core/air.py` as a tangential force or surface stress), each with
one test (a constant push moves a pool the expected way; the velocities out agree with flux / depth). Not more.

## Background (study 0251 – read its report: "Recommendation", items 1–5, the table, "Demo-sized projects")

- **Method a, shallow-liquid height field:** signed fluxes on cell faces (virtual pipes, waves at √(gh)), laminar wall
  friction 3ν/h² + a Stokes-layer term, the flux over a step limited to critical flow, a remaining film of 0.04 mm,
  drains as orifices (Cd 0.62); liquid leaving a chart (open edge, upside down) becomes ballistic **drops** that land
  on the next chart or the floor; **effective gravity** per cell = g minus the carrier's acceleration (from three places
  of its matrix), turned into the chart's frame. Exact bookkeeping: poured = on surfaces + in flight + drained + floor
  (to 1e-15 in the prototype).
- **Measured (4-core web machine, prototype, one core):** ~180 ns per cell and sub-step, 8–15 sub-steps a frame;
  scene S 30,000 cells → 77 ms a frame; the test mills 55–103 ms a frame at 20,000–44,000 cells.
- **Too slow for big projects:** 0249's VMC ≈ 250,000 cells at Normal; a 10-minute program (14,400 frames) ≈ 2–2.5 h on
  one core. Needed ~10–20× from: (1) a chart split into **strips over helper processes** (the owner's PC has 24
  cores), (2) stepping only the **wet region** of each chart, (3) **skipping settled frames** (nothing moves, the flow
  is off: copy the frame), (4) Draft detail (4 mm, ~8× less work).
- **Cache:** 16-bit depths compressed gave 6–29 MB on 12 s programs; the 4th axis' bar charts compress poorly →
  **8-bit steps of 0.05 mm, stored only where wet**.
- Detail: Draft 4 mm cells, Normal 2 mm, Final 1 mm (small parts 1.5 mm).

## What to build

**A. The solver** (`core/liquid.py`, cleaned up from the prototype; plain NumPy, mm / s / l inside, SI at the edges as
the other `core/` modules): charts (cell size, bed heights, open edges, walls, holes), one carrier matrix per chart
per frame (the caller gives them; B reads them from Blender), sources (a point or a small area on a chart or falling
from a jet, l/min per frame), drains (place, diameter → orifice flow), drops between charts, the floor. One call steps
a range of frames and returns per frame the depths of each chart + the drops in flight + the bookkeeping.

**B. Speed** (the four items above): the wet region (+ a margin) is stepped, dry cells cost nothing; a settled frame is
copied; a big chart is cut into strips that run in **helper processes** (fixed strip edges with one-cell halos
exchanged every sub-step, or whatever the measurement says is faster). Windows: Python's multiprocessing cannot pass
`CREATE_NO_WINDOW` (CLAUDE.md section 8) – follow how the STEP reader starts its own helpers, and get the runner
reviewed by an agent that did not write it. **Results must not depend on the number of helpers** (bit for bit with
1, 2 and 4 – test it).

**C. Cache** (no Blender): write / read the frames as 8-bit 0.05 mm steps where wet, compressed; a frame read in < 2 ms
for 250,000 cells; the file keyed by what B will key it on (a fingerprint argument).

**D. Tests** (`tests/test_liquid*.py`, numbers as on 0251's page, section 4): closed pocket holds (±2 %), open slot
drains (< 15 % left after 10 s), tilt spills at atan(d/w) ± 1.5°, tray empties down the drain (95 % within 30 s), slosh
period within 0.1 s of 2L/√(gh), nothing behind a 1-cell wall (0.000 cm³), same frame = same liquid (bit for bit),
volume bookkeeping to 1e-9 l over a long run, same result with 1 / 2 / 4 helpers, a cache round trip. Let an agent
that did not write the solver write a second set from this brief and try to break it (CLAUDE.md section 2,
"Subagents").

**E. Speed test** (a test with a time box, and numbers in the report): a synthetic 250,000-cell chart (a 1200 × 500
table + a sloped tray at 2 mm) with a 3 l/min pour moving along a slot for 60 s of program then 30 s with the flow off:
ms per frame on the 4-core web machine with 1 and 4 helpers, the share of settled frames, and the **expected** time for
the VMC's 10-minute program on a 24-core PC (say plainly it is an extrapolation; the owner measures it in task B's PC
check line).

## Done when

- [ ] `core/liquid.py` (+ runner) with docstrings; the prototype's scene S and the six tests give the page's numbers
- [ ] Speed: ≥ 10× the prototype on the 250,000-cell test on the web machine with 4 helpers, or the report says
      what is left and why; settled frames ≤ 1 ms
- [ ] Deterministic across helper counts; bookkeeping exact; cache round trip
- [ ] Independent tests (an agent that did not write the code); Windows-relevant runner code reviewed independently
- [ ] Full suite + GitHub green; report filled in (numbers, the API task B uses, open points)

## Not in this task

The Blender side (task B: charts found from the machine, the cut's top, bake at Build, drawing, settings, tour set
"Coolant liquid", PC check, guide), chips in the liquid, the air blast on the liquid, the web page, EEVEE looks.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
