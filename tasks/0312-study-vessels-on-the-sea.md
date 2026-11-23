# 0312 – Study + prototype (findings only): vessels on the sea – presets, driving and paths, anything floats and can be hit, waves that break on a beach, the camera under water

**Who:** worker · **Status:** running 23 Nov · **Branch:** `task/0312-study-vessels-on-the-sea` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner 21:14: "the same for the boats / ships as we told earlier for cars, driving
simulation but with ocean waves, and the path creation … this also adds water vessel interaction physics; waves that
break at the beach; the camera looks good under water (adjustable clarity as well); anything can float, and get hit;
different presets for different types of boats and ships, applied and adjusted by a user; a new preset can be saved by
user and organisation." Example he found: https://superhivemarket.com/products/ocean-physics-pro – "don't just copy it,
take inspiration, make it better and easier to use") · **Model:** Opus · effort High
**Area:** findings + design only; prototype in **new files** on the branch (e.g. `tools/vessels_proto/`). Reads the Sea
lane: `core/sea.py` (the spectrum sea, sum of travelling sines, deep water), `core/vessel_motion.py` /
`blender/vessel_motion.py` (0085), `core/vessel_work.py` / `blender/vessel_work.py` (0154: wake, bow wave, thruster
jets, ahead then DP), `blender/sea_view_cut.py` + 0081 / 0143 (seabed, clarity, cut-away, the 3D page under water),
`core/surroundings.py` (SEA, DECK, QUAY), `core/paths.py` / `camera_path.py` (curves), `people.py` (0157 walk paths).
Study **0306** (Vehicles) designs the drive / path recorder for cars – see point C. The page in `tasks/0312_page/`.
Not a code slot.

## The example (lead's notes from its page, 23 Nov – look yourself too; if the site is refused from the web machine, use these)

Ocean Physics Pro (Blender Procedural, GPL, Blender 5.2–5.3, ~$15): you **drive** boats and ships **with the keyboard**
on a real-time ocean; the hull cuts through the waves and leaves a **wake, foam and spray**; **nine ready-made vessels**
or your own model; **record the drive, bake it**, render in EEVEE or Cycles; "shore waves" and "under water" are listed
without details; built with Geometry Nodes. Its FAQ / documentation pages were not read. **Ideas only – no outside code**
(CLAUDE.md: the owner accepts no outside code).

## What to find out

A. **Where we stand**: what today's sea, vessel motion and water effects already do and what they cannot (shallow
   water, a shore, things floating that are not "the vessel", collisions, driving, more than one vessel).
B. **Vessel presets**: kinds a user of this app needs first (RIB, crew transfer vessel, tug, multicat / workboat, PSV,
   cable-lay vessel, a barge under tow, jack-up in transit, a yacht for scale …) – per kind: length, beam, draught,
   displacement, speed range, turning, how it pitches and rolls (0085's response), thrusters / DP, its wake class.
   Applying one to **the user's own model** (pick the hull; waterline from the model), adjusting it, **saving it as my /
   department / company preset** (0272's locations, `.frsetup`). Invented generic test vessels at real size for the
   prototype (the demo vessel's equipment stays private – CLAUDE.md section 6; the bare ship may be used).
C. **Driving and paths**: drive a vessel yourself on the live sea (keyboard; a game controller – 0306 checks whether
   Blender can read one), recorded → smoothed → an **editable path** like a drawn one; a path drawn on the water;
   speed along the path; manoeuvres (turn on the spot with thrusters, approach a monopile or quay and hold on DP).
   **The drive / path recorder is shared with 0306's cars**: if 0306 is done, build on its design; if not, write a
   section "What the shared drive / path tool must do for vessels" so the lead can merge the two designs.
D. **Water**: waves that feel the depth (shoaling, refraction round a shore), **waves that break on a beach** with
   foam (a hand-over with 0311's beach / terrain), spray where the hull slams, the vessel's own waves rocking other
   floating things; cost per frame; what stays exact with `core/sea.py`'s "one place" rule.
E. **Anything floats and can be hit**: buoyancy for any object (container, buoy, debris, a dropped part, a person in
   a life jacket?) from its size and how full / heavy it is, drift with wind and current; collisions – a vessel hits a
   floating object, an object hits a hull, two vessels touch; solved at Build (scripts-off safe, like the cables) or
   Blender's rigid bodies – which, and the cost.
F. **The camera under water**: crossing the surface (the water line across the picture), under-water colour and
   **adjustable clarity** (today's `sea_clarity`), light shafts, bubbles / particles; the same on the 3D page later.
G. **Users**: a sales person picks "Tug" + "Drive" or a ready path; an engineer sets the vessel up; an animator edits
   keys. Phases and build tasks with lanes (the Sea lane owns these files), models / efforts.
H. **Prototype** on the branch: a crew transfer vessel and a tug on a moderate sea – one driven, one on a drawn path –
   a container floating and hit, waves breaking on a beach, the camera dipping under; pictures + short clips; the page
   with pick ticks and a Copy line (`0312 pick: …`).

## Done when

- [ ] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 23 Nov 2026. Branch `task/0312-study-vessels-on-the-sea` (findings only,
never merged, every push `[skip ci]`). No subagents wrote code (one web reader was sent to the example's page: the site is
refused from the web machine – the lead's notes were used; no outside code).

**What changed:** only new files on the branch.
- `tools/vessels_proto/` – the prototype (not part of the app, nothing imports it): `hulls.py` (invented closed hulls at
  real size: monohull, catamaran, box), `presets.py` (9 vessel kinds + hydrostatics from the hull's mesh: waterline for a
  weight, LWL, BWL, block coefficient, KB, BM, the GM a roll period means), `drive.py` (3-way vessel model from a
  preset's few numbers, keyboard state, recorder, smoothing into path points + speed keys + crab keys on the app's own
  `core/camera_path`, a path follower with a speed planner), `floaters.py` (rigid bodies floating on `core/sea`'s waves:
  buoyancy per cell any way up, orbital-velocity drag, current, wind, hits with a vessel's waterline outline and between
  floaters), `shore.py` (depth-aware waves on a straight beach: dispersion, refraction, shoaling, breaking at 0.78 h,
  Gerstner lean; per-wave tables along the cross-shore distance), `render_scenes.py` (Cycles scenes: vessels, beach,
  under water with a lens dome), `measure_*.py`, `diagrams.py`, `render_all.sh`; `out/*.json` = the numbers below.
- `tasks/0312_page/` – the pick page (`index.html`, Copy line `0312 pick: …`) with 5 stills, 3 clips and 4 diagrams.

**Findings (A–G):**
- **A – today:** one vessel, at the scene's middle, never moving: heave / pitch / roll are sine curves (0085, scripts
  off); "ahead" moves the water and the seabed past it and draws a straight wake + Kelvin wedge in the water shader
  (0154). The sea is deep water only (ω² = gk); its fine mesh is round the model. Nothing else floats or drifts; nothing
  can be hit. No vessel paths or driving (camera paths 0087 and walk paths 0157 are the patterns to reuse). A camera under
  the app's sea sees no water: the sea is a surface, not a body (only the cut-away box and the web page have under-water
  looks). **A travelling vessel cannot use sine curves** (the waves it meets change with its speed and heading): its
  motion must be worked out at Build from the waves at its place, per frame (plane fit: ~0.1 ms a frame).
- **B – presets:** 9 kinds (RIB, CTV, ASD tug, multicat, PSV, cable-lay/construction = the public ship's class, barge
  under tow, jack-up in transit, yacht for scale) with length, beam, draught, displacement, top/cruise speed, time to
  speed, stopping distance, tactical diameter, spin rate, sideways speed, roll period and damping, propulsion and
  thrusters (0154's kinds), DP class, wake class. The hull is measured (vertical rays on a grid): waterline for the
  preset's weight in 0.8–1.8 s per invented hull in plain Python. **The roll period cannot come from CAD** (needs KG):
  it is a preset value; the IMO 2008 rule of thumb gave a believable KG for the tug and the PSV (88 / 94 % of the depth)
  and an impossible one (above the deck) for the catamaran, small boats, barge and jack-up – it only warns. Saving:
  0272's Locations get a kind "Vessels" (Mine / Department / Company, a `.json` per vessel, carried by `.frsetup`).
- **C – driving:** controls Up/Down = throttle lever (stays), Left/Right = helm while held (back to the middle when let
  go), Q/E = sideways, A/D = spin, Space = stop and hold, Shift = fine. Model: 0.1 ms per simulated second. 80 s of a CTV
  driven → 2,401 samples → **19 path points, 15 speed keys, 6 crab keys**, at most 0.82 m (mean 0.17 m) off, 0.6 s to
  smooth. A drawn S-bend followed: tug 199 s, cross-track mean 4.4 / max 16.1 m; CTV at 20 kn 113 s, 7.4 / 26.4 m; PSV
  296 s, 21.1 / 61.6 m and slowed to 2.5 kn (54 % of the bend is tighter than its 149 m turning radius). The app must draw
  the line the vessel will really drive next to the drawn one. Push-on at a boat landing: the CTV's bow (sea only, no
  vessel response) moves 0.40 m up and down at Bft 3 (Hs 0.43), 1.46 m at Bft 4 (Hs 1.0), 2.70 m at Bft 5 (Hs 1.67).
  **0306 has not started:** what the shared drive / path tool must do for vessels is below.
- **D – water:** depth-aware waves keep `core/sea.py`'s one-place rule – every wave stays one sine, with two tables per
  wave along the cross-shore distance (phase so far, amplitude factor; 10 ms to make, 512 samples). Energy flux of each
  wave stays constant outside the surf zone (by construction: 1e-15). Bft 3: surf zone 24 m, breaking in 0.8 m of water;
  Bft 5: 93 m, 3.1 m. NumPy surface: 75–97 ns per point per wave (Geometry Nodes cost not measured: the expectation is
  about twice today's per-point work, two table reads per wave). Straight parallel depth lines only; 0311's terrain or a
  curved coast needs wave rays traced over the depth map once (not tried). The vessel's own Kelvin waves rock floaters
  (added to the sea height at the floater's points).
- **E – floating and hits:** own solver at Build, keyed (scripts off, same Build = same keys): draughts within 2 % of the
  formula for an empty / 10 t container, a pallet and a person (30 t container: 2.21 vs 2.13 m, still bobbing after
  40 s; 40 t sinks). Tug at 7 kn: container (10 t, cargo on the floor) glanced aside at 0.6 m/s and turned 2 rad; a pallet
  caught by the bow and pushed. 0.58 ms per floater per 1/60 s step (1.2 ms per floater per 30 fps frame); batched over
  all floaters it should be much faster (expected). Blender rigid bodies: no buoyancy, and Python forces cannot reach
  Bullet's sub-steps – not used. A part dropped onto a deck and then into the sea would need contacts with any mesh
  (later).
- **F – under water:** the prototype's water is a closed body (glass surface IOR 1.333 + absorption/scatter by
  `core/sea.absorption(clarity)`); shadow rays pass the surface (else Cycles leaves everything under water black: no
  caustics). **The split picture** works with a lens dome: a 0.35 m sphere of air round the lens, cut out of the water
  body (Boolean), so rays going down enter the water and rays going up stay in air – the waterline across the picture,
  curved like a real dome port. Clarity 4 / 12 / 30 m differ clearly (the pile under water only at 30 m). The sky's sun
  disc showed through the dome as a bright spot (sun turned away in the prototype). Light shafts, moving light on the
  seabed, bubbles: not done.
- **G – users:** sales (Add vessel → kind → Drive or a ready route), engineer (hull, waterline, thrusters, save company
  vessel), animator (drag path points, edit speed / crab keys). Build tasks below.

**What the shared drive / path tool must do for vessels** (for the lead to merge with 0306's cars):
1. One recorder for anything driven: samples (t, x, y, heading, speed, controls) at 30 Hz; the driven thing's own model
   gives the motion (a car: wheels on the ground; a vessel: the 3-way model); the recorder does not care which.
2. Controls mapped per kind: a vessel's throttle is a **lever that stays** (not a pedal), the helm returns to the middle,
   plus two extra axes (sideways, spin) a car does not have; Space = stop and hold.
3. Smoothing into the same editable form: path points (RDP + the app's Catmull-Rom of `core/camera_path`), speed keys
   along the path, and a third channel a car does not need – **heading off the path** (crab / sideways / spin).
4. Following a drawn path through the same model with a speed planner: slows for bends tighter than the turning circle,
   spins where it can, and **shows the real line** beside the drawn one with a note where it cannot keep up.
5. Re-drive a stretch (record over part of an existing path, joined smoothly).
6. Works on uneven ground (car) and on moving water (vessel: the waves move it up and down, they do not steer it).
7. Live: the drive runs in a modal operator on a timer (the model is cheap: 0.1 ms per second); the view's frame rate is
   the limit. A game controller: Blender reads none; on Windows an Xbox-type pad can be read with ctypes from
   `xinput1_4.dll` (part of Windows) – 0306 to check on the owner's PC (no controller on the web machine).

**Build tasks (the page's ticks; ★ recommended):**
| Tick | Task | Lane | Model · effort | After |
| --- | --- | --- | --- | --- |
| A ★ | Vessel kinds on your own hull (Add vessel, waterline measured, adjust, save Mine / Department / Company) | Sea (new files + Locations kind) | Opus · Medium | – |
| B ★ | Vessels that really travel, several at once (motion at Build from the waves met, wake + Kelvin along the curve, the fine sea follows the camera) | Sea | Opus · High | A |
| C ★ | Drive it yourself + editable path + follow a drawn path (one tool with 0306) | Sea + Vehicles | Opus · High | B, 0306's design |
| D | Ready manoeuvres: push on at a turbine (slip warning), DP hold, spin, tow a barge (cable sag maths), pass by | Sea | Opus · Medium | C |
| E ★ | Anything floats and can be hit (Float on any part or prop; drift, waves, vessels' waves, hits; keyed at Build) | Sea | Opus · High | B |
| F ★ | Waves that break on a beach (straight beach, wet sand, run-up; then 0311's terrain) | Sea | Opus · High | 0311's beach |
| G ★ | The camera under water (water body round the camera, lens dome split shot, clarity, light shafts, specks) | Sea | Opus · High | – |
| H | Spray where the hull slams | Sea | Opus · Medium | B |
| I | Game controller on Windows (XInput) | Vehicles | Opus · Medium | 0306 |
| J | On the web page: travelling vessels, floaters, beach | Web 3D | – | B, E, F |

All of A–H touch the sea files (`surroundings.py`, `vessel_motion.py`, `vessel_work.py`): one at a time in the Sea lane;
G does not depend on B–F and could go first.

**Tested and measured** (web machine, 4 cores, no graphics card; invented models only; Blender 5.2.3 as a Python module
for the pictures): numbers above, from `tools/vessels_proto/out/*.json` (`measure_presets.py`, `measure_drive.py`,
`measure_floaters.py`, `measure_shore.py`, `diagrams.py`). Cycles on the processor, 960 × 540, 64 samples: vessels
still 23.5 s, beach 17.0 s, under water 30–33 s each. Clips at 640 × 360, 32 samples, 12 frames a second: see the
page (times in `render_all.sh`'s log). Nothing was run on a graphics card; the live driving frame rate is unmeasured.

**Open points / follow-up tasks:**
- The floating container rolls up to ±29° on Bft 4: the roll damping of a box is not calibrated (prototype constant).
- The prototype's own sea grid has a visible edge where the far plane starts; the app's sea rings would not.
- Light shafts, moving light on the seabed, spray, run-up on the sand, bubbles: designed, not tried.
- The IMO roll rule does not suit catamarans, barges, jack-ups and small craft: the preset's roll period is the value.
- Vessel motion of a travelling vessel was a plane fit under the hull (no roll resonance): B uses 0085's oscillator per
  frame instead.
- The example product (Ocean Physics Pro) could not be opened from the web machine; only the lead's notes were used.
