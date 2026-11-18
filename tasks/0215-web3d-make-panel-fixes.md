# 0215 – Web 3D follow-ups: Make > 3D page has its Export again, faster panel, page cable depth (bug hunt 0209 group E)

**Who:** worker · **Status:** done (0.2.165) · **Branch:** `task/0215-web3d-make-panel-fixes`
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

- [x] Each row's repeat case is a test that failed before; before / after numbers for row 21 (machine named).
- [x] Full run green; report filled in.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 18 Nov 2026

**What changed:** Row 6: `ui_web3d.py`'s three folds (Surroundings, Light, On the page) are module functions, so the Make popover (whose `self` is the popover) draws them and the Export… button. Row 21: `web3d._mesh_area` keeps a mesh's world area by mesh, counts, a sum of its points and the matrix's shape; the estimate no longer reads every mesh after each click / selection / frame change. Row 30: `SeaRest` takes each sea cable's own bottom (`paths_sea.bottom_z`) instead of the sea's seabed.

**Tested and measured** (4-core web machine): new real-app checks in `ui_test_panel.py` (Make > 3D page draws, has Export…; 37/39 before the fix, 39/39 after); `test_marine_estimate_reads_each_mesh_once`; `test_a_cable_with_its_own_depth_lies_on_its_own_bottom` (0.40 m off before, < 0.06 m after). Row 21 timing, `marine_estimate` after a scene change on a synthetic 69-part scene (not the small demo, which was not made): 222 ms before, 12 ms after – not the 5 ms asked; what is left is the per-part walk (`needs_own_bake`, `own_share_key`, the point sum). Runs: 3 (a lane-plan test failed because the new real-app step named the web 3D module; a version clash with 0213 → 0.2.165).

**Open points / follow-up tasks:** Row 21's remaining ~12 ms (per-part walk) and a measurement on the small demo itself. No subagents, no independent review (no Windows code).
