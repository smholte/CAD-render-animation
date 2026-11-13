# 0114 – House round trip: import a House Planner scene, bake, export the bake package

**Who:** worker · **Status:** running · **Branch:** `claude/keen-hypatia-mtjwps` (the web session's branch)
**Started by:** lead, 13 Nov 2026 · **Area:** House lane – new files `core/house_scene.py`, `core/house_snow.py`,
`blender/house_import.py`, `blender/house_bake.py`, `blender/ops_house.py`, `blender/ui_house.py`, their tests,
`tests/data/house/`; additive: `blender/lightbake.py` (one argument), `props.py`, the File > Import menu, tour, PC
check, guide, `tools/requirements-dev.txt` (`jsonschema`)
**Model:** Opus · effort High · Claude Code on the web, environment "CAD-render-animation" · **subagents** (CLAUDE.md
section 2: design first, one owner per file, an independent tester)

## Goal

The owner opens a House Planner export (`.hpscene`) in Fresing Render, presses one button, and gets a `.hpbake`
package back: baked light per surface for every moment of the recipe (morning, afternoon, evening, night …), snow
layers per season, the recipe's photos and videos. House Planner imports it and shows that light live, also on a phone.

## Background

- **The format** is the public repository `smholte/house-scene-format`, **pinned at tag `v1.0`** (commit `52c0352`).
  Read its `FORMAT.md` in full (546 lines) – it is the contract; sections 6, 8 and 10 are written for this task
  ("I24c" there = this task). Clone it read-only (`git clone --depth 1 --branch v1.0 …`). Never push to it: a change
  to the format is a task of its own that both leads review. If the format is unclear or `check.py` disagrees with
  `FORMAT.md`, **write the question in the report and go on with the safer reading** – do not change the format.
- **Never attach or clone `smholte/house-planner-dev`** (private: the owner's own house; CLAUDE.md section 6). Only the
  made-up samples of `house-scene-format`.
- The FR lead's review of the draft: `tasks/house-format-v1-review.md` – what Fresing Render promised (all of it is
  this task). House Planner's own side (export `.hpscene`, import `.hpbake`) starts after its task 0009; your real
  bake of the sample (below) is what it will test its import with.
- **0107 (0.2.89) `blender/lightbake.py`**: `lightbake.bake(objects, light, *, world, sky, occluders, lamps, ids,
  uv="AUTO"|"UV1"|"VERTEX", quality, texels_per_m, samples, device, progress, scene, denoise) -> Result`.
  `Result.items[id]` = `Item` (`pixels` (H, W, 3) row 0 at the bottom for `MAP`; `values` (vertices, 3) in the mesh's
  vertex order for `VERTEX`); `Result.reference`, `reference_sky`, `sun_separate`, `problems`. Note: `sky=` takes
  `sun_height` (elevation, degrees) and `sun_direction` = **the sky texture's `sun_rotation` in degrees**, not an
  azimuth – so pass `SUN_ROTATION_ZERO_AZ − azimuth` (`weather_sky.py`).
- **0109 (0.2.88)**: `core/weather.py` (`State`: hour = local solar time, day, latitude, north, clouds, low_clouds,
  visibility, rain, snow, snow_cover, wet, wind, wind_from; `exposure_for(sun_el, clouds)`); `weather_sky.py`
  (`SUN_ROTATION_ZERO_AZ` = 90, night sky, moon, stars); `weather_look.py` (snow/wet **material layer**:
  `add_objects`, `remove_objects`, `targets`; `SKY_DISTANCE` = 25 m).
- **Call 0107 and 0109, never copy them.** Their files stay unchanged except the one additive argument below. 0109's
  sky works its sun out from hour/day/latitude/north; House Planner's sun must win (FORMAT 7.5). If 0109 cannot take
  given angles, set `hour` and `north` so its sun lands on House Planner's elevation and azimuth (two numbers, two
  angles), check it within 0.5°, and say in the report how.
- The House lane line in `TASKS.md` lists the files.

## What to build

**1. `lightbake.bake(..., sizes={object: (W, H)})`** – additive, only with `uv="UV1"`: that object's image is exactly
W × H (any whole numbers); objects without an entry are sized as today. A size that disagrees with the object's UV
layout by more than 2 % → a `Result.problems` line, never a silent rescale. Own test. Nothing else in 0107 changes.

**2. `core/house_scene.py`** (no Blender): read a `.hpscene` – the zip rules of section 2 (refuse absolute paths,
`..`, duplicates, encryption), versions (refuse another major with the format's kind of message; read a newer minor
and ignore unknown fields; open-list values as section 13 says), the recipe. The sun: glTF vector → Blender
(x, −z, y) → scene azimuth + elevation → `sun_rotation`; compare with the moment's own angles (`problems` line above
0.5°). Write a `.hpbake`: `bake.json`, pages, vertex files, snow `.glb`, photos, videos, `surfaces` (hash at bake
time, world `box`, world `matrix` when the node had a transform), `problems`.
- **Encoding** (8.3): absolute L, `b = clamp(round(255·sqrt(max(L,0)/scale)), 0, 255)` with **round half away from
  zero** (`floor(x + 0.5)` on the non-negative values) – not 0107's `encode` (half to even). `scale` per moment = the
  99.9th percentile of all channel values of that moment's results (positive even when everything is dark).
  `reference` = 0107's `Result.reference`; `exposure` = 0109's `exposure_for`; `sun_light` = `reference −
  reference_sky` for `SOFT` in daylight with a separate sun, `null` for `ALL`, `LIVE`, night, no separate sun.
- **Pages** (8.3): PNG 8-bit RGB, not interlaced, **no colour chunks**, 256/512/1024/2048 px, at most `page_size`;
  each `MAP` result's rect is exactly its `uv1_px`, 2 texels apart, no overlap, PNG row r = Blender row H−1−r. Keep
  one rect layout for every moment (each moment its own page files) so House Planner can reuse its UV transform.
  Aim for one moment ≤ 4 pages (warn otherwise).
- **Vertex files** (8.4): 3 bytes per vertex, the `.glb`'s vertex order, every result its own range.
- **The surface hash `hp-hash/1`** (section 5): needed for the snow layers you make. Implement it here (or copy
  `hsf/surface.py`'s function from tag `v1.0` with a line naming its source) – the checker recomputes it.

**3. `blender/house_import.py`**: File > Import > **House Planner scene (.hpscene)…**: unzip to a folder next to the
project, Blender's glTF importer with merge vertices off and **Lighting Mode "Standard"**; every object's `hp` label
kept; the house in its own collection; a project holds one house – importing again replaces it (ids are stable).
`ob["hp"]["id"]` is the id results are written under (`ids=`). Lamps: their light objects are children of the
fittings. Season `foliage: bare` hides `foliage` surfaces in that season's moments.

**4. `blender/house_bake.py`**: per moment – 0109's sky (clouds, low_clouds, visibility, clock time for the night sky
and moon), House Planner's sun, the moment's lamps on (`"all"`, `"none"`, a list), the season's wet; then
`lightbake.bake` once for the `MAP` objects (`uv="UV1"`, `sizes` from `uv1_px`) and once for the `VERTEX` ones;
`NO` objects only take part (occluders). Night (elevation < 0): no sun disc, no sun lamp. **`open_storeys`**: hide
everything of a higher `level`, bake that storey's surfaces again → `open`. Quality from the recipe (`preset`,
`samples`). Progress per moment and Cancel (0107's); nothing in the project changed afterwards.

**5. `core/house_snow.py`** (+ its small Blender part): per season with `snow_cover` > 0 the **snow layer meshes** of
section 8.6 – new geometry by 0109's rule (upward faces under the open sky: nothing within `SKY_DISTANCE` above;
use 0109's own "facing up" threshold), thickness from `snow_cover` (1 ≈ 10 cm), large layers cut into ~0.5 m
pieces, kind `snow`, id `snow:<surface id>`, `on`, `storey`, `group`, `bake: VERTEX`, `hash`; written as
`snow/<season>.glb` – **float32 positions and normals, no required extensions** (if you reuse `core/web3d.py`'s
writer: no quantisation, no meshopt). Their light comes per vertex in that season's moments. Fresing Render's own
photos keep 0109's material layer (`weather_look.add_objects`).

**6. Photos and videos** of the recipe (7.6): Cycles at the photo's size, at its moment, with `falling` rain / snow /
wind through 0109; `turntable` videos round the camera's target with the app's turntable (MP4). Cameras from glTF
axes, `fov` vertical.

**7. Panel** `ui_house.py` (a sub-panel of 5 Scene & Render, shown when the project has a house): the house's title
and version, light choice and quality from the recipe (read-only), the list of seasons and moments, an estimate
(0107's `quick_estimate`), **Preview a moment** (sets the scene's 0109 weather to that moment, so the owner sees it in
the view), the big blue **Bake and export…** (writes `<house>.hpbake` next to the project, then "Show in Explorer"),
progress and Cancel, the `problems` after a bake. Tooltips on everything (CLAUDE.md section 6).

**8. Test data and the checker.** Copy, from tag `v1.0` of `house-scene-format`, `check.py`, `hsf/`, `schemas/` and
`samples/` into `tests/data/house/hsf-v1.0/`, with a `PINNED.md` naming the tag and commit and a test that checks the
copied files' SHA-256 against a list in that file (a newer tag = a new task). Add `jsonschema` (the format's
`requirements.txt` pin) to `tools/requirements-dev.txt`. The sample `.hpscene` also goes into
`fresing_render/data/` (made up, 98 KB) for the PC check and the tour.

## Done when

- [ ] The sample `sample-house.hpscene` imports; **Bake and export** writes a `.hpbake` that
      `check.py <bake> --scene <hpscene>` passes **with no ERROR** (on GitHub, low samples); warnings listed in the
      report with a reason each.
- [ ] A real bake of the sample at the recipe's quality (Draft, Cycles CPU on the web machine) is committed as
      `tests/data/house/sample-house.fresing.hpbake` (made up – fine in the public repository; House Planner's lead
      can test its import with it) – also passing `check.py`. Time and size in the report.
- [ ] Tests (sample only): `sizes=` exact and its 2 % `problems` line; encoding half away from zero (0.5 → 1, 2.5 →
      3) and the byte values for known L; the sun of FORMAT 7.5's example (elevation 29.35°, bearing 14.6° from +X
      towards −Y) and the resulting `sun_rotation` within 0.5°; night = no sun, `sun_light` null; `SOFT` day →
      `sun_light` present; page rows top-down (a surface lit from one side is brighter on the right rows); PNG has no
      colour chunks; another major version refused with a clear message, a newer minor read; zip with `..` refused;
      `bare` hides foliage; an `open` storey's results exist only for that storey; snow layers only on upward faces
      under the open sky (none under the roof) and their hashes recomputed by the checker; the table darkens the
      floor under it in a baked `SOFT` moment (a plain physical sanity check).
- [ ] **An independent tester subagent** (did not write the code) gets `FORMAT.md` and the checker and tries to break
      reader and writer (the format's own reviewer found six checker crashes that 43 tests missed). Its findings go
      back to the author; the report lists them.
- [ ] Tour stop (a new `@tour_set` with the sample house: a baked moment shown in the view) with `MIN_LINES_TOUR` /
      `MIN_CHECKS["tour"]`; PC-check line `house.bake` (Full: import the sample, bake one moment small, export, check
      the package's structure without `jsonschema`) with `MIN_LINES_FULL`; a Heavy line only if you find the bake time
      grows with load in a way the owner should see (say why or why not).
- [ ] User guide: a section "Houses from House Planner" (the owner's steps; the sample is the example), the panel's
      picture.
- [ ] Each test run on GitHub stays short: the bake tests at 4 samples on the sample house; a test longer than ~3 min
      is split.
- [ ] `lightbake.py`'s only change is `sizes=`; 0109's files unchanged.
- [ ] Report filled in: subagents and what each did, runs needed, times (bake of the sample per moment, the whole
      package), open questions about the format for the two leads.

## Not in this task

- Changing `house-scene-format` (questions go to the report; the leads decide a `v1.1`).
- House Planner's side (any repository of House Planner).
- Swapping in Fresing Render's own looks by `material` (later), walk-path videos (format: later minor), KTX2 page
  copies (optional in the format; skip), the web 3D export, 0109's snow material.
- Files of running tasks: 0081 (flex/sea/demo), 0110 (clash), 0112 (`site/`, render kit). `TASKS.md` lists them.

## Owner's check afterwards (the report gives the exact steps)

On the RTX 3090: File > Import > House Planner scene, the sample from the app's data folder (or House Planner's real
export, once it has one), Preview a moment, Bake and export – time per moment on the GPU, and the photo.

## Design (worker, 13 Nov 2026 – the subagents' brief; CLAUDE.md section 2)

Coordinates: **G** = glTF world (metres, +Y up) as in `house.glb`; **B** = Blender world = (x, −z, y) of G.
Units of light: L = 0107's units (Cycles DIFFUSE without colour). Pinned format: `tests/data/house/hsf-v1.0/`
(read `FORMAT.md` from the clone or the tag; the checker `check.py` there; samples there).

**Who owns which file** (one owner per file; subagents never push, merge, bump versions or touch TASKS.md):

| File | Owner |
| --- | --- |
| `core/house_hash.py` – `round_half_away`, `hash_primitives(prims, uv1_px)`, `scene_hash(pairs)` (done, = the checker on all 52 sample surfaces) | worker |
| `core/house_scene.py` + `tests/test_house_scene.py` | subagent A |
| `core/house_snow.py` + `tests/test_house_snow.py` | subagent B |
| `blender/lightbake.py` (`sizes=` only) + `tests/test_lightbake_sizes.py`; `blender/house_import.py`, `house_bake.py`, `ops_house.py`, `ui_house.py`, props, menu, registration, tour, PC check, guide, `tests/test_house_blender.py` | worker |
| `tests/test_house_independent.py` (written from FORMAT.md + this design, after the merge) | subagent C (independent tester) |

### `core/house_scene.py` (no Blender; numpy allowed; never imports the pinned `hsf`)

```python
VERSION = (1, 0)                       # the format version this code reads and writes ("1.0")
class FormatError(ValueError)          # a plain sentence for the owner
def read_zip(src) -> dict[str, bytes]  # path or bytes; section 2: refuse absolute paths, "\\", "." / ".." parts,
                                       # names listed twice, encryption (flag bit 0), methods other than stored/deflated,
                                       # empty names; FormatError with the reason
def check_version(doc, fmt) -> str | None   # fmt "house-scene"/"house-bake": wrong format or another major ->
    # FormatError("This house scene was made by a newer House Planner (format 2.0). Update Fresing Render to read it.")
    # (older major: "... an older House Planner ..."); a newer minor -> returns the note "Made by a newer House Planner
    # (format 1.3): some extras are not used." ; same version -> None
@dataclass Storey(id, name, level: int, elevation: float, height: float)
@dataclass Season(id, label, date, day: int (day of the year), snow_cover, wet, foliage)   # unknown foliage -> "full"
@dataclass Moment(id, label, season, time, utc_offset, azimuth, elevation, direction: tuple (G), clouds, low_clouds,
                  visibility, lamps)            # lamps: "all" | "none" | tuple of ids; an unknown text -> "none"
@dataclass Camera(id, label, position (G), target (G), fov)              # fov vertical, degrees
@dataclass Surface(id, kind, raw_kind, storey, group, bake, hash, uv1_px, node: int, mesh: int | None,
                   matrix: tuple (16, column-major world, G), moved: bool (matrix not identity), verts: int,
                   box: tuple (x0,y0,z0,x1,y1,z1 world G), source, material, light: int | None (KHR light index),
                   texels_per_m: float | None)   # unknown kind -> kind "other", raw_kind keeps the text
@dataclass Recipe(light, preset, texels_per_m, texels_per_m_by_group: dict, samples: int (resolved: given, else
                  16/64/256 by preset, NORMAL for an unknown preset), page_size, include_storeys, include_groups,
                  open_storeys, seasons: list, moments: list, cameras: dict, photos: list[dict], videos: list[dict])
                  # videos of an unknown kind are dropped (a note); fps not in 24/25/30/50/60 -> 25
@dataclass Scene(doc, files, glb: bytes, id, title, version_id, version_name, scene_hash, place: dict
                 (latitude, longitude, north (x, z), ground_level), storeys: list, recipe, surfaces: dict[id, Surface],
                 notes: list[str])     # notes: newer minor, a hash that does not match its geometry, ...
def read_scene(src) -> Scene           # path or bytes; FormatError for anything a reader must refuse
def storey_level(scene, storey_id) -> int | None
def glb_meshes(glb) -> (doc, binary)   # core/web3d.read_glb; primitives' arrays via web3d.accessor_array
def mesh_arrays(doc, binary, mesh) -> list[dict(positions, normals, uv1, indices)]
def world_triangles(scene, surface_id) -> (points (n,3) float64 G world, tris (m,3) int)   # all primitives, glb order
# the sun (FORMAT 7.5)
def gltf_to_blender(v) -> tuple                       # (x, -z, y)
def sun_angles(direction_g) -> (elevation_deg, scene_az_deg)   # B axes; scene_az = degrees(atan2(y, x))
def sun_rotation_deg(scene_az, zero_az=90.0) -> float          # 0109: zero_az - az, wrapped to (-180, 180]
def north_scene_az(north_xz) -> float                 # north (G x, z) -> B (x, -z) -> atan2
def sun_mismatch(moment, north_xz) -> float           # degrees between `direction` and (azimuth, elevation): compass
                                                      # azimuth turns clockwise from north seen from above
def weather_sun(elevation, scene_az, day, latitude) -> dict(hour, north, latitude, day, use_date=True)
    # 0109 (core/weather.py State) works its sun out from hour, day, latitude, north: solve hour (bisection, the
    # morning or afternoon branch whose bearing is nearer the wanted one) so sun_position(...)[0] == elevation, and
    # north so to_scene_az(bearing, north) == scene_az; when the elevation is out of reach on that day and latitude,
    # move the latitude (within ±70) until it is. Result checked: derive(State(**it)) gives sun_el, sun_az within 0.5°.
# light encoding (FORMAT 8.3)
def encode(L, scale) -> uint8 array    # clamp(round_half_away(255 * sqrt(max(L,0)/scale)), 0, 255)
def decode(b, scale) -> float32 array
def moment_scale(arrays) -> float      # 99.9th percentile of all channel values; positive even when all is dark
# pages (FORMAT 8.3)
def layout(sizes: dict[key, (W, H)], page_size, gap=2) -> (pages: list[(w, h)], rects: dict[key, (page, x, y)])
    # rows, tallest first, `gap` texels between rects; pages square 256/512/1024/2048 <= page_size, the smallest side
    # that holds everything in the fewest pages; a rect too big for page_size -> KeyError-free: left out + note
def page_png(rgb_uint8_top_down) -> bytes   # 8-bit RGB, no colour chunks (core/web3d.png)
class BakeWriter:
    def __init__(self, scene: Scene, *, light, samples, denoised=True, app_version="", bake_id=None, created=None)
    problems: list[str]                      # plain sentences, no line breaks
    def add_snow(self, season_id, glb_bytes)                       # snow/<season>.glb; its layers' ids/verts known
    def add_moment(self, moment_id, maps: dict[id, array], open: dict[storey, dict[id, array]] | None = None, *,
                   reference, exposure, sun_light=None)
        # array: MAP -> (H, W, 3) float, Blender rows (row 0 = bottom: PNG row r = row H-1-r); VERTEX -> (n, 3).
        # A MAP surface's result must be (uv1_px[1], uv1_px[0], 3); a VERTEX surface's (verts, 3); snow ids count as
        # VERTEX with their layer's vertex count. A result of the wrong kind or shape is left out with a problems line.
        # One rect layout for every moment (all MAP surfaces + every open storey's MAP surfaces), each moment its own
        # page files light/<moment>-p<k>.png and one vertex file light/<moment>-v.bin; scale = moment_scale of all of
        # the moment's results (maps, open, snow); warns (problems) above 4 pages per moment.
    def add_photo(self, photo_id, data: bytes, ext, size, moment, camera: dict)      # photos/<id>.<ext>
    def add_video(self, video_id, data: bytes, ext, size, moment, camera: dict, seconds, fps)   # videos/<id>.<ext>
    def bake_json(self) -> dict              # schema bake-1: surfaces = every surface with a result: hash (the
                                             # scene's), box, matrix when moved; no NaN; created "YYYY-MM-DDTHH:MM:SSZ"
    def write(self, path) -> None            # zip: JSON deflated, png/glb/bin/jpg/mp4 stored; temp file + os.replace
def structure_problems(path_or_bytes, scene=None) -> list[str]   # light check without jsonschema (PC check): zip
    # rules, version, every file named exists, PNG pages 8-bit RGB without colour chunks, rects inside pages and
    # = uv1_px, vertex ranges inside their file and = verts, sun_light null at night
```

### `core/house_snow.py` (no Blender; numpy)

```python
def min_up(cover) -> float        # 0109's "facing up" rule (weather_look._snow: lo = 0.85 - 0.45 cover, hi = lo +
                                  # 0.12; the middle of that ramp): 0.91 - 0.45 * cover, on the face normal's up part
THICKNESS_PER_COVER = 0.10        # m: cover 1 ≈ 10 cm (0109)
PIECE = 0.5                       # m: largest edge of a layer's triangles
def open_sky(points_g, tris_points_g, distance=25.0) -> bool array   # nothing within `distance` straight above
    # (+Y in G) each point; numpy, a grid over (x, z) so 100 k triangles x 10 k points stay fast; points lifted 1 mm
@dataclass Layer(id ("snow:<on>"), on, storey, group, positions (n,3) float32 G world, normals (n,3) float32,
                 indices (k,) uint32, hash)
def build_layers(scene, season, *, sky_distance=25.0) -> list[Layer]
    # candidates: surfaces with bake MAP or VERTEX, kind not glass/water/snow/lamp; foliage hidden when the
    # season is "bare" (it neither gets snow nor blocks the sky); faces facing up (geometric normal of the CCW
    # triangle, world G) >= min_up(cover); cut so no edge is longer than PIECE; a piece is kept when its centre is
    # under the open sky (blockers: every surface of the scene that is shown in that season); top = the kept pieces
    # lifted by THICKNESS_PER_COVER * cover along their normal, welded (one vertex per corner point, smooth light);
    # a skirt down to the surface along the layer's outline; every vertex used; hash = hash_primitives([...], None)
def layers_glb(layers) -> bytes   # glTF 2.0 binary: one node per layer (name = id, no transform), POSITION and
    # NORMAL float32 (min/max on POSITION), uint32 indices, extras.hp {id, kind "snow", storey, group, bake "VERTEX",
    # hash, on}; one scene; no extensions at all
```

### Blender side (worker)

- `lightbake.bake(..., sizes={object or name: (W, H)})`: with `uv="UV1"` that object's image is exactly W x H; the UV
  layout is checked: per triangle the texels per metre along U (W·|∇u|) and along V (H·|∇v|) must agree within 2 %
  (area-weighted), else a `problems` line – a wrong W or H shows as a stretched map.
- `house_import.import_scene(scene, path)`: unzip next to the project (`<project>/<name> house/`), glTF importer
  (merge vertices off, Lighting Mode Standard = `SPEC`) into collection "FR House", a model root "House: <title>"
  (so 5 Scene & Render shows), parts = the meshes (`fr_uid` = hp id). One house per project: importing again replaces it.
- `house_bake.HouseBake(scene, moments=None, photos=True, videos=True, samples=None).steps()` -> 0 … 1; per moment:
  0109's state with `weather_sun(...)` (checked against the channels within 0.5°), the moment's lamps, two
  `lightbake.bake` calls (MAP with `uv="UV1"` + `sizes`, VERTEX), each open storey again with higher levels left out,
  the season's snow layers baked per vertex (separate call, the house as occluders); SOFT at night is baked as ALL
  (the same light, FORMAT 7.5; `sun_light` null). Photos and turntable videos rendered with 0109's falling weather and
  its snow / wet material layer (`weather_look.add_objects`), then everything put back.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
