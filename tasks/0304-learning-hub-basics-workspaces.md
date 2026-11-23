# 0304 – Learning hub round 2: a Basics chapter (view, select, move and place, cameras), one chapter per workspace, the owner's example models

**Who:** worker · **Status:** waits – after 0292 (Place) and 0294 (workspaces) · **Branch:** `task/0304-hub-basics`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Tutorial / learnhub improvements and additions, like
moving and placing an object, not purely the functions. How to move the user's perspective. How to place camera views
and animate them. Let the user know how the app works." – "The different learnhub tutorials teach the user to use the
different workspaces." – "I have a few 3D models that can be added, to be used for the learnhub or just for examples.";
owner's click box 23 Nov: the models are his own and may be public) · **Model:** Opus · effort Medium
**Area:** Learning lane – `blender/lessons/` (new lesson modules), `blender/tour.py` (new sets / stops, additively),
`blender/lesson.py` only if a step kind is missing (e.g. a check on the view), the hub's chapters (`ui_tour.py`), new
test-model files for the owner's models (`tests/data/` + `fresing_render/data/` copies); guide, tour versions, CHANGELOG.
**Not:** the hub's panels and progress window (0275, 0281 done), workspaces themselves (0294).

## What to do

1. **Basics** – the first chapter of the hub: how the app works (the two panels, sections 1–8, workspaces, Make, saving
   and backups); move the view (orbit, pan, zoom with mouse and touchpad, numpad views, frame the selection); select
   parts and subassemblies; move and turn a part or a model (0292); place a camera and save a view; animate a camera
   (camera path, ride along, turntable); render a picture. Each a Show me / Build it yourself lesson (CLAUDE.md 6,
   lesson step rule) with `done` checks – view moves checked by the view's change.
2. **A chapter per workspace** (Essentials, Sales, Quick render, Animator, Reviewer, CNC & machining, Offshore, Product
   design, Lifting plans): a short lesson on what that workspace is for, on the fitting learning set.
3. **The owner's example models:** he attaches them in this session. Before adding one, ask him per file that it holds
   nothing of the Fresing 400 and nothing of an employer or client (CLAUDE.md 6), check sizes and real scale; then add
   them as learning sets or examples (Test models lane rules: maker or file, both copies, `THIRD-PARTY-NOTICES.md`
   not needed for his own – say © Fresing).

## Done when

- [ ] Lessons pass View / Show me / Build it yourself (`tests/test_lessons.py`); tour versions recorded; every new
      stop's check
- [ ] Guide (Learning hub) + pictures; function entries `lesson=`; full suite + GitHub run green; report; merged,
      version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
