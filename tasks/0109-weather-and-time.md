# 0109 – Weather and time of day in the app: rain, snow, wind, fog and clouds, day to night

**Who:** worker · **Status:** open – can start · **Branch:** `task/0109-weather-and-time`
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
- 0106 copies `surroundings.SEA` and `_waves` into the web page. **Calm and Rough must give exactly today's sea**
  (same numbers, same seed) when the wind is left at "From the sea state"; wind settings add to them, they do not change
  the old formula.
- Patterns to reuse: per-part looks through one node group in the materials (Fade 0073, cutaway 0086 – scripts off,
  Cycles + EEVEE, queue); motion from simple-expression drivers or keys (vessel motion 0085), never Python per frame;
  chips / coolant drops worked out once per animation and the same every time (0028, 0042).
- Indoors (halls, studios): no rain, snow or wind; time of day only where a hall has windows or a sky shows (say it in
  the panel).

## Scope

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
5. **Snow:** falling flakes (amount, wind drift), a **snow layer on upward faces** (thickness, only where snow can
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

- [ ] Scope 1–9; Weather Off and old projects look exactly as before (picture check); Calm/Rough waves unchanged with
      the wind "From the sea state" (unit test on the heights 0106 copies).
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
