# 0032 – PC check: one click tests a new version on the owner's PC

**Who:** worker · **Model:** Opus · effort Medium · **Place:** Claude Code on the web · **Status:** done (0.2.23)
**Branch:** `task/0032-pc-check`
**Started by:** lead chat, 6 Nov 2026 · **Lane:** PC check (new files `fresing_render/pccheck/`,
`tests/test_pccheck.py`; additive: one shortcut in `installer/Install-FresingRender.ps1`, one Help-menu
item in `app_template/`, one step per job in `.github/workflows/tests.yml`, `docs/USER-GUIDE.md`
troubleshooting chapter, a rule in `CLAUDE.md`). Feature modules are only *called*, not changed.

## Goal

After every update the owner runs one check on his own PC (Windows 11, 24 cores, RTX 3090) and gets a
report: does every main function still work with the test models – import, sorting, joints, couplings,
milling, surroundings, light looks, cameras, renders on the graphics card, videos, the queue – how long
each step took compared with the last run on his PC, small pictures of the renders, and the features
new in this version on top. Optionally the same on one of his own STEP files (numbers only).

## Background

- The self-test (`fresing_render/selftest.py`, Start menu "Fresing Render - Self test") checks the
  *installation*: 15 lines (STEP reader, all cores, CAD names, rule sets folder, Manifold, app start,
  update check, graphics card, import and sort, HD render on GPU, CPU render, joints + animation, MP4,
  queue, Time test). It stays as it is: quick, for "is it installed right". The PC check is the
  *feature* test; it may share helpers with it.
- GitHub tests every push on Linux (full suite, real app with clicks) and on Windows (install,
  self-test, update), but **no GitHub machine has a graphics card** and nobody uses the app on Windows
  there. The PC check is what covers the RTX 3090: GPU renders, OptiX denoise, EEVEE, render speed.
- The owner's open measurements (TASKS.md 0002: import time of a big model, animation time per frame,
  EEVEE speed on the RTX 3090) should come out of this check, so he no longer does them by hand.
- Test models: `tests/data/` (crane a/b, faces a/b, materials, machine, mill; all generic, ~0.8 MB).
  The ones the check needs ship inside the extension (`fresing_render/data/`). Never the owner's files.
- The repository is public: the report stays on his PC. What he sends back is a text block with
  numbers only – no file names, part names or pictures of his own models.

## What the check does

- **Quick** (target ≤ 3 min on his PC) and **Full** (target ≤ 15 min). Runs in a background Blender
  like the self-test, so it does not take over the screen; the report (HTML on the Desktop, like the
  self-test's) opens by itself at the end. Started from the Start menu ("Fresing Render - PC check")
  and from Help in the app.
- **Lines, one per function** (OK / FAILED with the reason / skipped with the reason), each with its
  time. Full covers at least: import + sorting (crane, faces, materials, mill), painted faces, rule-set
  switch, joints (rotate, slide, a stack), coupling + motor + Run motor step, poses, explode, saved
  scenes, model update crane A → B keeping the work, save + reopen, one offshore surrounding and one
  hall (Simple), light looks, camera views, background blur, a short turntable, milling (a few frames),
  stills Cycles on GPU and on the processor, EEVEE still, a short MP4 through the queue, Time test,
  update check (no install). Quick: import, a joint, one GPU still, one short EEVEE video.
- **Pictures checked automatically:** not black/empty, the model is in the picture, and a comparison
  with the same picture of the last run on this PC (a big difference is flagged "look at this"). Small
  pictures of the test-model renders in the report.
- **Speed against the last run on this PC:** a step more than ~25 % slower than last time is flagged
  (keep the last few runs' numbers next to the report).
- **New in this version:** every line knows the version it came in; lines new since the last run on
  this PC are shown on top. From now on each task that adds something the owner can see adds its
  line in the same task (write that rule in `CLAUDE.md` section 6).
- **His own model** (optional): a simple way to point the check at one of his STEP files (for example
  drop the file on the shortcut, or "PC check with my model…" in the app). Gives import time, parts,
  % sorted, a GPU still, Time test per frame for Preview and EEVEE – numbers only in the text block.
- **Text block for the lead chat** at the end of the report, with a Copy button: version, PC (CPU,
  GPU, driver), every line OK/FAILED/skipped with its time, flags. Nothing that names his models.

## Done when

- [x] PC check Quick and Full run from the Start-menu shortcut and from Help; the report opens by itself.
- [x] All lines above for 0.2.20's features; features of tasks merged before this one finishes get
      their lines too (0013, 0018, 0024, 0028 are running now).
- [x] Picture checks, comparison with the last run, speed flags, "new in this version" on top.
- [x] Own-model mode; text block with numbers only (a test checks that no file or part name gets in).
- [x] The check also runs on GitHub at every push (Linux real-app job and the Windows job; GPU lines
      "skipped: no graphics card"), so it cannot break unnoticed; say how many minutes it adds.
- [x] `CLAUDE.md`: the rule "a visible feature adds its PC-check line"; section 5 lists the PC check.
- [x] User guide, troubleshooting chapter: how to run it, what it shows, what to send back.
- [x] Windows-only parts (shortcut, Desktop/OneDrive path, opening the report, file drop) reviewed by a
      helper that did not write them.
- [x] Tests for the check itself (a line that fails is reported as FAILED, not a crash; comparison and
      speed flags; text block contents); full suite green on GitHub.
- [x] Version, changelog, merge, release (CLAUDE.md section 7); report below filled in.

## Not in this task

- Simulated clicks on Windows (the click tests stay on Linux/GitHub).
- Changing the self-test's lines or any feature module (if a hook is unavoidable: smallest possible,
  additive, named in the report).
- Task 0031 (Claude Code set-up) touches `CLAUDE.md` and maybe `.github/`: whoever merges second
  updates its branch to `main`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 5–6 Nov 2026 (Opus · Medium)

**What changed:**
- New `fresing_render/pccheck/`: `checks.py` (29 lines for Full, 6 for Quick, 4 more with an own model),
  `core.py` (no Blender: history of the last 5 runs per kind, speed flag >25 % and ≥1 s slower than the median of
  the last 3 runs, picture checks black / flat / model missing, picture difference vs last run (flag > 0.06),
  "new in this version", text block with numbers only (paths and part/file/user/computer names scrubbed; own-model
  lines carry numbers and the error type only), HTML report written after every line), `runner.py`, `launcher.py`,
  `ops.py` (Help > Fresing Render PC check… with Quick/Full and an optional own STEP file; on Windows makes missing
  shortcuts after an in-app update).
- Lines cover: app start, graphics card, import + sorting (crane, machine, CAD materials), painted faces, decals
  (0024), rule-set switch, joints rotate + stack, coupling + motor + Run motor, poses/explode/visibility/saved
  scenes, model update A→B, save + reopen, sea, CNC hall, light looks, views, blur + sharp spot, turntable (queue),
  milling, chips (0028), Cycles GPU HD, Cycles CPU, EEVEE time per frame at HD (queue), MP4 (queue), EEVEE video
  (queue), time test, update check. Own model: import time, parts, unique, triangles, % sorted, GPU still, time
  per frame Preview and EEVEE at HD (owner's open measurements 0002).
- Test models crane a/b, faces a, mill, decals a now ship in `fresing_render/data/` (a test keeps them equal to
  `tests/data/`).
- Shortcuts: Start menu "PC check (quick)" / "(full)", Desktop "Fresing Render - PC check" (a STEP file can be
  dropped there; the Start menu takes no files); Uninstall removes it.
- GitHub: Linux real-app job runs Full from the installed launcher (`pccheck`, MIN 29), Windows job runs Full from
  its Start-menu shortcut; both judged by `tools/ci_check_pccheck.py` (only "no graphics card" skips allowed).
  Windows job timeout 60 → 90 min.
- Hooks in other code (additive): `fresing_render/__init__.py` registers `pccheck`; nothing else in feature modules.
- CLAUDE.md: rule "a visible feature adds its PC-check line" (section 6), layout, test table, job times. User guide:
  troubleshooting chapter "The PC check", install step 5, a line under Updates.

**Tested and measured:**
- `tests/test_pccheck.py` (27 tests): failing line → FAILED not a crash, skip, needs-a-failed-line, black picture,
  picture comparison on the second run, speed flags, own-model runs compare only with the same file, text block
  without file/part/user names, report sections, shortcut quoting (also O’Brien), GitHub verdict.
- GitHub run 42131746253 (before chips): Linux PC check Full 28/28 (26 OK, 2 skipped: no graphics card; EEVEE runs
  in software there) in 6.3 min; Windows Full from the shortcut 28/28 (24 OK, 4 skipped: no graphics card) in
  4.5 min. Adds about 6 min to the Linux real-app job and 4.5 min to the Windows job.
- This machine (4 cores, no GPU, bpy module): Full in about 2.5 min. Quick + own model ran twice: second run
  compared times and pictures.
- Windows-only parts reviewed by a helper agent that did not write them: no blockers; its 4 points fixed
  (Desktop shortcut for dropping files, typographic apostrophes, .ps1 file instead of an encoded command with
  errors logged, job timeout).
- Not measured: anything on the RTX 3090 – the Quick/Full times on the owner's PC are expectations (≤3 / ≤15 min).

**Open points / follow-up tasks:**
- Owner: run "Fresing Render - PC check (full)" once after updating to 0.2.23 and paste the text block in the lead
  chat (first run = baseline; times compared from the second run on). With an own model: TASKS 0002 numbers.
- On a first run "new in this version" lists only lines of this version (no earlier run to compare with).
- Running tasks 0013, 0018 add their PC-check lines themselves (CLAUDE.md rule).
