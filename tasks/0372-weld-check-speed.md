# 0372 – Weld check after import: one parent → children map (28–33 s → under 1 s on big models)

**Who:** worker · **Status:** done (0.2.272) · **Branch:** `task/0372-weld-check-speed`
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

- [x] Stress-model weld stage under ~1 s (web machine), model update shorter by about that much; numbers in the report
- [x] Weld results identical (test); the speed guard in place
- [x] The other-lane table in the report
- [x] Tests added / updated; full suite passes (also on GitHub)
- [x] (UI: none – no visible change) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [x] (Windows-only code: none) reviewed by a helper that did not write it
- [x] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)
- [x] **Merged before 0370** (the owner's Inventor weldment, after 0340)

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

**Chat / date:** Claude Code on the web, 28 Nov 2026 – 0.2.272

**What changed:**
- `blender/weld_cad.py`: `children_map()` = {object: its children} of the whole file in one pass over
  `bpy.data.objects`, in the order `ob.children` gives; `_parts_of(root, include, kids=None)` walks that map instead
  of `ob.children` per object. `SCANS` counts the passes (the speed guard). `detect` makes the one map per check; an
  import, *Find welds in the CAD file* (per model) and a model update each make it once.
- `blender/welds.py`: `of_part` (unused, `ob.children` per part) removed. No other per-part `children` /
  `users_collection` scan in the Welds lane (`_ensure_object`'s `users_collection` is once per weld object made –
  0.0 s on the stress model, ~0 on 300 welds).
- `tests/test_weld_cad.py` +4: the same parts in the same order and the same welds bit for bit (table + bead / heat
  zone meshes) as the old walk on the Inventor weldment and the 12-weld grid; one pass per import / Find / model update
  (the speed guard – counts, no clock); no `.children` / `.children_recursive` attribute in the lane's code (AST).

**Tested and measured** – 4-core web machine, Blender 5.2.3 as a Python module, Normal detail, stress model made by
`stress_scene.py` (11,228 placed / 1,995 unique parts, 0 welds), revision A imported, then updated to B; old = `main`
0.2.270, new = this branch; the old code run twice (once making the cache, once from it):

| | old (from cache) | new (from cache) |
| --- | --- | --- |
| weld check after the import (`after_import`) | 30.1 s (31.2 the 1st run) | **1.4 s** |
| – of it the parts walk (`_parts_of`) | ~29 s | 0.05 s |
| whole import | 37.4 s | **9.6 s** |
| weld check in the model update (`carry_over`) | 69.8 s (66.7) | **3.2 s** |
| whole model update | 203.6 s (223.4) | **109.8 s** |

What is left of the 1.4 s / 3.2 s: a profile of the new update's 3.6 s (profiler on) – 2.6 s in Blender calls inside
`carry_over` (the scene update `view_layer.update()` for the new parts' places, which Blender would do at the next draw
anyway), ~1 s finding (name checks on 11,228 parts 0.36 s, 963 thin parts read as possible beads). The walk itself is
0.04–0.14 s. So "under ~1 s" holds for the check's own work; the scene update it starts with stays.
Same result: the stress model's 11,228 parts in the same order, same (empty) weld tables after import and update; the
300-weld frame (`make_test_weldment.py --heavy 100 --beads`, Normal, imported then updated with the same file): the
same 300-row tables and the same bead / heat-zone point hashes old vs new; its weld times unchanged (7.7 s import,
12.0 s update – 301 parts, the walk was never its cost).
Tests run locally: `test_weld_cad.py`, `test_welds.py` (56 pass). GitHub: see below.

**Open points / follow-up tasks** – the same O(n²) pattern elsewhere (found by a read-only helper agent, top rows
checked by hand; costs are estimates from call counts at ~1–3 ms per `children` / `users_collection` call on 11,000
objects, not measured):

| # | lane | file:line | function | when / how often | estimated cost on 11k parts |
|---|---|---|---|---|---|
| 1 | Motion (mechanisms) | `blender/linkages.py:179` | `_parts` (tree walk, `o.children` per node), via `_geometry` | each mechanism made, and at **every model update** (`rebuild_from_specs` → `create`), twice with the flip retry | base = whole model: ~11–33 s per mechanism; a few hundred parts: < 1 s |
| 2 | Section / cut-away | `blender/section.py:116` (via `sync`, ~580) | `_decals_of(p)`: `p.children` per cut part | adding / changing a cut, after a model update, **before every still and queue render** (`sync_for_render`) | cut on the whole model: ~11–33 s each time |
| 3 | Animation (fade) | `blender/fade.py:164` via `animation.py:1029` | `decals_of` per part of each Fade block, in `bake` | every Build | fading 2–5k parts: 2–15 s per Build |
| 4 | Animation (X-ray) | `blender/fade.py:164` via `apply_look` / `remove_look` | `decals_of` per selected part | X-ray on / off click | whole model: ~11–33 s per click |
| 5 | Animation (sequence) | `blender/sequence.py:520, 547` | `_show_again`, end-FADE loop: `fade.decals_of` per moved part | every Build with a take-apart step | 0.5–10 s per Build |
| 6 | Import / model (remove) | `blender/remove.py:326` | `_out_of_scene`: `users_collection` per removed object | Remove parts / a model | 5k parts: ~5–15 s |
| 7 | Motion (joints panel) | `blender/joint_show.py:47` (63–67) | `_meshes`: `children_recursive` per member of every joint, via `hidden_count` | **every redraw** of the Motion tab with a joint selected | ~250 calls: 0.25–0.75 s per redraw (lag) |
| 8 | Lifting | `blender/lifting.py:557` | `remove`: `users_collection` per object of the crane | removing a crane | 0.5–5 s once |
| 9 | House | `blender/house_bake.py:381` | `ob.children` per shown house object per moment | House bake | 4–12 s if a big model is in the same file |
| 10 | Motion (double arm) | `blender/doublearm.py:321` | `_pot_root`: `children_recursive` per ancestor per pot | Find pockets | 0.2–1 s per click |
| 11 | CNC (coolant) | `blender/coolant.py:82` | `_in_scene`: `users_collection` of the coolant root | every frame (frame handlers) | 1–3 ms per frame |

Small (a handful of objects per call): `spool.py:416, 1505`, `tc_person.py:348`, `person_rig.py:52`, `ops_linkages.py:215`,
`ops_doublearm.py:34`, `highlight.py:928`, `camera_path.py:181`, `decals.py:498`. Collection `.children` and
`logic.Tree.children` (a cached dict) are not this pattern. Fix idea for all: one map per operation
(`weld_cad.children_map` could move to `build.py` for everyone), or `logic.Tree`; for `users_collection` one
{collection: set(objects)} per operation.
- The model update's other big cost stays: "remove old" 77–84 s (`batch_remove`, Import lane – 0366's second point).

**Owner's check:** none needed by hand – the PC check's Heavy line "Big machine: where the import time goes" should show
the weld stage at about a second instead of ~30 s.

**GitHub runs:** 1st full run green (46137685101, 35.8 min; the first push's run was cancelled by the version push); 2nd full run after merging `main` (0356 brought code) green (46140656720, 30.4 min); 3rd: 0374 took 0.2.271 meanwhile – renumbered to 0.2.272.
