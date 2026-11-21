# 0255 – Coolant liquid A: the liquid core (`core/liquid.py`) – shallow-liquid height field, fast enough for a 10-minute program

**Who:** worker · **Status:** running · **Branch:** `task/0255-liquid-core`
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

## Design (worker, 21 Nov 2026 – committed before the code; the record if the session has to be continued)

**Files.** `fresing_render/core/liquid.py` (solver, no Blender, NumPy only, SI inside: m, s, m³; litres and l/min at
the edges), `fresing_render/core/liquid_pool.py` (helper processes + shared memory, started like the STEP reader's
helpers), `fresing_render/core/liquid_cache.py` (8-bit cache), `tests/test_liquid.py` (the six tests + API),
`tests/test_liquid_speed.py` (the 250,000-cell speed test), `tests/test_liquid_pool.py` (helpers, bit for bit),
`tests/test_liquid_cache.py`; the independent tester's file `tests/test_liquid_independent.py`.

**Grid.** A chart stores its cells with a ring of one "no surface" cell all round (open edges) – so every face the
solver touches lies between two stored cells. Faces: `qx` (NY, NX-1) between columns, `qy` (NY-1, NX) between rows.
**Tiles** of 64 × 64 cells; a face belongs to the tile of the cell on its +x / +y side.

**One sub-step on a window.** The kernel works on a window = a run of tiles (core) + 2 cells all round. New depths of the
core need the scaled fluxes of the core's faces, which need K (the "never more than the cell holds" factor) of the
core + 1 ring, which needs the unscaled fluxes round those cells, which need depths of core + 2. Only element-wise
operations (+ − × ÷ sqrt min max, no pow, no sums): **a cell's result is the same bit for bit whichever window or
helper computes it** – this is what makes results independent of the helper count and the wet-region skipping exact.

**Which tiles are stepped.** Per tile a state from its last computation: *dry* (no cell above the 0.04 mm film, all
fluxes 0, no wet drain), *active*, *settled* (wet, but over the last frame every depth changed < 1 µm and every speed
< 1 mm/s, no wet drain). A frame steps the active tiles + every tile next to one (8 neighbours) + tiles where drops,
pours, a push or the tool land, + every wet tile of a chart whose effective gravity changed. Others are skipped:
a dry tile would not change at all (exact); a settled tile is held at rest (its fluxes set to 0; faces between a
stepped and a skipped tile are closed for the frame) – the only approximation the skipping adds. Neighbouring stepped
tiles of one tile row are merged into one window (fewer NumPy calls).

**Effective gravity** per cell = R₁ᵀ(g − a(p)) with a(p) affine in the cell's place (second differences of the
carrier's matrices): per chart and frame a 3-vector + a 3 × 3 matrix; the fields are made per window from the cell
centres (x, y, bed). Pure translation → one number per chart.

**Sub-steps.** n = ceil(T / dt_max) rounded up to an even number (double buffers: depth and fluxes in buffer 0 at every
frame boundary, so skipped tiles are current in both buffers). dt_max = 0.45 cell / √(g_n h_max).

**Helpers** (`liquid_pool.Pool(n)`): plain-Python processes (`importer.runner.python_executable()` way; Windows:
CREATE_NO_WINDOW + below-normal priority + a kill-on-close job object; Linux: PDEATHSIG; they stop when the parent
stops), pickle messages over stdin / stdout as `step_reader`, the chart arrays in `multiprocessing.shared_memory`
(children attach with `track=False`). Per sub-step the master sends each helper its windows and waits for all (one round
trip per sub-step); the master computes a share itself. 0 helpers = everything in the master.

**Inputs per frame** (callables of the frame number): `pours(f)` → list of `Pour` (world point + direction, or a chart
cell area; l/min), `tool(f)` → `Tool` or None (tip, axis, radius, flute length, rpm signed: + = M3), `push(f)` →
{chart: (ax, ay)} m/s² along the chart's x / y (for the air blast later; a surface stress τ is a = τ / (ρ h)).
**Out per frame:** `Frame` (depths per chart as float32 copies on request, drops in flight: places, velocities,
volumes, the bookkeeping in litres: poured, on charts, in flight, drained, floor, thrown by the tool). `velocity(c)`
gives (u, v) per cell = the face fluxes / depth (for chips later).

**The spinning tool.** Ω = −rpm·2π/60 · â (â from the tip up the shank; M3 = clockwise seen from the spindle). Cells
whose centre lies within the tool's radius of its axis and whose liquid column overlaps the tool (tip − 0.5 mm …
tip + flute): a share 1 − e^(−T/τ) (τ = 0.05 s) of the liquid above the film there is thrown off each frame as one drop
per cell, from the tool's surface a little up the flutes, at v = min(ωR, 6 m/s) along (tangent + 0.25 radial + 0.1 up).
Ring R … 3R round it: a push in the turning direction, a = 0.5 · min(ωR, 6) · (R / r) / 0.2 s, tapering to 0 at 3R,
only on cells whose liquid reaches the tool's height.

**Cache** (`liquid_cache`): one file, a JSON head (fingerprint, charts, frames), per frame per chart: a packed wet
mask + uint8 depth in 0.05 mm steps (≥ 255 steps: an overflow list of uint16), zlib; the drops (float16 places,
float32 volumes); an index of offsets at the end for random access.

**Subagents.** (1) an independent tester (Sonnet, worktree) writes `tests/test_liquid_independent.py` from the brief
and the API only, and tries to break it; (2) an independent reviewer (read-only) of `liquid_pool.py` for Windows
(process start, shared memory, shutdown). The worker writes everything else.

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

**The spinning tool (owner 21 Nov 14:01: "the fluid should interact with the milling bit – when it spins fast the coolant
turns round it and is splashed away").** Also a core input now: per frame **one tool** – a cylinder (axis, tip, radius,
flute length) with its **spindle speed and direction** (M3 / M4). Liquid in cells under or inside the tool's circle is
**thrown off as drops**, tangentially at about the tool's surface speed ωr (capped – say the cap; a D10 at 10,000 rpm
is ~5 m/s) with some outward share, rising a little up the flutes; a ring of cells round it (~1–2 tool radii) gets a
**swirl push** in the turning direction, weaker further out, so a pool round the tool turns and climbs the pocket's
walls. A still spindle does nothing. Tests: a pool round a turning tool loses liquid as drops (bookkeeping still
exact), the drops leave in the turning direction at ~ωr, a pool round it rotates the right way, M4 the other way.
B hands the tool in from the CNC machine; the look of the jets and spray at the tool is task 0257.

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
