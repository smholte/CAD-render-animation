# 0116 – IEA 15 MW wind turbine for the site: onshore and offshore, detailed, moving

**Who:** worker · **Status:** done (0.2.93, 14 Nov 2026) · **Branch:** `task/0116-wind-turbine` (or the web session's branch)
**Started by:** lead chat, 13 Nov 2026 (owner's picks from study 0113, 22:07; owner's wishes 22:54)
**Area (Site kit lane):** new `tools/site_projects/iea15*.py` (+ an invented-parts maker, e.g.
`tools/site_projects/turbine_parts.py`), `tools/make_site_projects.py` (additive: a new model id),
`site/render_kit/models.ini` + `site/render_kit/projects/iea15_*.json` (new sections/sheets), new
`tests/test_site_turbine*.py`; `site/CREDITS.md`, `site/media/media.json` additively. **Looks lane (free)
additively** if a look is missing (point 4): `fresing_render/core/materials_lib.py`, the node building in
`fresing_render/blender/materials.py`. **Do not edit:** 0081's files (`core/sea.py`, the sea/seabed part of
`blender/surroundings.py`, `flex*`, `paths*`, `demo*`), 0114's (`house_*`, `lightbake.py`), 0111's picker files in
`site/` (page, picker, `tools/build_site.py` beyond what `--take` already does).
**Model:** **Opus · effort High** (subagents allowed, CLAUDE.md section 2) · **Place:** Claude Code on the web,
environment "CAD-render-animation"

## Goal

A real-looking 15 MW wind turbine in the site's gallery, in two versions – **onshore** and **offshore on a
monopile** – with paint, doors, platforms and the small parts a real one has, a turning rotor, yaw and blade pitch,
made into app projects by script so the owner's render kit renders stills and a clip on his PC. Later 0111's picker
can show it as a 3D model (keep the project maker callable from Python, as for Thor).

## Background

- **Source:** the IEA 15 MW reference turbine (github.com/IEAWindSystems/IEA-15-240-RWT, **Apache-2.0**). The
  owner opened its SolidWorks assembly (`CAD/deprecated/IEA-15-240-RWT_Solidworks.zip`, top `15MW.SLDASM`) in
  **Fusion** (he has no Inventor at the moment) and exports **one STEP**, which he attaches to the draft release
  `site-kit` (`gh release download site-kit --pattern "*.st*p"`; a draft is visible with the session's token). If it
  is not there yet, stop and tell the owner – do not build from other files.
- **What is in it** (owner's Fusion screenshots, 13 Nov): tower (sections visible as lines), the three pre-bent blades
  (beige in Fusion), the hub/spinner, the main bearing/flange, the generator and the **bedplate** – the curved cast
  frame on the tower top. **There is no nacelle cover**: the drivetrain is bare. No monopile, no transition piece, no
  door. The SolidWorks zip also has the drivetrain parts in `Generator/` (bedplate, rotor/stator halves, bearings,
  shaft, yaw bearing) – the STEP should hold them; check.
- **Also in the IEA repository** (same licence): the monopile and tower as OpenSCAD/STL (`CAD/OpenSCAD/`), the
  turbine's documentation (report: hub height, tilt, overhang, cone, rotor speed, monopile diameter/depth, water
  depth). **Take sizes from there, never guessed**, and write each number's source in the sheet's notes.
- **Owner's reference pictures** (13 Nov; described here, never committed):
  1. Close to an offshore turbine at sea level: a **yellow transition piece** (TP) on the monopile; on it a ring-shaped
     **working platform** with railings, a small **davit crane** on the platform's edge, a cabinet/container, a
     painted **heading marking** ("S 180°" with a short line) on the yellow TP; a vertical **boat-landing** ladder
     with two side tubes reaching down into the water; a light grey/white tower above the TP. A second turbine on the
     horizon (tower, nacelle with a small red mark, three blades).
  2. From a small boat looking up: white tower and blades, nacelle with equipment on its roof at the back, yellow TP
     with platform, railings, stairs/ladder, davit and a box-shaped unit on the platform; open sea, clouds.
  3. A schematic: hub, blades, nacelle, tower, a yellow foundation part above the water, the monopile going into the
     seabed; minimum tip clearance above the water.
- **App functions to use, never copy:** importer, Looks/materials, decals (`core/decal_art.py`: text, warning signs),
  joints (batch, 0093), poses, product video (0101), weather presets (0109), surroundings + sea (0016, 0109; 0081's
  seabed/water depth/cut-away if it is on `main` when you start), vessel motion **off** (a monopile does not move),
  clash check (0065/0110). The site's projects and kit: 0112 (`tools/site_projects/`, `projects.py`, `models.ini`,
  `stepout.py` for nested sub-assemblies, the `site-kit` workflow).

## Owner's choices (13 Nov)

- Turbine on the site: yes. **Two versions: onshore and offshore (monopile).** **Floating version: skip.**
- "Materials and textures, doors and such should also be added" – see Scope 2–4.
- **No brand logos or real makers' names** anywhere (an invented turbine ID and markings are fine).
- Credit IEA as the source and say what Fresing added (Apache-2.0 allows changes; state them).

## Scope

1. **Read and check the STEP.** Import with the app; list the parts; check scale (hub height, rotor diameter against
   the IEA report within 1 %), up axis, where the rotor axis lies (tilt, overhang). Blades' colour from Fusion is
   ignored (Looks below). Parts that are pure simulation aids (e.g. "fake bearing", springs for stiffness models):
   hide for good (the app's "excluded") and list them in the sheet's notes.
2. **Invented parts, made by script** (OCP like `fresing_render/demo_model/geom.py`; **every part one solid** –
   CLAUDE.md section 8, colours otherwise lost), written as one extra STEP or merged into the model's STEP via
   `stepout.py`, sized from the IEA numbers and fitted to the real geometry (no part through another: clash check):
   - **Both versions:** **nacelle cover** of our own design (rounded box over bedplate and generator, a cooler/roof
     edge at the back, a seam line; clearance to everything inside); **roof hatch**, **helicopter-hoist platform**
     with railings on the roof's back half, **aviation lights** (two on the roof), **wind sensors** (small mast with
     anemometer cup and vane) at the back; **tower door** with frame, hinges, handle; outside **steps/landing** to
     it; **tower flanges** where the sections meet (thin rings); a **yaw ring** line between tower and nacelle.
   - **Onshore:** a **concrete foundation** pedestal + buried slab edge showing in a gravel/grass ground; the door
     stair from the ground.
   - **Offshore (monopile):** the **monopile** (diameter and depth from IEA; water depth from IEA), a **transition
     piece** with its flange to the tower; a **working platform** (grating floor, railings with toe boards, a gate),
     a **davit crane** (slewing post + jib + hook block), a **cabinet**; an **access ladder** with rest platforms and
     cage, a **boat landing** (two vertical bumper tubes + ladder between them, rubber fenders), **2–3 J-tubes** (the
     pipes the export/array cables enter by, running down the monopile to a bell-mouth near the seabed – later the
     cable-lay demo's cable may run into one); **scour protection** (rock layer round the pile) if 0081's seabed is on
     `main`, else leave it and say so.
   - Details in proportion, not hundreds of bolts: the site shows it from metres away. Keep the invented parts under
     ~150 k triangles at Normal facets in total (measure; the IEA model's own count in the report).
3. **Signs and markings with decals:** an invented turbine ID (e.g. "WTG A07") on the TP and on the tower door side,
   the **heading markings** (S 180° style) on the TP, a "no unauthorised access" safety sign at the door, a load sign
   on the davit. Plain fonts from `decal_art`; no real logos.
4. **Looks** (owner: "materials and textures") – use the app's library first: tower and nacelle **light grey (RAL
   7035) marine paint**, blades **white matt** (a slightly worn **leading edge** if it can be done with the existing
   looks or a second group on a thin leading-edge strip), TP **traffic yellow (RAL 1023) marine paint**, railings and
   ladders **galvanised**, grating see-through (`wire_mesh` or a grating look), fenders black rubber, concrete for
   onshore. What the library lacks and the owner asked for: **concrete**, **marine growth / waterline band** (dark
   green-brown below about +1 m, slime and rust streaks in the splash zone), **light weathering streaks** under
   flanges and the platform. Add such a look **additively in the Looks lane** (`materials_lib.py` + its node
   building), procedural (no image files), with: its tooltip, guide line, a **test-tour stop** and a **PC-check line**
   (CLAUDE.md section 6) – these are app changes, so this task ends with a **version** (take the number last).
5. **Motion** (joint sheet `projects/iea15_*.json`, built with the app's functions as 0112's `projects.py` does):
   - **Rotor** turns about its real shaft axis (tilt from the geometry, checked against the report);
     **nacelle yaw** about the tower axis; **blade pitch** ×3 about each blade's own pitch axis (read from round
     faces at the blade root **and** the hub – CLAUDE.md section 8, 0112's lesson); offshore: **davit slew**; both:
     **tower door** opens.
   - Poses: "Running" (rotor at rated speed, from the report), "Feathered / parked" (blades at 90°), "Door open".
   - A **seamless loop** (first frame = last): rotor at rated speed for a whole number of thirds of a turn, the
     nacelle yawing a few degrees and back. Clash check of the loop: **0 rows** (blade tips clear the tower with the
     pre-bend and tilt – this is a real check, not a formality).
6. **Kit:** two sections in `models.ini` – `iea15_offshore` (sea surroundings, a weather preset such as a clear or
   hazy day at sea; stills: a low view from a work boat close to the TP as in picture 2, a wide view with the full
   turbine; clip: product video or the loop) and `iea15_onshore` (outdoor ground, one still, optional turntable).
   Kit time estimate updated. Clips ≤ ~5 MB after `--take`, posters as 0112.
7. **Credits:** `site/CREDITS.md` + `media.json`: IEA Wind TCP Task 37 reference turbine (names as in its README),
   Apache-2.0 with a link and the licence's NOTICE requirements followed; "nacelle cover, doors, platforms, monopile
   details, looks and motion added by Fresing". The STEP files stay out of the repository (the kit carries them, as
   Thor's).

## Done when

- [ ] Both projects build by script from the owner's STEP + the invented parts; sizes match the IEA report (tests,
      numbers with their source); every invented part one solid; triangle counts in the report
- [ ] Joints on the real axes (rotor, yaw, 3 × pitch, davit, door), checked from both sides; poses; the loop closes;
      **clash check 0 rows** for both versions
- [ ] Decals and looks as in Scope 3–4; any new look with tooltip, guide line, tour stop, PC-check line, its test
- [ ] Kit sections, time estimate, credits; `site-kit` workflow rebuilds the kit on `main` with the turbine in it
- [ ] Tests added; full suite green on GitHub; report filled in with a few small preview stills described in words
      (renders of the IEA model may be committed only as the site's own pictures later, through `--take`)
- [ ] Version + CHANGELOG only if Scope 4 added a look (app change); otherwise no version, say so

## Not in this task

The floating version (owner: skip). The "Turn it yourself" picker (0111). Mesh import. The cable-lay demo's cable into
a J-tube (a later Flex/Demo task). Rendering the final pictures (owner's PC with the kit). The demo vessel next to the
turbine (owner decides later).

---

## Design (worker, 13 Nov – the brief of the subagents)

**What the owner's STEP holds** (`15MW.step`, 81 MB, read with `tools/site_projects/iea15_source.py`): `tower` = ONE
solid, monopile + tower (pile tip −75 m, top +144.582 m); `assem_rotor` = bedplate (3 solids), newyaw_bearing,
misc_equipment, newNosePiece, stator, flange_2 ×2, newRotor (outer generator rotor, r 5.26 m), shaft, Hub (2 solids),
SRB_mock_bearing + TDO_mock_bearing (plain stand-in rings: hidden); 3 blades = an open SHELL each (117 m) + a 2 m root
disc (modelling aid: hidden). Reference numbers: IEA-15-240-RWT **v1.0** (commit 630f7cb, the version the SolidWorks
model is drawn from), table `IEA` in `iea15_source.py`, each with its file. Measured: hub height 150.49 m (150),
rotor Ø 240.001 m (240), tilt 6.000°, overhang 11.21 m (11.01), yaw bearing 0.38 m, **precone 0° in the CAD** (IEA 4°).

**Turbine frame "T"** (mm): tower axis = z (x = y = 0), MSL z = 0, rotor upwind towards **−y** (the app's front
views look at it), +y = north (heading marks: −y = S 180°, +x = E 90°). Offshore = T. **Onshore = T shifted down
14 000 mm**: ground z = 0, tower base on a 1.0 m concrete pedestal (z +1000), hub 136.5 m above ground.
Measured axes (`~/iea/work/measure.json`): yaw = z axis; rotor through the hub centre (0, −11210.3, 150488.1)
along (0, −0.99452, 0.10453); pitch i = blade i's own z axis (its point/direction in `measure.json["blades"]`, the
hub's ring face centred on it at 0.0 mm / 0.0°). Parts in T: `~/iea/work/src_T/*.brep`.

**Bodies** (nested sub-assemblies of the written STEP, `stepout.py`): TOWER (fixed: tower, monopile, foundation,
TP, platform, ladders, boat landing, J-tubes, door frame, steps, flanges, yaw bearing) · NACELLE (yaw: bedplate, nose,
stator, flanges, misc, the cover and everything on it) · ROTOR in NACELLE (shaft, generator rotor, hub) · BLADE 1–3
in ROTOR (pitch) · DOOR in TOWER · DAVIT in TOWER (offshore). The tower solid is cut at z +15 m (tower | monopile) and,
offshore, at −30 m (the 45 m below the seabed is a part of its own, hidden: no seabed on `main` until 0081).

**Files and owners:**

| File | Owner | What |
| --- | --- | --- |
| `tools/site_projects/occ.py`, `iea15_source.py` | worker (done) | OCP helpers; read + frame + measure |
| `tools/site_projects/turbine_parts.py` + `tests/test_site_turbine_parts.py` | subagent **B** | the invented parts |
| `tools/site_projects/iea15.py` | worker | convert: source parts + invented parts → `iea15_<variant>.step` + sheet |
| `site/render_kit/projects.py`, `make_site_pictures.py`, `models.ini`, `tools/make_site_projects.py`, `fetch.py`, workflow, CREDITS, media.json | worker | decals, cameras, scene settings, loop period in the sheet; kit |
| `fresing_render/core/materials_lib.py`, `fresing_render/blender/materials.py` (+ a new `blender/marine_looks.py` if it helps), `tests/test_marine_looks.py` | subagent **A** | the new looks |
| tour stop, PC-check line, guide, CHANGELOG, version, TASKS.md | worker | |

**Interface of `turbine_parts.py`** (B; no Blender, OCP only, mm, T frame of the variant):

```python
VARIANTS = ("offshore", "onshore")
@dataclass
class Part:
    name: str      # unique, UPPER CASE, starts with one of PREFIXES below (the kit colours parts by name)
    body: str      # "TOWER", "NACELLE", "DOOR", "DAVIT"
    shape: object  # ONE valid solid (occ.one_solid), placed in the frame at joint values 0
def make(fit: dict, variant: str) -> list[Part]
def door_cut(fit: dict, variant: str)      # the solid the converter cuts out of the tower (the door opening)
def joints(fit: dict, variant: str) -> list[dict]   # {"name": "Door"|"Davit", "kind": "ROTATE", "body": ...,
                                                    #  "point": [mm], "direction": [unit], "limits": [deg, deg]}
def anchors(fit: dict, variant: str) -> list[dict]  # decals: {"part": name, "point": [mm, on its surface],
       # "normal": [unit, outward], "up": [unit], "kind": "TEXT"|"STICKER", "text"|"sticker", "width_mm"}
def cameras(fit: dict, variant: str) -> list[dict]  # {"name", "eye": [mm], "target": [mm], "lens": mm}
```

`fit` = `measure.json` + `"variant"`, `"z_shift"` (0 / −14000, applied to every measured z), `"tower_profile"` =
[(z, outer r)] breakpoints of the tower in this variant's frame (linear between them), `"msl_z"`, `"seabed_z"`,
`"tower_base_z"`. **Name prefixes → looks** (models.ini `colours`): `NACELLE` (cover, hatch, cooler: marine paint RAL
7035), `HELI` (hoist platform: RAL 7035 deck, its rails `RAIL`), `LIGHT` (aviation lights: red glow), `SENSOR`
(wind sensors: grey plastic), `TOWER FLANGE`, `YAW SEAL` (dark rubber), `DOOR` (leaf, frame: RAL 7035), `HANDLE`,
`STEP` (stairs and landings: galvanised), `RAIL` (railings, toe boards, cage: galvanised), `GRATING` (see-through),
`TP` (transition piece: RAL 1023 marine paint), `PLATFORM BEAM`, `DAVIT` (RAL 1023), `HOOK` (dark), `CABINET` (RAL
7035), `LADDER` (galvanised), `BOAT LANDING` (RAL 1023), `FENDER` (black rubber), `J-TUBE` (RAL 1023 above, marine
growth below), `CLAMP`, `CONCRETE` (onshore pedestal, slab edge), `GRAVEL` (onshore apron).

**Layout** (B decides the numbers within these): offshore TP sleeve over the pile from about +3.5 m to the tower
base at +15 m (yellow), working platform deck at +15 m round the TP (to r ≈ 8.5 m) with railings + toe boards and a
gate, brackets under it; door in the tower above the deck (a step or two up), facing the boat landing side; boat
landing + ladder at azimuth ≈ 135° (front right: the app's LOW/ISO cameras see it), ladder up through the deck with
a cage and a rest platform; davit near it on the deck edge; cabinet; 2–3 J-tubes down to a bell-mouth just above the
seabed (−30 m). Onshore: pedestal, slab edge, gravel apron, door stair from the ground. Nacelle cover over the
bedplate behind the generator (front face clear of the turning generator rotor's back face at y −4430 by ≥ 100 mm),
hatch, heli-hoist platform on the back half of the roof, two aviation lights, wind-sensor mast at the back, cooler at
the back edge, a seam. Clearances: nothing fixed in the sweep of the blades, the turning generator, the door leaf or
the davit within their limits (the clash check must give 0 rows). Under ~150 k triangles in total at the importer's
Normal facets (`step_reader.FACETS`).

**New looks (A):** `concrete`, `paint_marine_growth` (marine paint, needs a colour, with marine growth below the
waterline and slime / rust streaks in the splash zone above it), `paint_marine_streaks` (marine paint with light
run-down weathering streaks). Procedural, Cycles + EEVEE, no image files, a test of each look's key and its nodes.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, branch `claude/exciting-faraday-mkxfqz`, 13–14 Nov 2026.

**What changed:**
- **Converter** (`tools/site_projects/iea15_source.py`, `iea15.py`, `occ.py`): reads the owner's `15MW.step`, moves it
  into the turbine frame (tower axis z, MSL z 0, rotor upwind −y; onshore 14 m lower: ground z 0), cuts the one tower
  solid at +15 m (tower | monopile) and −30 m (pile below the seabed: hidden), cuts the door opening, writes
  `iea15_offshore.step` (25 MB) / `iea15_onshore.step` (9 MB) with the bodies nested (TURBINE FIXED > NACELLE YAW >
  ROTOR TURNING > BLADE n PITCH, DOOR SWING, DAVIT SLEW) and the sheets `site/render_kit/projects/iea15_*.json`.
  STEP header says it is a modified copy (Apache-2.0 4b). Numbers from IEA-15-240-RWT **v1.0** (commit 630f7cb; the
  version the SolidWorks model is drawn from), each with its file, in the sheet.
- **Three fixes to the source the app needed** (all in the sheet's notes): (1) the blade skin is one B-spline of
  4,343 × 203 control points that OpenCascade meshes into 31–79 triangles – the blades were invisible; it is rebuilt
  from 121 × 161 sampled points (largest deviation 2 mm), closed (trailing edge ≤ 11.5 mm open in the CAD) and
  capped as ONE solid (an open skin has no inside: the clash check gave false 80 mm hub rows). (2) The CAD's blades
  are drawn for an anticlockwise rotor (leading edge measured at 30/60/90 m); mirrored in their own plane so the rotor
  turns clockwise like the IEA's. (3) The root is 95 mm out of round and 62 mm off its pitch axis and ran 160 mm into
  the hub's round ring when pitching: made round (r 2540) and blended over 4 m (the IEA's root is circular).
  Hidden: mock main bearings ×2, blade root discs ×3, a 0.2 m ball at the hub centre, pile below the seabed.
- **Invented parts** (`tools/site_projects/turbine_parts.py`, subagent B): both – nacelle cover (seam, cooler), hatch,
  heli-hoist platform + railings, 2 aviation lights, wind sensors, door (frame, leaf, handle), 3 tower flanges, yaw
  seal; offshore – TP sleeve +3.5…+15 m, grating deck, 8 beams, railings with toe boards and gate, davit (pedestal,
  slewing jib, hook), cabinet, ladder with cage and rest platform, boat landing + 4 fenders, 3 J-tubes + 12 clamps;
  onshore – concrete pedestal, slab edge, gravel apron, door stair + landing with railings. Every part one valid
  solid. Triangles at Normal: offshore 113,636 (67 parts), onshore 47,334 (26 parts); the IEA model's own:
  blades 762 k each at Normal (closed light blade), the rest < 50 k.
- **Motion** (sheet): Yaw (tower axis), Rotor (shaft axis, positive = clockwise from the front), Pitch 1–3 (blade z
  axes, positive = leading edge into the wind, −5…95°), Door (0…100°), Davit (±90°). Poses Running (a blade straight
  up), Feathered, Door open. Loop "Turbine running": 10.58 s, the rotor 4/3 turn at 7.56 rpm, nacelle yaws 4° and back;
  closes (the sheet's `periods`: 120° for the rotor). Decals: WTG A07 (TP, tower), N/E/S/W headings on the TP,
  warning sticker + NO UNAUTHORISED ACCESS on the door, SWL 1 t + hanging-load sticker on the davit. Cameras: Work boat,
  Whole turbine; From the field, At the door.
- **Kit** (`projects.py`, `make_site_pictures.py`, `make_site_projects.py`, `fetch.py`, `models.ini`, README,
  `site-kit.yml`): sheet `scene` (water level 30 m / floor gap −0.4 m), `decals`, `cameras` (models.ini `views` may
  name them), JOINT steps side by side (LINEAR), loop `periods`, a `check_animation` (every joint through both limits)
  clash-checked only by `make_site_projects.py --project`; parts found by instance name too (the three blades share one
  shape). The owner's STEP is fetched from the draft release (`FRESING_IEA15_STEP`, cache, or `GITHUB_TOKEN`; the
  workflow passes its token). Sections `[iea15_offshore]` (SEA, Clear day, Work boat + Whole turbine, the loop as clip)
  and `[iea15_onshore]` (SKY, Clear day, From the field + At the door, no clip), import quality Normal. Kit zip grows by
  about 8 MB (the two STEPs zipped); README: about 4 h.
- **Looks** (app, subagent A): `concrete`, `paint_marine_growth` (growth below the waterline, splash zone with rust
  streaks; the waterline = scene property `fr_waterline_z`, synced from the surroundings' sea, default world z 0),
  `paint_marine_streaks`; `blender/marine_looks.py`. Guide line (3 Looks), PC-check line `looks.marine`, tour stop
  "Marine growth, streaks, concrete" (set `marine`).
- **Clash check** (app): rigid bodies far from the origin – the onshore rotor's shaft and generator (136 m up) differed
  by 3e-5 m in float32 and were checked against each other (1.5 mm false rows). `core/clash.rigid_groups(reach=)`
  allows 4 float32 steps of the distance from the origin; test in `test_clash_core.py`. Check time on the onshore
  turbine 116 → 74 s.
- **Credits:** `site/CREDITS.md` (row + "what Fresing changed" section), `media.json` models entries (not shown until
  pictures exist). No maker's names or logos (tested).

**Tested and measured** (4-core web machine, the owner's STEP):
- Sizes vs IEA v1.0: hub height 150.49 m (150, +0.3 %), rotor Ø 240.001 m (240), tilt 6.000°, tower top 144.582 m
  (144.495), blade 117.0 m, pre-bend 4.00 m, overhang 11.21 m (11.01, +1.8 %), **precone 0° in the CAD** (IEA 4°: kept
  as drawn, said in the sheet). Every axis from round faces on both sides: yaw 0.000 mm, rotor 0.000 mm / 0.0000°,
  hub rings centred on the pitch axes 0.000 mm.
- App projects (draft import 8 s): axis error 0.0° / 0.009 mm; loop gap 0; **clash rows 0** for the loop (118 s) and
  0 for the check animation (pitch −5…95, door 0…100, davit ±90, yaw ±10; 457 s offshore, 588 s onshore), both versions.
- Kit `--small` run of both models: 4 pictures + the clip, 0 problems. Larger previews (800 px, Cycles draft, not
  committed): offshore from the work boat – the yellow TP from below, the grating platform with railings and toe
  boards, the davit, the ladder with its cage, a blade edge-on overhead; whole turbine – three white blades with one
  straight up on the grey tower, the yellow TP at the waterline, open sea; on land – the whole turbine from the field;
  at the door – the door in the tower foot with a galvanised stair and landing on the round concrete foundation.
- Tests: `test_site_turbine.py` (sheets vs IEA, joints, loop, decals, kit, credits; with the STEP: shipped sheets =
  fresh conversion), `test_site_turbine_parts.py` (27; 19 without the owner's model: every part one valid solid,
  names, budget, clearances against the source parts), `test_site_turbine_standin.py` (31, subagent C: a 0.5 MB
  stand-in STEP with the source's structure so GitHub tests the converter + an app build with 0 clash rows),
  `test_marine_looks.py` (15), `test_clash_core.py` (+1), tour and PC-check lines run locally. 137 tests of these
  files passed locally before the merge of `main`.
- Subagents: A (looks, its own module + tests), B (invented parts + tests), C (independent tester: stand-in model and
  converter tests; found 4 real faults – ground 0.4 m low on land, the check animation missing half the davit and the
  pitch limits, two parts named NOSE FLANGE 1, the onshore fit's hub height – all fixed; and the false HUB × BLADE rows
  that led to the closed blades). Re-done after merging: B's cameras (onshore field view 70 m → 360 m, plus "At the
  door"), C's floor test value.

**Open points / follow-up tasks:**
- **Scour protection** and showing the 45 m of pile in the ground: 0081's seabed reached `main` while this task ran
  (it was not there at the start, as the brief asked): a small follow-up (rock layer, the pile below the seabed shown).
- The blades' worn leading edge was not done (no look or strip for it).
- The owner renders both with the next kit run (the site-kit workflow put them in the kit); then the take-in session.
- The check animation's clash check takes 8–10 min on the 4-core machine (only `make_site_projects.py --project`, not
  the kit).

