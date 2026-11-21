# 0251 – Study + prototype (findings only): coolant that pools in the cuts, moves with the machine and runs to the drain

**Who:** worker · **Status:** running (findings only: a prototype on its own branch, `[skip ci]`, only the
`tasks/` files go to `main`) · **Branch:** `task/0251-study-coolant-pools`
**Started by:** lead, 20 Nov 2026 (owner 23:45: "I also want coolant fluid to simulate on the machine. So when milling
collecting in the cut slots, moving around with the motions and going down in the drain." His picks 23:50 in the
answer box below.) · **Model:** Opus · effort High
**Area:** Machining lane – read `core/coolant.py`, `blender/coolant.py` (0042: jets, drops, splash, wet sheen, every
frame from the frame number), `blender/machining.py` / `core/machining*` (the cut mesh and its pockets / slots),
`core/chips.py` (how chips land and pile – the nearest thing to what is wanted), `blender/animation.py` (the joints'
motion per frame). Prototype code only on the branch; nothing merged to the app.

## Owner's picks (20 Nov 23:50)

- **Study + prototype first**, a page with pictures / short videos so he can pick.
- **Path of the liquid:** fills the cut pockets and slots → spills over onto the table → runs along the T-slots and off
  the table's ends → **chip tray / way-cover troughs → down a drain hole**.
- **Shown in:** Cycles and EEVEE renders **and** the 3D view while playing (the web 3D page later).
- **Machine:** the new larger VMC (0249, which gets a chip tray and a drain). The study can use today's test mill and
  a plain stand-in tray; the build task comes after 0249.

- **Tested on 3, 4 and 5 axis + stand-alone fluid tests** (owner 23:48): every method is tried on (1) the 3-axis
  test mill (pockets and slots filling, the table moving in X / Y), (2) the 4th-axis mill (liquid on the turning bar
  and the rotary table – it runs off as the bar turns), (3) the 5-axis trunnion (the cradle tilts: pools spill and
  run to the low side), and (4) **stand-alone fluid tests without a machine** – small invented test models of their
  own, each proving one thing with a number: a closed pocket fills to a known volume and holds it; an open slot drains
  out at its end; a plate tilted 0 → 30° spills at the right angle; a tray with a slope empties down its drain in a
  measured time; a box moved and stopped hard sloshes and settles; nothing leaks through a wall. Propose these as tour
  stops and automatic tests for the build task (a new learning / test set "Coolant liquid").

## Questions to answer

1. **Method.** Compare at least:
   a. a **shallow-liquid height field** on the wet surfaces (part, table, tray): a grid baked at Build (water depth +
      flow per cell, gravity + the table's acceleration from the joints' motion, fill from the jets' flow rate, run-off
      at edges / into T-slots / to the drain), drawn as a thin mesh with a liquid material;
   b. **particles baked at Build** (SPH / position-based: a few thousand drops that pool), drawn as a meshed surface or
      metaballs;
   c. **Blender's own liquid simulation** (Mantaflow FLIP) on a small domain round the table;
   d. anything better found (web search works: real-time fluid in games, machining-sim products – public sources, no
      maker's code).
   For each: how it looks (pictures + a 5–10 s video of a pocket filling, the table moving in X and the liquid
   sloshing, run-off to the drain), Build time, per-frame cost in the 3D view, render cost (Cycles / EEVEE), memory /
   cache size on disk, whether it gives the same picture for the same frame whatever was shown before (0042's rule),
   and how it behaves on the demo-sized projects.
2. **Pockets and slots.** How the liquid finds the cut's low spots: from the cut mesh (`machining`) or a height map of
   the workpiece's top; open slots that run out at the part's edge drain, closed pockets hold.
3. **Moving with the machine.** The table / part move (X / Y joints, 4th / 5th axis tilt): the liquid follows the part,
   lags with acceleration (sloshes), spills when tilted. What the head's motion does (nothing, except the jets).
4. **Amount.** Flow rate from today's coolant settings (flood / mist / off, `gcode_coolant` spans), chips in the
   liquid (do they float / settle?), M9 → the pools drain slowly, the film dries (0042's wet sheen).
5. **The drain.** What 0249's VMC needs: tray shape, slope, trough along the way covers, the drain hole's place and
   size – written as a short list **for 0249's maker** (the lead adds it to 0249 / 0250).
6. **Settings the user sees.** As few as possible (owner's aim: simple): probably one "Liquid on the machine" tick box
   in 4 Motion > CNC machine > Coolant, a Detail choice tied to Draft / Normal / Final.

## Page and report

`tasks/0251_page/index.html` (published by the lead): the methods side by side with pictures and the short videos
(test models only – never the Fresing 400 or the demo's equipment), one row per test (3 / 4 / 5 axis, each stand-alone test), the numbers table, the lead-recommended method
first. The report: the recommendation, the build task(s) split by lane with sizes, what 0249 needs for the drain, open
points, the branch (kept for the build task's prototype code or deleted).

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 20–21 Nov 2026. Prototype on branch `task/0251-study-coolant-pools`
(commits `[skip ci]`, never merged, no version change): `tools/proto_0251/` – `liquid.py` (the solver, no Blender),
`standalone.py` (the six stand-alone tests), `scene_s.py` + `render_s.py` (the comparison scene), `pbf.py` +
`render_pbf.py` (particles), `flip_s.py` (Blender's liquid), `machine.py` (the 3-/4-/5-axis test mills with the app),
`bl.py` (meshes, material, studio, render), `render_standalone.py`, `make_page.py`, `run_*.sh` (the render queue).
Page `tasks/0251_page/index.html` (its own `img/` with the videos; `numbers.json` = every number below).
All measured on the 4-core web machine without a graphics card (Blender 5.2.3, Cycles/EEVEE on the processor).

**Recommendation: method a, a shallow-liquid height field** (+ drops between surfaces, + the app's own jets of 0042).

1. **Method.**
   - **a · Height field** (`liquid.py`): per surface a grid ("chart") in the carrier's own frame – bed height + liquid
     depth per cell; signed fluxes on the cell faces (virtual-pipe / shallow-water: waves at √(gh)), laminar wall
     friction 3ν/h² + a Stokes-layer term (films run off at the Nusselt rate, a slosh settles like water, ~3 % per
     swing), the flux over a step limited to critical flow (else rings of waves at every rim), a film of 0.04 mm stays
     (it dries with 0042's wet sheen), drains as orifices (Cd 0.62). Liquid that leaves a chart (open edge, upside
     down) becomes drops (ballistic) that land on the next chart or the floor. Exact volume bookkeeping (poured = on
     surfaces + in flight + drained + floor to 1e-15).
     Comparison scene S (block with pocket + open slot on a moving plate, tray + drain, 8 s): **bake 14.9 s
     (77 ms a frame, 30,000 cells)**, **7.3 ms a frame** to put the liquid in place (3D view), Cycles 6.4 s a frame
     at 640 × 360 / 24 samples, cache 6.3 MB (16-bit depths, compressed). ~180 ns per cell and sub-step (NumPy, one
     core); 8–15 sub-steps a frame (stability: deeper pools need more).
   - **b · Particles** (`pbf.py`, position-based fluids, 2 mm particles, meshed by Geometry Nodes Points to Volume →
     Volume to Mesh): 0.64 s a frame alone at 7,500 particles (505 s for scene S with other jobs running), cache
     16.7 MB, ~140 ms a frame to mesh in the 3D view. Thin films and run-off break into beads (a film thinner than a
     particle cannot exist), pockets 8 deep are 4 particles, particles fall through thin parts unless the step is
     small. Good for splash, wrong for pools/films.
   - **c · Blender's liquid (Mantaflow FLIP)**: crashes in Blender-as-a-module (`Manta::Error: can't clean grid
     cache`) – runs only in the real Blender. Scene S at resolution 64: ~45 s a frame; at 96 (effector meshes
     decimated): see the page (≈ 40 s a frame here) → ≈ 2 h for 8 s. Voxels of 5 mm: an 8 mm pocket is 1–2 cells, no
     films, no run-off along slots. Any change = bake again from the start. Not usable for a whole program.
   - **d · Searched:** games and films do big water exactly as a): a height field for the bulk + particles for what it
     cannot show (Chentanez & Müller 2010; Müller GDC 2008). Machining software (VERICUT, NCSIMUL) shows no coolant
     liquid; coolant flow is engineering CFD (Simcenter FLOEFD, Particleworks): hours per second. Nothing better found.
   - **Same frame = same picture:** a) yes – baked once at Build, frame f read from the bake; two bakes bit for bit
     identical (test 7). b) yes once baked. c) yes once baked.
2. **Pockets and slots:** from the **cut part's top by rays** in the carrier's frame, read again every 4 frames during
   Build's pass (3-axis: 3.0 s of rays for 289 frames; 4-axis 6.9 s; 5-axis 0.7 s). For Fast 3-axis the app's own
   height map (`core/heightmap.py`) can be used directly. Closed pockets hold (test 1: 12.86 of 12.8 cm³), open slots
   drain at their end (test 2: half gone in 0.33 s, ~8 % stays as a 0.5 mm layer). **Limit:** a height map sees only
   the top: a T-slot's undercut (the wide part under the 14 mm opening) does not count – the slot holds less than it
   really does; a per-cell "extra volume" can fix it later.
3. **Moving with the machine:** every chart rides with its carrier; each frame the **effective gravity** of every cell
   (g minus its acceleration, from three places of the carrier's matrix) is turned into the chart's frame: the normal
   part presses the liquid down, the tangential part drives it. Covers table X/Y starts and stops (slosh: period
   1.25 s vs 1.28 s by formula, test 5), tilts (spill at 14.9° vs 14.0° by geometry, test 3), the 4th axis turning the
   bar (four charts round the bar; upside-down liquid drips off), the trunnion tilting and C turning (flung outwards).
   The head's motion does nothing except move the jets (they pour at the tool's tip while the flood is on).
4. **Amount:** today's coolant has no flow rate (`flow` 0.1–1 only shapes the jets). Proposal: show "about N l/min"
   (flow 1 = 20 l/min, a VMC flood pump) and use it for the liquid; the prototype used 2–3 l/min so the small test
   models do not drown. Flood on/off from 0042's spans (M8/M9/step setting); mist adds no liquid. After M9: open slots
   and the table run off in seconds, the tray drains in ~20 s (test 4: 95 % in 22 s after the pour), closed pockets
   **stay full** (as on a real machine until the air blast or a person empties them), the 0.04 mm film is the wet
   sheen that dries in `dry_time`. **Chips in the liquid: not prototyped** – proposal: chips sink (aluminium 2.7,
   steel 7.8 g/cm³) and stay put unless the flow there is fast (> ~0.1 m/s: carried towards the drain, collected in the
   tray); a later step.
5. **The drain – a list for 0249's maker** (the VMC, table ~1200 × 500, travel X 1000):
   - `CHIP TRAY`: one solid under the whole travel of the table plus the table (about 2300 × 1100), floor sloped
     **2°** (at least 1.5°) towards the drain as two planes meeting in a valley (a "V" to the drain), walls ≥ 60 mm;
     its floor a clean flat solid of its own (not fused with the bed: the height map reads the top face).
   - **Troughs** along the X way covers, front and back: 60–80 wide, 30 deep, sloped 1–2° towards the tray's low end,
     ending open over the tray (liquid falls into it); the covers' tops shed to the troughs (slight outward slope).
   - `COOLANT DRAIN`: a separate part, a hole **Ø 50** at the tray's lowest point, front right (Ø 50 takes ~30 l/min at
     10 mm of liquid; Ø 40 ~20 l/min) + a short pipe down to a `COOLANT TANK` box under the bed.
   - **Table:** T-slots along X (the long side), opening **18 mm** (the BT40 class), 3–5 slots, **open at both ends**
     (no end plates or chip guards that close them), so the liquid runs along them and off the table's ends.
   - Every surface the liquid can meet is its own solid with a flat or plainly curved top; no gaps under ~3 mm between
     tray and walls (the grid cell at Normal is 2–3 mm).
6. **Settings the user sees:** one tick **"Liquid on the machine"** in 4 Motion > CNC machine > Coolant (off by
   default, only when coolant is on); **Detail** follows the project's quality (Draft 4 mm cells, Normal 2 mm, Final
   1 mm; small parts 1.5 mm); flow = today's Flow slider labelled in l/min. Surfaces and drain found automatically:
   the parts that ride with the workpiece and the still parts under it (as chips' `_catch` does), the cut workpiece,
   the part named `COOLANT DRAIN` (else the lowest point of the tray). Nothing else.

**On the test mills** (method a with the app's Build, cut, jets and splash; numbers from the runs on the page):

| Machine (12 s program, 289 frames, flood 3 l/min) | Build | Pass through the frames (of it: the cut's top by rays) | Liquid bake | Cells | Cache | Liquid in place / frame | Cycles 480 × 270, 16 samples |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3-axis test mill: pocket 50 × 60 × 10 + an open slot, table rapids ±70 mm in Y | 2.3 s | 7.1 s (2.8 s) | **29.8 s** (103 ms a frame) | 44,000 | 13.4 MB | **9.0 ms** | 5.3 s a frame |
| 4th axis: the test program (wrapped slot, two flats), flood all the time | 11.1 s | 21.1 s (6.3 s) | **21.0 s** (73 ms) | 22,000 (4 charts round the bar + tray) | 28.9 MB | **7.9 ms** | 5.5 s |
| 5-axis trunnion: two 3+2 pockets at A30, a groove while C turns | 3.0 s | 5.2 s (0.7 s) | **15.9 s** (55 ms) | 19,869 (table C, cradle, tray) | 6.5 MB | **6.0 ms** | 5.4 s |

Liquid kept: 3-axis 518 of 529 cm³ on the surfaces at the end, 10.7 cm³ (2 %) thrown past the bed by the rapids; 4-axis
11 cm³ down the drain, 3 cm³ past the tray; 5-axis 4.4 cm³ past the tray. The 4th axis' cache is the biggest (its bar
charts change every frame and compress poorly): store depths as 8-bit steps of 0.05 mm where wet only in the build.

**In Cycles, EEVEE and the 3D view:** the liquid is an ordinary mesh with the coolant's milky colour, so it renders in
Cycles, EEVEE, the 3D view and the render queue. Cycles: fine. EEVEE (software drawing here, 64 s a frame!): the
see-through (refractive) liquid is grainy at 32 samples; drawn "blended" without refraction it is smooth but reads as
white paint – EEVEE needs its own liquid settings, tuned on the owner's RTX 3090 (open point). The 3D view (solid /
Workbench) shows the liquid as a light grey sheet.

**Demo-sized projects – the cost (open point, the build task's main risk):** the bake costs ~180 ns per cell and
sub-step (NumPy, one core): 125,000 cells with 2 mm of liquid = 0.32 s a frame. 0249's VMC (table 1200 × 500 at 2 mm +
a tray at 5 mm ≈ 250,000 cells) with a 10-minute program (14,400 frames) ≈ **2–2.5 h at Normal** – too slow. The
build task must get ~10–20× by: (1) splitting a chart into strips over helper processes (the owner's PC has 24 cores;
the importer already does this), (2) stepping only the wet part of each chart, (3) skipping frames where nothing moves
and the flow is off (the liquid is settled: copy the frame), (4) Draft detail (4 mm: ~8× less work), and bake in the
background with progress + Cancel like the cable re-bake (0160). Goal for the build: that 10-minute VMC program in
under 10 minutes on the owner's PC at Normal.

**Proposed build tasks (Machining lane, after 0249):**
- **A · Liquid core** (`core/liquid.py` + tests): the solver of `liquid.py` cleaned up, the six stand-alone tests as
  pytest (numbers as on the page), the strips over processes + wet-region + still-frame skipping, a speed test on a
  250,000-cell chart. **Opus · High**, 1 session.
- **B · Liquid on the machine** (`blender/liquid.py`, after A and 0249): the charts found from the machine (riding /
  still / carrier as chips do; the bar's four charts on a 4th axis; the cradle on a trunnion), the cut's top from
  `heightmap.py` or rays, the bake at Build after milling + coolant, the cache file next to the project (keyed on the
  Build), drawing (grid meshes + drops, frame handler; the EEVEE material), the tick + Detail + l/min, PC-check line
  (+ Heavy line: the VMC program), tour set **"Coolant liquid"** (stops: the six stand-alone tests + 3-, 4-, 5-axis),
  guide. **Opus · High**, 1–2 sessions (split B1 3-axis + tray + settings, B2 4th/5th axis + tour set if long).
- Later (owner decides): chips carried by the liquid; the air blast (0039) pushes liquid out of pockets; the web 3D
  page (a baked liquid is a big animation for the web).

**Automatic tests and tour stops proposed** (set "Coolant liquid", each with its number): closed pocket holds
(±2 %), open slot drains (< 15 % left after 10 s), tilt spills at atan(d/w) ± 1.5°, tray empties down the drain
(95 % within 30 s), slosh period within 0.1 s of 2L/√(gh), nothing behind a 1-cell wall (0.000 cm³), same frame =
same liquid (bit for bit). Results today: all pass (page section 4).

**Subagents:** one read-only Explore agent mapped the coolant, machining, chips and rotary code (no code written by
it). No independent review: findings only, no app code.

**Open points:** speed for long programs (above); EEVEE look; T-slot undercuts; chips in the liquid; liquid on the
tool / spindle (none: the head stays dry); a fast table rapid in the prototype throws ~2 % past the tray (drops leave
with the table's speed); the tray in the 3-axis run is the bed's flat top as a stand-in (liquid can sit "under" the
table there – hidden).

**Branch:** keep `task/0251-study-coolant-pools` for build task A (its `liquid.py` and tests are the starting point);
delete it after B is merged.
