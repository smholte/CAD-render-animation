# 0069 – Improvement study: what to add, and what could be done a better way (findings only, no code changes)

**Who:** worker · **Status:** open – start now (Wed 11 Nov, overnight) · **Branch:** `task/0069-improvement-study`
(the report only – **do not push to `main`**: other workers fast-forward `main` tonight; the lead brings it over)
**Started by:** lead chat, 11 Nov 2026 (owner's wish) · **Lane:** none – reads code and searches the web, **changes
no app code, tests or tools**, so it runs next to every lane (tonight: 0029, 0067, 0068)
**Model:** **Opus · effort High** · **Environment:** "CAD-render-animation"

## Goal

Fresing Render has grown fast (0.2.53, ~35 sub-panels, every feature on the owner's list nearly done). Before the
next round of planning, the owner wants an outside look: **what else should the app do, and which things it already
does could be done in a better, faster or simpler way.** The result is a ranked write-up the lead turns into tasks.

## Who uses it, for what (keep the ideas aimed here)

The owner makes realistic stills and animations of large machines from Inventor STEP files (AP214/AP242, up to
~3,000 parts): offshore wind / cable-laying machines (winches, cranes, tensioners, carousels), and his startup's
CNC mill (LinuxCNC, BT30, double-arm tool changer, 4th/5th axis later), for marketing videos, the website and
customers. One Windows PC (Ryzen 9 24 cores, RTX 3090), Blender 5.2.3 under the hood. He is an engineer, not a
programmer and not a 3D artist: short paths from STEP to a good result matter more than knobs.

## What to do

1. **Know what is there first:** CLAUDE.md, `TASKS.md` (Done + Open), `CHANGELOG.md`, `docs/USER-GUIDE.md`, and the
   reports' "Open points" in `tasks/`. Do not suggest what already exists – suggest improving it, with what is weak.
2. **Look outside** (web search; name every source):
   - **Tools people use for the same job:** KeyShot (incl. its animation and CAD import), SolidWorks Visualize,
     Inventor Studio, Fusion's render/animation, Twinmotion / Unreal (Datasmith), Omniverse, Blender CAD add-ons,
     machine-builder marketing videos. Which of their functions would matter for these machines and are missing
     here (e.g. section/cutaway views, X-ray, assembly/exploded sequences, variants, interactive 3D on the website,
     AR, configurators)?
   - **CNC simulation:** CAMotics, NC Viewer, Vericut, Fusion simulation, LinuxCNC's own preview – what they show
     that our milling does not, and how they remove material (dexels/tri-dexels, voxels/SDF, GPU) vs our mesh
     boolean per straight move.
   - **Offshore/heavy-lift visualisation:** wire rope, sheaves, sea state, vessel motion, lifting sequences – what
     such videos usually show (feeds "motion paths", owner's priority 4, and later tasks).
3. **Better ways for what the app already does** – read the code of each area and compare with known methods,
   e.g.: STEP import and tessellation (OCCT settings, instancing of repeated parts, LOD), materials and looks, render
   speed and quality (Cycles/EEVEE settings, light tree, denoising, persistent data, adaptive sampling, render passes),
   video encoding, memory on big models, material removal and chips, clash check speed, the render queue, the
   installer/update path, the test run. Where a claim is cheap to check, **measure** it with a small script in a
   scratch folder outside the repository (time-box each to ~20 min) and give the numbers.
4. **Workflow from Inventor to a finished video:** what could the app read or do so the owner sets up less by hand
   (joints or constraints from CAD, STEP AP242 kinematics/PMI, Inventor or Fusion exports, templates, presets per
   machine type, batch renders of variants)?
5. **Write up** in this file (below), worst-gap or best-value first:
   - **Table:** `# · idea · what the owner gets (one sentence, in his terms) · kind (new feature / better way /
     faster / simpler / quality) · effort (S/M/L) · risk · evidence (source links, measured numbers) · lane · model`.
   - Three short lists after it: **quick wins** (S effort, clear value), **big ones worth a Fable day**, and **ideas
     looked at and dropped** (with one line why – so they are not looked at again).
   - Sources at the end. Plain language; the owner reads the top 10 rows himself.
   Helper agents may search areas in parallel (at most 4, one area each); the main session checks each idea against
   the code before it goes in the table (no "missing" feature that actually exists).

## Done when

- [ ] What exists read first; every row checked against the code; every outside claim has a source or a measurement.
- [ ] Table ranked, quick wins / big ones / dropped lists, sources.
- [ ] No change to app code, tests or tools; the report pushed to `task/0069-improvement-study`.

## Not in this task

Building or fixing anything (that is for the tasks the lead makes from this). Bugs (0068 hunts those tonight – if you
trip over one, note it in one line). The owner's own files (the repository is public).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings:**

**Quick wins / big ones / dropped:**

**Sources:**
