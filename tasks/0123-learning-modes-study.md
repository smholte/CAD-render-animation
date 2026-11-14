# 0123 – Study: interactive learning with the test models (three modes, in-app guide, links from the website)

**Who:** worker · **Status:** done (14 Nov; a study: counts as no code task, starts no test run of the app) ·
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

- [x] Every question answered in the report with what was tried and measured (machine named).
- [x] Prototype on the branch: one panel button highlighted, one part highlighted with a text card, three steps of the
      crane lesson in Show me and one in Build it yourself; small screenshots described in the report (not committed if
      large).
- [x] Proposed registry format and the complete crane lesson written out.
- [x] Proposed tasks with order, lanes, model · effort, and the CLAUDE.md rule text; questions for the owner listed.
- [x] Report on `main` (task file only); `TASKS.md`.

## Not in this task

Building the modes in the app. Changing the test models (0122). Changing the panels (0062). The website itself.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 14 Nov 2026. Prototype on branch **`task/0123-learning-study`** (not
merged: no change to the app on `main`).

### In short (for the owner)

- **It can be done, and it looks smooth.** In the real app the prototype makes the button you need glow with a soft
  pulsing magenta frame, scrolls the side panel to it, makes a closed section's header glow, makes the parts glow in
  the 3D view and puts a short text card beside them (never on them), with a line to the part and "More" for the
  longer text. Show me then does the step itself; Build it yourself waits until you did it and goes on.
- **One recipe.** A lesson step does exactly what the test tour's set build does; the build task turns the tour's set
  builds into lesson steps, so View (tour), Show me and Build it yourself can never drift apart.
- **One function list** (`core/functions.py`) that the panels (0062), the lessons, the guide and the website read.
- **Order:** the function list + guide anchors first (now, before 0062), the highlight hook inside 0062, then the
  lessons, the guide inside the app, and the website's "Open in Fresing Render".
- Pictures (test crane only): `tasks/img/0123_show_me_pointing.jpg` (Show me points at *Add slide joint*, the trolley
  glows, the card sits left of it), `tasks/img/0123_show_me_done.jpg` (the step is done: green, the boom swings up and
  back once), `tasks/img/0123_closed_section.jpg` (6 Animation is closed: a dot in its header shows where to open).

### What changed (on the branch only)

| File | What |
| --- | --- |
| `fresing_render/core/functions.py` | the function list (format + the 11 entries the crane lesson uses) and `problems()`, the check that keeps it in step with the guide's anchors, the tour's stops, the PC check's lines and the lessons (no Blender: the precheck can run it) |
| `fresing_render/blender/lesson.py` | the lesson engine: the stand-in layout that marks the target button, the glow found in the side panel's own pixels, folds opened by themselves, part glow + text card, Show me / Build it yourself / Do it for me / Back / More, the Lesson panel |
| `fresing_render/blender/lesson_crane.py` | the complete crane lesson (11 steps, below), each step's `do` = the tour build's call |
| `tests/test_lesson_proto.py` | 4 tests: every crane step's `do` makes its `done` true (and it was false before); the lesson's place follows the scene; the function list against guide/tour/PC check; the card never covers the part |
| `tools/lesson_proto_app.py` | the real-app run: Build it yourself step 2 with a click where the glow is, Show me steps 3–5, Back, a closed section, costs |

The engine is not registered by the app (the test and the script register it): `main` is unchanged.

### Tested and measured

Machine: **Claude Code web session, 4 cores, no graphics card**; real Blender 5.2.3 under xvfb (software OpenGL),
window 1600 × 1000, side panel 292 × 824 px, UI scale 1.0; **test crane** (`test_crane_a.step`, draft).

- `tools/lesson_proto_app.py`, last run: **16 of 16 checks OK**, no Python error in Blender's log. Build it yourself:
  the glow was found at the *Product studio* button, the script clicked there (as a user would), the look changed, the
  lesson saw it **1.0–1.2 s** later and went on to step 3 by itself. Show me: steps 3 (rotate joint), 4 (stacked
  slide joint) and 5 (camera) each pointed first, then did the step (`['point', 'done']`); Back (undo) took the camera
  away and the lesson went back to step 5; step 7's section (6 Animation, closed) glowed at its header.
- `pytest tests/test_lesson_proto.py`: 4 passed (3 s; 68 s the first time with Blender's start).
- **Cost while a lesson points** (nothing at all without a lesson: no handler, no timer, nothing wrapped):
  - side panel, Python draw of all open Fresing panels: **2.6 ms** per redraw without the stand-in (crane tour set
    built, every panel open), **≈ 3.1 ms** with it (0.067 ms × ≈ 47 panel draws);
  - finding the marker in the side panel's pixels: **3.6 ms** per side-panel redraw (292 × 824 px, NumPy);
  - so the 20-per-second pulse costs ≈ 13 % of one core while the lesson points;
  - 3D view: 82–90 ms per redraw in software OpenGL without a lesson, 59–73 ms with part glow + card – the overlay adds
    nothing measurable here; the view's own redraw dominates. On the owner's RTX 3090 a view redraw takes a few ms
    (expectation, not measured), so the timer runs its full 20 per second and Build it yourself sees a click in
    < 0.1 s (here only ~5 ticks/s, because every tick asks for a 3D-view redraw).
- Searching the side panel by scrolling (target not on screen) took 7–9 redraws from the top. The frame found the
  button's own edge in 4 of 5 cases; once (*Add rotate joint*, aligned with *Add slide joint*) it covered both.

Found on the way (each changed the design):
1. A **marker beside the button** (an extra row) cut the label off ("Add rotate j…"); the marker **as the button's own
   icon** changes nothing in the layout. Used now.
2. A **whole page** of scrolling jumped over the camera buttons; 60 % of the panel's height per redraw does not.
3. The import already makes a **camera**, so "is there a camera" was true before the step: a `done` check must compare
   with the plain import.
4. The tour's crane camera ("Iso front-right") **has no button** of its own (only in *More*): a lesson step must call
   the button's own operator (`bpy.ops.fresing.camera_add(view="HIGH")`), not a helper that does something similar.
5. Panel classes have **no `bl_idname` attribute** in Python (Blender uses the class name): the header hook failed.
6. Changing `cls.draw` after registration **does** take effect at the next redraw (measured: 40 calls) – the hook
   needs no re-registering. But a child layout cannot be made active again inside a greyed one (`active=False` wins),
   so "grey out everything except the target" needs a per-button change: left out.

### Answers to the questions

**1. Highlighting a button.** Blender's Python cannot ask where a button is, and panels cannot be opened from Python.
What works (tried): (a) every Fresing panel's `draw` gets a stand-in layout while a lesson runs; it passes every call
through and gives the target button (operator id + its text, or a property) a **marker icon** instead of its own icon;
(b) a `POST_PIXEL` draw handler of the side panel (`region "UI"`) reads the side panel's pixels after Blender drew it,
finds the marker's exact colour and draws a three-line soft frame round the button, its alpha and width pulsing at
0.9 Hz, magenta while pointing, green when done; (c) the target's section header gets a second marker (a dot) – a
closed section glows at its header; (d) a fold (`layout.panel`) that holds the target is drawn as `panel_prop` on a
property set True, so it opens by itself; (e) neither marker on screen → the side panel scrolls (`view2d.scroll_*`)
until one is, and a target half off the edge is nudged in; (f) the side panel is switched to the Fresing tab
(`region.active_panel_category`). Rejected: `alert` (red reads as an error and does not pulse smoothly), `depress`
(already means "main button"), greying out the rest (see finding 6), an arrow in the 3D view pointing at the side panel
(the button's place is unknown there). Cost: above. **Best two** (pictures): the frame on the button; the dot on a
closed section's header.

**2. Parts and text.** Own small draw handlers, built like `hover.py`'s (magenta, a see-through fill on top of the model,
`depth_test NONE`, one triangle batch per mesh, read once with `foreach_get`), not `callouts.py` (that one draws video
labels into the render). The card: title (step k of n), one or two lines, "More" unfolds the longer text, a hint line;
dark box with a coloured edge; placed **right of the part's box on screen, else left, else above, else below**, never on
it (`place_card`, tested over 315 boxes), and never under the side panel (it is drawn over the 3D view: the free width
is the view minus the side panel); a line from the card to the part's nearest edge.

**3. One function list.** `fresing_render/core/functions.py` (plain Python, read by the app, the precheck, the guide
build and the site build):

```python
fn(id="joints.rotate",            # area.name, never changes (lessons and the website keep it)
   title="Rotate joint",          # the owner's word for it
   family="motion",               # 0062's panel sets: import, looks, motion, machines, cnc, milling, offshore,
                                  #   scene, animation, queue, web, house
   panel="FRESING_PT_motion",     # the section it lives in
   fold="",                       # the fold inside that section (ui.fold idname), "" = the section's body
   button="fresing.joint_pick_axis", text="Add rotate joint",   # what a lesson points at (or prop="background")
   guide="motion",                # <a id="…"> in docs/USER-GUIDE.md
   tour=("joint",),               # test-tour stop ids
   pccheck=("joints.rotate",),    # PC-check line ids
   lesson="crane:3",              # the lesson step that teaches it
   since="0.2.10")
```

Who reads it: **0062** groups the panels by `family` ("show only the families this project needs"); the **lessons**
point at `panel`/`fold`/`button`; the **guide** gets an anchor per entry and a link from the Lesson panel; the
**website**'s `media.json` names function ids (`"functions": ["joints.rotate", "animation.joint_step"]`) and
`build_site.py` writes "How: Rotate joint · Joint step" links to `guide/#<anchor>` under each picture, video and 3D
viewer; the **tour** and **PC check** keep their own lists but every stop and every Full line must be named by an
entry. Kept in step by `functions.problems()` in the precheck (the prototype's test runs it): an entry without a guide
anchor, a stop or line nobody names, an entry whose lesson step does not exist → the precheck fails with the sentence
to fix it, as it does for tour stops today. Today it finds 4 missing anchors for the crane's 11 entries (`camera`,
`light-look`, `poses`, `saved-scenes`): the guide has 23 anchors for 76 sections; the registry task adds the rest
(also fixes `find`, which sits on "X-ray look", not "Find & sort parts").

**4. Lessons.** One lesson per test model (= per tour set): ordered steps; a step names its function id, a short
text, a "More" text, the parts that glow, the parts selected first, `do(scene)`, `done(scene)` and an optional
`show(scene, t)` (a joint swings out and back once after Show me made it). **The set builds can become the lessons:**
`build_crane` becomes "run every crane lesson step's `do`, then the tour's own extra shots" (the sea, the looks, the
labels … are tour pictures, not set-up). Two rules from findings 3 and 4: `do` calls the button's own operator where
the button is a plain button, and for a click-on-the-model button the function the click ends in (`joints.create` with
`axis_from_hit`, as `_boom_joint` does); `done` compares with the plain import and accepts any way of doing it (the
list's +, a copy, the button – the scene decides). **Where the lesson is** = the first step whose `done` is false: undo,
Back (= undo), saving half-way and opening the project again (`scene["fr_lesson"]`) all land right without own state.
A model update keeps the parts' names, so the checks keep working; a part the update removed makes its step "not
done" and the card says the part is gone. The user doing something else: the lesson keeps pointing; another tab or a
closed side panel → the Lesson panel says where to look (the prototype switches to the Fresing tab at each step).
Build it yourself: **Do it for me** runs `do`; done → green for 1.4 s, then the next step. Show me: the glow shows for
1.6 s once it is on screen, then the app does the step and waits for **Next**.

**The crane lesson** (written out completely in `lesson_crane.py`, 11 steps; Show me ran 3–5, Build it yourself 2):

| # | Function | Text (short) | Parts | Show me does | Done when |
| --- | --- | --- | --- | --- | --- |
| 1 | import.step | Import STEP… reads the crane; it stands still | – | (the lesson starts after it) | a model is in the project |
| 2 | looks.light_look | Product studio sets background, light, floor | – | `light_look(look=PRODUCT)` | the Product look is what the settings show |
| 3 | joints.rotate | Add rotate joint, click the boom's pin | BOOM.ASM, BOOM.PIN | `tour._boom_joint` (the click's own function) | a rotate joint moves BOOM.ASM |
| 4 | joints.stack | Add slide joint along the boom: it rides on the boom's joint | TROLLEY.ASM | slide joint, base BOOM.ASM | a slide joint moves TROLLEY.ASM |
| 5 | scene.camera | One more camera: 3/4 hero, high | – | `camera_add(view=HIGH)` | 2 app cameras |
| 6 | scene.save | Saved scene keeps camera, look, pose, visibility | – | `states.save_shot` | a saved scene |
| 7 | animation.add | + in 6 Animation | – | new animation from the saved scene | an animation |
| 8 | animation.joint_step | Boom 0° → 35° in 2 s | BOOM.ASM | `tour._joint_step` | a joint step |
| 9 | animation.build | Build & play | – | `tour._bake` | an animation is built |
| 10 | poses.explode | Explode, keep it as a scene | – | `states.explode` + save "Exploded" | a scene "Exploded" |
| 11 | queue.still | A picture of the saved scene in the render queue | – | `queue.add_job(STILL)` | the queue has a job |

**5. The guide in the app.** Measured: the guide is 76 sections (average 3 kB of text, longest 25 kB), 98 pictures,
4.6 MB as one HTML file. Blender cannot show HTML; a Text editor shows raw Markdown without pictures; drawing the whole
guide with `blf` is a big job. Proposal (good enough and easy): (a) a **Guide** panel in the side panel that shows the
section of the function you are on (the Lesson step, or the section the mouse was last in) as wrapped text with its
pictures as icons (`bpy.utils.previews` + `template_icon`, both used by the prototype: the marker icons) – hide it by
folding it; (b) **pop out**: the same panel as a floating box (`wm.call_panel(keep_open=True)`) or in a new Blender
window (`wm.window_new` with a 3D view showing only its side panel – that one can be made as big as you like); (c)
**Open the whole guide here** = the browser at that section. On Windows `os.startfile` drops a `#section`, so the app
writes a one-line jump page (`<meta http-equiv="refresh" content="0;url=…/user_guide.html#motion">`) and opens that –
Windows-only, to be tried on the owner's PC (a PC-check line). Not tried in the real app in this study.

**6. Website links.** Today the installer registers nothing and the app reads no argument. Proposal: `Install.bat` adds
a link type **`fresing://`** for the current user only (`HKCU\Software\Classes\fresing`, no admin; `Uninstall.bat`
removes it) whose command starts the launcher with the link after `--`. The app template reads it at start and accepts
only known ids (`fresing://lesson/<lesson id>?mode=show|build|view&min=<version>`): never a path, never code – a link
on any web page can start it. Older app than `min` → it offers the update first. Not installed → the website's
link goes to a small page `open.html#crane` that tries the link and after 2 s shows "Fresing Render not installed?
Download it" (browsers give no answer when no program takes a link type). Windows-only: independent review + a
self-test line. **Models:** test crane, test mill and every app-made test model are the app's own (GPL as the app) and
ship as today; **Thor** and the **CEB press** are CC BY-SA 4.0: may be offered, as a download on demand (not in every
install), with the credit and licence shown in the lesson and the converted STEP under the same licence;
**IEA 15 MW** Apache-2.0: may be offered with its NOTICE and the "modified by Fresing" note; the **demo vessel** is
invented: may be offered (it is made by Help > Make demo project already); **Fresing 400: never** (`build_site.py`
already refuses it). **Guide links per function: always**, from `media.json` `functions` through the list (no app or
licence needed).

**7. Order and split** – see "Proposed tasks". What the list must know before 0062: for every function its `family`,
`panel` and `fold` (0062 sorts the panels by them) – so functions added before 0062 just add their entry, and 0062
reads where everything is from one place.

**8. What a new function's task adds** – the rule text below; about **20–40 minutes** of a worker's time on top of
today's tour stop (an entry: 5 min; an anchor: 2 min; a lesson step with its texts and `done` check, run once in Show
me: 15–30 min).

### Proposed tasks (the lead numbers them)

| Order | Task | Lane | Before/after | Model · effort |
| --- | --- | --- | --- | --- |
| 1 | **Function list + guide anchors**: `core/functions.py` with every function (~120 entries: each tour stop, Full PC-check line and guide section named), an anchor on every guide section (`build_guide.py` lists `###` in the contents), the precheck check, guide links on the website (`media.json` `functions`, additive in `build_site.py`). No UI change. | Learning (+ Docs; additive in `tools/ci_precheck.py`, `build_site.py`) | **now, before 0062**; can run beside the open tasks | Sonnet · Medium |
| 2 | **Inside 0062**: the shared panel base draws through the lesson hook (no swap at run time), `fold()` uses `panel_prop` with a property per fold (lessons and the tour can open folds), a header slot for the marker, families from the list | (0062) | in 0062 | as 0062 |
| 3 | **Lessons: Show me + Build it yourself** – the engine from this prototype, Help > Learn (a list of test models, each with View / Show me / Build it yourself), the crane, mill and vessel sets' builds made of lesson steps, a PC-check line and a tour stop, guide chapter | Learning | after 0062 (and after 0122: both touch the tour sets) | Opus · High |
| 4 | **The other sets' lessons** (about 34 sets, along the pattern of 3) | Learning | after 3 | Sonnet · Medium (two sessions) |
| 5 | **Guide inside the app**: Guide panel per function, pop-out, the browser at the section (jump page), Lesson panel link | Learning (new `ui_guide.py`) | after 0062, beside 3 | Opus · Medium |
| 6 | **"Open in Fresing Render"**: `fresing://` in the installer (current user), the app reads it (ids only), lesson models downloaded on demand with credit, `open.html` fallback on the site | Quality & delivery (installer) + Web 3D (site) | after 3; Windows-only → independent review | Opus · High |

### Rule text for CLAUDE.md section 6 (extends the tour-stop rule; to add with task 3)

> **Function list, guide and lesson** (owner's wish, task 0123): a task that adds a function the owner can see adds,
> in the same task, (1) its entry in `fresing_render/core/functions.py` (id, title, family, panel, fold, button or
> setting, guide anchor, tour stops, PC-check lines, lesson step); (2) its guide section with `<a id="…"></a>` above
> the heading; (3) its test-tour stop (as today); (4) its step(s) in the lesson of its test model: `do` = the button's
> own call (or, for a click on the model, the function the click ends in) – the tour's set build runs the same steps –,
> `done` = a check on the scene that is false on the plain import and true however the user did it, a short text and a
> "More" text; run it once in Show me. The precheck refuses an entry, stop, line or lesson step that is not linked.

### Questions for the owner

1. The highlight: the **soft magenta frame** on the button and a **dot** on a closed section's header (pictures) – good?
   (Greying out everything else is possible only with more work per button.)
2. **Show me's pace:** point 1.6 s, do it, then wait for *Next* (prototype) – or play on by itself with pauses?
3. **Build it yourself:** accept the step however you did it (recommended), or only with the glowing button?
4. Lessons on the **site models** (Thor, brick press – CC BY-SA, with credit; IEA turbine – Apache): offer them in the
   app as downloads? And the demo vessel?
5. The **guide inside the app** as a side-panel section per function + pop-out window, the full guide in the browser –
   enough?
6. May the installer register the **`fresing://` link** (current user only, removed by Uninstall) for "Open in Fresing
   Render" on the website?

**Open points:** the prototype's glow once covered two aligned buttons (0062 can keep the target's edge readable, or
the build task measures the text width); scrolling to the target starts at the top (could start in the right direction
from the known panel order); the guide panel and the `fresing://` link were not tried (Windows-only parts on the owner's
PC); Show me for click-on-the-model steps calls the click's function directly – showing a moving "mouse" on the part
first is possible (a dot travelling to the pin) and left for task 3.

Subagents: two read-only mapping agents (tour + crane set build; guide, site, installer) – their findings are in the
answers above; nothing they wrote was used as code. No independent reviewer (study only; task 3 should give the engine
to one).
