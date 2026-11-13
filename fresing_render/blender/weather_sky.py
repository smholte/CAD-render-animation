"""Weather and time of day, the sky part (task 0109): the sky by the clock, clouds, haze and fog, the night (stars,
the moon, moonlight, floodlights), the camera's exposure, and work lights on parts.

Everything here reads the weather **channels** (``scene["fr_wx_<name>"]``, ``core/weather.py``) through drivers
whose expressions are *simple expressions* (scripts off, the render queue, every paint scheme): a Weather & time
animation step that keys the channels moves the sun, the clouds, the fog and the lamps without any Python per frame.

* ``world_branch`` – the sky the world shader draws when the weather is on outdoors (``world.apply`` calls it in
  place of ``_env_branch``): the physical sky texture (the sun's height and direction, twilight colours) under cloud
  patches that close to an overcast as the cover grows, a low cloud deck, haze towards the horizon, the dark night
  sky with stars and the moon's disc; below the horizon the neutral ground of before, as bright as the light.
* ``apply`` / ``remove`` – what the sky cannot do: moonlight (a dim Sun lamp), floodlights on masts round the model
  (sea, deck, quay), the exposure the eye adds at dusk and night (a driver ``base + exposure`` on the scene's
  exposure, the user's own value kept), and **fog**: laid over the picture by the compositor from the Z pass,
  ``T = exp(-fog · distance)`` (per km; the sky itself gets its haze in the world shader). Measured before choosing
  (task 0109, test crane on the quay, Cycles CPU Draft 960 x 540 on the 4-core web machine): the compositor's fog
  adds nothing measurable (70.4 s with, 70.4 s without); a world volume for 400 m took 103 s (+47 %) and rendered
  black – an endless world volume swallows the light of the sky and the sun (a bounded fog box would be needed,
  noisy and slower still). The Z pass is one sample per pixel, so edges against the sky get no fog fringe.
  Only haze beyond today's clear air (visibility under 40 km) is added: a clear day looks as the sky of before.
* Work lights: a part becomes a lamp (``add_work_light``); kept through a model update (``after_model_update``),
  working with the weather off too.

Every object made here carries ``fr_weather`` = its role (work lights ``fr_work_light`` = the part's ID instead),
and ``fr_kind`` = "cnc" so the structure tree (``logic.Tree``) leaves it out.
"""

from __future__ import annotations

import json
import math

import bpy
from mathutils import Matrix, Vector

from ..core import weather as core

SUN_ROTATION_ZERO_AZ = 90.0     # scene azimuth of the sky texture's sun at sun_rotation 0 (measured: the back, +Y);
#                                 sun_rotation = radians(SUN_ROTATION_ZERO_AZ - azimuth) (tests/test_weather_sky.py)
TAG = "fr_weather"              # on every object made here (value: its role)
WORK_TAG = "fr_work_light"      # on a work light: the part's ID (build.PROP_UID)
WORK_KIND = "fr_work_light_kind"
WORK_LOCAL = "fr_work_light_local"       # the light's place relative to its part (16 numbers), for a model update
FOG_COMPOSITING = "fr_weather_compositing"   # the user's own compositing switch, given back by fog_off
HELPER_KIND = "cnc"             # fr_kind of objects that are not part of the CAD tree (logic.Tree skips it)
COLLECTION = "FR Weather lights"
WORK_COLLECTION = "FR Work lights"
KEY = "fr_weather_sky_key"      # scene property: what apply built last (cheap when nothing changed)
EXPOSURE_BASE = "fr_weather_exposure_base"   # the user's own exposure while the weather adds to it
FOG_GROUP = "FR weather fog"
FOG_PASS_Z = "fr_weather_had_z"              # the view layer's Z pass before the fog switched it on
SKY_SCALE = 0.08                # the physical sky's strength in the app (world._env_branch)
GROUND = (1.0, 0.97, 0.92)      # world.GROUND_RADIANCE's colour
FLOOD_W = 5.0                   # watts of a floodlight 15 m from the middle of the model (scaled by distance²):
#                                 four of them, at the night's +4 EV, light the model about a tenth as bright as day
FLOOD_COLOUR = (1.0, 0.88, 0.72)
WORK_W = 3.0                    # watts of a work light 5 m from what it lights (bright at night, faint by day)
WORK_COLOUR = (1.0, 0.93, 0.82)
FLOOD_BACKGROUNDS = ("SEA", "DECK", "QUAY")
MASTS = ("DECK", "QUAY")        # floodlights stand on masts here (on the open sea they hang on an unseen vessel)

# the expressions shared with core/weather.py (its tests check the two agree)
SKY_LIGHT = "pow(smoothstep(-9, 30, sun_el), 1.5)"


# ---------------------------------------------------------------------------
# drivers: simple expressions on the channels
# ---------------------------------------------------------------------------

def _var(drv, name: str, scene, path: str) -> None:
    v = drv.variables.new()
    v.name = name
    v.type = "SINGLE_PROP"
    t = v.targets[0]
    t.id_type = "SCENE"
    t.id = scene
    t.data_path = path


def drive(owner, path: str, expr: str, scene, index: int = -1, extra: dict | None = None):
    """A driver on ``owner.path`` with ``expr``; every channel named in it is a variable (``sun_el`` reads
    ``scene["fr_wx_sun_el"]``); ``extra`` = {variable: data path on the scene}. Returns the F-curve."""
    try:
        owner.driver_remove(path, index)
    except (TypeError, RuntimeError):
        pass
    fc = owner.driver_add(path, index) if index >= 0 else owner.driver_add(path)
    for m in list(fc.modifiers):           # the generator Blender may add: the expression alone decides
        fc.modifiers.remove(m)
    d = fc.driver
    d.type = "SCRIPTED"
    for name in core.CHANNEL_NAMES:
        if _uses(expr, name):
            _var(d, name, scene, f'["{core.prop(name)}"]')
    for name, p in (extra or {}).items():
        _var(d, name, scene, p)
    d.expression = expr
    return fc


def sock(sockets, name: str):
    """The *enabled* socket called ``name`` (a Mix node has one A, B, Result per data type)."""
    for x in sockets:
        if x.name == name and x.enabled:
            return x
    return sockets[name]


def _uses(expr: str, name: str) -> bool:
    import re
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", expr) is not None


# ---------------------------------------------------------------------------
# the sky (world shader)
# ---------------------------------------------------------------------------

class _Nodes:
    """Small builder for the world's sky nodes."""

    def __init__(self, nt, scene, y: float):
        self.nt, self.scene, self.y, self.x = nt, scene, y, -3000.0

    def new(self, kind: str, x: float | None = None, dy: float = 0.0, label: str = ""):
        n = self.nt.nodes.new(kind)
        if x is None:
            self.x += 160.0
            x = self.x
        n.location = (x, self.y + dy)
        if label:
            n.label = label
        return n

    def link(self, a, b) -> None:
        self.nt.links.new(a, b)

    def value(self, label: str, expr: str, dy: float = 0.0):
        """A Value node driven by ``expr``: its output socket."""
        n = self.new("ShaderNodeValue", x=-3200.0, dy=dy, label=label)
        n.name = "wx " + label
        drive(n.outputs[0], "default_value", expr, self.scene)
        return n.outputs[0]

    def _in(self, sock, v) -> None:
        if isinstance(v, (int, float)):
            sock.default_value = float(v)
        elif isinstance(v, tuple):
            sock.default_value = v
        else:
            self.link(v, sock)

    def math(self, op: str, a, b=0.0, c=None, clamp: bool = False):
        n = self.new("ShaderNodeMath", label=op.lower())
        n.operation = op
        n.use_clamp = clamp
        self._in(n.inputs[0], a)
        self._in(n.inputs[1], b)
        if c is not None:
            self._in(n.inputs[2], c)
        return n.outputs[0]

    def vec(self, op: str, a, b=None, scale=None):
        n = self.new("ShaderNodeVectorMath", label=op.lower())
        n.operation = op
        self._in(n.inputs[0], a)
        if b is not None:
            self._in(n.inputs[1], b)
        if scale is not None:
            self._in(n.inputs["Scale"], scale)
        return n.outputs["Vector"] if op not in ("DOT_PRODUCT", "DISTANCE", "LENGTH") else n.outputs["Value"]

    def mix(self, fac, a, b, blend: str = "MIX"):
        n = self.new("ShaderNodeMix", label="mix")
        n.data_type = "RGBA"
        n.blend_type = blend
        n.clamp_factor = True
        self._in(sock(n.inputs, "Factor"), fac)
        self._in(sock(n.inputs, "A"), a)
        self._in(sock(n.inputs, "B"), b)
        return sock(n.outputs, "Result")

    def ramp(self, v, a: float, b: float, lo: float = 0.0, hi: float = 1.0, kind: str = "LINEAR"):
        """Map Range: ``v`` from a … b to lo … hi, clamped."""
        n = self.new("ShaderNodeMapRange", label="range")
        n.interpolation_type = kind
        n.clamp = True
        self._in(n.inputs["Value"], v)
        self._in(n.inputs["From Min"], a)
        self._in(n.inputs["From Max"], b)
        n.inputs["To Min"].default_value = lo
        n.inputs["To Max"].default_value = hi
        return n.outputs["Result"]


def world_branch(nt, scene, s, y: float = 0.0):
    """The weather's sky in the world tree ``nt``; returns its Background shader output. ``s`` = the scene's
    Fresing settings (the light strength scales it all, as before). All values are radiance at light strength 1;
    the channels come in through driven Value nodes (labels 'wx …')."""
    b = _Nodes(nt, scene, y)
    coord = b.new("ShaderNodeTexCoord")
    d = b.vec("NORMALIZE", coord.outputs["Generated"])
    sep = b.new("ShaderNodeSeparateXYZ")
    b.link(d, sep.inputs["Vector"])
    z = sep.outputs["Z"]
    zpos = b.math("MAXIMUM", z, 0.0)
    below = b.math("LESS_THAN", z, 0.0)

    # the clear sky: Blender's physical sky (twilight colours below 0°, black from about -12°)
    sky = b.new("ShaderNodeTexSky", label="clear sky")
    sky.name = "wx sky"
    try:
        sky.sky_type = "MULTIPLE_SCATTERING"
    except TypeError:
        pass
    sky.sun_disc = True
    drive(sky, "sun_elevation", "radians(sun_el)", scene)
    drive(sky, "sun_rotation", f"radians({SUN_ROTATION_ZERO_AZ:g} - sun_az)", scene)
    drive(sky, "sun_intensity", "sun", scene)
    clear = b.vec("SCALE", sky.outputs["Color"], scale=SKY_SCALE)

    # the overcast: brightest straight up, a third of it at the horizon (CIE overcast), darker under a low deck
    grad = b.math("MULTIPLY_ADD", zpos, 2.0 / 3.0, 1.0 / 3.0)
    ocl = b.value("overcast", f"{core.OVERCAST_ZENITH:g} * {SKY_LIGHT} * (1 - 0.55 * low)", dy=0)
    oc = b.vec("SCALE", (0.93, 0.96, 1.0), scale=b.math("MULTIPLY", grad, ocl))
    # cloud patches: lit brighter than the grey deck when the sky is mostly clear, golden at a low sun
    lift = b.value("cloud light", "1 + 0.9 * (1 - clouds) * day", dy=-60)
    warm = b.value("warm", "(1 - smoothstep(1, 18, sun_el)) * smoothstep(-6, 0, sun_el) * (1 - 0.7 * clouds)",
                   dy=-120)
    tint = b.mix(warm, (1.0, 1.0, 1.0, 1.0), (1.7, 1.0, 0.62, 1.0))
    cloud = b.vec("SCALE", b.vec("MULTIPLY", oc, tint), scale=lift)
    # where the clouds are: a noise field on a ceiling (directions spread out over a plane: patches get small and
    # close up towards the horizon); the cover moves the edge; a full cover and a low deck close the sky
    inv = b.math("DIVIDE", 1.0, b.math("ADD", zpos, 0.12))
    px = b.math("MULTIPLY", sep.outputs["X"], inv)
    py = b.math("MULTIPLY", sep.outputs["Y"], inv)
    cxy = b.new("ShaderNodeCombineXYZ")
    b.link(px, cxy.inputs["X"])
    b.link(py, cxy.inputs["Y"])
    cxy.inputs["Z"].default_value = 3.7
    noise = b.new("ShaderNodeTexNoise", label="cloud patches")
    noise.noise_dimensions = "3D"
    noise.inputs["Scale"].default_value = 1.1
    noise.inputs["Detail"].default_value = 7.0
    noise.inputs["Roughness"].default_value = 0.58
    b.link(cxy.outputs["Vector"], noise.inputs["Vector"])
    edge = b.value("cloud edge", "0.68 - 0.38 * clouds", dy=-180)
    patch = b.ramp(noise.outputs["Fac"], edge, b.math("ADD", edge, 0.09), kind="SMOOTHSTEP")
    there = b.value("clouds there", "smoothstep(0, 0.06, clouds)", dy=-240)
    full = b.value("overcast share", "max(smoothstep(0.72, 0.97, clouds), smoothstep(0, 0.6, low))", dy=-300)
    m = b.math("MAXIMUM", b.math("MULTIPLY", patch, there), full)
    under = b.math("SUBTRACT", 1.0, b.math("MULTIPLY", m, 0.92))           # how much of the sky shows through
    day_sky = b.mix(m, clear, b.mix(full, cloud, oc))

    # the night: airglow, stars, the moon (behind the clouds)
    ng = b.value("night sky", f"{core.NIGHT_SKY:g} * night + {core.MOON_SKY:g} * moon", dy=-360)
    night_col = b.vec("SCALE", core.FOG_NIGHT, scale=ng)
    vor = b.new("ShaderNodeTexVoronoi", label="stars")
    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = 260.0
    vor.inputs["Randomness"].default_value = 1.0
    b.link(d, vor.inputs["Vector"])
    core_ = b.ramp(vor.outputs["Distance"], 0.11, 0.0)
    rnd = b.new("ShaderNodeSeparateXYZ")
    b.link(vor.outputs["Color"], rnd.inputs["Vector"])
    pick = b.ramp(rnd.outputs["X"], 0.84, 1.0, 0.0, 1.0)
    pick = b.math("POWER", pick, 2.0)
    stars = b.value("stars", "stars * 4", dy=-420)
    star = b.math("MULTIPLY", b.math("MULTIPLY", core_, pick), b.math("MULTIPLY", stars, b.ramp(zpos, 0.0, 0.15)))
    mx = b.value("moon x", "cos(radians(moon_el)) * cos(radians(moon_az))", dy=-480)
    my = b.value("moon y", "cos(radians(moon_el)) * sin(radians(moon_az))", dy=-540)
    mz = b.value("moon z", "sin(radians(moon_el))", dy=-600)
    mdir = b.new("ShaderNodeCombineXYZ")
    for sock, v in zip(mdir.inputs, (mx, my, mz)):
        b.link(v, sock)
    dist = b.vec("DISTANCE", d, mdir.outputs["Vector"])
    r = 0.0045 * 1.6                     # the moon's radius (rad), a little larger than life
    disc = b.ramp(dist, r, r * 0.8)
    glow = b.math("POWER", b.ramp(dist, 0.7, 0.0), 6.0)
    moon = b.value("moon", "moon", dy=-660)
    moonrad = b.math("MULTIPLY", moon, b.math("ADD", b.math("MULTIPLY", disc, 0.6), b.math("MULTIPLY", glow, 0.01)))
    lights = b.vec("SCALE", (1.0, 0.97, 0.9), scale=b.math("ADD", star, moonrad))
    night = b.vec("SCALE", b.vec("ADD", night_col, lights), scale=under)
    sky_all = b.vec("ADD", day_sky, night)

    # below the horizon: today's neutral ground, as bright as the light
    gl = b.value("ground", f"{world_ground():g} * ({SKY_LIGHT} * (1 - 0.25 * clouds) * (1 - 0.4 * low) + "
                           f"{core.NIGHT_SKY * 2:g} * night + {core.MOON_SKY * 2:g} * moon)", dy=-720)
    ground = b.vec("SCALE", GROUND, scale=gl)
    col = b.mix(below, sky_all, ground)

    # haze towards the horizon (only what is more than today's clear air): 1 - exp(-fog · path), a 0.6 km layer
    fx = b.value("haze per km", f"max(fog - {core.CLEAR_FOG:.6f}, 0)", dy=-780)
    path = b.math("MINIMUM", b.math("DIVIDE", 0.6, b.math("ADD", b.math("ABSOLUTE", z), 0.008)), 80.0)
    h = b.math("SUBTRACT", 1.0, b.math("EXPONENT", b.math("MULTIPLY", b.math("MULTIPLY", fx, path), -1.0)))
    fogc = b.new("ShaderNodeCombineColor", label="fog colour")
    for i, ch in enumerate(("fog_r", "fog_g", "fog_b")):
        b.link(b.value(ch, ch, dy=-840 - 60 * i), fogc.inputs[i])
    col = b.mix(h, col, fogc.outputs["Color"])

    bg = b.new("ShaderNodeBackground", x=-50.0)
    bg.inputs["Strength"].default_value = float(s.light_strength)
    b.link(col, bg.inputs["Color"])
    return bg.outputs["Background"]


def world_ground() -> float:
    from . import world
    return world.GROUND_RADIANCE * SKY_SCALE


# ---------------------------------------------------------------------------
# apply / remove
# ---------------------------------------------------------------------------

def _settings(scene):
    return scene.fresing


def _peak(scene, name: str) -> float:
    try:
        from . import weather
        return float(weather.peak(scene, name))
    except Exception:
        return float(scene.get(core.prop(name), 0.0))


def _key(scene, place: str) -> str:
    s = _settings(scene)
    root = _sur_root()
    floods = _floods_wanted(scene, place)
    return json.dumps([
        place, s.background, round(float(s.light_strength), 6), floods, _fog_wanted(scene, place),
        [list(map(lambda v: round(float(v), 4), root.get("fr_min", (0, 0, 0)))),
         list(map(lambda v: round(float(v), 4), root.get("fr_max", (0, 0, 0)))),
         [round(float(v), 4) for v in root.location]] if (floods and root is not None) else None,
        _flood_parent_name(scene) if floods else None,
    ])


def _sur_root():
    try:
        from . import surroundings
        return surroundings.root_object()
    except Exception:
        return None


def _floods_wanted(scene, place: str) -> bool:
    s = _settings(scene)
    return place == "sky" and s.background in FLOOD_BACKGROUNDS and _peak(scene, "flood") > 1e-3


def _fog_wanted(scene, place: str) -> bool:
    return place == "sky" and _peak(scene, "fog") > core.CLEAR_FOG * 1.001


ROLES = ("moon", "floods", "flood", "mast", "fog")     # what this module makes (weather_fx shares the tag)


def _objects(role: str | None = None) -> list:
    return [ob for ob in bpy.data.objects if ob.get(TAG) in ROLES and (role is None or ob.get(TAG) == role)]


def _collection(scene, name: str = COLLECTION):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def apply(scene, st: core.State, place: str) -> None:
    """Moonlight, floodlights, the exposure and the fog for the weather ``st`` at ``place`` ('sky', 'photo',
    'indoor'). Cheap when nothing changed (a key in a scene property); never raises."""
    try:
        _apply(scene, place)
    except Exception as exc:                 # never into the UI
        import traceback
        traceback.print_exc()
        print("Fresing Render: weather sky not set up:", exc)


def _apply(scene, place: str) -> None:
    scene.update_tag()                       # the channels were written from Python: the drivers read them again
    _exposure_on(scene)
    key = _key(scene, place)
    floods = _floods_wanted(scene, place)
    have = bool(_objects("moon")) == (place == "sky") and bool(_objects("flood")) == floods
    have = have and (_foreign_compositor(scene)
                     or (bpy.data.node_groups.get(FOG_GROUP) is not None) == _fog_wanted(scene, place))
    if scene.get(KEY) == key and have:
        return
    _remove_objects(keep_work=True)
    if place == "sky":
        _moon(scene)
    if floods:
        _floodlights(scene)
    if _fog_wanted(scene, place):
        fog_on(scene)
    else:
        fog_off(scene)
    scene[KEY] = key


def remove(scene) -> None:
    """Take away everything the weather's sky made (work lights stay). Never raises."""
    try:
        _exposure_off(scene)
        fog_off(scene)
        _remove_objects(keep_work=True)
        if KEY in scene:
            del scene[KEY]
    except Exception as exc:
        print("Fresing Render: weather sky not removed:", exc)


def _remove_objects(keep_work: bool = True) -> None:
    objs = _objects()
    datas = [ob.data for ob in objs if ob.data is not None]
    if objs:
        bpy.data.batch_remove(objs)
    orphans = [x for x in datas if x.users == 0]
    if orphans:
        bpy.data.batch_remove(orphans)
    col = bpy.data.collections.get(COLLECTION)
    if col is not None and not col.objects and not col.children:
        bpy.data.collections.remove(col)
    for name in ("FR weather mast", "FR weather lamp"):
        mat = bpy.data.materials.get(name)
        if mat is not None and mat.users == 0:
            bpy.data.materials.remove(mat)


# ---- exposure ------------------------------------------------------------------

def _exposure_on(scene) -> None:
    """The scene's exposure = the user's own + the weather's (``exposure`` channel), by a driver."""
    scene[EXPOSURE_BASE] = float(_settings(scene).exposure)
    ad = scene.animation_data
    if ad is not None and any(fc.data_path == "view_settings.exposure" for fc in ad.drivers):
        return
    drive(scene, "view_settings.exposure", "b + exposure", scene, extra={"b": f'["{EXPOSURE_BASE}"]'})


def _exposure_off(scene) -> None:
    ad = scene.animation_data
    if ad is not None and any(fc.data_path == "view_settings.exposure" for fc in ad.drivers):
        scene.driver_remove("view_settings.exposure")
    if EXPOSURE_BASE in scene:
        scene.view_settings.exposure = float(scene[EXPOSURE_BASE])
        del scene[EXPOSURE_BASE]
    if ad is not None and not ad.drivers and ad.action is None and not ad.nla_tracks:
        scene.animation_data_clear()


# ---- moonlight -------------------------------------------------------------------

def _moon(scene) -> None:
    light = bpy.data.lights.new("FR weather moonlight", "SUN")
    light.color = (0.72, 0.82, 1.0)
    light.angle = math.radians(0.6)
    ob = bpy.data.objects.new("FR weather moonlight", light)
    ob[TAG] = "moon"
    ob["fr_kind"] = HELPER_KIND
    ob.hide_select = True
    _collection(scene).objects.link(ob)
    drive(light, "energy", f"moon * {core.MOON_W:g}", scene)
    drive(ob, "rotation_euler", "radians(90 - moon_el)", scene, index=0)
    drive(ob, "rotation_euler", "radians(moon_az + 90)", scene, index=2)


# ---- floodlights -------------------------------------------------------------------

def _flood_parent_name(scene) -> str:
    from . import build
    roots = sorted(build.model_roots(scene), key=lambda o: o.name)
    return roots[0].name if roots else ""


def flood_spots(kind: str, mn, mx, base_z: float) -> list[tuple[tuple, tuple, bool]]:
    """Where the floodlights go: [(lamp position, aim point, on a mast)] round the model's box ``mn``/``mx``
    (world metres); masts stand at ``base_z`` (the deck or the quay). Three masts behind and beside the model and
    a fourth lamp on the camera's side (front right: +x, -y) without a mast, so no pole stands in the default
    view. On the open sea none stands (lamps of an unseen vessel)."""
    from ..core import surroundings as env
    w, d, h = (max(0.2, float(mx[i] - mn[i])) for i in range(3))
    kx, ky, _kh = env.keepout_for(w, d, h)
    cx, cy = (mn[0] + mx[0]) / 2.0, (mn[1] + mx[1]) / 2.0
    top = base_z + max(8.0, 1.35 * h + 3.0)
    aim = (cx, cy, base_z + 0.35 * h)
    mx_, my_ = kx + 1.5, ky + 1.5
    if kind == "DECK":
        my_ = max(9.0, ky + 4.0) - 1.2       # along the railings
    corners = [(-1, 1, True), (1, 1, True), (-1, -1, True), (1, -1, False)]
    out = []
    for sx, sy, mast in corners:
        p = (cx + sx * mx_, cy + sy * my_, top)
        out.append((p, aim, mast and kind in MASTS))
    return out


def _lamp_rotation(pos, aim) -> Matrix:
    direction = Vector(aim) - Vector(pos)
    return direction.to_track_quat("-Z", "Y").to_matrix().to_4x4()


def _materials():
    mast = bpy.data.materials.get("FR weather mast")
    if mast is None:
        mast = bpy.data.materials.new("FR weather mast")
        bsdf = mast.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.32, 0.33, 0.34, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.6
        bsdf.inputs["Roughness"].default_value = 0.5
        mast.diffuse_color = (0.32, 0.33, 0.34, 1.0)
    lamp = bpy.data.materials.get("FR weather lamp")
    if lamp is None:
        lamp = bpy.data.materials.new("FR weather lamp")
        nt = lamp.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.2
        bsdf.inputs["Emission Color"].default_value = (*FLOOD_COLOUR, 1.0)
        at = nt.nodes.new("ShaderNodeAttribute")          # the floodlight channel (a key in the animation works)
        at.attribute_type = "VIEW_LAYER"
        at.attribute_name = core.prop("flood")
        at.location = (-500, -300)
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = 40.0
        mul.location = (-300, -300)
        nt.links.new(at.outputs["Fac"], mul.inputs[0])
        nt.links.new(mul.outputs[0], bsdf.inputs["Emission Strength"])
    return mast, lamp


def _mast_mesh(name: str, height: float) -> bpy.types.Mesh:
    """A pole (8 sides, 0.14 m) from 0 to ``height`` with a lamp head (0.7 x 0.35 x 0.45 m) at the top; the head's
    front (−y in the mesh) is the lamp glass (material 1)."""
    verts, faces, mats = [], [], []
    n, r = 8, 0.07
    for z in (0.0, height - 0.2):
        for i in range(n):
            a = 2 * math.pi * i / n
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
        mats.append(0)
    faces.append(tuple(range(n - 1, -1, -1)))
    mats.append(0)
    faces.append(tuple(range(n, 2 * n)))
    mats.append(0)
    o = len(verts)
    hx, hy, hz = 0.35, 0.18, 0.225
    zc = height
    for dz in (-hz, hz):
        for dx, dy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
            verts.append((dx, dy, zc + dz))
    box = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for k, f in enumerate(box):
        faces.append(tuple(o + i for i in f))
        mats.append(1 if k == 2 else 0)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for p, mi in zip(me.polygons, mats):
        p.material_index = mi
    me.update()
    return me


def _floodlights(scene) -> None:
    from . import logic
    s = _settings(scene)
    root = _sur_root()
    if root is not None and root.get("fr_min") is not None:
        mn, mx = list(root["fr_min"]), list(root["fr_max"])
        base_z = float(root.location.z)
    else:
        mn, mx = logic.cached_bounds(scene)
        base_z = float(mn[2])
    spots = flood_spots(s.background, mn, mx, base_z)
    col = _collection(scene)
    group = bpy.data.objects.new("FR weather floodlights", None)
    group[TAG] = "floods"
    group["fr_kind"] = HELPER_KIND
    group.empty_display_size = 0.5
    group.hide_select = True
    col.objects.link(group)
    mast_mat, lamp_mat = _materials()
    for i, (pos, aim, mast) in enumerate(spots):
        dist = (Vector(aim) - Vector(pos)).length
        light = bpy.data.lights.new(f"FR weather floodlight {i + 1}", "SPOT")
        light.color = FLOOD_COLOUR
        radius = 0.5 * math.hypot(mx[0] - mn[0], mx[1] - mn[1]) + 2.0
        light.spot_size = min(max(2.0 * math.atan2(radius * 1.1, dist), math.radians(25)), math.radians(100))
        light.spot_blend = 0.55
        light.shadow_soft_size = 0.25
        drive(light, "energy", f"flood * {FLOOD_W * max(dist / 15.0, 0.3) ** 2:.2f}", scene)
        lob = bpy.data.objects.new(f"FR weather floodlight {i + 1}", light)
        lob[TAG] = "flood"
        lob["fr_kind"] = HELPER_KIND
        lob.hide_select = True
        lob.matrix_world = Matrix.Translation(Vector(pos) + (Vector(aim) - Vector(pos)).normalized() * 0.5) \
            @ _lamp_rotation(pos, aim)
        lob.parent = group
        col.objects.link(lob)
        if mast:
            me = _mast_mesh(f"FR weather mast {i + 1}", pos[2] - base_z)
            me.materials.append(mast_mat)
            me.materials.append(lamp_mat)
            mob = bpy.data.objects.new(f"FR weather mast {i + 1}", me)
            mob[TAG] = "mast"
            mob["fr_kind"] = HELPER_KIND
            mob.hide_select = True
            facing = math.atan2(aim[1] - pos[1], aim[0] - pos[0]) + math.pi / 2   # the glass (−y) to the model
            mob.matrix_world = Matrix.Translation((pos[0], pos[1], base_z)) @ Matrix.Rotation(facing, 4, "Z")
            mob.parent = group
            col.objects.link(mob)
    # on a vessel they move with it: ride on the model's root (which follows the vessel's motion)
    from . import build
    roots = sorted(build.model_roots(scene), key=lambda o: o.name)
    if roots:
        import contextlib
        try:
            from . import vessel_motion
            rest = vessel_motion.at_rest(scene)          # the root's place without the sea's motion
        except Exception:
            rest = contextlib.nullcontext()
        with rest:
            bpy.context.view_layer.update()
            inv = roots[0].matrix_world.inverted()
        group.parent = roots[0]
        group.matrix_parent_inverse = inv


# ---- fog (compositor) ----------------------------------------------------------------

def _fog_tree(scene):
    ng = bpy.data.node_groups.get(FOG_GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(FOG_GROUP, "CompositorNodeTree")
    try:
        _fog_nodes(scene, ng)
    except Exception:
        bpy.data.node_groups.remove(ng)
        raise
    return ng


def _fog_nodes(scene, ng) -> None:
    ng[TAG] = "fog"
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N = ng.nodes
    L = ng.links
    rl = N.new("CompositorNodeRLayers")
    rl.location = (-900, 0)

    def node(kind, x, y, op=None, a=None, b=None):
        n = N.new(kind)
        n.location = (x, y)
        if op:
            n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = float(v)
            else:
                L.new(v, n.inputs[i])
        return n

    def value(label, expr, y):
        n = N.new("ShaderNodeValue")
        n.label = n.name = "wx " + label
        n.location = (-900, y)
        drive(n.outputs[0], "default_value", expr, scene)
        return n.outputs[0]

    depth = rl.outputs["Depth"]
    km = node("ShaderNodeMath", -600, -200, "MULTIPLY", depth, 0.001).outputs[0]
    fx = value("fog per km", f"max(fog - {core.CLEAR_FOG:.6f}, 0)", -350)
    tau = node("ShaderNodeMath", -400, -250, "MULTIPLY", km, fx).outputs[0]
    neg = node("ShaderNodeMath", -250, -250, "MULTIPLY", tau, -1.0).outputs[0]
    t = node("ShaderNodeMath", -100, -250, "EXPONENT", neg).outputs[0]
    sky = node("ShaderNodeMath", -100, -400, "GREATER_THAN", depth, 1.0e8).outputs[0]
    keep = node("ShaderNodeMath", 50, -300, "MAXIMUM", t, sky).outputs[0]
    fogc = N.new("CompositorNodeCombineColor")
    fogc.location = (-250, -550)
    strength = float(_settings(scene).light_strength)
    for i, ch in enumerate(("fog_r", "fog_g", "fog_b")):
        L.new(value(ch, f"{ch} * {strength:g}", -500 - 80 * i), fogc.inputs[i])
    fogc.inputs["Alpha"].default_value = 1.0
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.clamp_factor = True
    mix.location = (250, 0)
    L.new(keep, sock(mix.inputs, "Factor"))
    L.new(fogc.outputs["Image"], sock(mix.inputs, "A"))
    L.new(rl.outputs["Image"], sock(mix.inputs, "B"))
    alpha = N.new("CompositorNodeSetAlpha")
    alpha.location = (450, 0)
    L.new(sock(mix.outputs, "Result"), alpha.inputs["Image"])
    L.new(rl.outputs["Alpha"], alpha.inputs["Alpha"])
    out = N.new("NodeGroupOutput")
    out.location = (650, 0)
    L.new(alpha.outputs["Image"], out.inputs[0])


def _foreign_compositor(scene) -> bool:
    cur = getattr(scene, "compositing_node_group", None)
    return cur is not None and cur.name != FOG_GROUP


def fog_on(scene) -> None:
    """Fog laid over the picture by the compositor (unless the scene has a compositor of its own)."""
    if _foreign_compositor(scene):
        print("Fresing Render: the scene has its own compositor; the weather's fog is left out")
        return
    vl = scene.view_layers[0] if scene.view_layers else None
    if vl is not None and FOG_PASS_Z not in scene:
        scene[FOG_PASS_Z] = bool(vl.use_pass_z)
        vl.use_pass_z = True
    scene.compositing_node_group = _fog_tree(scene)
    if FOG_COMPOSITING not in scene:
        scene[FOG_COMPOSITING] = bool(scene.render.use_compositing)
    scene.render.use_compositing = True


def fog_off(scene) -> None:
    cur = getattr(scene, "compositing_node_group", None)
    if cur is not None and cur.name == FOG_GROUP:
        scene.compositing_node_group = None
    ng = bpy.data.node_groups.get(FOG_GROUP)
    if ng is not None and ng.users == 0:
        bpy.data.node_groups.remove(ng)
    if FOG_COMPOSITING in scene:
        scene.render.use_compositing = bool(scene[FOG_COMPOSITING])
        del scene[FOG_COMPOSITING]
    if FOG_PASS_Z in scene:
        vl = scene.view_layers[0] if scene.view_layers else None
        if vl is not None:
            vl.use_pass_z = bool(scene[FOG_PASS_Z])
        del scene[FOG_PASS_Z]


# ---------------------------------------------------------------------------
# work lights: a part becomes a lamp
# ---------------------------------------------------------------------------

def _part_box(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _model_centre(scene):
    from . import logic
    try:
        mn, mx = logic.cached_bounds(scene)
        return Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, float(mn[2]))), float(max(mx - mn))
    except Exception:
        return Vector((0.0, 0.0, 0.0)), 2.0


def add_work_light(scene, part, kind: str = "SPOT"):
    """Make ``part`` a lamp: a light on the part (its child, so it moves with it), aimed at the middle of the
    model's floor – or straight down when the part hangs above it. ``kind`` SPOT (a 60° beam) or FLOOD (wide,
    soft). Kept through model updates; works with the weather off. Returns the light object."""
    from . import build
    kind = "FLOOD" if str(kind).upper() == "FLOOD" else "SPOT"
    bpy.context.view_layer.update()
    lo, hi = _part_box(part)
    centre = (lo + hi) / 2
    target, size = _model_centre(scene)
    to = target - centre
    if to.length < 1e-6 or (to.normalized().z < -0.85):
        direction = Vector((0.0, 0.0, -1.0))
        to = Vector((0.0, 0.0, -max(centre.z - target.z, 1.0)))
    else:
        direction = to.normalized()
    half = (hi - lo) / 2
    out = abs(direction.x) * half.x + abs(direction.y) * half.y + abs(direction.z) * half.z
    pos = centre + direction * (out + 0.05)
    dist = max(to.length - out, 1.0)
    name = part.get(build.PROP_NAME, part.name)
    light = bpy.data.lights.new(f"Work light {name}", "SPOT")
    light.color = WORK_COLOUR
    light.energy = round(min(max(WORK_W * (dist / 5.0) ** 2, 0.5), 200.0), 2)
    light.spot_size = math.radians(120.0 if kind == "FLOOD" else 60.0)
    light.spot_blend = 0.7 if kind == "FLOOD" else 0.35
    light.shadow_soft_size = 0.15 if kind == "FLOOD" else 0.05
    ob = bpy.data.objects.new(f"Work light {name}", light)
    ob[WORK_TAG] = str(part.get(build.PROP_UID, ""))
    ob[WORK_KIND] = kind
    ob["fr_kind"] = HELPER_KIND
    _collection(scene, WORK_COLLECTION).objects.link(ob)
    world = Matrix.Translation(pos) @ direction.to_track_quat("-Z", "Y").to_matrix().to_4x4()
    _hang(ob, part, part.matrix_world.inverted() @ world)
    return ob


def _hang(ob, part, local: Matrix) -> None:
    """Make ``ob`` a child of ``part`` at ``local`` (its place in the part's coordinates)."""
    ob.parent = part
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = local
    ob[WORK_LOCAL] = [v for row in local for v in row]


def work_lights(scene) -> list:
    """The work lights of the scene (objects with ``fr_work_light``)."""
    return [ob for ob in scene.objects if ob.get(WORK_TAG) is not None]


def remove_work_light(scene, ob) -> None:
    """Delete a work light (and its lamp data when nothing else uses it)."""
    if ob is None or ob.get(WORK_TAG) is None:
        return
    data = ob.data
    bpy.data.objects.remove(ob)
    if data is not None and data.users == 0:
        bpy.data.lights.remove(data)
    col = bpy.data.collections.get(WORK_COLLECTION)
    if col is not None and not col.objects and not col.children:
        bpy.data.collections.remove(col)


def after_model_update(scene, mapping: dict, by_uid=None) -> list[str]:
    """Model update (reimport): each work light moves to the new copy of its part, at the same place on it.
    ``mapping`` = {old part ID: new ID or 'gone:…'}; ``by_uid`` (optional) = {old part ID: new object}. A light
    whose part is gone stays where it is. Returns notes for the report."""
    from . import build
    notes = []
    for ob in work_lights(scene):
        old = str(ob.get(WORK_TAG, ""))
        new = mapping.get(old)
        if new is None:
            continue
        cur = ob.parent
        if cur is not None:
            local = cur.matrix_world.inverted() @ ob.matrix_world
        else:
            vals = list(ob.get(WORK_LOCAL, [])) or [v for row in Matrix.Identity(4) for v in row]
            local = Matrix([vals[0:4], vals[4:8], vals[8:12], vals[12:16]])
        if str(new).startswith("gone:"):
            world = ob.matrix_world.copy()
            ob.parent = None
            ob.matrix_world = world
            notes.append(f"Work light '{ob.name}': its part is not in the new model; the lamp stays where it was")
            continue
        target = by_uid.get(old) if by_uid is not None else None
        if target is None:
            hits = [o for o in scene.objects if o.get(build.PROP_UID) == new and o.get(build.PROP_KIND) == "part"]
            hits.sort(key=lambda o: o is cur)               # the new copy before the old one
            target = hits[0] if hits else None
        if target is None:
            continue
        _hang(ob, target, local)
        ob[WORK_TAG] = str(new)
    return notes
