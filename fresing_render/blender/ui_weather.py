"""Side panel: 5 Scene & Render > Weather & time (task 0109). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core import weather as core
from . import build, weather
from .ui import _has_model, _Panel, fold, gap, header_status, hint, split_props, steps, wrap

PLACE_WORDS = {
    "photo": "With a 360° photo the photo keeps its own sun and sky: the time of day and the clouds are not used. Rain, "
             "snow, wind and the wet look work.",
    "indoor": "Indoors (studios, halls, a plain background) nothing falls and the sky is not seen: only work lights "
              "are used. Pick the Open sea, the Vessel deck, the Quayside or Sky under Background & surroundings for "
              "the weather.",
}


# the presets' pictures (task 0299): drawn once from their numbers (core/weather_thumbs.py), kept as preview icons
SHORT = {"CLEAR_DAY": "Clear day", "SUNRISE": "Sunrise", "SUNSET": "Sunset", "GREY_NORTH_SEA": "Grey sea",
         "SEA_MIST": "Sea mist", "STORM": "Storm", "THUNDERSTORM": "Thunder", "HAIL": "Hail / sleet",
         "SNOW_QUAY": "Snow", "HOT_CALM": "Hot, calm", "NIGHT_SHIFT": "Night shift"}
GRID_COLUMNS = 3
_THUMBS: dict = {}


def thumb(name: str) -> int:
    """The icon number of a preset's picture (0 when it cannot be made: a background Blender)."""
    try:
        coll = _THUMBS.get("coll")
        if coll is None:
            from bpy.utils import previews
            from ..core import weather_thumbs
            coll = previews.new()
            for key, img in weather_thumbs.presets().items():
                pv = coll.new(key)
                h, w = img.shape[:2]
                flat = weather_thumbs.for_blender(img)
                pv.image_size = (w, h)
                pv.image_pixels_float = flat
                pv.icon_size = (w, h)
                pv.icon_pixels_float = flat
            _THUMBS["coll"] = coll
        return coll[name].icon_id if name in coll else 0
    except Exception:  # noqa: BLE001 - a picture never stops the panel
        return 0


def free_thumbs() -> None:
    coll = _THUMBS.pop("coll", None)
    if coll is not None:
        from bpy.utils import previews
        previews.remove(coll)


def draw_presets(layout, w) -> None:
    """The presets as a grid of pictures, each with its button (the one in use pressed)."""
    flow = layout.grid_flow(row_major=True, columns=GRID_COLUMNS, even_columns=True, even_rows=True, align=True)
    for name in core.PRESET_ORDER:
        cell = flow.column(align=True)
        icon = thumb(name)
        if icon:
            cell.template_icon(icon_value=icon, scale=3.2)
        op = cell.operator("fresing.weather_preset", text=SHORT.get(name, core.PRESETS[name][0]),
                           depress=w.preset == name)
        op.name = name


def draw_change(layout, context) -> None:
    """Change to ▸ [preset] over [N s] at the playhead (task 0299): a Weather & time step in two clicks."""
    from . import weather
    scene = context.scene
    s = scene.fresing
    w = s.weather
    box = layout.box()
    box.label(text="Change in a video", icon="TIME")
    col = split_props(box)
    col.prop(w, "change_to", text="Change to")
    col.prop(w, "change_seconds", text="Over")
    box.operator("fresing.weather_change", text="Add at playhead", icon="ADD")
    anim = s.animations[s.animations_index] if 0 <= s.animations_index < len(s.animations) else None
    at = weather.seconds_at(anim, scene.frame_current) if anim is not None else (scene.frame_current - 1) / 25.0
    n = sum(1 for b in anim.blocks if b.kind == "WEATHER") if anim is not None else 0
    where_ = f"'{anim.name}'" if anim is not None else "a new animation 'Weather'"
    hint(box, context, f"At {at:.1f} s of {where_}" + (f" ({n} weather changes)" if n else "") +
         ". Then Build & play.", inset=12)


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
        steps(layout, context, ["Tick 'Weather & time'",
                                "Click a picture: a ready-made weather (sunrise, storm, sea mist, thunderstorm …)",
                                "Change the clock and any value; Live preview shows it",
                                "For a video: put the playhead where the weather should change, pick 'Change to' "
                                "and click Add at playhead; Build & play"],
              key="fr_how_weather", used=bool(w.enabled))
        gap(layout)
        layout.prop(w, "enabled", text="Weather & time")
        from .ops_scene import draw_start_scene             # Build puts the start scene's weather back (task 0160)
        draw_start_scene(layout, context, ["weather"])
        if not w.enabled:
            gap(layout)
            _work_lights(layout, context)
            return
        where = weather.place(scene)
        col = split_props(layout)
        col.prop(w, "preset", text="Preset")
        body = fold(layout, "fr_weather_presets", "Presets", "IMAGE_DATA", closed=False,
                    state=core.PRESETS[w.preset][0] if w.preset in core.PRESETS else "Own settings")
        if body:
            draw_presets(body, w)
        gap(layout)
        draw_change(layout, context)
        if where in PLACE_WORDS:
            wrap(layout, context, PLACE_WORDS[where], icon="INFO")
        st = weather.state(scene)

        # -- time of day
        if where == "sky":
            gap(layout)
            el, _az = core.sun_of(st)
            wrap(layout, context, f"Time  {core.clock(w.hour)}  ({core.part_of_day(el, w.hour)}, sun {el:.0f}°)",
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
                wrap(body, context, text, icon="BLANK1")

            # -- sky
            gap(layout)
            layout.label(text="Sky", icon="OUTLINER_DATA_VOLUME")
            col = split_props(layout)
            col.prop(w, "clouds", text="Clouds")
            col.prop(w, "low_clouds", text="Low clouds")
            col.prop(w, "visibility", text="Visibility (m)")
            col.prop(w, "mist", text="Sea mist")
            col.prop(w, "heat", text="Heat")
            layout.label(text=core.visibility_words(w.visibility).capitalize(), icon="BLANK1")
        if where == "indoor":
            gap(layout)
            _work_lights(layout, context)
            return

        # -- rain and snow
        gap(layout)
        layout.label(text="Rain, snow, hail, lightning", icon="MOD_FLUIDSIM")
        col = split_props(layout)
        col.prop(w, "rain", text="Rain")
        sub = col.column(align=True)
        sub.active = w.rain > 0.0
        sub.prop(w, "drop_size", text="Drop size (mm)")
        col.prop(w, "wet", text="Wet")
        col.prop(w, "snow", text="Snow")
        col.prop(w, "snow_cover", text="Snow layer")
        col.prop(w, "hail", text="Hail")
        if where == "sky":
            col.prop(w, "lightning", text="Lightning")
            sub = col.column(align=True)
            sub.active = w.lightning > 0.0
            sub.prop(w, "flash_still", text="Flash in the picture")

        # -- wind
        gap(layout)
        wrap(layout, context, f"Wind  Bft {w.wind:.0f} {core.bft_name(w.wind).lower()}, "
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
            col.prop(w, "vessel_speed", text="Vessel (kn)")         # "Vessel speed (kn)" was cut off
            col.prop(w, "bow", text="Bow")

        # -- night
        gap(layout)
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
        gap(layout)
        hint(layout, context, "A video can change the weather: Change in a video above, or 6 Animation > a Weather "
                              "& time step.")


PANELS = (FRESING_PT_weather,)
CLASSES = PANELS
