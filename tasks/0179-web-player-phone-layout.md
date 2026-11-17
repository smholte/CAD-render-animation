# 0179 – Web player on a phone: saved views, layout, view names

**Who:** worker (web session) · **Status:** running (owner started it 17 Nov ~08:00) · **Branch:** `task/0179-web-player-phone-layout` (a web session may name its own)
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

- [ ] All 8 points above, on the demo export (21 views) and on the site's models (`site/media/*.page.html` re-made as
      0134 did)
- [ ] Screenshots in a headless browser at **360 × 780** (the owner's phone), 390 × 844, 412 × 915, 844 × 390 (sideways),
      768 × 1024, 1366 × 768, 1920 × 1080 – each with 0, 1, 3, 9 and 21 views, animated and still; the overlap /
      inside-the-screen check runs on all of them in `tests/test_web_player.py`; a few of these pictures (the demo is
      invented, so they may be committed) in `tasks/img/0179_*` and named in the report
- [ ] The view-names setting tested: Camera names, Numbered, and *Hide part names* on with Camera names (part names
      still hidden everywhere else – the existing hide-names tests stay green)
- [ ] An independent tester (a subagent that did not write the code) uses the page at 360 × 780 and 844 × 390 as a
      first-time visitor and lists what is unclear; its faults fixed or listed
- [ ] Guide: the web 3D section (pictures re-made), the function-list entry for the new setting + guide anchor (0124),
      the PC-check self-test of the player still passes
- [ ] Tests added/updated; full suite passes on GitHub; report filled in; merged; release as usual (section 7)
- [ ] Report ends with **steps for the owner**: export the demo again, open it on his phone (upright and sideways)
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
