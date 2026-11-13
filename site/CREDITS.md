# Credits for the landing page

The pictures and videos on https://smholte.github.io/CAD-render-animation/ show these models, rendered with Fresing
Render. The models themselves are **not** in this repository – only the pictures. Every line here is also on the page
(`site/media/media.json` → "Credits"); `tests/test_site.py` checks both.

## Models on the page now

- Milling video: a Fresing CNC mill, Fresing's own design, rendered with Fresing Render – https://fresing.nl
- Mekanika EVO CNC by Mekanika SRL, CERN-OHL-S-2.0 – https://github.com/mekanika-dev/evo
- Thor robot arm by Ángel L. M. (AngelLM), CC BY-SA 4.0 – https://github.com/AngelLM/Thor (first render; a corrected one follows)
- FarmBot Genesis by FarmBot Inc., CC0 1.0 – https://genesis.farm.bot/
- CEB Press by Open Source Ecology, CC BY-SA 4.0 (pictures of it: CC BY-SA 4.0) – https://github.com/goscommons/CEB-Press
- Test mill with a double-arm tool changer: an invented machine made by Fresing Render's own test-model maker (tools/make_test_atc.py) – the 3D model of "Turn it yourself" (task 0099), exported with 5 Scene & Render > Web 3D model

Rendered by the owner on his PC with `site/render_kit` (RTX 3090, Final quality, 9 Nov 2026). The test-model
placeholders of the first version are gone. Thor and OpenArm follow after a second run (see below).

## All models of the kit (site/render_kit/models.ini)

Licences checked on 8 Nov 2026 on the project pages. The owner approved EVO, OpenArm, Thor and FarmBot (8 Nov) and
asked for a model with a cylinder or a crane: the CEB press is the only openly licensed one found with CAD (no crane
with an open licence and CAD was found; rejected: MathWorks backhoe – MathWorks-only licence, HydraulicExcavatorCad –
CAD not licensed, Open-MiRoREA – non-commercial).

| Model | Maker | Licence | Where | Credit line |
| --- | --- | --- | --- | --- |
| Mekanika EVO CNC router | Mekanika SRL | CERN-OHL-S-2.0 (`REUSE.toml`: `cad/*.step`) | https://github.com/mekanika-dev/evo | Mekanika EVO CNC by Mekanika SRL, CERN-OHL-S-2.0 |
| OpenArm robot arm | Enactic, Inc. | CERN-OHL-S-2.0 (`LICENSE.txt`) | https://github.com/enactic/openarm_hardware | OpenArm by Enactic, Inc., CERN-OHL-S-2.0 |
| Thor robot arm | Ángel L. M. (AngelLM) | CC BY-SA 4.0 | https://github.com/AngelLM/Thor | Thor robot arm by Ángel L. M. (AngelLM), CC BY-SA 4.0 |
| FarmBot Genesis | FarmBot Inc. | CC0 1.0 (to be confirmed on genesis.farm.bot) | https://genesis.farm.bot/ | FarmBot Genesis by FarmBot Inc., CC0 1.0 |
| CEB brick press (hydraulic cylinders) | Open Source Ecology | CC BY-SA 4.0 (`LICENSE.md`) | https://github.com/goscommons/CEB-Press – FreeCAD, converted to STEP in this session (246 parts) | CEB Press by Open Source Ecology, CC BY-SA 4.0 (pictures of it: CC BY-SA 4.0) |
| IEA 15 MW wind turbine, offshore (monopile) and on land | IEA Wind TCP Task 37 (Gaertner et al., NREL / DTU / UMaine, 2020) | Apache-2.0 (`LICENSE`; no NOTICE file in the repository) | https://github.com/IEAWindSystems/IEA-15-240-RWT – its SolidWorks model (`CAD/deprecated/IEA-15-240-RWT_Solidworks.zip`), exported to STEP by the owner in Fusion (task 0116) | IEA 15 MW Reference Wind Turbine (IEA-15-240-RWT) by IEA Wind TCP Task 37, Apache-2.0; nacelle cover, doors, platforms, monopile details, looks and motion added by Fresing |

Not used: anything from GrabCAD (its terms do not allow it), MPCNC / LowRider (non-commercial licence), PrintNC
(CAD moved off the licensed repository), and models whose licence could not be confirmed.

## The IEA 15 MW turbine: what Fresing changed (Apache-2.0, section 4)

The model is the IEA Wind TCP Task 37 reference turbine, version 1.0 (github.com/IEAWindSystems/IEA-15-240-RWT, tag
v1.0, Apache-2.0; report: Gaertner et al., "Definition of the IEA 15-Megawatt Offshore Reference Wind Turbine",
NREL/TP-5000-75698, 2020). The STEP files of the render kit (`iea15_offshore.step`, `iea15_onshore.step`, written by
`tools/make_site_projects.py`) are **modified** copies of its SolidWorks model, and say so in their header. Changes:
the model moved so the tower stands on z and the sea level is z 0 (on land 14 m lower); the tower solid cut into tower
and monopile, a door opening cut into it; modelling aids hidden (the stand-in main bearing rings, the blades' root
discs, a ball at the hub's centre, the monopile below the seabed); added by Fresing: nacelle cover with hatch, cooler,
helicopter-hoist platform, aviation lights and wind sensors, tower door, steps, tower flanges, yaw seal, transition
piece, working platform, davit, cabinet, ladder, boat landing, J-tubes (offshore), concrete foundation and stair (on
land), signs, looks and the motion (yaw, rotor, pitch, door, davit). Nothing of the IEA model is in this repository;
no maker's name or logo is on the model.

## The 3D viewer

- "Turn it yourself" (model/index.html) shows the web model with Google's model-viewer 4.4.0, Apache-2.0
  (`vendor/model-viewer-umd.min.js` and its licence, copied from `fresing_render/web/`; three.js MIT and lit
  BSD-3-Clause are inside it with their notes). Nothing is loaded from other sites. Only invented or openly licensed
  models go there – never the Fresing 400 (not public, owner 12 Nov 2026). Swap the model with
  `tools/build_site.py --web-model <file.glb> --model <id>` after adding its credit here and in media.json.

## Type and logo

- IBM Plex Sans, © IBM Corp., SIL Open Font License 1.1 (`site/fonts/OFL-IBM-Plex.txt`).
- The Fresing logo (`site/brand/`) is Fresing's own, approved for this page by the owner (8 Nov 2026).
