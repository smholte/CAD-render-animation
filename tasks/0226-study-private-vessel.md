# 0226 – Study (findings only): the cable-lay vessel's equipment becomes private – what moves, what stays, how

**Who:** worker · **Status:** done 20 Nov (study, no code – no lane) · **Branch:** `task/0226-study-private-vessel`
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

- [x] The table of every place (point 1) with public / equipment / mixed and the split for "mixed"
- [x] The functions table (point 2) with today's public proof or a proposed stand-in
- [x] A recommended design for the private repository and how the owner gets the full demo (point 3), with its tests
- [x] The public demo project's future (point 4) and the CLAUDE.md lines (point 5), as proposed text
- [x] 2–4 build packages in order, each with model · effort, lane(s) and which running tasks it must wait for
      (two tasks never change the same files)
- [x] Questions for the owner at the end (short, one line each)
- [x] No code changed; report merged to `main` (no release)

## Not in this task

Building or moving anything. Rewriting git history. Deleting old releases. The landing page's other content.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 20 Nov 2026 (branch `task/0226-study-private-vessel`). Read-only: three
read-only mapping subagents (the maker package; `blender/demo*.py` and the app; tests / CI / tools / site / docs /
tasks), their findings spot-checked by the worker (file lists, the picture count, the CI artifacts, the tour stop and
the Heavy line). No code changed, nothing run in Blender, no pictures looked at.

### Short answer

- **The equipment is not in separate files today.** The maker writes the ship and its spread as ONE STEP
  (`demo_cable_lay.step`); `vessel.py` holds a crane and cuts a carousel well; the cable on the seabed is the CAD cable
  that runs through the tensioners and over the horn; `demo.py`'s 41 stages mix all three. So "take it off" means a
  **split**, not a delete.
- **What is public today:** the equipment's code ships in **every release zip** (`fresing_render/demo_model/`,
  `blender/demo.py`), its picture `docs/img/demo_overview.jpg` is in the guide on the landing page and in every
  release, and **~53 report pictures (13 MB)** in `tasks/img/` show it. The landing page itself, its media and the
  web 3D pages hold **nothing** of the vessel.
- **Every app function already has a public tour stop and PC-check line on a test model.** The demo is the only proof
  of: the functions **at full size and together** (clash check at 1,250 parts, the 28.8 km coil, tracks on a tilting
  frame, a load lowered on a wire between open tensioners, a model update and a re-bake of the whole spread) – these
  need stand-ins (package 3).
- **Recommended design:** a private repository with a **"demo kit"** – a zip the owner adds once in Help > Make demo
  project…; the public app gets a generic kit list (it never names the kit), its own public demo is the **bare ship
  in the wind park**. Private tests run once a day against the newest public release.
- **4 packages:** 1 private repo + kit hook (public side additive) · 3 stand-in tests on public models (same time as 1)
  · 2 the cut (after 1 and 3) · 4 pictures and texts (with or after 2).

### 1. Every place (public / equipment / mixed)

Paths under `fresing_render/` unless given. "Split" says what stays public.

**The model maker `demo_model/`**

| File | Class | Split / note |
| --- | --- | --- |
| `geom.py` | public (shared) | The shape / scene-tree / STEP-writer library of **every test model** (`tools/make_test_*.py` ×10, `machine_parts.py`, `model_details.py`) and of `lifting_model/` (5 files) and `tools/inventor/prototype`. Stays public; the private kit imports it. |
| `occ.py` | public (shared) | turbine / substation only; `tools/site_projects/occ.py` re-exports it |
| `turbine.py`, `turbine_parts.py`, `substation.py`, `park.py` | public (environment) | need only `geom`, `route.Line/Arc/Route`, the cable's Ø / bend radius. `tools/site_projects/iea15_standin.py` imports `turbine` |
| `vessel.py` | mixed (mostly ship) | Hull, paint bands, skeg, thrusters, superstructure, lifeboats, bollards, anchors stay. Equipment hooks to remove: the **carousel well** cut through hull and deck + its lining (`:605-640`), the **bulwark opened aft to `board_x`** (the quay-cable boarding point, `:671`), `L` taken from `route.positions` (which can grow it from the carousel, `route.py:460`), `from .machines import Kit` (`:598`, only `Kit.get`), the `outfit` boxes kept clear of the spread (`:596`). **The deck crane + hoist** (`:448-551`) – ship or equipment: owner question 1. The bare ship needs its own small input (length, beam fixed) instead of `route.positions`. |
| `params.py` | mixed | Public: `length`, `beam`, `deck_z`, `keel_z`, the cable (`cable_d`, `mbr`, `cable_r`, `bend_r` …), `ParkParams`. Private: carousel, cable line, hinge, tensioner, roller, Lebus, rope Ø and the derived properties. `__post_init__` widens `beam` from the spread (`:78-94`): a public `ShipParams` with a fixed beam (27,000 at the default Ø200), the private `Params` extends it. |
| `route.py` | mixed | Public (shared geometry): `unit`, `rotate`, `Line`, `Arc`, `Route`, `turn`, `pitch`, `s_bend*`, `tangent_*`, `rope_route` (`:16-215`, `:330-350`, `:573-768`). Private: the constants `:216-281`, `cps_*`, `d_*`, `ar_*`, `top_pulley`, `arch_geometry`, `main_route`, `cps_*_route`, `core_end_route`, `quay_route`, `positions()` (`:378-468`, chains hinge → tensioners → CPS → quadrant → winches → carousel). |
| `machines.py` | equipment (Kit + 2 helpers shared) | `Kit.get` (the shape cache), `cable_drive`, `turn_axis` → a public `kit.py` (or `geom.py`); carousel, tensioner tracks, winches, Lebus drum, chute, rollers → private |
| `deck.py` | equipment (quay public) | `quay()` + its colours stay; cradles, trestle, walkway, loading tower, cable engine, D / quadrant, rails, swivel sheave, CPS, trough → private |
| `rov.py` | equipment | whole file |
| `layout.py` | mixed (mostly equipment) | Writes 11 STEP files + `demo_cable_route.json` + `demo_joints.json`. Public: `demo_vessel.step`, `demo_park.step`, the quay slab, the sheet's `park` / cable Ø / quay-edge parts, `_park_sheet` and the small helpers. Everything else private (`build`, `quadrant_system`, `quay_loading`, `route_sheet`, `joint_sheet`, the spread's files). `demo_quay_loading.step` is mixed: quay public; storage carousel, quay tower, cradles, boarding controller private. Split: a public `layout_public.py` (ship + park + quay + its own small sheet: the ship's joints – thrusters, radars), the private layout imports it. |
| `make.py` | mixed | flags `out`, `--cable-d`, `--only`, `--progress`; calls only `layout.write`. Public maker writes the public files; the kit has its own maker that imports the public package. |
| `__init__.py` | text | its module list names machines / deck / layout: reword |

**The app (`blender/`, `pccheck/`, `core/`)**

| File | Class | Split / note |
| --- | --- | --- |
| `blender/demo.py` (2,327 lines, 41 stages) | mixed | Public stages: model (ship + park only), looks (ship rows), marks, joints (ship: thrusters, propellers, radars), surroundings (Sun, sea, vessel motion; the quay scene without the storage carousel), sea (depth, cut-away – **without** the hang-off from horn A), cameras (Overview, Stern, Into the sea, At the seabed, Stern thrusters, Hull side, Open sea, Loading at the quay), brand, shot 1 (aim at the hull, not `TURNTABLE` `:1427`), propulsion (**breaks** today without the carousel: `:2180` starts at shot "Carousel"), finish. Private: hold, cps_path, cable, spool, tracks, cylinders, wires, winch_wires, shots 2–6, 8, 8b, 9–12, quadrant_ops, the constants `TRAVEL`, `WINCH_TRAVEL`, `TENSIONERS`, `CABLE_ITEM`, `set_down_shares`, `lowered_parts`. Saved cameras Carousel, Roller highway, Tensioner, Handling winch, Quadrant, CPS rack, CPS on the D, Deck from above → private. It imports `demo_model.layout/route/params` directly (`:203-209`, `:1666-1708`). |
| `blender/demo_park.py` | public (environment) | depends on the lay cable (`CABLE_ITEM`, `sea_dir`, `_cable_value_at`) to place the park and its first end: give it the route's seabed start instead. Shot 2b, 8a, 13, rotors, lights, shift to turbine B stay. |
| `blender/demo_rov.py` | equipment | whole file (ROV, tether hose, thruster joints, clash hook) |
| `blender/ops_demo.py` | public | Make / Cancel / Open stay; the kit list goes here (package 1) |
| `blender/tour.py` stop "demo" (`:4258`), `_check_demo` (`:4055`) | mixed (text) | promises 432 joints, the vessel "on the open sea"; `MIN_JOINTS` → the bare ship's numbers |
| `pccheck/heavy.py` `heavy.demo` (`:820-876`) | mixed | checks `demo.TENSIONERS` lift + 70° tilt, `MIN_JOINTS`, renders `demo_overview` – runs in CI (scaled down) and on the owner's PC; becomes the public demo's line (make time, Build, frame time) |
| `core/functions.py` `help.demo` (`:517`) | public (title) | title "Demo project: cable-lay vessel" → the new name |
| `ui_header.py`, `workspaces.py` (`"fr_demo"`), `lock.py`, `ui_topbar.py`, `pccheck/runner.py` `demobuild`, `pccheck/ops.py` | public | keep (tags, menus, the background entry) |
| `paths.py`, `spool.py`, `tracks.py`, `clash.py`, `core/catenary.py`, `core/part_types_data.py` … | public | **No special case for the demo's equipment in any app function** (checked by name: carousel, tensioner, chute, A-frame, ROV, quadrant, LARS). Comments and measured numbers that cite the demo: text only, keep. |
| `lifting_model/` | public | imports only `demo_model.geom` |

**Tests, CI, tools**

| Where | Class | Split / note |
| --- | --- | --- |
| `tests/demo_made.py` | mixed | makes the small demo once per run; helpers `_t9`, `_cps_shot`, `_solved` are equipment. Public version makes the bare-ship demo. |
| `test_demo_cable_lay.py` (40 tests), `test_demo_rov_model.py`, `test_demo_project_cable.py`, `_cps.py`, `_lowering.py`, `_quadrant.py`, `test_demo_clash.py` + `_b.py` + `demo_clash_child.py` (except `test_windows_find_what_the_whole_check_finds`, which uses `test_clash.step`), `demo_cps_check.py` | equipment | → private repo |
| `test_demo_project.py` | mixed | private: every sheet joint, couplings, handler cylinders; public: scripts off, scenes / cameras / animation, save–reopen–Build, Cancel, failure, stages, maker ships, tooltips, `test_the_vessel_in_detail` |
| `test_demo_project_park.py` | mostly public | `test_the_park_keeps_clear_of_the_vessel_and_the_d` uses `demo.lowered_parts` → private (or clear of the hull only) |
| `test_demo_project_realism.py` | mixed | public: 38 kg/m catenary tension, Lay data label → re-home on `test_sea` (package 3); private: tensioner caption, ROV, tipping drums |
| `test_demo_project_rebake.py`, `test_demo_project_update.py` | mixed, equipment-heavy | the functions are generic, the cases are the spread's → stand-ins (package 3), the demo's case private |
| `test_demo_vessel.py` | public (ship) | builds with `Kit` + `route.positions` today: switch to the bare ship's input; its deck-crane checks follow question 1 |
| `test_demo_park_model.py` | public | imports `Params` (the cable) – fine after the split |
| `test_paths.py:1680-1850`, `test_paths_core.py:1375-1550` | equipment | the demo's power cable over the roller highway / its CAD centreline → private (the same functions are proven on `test_paths_a`, `test_spool`) |
| `test_tracks_core.py:15-125` | equipment-derived | `demo_pins`: the demo tensioner's track numbers inlined → replace by `test_tracks`' own pins (they exist: `make_test_tracks.track_pins`) |
| `test_flex_followups_independent.py:486-520` | equipment | imports `demo.set_down_shares` → private |
| `test_web_player.py:359,519`, `test_user_guide.py:166`, `test_ci_tools.py:266-280,683-696` | mixed (names / text) | shot names "carousel", "tensioners", "chute" as strings, the guide anchor, the demo group names: reword |
| `.github/workflows/tests.yml:170-270,564-588`, `tools/ci_groups.py` (`DEMO_GROUPS = 4`, `matrix_demo`), `tools/ci_times.json` (17 entries) | mixed | stay, smaller: the public demo is lighter (expect 1–2 demo groups) |
| CI artifacts | equipment while the demo has it | `demo-made` (the whole demo project, kept 1 day), the PC check Heavy report with the `demo_overview` picture (7–14 days). Stop with package 2; old ones expire by themselves. |
| `tools/make_demo_cable_lay.py`, `demo_cable_lay_pictures.py`, `measure_cables.py` (`:140-184`) | equipment | → private |
| `tools/measure_demo.py` | mixed | generic profiler; keep, its defaults name equipment shots |
| `tools/ui_test_layout.py`, `web3d_measure.py:9`, `make_site_web_models.py:16`, `make_test_tracks.py:19` | public | tag / docstring only |

**Site, docs, tasks**

| Where | Class | Note |
| --- | --- | --- |
| `site/` (media, `media.json`, web 3D models, render kit) | public | **no vessel media**; `CREDITS.md:35-40` credits the park only |
| `docs/USER-GUIDE.md` chapter `demo` (`:4358-4476`) | mixed | public: Make / Cancel / Open, the vessel, wind park, cable 38 kg/m; equipment: joints list, wires, ROV, second end, CPS, the shots. Mentions elsewhere: `:1495`, `:1555`, `:1888`, `:3193`, `:3208`, `:3824` (text, reword) |
| `docs/img/demo_overview.jpg` | equipment | **the only guide picture of the spread**; also on the landing page's guide and in every release zip → replace with the bare ship |
| `CHANGELOG.md` (94 lines), `CLAUDE.md` (32 lines), `TASKS.md` (67 lines) | text | CHANGELOG: leave (as briefed); CLAUDE.md: section 3's `demo.py` / `demo_model` lines + section 6 rule (point 5) |
| `tasks/*.md` | text | 83 of 224 task files describe the vessel; ~30 are about it. Text: owner question 5 |
| `tasks/img/` | equipment | **53 files, 13 MB** certainly showing the spread: 0076 (4), 0077 (2), 0078 (2), 0079 (1), 0084 (7), 0091 (2), 0095 (3), 0102 (2), 0107 (2), 0142 (3), 0143 (3), 0149 (1), 0153 (4), 0154 (3), 0158 (3), 0159 (2), 0166 (3, the park with the vessel in view), 0173 (3), 0174 (1), 0175 (1). Probably: 0106 (5, "demo vessel, same camera"), 0109 (3), 0179 (1): look before deleting. |
| Releases (100+ on GitHub) | equipment (published) | every zip holds `demo_model/` + the guide picture. Stay as they are (GPL, can't be taken back); not part of the plan |

### 2. Functions proven only by the equipment today

Every function below already has a public tour stop and PC-check line on a test model (`core/functions.py`). What the
demo adds is size and the functions together.

| Function | Public proof today | Only on the demo | Stand-in (package 3), none taken from the spread |
| --- | --- | --- | --- |
| Carousel spooling | tour `spool`, `motion.spool`, Heavy (test carousel, Ø10 mm, 38 layers), `test_spool_full*` | 28.8 km coil; partly paid-out top layer must be an **even** layer (CLAUDE.md §8); arch guide | `test_spool` carousel: a case with an odd number of full layers + a partly paid-out top layer leaving at its innermost turn |
| Lebus drum with climbs | `test_spool_core/full/independent`, `test_cable_speed` | `joints.table_keys` (keys closer than 0.02 → leader × 1000) – **no public test** | `test_spool`'s drum as Lebus with climbs 7–8 mm of payout apart: the drum's turn within 0.1° after Build |
| Tensioner tracks | tour `tracks`, `motion.tracks` (`test_tracks`) | tracks on a frame that **lifts and tilts** (cylinders), a load passing between open tracks | `test_tracks`: its tensioner frame on a hinge + a cylinder (test-models change, new `changed=`) |
| Cable over rollers that follow a cable joint | tour `cables` (`test_paths_a`), `test_paths*` | the long roller highway, a CAD cable read in overlapping pieces (`core/paths.centreline`) | `test_paths_core` already cuts long tubes; add a public long-cable case (a made-up 300 m tube in the test, no model) |
| Chute / horn, cable into the sea, catenary, touch-down | tour `sea_cable` (`test_sea`), `motion.sea_cable`, `test_paths_sea*`, `test_catenary` | 38 kg/m tension numbers, Lay data label | move the two realism checks onto `test_sea` |
| A load lowered on a wire, second end over the stern, CPS rider | `test_moving` (block lowered as on a wire), `test_paths_settle`, 6 rider files | the D-quadrant lowered between open tensioners (clash-checked), the set-down shares | `test_moving`'s block lowered past a part it must clear, with the clash check (0 rows) |
| Vessel motion, vessel at work, thrusters, wake | tours `vessel`, `vessel_work` (`test_thrusters`, `test_sea`) | at ship size | **stays public**: the bare ship keeps them |
| Clash check at size (rollers held still, spoked sheaves once per turn, rim fence, windows in 4 processes) | `test_clash*`, `test_clash_turning`, Heavy (3,000 small parts), tour `clash` | 1,250 parts, the only "big + many turning parts" case; the 4-window split | the public demo keeps propellers, radars, 9 turbines' rotors (turning parts) + park; plus a made-up rim of 200 rollers on the bare ship's deck in a test (not a model). The 4-window machinery keeps its own test on `test_clash.step`. Expect the demo clash job to drop from ~9 min. |
| Model update keeps cables, wraps set by hand | `test_paths_update_same` (`test_paths_a`), `test_model_update_cables` | tipping wires' ends, the A&R top pulley (`wrap_user`) | `test_swivel` or `test_paths_a`: a wrap set by hand on a sheave on a moving part, update with the same file |
| Re-bake after a sea change (job, Cancel) | `test_sea_after_build`, `test_rebake_objects_gone`, `test_camera_ride_rebake` | the whole spread, CALM → ROUGH | the public demo (bare ship, park, a seabed cable) keeps a re-bake test |
| ROV + tether | tour `hoses` (a hose to a moving part) | the ROV | none needed (the hose function is proven); the ROV goes private |
| Joints in a batch, 400+ joints | `test_joint_batch` | 432 joints | `test_joint_batch` with a made-up 400-joint scene (add a size case if it has none) |

### 3. The private repository and how the owner gets the full demo

**Name:** `smholte/fresing-render-vessel` (private), made empty by the owner on github.com (a worker session cannot
create repositories). **In it:** `kit/` (the private maker modules: carousel, tensioners, chute, cranes, ROV, deck
machines, the layout and route sheets – imports the public `demo_model.geom`, `route`, `vessel`, `park`), `stages/`
(the private stages of today's `demo.py`, `demo_rov.py`), `tests/` (the equipment tests of section 1, unchanged
where possible), `tools/` (pictures, `measure_cables.py`), `kit.json`, `img/` (the 53 report pictures, for the owner's
record), its own `CLAUDE.md`, and a workflow that tests and builds `FresingVesselKit-<n>.zip`.

| Way | How the owner gets it | Verdict |
| --- | --- | --- |
| **(c) Demo kit (recommended)** | Help > Make demo project… shows a list: the public demo, and **Add a demo kit…** (pick the zip). The app checks `kit.json` (id, title, the app versions it was made for), unpacks it into `<settings>/fresing_demo_kits/<id>/`, and lists it. Make runs as today in the background Blender (`demobuild <folder> --kit <id>`): the kit's maker runs with Blender's Python next to the public maker, the kit's stages register with the same `@stage` and run after the public ones. A kit made for another app version gets a plain message ("made for 0.2.180–0.2.199: download the kit's newer version"). Updating = Add again. | One click a release for the owner, no code in the public app that knows the vessel, the whole demo built on his PC (his speed measured as today). The public hook is tested with a tiny made-up kit in `tests/data/` (one box with a joint on the bare ship). `docs/COMPANY-USE.md` gets a line: a kit is Python code, add only your own. |
| (a) A private Blender extension | Install from Disk in Blender's preferences | Blender gives extensions no way to import each other (the module path `bl_ext.<repo>.fresing_render` differs per install); the background build would have to switch it on too; the owner would use Blender's preferences, which the app hides. More fragile than (c), no gain. |
| (b) The private maker writes STEP files | owner imports them | Loses the 300+ joints, cables, spools, tracks, wires, shots and the video: hours of set-up per release. No. |
| (d) Private CI makes the finished `.blend`, owner downloads it | open the file | Simplest click-wise, but a saved demo holds absolute paths to its model and cache files (§8) made on Linux, and it would not be rebuilt by his app version. Keep as the fallback if (c) is refused. |

**Noticing a public change that breaks the private demo:**

- **Private CI, once a day:** a scheduled workflow looks up the newest public release (public API, no token), and only
  when it is new since the last run: clones the public repository at that tag, makes the full demo with the kit
  (small form) and runs the private tests in 2 jobs. Plus on every push to the private repository. Today the demo
  part of a public run is ~35–45 runner-minutes; trimmed to 2 jobs ~25 min → ~750 min a month daily. **Not checked
  (docs.github.com is blocked here):** from memory, GitHub Free gives 2,000 Actions minutes a month for private
  repositories (Pro 3,000), Linux counting 1×: daily fits, per release (several a day) does not. The owner can see
  his plan and minutes at github.com → Settings → Billing. GitHub e-mails a failed scheduled run.
- **The lead:** at each status check reads the private run's result (a lead session with the private repository
  attached read-only), and writes a fix task for the **private** repository when it is red.
- **Public side:** the hook's own public test (the made-up kit) keeps the interface from rotting; the kit names the
  public functions it uses in `kit.json` → a test in the private repo lists them.

### 4. The public demo project after the change

**Proposal:** one public demo, renamed **"Vessel in a wind park"** (Help > Make demo project… / Open), the private
full demo next to it in the same list only on the owner's PC once his kit is added. It shows: the bare ship (hull,
paint, draft marks and name decals, superstructure, thrusters, propellers and radars turning), sailing in and holding
on DP (vessel at work: wake, bow wave, thruster jets), vessel motion, weather and night, the wind park (9 turbines,
rotors, lights, substation), the **cable already laid on the seabed** along the public route (from `park.first_end`
and the route's seabed run – no hang-off from the ship), sea cut-away with seabed and the monopile to its toe,
saved cameras (Overview, Stern thrusters, Hull side, Beside turbine A, Park overview, Park at night, At the seabed)
and a shorter video (~1 min). It does not show cable laying: that is the learning set "Cable into the sea"
(`test_sea`), which 0224's re-brief gives a fitting environment.

**0211 "Lifting site":** onshore, no conflict. Its **offshore stage** puts the load on the **bare ship** (or a
jack-up) and lifts with the Lifting lane's own built-in cranes (`lifting_model` classes, e.g. a KB knuckle-boom) and
0180's foundation tools – never the vessel's crane or A-frame. Brief 0211 after package 2 (both change `demo.py` /
`ops_demo.py`); it becomes a second public entry in the same list.

### 5. Proposed CLAUDE.md lines (replace the section 6 rule "The cable-lay vessel's equipment becomes private")

> - **The cable-lay vessel's equipment is private** (owner, 19–20 Nov 2026; task 0226). The public repository holds the
>   **bare ship** (`demo_model/vessel.py`), the environment (sea, seabed, wind park, turbines, substation, quay, the
>   cable on the seabed) and the test models. Everything on or hanging from the ship (carousel, tensioners, chute,
>   cranes / A-frame, ROV, deck machines) and its layout lives in **the private vessel repository** as a demo kit;
>   the public app knows only "demo kits", never this one. Never add equipment to the bare ship, the public demo,
>   a test model, a tour set, a picture, a web page or a report, and never copy anything from the private repository
>   into this one – also not as a "test model". The owner shows the full demo to companies: it is his, not the
>   learning environment's.
> - **Who may attach the private vessel repository:** the lead (read-only, to read its daily test run) and only the
>   tasks whose file header says **"Private vessel: yes"**; the lead's start sentence then names the repository.
>   Such a task works in the private repository's own branch and rules (its `CLAUDE.md`), reports in numbers only,
>   and its public part (a change to the kit hook) goes through this repository as usual.
> - **A cable / spool / track / sea task without that line** tests on the public test models (`test_spool`,
>   `test_tracks`, `test_paths_a`, `test_sea`, `test_moving`, `test_swivel`, `test_thrusters`) and the public demo.
>   If the change may break the full demo (a renamed function the kit uses, a changed `@stage`, the kit hook), say so
>   in the report: the lead checks the next daily private run.

Section 3's lines for `demo.py` and `demo_model/` change with package 2 (the public files only, plus one line for the
kit hook in `ops_demo.py`).

### Packages proposed (in order)

| # | Package | Model · effort | Lane | Waits for |
| --- | --- | --- | --- | --- |
| **1** | **Private repository + demo kit hook.** Owner makes the empty private repo (steps in the brief). Worker: in the public repo, **additive only**: the kit list in Help > Make demo project…, Add a demo kit…, `kit.json` check, `demobuild --kit`, kit stages after the public ones, the made-up test kit, guide section, COMPANY-USE line, tour stop / PC-check text (the hook is something the owner sees). In the private repo: a copy of the equipment code, stages, tests, tools and the 53 pictures as a kit that runs on top of **today's** public demo (nothing deleted yet), its CI (daily + push), its `CLAUDE.md`. Done when the owner made the full demo from the kit on his PC. **Task file: "Private vessel: yes".** | Opus · High | Demo models lane (`demo.py`, `ops_demo.py` additive) + new private repo | nothing running in `demo.py`; 0227 / 0221 don't touch it (the kit operator stays out of `lock.ALLOWED`) |
| **3** | **Stand-ins on public models** (section 2's last column): spool odd/even top layer, Lebus climb keys, `test_tracks` tensioner on a hinge + cylinder, lowering past a part with the clash check, realism checks on `test_sea`, a wrap set by hand kept through an update, joints at 400, a made-up roller rim for the clash check, `test_tracks_core`'s `demo_pins` → the test model's own pins. | Opus · Medium | Test models lane + the cable/spool/track tests | runs **at the same time as 1** (different files); coordinate with 0224's re-briefed tour packages if they change `test_tracks` / `test_spool` sets |
| **2** | **The cut.** Split `demo_model/` (public `ShipParams`, bare `vessel.py` without well / opening / crane per Q1–2, `kit.py` from `Kit.get`, `layout_public.py`, route geometry kept), `demo.py` down to the public stages + the seabed cable, `demo_park.py` placed from the route, delete `demo_rov.py` and the equipment tests/tools (they are in the private repo), rename the demo, tour stop + `_check_demo`, `heavy.demo`, `functions.py` title, `demo_made.py` + fewer demo groups, guide chapter + a new `demo_overview.jpg` (bare ship), CLAUDE.md §3 + §6 lines, CHANGELOG. Before merging: the private kit is switched to run on the cut public package (the owner makes the full demo once more). **"Private vessel: yes"** (to move the kit onto the new public interface in the same task). | Opus · High | Demo models lane; touches `tour.py` (one stop), `pccheck/heavy.py` (one line), CI files (Quality lane) | 1 and 3 merged; no tour package of 0224's re-brief running at the same time (both edit `tour.py`) |
| **4** | **Pictures and texts.** Delete the 53 (+ after a look 0106 / 0109 / 0179) report pictures from `main` (already copied to the private repo by 1), their links in task files become "(picture removed – private, task 0226)", guide mentions reworded (`:1495`, `:1555`, `:1888`, `:3193`, `:3208`, `:3824`). Docs-only push. | Sonnet · Low | Docs lane, `tasks/` | after 1 (copies exist); with or after 2 (the guide) |

From the release of package 2 on: no equipment in the repository's `main`, the extension, the release files, the
landing page's guide, the tour, the PC check or CI artifacts. Git history and the releases up to then keep it.

### Questions for the owner

1. The ship's own **deck crane** (provision crane with hoist, part of the ship model today): equipment (goes private) or ship (stays)? *Recommended: private.*
2. The **carousel well** cut through the deck and the bulwark opening aft: close them for a plain deck? *Recommended: yes.*
3. Public demo **"Vessel in a wind park"** – the ship sailing in, holding position, park, weather, cable lying on the seabed, **no cable laying** – OK?
4. Delete the **~53 report pictures** of the equipment from the repository (a copy kept in your private repository; old copies stay in the history)? *Recommended: yes.*
5. Old task reports and CHANGELOG entries that **describe** the equipment in words: leave as they are? *Recommended: leave.*
6. **Rewrite the git history** to remove it from the past too? *Recommended: no* – every clone and running session breaks, and the 100+ old releases keep the code anyway (today 0 forks, 0 stars).
7. Private repository name **`smholte/fresing-render-vessel`** – OK? You make it empty and private on github.com (steps in package 1).
8. Your GitHub plan – **Free or Pro**? (decides how often the private tests can run; github.com → Settings → Billing)

**Owner's answers (20 Nov 2026, 16:22–16:29, to the lead):**
1. **The ship's own deck crane stays public with the ship** (provision crane with hoist). All the rest of the equipment goes private.
2. **Yes, a plain deck** – the carousel well and the aft bulwark opening are closed in the public ship.
3. **Yes** – the public demo is "Vessel in a wind park" (sails in, holds position, park, weather, cable on the seabed, no cable laying).
4. **Yes** – delete the ~53 report pictures from `main` (copies in the private repository first).
5. **Leave** old reports and CHANGELOG entries that describe the equipment in words.
6. **No** history rewrite.
7. Private repository: **`smholte/fresing-render-vessel`** (the owner makes it empty and private).
8. GitHub plan **Free** – and private Actions minutes are **shared with the owner's other private projects**. So the
   private repository's tests are kept small: **no daily or scheduled run**; they run only on a push to the private
   repository and by hand (`workflow_dispatch`), Linux only (no Windows job – Windows minutes count double), one job,
   aim ≤ ~10 min per run, `concurrency` cancels a superseded run, no artifacts kept beyond a few days. The public
   repository's tests stay as they are (public repositories' minutes are free).

**Owner's addition (20 Nov 2026, 16:55 + correction 17:02, to the lead):** the **private** repository keeps the
**entire cable-lay project** as a self-contained kit – its own copies of the ship, equipment, environment and
animations (16:55). **Public stays as answered:** "the windpark and the ship with the crane stays" (17:02) – answers 1–3
hold (ship with its deck crane, plain deck, the wind park, public demo "Vessel in a wind park"). Briefs 0228 and 0229
and CLAUDE.md section 6 say so.
