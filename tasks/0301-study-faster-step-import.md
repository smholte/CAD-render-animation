# 0301 – Study (findings + measurements only): faster STEP import – more cores and other gains

**Who:** worker · **Status:** open – can start · **Branch:** `task/0301-study-faster-import` (branch only, never merged;
every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Multicore step import / import time improvements.")
· **Model:** Opus · effort High
**Area:** findings only; measuring scripts in new files on the branch (e.g. `tools/import_timing/`); reads
`importer/step_reader.py`, `importer/runner.py`, `blender/build.py`, `blender/ops_import.py`, `logic.py`,
`pccheck/heavy_scene.py`, `docs/DEVELOPMENT.md` (measured timings). Not a code slot.

## Background

The reader meshes on all cores but one with helper processes (task 0074); reading the file and turning it into shapes
is one process. On the owner's PC (24 cores): the EGR line (78 MB, 2,789 parts – a GrabCAD model, not in the
repository; ask the owner to attach it if needed) 50–52 s at Normal, 40 s at Draft (2 Nov). Big invented models: the
PC check's Heavy machine (`heavy_scene.py`, ~3,000 parts, written at run time).

## What to find out

A. **Time per stage** on the Heavy machine and a larger invented one, with 1 / 2 / 4 helpers on the 4-core web machine:
   read (STEP parse), transfer to shapes (names, colours, tree), meshing, cache write, Blender build (objects, meshes,
   materials, collections), sorting rules, first draw. Which stages use one core.
B. **Options**, each with the expected gain on a 24-core PC (an expectation, said as one): parallel parsing (OpenCascade's
   own parallel options; reading sub-assemblies in helpers), meshing started while reading, fewer copies between
   processes (shared memory), a faster Blender build (`foreach_set` in bulk, fewer datablocks, instancing), showing the
   model early (Draft at once, Normal swapped in the background), a model update that reads only changed parts, keeping
   OpenCascade's own binary for re-imports.
C. **Ranked proposals** (gain / risk / work), the first one to build, and a PC-check Heavy line that measures the stages
   on the owner's PC.

## Done when

- [ ] Report with the measured table and the ranked proposals on the branch → the lead briefs the build task(s)

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
