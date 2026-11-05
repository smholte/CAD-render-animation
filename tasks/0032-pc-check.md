# 0032 – PC check: one click tests a new version on the owner's PC

**Who:** worker · **Model:** Opus · effort Medium · **Place:** Claude Code on the web · **Status:** open – can start
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

- [ ] PC check Quick and Full run from the Start-menu shortcut and from Help; the report opens by itself.
- [ ] All lines above for 0.2.20's features; features of tasks merged before this one finishes get
      their lines too (0013, 0018, 0024, 0028 are running now).
- [ ] Picture checks, comparison with the last run, speed flags, "new in this version" on top.
- [ ] Own-model mode; text block with numbers only (a test checks that no file or part name gets in).
- [ ] The check also runs on GitHub at every push (Linux real-app job and the Windows job; GPU lines
      "skipped: no graphics card"), so it cannot break unnoticed; say how many minutes it adds.
- [ ] `CLAUDE.md`: the rule "a visible feature adds its PC-check line"; section 5 lists the PC check.
- [ ] User guide, troubleshooting chapter: how to run it, what it shows, what to send back.
- [ ] Windows-only parts (shortcut, Desktop/OneDrive path, opening the report, file drop) reviewed by a
      helper that did not write them.
- [ ] Tests for the check itself (a line that fails is reported as FAILED, not a crash; comparison and
      speed flags; text block contents); full suite green on GitHub.
- [ ] Version, changelog, merge, release (CLAUDE.md section 7); report below filled in.

## Not in this task

- Simulated clicks on Windows (the click tests stay on Linux/GitHub).
- Changing the self-test's lines or any feature module (if a hook is unavoidable: smallest possible,
  additive, named in the report).
- Task 0031 (Claude Code set-up) touches `CLAUDE.md` and maybe `.github/`: whoever merges second
  updates its branch to `main`.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
