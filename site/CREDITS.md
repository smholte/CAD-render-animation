# Credits for the landing page

The pictures and videos on https://smholte.github.io/CAD-render-animation/ show these models, rendered with Fresing
Render. The models themselves are **not** in this repository – only the pictures. Every line here is also on the page
(`site/media/media.json` → "Credits"); `tests/test_site.py` checks both.

## Models on the page now

- Milling video: a Fresing CNC mill, Fresing's own design, rendered with Fresing Render
  (the owner's own machine; shown at his request, 8 Nov 2026 – nothing secret in it)
- Test crane: generic test model made by Fresing Render's own tools
  (`tools/make_test_crane.py`, in this repository; GPL-3.0-or-later like the app)
- Test mill: generic test model made by Fresing Render's own tools (`tools/make_test_mill.py`)
- Test luffing crane: generic test model made by Fresing Render's own tools (`tools/make_test_cylinder.py`)
- Test gantry: generic test model made by Fresing Render's own tools (`tools/make_test_gantry.py`)

## Models planned for the owner's renders (site/render_kit/models.ini)

Licences checked on 8 Nov 2026 on the project pages; the owner approves the list before they are used.

| Model | Maker | Licence | Where | Credit line |
| --- | --- | --- | --- | --- |
| Mekanika EVO CNC router | Mekanika SRL | CERN-OHL-S-2.0 (`REUSE.toml`: `cad/*.step`) | https://github.com/mekanika-dev/evo | Mekanika EVO CNC by Mekanika SRL, CERN-OHL-S-2.0 |
| OpenArm robot arm | Enactic, Inc. | CERN-OHL-S-2.0 (`LICENSE.txt`) | https://github.com/enactic/openarm_hardware | OpenArm by Enactic, Inc., CERN-OHL-S-2.0 |
| Thor robot arm | Ángel L. M. (AngelLM) | CC BY-SA 4.0 | https://github.com/AngelLM/Thor | Thor robot arm by Ángel L. M. (AngelLM), CC BY-SA 4.0 |
| FarmBot Genesis | FarmBot Inc. | CC0 1.0 (to be confirmed on genesis.farm.bot) | https://genesis.farm.bot/ | FarmBot Genesis by FarmBot Inc., CC0 1.0 |

Not used: anything from GrabCAD (its terms do not allow it), MPCNC / LowRider (non-commercial licence), PrintNC
(CAD moved off the licensed repository), and models whose licence could not be confirmed.

## Type and logo

- IBM Plex Sans, © IBM Corp., SIL Open Font License 1.1 (`site/fonts/OFL-IBM-Plex.txt`).
- The Fresing logo (`site/brand/`) is Fresing's own, approved for this page by the owner (8 Nov 2026).
