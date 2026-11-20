# 0230 – Lessons: Show me and Build it yourself – the engine, the Learn window, the crane and mill lessons

**Who:** worker · **Status:** running (20 Nov) · **Branch:** `claude/clever-cray-qd0bn8`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
