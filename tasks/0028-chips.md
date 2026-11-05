# 0028 – Chips: flying chips that depend on the bit and the material

**Who:** worker · **Model:** Opus · **Status:** done (0.2.21) · **Branch:** `task/0028-chips`
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

- [x] Tests: chips appear only while cutting, the amount follows removed volume, the bake is the
      same on two runs, queue render shows chips, each preset builds
- [x] Render time per frame with chips (few / realistic) measured on the test machine
- [x] Real-app click test step, screenshots, full suite, GitHub run green; merged and released

## Not in this task

- Sparks, smoke, fluid coolant jets (possible follow-ups).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 5–6 Nov 2026 (Opus). Version 0.2.21, no installer (usage rule).

**Choice:** not Blender particles or a Geometry Nodes simulation zone, but a flight worked out in numpy
(`core/chips.py`, no Blender) and shown as two point clouds with a small Geometry Nodes instancer. Why: the
chips must come off where and when material is removed (per frame, per spot), land on a workpiece that is
being cut and on a table that moves, and give the same result in any frame order (scrubbing, the queue);
in numpy that is exact, deterministic and testable without Blender. The "bake" is kept in memory (worked out
again in under a second after opening; nothing big in the .blend).

**What changed:**
- `core/chips.py`: 35 presets (7 materials × 5 bit types: end, ball, face mill Ø ≥ 25, drill, V-bit) + coolant
  mist + wood dust; 8 chip shapes made in code (curl, helix, comma, ribbon, flake, crumb, dust, drop; 6
  variants each, closed meshes); material from names (EN/NL/DE words, alloy codes, prefixes only for long words)
  then the group's material in 3 Looks, else aluminium. Workpiece height field (≤ 420 cells a side, ~0.5 mm),
  the bits' paths stamped in time order (finished part as floor) → removed volume per frame and per spot.
  Chips per mm³ removed (Few × 0.12); flight with gravity, drag, bounces, pocket walls, 4 steps per frame;
  landing on the workpiece as cut at that moment, on parts that move with it (riding space) and on parts that
  stand still (world) or the floor; piles; chips on the block end when the bit cuts there; cap 3,000 / 25,000
  alive (oldest lying ones shrink away in 0.16 s).
- `blender/chips.py`: inputs from the milling set-up; parts that move with the workpiece / stand still found
  from keys, drivers and constraints on their parents (no frame stepping); rays cast down for the catch height
  fields; "FR Chips" (Copy Transforms to the workpiece) and "FR Chips (fallen)" point clouds; instancer node
  group, shape objects named in index order, one material per family (colour ramp on a per-chip tint; plastic
  takes the block's colour). `machining.py`: `sample()` also stores the workpiece's place at every frame;
  `refresh()` shows the chips; Stop milling / Cut material off / no bits hide or remove them.
- 4 Motion > Milling > **Chips** sub-panel (Chips, Material, what was read, per bit what it throws, status,
  Clear chips, More: Spindle turns, Coolant mist). Tooltip check: 295 found, 0 missing, 0 weak.
- User guide: "Chips" in the Milling chapter with a table and measured times, picture `panel_4_chips.png`
  (real app, test mill). CLAUDE.md: layout + 3 lessons. `tools/bench_chips.py`.

**Tested and measured** (2-core test machine):
- `tests/test_chips_core.py` 76 (every preset and variant builds a closed mesh; names → material; slot volume
  to 1 %; chips only from the first to the last cutting frame; count = removed mm³ × rate, 10 mm deep = 2.00 ×
  5 mm; cumulative chips follow cumulative volume; bake bit-identical twice, any frame order; landing on block,
  table, bed and floor, never inside the slot walls; piles; chips on the block gone when a second slot cuts
  there; a moved table shifts the fallen chips by exactly its offset; cap; mist fades; other materials/bits).
  `tests/test_chips.py` 9 on the test mill (appear while cutting, riding chips go with the table, same chips
  after forgetting and after save/open, material from the group look and chosen, deeper cut = 2× chips, Clear
  chips and Stop milling remove everything, panel draws, tooltips, **real render queue: a close-up of the block
  beside the slot is bare in frame 1 and shows chips in the last frame**). `test_machining.py` still 14/14.
- Real app `ui_test_milling.py` 24/24 (7 new: Few shows chips, none before the cut, same after scrubbing, status,
  Clear chips, back after reopening, gone after Stop milling); MIN_CHECKS 17 → 24.
- Working out: test-mill slot 0.36 s (Few) / 0.44 s (Realistic) incl. 0.24 s reading the machine; zig-zag pocket
  150 × 150 × 5 mm, 1,158 frames: 4.0 s (6,600 chips) / 4.5 s (55,000 chips). Showing a frame: 0.35 ms (Few) /
  2.8 ms (25,000 chips) to look up, 8–17 ms per frame change in Blender (milling 5 ms of that).
- Render, Cycles on the processor, 640 × 360, Preview: slot 50 × 10 × 5 mm: none 26.0 s, Few (150) 26.5 s,
  Realistic (1,218 in view) 28.8 s; slot 90 × 10 × 15 mm: none 24.4 s, ~6,200 aluminium curls 32.2 s (+32 %),
  25,000 brass crumbs 29.9 s (+23 %). GPU not measured.
- GitHub run: see below (branch and main). Helper-agent review skipped: no Windows-only code.

**Open points / follow-up tasks:**
- Owner test on his PC: a milling animation with Realistic chips, time per frame on the RTX 3090; viewport with
  25,000 chips. For the PC check (task 0032): one line "milling + chips at one frame" would fit.
- Height fields see from above only: chips do not land on parts that hang over the table (the head) and pass
  through the bit and the spindle; with a tilted bit (4/5-axis, task 0029) the chips' spots are approximate.
- Long programs: working out takes ~4 ms per frame of program on 2 cores (3,800 frames ≈ 15 s, with a progress
  bar); the owner's PC should be faster.
- Not in this task: sparks, smoke, coolant jets. Branch `task/0028-chips` can be deleted on github.com.
