# 0347 – Coolant liquid B2: 4th axis, 5-axis trunnion, the "Coolant liquid" tour set, the lost wet sheen

**Who:** worker · **Status:** done (0.2.276) · **Branch:** `ccr-f71b2999-erailu`
**Started by:** lead, 28 Nov 2026 (0346's "What B2 (0347) needs"; TASKS.md "Problems found": coolant sheen) ·
**Model:** Opus · effort High
**Area:** Machining lane – `blender/liquid.py`, `core/liquid*.py`, `ops_liquid.py`, `coolant.py` (row E only),
`chips.py` / `rotary.py` read-only unless a carrier hook is needed (then additive), Test models lane for the remade
models (`tools/make_test_mill.py`, `make_test_*axis*`, the ATC / cabinet / toolpath / way-cover makers, `tests/data/`
copies and their tour sets' `changed=`), `tour.py` own spots, `pccheck` only an additive Heavy line, their tests,
guide. **Not:** `core/clash.py`, `blender/clash.py`, `materials.py` / `build_nodes` (0360 later), `tools/guide_screens.py`'s
start-up (0373).

## What to do (0346's report, "What B2 (0347) needs", is the plan)

- **A – 4th axis:** charts round the bar from `rotary` (the prototype's four charts, `tools/proto_0251/machine.py` on
  branch `task/0251-study-coolant-pools`), riding on the A-axis carrier (`chips.carrier`); the cut read per chart by
  rays in each chart's own frame (`_Cut` is one top-down chart today). Liquid runs off as the bar turns.
- **B – 5-axis:** the cradle as a riding chart (the trunnion tilts it – effective gravity spills pools to the low side),
  the C table.
- **C – models:** make `test_4axis.step` / `test_5axis.step` and the ATC / cabinet / toolpath / way-cover models again
  with the fixed tray of `make_test_mill.py`; their tour sets' `changed=`.
- **D – tour set "liquid":** add 0251's six stand-alone stops and the 4- / 5-axis stops.
- **E – wet sheen lost when a wet group's look changes** (found by reading in 0344, not run): `build_nodes` clears a
  material's nodes but keeps `fr_coolant_patch`, so `coolant.is_patched` stays true and `_patch_new_materials` does not
  put the sheen back (`coolant.py` ~311–318, ~556–568). Repeat it first; fix in `coolant.py` (e.g. a check that the
  patch node is still there), not in `build_nodes`.
- **F – cache size** (2.7 GB for 10 min at Normal on 3-axis; the bar's charts change every frame): measure a long
  4-axis program, propose a limit / lighter cache with numbers. The owner decides whether new projects get liquid on
  (0346) – give him the numbers.

## Done when

- [ ] A–E work with tests; F measured with a proposal
- [ ] Goal kept: the 10-minute 3-axis VMC program still < 10 min at Normal (owner's PC line unchanged)
- [ ] Tests added / updated; full suite passes (also on GitHub)
- [ ] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [ ] (Windows-only code) reviewed by a helper that did not write it
- [ ] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)
- [ ] **Owner's check** line (tour stops to look at; the Heavy line to send)

## Not in this task

Chips carried by the liquid and the air blast (later, owner decides); liquid in a T-slot's undercut; drops through way
covers (0346 open points – list if you touch them).

**Running beside it (weekend 28–29 Nov):** 0371 Demo · 0355 / 0356 Assets · 0372 Welds · 0347 Machining · 0349
Lifting · 0353 Web 3D + House · 0373 guide-picture tool · 0374 cable-lay line · 0375 Sea · 0377 Start & windows ·
0379 PC check · findings-only 0380 / 0381. Shared files only additively, each in its own spot: `props.py`, `tour.py`,
`core/functions.py`, `tools/guide_screens.py` (0373 owns its start-up code), `pccheck/checks.py` / `heavy.py` (0379
owns the lines it names). Whoever merges second updates its branch to `main`; versions: CLAUDE.md section 7 step 0.

## Design (worker, 28 Nov 2026)

**A / B – charts from the chain of movers (`blender/liquid.py`, `machining.sample`).** `machining.sample` also stores
the world matrix of every mover above the workpiece's own at every frame (`fr_chain_m`, names in `fr_chain`; chips
keep `fr_carrier_m`). The liquid takes the levels from the workpiece's mover upwards and stops after the first level
that only slides (3-axis: the table alone – as 0346; 4th axis: A, then the X table; trunnion: C, the cradle A, then
the X table). Every level is a top-down chart of the parts that ride on exactly that mover, in its riding space (the
world at the motion's first frame); the workpiece's level also has the cut block (`_Cut`). **Bar mode:** when the
workpiece's mover turns about a line more than 45° from vertical (relative to its carrier), its level is four charts
round that line (chart z = outward at 0°, 90°, 180°, 270°, x = along the axis, the bar's length; height = the distance
from the axis; rays inward in each chart's own frame), as the 0251 prototype. Every chart keeps its placement:
`to_obj` (chart frame → the followed object's local frame at the first frame) and the object it follows (the
workpiece, a mover, none = world), saved in the beds file; `show` draws one sheet object per chart
("FR coolant liquid (<chart>)", the 3-axis names stay) following its object with Copy Transforms. `_Cut` reads per
cut chart in that chart's frame. `VERSION` 2.

**D – the lab (subagent, own files):** `core/liquid_lab.py` (no Blender: the six stand-alone cases of 0251 as charts +
mats + pours + the case's number), `blender/liquid_lab.py` (bed meshes, bake into a cache next to the project, its own
frame handler drawing with `liquid.sheet` / `liquid.material`), `tests/test_liquid_lab.py`; tour set "liquid_lab"
(no model) with six stops. 4- / 5-axis stops: tour sets "liquid4" (test_4axis.step) and "liquid5" (test_5axis.step),
set up by `liquid.set_up_test_rotary`.

**E** – `coolant.is_patched` asks for the patch nodes too; `_patch_new_materials`' key holds each material's node count.

**C** – the five makers run again; each new file differs from the old in CHIP TRAY only (volume 17,453,205 →
16,502,993 mm³, its bottom 33.85 mm higher), compared part by part with OpenCascade.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 28 Nov 2026 · version 0.2.276 (branch `ccr-f71b2999-erailu`).

**What changed:**
- **A – 4th axis / B – trunnion** (`blender/liquid.py`, `machining.sample`): `machining.sample` also stores the world
  matrix of every mover above the workpiece's own per frame (`fr_chain`, `fr_chain_m`). The liquid's charts come from
  that chain: the workpiece's mover up to the first level that only slides (3-axis: the table alone – as 0346; 4th
  axis: A, the X table; trunnion: C, the cradle A, the X table), each a top-down chart of the parts riding on exactly
  that mover ("table", "carrier 1", "carrier 2") + the tray. A workpiece turning about a lying axis gets **four charts
  round the bar** ("bar 1" … "bar 4", the 0251 prototype's, 0.75 x the table's cell), the cut read in each chart's own
  frame (`_Cut.read_all`, `_cast_in`). Every chart's sheet follows its object (workpiece, mover, none) with its
  placement in the beds file (`Beds.place`, `Beds.follow`). `set_up_test_rotary` (+ `TEST_PROGRAM_4`, `_program_5`,
  `long_program_4`) = tests, tour, Heavy line. An older Build without `fr_chain` asks for Build & play. `VERSION` 3.
- **Solver** (`core/liquid.py`, two small changes, both only where a chart is steeper than 45°): the critical-flow cap
  uses the larger of pressing and sliding gravity (a chart on its side let nothing run along it: 3–4 cm columns), and
  a chart can drip off below a share of g (`Chart.drip_below`, default 0.05 as before; the bar's charts 0.5 = steeper
  than 60°). The jets land spread over 12 mm (`JET_SPREAD`, was 2.5 mm: a 14 l/min flood stood 2 cm high on the bar).
- **C – models:** `make_test_4axis/5axis/atc/mill_cabinet/toolpath.py` run again: each new STEP differs from the old
  one in CHIP TRAY only (volume 17,453,205 → 16,502,993 mm³, its bottom 33.85 mm higher; compared part by part with
  OpenCascade), copied to `tests/data/` and `fresing_render/data/`; their tour sets' `changed=`.
- **D – tour:** sets "liquid4" (test_4axis) and "liquid5" (test_5axis) with stops "Coolant liquid on the 4th axis" /
  "… on the trunnion"; set "liquid_lab" ("Coolant liquid – six checks", no model; `core/liquid_lab.py` +
  `blender/liquid_lab.py`: the six rigs with their own bakes and frame handler; `tests/liquid_scenes.py` now uses them)
  with six stops, each showing its number. Function `cnc.liquid` names all 9 stops.
- **E – wet sheen:** `coolant.is_patched` wants the patch nodes too; `_patch_new_materials`' key holds every
  material's node count. Repeated first (`test_wet_sheen_comes_back_after_the_look_changed` failed before the fix).
- PC check: Heavy `heavy.liquid4` (5-minute 4th-axis program at Normal; scaled down: 16 s Draft); guide section
  "Coolant liquid on the machine" (4th axis, trunnion, the six checks, the film on the bar); CLAUDE.md section 3.

**Tested and measured** (4-core web machine, Intel Xeon; Blender 5.2.3 as a module; test models only):
- `tests/test_coolant_liquid_rotary.py` (6, mine), `tests/test_coolant_liquid_rotary_independent.py` (14, the
  independent tester's), `tests/test_liquid_lab.py` (6), `test_coolant_liquid*.py` + `test_coolant.py` (0346's and
  0042's, all green with the solver changes), `test_liquid*.py` (108, 0255's – the six cases' numbers unchanged).
- 4th axis (Draft, 16 s, 385 frames): four bar charts of ~1,120 cells, the table, the tray; ~120 ms a frame on one
  process; the pocket holds while it is up, after the turn < 0.05 cm³ is left on the bar; books exact.
  Trunnion (Draft, 385 frames, ~63 ms a frame): the C table holds ~150 cm³ while flooding; at A-35 it has spilled
  > half onto the cradle (232 cm³ there), what is left moved to the low side.
- Six checks (lab, placed rigs): pocket 12.86 of 12.80 cm³ (+0.5 %), slot 8.3 % left / half gone in 0.38 s, tilt
  spills at 15.1° (14.0° expected), tray 95 % gone 22.5 s after the pour, slosh 1.24 s (1.28), wall 0.000 cm³.
- Tour: `test_tour_clash.py` 0 clashes for liquid4, liquid5, liquid_lab and the five remade models' sets; Go + check of
  all 9 liquid stops pass (`test_tour.py`).
- **Goal kept (3-axis, 16 s program, Normal, 1 process, same machine, same load):** 225 ms a frame on main, 233 with
  this branch (+4 %, same sub-steps 11.7, same 38 MB) – the owner's 10-minute line is not expected to move.
- **F – cache size, a 2-minute 4th-axis program at Normal** (`long_program_4`, 2,881 frames, 3 helpers, 4 shared
  cores while other tests ran): bake 74.5 min (not a speed figure: the machine was full), **955 MB = 331 kB a frame
  ≈ 480 MB a minute of program → ~4.8 GB for 10 minutes.** Where it goes: **drops 614 MB (64 %)**, the X table 165 MB,
  the tray 153 MB, the four bar charts 4 MB each. Lighter storage, measured by re-encoding that file:
  drops as 16-bit places + half floats **−384 MB** (955 → ~570), the table and tray stored at twice the cell −229 MB,
  every second frame −50 %, zlib level 6 −3 %, 0.1 mm steps −5 %.
  **Proposal:** (1) drops as 16-bit (no visible change, −40 %); (2) the table and tray stored at twice the cell at
  Normal (−25 % more; the sheet is drawn from a coarser grid on the big flat charts only); together ~1.7 GB for a
  10-minute 4th-axis program, ~1 GB for the 3-axis one (2.7 GB today); (3) keep liquid off for new projects until
  then (0346's advice stands). The owner decides; a small follow-up task in the Machining lane.

**Subagents:** (1) one worker subagent (Opus, worktree) wrote the six checks: `core/liquid_lab.py`,
`blender/liquid_lab.py`, the "liquid_lab" set and stops, `tests/test_liquid_lab.py`, `tests/liquid_scenes.py` moved
onto it; merged as it was. (2) an independent tester (Sonnet, worktree) wrote
`tests/test_coolant_liquid_rotary_independent.py` (14) from the brief: it found the liquid columns on the bar (fixed:
the two solver changes + the drawing cap) and sheet points inside the bar at its end face (fixed: the bar's charts
over whole cells only); kept as written. No Windows-only code was added (no review needed).

**GitHub runs:** 4 full runs on the branch – (1) cancelled by a newer push; (2) 0.2.275: two failures – the new
sets liquid4 / liquid5 were not in `tour.MILLING_SETS` (fixed: their stops now check the cut too) and 0374's
`test_KNOWN_FAULT_a_coil_read_from_a_coarse_faceted_tube_is_refused_in_words` read 11.6 mm on that runner (6.5 mm
limit; passes here – a CPU-dependent known fault of the cable lane, not touched; lead: 0374's follow-up); (3) precheck:
0.2.275 taken by 0349 → merged main, renumbered 0.2.276; (4) **green, run 46170927053** (36 min). Then main's
document commits merged, report pushed, fast-forward of `main`.

**Open points / follow-up tasks:**
- **The film on the bar is thicker than real** (the height field carries a film at critical depth: ~5 mm at 14 l/min
  where a real one is ~1 mm), and on a strip of the bar standing on its side single cells can still hold columns of
  2–4 cm for some frames (no gravity presses them flat). Drawn at most 6 mm thick (`BAR_SHOW_MAX`); the volumes are
  as worked out. A better way: one chart wrapped round the bar (cylinder coordinates) instead of four flat ones.
- The cache proposal above (owner's choice).
- Only lying axes get bar charts; a tombstone (a block on a horizontal 4th axis) is charted as a bar (four strips
  round its axis) – fine for its faces, untested.
- Charts are cast in each level's frame at the motion's first frame: a trunnion that starts tilted gets its C table
  chart tilted (the liquid is right, the grid is less fine across the slope).
- `test_the_tour_builds_every_project` (all sets < 240 s): 346 s on this machine while two other jobs ran; the three
  new sets took 16 + 9 + 26 s of it (the lab bakes six cases at build).

**Owner's check** (on the PC, after Update now):
1. Help > Fresing Render PC check… > **Heavy** – send the lines "Milling: coolant liquid on the 4th axis, a long
   program" (minutes, MB, MB a minute) and "Milling: coolant liquid of a 10-minute program".
2. Help > Make test tour project; in the Test tour panel: **Machining > Coolant liquid on the 4th axis** and **… on
   the trunnion** – press **Go**, then play; and the six stops of **Coolant liquid – six checks** (each shows its
   number in its check).
3. Decide: lighter cache (proposal above) – and whether new projects get liquid on.
