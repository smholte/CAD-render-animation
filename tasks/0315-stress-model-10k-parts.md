# 0315 – A stress test assembly of ~10,000 parts and a "Stress" run that measures where the app slows down or breaks

**Who:** worker · **Status:** done (0.2.234, 24 Nov 2026) · **Branch:** `task/0315-stress-model`
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

**Chat / date:** Claude Code on the web (worker), 24 Nov 2026. Released as **0.2.234**.

**What changed:**
- **The model** – `fresing_render/pccheck/stress_scene.py` (shipped in the extension, so the owner's PC makes it at run
  time, like Heavy's `heavy_scene.py`; uses the app's shape library `demo_model/geom.py`, loaded by its path). An
  invented offshore substation topside 36 x 24 m, three decks + roof: welded primary steel (I-profiles with root radii,
  stiffeners, gussets; Frame-Generator style: every member its own part), bolted secondary beams, gratings with clips,
  plated decks, handrails, a stair tower and ladder, two transformer rooms (filleted tank, lofted cooling walls,
  radiators, revolved bushings, conservator, bolted lid), two switchgear rooms (32 cabinets with filleted doors,
  breakers unique per cabinet, terminals, glands, a wiring loom), six cable-tray runs with 48 B-spline cables, a pipe
  rack (spools, weld-neck flanges with studs, gate valves with lofted bodies, gauges with tag plates, U-bolts), HVAC
  units with lofted fan blades, lights and junction boxes, a pedestal crane (slewing ring with 2 x 40 bolts, lattice
  boom, hook block) and a davit. Inventor occurrence names `Name:1`, 6 levels, 9 parts named "PartNN", 29 castings
  turned into B-splines. Joint sheet `<step>.joints.json` (crane slew / boom luff / hoist, davit slew, 4 room doors);
  `--revision B` changes 103 of 11,228 placed parts (0.9 %: stiffeners, a handrail side, a tray run and its cables,
  cabinet bodies, a spool, valve bonnets, the boom sheave) with the same names.
  `tools/make_test_stress.py` = the command line (`--measure` with the app's reader, `--zip`, `--publish` to the draft
  release). **Deviation from the brief:** the maker itself is not in `tools/` (not shipped) but in `pccheck/`; the
  tools file is its command line.
- **The Stress run** – `fresing_render/pccheck/stress.py`: 16 lines (`stress.model`, `import_draft`, `import_normal`,
  `lists`, `select`, `solid`, `live`, `build`, `drag`, `clash`, `save`, `backup`, `undo`, `render`, `web3d`,
  `update` last because it changes the model). Each: time, **peak memory during the line** (a sampling thread,
  `MemoryWatch`; the import helpers' memory is not in it), a **limit** (`Line.limit`, about 2 x the first web-machine
  time) -> mark pass / slow / failed. `core.py`: mode `stress`, compared with the **previous** Stress run only, flagged
  from **15 %** slower (`SLOWER_BY_MODE`, `REFERENCE_RUNS_BY_MODE`; other modes unchanged), the table
  (`stress_rows`, `stress_csv`, `stress_text`) -> **Fresing Render stress table.csv** next to the report and in the
  text block. The console says "this takes long – about N minutes" first; Cancel works (also while the model is made).
- **Where it runs** – PC-check window: choice **Stress (10 to 20 minutes)** with a warning text; Tools folder:
  **PC check (stress)** (installer + `appicon.TOOLS`, so an app updated with Update now makes it too;
  `ci_windows_install.ps1` expects 7 shortcuts). GitHub: `.github/workflows/stress.yml`, **workflow_dispatch only**
  (size full/small, optional "put the model on the draft release"), runs `tools/ci_stress.py` (installs the app into a
  fresh settings folder, starts the launcher in mode Stress under xvfb, judges the text block). Not in `tests.yml`:
  the push run is unchanged apart from `tests/test_stress.py` (~20 s).
- Guide: PC check section, "Stress" paragraph with numbered steps and how to read the table; the Tools-folder list.
  CHANGELOG 0.2.234; `help.pc_check` changed=0.2.234.

**Tested and measured** (4-core web machine, Intel Xeon 2.3 GHz, 16 GB, no graphics card, Linux):
- Model (full): **11,228 placed / 1,995 unique parts, 4,940 fasteners (44 %)**, 42,626 B-rep faces (576 B-spline
  faces, 1.4 % of the faces but most of the triangles: the cables), **STEP 206 MB** (34 MB zipped), **made in 56–61 s**
  (shapes 39 s, STEP writing 22 s). Triangles with the app's reader (3 helpers): **Draft 4.13 M** placed / 2.58 M
  unique (50 s), **Normal 13.9 M** / 10.9 M (91 s), **Fine 34.7 M** / 28.3 M (195 s) – inside the 8–15 M target at
  Normal. Size per unique part ~100 KB (the EGR line: 133 KB), so the file size is realistic.
- **Stress run, real Blender 5.2.3 in the background (as the shortcut starts it): 16 lines in 13.1 min**:

  | line | s | numbers | peak MB |
  | --- | --- | --- | --- |
  | model | 56.5 | 206 MB | 369 |
  | import_draft | 55.9 | 4.13 M triangles | 1,345 |
  | import_normal | 113.2 | import 100 s, from cache 12.6 s, 13.9 M triangles | 1,855 |
  | lists | 1.1 | sort 0.18 s, Structure list 0.16 s, one redraw 1.1 ms (searching 1.3 ms), find 0.02 s | 1,686 |
  | select | 0.5 | select all 0.07 s, hover 6.3 ms mean / 15.8 ms slowest | 1,696 |
  | solid | 200.5 | first picture 16.1 s, **0.07 pictures/s** turning (software OpenGL: no graphics card) | 4,080 |
  | live | 10.5 | first Cycles picture 10.4 s (CPU) | 6,041 |
  | build | 7.8 | 8 joints 1.6 s, Build 0.9 s, playback 21 ms/frame (251 frames) | 4,327 |
  | drag | 4.1 | **78 ms per step** (slowest 96 ms) | 4,325 |
  | clash | 53.7 | 791 moments, 42 clashes | **7,509** |
  | save | 4.1 | save 1.6 s, open 2.4 s, **313 MB** project | 5,237 |
  | backup | 1.7 | 313 MB | 4,898 |
  | undo | – | skipped in that run (fixed: Blender needs an undo step after the action too); after the fix: small model 0.06 s, GitHub full model **0.71 s** | – |
  | render | 11.1 | 480 x 270 Draft on the CPU (no graphics card) | 6,783 |
  | web3d | 75.2 | 28.6 MB .glb, 13.9 M triangles | 6,296 |
  | update | 187.6 | revision B made 56.5 s, **model update 131 s** for 103 changed parts (0.9 %), joints kept | 6,142 |

- Small model (`FRESING_PCCHECK_STRESS_SMALL=1`, 1,643 parts): the whole Stress run in real Blender 1.9 min, all 16
  lines OK incl. Undo; in Blender as a Python module 113 s.
- Comparison with the previous run, the 15 % flag, the limit, the CSV: `tests/test_stress.py` (also the small maker
  with revision B, the joint sheet, the line list, the mode / shortcut / installer / workflow wiring, the memory
  watch). Local: test_stress, test_pccheck, test_appicon, test_functions, test_user_guide, test_updates: 150 passed.
- Independent review (a helper agent that did not write it) of the Windows-only parts (`current_memory_mb`,
  the installer line, `appicon`, `ci_windows_install.ps1`): no faults found; its one tidy-up (the launcher docstring)
  done.
- **GitHub runs: 1 full run** of the branch, green first time (run 45385725066, 31 jobs, 31 min with other tasks'
  runs queued). `main` fast-forwarded to that commit: reuse run 45390587544 published **v0.2.234**, the Windows
  self-update check from the release and "Offer" green; only the landing-page deploy failed with GitHub's own
  "Deployment failed, try again later" (re-run). The push run's own time: unchanged except `test_stress.py` (~20 s).
- **Manual Stress workflow, green once:** https://github.com/smholte/CAD-render-animation/actions/runs/45390611100
  (full size, AMD EPYC 9V74, 4 cores, no graphics card): **16 of 16 OK in 14.4 min** (job 16.7 min) – model 55 s,
  import Draft 60 s / Normal 120 s, lists 1.3 s, hover 6.8 ms, Solid 19.4 s first picture, Live 15.7 s, Build 1.0 s,
  drag 82 ms/step, clash 60 s, save 1.7 s / open 2.1 s, backup 1.6 s, **Undo 0.71 s**, render 15.8 s, web 3D 82 s,
  model update 141 s; peak memory 7.4 GB (clash). The model zip (33.7 MB) is on the **draft release `stress-model`**.

**Ranked for the lead – the slow places this run shows** (on the 4-core machine; the owner's PC will say how they
scale):
1. **Model update 131 s for 0.9 % changed parts** – longer than a fresh Normal import (100 s): every part is read and
   meshed again (study 0301's unchanged-part hashing would skip ~99 % of the meshing).
2. **Long B-spline cables mesh into ~127,000 triangles each at Normal** (a 30 m cable; 0.5 mm cap): 48 cables = 8 of
   the 13.9 M triangles and most of the meshing time. A real Inventor cable harness will do the same.
3. **Dragging a joint: 78 ms per step** (~13 steps a second) with 11,000 parts, though only the crane moves.
4. **Clash check peak memory 7.5 GB**; the session as a whole stays at 5–7 GB after the import.
5. Import at Normal 100 s on 4 cores (reader 33 s on one core before meshing starts).
6. Solid view 0.07 pictures/s here is software OpenGL – the owner's run will show the real number.

**The owner's test (on your PC, once):**
1. Install 0.2.234 (**Update now** when the app offers it).
2. Close other programs.
3. In the app: **Fresing > Tools and checks > PC check…**, click **Stress (10 to 20 minutes)**, then **Start**.
   (Or: **Fresing > Tools and checks > Open the app folder** and double-click **PC check (stress)**.)
4. A black window opens and first says how long it takes. Leave the PC alone.
5. At the end "Fresing Render PC check.html" opens in your browser; **Fresing Render stress table.csv** is on the
   Desktop next to it.
6. In the report, at the bottom under **For the lead chat**, click **Copy** and paste the text into the lead chat.
   You should see 16 lines, every one OK (pass or slow), none FAILED.

**The model as a download:** **draft release `stress-model`** (Releases page, only visible to you), file
**FresingStressModel.zip** – unzip it and import "Fresing stress topside.step" with **1 Model > Import STEP…** (Normal:
a few minutes).

**Open points / follow-up tasks:**
- The slow places above (1–4) are candidates for their own tasks (not in this one by the brief).
- Peak memory is the app's own process only; the import's helper processes come on top (not measured).
- The Solid view line renders offscreen with Workbench (the PC check has no window), so "pictures a second" is close to
  but not the same as the 3D view's frame rate; the Live preview line is a Cycles Draft render at the preview's size.
- The limits are from the 4-core machine; after the owner's first Stress run they can be set from his numbers.
