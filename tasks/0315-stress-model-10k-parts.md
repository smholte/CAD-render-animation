# 0315 – A stress test assembly of ~10,000 parts and a "Stress" run that measures where the app slows down or breaks

**Who:** worker · **Status:** open – can start (0296 done, 0.2.221) · **Branch:** `task/0315-stress-model`
**Started by:** lead, 23 Nov 2026 (owner 21:29: "Could we also add a larger test assembly? with 10k parts or so (not
used normally but used for more stress tests)") · **Model:** Opus · effort High
**Area:** new `tools/make_test_stress.py` (the maker; Test models lane, new file only), new
`fresing_render/pccheck/stress.py` + a small additive mode entry in `pccheck/ops.py` / the app folder's Tools (0212: no
new Desktop shortcut), a **manual-only** GitHub workflow (`workflow_dispatch`, Linux, never on push), its tests, guide
(PC check section), CHANGELOG.
**Not:** the normal test run (nothing here may slow down a push run); the Heavy mode's lines (keep them); import speed
work itself (study 0301's ranked options are their own tasks).

## Goal

One invented assembly about three times the size of the PC check's Heavy machine, as close as we can get to a real
large Inventor STEP, made on demand and never in the normal tests. A **Stress** run imports it and times every heavy
action, so the owner (on his PC) and the lead (on GitHub, by hand) can see where the app slows down or breaks, and
compare one version with the next.

## Background

- PC check **Heavy** (`pccheck/heavy.py`, `heavy_scene.py`): about 3,000 placed / 600 unique generic parts, made at run
  time, deleted after. Study **0301** (branch `task/0301-study-faster-import`) also built **Big** = Heavy × 4 (96 MB) in
  `tools/import_timing/make_models.py` and found our invented parts have simple faces (planes, cylinders) – real
  models have more B-spline faces and mesh slower (its "Heavy as B-splines" model). Start from both; do not copy the
  0301 files onto `main` unless you move them here properly.
- The owner's real numbers: EGR line 78 MB, 2,789 parts, import 50–52 s Normal on his 24-core PC.
- Rules: invented only (CLAUDE.md: never the owner's or his employer's models); **not the Fresing 400's size class**
  (no CNC mill of that size); **not the private demo vessel's equipment** (CLAUDE.md section 6).

## What to do

1. **The model** – an invented **offshore substation topside module** (fits the owner's field): transformer and
   switchgear rooms with cabinets, cable trays with cables, pipe racks with valves and flanges, gratings, stairs,
   ladders, handrails, doors, a pedestal crane on top, a davit – at real size.
   - About **10,000 placed parts**, about **2,000–3,000 unique**; **fasteners about 40 %** (bolts, nuts, washers in
     ISO / DIN names, as real assemblies have them); 5–7 subassembly levels named the way Inventor writes them
     (`Name:1`), a few parts without a useful name.
   - Realistic faces: a share of B-spline / lofted / filleted faces (0301's finding), so meshing is like a real model.
   - **Joints-ready**: the crane (slew, boom, hoist), the davit and a few doors, so motion, Build and lead motions
     (0309) can be stress-tested.
   - Report the numbers: parts, unique parts, faces, triangles at Draft / Normal / Fine, STEP size, make time.
     Target 8–15 M triangles at Normal; if it is far off, say why and what you chose.
   - **Never committed**: made at run time into a temp folder (as Heavy). Also offer it to the owner as a download:
     attach the STEP to a **draft release `stress-model`** (as the site kit did) so he can import it by hand.
2. **The Stress run** – lines, each with time, peak memory and a pass / slow / failed mark against a limit you set
   from the first measurement:
   import (Draft and Normal), the side panel's group lists and search, select / hover, Solid view and Live preview
   (first picture, orbit frames per second), Build with the joints, a joint drag, the clash check, save / load (time,
   file size), an automatic backup, a **model update with ~1 % of the parts changed**, Undo after a big action, Render
   image 4K (GPU on his PC; a small size on GitHub), the web 3D export (size, time). Results to a table file next to the
   PC-check report **and compared with the previous Stress run** on that machine (slower by more than 15 % = marked).
3. **Where it runs**: on the owner's PC as PC check mode **Stress** (Tools folder in the app folder + the app's PC-check
   menu; a clear "this takes long – about N min" before it starts, Cancel works); on GitHub only as a **manual**
   workflow on Linux (no graphics card: say which lines are skipped there). Never in the push run.
4. Guide: what Stress is for and how to read its table; numbered steps for the owner to run it once on his PC.

## Done when

- [ ] Maker writes the ~10,000-part model; numbers in the report; a test on a small version of the maker (seconds)
- [ ] Stress run: all lines run on the web machine (Linux, no graphics card) with their times in the report; the
      comparison with a previous run works (test)
- [ ] Manual GitHub workflow runs green once (link in the report); the push run's time unchanged
- [ ] Draft release `stress-model` holds the STEP; the owner's test steps (numbered, click by click) in the report
- [ ] Tests added/updated; full suite passes; merged, version, release

## Not in this task

Making any slow line faster (the report lists them, ranked, for the lead); 0301's import options; Heavy's own lines.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
