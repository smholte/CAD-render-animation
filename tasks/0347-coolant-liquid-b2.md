# 0347 – Coolant liquid B2: 4th axis, 5-axis trunnion, the "Coolant liquid" tour set, the lost wet sheen

**Who:** worker · **Status:** running · **Branch:** `ccr-f71b2999-erailu`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
