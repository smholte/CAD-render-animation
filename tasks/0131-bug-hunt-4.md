# 0131 – Bug hunt, round 4: everything built since 0118 (findings only, no code changes)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0131-bug-hunt-4` (the report only – **do not push to
`main`**, see step 5)
**Started by:** lead chat, 15 Nov 2026 (owner: "all tasks") · **Lane:** none – reads everything, **changes no app code,
tests or tools**, so it runs next to every lane and starts **no** test run on GitHub
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation" (real Blender
at start, CLAUDE.md section 4)

## Goal

A ranked list of real problems in what was built since the third bug hunt (0118, 14 Nov, 0.2.92) – crashes, lost
work, old projects that no longer open, wrong output, slow spots, functions that fight each other – each with proof
and a suggested fix, so the lead can turn them into tasks **before** the owner hits them on his PC.

## Background

- Since 0118: **0.2.93 → 0.2.103** – "Turn it yourself" picker (0111), IEA 15 MW turbine + looks concrete / marine
  growth / run-down streaks (0116), quadrant operations + A&R / tipping wires as app cables + shots 9–12 (0082),
  bug-hunt fixes A/B/C (0119, 0120, 0121 = 0118's rows), mesh import glTF/OBJ/FBX (0117), function list + guide
  anchors (0124), nicer test models (0122), motion extras: blocked ways, riders, stacking, Back to CAD, product-video
  close-ups (0129), quadrant and sea follow-ups: settling, seabed set-down, swivels, free bend (0125), random test
  failures (0127). Each task file has its report and open points: read them first, do not re-report a known open
  point (mention it only if it is worse than the report says).
- Check that **0118's rows really are fixed** (0119–0121, 0117 row 14): one quick repeat of each row's proof.
- Read CLAUDE.md section 8 (Blender's traps found so far) and look for the same kinds of mistakes in the new code.
- **Running at the same time** (their files change tonight – look at them lightly and check each finding there against
  the newest `main` before writing it): **0128** turbine extras + ATC web model (`tools/site_projects/`,
  `site/render_kit/`, `marine_looks.py`, `site/media/`), **0126** CPS run (`demo_model/`, `demo.py`, maybe
  `paths*.py`), **0130** House format 1.0.1 (`house_*`), **0132** Motion follow-ups (`ui_motion.py` joint box,
  `sequence.py`, maybe `clash.py`).

## What to do

1. **Functions together** (the main point), on the generic test models (0122's new ones) and the demo project:
   - **Demo project** with shots 9–12: the quadrant lowered, tipped, let go on the seabed with vessel motion on, a
     weather preset, the cut-away under water, a product video, a web 3D export; save, reopen, Build again – does the
     cable, the D, the swivels, the settled sea cable or the CPS move, double or vanish?
   - **Assembly sequence + riders + Back to CAD** (0129) with a model update, a clash check, the render queue and a
     product video in the same project.
   - **Mesh import** (0117): made-up glTF/OBJ/FBX files only (made in Blender in the scratch folder – never downloaded
     manufacturer models): joints on facetted cylinders, decals, a model update from a changed file, the look "From
     file", web 3D export of a mesh project, a mix of STEP and mesh models in one project.
   - **Turbine** (0116): the stand-in conversion with weather, vessel motion off, clash check, web 3D export.
   - **Scripts off** (as 0118 did): every driver of the new data (A&R/tipping wires, swivels, riders, sequence steps,
     Back to CAD) still moves with "Auto Run Python Scripts" off.
   - **Undo / Ctrl+Z** after the new buttons (mesh import, Back to CAD step, swivel, let go, sequence preview).
   - **Function list** (0124): every entry's button, guide anchor, tour stop and PC-check line really exist and fit.
2. **Old projects:** make projects with **0.2.92, 0.2.95 and 0.2.101** (their tags; joints, a look, a decal, a
   G-code step, a cable with a sea end, a sequence step, a queued job) and open them in the newest `main`: everything
   there, nothing doubled, the queue job still renders.
3. **Slow:** ms per frame change and per redraw on the demo project (shots 9–12 with the sea end and swivels) and on
   the Heavy machine, each new per-frame feature switched on one by one; Make demo's time; the preview plan on a big
   subassembly.
4. **Prove** each finding: a short script or click test (scratch folder **outside** the repository; the few lines
   needed to repeat it go into the report). A finding that cannot be shown is *suspected*, never confirmed.
   Windows-only code: review by reading. Helper agents may read areas in parallel (at most 3, one area each, findings
   only); the main session checks every finding itself.
5. **Report** in this file, one table row per finding, worst first:
   `# · severity (crash / lost work / old project / wrong output / slow / small) · where (file:function) · what
   happens and when · proof (confirmed + how / suspected) · suggested fix in one sentence · lane · model · effort`.
   Then a short list of areas that looked sound. Group small findings (texts, tooltips) in one row.
   **Push the report to the branch `task/0131-bug-hunt-4` only.** The lead brings it to `main` and turns rows into
   tasks. Set the task to "running" in `TASKS.md` on `main` at the start (a TASKS.md-only push starts no run).

## Done when

- [ ] Step 1 combinations tried (say which were not and why); 0118's rows re-checked; old projects from 0.2.92,
      0.2.95, 0.2.101 opened; speed measured
- [ ] Findings table filled in, worst first, each confirmed with proof or marked suspected; sound areas listed
- [ ] No change to app code, tests or tools; the report pushed to `task/0131-bug-hunt-4`

## Not in this task

Fixing anything – even one-line fixes go into the report as a suggested fix. New features, the look of the UI (0062),
render quality judgements. The owner's own files (the repository is public – generic test models only). The Fresing
400 (CLAUDE.md section 6). Nothing from `smholte/house-planner-dev`.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
