# 0134 – Web 3D player: settings menu, playback controls, "no graphics card" warning, lighter on PC

**Who:** worker · **Status:** done (0.2.112) – was: open – starts **after 0136 is merged** (0136 fixes the export crash in `web3d.py`; 0128 merged as 0.2.105)
· **Branch:** `task/0134-web-player`
**Started by:** lead chat, 15 Nov 2026 (owner's wishes, 15 Nov evening) · **Model:** Opus · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Web 3D lane):** `fresing_render/web/fr_page.js`, `fr_math.js`, the page writer in `core/web3d.py` /
`core/web3d_env.py`, `blender/web3d.py` (what goes into the file: saved cameras, animation length), `ui_web3d.py`,
their tests; the site's model pages re-made at the end (`tools/make_site_web_models.py`, `build_site.py --web-model`).
**Do not edit:** the Learning lane's files (0133 prototype branch), `demo_model/`, `demo.py`, `paths*.py` (0126).

## Goal

The web 3D page the app exports (and the site's "Turn it yourself" pages) becomes a small player: a settings menu
with surroundings on/off, quality, fps and the graphics card, play/pause with a time line, saved views, a clean
"model only" look – and it tells the visitor plainly when the browser draws without the graphics card.

## Background

- **What the owner saw (15 Nov):** the page was slow on his PC, smooth on his phone. Cause: Chrome had fallen back to
  software drawing (`chrome://gpu`: GL_RENDERER "ANGLE (Microsoft, Microsoft Basic Render Driver … D3D11-WARP)",
  WebGL "Software only") after a GPU reset on 12 Nov and had not really been closed since ("Continue running
  background apps" on). `chrome://restart` fixed it. A page cannot choose the GPU; it **can** notice and say so.
- His screens: 2560×1440 at 165 Hz (scale 1) and 2560×1440 at 160 Hz (scale 1.5). The page draws every frame
  (`requestAnimationFrame`, `fr_page.js` `frame()`), so at 160–165 Hz it keeps the GPU busy even when nothing moves.
- **Auto quality** (`core/web3d_env.py` `QUALITY`, `AUTO_FPS = 30`; `fr_page.js` `setLevel`): steps down when fps
  < 27 after a 2.5 s warm-up and **never steps back up**. The owner often sees "Quality Phone: lowered to keep it
  smooth" when he leaves and re-enters the page – likely loading / shader compiling counted as slow frames. Find the
  real cause, fix it, and let Auto step back up.
- Two page kinds today: Surroundings None → model-viewer 4.4.0; with surroundings → the three.js r180 page
  (`fr_page.js`). Every feature below must work in **both**, or move the plain page onto the three.js player if that
  is simpler – measure the page size and the phone first (Phone quality, a phone-sized headless window) and say in
  the report what you chose and why.
- Baked light (0107, a choice per export: SOFT / ALL / LIVE): with light baked into the textures a moving sun cannot
  move the baked shadows.
- Part names are hidden in exports by default (`hide_names=True`; the repository and the site are public).

## What to build

1. **"No graphics card" warning.** At start read the renderer (`WEBGL_debug_renderer_info`; three.js
   `renderer.getContext()`); "Basic Render", "WARP", "SwiftShader", "llvmpipe", "Software" → a bar at the top:
   *This browser is drawing the 3D model without the graphics card, so it is slow. Fix: type chrome://restart (Edge:
   edge://restart) in the address bar. Still slow: Settings → System → "Use graphics acceleration when available" on,
   then restart.* With a Hide button; the page goes to its lightest settings (Phone, no shadows, ≤ 30 fps). Backup
   when the browser hides the name: still under ~15 fps at Phone after warm-up → the same bar, worded "probably".
2. **Lighter:** at most 60 fps; draw only when something changes (camera moved, animation or sea/rain playing,
   menu change, resize); nothing while the tab is hidden; pixels capped by count, not only by ratio.
3. **Settings menu** (a gear button): surroundings items on/off – sea, sky, haze, rain/spray, vessel motion, shadows
   (only those the export holds); **Quality** Auto / Phone / Balanced / Best (manual overrides Auto); live **fps**;
   the **graphics card name**; **Auto-turn** on/off (turntable that starts only after ~8 s without input, stops at
   the first touch); **Sun / time of day** slider only with live light (LIVE); with baked light show it greyed with
   one line "Light is baked into this model"; **remember choices** for the next visit (localStorage, wrapped in
   try/catch; a "Reset" line).
4. **Playback** (pages with an animation): **spacebar** play/pause; a play button and a **time slider** to drag to
   any moment (phone too); **speed** ½× / 1× / 2×.
5. **Saved views:** the project's saved cameras go into the export (names as the owner gave them – they are his
   texts, not part names; still none when "hide names" is on, then "View 1, 2 …"); one button each, the camera flies
   there.
6. **View tools:** Fullscreen (F) and Reset view (R) with buttons; **Screenshot** (PNG of the current view, without
   the menu); **Copy link to this view** (camera + moment + menu choices in the address; the page already reads
   `?orbit=`); **Keyboard help** (? key) – a small card with every key.
7. **Clean look:** one key/button hides every control and bar; only a small faint button in a corner brings them back
   (and the key again).
8. **Loading bar** with MB loaded / total.
9. The app side: `ui_web3d.py` and the guide section say what the page offers (one short list), with the tooltips;
   the function list entry (0124) and guide anchor; the PC-check line for the web page gets the new checks it can do
   headless (menu present, spacebar pauses, the warning shows under a software renderer – headless Chrome is one).

## Done when

- [ ] Items 1–9 in both page kinds (or one player, with the reason); a test per item that can run headless (the page's
      `page.*` probe values: `page.fps`, `page.level`, `page.paused`, `page.warned`, …).
- [ ] Measured on the web machine: frames drawn per second with the camera still (aim: 0 or near it without
      animation/sea), page size before/after, Phone-quality load on a phone-sized window.
- [ ] The "lowered to keep it smooth" cause found and named in the report; Auto steps up again.
- [ ] Site pages re-made (`make_site_web_models.py`), "Turn it yourself" checked headless.
- [ ] Tooltips, guide, function list, PC-check line, test-tour stop if the tour shows the page; tests; GitHub run
      green; merged; version (CLAUDE.md section 7); report with a short list for the owner of what to try on his PC
      and phone.

## Not in this task

Click-a-part, measuring, cutaway, fade-the-rest → **0135** (same files, after this one). The weather and white caps on
the page → 0115 (owner decides).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 15–16 Nov 2026 (branch `claude/blissful-cray-6t7nco`; the session's branch
name instead of `task/0134-web-player`). No subagents.

**What changed:**
- **One player for every page** (the reason: each feature once, and the page is no bigger). Surroundings None now
  writes the three.js page in its plain form (light background, project's light) instead of model-viewer. Test mill
  page: 1.517 MB with model-viewer → 1.516 MB with the player. model-viewer stays only for a bare `.glb` on the site.
- `fr_page.js`: draws on demand (camera moves, animation/sea/vessel/rain playing, menu change, resize; nothing while
  hidden), at most 60 pictures a second (30 in software), pixels capped by count (`QUALITY[...]["pixels"]` 1.2 / 3.7 /
  8.3 million); software renderer detection (Basic Render / WARP / SwiftShader / llvmpipe / software → `warned`,
  Phone, no shadows, 30 fps; backup "probably" when the name is hidden and Phone stays < 15 fps); items on/off; Quality
  Auto/manual; sun over the day (live light only); auto-turn after 8 s; saved views (fly 0.9 s); link
  (`orbit, at, fov, time, paused, speed, quality, off, turn, sun`); screenshot; remembered choices (localStorage).
- `fr_player.js` (new): gear menu, play bar (Space, slider, ½× 1× 2×, ← →), view buttons (1…9), Fullscreen F, Reset R,
  Screenshot S, Link L, help ?, clean look H, the red bar, `?selftest=1` for the PC check.
- Loading bar in the page template (MB read of the model, then "Preparing").
- Export: the project's cameras go into the page as views (`blender/web3d.views`; View 1, 2 … with hide names).
- Site: `build_site.py` writes each own-page model again with today's player (`fresh_page`); no site Pause button on
  those (the player has its own). Test mill and Thor re-made (`make_site_web_models.py all`, 9 min); now with 1 and 2
  saved views.
- Panel fold "On the page" (short list), guide section `web3d-player`, function `web.player`, PC-check line
  `web3d.export` opens the page headless with `selftest=1` (menu, help, link, Space on a moving page, the bar), tour
  stop `web3d` text + check.

**"Lowered to keep it smooth" – the cause:** `requestAnimationFrame` does not run in a hidden tab (or a frozen page),
so the old `document.hidden` check inside the frame never ran; the first frame after coming back counted the whole
hidden time as one slow frame (e.g. 120 frames over 5 s = 24 fps < 27) and Auto stepped down – every time. Also the
first second of shader compiling could count. Reproduced headless (`tools/web_player_probe.js`, a 3 s hidden tab or
freeze on the old page: lowered 1, level Phone); new page: 0, Balanced. Now only pictures drawn one right after the
other count, a warm-up follows every change, and Auto steps up again (two good 2-s windows ≥ 50 fps; slower after a
step down).

**Tested and measured** (4-core web machine, no graphics card, headless Chromium with SwiftShader):
- Pictures drawn with the camera still: **0 in 5 s** (test mill page, 1280×800); old page here ~30 a second (on a
  PC: the screen's rate, 160–165). Paused animation: 0. After a drag: drawing stops when the turn settles.
- Page size: see above (−1 kB). Phone window 390×844 at 3×: test mill page loads in ~0.43 s, Phone quality draws
  0.33 million pixels; sea test page at Phone: no error.
- `tests/test_web_player.py` (13 tests, headless; on GitHub's runner node checks the scripts), `test_web3d*.py`,
  `test_site.py`, `test_tour.py`, `test_functions.py` pass locally. Site built, both "Turn it yourself" pages checked
  headless (load, Space pauses, 0 pictures while paused, menu).
- The PC-check line's new part passed on its own here; the line as a whole fails here at the read-back on `main` too
  (the bpy module has no meshopt library), GitHub's real Blender runs it.

**For the owner – try on your PC (Chrome) and phone:** open a page (5 Scene & Render > Web 3D model > Open page, or
"Turn it yourself" on the site): 1. the gear: switch items, pick Phone/Best, see the pictures a second and your
graphics card's name; 2. Space and the time line; 3. the view buttons; 4. L, then paste the link in a new tab; 5. H;
6. leave the tab for a minute and come back: no "lowered" note; 7. with nothing moving, Task Manager → GPU should
stay near 0 %.

**Open points:** the sun slider is greyed for a 360° photo light too ("The light comes from the project's 360°
picture"); fullscreen is not offered where the browser has none (iPhone Safari). GitHub runs: 7 on the branch – 1 real failure (`test_lightbake` still expected model-viewer), 1 Windows PC-check
failure (the headless browser stopped before the player's self-test answered: it now runs the moment the page is
ready, the check retries once and counts a missing answer as "not counted"), 4 more because other tasks took
0.2.108–0.2.111 first; the last green run 43790944832; `main` then only had task-list commits on top.

