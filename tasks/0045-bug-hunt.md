# 0045 – Bug hunt across the whole app (findings only, no code changes)

**Who:** worker · **Status:** open – can start · **Branch:** none – the report goes to `main` (task files only)
**Started by:** lead chat, 8 Nov 2026 · **Lane:** none – reads everything, **changes no app code**, so it runs next to
every lane
**Model:** Opus · effort High · **Environment:** "CAD-render-animation" (real Blender at start, CLAUDE.md section 4)

## Goal

A ranked list of real problems in Fresing Render – crashes, lost work, old projects that no longer open, wrong
output, slow spots – each with proof and a suggested fix, so the lead can turn them into tasks **before** the owner
hits them on his PC (like the milling crash at the end of a 2-hour 4K render, 0037/0038).

## Background

- 0.2.34 on `main`, ~47,000 lines of Python in `fresing_render/`, 1,360+ tests, GitHub runs everything at every push.
  The tests prove what each task thought of; this task looks for what nobody thought of.
- Crashes found so far all came from Blender itself misbehaving, not from Python errors: arrays of another length in
  ID properties (0038), undo after a scripted Build (CLAUDE.md section 8), drivers read one update late (0012), stale
  references to collection items (0034). Section 8 of CLAUDE.md lists them all: **read it first**, then look for
  other places in the code where the same kind of mistake is still possible.
- The owner works with big models (2,800 parts), long queued 4K renders (500 frames, 2+ hours), projects that he
  keeps for weeks and opens in newer versions, and a shared project folder (`project_lock.py`).
- Running at the same time: **0040** tool library (`core/gcode.py`, `blender/gcode.py`, `ui_gcode.py`,
  `machining.py`, `chips.py`), **0043** surroundings re-lay + MP4 encode (`blender/surroundings.py`, `queue.py`
  encode, `video.py`), **0044** guide pictures (`docs/`). Those files will change: look at them lightly, and before
  writing the report check each finding in them against the newest `main` (`git pull`).

## What to do

1. **Read** the code area by area: importer + model update (`importer/`, `reimport.py`, `build.py`), project
   load/save and upgrades of old data (`handlers.py` load_post, every `upgrade_*`), joints / cylinders / mechanisms /
   way covers, animation bake and render queue (`animation.py`, `queue.py`, `queue_runner.py`), milling / chips /
   air, video finishing and labels, updates and the update helper, PC check, the UI's redraw code (`ui*.py`,
   `UIList.filter_items`, handlers that run every frame or every redraw).
   Helper agents may read areas in parallel (at most 4, one area each, findings only); the main session checks
   every finding itself before it goes in the report.
2. **Look for**, in this order of importance:
   - **Crashes and hangs** of Blender (memory, handlers, undo, timers, threads, files closed while a job runs).
   - **Lost work:** an action that silently drops joints, groups, looks, decals, animation steps or queue jobs;
     model update or save/reopen that loses something; the project lock left behind.
   - **Old projects:** make a project with an older version and open it in 0.2.34 – at least 0.2.20 and 0.2.30, with
     joints, a group look, a decal, an animation and a queued job. Old versions: the release zips on GitHub
     (v0.2.16 and newer), or check out the tag and build it (`tools/build_release.py`).
   - **Wrong output:** a render or video that differs from what the view shows (hidden parts, camera, finishing).
   - **Slow:** anything that grows faster than the model (a loop over all parts inside a loop over all parts, work
     at every redraw). Measure on the generated Heavy machine (`pccheck/heavy_scene.py`, ~3,000 parts).
   - **Windows-only code** (paths with spaces/accents, long paths, subprocess flags, the update helper): review by
     reading; it cannot run here.
3. **Prove** each finding: a short script or click test that shows it (keep these in a scratch folder **outside**
   the repository; put the few lines needed to repeat it in the report). A finding that cannot be shown is listed as
   *suspected*, never as confirmed.
4. **Report** in this file (below), one table row per finding, worst first:
   `# · severity (crash / lost work / old project / wrong output / slow / small) · where (file:function) · what
   happens and when · proof (confirmed + how / suspected) · suggested fix in one sentence · lane · model · effort`.
   Then a short list of areas that looked sound. Group small findings (texts, tooltips) in one row.
5. Commit only this file and `TASKS.md` (status running → done) to `main`: task-file-only pushes start no test run.

## Done when

- [ ] Every area in step 1 read; old projects from at least two versions opened; the Heavy machine measured.
- [ ] Findings table filled in, worst first, each one confirmed with proof or marked suspected; areas that looked
      sound listed.
- [ ] No change to app code, tests or tools in the repository (the lead turns findings into tasks).
- [ ] `TASKS.md`: 0045 done; findings named under "Problems found, waiting for a task" as one line pointing here.

## Not in this task

Fixing anything – even one-line fixes go into the report as a suggested fix. New features, look of the UI, render
quality. The owner's own STEP files and projects (not attached; the repository is public – generic test models only).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings:**

**Areas that looked sound:**

**Tested and measured** (name the machine and the model):

**Open points:**
