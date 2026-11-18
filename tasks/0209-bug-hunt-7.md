# 0209 – Bug hunt round 7 (findings only): everything merged since 0.2.141 used together

**Who:** worker · **Status:** open – can start · **Branch:** none (report on `main`, touching only `tasks/` and `TASKS.md`)
**Started by:** lead chat, 18 Nov 2026 (owner: "more tasks?") · **Model:** Opus · effort High · **Place:** Claude Code on
the web, environment "CAD-render-animation". Findings only: no app code, no version, no test run of its own – it does
not count towards the four code tasks.

## Goal

Find what breaks when the functions of 0.2.142 to the newest are used together – above all the new side panel (0062),
the Fresing menu / welcome / What's new (0199), the usage tracker (0181) and the Lifting plans workspace (0191, 0201,
0204, and 0203 / 0206 / 0208 if merged when you start) – on old projects, the made demo and the test tour. Same method
as 0118 / 0131 / 0147 / 0183 (read 0183's brief and report first).

## What to look at

- Everything in `CHANGELOG.md` from 0.2.142 to the newest: carousel read (0184), smaller web files (0175), mesh update
  of moved groups (0188), Fast 3-axis hole (0186), re-bake save / undo (0187), web export 8× faster (0189), view clip
  (0193), cable routes kept + re-bake fixes (0192), layout kept on open (0198), twelve cranes (0191), the cleaner side
  panel – workspaces, Client view lock, Make, Set-up window, folded sections, section tabs (0062), sea cut-away in the
  view + faster sea change (0196, 0202), stand spot (0194), Fresing menu / welcome / What's new (0199), Lifting plan:
  place, CoG, Hook to here (0201), usage tracker: favourites bar, declutter question, My usage, profiles (0181), Make
  a crane (0204).
- Used together: every workspace (incl. Client view and an own workspace file) with every section; the Client view
  with Build, render queue, web export, model update, undo, save / reopen; a personal hide (0181) against a workspace
  and against what the project uses; What's new after an update from 0.2.141 (the update test's old build is fine);
  Lifting plans on the demo (a crane on the quay, Hook to here to a demo part, a made crane, save / reopen, model
  update of the demo, undo); the Set-up window on the second monitor stand-in (two windows) with undo and save.
- Old projects saved by 0.2.135, 0.2.145 and 0.2.151 opened in the newest version: layout, workspace, panels open,
  everything builds the same.
- 0183's rows: re-check that each fix holds (0186–0189, 0192, 0194). Open points of 0062 (end of its report) and 0201:
  note only what you see.
- Speed: side-panel redraw with all sections open on the demo, a click to select, Build, playback, a sea change –
  against 0195's numbers (`tools/measure_demo.py`; name the machine).

## Rules

Public repository (CLAUDE.md section 6). Each row: what you did, what happened, what should happen, how often, the
smallest repeat case, severity (crash / lost work / wrong result / small), the lane and a proposed task grouping (two
fix tasks never share a file). Push only `tasks/0209-bug-hunt-7.md` (+ `tasks/img/0209_*` if a picture is needed,
small) and `TASKS.md`.

## Done when

- [ ] Report: "In short (for the owner)" (≤ 8 lines), the rows, a grouping into fix tasks by lane for the lead.
- [ ] Pushed to `main` touching only `tasks/` and `TASKS.md`; then check that main really contains your commit.

---

## Report (filled in by the chat that did the task)

**Chat / date:**
