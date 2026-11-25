# 0346 – Coolant liquid B1: liquid on the 3-axis machine, the tray and the drain

**Who:** worker · **Status:** running · **Branch:** `task/0346-coolant-liquid-b1`
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

- [ ] Liquid fills pockets / slots, spills, runs along the T-slots, off the table into the tray and down the drain on the VMC
- [ ] Cycles, EEVEE (2–3 choices for the owner), 3D view and the render queue show it; same frame = same liquid
- [ ] Bake in the background with progress + Cancel; cache reused on an unchanged Build
- [ ] Speed measured: web machine numbers + the expected time on the owner's PC for the 10-minute VMC program
- [ ] Tests added; 0255's tests green; full suite passes; GitHub run green
- [ ] PC-check lines, tour stop, guide, function list, tooltips, CHANGELOG
- [ ] Before/after pictures (3–4 frames of the VMC program) in `tasks/0346_page/` for the owner
- [ ] Report below filled in (incl. "what B2 needs"), merged, released; the owner's check line ("PC check > Heavy – the
      liquid line"; the EEVEE choices to look at)

---

## Report (filled in by the chat that did the task)
