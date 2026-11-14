# 0118 – Bug hunt, round 3: everything built since 0068 (findings only, no code changes)

**Who:** worker · **Status:** running · **Branch:** `task/0118-bug-hunt-3` (the report only – **do not push to
`main`**, see step 5)
**Started by:** lead chat, 14 Nov 2026 · **Lane:** none – reads everything, **changes no app code, tests or tools**,
so it runs next to every lane and starts **no** test run on GitHub
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation" (real Blender
at start, CLAUDE.md section 4)

## Goal

A ranked list of real problems in what was built since the second bug hunt (0068, 11 Nov, 0.2.53) – crashes, lost
work, old projects that no longer open, wrong output, slow spots, functions that fight each other – each with proof
and a suggested fix, so the lead can turn them into tasks **before** the owner hits them on his PC.

## Background

- Since 0068 about forty versions went in, **0.2.54 → 0.2.92**, many on the same day and each tested on its own:
  clash follow-ups and speed (0067, 0072, 0092, 0110), app-made toolpath (0029), machining fixes and tool marks (0071,
  0061, 0096, 0098, 0103 cycle time), Fade / X-ray / trails (0073), facets by size + paint schemes (0074), vessel motion
  (0085), cutaway (0086), camera rides (0087), hover pickers (0088/0089), way covers (0035/0090), joints in a batch
  (0093), the demo project and its stages (0077, 0091, 0095, 0097, 0102), hoses/cables/drag chains (0058), cable paths
  (0078), spooling (0080), tracks (0079), into the sea + riders (0081), assembly sequence (0100), product video (0101),
  web 3D model, smaller files, surroundings, baked light (0099, 0105, 0106, 0107), weather and time of day (0109), House
  import + bake (0114), the render kit with motion (0112). Each task file has its report and open points: read them
  first, do not re-report a known open point (mention it only if it is worse than the report says).
- Read CLAUDE.md section 8 (Blender's traps found so far) and look for the same kinds of mistakes in the new code.
- **Running at the same time** (their files change tonight – look at them lightly and check each finding there
  against the newest `main` before writing it): **0116** turbine (`tools/site_projects/`, `site/render_kit/`, maybe
  `materials_lib.py`), **0082** quadrant (`paths*.py`, `demo.py`, wake in the weather/sea code), **0117** mesh import
  (`importer/`, `ops_import.py`, `build.py`, `faces.py`), **0111** picker (`site/`, `web3d*`).

## What to do

1. **Functions together** (the main point), on the generic test models and the demo project:
   - **Demo project** (Help > Make demo project, Blender as a module or the real app): the whole animation with vessel
     motion on, the weather presets (rain, snow, night), the cut-away under water, a product video, the clash check,
     a web 3D export with surroundings and baked light; save, reopen, Build again – does anything move, double or
     vanish (cable payout, spool layers, track pads, riders, the sea end, seabed)?
   - **Model update** (0052) on projects that use the new kinds of data: a cable with contacts + sea end + riders, a
     spool, a track, a hose, a way cover, an assembly sequence step, decals, a cutaway, a camera ride: all kept, none
     doubled, warnings honest.
   - **Scripts off** ("Auto Run Python Scripts" off, real Blender with `-Y` and the control driver of
     `tools/coupling_check_noscripts.py`): do the new drivers (cables, spools, tracks, weather, vessel motion, riders)
     still move? Any Python driver that slipped in?
   - **The render queue** (background Blender) for a job with weather + vessel motion + a cable in the sea + tracks:
     does the video match the view? Start later; a paint-scheme job (0074).
   - **Undo / Ctrl+Z** after the new buttons (Add cable, Into the sea, Add track, Add spool, Bake light, Make product
     video, House import/bake, Check for clashes) – crash or half-done state?
   - **House import** (0114) with odd but valid `.hpscene` samples from `smholte/house-scene-format` only (never
     `house-planner-dev`).
2. **Old projects:** make projects with **0.2.53, 0.2.70 and 0.2.85** (release zips on GitHub or the tags; joints,
   a look, a decal, a G-code step, a cable, a queued job) and open them in 0.2.92: everything there, nothing doubled,
   the queue job still renders.
3. **Slow:** ms per frame change and per redraw on the demo project and on the Heavy machine
   (`pccheck/heavy_scene.py`) with each new per-frame feature switched on one by one; side-panel redraw time with the
   demo open (anything walking the whole scene at every redraw – CLAUDE.md section 8, `logic.Tree`).
4. **Prove** each finding: a short script or click test (scratch folder **outside** the repository; the few lines
   needed to repeat it go into the report). A finding that cannot be shown is *suspected*, never confirmed.
   Windows-only code: review by reading. Helper agents may read areas in parallel (at most 3, one area each, findings
   only); the main session checks every finding itself.
5. **Report** in this file, one table row per finding, worst first:
   `# · severity (crash / lost work / old project / wrong output / slow / small) · where (file:function) · what
   happens and when · proof (confirmed + how / suspected) · suggested fix in one sentence · lane · model · effort`.
   Then a short list of areas that looked sound. Group small findings (texts, tooltips) in one row.
   **Push the report to the branch `task/0118-bug-hunt-3` only** (several workers fast-forward `main` tonight). The
   lead brings it to `main` and turns rows into tasks.

## Done when

- [ ] Step 1 combinations tried (say which were not and why); old projects from 0.2.53, 0.2.70, 0.2.85 opened; speed measured
- [ ] Findings table filled in, worst first, each confirmed with proof or marked suspected; sound areas listed
- [ ] No change to app code, tests or tools; the report pushed to `task/0118-bug-hunt-3`

## Not in this task

Fixing anything – even one-line fixes go into the report as a suggested fix. New features, the look of the UI (0062),
render quality judgements. The owner's own files (the repository is public – generic test models only). The Fresing
400 (CLAUDE.md section 6).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings** (worst first):

**Areas that looked sound:**
