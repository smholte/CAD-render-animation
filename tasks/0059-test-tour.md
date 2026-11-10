# 0059 – Test tour: one project the owner opens to see every function work, and an automatic run through it

**Who:** worker · **Status:** done (0.2.47) · **Branch:** `ccr-5464fcca-ugf81y` (the session's branch; `task/0059-test-tour` was pushed at the start pointing at `main` and is unused: delete it on github.com)
**Started by:** lead chat, 9 Nov 2026 (owner: "make it easier/faster for me to check the functions – a test Blender
file to open and see the functions work, and a test running through it")
**Lane:** Quality & delivery + PC check – new files `blender/tour.py`, `blender/ops_tour.py`, `ui_tour.py` (its own
panel or sub-panel), `pccheck/tour.py` (the automatic run); `pccheck/ops.py` / `checks.py` only to add the mode
"Tour" and reuse the report code; new generic test models in `tests/data/` if needed; guide chapter "Test tour";
CLAUDE.md (one rule, see 6)
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as 0042 coolant (Machining lane): do not change machining, chips, air, coolant, G-code or
toolchange code – only call them. If a function needs a fix to show properly, write it as an open point.

## Why

The owner tests on his own PC (Windows 11, RTX 3090) but has little time. His open list: cylinders, mechanisms,
decals, chips, video finishing, labels, way covers, G-code, air, tool library, the manual-change hand on a BT30
holder, the ATC carousel, cut faces and raw stock, the 0046 materials and Wear, two copies of one STEP, model update,
render queue. Today each needs his own model and set-up. The PC check Full tests functions but is made for numbers,
not for looking at a function and saying "yes, that's right".

## What to build

1. **"Make test tour project"** (button with tooltip, next to the PC check in the app): builds
   `Documents\Fresing Render\Test tour\Test tour <version>.blend` fresh from generic test models in the repository
   (the repository is public: only generic models – `tests/data/*.step` and the PC check's own scenes; new ones if
   needed, e.g. a small mill with a BT30 spindle and an 8-pocket carousel). Built for the installed version, so it is
   never out of date. Takes at most ~2 minutes; a progress line.
2. **Tour panel** in that project: numbered stops (about 20–30), each with
   - a title and one or two lines "what you should see" (plain words, no code terms);
   - **Go** – sets everything up: opens the saved scene, camera, frame range, plays or scrubs to the right frame,
     selects the part, opens the right panel;
   - **OK / Problem** and a short note field;
   - stops grouped: Look (materials, Wear, cut faces + raw stock, decals, painted faces, surroundings, light looks),
     Motion (joints, stacked joints, cylinders by stroke, mechanisms, way covers, two copies of one STEP, model update
     A → B), Machining (G-code run, three tools with M6 + G43, manual change with the hand on a **BT30 holder**, ATC
     carousel, chips, air blast), Output (stills, turntable, video finishing: title/end cards, captions, watermark,
     labels, render queue still + video, 1:1 / 9:16).
   - **Copy results**: one short text (version, PC, per stop OK/Problem + note) to the clipboard and a `.txt` next to
     the project, to paste into the lead chat.
3. **Automatic run ("Tour" mode of the PC check, also a button in the tour panel):** goes through every stop
   unattended, renders each one (Cycles GPU still and/or a short EEVEE clip, small sizes), checks what can be checked
   by numbers (the same kind of checks as the PC check: positions, frame counts, files made) and writes the PC check
   style HTML report with a picture or clip per stop, the "what you should see" text and OK/FAILED for the number
   checks. Time on the web machine in the report; target ≤ 15 min on the owner's PC. The owner can start it, walk
   away, and later look at the report and tick OK/Problem in the tour panel.
4. **Tests:** the tour project builds on the web machine; every stop's Go works (no errors, the expected scene/frame
   is set); the automatic run finishes with pictures for every stop (CPU, tiny sizes in CI); Copy results text.
5. **Guide chapter "Test tour"** with a picture of the tour panel; tooltips on every button.
6. **Keep it current:** add a rule to CLAUDE.md (definition of done): every new visible function adds its tour stop
   (one entry in `blender/tour.py`). Make adding a stop one small entry (title, text, set-up function, optional
   number check). Coolant (0042, running at the same time) and hoses/drag chains (0058) add theirs in their own tasks
   – leave a note in their task files' Done-when lists.

## Done when

- [x] Make test tour project → a working tour project in ≤ ~2 min; all stops with Go, OK/Problem, note.
- [x] Copy results; automatic run with the HTML report (picture or clip per stop).
- [x] Tests as in 4; GitHub green.
- [x] Guide chapter, tooltips, CLAUDE.md rule, notes in 0042 and 0058.
- [x] Merged to `main`, next free version, released (CLAUDE.md section 7).
- [x] Report filled in, with the list of stops; `TASKS.md`: 0059 done.

## Not in this task

New app functions or fixes (write problems found as open points). Coolant's and hoses' own stops (their tasks).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 9 Nov 2026. Version **0.2.47**.

**What changed:**
- `blender/tour.py` – the stops and the sets. 27 stops in 4 groups, 14 small projects (the crane is the hub,
  "Test tour <version>.blend"; the others in "Test tour <version> files\"). Adding a stop = one `stop(...)` entry
  (title, what you should see, where, set, `shot` via `_shot(b, "@id")` or `animation`/`at`/`play`, `select`, a number
  `check`, optional `auto`). Go = `apply()`: the stop's saved scene (camera, pose, visibility, looks, background, size)
  or its animation built (start scene = the stop's shot) at its frame; milling read again; parts selected; labels only
  on the Labels stop. Results (OK / Problem / note, the stop picked) in "Test tour <version> results.json", shared by
  all projects of the tour.
- `blender/ops_tour.py` – Help > **Make test tour project…** (background Blender `launcher.py -- tourbuild <folder>`,
  progress in the status bar, a popup with **Open test tour project** when done; log "Make test tour log.txt"),
  Help > **Open test tour project**, Go (opens another project and sets the stop up after loading: load_post handler +
  timer, then Go again with its own undo step), OK / Problem (second click takes it off), Note…, **Copy results**
  (clipboard + "…results.txt"), **Run the whole tour by itself** (= PC check mode Tour), Show the tour folder. A tour
  project opens with the side panel on the Fresing tab.
- `blender/ui_tour.py` – the **Test tour** panel (only in a tour project, on top of the Fresing tab): stops in folds
  per group with a mark icon, the picked stop's box (what you should see, where, big Go, OK / Problem, note, Next),
  Copy results, More (run by itself, folder, make again).
- `pccheck/tour.py` + `runner.py`/`core.py`/`ops.py` – PC check mode **Tour** ("Test tour" in the PC check dialog):
  builds a fresh tour in its work folder, one line per stop (Go + number check + a picture; motion stops three frames
  side by side; the finished video read back from the MP4: title card, motion, end card; labels, queue and 9:16 / 1:1
  through the queue's own code). Report "Fresing Render test tour.html" with a card per stop. Pictures 480 px on the
  processor (Draft), 960 px on the graphics card (Preview).
- `blender/queue.py` – one additive line: a job may carry `scale` (only the tour uses it: video frames at a quarter of
  540p on the processor, half on the graphics card).
- PC check Full line `tour.make` (builds the tour, Go + check of every stop, no pictures) – so the Windows job also
  builds the tour on Windows at every push. `MIN_LINES_FULL` 44 → 45, new `MIN_LINES_TOUR` 28 (precheck counts the
  `stop(` entries).
- Guide chapter "Test tour" with `docs/img/panel_tour.png` (`guide_screens.py` mode `tour`); CLAUDE.md rule "Test tour
  stop" (section 6) + layout and test table; notes in 0042 and 0058.

**The stops:** Look: 1 Ready-made materials and Wear · 2 Painted faces · 3 Logos and stickers · 4 Cut faces and raw
stock · 5 Surroundings: open sea · 6 Light looks. Motion: 7 Joint: the boom turns · 8 Stacked joints: boom + trolley ·
9 Exploded view · 10 Cylinder: stroke drives the arm · 11 Mechanisms: scissor lift, crank · 12 Way cover follows the
axis · 13 Two copies of one STEP · 14 Model update A → B. Machining: 15 G-code program runs the machine · 16 Three
tools with M6 and G43 (BT30 face mill, end mill, chamfer mill) · 17 Tool change by hand (BT30) · 18 Tool changer:
8-pocket carousel · 19 Chips fly · 20 Air blast. Pictures and videos: 21 Still picture · 22 Camera views and blur ·
23 Turntable video · 24 Finished video: cards, captions · 25 Labels with lines · 26 Render queue: picture + video ·
27 Upright 9:16 and square 1:1.

**Tested and measured** (web machine: 4 cores, Intel Xeon 2.3 GHz, no graphics card; generic test models only):
- Make test tour project: 14 projects in 20–27 s (bpy module and real Blender 5.2.3).
- Automatic run (mode Tour) in the real Blender from the installed launcher (`ci_real_app.py --only tour`): 28/28 OK
  in 191 s (finished video 37 s, queue 40 s, every other stop 2–8 s). On the owner's PC: expectation, not measured.
- `tests/test_tour.py`: 37 tests (every stop's Go + check, buttons, marks, Copy results, automatic run for 5 stops)
  in about 1 min. Real-app `ui_test_tour.py` 15/15 (Make, Open, Go here: built + playing + camera view; Go into another
  project: opened and set up after loading; marks, note, Copy results). PC check line `tour.make` 23 s.
- Pictures of all 27 stops looked at once (contact sheet of the report): every stop shows its model and function.
- GitHub: see the run in the commit history of this task (runs: 1 full run of the branch, then the reuse run on main).
- Helper-agent review skipped: no Windows-only code (the build's subprocess start is the PC check's existing pattern;
  the Windows job runs `tour.make` inside the PC check Full).

**Open points / follow-up tasks:**
1. **Bug (found by the tour): a still with a logo or a watermark comes out black when the timeline is not on
   frame 1.** `render.render_still` → `video.finish_picture` renders its throw-away sequencer scene with
   `bpy.ops.render.render(scene=enc.name)`, which takes the frame of the scene in the context (frame 26 → nothing in
   the sequencer → black). Repro: crane, brand logo, 5 Scene & Render logo on pictures "Bottom right", timeline at 26,
   render a picture → mean brightness 0.0 (at frame 1: 0.8). Probably also queued pictures of an animation frame
   (0.2.46) with logo or watermark. Fix: render with `bpy.context.temp_override(scene=enc)` (the tour's own video
   read-back does exactly this). The tour keeps the still logo off until then. Suggest: into 0060 small fixes.
2. Go cannot open a closed sub-panel (Blender has no way to do that from Python): each stop says where to look
   ("Where: 4 Motion > Cylinders").
3. Labels are drawn only in renders, not in the view: the Labels stop says so; the automatic run shows them.
4. The tour's projects are saved in the background, so their window layout is Blender's default; the app shows the
   side panel on the Fresing tab when a tour project opens.
5. Coolant (0042) and hoses/drag chains (0058) add their stops in their own tasks (notes in their Done-when lists).
