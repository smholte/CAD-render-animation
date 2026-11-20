# 0247 – The cut: the vessel's equipment leaves the public repository; the public demo becomes "Vessel in a wind park"

**Who:** worker · **Status:** open – can start · **Branch:** `task/0247-the-cut` (public) + a branch in the private repository
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

- [ ] `demo_model/`, `blender/demo*.py`, `tests/`, `tools/`, `docs/` and the release zips hold no equipment of the
      vessel (the name test of E passes; F checked); the deck crane and the plain deck are in the public ship
- [ ] The public demo "Vessel in a wind park" makes, opens, builds and plays (full and small form); numbers in the
      report: joints, objects, triangles at Normal, saved scenes, frames, make time, frame time on the web machine
- [ ] Help > Make demo project… lists "Vessel in a wind park" (and kits as before); Cancel / Open / demo kits unchanged
      (`test_demo_kits.py`, real-app `demokits` green)
- [ ] The clash check honours the stored tag through save, reopen and a model update (tests); without the old hook
- [ ] Tour stop `demo` + `_check_demo`, `heavy.demo`, `help.demo`, guide chapter + picture + mentions, PC-check texts
      updated; version fields (`changed=` / `since=`, `tools/tour_versions.py --record`)
- [ ] Kit 2 builds the full demo on the cut public package with 0228's numbers; private tests green; kit 2 released
      after the public release (by hand, one run); the private workflow skips `*.md` / `img/` pushes
- [ ] Full suite + GitHub green (fewer demo groups); CLAUDE.md sections 3 and 6, CHANGELOG
- [ ] Report: numbers only for anything of the equipment – **no pictures of the equipment** anywhere (pictures of the
      public demo are fine); the owner's steps for kit 2

## Not in this task

- The report pictures in `tasks/img/` and their links (package 4 – briefed after this one; Sonnet · Low).
- 0211 "Lifting site" (after Lifting L7).
- The let-go shape (0248), any other tour set, any change to a test model.
- Rewriting git history, old releases, old task texts or CHANGELOG lines (owner: leave them).
- New equipment, new pictures of the equipment, copying anything from the private repository into the public one.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Owner steps** (after the update):

**Open points / follow-up tasks:**
