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

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
