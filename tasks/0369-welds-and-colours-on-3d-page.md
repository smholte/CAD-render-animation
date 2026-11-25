# 0369 – 3D page: welds with their ripples and heat tint + dark warm colours as in the app

**Who:** worker · **Status:** running · **Branch:** `task/0369-welds-colours-3d-page`
**Started by:** lead, 25 Nov 2026 23:5x (owner allowed extra code tasks for the night; open points of 0319 and 0143)
· **Model:** Opus · effort Medium
**Area:** Web 3D lane – `blender/web3d.py`, `blender/web3d_env.py`, `core/web3d.py`, `core/web3d_env.py`,
`fresing_render/web/fr_page.js`, their tests, the guide's 3D page section, CHANGELOG. `pccheck/checks.py`: a new check
inside your own new function only (0348 adds to the file elsewhere – whoever merges second updates its branch).

**Not:**
- **The Welds lane's files – 0368 runs there:** `core/welds.py`, `core/weld_cad.py`, `blender/welds.py` (incl.
  `web_objects`), `blender/weld_looks.py`, `blender/weld_cad.py`. Read them; don't change them. If the export needs
  more than `welds.web_objects` gives, gather it in `web3d.py` from the weld objects (their material slots, the UV
  layer `fr_weld`, the heat-zone strips – 0368 keeps those names as today) and say in the report what the Welds lane
  could offer instead.
- `vessel_motion` files (0326).
- The demo vessel and its equipment (private) – use public test-tour models only.
- The format number on pages (0353) and the assets pack caps (0364) – later.

## Goal

On the 3D page, welds look like welds: the ripples along the bead and the heat tint beside it, as in the app's
renders. Dark warm colours (sand, rust, brown paint) on the page are no longer greyer than in the app.

## Background

- **Welds (0319's report, `tasks/0319-welds.md`):** the beads are exported in their colour / paint. The ripples and the
  heat tint are not: the page bakes 0.2 m tiles in the part's space, while they live on the weld's own UVs (`fr_weld`).
  The heat-zone strips are left out (`web3d.py` around line 117: `welds.web_objects`).
- **Colours (0143's report, `tasks/0143-web-sea-cutaway.md`):** the page's sand under the sea is greyer and darker.
  Mean RGB at the box's far end: app 105 / 96 / 79, page 70 / 77 / 76 – not the shadow. 0143 thought "the page's light
  makes dark warm colours greyer". Not checked whether it is only the seabed or all dark warm colours.
- Page budgets and quality levels: `core/web3d_env.QUALITY`; tiles 512 / 1,024 / 2,048 px per 0.2 m.

## What to do

1. **Welds:** bake each bead along its own UVs (the ripples, its finish, rust), plus the heat-zone strips (the tint
   fading from the bead). Keep the file small: one atlas or a few small tiles per weld kind, not a picture per weld. At
   Phone level they may stay plain if that keeps the page smooth (say so). A painted weld stays in its paint, as in the
   app.
2. **Colours:** compare app and page on a swatch set: dark warm (sand, rust, brown), dark cool, mid grey, bright paint,
   on Surroundings None, a sea set and under the sea. Use the same view, Cycles in the app, the page in headless
   Chromium. Find where the difference comes from (colour space of the baked tiles or of the seabed's numbers, tone
   mapping, the light picture, fog / water fade) and fix it at that place. Make nothing else worse.
3. The guide's 3D page section mentions the welds; the PC-check gets a check that a weld project's page holds the ripples
   / heat tint; the function list follows (CLAUDE.md section 6).

## Done when

- [ ] The test weldment's page shows ripples and heat tint. A picture app vs page side by side is in the report. Page size
      and export time before / after are given.
- [ ] Swatch table app vs page (mean RGB per swatch) before / after; dark warm colours within about 10 of 255 per channel
      of the app where the light is the same; the others no worse. Pictures side by side in the report for the owner.
- [ ] `test_web3d*` green; new tests for the weld bake and the colour path; full suite passes; GitHub run green;
      CHANGELOG.
- [ ] Report filled in, with the owner's line (which page to open on his PC to look at both). Merged, released.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
