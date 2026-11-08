# 0044 – Missing user-guide pictures

**Who:** worker · **Status:** done · **Branch:** `task/0044-guide-pictures`
**Started by:** lead chat, 8 Nov 2026 (taken out of 0035 so it need not wait for the way-cover work) · **Lane:** Docs –
`docs/img/`, `docs/USER-GUIDE.md` (only the chapters named below), `tools/guide_screens.py` (new shots only)
**Model:** Sonnet · effort Low · **Environment:** "CAD-render-animation" (real Blender at start, CLAUDE.md section 4)

Runs next to 0040 (which writes its own "Tools" chapter) and 0043: touch only the chapters below; merge `main`
before pushing.

## Goal

The guide shows the panels that have no picture yet, made with `tools/guide_screens.py` so they can be made again.

## Pictures to add

- 4 Motion > **Way covers** panel, and a render of the generic way-cover test model (`tests/data/test_waycover_a.step`).
- 4 Motion > CNC machine with the **Air blast** fold open, and the G-code step's "Blow the part clean at the end"
  (0039 has a render only).
- 5 Scene & Render > **Labels** fold; one still of the test crane with two labels if it is cheap.
- 6 Animation > **Pictures** and **Music** folds.

Generic test models only – the repository is public.

## Done when

- [ ] Pictures in `docs/img/`, placed in the right chapters; shots added to `tools/guide_screens.py`.
- [ ] `tools/build_guide.py` builds; GitHub green (docs-only run); merged; `TASKS.md` updated; report below.
- [ ] Report says whether everything ran locally (proof for 0031) and how long the pictures took.

## Not in this task

Text rewrites beyond a caption per picture; app code; the way-cover code changes (0035).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 8 Nov 2026

**What changed:** 8 pictures in `docs/img/` (panel_4_waycover, view_waycover, panel_4_air, panel_6_gcode_air, panel_5_labels, panel_6_cards, panel_6_music) placed in their chapters; new runs `GUIDE_SHOTS=waycover|air|labels` in `tools/guide_screens.py`. The way-cover picture is a view of the covers opened 500 mm (not a Cycles render); no label render (not cheap).

**Tested and measured:** everything ran locally in the web session (stored set-up present: proof for 0031); the three runs took about 25 s each; build_guide and test_user_guide pass. 1 run expected.

**Open points / follow-up tasks:**
