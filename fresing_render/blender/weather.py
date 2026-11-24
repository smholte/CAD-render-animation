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
from ..core import weather_fx as fx_core

PROPS = ("hour", "use_date", "day", "latitude", "north", "clouds", "low_clouds", "visibility", "rain", "drop_size",
         "wet", "snow", "snow_cover", "wind", "wind_from", "wind_ref", "floodlights", "flood_strength",
         "lightning", "mist", "hail", "heat")
EXTRA = ("spray", "flag", "vessel_speed", "flash_still")   # weather settings that are not part of a State (no fading)
STILL_FLASH = 0.9                  # 'Flash in the picture': how bright the flash of a still picture is
STILL_BOLT = 1.0                   # ... and which bolt it shows (one near the middle of the view)
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


def bow_az(scene) -> float:
    """Scene azimuth the vessel's bow points to (task 0125): the one source wind 'from the bow', the wake, the bow
    spray and the swell read (``surroundings.bow_az``)."""
    try:
        from . import surroundings
        return surroundings.bow_az(scene)
    except Exception:                        # (an older project being read)
        return core.BOW_AZ


def state(scene) -> core.State:
    w = settings(scene)
    return core.State(**{k: (int(getattr(w, k)) if k == "day" else
                             getattr(w, k) if k in ("use_date", "wind_ref", "floodlights") else float(getattr(w, k)))
                         for k in PROPS}, bow_az=bow_az(scene))


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
    if st is not None and st.bow_az != bow_az(scene):
        from dataclasses import replace
        st = replace(st, bow_az=bow_az(scene))
    ch = core.derive(st or state(scene), place(scene))
    if settings(scene).flash_still and ch["lightning"] > 0.0:      # task 0299: a still picture with a flash
        ch.update(flash=STILL_FLASH, bolt=STILL_BOLT)
    return ch


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


def _left_over(scene) -> bool:
    """Anything the weather made: channels, its node group, objects, the exposure or fog it set."""
    if any(k.startswith(core.PREFIX) for k in scene.keys()):
        return True
    if any(k.startswith("fr_weather") for k in scene.keys()):
        return True
    if bpy.data.node_groups.get("FR weather") is not None:
        return True
    return any(o.get("fr_weather") is not None for o in bpy.data.objects)


def after_world(scene) -> None:
    """Called at the end of ``world.apply``: the lamps, looks and falling things follow the channels."""
    if _STATE["busy"]:
        return
    _STATE["busy"] = True
    try:
        if not enabled(scene) and not _left_over(scene):
            return                           # (weather off and nothing of it in the file: every world.apply)
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


def short(scene) -> str:
    """The panel header: a few characters (the title must stay readable), e.g. '13:00 rain'."""
    if not enabled(scene):
        return "Off"
    st = state(scene)
    bits = [core.clock(st.hour)] if place(scene) == "sky" else []
    if place(scene) != "indoor":
        bits.append("lightning" if st.lightning > 0.01 else "hail" if st.hail > 0.01 else "snow" if st.snow > 0.01
                    else "rain" if st.rain > 0.01 else "mist" if st.mist > 0.01 or st.visibility < 1000.0
                    else "heat" if st.heat > 0.01 else "")
    return " ".join(b for b in bits if b) or "On"


def header(scene) -> str:
    if not enabled(scene):
        return "Off"
    return core.words(state(scene), place(scene))


# ---------------------------------------------------------------------------
# the Weather & time step of 6 Animation
# ---------------------------------------------------------------------------

STEP_FIELDS = (("wx_hour", "hour"), ("wx_clouds", "clouds"), ("wx_low_clouds", "low_clouds"),
               ("wx_visibility", "visibility"), ("wx_rain", "rain"), ("wx_wet", "wet"), ("wx_snow", "snow"),
               ("wx_snow_cover", "snow_cover"), ("wx_wind", "wind"), ("wx_wind_from", "wind_from"),
               ("wx_drop_size", "drop_size"), ("wx_lightning", "lightning"), ("wx_mist", "mist"), ("wx_hail", "hail"),
               ("wx_heat", "heat"))
# task 0299: the fields a step saved before 0.2.<this> did not have; such a step keeps the weather before it there
# (its own value would be the property's default, e.g. drop size 2 mm or no mist, and would change it)
NEW_STEP_FIELDS = ("wx_drop_size", "wx_lightning", "wx_mist", "wx_hail", "wx_heat")
STEP_VERSION = "fr_wx_v"              # on a step: 2 = it has the fields of task 0299
STEP_TAG = "fr_weather_keys"          # on the scene: a Build keyed its channels


def step_state(start: core.State, b) -> core.State:
    """The weather at the end of a Weather & time step that starts from ``start``."""
    from dataclasses import replace
    new = int(b.get(STEP_VERSION, 1)) >= 2
    return replace(start, **{k: float(getattr(b, f)) for f, k in STEP_FIELDS if new or f not in NEW_STEP_FIELDS})


def put_step(b, st: core.State) -> None:
    for f, k in STEP_FIELDS:
        setattr(b, f, getattr(st, k))
    b[STEP_VERSION] = 2


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


def upgrade_step(scene, b) -> None:
    """A step saved before task 0299 gets the weather before it as its new values (then a change to one of them only
    changes that one)."""
    s = scene.fresing
    anim = next((a for a in s.animations if any(x == b for x in a.blocks)), None)
    keep = {f: float(getattr(b, f)) for f in NEW_STEP_FIELDS}
    b[STEP_VERSION] = 2
    if anim is None:
        return
    st = state_before(scene, anim, b)
    defaults = {f: b.bl_rna.properties[f].default for f in NEW_STEP_FIELDS}
    for f, k in STEP_FIELDS:
        if f in NEW_STEP_FIELDS and abs(keep[f] - defaults[f]) < 1e-9:   # (not the value just set by hand)
            setattr(b, f, getattr(st, k))


def step_from_preset(scene, b, name: str) -> None:
    put_step(b, core.preset(name, state(scene)))


def _is_preset(b) -> bool:
    """The step's values are still its 'To' preset's (not changed by hand afterwards)."""
    if b.wx_preset == "CUSTOM" or b.wx_preset not in core.PRESETS:
        return False
    want = core.preset(b.wx_preset)
    return all(abs(float(getattr(b, f)) - float(getattr(want, k))) < 1e-3 for f, k in STEP_FIELDS
               if k not in ("wind_from",))


def step_label(b) -> str:
    if _is_preset(b):
        return f"Weather to {core.PRESETS[b.wx_preset][0]} ({core.clock(b.wx_hour)})"
    bits = [core.clock(b.wx_hour)]
    if b.wx_lightning > 0.01 and int(b.get(STEP_VERSION, 1)) >= 2:
        bits.append("lightning")
    if b.wx_rain > 0.01:
        bits.append("rain")
    if b.wx_snow > 0.01:
        bits.append("snow")
    if b.wx_hail > 0.01 and int(b.get(STEP_VERSION, 1)) >= 2:
        bits.append("hail")
    if b.wx_visibility < 4000.0 or (b.wx_mist > 0.01 and int(b.get(STEP_VERSION, 1)) >= 2):
        bits.append("fog" if b.wx_visibility < 1000.0 else "mist")
    return "Weather to " + ", ".join(bits)


def flash_times(b) -> list[float]:
    """The step's set moments of lightning ('Flash at': seconds from its start, commas or spaces between), within
    its duration; text that is no number is left out."""
    out = []
    for part in (b.wx_flash_at or "").replace(";", ",").replace(" ", ",").split(","):
        try:
            t = float(part)
        except ValueError:
            continue
        if 0.0 <= t <= float(b.duration) + 1e-9:
            out.append(t)
    return out


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


def bake(scene, anim, blocks, frame_of, ease, f_end: int = 0) -> list[str]:
    """Keys of the Weather & time steps: every channel, every frame of a step (the clock, the sun and the fog
    change non-linearly), constant before and after. Lightning (task 0299): the flashes of the whole animation
    (``f_end``) – at random while lightning is above 0 (the panel's or a step's), and at a step's set moments. Returns
    warnings."""
    if not blocks:
        if f_end and enabled(scene) and state(scene).lightning > 0.0 and place(scene) == "sky":
            return _bake_flashes(scene, anim, [], frame_of, f_end, None)
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
    base = state(scene)
    rows = {n: [] for n in core.CHANNEL_NAMES}
    steps = []
    for b in sorted(blocks, key=lambda x: x.start):
        f0, f1 = frame_of(b.start), frame_of(b.start + b.duration)
        steps.append((b, f0, max(f1, f0 + 1)))
    last = max(f1 for _b, _f0, f1 in steps)

    def at(f):
        """The weather at frame ``f``: each step leads from the weather of that moment (the steps before it, also
        while they still run: overlapping steps blend, never jump) to its own values."""
        st = base
        for b, f0, f1 in steps:
            if f <= f0:
                continue
            st = core.mix(st, step_state(st, b), ease(b.easing, (f - f0) / (f1 - f0)))
        return st

    end = max(last, int(f_end or 0))
    for f in range(1, end + 1):
        for n, v in core.derive(at(f) if f <= last else at(last), where).items():
            rows[n].append((f, v, "LINEAR", "AUTO"))
    if where == "sky" and (max(v for _f, v, _i, _h in rows["lightning"]) > 0.0 or any(flash_times(b) for b in blocks)):
        rate = [v for _f, v, _i, _h in rows["lightning"]]
        fixed = [frame_of(b.start + t) - 1 for b in blocks for t in flash_times(b)]
        flash, bolt = fx_core.flash_track(rate, animation.fps_of(anim), fixed, seed=_flash_seed(anim))
        rows["flash"] = [(i + 1, float(v), "LINEAR", "AUTO") for i, v in enumerate(flash)]
        rows["bolt"] = [(i + 1, float(v), "CONSTANT", "AUTO") for i, v in enumerate(bolt)]
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


def _flash_seed(anim) -> int:
    """The lightning's seed: one per animation (its name), so two animations do not flash at the same moments but the
    same animation flashes the same way at every Build."""
    import zlib
    return fx_core.SEED_FLASH + zlib.crc32(anim.name.encode("utf-8")) % 100000


def _bake_flashes(scene, anim, warnings, frame_of, f_end, _unused) -> list[str]:
    """An animation without Weather & time steps under a panel with lightning: random flashes all through it."""
    from . import animation
    rate = [state(scene).lightning] * int(f_end)
    flash, bolt = fx_core.flash_track(rate, animation.fps_of(anim), (), seed=_flash_seed(anim))
    cb = animation._channelbag(scene, "SCENE")
    write_channels(scene, channels(scene))
    for n, vals, interp in (("flash", flash, "LINEAR"), ("bolt", bolt, "CONSTANT")):
        keys = [(i + 1, float(v), interp, "AUTO") for i, v in enumerate(vals)]
        keys = [k for i, k in enumerate(keys) if i in (0, len(keys) - 1)
                or abs(k[1] - keys[i - 1][1]) > 1e-9 or abs(k[1] - keys[i + 1][1]) > 1e-9]
        animation._write(cb, f'["{core.prop(n)}"]', 0, keys)
    scene[STEP_TAG] = True
    after_world(scene)
    return warnings


# ---------------------------------------------------------------------------
# Change to ▸ a preset at the playhead (task 0299)
# ---------------------------------------------------------------------------

CHANGE_ANIM = "Weather"               # the animation made when there is none
CHANGE_FLASH = 0.8                    # a change to lightning flashes once for sure, at this share of its time


def seconds_at(anim, frame: int) -> float:
    """The animation time (s) of a frame (frame 1 = 0 s)."""
    from . import animation
    return max(0.0, (int(frame) - 1) / float(animation.fps_of(anim)))


def change_at_playhead(scene, name: str, seconds: float) -> tuple:
    """Change to the preset ``name`` over ``seconds`` from the playhead: a Weather & time step in the active animation
    (one is made when there is none) – the one that starts at the playhead is changed instead of adding another.
    Returns (animation, step, made: True when a new step was added)."""
    from . import animation
    s = scene.fresing
    if not s.weather.enabled:
        s.weather.enabled = True
    anim = s.animations[s.animations_index] if 0 <= s.animations_index < len(s.animations) else None
    if anim is None:
        anim = s.animations.add()
        anim.name = CHANGE_ANIM if s.animations.get(CHANGE_ANIM) is None else animation.unique_name(scene)
        if s.active_shot and s.active_shot in s.shots:
            anim.start_shot = s.active_shot
        s.animations_index = len(s.animations) - 1
    t = round(seconds_at(anim, scene.frame_current), 2)
    half = 0.5 / float(animation.fps_of(anim))
    b = next((x for x in anim.blocks if x.kind == "WEATHER" and abs(x.start - t) <= half + 1e-9), None)
    made = b is None
    if made:
        b = anim.blocks.add()
        b.kind = "WEATHER"
        b.start = t
    b.duration = float(seconds)
    b.easing = "SMOOTH"
    b.enabled = True
    step_init(scene, anim, b)
    b.wx_preset = name                       # sets the values (props._wx_step_preset)
    step_from_preset(scene, b, name)         # (also when the update did not run: a step from Python)
    if b.wx_lightning > 0.0 and not b.wx_flash_at:
        b.wx_flash_at = f"{round(CHANGE_FLASH * float(seconds), 2):g}"    # one flash for sure, as the storm arrives
    anim.blocks_index = list(anim.blocks).index(b)
    return anim, b, made

def after_clear(scene) -> None:
    """'Clear keys': the channels go back to the panel's weather."""
    if not scene.get(STEP_TAG):
        return
    del scene[STEP_TAG]
    from . import animation
    ad = scene.animation_data
    act = ad.action if ad is not None else None
    if act is not None and act.get(animation.TAG):
        animation._drop_action(scene)       # a scene action of the user's own comes back (bug hunt 0118 row 18c)
        if act.users == 0:                   # Clear keys removed the orphans already: never leave this one behind
            bpy.data.actions.remove(act)
    if scene.get(animation.TAG):
        del scene[animation.TAG]
    if enabled(scene):
        write_channels(scene, channels(scene))
        after_world(scene)
