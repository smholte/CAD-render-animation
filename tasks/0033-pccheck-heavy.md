# 0033 – PC check "Heavy": longer, bigger tests that really load the owner's PC

**Who:** worker · **Model:** Sonnet · effort Medium · **Place:** Claude Code on the web · **Status:** open – can start
**Branch:** `task/0033-pccheck-heavy`
**Started by:** lead chat, 6 Nov 2026 · **Lane:** PC check (`fresing_render/pccheck/`, `tests/test_pccheck.py`;
additive: a Start-menu shortcut, a Help-menu choice, one CI step). Feature modules are only *called*.

## Goal

The owner's first Full run (0.2.26, RTX 3090, 24 cores) passed 32 lines in **46 seconds**. That proves the
functions work, but not how the app behaves under real load: the test renders are tiny (12 parts, 3–6 frames,
0.3 s per frame), so nothing about big models, long animations, real quality or memory shows. He wants a check
that shows **more in the renders and the animation video** and takes **longer** (target 10–20 minutes on his PC)
– as a new mode next to Quick and Full, started on purpose. GitHub's runners (no graphics card) and a small
test machine cannot run it at full size, so it must also run in a **scaled-down form** (same lines, tiny sizes)
that GitHub runs at every push, so the lines cannot break unnoticed.

## Background

- Read `tasks/0032-pc-check.md` (report) and `fresing_render/pccheck/` first: `checks.py` (the lines),
  `core.py` (history, speed/picture flags, text block, HTML report), `runner.py`, `launcher.py`, `ops.py`.
  CLAUDE.md section 6 has the rule for lines.
- Owner's numbers from 0.2.26 Full: GPU still HD (Cycles) 3.3 s; EEVEE 0.4 s per frame at HD; Cycles time test
  0.4 s per frame at 540×540; turntable 0.3 s per frame; import of the 12-part crane 1.2 s. His earlier real
  animation: 236 frames at 2560×1440, Preview, about 15 s per frame (3 Nov, before the speed-ups).
- The repository is public: **no owner files, and no big model files in the repository.** Big test scenes are
  *made at run time* by a generator (see 1).
- Real-app clicks are not needed here (they stay on Linux/GitHub); the lines call the same functions as the
  existing ones.

## What to build

1. **Mode "Heavy"** (Start menu "Fresing Render - PC check (heavy)", Help > PC check…, Desktop shortcut as for
   the others). Own history per mode, as Quick and Full have. A progress line in the report while it runs
   (which line, elapsed, expected), and **Cancel** that keeps the finished lines in the report. Target
   10–20 min on the owner's PC (an expectation – measure on his PC in round 1, see "Two rounds").
2. **A big generated scene** (no file in the repo): a generator that writes a STEP of an invented machine with
   about 3,000 placed / 600 unique parts and about 3–4 M triangles, with generic names, nested subassemblies and
   many fasteners (ideally from OpenCascade in the bundled OCP, `STEPControl_Writer`; if that is not possible
   in the installed app, build the scene directly in Blender and say so in the report). It is written to a
   temporary folder and deleted at the end. Lines: import time on all cores (and the second import from the
   cache), build + sort, tree/search/show-only speed, explode, a pose, save + reopen time and file size,
   **peak memory** (Windows: `GetProcessMemoryInfo` via ctypes – Windows-only code, get it reviewed).
3. **Real renders, not tiny ones:** Cycles stills at 1920×1080 and 3840×2160 on the graphics card, in Preview
   and Normal quality, with time per picture; EEVEE at HD and 4K; the CNC hall and the open sea in **Detailed**
   at HD; the big scene from a 3/4 hero view. Pictures larger in the report (not thumbnails), with the settings
   under each.
4. **A real animation:** about 10 s (250 frames) with several steps (a joint, a cylinder, a mechanism, a motor)
   rendered **fully** through the queue to an MP4 at 1920×1080 EEVEE, and a shorter Cycles Preview clip (about
   3 s). Checks: frame count and length match, the file opens and has the right size/duration, first and last
   frame **differ** (motion visible), no black/flat frames, time per frame and total, queue overhead. In the
   report: a **contact sheet** (6–8 frames across the video, side by side) and the last frame.
5. **Milling with chips at length:** the mill program of 0027/0028 for 100+ frames with chips Realistic: time to
   work out, time per frame with and without chips, workpiece face count.
6. **Playback speed under load:** 250 frames of the animation scrubbed with all mechanisms/cylinders/couplings
   in the scene: ms per frame (the existing core numbers are 0.03–0.09 ms; flag a big jump).
7. **Report additions:** under every Heavy line one sentence "what this shows" and one "what it does not show"
   (for example: GPU memory use, the owner's own parts). Heavy lines with their sizes in the text block
   (numbers only, as before). Speed flags and picture comparison against the last Heavy run as for the others.
8. **Scaled-down form for GitHub and small machines:** an environment switch (like `FRESING_SELFTEST_NO_GPU`)
   shrinks every Heavy size (a few hundred parts, 12 frames, 480×270) and turns the graphics-card lines into
   "skipped: no graphics card"; the Linux real-app job and the Windows job run it. Say in the report how many
   minutes it adds (aim: ≤ 3 minutes on the Linux job). `tools/ci_check_pccheck.py` knows the Heavy line count.
9. CLAUDE.md (section 3 layout, section 5 table, the rule in section 6 gets a line for Heavy: a task with a
   visible, load-sensitive feature adds a Heavy line too), user guide troubleshooting chapter "The PC check"
   (what Heavy is, how long, how to cancel), `README-install.txt`, CHANGELOG, version bump.

## Two rounds (the owner offered to run the check while this is built)

- **Round 1 (merge and release first):** Heavy mode with the big generated scene, the 4K stills and the
  10 s EEVEE video, with sizes you chose from the 2-core/4-core numbers. Release it (CLAUDE.md section 7) and tell
  the owner (in the chat) to update and run **PC check (heavy)** and paste the text block.
- **Round 2:** from his real timings set the sizes so Heavy takes 10–20 minutes, add the remaining lines
  (Detailed halls, milling at length, playback under load, own-model Heavy), fix what his run showed. Release
  again. If the owner is not in the chat, finish round 2 with the sizes you have and say plainly that they are
  not tuned to his PC.

## Done when

- [ ] Heavy mode runs from the Start menu / Help / Desktop shortcut, shows progress, can be cancelled, report opens.
- [ ] Lines 2–6 above work; each has "shows / does not show" in the report; text block numbers only (a test checks).
- [ ] The scaled-down form runs on GitHub (Linux and Windows jobs) and is judged by `ci_check_pccheck.py`.
- [ ] Round 1 released and run by the owner; round 2 done or its state written in the report.
- [ ] Tests for the new core parts (history per mode, flags, contact sheet, text block, scaled-down sizes); full suite green on GitHub.
- [ ] Windows-only code (memory reading, shortcut, temp folders) reviewed by a helper that did not write it.
- [ ] Guide, CLAUDE.md, CHANGELOG, report filled in.

## Not in this task

- Simulated clicks on Windows; changes to feature modules (smallest additive hook only, named in the report).
- Task 0031 (Claude Code set-up) and 0034 (way covers, own files): whoever merges second updates its branch to `main`.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
