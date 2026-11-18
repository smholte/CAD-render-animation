# 0224 – Study (findings only): every test-tour set brought up to the newest app

**Who:** worker · **Status:** done 19 Nov – findings only · **Branch:** `task/0224-study-tour-up-to-date`
**Started by:** lead, 19 Nov 2026 (owner, 00:16, after the milling sets: "all test tours should get updated / most")
· **Model:** Opus · effort Medium
**Area:** this file only (+ small pictures under `tasks/img/0224/`, test models only)

## Goal

The test tour is where the owner – and later new users and his employer – see what the app can do. Most sets were last
changed at 0.2.101 or earlier (see `@tour_set(..., changed=)` in `blender/tour.py`), ~70 versions ago. This study goes
through **every set except the machining ones** (task 0223 does those) on the newest `main` and lists, per set, what
it shows today against what the app can do now, so the lead can brief the updates by lane.

## For each set and its stops

- **Works?** Go, the check, the animation: anything wrong, missing or ugly (a picture where it helps).
- **Up to date?** Newer functions or looks the set's subject now has that it does not use (examples to check: the
  better materials and marine looks, served cables and full spools, people and props for scale, weather and time of
  day, the sea and its cut-away / view cut, the new side panel and workspaces, Slice instead of Cutaway (0220),
  lifting plans, the Make list). Only what belongs to the set's subject – a set stays small and quick to build.
- **Looks good enough to show a client?** Model detail, materials, camera, light.
- **Proposal** (S / M / L): what to change, which lane's files it touches (tour sets share `tour.py`: group the
  changes so no two fix tasks edit the same set at once).

## Also

- Sets or stops that test the same thing twice; functions that have **no** stop yet (`core/functions.py` entries
  without `tour=`), and whether they need one.
- How long making the whole tour takes now (the owner's PC numbers are not known; measure on the web machine) and
  what a refresh adds.

## Done when

- [x] A table: every non-machining set – works / up to date / client-ready / proposal / size / lane
- [x] 2–5 fix packages for the lead, each with its sets, model · effort and lane, in the order that gives the owner
      the most for the least
- [x] Short questions for the owner at the end
- [x] No code changed; report merged to `main` (no release)

## Not in this task

The machining sets (0223). Fixing anything. The Cutaway → Slice rename (0220) – note only what it leaves.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 19 Nov 2026, on `main` at 0.2.169. No subagents. No GitHub run needed (only
this file and four small pictures).

**How:** the whole tour built with `tour.build_all` (bpy module, 4-core web machine), then for each of the **66
non-machining stops**: Go (`tour.apply`), its number check, a fact sheet (parts shown, triangles, materials, background,
props) and a 400 px Cycles picture (12 samples). Pictures: `tasks/img/0224/` (test models only).

### Findings

**Works:** every non-machining set builds (no error), every one of the 66 stops' Go gives no warning and its check
passes. **One real fault the checks miss:** in all four Lifting stops (`lifting_place`, `lifting_cog`, `lifting_hook`,
`lifting_make`) the load and its CoG are **hidden behind the mobile crane** – a ray from the camera to the CoG first
hits the crane's CARRIER DECK (1.5–2.2 m in front of it); the CoG close-up shows only the truck's wheels
(`img/0224/lifting-marine-sea.jpg`, top row).

**Time (web machine, 4 cores):** whole tour 169 s (house 25 s with its light bake, moving_cable 9 s, vessel_work 8 s,
the rest 1.4–6 s each). Go + check of all 66 stops 18 s; a 400 px picture each 1–4 s. A refresh as proposed below adds
mostly cameras and settings (~0); a sea/quay background adds ~1–2 s per set, new test models ~0.

**Overall:** the sets prove the functions well, but almost all of them were built the same way – PRODUCT light, plain
grey studio, a default ISO camera, the test model in the colours the sorting rules give. Newer looks (surroundings,
weather, props/people, marine looks) are shown only in their own stop, never used by the sets whose subject they fit.
Client-ready today: served, spool, cables, tracks, chains, hoses, cylinder, waycover, sea_cable, props, crane_setup.

| Set (stops) | Works | Up to date? | Client-ready? | Proposal | Size | Pkg |
| --- | --- | --- | --- | --- | --- | --- |
| crane hub – Look `sea`, `looks` | yes | `sea` = crane's desk base floating on the water with a ghost shadow; the sea now has vessel deck, cut-away, ground | no (`sea`) / yes (`looks`) | `sea`: the crane on the Vessel deck or Quay, or drop the stop (vessel, sea_cable show the sea better) | S | B |
| crane hub – Motion `joint` … `explode` | yes | yes | yes (studio) | – | – | – |
| crane hub – Output `still` … `learn` (20 stops) | yes | yes (UI stops of 0.2.150–0.2.160 present) | yes (studio) | `finishing`: add a picture card + music (functions `animation.cards`, `animation.music` have no stop); `demo` passes with "no demo project yet" (fine) | S | D |
| looks – `materials` | yes | yes (0.2.101) | half: Wear not visible at the camera's distance | closer camera on the worn group | S | D |
| faces | yes | no change since 0.2.47 | no: coloured boxes | nicer test model (a housing with a painted face) | M | C |
| decals | yes | no change since 0.2.47 | no: plate + two grey cylinders | nicer test model (a panel / hydraulic tank) | M | C |
| cutaway | yes | 0220 renames it to Slice: leaves the set title / file "Cutaway.blend", the animation name "The pedestal opens up", stop id `cutaway` (ids kept by design) | yes | rename the set title with 0220 or after it (file name changes) | S | (0220) |
| marine | yes | uses none of the sea | no: primitives on grey, the pile cut off top and bottom | a monopile/TP standing in the real sea (SEA + sea cut-away, waterline from the sea), whole pile in frame | M | B |
| served, spool | yes | yes (0.2.139) | yes | – | – | – |
| vessel (+ `web3d_env`) | yes | yes | half: grey deck only | a prop or two on the deck (container, person) | S | B |
| weather (`weather`, `weather_step`, `start_scene`, `night`) | yes | yes (0.2.125) | half: `weather_step` and `night` pictures almost black at 400 px | `night`: a floodlit spot in frame; `weather_step` at ~0.6 instead of the end | S | D |
| props | yes | yes | yes | link `scene.props_detail` to this stop (function has no stop) | S | D |
| cylinder, waycover, waycover2, hoses, chains, cables, tracks, swivel | yes | yes | yes | link `joints.couplings` to `tracks`/`cables` (coupled wheels) | S | D |
| linkage – `mechanism` | yes | no change since 0.2.54 | no: the scissor platform at 1.5 m is out of frame | camera fitted to the raised platform | S | D |
| sea_cable | yes | yes (0.2.141) | yes (box hull) | link `scene.sea_ground` (the ground in the cut-away shows here) | S | B |
| vessel_work | yes | yes | no: a flat blue box seen from 70 m | hull with a shape (make_test_thrusters), camera closer, link `offshore.thrusters` | M | B |
| moving_cable | yes | yes | half: box hull | hull shape (make_test_moving / make_test_sea share it) | S | B |
| copies, update | yes | yes | yes (studio) | link `poses.pose` to `update` (the "Work" pose is kept) | S | D |
| mesh | yes | yes | half: low-poly crane (on purpose: a mesh file) | – | – | – |
| lifting (`lifting_place`, `lifting_cog`, `lifting_hook`) | yes, but **load hidden** | half: no site ground, no mats, desk-size load | **no** | cameras that see load + CoG + hook, a check that the CoG is not hidden; the load on a quay/yard ground; a real-size invented load | M | A |
| crane_setup | yes | yes (0.2.166) | yes | – | – | – |
| lifting_make | yes, but **load hidden** | repeats `lifting_hook` (a second Hook to here) | no | show the made crane by itself (boom out, chart); keep one Hook-to-here stop | S | A |
| clash | yes | no change since 0.2.53 | half: plain arms | – (test model is fine for its job) | – | – |
| sequence, productvideo, sequenceframe (`backtocad`) | yes | yes (0.2.102) | half: `sequence` model small in the frame | camera closer at the start | S | D |
| people | yes | yes | no: a desk-size test crane next to life-size people | people on the Quay round a real-size prop (container, pallet) | S | D |
| house | yes | yes (0.2.152) | no: the format's sample house is one brick box | not ours: a nicer sample is a house-scene-format task (both leads) | – | (Q4) |

**Twice the same:** `lifting_make` repeats `lifting_hook`; the hub's `sea` repeats what `vessel`, `sea_cable`,
`moving_cable` show better; `looks`/`still`/`turntable` and the UI stops share one picture (fine: they test different
things). **Functions without a stop (33):** most need none (import, structure, rules, help, updates, PC check, About, the
tour itself, machining ones → 0223). Cheap to link to an existing stop (`tour=` in `core/functions.py`, no new stop):
`offshore.thrusters` → vessel_work, `scene.sea_ground` → sea_cable, `scene.props_detail` → props, `poses.pose` →
update, `joints.couplings` → tracks. Worth a small addition: `animation.cards` + `animation.music` in `finishing`;
`lifting.chart_entry` (a CSV chart) in the lifting set. `web.under` / `web.moving` could be a web-3D stop on the
sea_cable set (an export of ~5 s) – optional.

### Packages proposed (in order of most for least)

Each package owns its own sets in `tour.py` (no two packages touch the same set); each sets `changed=` on its sets and
runs `tools/tour_versions.py --record`; every package keeps `tests/test_tour_clash.py` at 0 clashes.

1. **A – Lifting stops see the load** (Lifting lane; sets `lifting`, `lifting_make`; Sonnet · Medium; S): cameras that
   see load, CoG and hook (and a check in the stop: the line from the camera to the CoG is not blocked – the fault no
   check caught); ground = Quay/yard surroundings with mats under the outriggers; `lifting_make` shows the made crane
   on its own. Owner Q3 decides the load.
2. **D – Framing and links in the studio sets** (no lane of its own – tour + `core/functions.py` only; sets `crane`
   hub (finishing only), `looks`, `weather`, `linkage`, `sequence`, `people`, `props`, `update`, `tracks`, `cables`;
   Sonnet · Medium; S–M): mechanism / sequence / materials / night / weather_step cameras and frames; people on the
   Quay with a real-size prop; picture card + music in Finished video; the five `tour=` links. Owner Q1 decides
   whether the studio sets also get a showroom look.
3. **B – Offshore sets that look offshore** (Sea lane + the hull makers of the Test models lane; sets `crane` hub
   (`sea` stop only – do after D or in it), `marine`, `vessel`, `vessel_work`, `sea_cable`, `moving_cable`; Opus ·
   Medium; M): the marine pile in the real sea, the sea stop on a deck or dropped, the workboat/hull models with a
   hull shape (`make_test_thrusters.py`, `make_test_sea.py`, `make_test_moving.py`, both data copies), closer cameras,
   a prop on the vessel deck.
4. **C – Test models round 2** (Test models lane; sets `faces`, `decals`; Sonnet · Medium; M): the two sets 0122 did not
   reach get real-looking models (`make_test_faces.py`, `make_test_decals.py`), same part names so the checks stay.

**Not a package:** the Cutaway → Slice set title goes with task 0220 (or a one-line follow-up after it); the House
sample is the format repository's (Q4).

### Questions for the owner

1. The studio sets (grey floor, PRODUCT light): keep them plain – quick to judge whether a function works – or give
   them a showroom / hall look so the tour can be shown to a client as it is?
2. Is the test tour also meant as the thing you show clients and your employer, or do clients get the demo projects
   (vessel, later the lifting site 0211) and the tour stays a check list? That decides how far packages B–D go.
3. Lifting stops: the load is the desk-size test crane's boom (1.2 t on a 1.5 m model). Switch to a real-size invented
   load (a container, a skid, an IBC)?
4. The House stop's sample is a single brick box from the public format repository. Worth a format task (both leads)
   for a nicer sample house, or leave it?
