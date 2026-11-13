"""House Planner scenes in, bake packages out (task 0114). No Blender.

The format is the public repository github.com/smholte/house-scene-format, **tag v1.0** (its ``FORMAT.md`` is the
contract; a copy of its checker, schemas and samples is in ``tests/data/house/hsf-v1.0``). "FORMAT 7.5" below means
section 7.5 of that text. This module never imports the checker (``hsf``): the app ships without it.

- **Reading** a ``.hpscene`` (:func:`read_scene`): the zip rules (FORMAT 2), the version (another major is refused,
  a newer minor read with a note), the house's surfaces from ``house.glb`` (ids, world matrices and boxes, the hash
  checked again) and the recipe, with the open-list values of FORMAT 13 turned into what a reader must use.
- **The sun** (FORMAT 7.5): House Planner's direction in glTF axes -> Blender axes -> scene azimuth and elevation ->
  the sky texture's ``sun_rotation``; and the 0109 weather state (``core/weather.py``) whose own sun lands there.
- **Writing** a ``.hpbake`` (:class:`BakeWriter`): absolute light encoded per moment (FORMAT 8.3), the atlas pages
  (one rect layout for every moment), the vertex files (8.4), snow files, photos, videos, ``bake.json``.
- :func:`structure_problems`: a light check of a written package without ``jsonschema`` (the PC check).

Coordinates: **G** = glTF (metres, +Y up), as in ``house.glb``; **B** = Blender = (x, -z, y) of G.
Light: L = 0107's units (Cycles DIFFUSE without colour: what a white matte surface shows).
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import struct
import tempfile
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import datetime, timezone

import numpy as np

from . import house_hash, weather, web3d

VERSION = (1, 0)                       # the format version this code reads and writes ("1.0")
APP = "Fresing Render"

LIGHTS = ("LIVE", "SOFT", "ALL")       # closed lists (FORMAT 13): another value is another major version
BAKES = ("MAP", "VERTEX", "NO")
KINDS = ("wall", "floor", "ceiling", "slab-edge", "roof", "opening", "glass", "stair", "furniture", "install", "lamp",
         "ground", "garden", "plant", "foliage", "street", "neighbour", "water", "park", "snow", "other")
FOLIAGE = ("full", "autumn", "bare")
PRESET_SAMPLES = {"DRAFT": 16, "NORMAL": 64, "FINE": 256}     # 0107's samples when the recipe's samples is null
VIDEO_KINDS = ("turntable",)
FPS = (24, 25, 30, 50, 60)
DEFAULT_FPS = 25
SIDES = (256, 512, 1024, 2048)         # page sizes (px a side)
GAP = 2                                # texels between two rects on a page (FORMAT 8.3)
PHONE_PAGES = 4                        # pages one moment should fit in (FORMAT 11)
SUN_TOL = 0.5                          # degrees: a moment's direction and its angles may differ this much
IDENTITY_TOL = 1e-6                    # a node's world matrix this close to the identity is "not placed"

MAX_ENTRY = 512 * 1024 * 1024          # zip limits: the checker's (hsf/package.py)
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_FILES = 10000

ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
PNG_SIG = b"\x89PNG\r\n\x1a\n"
COLOUR_CHUNKS = (b"gAMA", b"iCCP", b"sRGB", b"cHRM", b"cICP", b"mDCV", b"cLLI", b"tRNS")


class FormatError(ValueError):
    """A package a reader must refuse. The text is a plain sentence for the owner."""


# ---------------------------------------------------------------------------
# packages (FORMAT 2)
# ---------------------------------------------------------------------------

def _name_problem(name: str) -> str | None:
    """Why a path inside a package is not allowed (FORMAT 2), or None."""
    if not name:
        return "has no name"
    if name.startswith("/") or "\\" in name or ":" in name.split("/")[0]:
        return "must be a relative path with forward slashes"
    if any(part in ("", ".", "..") for part in name.split("/")):
        return "must not contain empty parts, '.' or '..'"
    return None


def read_zip(src) -> dict[str, bytes]:
    """The files of a package: {path: bytes}. ``src`` is a path or the bytes. Refuses (FormatError) absolute paths,
    backslashes, '.' and '..' parts, names listed twice, encrypted files, methods other than stored or deflated, and
    files larger than the checker's limits – so nothing is read half."""
    data = src
    if not isinstance(src, (bytes, bytearray)):
        with open(src, "rb") as fh:
            data = fh.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError, ValueError):
        raise FormatError("This is not a zip package (the file is damaged or of another kind).") from None
    infos = zf.infolist()
    if len(infos) > MAX_FILES:
        raise FormatError(f"The package holds more than {MAX_FILES} files.")
    total, files = 0, {}
    for info in infos:
        name = info.filename
        if name.endswith("/") and info.file_size == 0:      # a folder entry
            continue
        why = _name_problem(name)
        if why:
            raise FormatError(f"The package's file '{name}' {why}.")
        if name in files:
            raise FormatError(f"The package lists '{name}' twice.")
        if info.flag_bits & 0x1:
            raise FormatError(f"The package's file '{name}' is encrypted.")
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise FormatError(f"The package's file '{name}' is packed in a way the format does not allow "
                              "(only stored or deflated).")
        if info.file_size > MAX_ENTRY:
            raise FormatError(f"The package's file '{name}' is larger than {MAX_ENTRY // 2**20} MB.")
        total += info.file_size
        if total > MAX_TOTAL:
            raise FormatError(f"The package's files add up to more than {MAX_TOTAL // 2**30} GB.")
        try:
            with zf.open(info) as fh:
                body = fh.read(MAX_ENTRY + 1)
        except (zipfile.BadZipFile, zlib.error, OSError, RuntimeError, NotImplementedError) as e:
            raise FormatError(f"The package's file '{name}' cannot be unpacked ({e}).") from None
        if len(body) != info.file_size:
            raise FormatError(f"The package's file '{name}' is not the size the zip says.")
        files[name] = body
    return files


def _no_constant(name):
    raise ValueError(f"{name} is not allowed (JSON has no NaN or Infinity)")


def _json(data: bytes, what: str) -> dict:
    try:
        doc = json.loads(data.decode("utf-8"), parse_constant=_no_constant)
    except (UnicodeDecodeError, ValueError) as e:
        raise FormatError(f"{what} is not valid JSON ({e}).") from None
    if not isinstance(doc, dict):
        raise FormatError(f"{what} does not hold a JSON object.")
    return doc


# what each package is, who makes it, and the words for the messages
_FORMATS = {"house-scene": ("house scene", "House Planner", "Export it again from a current House Planner."),
            "house-bake": ("bake", APP, "Bake it again with a current Fresing Render.")}


def parse_version(v) -> tuple[int, int] | None:
    """(major, minor) of "M.n" – two whole numbers compared as numbers ("1.10" is newer than "1.9")."""
    m = re.fullmatch(r"(\d+)\.(\d+)", v) if isinstance(v, str) else None
    return (int(m.group(1)), int(m.group(2))) if m else None


def check_version(doc: dict, fmt: str) -> str | None:
    """The version rule of FORMAT 2 for ``fmt`` "house-scene" or "house-bake". Another format or another major
    version: FormatError (never read half of it). A newer minor: the note to show once. This version: None."""
    what, maker, again = _FORMATS[fmt]
    if doc.get("format") != fmt:
        raise FormatError(f"This is not a {what} package (its format is {str(doc.get('format'))[:40]!r}).")
    v = parse_version(doc.get("version"))
    if v is None:
        raise FormatError(f"This {what} has no version Fresing Render understands "
                          f"({str(doc.get('version'))[:20]!r}).")
    text = f"{v[0]}.{v[1]}"
    if v[0] > VERSION[0]:
        raise FormatError(f"This {what} was made by a newer {maker} (format {text}). Update Fresing Render to "
                          "read it.")
    if v[0] < VERSION[0]:
        raise FormatError(f"This {what} was made by an older {maker} (format {text}), which Fresing Render cannot "
                          f"read. {again}")
    if v[1] > VERSION[1]:
        return f"Made by a newer {maker} (format {text}): some extras are not used."
    return None


# ---------------------------------------------------------------------------
# the scene
# ---------------------------------------------------------------------------

@dataclass
class Storey:
    id: str
    name: str
    level: int
    elevation: float
    height: float


@dataclass
class Season:
    id: str
    label: str
    date: str
    day: int                        # day of the year of ``date`` (1 … 366)
    snow_cover: float
    wet: float
    foliage: str                    # "full" | "autumn" | "bare" (an unknown value reads as "full")


@dataclass
class Moment:
    id: str
    label: str
    season: str
    time: str
    utc_offset: str
    azimuth: float                  # degrees clockwise from north (House Planner's)
    elevation: float                # degrees above the horizon, negative at night
    direction: tuple                # unit vector towards the sun, G
    clouds: float
    low_clouds: float
    visibility: float               # metres
    lamps: object                   # "all" | "none" | tuple of lamp ids (an unknown text reads as "none")


@dataclass
class Camera:
    id: str
    label: str
    position: tuple                 # G
    target: tuple                   # G
    fov: float                      # vertical, degrees


@dataclass
class Surface:
    id: str
    kind: str                       # an unknown kind reads as "other" …
    raw_kind: str                   # … and this keeps the text
    storey: str | None
    group: str
    bake: str                       # "MAP" | "VERTEX" | "NO"
    hash: str | None                # as the scene states it (None for a lamp without a mesh)
    uv1_px: tuple | None            # (W, H) for MAP
    node: int
    mesh: int | None
    matrix: tuple                   # 16 numbers, column-major, world, G
    moved: bool                     # the node has a world transform (matrix not the identity)
    verts: int                      # all primitives
    box: tuple                      # (x0, y0, z0, x1, y1, z1), world, G (a lamp without a mesh: its point)
    source: str | None
    material: str | None
    light: int | None               # KHR_lights_punctual light index on the node
    texels_per_m: float | None      # the surface's own density, when it has one


@dataclass
class Recipe:
    light: str
    preset: str
    texels_per_m: float
    texels_per_m_by_group: dict
    samples: int                    # resolved: given, else 16 / 64 / 256 by preset (64 for an unknown preset)
    page_size: int
    include_storeys: list
    include_groups: list
    open_storeys: list
    seasons: list
    moments: list
    cameras: dict
    photos: list                    # dicts: id, label, camera, moment, size (W, H), falling (dict or None)
    videos: list                    # dicts: … + kind, seconds, fps (unknown kinds dropped, fps fixed to 25)


@dataclass
class Scene:
    doc: dict
    files: dict
    glb: bytes
    id: str
    title: str
    version_id: str
    version_name: str
    scene_hash: str
    place: dict                     # latitude, longitude, north (x, z), ground_level
    storeys: list
    recipe: Recipe
    surfaces: dict                  # id -> Surface, in node order
    notes: list                     # plain sentences: a newer minor, a hash that does not match its geometry, …
    gltf: tuple = field(default=None, repr=False)     # (doc, binary) of house.glb, parsed once

    def season(self, season_id: str) -> Season | None:
        return next((s for s in self.recipe.seasons if s.id == season_id), None)

    def moment(self, moment_id: str) -> Moment | None:
        return next((m for m in self.recipe.moments if m.id == moment_id), None)


def storey_level(scene: Scene, storey_id) -> int | None:
    """The ``level`` of a storey (0 = ground floor), or None (plot parts have no storey)."""
    return next((s.level for s in scene.storeys if s.id == storey_id), None)


def surface_density(recipe: Recipe, surface: Surface) -> float:
    """A MAP surface's texels per metre (FORMAT 6 rule 1): its own, else its group's, else the recipe's."""
    if surface.texels_per_m:
        return float(surface.texels_per_m)
    return float(recipe.texels_per_m_by_group.get(surface.group, recipe.texels_per_m))


def _num(x, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise FormatError(f"scene.json: {what} is not a number.")
    return float(x)


def _vec(x, n: int, what: str) -> tuple:
    if not isinstance(x, list) or len(x) != n:
        raise FormatError(f"scene.json: {what} is not {n} numbers.")
    return tuple(_num(v, what) for v in x)


def _text(x, what: str, default=None) -> str:
    if x is None and default is not None:
        return default
    if not isinstance(x, str):
        raise FormatError(f"scene.json: {what} is missing or not text.")
    return x


def _day_of_year(text: str, what: str) -> int:
    try:
        return _date.fromisoformat(text).timetuple().tm_yday
    except (TypeError, ValueError):
        raise FormatError(f"scene.json: {what} {str(text)[:20]!r} is not a date (YYYY-MM-DD).") from None


def _falling(f) -> dict | None:
    if not isinstance(f, dict):
        return None
    return {k: float(f.get(k, d)) for k, d in (("rain", 0.0), ("snow", 0.0), ("wind", 0.0), ("wind_from", 0.0))}


def _recipe(r: dict, notes: list) -> Recipe:
    """The recipe, with FORMAT 13's rules for open-list values a newer minor version may bring."""
    if not isinstance(r, dict):
        raise FormatError("scene.json has no recipe.")
    light = r.get("light")
    if light not in LIGHTS:
        raise FormatError(f"scene.json: the light choice {str(light)[:20]!r} is not one of {', '.join(LIGHTS)}.")
    q = r.get("quality") or {}
    preset = _text(q.get("preset"), "recipe.quality.preset")
    samples = q.get("samples")
    if samples is None:
        samples = PRESET_SAMPLES.get(preset, PRESET_SAMPLES["NORMAL"])     # unknown preset: NORMAL (FORMAT 13)
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
        raise FormatError("scene.json: recipe.quality.samples is not a whole number.")
    page = q.get("page_size")
    if page not in (1024, 2048):
        raise FormatError(f"scene.json: recipe.quality.page_size {str(page)[:10]} is not 1024 or 2048.")
    by_group = {str(k): _num(v, "recipe.quality.texels_per_m_by_group")
                for k, v in (q.get("texels_per_m_by_group") or {}).items()}
    inc = r.get("include") or {}
    seasons = []
    for s in r.get("seasons") or []:
        fol = s.get("foliage")
        seasons.append(Season(
            id=_text(s.get("id"), "a season's id"), label=_text(s.get("label"), "a season's label", ""),
            date=_text(s.get("date"), "a season's date"), day=_day_of_year(s.get("date"), "a season's date"),
            snow_cover=_num(s.get("snow_cover", 0.0), "snow_cover"), wet=_num(s.get("wet", 0.0), "wet"),
            foliage=fol if fol in FOLIAGE else "full"))
    if not seasons:
        raise FormatError("scene.json: the recipe has no seasons.")
    season_ids = {s.id for s in seasons}
    moments = []
    for m in r.get("moments") or []:
        mid = _text(m.get("id"), "a moment's id")
        if m.get("season") not in season_ids:
            raise FormatError(f"scene.json: moment '{mid}' names season {str(m.get('season'))[:64]!r}, which is "
                              "not in the recipe.")
        sun = m.get("sun") or {}
        sky = m.get("sky") or {}
        lamps = m.get("lamps")
        if isinstance(lamps, list):
            lamps = tuple(str(x) for x in lamps)
        elif lamps not in ("all", "none"):
            lamps = "none"                                            # an unknown value (FORMAT 13)
        moments.append(Moment(
            id=mid, label=_text(m.get("label"), "a moment's label", ""), season=m["season"],
            time=_text(m.get("time"), "a moment's time"), utc_offset=_text(m.get("utc_offset"), "utc_offset"),
            azimuth=_num(sun.get("azimuth"), f"moment '{mid}' sun.azimuth"),
            elevation=_num(sun.get("elevation"), f"moment '{mid}' sun.elevation"),
            direction=_vec(sun.get("direction"), 3, f"moment '{mid}' sun.direction"),
            clouds=_num(sky.get("clouds", 0.0), "clouds"), low_clouds=_num(sky.get("low_clouds", 0.0), "low_clouds"),
            visibility=_num(sky.get("visibility", 40000.0), "visibility"), lamps=lamps))
    if not moments:
        raise FormatError("scene.json: the recipe has no moments.")
    moment_ids = {m.id for m in moments}
    cameras = {}
    for c in r.get("cameras") or []:
        cid = _text(c.get("id"), "a camera's id")
        cameras[cid] = Camera(id=cid, label=_text(c.get("label"), "a camera's label", ""),
                              position=_vec(c.get("position"), 3, f"camera '{cid}' position"),
                              target=_vec(c.get("target"), 3, f"camera '{cid}' target"),
                              fov=_num(c.get("fov"), f"camera '{cid}' fov"))

    def shot(p, kind):
        pid = _text(p.get("id"), f"a {kind}'s id")
        if p.get("camera") not in cameras or p.get("moment") not in moment_ids:
            notes.append(f"The {kind} '{pid}' names a camera or moment the recipe does not have: it is skipped.")
            return None
        size = p.get("size")
        if not (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and v > 0 for v in size)):
            notes.append(f"The {kind} '{pid}' has no size in pixels: it is skipped.")
            return None
        return {"id": pid, "label": str(p.get("label") or pid), "camera": p["camera"], "moment": p["moment"],
                "size": tuple(size), "falling": _falling(p.get("falling"))}

    photos = [x for x in (shot(p, "photo") for p in r.get("photos") or []) if x]
    videos = []
    for v in r.get("videos") or []:
        if v.get("kind") not in VIDEO_KINDS:
            notes.append(f"The video '{str(v.get('id'))[:64]}' is of a kind this version cannot make "
                         f"({str(v.get('kind'))[:20]!r}): it is skipped.")
            continue
        x = shot(v, "video")
        if x:
            fps = v.get("fps")
            x.update(kind=v["kind"], seconds=_num(v.get("seconds"), "a video's seconds"),
                     fps=fps if fps in FPS and not isinstance(fps, bool) else DEFAULT_FPS)
            videos.append(x)
    return Recipe(light=light, preset=preset, texels_per_m=_num(q.get("texels_per_m"), "recipe.quality.texels_per_m"),
                  texels_per_m_by_group=by_group, samples=int(samples), page_size=int(page),
                  include_storeys=list(inc.get("storeys") or []), include_groups=list(inc.get("groups") or []),
                  open_storeys=[str(s) for s in r.get("open_storeys") or []], seasons=seasons, moments=moments,
                  cameras=cameras, photos=photos, videos=videos)


# ---- house.glb ----

def glb_meshes(glb: bytes) -> tuple[dict, bytes]:
    """(the glTF document, its binary chunk) of a .glb (``core/web3d.read_glb``); FormatError when it is none."""
    try:
        doc, binary = web3d.read_glb(glb)
    except (ValueError, struct.error, UnicodeDecodeError) as e:
        raise FormatError(f"house.glb cannot be read ({e}).") from None
    if not isinstance(doc, dict):
        raise FormatError("house.glb has no glTF document.")
    return doc, binary


def mesh_arrays(doc: dict, binary: bytes, mesh: int) -> list[dict]:
    """The primitives of a mesh as arrays, in order: dicts with ``positions`` (n, 3) float32, ``normals`` (n, 3) or
    None, ``uv1`` (n, 2) or None (TEXCOORD_1, glTF's v), ``indices`` (k,) uint32 or None."""
    out = []
    for prim in doc["meshes"][mesh]["primitives"]:
        if prim.get("mode", 4) != 4:
            raise FormatError(f"house.glb: mesh {mesh} holds something other than triangles.")
        attrs = prim["attributes"]

        def arr(name):
            return web3d.accessor_array(doc, binary, attrs[name]) if name in attrs else None
        idx = prim.get("indices")
        out.append({"positions": np.asarray(arr("POSITION"), np.float32).reshape(-1, 3),
                    "normals": arr("NORMAL"), "uv1": arr("TEXCOORD_1"),
                    "indices": None if idx is None else
                    web3d.accessor_array(doc, binary, idx).ravel().astype(np.uint32)})
    return out


def _local_matrix(node: dict) -> np.ndarray:
    """A node's own transform (4 x 4, row-major numpy) from ``matrix`` or translation / rotation / scale."""
    if "matrix" in node:
        return np.array(node["matrix"], np.float64).reshape(4, 4).T
    t = node.get("translation", [0, 0, 0])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]], np.float64)
    m = np.eye(4)
    m[:3, :3] = r * np.asarray(s, np.float64)[None, :]
    m[:3, 3] = t
    return m


def _world_matrices(doc: dict) -> dict[int, np.ndarray]:
    """Node index -> world matrix (4 x 4) for every node reached from the default scene; FormatError for a node
    tree that is not a tree (the checker's rules)."""
    nodes = doc.get("nodes") or []
    scenes = doc.get("scenes") or []
    si = doc.get("scene", 0)
    if not isinstance(si, int) or not (0 <= si < len(scenes)):
        raise FormatError("house.glb has no scene.")
    out: dict[int, np.ndarray] = {}
    stack = [(r, np.eye(4)) for r in scenes[si].get("nodes", [])]
    while stack:
        i, parent = stack.pop()
        if not isinstance(i, int) or not (0 <= i < len(nodes)):
            raise FormatError(f"house.glb: node {i!r} does not exist.")
        if i in out:
            raise FormatError(f"house.glb: node {i} is reached twice.")
        m = parent @ _local_matrix(nodes[i])
        if not np.isfinite(m).all():
            raise FormatError(f"house.glb: node {i} has a transform that is not numbers.")
        out[i] = m
        stack.extend((c, m) for c in nodes[i].get("children", []))
    return out


def _transform(m: np.ndarray, pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, np.float64).reshape(-1, 3)
    return pts @ m[:3, :3].T + m[:3, 3]


def _surfaces(doc: dict, binary: bytes, notes: list) -> dict[str, Surface]:
    world = _world_matrices(doc)
    out: dict[str, Surface] = {}
    for i, node in enumerate(doc.get("nodes") or []):
        hp = (node.get("extras") or {}).get("hp") if isinstance(node.get("extras"), dict) else None
        has_mesh = "mesh" in node
        if not isinstance(hp, dict):
            if has_mesh:
                notes.append(f"house.glb: node {i} has geometry but no label (extras.hp): it only casts shadows.")
            continue
        sid = hp.get("id")
        if not isinstance(sid, str) or not sid:
            raise FormatError(f"house.glb: node {i} has a label without an id.")
        if sid in out:
            raise FormatError(f"house.glb: the id '{sid}' is used by two nodes.")
        if i not in world:
            notes.append(f"house.glb: '{sid}' is not in the file's scene: it is left out.")
            continue
        bake = hp.get("bake")
        if bake not in BAKES:
            raise FormatError(f"house.glb: '{sid}' has bake {str(bake)[:20]!r}, not one of {', '.join(BAKES)}.")
        kind = str(hp.get("kind", "other"))
        m = world[i]
        light = ((node.get("extensions") or {}).get("KHR_lights_punctual") or {}).get("light")
        uv1_px = hp.get("uv1_px")
        uv1_px = (int(uv1_px[0]), int(uv1_px[1])) if bake == "MAP" and isinstance(uv1_px, list) \
            and len(uv1_px) == 2 and all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 16384
                                         for v in uv1_px) else None
        verts, h = 0, hp.get("hash")
        if has_mesh:
            try:
                prims = mesh_arrays(doc, binary, node["mesh"])
            except (KeyError, IndexError, TypeError, ValueError) as e:
                raise FormatError(f"house.glb: the geometry of '{sid}' cannot be read ({e}).") from None
            verts = sum(len(p["positions"]) for p in prims)
            pts = _transform(m, np.concatenate([p["positions"] for p in prims]))
            box = tuple(float(v) for v in np.concatenate([pts.min(0), pts.max(0)])) if len(pts) else (0.0,) * 6
            try:
                got = house_hash.hash_primitives(prims, uv1_px)
            except ValueError as e:
                raise FormatError(f"house.glb: '{sid}': {e}.") from None
            if h != got:
                notes.append(f"house.glb: '{sid}' has hash {str(h)[:32]}, its geometry gives {got}: its bake is "
                             "stored under the scene's hash.")
                h = h if isinstance(h, str) else got
            if bake == "MAP" and uv1_px is None:
                notes.append(f"house.glb: '{sid}' has a light map but no size (uv1_px): it gets no result.")
        else:
            p = m[:3, 3]
            box = tuple(float(v) for v in (*p, *p))
            h = None
        out[sid] = Surface(
            id=sid, kind=kind if kind in KINDS else "other", raw_kind=kind, storey=hp.get("storey"),
            group=str(hp.get("group", "house")), bake=bake, hash=h, uv1_px=uv1_px, node=i,
            mesh=node.get("mesh") if has_mesh else None, matrix=tuple(float(v) for v in m.T.ravel()),
            moved=bool(np.abs(m - np.eye(4)).max() > IDENTITY_TOL), verts=int(verts), box=box,
            source=hp.get("source"), material=hp.get("material"), light=light if isinstance(light, int) else None,
            texels_per_m=float(hp["texels_per_m"]) if isinstance(hp.get("texels_per_m"), (int, float)) else None)
    return out


def read_scene(src) -> Scene:
    """Read a ``.hpscene`` (a path or its bytes). FormatError for anything a reader must refuse (the zip rules,
    another format or major version, no house.glb, a broken node tree, a closed-list value it does not know);
    notes for what it reads with a rule (a newer minor version, unknown open-list values, a hash that does not match
    its geometry, a sun direction away from its angles)."""
    files = read_zip(src)
    if "scene.json" not in files:
        raise FormatError("This is not a house scene: it has no scene.json.")
    doc = _json(files["scene.json"], "scene.json")
    notes = []
    note = check_version(doc, "house-scene")
    if note:
        notes.append(note)
    glb = files.get("house.glb")
    if glb is None:
        raise FormatError("This house scene has no house.glb.")
    try:
        place = doc["place"]
        north = _vec(place["north"], 2, "place.north")
        if abs(math.hypot(*north) - 1.0) > 1e-3:
            raise FormatError("scene.json: place.north is not a unit vector.")
        place = {"latitude": _num(place["latitude"], "place.latitude"),
                 "longitude": _num(place["longitude"], "place.longitude"), "north": north,
                 "ground_level": _num(place.get("ground_level", 0.0), "place.ground_level")}
        storeys = [Storey(id=_text(s["id"], "a storey's id"), name=_text(s.get("name"), "a storey's name", ""),
                          level=int(s["level"]), elevation=_num(s.get("elevation", 0.0), "a storey's elevation"),
                          height=_num(s.get("height", 2.8), "a storey's height")) for s in doc["storeys"]]
        recipe = _recipe(doc["recipe"], notes)
        house = doc.get("house") or {}
        head = dict(id=_text(doc["id"], "id"), title=_text(doc.get("title"), "title", ""),
                    version_id=_text(house.get("version_id"), "house.version_id", ""),
                    version_name=_text(house.get("version_name"), "house.version_name", ""),
                    scene_hash=_text(doc.get("scene_hash"), "scene_hash"))
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as e:
        if isinstance(e, FormatError):
            raise
        raise FormatError(f"scene.json is not a house scene Fresing Render can read ({type(e).__name__}: "
                          f"{e}).") from None
    gdoc, binary = glb_meshes(glb)
    try:
        surfaces = _surfaces(gdoc, binary, notes)
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as e:
        if isinstance(e, FormatError):
            raise
        raise FormatError(f"house.glb cannot be read ({type(e).__name__}: {e}).") from None
    want = house_hash.scene_hash({k: s.hash for k, s in surfaces.items() if s.hash})
    if want != head["scene_hash"]:
        notes.append(f"The scene's hash {head['scene_hash'][:32]} does not match its surfaces ({want}).")
    lamps = {k for k, s in surfaces.items() if s.light is not None}
    for m in recipe.moments:
        off = sun_mismatch(m, north)
        if off > SUN_TOL:
            notes.append(f"Moment '{m.id}': its sun direction is {off:.1f}° from its azimuth and elevation; the "
                         "direction is used.")
        if isinstance(m.lamps, tuple) and any(x not in lamps for x in m.lamps):
            notes.append(f"Moment '{m.id}' switches on a lamp the house does not have.")
    return Scene(doc=doc, files=files, glb=glb, place=place, storeys=storeys, recipe=recipe, surfaces=surfaces,
                 notes=notes, gltf=(gdoc, binary), **head)


def world_triangles(scene: Scene, surface_id: str) -> tuple[np.ndarray, np.ndarray]:
    """A surface's points in the world (n, 3) float64, G, and its triangles (m, 3) into them – all primitives in
    the .glb's order (the vertex order light per vertex follows)."""
    s = scene.surfaces[surface_id]
    if s.mesh is None:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    doc, binary = scene.gltf if scene.gltf else glb_meshes(scene.glb)
    pts, tris, base = [], [], 0
    for p in mesh_arrays(doc, binary, s.mesh):
        n = len(p["positions"])
        idx = np.arange(n) if p["indices"] is None else p["indices"].astype(np.int64)
        pts.append(p["positions"])
        tris.append(idx.reshape(-1, 3) + base)
        base += n
    m = np.array(s.matrix, np.float64).reshape(4, 4).T
    return _transform(m, np.concatenate(pts)), np.concatenate(tris)


# ---------------------------------------------------------------------------
# the sun (FORMAT 7.5)
# ---------------------------------------------------------------------------

def gltf_to_blender(v) -> tuple:
    """glTF (x, y, z) -> Blender (x, -z, y), as Blender's glTF importer turns the house."""
    x, y, z = (float(a) for a in v)
    return (x, -z, y)


def sun_angles(direction_g) -> tuple[float, float]:
    """(elevation, scene azimuth) in degrees of a direction towards the sun given in glTF axes. Scene azimuth: the
    studio convention of ``core/weather.py`` – 0° = Blender's +X, 90° = +Y, counter-clockwise seen from above."""
    x, y, z = gltf_to_blender(direction_g)
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def _wrap(a: float) -> float:
    """An angle in degrees into (-180, 180]."""
    a = (a + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


def sun_rotation_deg(scene_az: float, zero_az: float = 90.0) -> float:
    """The sky texture's ``sun_rotation`` (degrees) for a sun at ``scene_az``: 0109's sky turns its sun from
    ``zero_az`` (``weather_sky.SUN_ROTATION_ZERO_AZ``) the other way round, so rotation = zero_az - az."""
    return _wrap(zero_az - scene_az)


def north_scene_az(north_xz) -> float:
    """``place.north`` (glTF x, z) as a scene azimuth (0109's ``State.north``): G (x, z) -> B (x, -z)."""
    x, z = north_xz
    return math.degrees(math.atan2(-z, x))


def _sun_vector(azimuth: float, elevation: float, north_xz) -> tuple:
    """Unit vector towards the sun in G from a compass azimuth (clockwise from north seen from above) and an
    elevation – as House Planner writes it (east = north turned clockwise: (-north.z, north.x))."""
    a, e = math.radians(azimuth), math.radians(elevation)
    nx, nz = north_xz
    ex, ez = -nz, nx
    return (math.cos(e) * (math.cos(a) * nx + math.sin(a) * ex), math.sin(e),
            math.cos(e) * (math.cos(a) * nz + math.sin(a) * ez))


def _angle(u, v) -> float:
    u, v = np.asarray(u, np.float64), np.asarray(v, np.float64)
    c = float(u @ v) / ((np.linalg.norm(u) * np.linalg.norm(v)) or 1.0)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def sun_mismatch(moment: Moment, north_xz) -> float:
    """Degrees between a moment's ``direction`` and the direction its ``azimuth`` and ``elevation`` give."""
    return _angle(moment.direction, _sun_vector(moment.azimuth, moment.elevation, north_xz))


def _reachable_latitude(elevation: float, dec: float, latitude: float) -> float:
    """The latitude nearest ``latitude`` (within 0109's ±70°) at which the sun reaches ``elevation`` on a day with
    declination ``dec``: the noon height is 90 - |lat - dec|, the midnight depth -90 + |lat + dec|."""
    e = max(-89.99, min(89.99, elevation))
    lo = max(dec - (90.0 - e), -dec - (90.0 + e), -weather.MAX_LATITUDE)
    hi = min(dec + (90.0 - e), -dec + (90.0 + e), weather.MAX_LATITUDE)
    margin = 1e-3
    if lo <= latitude <= hi:
        return latitude
    return min(max(latitude, lo + margin), hi - margin)


def weather_sun(elevation: float, scene_az: float, day: int, latitude: float, *, bearing: float | None = None) -> dict:
    """The 0109 weather settings (``core/weather.State`` fields) whose sun stands at House Planner's ``elevation``
    and ``scene_az``. 0109 works its sun out from the hour, day, latitude and north, and has no way to take given
    angles: so the hour is chosen for the elevation (closed form of ``weather.sun_position``) and north for the
    azimuth. ``bearing`` (House Planner's compass azimuth) picks the morning or afternoon hour whose bearing is nearer
    it, so north lands near the real north (wind directions stay right); without it the morning is used. When the
    elevation is out of reach on that day at that latitude (0109's sun formula is not House Planner's), the latitude
    is moved – as little as needed, within ±70°. ``derive(State(**result))`` then gives ``sun_el`` = elevation and
    ``sun_az`` = scene_az."""
    dec = weather.declination(day)
    lat = _reachable_latitude(elevation, dec, latitude)
    phi, d = math.radians(lat), math.radians(dec)
    c = (math.sin(math.radians(elevation)) - math.sin(phi) * math.sin(d)) / (math.cos(phi) * math.cos(d))
    h = math.degrees(math.acos(max(-1.0, min(1.0, c)))) / 15.0          # hours from noon
    hours = (12.0 - h, 12.0 + h)
    if bearing is not None:
        hours = sorted(hours, key=lambda t: abs(_wrap(weather.sun_position(t, day, lat)[1] - bearing)))
    hour = hours[0]
    got_bearing = weather.sun_position(hour, day, lat)[1]
    return {"hour": hour, "use_date": True, "day": int(day), "latitude": lat,
            "north": _wrap(scene_az + got_bearing)}


def moment_sun(scene: Scene, moment: Moment) -> dict:
    """Everything the bake needs of a moment's sun: ``elevation`` and ``scene_az`` (from its direction),
    ``sun_rotation`` (degrees, for 0109's sky), ``night``, ``mismatch`` (degrees to its own angles) and ``weather``
    (:func:`weather_sun`)."""
    el, az = sun_angles(moment.direction)
    season = scene.season(moment.season)
    return {"elevation": el, "scene_az": az, "sun_rotation": sun_rotation_deg(az), "night": el < 0.0,
            "mismatch": sun_mismatch(moment, scene.place["north"]),
            "weather": weather_sun(el, az, season.day, scene.place["latitude"], bearing=moment.azimuth)}


# ---------------------------------------------------------------------------
# light encoding (FORMAT 8.3)
# ---------------------------------------------------------------------------

def _clean(L) -> np.ndarray:
    """Light values as float64 with NaN -> 0, +inf -> very bright, -inf -> 0."""
    return np.nan_to_num(np.asarray(L, np.float64), nan=0.0, posinf=1e30, neginf=0.0)


def encode(L, scale: float) -> np.ndarray:
    """b = clamp(round(255 x sqrt(max(L, 0) / scale)), 0, 255), round half away from zero (FORMAT 5, 8.3) – not
    0107's ``encode``, which rounds half to even. uint8, the shape of ``L``."""
    x = 255.0 * np.sqrt(np.maximum(_clean(L), 0.0) / float(scale))
    return np.clip(house_hash.round_half_away(x), 0, 255).astype(np.uint8)


def decode(b, scale: float) -> np.ndarray:
    """L = scale x (b / 255) ^ 2, float32."""
    return (float(scale) * (np.asarray(b, np.float64) / 255.0) ** 2).astype(np.float32)


def moment_scale(arrays) -> float:
    """The 99.9th percentile of all channel values of a moment's results (FORMAT 8.3's recommendation); always
    positive: the brightest value when the percentile is 0, else 1.0 when everything is dark."""
    vals = [np.maximum(_clean(a).ravel(), 0.0) for a in arrays]
    vals = np.concatenate(vals) if vals else np.zeros(0)
    if not vals.size:
        return 1.0
    p = float(np.percentile(vals, 99.9))
    if p > 0.0 and math.isfinite(p):
        return p
    top = float(vals.max())
    return top if top > 0.0 and math.isfinite(top) else 1.0


# ---------------------------------------------------------------------------
# pages (FORMAT 8.3)
# ---------------------------------------------------------------------------

def _shelf(items, side: int, gap: int):
    """Rows, tallest first: (pages used, {key: (page, x, y)})."""
    rects, page, x, y, row = {}, 0, 0, 0, 0
    for key, (w, h) in items:
        if x > 0 and x + w > side:                  # next row
            x, y, row = 0, y + row + gap, 0
        if y + h > side:                            # next page
            page, x, y, row = page + 1, 0, 0, 0
        rects[key] = (page, x, y)
        x += w + gap
        row = max(row, h)
    return (page + 1 if items else 0), rects


def layout(sizes: dict, page_size: int, gap: int = GAP) -> tuple[list, dict]:
    """Rectangles of the given sizes {key: (W, H)} on square pages: ``(pages [(w, h)], rects {key: (page, x,
    y)})``. Rows, tallest first, ``gap`` texels between rects; the page side is one of 256 … 2048, at most
    ``page_size``: the one that holds everything in the fewest pages, the smallest of those. A rect larger than
    ``page_size`` is left out (the caller names it)."""
    sides = [s for s in SIDES if s <= page_size]
    fits = {k: (int(w), int(h)) for k, (w, h) in sizes.items()
            if sides and 0 < w <= sides[-1] and 0 < h <= sides[-1]}
    if not fits:
        return [], {}
    items = sorted(fits.items(), key=lambda kv: (-kv[1][1], -kv[1][0], str(kv[0])))
    best = None
    for side in sides:
        if any(w > side or h > side for w, h in fits.values()):
            continue
        n, rects = _shelf(items, side, gap)
        if best is None or n < best[0]:
            best = (n, side, rects)
    n, side, rects = best
    return [(side, side)] * n, rects


def page_png(rgb) -> bytes:
    """A page as PNG: 8-bit RGB, not interlaced, no colour chunks (``core/web3d.png``); rows top-down."""
    a = np.ascontiguousarray(rgb, np.uint8)
    if a.ndim != 3 or a.shape[2] != 3:
        raise ValueError("a page is (h, w, 3) bytes")
    return web3d.png(a)


def png_page_problem(data: bytes) -> str | None:
    """Why a PNG is not a light-map page (FORMAT 8.3: 8-bit RGB, not interlaced, no colour chunks), or None."""
    if data[:8] != PNG_SIG:
        return "is not a PNG"
    pos, first = 8, True
    while pos + 8 <= len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        if first:
            if kind != b"IHDR" or n != 13:
                return "has no IHDR first"
            _, _, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", data[pos + 8:pos + 21])
            if (depth, ctype) != (8, 2):
                return f"is {depth}-bit colour type {ctype}, not 8-bit RGB"
            if inter:
                return "is interlaced"
            first = False
        if kind in COLOUR_CHUNKS:
            return f"has a {kind.decode()} chunk"
        if kind == b"IEND":
            return None
        pos += 12 + n
    return "is cut off"


# ---------------------------------------------------------------------------
# the bake package
# ---------------------------------------------------------------------------

def _plain(text: str) -> str:
    """A problems line: no control characters (FORMAT 2), at most 500 characters (the schema)."""
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(text)).strip()[:500]


def _snow_layers(glb: bytes) -> dict[str, dict]:
    """The layers of a snow .glb: id -> {verts, storey, group, bake, kind}."""
    doc, binary = glb_meshes(glb)
    out = {}
    for node in doc.get("nodes") or []:
        hp = (node.get("extras") or {}).get("hp") if isinstance(node.get("extras"), dict) else None
        if not isinstance(hp, dict) or "mesh" not in node:
            continue
        mesh = doc["meshes"][node["mesh"]]
        verts = sum(int(doc["accessors"][p["attributes"]["POSITION"]]["count"]) for p in mesh["primitives"])
        out[str(hp.get("id"))] = {"verts": verts, "storey": hp.get("storey"), "group": hp.get("group"),
                                  "bake": hp.get("bake"), "kind": hp.get("kind")}
    return out


def _created(created) -> str:
    if created is None:
        created = datetime.now(timezone.utc)
    if isinstance(created, datetime):
        created = created.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(created)


class BakeWriter:
    """Collects a bake's results and writes the ``.hpbake``. Nothing a reader must refuse is written: a result of
    the wrong kind or shape, an unknown id, a snow file for an unknown season … are left out with a ``problems``
    line (plain sentences, shown to the owner by House Planner)."""

    def __init__(self, scene: Scene, *, light: str, samples: int, denoised: bool = True, app_version: str = "",
                 bake_id: str | None = None, created=None):
        if light != scene.recipe.light:
            # FORMAT 8.1: light MUST be the recipe's (SOFT at night is still written as SOFT)
            raise ValueError(f"the bake's light {light!r} must be the recipe's {scene.recipe.light!r}")
        self.scene = scene
        self.light = light
        self.samples = max(1, int(samples))
        self.denoised = bool(denoised)
        self.app_version = str(app_version)[:40]
        self.created = _created(created)
        stamp = re.sub(r"[^0-9]", "", self.created)[:14]
        self.bake_id = bake_id if bake_id and ID_RE.match(bake_id) else f"fr-{stamp or 'bake'}"
        self.problems: list[str] = []
        self._moments: dict[str, dict] = {}            # id -> {entry, pages, vertex_files, files}
        self._snow: dict[str, tuple] = {}              # season -> (file, bytes)
        self._snow_ids: dict[str, dict] = {}           # snow id -> layer info + season
        self._photos: dict[str, tuple] = {}            # id -> (entry, file, bytes)
        self._videos: dict[str, tuple] = {}
        self._layout()

    def problem(self, text: str) -> None:
        line = _plain(text)
        if line and line not in self.problems:
            self.problems.append(line)

    # ---- one rect layout for every moment ----
    def _layout(self):
        sc, rec = self.scene, self.scene.recipe
        sizes = {("", sid): s.uv1_px for sid, s in sc.surfaces.items() if s.bake == "MAP" and s.uv1_px}
        for st in rec.open_storeys:
            sizes.update({(st, sid): s.uv1_px for sid, s in sc.surfaces.items()
                          if s.bake == "MAP" and s.uv1_px and s.storey == st})
        self.pages, self.rects = layout(sizes, rec.page_size)
        for key in sorted(set(sizes) - set(self.rects)):
            if not key[0]:
                w, h = sizes[key]
                self.problem(f"{key[1]}: its {w} x {h} light map is larger than a {rec.page_size} px page; it is "
                             "left out.")
        if len(self.pages) > PHONE_PAGES:
            self.problem(f"One moment needs {len(self.pages)} light-map pages, more than a phone should hold "
                         f"({PHONE_PAGES}).")

    # ---- snow ----
    def add_snow(self, season_id: str, glb_bytes: bytes) -> None:
        """A season's snow layers (FORMAT 8.6) as ``snow/<season>.glb``; their light comes per vertex in that
        season's moments (``add_moment`` with the snow ids)."""
        if self.scene.season(season_id) is None:
            self.problem(f"Snow for season '{season_id}', which the recipe does not have, is left out.")
            return
        try:
            layers = _snow_layers(glb_bytes)
        except (FormatError, KeyError, IndexError, TypeError, ValueError) as e:
            self.problem(f"The snow of season '{season_id}' cannot be read ({e}); it is left out.")
            return
        clash = [k for k in layers if k in self.scene.surfaces or (k in self._snow_ids
                                                                    and self._snow_ids[k]["season"] != season_id)]
        if clash:
            self.problem(f"The snow of season '{season_id}' reuses the id '{clash[0]}'; it is left out.")
            return
        for k in [k for k, v in self._snow_ids.items() if v["season"] == season_id]:
            del self._snow_ids[k]
        self._snow[season_id] = (f"snow/{season_id}.glb", bytes(glb_bytes))
        for k, v in layers.items():
            self._snow_ids[k] = dict(v, season=season_id)

    # ---- results ----
    def _accept(self, sid: str, arr, season: str, where: str):
        """('MAP', array (H, W, 3)) or ('VERTEX', array (n, 3)) for a valid result, else None (+ a problems line)."""
        s = self.scene.surfaces.get(sid)
        snow = self._snow_ids.get(sid)
        if s is None and snow is None:
            self.problem(f"{where}: '{sid}' is not a surface of the house; its result is left out.")
            return None
        if snow is not None and snow["season"] != season:
            self.problem(f"{where}: '{sid}' is snow of season '{snow['season']}'; its result is left out.")
            return None
        a = np.asarray(arr)
        bake = s.bake if s is not None else "VERTEX"
        if bake == "MAP":
            want = (s.uv1_px[1], s.uv1_px[0], 3) if s.uv1_px else None
        elif bake == "VERTEX":
            want = ((s.verts if s is not None else snow["verts"]), 3)
        else:
            self.problem(f"{where}: '{sid}' takes part in the light only (bake NO); its result is left out.")
            return None
        if want is None or a.shape != want or not np.issubdtype(a.dtype, np.number):
            self.problem(f"{where}: the result of '{sid}' has the shape {tuple(a.shape)}, its surface needs "
                         f"{want}; it is left out.")
            return None
        return bake, a

    def add_moment(self, moment_id: str, maps: dict, open: dict | None = None, *, reference, exposure,
                   sun_light=None) -> None:
        """One baked moment. ``maps`` {id: array}: MAP -> (H, W, 3) float in Blender's rows (row 0 = the bottom;
        PNG row r = row H - 1 - r), VERTEX (and snow ids of the moment's season) -> (vertices, 3) in the .glb's
        order. ``open`` {storey: {id: array}} for the recipe's open storeys, that storey's surfaces only.
        ``reference`` RGB (0107's probe), ``exposure`` EV (0109's ``exposure_for``), ``sun_light`` RGB or None:
        written only for SOFT in daylight. Calling it again for the same moment replaces it."""
        sc, rec = self.scene, self.scene.recipe
        m = sc.moment(moment_id)
        if m is None:
            self.problem(f"Results for moment '{moment_id}', which the recipe does not have, are left out.")
            return
        if self.light == "LIVE":
            if maps or open:
                self.problem("The light choice is Live only: baked light is not written.")
            return
        variants = [("", maps or {})]
        for st, res in (open or {}).items():
            if st not in rec.open_storeys:
                self.problem(f"Moment '{moment_id}': storey '{st}' is not baked open in the recipe; its results are "
                             "left out.")
                continue
            variants.append((st, res or {}))
        accepted = []            # (variant, sid, kind, array)
        for st, res in variants:
            where = f"Moment '{moment_id}'" + (f" (open '{st}')" if st else "")
            for sid, arr in res.items():
                got = self._accept(sid, arr, m.season, where)
                if got is None:
                    continue
                if st:
                    on = sc.surfaces[sid].storey if sid in sc.surfaces else self._snow_ids[sid]["storey"]
                    if on != st:
                        self.problem(f"{where}: '{sid}' is not on that storey; its result is left out.")
                        continue
                if got[0] == "MAP" and (st, sid) not in self.rects:
                    continue                        # too big for a page: named once in _layout
                accepted.append((st, sid, got[0], got[1]))
        bad = sum(int(np.size(a) - np.isfinite(np.asarray(a, np.float64)).sum()) for *_, a in accepted)
        if bad:
            self.problem(f"Moment '{moment_id}': {bad} light values were not numbers and are written as 0.")
        scale = moment_scale([a for *_, a in accepted])
        index = [x.id for x in rec.moments].index(moment_id)
        # pages: one canvas per page of the layout that holds a result
        canvases: dict[int, np.ndarray] = {}
        for st, sid, kind, a in accepted:
            if kind == "MAP":
                k, x, y = self.rects[(st, sid)]
                if k not in canvases:
                    w, h = self.pages[k]
                    canvases[k] = np.zeros((h, w, 3), np.uint8)
                H, W = a.shape[:2]
                canvases[k][y:y + H, x:x + W] = encode(a, scale)[::-1]     # Blender rows bottom-up -> PNG top-down
        page_ids, pages, files = {}, [], {}
        for k in sorted(canvases):
            pid = f"m{index}p{k}"
            path = f"light/{moment_id}-p{k}.png"
            page_ids[k] = pid
            files[path] = page_png(canvases[k])
            pages.append({"id": pid, "file": path, "size": list(self.pages[k])})
        vid, vpath, chunks, offset = f"m{index}v", f"light/{moment_id}-v.bin", [], 0
        out = {"": {}}
        out.update({st: {} for st, _ in variants if st})
        for st, sid, kind, a in accepted:
            if kind == "MAP":
                k, x, y = self.rects[(st, sid)]
                out[st][sid] = {"page": page_ids[k], "rect": [x, y, int(a.shape[1]), int(a.shape[0])]}
            else:
                b = encode(a, scale)
                chunks.append(b.tobytes())
                out[st][sid] = {"vertex": vid, "offset": offset, "count": int(len(b))}
                offset += len(b)
        vfiles = []
        if chunks:
            files[vpath] = b"".join(chunks)
            vfiles.append({"id": vid, "file": vpath})
        sun = None
        if self.light == "SOFT" and m.elevation >= 0.0 and sun_light is not None:
            sun = [float(v) for v in np.asarray(sun_light, np.float64).ravel()]
            if len(sun) != 3 or not all(math.isfinite(v) for v in sun):
                self.problem(f"Moment '{moment_id}': the sun's light is not three numbers; it is left out.")
                sun = None
            else:
                sun = [max(v, 0.0) for v in sun]
        ref = [float(v) for v in _clean(reference).ravel()[:3]]
        ref = [max(v, 0.0) for v in ref] + [0.0] * (3 - len(ref))
        ev = float(exposure) if math.isfinite(float(exposure)) else 0.0
        entry = {"id": moment_id,
                 "encoding": {"curve": 2.0, "scale": scale, "reference": ref, "exposure": ev},
                 "sun_light": sun, "maps": out[""], "open": {st: out[st] for st in out if st}}
        self._moments[moment_id] = {"entry": entry, "pages": pages, "vertex_files": vfiles, "files": files,
                                    "index": index}

    # ---- photos and videos ----
    def _shot(self, kind: str, sid: str, moment, camera):
        want = {p["id"]: p for p in (self.scene.recipe.photos if kind == "photo" else self.scene.recipe.videos)}
        if sid not in want:
            self.problem(f"The {kind} '{sid}' is not in the recipe; it is left out.")
            return None
        r = want[sid]
        if moment is not None and moment != r["moment"]:
            self.problem(f"The {kind} '{sid}' was made at moment '{moment}', the recipe asked for "
                         f"'{r['moment']}'; it is left out.")
            return None
        cam = self.scene.recipe.cameras[r["camera"]]
        if camera is None:
            camera = {"position": cam.position, "target": cam.target, "fov": cam.fov}
        camera = {"position": [float(v) for v in camera["position"]], "target": [float(v) for v in camera["target"]],
                  "fov": float(camera["fov"])}
        return r, camera

    def add_photo(self, photo_id: str, data: bytes, ext: str, size=None, moment=None, camera: dict | None = None):
        """A photo of the recipe as ``photos/<id>.<ext>`` (png, jpg). ``size`` is read from the picture itself;
        ``moment`` and ``camera`` default to the recipe's."""
        got = self._shot("photo", photo_id, moment, camera)
        if got is None:
            return
        r, camera = got
        ext = str(ext).lower().lstrip(".")
        kind = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg"}.get(ext)
        real = (data[:8] == PNG_SIG and "png") or (data[:2] == b"\xff\xd8" and "jpeg") or None
        w, h = web3d.image_size(data)
        if kind is None or real != kind or not (w and h):
            self.problem(f"The photo '{photo_id}' is not a PNG or JPEG picture; it is left out.")
            return
        if size is not None and tuple(size) != (w, h):
            self.problem(f"The photo '{photo_id}' is {w} x {h} pixels, not {size[0]} x {size[1]}.")
        path = f"photos/{photo_id}.{ext}"
        entry = {"id": photo_id, "file": path, "size": [int(w), int(h)], "moment": r["moment"], "camera": camera}
        self._photos[photo_id] = (entry, path, bytes(data))

    def add_video(self, video_id: str, data: bytes, ext: str, size, moment=None, camera: dict | None = None,
                  seconds: float = 0.0, fps: int | None = None):
        """A video of the recipe as ``videos/<id>.<ext>`` (mp4, webm). bake.json has no fps (bake-1 schema): it is
        taken for the call's symmetry only."""
        got = self._shot("video", video_id, moment, camera)
        if got is None:
            return
        r, camera = got
        ext = str(ext).lower().lstrip(".")
        if ext not in ("mp4", "webm") or not data:
            self.problem(f"The video '{video_id}' is not an MP4 or WebM file; it is left out.")
            return
        seconds = float(seconds or r["seconds"])
        if not (seconds > 0 and math.isfinite(seconds)):
            self.problem(f"The video '{video_id}' has no length; it is left out.")
            return
        path = f"videos/{video_id}.{ext}"
        entry = {"id": video_id, "file": path, "size": [int(size[0]), int(size[1])], "seconds": seconds,
                 "moment": r["moment"], "camera": camera}
        self._videos[video_id] = (entry, path, bytes(data))

    # ---- the package ----
    def _ordered_moments(self):
        return sorted(self._moments.values(), key=lambda x: x["index"])

    def bake_json(self) -> dict:
        """bake.json (schema bake-1). ``surfaces``: every surface of the house with a result – its hash as the scene
        states it, its world box and, when its node is placed, its world matrix."""
        sc = self.scene
        used = set()
        for mo in self._moments.values():
            e = mo["entry"]
            used.update(e["maps"])
            for res in e["open"].values():
                used.update(res)
        surfaces = {}
        for sid, s in sc.surfaces.items():
            if sid in used and sid not in self._snow_ids:
                d = {"hash": s.hash, "box": [float(v) for v in s.box]}
                if s.moved:
                    d["matrix"] = [float(v) for v in s.matrix]
                surfaces[sid] = d
        moments = self._ordered_moments()
        return {
            "format": "house-bake", "version": f"{VERSION[0]}.{VERSION[1]}",
            "generator": {"app": APP, "version": self.app_version},
            "id": self.bake_id, "created": self.created,
            "scene": {"id": sc.id, "scene_hash": sc.scene_hash},
            "light": self.light, "uv1": "hp-uv/1",
            "quality": {"texels_per_m": float(sc.recipe.texels_per_m), "samples": self.samples,
                        "denoised": self.denoised},
            "surfaces": surfaces,
            "pages": [p for mo in moments for p in mo["pages"]],
            "vertex_files": [v for mo in moments for v in mo["vertex_files"]],
            "moments": [mo["entry"] for mo in moments],
            "snow": [{"season": s, "file": f} for s, (f, _) in sorted(self._snow.items())],
            "photos": [e for e, _, _ in self._photos.values()],
            "videos": [e for e, _, _ in self._videos.values()],
            "problems": list(self.problems),
        }

    def files(self) -> dict[str, bytes]:
        """Every file of the package, bake.json first."""
        out = {"bake.json": json.dumps(self.bake_json(), ensure_ascii=False, allow_nan=False,
                                       separators=(",", ":")).encode("utf-8")}
        for mo in self._ordered_moments():
            out.update(mo["files"])
        for f, data in self._snow.values():
            out[f] = data
        for _, f, data in list(self._photos.values()) + list(self._videos.values()):
            out[f] = data
        return out

    def write(self, path) -> None:
        """Write the .hpbake: JSON and vertex files deflated, pictures, models and videos stored (FORMAT 2: they
        are compressed already); a temporary file next to it, then moved into place (a half-written package never
        has the name)."""
        files = self.files()
        stamp = datetime.strptime(self.created[:19], "%Y-%m-%dT%H:%M:%S").timetuple()[:6] \
            if re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", self.created) else (2026, 1, 1, 0, 0, 0)
        folder = os.path.dirname(os.path.abspath(path))
        fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "wb") as fh, zipfile.ZipFile(fh, "w") as zf:
                for name, data in files.items():
                    info = zipfile.ZipInfo(name, max(stamp, (1980, 1, 1, 0, 0, 0)))
                    info.external_attr = 0o644 << 16
                    deflate = name.endswith((".json", ".bin"))
                    info.compress_type = zipfile.ZIP_DEFLATED if deflate else zipfile.ZIP_STORED
                    zf.writestr(info, data)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise


# ---------------------------------------------------------------------------
# a light check of a written package (no jsonschema)
# ---------------------------------------------------------------------------

def structure_problems(src, scene: Scene | None = None) -> list[str]:
    """What is wrong with a .hpbake's structure ([] = fine): the zip rules, the version, every file bake.json names
    is there, pages are 8-bit RGB PNGs without colour chunks of their stated size, rects lie inside their pages and do
    not overlap, vertex ranges lie inside their files and do not overlap, sun_light null where it must be; with the
    ``scene``: rects = uv1_px, counts = vertex counts, MAP on pages and VERTEX per vertex, open results on their
    storey, sun_light null at night, page sizes within the recipe's. A light stand-in for the format's checker (the
    PC check has no jsonschema)."""
    try:
        files = read_zip(src)
        if "bake.json" not in files:
            return ["The package has no bake.json."]
        doc = _json(files["bake.json"], "bake.json")
        check_version(doc, "house-bake")
    except FormatError as e:
        return [str(e)]
    out: list[str] = []
    try:
        _structure(doc, files, scene, out)
    except Exception as e:  # noqa: BLE001 – a damaged package is reported, never raised
        out.append(f"bake.json cannot be read ({type(e).__name__}: {e}).")
    return out


def _structure(doc: dict, files: dict, scene: Scene | None, out: list) -> None:
    for key in ("light", "surfaces", "pages", "vertex_files", "moments", "snow", "photos", "videos"):
        if key not in doc:
            out.append(f"bake.json has no '{key}'.")
            return
    if doc["light"] not in LIGHTS:
        out.append(f"bake.json: light {doc['light']!r} is not one of {', '.join(LIGHTS)}.")
    pages, vcount = {}, {}
    for p in doc["pages"]:
        f = p["file"]
        if f not in files:
            out.append(f"Page '{p['id']}': '{f}' is not in the package.")
            continue
        why = png_page_problem(files[f])
        if why:
            out.append(f"Page '{p['id']}' ({f}) {why}.")
            continue
        w, h = struct.unpack(">II", files[f][16:24])
        if [w, h] != list(p["size"]) or w not in SIDES or h not in SIDES:
            out.append(f"Page '{p['id']}' is {w} x {h}, bake.json says {p['size']} (pages are 256 … 2048 px).")
        if scene is not None and max(w, h) > scene.recipe.page_size:
            out.append(f"Page '{p['id']}' is larger than the recipe's page size {scene.recipe.page_size}.")
        pages[p["id"]] = (w, h)
    for v in doc["vertex_files"]:
        if v["file"] not in files:
            out.append(f"Vertex file '{v['id']}': '{v['file']}' is not in the package.")
            continue
        n = len(files[v["file"]])
        if n % 3:
            out.append(f"Vertex file '{v['id']}' is not a whole number of RGB values.")
        vcount[v["id"]] = n // 3
    snow = {}
    for s in doc["snow"]:
        if s["file"] not in files:
            out.append(f"Snow '{s['season']}': '{s['file']}' is not in the package.")
            continue
        try:
            for k, info in _snow_layers(files[s["file"]]).items():
                snow[k] = dict(info, season=s["season"])
        except (FormatError, KeyError, IndexError, TypeError, ValueError) as e:
            out.append(f"Snow '{s['season']}' cannot be read ({e}).")
    nights = {m.id for m in scene.recipe.moments if m.elevation < 0} if scene is not None else set()
    seasons = {m.id: m.season for m in scene.recipe.moments} if scene is not None else {}
    on_page, on_file = {}, {}
    for m in doc["moments"]:
        mid = m["id"]
        enc = m.get("encoding") or {}
        sc_ = enc.get("scale")
        if not isinstance(sc_, (int, float)) or not (sc_ > 0 and math.isfinite(sc_)):
            out.append(f"Moment '{mid}': its scale is not a positive number.")
        if m.get("sun_light") is not None and (doc["light"] != "SOFT" or mid in nights):
            out.append(f"Moment '{mid}': sun_light must be null (light {doc['light']}"
                       + (", night" if mid in nights else "") + ").")
        if scene is not None and scene.moment(mid) is None:
            out.append(f"Moment '{mid}' is not in the recipe.")
        for st, res in [("", m.get("maps") or {})] + list((m.get("open") or {}).items()):
            where = f"Moment '{mid}'" + (f" open '{st}'" if st else "") + " "
            for sid, e in res.items():
                if sid not in doc["surfaces"] and sid not in snow:
                    out.append(where + f"'{sid}' is not in bake.json's surfaces or a snow file.")
                surf = scene.surfaces.get(sid) if scene is not None else None
                if "page" in e:
                    if e["page"] not in pages:
                        out.append(where + f"'{sid}': page '{e['page']}' is missing.")
                        continue
                    x, y, w, h = e["rect"]
                    pw, ph = pages[e["page"]]
                    if w < 1 or h < 1 or x < 0 or y < 0 or x + w > pw or y + h > ph:
                        out.append(where + f"'{sid}': rect {e['rect']} is not inside its {pw} x {ph} page.")
                        continue
                    on_page.setdefault(e["page"], []).append((x, y, x + w, y + h, sid))
                    if surf is not None and (surf.bake != "MAP" or list(surf.uv1_px or ()) != [w, h]):
                        out.append(where + f"'{sid}': rect {w} x {h}, its surface is {surf.bake} "
                                   f"{list(surf.uv1_px or ())}.")
                else:
                    if e["vertex"] not in vcount or e["offset"] + e["count"] > vcount[e["vertex"]]:
                        out.append(where + f"'{sid}': its values run past the end of vertex file '{e['vertex']}'.")
                        continue
                    on_file.setdefault(e["vertex"], []).append((e["offset"], e["offset"] + e["count"], sid))
                    want = surf.verts if surf is not None and surf.bake == "VERTEX" else \
                        snow[sid]["verts"] if sid in snow else None
                    if scene is not None and (want is None or e["count"] != want):
                        out.append(where + f"'{sid}': {e['count']} vertex values, its surface needs {want}.")
                if scene is not None and st:
                    on = surf.storey if surf is not None else snow.get(sid, {}).get("storey")
                    if on != st:
                        out.append(where + f"'{sid}' is not on that storey.")
                if sid in snow and seasons.get(mid, snow[sid]["season"]) != snow[sid]["season"]:
                    out.append(where + f"'{sid}' is snow of another season.")
    for pid, rects in on_page.items():
        rects.sort()
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                if b[0] >= a[2]:
                    break
                if b[1] < a[3] and a[1] < b[3]:
                    out.append(f"Page '{pid}': '{a[4]}' and '{b[4]}' overlap.")
    for fid, ranges in on_file.items():
        ranges.sort()
        for a, b in zip(ranges, ranges[1:]):
            if b[0] < a[1]:
                out.append(f"Vertex file '{fid}': '{a[2]}' and '{b[2]}' share values.")
    for kind in ("photos", "videos"):
        for p in doc[kind]:
            if p["file"] not in files:
                out.append(f"The {kind[:-1]} '{p['id']}': '{p['file']}' is not in the package.")
