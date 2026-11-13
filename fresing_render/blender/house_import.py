"""A house from House Planner (task 0114): File > Import > House Planner scene (.hpscene).

The package (format ``house-scene`` 1.0, ``core/house_scene.py`` reads and checks it) is copied and unpacked next to
the project ("<project folder>/<name> house/"); its ``house.glb`` comes in with Blender's own glTF importer – merge
vertices off (the vertex order is the light per vertex's order) and Lighting Mode "Standard" (candela to watts, as
FORMAT.md section 10 asks) – into the collection "FR House". Every object keeps its label ``ob["hp"]`` (the glTF
extras); ``hp["id"]`` is the id its baked light is written under. A lamp's light is a child of its fitting (the
importer makes it so); it gets ``fr_house_lamp`` = the fitting's id.

The house is a model like a STEP import (a root empty "House: <title>", its meshes are parts with ``fr_uid`` = the
id), so the side panel's steps show and the explorer lists it. One house per project: importing again replaces it
(the ids are stable, so a new export of the same house lines up).

A **moment** of the recipe (morning, evening, night …) is shown with 0109's weather (``preview``): its clouds, haze,
the season's wet and snow, House Planner's sun – 0109 works its sun out from the clock, so ``moment_state`` sets
hour, day, latitude and north so that its sun lands where House Planner's stands (``house_scene.weather_sun``,
checked within 0.5°) –, the moment's lamps on, bare trees without their leaves.
"""

from __future__ import annotations

import os
import re
import shutil

import bpy

from ..core import house_scene as hs
from ..core import weather as wcore

COLLECTION = "FR House"
TAG = "fr_house"                 # on every object of the house: "root" | "part" | "light"
LAMP = "fr_house_lamp"           # on a lamp's light object: the id of its fitting
EXT = ".hpscene"
_CACHE: dict = {}                # path -> (mtime, house_scene.Scene)


# ---------------------------------------------------------------------------
# what is there
# ---------------------------------------------------------------------------

def settings(scene):
    return scene.fresing.house


def has_house(scene) -> bool:
    return scene is not None and root(scene) is not None


def root(scene):
    return next((ob for ob in scene.objects if ob.get(TAG) == "root"), None)


def parts(scene) -> list:
    """The house's mesh objects that carry a label (every surface of the export)."""
    return [ob for ob in scene.objects if ob.get(TAG) == "part" and ob.type == "MESH"]


def by_id(scene) -> dict:
    return {str(ob["hp"]["id"]): ob for ob in parts(scene) if ob.get("hp") is not None}


def lights(scene) -> list:
    return [ob for ob in scene.objects if ob.type == "LIGHT" and ob.get(LAMP)]


def package_path(scene) -> str:
    """The copy of the .hpscene next to the project (what bakes read)."""
    h = settings(scene)
    return os.path.join(h.folder, "house" + EXT) if h.folder else ""


def house(scene):
    """The imported house's ``house_scene.Scene`` (read once, again when the file changed)."""
    path = package_path(scene)
    if not path or not os.path.exists(path):
        raise FileNotFoundError("The house's files are missing next to the project – import the house again")
    mtime = os.path.getmtime(path)
    hit = _CACHE.get(path)
    if hit is None or hit[0] != mtime:
        hit = _CACHE[path] = (mtime, hs.read_scene(path))
    return hit[1]


def safe_name(text: str, fallback: str = "House") -> str:
    s = re.sub(r"[^A-Za-z0-9 _.-]+", " ", str(text or "")).strip(" .")
    return re.sub(r"\s+", " ", s)[:60] or fallback


def base_folder(scene, source: str) -> str:
    """Next to the project; a project not saved yet: next to the .hpscene."""
    return os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.dirname(os.path.abspath(source))


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------

def remove(scene) -> int:
    """Take the house out of the project (its objects, lights, collection). Returns how many objects went."""
    obs = [ob for ob in bpy.data.objects if ob.get(TAG)]
    datas = [ob.data for ob in obs if ob.data is not None]
    n = len(obs)
    if obs:
        bpy.data.batch_remove(obs)
    orphans = [d for d in datas if d.users == 0]
    if orphans:
        bpy.data.batch_remove(orphans)
    col = bpy.data.collections.get(COLLECTION)
    if col is not None and not col.objects and not col.children:
        bpy.data.collections.remove(col)
    return n


def import_scene(scene, path: str) -> dict:
    """Import a House Planner scene; returns {"house": Scene, "objects": n, "notes": [...]}. Raises
    ``house_scene.FormatError`` (a plain sentence) when the package must be refused."""
    path = os.path.abspath(path)
    house_ = hs.read_scene(path)                     # refuses a bad package before anything changes
    folder = os.path.join(base_folder(scene, path), safe_name(house_.title or os.path.splitext(
        os.path.basename(path))[0]) + " house")
    os.makedirs(folder, exist_ok=True)
    copy = os.path.join(folder, "house" + EXT)
    if os.path.abspath(copy) != path:
        shutil.copyfile(path, copy)
    glb = os.path.join(folder, "house.glb")
    with open(glb, "wb") as fh:
        fh.write(house_.glb)
    s = scene.fresing
    live = s.live_update
    s.live_update = False                           # one world rebuild at the end, not one per setting
    try:
        remove(scene)
        col = bpy.data.collections.new(COLLECTION)
        scene.collection.children.link(col)
        vl = bpy.context.view_layer
        before = vl.active_layer_collection
        vl.active_layer_collection = vl.layer_collection.children[col.name]
        old = set(bpy.data.objects)
        try:
            res = bpy.ops.import_scene.gltf(filepath=glb, merge_vertices=False,
                                            export_import_convert_lighting_mode="SPEC")
        finally:
            vl.active_layer_collection = before
        if res != {"FINISHED"}:
            raise RuntimeError(f"Blender's glTF importer could not read the house ({res})")
        new = [ob for ob in bpy.data.objects if ob not in old]
        top = _mark(scene, col, new, house_)
        # the model root: the side panel's steps show for a model
        from . import build
        r = bpy.data.objects.new("House: " + (house_.title or "House")[:50], None)
        r.empty_display_type = "PLAIN_AXES"
        r.empty_display_size = 0.5
        r[build.PROP_ROOT] = True
        r[build.PROP_KIND] = "assembly"
        r[build.PROP_NAME] = house_.title or "House"
        r[TAG] = "root"
        col.objects.link(r)
        for ob in top:
            mw = ob.matrix_world.copy()
            ob.parent = r
            ob.matrix_world = mw
        h = settings(scene)
        h.source = path
        h.folder = folder
        h.scene_id = house_.id
        h.title = house_.title
        h.version_name = house_.version_name or ""
        h.last_text = ""
        h.last_problems = ""
        # how the project shows a house: Cycles, the app's sky with 0109's weather, no floor (the plot is the floor)
        scene.render.engine = "CYCLES"
        s.background = "SKY"
        s.floor = "NONE"
        s.weather.enabled = True
    finally:
        s.live_update = live
    from . import logic, tree
    tree.rebuild(scene)
    logic.update_bounds(scene)
    first = house_.recipe.moments[0].id if house_.recipe.moments else ""
    preview(scene, first)
    _CACHE[copy] = (os.path.getmtime(copy), house_)
    return {"house": house_, "objects": len(new), "notes": list(house_.notes)}


def _mark(scene, col, new: list, house_) -> list:
    """Label the imported objects; returns those without a parent (to hang under the root)."""
    from . import build
    for ob in new:
        if ob.name not in col.objects:              # (the importer links into the active collection)
            col.objects.link(ob)
        hp = ob.get("hp")
        if ob.type == "MESH" and hp is not None and "id" in hp:
            sid = str(hp["id"])
            ob[TAG] = "part"
            ob[build.PROP_KIND] = "part"
            ob[build.PROP_UID] = sid
            ob[build.PROP_NAME] = sid
        elif ob.type == "LIGHT":
            p = ob.parent
            fitting = p.get("hp") if p is not None else ob.get("hp")
            ob[TAG] = "light"
            ob[LAMP] = str(fitting["id"]) if fitting is not None and "id" in fitting else ob.name
        else:
            ob[TAG] = "node"
    return [ob for ob in new if ob.parent is None]


# ---------------------------------------------------------------------------
# moments
# ---------------------------------------------------------------------------

def season_of(house_, moment):
    return next((s for s in house_.recipe.seasons if s.id == moment.season), None)


def moment_of(house_, moment_id: str):
    return next((m for m in house_.recipe.moments if m.id == moment_id), None)


def moment_state(house_, moment, falling: dict | None = None):
    """0109's weather for a moment: its sky, its season's wet and snow, and a clock / day / latitude / north that
    put 0109's sun where House Planner's stands. Returns (State, off), off = degrees between 0109's sun and House
    Planner's (should be well under 0.5)."""
    season = season_of(house_, moment)
    el, az = hs.sun_angles(moment.direction)
    day = season.day if season is not None else wcore.EQUINOX_DAY
    lat = float(house_.place.get("latitude", wcore.DEFAULT_LATITUDE))
    sun = hs.weather_sun(el, az, day, lat, bearing=float(moment.azimuth))
    f = falling or {}
    st = wcore.State(hour=float(sun["hour"]), use_date=True, day=int(sun["day"]), latitude=float(sun["latitude"]),
                     north=float(sun["north"]), clouds=float(moment.clouds), low_clouds=float(moment.low_clouds),
                     visibility=float(moment.visibility), rain=float(f.get("rain", 0.0)),
                     wet=float(season.wet if season is not None else 0.0), snow=float(f.get("snow", 0.0)),
                     snow_cover=float(season.snow_cover if season is not None else 0.0),
                     wind=float(f.get("wind", 0.0)), wind_from=float(f.get("wind_from", 225.0)),
                     floodlights="OFF")
    ch = wcore.derive(st)
    off = _angle(el, az, ch["sun_el"], ch["sun_az"])
    return st, off


def _angle(el1, az1, el2, az2) -> float:
    import math
    a = [math.radians(v) for v in (el1, az1, el2, az2)]
    u = (math.cos(a[0]) * math.cos(a[1]), math.cos(a[0]) * math.sin(a[1]), math.sin(a[0]))
    v = (math.cos(a[2]) * math.cos(a[3]), math.cos(a[2]) * math.sin(a[3]), math.sin(a[2]))
    c = max(-1.0, min(1.0, sum(x * y for x, y in zip(u, v))))
    return math.degrees(math.acos(c))


def lamps_of(scene, moment) -> list:
    """The light objects a moment switches on ("all", "none" or a list of fitting ids)."""
    which = moment.lamps
    if which == "all":
        return lights(scene)
    if which == "none" or not which:
        return []
    ids = set(which)
    return [ob for ob in lights(scene) if ob.get(LAMP) in ids]


def hidden_in(house_, season) -> set:
    """Ids hidden in a season: a tree's leaves when it is bare."""
    if season is None or season.foliage != "bare":
        return set()
    return {sid for sid, sf in house_.surfaces.items() if sf.kind == "foliage"}


def set_weather(scene, st) -> None:
    """Put a weather on the scene (0109) and rebuild the world once."""
    from . import weather, world
    s = scene.fresing
    live = s.live_update
    s.live_update = False
    try:
        weather.put_state(scene, st)
        s.weather.enabled = True
        if s.background != "SKY":
            s.background = "SKY"
    finally:
        s.live_update = live
    weather.write_channels(scene, weather.channels(scene))
    world.apply(scene, s)


def preview(scene, moment_id: str) -> str:
    """Show a moment in the project: 0109's weather and sun, its lamps on, bare trees without leaves. Returns a
    line for the panel ("" when the house has no such moment)."""
    house_ = house(scene)
    m = moment_of(house_, moment_id)
    if m is None:
        return ""
    st, off = moment_state(house_, m)
    set_weather(scene, st)
    on = set(lamps_of(scene, m))
    for ob in lights(scene):
        ob.hide_render = ob not in on
        ob.hide_viewport = ob not in on
    hide = hidden_in(house_, season_of(house_, m))
    for sid, ob in by_id(scene).items():
        ob.hide_render = sid in hide
        ob.hide_viewport = sid in hide
    from . import weather_look
    weather_look.add_objects(scene, parts(scene))      # the season's wet and snow look (0109) on the house
    settings(scene).moment = m.id
    return f"{m.label or m.id}: sun {hs.sun_angles(m.direction)[0]:.0f}° high" + (
        f" (0109's sun {off:.1f}° off)" if off > 0.5 else "")
