# 0166 – Demo: a wind park round the cable-lay vessel – turbines, a substation, the cable from turbine to turbine, night lights

**Who:** worker · **Status:** waiting – starts **after 0160 is merged** (the sea cable code `paths_sea.py`) ·
**Branch:** `task/0166-demo-wind-park` (a session branch `claude/…` is fine – say which in the report)
**Started by:** lead chat, 16 Nov 2026 (owner's wish "add windmills to the cable-lay demo – a wind park"; his answers
below) · **Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation".
Subagents allowed (CLAUDE.md section 2): a maker for the turbine + substation, an independent tester.
**Area (Demo models lane):** `fresing_render/demo_model/` (new `park.py` or `turbine.py` + `substation.py`, `params.py`,
`layout.py`, `make.py`), `blender/demo.py` (new stages + the shots below, the seabed's motion taking the park along),
`blender/paths_sea.py` only for the cable's first end at the J-tube (after 0160), the demo tests (a new
`tests/test_demo_project_park.py` with `from demo_made import made`), the guide's demo section, `site/CREDITS.md`.
Shared code with the site's turbine: see "Turbine" below (`tools/site_projects/turbine_parts.py`, `iea15_standin.py` –
the Site kit lane is free).
**Do not edit:** `surroundings.py`, `core/sea.py`, `vessel_motion.py` (0155, then 0154 – if the sea does not reach the
far turbines, write it as an open point for 0154); the Web 3D lane (0164, 0165, 0143); `cable_looks.py` (0164);
`demo_model/vessel.py` (0153's vessel, read only).

## Goal

The demo project "Cable-lay vessel" works inside an offshore wind park: monopile turbines in rows and an offshore
substation stand round the vessel, their rotors turn, the vessel lays an array cable from one turbine to the next, and
new shots show the park from above, the vessel beside a turbine, and the park at night with its lights.

## Owner's answers (16 Nov 2026)

- **Role:** scenery **and** the cable route – the cable runs from one turbine to the next: its first end goes up a
  J-tube of turbine A, the second end (shots 9–12) is laid down beside turbine B (pulled in later – not shown).
- **Turbines:** monopiles (like the IEA 15 MW offshore turbine of 0116) **plus an offshore substation** where the export
  cables go. Rows, about 1–2 km apart.
- **Shots:** (1) an overview of the park with the vessel laying; (2) the vessel beside a turbine – the boat-landing /
  J-tube side; (3) night with the turbine lights.
- Licences (owner, 16 Nov): own models or CC0 bases only. Everything here is invented by Fresing, sized from the IEA
  15 MW public numbers (credit the IEA reference turbine as the site does).

## Background

- **The vessel stands still; the seabed moves aft** with the lay (`demo.py` around the `sea` stage: the lay cable's
  metres drive the seabed). The park stands on the seabed, so **it must move aft with exactly the same motion** (same
  driver, scripts off), never with the vessel's heave/pitch/roll (0085: not a child of the vessel rig). At the demo's
  lay speed the park moves only tens of metres per shot: turbine A beside the vessel and turbine B at 1–2 km cannot both
  be close in one shot. Place the park **per shot** (an offset keyed at each shot's start, as the seabed already takes
  Cable travel's value before shot 9), so turbine A is beside the vessel in the first-end shots and turbine B in shots
  9–12. Write the scheme in the task file's Design first.
- **Turbine:** the site's turbine (0116) is converted from the owner's STEP, which is **not** in the repository and
  must not be. The repository has an invented stand-in with the same sizes (`tools/site_projects/iea15_standin.py`)
  and the invented parts at the tower's foot (`turbine_parts.py`: transition piece, platform with grating and railings,
  boat landing with fenders and ladder, davit crane, door with landing, J-tubes, cabinets, lights). The demo's maker
  runs inside the extension (`fresing_render/demo_model/`, shipped), `tools/` is not shipped: move what both need into
  the package (e.g. `demo_model/turbine.py`) and let `tools/site_projects/` import it from there, so the site's
  converter keeps working unchanged (its tests must stay green, byte-identical sheets). Blades: closed, round root,
  turning **clockwise** seen from the front (CLAUDE.md section 8).
- **Substation:** invented: a jacket (four legs, braces, piles), a topside with two or three decks, cladding, a
  helideck, a pedestal crane, a cable deck with the J-tubes / I-tubes coming up, a boat landing and ladder, lights.
- **Instancing:** the importer keeps one mesh per unique part, so 6–9 identical turbines cost objects, not meshes.
  Each turbine's rotor (and yaw) is a joint; rotors turn at slightly different phases, all facing the same wind.
- **Clash check:** the park must give 0 clash rows; parts far from anything that moves may be left out of the check if
  that is the only way to keep the demo's clash jobs within their time – measure first, say what was left out.
- **Night:** the weather preset Night shift (0109) gives the night sky, the vessel's floodlights and work lights. Add:
  red aviation lights on every nacelle flashing **together** (one simple-expression driver on the emission, scripts
  off), yellow flashing lights on the transition pieces / substation corners, the substation's own deck lights.
  Check the real marking practice in the report in one line (no web pages needed – plain knowledge, marked as such).

## What to build

1. **Park layout** (`params.py`): turbines in 2–3 rows on a grid of about 1.0–1.5 km, the substation near the middle,
   the cable route from turbine A to turbine B along the vessel's lay line; water depth = the demo's sea depth.
2. **Turbine and substation makers** (one solid per part, CLAUDE.md section 8), parts named so the demo's groups and
   looks pick them up (paint, galvanised, the marine looks of 0116/0128 below the waterline).
3. **Stages in `demo.py`:** `park` (import / place / joints / looks / lights, after `sea`), the park's motion with the
   seabed, the first end at turbine A (the cable from the J-tube's bell-mouth on the seabed to the touch-down – a fixed
   end on the seabed; the turbine's J-tube carries it up into the tower foot), the second end of shots 9–12 laid down
   beside turbine B.
4. **Shots:** "Park overview" (high camera, the vessel laying, rows of turbines, the substation), "Beside turbine A"
   (boat-landing / J-tube side, the cable into the J-tube, a sea cut-away view if it reads well), "Park at night"
   (Night shift, the lights flashing). Saved cameras for each.
5. **Measure** before/after on the made demo: Make demo time, objects and triangles, Build time, playback ms per frame,
   the demo clash jobs' times on GitHub, the project file size.

## Done when

- [ ] The park stands on the seabed and moves with it in every shot (test: the turbines' feet stay on the seabed
      within 1 mm at every frame; they never heave with the vessel).
- [ ] The cable's first end runs from turbine A's J-tube along the seabed to the touch-down without passing through the
      monopile, scour rock or seabed (test); shots 9–12 lay the second end beside turbine B (test: its end lies within
      the planned distance of B's J-tube bell-mouth).
- [ ] Rotors turn clockwise seen from the front, every turbine faces the same wind; lights flash together at night
      (test reads the driver at two frames); scripts off works.
- [ ] 0 clash rows on the demo; the demo jobs on GitHub stay ≤ ~10 min each (CLAUDE.md section 5) – split a new check
      into its own `test_demo_project_<topic>.py`.
- [ ] The site's converter tests still green with the moved code (`tests/test_site_turbine_*.py`).
- [ ] Guide's demo section, test-tour stop or PC-check line only if a new function the owner can see appears (the park
      is demo content – say what was decided); `site/CREDITS.md` line.
- [ ] GitHub run green; merged; version (CLAUDE.md section 7); report with small pictures of the three new shots
      (invented content only) in `tasks/img/0166_*` and the measured numbers before/after.

## Not in this task

Pulling the second end into turbine B; the export cable to the substation laid by the vessel; the park on the web
page (Web 3D lane, later – the owner decides when the demo goes on the site); the sea reaching the horizon (0154's
area – open point if needed); floating turbines.

## Design (worker, 16 Nov 2026 – written before the code)

**Files.** The maker writes a fourth model file `demo_park.step` (`layout.FILES["park"]`), imported as its own model
(root "DEMO WIND PARK") in the `park` stage, also in the small (PC check / GitHub) form. Its joints go into the joint
sheet's `machine_files["demo_park.step"]`, its numbers into the route sheet's `park`.

- `demo_model/occ.py`, `demo_model/turbine_parts.py`: moved from `tools/site_projects/` (unchanged output); the old
  modules there are aliases (`sys.modules[__name__] = …`), so the site's converter, its tests and sheets stay as they
  are. Two options with the site's values as defaults: `_jtubes(bell_z=…)` (the demo's J-tubes end over the rock, not
  in it) and `_scour(corridor=…)` (no boulder where the cable comes over the rock).
- `demo_model/turbine.py`: the IEA 15 MW public numbers (tower profile, hub, tilt, blade stations – also read by
  `iea15_standin.py`), tower + monopile, hub with spinner, three CLOSED blades with a round root whose leading edge
  leads a CLOCKWISE turn seen from the front, the nacelle and the foot from `turbine_parts`, yellow marine lights on the
  platform; `turbine(name, turn, phase)` = an Asm per turbine (shared Parts: one mesh per part in the app).
- `demo_model/substation.py`: jacket (4 legs, X braces, piles), topside with three decks, cladding, helideck,
  pedestal crane, cable deck with J-tubes, boat landing + ladder, deck lights, yellow corner lights.
- `demo_model/park.py`: the park in **park coordinates** (mm): origin = where the first end's CAD piece meets the
  seabed lay line (the end of the app's laid cable), +x along the lay line towards the vessel, z = 0 the waterline,
  seabed at -SEA_DEPTH. A 3 x 3 grid (1.2 km along the rows, 1.5 km between them), turbine A in the middle with its
  J-tube 1 towards +x, turbine B the next one along the row, 50 m to starboard of the lay line, the substation between
  the rows; every rotor faces the same wind (from -y: rotor planes along x, never over the vessel), each at its own
  phase. The CAD piece "CABLE (FIRST END)" runs from A's J-tube bell-mouth over the scour rock down to the seabed.
  Joints (root level): "Park: on to turbine B" (slide, moves the whole park), per turbine "WTG xx: Yaw" (rides on it)
  and "WTG xx: Rotor" (rides on the yaw, a motor, axis = downwind along the shaft: + = clockwise seen from the front).

**Motion scheme (scripts off).** The park root gets, in this order: a Child Of "FR park on the seabed" on
`paths_sea.BED` ("FR seabed motion": payout x lay direction + the waterline; the seabed's own driver – nothing new
drives anything), then vessel motion's own pair "FR vessel motion" + "FR vessel still" (the park marked **Still** with
the button's operator): the pair cancels exactly (still pivot = inverse of the vessel pivot), so the park is
BED @ basis at every frame, never heaving. The root's basis puts the park origin on the Power cable's `sea_start`
along -`sea_dir`. Shots 1–8b: the park joint at 0 – turbine A's cable piece meets the app's laid cable exactly.
**Per shot:** one frame before shot 9's cut a "Move joint" step of one frame takes "Park: on to turbine B" to the
distance that puts B abeam the stern, 45 m from where the second end is laid (the payout stands still in shots
9–12, so B stays there). A Build re-times it with the animation (no hand keys).

**Model size.** A 3 km park would become "the model's size" (floor, sea, vessel motion's hull, the clash check's
boxes): parts of a root marked `fr_scenery` are left out of `build.world_bounds` when the list holds other parts too
(build.py, additive; the demo marks the park).

**Stages / shots.** `park` after `sea`: import, place, Still mark + Child Of, joints, looks (groups "Demo: turbine
…"), lights (aviation red on the nacelles and marine yellow on the platforms / substation corners flash together:
one simple-expression driver each on the group material's emission). Shots: "Beside turbine A" after shot 2 (the
vessel 120 m off A, the cable from its J-tube; payout 0 there), "Park overview" after shot 8 (high, the vessel laying,
x 30 time-lapse), "Park at night" after shot 12 (a Weather & time step to Night shift, the lights flashing, turbine B
beside the vessel). The rotors run as Run motor steps through the whole animation (7.5 rpm).

**Tests.** `tests/test_demo_park_model.py` (the maker: one solid per part, names, joints, clockwise blades, the
cable piece clear of rock/pile/seabed); `tests/test_demo_project_park.py` (the made demo: feet on the seabed and
moving with it at every frame, never heaving; A's piece meets the laid cable in shots 1–8b; B near the second end;
rotors clockwise and facing one wind; the light drivers simple and flashing together; the bounds without the park).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026, branch `task/0166-demo-wind-park`. No subagents (one maker
and one set of stages; the independent checks are the tests below).

**What changed**
- `fresing_render/demo_model/`: new `turbine.py` (an invented turbine sized from the IEA 15 MW public numbers: monopile,
  tower with its door, spinner, three closed flat-faced blades with a round root, leading edge for a clockwise turn,
  bigger aviation lanterns, yellow marine lights), `substation.py` (jacket on piles, three decks, cladding, helideck,
  crane, 6 J-tubes, boat landing + ladder, floodlights), `park.py` (3 x 3 grid 1.2 / 1.5 km, A in the middle with its
  J-tube 1 along the lay line, B the next along A's row 42 m to starboard of the lay line, the substation between the
  rows, the CAD piece "CABLE FIRST END" from A's bell-mouth over the scour rock's ridge onto the seabed, 19 joints),
  `ParkParams` in `params.py`, `layout.FILES["park"] = demo_park.step` (+ its joints in the joint sheet's
  `machine_files`, its numbers in the route sheet's `park`). `occ.py` and `turbine_parts.py` moved here from
  `tools/site_projects/` (the old names are aliases, `sys.modules[__name__] = …`); two demo-only options in
  `turbine_parts` (J-tube bell-mouths over the rock and open, no boulders in J-tube 1's strip), the site's parts
  unchanged. `iea15_standin.py` reads the shared numbers and blade section from `turbine.py`.
- `blender/demo_park.py` (imported by `demo.py`): stages `park` (after `sea`: Weather & time on, import, place, Still
  mark + Child Of on the seabed's motion, joints, looks, light drivers), `park_cameras`, `park_shift` (the one-frame
  step of "Park: on to turbine B" right before shot 9), shots 2b "Beside turbine A", 8a "Park overview" (x 30),
  13 "Park at night" (Weather & time step to Night shift), `park_rotors` (Run motor, 7.5 rpm). The clash hook (below).
  `demo.py`: the park in `MODEL_KEYS`; the lay cable's laid length 120 → 60 m (`SEA_LAID_FIRST`: the vessel ~130 m
  off turbine A at the start; the second end keeps 120 m).
- `blender/build.py`: `PROP_SCENERY` – `world_bounds` leaves scenery objects out when other objects are given, so the
  park (3 km) is not "the model's size" (floor, sea, vessel motion's hull, cameras).
- Guide (demo section), `site/CREDITS.md` (the park's line), `tools/make_demo_cable_lay.py` docstring.

**Motion scheme** (Design above): root = seabed motion @ basis, then vessel motion's own Child Of pair cancels
(Still). Tested at every frame: the root is the seabed's motion @ basis to < 1 mm, no heave, roll or pitch, while the
hull heaves; the monopiles' feet stay 3 m in the seabed (every 25th frame + round the shift).

**Decisions**
- No new function the owner can see (demo content): no PC-check line, no tour stop, no function-list entry.
- **Clash check** (measured on GitHub, each half of the demo's check, test call): with the whole park in, 1,518 s
  and 0 real rows (was ~5 min); the nine rotors' blade tips move 4 m a frame, so the check looked between frames ten
  times as often (376,668 moments in one half), and the park's 879 m one-frame move gave one false row (shaft vs
  nacelle cover: a jump plus a turn is one screw step between two frames). With nacelles, rotors, the seven far
  turbines and the substation left out: 924 / 905 s – still 3 x, because turbines A and B are one rigid body with the
  park (a box 1.2 km long round the vessel) moving with the seabed up to 0.6 m a frame in the time-lapse. So the whole
  park is left out of the clash check (`demo_park._clash_hook`, demo projects only) and its clearances are tested
  directly: every vessel part against every turbine's platform (+2 m) and rotor disc, the lowered D against turbine
  B's scour rock (`test_the_park_keeps_clear_of_the_vessel_and_the_d`); the rotors' room in the maker.
- Weather & time is on in the demo from the park stage (from the project's own sky, the first switch-on), so the
  start scene keeps it and the night step leads from it.
- Marking (plain knowledge, not checked on web pages): offshore turbines carry red medium-intensity aviation lights on
  the nacelle, flashing in sync across the park (ICAO / national rules, ~20–60 flashes a minute); the transition
  pieces of the park's corner (significant peripheral) structures carry yellow lights flashing in sync, visible about
  5 nm (IALA O-139). The demo puts yellow lights on every platform for the picture.

**Tests**
- `tests/test_demo_park_model.py` (7, no Blender): one solid and a colour per part, layout, joints (one wind,
  rides-on, motors, own phases), blades lead a clockwise turn, round root, the cable piece clear of pile, rock and
  seabed (sinks 30 % as the app's), bends ≥ MBR, ends at the origin along +x, the laid cable clear of A's rock; demo
  options leave the site's parts alone; the rotor's room.
- `tests/test_demo_project_park.py` (8, on the made demo): on the seabed at every frame, feet, the first end meets
  the lay cable at every frame of shots 1–8a (< 1 mm), the second end 43 m from B's bell-mouth (planned ≤ 45 m),
  rotors clockwise facing one wind, lights flash together (driver read at two frames, simple expressions), the park
  not in the model's size, the shots and the shift step.
- `tests/test_demo_project.py`: stage list, length bound, joint count with the park.
- Site converter: `test_site_turbine*.py` + `test_site_projects.py` 72 passed with the moved code; the stand-in's
  converted sheets byte-identical before/after (sha256 25d46cbdf32f4114 offshore, 7f29f2bb51c8aec0 onshore).

**Measured** (small form = the PC check's / GitHub's, Blender as a module, 4-core web machine; before = main 0.2.126):

| | before | after |
| --- | --- | --- |
| Make demo (small) | 269 s | 406 s (write 76 → 80 s, park import 18 s, park stage 22 s, Build 117 → 221 s) |
| Animation | 3,831 frames | 4,481 frames (+26 s: shots 2b, 8a, 13) |
| Objects / parts | 2,291 / 1,416 | 3,132 / 2,178 |
| Triangles placed / unique (draft) | 0.88 M / 0.39 M | 1.75 M / 0.52 M (park normal quality: 1.35 M placed) |
| Playback (bpy, ~300 frames) | 33.7 ms/frame | 44.6 ms/frame |
| Project file | 192 MB | 221 MB |
| demo_park.step | – | 53 MB, written in 5.6 s |

First park build: the blades were spline lofts, 261 k triangles each (7 M placed): now flat-faced, ~3 k.

**Pictures** (invented content): `tasks/img/0166_beside_turbine_a.jpg`, `0166_park_overview.jpg`,
`0166_park_at_night.jpg` (640 px, 24 samples, Cycles CPU).

**Open points**
- The Sea's seabed is a 2 km square round the seabed motion: the outer rows' monopiles stand beyond it (under 30 m of
  water, not seen; for 0154 if a cut-away ever shows them). The sea surface (40 km) reaches every turbine.
- The Web 3D export of the demo would now hold the park (Web 3D lane, later).
- Rotor speed is in video time (7.5 rpm) also in the time-lapse shots.

**GitHub runs:** RUNS
