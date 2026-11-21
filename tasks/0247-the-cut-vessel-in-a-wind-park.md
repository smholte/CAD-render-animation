# 0247 – The cut: the vessel's equipment leaves the public repository; the public demo becomes "Vessel in a wind park"

**Who:** worker · **Status:** done (0.2.188) · **Branch:** `task/0247-the-cut` (public) + a branch in the private repository
**Started by:** lead, 21 Nov 2026 00:10 (study 0226 package 2; owner's answers 20 Nov 16:22–17:02; owner asked 20 Nov
23:01 whether the equipment is gone from the release – it is not: 0.2.184 still ships `demo_model/` and the full demo)
· **Model:** Opus · effort High
**Private vessel: yes** – this task attaches `smholte/fresing-render-vessel` (private) with push access; the start
sentence names it. Follow its own `CLAUDE.md` there; mind the owner's private GitHub minutes (CLAUDE.md section 6).
**Area:** Demo models lane –
- `fresing_render/demo_model/` (the split; **`geom.py` unchanged** – every test model, `lifting_model/` and the kit
  import it), `blender/demo.py`, `blender/demo_park.py`, `blender/demo_rov.py` (deleted), `blender/ops_demo.py` (title
  only), `core/functions.py` (`help.demo` title only);
- `blender/clash.py` – **additive only**: a part tag "left out of the clash check" stored in the project (C below);
- `blender/tour.py` – **only** stop `demo` and `_check_demo` (0230 and 0232 run in other sets of `tour.py`);
- `pccheck/heavy.py` – only `heavy.demo`;
- tests: the equipment test files deleted, the mixed ones trimmed, `tests/demo_made.py`; CI: the demo part of
  `.github/workflows/tests.yml`, `tools/ci_groups.py` (`DEMO_GROUPS`), `tools/ci_times.json`; the equipment tools in
  `tools/` deleted;
- `docs/USER-GUIDE.md` chapter `demo` + the other mentions (study 0226 section 1, "Site, docs, tasks"),
  `docs/img/demo_overview.jpg` (new picture), CLAUDE.md section 3 (`demo.py`, `demo_model/` lines) and section 6 (the
  vessel rule's "until the cut is merged" sentence), `CHANGELOG.md`;
- the private repository: the kit moved onto the cut public package (G below).

**Not:** `blender/paths.py`, `paths_sea.py`, `core/catenary.py` (0248 runs there), `reimport.py` (0237),
`camera_path.py` / `rebake.py` (0238), `tc_person.py` (0239), other sets of `tour.py`, the report pictures in
`tasks/img/` (package 4, next).

## Goal

From this task's release on, **nothing of the cable-lay vessel's equipment** is in the public repository's `main`, the
extension, the release zips, the landing page's guide, the test tour, the PC check or the CI artifacts. The public demo
is **"Vessel in a wind park"**: the ship with its own deck crane and a plain deck, the wind park, the sea and the cable
lying on the seabed – no cable laying. The owner's full cable-lay demo still builds, unchanged, from his private kit
(kit 2) on the new public app.

## Background

- **Read first:** `tasks/0226-study-private-vessel.md` – section 1 (every file: public / equipment / mixed, with line
  numbers – check them, the code has moved on), section 4 (the public demo), section 5 (CLAUDE.md lines), packages and
  the owner's answers; `tasks/0228-private-vessel-kit.md` – the report (how a kit build works, the kit's `uses` list,
  the numbers, open points); `tasks/0229-*.md` (the stand-ins on public models – done 0.2.177, so the equipment tests
  are no longer the only proof of any function).
- **Owner's answers (20 Nov):** the ship's **deck crane + hoist stays public** with the ship; **plain deck** – the
  carousel well and the aft bulwark opening are closed; public demo **"Vessel in a wind park"** (sails in, holds
  position, park, weather, cable on the seabed, no cable laying); old reports and CHANGELOG lines stay; **no history
  rewrite**; the private repository keeps the **whole** cable-lay project as its own copies (0228 did this).
- **The kit already is self-contained** (0228): it has its own copies of `demo_model/` (except `geom.py`), of the
  demo's stages, `demo_park.py` and `demo_rov.py`. What it imports from the public app is its `kit.json` `uses` list –
  `demo_model.geom`; from `blender.demo` the framework (`Demo`, `STAGES`, `stage`, `Cancelled`, `cancel_path`,
  `model_dir`, `project_dir`); the app modules `animation, build, callouts, cameras, clash, cylinders, decals, faces,
  flex, joints, logic, materials, paths, paths_riders, paths_sea, spool, states, tour, tracks, vessel_motion,
  vessel_work, weather`. **These names stay public and keep their meaning.** Read the private `kit.json` for the exact
  list before cutting.
- 0228's numbers (kit build = the app's own): full form 466 joints, 20 saved scenes, 3,696 objects, 4,481 frames,
  411 s; small form 356 joints, 3,269 objects, 356 s.
- 0228's open points that belong here: the ROV's clash-check leave-out is code (`demo_rov._clash_hook`, `KEEP =
  "fr_rov"`) that only runs while `demo_rov.py` is loaded – after the cut it must be a tag stored in the project; set
  `demo.PUBLIC` (stays `True`: the public demo is in the list); the tour stop's "432 joints"; the private copies of
  `test_demo_project.py` still check the app's own demo; the private workflow runs on `*.md`-only pushes.

## What to build

**A. The model maker split (`demo_model/`).** As study 0226 section 1 says, in short: a public `ShipParams` with a
fixed beam (no widening from the spread); a **bare `vessel.py`** – hull, paint bands, skeg, thrusters,
superstructure, lifeboats, bollards, anchors, **the deck crane + hoist**; no carousel well or lining, the aft bulwark
closed, no `Kit` import, no `outfit` boxes kept clear of a spread, its own small input instead of `route.positions`;
`route.py` keeps only the shared geometry (`Line`, `Arc`, `Route`, the helpers the park and the seabed cable need);
`deck.py` keeps only `quay()`; `machines.py`, `rov.py` and the private parts of `route.py`, `params.py`, `deck.py`,
`layout.py` are deleted (they are in the private repository); a public layout writes the ship, the park, the quay and
a small sheet with **the ship's own joints** (thrusters, propellers, radars, the crane's slew / luff / hoist);
`make.py` and `__init__.py` reworded. `geom.py`, `occ.py`, `turbine*.py`, `substation.py`, `park.py` stay as they are
unless they import something deleted.

**B. The public demo (`blender/demo.py`, `demo_park.py`).** `TITLE = "Vessel in a wind park"`; only the public stages
(study section 1's list: model, looks, marks, joints, surroundings, sea, cameras, brand, shot 1, propulsion, the park's
stages, finish) plus **the cable lying on the seabed** along the public route from the park's first end – no hang-off
from the ship. Shot 1 aims at the hull; propulsion no longer starts at the shot "Carousel"; the ship sails in and holds
position (vessel at work: wake, bow wave, thruster jets), the crane moves once (a slew and a hoist – it is the ship's
own). Saved cameras as section 4 (Overview, Stern thrusters, Hull side, Beside turbine A, Park overview, Park at
night, At the seabed, + one of the crane). Video about 1 min. `demo_park.py` places the park from the route's seabed
start, not from the lay cable. `demo_rov.py` and every equipment stage, constant and saved camera are deleted.
`MIN_JOINTS` and the other numbers become the bare ship's. **The framework the kit uses stays exactly as it is.**

**C. "Left out of the clash check" as a tag (`blender/clash.py`, additive).** A part tag stored in the project (on the
part's root object, kept through save, reopen and a model update) that the clash check honours like today's code hook.
The kit's ROV stage sets it (G). Keep the hook mechanism if anything public still uses it; otherwise it may go. No new
button (none is needed for this task; say in the report whether one would be useful).

**D. Everything that names the demo.** Tour stop `demo` text + `_check_demo` (the bare ship's numbers, `changed=`,
re-record), `heavy.demo` (make time, Build, frame time of the public demo; no tensioner lift / tilt), `help.demo`'s
title, the guide's chapter `demo` (kept: Make / Cancel / Open, demo kits; rewritten for the bare ship and the park) and
the other guide mentions, **a new `docs/img/demo_overview.jpg`** of the bare ship in the park (look at it before
committing: ship, crane, park, sea only), the PC-check line texts, CHANGELOG, CLAUDE.md sections 3 and 6.

**E. Tests and CI.** Delete the equipment test files and tools (study section 1, "Tests, CI, tools" – they are in the
private repository already); trim the mixed ones to their public checks; `tests/demo_made.py` makes the public demo;
`test_flex_followups_independent.py`'s `set_down_shares` block goes (private); fewer demo groups in CI (`DEMO_GROUPS`,
`ci_times.json`; expect 1–2); the `demo-made` artifact now holds only the public demo. **Add one public test** that
builds the public demo's model files and fails if any part, object or file name holds an equipment word (carousel,
tensioner, chute, quadrant, A-frame, LARS, ROV, CPS, cradle, trestle, loading tower, …) – the app's generic functions
(spool, Lebus, tracks, tensioner test models) are not the demo and are not checked by it.

**F. The release check.** Unpack the built extension zip and the release zip: no `demo_rov.py`, no `machines.py` /
`rov.py`, no equipment STEP or sheet, no equipment picture. Say what you checked in the report.

**G. The private repository (its own rules).** On a branch there: the kit runs on **this task's public branch**
(pinned the way 0228's `kit_made.py` does); the kit's ROV stage sets the tag from C instead of registering a hook; the
private copies of `test_demo_project.py` lose the checks of the app's own demo (Cancel, failure, tour stop, menu) that
the public repository keeps; `paths-ignore` for `*.md` and `img/` in its workflow; `kit.json`'s version range starts at
this task's version. **Proof:** the kit builds the full demo on the public branch with 0228's numbers (466 joints, 20
saved scenes, 3,696 objects, 4,481 frames; small form 356 / 3,269), the ROV is not in the clash check's results, the
private tests pass in its one Linux job. After the public release: merge there and release **kit 2** by hand (one
run).

## Done when

- [x] `demo_model/`, `blender/demo*.py`, `tests/`, `tools/`, `docs/` and the release zips hold no equipment of the
      vessel (the name test of E passes; F checked); the deck crane and the plain deck are in the public ship
- [x] The public demo "Vessel in a wind park" makes, opens, builds and plays (full and small form); numbers in the
      report: joints, objects, triangles at Normal, saved scenes, frames, make time, frame time on the web machine
- [x] Help > Make demo project… lists "Vessel in a wind park" (and kits as before); Cancel / Open / demo kits unchanged
      (`test_demo_kits.py`, real-app `demokits` green)
- [x] The clash check honours the stored tag through save, reopen and a model update (tests); without the old hook
- [x] Tour stop `demo` + `_check_demo`, `heavy.demo`, `help.demo`, guide chapter + picture + mentions, PC-check texts
      updated; version fields (`changed=` / `since=`, `tools/tour_versions.py --record`)
- [x] Kit 2 builds the full demo on the cut public package with 0228's numbers; private tests green; kit 2 released
      after the public release (by hand, one run); the private workflow skips `*.md` / `img/` pushes
- [x] Full suite + GitHub green (fewer demo groups); CLAUDE.md sections 3 and 6, CHANGELOG
- [x] Report: numbers only for anything of the equipment – **no pictures of the equipment** anywhere (pictures of the
      public demo are fine); the owner's steps for kit 2

## Not in this task

- The report pictures in `tasks/img/` and their links (package 4 – briefed after this one; Sonnet · Low).
- 0211 "Lifting site" (after Lifting L7).
- The let-go shape (0248), any other tour set, any change to a test model.
- Rewriting git history, old releases, old task texts or CHANGELOG lines (owner: leave them).
- New equipment, new pictures of the equipment, copying anything from the private repository into the public one.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (4 cores), 20–21 Nov 2026, branch `task/0247-the-cut` → **0.2.188** (0.2.185 – 0.2.187
went to tasks 0239, 0237 and 0246 meanwhile); private repository `smholte/fresing-render-vessel`, branch `task/0247-the-cut` → `main`, kit 2.
No subagents (one design, mostly deletion and a few stages; the kit build on the new app is the independent proof).

**What changed (public):**
- `demo_model/`: `params.ShipParams` (fixed beam, the cable's Ø / MBR) + `ParkParams`; `vessel.py` the bare ship – no
  carousel well or lining, the bulwark closed all round (transom and starboard quarter), its own small `Kit` cache, no
  `outfit` boxes; **the deck crane stays** and its hook block got a slide joint **Hook lower** (plumb, 0–30 m) on its
  hoist; `route.py` only the shared geometry (Line, Arc, Route, turn/pitch/s-bend, rope routes); `deck.py` only the quay;
  `park.py` adds **CABLE ON THE SEABED** (from the first end's seabed point along the lay line to abeam turbine B) and its
  sealed **CABLE END**; `layout.py` writes `demo_vessel.step` (root "DEMO VESSEL"), `demo_park.step`, `demo_quay.step`,
  `demo_route.json` (ship, crane, `place` = park origin 105 m aft of the transom on the centre line, park, quay) and
  `demo_joints.json` (the ship's 13 joints + the park's 19); `machines.py`, `rov.py` deleted; `geom.py` unchanged.
- `blender/demo.py`: TITLE "Vessel in a wind park"; stages model, looks, marks, joints, **crane** (the hoist wire a cable
  on "DECK CRANE: Hoist wire travel", spooled on its drum, its end on the hook; the hook follows the wire 1:1), surroundings
  (quay scene "At the quay"), sea (30 m, a typed-in cut-away 150 × 30 m behind the stern), park, cameras (Overview, Stern
  thrusters, Hull side, At the seabed, Deck crane + the park's three), brand, shots fly (aims at the hull) – turbine A –
  **crane** (slew 90° outboard, 20 m of wire, the hook down beside the ship) – hull + stern thrusters – seabed – park –
  night, propulsion (sails in at 6 kn, DP from the crane's shot), park rotors, finish. The framework the kit uses
  (`Demo`, `STAGES`, `stage`, `Cancelled`, `cancel_path`, `model_dir`, `project_dir`) unchanged; `Demo.set_down_error`
  and every equipment stage / constant / camera deleted; `MIN_JOINTS` 33; `PUBLIC` stays True. `demo_rov.py` deleted.
- `blender/demo_park.py`: placed by the sheet's `place` on the ship at rest (no seabed motion – nothing is laid), Still,
  shift stage gone, shots 2 / 6 / 7 reworded; its clash hook replaced by the tag.
- `blender/clash.py` (additive): `NO_CLASH`, `leave_out(ob, on)`, `left_out(ob, scene)`; `objects()` honours it. Stored
  twice: a custom property on the object and its part ID in the scene's list – a model update makes a **new** root
  object (found by the test) but keeps its part ID, so the list carries the tag over. `HOOKS` stays (flex, paths, spool,
  tracks, people, tc_person use it). A button would be useful for a user's own scenery model (a quay, a second machine
  that never comes near): a later task.
- Tour stop `demo` (text, `changed=0.2.188`; set crane `changed=0.2.188`, recorded), `_check_demo` (50–80 s);
  `heavy.demo` (title, texts, the crane's hook coupling instead of the tensioners, the two new cameras); `help.demo`
  title; `ops_demo.py` texts; guide chapter `demo` rewritten + the clash chapter's "left out" line + the other mentions
  (cable / tracks bullets removed, measurements named "the old cable-lay demo"); **new `docs/img/demo_overview.jpg`**
  (looked at: the ship, her crane, turbine A and the park, the sea – nothing else); CHANGELOG; CLAUDE.md §3 (`demo.py`,
  `demo_model/`, tools), §5 (demo group), §6 (the rule after the cut), §8 (a hook works only while its code is loaded).
- Tests: deleted `test_demo_cable_lay`, `_rov_model`, `test_demo_project_cable` / `_cps` / `_lowering` / `_quadrant` /
  `_realism` / `_rebake` / `_update`, `test_demo_clash` + `_b`, `demo_cps_check.py`; the windows proof moved to
  `tests/test_clash_windows.py` (+ `clash_windows_child.py`); trimmed `test_paths.py`, `test_paths_core.py`,
  `test_flex_followups_independent.py` (set-down shares), `test_ci_tools.py`, `test_web_player.py` (strings);
  rewritten `test_demo_project.py` (incl. **the equipment-word test** over the files, STEP product names, objects,
  groups, joints, cables, spools, scenes and steps; the crane shot; the clash check with the park left out after a
  reopen), `test_demo_project_park.py`, `test_demo_vessel.py` (+ a plain deck), new `test_clash_tag.py`. Tools deleted:
  `make_demo_cable_lay.py`, `demo_cable_lay_pictures.py`, `measure_cables.py`. CI: `DEMO_GROUPS` 1, `ci_times.json`.

**Release check (F):** built `tools/build_release.py` on the branch and unpacked both zips: no `demo_rov.py`,
`machines.py`, `rov.py`, no equipment STEP (the 43 STEP files are the test models and the lifting cranes), no sheet;
a word search (carousel, tensioner, quadrant, chute, ROV, CPS, Lebus, DEMO CABLE LAY) in `demo_model/` and
`blender/demo*.py` finds only `geom.py`'s generic Lebus-drum shapes and one docstring example (kept: `geom.py` stays as
it is) and the sheet drive kind "carousel" in `make_joints`; the guide inside carries the new picture.

**Tested and measured** (web machine, 4 cores, Blender 5.2.3 as a module):
- Public demo, scaled-down form: made in 71–72 s (cable-lay demo: 356 s), 33 joints, 1,028 objects, 870 parts, 1.01 M
  triangles (Draft), 9 saved scenes, 1,489 frames (59 s + cards), 6.2 ms per frame scrubbing. Full form (with the quay):
  made in 76 s (write 31, import 8, park 14, Build 10), 33 joints, 1,054 objects, 893 parts, **1.96 M triangles at
  Normal**, 10 saved scenes, 1,489 frames, 6.3 ms per frame. Clash check over the whole animation: 0 rows in 51 s.
- `test_demo_project.py` 14 + `_park.py` 8 passed (~2 min on the made demo), `test_demo_vessel.py` +
  `test_demo_park_model.py` 18, `test_clash_windows.py` 2, `test_clash_tag.py` 2, `test_demo_kits.py` +
  `test_user_guide.py` + `test_functions.py` + `test_clash.py` 89, `test_ci_tools.py` 63, `test_tour_versions.py` +
  `test_places.py` + `test_web_player.py` 31; PC-check line `heavy.demo` (scaled down) OK: make 72 s, Build 11 s,
  8 ms per frame, peak 1.4 GB; tooltip report 884 / 0 missing; precheck passed.
- **Kit 2 on the cut public branch** (private, numbers only): scaled-down 356 joints, 6 cylinders, 19 saved scenes, 109
  steps, 4,481 frames, 3,269 objects (285 s) – equal to 0228; full form 466 joints, 20 saved scenes, 3,696 objects,
  4,481 frames (346 s) – equal to 0228. In the reopened full project the ROV (28 parts) and the park (762 parts) are not
  among the clash check's objects, and no kit code is in `clash.HOOKS`. Private tests (the workflow's set +
  `test_demo_project.py`) 29 passed locally.
- GitHub (public): **4 full runs.** Run 1 failed one test only (the tour stop's title over 32 characters; every other
  job green, the demo group 1.9 min after a 1.2-min make – the cable-lay demo needed 3.7 + 4 × 6–10 min); run 2 green
  (62 min in a busy queue) but 0.2.186 had gone to 0237 meanwhile; run 3 replaced when 0.2.187 went to 0246; run 4
  green (42 min), `main` fast-forwarded (with 0246's report merged: a docs run).
- GitHub (private, the owner's minutes): one proof run by hand on the branch with the public branch (6.1 min, green);
  then the merge to `main` with `[skip ci]` and one by-hand release run for kit 2 (below).

**Owner steps** (after the update to 0.2.188):
1. **Help > Make demo project…** → pick **Vessel in a wind park** → **Make it**. About a minute later the small window
   says it is ready → **Open demo project**. You should see the ship in the wind park; 6 Animation > "What it can do
   today" → **Build & play**: about a minute – she sails in, her crane swings out and lowers its hook, the thrusters
   under water, the cable on the seabed, the park, night.
2. Your full cable-lay demo: on github.com, signed in: **smholte/fresing-render-vessel** → **Releases** → **Demo kit 2
   (cable-lay vessel)** → download **FresingVesselKit-2.zip**. In Fresing Render: **Help > Make demo project…** → **Add a
   demo kit…** → pick the zip → the status line says "Demo kit added". Then pick **Demo cable-lay vessel (full) (kit 2)**
   → **Make it** (a few minutes) → **Help > Open Demo cable-lay vessel (full)**: the same demo as before (466 joints).
   Use kit 2 from now on (it needs 0.2.188 or newer): with kit 1 the ROV is clash-checked again once the project
   is reopened.

**Open points / follow-up tasks:**
- Package 4: the report pictures in `tasks/img/` and their links (untouched here).
- A button "Leave out of the clash check" for a user's own model (the tag works; no button yet).
- The old demo's measurements in the guide (web 3D, clash times) are kept as "the old cable-lay demo"; a later
  measuring task can redo them on the public demo.
- Leftover branches to delete on github.com: `task/0247-the-cut` (public and private).
