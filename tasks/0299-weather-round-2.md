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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
