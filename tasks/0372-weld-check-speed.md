# 0372 – Weld check after import: one parent → children map (28–33 s → under 1 s on big models)

**Who:** worker · **Status:** running · **Branch:** `task/0372-weld-check-speed`
**Started by:** lead, 28 Nov 2026 (0366's first open point) · **Model:** Opus · effort Medium · Claude Code on the web,
environment "CAD-render-animation"
**Area:** Welds lane – `blender/weld_cad.py` (`_parts_of` and every caller), the same kind of walk in `welds.py` /
`weld_looks.py` / `weld_symbols.py` if it is there, their tests, CHANGELOG.
**Not:** `build.py`, `reimport.py`, `importer/` (Import lane – **0340 starts Mon 30 Nov**), `props.py` beyond additive,
other lanes' files (list what you find there, don't change it).

## Goal

The weld check after an import and after a model update stops growing with the square of the part count: on the stress
model **28–33 s → well under 1 s**, and the model update about 50 s shorter. Same welds found, same result.

## Background

- 0366's report, "Open points", first bullet: the weld check walks the parts with `ob.children`; Blender works
  `children` out by looking at every object in the file, once per call – so the walk is O(n²): 28–33 s of the ~35–45 s
  Blender side of a Big / Stress import and 52 s of a 128 s model update (web machine).
- `blender/weld_cad.py` ~line 76: `_parts_of(root, include)` does `stack.extend(o.children)`; line ~103 calls it.
- 0366 added the PC-check line `heavy.import_stages` ("Big machine: where the import time goes") – use its stages.
- 0368 made the weld finding itself faster (300 welds 30 s → 10 s); this task is the walk around it.

## What to do

1. Measure before: stress model (`tools/make_test_stress.py`) import + model update, the weld stage alone.
2. Build the parent → children map once per check (one pass over `bpy.data.objects`, or `root.children_recursive`
   once) and hand it down; same for any other per-part `children` / `users_collection` scan in the Welds lane.
3. A test that the weld list is **identical** before and after on the test weldment, the 300-weld frame and the
   stress model; a speed guard that cannot flake (e.g. the number of full-object scans per check, not wall time).
4. Measure after (same machine), numbers in the report and CHANGELOG in plain words.
5. Grep the whole app for the same pattern in per-part loops (`.children` inside a loop over parts, `children_recursive`
   per part, `users_collection` per part) outside the Welds lane: a table in the report (lane, file, line, how often per
   import / update, estimated cost). Don't change them – the lead makes follow-ups.

## Done when

- [ ] Stress-model weld stage under ~1 s (web machine), model update shorter by about that much; numbers in the report
- [ ] Weld results identical (test); the speed guard in place
- [ ] The other-lane table in the report
- [ ] Tests added / updated; full suite passes (also on GitHub)
- [ ] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [ ] (Windows-only code) reviewed by a helper that did not write it
- [ ] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)
- [ ] **Merged before 0370** (the owner's Inventor weldment, after 0340)

## Not in this task

A square groove round a pipe (0368's open point – 0370 looks at real Inventor welds), painted welds on painted faces
(after 0340), anything in the Import lane.

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
