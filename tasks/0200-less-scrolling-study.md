# 0200 – Study + prototype (findings only): less scrolling – a floating set-up window, and all ways to render side by side

**Who:** worker · **Status:** running (findings only: no merge of app code, does not count as a code task) ·
**Branch:** the session's own; prototype code pushed with `[skip ci]`, never merged; report + page to `main` as
`tasks/` files only
**Started by:** lead chat, 17 Nov 2026 22:30 (owner's wishes) · **Lane:** Start & learn (study; feeds 0062)
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner (17 Nov, his words): *"All the different ways of rendering – 3D page, turntable, current view and others –
to be close to each other. I want less scrolling in the menu. Possibly a sub-menu or a popup menu that hovers over the
rest, that I can drag around, for the set-up of a CNC mill for example or different mechanisms."*

0062 (the side-panel overhaul, Fable · High, runs alone and without stopping) will build what he picks. This study
finds what Blender 5.2.3 really allows, tries it in the real app, and gives him a page with pictures to pick from –
like study 0197 did (its page: `tasks/0197_page/`; use the same style, ticks and a Copy line).

## Background

- 0197's survey (report in `tasks/0197-panel-survey-for-0062.md`): ~36 sub-panels and 13 folds under 7 sections; the
  side panel all open is ~11,000 px tall at UI scale 1.5; in the real app sub-panels start closed. Ways to make an
  output are spread over **5 Scene & Render** (Image size & render, Turntable video, Web 3D model), **6 Animation**
  (Build, Make a product video, Finishing) and **7 Render queue** (still, video, every paint scheme, Start later).
- Blender's own tools for "a panel somewhere else": popover panels (`layout.popover`, `wm.call_panel` with
  `keep_open`), operator dialogs (`invoke_props_dialog`, `invoke_popup`), a second app window (`wm.window_new`, an
  area turned into a sidebar / Properties editor showing one panel category), splitting the 3D view, pie menus. Which
  of them can be **dragged**, **stay open** while the user clicks parts in the 3D view, and work on Windows is what
  this study measures – no guesses.

## What to deliver

1. **All ways to make an output, together.** An inventory (every button that renders or exports: Render image of the
   current view, Turntable, product video, animation, Web 3D model "3D page", queue still / video, every paint scheme,
   time test …: where it sits, which settings it needs). Then **2–3 layouts** where they sit side by side – e.g. one
   "Make" section with a row of big buttons, each opening its own settings; a "Render" popover in the 3D view header;
   a top-bar menu – each as a picture of the real app (prototype or mock drawn from real screenshots), with what moves
   where and what it costs 0062 (section numbers are written ~230 times in texts: say how a layout avoids renumbering).
2. **The floating set-up window.** For each Blender way above: can it be dragged; does it stay open while the user
   clicks in the 3D view (picking an axis, a part); does it survive a redraw, an undo, a file save; can it sit on a
   second monitor; does it scroll; cost per redraw. Measured in the real app under xvfb (what xvfb cannot show –
   OS window dragging on Windows – say so, and give the owner 3–4 click steps to check it on his PC).
   Then a **prototype on the branch** of the best one or two, with the owner's examples: **"Set up a CNC mill"**
   (the steps of 4 Motion > CNC machine in order: axes, spindle, tool, work zero, then the G-code step) and **"Set up
   a mechanism"** (4 Motion > Mechanisms): one step at a time, Back / Next, the step's buttons only, the 3D view usable
   behind it. Pictures (a short GIF or a strip of stills) on the page.
3. **Less scrolling in the side panel in general:** measured heights (UI scale 1.0 and 1.5) of the sections as they
   start and fully open; 3–4 options – one section open at a time (opening one folds the others), a row of section
   tabs at the top, sub-panels as popovers, rarely used settings in "More" – each with a before / after picture and
   what it breaks (real-app tests and guide pictures that click fixed spots, 0197 lists them).
4. **One page** `tasks/0200_page/index.html` (pictures in `img/`, no external links): the options of 1–3 with ticks,
   a recommended choice marked ★ with one line why, and a Copy line the owner pastes back to the lead (e.g. `0200
   pick: render B, float 2, scroll 1+4`). The lead publishes it.
5. **Report** in this file: the measurements, what was tried, the recommendation, and what 0062 must build for each
   option (files, rough size).

## Done when

- [ ] Each Blender way measured on the four questions (drag, stays open while clicking the 3D view, survives
      redraw / undo / save, second monitor) – in the report as a table.
- [ ] Prototype of the floating set-up window with the CNC mill and Mechanisms steps, on the branch, pictures on the
      page; Windows check steps for the owner.
- [ ] 2–3 "all outputs together" layouts and 3–4 less-scrolling options, each with pictures and cost for 0062.
- [ ] Page with ticks + Copy line; report filled in; `TASKS.md` row to done (pushed with `[docs]`).

## Not in this task

Building any of it in the app (0062 does). The top-bar Fresing menu, welcome and What's new (0199). Changing
`ui*.py` on `main`. Nothing of the owner's files in pictures – test models only.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
