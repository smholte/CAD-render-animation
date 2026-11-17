# 0183 – Bug hunt round 6 (findings only): everything merged since 0.2.114 used together

**Who:** worker · **Status:** running (17 Nov) · **Branch:** none (report on `main`, touching only `tasks/`)
**Started by:** lead chat, 17 Nov 2026 (plan before 0062) · **Model:** Opus · effort High · **Place:** Claude Code on
the web, environment "CAD-render-animation". Findings only: no app code, no version, no test run of its own.

## Goal

Find what breaks when the functions of 0.2.115–0.2.141 are used together, on old projects and on the made demo, before
the big side-panel task 0062 moves every panel. Same method as 0118 / 0131 / 0147 (read their briefs and reports).

## What to look at

- Everything in `CHANGELOG.md` from 0.2.115 to the newest: seabed cut (0148), height-map cutter + follow-ups (0146,
  0167), served cable + spiral bands (0158, 0164), full carousel and full spools + winch wires (0159, 0174), Flex
  follow-ups (0160, 0172), vessel details and water effects (0153, 0154), web export fixes, marine detail, page under
  the sea, web part tools, web player on a phone (0161, 0165, 0143, 0135, 0179), props and people, paths and actions, a
  person changes the tool (0155, 0157, 0156), wind park (0166), demo realism with label fields, ROV and tipping winches
  (0173), logo watermark + brand kit, app icon, Task Manager name (0176, 0169, 0178).
- Used together: Build → model update → re-bake → undo; save / reopen; render queue and every-paint-scheme videos;
  web export of the demo with people, ROV, labels and the sea cut-away; scripts off; the test tour.
- Old projects saved by 0.2.114, 0.2.125 and 0.2.135 opened in the newest version.
- 0147's rows: re-check that each fix holds. The tour stop `spool` that fails at random on GitHub is task 0184 – note
  only what you see.
- Speed: Build, playback and a web export of the demo against the numbers in the reports (name the machine).

## Rules

Public repository (CLAUDE.md section 6). Each row: what you did, what happened, what should happen, how often, the
smallest repeat case, severity (crash / lost work / wrong result / small), the lane and a proposed task grouping.
Push only `tasks/0183-bug-hunt-6.md` (+ `tasks/img/0183_*` if a picture is needed, small) and `TASKS.md`.

## Done when

- [ ] Report: "In short (for the owner)" (≤ 8 lines), the rows, a grouping into fix tasks by lane for the lead.
- [ ] Pushed to `main` touching only `tasks/` and `TASKS.md`; then check that main really contains your commit.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
