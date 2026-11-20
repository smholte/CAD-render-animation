# 0228 – The vessel's equipment in a private repository as a "demo kit"; the public app learns to add a kit

**Who:** worker · **Status:** running · **Branch:** `task/0228-private-vessel-kit` (public) + `main` of the private repository
**Started by:** lead, 20 Nov 2026 (study 0226 package 1; owner's answers 20 Nov 16:22–16:35) · **Model:** Opus · effort High
**Private vessel: yes** – this task attaches `smholte/fresing-render-vessel` (private, made empty by the owner on 20 Nov
16:35) with push access; the start sentence names it.
**Area:** public repository, **additive only**: `blender/ops_demo.py` (the kit list, Add a demo kit…), `blender/demo.py`
(the kit's stages run after the public ones – a registration hook, no stage changed), `pccheck/runner.py`
(`demobuild … --kit <id>`), a new `core/demo_kits.py` (`kit.json` check, unpack, list), `tests/data/demo_kit_test/` (a
made-up kit), `tests/test_demo_kits.py`, guide chapter `demo`, `docs/COMPANY-USE.md` (one line), `core/functions.py`
(one entry), the PC-check line. Private repository: everything in it.

## Goal

The owner's full cable-lay demo (the ship **with** its equipment: carousel, tensioners, chute, A-frame / quadrant, ROV,
deck machines, wires, the shots) comes from a private **demo kit**: a zip he adds once in **Help > Make demo project… >
Add a demo kit…**; then **Make** builds the full demo on his PC exactly as today. The public app only knows "demo kits",
never this one. Nothing is deleted from the public repository yet – that is the cut (package 2, later).

## Background

- Study 0226 (report in its task file): the equipment is not in separate files – the maker writes ship + spread as one
  STEP, `vessel.py` holds the deck crane and cuts the carousel well, `demo.py`'s 41 stages mix ship and equipment.
  Section 1 lists every file (public / equipment / mixed), section 3 the kit design (way **(c)**), section 5 the CLAUDE.md
  rule (already on `main`, section 6, "The cable-lay vessel's equipment is private").
- **Owner's answers (20 Nov):** the ship's own **deck crane stays public** with the ship; plain deck later (package 2);
  public demo "Vessel in a wind park" (package 2); the 53 report pictures are deleted from `main` later (package 4) –
  **this task copies them into the private repository first**; no history rewrite.
- **GitHub Free, private Actions minutes shared with the owner's other private projects.** The private repository's
  workflow: **no `schedule:`**; runs on push to its `main` and by hand (`workflow_dispatch`); **Linux only, one job,
  aim ≤ ~10 min**; `concurrency` cancels a superseded run; artifacts `retention-days: 3` at most; the kit zip is built
  only by hand (`workflow_dispatch` input `release: true`) and published as a release **of the private repository**
  (the owner downloads it there when signed in). The public repository's tests stay as they are.
- Running at the same time: 0229 (stand-in tests on public models – different files), the learning-set tasks (tour
  sets; none edits `demo.py`, `ops_demo.py`, the demo tests). Nothing else edits `demo.py` now.

## Owner's addition (20 Nov 16:55, corrected 17:02) – the kit holds the WHOLE project; the ship and park stay public too

The private repository keeps the **entire cable-lay project as a self-contained kit**: its own copies of the ship
(`vessel.py`, `params.py`, `route.py`), the wind park (`park.py`, `turbine*.py`, `substation.py`), the equipment, all
of `blender/demo.py`, `demo_park.py`, `demo_rov.py`, every demo test and tool, and the pictures. The kit builds the
full demo **by itself** from its own maker, importing from the public package only generic libraries (today
`demo_model/geom.py`); list what it imports in `kit.json` `uses`.
**Public stays as decided (owner 17:02: "the windpark and the ship with the crane stays"):** the ship with its deck
crane, the wind park, and later the public demo "Vessel in a wind park" (package 2). Nothing is deleted in this task;
the public demo keeps building as today.

## What to do

**Public repository (additive; every existing demo test stays green, the public demo builds as today):**
1. `core/demo_kits.py`: a kit = a zip with `kit.json` (`id`, `title`, `kit_version`, `app_min`, `app_max`, `stages`
   (names), `uses` (the public functions/modules it imports), `maker` (module path)) + a Python package. Check
   (id is a slug, versions parse, the zip holds only files under one top folder, no absolute paths or `..`), unpack into
   `<user settings>/fresing_demo_kits/<id>/` (replace on Add again), list, remove. A kit made for another app version →
   a plain message ("This kit was made for 0.2.180–0.2.199. Download the kit's newer version.").
2. Help > Make demo project…: a list – the public demo, then each added kit (title, kit version) – **Add a demo kit…**
   (file picker, `.zip`) and **Remove**. Make / Cancel / Open work for the chosen entry; the kit's demo opens as its
   own project file next to the public one. Tooltips. Client view: Add / Remove refused (not in `lock.ALLOWED`).
3. Build: the background Blender run (`demobuild <folder> --kit <id>`) puts the kit's folder on `sys.path`, runs the
   kit's maker after the public maker, imports the kit's stage module so its `@stage` functions register and run
   **after** the public stages (a small hook in `demo.py`: "extra stage modules" – no public stage changes). Progress
   and Cancel as today.
4. A **made-up test kit** in `tests/data/demo_kit_test/` (one box with a slide joint on the ship's deck, one stage, one
   saved camera) – no vessel equipment. Tests: check/refuse (bad id, `..`, wrong versions), unpack/replace/remove, the
   list, Build with the test kit gives the box + joint + camera, the public demo unchanged without a kit.
5. Guide chapter `demo`: a short section "Demo kits" (what a kit is, Add / Remove, versions); `docs/COMPANY-USE.md`:
   "a demo kit is Python code that runs in the app: add only kits you made yourself"; function-list entry
   (`help.demo_kits`, `since=`); PC-check line (adds the test kit, builds, checks the box's joint); a tour stop only if
   the precheck asks.

**Private repository `smholte/fresing-render-vessel`** (its own `CLAUDE.md` with this task's rules, short):
6. `kit/` – a copy of today's equipment code from `demo_model/` and the equipment parts of `blender/demo.py`,
   `demo_rov.py` (study section 1 says which), turned into a kit that **imports the public package** (`demo_model.geom`,
   `route`, `params`, `vessel`, `park`) and **runs on top of today's public demo**: Make with the kit = today's full demo
   (same 432 joints, same stages and shots). Where the public files still hold equipment (until package 2), the kit
   may simply rely on them – say in the report which public names the kit uses (`kit.json` `uses`).
7. `tests/` – the equipment tests of study section 1 (copied, made to run against the public repository at a given
   tag/commit: the workflow clones it), trimmed to fit **one Linux job ≤ ~10 min** (pick the ones that prove the kit
   builds and the spread works; list what you left for "by hand" in the private `CLAUDE.md`).
8. `tools/` (the picture makers, `measure_cables.py`), `img/` (the **53 report pictures** of study section 1 + 0106 /
   0109 / 0179 after a look – copied from the public `tasks/img/`, same names, a list with their task numbers).
9. `.github/workflows/kit.yml` as in Background; `kit.json`; a `make_kit.py` that writes `FresingVesselKit-<n>.zip`.
10. Reports in the private repository's own `REPORT.md`; the public report (below) gives numbers only, no pictures, no
    equipment names beyond those already public.

## Design (worker, 20 Nov 2026)

After the owner's addition (the kit holds the WHOLE project) a kit is a **complete demo of its own**, not stages on top
of the app's demo:
- **A kit build runs only the kit:** `demo.build_project(folder, version, kit=<KitInfo>)` sets the app's own stages
  aside, registers a first stage `kit_model` (runs the kit's `maker` as its own program through `core/demo_kit_run.py`,
  Blender's Python, progress JSON `{"text", "done", "total"}`), imports the kit's `stage_module` (its `@stage`
  functions register on the app's list, in their own order), runs them, saves `<title> <version>.blend` in
  `<demo folder>/Kits/<id>/<version>/`, and puts the app's stages back. A stage module may define `Demo` (a subclass of
  the app's): the stages get it. Build framework names (`stage`, `Demo`, `Cancelled`, paths) stay public.
- **Inside a kit the app is `fresing_app`** (a meta-path alias to the installed package, same module objects; also in
  the maker program). `kit.json`: `id`, `title`, `kit_version`, `app_min`, `app_max` ("" = open), `stage_module`,
  `maker`, `stages` (checked registered), `uses` (app names, checked present before the build).
- **No app demo in the list** works (`demo.PUBLIC = False`, for after the cut; tested): the list holds only kits, or
  says "No demo yet: add a demo kit".
- **Private kit:** copies of `demo_model/` (all but `geom.py`, which hands over the app's own), `demo.py` (framework
  removed, stages kept), `demo_park.py`, `demo_rov.py`; its maker writes the same files as the app's (`--small` = the
  scaled-down set). Its tests: copies of every demo test, `kit_made.py` (made once from the kit zip, added as the app
  adds it), `test_kit_builds.py` (same stages, joints, cylinders, saved scenes, steps, frames, objects as the app's own
  demo of 0.2.175).

## Done when

- [ ] Public: test kit added, built, removed in tests; real-app test of the list + Add; the public demo and all demo
      tests unchanged and green; guide, function list, PC-check line, COMPANY-USE line; precheck green; merged + released
- [ ] Private: on the web machine the kit + the newest public release make the full demo with the same joints, stages,
      shots and frame count as today's public demo (numbers in the report); the private workflow green on push, ≤ ~10 min,
      no schedule, Linux only; a kit zip published by hand as a private release
- [ ] The 53 (+ checked) pictures in the private `img/`; nothing deleted from the public repository
- [ ] Owner steps in the report (numbered, click by click): download the kit from the private release, Help > Make
      demo project… > Add a demo kit…, Make, what he should see. **His confirmation on his PC is an owner to-do, not a
      blocker for merging**
- [ ] Report filled in (runs needed, private minutes used per run)

## Not in this task

Deleting or splitting anything public (package 2: bare ship, plain deck, "Vessel in a wind park", fewer demo CI groups);
the stand-in tests (0229); the report pictures' deletion from `main` (package 4); `tour.py`; the 0211 lifting demo.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
