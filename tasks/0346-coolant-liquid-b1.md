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
