# 0250 – The double-arm ATC mill and the 4th- / 5th-axis mills rebuilt on 0249's larger VMC

**Who:** worker · **Status:** open – waits for 0249 · **Branch:** `task/0250-larger-atc-rotary-mills`
**Started by:** lead, 20 Nov 2026 (owner 23:35 / 23:40 – all small mills replaced, see 0249) ·
**Model:** Opus · effort High
**Area:** Test models lane – `tools/make_test_atc.py`, `tools/make_test_4axis.py`, `tools/make_test_5axis.py`,
`tools/machine_parts.py` (reuse 0249's machine), their STEP files in `tests/data/` and `fresing_render/data/`; the tour
sets `atc` only where it uses these models, `doublearm`, `rotary4`, `rotary5` in `blender/tour.py`; `blender/doublearm.py`,
`blender/rotary.py`, `blender/toolpath.py` only where they hold these models' numbers; `pccheck/checks.py` (their lines);
`tools/make_site_web_models.py` and the **landing page's web model** if it is one of these; `tools/guide_screens.py` + the
guide pictures and texts of these stops; tests: `test_doublearm`, `test_rotary`, `test_toolmarks_done`,
`test_machining_fixes`, `test_pccheck`, `tools/ui_test_doublearm.py` (check with a grep – this list is the lead's).
**Not** the gantry router (`test_gantry.step`), not 0249's models.

## Why

Same as 0249: the **Fresing 400** (a mill of about today's test mills' size, with a **double-arm tool changer and BT30
holders**) is not to be shown in any form. Today's `test_atc.step` – a small vertical mill with a double-arm changer –
is the closest of all; it goes first in this task.

## What to build

- **Double-arm ATC mill:** 0249's VMC (~1000 × 500 × 500 travel, BT40) with a double-arm tool changer and a
  **side-mounted chain or disc magazine of 24 pockets or more** beside the column (a common big-VMC layout, unlike a
  small mill's) – invented, no maker look. Keep the joints, part names and the tool-change sequence the app and tests
  read (`doublearm.py`); new numbers for the reach, swing and times where the bigger machine needs them.
- **4th axis:** the same VMC with a rotary table (A axis) and a tailstock on its table, sized for it (faceplate
  Ø200–250).
- **5th axis:** the same VMC with a trunnion (A tilts, C turns) on its table (table Ø200–320) – or a larger 5-axis
  layout if it reads better; keep the TCP stop (63) working.
- Workpieces, tools and programs kept where possible (same rule as 0249: work zero in the same place relative to the
  stock).
- Up to about 4 MB per STEP; the site's web model (if it is one of these) kept small enough for the page (report its
  size and load time before / after).
- Old copies: from now on only (old releases and history stay).

## Checks

- Every test above green; changed numbers listed with the reason.
- Stops 60–63 (tool changer, double-arm, 4th axis, 5th axis TCP) played through: no clashes, the tool change times
  shown match the bigger arm, the TCP keeps the tool tip on the part.
- Guide pictures and texts of these stops re-made; PC-check lines updated; `tour_versions` re-recorded after merging
  `main` once.
- A search for the small mills' sizes / names in pictures and texts comes back empty (except `tasks/` and
  `CHANGELOG.md`).

## Report

Pictures from the test models, STEP sizes, import times, the web model's size if changed, changed numbers, open points,
the branch to delete. Owner's PC steps: test tour > Machining > 60–63, Go; the landing page's 3D model if changed.
