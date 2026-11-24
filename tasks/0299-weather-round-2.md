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

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
