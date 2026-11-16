# 0161 – Fix: web 3D export – light bake with live handlers off, marine looks on the page, isometric view, safe settings block

**Who:** worker · **Status:** open – can start when a code slot is free (before 0143: same files) ·
**Branch:** `task/0161-web-export-fixes`
**Started by:** lead chat, 16 Nov 2026 (rows of bug hunt 0147, report in `tasks/0147-bug-hunt-5.md`) ·
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation". Subagents
allowed (CLAUDE.md section 2).
**Area (Web 3D lane):** `blender/lightbake.py` (`_bake_call`), `blender/web3d.py` (the looks bake for marine looks,
`views()`), `core/web3d_env.py` (`page_html`), `ui_web3d.py` (a note), their tests, the guide's web 3D section.
**Do not edit:** `web/fr_page.js`, `web/fr_tubes.js`, `blender/web3d_drawn.py`, `cable_looks.py` (0158 runs there),
`marine_looks.py` (read only; 0153 may add to it), `surroundings.py` (0148), `paths*` / `spool` / `flex` (0159, 0160),
`house_*` (0163).

## Goal

Export web 3D model can never crash Blender in the light bake, and what the page shows matches the app: marine growth,
streaks and the worn blade edge on the turbine and crane pages, isometric views at the right size, any camera name.

## Background

Read rows 1, 10, 14 and 15 of `tasks/0147-bug-hunt-5.md` first (place in the code, proof, suggested fix). Repeat each
one before fixing it.

- **Row 1 (crash risk, first):** 0136 paused the live handlers only around the looks bake. Wrap the light bake's
  `bpy.ops.object.bake` in `_bake_call` (Soft light / Everything baked, and the House bake that calls it) in
  `handlers.pause_live()` too. Test as the row says: moving cable not built, light Soft, the copy's `fr_bake` tag taken
  off → no crash (in a process of its own, as 0136's test), handlers back afterwards, also after a cancel.
- **Row 10:** marine looks (growth band, mottling, run-down streaks, worn leading edge) depend on world height, up
  direction or the part's own axes, so a flat tile cannot carry them. Bake parts with these looks per object on their
  own UVs (as the light bake does), with the part in its place at the frame shown; other looks keep the tiles. Measure
  the file and bake time on the offshore turbine and the crane with growth. If a part is too big for its own bake at
  the chosen texture size, say so in the export line. Compare app render and page picture (headless Chromium) as 0147
  did.
- **Row 14:** an orthographic camera: fov = 2·atan(ortho_scale / 2 / distance to the target), so the page frame
  matches the app (×1.00, as perspective cameras already do).
- **Row 15:** escape every `<` in the JSON settings block as `<`. Test: a camera named `<!-- <script` with Hide
  part names off opens.

Rows 11 (saved views under water) go into 0143, rows 16 and 21d–f (page settings and phone layout) into 0135 – both
edit `fr_page.js`.

## Done when

- [ ] Every row above fixed, each with a test that failed before the fix.
- [ ] Tooltip / note / guide sentence where the owner sees a change; PC-check line only if a new one is needed.
- [ ] GitHub run green; merged; version (CLAUDE.md section 7); report with a short list for the owner and the
      measured file sizes / bake times.

## Not in this task

The other rows of 0147 (0160, 0162, 0163; 11 → 0143; 16, 21d–f → 0135); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026 – branch `claude/relaxed-einstein-qn16gw` (the session's
branch, not `task/0161-…`), version 0.2.121. No subagents (Medium task; the rows were small or one design).

**What changed:**
- **Row 1 (crash risk):** `lightbake.Bake._bake_call` runs `bpy.ops.object.bake` inside `handlers.pause_live()`
  (Soft light, Everything baked, the House bake). Test `test_web3d_bake_safe.py::test_light_bake_keeps_the_live_handlers_away_from_the_copy`
  (own process): moving cable not built, Soft light, the copy's `fr_bake` tag taken off, a spy handler; also a Cancel
  in the middle. Before the fix: **segfault (signal 11)**; after: no handler sees the copy, handlers back both times.
- **Row 10 (marine looks):** `web3d.needs_own_bake(ob)` = a part (no modifier) with a marine look (`marine_looks.nodes_of`).
  Such parts are baked **on their own UVs** where they stand (`Baker.own`): `lightmap.unwrap` of the world-scaled mesh,
  `core.own_atlas` (one square picture up to 2048 px, power of two, 4 px padding, bake margin 6 px EXTEND), a triangle
  copy with the part's custom properties and the export scene's waterline; colour/roughness/metal/alpha by Emit (edge
  wear and AO kept – it is the real shape), the normal by Cycles' **tangent-space Normal bake** (the growth's bumps).
  Every slot of such a part reads the part's pictures (no `KHR_texture_transform`, CLAMP); the mesh gets its own
  `TEXCOORD_0` (float) and keeps baked light (`TEXCOORD_1`). Texels: `core.own_tpm` = texture size per metre
  (1024 → 1 mm), at most `OWN_BUDGET` 8 M texels for all such parts together. Export line: `core.own_line`
  ("marine looks baked on N parts (X mm per pixel…)", "too big for the fine streaks and barnacles" above 10 mm).
  Panel note when a material in use has a marine look; guide paragraph in the Web 3D section; CHANGELOG.
  Tests: `test_web3d_own_bake.py` (an upright plate through the waterline: page colour below the band < 0.6 × above,
  above = the yellow paint; fails on the tiles: 0.51 vs 0.51), `test_web3d_core.py` (`own_atlas`, `own_tpm`, `own_line`).
- **Row 14:** `views()`: an ORTHO camera gets fov = 2·atan(ortho_scale / 2 / distance to the target). Test
  `test_web3d.py::test_isometric_view_keeps_its_frame_on_the_page` (before: ×0.58 of the frame width on the mill's
  camera set-up; after ×1.000).
- **Row 15:** `page_html` escapes every `<` as `\u003c` (`page_settings` reads both forms). Test
  `test_web3d_env.py::test_settings_block_escapes_every_lt` (fails before); the camera name `<!-- <script` read back
  by `JSON.parse` in headless Chromium.

**Tested and measured** (4-core web machine, CPU bake, no graphics card):

| Model | Before (0.2.120) | After |
| --- | --- | --- |
| Test crane, every part marine growth, waterline 0.3 m, 512 px | 0.2 MB, 3 textures, 2.5 s, page plain yellow | 0.8 MB, 59 textures, 25.5 s (20 parts, 2 mm per pixel) |
| Offshore turbine **stand-in** (monopile + tower −30 … +144 m with growth, transition piece with streaks, 3 blades 117 m with the worn edge), 1024 px | 0.6 MB, 5 textures, 10.1 s, no growth on the page | 2.3 MB, 15 textures, 86.5 s (6 parts, 32–75 mm per pixel, "too big for the fine streaks" said) |

The owner's IEA 15 MW STEP is not on this machine (draft release `site-kit`), so the turbine numbers are of a stand-in
of the same size, not of the real turbine. App render (Cycles) vs page (headless Chromium, SwiftShader), the crane
from its saved view: the growth patches sit in the same places; the turbine stand-in shows the growth below the
waterline on the page (before: plain paint). Local tests: the web 3D and light bake files (91 passed), tooltip check
756/756 ok, precheck. GitHub runs: see below.

**Open points / follow-up tasks:**
- At the 8 M texel budget a turbine tower gets 3–7 cm per pixel: the band and patches show, streaks and barnacles do
  not. A bigger budget doubles the file and bake time; owner decides (one number, `core.OWN_BUDGET`).
- A marine part drawn by a modifier (none today) keeps the tiles; a marine part that moves keeps the band where it
  was at the frame shown (the band is world height).
- Not checked on the owner's turbine page (0128) – it needs the owner's STEP or his next kit run.
