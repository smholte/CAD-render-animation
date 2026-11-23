# 0298 – Hoses and cables round 3: Avoid other parts (collision on / off) and a route you can shape between the two ends

**Who:** worker · **Status:** open – can start · **Branch:** `task/0298-hoses-avoid-and-shape`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Hoses and cables improvements. A collision active button,
for collision with other objects. And able to adjust the path it takes, between the two points.") · **Model:** Opus ·
effort High
**Area:** Flex parts lane – `core/flex.py`, `blender/flex.py`, `ops_flex.py`, `ui_flex.py`, the drawn hoses of 0240
(`drawn.py`, `ops_drawn.py`), `paths.py` only where cables need the same; `clash.HOOKS`; tests, test models
(`tools/make_test_flex.py`), tour, PC check (+ Heavy if it costs), guide, CHANGELOG.
**Not:** sea cables and spools (Sea / Flex parts work of 0081 / 0080 stays), drag-chain links (0058's chain solver) unless
the same switch fits them for free.

## Background

Hoses solve as an elastic rod under its own weight between fixed ends (0058); they pass through other parts, and flex
parts are left out of the clash check. 0240 draws hoses / cables by clicking points (fittings, clips, sheaves); its open
points: a drawn route is not re-laid when its sheaves move, clips hold the hose fixed.

## What to do

1. **Avoid other parts** – a switch on each hose / cable row (off by default): on, the solved shape stays outside the
   other parts with its own radius – it lies on them and slides along – live and at Build (scripts-off safe, as today).
   Which parts count: everything visible near it (a box search) or picked ones – choose and say. Measure the cost per
   hose per frame on the test models and on a big scene; a Heavy line if it matters.
2. **Shape the route between the two ends** – for any hose / cable, CAD-read or drawn: its middle line with handles in
   the view: drag a point, click on the line to add a via point, remove one; the solver keeps the hose through the via
   points; **Length**: automatic or a fixed number. Undo, save, model update keep it.
3. 0240's open points: a drawn route re-laid when its sheaves / parts move; clips that ride on their part.
4. A hose with Avoid on can join the clash check (an option on the clash panel).

## Done when

- [ ] Tests: a hose across a block with Avoid on stays outside it at every frame of a motion (distance ≥ radius − a set
      tolerance), off = as today; a via point dragged changes the route, kept over save + reopen and a model update
- [ ] Test model with a block in a hose's way; tour stop `flex_avoid`; PC check line(s); guide + pictures; function
      entries; full suite + GitHub run green; report with the cost numbers; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
