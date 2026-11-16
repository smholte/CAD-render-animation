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

---

## Report (filled in by the chat that did the task)

**Chat / date:**
