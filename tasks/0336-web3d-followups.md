# 0336 – 3D page follow-ups (0328 F7)

**Who:** worker · **Status:** running · **Branch:** `task/0336-web3d-followups`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Sonnet · effort Medium
**Area:** Web 3D lane – `blender/ui_web3d.py`, `blender/web3d.py`, `core/web3d.py`, `fr_player.js` (and the site copy it is built into), their tests, guide, CHANGELOG.
**Not:** `ops_make.py` window size (0331) – put the result where the eye is inside your own panel instead.

## Goal

After Export the result and Open page are in sight; a greyed choice says why; on a phone held sideways the menu stays clear of the play bar; the user chooses which cameras become page views (the app's own cameras off by default).

## What to do

Fix 0328's rows **14, 15, 21 (0179 open point), 31 + the meshopt word of row 32** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Row 14 first.

## Watch

- Each row's **repeat case** and **proposed fix** are in `tasks/0328-bug-and-friction-hunt-8.md` ("Rows" table) – read those rows first, repeat the
  case, then fix. The proposed fix is a proposal: a better one is fine, say why in the report.
- Row 32's words: change only the words that are in **your** files (the row lists them by place).
- Every visible change: tooltip, user guide, PC-check line, tour stop / function-list entry with `since=` / `changed=`
  (CLAUDE.md section 2). Real-app check (`tools/ci_real_app.py`) for every row that was seen in the real app.
- Two tasks never share a file: stay inside **Area**; a needed change elsewhere → open point in the report.

## Done when

- [ ] Each row's repeat case now gives "what should happen" (a test per row; real-app check where it was seen there)
- [ ] Tests added/updated; full suite passes; GitHub run green
- [ ] (UI) screenshots checked with tools/ui_screens.py
- [ ] Guide, PC-check line, tour / function-list version fields as CLAUDE.md section 2 asks
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25 Nov 2026 (0.2.249)

**What changed:**
- **Row 14** – Open page and the folder button sit on Export's own row (`ui_web3d.py`), greyed until an export; the
  box with the file name and size stays under it. Chosen over "the result under Export…": it already was under it –
  Export itself sat at the Make window's lower edge – and a row that is always there keeps the panel still (CLAUDE.md
  section 6). The window size (`ops_make.py`) is untouched (0331).
- **Row 15** – before a Build "Include animation" is a label + **Build & play first** (`fresing.anim_build`, whose poll
  says "Make an animation first" when there is none); a built animation without a moving camera says "No Film button".
- **Row 31** – fold **Page views** ("2 of 2"): a tick per camera (`fresing.web3d_view`, UNDO; All / None). The tick is
  a custom property `fr_web3d_view` on the camera (no new project property, `props.py` untouched for it); none = on for
  the user's cameras, off for `fr_anim_camera`, `fr_product_video_cam`, `fr_turntable` (`web3d.on_page`,
  `page_cameras`; `view_names` / `views` follow it). Folded, the line under it still names the page's views (0179).
- **Row 21 (0179)** – `fr_player.js`: the views pill when `compact` (upright or height < 480), the settings menu's
  max-height ends above `--fr-stack` (it scrolls). At 932 × 430 with 7 views the menu went down to y 418 over the play
  bar at 357; now it ends above the views, views as the pill, no overlaps.
- **Row 32, meshopt** – the Smaller file tooltip (one string in `props.py`, outside the Area list – the word was only
  there) and the guide no longer name it.
- PC check `web3d.export`: a Turntable camera is made and must stay off the page; function entry `web.page_views`
  (since 0.2.249), `web.export` / `web.phone` changed 0.2.249; guide sections Web 3D model, Saved views, On a phone;
  picture `panel_5_web3d.png` made again. `tools/guide_screens.py` now ticks the web family for that picture – it showed
  Blender's Item tab (the web family is off until used; the picture of 23 Nov must have come from an older state).

**Tested and measured** (web machine, 4 cores, test mill / test crane): new `tests/test_web3d_panel.py` (3 tests, one
per panel row; each failed on the old panel) and `test_phone_sideways_menu_clear_of_the_play_bar` in
`tests/test_web_player.py` (failed before: mode row, menu over the play bar); `test_web_player.py` 24 passed,
`test_web3d.py` + `test_blender.py` + `test_fixes_0120.py` 50 passed, guide / functions tests 40 passed. Panel looked at
in the real app (guide picture, side panel 399 px at scale 1.5): no cut labels after renaming "Views on the page" →
"Page views". The PC-check line fails locally on Blender-as-a-module's missing meshopt library at the glTF read-back,
also without this change (my check comes before it); GitHub runs it in real Blender. No new real-app script: rows 14
and 15 are checked by drawing the panel's own `draw`; the Make window's size is 0331's.

**Open points / follow-up tasks:**
- The other words of 0328 row 32 belong to their files' tasks (context menu, ui_motion, ops_main, ui_left, ui.py …).
- Picture `web3d_phone.jpg` in the guide still shows the upright phone only (no sideways picture made).
