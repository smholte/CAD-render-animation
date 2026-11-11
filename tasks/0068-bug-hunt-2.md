# 0068 – Bug hunt, round 2: everything built since 0045 (findings only, no code changes)

**Who:** worker · **Status:** open – start now (Wed 11 Nov, overnight) · **Branch:** `task/0068-bug-hunt-2` (the
report only – **do not push to `main`**, see step 5)
**Started by:** lead chat, 11 Nov 2026 · **Lane:** none – reads everything, **changes no app code, tests or tools**,
so it runs next to every lane
**Model:** **Opus · effort High** · **Environment:** "CAD-render-animation" (real Blender at start, CLAUDE.md section 4)

## Goal

A ranked list of real problems in the functions built since the first bug hunt (0045, 9 Nov, 0.2.34–0.2.38) – crashes,
lost work, old projects that no longer open, wrong output, slow spots, functions that fight each other – each with
proof and a suggested fix, so the lead can turn them into tasks **before** the owner hits them on his PC.

## Background

- Newest release **0.2.53**. Since 0045, these went in (task files have the details and each report's open points):
  0040/0049 tool library, 0041 tool changes + carousel ATC, 0042 coolant, 0046 better materials, 0050 Start later,
  0051 cut-face look, 0052 model update keeps everything, 0053 safe updates + project lock, 0054 queue fixes,
  0055/0056 Looks fixes + same STEP twice, 0059 test tour, 0060 small fixes, 0064 double-arm changer, 0065 clash
  check, 0066 rotary axes A/B/C. Each was tested on its own; **few were tested together.**
- Read CLAUDE.md section 8 (Blender's traps found so far) first, then look for the same kinds of mistakes in the new code.
- Running at the same time: **0029** app-made toolpath (`core/toolpath.py`, `blender/toolpath.py`, `ops_toolpath.py`,
  `ui_machining.py`, a few lines in `ops_gcode.py`) and **0067** clash follow-ups (`clash*.py`, test-model makers
  `make_test_atc/gantry/linkage.py`, CI groups). Those files will change: look at them lightly, and before writing the
  report check each finding in them against the newest `main` (`git pull`).

## What to do

1. **Functions together** (the main point of this round) – on the generic test models, in one project each:
   - The test mill: G-code with **tool changes** (manual, carousel, double arm) **+ coolant + air + chips + cut-face
     look + Fit into + ATC speed**; then a model update (0052), save/reopen, Start later in the queue (0050), and a
     queued MP4 render of part of it (Draft) – does the video match the view (tools held, chips, wet sheen, hoses)?
   - The 4-axis and 5-axis models (0066) with coolant, chips, a tool change and the clash check (0065).
   - Same STEP twice (0056) + joints + clash check + model update. A rule-set switch (0015) on a project with decals
     and painted faces.
   - Undo / Ctrl+Z after each of the new buttons (Click the hub, Click the hinge, Check, Check for clashes, rotary
     Check, Make tool list) – crash or a half-done state?
2. **Old projects:** make a project with **0.2.34, 0.2.45 and 0.2.50** (release zips on GitHub, or check out the tag;
   joints, a group look, a decal, a G-code step with a tool change, a queued job) and open it in 0.2.53: everything
   there, nothing doubled, the queue job still renders.
3. **Slow:** the new per-frame work (tool copies, double-arm visibility keys, rotary samples, coolant, clash markers)
   on the generated Heavy machine (`pccheck/heavy_scene.py`, ~3,000 parts) – ms per frame before/after switching
   each one on; anything at every redraw.
4. **Prove** each finding: a short script or click test (keep these in a scratch folder **outside** the repository;
   put the few lines needed to repeat it in the report). A finding that cannot be shown is *suspected*, never
   confirmed. Windows-only code (project lock, safe updates): review by reading. Helper agents may read areas in
   parallel (at most 4, one area each, findings only); the main session checks every finding itself.
5. **Report** in this file (below), one table row per finding, worst first:
   `# · severity (crash / lost work / old project / wrong output / slow / small) · where (file:function) · what
   happens and when · proof (confirmed + how / suspected) · suggested fix in one sentence · lane · model · effort`.
   Then a short list of areas that looked sound. Group small findings (texts, tooltips) in one row.
   **Push the report to the branch `task/0068-bug-hunt-2` only** (two workers will be fast-forwarding `main`
   tonight; a push to `main` in between would block them). The lead brings the report to `main`.

## Done when

- [ ] Every combination in step 1 tried; old projects from 0.2.34, 0.2.45 and 0.2.50 opened; Heavy measured.
- [ ] Findings table filled in, worst first, each confirmed with proof or marked suspected; sound areas listed.
- [ ] No change to app code, tests or tools; the report pushed to `task/0068-bug-hunt-2`.

## Not in this task

Fixing anything – even one-line fixes go into the report as a suggested fix. New features, the look of the UI (0062),
render quality. The owner's own STEP files and projects (the repository is public – generic test models only).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings:**

**Areas that looked sound:**
