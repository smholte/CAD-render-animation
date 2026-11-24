# 0299 – Weather round 2: thunderstorm, fog / sea mist, sunrise and sunset, hail / sleet, hot and calm; change the weather in a few clicks

**Who:** worker · **Status:** running · **Branch:** `task/0299-weather-round-2`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "More weather options, like a thunderstorm. And how does
the current weather function work, should be very easy to change between weather and time for an animation using a few
clicks, with smooth animations."; owner's click box 23 Nov: also fog / sea mist, sunrise / sunset, hail / sleet, hot
and calm) · **Model:** Opus · effort High
**Area:** Scene & Render lane – `core/weather.py` (`PRESETS`, `State`), `core/weather_fx.py`, `blender/world.py`,
`blender/ops_weather.py`, the Weather & time panel, the "Weather & time" step (`animation.py` additively, `props.py`
additively); tests, PC check (+ Heavy if a preset is costly), tour, guide, CHANGELOG.
**Not:** the sea's own solver (read the wind as today), vessel motion, the web 3D page's weather (0115 reserved).

## Background

0109: five presets (Clear day, Grey North Sea, Storm, Snow at the quay, Night shift) and settings (time of day, clouds,
low clouds, visibility, rain, drop size, wet, snow, snow cover, wind, floodlights) in 5 Scene & Render > Weather & time;
the animation step **Weather & time** (6 Animation) changes them over the step's duration.

## What to do

1. **New presets**, each with a thumbnail: **Thunderstorm** – dark storm clouds, heavy rain, lightning: bolts in the sky
   at a distance and flashes that light the whole scene for a few frames (random, or at set moments in an animation;
   thunder in a video only if cheap – say); **Fog / sea mist** – visibility 50–300 m, height fog over water, the
   machine fading in and out; **Sunrise** and **Sunset** – golden low sun, long shadows; **Hail / sleet** – hail
   bouncing on surfaces, wet grey; **Hot and calm** – bright haze, a heat shimmer above hot surfaces (only if it is
   affordable), flat sea.
2. **A few clicks in an animation:** in Weather & time, **Change to ▸ [preset] over [5 s] at the playhead** adds (or
   edits) a Weather & time step at the current frame; the steps list shows the weather blocks; a second change later in
   the same animation in two clicks.
3. **Smooth:** every value blends over the step – rain starting / stopping, snow cover growing, fog rolling in,
   lightning fading out, the sun moving with the time of day. Find today's jumps and fix them.
4. **How it works:** the guide explains the weather function step by step (the owner asked); a Learning hub stop /
   lesson step for Weather.
5. Render cost per preset (Cycles Draft / Final, EEVEE) on the web machine in the report.

## Done when

- [ ] Tests: every preset's values; a Change to step blends without a jump (sampled per frame); lightning only within
      its step; save + reopen
- [ ] PC check line per new preset (a picture each); tour stops; function entries; guide + pictures; full suite +
      GitHub run green; report; merged, version, release

## Design (worker, 24 Nov 2026)

**Four new weather values** in `core/weather.State` (0 … 1, all blend in a step, all keyed as channels):
`lightning` (how often flashes come), `mist` (height fog over the water / ground), `hail` (falling hail that bounces),
`heat` (hot haze + heat shimmer). Channels `lightning`, `flash` (0 … 1, the flash now), `bolt` (which of 4 bolts),
`mist` (per km at the surface), `hail`, `heat`.

**Presets** (old numbers 1–5 kept in files, new ones 6–11): Thunderstorm, Fog / sea mist, Sunrise, Sunset,
Hail / sleet, Hot and calm. Each has a **thumbnail** drawn from its own channels (`core/weather_thumbs.py`, NumPy, no
picture files) shown as a picture grid in the panel (`fresing.weather_preset`).

**Lightning** (`core/weather_fx.flash_track`): a seeded schedule per frame – random flashes while `lightning` > 0
(more often and brighter the higher it is), plus flashes at set moments of a step (`wx_flash_at`, seconds). Each flash
flickers over ~0.2 s (return strokes). Keyed at Build into `flash` / `bolt`; nothing per frame in Python. What shows a
flash: a Sun lamp (`weather_sky`, energy = flash), the sky lit from inside the clouds (world shader), 4 bolt meshes
~900 m away round the camera's view (emission only while their bolt flashes, see-through otherwise). A still picture:
the panel's "Flash in this picture".

**Mist** (`weather_sky` compositor): density `mist · exp(-(z - ground) / 25 m)` integrated along each pixel's ray
(Position pass + the camera's height by a driver), drifting banks = noise on the hit point moving with the wind
(the machine fades in and out). **Heat shimmer**: the compositor's Displace by an animated noise, growing with
distance. **Hail**: a third falling kind (ice balls, Matson & Huggins 1980 fall speed) and stones that bounce on the
top faces (the splash spots).

**Change to ▸ [preset] over [N s] at the playhead** (`fresing.weather_change`): adds a Weather & time step at the
playhead (or edits the one that starts there) in the active animation (made when there is none), easing Smooth.

**Jumps found** (every channel sampled per frame, all preset pairs): when a step runs the clock through sunrise or
sunset the direct sun, daylight and floodlights switched in 1–3 frames (12 h in 5 s). Fix: the clock runs slower where
the light changes most (`core.weather.clock_at`: equal change of light per frame). A test samples every channel of
every preset pair per frame.

**Lesson**: `blender/lessons/weather.py` on the tour set "weather" (import, Weather & time on, a preset, Change to
Thunderstorm); `tour.build_weather` runs it first.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 24 Nov 2026 – version 0.2.223.

**What changed:**
- Six new presets (Thunderstorm, Fog / sea mist, Sunrise, Sunset, Hail / sleet, Hot and calm); old presets keep their
  numbers in project files. Each preset is a **picture** in a grid (fold "Presets"), drawn from its own values
  (`core/weather_thumbs.py`, no picture files).
- New values `lightning`, `mist`, `hail`, `heat` (panel, saved scenes, the Weather & time step with `Flash at`, drop
  size too). Lightning: a seeded flash schedule keyed at Build (random while lightning > 0, set moments; ~0.2 s flicker),
  a Sun lamp, the clouds lit, 4 bolt meshes ~900 m away round the camera's view. Still pictures: "Flash in the
  picture". Sea mist = height fog (25 m scale) along each pixel's ray (Position pass + camera height by driver) with
  drifting banks; heat shimmer = compositor Displace growing with distance; hail = falling stones (Matson & Huggins
  fall speed) + stones hopping on the top faces.
- **Change to ▸ preset over N s ▸ Add at playhead** (`fresing.weather_change`): adds or edits the Weather & time step
  at the playhead, makes an animation "Weather" when there is none; a change to lightning gets one set flash at 80 %.
- **Jumps found and fixed** (every channel per frame, all 110 preset pairs, 5 s at 25 fps): the clock ran through
  sunset at constant speed, so the direct sun / daylight / floodlights switched in 1–3 frames (60 % of the change in one
  frame). Now the clock slows where the light changes and keeps the sun's movement even (largest frame step 11 % of a
  change, the sun ≤ 2° per frame); it goes the shorter way round (15:00 → 14:00 no longer runs through a night); a
  date change blends day by day; new steps are Smooth. Also: the white-cap number cost 0.1 s per new wind value
  (12 s of a Build with changing wind) – now exact on half Beaufort, straight between.
- Weather lesson (`lessons/weather.py`, 4 steps; the tour's weather set runs it first), 6 tour stops (`wx_*`), 6 PC
  check lines (`weather.thunderstorm`, `.mist`, `.sunrise`, `.sunset`, `.hail`, `.heat`), 6 function entries, the guide
  (step by step + anchors, new panel picture), CHANGELOG.

**Tested and measured** (4-core web machine, test crane on the quay, 640 x 360, processor):
- Local: weather, lessons, functions, places, tour versions, guide, CI tools, tour clash (weather set): 577 passed;
  the tour's weather/lesson stops: 14 passed; the 8 weather PC check lines OK (pictures looked at).
- Render time per preset (Cycles Draft / Final, s): no weather 2.1 / 46.3 · Clear day 2.2 / 53.0 · Sunrise 2.7 / 21.0
  · Sunset 2.3 / 19.1 · Sea mist 2.8 / 37.6 · Thunderstorm (with flash) 3.7 / 83.9 · Hail / sleet 5.2 / 75.3 · Hot and
  calm 2.0 / 40.4. EEVEE here runs on software OpenGL (no graphics card), so its times only compare with each other:
  26.6 / 50.7 / 142.6 / 24.7 / 46.5 / 299.2 / 137.3 / 27.8 s in the same order (rain and hail streaks are the cost);
  all pictures right (bolt, flash, mist, hail).
- Independent tester (a subagent that did not write the code, 278 tests in
  `tests/test_weather_round2_independent.py`): found 3 faults – a date change switched the sun half way (sun 7.9° →
  50.9° in one step), the clock could return 24.0, flash_track with fps 0 gave NaN – all fixed, all its tests pass.
- GitHub runs: see below.

**Open points / follow-up tasks:**
- No Heavy line: the new presets cost like Storm / Snow (already in heavy.weather); Thunderstorm and Hail roughly 2x
  Clear day in Final on this model.
- Thunder sound in a video: not done (not cheap: the video's sound track is the Music step's).
- Hot and calm makes the sea flat only when the sea follows the wind (Background & surroundings > Sea: From the wind),
  as Storm's white water does; the preset does not switch the sea's state.
- Hail stones (8 mm) are small at the distance of a big machine: they show in close-ups; the grey wet look and the
  slush carry the hail in wide shots.
- EEVEE on the owner's graphics card and the heat shimmer on his PC: not measured here.

**Owner's check on your PC:**
1. Update, open a project with a model, 5 Scene & Render > Weather & time: tick it, pick Background Quayside or Open
   sea.
2. Click the pictures Sunrise, Sunset, Sea mist, Thunder, Hail / sleet, Hot, calm: the view changes each time.
3. Playhead at the start, Change to Thunderstorm, Over 5 s, Add at playhead; Build & play: the storm comes and a flash
   lights the scene at about 4 s.
4. Fresing > Learn… > Weather: Show me.
