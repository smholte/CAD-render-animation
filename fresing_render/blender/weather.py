"""Weather and time of day (task 0109): the coordinator.

The settings live in ``scene.fresing.weather`` (``props.FRWeather``); ``core/weather.py`` turns them into the
scene's **channels** – plain custom properties ``scene["fr_wx_<name>"]`` – and every part that shows weather reads
only those (View Layer attributes in shaders, simple-expression drivers elsewhere), so a *Weather & time* animation
step only keys the channels (scripts off, render queue, every paint scheme):

    weather_sky.py    the sky by the clock, clouds, haze and fog, stars and the moon, floodlights, work lights
    weather_look.py   the "FR weather" node group in every look: wet (darker, glossy, drops, streaks, puddles),
                      the snow layer on upward faces under the open sky
    weather_fx.py     falling rain and snow, splashes, the flag
    surroundings.py   the sea: waves and white caps from the wind (core/sea.py), hull foam, wake, spray

Off (``enabled`` False): no channels, no node group, no lamps, no rain or snow objects – the scene is exactly as
without this task (only the sea itself is new).
"""

from __future__ import annotations

import bpy

from ..core import weather as core

PROPS = ("hour", "use_date", "day", "latitude", "north", "clouds", "low_clouds", "visibility", "rain", "drop_size",
         "wet", "snow", "snow_cover", "wind", "wind_from", "wind_ref", "floodlights", "flood_strength")
EXTRA = ("spray", "flag", "vessel_speed")            # weather settings that are not part of a State (no fading)
_STATE = {"busy": False}


def settings(scene):
    return scene.fresing.weather


def enabled(scene) -> bool:
    return bool(scene is not None and scene.fresing.weather.enabled)


def place(scene) -> str:
    """'sky', 'photo' or 'indoor' (core.weather.where)."""
    return core.where(scene.fresing.background)


def sky_on(scene) -> bool:
    """The weather draws the sky (time of day, clouds): on, and outdoors under the app's own sky."""
    return enabled(scene) and place(scene) == "sky"


def state(scene) -> core.State:
    w = settings(scene)
    return core.State(**{k: (int(getattr(w, k)) if k == "day" else
                             getattr(w, k) if k in ("use_date", "wind_ref", "floodlights") else float(getattr(w, k)))
                         for k in PROPS})


def put_state(scene, st: core.State) -> None:
    """Set the panel's controls to ``st`` (one update at the end)."""
    w = settings(scene)
    w["_preset_busy"] = True
    w["_busy"] = True
    try:
        for k in PROPS:
            setattr(w, k, getattr(st, k))
    finally:
        del w["_busy"]
        del w["_preset_busy"]


def channels(scene, st: core.State | None = None) -> dict:
    return core.derive(st or state(scene), place(scene))


def keyed(scene) -> set:
    """Names of the channels an animation keys (a Weather & time step was built)."""
    ad = scene.animation_data
    act = ad.action if ad is not None else None
    out = set()
    if act is None:
        return out
    try:
        from . import animation
        curves = animation._all_fcurves(act) if hasattr(animation, "_all_fcurves") else act.fcurves
    except Exception:
        curves = getattr(act, "fcurves", ())
    for fc in curves:
        p = fc.data_path
        if p.startswith('["' + core.PREFIX) and p.endswith('"]'):
            out.add(p[2 + len(core.PREFIX):-2])
    return out


def write_channels(scene, ch: dict) -> None:
    """The channels as the scene's custom properties (the keyed ones are left to their keys)."""
    skip = keyed(scene)
    for name, v in ch.items():
        if name in skip:
            continue
        key = core.prop(name)
        if scene.get(key) != v:
            scene[key] = float(v)
            lo, hi, text = core.CHANNELS[name]
            try:                     # wide limits: Blender clamps keyed values to a property's min/max
                scene.id_properties_ui(key).update(min=-1.0e6, max=1.0e6, soft_min=lo, soft_max=hi, description=text)
            except (TypeError, KeyError):
                pass


def clear_channels(scene) -> None:
    for name in core.CHANNEL_NAMES:
        key = core.prop(name)
        if key in scene:
            del scene[key]


def peak(scene, name: str) -> float:
    """The largest value a channel takes: now, or anywhere in a built animation (rain or snow objects are needed
    while any frame has rain or snow)."""
    v = float(scene.get(core.prop(name), 0.0))
    ad = scene.animation_data
    act = ad.action if ad is not None else None
    if act is not None:
        path = f'["{core.prop(name)}"]'
        for fc in getattr(act, "fcurves", ()) or ():
            if fc.data_path == path:
                v = max([v] + [k.co[1] for k in fc.keyframe_points])
    return v


# ---------------------------------------------------------------------------
# the parts
# ---------------------------------------------------------------------------

def _parts():
    from . import weather_fx, weather_look, weather_sky
    return weather_sky, weather_look, weather_fx


def after_world(scene) -> None:
    """Called at the end of ``world.apply``: the lamps, looks and falling things follow the channels."""
    if _STATE["busy"]:
        return
    _STATE["busy"] = True
    try:
        sky, look, fx = _parts()
        if not enabled(scene):
            sky.remove(scene)
            look.apply(scene, False)
            fx.remove(scene)
            return
        st = state(scene)
        where = place(scene)
        write_channels(scene, channels(scene, st))
        sky.apply(scene, st, where)
        look.apply(scene, True)
        fx.apply(scene, st, where)
    finally:
        _STATE["busy"] = False


def changed(scene) -> None:
    """A weather control changed (or a preset was picked)."""
    if not enabled(scene):
        return
    write_channels(scene, channels(scene))
    _rebuild_world(scene)


def _rebuild_world(scene) -> None:
    s = scene.fresing
    if not s.live_update:
        return
    from . import world
    world.apply(scene, s)


def switched(scene) -> None:
    """Weather & time switched on or off."""
    w = settings(scene)
    if w.enabled and not w.get("fr_started"):
        # the first time: start from the project's own sky (Sun / Overcast, sun height, light rotation)
        s = scene.fresing
        from . import weather_sky
        st = core.from_old(s.sun_elevation, s.light_rotation, s.sky_weather == "OVERCAST",
                           weather_sky.SUN_ROTATION_ZERO_AZ)
        put_state(scene, st)
        w["fr_started"] = True
    if w.enabled:
        write_channels(scene, channels(scene))
    else:
        clear_channels(scene)
    _rebuild_world(scene)
    if not scene.fresing.live_update:          # (the world is not rebuilt: tidy up anyway)
        after_world(scene)


def use_preset(scene, name: str) -> None:
    st = core.preset(name, state(scene))
    put_state(scene, st)
    w = settings(scene)
    w["_busy"] = True
    try:
        w.preset = name
    finally:
        del w["_busy"]
    changed(scene)


def header(scene) -> str:
    if not enabled(scene):
        return "Off"
    return core.words(state(scene), place(scene))
