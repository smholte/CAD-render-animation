# 0165 – Web 3D export: a "Marine detail" choice (Normal / Fine) for the marine looks on big parts

**Who:** worker · **Status:** open – can start (beside 0164 and 0155; 0143 waits for it) · **Branch:** `task/0165-web-marine-detail`
(a session branch `claude/…` is fine – say which in the report)
**Started by:** lead chat, 16 Nov 2026 (owner's wish after 0161's report: "yes, I want this") ·
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation".
**Area (Web 3D lane):** `core/web3d.py` (`OWN_BUDGET` → a budget per choice, `own_tpm`, `own_line`, and
`own_atlas`'s `max_px` only if Fine needs it), `blender/web3d.py` (passes the export's choice to the own bake),
the export settings in `props.py` (additive: one enum), `ui_web3d.py` (one row + tooltip, next to Light / Bake quality),
`core/functions.py` (the `web.export` entry or a new `web.marine_detail` entry), the tour's web 3D stop (one check), their
tests (`tests/test_web3d_core.py`, `tests/test_web3d_own_bake.py`), the guide's web 3D section (one paragraph).
**Do not edit:** `web/fr_page.js`, `web/fr_tubes.js`, `blender/web3d_drawn.py`, `core/web3d_tubes.py`, `cable_looks.py`,
`ui_paths.py` (0164 runs there); `surroundings.py`, `core/sea.py` (0155, then 0154); `paths*`, `spool`, `flex` (0160);
`marine_looks.py` (read only); `demo_model/`, `demo.py`.

## Goal

The owner picks per export how much detail the marine looks (growth band, patches, streaks, barnacles – 0128, 0161) get
on the web page: **Normal** (today's size, small page, the default) or **Fine** (the streaks and barnacles show on a part
as big as a turbine tower, at a bigger file and bake time that the panel tells him before he exports).

## Background

- 0161 (0.2.121) bakes the marine looks on a part's own UVs. All such parts together share `core.OWN_BUDGET` =
  8 M texels per channel (two pictures of 2048 px). On the IEA turbine's tower that gives 3–7 cm per pixel: band and
  patches show, the fine streaks and barnacles do not (`OWN_DETAIL_MM` = 10 mm is where they are lost). 0161 said a
  bigger budget about doubles the turbine's file and bake time. Its report: `tasks/0161-web-export-fixes.md`.
- `own_atlas` caps a picture at `ATLAS_MAX` = 2048 px (0105 chose this – 4096 px pictures cost phones memory). Fine may
  need 4096 px pictures **for these own bakes only**; if so, keep every other bake at 2048 and say on the panel note that
  Fine pages are heavier on phones. Keep the page's code unchanged (`fr_page.js` belongs to 0164 / 0143).
- Owner's wishes that apply (13 Nov): every surroundings item and the light are choices per export; the page stays one
  offline file; Page quality Phone / Balanced / Best + Auto already exists on the page.

## What to build

- **Setting** "Marine detail" on 5 Scene & Render > Web 3D model, per export, saved with the project: **Normal**
  (= today, bit for bit the same file) / **Fine**. Shown only (or enabled only) when a material in use has a marine look
  – 0161's panel note already finds that. Tooltip says what Fine shows and what it costs.
- **Fine's size:** pick the budget so the IEA turbine tower (offshore variant, the stand-in in the tests is fine) gets
  **≤ 10 mm per pixel** where the band is (the streaks and barnacles show), or as close as 4096 px pictures allow – measure,
  do not guess. If the whole tower cannot reach 10 mm, spend the texels on the band's height range (the splash zone,
  where the marine look changes) rather than evenly up the tower – only if that is simple; otherwise write it as an open
  point.
- **Estimate before export:** the panel's existing estimate (or the export line) shows the marine bake's file size and
  bake time for the choice, so the owner sees "Fine: about +X MB, +Y s" before he clicks.
- **Export line** (`own_line`): with Normal and a part coarser than 10 mm per pixel, it suggests Fine.
- Old projects open as Normal.

## Done when

- [ ] Normal gives the same .glb as before (test: byte-compare or same image hashes on the test plate).
- [ ] Fine: a test that the turbine stand-in's tower gets ≤ 10 mm per pixel at the band (or the measured best, written
      in the report), and that the page still opens (`test_web3d_own_bake.py` style: page colour below/above the band).
- [ ] Measured on the turbine stand-in (and the demo vessel if it carries marine looks): file size and bake time
      Normal vs Fine – in the report and in the guide paragraph.
- [ ] Tooltip, guide paragraph, function-list entry, the tour's web 3D stop checks the setting; PC-check line only if a
      new one is needed (CLAUDE.md section 6).
- [ ] GitHub run green; merged; version (CLAUDE.md section 7); report with a short list for the owner.

## Not in this task

The page's own code (`fr_page.js`); the marine looks themselves (`marine_looks.py`); the other bakes' sizes (0105);
the smaller-file proposals of study 0149 (later, after 0143 / 0135).

---

## Report (filled in by the chat that did the task)

**Chat / date:**
