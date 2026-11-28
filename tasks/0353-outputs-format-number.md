# 0353 – Format number on outputs (3D page, House round-trip file) + House sample re-pin to v1.0.2

**Who:** worker · **Status:** open – can start · **Branch:** `task/0353-outputs-format-number`
**Started by:** lead, 28 Nov 2026 (owner 25 Nov 22:5x: before the baseline and before the Viewer; 0352 done) ·
**Model:** Sonnet · effort Medium
**Area:** Web 3D + House lanes – the format-number spots only: `blender/web3d*.py` / `core/web3d*.py` (where the page's
data is written), the page's own reader in `fresing_render/web/`, `core/house_scene.py`, `house_import.py`,
`house_bake.py`, `ops_house.py`, `toolbox_inbox.py`, the House sample in `tests/data/` / `fresing_render/data/`, their
tests, guide lines. **Not:** the page's light / colours (0382 later), `core/compat.py` beyond reading (0352's style).

## What to do

1. **3D page:** the exported page and its data file carry a format number; the page reads older numbers and, for a
   newer one, says plainly "made by a newer Fresing Render – update to open it fully" and shows what it can.
2. **House round trip:** the bake package we send back carries our format number; the House scene we read is checked
   against what we support, with the same plain message for a newer one (agree the field with the House format – read
   the pinned spec, don't change House Planner).
3. **ToolBox inbox:** reads the numbers and passes the plain message on.
4. **Re-pin the House sample** to House Planner's tag `v1.0.2` with `example-house.hpscene` (as 0130 did for v1.0.1).
5. Same style as 0352's `core/compat` (a number + a plain line); one test per output for "older", "same", "newer".
6. The Viewer reads these later (V1): write the numbers and rules in `docs/` where the Viewer task will find them.

## Done when

- [ ] Both outputs carry the number; readers handle older / newer with tests; the re-pin done
- [ ] Tests added / updated; full suite passes (also on GitHub)
- [ ] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [ ] (Windows-only code) reviewed by a helper that did not write it
- [ ] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)

**Running beside it (weekend 28–29 Nov):** 0371 Demo · 0355 / 0356 Assets · 0372 Welds · 0347 Machining · 0349
Lifting · 0353 Web 3D + House · 0373 guide-picture tool · 0374 cable-lay line · 0375 Sea · 0377 Start & windows ·
0379 PC check · findings-only 0380 / 0381. Shared files only additively, each in its own spot: `props.py`, `tour.py`,
`core/functions.py`, `tools/guide_screens.py` (0373 owns its start-up code), `pccheck/checks.py` / `heavy.py` (0379
owns the lines it names). Whoever merges second updates its branch to `main`; versions: CLAUDE.md section 7 step 0.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
