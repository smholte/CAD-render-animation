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

## Not in this task

The web page (a later Web 3D task). Cables / hoses / flex parts moving in the wind. Lightning, hail. Changing the
Looks lane's materials beyond the one hook. Real weather data from the internet.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
