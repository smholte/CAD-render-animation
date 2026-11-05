# 0028 – Chips: flying chips that depend on the bit and the material

**Who:** worker · **Model:** Opus · **Status:** running (worker chat, 5 Nov 2026) · **Branch:** `task/0028-chips`
**Started by:** lead chat, 5 Nov 2026 · **Lane:** Machining · **Area:** `blender/machining.py`,
new `blender/chips.py`, `core/` data for chip presets, `blender/ui_machining.py`,
`blender/props.py` (additive), the user guide's Milling chapter, `tests/`.

## Goal

While milling, chips fly from the bit like on the real machine, and they look different per bit
type and per workpiece material: curly shiny aluminium chips, blue-brown steel curls, small brass
crumbs, long plastic ribbons, wood dust and shavings; long spirals out of a drilled hole; fine dust
from an engraving bit.

## Background

- Builds on 0027 (removed volume per frame and where the bit cuts); read its report.
- Blender's Geometry Nodes simulation zones (or particles) can emit, move with gravity, bounce on
  the workpiece/table and pile up; the simulation must be **baked before rendering** so the
  background queue gives the same result in every frame and on every PC.
- The workpiece's material comes from its group (3 Looks: aluminium, steel, brass, POM…, task
  0008's library) – pick the chip preset from it automatically, changeable.

## What to build

1. Chip presets (shape made in code, size, colour/material, how many per mm³ removed, how they
   fly): per material (aluminium, steel, stainless, brass/bronze, cast iron, plastics, wood/MDF) ×
   per bit type (end mill, ball, face mill, drill, engraving/V-bit).
2. Emission where the bit cuts, amount from the removed volume, thrown off in the spindle's
   turning direction; gravity, bounce, chips piling up on the table; optional coolant mist.
3. Amount setting (none / few / realistic) and its effect on render time measured.
4. Baked automatically before a queued render; "Clear chips" button.
5. Tooltips; user guide Milling chapter.

## Done when

- [ ] Tests: chips appear only while cutting, the amount follows removed volume, the bake is the
      same on two runs, queue render shows chips, each preset builds
- [ ] Render time per frame with chips (few / realistic) measured on the test machine
- [ ] Real-app click test step, screenshots, full suite, GitHub run green; merged and released

## Not in this task

- Sparks, smoke, fluid coolant jets (possible follow-ups).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
