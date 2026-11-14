# 0123 – Study: interactive learning with the test models (three modes, in-app guide, links from the website)

**Who:** worker · **Status:** open – can start (a study: counts as no code task, starts no test run of the app) ·
**Branch:** `task/0123-learning-study`
**Started by:** lead chat, 14 Nov 2026 (owner's wish) · **Lane:** Learning (new). Findings + a small prototype; no change
to the app on `main`. The report (this file) goes to `main`; the prototype stays on the branch (name it in the report).
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation" (the prototype
needs the real Blender under xvfb)

## Goal

The owner wants the app to **teach itself** with the test models, as part of the full UI overhaul (0062). This study
works out how, proves the hard parts with a small prototype, and proposes the build tasks and their order. It also
designs **one list of the app's functions** that the panel families (0062), the lessons, the user guide and the website
all read, so that adding a new function later means adding one entry, one test model set and one lesson – nothing
scattered.

## The owner's wishes (14 Nov 2026)

1. **Three modes per test model**:
   - **View** – open a test model's finished project and look for yourself. **Keep this as it is today** (the test
     tour: Help > Make test tour project, Go per stop).
   - **Show me** – the app walks through how the model was set up, function by function: **smooth highlights in the
     UI** (the panel and button being used), **highlights on the model** (the parts it acts on), a little text next to
     it. Text short; **expandable** for more.
   - **Build it yourself** – start from the plain imported model (still standing, nothing set up); the app helps you
     make the set-up yourself, step by step: shows where to click, waits, sees that you did it, goes on.
   It must **flow smoothly**.
2. **The whole user guide inside the app**, if it can be done easily: open it, hide it easily, or pop it into a small
   window you can enlarge.
3. **On the website**, next to every render, video or 3D viewer: a link to **open it in Fresing Render** as a test
   model with the three modes – only when the model's licence allows it – and **always** a link to the place in the
   written guide for each function the preview uses.
4. **Adding a new test when a function is added must be easy**, and it all must work well together.

## Questions to answer (with measurements or a tried prototype, not guesses)

1. **Highlighting a button in Blender's side panel.** Blender's Python cannot ask where a button is on screen. Work out
   and try what works: the app's own panels drawing the lesson's target differently (`alert`, `depress`, an arrow or
   a "Do this" row, the target's folds opened, the panel scrolled to it), a pulse by timer redraws, a viewport overlay
   with a line towards the side panel, … Which looks "smooth" enough? What does it cost per redraw (the panels redraw
   often – CLAUDE.md section 8)? Small screenshots of the best two for the owner.
2. **Highlighting parts on the model and text next to them**: reuse `hover.py`'s draw handlers (magenta overlay, POST_PIXEL
   text) or `callouts.py`? Text card size, expandable "More", where it sits so it never covers the target.
3. **One function list** (registry): proposed format and place (e.g. `core/functions.py`): id, title, family (for 0062's
   panel sets), panel/fold path, the operator(s) and properties of each step, guide anchor, tour stop(s), PC-check line.
   How tour stops, the 0062 families, the lessons, the guide's anchors and the site's links read it; tests that keep
   them in step (a function without a guide anchor or a lesson fails the precheck, as tour stops do today).
4. **Lessons**: format of a lesson per test model – ordered steps, each: function id, what to do, the parts it acts on,
   how the app does it in **Show me** (the same calls the tour's set build makes today – can the set builds *become*
   the lessons, so there is only one recipe?), how **Build it yourself** knows the user did it (a check on the scene),
   "Do it for me" and "Back". Undo, saving in the middle, a model update during a lesson, the user doing something else.
   Write one lesson completely (the test crane) as the example.
5. **The guide in the app**: options and cost – a Blender window with the guide as text + pictures drawn by the app,
   a Text editor area, the system browser beside Blender (`build_guide.py` already makes `user_guide.html`), a small
   floating window that can grow. Which is "easy" and good enough? Jump from a lesson step to its guide section and back.
6. **Website links**: "Open in Fresing Render" – a link scheme registered by `Install.bat` for the current user only
   (no admin; Windows-only code → independent review), what happens when the app is not installed or too old, which
   lesson and model it opens. Per site model (test mill, Thor CC BY-SA 4.0, CEB press, IEA turbine Apache-2.0, a later
   demo vessel; **never the Fresing 400**): may it ship or be downloaded into the app as a lesson model, and with what
   credit? Guide links per function from `media.json` (`functions: [...]`) through the registry.
7. **Order and split**: which pieces go **before 0062** (e.g. the registry and guide anchors), which **inside 0062**
   (the highlight hook in the shared panel helpers, families from the registry), which **after** (Show me, Build it
   yourself, in-app guide, website links); lanes, model and effort per proposed task. The owner thinks more functions
   should come before the UI overhaul so it is sorted right the first time: say what the registry must already know
   for that.
8. **What a new function's task must then add** (the rule for CLAUDE.md section 6, replacing or extending the tour-stop
   rule), and how long it takes a worker.

## Done when

- [ ] Every question answered in the report with what was tried and measured (machine named).
- [ ] Prototype on the branch: one panel button highlighted, one part highlighted with a text card, three steps of the
      crane lesson in Show me and one in Build it yourself; small screenshots described in the report (not committed if
      large).
- [ ] Proposed registry format and the complete crane lesson written out.
- [ ] Proposed tasks with order, lanes, model · effort, and the CLAUDE.md rule text; questions for the owner listed.
- [ ] Report on `main` (task file only); `TASKS.md`.

## Not in this task

Building the modes in the app. Changing the test models (0122). Changing the panels (0062). The website itself.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
