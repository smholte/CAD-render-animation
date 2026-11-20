# 0228 – The vessel's equipment in a private repository as a "demo kit"; the public app learns to add a kit

**Who:** worker · **Status:** done 20 Nov (0.2.178) · **Branch:** `task/0228-private-vessel-kit` (public) + `main` of the private repository
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

- [x] Public: test kit added, built, removed in tests; real-app test of the list + Add; the public demo and all demo
      tests unchanged and green; guide, function list, PC-check line, COMPANY-USE line; precheck green; merged + released
- [x] Private: on the web machine the kit + the newest public release make the full demo with the same joints, stages,
      shots and frame count as today's public demo (numbers in the report); the private workflow green on push, ≤ ~10 min,
      no schedule, Linux only; a kit zip published by hand as a private release
- [x] The 53 (+ checked) pictures in the private `img/`; nothing deleted from the public repository
- [x] Owner steps in the report (numbered, click by click): download the kit from the private release, Help > Make
      demo project… > Add a demo kit…, Make, what he should see. **His confirmation on his PC is an owner to-do, not a
      blocker for merging**
- [x] Report filled in (runs needed, private minutes used per run)

## Not in this task

Deleting or splitting anything public (package 2: bare ship, plain deck, "Vessel in a wind park", fewer demo CI groups);
the stand-in tests (0229); the report pictures' deletion from `main` (package 4); `tour.py`; the 0211 lifting demo.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4 cores), 20 Nov 2026, branch `task/0228-private-vessel-kit` → **0.2.178**;
private repository `smholte/fresing-render-vessel` (`main`). No subagents (the kit is copies + a hook; the hook's tests
and the real-app test were written from the brief; an independent review was skipped – no Windows-only code, the risky
part, the kit build, is proven by building the full demo both ways and comparing).

**Owner's change during the task:** at 16:55 / 17:02 the lead passed on that the kit holds the **whole** project (its
own ship, park, equipment, stages), while the ship, crane and park stay public. So a kit is a **complete demo of its
own**: a kit build sets the app's demo stages aside and runs only the kit's maker and stages (section "Design").

**What changed (public, additive):**
- `core/demo_kits.py` (new): kit.json check (id slug, versions, module paths, title usable as a file name), zip check
  (one top folder, no `..`, absolute paths, backslashes or links, size limits), unpack (replace on Add again), list,
  remove, deterministic `pack`; `loaded()` puts a kit on `sys.path` with the app as `fresing_app` (a meta-path alias:
  the same module objects, the app's `__spec__` kept) and forgets the kit afterwards; `missing_uses`; the version
  message ("This kit was made for 0.2.180–0.2.199. Download the kit's newer version.").
- `core/demo_kit_run.py` (new): starts a kit's maker as its own program with Blender's Python.
- `blender/demo.py`: `build_project(kit=…)` (`_kit_build`: app stages set aside, stage `kit_model` = the kit's maker,
  the kit's stage module, its `Demo` subclass; app stages back afterwards; nothing left after a failure),
  `build_main(kit=…)`, `kits_dir`, `kit_folder` (`<demo folder>/Kits/<id>/<version>/`), `PUBLIC`, `KIT_TAG`,
  `Demo.anim_name`, `project_path(…, title)`, `exists(…, title)`. No public stage changed.
- `blender/ops_demo.py`: the Make window's list (app demo while `PUBLIC`, then each kit "title (kit n)"), Add a demo
  kit… (`fresing.demo_kit_add`, .zip picker), Remove (`fresing.demo_kit_remove`, asks first), Make / Cancel / Open per
  entry, Help > Open <kit title>. Add / Remove are not in `lock.ALLOWED` (off in the Client view; the function entry
  is not shown there either).
- `pccheck/runner.py`: `demobuild <folder> [small] --kit <id>`. PC-check line `demo.kit` (Full; `MIN_LINES_FULL` 107).
- Test kit `tests/data/demo_kit_test/` (a deck plate and a box sliding on it, stage `box` + the app's `finish`), its
  zip in `fresing_render/data/demo_kit_test.zip` (a test keeps it equal to the packed folder).
- Guide: "Demo kits" in chapter `demo` (anchor `demo-kits`); `docs/COMPANY-USE.md` (+ its copy in `licenses/`): a demo
  kit is Python code that runs in the app – add only kits you made yourself; function `help.demo_kits` (since 0.2.178);
  CHANGELOG; CLAUDE.md section 3 line.

**Private repository:** a self-contained kit `fresing-vessel` (copies of `demo_model/` except `geom.py`, of `demo.py`
without its framework, `demo_park.py`, `demo_rov.py`; its own maker), `make_kit.py`, 18 copied demo test files (152
tests) + `kit_made.py` + `test_kit_builds.py`, the tools, 62 pictures (the 53 of study 0226 + 0106 ×5, 0109_presets,
0179_before_360, 0143's page – looked at – + the guide's `demo_overview.jpg`), one workflow (push + by hand, Linux, one
job, no schedule, no artifacts), its `CLAUDE.md`, `README.md` and `REPORT.md`.

**What the kit imports from the public app (`kit.json` `uses`, package 2 keeps these):** `demo_model.geom`; from
`blender.demo` the framework: `Demo`, `STAGES`, `stage`, `Cancelled`, `cancel_path`, `model_dir`, `project_dir`; the
app modules `blender.animation, build, callouts, cameras, clash, cylinders, decals, faces, flex, joints, logic,
materials, paths, paths_riders, paths_sea, spool, states, tour, tracks, vessel_motion, vessel_work, weather`.

**Tested and measured** (web machine, 4 cores, Blender 5.2.3 as a module unless named):
- The kit makes **the same demo** as the app's own (both built here): the same 41 stages in the same order (+ `kit_model`
  first); scaled-down form 356 = 356 joints, 6 = 6 cylinders, 19 = 19 saved scenes, 109 = 109 steps, 4,481 = 4,481
  frames, 3,269 = 3,269 objects (356 s with the kit, 332 s the app's own); full form 466 = 466 joints, 20 = 20 saved
  scenes, 3,696 = 3,696 objects, same steps and frames (411 s / 389 s). (The tour stop's "432 joints" text is older than
  tasks 0159–0173.)
- On the kit's demo: `test_kit_builds.py` 3/3, `test_demo_project_cable.py` + ROV + park models 20/20 (276 s),
  `_park` + `_realism` 17/17 (284 s), `_quadrant` + `_cps` 7/7 (962 s).
- Public: `tests/test_demo_kits.py` 33 tests (~30 s: refusals, add/replace/list/remove, the alias, the maker program,
  a build with the test kit, a kit lacking a `uses` name or a stage leaves nothing, `demobuild --kit`); real-app test
  `demokits` 23/23 (the Make window, Add, refusals, Client view, no app demo in the list, Make with the test kit through
  the background Blender in 7 s, Open, Remove); PC-check line `demo.kit` OK in 4 s; `test_demo_project.py` +
  `test_pccheck.py` 46/47 before the version raise (the one: `since` ahead of the version, fixed by the raise).
- GitHub (public): **3 full runs**, all green – 26.4 min, 35.0 min, 25.2 min (then `main` reused it: release in 4.5 min) – the 2nd and 3rd only because tasks 0231
  and 0229 took 0.2.176 and 0.2.177 meanwhile (renumbered twice).
- GitHub (private, Linux, one job, no schedule): push run 7.4 min (kit demo made on v0.2.178 in 357 s, 21 tests passed;
  packages not cached yet), the by-hand release run 6.0 min (288 s, 21 passed, release `kit-1`). A third run started by
  a REPORT.md-only push was cancelled after a few seconds (open point: such pushes could skip the run).

**Owner steps** (on your PC, after the update to 0.2.178):
1. On github.com, signed in: **smholte/fresing-render-vessel** → **Releases** → **Demo kit 1 (cable-lay vessel)** →
   click **FresingVesselKit-1.zip** to download it.
2. In Fresing Render: **Help > Make demo project…**. The window lists "Demo cable-lay vessel".
3. Click **Add a demo kit…** → pick the downloaded **FresingVesselKit-1.zip** → **Add a demo kit…** (the blue button
   of the file window). The status line says "Demo kit added: Demo cable-lay vessel (full) (kit 1)".
4. **Help > Make demo project…** again: the list now shows **Demo cable-lay vessel (full) (kit 1)** under the app's own;
   click it → **Make it**. The bottom line shows "Making Demo cable-lay vessel (full): …" for a few minutes.
5. When the small window says it is ready, click **Open demo project** (later: **Help > Open Demo cable-lay vessel
   (full)**). You should see the demo exactly as before: 466 joints in 4 Motion, the saved scenes, and 6 Animation >
   "What it can do today" (Build & play). It is in Documents\Fresing Render\Demo\Kits\fresing-vessel\0.2.178.
6. Tell the lead if anything differs from the demo you had (this is an owner to-do, not a blocker).

**Open points / follow-up tasks:**
- **ROV clash hook:** `demo_rov` adds a clash-check hook (leave the ROV out) when its code is loaded; the kit's code is
  loaded only while the demo is built. Today the app's own `demo_rov.py` still registers it, so nothing changes; after
  the cut (package 2) the clash check in an opened kit demo would check the ROV. Package 2: store "leave out of the clash
  check" in the project (a part tag) instead of code.
- Package 2 (the cut) keeps exactly the `uses` names above public; the kit then needs nothing else. After the cut, set
  `demo.PUBLIC` as decided (the hook already works with no app demo in the list – tested).
- The tour stop text "432 joints" is out of date (466) – package 2 rewrites that stop anyway.
- Private copies of `test_demo_project.py` still hold checks of the app's own demo (Cancel, failure, tour stop, menu):
  sort out after the cut (private CLAUDE.md says so).
- The private workflow runs on every push to its `main`, also one that changes only `REPORT.md`: a `paths-ignore` for
  `*.md` / `img/` would save the owner's minutes (left for the next private task, it needs a run of its own).
