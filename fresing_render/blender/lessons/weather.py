"""The weather lesson (task 0299): the test crane on the quay – Weather & time on, a preset from its picture, a change
to a thunderstorm in a video at the playhead. 4 steps.

The test tour's set "Weather and time of day" runs these steps first (``tour.build_weather``): its stop "Thunderstorm
in a video" plays the animation the lesson made. Each ``do`` is the button's own call.
"""

from __future__ import annotations

import bpy

from ..lesson import Lesson, Step, import_model, lesson

PRESET = "GREY_NORTH_SEA"
CHANGE_TO = "THUNDERSTORM"
CHANGE_SECONDS = 4.0
ANIM = "Weather"                       # the animation Add at playhead makes (weather.CHANGE_ANIM)


def _on(scene):
    """Tick Weather & time, on the Quayside (the weather shows outdoors)."""
    s = scene.fresing
    s.env_detail = "SIMPLE"
    s.background = "QUAY"
    s.weather.enabled = True


def _preset(scene):
    res = bpy.ops.fresing.weather_preset(name=PRESET)
    if res != {"FINISHED"}:
        raise RuntimeError(f"the preset button returned {res}")


def _change(scene):
    w = scene.fresing.weather
    w.change_to = CHANGE_TO
    w.change_seconds = CHANGE_SECONDS
    scene.frame_set(scene.frame_start)
    res = bpy.ops.fresing.weather_change()
    if res != {"FINISHED"}:
        raise RuntimeError(f"Add at playhead returned {res}")


def _has_change(scene) -> bool:
    return any(b.kind == "WEATHER" and b.wx_lightning > 0.0 for a in scene.fresing.animations for b in a.blocks)


WEATHER = lesson(Lesson(
    "weather", "Weather: a storm rolls in",
    "Weather & time on the quay, a ready-made weather from its picture, a change to a thunderstorm at the playhead",
    [
        Step("import.step", "Import the model",
             "Import STEP… read the test crane. It stands still, every part in its CAD place.",
             more="The weather works outdoors: on the Open sea, the Vessel deck, the Quayside and Sky.",
             do=import_model("weather"), done=lambda sc: sc.fresing.model_count > 0),
        Step("scene.weather", "Weather & time on",
             "Tick Weather & time (5 Scene & Render). The crane stands on the quay; the sky follows the clock.",
             more="Unticked, everything looks exactly as without it. The first time it starts from your own sky, so "
                  "nothing jumps.",
             do=_on, done=lambda sc: bool(sc.fresing.weather.enabled)),
        Step("scene.weather_presets", "Pick a weather",
             "Click the picture Grey sea: overcast, a strong breeze, drizzle; the crane gets wet.",
             more="A preset sets every value below it (clock, clouds, rain, wind …). Change any of them afterwards: "
                  "the preset then reads Own settings.",
             do=_preset, done=lambda sc: sc.fresing.weather.enabled and sc.fresing.weather.preset != "CUSTOM"),
        Step("animation.weather_change", "A storm rolls in, in a video",
             f"With the playhead at the start: Change to Thunderstorm, over {CHANGE_SECONDS:g} s, then Add at "
             "playhead. Build & play shows the storm coming, lightning flashing.",
             more="Add at playhead puts a Weather & time step in the animation (it makes one when there is none). "
                  "Move the playhead later and add another change: the storm can pass again.",
             do=_change, done=_has_change,
             point={"panel": "FRESING_PT_weather", "button": "fresing.weather_change", "text": "Add at playhead"}),
    ]))
