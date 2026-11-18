# 0215 – Web 3D follow-ups: Make > 3D page has its Export again, faster panel, page cable depth (bug hunt 0209 group E)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0215-web3d-make-panel-fixes`
**Started by:** lead, 18 Nov 2026 · **Model:** Sonnet · effort Medium
**Area:** Web 3D lane – `blender/ui_web3d.py`, `blender/web3d.py`, the page's cable code only if row 30 needs it
(`web/fr_page.js`), their tests.

## Goal

Fix rows **6, 21, 30** of `tasks/0209-bug-hunt-7.md`. Row 6 first:
- **6** (since 0.2.152) Make > 3D page stops after "Include animation" with an AttributeError at every draw: no
  Surroundings / Light / Player settings and **no Export… button**, in every workspace. Add a real-app test that opens
  Make > 3D page and finds the Export button – the reason nothing caught it.
- **21** the Web 3D panel's draw takes 135–378 ms after each click / selection / frame change on the small demo
  (`marine_estimate`): cache it by what it depends on; draws ≤ 5 ms after a frame change, measured before / after.
- **30** a test_moving cable with its own depth on an animated page without vessel motion lies 0.17–0.65 m off the
  app's.

## Done when

- [ ] Each row's repeat case is a test that failed before; before / after numbers for row 21 (machine named).
- [ ] Full run green; report filled in.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
