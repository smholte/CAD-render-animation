# 0109 – Weather and time of day in the app: a better ocean, rain, snow, wind, fog and clouds, day to night

**Who:** worker · **Status:** running · **Branch:** `claude/affectionate-turing-97hxbu`
**Started by:** lead chat, 13 Nov 2026 (owner: "improve the environment: rain, snow, time, wind")
**Lane:** Scene & Render + Sea (both free): new files `core/weather.py`, `blender/weather.py`, `ops_weather.py`,
`ui_weather.py` (a sub-panel of 5 Scene & Render); `world.py` (sky, sun, night); the sea and the outdoor surroundings in
`surroundings.py`. Additive: `props.py`, `reimport.py`, the material hook next to `fade.py` / `section.py` (one node
group in every look, like the cutaway – the Looks lane's files are not otherwise changed), a step kind in 6 Animation
(`props.BLOCK_KINDS`, a few lines in `animation.py` / `ops_motion.py` / `ui_motion.py`, as 0100 did), the tour, the PC
check, the guide.
**Model:** **Fable · effort High** (subagents, CLAUDE.md section 2) – or Opus · High to save usage · **Place:** Claude Code
on the web, environment "CAD-render-animation"
**Runs beside:** 0079 (Flex parts + Demo models: `demo.py`, flex/paths files), 0106 (Web 3D files; it **reads**
`surroundings.SEA` / `_waves` and the sky settings), 0108 (CI/test machinery). Touch none of their files.
**Afterwards:** a Web 3D task brings this weather onto the web page (after 0106 and this task; the lead briefs it).

## Goal

The owner sets the weather and the time for a still or a video in one place: **rain, snow, wind, fog / haze / low
clouds, and any time from sunrise to night** (with floodlights and work lights). The machine looks wet in rain, gets a
snow layer in snow, the sea follows the wind, and a video can go from day to dusk. It renders the same every time, in
the render queue too, on Cycles and EEVEE.

## Owner's answers (13 Nov)

- Where: **in the app's renders and videos, and the web page takes the same settings over afterwards**.
- What: **all four** – rain + snow, time of day + night, wind, fog / haze / clouds.

## Background

- Today: light looks (`core/studio.py` `LIGHT_ITEMS`: studios, 360° photo, Sky) with Sky weather **Sun / Overcast**
  (`WEATHER_ITEMS`), sun height, light rotation / strength, exposure (`props`, `world.py`); surroundings open sea, vessel
  deck, quayside, halls (`surroundings.py`, task 0016); the sea `SEA` Calm / Rough (swell, wavelengths, ripples,
  foam) with moving waves (geometry near the machine in Detailed); vessel motion adds a long swell (0085).
- 0106 (running) copies today's `surroundings.SEA` and `_waves` into the web page. **The sea may change here** (owner,
  13 Nov: it looks wrong, scope 0): put the new sea's definition – wave components, heights, crest/foam rule, colours –
  in **one pure-Python place** (`core/sea.py`, unit-tested: height and foam at a point and a time) so the later Web 3D
  task can copy it to the page. Do not edit 0106's files.
- Patterns to reuse: per-part looks through one node group in the materials (Fade 0073, cutaway 0086 – scripts off,
  Cycles + EEVEE, queue); motion from simple-expression drivers or keys (vessel motion 0085), never Python per frame;
  chips / coolant drops worked out once per animation and the same every time (0028, 0042).
- Indoors (halls, studios): no rain, snow or wind; time of day only where a hall has windows or a sky shows (say it in
  the panel).

## Scope

0. **A better ocean first** (owner's picture, 13 Nov – described here in words, not committed): top view of the demo
   vessel on Open sea, Rough, Detailed, Foam on, Moving, light Overcast, vessel motion Rough 150 % from the bow quarter.
   **What is wrong:** the foam forms broad, regular, parallel white bands right across the sea, about half the surface
   white, spaced at the main wavelength – stripes, not a sea; the pattern repeats visibly from above; the water is a flat
   dark green-grey; no foam where the hull meets the water. **Cause in the code** (`surroundings._water_shader`): foam =
   the crest attribute `fr_crest` + 0.35 × noise over a threshold (Rough 0.55), so every crest of the 70 m wave turns
   white along its whole length; only 5–6 wave components (directions 25° ± 35°, `_waves`) plus vessel motion's swell;
   base colour (0.006, 0.03, 0.035) with little sky in it. **Aim:**
   - whitecaps only where waves are steep or breaking, patchy, short-lived and drifting; **coverage from the wind**
     (Bft 3 ≈ hardly any, Bft 6 ≈ a few per cent, storm much more; streaks of foam along the wind from about Bft 7) –
     take the coverage from a published relation (e.g. Monahan's whitecap coverage vs wind speed) and cite it;
   - a sea built from a wave **spectrum** with directional spread (e.g. Pierson–Moskowitz / JONSWAP) – no visible repeat
     from any height, also a top view of the whole 124 m vessel and towards the horizon; Calm and Rough stay the two
     quick choices (now = a wind strength), vessel motion's swell keeps matching the vessel's motion;
   - water colour and reflection right under sun and overcast (deep-water colour, Fresnel sky reflection, a little
     scatter in wave crests);
   - **foam round the hull** at the waterline that follows heave and roll; a **wake** when a vessel speed is set
     (default 0: a cable-lay vessel lays at walking pace or slower);
   - checked from the owner's view (top, whole vessel), the deck camera and a horizon shot, Cycles and EEVEE, Calm,
     Rough and three wind strengths; old projects open with the new sea (say so in the changelog).

1. **Panel 5 Scene & Render > Weather & time** (every control with a tooltip; folded): presets **Clear day · Grey North
   Sea · Storm · Snow at the quay · Night shift** that set the controls below; Off = today's look exactly.
2. **Time of day:** a clock time (and optionally date + latitude for the real sun path – your call, say why) sets sun
   height, direction and the sky's colour (sunrise, day, golden hour, dusk); **night**: dark sky, moon and stars,
   **floodlights** on masts/deck or quay set up automatically for the outdoor surroundings, and **work lights**: click a
   part and it becomes a lamp (spot or flood, colour, strength), kept through model updates. The old Sun / Overcast
   settings map to it (old projects look the same).
3. **Clouds, fog, haze:** cloud cover (clear → overcast → low clouds), haze to the horizon, sea mist / fog with a
   visibility in metres; cheap enough for videos (measure: a world/distance fog before a volume, volume only where it
   pays off).
4. **Rain:** falling rain (amount, drop size), slanting with the wind, splashes on the deck and the sea; **wet look**
   on the machine and the deck through the material hook: darker, glossier, drops and run-off streaks on sloped
   surfaces, puddles on flat deck parts; a Wet slider that also works without falling rain (after the rain).
5. **Snow** (added 13 Nov, House round trip: **snow build-up has to work on imported geometry** – any mesh object, also
   one not made by the STEP importer, without part IDs or CAD faces, e.g. a house from a `smholte/house-scene-format`
   package; make it a function another lane can call on a list of objects. Never attach `smholte/house-planner-dev`;
   tests only with made-up geometry or that repository's sample packages)**:** falling flakes (amount, wind drift), a **snow layer on upward faces** (thickness, only where snow can
   lie: by normal and by being under the sky – parts under a roof stay clear; a ray or shadow test, your design), snow
   on the deck and quay, frozen spray look optional.
6. **Wind:** direction (also relative to the vessel's heading) and strength (Beaufort or m/s): with the sea "From the
   wind" the swell, chop and white caps follow it (Calm ≈ Bft 3, Rough ≈ Bft 6 – match today's look at those); spray
   off wave tops and at the bow; rain and snow slant and drift; **flags** (an optional flag prop on a mast or the
   stern, cloth-like by a shader or shape keys, no simulation per frame). Hanging cables and hoses swaying in the wind:
   **not here** (Flex parts lane, later).
7. **Changes over a video:** a step **Weather & time** in 6 Animation that fades from the current weather/time to a
   new one over its length (day to dusk, the rain starting, the fog lifting); keys, scripts off, the queue renders it.
8. **Same every time:** rain, snow, spray and flags depend only on the frame number (seeded); the render queue and
   every paint scheme render it; saved scenes keep their weather; a model update keeps work lights.
9. **Cost:** render time per frame with each item on (Cycles CPU and EEVEE on the web machine, the demo vessel and a
   test mill, Draft); viewport stays usable (a lighter look while posing if needed). PC check: a line per item
   (`weather.*`), times in the Heavy mode; tour stops "Weather" and "Night shift"; guide chapter with pictures (invented
   models only, `docs/img/`), tooltips.

## Done when

- [ ] Scope 0–9; with Weather Off everything except the sea looks exactly as before (picture check); the new sea in
      `core/sea.py` with unit tests (heights, foam coverage per wind strength within the cited relation's range).
- [ ] A before/after contact sheet of the sea in the owner's view (top, whole demo vessel, Rough, Overcast) and a horizon
      shot in the report.
- [ ] Tests per part (time → sun angle, presets, seeds same every time, the material hook in Cycles + EEVEE with
      scripts off, snow only under the open sky, the animation step, model update); an agent that did not write the
      code tries to break it; Windows-only code: none expected (say so).
- [ ] A contact sheet of the presets on the demo vessel and the test mill in the report (`tasks/img/0109_*.jpg`).
- [ ] GitHub green incl. Windows; report filled in (subagents, runs, render-time numbers); merge to main and release
      when green, then check that main really contains your commit.

## Design (worker, 13 Nov – the subagents' brief)

**The contract: channels.** `core/weather.py` (written first, by the worker) holds the settings (`State`, mirrored by
`props.FRWeather` = `scene.fresing.weather`), the presets, the sun's path (local solar time; equinox without a date),
Beaufort ↔ m/s, `mix()` (the step) and `derive(state, place) -> {channel: float}`. The coordinator
`blender/weather.py` writes the channels as plain scene custom properties **`scene["fr_wx_<name>"]`**
(`core.weather.CHANNELS`: sun_el, sun_az, moon_el, moon_az, day, night, sun, clouds, low, fog (per km), fog_r/g/b,
stars, moon, exposure, flood, rain, drop, wet, snow, cover, wind (m/s), wind_x, wind_y, foam). **Everything that shows
weather reads only channels:** in shaders an Attribute node of type **VIEW_LAYER** named `fr_wx_<name>` (reads the
scene's property; Cycles + EEVEE); elsewhere (world node inputs, lamp energy, modifier inputs, compositor) a driver
of type SCRIPTED with a **simple expression** whose variable is SINGLE_PROP, id_type SCENE, data_path
`'["fr_wx_<name>"]'`. No Python per frame. The Weather & time step keys the channels (plain props: scripts off, queue).
`place` = `core.weather.where(background)`: "sky" (SKY, SEA, DECK, QUAY: the app draws the sky), "photo" (360°
photo: rain/snow/wet/wind but its own light), "indoor" (halls, studios, colour: only work lights).

**Order of a rebuild:** a control changes → `weather.changed` writes the channels → `world.apply(scene, s)` (world
tree, surroundings incl. the sea) → at its end `weather.after_world(scene)` → `weather_sky.apply(scene, st, place)`,
`weather_look.apply(scene, True)`, `weather_fx.apply(scene, st, place)`; Off → `weather_sky.remove`,
`weather_look.apply(scene, False)`, `weather_fx.remove`, channels deleted. Each must be cheap when nothing changed and
must never raise into the UI.

**Owners (one owner per file):**

| Who | Files | Delivers |
| --- | --- | --- |
| worker | `core/weather.py` (until handed to Sky, see below), `blender/weather.py`, `props.py`, `ui.py`, new `ui_weather.py`, `ops_weather.py`, `animation.py`, `ops_motion.py`, `ui_motion.py`, `states.py`, `reimport.py`, tour, PC check, guide, CHANGELOG, TASKS.md, version files | settings, panel, presets, the step, saved scenes, model update, tour/PC check/guide |
| **Sea** agent | new `core/sea.py` + `tests/test_sea.py`; the sea part of `blender/surroundings.py` (and `core/surroundings.py` if the Simple sea mesh needs rings near the hull); `core/vessel_motion.py` / `blender/vessel_motion.py` only for compatibility | scope 0 + spray (6) |
| **Sky** agent | `blender/weather_sky.py` (new), `blender/world.py`; owns `core/weather.py` from its start (the worker no longer edits it; tests `tests/test_weather_core.py`, `tests/test_weather_sky.py`) | scope 2, 3 (+ the sky part of 1) |
| **Look** agent | `blender/weather_look.py`, `blender/weather_fx.py`, `core/weather_fx.py` (all new), the 3-line hook in `blender/materials.py` `build_nodes`; tests `tests/test_weather_look.py`, `tests/test_weather_fx.py` | scope 4, 5, flags of 6 |
| tester (later) | new tests only | breaks it from this brief |

**Sea agent – interfaces.** `core/sea.py` (pure Python + NumPy): `components(wind_bft, toward_deg, seed=…) ->
list[(amp, dx, dy, k, phase)]` (the same tuple as today's `surroundings._waves`; a Pierson–Moskowitz/JONSWAP
spectrum with cos-2s spreading, ≥ 24 components, no visible repeat; deterministic); `height(x, y, t, comps)`,
`slope(x, y, t, comps)`; `whitecap_coverage(u10)` (Monahan & O'Muircheartaigh 1980, W = 3.84e-6 U^3.41, cite it);
`foam(x, y, t, wind_bft, comps)` – the **exact** formula the water shader evaluates (crest steepness × a patch field
made of sines that drifts along the wind and lives a few seconds; streaks along the wind from Bft 7; no Blender noise
in the coverage part, so Python and the shader agree); `foam_threshold(bft) -> float` (calibrated so the share of sea
above it equals the Monahan coverage; `core/weather.derive` already calls it for the `foam` channel); `STATES =
{"CALM": 3.0, "ROUGH": 6.0}` (Beaufort; today's two choices); water colours. `blender/surroundings.py`: `SEA` and
`_waves(state, swell=())` stay (0106 reads them; `_waves` returns the new components for CALM/ROUGH/WIND);
`s.sea_state` has a third item `WIND` ("From the wind": `scene["fr_wx_wind"]`… read the *settings*
`scene.fresing.weather.wind` and `core.weather.wind_vector(weather.state(scene))` at build; the sea is rebuilt when
they change – put them in `_settings_key`); the water shader reads the `foam` threshold from the channel when
`scene.fresing.weather.enabled` (VIEW_LAYER attribute `fr_wx_foam`), else from `foam_threshold(STATES[state])`;
normals from the analytic slope (no repeat far away); deep-water colour + Fresnel + crest scatter, right under Sun and
Overcast; **hull foam** at the waterline that follows heave and roll (e.g. a footprint line of the model at the water,
a child of the vessel rig, Geometry Proximity in the sea's GN → attribute), in Simple and Detailed; **wake** behind the
stern when `scene.fresing.weather.vessel_speed` > 0 (knots; the stern is at +x, bow at -x); **spray** (an object of
its own, GN, seeded, Scene Time) off white caps and at the bow from Bft 6 when `weather.spray`; bump `MAT_VERSION`;
vessel motion keeps matching (`core/vessel_motion.scales` per state: give WIND the nearest/interpolated table).

**Sky agent – interfaces.** `weather_sky.SUN_ROTATION_ZERO_AZ` (scene azimuth of the sky texture's sun at
`sun_rotation` 0; `weather.switched` uses it so an old project's sun stays where it was); `world_branch(nt, scene, s,
y) -> socket` used by `world.apply` instead of `_env_branch` when `weather.sky_on(scene)`: the sky from `sun_el` /
`sun_az` / `sun` / `clouds` / `low` / `day` (sunrise, day, golden hour, dusk colours), stars and a moon disc at night,
haze towards the horizon, keeping today's ground below the horizon; `world.apply` calls `weather.after_world(scene)` at
its end (guarded). `apply(scene, st, place)`: moonlight (a dim Sun lamp, energy driven by `moon`), sunlight if needed,
**floodlights** set up automatically for SEA/DECK/QUAY (spots on masts round the model's box at deck/quay height; a
mast mesh where it stands on the quay), energy = watts × `flood`; **fog/haze**: measure world/distance fog first (e.g.
Mist pass + compositor `scene.compositing_node_group` with exp(-fog·d) – the sky itself gets haze from the world
shader) and a volume only where it pays off; the exposure (`exposure` channel added to the user's own: a driver
`base + e` on `view_settings.exposure`, base kept in a scene property). **Work lights:** `add_work_light(scene, part,
kind="SPOT"|"FLOOD") -> light object` (child of the part, tag `fr_work_light` = the part's uid, kept through a model
update by `after_model_update(scene, mapping)`), `work_lights(scene)`, `remove_work_light(scene, ob)`; they work with
weather off too. `remove(scene)` takes away everything weather_sky made except work lights.

**Look agent – interfaces.** `weather_look.GROUP = "FR weather"`, `TAG = "fr_weather_wrap"`; `wrap(mat)` puts the
group (shader in → shader out) **innermost**: between the look's shader and whatever follows (the fade group
"FR fade", the section group, or the output) – fade/section keep working on the wet surface; `unwrap(mat)`,
`is_wrapped(mat)`; `apply(scene, on)` wraps every material of the model's parts and decals and the surroundings'
ground/deck/quay materials (`surroundings.TAG` objects; never the water, lamps, glass of lamps or the sky), unwraps all
when off. Hook in `materials.build_nodes` before the fade/section lines: `if mat.get("fr_weather_wrap"):
weather_look.wrap(mat)`. The group reads `wet`, `cover`, (`snow`) by VIEW_LAYER attributes: wet = mixing towards a
darker version + a clear wet film (glossy, Fresnel), drops and run-off streaks on slopes (world-space, along gravity),
puddles on flat up-facing faces; snow = a white, rough layer by normal·up and **only under the open sky** (Cycles: the
AO node, not local, distance ~ tens of metres, on up-facing points; EEVEE: what its AO gives), thickness from `cover`.
**Snow on imported geometry (brief change 13 Nov):** `weather_look.add_objects(scene, objects) -> int`, `remove_objects(scene, objects) -> int`, `targets(scene)` – any mesh object (no part ids, no CAD faces, maybe no material: it gets a made-for-it neutral one), marked `fr_weather_target`; `apply` includes them; the snow test uses only geometry and the world. Tests with made-up geometry only (never smholte/house-planner-dev).
`weather_fx.apply(scene, st, place)` / `remove(scene)`: falling rain (streaks, size from `drop`, slanting with
`wind_x/y`·`wind`), splashes on the deck and the sea (spots worked out once by rays straight down, then GN with Scene
Time), falling snow (flakes drifting with the wind), the flag (`weather.flag`: a pole + cloth moved by a GN/shader
wave from the wind, no simulation) – all seeded, depend only on the frame; in a box round the camera's view / the
model; amounts driven by the channels (`rain`, `snow`), so the step can start the rain. Objects tagged `fr_weather`.

**Rules for every agent:** first line `git merge claude/affectionate-turing-97hxbu` in the worktree. Never push,
merge into main, bump the version or touch `TASKS.md`. Tests with `~/venv/bin/python -m pytest tests/<your files>`;
real-Blender renders one at a time (4 cores). Scripts off (simple expressions only), Cycles + EEVEE, the render queue
(a background Blender opens the saved file: nothing may depend on Python handlers). Commit in your worktree; report
what you made, the tests, the numbers measured (render time per frame with your item on: Cycles CPU and EEVEE, Draft)
and pictures you looked at (`tasks/img/0109_<name>.jpg`, small JPEGs, invented models only).

## Not in this task

The web page (a later Web 3D task). Cables / hoses / flex parts moving in the wind. Lightning, hail. Changing the
Looks lane's materials beyond the one hook. Real weather data from the internet.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
