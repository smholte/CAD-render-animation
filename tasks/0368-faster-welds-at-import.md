# 0368 – Faster welds at import and model update + the square groove with a root gap (0323's open points)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0368-faster-welds-at-import`
**Started by:** lead, 25 Nov 2026 23:5x (owner allowed extra code tasks for the night; 0323's open points)
· **Model:** Opus · effort Medium
**Area:** Welds lane – `core/welds.py`, `core/weld_cad.py`, `blender/welds.py`, `blender/weld_cad.py`,
`tools/make_test_weldment.py` (+ the CAD-weld test makers), their tests, the welds tour set, CHANGELOG. Small extras,
own spots only:
- `tools/guide_screens.py`: the `welds_panel` / `weld_cad_panel` modes.
- `blender/tour.py`: the welds set's stop camera.

0348 also edits both of these files in other places – whoever merges second updates its branch.

**Not:**
- `blender/weld_looks.py`'s look: the bead's colour / ripples / heat tint stay as they look today.
- `blender/welds.py`'s `web_objects`: 0369 runs beside you and exports the welds to the 3D page.
- **Keep the weld objects, their material slots, the UV layer `fr_weld` and the heat-zone strips' material names as
  today** – 0369 reads them.
- `ops_import.py` / `reimport.py` beyond the existing weld calls (0340 starts there on Monday).
- `pccheck/checks.py` existing lines (0348) – a new line is fine as a function of your own.
- Painted welds on a part with painted faces (0319's point: they take the part's main paint) → after 0340, which changes
  how painted faces come in.
- AP242 weld PMI (owner decides later).

## Goal

A welded frame with hundreds of welds imports and updates without the long wait. A square butt groove with a root gap
in the CAD file is found as a butt weld.

## Background (0323's report, `tasks/0323-*.md` on `main`)

- **Import time, 300-weld frame** (`--heavy 100 --beads`, 301 parts, Normal, 4-core web machine): 1.0 s without the welds
  → 32 s with them. 30.3 s go to finding and making 300 welds (~0.1 s per weld), about half of it 0319's heat-zone
  strips (`core/welds.py` `_heat` / `_heat_rows`). Proposed: share the heat-zone work, or do the welds' pure-Python part
  (no Blender: `core/welds.py`, `core/weld_cad.py`) in helper processes, as the importer does.
- Not found: a square groove with a root gap. There is no common edge, so the finder sees no corner. When named it comes
  in as OTHER (own shape only), and it is not found by shape.
- The Welds panel's guide pictures are wrong since 0319: `tools/guide_screens.py welds_panel` grabs the 3D view's toolbar
  ("Active Tool") instead of the side panel (`docs/img/panel_3_welds.png`); the CAD section has no picture.
- The tour stop's camera frames both weldments (the close camera fits wider than asked).

## What to do

1. **Profile first** one import of the 300-weld frame and one model update of it (`find_again`, `carry_over`): finding,
   bead mesh, heat zone, Blender objects. Put the split in the report.
2. Make it faster: share the heat-zone work, reuse what repeats, and move the pure-Python work into helper processes if
   the profile says it pays off. A model update re-does only the welds whose parts changed (check what it does today).
3. The square groove with a root gap (a few mm, no common edge): found by its shape and from the CAD file as a butt weld
   (BUTT) with its gap. Add it to the test weldment / the CAD-weld test files.
4. The two guide pictures (panel 3 Looks > Welds, and the "From the CAD file" section) show the side panel. The tour
   stop's close camera frames the asked weldment only.

## Done when

- [ ] 300-weld frame: the welds take **≤ about 10 s** at import on the web machine (was 30.3 s). Model update measured
      before / after. The profile split before / after is in the report.
- [ ] The same welds as before: the existing weld tests and the 0323 CAD tests stay green. The 6-weld frame and the tour
      set give the same welds and looks (a picture before / after in the report).
- [ ] A square groove with a root gap is found by shape and from the CAD file as BUTT – a new test each.
- [ ] Guide pictures right; tour set `changed=` raised if the stop changed (`tools/tour_versions.py --record`).
- [ ] Tests added / updated; full suite passes; GitHub run green; CHANGELOG.
- [ ] Report filled in, merged, released.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
