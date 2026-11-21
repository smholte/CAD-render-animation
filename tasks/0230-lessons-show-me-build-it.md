# 0230 – Lessons: Show me and Build it yourself – the engine, the Learn window, the crane and mill lessons

**Who:** worker · **Status:** done (0.2.187, 21 Nov) · **Branch:** `claude/clever-cray-qd0bn8`
**Started by:** lead, 20 Nov 2026 (study 0123 task 3; owner 15 Nov answers; owner 20 Nov: "the test tour is the users'
learning environment"; owner 16:35: brief the learning sets and the lessons task together) · **Model:** Opus · effort High
**Area:** Learning lane – new `blender/lesson.py` (engine), `blender/lessons/` (one module per set: `crane.py`,
`mill.py`), `blender/ui_lesson.py` (Lesson panel / card), `blender/ops_learning.py` (fills the greyed `learn_lesson`
hook of 0208 + the Learn window), `blender/ui_topbar.py` (one Fresing-menu entry **Learn…** + `entries()`),
`core/functions.py` (`lesson=` on the crane's and mill's entries; `problems()` checks lessons), `blender/tour.py`
**only the crane hub set (`HUB_SET`, all its stops) and the `mill` set**, `blender/highlight.py` only if the engine needs
a hook, the precheck's lesson check, `docs/USER-GUIDE.md` (new chapter "Learn"), PC-check line, tests, CLAUDE.md section
6 (the lesson rule).

## Goal

The owner's three ways to learn the app on the sample projects (the test tour sets): **View** (the finished set, its
stops with Go – today's tour), **Show me** (the app does each step itself while pointing at the button and the parts,
with a short card) and **Build it yourself** (the user does each step; the app points, waits until the scene shows the
step is done, however it was done, and goes on). This task builds the engine, the **Learn** window and two complete
lessons (crane, mill). The other sets' lessons follow along the same pattern (a later task, after the learning-set
environments 0231, 0233–0235).

## Background

- **Study 0123** (`tasks/0123-learning-modes-study.md`): the engine design (answers 1, 2, 4), the crane lesson written
  out (11 steps, table in the report), the costs measured, findings 1–6 (marker as the button's icon, scroll 60 % per
  redraw, compare `done` with the plain import, call the button's own operator, panel classes have no `bl_idname`, no
  greying of the rest). Prototype code on branch **`task/0123-learning-study`** (`lesson.py`, `lesson_crane.py`,
  `tests/test_lesson_proto.py`, `tools/lesson_proto_app.py`) – start from it, do not merge the branch.
- **Owner's answers (15 Nov):** the highlight is **not** the magenta frame – since 0062 it is `blender/highlight.py`
  (look **C bright** for buttons, sections 5 + 4, parts 3 + 1, **Fresing Green**, Preferences > Lesson highlight;
  `highlight.point(...)`, `point_function(fid, parts)`, `clear()`) – **use it, no own frame**. Show me: **wait for Next by
  default, a "Play on" switch** that runs on with pauses. Build it yourself: **accept the step however it was done**
  (check the scene). Lesson downloads (Thor, brick press, IEA turbine), `fresing://`, the guide inside the app: **not
  this task**.
- **0208** left the hooks: Fresing menu > My learning list… shows a greyed **Show me** (`fresing.learn_lesson`, `poll`
  False) and the declutter question's learn buttons; fill them: a function whose `lesson=` is set opens its lesson at
  that step.
- **Function list** (`core/functions.py`): `lesson="crane:3"` field exists, empty everywhere; `problems()` already has a
  `lessons=` argument. The precheck must refuse a `lesson=` that names no step and a lesson step whose function id does
  not exist.
- **One recipe** (0123): a lesson step's `do` is the tour build's call. Turn the **crane hub's** set build into "run every
  crane lesson step's `do`, then the tour's own extra shots", same for `mill` – View, Show me and Build it yourself can
  then never drift apart. Every existing crane / mill stop and its check stay as they are (numbers may not change).
- **The app's aim (owner 19 Nov):** as simple as possible for users who do not know Blender. 0221 (running, nearly
  done) hides Blender's right-hand column; the lesson must work with it hidden and shown. 0222's packages A–C come later
  in the Start & learn lane (splash, keys, menus) – the engine must not depend on Blender's menus.
- **Crane hub small items from study 0224** (this task owns the hub): the stop **`sea`** (the crane's desk base floating
  on the water) → **drop it** (vessel, sea_cable show the sea; move its function link to `sea_cable`); the stop
  **`finishing`**: add a picture card + music (functions `animation.cards`, `animation.music` get `tour=` to it). The hub
  stays in the plain studio (its fitting environment).

## What to do

1. **Engine** (`lesson.py`): a lesson = ordered steps; a step = function id, short text, "More" text, parts that glow,
   parts selected first, `do(scene)`, `done(scene)` (false on the plain import, true however done), optional
   `show(scene, t)`. Where the lesson is = the first step whose `done` is false (undo, Back, save + reopen all land right;
   `scene["fr_lesson"]` keeps only which lesson). Pointing through `highlight.py`; the card beside the parts, never on
   them, never under the side panel (0123's `place_card`). Nothing runs without a running lesson (no handler, no timer).
2. **Show me:** point (about 1.6 s once on screen), `do`, optional `show`, then wait for **Next**; **Play on** switch
   (remembered per user) runs on with pauses. **Build it yourself:** point, wait for `done` (a cheap check on a timer
   only while a lesson runs), green, next; **Do it for me** runs `do`; **Back** = undo.
3. **Learn window** (Fresing menu > **Learn…**, also from the welcome's "take the test tour" line if it fits): the
   learning sets in a list (title, one line, what it teaches), each with **View** (makes / opens the tour project at that
   set, as today), **Show me** and **Build it yourself** (greyed with "Lesson coming" for sets without a lesson). Show me
   / Build it yourself open a **new project with the set's plain import** (the set's model, its environment) and start
   the lesson. Every button a tooltip.
4. **The crane lesson** (0123's 11 steps, adjusted to today's app – 0062's panels, 0199's menu, 0221) and **the mill
   lesson** (import the test mill, set it up as a CNC mill, work zero, a tool, load the program, Build, a still of the
   cut – about 8–10 steps; from the `mill` set's build). Each step's `do` = the button's own operator, or for a click on
   the model the function the click ends in (0123 finding 4).
5. The **0208 hooks** live: My learning list's Show me / Build it yourself for a function with `lesson=`.
6. Guide chapter "Learn" (+ a picture of the Learn window and one of Show me pointing, test crane only); function-list
   entries (`learn.window`, `learn.show_me`, `learn.build`, `since=`); `lesson=` on every crane / mill function a step
   teaches; PC-check line (runs the crane lesson in Build it yourself with Do it for me to the end, and Show me's first
   three steps); a tour stop "Learn" in the hub; the CLAUDE.md section 6 lesson rule (0123's text, adjusted).
7. **Independent check:** give a subagent that did not write the engine the job of breaking it (undo in the middle, save
   + reopen half-way, the side panel on another tab or closed, Client view on, a model update half-way, Blender's column
   shown / hidden). Send its findings back to the author.

## Done when

- [ ] Crane lesson: Show me runs all 11 steps; Build it yourself finishes by clicking where the highlight points (real
      app, as 0123's `lesson_proto_app.py`) and by Do it for me; a step done another way (copy, the list's +) counts
- [ ] Mill lesson: both modes end with the cut and the still; the `mill` set's stops and checks unchanged
- [ ] View / Show me / Build it yourself give the same scene for each set (one test per set compares them)
- [ ] Cost: nothing without a lesson; while pointing, the side panel and 3D view costs measured (numbers in the report)
- [ ] Crane hub: `sea` stop gone (its function linked to `sea_cable`), `finishing` with card + music; `changed=` on the
      hub and `mill`, re-recorded; `tests/test_tour_clash.py` 0 clashes
- [ ] Precheck refuses a broken `lesson=` link; guide, function list, PC-check line, tour stop, CLAUDE.md rule
- [ ] Independent tester's findings fixed or listed; full suite green; report filled in, merged, released

## Not in this task

The other sets' lessons (later, after 0231 and 0233–0235 settle the sets); the guide inside the app; `fresing://`;
lesson downloads; any tour set other than the crane hub and `mill`; 0222's Blender-interface packages.

## Design (worker, 20 Nov)

- `blender/lesson.py` – the engine: `Lesson` / `Step` (function, title, say, more, parts, select, do, done, show, point),
  `LESSONS`, `first_not_done`, `run` (View's recipe: every step not done → `do` → `done` must be true), the running
  lesson (`start(scene, id, mode, at)`, `stop(forget)`, `do_step`, `next_step`, `back`, `tick(scene, now)` = the timer's
  look, `advance`), pointing through `highlight.point_function` / `point` (+ `keep_clear("FRESING_PT_lesson")`), the
  card (`place_card`, draw handler on the 3D view), the side panel scrolled to the target, handlers only while a lesson
  runs (`handlers_left`), `new_project` / `open_lesson` (waits for `editors.busy()` before pointing: Blender 5.2.3
  crash).
- `blender/lessons/crane.py` (11 steps), `lessons/mill.py` (13 steps); `tour.build_crane` / `build_mill` run them first.
- `blender/ui_lesson.py` – the Lesson panel + `fresing.lesson_*`; `ops_learning.py` – `fresing.learn_lessons` (Learn
  window), `learn_start`, `learn_view`, `learn_lesson` (0208's hook, at the function's step).
- `core/functions.py` – `read_lessons` (AST, no Blender), `problems(lesson_steps=)`; `lesson=` links; `learn.*`.
- `highlight.py` – marks an `operator_menu_enum` too (the animation's + for a step); `_show_tab` waits for the editors.
- Tests: `tests/test_lessons.py` (bpy module), `tools/ui_test_lesson.py` (real app, group tour-b), PC-check
  `app.lessons`, tour stop `lessons`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 20 Nov 2026. Branch `claude/clever-cray-qd0bn8` (the session's branch;
the brief's `task/0230-lessons` was not used). Version **0.2.189** (0.2.181–0.2.188 were taken by other tasks meanwhile).

**What changed:**
- **Engine** `blender/lesson.py`: lesson = steps (function, title, say, more, parts, select, do, done, show, point);
  `run` = View's recipe (each step not done → do → done must be true); Show me (point → target seen 1.6 s, or 4.5 s
  at most → do → wait for Next / **Play on** in the preferences) and Build it yourself (done checked on a 0.1 s timer,
  "Done" 1.4 s, next); Do it for me, Back (= undo), More, mode switch, Stop; pointing through `highlight.py` (Lesson
  panel kept clear), the card beside the parts (`place_card`), the side panel scrolled to the target. Where the lesson
  is: `place()` – from where it was, back while the step before is undone, on past what is done (so a later setting
  change does not rewind it); `scene["fr_lesson"]` + `fr_lesson_step` for going on after a reopen. Nothing runs
  without a lesson (`handlers_left()`); the app's own clicks of Show me are not counted as the user's use.
- **Lessons** `blender/lessons/crane.py` (11 steps, 0123's list on today's panels) and `mill.py` (13 steps). Every
  `do` is the button's operator (light look, camera, save scene, +, add step, Build, Explode, queue, Use as bit /
  workpiece) or the function a click on the model ends in (boom pin → `tour._boom_joint`, slide joints →
  `joints.create`); step 1 re-imports the model when undone past the import.
- **The mill lesson follows the `mill` set** (joints X/Y/Z + two joint steps), not a G-code program as the brief's
  sketch said – the set has none, and its stops had to stay unchanged. A G-code lesson belongs with the gantry set.
- **Tour**: `build_crane` = `lesson.run("crane")` + the tour's extra shots; `build_mill` = `lesson.run("mill")`.
  **Every crane and mill stop's check gives the same numbers as before** (compared before/after: only the planned
  changes differ – `finishing` now with a picture card + music, the menu has 15 entries). `sea` stop dropped
  (`scene.surroundings` → `sea_cable`); new stop `lessons` (hub); `changed="0.2.189"` on crane + mill, recorded. The
  mill set's close-up camera is now the "3/4 hero, high" button on the selected block (the shot is called "Close-up").
- **Learn window** (Fresing > Learn…, `fresing.learn_lessons`): Crane and Milling a slot with View / Show me / Build it
  yourself, the 46 other sets with View (one header line says their lessons are coming, instead of 92 greyed buttons).
  Show me / Build open a new project with the plain import (asks first when the open project has unsaved changes).
- **0208's hooks**: My learning list's Show me + Build open the function's lesson at its step; the unused-panel question
  offers "Show me in a lesson". **Lesson panel** `ui_lesson.py` (on top of the Fresing tab; in a reopened project it
  offers to go on). **Client view**: the lesson pauses, Stop / More / mode stay allowed (`lock.ALLOWED`).
- `core/functions.py`: `read_lessons` (AST, no Blender), `problems(lesson_steps=)` refuses a `lesson=` that names no step
  or another function's step and a step whose function is not listed; `lesson=` on the 16 functions the steps teach;
  new `learn.window` (headline), `learn.show_me`, `learn.build`, `joints.slide`, `milling.workpiece`.
- `highlight.py`: marks an `operator_menu_enum` (the animation's + for a step) and does not touch a 3D view while
  Blender's column is being closed after a load (it crashed Blender 5.2.3 at the lesson's start – found here).
- Guide chapter "Learn" (+ `learn_window.png`, `lesson_show_me.jpg`, test crane), PC-check line `app.lessons`,
  CLAUDE.md section 6 "Lesson step" rule + section 3 entry, real-app tests `lesson` (pccheck-b) and `lessoni` (scenes).

**Tested and measured** (Claude Code web machine, 4 cores, no graphics card; real Blender 5.2.3 under xvfb, test crane):
- `tests/test_lessons.py` 10 + `tests/test_lessons_independent.py` 21 (+1 skipped: Play on needs the add-on prefs):
  every step's done false before / true after its do; **View, Show me and Build it yourself give the same project for
  the crane and the mill**; a step done another way counts; a function opens its lesson at its step.
- Real app `ui_test_lesson.py` **40/40**: Build it yourself on the crane with **5 real clicks where the highlight found
  the button** (Product studio, 3/4 hero high, the animation's +, Build & play, Queue this) and Do it for me for the
  rest, the trolley's joint made another way, Show me from the learning list at step 3, Back, saved half-way + reopened
  + Go on. `ui_test_lesson_independent.py` 38/38 (both lessons to the end with Play on: crane 58 s, mill 70 s).
- PC-check `app.lessons`: Build it yourself 10 steps with Do it for me in 1.6–1.7 s, Show me steps 2–4 in 1.5 s.
  `tour.make` locally: 48 projects, 87 stops, all checks OK. `test_tour_clash` crane + mill: 0 clashes.
- **Cost** (real app, software OpenGL): nothing without a lesson. Side panel redraw 0.8–0.9 ms without, 4.0–4.5 ms
  while pointing (the highlight's pixel read ~3 ms of it); 3D view redraw 184–315 ms either way (software GL; the
  lesson's card 1.4 ms, the part look 1.2–1.7 ms); the lesson's timer look 2–3.6 ms while Show me's move plays, a
  Build it yourself check < 0.1 ms. Not measured on the owner's RTX 3090.
- GitHub: run 44811470342 (first push) green except the tour-version record (written later); the final run: see below.

**Subagents:** one independent tester (worktree, did not write the code) – 9 findings, all handled: 1 unsaved work lost
without asking → asks; 2 Show me / Next did a step again that the user had done → never; 3 Client view refused Stop
while Show me edited the locked project → pauses, Stop works; 4 a later setting change rewound the lesson → `place()`;
5 the mill's cut used joint names Z / X → the user's own joints; 6 stuck when undone past the import → re-imports;
7 Ctrl+Z in Show me was redone 1.6 s later → it now waits for Next; 8 Stop forgets the lesson – kept (Stop = end;
a project saved while it runs offers to go on); 9 notes kept after the end → cleared. Its tests are in the suite.

**Runs:** 6 full GitHub runs: the tour-version record (written with the version), Make test tour in the app (no active object in an operator – fixed), a line break lost in the Fresing menu (fixed + test), two skipped tests in one group (fixed), and four version numbers taken by tasks that merged first (0.2.181–0.2.185).

**Open points / follow-up tasks:**
- The other sets' lessons (lead, after 0231 and 0233–0235); a G-code lesson on the gantry set.
- The welcome screen still offers only "Take the test tour" (its answers live in Blender's splash); Learn… is right
  under it in the Fresing menu.
- On the owner's PC: Show me's timing and the card's place at his screen size; the highlight's cost on the RTX 3090.
