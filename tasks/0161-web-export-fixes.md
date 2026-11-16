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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
