# House scene format v1.0 draft – Fresing Render lead's review

**Reviewed:** `FORMAT.md` on branch `claude/intelligent-mccarthy-o7vgza` of `smholte/house-scene-format` (House
Planner task 0016), 13 Nov 2026, by the Fresing Render lead chat. Checked against Fresing Render `main` at 0.2.89
(0107 `blender/lightbake.py`, `core/lightmap.py`; 0109 `core/weather.py`, `blender/weather_look.py`,
`blender/weather_sky.py`). Focus: sections 7.5, 8.3, 10, and House Planner's questions 1–4.

**Verdict:** agreed. Tag `v1.0` after the small text changes marked **(change)** below. The Fresing Render side of each
answer is done by the **House lane's first task** (TASKS.md), which starts after the tag. 0107 and 0109 are **not**
reopened.

## Answers to House Planner's four questions

**1. Exact image size per object with `uv="UV1"` – yes.**
Today `lightbake` sizes a `UV1` object's image itself (`core/lightmap.image_size`: a square power of two from its area
and `texels_per_m`). The House task adds one optional argument, additive only:
`lightbake.bake(objects, ..., uv="UV1", sizes={object: (W, H)})`. With `sizes`, each object's image is exactly W × H
(any whole numbers, not only powers of two); objects without an entry are sized as today. A size that disagrees with
the object's UV layout by more than 2 % is a `problems` line, not a silent rescale. `Item.pixels` is already
(H, W, 3) with row 0 at the bottom, which matches section 6's flip rule.

**Per-surface texel density** (House Planner's extra request: `extras.hp.texels_per_m`, defaults per group): fine for
Fresing Render. With `sizes` taken from each surface's `uv1_px`, the bake no longer needs one density for the whole
export. **(change)** Section 8.1 says `quality.texels_per_m` MUST be the recipe's. With per-surface densities, word it
as "each `MAP` result's rect is that surface's `uv1_px`". The checker then compares per surface. Keep
`recipe.quality.texels_per_m` as the default for surfaces without their own value.

**2. Sun as a vector, night with no sun – yes.**
Fresing Render takes the vector as given. It turns glTF (x, y, z) into Blender (x, −z, y), works out the scene azimuth
and elevation, and sets the sky by 0109's convention (`sun_rotation = radians(SUN_ROTATION_ZERO_AZ − azimuth)`,
`weather_sky.py`) through `lightbake`'s `sky={"sun_height", "sun_direction"}`. As a sanity check it compares this with
the moment's own `azimuth` / `elevation` and writes a `problems` line above 0.5°.
**Night** (elevation < 0): no sun disc and no Sun lamp. **(change)** In 7.5, write "the night sky as Fresing Render
renders that clock time (0109: stars, the moon when it shows one) and the moment's lamps" instead of "sky and lamps
only", so the bake and the photos of the same moment agree. At night `SOFT` and `ALL` give the same light. That is
expected, so it gets no `problems` line.

**3. Absolute light L with one scale per moment – yes, better than 0107's factor** (night would be about 250× off).
Two notes:
- **Rounding:** 0107's `core/lightmap.encode` rounds half to even (`np.round`); the format says half away from zero.
  The House task writes with half away from zero (`floor(x + 0.5)` on the non-negative values), so `check.py`'s
  byte comparison holds. The text stays as it is; 0107's web export is not changed.
- **(change, optional field in 1.0)** For `SOFT` in **absolute** mode, House Planner adds its live sun in L units but
  has no number for it. Proposal: an optional `sun_light` [R, G, B] per moment = the sun's direct light on a white
  matte surface facing the sun, in the same units as L (Fresing Render has it from 0107's open probe:
  `reference − reference_sky`). It is `null` for `ALL`, for night, and when the light has no separate sun. In factor
  mode House Planner can ignore it.

**4. Snow as a mesh layer per surface – yes.** three.js cannot run 0109's material.
**(change)** In 8.6, "Fresing Render makes them from its 0109 snow" is not quite right: 0109's snow is a **material
layer** (the "FR weather" node group; `weather_look.add_objects` only marks objects), not geometry. The House task
builds the layer meshes as **new geometry with 0109's rule**: faces facing up under the open sky (nothing within
0109's `SKY_DISTANCE` = 25 m above), thickness from `snow_cover` (1 ≈ 10 cm). Fresing Render's own photos keep 0109's
material layer. Both follow the same rule, so they agree. Large layers (plot, roofs) are cut to about 0.5 m so their
per-vertex light has enough points.

## Other points

- **Lamps (4.4 / 10)** **(change)**: name the import setting. Fresing Render imports `house.glb` with Blender's glTF
  importer, **Lighting Mode "Standard"** (its default: candela → watts). Write it in section 10 so both sides test the
  sample's ceiling lamp the same way. `lamps=` in `lightbake.bake` gets the moment's light objects, which the importer
  makes as children of their fittings.
- **Section 10, snow call:** `weather_look.add_objects` is right for Fresing Render's own **photos and videos** (the
  material layer). The **package's** snow comes from the House task's new mesh builder (point 4).
- **Weather names** in 7.5 (`clouds`, `low_clouds`, `visibility`, `snow_cover`, `wet`) match 0109's channels
  (`core/weather.py`). `exposure` in 8.3 is 0109's exposure channel. Agreed.
- **8.3 pages:** row 0 at the top in the PNG and bottom-up in Blender are both stated. PNG without colour chunks and no
  JPEG: agreed.
- **`open_storeys`:** Fresing Render hides everything with a higher storey `level` and bakes that storey's surfaces
  again. Agreed.

## What changes on the Fresing Render side (all in the House lane's first task)

| Where | Change |
| --- | --- |
| `blender/lightbake.py` (0107's) | additive: `sizes={object: (W, H)}` for `uv="UV1"`, with a test; nothing else changes |
| new `core/house_scene.py` | reads `.hpscene` (format v1.0), sun vector → sky angles, writes `.hpbake` (absolute L, rounding half away from zero, per-moment scale = 99.9th percentile, optional `sun_light`) |
| new snow-layer builder (House lane file) | mesh layers by 0109's rule; 0109's files unchanged |
| `blender/house_import.py`, `ops_house.py`, `ui_house.py` | as in the House lane |

Tests use only `house-scene-format`'s made-up samples, never `smholte/house-planner-dev` (CLAUDE.md section 6).
