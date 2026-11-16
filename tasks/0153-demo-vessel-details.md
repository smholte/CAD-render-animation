# 0153 – Demo vessel: a detailed hull, superstructure, propulsion and its looks

**Who:** worker · **Status:** done (0.2.120, 16 Nov) · **Branch:** `ccr-82ef1269-tt9p0w` (the web session's branch)
**Started by:** lead chat, 16 Nov 2026 (owner: "more details to the ship itself") · **Model:** Opus · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation". Subagents allowed (CLAUDE.md section 2).
**Area:** Demo models lane: `fresing_render/demo_model/` (params, geom, the hull and new parts), `demo.py` (looks, joints of the new parts, the stage list only where needed), `blender/marine_looks.py` (use, add only if needed), the demo's tests (as 0145 split them).
**Do not edit:** the sea / surroundings code (`surroundings.py`, `core/sea.py` – 0148, then 0154), the Web 3D lane (0142/0143), `paths*` / cable code, milling (0146).

## Goal

The demo's vessel looks like a real offshore cable-lay vessel close up, not a box with a deck: shaped hull, a proper superstructure, propulsion you can see turning, and believable paint, wear and growth.

## What to build

1. **Hull:** a shaped bow (flare, optional bulbous bow), a stern with a skeg / transom, bilge keels, a slight sheer;
   still a ruled loft (0074: smooth lofts mesh 5× heavier). Moon pool optional.
2. **Superstructure and deck outfitting:** accommodation block with window rows, bridge with wings and bridge windows,
   mast with radar / antennas / lights, funnel(s), lifeboats or rescue boat in davits, railings along the deck edge,
   a helideck optional, a deck crane (its own joints, parked), bollards, fairleads, hatches. Keep the cable-lay
   spread and its clearances as they are (the stages and the clash test must not change).
3. **Propulsion:** two azimuth thrusters (or shaft propellers + rudders) at the stern, one or two **tunnel bow
   thrusters** (openings in the hull, propellers inside), a retractable azimuth optional. Each propeller and azimuth
   gets a joint (turn / steer) so the animation and 0154's water effects can drive them.
4. **Looks:** hull paint above the waterline, boot-top stripe, red antifouling below, draft marks and a name plate
   (invented name, decals of 0024), non-slip deck paint, steel and galvanised outfitting, glass; wear: rust streaks
   from scuppers and hawse pipes, scratches on the side where fenders touch, **marine growth below the waterline**
   (0116's `paint_marine_growth`, banded by `fr_waterline_z`).
5. The demo's shots and cameras still frame well; one new camera for the stern / thrusters and one along the hull side.

## Rules

The vessel is **invented** (CLAUDE.md section 6): no real vessel's or the owner's employer's design, names or
pictures; generic features every offshore construction / cable-lay vessel has. Test models one solid per part
(`geom.write_step`). Every tour animation keeps 0 clashes; the demo's clash test stays green.

## Done when

- [x] Model maker tests (sizes, one solid per part, joint count), the demo builds and its tests pass; the clash test 0
      rows; triangles and Make demo time before/after (aim: Make demo ≤ +20 %).
- [x] Tooltips, guide, PC-check line / tour stop, function list for anything new the owner sees; GitHub run green;
      merged; version (CLAUDE.md section 7); report with small before/after pictures (invented demo only) in
      `tasks/img/0153_*` and the cost (import time, triangles, frame time) before/after.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 16 Nov 2026. Version **0.2.120**. No subagents (the work was one
module plus its wiring; the independent review was skipped: no Windows-only code).

**What changed:**
- **`fresing_render/demo_model/vessel.py` (new)** – the vessel moved out of `machines.py` and grew:
  - *Hull* (still a ruled loft): fuller deck forward with flare, a raked stem (the forward stations' keel rises above
    the waterline), a bulbous bow, a 2 m sheer over the forward 14 m only (aft of it – where the whole spread stands –
    the deck stays level at `deck_z`, so no stage, clearance or clash changes), a centre skeg, two bilge keels, a
    rubbing strake along each side, freeing ports and fairleads in the bulwark (which now follows the sheer). The hull
    is cut into **HULL BOTTOM** (keel to −0.9 m), **BOOT TOP** (−0.9 … +0.7 m) and **HULL**; **MAIN DECK** is the top
    40 mm, following the sheer (bands sampled at the stations: the top is plane between them).
  - *Superstructure*: three tiers with window rows (openings cut, tinted glass set back), a bridge with wings and
    window bands, two funnels with black tops, a mast with two radars (each a joint), antennas and lights, lifeboats in
    davits, railings (square bars: round ones made the booleans 10 × slower).
  - *Propulsion*: two **azimuth thrusters** under the stern (housing, strut, pod, nozzle with stators, propeller;
    joints *Steer* and *Propeller turn* riding on it) and two **bow tunnel thrusters** (the tunnels cut through the hull
    bottom, a lining, a gearbox on a strut, a propeller; joint *Propeller turn*). Propellers are lofted twisted blades.
  - *Outfitting*: a deck crane on port (slew + luff joints, parked with its boom up 70° forward), 6 bollards,
    4 fairleads, 3 hatch covers, 2 windlasses, 2 hawse pipes with stockless anchors, name boards and draft-mark boards.
  - 10 new joints in the sheet (317 now); propellers, steers, radars and the crane's slew carry `motor: true`.
- **`blender/demo.py`**: looks for the new parts (hull `paint_marine_streaks` RAL 5003, boot top and antifouling
  `paint_marine_growth` – growth below `fr_waterline_z` –, non-slip deck `powder_coat`, white superstructure with
  streaks, tinted glass, galvanised railings/davits/antennas, orange lifeboats, bronze propellers, black deck fittings
  and rubbing strake with wear 0.8); new stage **marks** (text decals: "DEMO LAYER" on both name boards, 5M/6M/7M on
  the four draft-mark boards); `make_joints` sets the sheet's motors; new stage **propulsion** (a *Run motor* step per
  propeller – 30 rpm azimuths, 40 rpm bow thrusters – and radar – 24 rpm – over the whole animation); two saved cameras
  **Stern thrusters** (under water) and **Hull side** (from ahead of the bow along the starboard side). `MIN_JOINTS` 318.
  No new button or setting: no tooltip, function-list entry or tour stop of its own (the demo's stop and Heavy line
  were extended).
- **Test tour** stop "demo": its text, and its check's animation length 60–80 s → 120–200 s (the animation has been
  ~150 s since the quadrant shots; the stop would have failed on the owner's PC once a demo was made).
- **PC check Heavy** `heavy.demo`: also checks the propellers/radars are motors and the two cameras exist.
- **Guide** (demo chapter): the vessel's details, looks, joints, cameras; the overview picture replaced.
- **Tests**: `tests/test_demo_vessel.py` (new, 9 tests: one solid per part, part counts, joints and motors, propellers
  turned at 4 angles never meet nozzle/pod/tunnel/hull, thrusters under water, tunnels through the hull, sheer/stem/
  bulb/paint bands, deck plate volume, outfitting inside the deck outline and not overlapping, boards on the side);
  `test_demo_cable_lay.py`: the outfitting keeps 100 mm clear of every part of the spread; `test_demo_project.py`:
  looks, decals, cameras, motors turning at their speed, stage order, 317 joints.

**Tested and measured** (4-core web machine, Blender 5.2.3 as a module; the demo's scaled-down form as GitHub makes it):
- Make demo (`tests/demo_made.py`): before 312 s; after 348 s and 375 s in two runs (+12 % / +20 %; the runs vary – the
  model stage 86 → 83–87 s). The animation build alone, profiled on the saved projects: 83 → 90 s (+8.5 %); a frame
  change 40.5 → 42.9 ms (+6 %); the propellers' motors cost nothing measurable (44.6 ms with them stopped).
- Import at Normal (the app's importer on demo_cable_lay.step): placed parts 1,327 → 1,416; placed triangles
  1.95 M → 2.12 M (+8.5 %; the vessel's own 324 k → 490 k; budget 3 M); read 17.3 → 17.7 s; STEP 35.8 → 46.7 MB.
- The vessel alone builds in ~10 s (was ~3 s).
- `test_demo_cable_lay.py` + `test_demo_vessel.py`: all pass. Demo project tests locally (made demo, 24 tests): all pass
  but the stage-order check, which was then updated for the new stages.
- **The demo's clash check found two faults of mine**, both fixed and now covered by `test_every_turning_part_turns_free`
  (every motor joint turned to 7 angles, nothing it may meet): radar scanner 1 swept through the mast's pole (259 mm),
  and an azimuth thruster steered round met the hull bottom that slopes down forward (now mounted under the lowest
  point of its whole sweep). After the fix the first half of the clash check passed locally with 0 rows; the whole
  check is green on GitHub.
- GitHub: 4 runs. Two stopped in the precheck on a version clash (0.2.117 and 0.2.119 were taken by 0146 and 0162
  while this ran), one full run green on the merged branch (21.5 min), one more full run for the Hull side camera fix
  and the second merge (the one main was fast-forwarded to). Demo jobs 7.9 / 9.6 / 9.9 / 12.7 min
  (main's run before: 9.1 / 9.2 / 10.2 / 9.2); "make the demo project" 4.9 min (was 3.7, the arch change of 0159 is in
  it too).
- Pictures (invented demo only, Cycles 24 samples, the scaled-down demo): `tasks/img/0153_hull_side_before.jpg` /
  `_after.jpg`, `tasks/img/0153_stern_before.jpg` / `_after.jpg` (under water: the azimuth thrusters in their nozzles,
  growth on the antifouling); the guide's `docs/img/demo_overview.jpg` replaced.

**Open points / follow-up tasks:**
- Helideck and a retractable azimuth (both optional in the brief) not made.
- Rust streaks run down everywhere on the hull (`paint_marine_streaks`), not from each scupper and hawse pipe in
  particular; fender scratches are the rubbing strake's edge wear, not marks on the plating.
- The bow thrusters and azimuths do not steer in the animation (their joints exist for 0154).
- The hull is still a ruled loft: in close-ups at low sun its bow shows the facets between stations (0074's reason
  for ruled lofts – triangles – still holds; more stations forward would soften it at some triangle cost).
- The name and draft marks are decals on thin boards (the hull's ruled faces are not flat enough for a flat decal);
  the boards show a 15 mm step at their edges close up.
