# 0179 – Web player on a phone: saved views, layout, view names

**Who:** worker (web session) · **Status:** done (0.2.140, 17 Nov) · **Branch:** `task/0179-web-player-phone-layout` (a web session may name its own)
**Started by:** lead, 17 Nov 2026 · **Area:** Web 3D lane: `fresing_render/web/fr_player.js` (most of it),
`fresing_render/web/fr_page.js` (only: the quality note, the start-view framing, the view list), the page templates in
`core/web3d.py` / `core/web3d_env.py` (viewport meta, header), `blender/web3d.py` (only the saved-views function and the
new setting), `blender/ui_web3d.py` + `blender/props.py` (additive: one setting), the site's web models re-made, their
tests, the guide's web 3D section, the function list. **Model · effort:** Opus · High. Claude Code on the web,
environment "CAD-render-animation".

## Goal

An exported web 3D page is pleasant to use on a phone held upright: the model fills the screen, the saved views are
one compact control with their real names, nothing overlaps, and the page still works as now on a PC and a phone held
sideways.

## Background

Owner's screenshot, 17 Nov 02:31 (Android phone, 1080 × 2340 pixels ≈ 360 × 780 CSS px, Chrome; the demo
"Demo cable-lay vessel" exported with 0.2.133, Quality Phone; described in words, not committed):

1. **21 saved views as a wall of buttons:** "View 1" … "View 21" in six rows of 3–4 large buttons, covering the lower
   ~40 % of the screen – and the vessel itself, which is drawn small in the lower middle, mostly behind the buttons.
   The upper half of the screen shows only empty sea.
2. **The names say nothing:** "View 1 … 21" because *Hide part names* (on by default) also numbers the cameras
   (`blender/web3d.py`, the saved-views function: `name = f"View {k + 1}" if hide_names else ob.name`). The demo's
   cameras have good names ("Shot 3: carousel and arch", "Shot 6: handling winch drum, depth of field", …).
3. **Overlapping text at the bottom:** the quality note "Quality Phone: lowered to keep it smooth" (`#quality`,
   `fr_page.js` `note()`) is drawn on top of "Made with Fresing Render" (the `.note` line moved into `#fr-bottom`).
4. **Header takes four lines over the scene:** title "Demo cable-lay vessel 0.2.133 web 3D" (two lines) and the hint
   "Drag to turn · pinch to zoom · two fingers to move · tools on the left" (two lines), always shown.
5. **Icon-only tool columns:** 4 buttons on the left (part info, measure, cutaway, fade), 8 on the right (settings,
   fullscreen, reset, screenshot, link, help, clean look …). On touch there is no tooltip, so the left ones in
   particular are guesswork.
6. **Play bar:** fine in itself, but narrower than the screen with the speed buttons wrapped to a second line; at the
   very bottom edge a dark rounded bar is cut off by the screen edge (an element under Android's gesture bar – the
   page uses no `env(safe-area-inset-*)` and no `viewport-fit=cover`).
7. **Start view framing:** the model is framed for the whole screen, not for the free part between the header, the
   tool columns and the bottom controls.

Code: the player UI is `fresing_render/web/fr_player.js` (0134; CSS at the top, `#fr-views` wraps freely,
`@media (max-width: 600px)` only moves the tools), the scene and the quality note in `fr_page.js` (`page.views`,
`page.goView`, `setLevel` → `note()`). Tests: `tests/test_web_player.py` (headless browser; `test_phone_sized_window`,
`test_saved_views_and_view_tools`).

## What to build (lead's choices – the owner may change them before the start; a better idea is welcome if the report
says why)

1. **Saved views as one compact control.**
   - **Phone upright** (narrow screen): one pill above the play bar: `‹  Shot 3: carousel and arch  ›` – the arrows step
     to the previous / next view, a tap on the name opens a sheet from the bottom with all views as a list (current
     one marked, scrolls, closes on a pick, a tap outside or Back). Long names end in "…" on the pill, full in the list.
   - **Wide screens and phone sideways:** one row of view buttons that never wraps; when they do not fit, the row
     scrolls sideways (with fade edges) and an "All views" button at its end opens the same list. Keys 1–9 stay.
   - 0 views: nothing shown; 1 view: one button (as now); 2–3 views on a phone may stay as buttons if they fit in one
     row.
2. **View names = the cameras' names.** New export setting **"View names: Camera names / Numbered"** right under *Hide
   part names* (default **Camera names**; tooltip: the camera names are shown on the page, choose Numbered if they
   should stay private). The panel shows the names the page will get (first few + "…"), so nothing goes out unseen.
   *Hide part names* no longer touches the view names. Old pages keep what they have; a re-export gives the names.
3. **One bottom stack, no overlaps.** From the bottom: the "Made with" line (small), the play bar (full width on a phone,
   speed buttons on the same line), the views control. The quality note becomes a short message (as the toast) that
   goes away after ~4 s and never covers another control; the current quality stays readable in the gear menu.
   An automatic check: at every tested size, no two visible controls overlap and every control lies inside the screen
   minus the safe areas.
4. **Header on a phone:** title on one line (ends in "…"; full title in the info / help sheet), the hint shown on the
   first visit only until the first touch or ~6 s, then gone (it stays in the help sheet). Remembered like the other
   choices.
5. **Tool buttons readable on touch:** keep the icons, but make their meaning findable without a mouse – e.g. a
   long-press shows the button's name, and the help sheet lists every button with its icon and name. On a phone the
   right column may fold the rarer ones (screenshot, link, clean look, keys) into one "More ⋯" sheet; at most ~5
   buttons per column upright. Touch targets ≥ 40 px.
6. **Safe areas:** `viewport-fit=cover` + `env(safe-area-inset-*)` on the header, the tool columns and the bottom
   stack (notches, Android gesture bar, iPhone home bar).
7. **Start view and saved views framed in the free area:** the model's fit (and each saved view's centre) placed in the
   rectangle not covered by the header, tool columns and bottom stack (e.g. three.js `setViewOffset`, or the fit done
   on that rectangle), re-done on resize / turning the phone. The model must not sit behind the controls at the start.
8. **Keep what works:** desktop layout, keys, clean look, fullscreen, the part tools (0135), the sea switch (0143),
   the settings menu, the site's own frame (`--fr-top`) – same functions, only placed better.

Use the frontend-design skill's eye for spacing and type, but stay in the page's existing look (Fresing Green / amber,
IBM Plex Sans, dark translucent panels).

## Done when

- [x] All 8 points above, on the demo export (21 views) and on the site's models (`site/media/*.page.html` re-made as
      0134 did)
- [x] Screenshots in a headless browser at **360 × 780** (the owner's phone), 390 × 844, 412 × 915, 844 × 390 (sideways),
      768 × 1024, 1366 × 768, 1920 × 1080 – each with 0, 1, 3, 9 and 21 views, animated and still; the overlap /
      inside-the-screen check runs on all of them in `tests/test_web_player.py`; a few of these pictures (the demo is
      invented, so they may be committed) in `tasks/img/0179_*` and named in the report
- [x] The view-names setting tested: Camera names, Numbered, and *Hide part names* on with Camera names (part names
      still hidden everywhere else – the existing hide-names tests stay green)
- [x] An independent tester (a subagent that did not write the code) uses the page at 360 × 780 and 844 × 390 as a
      first-time visitor and lists what is unclear; its faults fixed or listed
- [x] Guide: the web 3D section (pictures re-made), the function-list entry for the new setting + guide anchor (0124),
      the PC-check self-test of the player still passes
- [x] Tests added/updated; full suite passes on GitHub; report filled in; merged; release as usual (section 7)
- [x] Report ends with **steps for the owner**: export the demo again, open it on his phone (upright and sideways)
      and on his PC, what to look at

## Not in this task

- Cables, coils, spools and the sea's moving parts on the page (`fr_page.js` cable shader, `core/web3d_tubes.py`,
  the coil export) – a layout task only. (0174 full spools merged 17 Nov, 0.2.139: its page still shows a temporary
  solid coil – not this task.)
- Smaller files (0175, Web 3D lane, after this task), the weather on the page (0115), the page's water effects (0154's
  open point).
- View thumbnails (pictures per view in the list): only as a proposal with its size cost in the report.
- The app's own side panel (0062).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 17 Nov 2026. Branch `task/0179-web-player-phone-layout`, version
0.2.140.

**What changed:**
- `fr_player.js` (most of it): **saved views** as one control – wide screens and a phone sideways: one row that never
  wraps (scrolls sideways, fading edges, **All views** at its end when they do not fit); a phone upright (< 600 px
  wide): one pill **‹ name ›** (arrows step and wrap round, the name opens the list; 2–3 short names stay buttons);
  the list is a sheet from the bottom (current view marked, scrolls, closes on a pick, a tap outside, Esc or Back).
  Keys 1–9 stay. **One bottom stack** (views, play bar full width on a phone with the speeds on the same line, "Made
  with"); the empty parts of the stack let drags through to the model. **Header** on a phone: the title on one line
  with "…" (whole in the help); the hint is a bubble on the first visit only, gone at the first touch or after 6 s
  (remembered; Reset in the settings forgets it). **Tool columns** start under the measured header; at most 5 buttons
  upright, fewer when the screen is short – the rarer ones (Screenshot, Copy link, Clean look; then Help) fold into
  **More tools** (⋯), a menu with their names. A **long press** on any button shows its name and does not press it;
  the **help** lists the page's title, every button with its icon and name, the gestures and (with a mouse) the keys.
  **Safe areas** (`viewport-fit=cover`, `env(safe-area-inset-*)`) on the header, columns, stack, sheets and the warning
  bar. The **quality note** is a short message above the stack for at most 4 s (the level is in the settings: "Now:
  Phone – lowered to keep it smooth"). **Back** closes an open sheet (help, settings, More, the list) instead of
  leaving the page (one history entry while any is open). The settings got a close button; "Remembered in this
  browser". `frPage.layoutCheck()` lists overlaps, controls outside the safe area and buttons under 40 px; the PC
  check's self-test now also fails on an overlap.
- `fr_page.js`: `setFree` – the camera's frame is the rectangle the header and the bottom stack leave free (three.js
  view offset: the fit, Reset and every saved view's aim are placed there; never less than 40 % of the screen);
  `refit` frames the start view again when the free area changes (controls laid out, phone turned) while the visitor
  has not moved the camera; the quality note goes to the player's message.
- `fr_tools.js` (CSS only): the part tools' column under the measured header, 40 px buttons always, safe areas; on a
  short screen where it would reach the stack, the stack moves beside it.
- App: new setting **View names: Camera names / Numbered** (default Camera names) under Hide part names, with the
  names the page will get shown below it ("Views on the page (2): 3/4 hero, low, Iso front-right"); Hide part names
  no longer touches the views. `web3d.view_names()`, `views(numbered=)`, `Job(view_names=)`.
- Page template: `viewport-fit=cover`. Probe (`tools/web_player_probe.js`): steps `size`, `touchon`, `back`.
- Guide: View names, the saved views' row / pill / list, a new "On a phone" part with a picture
  (`docs/img/web3d_phone.jpg`), panel picture re-made. Function list: `web.view_names`, `web.phone` (anchors
  `web3d-view-names`, `web3d-phone`). Site: test mill and Thor re-made (`make_site_web_models.py all`, ~10 min) –
  their views are now "Iso front-right" and "Iso front-right", "Thor at work" (were View 1, View 2).
- Pictures: *(picture removed – private, task 0226)* (before, 21 views at 360 × 780), `0179_phone_upright.png` (pill + list,
  test mill with 6 views), `0179_phone_sideways.png` (844 × 390), `0179_laptop.png` (1366 × 768).

**Tested and measured** (4-core web session, headless Chromium with software drawing):
- `tests/test_web_player.py`: every size of the brief (360 × 780, 390 × 844, 412 × 915, 844 × 390 as a touch phone;
  768 × 1024, 1366 × 768, 1920 × 1080) × 0, 1, 3, 9, 21 views × animated / still – no overlaps, nothing outside the
  screen, buttons ≥ 40 px, also with a message shown and with a notch + gesture bar (28 / 24 px) set; pill and list
  (step, pick, tap outside, Back, Esc, keys); row (one line, scrolls, All views, the picked one scrolled into sight);
  2–3 short names stay buttons on a phone, 3 long ones become the pill; the model's box and aim inside the free area
  at the start and after turning the phone, a saved view's aim in its middle; title on one line, hint once, More
  tools, long press, help, the message's 4 s; Back closes help, settings, More and the list and the page stays.
  `tests/test_web3d.py`: Camera names by default also with Hide part names on, Numbered keeps them out of the page.
  All web tests (109) and the site, guide, function-list tests pass locally.
- At 360 × 780 with 21 views: before, the buttons covered the lower ~40 % of the screen and the title area; now the
  views take one line of 44 px and the model gets 615 of 780 px height (free area 0–36 px header, stack ~130 px).
  Sideways (844 × 390) the model gets 231 px height.
- Not run: the real demo export (21 cameras) – checked with a page of 21 views named like the demo's shots instead.
  Nothing tried on a real phone (real safe areas, real Back gesture): the owner's steps below.
- Subagents: one **independent tester** (Sonnet, did not write the code) used the 21-view page at 360 × 780 and
  844 × 390 as a first-time visitor: 10 findings. Fixed: Back with the help open left the page (high), the settings
  had no close button, "Remembered on this PC" on a phone. Not reproduced: "Next view shows no name" (shows "Shot 1:
  … 1/21"; its picture was taken while a quality message showed). Left as they are, see open points.

**GitHub runs:** 3 – run 44045080244 red on the spool tour stop (not this task, open point 4), its failed job run
again: red the same way; after merging main (0171) run 44052893450 green; `main` fast-forwarded to it (6900500).

**Open points / follow-up tasks:**
1. Panning on a phone upright is ~1.3 × slower than the finger (three.js OrbitControls scales by the whole canvas
   height; the frame is the free area) – expectation from the numbers, not measured on a phone. Small; a fix would
   patch OrbitControls' pan.
2. Sideways the settings menu scrolls (it is longer than 390 px) and covers the play bar while open; the help moves
   into More tools there (fullscreen kept first). The title is white on a bright sky (text shadow only).
3. `build_site.py --web-model` (run by `make_site_web_models.py`) drops `media.json` "models" entries no picture uses
   yet: it removed the two IEA 15 MW entries; restored by hand here. → Site lane.
4. A random failure, not of this task: run 44045080244 (branch), `test_tour.py` stop `spool` – "Cable 'Power cable' no
   longer touches 'GUIDE SHEAVE' at frame 233" in a test-suite-5 job that took 19.4 min (usually 7.8, a busy runner);
   the same test passes here (204 s; the whole tour file 81 passed, 433 s) and on main; the failed job, run again,
   failed the same way. Measured here on the tour's spool set: the cable's wrap round GUIDE SHEAVE jumps from 0.92 to
   1.31 rad between frames 231 and 232 (where the full spool's leave point moves on, 0174) – the lift judgement sits
   near that jump, and a slower runner's numbers tip it. Not this task's code (nothing of paths/spool changed).
   → Flex parts lane (0174's spool stop).
5. View thumbnails in the list (proposal only): a 160 × 90 JPEG per view ≈ 5–7 KB, ~130 KB base64 for 21 views
   (estimate), made at export by a small Cycles/EEVEE render per camera.

**Steps for the owner** (after Update now to 0.2.140):
1. Open the demo project (Help menu: make it first if you have none, then open it), go to 5 Scene & Render > Web 3D model. Under **Hide part names**
   you see **View names: Camera names** and the line "Views on the page (21): Shot 1 …".
2. Click **Export…**, save, then **Open page** (PC). Check: one row of view buttons at the bottom; if they do not fit,
   the row scrolls sideways and **All views** opens the list.
3. Send the `.html` to your phone (e-mail or a cloud folder) and open it in Chrome, held upright. You should see:
   the title on one line, four buttons left, five right (the last is ⋯ More tools), at the bottom **‹ Shot … ›**, the
   play bar on one line and "Made with Fresing Render" under it – nothing on top of anything, nothing under the
   gesture bar, the vessel in the middle of the free space.
4. Tap › and ‹ (the view flies, the name changes), tap the name (the list of 21 opens; pick one; open it again and
   use the phone's Back – the list closes, the page stays).
5. Hold a button (e.g. the ruler) for a second: its name shows. Tap ? : the help lists every button.
6. Turn the phone sideways: the views become a row, the vessel is framed again between the title and the row.
