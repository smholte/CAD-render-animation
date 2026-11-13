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
    out = set()
    for fc in _scene_curves(scene):
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
    path = f'["{core.prop(name)}"]'
    for fc in _scene_curves(scene):
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
            if not keyed(scene):
                clear_channels(scene)
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


# ---------------------------------------------------------------------------
# the Weather & time step of 6 Animation
# ---------------------------------------------------------------------------

STEP_FIELDS = (("wx_hour", "hour"), ("wx_clouds", "clouds"), ("wx_low_clouds", "low_clouds"),
               ("wx_visibility", "visibility"), ("wx_rain", "rain"), ("wx_wet", "wet"), ("wx_snow", "snow"),
               ("wx_snow_cover", "snow_cover"), ("wx_wind", "wind"), ("wx_wind_from", "wind_from"))
STEP_TAG = "fr_weather_keys"          # on the scene: a Build keyed its channels


def step_state(start: core.State, b) -> core.State:
    """The weather at the end of a Weather & time step that starts from ``start``."""
    from dataclasses import replace
    return replace(start, **{k: float(getattr(b, f)) for f, k in STEP_FIELDS})


def put_step(b, st: core.State) -> None:
    for f, k in STEP_FIELDS:
        setattr(b, f, getattr(st, k))


def state_before(scene, anim, b) -> core.State:
    """The weather a step starts from: the panel's, changed by the Weather & time steps before it."""
    st = state(scene)
    for o in sorted((x for x in anim.blocks if x.enabled and x.kind == "WEATHER"), key=lambda x: x.start):
        if o == b or o.start > b.start:
            break
        st = step_state(st, o)
    return st


def step_init(scene, anim, b) -> None:
    """A new step: it starts out as the weather before it (change what should change)."""
    put_step(b, state_before(scene, anim, b))


def step_from_preset(scene, b, name: str) -> None:
    put_step(b, core.preset(name, state(scene)))


def step_label(b) -> str:
    bits = [core.clock(b.wx_hour)]
    if b.wx_rain > 0.01:
        bits.append("rain")
    if b.wx_snow > 0.01:
        bits.append("snow")
    if b.wx_visibility < 4000.0:
        bits.append("fog" if b.wx_visibility < 1000.0 else "mist")
    return "Weather to " + ", ".join(bits)


def _scene_curves(scene) -> list:
    ad = scene.animation_data
    act = ad.action if ad is not None else None
    if act is None:
        return []
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                out += list(bag.fcurves)
    return out


def bake(scene, anim, blocks, frame_of, ease) -> list[str]:
    """Keys of the Weather & time steps: every channel, every frame of a step (the clock, the sun and the fog
    change non-linearly), constant before and after. Returns warnings."""
    if not blocks:
        return []
    from . import animation
    warnings = []
    w = settings(scene)
    if not w.enabled:
        w.enabled = True                     # (switched on: the step needs the weather)
        warnings.append("Weather & time was off: the Weather & time step switched it on (5 Scene & Render)")
    where = place(scene)
    if where == "indoor":
        warnings.append("The Weather & time steps change little indoors: pick the Open sea, the Vessel deck, the "
                        "Quayside or Sky as the background")
    cur = state(scene)
    rows = {n: [] for n in core.CHANNEL_NAMES}

    def put(f, st, interp="LINEAR"):
        for n, v in core.derive(st, where).items():
            rows[n].append((f, v, interp, "AUTO"))

    put(1, cur)
    for b in sorted(blocks, key=lambda x: x.start):
        f0, f1 = frame_of(b.start), frame_of(b.start + b.duration)
        f1 = max(f1, f0 + 1)
        end = step_state(cur, b)
        for f in range(max(f0, 2), f1 + 1):
            put(f, core.mix(cur, end, ease(b.easing, (f - f0) / (f1 - f0))))
        cur = end
    write_channels(scene, core.derive(state(scene), where))
    cb = animation._channelbag(scene, "SCENE")
    for n, keys in rows.items():
        values = [k[1] for k in keys]
        if max(values) - min(values) < 1e-9:
            continue                         # stays the same: no keys
        keys = [k for i, k in enumerate(keys) if i in (0, len(keys) - 1)
                or abs(k[1] - keys[i - 1][1]) > 1e-9 or abs(k[1] - keys[i + 1][1]) > 1e-9]
        animation._write(cb, f'["{core.prop(n)}"]', 0, keys)
    scene[STEP_TAG] = True
    after_world(scene)                       # rain / snow objects exist while any frame has rain or snow
    return warnings


def after_clear(scene) -> None:
    """'Clear keys': the channels go back to the panel's weather."""
    if not scene.get(STEP_TAG):
        return
    del scene[STEP_TAG]
    ad = scene.animation_data
    if ad is not None and ad.action is not None:
        ad.action = None
    if enabled(scene):
        write_channels(scene, channels(scene))
        after_world(scene)
