# 0116 – IEA 15 MW wind turbine for the site: onshore and offshore, detailed, moving

**Who:** worker · **Status:** waiting – starts when the owner's STEP is on the draft release `site-kit` (and no
take-in session of the Site kit lane is running) · **Branch:** `task/0116-wind-turbine` (or the web session's branch)
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

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
