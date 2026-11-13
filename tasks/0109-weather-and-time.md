# 0109 – Weather and time of day in the app: a better ocean, rain, snow, wind, fog and clouds, day to night

**Who:** worker · **Status:** done (0.2.88) · **Branch:** `claude/affectionate-turing-97hxbu`
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

- [x] Scope 0–9; with Weather Off everything except the sea looks exactly as before (picture check); the new sea in
      `core/sea.py` with unit tests (heights, foam coverage per wind strength within the cited relation's range).
- [x] A before/after contact sheet of the sea in the owner's view (top, whole demo vessel, Rough, Overcast) and a horizon
      shot in the report.
- [x] Tests per part (time → sun angle, presets, seeds same every time, the material hook in Cycles + EEVEE with
      scripts off, snow only under the open sky, the animation step, model update); an agent that did not write the
      code tries to break it; Windows-only code: none expected (say so).
- [x] A contact sheet of the presets on the demo vessel and the test mill in the report (`tasks/img/0109_*.jpg`).
- [x] GitHub green incl. Windows; report filled in (subagents, runs, render-time numbers); merge to main and release
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

**Chat / date:** worker session on Claude Code on the web, 13 Nov 2026 (branch `claude/affectionate-turing-97hxbu`).

**What changed:**
- **Channels** (`core/weather.py`): the settings become plain scene properties `fr_wx_*`; everything reads only those
  (VIEW_LAYER attributes in shaders, simple-expression drivers elsewhere), so the new **Weather & time step** only keys
  them (scripts off, render queue, paint schemes). Off = no channels, no group, no lamps, no objects.
- **Sea** (`core/sea.py`, sea part of `surroundings.py`): JONSWAP / Pierson–Moskowitz spectrum, 28 components with
  cos-2s spreading; white caps from steep crests × a drifting patch field, threshold calibrated to Monahan &
  O'Muircheartaigh (1980); analytic normals; deep-water colour; hull foam (model's waterline outline, rides with
  vessel motion), wake (vessel speed), spray (Bft ≥ 6); Sea **From the wind**. `MAT_VERSION` 4: old projects rebuild it.
- **Sky** (`weather_sky.py`, `world.py`): physical sky by the clock (solar time; equinox or a date + latitude), cloud
  patches → overcast → low deck, haze, stars + moon; moonlight; floodlights on masts (Quay/Deck/Sea, Auto from dusk);
  exposure opens up at dusk/night; fog in the compositor (Z pass); work lights (any part, kept through a model update).
- **Looks** (`weather_look.py`, hook in `materials.build_nodes`): the "FR weather" group innermost (before fade /
  section): wet (darker, glossy film, streaks, puddles), snow layer (normal·up × AO under the open sky). Only the parts
  a project uses are built. **Snow on any mesh** (brief change 13 Nov): `add_objects / remove_objects / targets`.
- **Falling things** (`weather_fx.py`, `core/weather_fx.py`): rain streaks (Atlas fall speed, wind slant), splashes
  (z-buffer from above), snow flakes drifting, the flag (no simulation) – GN with Scene Time, seeded.
- **Panel** 5 Scene & Render > Weather & time (presets, time, sky, rain and snow, wind, night lights, work lights),
  saved scenes keep the weather, render-queue fingerprint, the step in 6 Animation (overlapping steps blend).
- Tour set "weather" (3 stops), PC-check lines `weather.time/rain/snow/fog/sea/step`, Heavy `heavy.weather`, guide chapter.

**Subagents:** Sea (core/sea.py + the sea), Sky (core/weather.py from its start, weather_sky.py, world.py), Look
(weather_look.py, weather_fx.py, core/weather_fx.py, the materials hook) in parallel worktrees from the Design above;
then an **independent tester** (64 tests from the brief, `tests/test_weather_independent.py`) and a picture helper
(Sonnet). The tester found 5 faults, all fixed by the worker after merging: the sky's lamps and fog deleted by the rain
module's clean-up (shared tag + collection – also found by the worker while merging), overlapping steps jumped
(34.8° of sun), a low old sun (< 19.5°) came back too high (latitude clamp), the compositor switch not given back, rain
and flag inside the model tree. Merging also found: the sea material's own `fr_weather` flag made the rain clean-up
delete it (renamed `fr_sea_weather`), a spray material left after Off.

**Tested and measured** (web machine, 4 cores, no graphics card):
- Local: `test_sea` 36, `test_weather_core` 21, `test_weather_sky` 13, `test_weather_look` + `_fx` 23, `test_weather` 15,
  `test_weather_independent` 64, `test_vessel_motion` 30, `test_surroundings` 76 – 213 + 64 pass together; `test_tour`
  64 pass (3 new stops: build, Go, check); tooltip check 714 / 0 missing; precheck green.
- Sea (invented 124 m vessel, Rough, Detailed, Overcast, vessel motion, Draft 640×360): Cycles CPU top 41.4 → 47.4 s
  (+15 %), horizon 27.0 → 36.0 s (+33 %); EEVEE (software GL) 15.9 → 11.7 s. White caps measured vs Monahan: Bft 3
  0.055 % / 0.060 %, Bft 6 1.88 % / 2.0 %, Bft 9 16.1 % / 15.9 %, Bft 10 27.0 % / 27.0 %. Hs Calm 0.43 m, Rough 2.31 m.
- Sky (test crane on the quay, Cycles CPU Draft 960×540): noon 70.4 s, fog 400 m 70.2 s (compositor: no measurable
  cost; a world volume instead: +47 % and black), night with floodlights 69–82 s vs 38–45 s without.
- Looks (spool test model on the quay, CPU seconds, machine shared): weather on but nothing wet/snowy +2 %; wet 1 +34 %;
  snow layer 0.7 +57 %; rain 0.6 with wet +86–95 %; falling snow +31 %; flag +2 %. EEVEE (software GL) wet/snow ~0.
- Pictures: `tasks/img/0109_sea_before_after.jpg` (the owner's view: stripes before, patchy white caps + hull foam after),
  `0109_sea_horizon.jpg`, `0109_time_of_day.jpg`, `0109_wet_snow.jpg`, `0109_presets.jpg`.
- Presets contact sheet (`0109_presets.jpg`, Cycles CPU Draft 480×270, 24 samples): demo vessel 5.2–8.3 s, test mill
  3.2–6.4 s per tile. It showed the mill's Night shift lit like day: the mast heads' glow lit a small model's quay at
  +4 EV – the heads now glow without lighting the scene (mill night/day screen brightness 0.20 / 0.59, 0.13 without
  floodlights; `0109_mill_night_fixed.jpg`; the sheet's mill night tile is from before the fix). Also fixed from it: the
  panel header (title overlapped), Visibility shown in mm, the cut-off wind button.
- Merging main (0.2.86 web 3D surroundings, 0.2.87 tracks): the page drew the old sea's formula; it now gets the waves
  the app draws (none < 1 m, a short wave fading out at 5–8 of its lengths) – Python formula, page formula and shader;
  its white caps keep the crest rule of before (`SEA[state]["page_foam"]`). `test_web3d*` 37 pass.
- GitHub: 2 full runs on the branch – the first with the guide picture still missing and the PC-check "since" ahead of
  the version (expected), the second green (below); merged by fast-forward.
- Windows-only code: none.

**Open points / follow-up tasks:**
1. **Owner, on the RTX 3090:** EEVEE – the sky's sun gave no direct sunlight under software GL here, floodlights
   weaker than in Cycles; if so on the GPU: a Sun lamp driven by `sun_el/sun_az/sun` for EEVEE (small follow-up).
2. Fog shows in Live preview only with the viewport compositor on; stills, the queue and videos have it.
3. EEVEE's AO only sees what is on screen: a roof keeps less snow off in EEVEE than in Cycles. Wet does not check
   for a roof (only snow does).
4. Falling snow is faint at Draft distance; streaks of foam along the wind at Bft 8–9 are faint (`STREAK_MAX`);
   the white-cap patches are a little blob-shaped – owner to judge.
5. The waves keep the wind of the video's start (a step changes white caps, spray, rain, snow – not the wave heights);
   vessel motion holds Rough's numbers above Bft 6. Splash spots and the roof test are taken when the weather is set
   (a part that moves later keeps its spots).
6. Lamp powers set by eye from renders; the flag stands beside the back-right corner on Quay/Deck.
7. Web 3D: the later task brings the weather and the new white caps onto the page (it has the new waves already;
   `SEA[state]["foam"]` is now the new threshold, the page reads `page_foam`).
8. Falling rain reads at Draft distance mostly as a fine dotted texture (Storm); the white caps at Bft 9 have hard
   edges – owner to judge on his PC.
