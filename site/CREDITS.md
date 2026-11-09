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

Not used: anything from GrabCAD (its terms do not allow it), MPCNC / LowRider (non-commercial licence), PrintNC
(CAD moved off the licensed repository), and models whose licence could not be confirmed.

## Type and logo

- IBM Plex Sans, © IBM Corp., SIL Open Font License 1.1 (`site/fonts/OFL-IBM-Plex.txt`).
- The Fresing logo (`site/brand/`) is Fresing's own, approved for this page by the owner (8 Nov 2026).
