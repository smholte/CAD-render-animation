# 0226 – Study (findings only): the cable-lay vessel's equipment becomes private – what moves, what stays, how

**Who:** worker · **Status:** open – can start (study, no code – no lane) · **Branch:** `task/0226-study-private-vessel`
**Started by:** lead, 19 Nov 2026 (owner, 20:34: "the cable laying ship should be a demo model, but not shipped with
the app, it should be kept private for me"; 20:53, final: "the ship itself can stay, but all the equipments need to
come off. the demo models can stay.")
· **Model:** Opus · effort High
**Area:** this file only. **No pictures of the ship's equipment** in this report (text and tables only).

## Goal

A plan the lead can brief as 2–4 build tasks, so that from one release on:

- **nothing of the invented cable-lay vessel's equipment is public** – not in the repository, the shipped extension,
  release files, the landing page, web 3D pages, the user guide, the test tour, PC-check reports or task reports.
  "Equipment" = everything on or hanging from the ship (carousel, tensioners, chute / overboarding, cranes / A-frame,
  ROV and its launch system, the deck machines) and the demo's layout of them;
- **stays public**: the **ship itself** (hull, superstructure, plain deck), the environment (sea, seabed, wind park,
  turbines, substation, cable route and the cable on the seabed, quay) and **the other demo / test models** (the test
  projects, including their own carousel, tensioner or crane test models);
- **the owner keeps the full demo on his own PC**, made from a **private repository** (proposal for its name and
  layout below), in his installed app, as easily as Help > Make demo project today;
- **the public app keeps working with nothing private present**, and the public automatic tests still prove every
  function they prove today (with the bare ship and the test models).

What is already published stays published (git history, the 0.2.x releases – those copies are GPL and can't be taken
back). Rewriting history is **not** part of the plan unless the owner asks for it (put it as a question, with its
costs: broken clones and forks, and the old releases stay out there anyway).

## What to find out

1. **Every place** that makes, uses, tests, shows or describes the ship's equipment. Start from
   `fresing_render/demo_model/` (`vessel.py`, `deck.py`, `machines.py`, `rov.py`, `layout.py`, `params.py`, `make.py`;
   environment: `park.py`, `turbine*.py`, `substation.py`, `route.py`; shared: `geom.py`, `occ.py`),
   `fresing_render/blender/demo.py` (Help > Make demo project), `fresing_render/lifting_model/` (uses parts of
   `demo_model`?), `tests/` (the demo groups, `demo_made.py`, `test_demo_*`), `tools/` (`make_demo_cable_lay.py`,
   `demo_cable_lay_pictures.py`, `measure_demo.py`, `tools/site_projects/`), `.github/workflows/tests.yml`
   (`demo-make` job, `DEMO_GROUPS` in `tools/ci_groups.py`), the PC check (`pccheck/`), the test tour (`tour.py` sets
   and stops), the user guide (`docs/USER-GUIDE.md`, its pictures), the function list, `site/` and its media, the web
   3D pages, `README.md`, `CHANGELOG.md` (text only – leave old entries), `docs/img/`. For each: **public** (ship,
   environment, test models – stays) / **equipment** (goes private) / **mixed** (must be split – say how).
2. **Which app functions are proven only by the ship's equipment today** (carousel spooling, tensioners, chute /
   overboarding, sea cable from the ship, vessel at work and water effects, clash check at demo size, ROV, …). For
   each: is there already a public test model that proves it (the test projects, `tests/` models)? Where none: propose
   a stand-in **not taken from the ship's equipment** (e.g. a test-project carousel or tensioner placed on the bare ship
   or on a quay rig) – the owner said the test models may stay public.
3. **The private repository**: name proposal (e.g. `smholte/fresing-render-vessel`, private), what goes in it, and how
   the owner's installed app gets the equipment onto the ship. Compare at least: (a) a small private extension that the
   public app finds and offers in Help > Make demo project; (b) the private maker writes STEP files the owner imports;
   (c) anything better. The public app must not name or link the private repository. How a public-app change that
   breaks the private demo is noticed (private tests where and how often – GitHub's Actions minutes for private
   repositories are limited; a test the owner runs on his PC; a lead check before a release).
4. **The demo project in the public app** after the change: the bare ship in the wind park (what it then shows –
   cable laying without equipment?), renamed, or both public and full versions – propose one. Same for 0211's planned
   "Lifting site" demo and its later offshore stage (no ship's equipment in public).
5. **Workers from now on**: the CLAUDE.md lines that keep workers from adding the equipment back (where the private
   repository may be attached and by which tasks only – like the House Planner rule), and how a worker who needs the
   equipment for a cable task tests without it.

**Owner, 20 Nov 2026:** the full cable-lay demo (vessel with all its equipment) becomes a **private demo project he shows to a
company** – his showing piece, not part of the public learning environment. The public test-tour sets are the users' learning
environment (their offshore sets get their own invented, fitting environments) and must not depend on the private demo.

## Done when

- [ ] The table of every place (point 1) with public / equipment / mixed and the split for "mixed"
- [ ] The functions table (point 2) with today's public proof or a proposed stand-in
- [ ] A recommended design for the private repository and how the owner gets the full demo (point 3), with its tests
- [ ] The public demo project's future (point 4) and the CLAUDE.md lines (point 5), as proposed text
- [ ] 2–4 build packages in order, each with model · effort, lane(s) and which running tasks it must wait for
      (two tasks never change the same files)
- [ ] Questions for the owner at the end (short, one line each)
- [ ] No code changed; report merged to `main` (no release)

## Not in this task

Building or moving anything. Rewriting git history. Deleting old releases. The landing page's other content.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings:**

**Packages proposed:**

**Questions for the owner:**
