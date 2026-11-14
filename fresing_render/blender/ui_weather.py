"""Side panel: 5 Scene & Render > Weather & time (task 0109). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core import weather as core
from . import build, weather
from .ui import _has_model, _Panel, fold, header_status, split_props, steps, wrap

PLACE_WORDS = {
    "photo": "With a 360° photo the photo keeps its own sun and sky: the time of day and the clouds are not used. Rain, "
             "snow, wind and the wet look work.",
    "indoor": "Indoors (studios, halls, a plain background) nothing falls and the sky is not seen: only work lights "
              "are used. Pick the Open sea, the Vessel deck, the Quayside or Sky under Background & surroundings for "
              "the weather.",
}


_LIGHTS: dict = {"key": None, "n": 0, "at": 0.0}
LIGHTS_AGE = 2.0                       # s: kept between redraws (an undo can change it behind our back)


def light_count(scene) -> int:
    """How many work lights, for the fold's title. Looking walks every object (0.76 ms on the demo) and the panel
    redraws every frame while playing (bug hunt 0118 row 18a): kept until objects come or go, at most 2 s."""
    import time
    from . import weather_sky
    key = (scene.name, len(scene.objects))
    now = time.monotonic()
    if _LIGHTS["key"] != key or now - _LIGHTS["at"] > LIGHTS_AGE:
        _LIGHTS.update(key=key, n=len(weather_sky.work_lights(scene)), at=now)
    return _LIGHTS["n"]


def _work_lights(layout, context) -> None:
    from . import weather_sky
    scene = context.scene
    n = light_count(scene)
    body = fold(layout, "fr_weather_work", f"Work lights ({n})" if n else "Work lights", "LIGHT_SPOT")
    if not body:
        return
    lights = weather_sky.work_lights(scene)            # the fold is open: the lights themselves
    wrap(body, context, "Select a part (a lamp on the machine), then make it a light:")
    row = body.row(align=True)
    row.operator("fresing.work_light_add", text="Spot", icon="LIGHT_SPOT").kind = "SPOT"
    row.operator("fresing.work_light_add", text="Flood", icon="LIGHT_AREA").kind = "FLOOD"
    for ob in lights[:12]:
        box = body.box()
        row = box.row(align=True)
        part = ob.parent
        row.label(text=(part.get(build.PROP_NAME) or part.name) if part is not None else ob.name,
                  icon="LIGHT_SPOT" if ob.data.type == "SPOT" else "LIGHT_AREA")
        row.operator("fresing.work_light_remove", text="", icon="X").light = ob.name
        row = box.row(align=True)
        row.prop(ob.data, "color", text="")
        row.prop(ob.data, "energy", text="Power")
        if ob.data.type == "SPOT":
            box.prop(ob.data, "spot_size", text="Beam")
    if len(lights) > 12:
        body.label(text=f"… and {len(lights) - 12} more", icon="BLANK1")


class FRESING_PT_weather(_Panel, bpy.types.Panel):
    bl_label = "Weather & time"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="OUTLINER_DATA_LIGHTPROBE")

    def draw_header_preset(self, context):
        header_status(self.layout, weather.short(context.scene))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        w = s.weather
        layout.prop(w, "enabled", text="Weather & time")
        if not w.enabled:
            steps(layout, context, ["Tick 'Weather & time'",
                                    "Pick a preset (Clear day, Grey North Sea, Storm, Snow at the quay, Night shift)",
                                    "Set the clock and the weather; Live preview shows it",
                                    "For a video: 6 Animation > a Weather & time step (day to dusk, rain starting)"])
            _work_lights(layout, context)
            return
        where = weather.place(scene)
        col = split_props(layout)
        col.prop(w, "preset", text="Preset")
        if where in PLACE_WORDS:
            wrap(layout, context, PLACE_WORDS[where], icon="INFO")
        st = weather.state(scene)

        # -- time of day
        if where == "sky":
            el, _az = core.sun_of(st)
            layout.label(text=f"Time  {core.clock(w.hour)}  ({core.part_of_day(el, w.hour)}, sun {el:.0f}°)",
                         icon="TIME")
            col = split_props(layout)
            col.prop(w, "hour", text="Time")
            col.prop(w, "north", text="North")
            body = fold(layout, "fr_weather_date", "Date and place", "WORLD")
            if body:
                col = split_props(body)
                col.prop(w, "use_date", text="Real sun path")
                sub = col.column(align=True)
                sub.active = w.use_date
                sub.prop(w, "day", text="Day of the year")
                sub.prop(w, "latitude", text="Latitude")
                rs = core.sunrise_sunset(st.day if st.use_date else core.EQUINOX_DAY, st.latitude)
                text = (f"Sunrise {core.clock(rs[0])}, sunset {core.clock(rs[1])} (sun time)" if rs else
                        "The sun does not rise or set on this day here")
                body.label(text=text, icon="BLANK1")

            # -- sky
            layout.label(text="Sky", icon="OUTLINER_DATA_VOLUME")
            col = split_props(layout)
            col.prop(w, "clouds", text="Clouds")
            col.prop(w, "low_clouds", text="Low clouds")
            col.prop(w, "visibility", text="Visibility (m)")
            layout.label(text=core.visibility_words(w.visibility).capitalize(), icon="BLANK1")
        if where == "indoor":
            _work_lights(layout, context)
            return

        # -- rain and snow
        layout.label(text="Rain and snow", icon="MOD_FLUIDSIM")
        col = split_props(layout)
        col.prop(w, "rain", text="Rain")
        sub = col.column(align=True)
        sub.active = w.rain > 0.0
        sub.prop(w, "drop_size", text="Drop size (mm)")
        col.prop(w, "wet", text="Wet")
        col.prop(w, "snow", text="Snow")
        col.prop(w, "snow_cover", text="Snow layer")

        # -- wind
        layout.label(text=f"Wind  Bft {w.wind:.0f} {core.bft_name(w.wind).lower()}, "
                          f"{core.bft_to_ms(w.wind):.0f} m/s", icon="FORCE_WIND")
        col = split_props(layout)
        col.prop(w, "wind", text="Beaufort")
        col.prop(w, "wind_from", text="From")
        col.prop(w, "wind_ref", text="Measured")
        row = layout.row(align=True)
        row.prop(w, "spray", text="Spray")
        row.prop(w, "flag", text="Flag")
        if s.background in ("SEA", "DECK", "QUAY") and s.sea_state != "WIND":
            wrap(layout, context, "The sea has its own state (Calm / Rough): pick 'From the wind' under Background & "
                 "surroundings so the waves and white caps follow this wind.", icon="INFO")
        if s.background in ("SEA", "DECK"):
            col = split_props(layout)
            col.prop(w, "vessel_speed", text="Vessel speed (kn)")
            col.prop(w, "bow", text="Bow")

        # -- night
        if where == "sky":
            body = fold(layout, "fr_weather_night", "Night lights", "LIGHT_SUN")
            if body:
                col = split_props(body)
                col.prop(w, "floodlights", text="Floodlights")
                col.prop(w, "flood_strength", text="Strength")
                if s.background not in ("SEA", "DECK", "QUAY"):
                    wrap(body, context, "Floodlights are set up on the Open sea, the Vessel deck and the Quayside.",
                         icon="INFO")
        _work_lights(layout, context)
        wrap(layout, context, "A video can change the weather: 6 Animation > add a Weather & time step.",
             icon="RENDER_ANIMATION")


PANELS = (FRESING_PT_weather,)
CLASSES = PANELS
