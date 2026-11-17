# 0195 – Study: the cable-lay demo project running smoothly in the app – every function measured, ranked proposals

**Who:** worker · **Status:** open – can start · **Branch:** `task/0195-demo-smooth-study`
**Started by:** lead chat, 17 Nov 2026 (owner: "look through the entire model of the cable-lay demo project and all the
functions on how to optimise it, to get it to run smoothly in the app") · **Model:** Opus · effort High · **Place:**
Claude Code on the web, environment "CAD-render-animation"
**Area:** findings + measurements only: a report, a measuring tool `tools/measure_demo.py` (new, not app code) and its
small test. **No change to the app** – the lead turns the findings into fix tasks. Does not count as a code task.

## Goal

The owner works in the demo project (Help > Make demo project: ~2,400 parts, ~3,130 objects, ~3.6 M triangles,
4,481 frames, wind park, sea, cables, spools, tracks, people) and it should feel smooth: play, scrub, orbit the view,
select, open panels, change a setting. Find **where the time goes** in every function the demo uses, measured, and
propose fixes ranked by gain / effort / risk – so the lead can brief them as tasks.

## Background

- Known numbers (progress note, 17 Nov): playback ~39–45 ms a frame on the 4-core web machine (unloaded, Blender as a
  module); project ~226 MB; Make demo ~290 s+; Build 221 s on the small demo, the background re-bake 606 s (0183 row
  10 → **0192, running – do not re-measure that one**); web export ~23× too slow (0183 row 9 → **0189, running**).
- Earlier measuring work to build on, not repeat: `tools/measure_cables.py` (0159: Build by module, playback, live
  posing, memory for cables / spools / tracks), CLAUDE.md section 8 (frame pass ~7 ms a frame of Blender's own update,
  Geometry Nodes ~0.007 ms per object per frame, NumPy per-call cost, `logic.Tree` once per operation), 0149 (web size
  ranks), 0151 (render speed study), 0118 (speed per frame and per redraw), 0174 (+3.1 ms a frame after Build).
- No chat machine has a graphics card: drawing cost (triangles, draw calls, Material Preview, EEVEE) can only be
  measured on the owner's PC (RTX 3090, Ryzen 9 9900X, 24 cores).

## What to do

1. **Measure on the web machine** (real Blender 5.2.3 under xvfb where a window matters, Blender as a module where not;
   the made demo of `tests/demo_made.py`), each number with machine, model and how often repeated:
   - per frame while playing and scrubbing: split into Blender's depsgraph (drivers, constraints, Child Of to the
     vessel rig, modifiers per kind: FR flex / FR cable / spool trims / FR track / FR prop detail / decals / sea /
     marine looks …) and the app's Python handlers (`frame_change_*`, `depsgraph_update_post`: flex, paths, clash
     overlay, machining, labels, coolant, vessel work, …) – which run although the demo has nothing for them?
   - per UI action: redraw of each Fresing panel (the tree with 2,400 parts, joints list with ~445 joints, cables, the
     function list), select a part, hover, change a joint value live, a light look, a sea state, Undo / Redo, save,
     open, autosave.
   - memory and file size per kind of data (meshes, the shapes meshes of cables / flex, ID-property arrays, images).
   - the scene's make-up: objects, unique meshes vs copies (instancing), triangles per part group (vessel, park,
     quay, deck machines, people, props), modifiers per object, drivers count, constraints count.
2. **The model itself:** where the demo is heavier than it needs (parts nobody sees from the saved cameras, park
   turbines at full detail 2 km away, duplicated meshes not instanced, very fine round faces, the carousel's layers,
   marine pictures). Compare with what the importer's Draft / Normal give.
3. **What the owner measures on his PC:** `tools/measure_demo.py` – opened in the demo project, run from the app
   (write the steps click by click: Scripting tab → Open → Run, or a Help-menu-free way), it plays a fixed range in
   Solid and in Material Preview, orbits the view, times each panel redraw and writes one text block he pastes back
   (fps, ms per frame split, GPU memory, the top 10 costs). Test the tool here headless (a small test that it runs and
   writes its block); say which numbers are only real on his PC.
4. **Proposals:** a ranked table (gain in ms a frame / seconds per action, effort, risk, lane, model · effort), split
   into: app-wide (benefit every big project – the owner's own assemblies too), demo-model only, and settings the owner
   can switch himself today (e.g. Simplify, viewport detail of the park, hide surroundings in view). Mark any proposal
   that changes what a render shows.

## Rules for this task

- Findings only: no app code changed; the measuring tool and its test may be merged (tools/ only, with `[full run]`
  if the precheck wants it), the report goes to `main`.
- Numbers measured, never guessed (CLAUDE.md section 6); an expectation is called one.
- Up to 3 subagents for separate measuring areas (CLAUDE.md "Subagents"); real-Blender runs one at a time.
- Do not touch the files of running tasks (0189 Web 3D, 0192 cables, 0193 view clip, 0196 sea cut-away view).

## Done when

- [ ] Report below: the scene's make-up, the per-frame split, per-action costs, memory, the model's heavy spots, the
      ranked proposals with lanes, and the owner's steps for `measure_demo.py`.
- [ ] `tools/measure_demo.py` + its test on `main`; TASKS.md row moved to Done ("findings only").

## Not in this task

Fixing anything; the web export (0189); the background re-bake (0192); render speed on the GPU (study 0151).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
