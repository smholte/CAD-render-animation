# 0349 – Lifting L6b: clearances along the path, reach envelope, exclusion zone, ground footprint + the makers' fixes

**Who:** worker · **Status:** done (0.2.275) · **Branch:** `claude/cad-render-animation-0349-9y2i9w`
**Started by:** lead, 28 Nov 2026 (0348 done 0.2.269, 0327 done 0.2.261; 0180's L6 plan) · **Model:** Opus · effort High
**Area:** Lifting lane – `core/lifting_path.py`, `blender/lifting_path.py`, `core/lifting_reach.py`, `core/lifting.py`,
`blender/lifting*.py`, `ops_lifting*.py`, `ui_lifting*.py`, the makers (`ops_lifting_make.py`, `core/lifting_library.py`,
`lifting_rig*.py`, `setup_crane.py`, `fresing_render/lifting_model/`), the Lifting tour stops (own spots), their tests,
guide. `core/clash.py` / `blender/clash.py` **additive only** (a minimum-distance query, if the existing gap search can't
give it) – the Clash lane's own fixes (0378) wait for this task. **Not:** 0211's demo (after L7–L9).

## Part 1 – L6b (0180 report: the L6 plan, lines ~290–310; 0348's "What L6b needs")

- **Clearances along the path:** minimum distance boom / load / rigging ↔ obstacles at every moment (the clash check's
  gap search 0065 / 0110 as a distance); rows join `Checks.at` (the search already handles them); a threshold the user
  sets (default from a public guideline, cited), colour like C1–C6.
- **Reach envelope:** the chart curve as a range diagram (2D, in the plan / data box) + a 3D ring in the view.
- **Exclusion zone:** a ring / polygon on the ground round the lift (load path + margin), drawn and printable.
- **Ground footprint:** pads / tracks coloured by C5 / C6 pressure per moment (`Supports.items`).
- All in the printable plan where 0201 / 0348 put checks.

## Part 2 – the makers (do first: they change what Part 1 shows)

- **AT / KB samples' masses don't fit their sample charts** (0348): the charts' tipping assumed the carrier at the slew
  axis; the files' carrier CoG is its solid's centre (AT-40: 4.2 m forward, front pads at 2.7 m) → C5 red at 96 % chart
  use, an outrigger lifts off at 6 t. Fix in the makers (outriggers at the carrier's ends, or charts from the real CoGs).
- **CC-750 "Steep":** boom pendant bar L × rod L 4.9 mm in its own pose (0203) + a **clash test of every built-in pose**
  of every maker.
- **Library picture after Replace** stays the old one until a restart (0204: the cache keys on the path).

## Done when

- [x] Part 2 fixed with tests; Part 1's four features with tests, tooltips, guide, tour stop, function list
- [x] A lift on the Lifting set shows all four, and the printed plan has them (pictures in the report)
- [x] Tests added / updated; full suite passes (also on GitHub)
- [x] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [x] (Windows-only code) reviewed by a helper that did not write it
- [x] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)
- [x] **Owner's check** line

**Running beside it (weekend 28–29 Nov):** 0371 Demo · 0355 / 0356 Assets · 0372 Welds · 0347 Machining · 0349
Lifting · 0353 Web 3D + House · 0373 guide-picture tool · 0374 cable-lay line · 0375 Sea · 0377 Start & windows ·
0379 PC check · findings-only 0380 / 0381. Shared files only additively, each in its own spot: `props.py`, `tour.py`,
`core/functions.py`, `tools/guide_screens.py` (0373 owns its start-up code), `pccheck/checks.py` / `heavy.py` (0379
owns the lines it names). Whoever merges second updates its branch to `main`; versions: CLAUDE.md section 7 step 0.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus · High), 28 Nov 2026 · released as **0.2.275**

**What changed:**
- **Part 2a – the AT / KB samples fit their charts** (`lifting_model/classes.py`, `charts.py`, `common.py`,
  `equipment.py`, `knuckle.py`, `params.py`): a mobile crane's front outrigger pair stands right behind its front axles,
  the rear pair "Front to rear pads" behind it (class spans 7.9 / 8.5 / 10.8 / 11.0 m; a span that leaves the rear pads
  closer than 30 % of it behind the slew axis is refused: new Make-a-crane rule `pads_apart`); a knuckle-boom truck's
  front stabilisers stand ahead of its cab (they stood under the column: the base's edge ran through the slew axis);
  a cab or bonnet counts at 15 % of its volume for the centres of gravity (`common._weight`); the SAMPLE charts' tipping
  is worked out from the file's own CoGs over the real outrigger base at every slew angle (`charts.tip_load`,
  `base_margins`; backward stability by the same rule as 0348's BACK row). All 12 files, 8 STEPs and 8 pictures made
  again. AT charts nearly unchanged (AT-40 at 9 m 13.7 → 15.3 t), KB ≤ 3 % lower at long reach.
- **Part 2b**: Set up a crane's Check leaves a cylinder's own sliding parts out (`setup_crane.cylinder_pairs`) – the
  CC-750 'Steep' 4.9 mm (reproduced: 4.9 mm in 'Steep', 8.2 mm over the luff range) is the clash check's inside test of
  the 7 m pendant bore (Clash lane 0378); the geometry is right (pin distance within the fit). New tests: every built-in
  pose of all 12 classes through the app's clash check (`tests/test_lifting_pose_clash_{at,kb,cc_a,cc_b,cc_c}.py`).
- **Part 2c**: the library picture cache keys on path + change time + size (`ui_lifting.picture_key`).
- **Part 1 – `core/lifting_zones.py`** (new, no Blender): `Clearance` (moving parts as surface points 5 cm apart in
  their joint's frame at zero, grouped in 15 cm and 1 m cubes; obstacles as triangles; a best-first search – the same
  answer as every point; a point behind a face, straight below it, reads 0 m; what the load touches at the pick / the
  set-down is left out, what it is nearer to than the clearance needed counts again once it moved that far), row `CLR`
  in `lifting_path.Checks.at` (use = needed / distance, amber from 75 %, red under it); `reach` + `range_curve`;
  `exclusion_zone` (tail swing – OSHA 29 CFR 1926.1424(a) –, supports, path + load radius, margin; polygons that hold
  their circles); `footprint` (pads with reactions / pressures, tracks in 8 pieces); `plan_svg`, `range_svg`,
  `sheet_html`. Default clearance 3.05 m = OSHA 29 CFR 1926.1408 Table A (10 ft, lines up to 50 kV), checked at the
  source.
- **`blender/lifting_zones.py`** (new): moving parts / obstacles from the project (not the ground, floor, sea or the
  app's helpers), Blender's BVH for the obstacles, a project key (every object's own matrix), the live row worked out
  once the pose stood 0.3 s (a drag costs nothing), drawing on the ground (POST_VIEW, never in a render), `path_view`
  (stored in the path result), **Plan sheet…** (HTML, A4 landscape, opened in the browser).
- UI: sub-panel **8 Lifting plan > Clearance & zones** (`core/places.py`), the path table shows the clearance as a
  distance; props (additive) `clearance_m`, `zone_margin`, `show_reach`, `show_zone`, `show_footprint`; operator
  `fresing.lifting_plan_sheet`. Function entries `lifting.clearance`, `lifting.zones`, `lifting.sheet`; tour stop
  `lifting_zones` (Lifting set, from above; MIN_LINES_TOUR / MIN_CHECKS tour 122); PC-check line `lifting.zones`
  (MIN_LINES_FULL 168); guide section "Clearance & zones" + `panel_8_lifting_zones.png` (the other Lifting panel
  pictures made again); `tools/guide_screens.py` (additive: the zones step).

**Tested and measured** (4-core web machine):
- Built-ins at full chart capacity, 24 slew angles × 9 radii, the file's own masses: before, AT-40 "outside the
  outriggers" (red) at slew 0° / 45° on every radius, KB-20 red at 90–180°; after, **no red on any AT / KB class**; a pad
  goes light (amber) on AT-40 only from 75 % of the chart, AT-100 at 100 %; KB-200 from 50 % at long reach over the
  rear corners (the 4-pad rule of C5). `tests/test_lifting_cranes_fit.py`.
- Every own pose of the 12 classes through the app's clash check: clean (AT 18 s, KB 30 s, CC-750 98 s each).
- Clearance against a wall 0.8 m beside the hook block: the true gap (1 cm points on the faces) or up to 3.5 cm more.
  Check along the path on the skid lift (226 moments): first version 25 s **per moment** (box trees), now **3.6 s for
  the whole check** including the Build (the clearance ~5 ms a moment). Drag test of 0348 still under its 5 % / 10 %.
- Real app (`ci_real_app.py --only lifting,liftingmake,setupcrane`): 22/22, 25/25, 32/32. Tour Lifting set 17 passed.
  PC-check lines `lifting.path`, `lifting.zones` OK.
- **Independent tester (subagent, did not write the code): 59 tests**, found 10 faults – a left-out obstacle hid the
  others, leave-out by name (repeated names), no inside reading, the project key missed a turn in place, points 0.47 m
  apart on a 30 m boom, a NaN corner hid a part, the sheet said "lower bound", `distances`' docstring, the zone's
  polygons inside their circles (−5 cm). All fixed but one (below); 8 of its tests adjusted to the deliberate design
  (index-based leave-out, the reach words, the pick rule). 71 pass + 1 xfail.
- GitHub: see the last line of the report.

**Task 0380's fix group F1 (owner's request, 28 Nov)** – the rows of bug hunt 9 on the lift path, `tests/test_lifting_0380.py`:
- **Row 1 – crash** (Check along the path → Go there → Ctrl+Z → segfault): the cached checks' line pull held the crane
  that the undo freed. `undo_post` / `redo_post` now drop the lifting caches (readouts, checks, live rows, clearance);
  the line pull looks the crane up by name when asked (gone: grey "no longer in the plan"); **Go there** has its own
  undo step. Tested on the module (the handlers, a line pull after the crane is removed); the real-app Ctrl+Z was not
  repeated.
- **Row 10** (C5 "outside its outriggers" while C1 25–39 %): the AT-40's file, fixed by Part 2a. The 0380 lift (the
  example to −2, 4.5, 0): with the old file the test fails exactly as reported (frame 259, C1 25 %, C5 "outside the
  base"); with the new one no moment is outside and the worst C5 moment equals a hand calculation.
- **Row 11** (a key changed by hand did not date the checks): the check stores the built keys' print; while the path's
  animation is the one built, a changed key makes it "Changed since it was checked".
- **Row 25**: the luff / telescope pieces are named "Luff / telescope 1/6 … 6/6", the message says "N steps (M joint
  moves)"; Remove the crane removes its proposed lift path (and the plan's path and checks); your own animations stay.

**Pictures** (`tasks/0349_page/`): `1_zones_top.png` (the 3D view from above: exclusion zone, red / amber reach rings,
the mats coloured), `2_plan_sheet.png` (the printed plan: plan view, range diagram, checks), `3_panel.png`.

**Open points / follow-up tasks:**
- A moving part wholly inside a closed obstacle deeper than the search (4.5 m) is not found (the tester's xfail test);
  within the search a point behind a face reads 0 m. The clash check covers overlaps.
- The hoist rope is not in the clearance (it is a cable); the rope near a power line matters – later.
- Clash lane 0378: the inside test in a long thin bore (the CC-750 pendant) – Check leaves own cylinder parts out now.
- KB-200 lifts a pad at 50 % of the chart at long reach: the C5 4-pad rule (one pad unloaded = amber); a sector chart
  over the rear corners would be more like a real loader crane – Lifting makers, later.
- The plan view draws the footprint and zone, not the crane's outline or the obstacles' outlines (L7's drawings).
- The ground drawings are in the 3D view only; the printed plan is HTML (L7 brings the PDF).

**Owner's check line:** Update, open the test tour, Lifting set, stop "Lifting: clearance and zones":
from above you see the red dashed exclusion zone, two rings and four green mats; 8 Lifting plan > Clearance & zones >
**Plan sheet…** opens the page to print in your browser.
