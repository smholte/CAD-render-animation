# 0346 – Coolant liquid B1: liquid on the 3-axis machine, the tray and the drain

**Who:** worker · **Status:** done (26 Nov 2026, 0.2.263) · **Branch:** `task/0346-coolant-liquid-b1`
**Started by:** lead, 25 Nov 2026 (Machining lane: 0251 study → 0255 core A → 0257 → **B1** → B2 = 0347) ·
**Model:** Opus · effort High · Claude Code on the web, environment "CAD-render-animation"
**Area:** Machining lane – new `blender/liquid.py` (+ `ops_liquid.py` / `ui_liquid.py` if you need them, or additions to
`ui_coolant.py` / `ops_coolant.py`), small additions to `blender/coolant.py` (the bake after coolant at Build),
`core/liquid*.py` only where the machine needs it, `core/functions.py` (additive), tests, user guide, CHANGELOG.
`pccheck/checks.py`: **add your lines only, at the end of their group** – 0333 is changing that file now; merge `main`
first before you release.
**Not:** `blender/handlers.py`, `joints.py`, `logic.py`, `vessel_motion.py` (0326 running) – register your own frame
handler in `liquid.py` as `coolant.py` / `measure.py` do; `core/clash.py`, `blender/clash.py` (0327); the 4th axis, the
trunnion and the tour set (these belong to B2 = 0347); chips carried by the liquid and the air blast (later, owner decides).

## Design (worker, 25 Nov 2026 – committed before the code; the record if the session has to be continued)

**Files.** `blender/liquid.py` (set-up, bake, cache, drawing, frame handler), `blender/ops_liquid.py` (Work out the
liquid: modal job with progress + Cancel as `fresing.rebake`; Cancel), additions to `ui_coolant.py` (a "Liquid on the
machine" part of the Coolant panel), `props.py` (three settings on `FRCoolant`, additive), `machining.py` (`prepare`
also prepares the liquid for the render queue; `update_if_needed` asks for the bake after the motion was read),
`__init__.py` (register). `core/liquid*.py` untouched unless a measurement asks for it.

**Charts (3-axis).** Two charts, like the prototype:
1. **"table" – riding** with the workpiece's mover (riding space = the world at the motion's first frame, as chips):
   one height field over every riding part (table with its T-slots, clamps, bolts, the X motor) **and the cut block**:
   rays straight down. Cells where nothing is hit = no surface (open edge: the liquid leaves as drops). Cell: Normal
   2 mm, Draft 4 mm. Matrices per frame = `fr_wp_m[f] @ inv(fr_wp_m[0])` (read by `machining.sample`).
2. **"tray" – still**: rays down onto the parts that stand still (chip tray, bed, rails, drain, tank); walls are high
   cells (closed edges). The `COOLANT DRAIN` part: the cells within its hole's radius get the tray floor's height round
   the hole and a drain (orifice area = cell²). Cell: Normal 5 mm, Draft 10 mm.
   Moving way covers and the saddle are no charts (drops pass them; they land on the bed / in the tray under them).
**The cut block's top**: the base bed is made without the block; at the start and whenever cutting moves ran since the
last read (every `CUT_EVERY` frames at most), the milling timeline's mesh at that moment is read (`mesh_at`), only the
cells the tools swept since the last read (+ a margin) are cast again, `Liquid.set_bed` takes the new bed. Each change
is kept (the changed cells) in a sidecar so the drawing knows the bed at any frame.

**Inputs per frame.** Pours while flood flows (coolant spans of kind flood, `fr_spans`): `flow x 20 l/min` (0.1 … 1 →
2 … 20 l/min; shown in l/min), poured at the tool's tip from as many points round it as hoses (radius + 2 mm). The
tool: tip / axis from the bits' paths (riding space → world by the matrices), radius / flute from the cut items, rpm
from the coolant's `fr_rpm`. Mist adds no liquid.

**Bake.** A generator (`liquid.steps`) yields progress 0 … 1: gather (rays) → `core.liquid.Liquid` with
`liquid_pool.default_helpers()` → frame by frame, `liquid_cache.Writer` → closed file. The modal operator steps it in
0.15 s slices (UI stays live, Esc / Cancel stops it, the half file is thrown away); background (queue, tests, PC
check): run to the end. **Fingerprint** (sha1): LIQUID_VERSION, the milling path signature, the stock / cut items, the
coolant spans / rpm / tools, the liquid settings, fps, frame range, the charts' parts and places. Cache:
`<project folder>/<project name>_liquid/<scene>.frliquid` (+ `.beds.npz`), unsaved projects in the temp folder. Same
fingerprint = the file is read, no bake. The bake starts by itself in the window after Build once the motion is read
(not again after a Cancel until something changes or the user presses Work out the liquid).

**Drawing.** One mesh object per chart in a collection "FR Coolant liquid": a sheet over the wet cells (depth > 0.1
mm), corners at the mean surface height of the wet cells round them; drops as points instanced as spheres (the
coolant's drops node group). The riding sheet follows the workpiece by a Copy Transforms constraint (vertices written in
the workpiece's own space), the tray sheet stands still. Frame handler of its own (pre + post as coolant), also in
renders and the queue; a frame is read from the cache only → same frame = same liquid. Material "FR coolant liquid":
two outputs – Cycles (the coolant's milky emulsion / oil look) and EEVEE (setting **EEVEE look**: A *Clear* =
ray-traced refraction, B *Milky* = no refraction, soft milky with a clear coat, C *Blended* = see-through blended);
Solid view: light grey (`diffuse_color`).

**Settings** (`FRCoolant`): `liquid_on` (off), `liquid_detail` DRAFT / NORMAL, `liquid_eevee` CLEAR / MILKY /
BLENDED. The flow is 0042's Flow slider, shown as "about N l/min".

**Tests** (`tests/test_coolant_liquid.py`, real VMC `test_mill.step`): pocket fills and holds (±2 % of the poured
volume against a closed pocket), liquid leaves the table at its ends and reaches the tray, the tray empties down the
drain (95 % within 30 s), same frame = same liquid (bit for bit, frame read twice in different orders), tick off = no
objects and the build the same; cache reused (no bake the second time). An old project: opened, built, the same.
**PC check**: Full `milling.liquid` (small program), Heavy `heavy.liquid` (the VMC program's bake time, frames, cells).
**Tour**: a stop on the coolant set (3-axis VMC). **Subagents**: an independent tester (worktree) writes
`tests/test_coolant_liquid_independent.py` from this brief after the code is in.

## Goal

On the VMC of 0249, coolant from the 0042 / 0257 jets **fills the cut pockets and slots, spills onto the table, runs
along the T-slots and off the table's ends into the chip tray, and goes down the drain**. It looks right in Cycles,
EEVEE, the 3D view and the render queue, it is the same every time a frame is shown, and the bake is fast enough for a
real program.

## Background (read these first – only the parts named)

- `tasks/0251-study-coolant-pools-drains.md`: "Owner's picks" and the report's proposed build task **B**, the cost
  paragraph ("Demo-sized projects – the cost") and the open points. The prototype `liquid.py` on branch
  `task/0251-study-coolant-pools` shows how the charts ride the machine.
- `tasks/0255-liquid-core.md`: the "Open points" (8.4 × with 3 helpers on the web machine; float32 fluxes, smaller
  margin, local sub-steps as ideas). `core/liquid.py`, `liquid_pool.py`, `liquid_cache.py` are ready and nothing
  imports them yet.
- `tasks/0257-coolant-at-the-spinning-tool.md`: the splash and film at the tool (drops pass through walls).
- `tasks/0249-larger-test-mill.md`: the VMC with chip tray, Ø50 drain and tank.

## What to do

1. **Charts from the machine** (3-axis): the cut part's top from `core/heightmap.py` (or rays where there is no height
   map), the table with its T-slots, the chip tray / way-cover troughs with the drain. Riding / still / carrier as chips
   do (`chips.py`), so the table's X / Y moves carry the liquid.
2. **The bake at Build**, after milling and coolant (same Build order as chips / coolant): in the background with progress
   and Cancel like the cable re-bake (0160); cache file next to the project, keyed on the Build (8-bit 0.05 mm where
   wet, `liquid_cache.py`); a changed program or model gives a new bake, an unchanged one reuses the cache.
3. **Speed – the main risk.** Goal from the study: **the VMC's 10-minute program in under 10 minutes at Normal on the
   owner's PC** (24 cores). Use the helpers over strips, wet-region-only stepping, skip settled frames with no flow,
   Draft detail (4 mm). Measure on the web machine and say what the owner's PC should give; if the goal is out of reach,
   stop at findings and ask the lead before cutting quality.
4. **Drawing:** grid meshes + drops, own frame handler; the coolant's milky colour; **an EEVEE material of its own** (the
   study found the see-through look grainy at 32 samples and "blended" reads as white paint) – make 2–3 EEVEE choices
   and give the owner a line to judge them on his RTX 3090; Solid view: a light grey sheet.
5. **Settings** in the Coolant panel: one tick "Liquid on the machine" (off by default; old projects stay off – say in
   the report whether new projects with coolant should have it on, the owner decides), Detail (Draft / Normal), the flow
   in l/min (from 0042's flow). Every button gets a tooltip.
6. **Tests:** the six stand-alone tests of 0255 stay green; add machine tests: a pocket on the 3-axis test block fills
   and holds (±2 %), liquid leaves the table at its ends and reaches the tray, the tray empties down the drain (95 %
   within 30 s), same frame = same liquid (bit for bit), an old project (0.2.240 or newer) opens and builds the same with
   the tick off.
7. **PC check:** a Full line (small program) and a **Heavy line: the VMC program's bake time** with its frames and cells.
8. **Guide:** user guide section + picture; function list entry with `since=`; a tour stop on the 3-axis VMC (the
   other stops come with B2). CHANGELOG in plain words.

## Done when

- [x] Liquid fills pockets / slots, spills, runs along the T-slots, off the table into the tray and down the drain on the VMC
- [x] Cycles, EEVEE (2–3 choices for the owner), 3D view and the render queue show it; same frame = same liquid
- [x] Bake in the background with progress + Cancel; cache reused on an unchanged Build
- [x] Speed measured: web machine numbers + the expected time on the owner's PC for the 10-minute VMC program
- [x] Tests added; 0255's tests green; full suite passes; GitHub run green
- [x] PC-check lines, tour stop, guide, function list, tooltips, CHANGELOG
- [x] Before/after pictures (3–4 frames of the VMC program) in `tasks/0346_page/` for the owner
- [x] Report below filled in (incl. "what B2 needs"), merged, released; the owner's check line ("PC check > Heavy – the
      liquid line"; the EEVEE choices to look at)

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 25–26 Nov 2026 · version 0.2.263. Page for the owner:
`tasks/0346_page/index.html` (before / after, 4 frames, two views, Cycles; test models only).

**What changed:**
- `blender/liquid.py` (new): the two charts from the machine by rays – "table" riding with the workpiece's mover
  (table + T-slots, clamps, bolts, motor, and the cut block; parts inside the block such as a finished-part reference
  are no surface) and "tray" of the still parts (the parts named …TRAY / …DRAIN whole; the `COOLANT DRAIN`'s hole
  = orifice cells 2 mm below the floor round it). The block's top is read from the milling timeline (`mesh_at`) every
  4 frames while cutting moves ran, only where the tools went (`_Cut`), changes kept in a sidecar (`Beds`). Pours:
  Flow × 20 l/min (0.7 = 14 l/min) from one jet per hose just outside the tool while flood flows; the spinning tool
  from the bits' paths + the coolant's rpm. The bake (`steps`, a generator) runs as a modal job with progress + Cancel
  (`ops_liquid.py`), in the background at once (`bake_now`; the render queue via `machining.prepare`); everything is
  read at the motion's first frame. Cache `<project>_liquid/<scene>.frliquid` (+ `.beds.npz`), keyed by a fingerprint
  (motion signature, block, tools, coolant spans / rpm, settings, frames, the parts and their places on their movers);
  unsaved projects in the temp folder, moved next to the project when it is saved. Drawing: one sheet per chart
  (wet cells > 0.1 mm, corners at the mean top round them), drops as the coolant's spheres, own `frame_change_pre`
  handler, the table's sheet follows the block (Copy Transforms). Material "FR coolant liquid": Cycles output (the
  coolant's emulsion / oil look) + EEVEE output (**EEVEE look** Clear = ray-traced refraction, Milky = no refraction,
  subsurface + clear coat, Blended = alpha 0.72 blended), light grey in Solid view.
- Settings (`props.py`, `FRCoolant`, additive): `liquid_on` (off), `liquid_detail` Draft 4 / 10 mm, Normal 2 / 5 mm,
  `liquid_eevee`. Coolant panel: tick + "about N l/min", Detail, EEVEE look, state line with Work out / Cancel.
- `core/liquid.py` (two additions, both needed on the machine): **`wave_depth`** (a face's depth counts at most
  10 mm for the flow: waves in T-slots and deep pockets no faster than √(g·10 mm), half the sub-steps; levels and
  volumes unchanged; None = as before for 0255's tests) and a **crest rule** (the flow out of a cell over a step up is
  limited by the head over the higher bed, measured along the driving gravity – a full pocket stopped spilling only
  well below its rim by momentum).
- **Test model:** `tools/make_test_mill.py` – the chip tray's left half fell *away* from the drain (sign of the V) and
  its front left corner had a hole (the floor below the solid's bottom): fixed, `test_mill.step` made again (only CHIP
  TRAY changed, checked part by part). The 4th / 5th-axis, ATC, cabinet, toolpath and way-cover models still have the
  old tray (not made again here: B2 makes the 4th / 5th-axis ones).
- PC check: Full `milling.liquid`, Heavy `heavy.liquid`; tour set + stop "liquid" (in `MILLING_SETS`); function
  `cnc.liquid`; guide section "Coolant liquid on the machine" + picture; `liquid.set_up_test_model` shared by tests, PC
  check and tour; CLAUDE.md section 3.

**Tested and measured** (4-core web machine, Intel Xeon 2.1 GHz):
- `tests/test_coolant_liquid.py` (10) and `tests/test_coolant_liquid_independent.py` (14, the independent tester's):
  pocket fills (spills during the flood) and holds from 1 s after M9 to the end (±2 %; it keeps ~86 % of its 36 cm³:
  the heap over the rim runs off and the pocket sloshes when the flood stops), liquid in the tray beyond the table's
  ends and down the drain, bookkeeping exact, the VMC's tray empties 97 % of a 20 s flood (14 l/min off both table
  ends) within 30 s after it stops (test: ≥ 95 %), same frame = same liquid bit for bit, helpers 2 = helpers 0 bit for
  bit, the bake is the same whatever frame is shown, cache reused (also after forget / reopen), Detail / Flow /
  program change the fingerprint, tick off = nothing made and the same Build, an old project (0.2.195) opens with the
  tick off and builds without liquid (there is no 0.2.240 project in tests/data), EEVEE looks, Beds round trip.
- 0255's tests: all green after the core changes (`test_liquid.py` 21, pool, cache, independent, speed). T3 (tilt):
  left at 30° now 3.75 cm³ vs geometry 3.46 (+8 %, was −2 %), spill angle still within 1.5°.
- Tour: stop "liquid" passes (`test_tour.py -k liquid`, 4.3 min with its build), its set 0 clashes.
- PC check `milling.liquid` locally: OK in 37 s (bake 16.2 s with 3 helpers, 63,626 cells, 36.6 ms a frame shown).
- **Speed** (the 16 s test program, 385 frames, the whole table wet):

| | table + tray cells | ms a frame, 1 process | ms a frame, 3 helpers |
| --- | --- | --- | --- |
| Normal, before the wave cap | 151,856 + 102,014 | 270 | – |
| Normal | 151,856 + 102,014 | 181 | 129–137 |
| Draft | 38,108 + 25,518 | ~40 | 42 (helpers do not pay at Draft here) |

  Sub-steps a frame 21.8 → 11.7 with the wave cap; ~185,000 cells stepped a frame (the liquid keeps moving while the
  table moves: no frame settles). Cache: Normal 38 MB, Draft 12 MB for 16 s.
- **The 10-minute VMC program at Normal** (PC check Heavy `heavy.liquid`, full size, run here: six pockets in three
  depths + slots, fitted to 600 s = **14,401 frames, 253,845 cells**, flood all the time): build + motion read 68 s,
  **liquid bake 3,107 s = 51.8 min with 3 helpers** (216 ms a frame; for some minutes other test runs shared the
  machine), 0.6 % of the frames at rest (the table moves all the time), peak memory 648 MB, **bake on disk 2,684 MB**.
  **Expected on the owner's PC (24 cores, an extrapolation, not a measurement):** this machine gives ~290 ms a frame on
  one process for this program; a desktop core of today is ~1.5–2 × faster (→ 35–45 min on one core), and the 23
  helpers share it – here 3 helpers gave only 1.3–1.4 × (4 shared cores, memory-bound), the 0255 estimate for 24
  cores is 4–6 × → **about 6–11 min**: the 10-minute goal is within reach but not proven. The owner's PC check Heavy
  line measures it. Draft is ~4 × quicker (16 s program: 16 s vs 50 s).
- **Cache size is the bigger problem:** 2.7 GB next to the project for a 10-minute program at Normal (~190 KB a frame:
  the whole table is wet and moving, ~1 byte per wet cell; drops 30–40 %). Changing frame to frame, so deltas do not
  help (measured: 90 % of the wet cells change every frame). Not cut here (the brief: ask before cutting quality).
  Choices for the lead / owner: store every 2nd frame and blend between (½), drops as 16-bit (−15 %), a coarser stored
  grid on the table at Normal (¼), or keep it and say so in the panel.

**GitHub runs:** 2 full runs on the branch – the first (before the version raise) all green except two version
bookkeeping checks (the new line's `since` ahead of the branch, the tour-version record), Windows install A with the
PC check Full (`milling.liquid` with helper processes on Windows) green; the second after merging `main` (0.2.261)
and raising to 0.2.263 (another task took 0.2.262 meanwhile: merged again, renumbered): green, run 45725343042 (49.9 min on runners shared with other tasks). Then the report push and the fast-forward of `main`.

**Subagents:** one independent tester (Sonnet, worktree) wrote `tests/test_coolant_liquid_independent.py` (14 tests)
from the brief and the code's functions. It found two real faults, both fixed by me and its tests kept as they are:
(1) the bake depended on the frame shown when it started (the machine was read at the current frame – up to 0.7 mm
in 994 cells; now read at the motion's first frame), (2) the cache's stored place went stale after the first save
(moved after the file was written; now moved in `save_pre`, and kept current when a bake is found). It also noted that
switching coolant off and on drops the coolant's Build data (0042's behaviour: the liquid then asks for Build & play).
I found myself: the test mill's tray fault, a finished-part reference read as the table's surface, a stale fingerprint
memo after hiding a part (test added). No independent review of Windows code: no Windows-only code was added (the
helper processes are 0255's, reviewed then; they ran on GitHub's Windows in the PC check).

**What B2 (0347) needs:**
- 4th axis: charts round the bar from `rotary` (the prototype's four charts, `tools/proto_0251/machine.py` on branch
  `task/0251-study-coolant-pools`), riding on the A-axis carrier (`chips.carrier`), the cut read per chart by rays in
  each chart's frame (`_Cut` is for one top-down chart now); upside-down drips are in the core already.
- 5-axis: the cradle as a riding chart (the trunnion tilts it: effective gravity does the spilling), the C table.
- Make `test_4axis.step` / `test_5axis.step` (and the ATC / cabinet / toolpath / way-cover models) again with the fixed
  tray of `make_test_mill.py`; then their tour sets' `changed=`.
- The tour set "liquid" exists (one stop on the 3-axis VMC): add the six stand-alone stops and the 4 / 5-axis stops.
- The cache size decision above, before long 4-axis programs (their bar charts change every frame).
- `liquid.set_up_test_model` is the shared set-up; `CUT_EVERY` (4 frames) and the pours (one jet per hose just outside
  the tool) are constants at the top of `blender/liquid.py`.

**Open points:**
- The guide's Coolant panel picture (`docs/img/panel_4_coolant.png`) is not remade: `tools/guide_screens.py`'s panel
  modes (coolant, also air, untouched by this task) picture Blender's Item tab (Transform) on this machine with a fresh
  settings folder; the old picture stays (without the liquid rows). Lead: a small tools task.
- A pocket keeps ~86 % of its volume after the flood stops (the heap over the rim runs off and it sloshes for a few
  seconds); real liquid with surface tension would keep a little more.
- New projects with coolant: liquid off by default (as the brief); **the owner decides** whether it should be on –
  worker's advice: keep it off until the cache size is settled (2.7 GB for 10 min at Normal).
- The EEVEE looks are untested on a graphics card (EEVEE cannot run on the test machines): the owner judges them.
- Liquid in a T-slot's undercut is not seen (rays see the top only); moving way covers are no surface (drops pass
  them and land on the bed under them, hidden).

**Owner's check (on the PC, after Update now):**
1. Help > Fresing Render PC check… > **Heavy** – send the line "Milling: coolant liquid of a 10-minute program"
   (minutes, MB).
2. Help > Make test tour project, open it; in the Test tour panel go to **Machining > Coolant liquid on the machine**,
   press **Go**, then play: milky coolant fills the pocket, runs over the table into the tray.
3. 4 Motion > CNC machine > Coolant > **EEVEE look**: try Clear, Milky, Blended with an EEVEE picture
   (5 Scene & Render, engine EEVEE, Render image) and tell the lead which looks best.
