"""The checker: a list of problems in a .hpscene or .hpbake package (FORMAT.md section 9).

``check(path_or_package, scene=None) -> Report``. ERROR = a reader must refuse the package (or that part of it);
WARNING = it can be read, but something is probably wrong or too big for a phone.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import jsonschema

from . import surface as S
from .glb import Glb, GlbError, is_identity, is_rigid
from .images import page_png_problem, picture_info
from .package import Package, PackageError, control_text
from .sun import sun_position, utc_moment

SUPPORTED = (1, 0)  # the version this checker is written for: reads 1.x, knows the fields of 1.0
SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"

GAP_PX = 4       # hp-uv/1: at least 4 texels between two charts of a surface's map
BORDER_PX = 2    # … and 2 texels between a chart and the map's edge
TOL_PX = 0.01
SITE_GROUPS = ("garden", "street", "houses", "park")
NO_LIGHT_KINDS = ("glass", "water")
PHONE_PAGES = 4          # light-map pages of one moment a phone should have to hold at once
BIG_GLB = 300 * 2**20


class Report:
    def __init__(self, name: str):
        self.name = name
        self.items: list[tuple[str, str]] = []

    def error(self, text: str):
        self.items.append(("ERROR", text))

    def warn(self, text: str):
        self.items.append(("WARNING", text))

    @property
    def errors(self):
        return [t for lv, t in self.items if lv == "ERROR"]

    @property
    def warnings(self):
        return [t for lv, t in self.items if lv == "WARNING"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def text(self) -> str:
        head = f"{self.name}: " + ("OK" if self.ok else f"{len(self.errors)} error(s)") + (
            f", {len(self.warnings)} warning(s)" if self.warnings else "")
        return "\n".join([head] + [f"  {lv}: {t}" for lv, t in self.items])


# ---------------------------------------------------------------- versions and schemas
def parse_version(v) -> tuple[int, int] | None:
    try:
        a, b = str(v).split(".")
        return int(a), int(b)
    except (ValueError, AttributeError):
        return None


def _relax(schema):
    """The schema for a newer minor version: unknown fields allowed, and new values in the lists of choices marked
    "x-extensible" (FORMAT.md section 13). Other lists and fixed values stay: a new value there is a new major."""
    s = copy.deepcopy(schema)

    def walk(x):
        if isinstance(x, dict):
            if x.get("additionalProperties") is False:
                del x["additionalProperties"]
            if x.pop("x-extensible", False) and "enum" in x:
                kinds = {type(v) for v in x.pop("enum")}
                x["type"] = "integer" if kinds == {int} else "string"
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(s)
    return s


def _schema(name: str, relaxed: bool):
    schema = json.loads((SCHEMAS / f"{name}-1.schema.json").read_text(encoding="utf-8"))
    return _relax(schema) if relaxed else schema


def _validate(doc, name: str, relaxed: bool, rep: Report, where: str) -> bool:
    v = jsonschema.Draft202012Validator(_schema(name, relaxed))
    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
    for e in errs[:30]:
        at = "/".join(str(p) for p in e.absolute_path) or "(top)"
        rep.error(f"{where} {at}: {e.message}")
    if len(errs) > 30:
        rep.error(f"{where}: … and {len(errs) - 30} more schema errors")
    return not errs


def version_check(doc: dict, expected_format: str, rep: Report) -> bool | None:
    """True = a newer minor (read relaxed), False = this version, None = refuse (error given)."""
    if doc.get("format") != expected_format:
        rep.error(f"'format' is {doc.get('format')!r}, expected {expected_format!r}")
        return None
    v = parse_version(doc.get("version"))
    if v is None:
        rep.error(f"'version' {doc.get('version')!r} is not 'major.minor'")
        return None
    if v[0] != SUPPORTED[0]:
        newer = v[0] > SUPPORTED[0]
        rep.error(f"this package is format version {v[0]}.{v[1]}; this checker reads {SUPPORTED[0]}.x"
                  + (" – it was made by a newer app: update the app (and this checker) to read it" if newer
                     else " – it is older than version 1 and cannot be read"))
        return None
    if v[1] > SUPPORTED[1]:
        rep.warn(f"format version {v[0]}.{v[1]} is newer than {SUPPORTED[0]}.{SUPPORTED[1]}: read as "
                 f"{SUPPORTED[0]}.{SUPPORTED[1]}, fields this checker does not know are ignored")
        return True
    return False


# ---------------------------------------------------------------- glb surfaces
class Surfaces:
    """The surfaces (and lamps) of a .glb: id -> info."""

    def __init__(self):
        self.by_id: dict[str, dict] = {}
        self.lamps: set[str] = set()


ALLOWED_EXTENSIONS = ("KHR_lights_punctual", "KHR_materials_transmission", "KHR_materials_emissive_strength",
                      "KHR_texture_transform")


def glb_problems(glb: Glb) -> list[str]:
    """The .glb as a whole: one scene, a tree of nodes, no required extensions, extensions version 1 knows."""
    doc = glb.json
    out = []
    if doc.get("extensionsRequired"):
        out.append(f"extensionsRequired {doc['extensionsRequired']}: version 1 allows no required extension "
                   "(no Draco, meshopt or KTX2 inside house.glb)")
    used = doc.get("extensionsUsed", [])
    if not isinstance(used, list) or any(e not in ALLOWED_EXTENSIONS for e in used):
        out.append(f"extensionsUsed {used}: version 1 allows only {', '.join(ALLOWED_EXTENSIONS)}")
    if len(doc.get("scenes", [])) != 1:
        out.append(f"{len(doc.get('scenes', []))} scenes – exactly one is allowed")
    lights = ((doc.get("extensions") or {}).get("KHR_lights_punctual") or {}).get("lights", [])
    for i, n in enumerate(doc.get("nodes", []) if isinstance(doc.get("nodes"), list) else []):
        li = ((n.get("extensions") or {}).get("KHR_lights_punctual") or {}).get("light") if isinstance(n, dict) \
            else None
        if li is not None and (not isinstance(li, int) or not (0 <= li < len(lights))):
            out.append(f"node {i}: light {li!r} does not exist")
    return out


def read_surfaces(glb: Glb, rep: Report, where: str, relaxed: bool, *, snow: bool,
                  quality: dict | None = None) -> Surfaces:
    out = Surfaces()
    for p in glb_problems(glb):
        rep.error(f"{where}: {p}")
    try:
        world = glb.world_matrices()
    except Exception as e:  # noqa: BLE001 – a broken node tree is reported, not raised
        rep.error(f"{where}: its node tree cannot be read ({e})")
        return out
    nodes = glb.json.get("nodes", [])
    surf_schema = jsonschema.Draft202012Validator(_schema("surface", relaxed))
    for i, node in enumerate(nodes):
        try:
            _one_surface(glb, i, node, world, out, rep, where, surf_schema, snow, quality)
        except Exception as e:  # noqa: BLE001 – whatever a hostile file holds: report it, never crash
            rep.error(f"{where} node {i}: cannot be read ({type(e).__name__}: {e})")
    return out


def density(hp: dict, quality: dict | None) -> float | None:
    """A MAP surface's texels per metre (FORMAT.md 6): its own value, else the recipe's for its group, else the
    recipe's default."""
    if "texels_per_m" in hp:
        return hp["texels_per_m"]
    if quality is None:
        return None
    return (quality.get("texels_per_m_by_group") or {}).get(hp["group"], quality["texels_per_m"])


def _one_surface(glb, i, node, world, out, rep, where, surf_schema, snow, quality):
    extras = node.get("extras")
    hp = extras.get("hp") if isinstance(extras, dict) else None
    has_mesh = "mesh" in node
    ext = node.get("extensions")
    light = ((ext.get("KHR_lights_punctual") or {}).get("light")) if isinstance(ext, dict) else None
    if hp is None:
        if has_mesh:
            rep.error(f"{where} node {i} ('{node.get('name', '')}'): a mesh without extras.hp – every piece of "
                      "geometry needs an id, a storey and a group")
        if light is not None:
            rep.error(f"{where} node {i}: a light without extras.hp")
        return
    bad = control_text(hp)
    if bad:
        rep.error(f"{where} node {i} extras.hp: {bad}")
        return
    errs = list(surf_schema.iter_errors(hp))
    for e in errs[:5]:
        at = "/".join(str(p) for p in e.absolute_path) or "(top)"
        rep.error(f"{where} node {i} extras.hp {at}: {e.message}")
    if errs:
        return
    sid = hp["id"]
    if S.id_problem(sid):
        rep.error(f"{where} node {i}: id {sid!r} {S.id_problem(sid)}")
        return
    if sid in out.by_id:
        rep.error(f"{where}: id '{sid}' is used by two nodes")
        return
    if i not in world:
        rep.error(f"{where}: '{sid}' is not in the glb's scene (the scene does not reach its node)")
        return
    if node.get("name") != sid:
        rep.error(f"{where}: node of '{sid}' must be named '{sid}' (it is '{node.get('name')}')")
    if snow != (hp["kind"] == "snow"):
        rep.error(f"{where}: '{sid}' has kind '{hp['kind']}'" + (
            " – a snow file holds only snow" if snow else " – snow belongs in a bake package's snow files"))
    if snow and "on" not in hp:
        rep.error(f"{where}: snow '{sid}' does not say which surface it lies 'on'")
    if not snow and "on" in hp:
        rep.error(f"{where}: '{sid}' has 'on' – only snow lies on another surface")
    if hp["kind"] == "lamp" and hp["group"] in S.GROUPS and hp["group"] not in S.LAMP_GROUPS:
        rep.error(f"{where}: lamp '{sid}' is in group '{hp['group']}' – lamps are in "
                  f"{', '.join(S.LAMP_GROUPS)}")
    info = {"node": i, "hp": hp, "matrix": world[i], "mesh": node.get("mesh"), "verts": 0}
    if not has_mesh:
        if hp["kind"] != "lamp" or light is None:
            rep.error(f"{where}: '{sid}' has no mesh – only a lamp (kind 'lamp' with a KHR_lights_punctual "
                      "light) may be a node without one")
        if hp["bake"] != "NO":
            rep.error(f"{where}: lamp '{sid}' without a mesh must have bake 'NO'")
        out.lamps.add(sid)
        out.by_id[sid] = info
        return
    if light is not None:
        if hp["kind"] != "lamp":
            rep.error(f"{where}: '{sid}' carries a light but its kind is '{hp['kind']}', not 'lamp'")
        out.lamps.add(sid)
    mi = node["mesh"]
    if not isinstance(mi, int) or isinstance(mi, bool) or not (0 <= mi < len(glb.json.get("meshes", []))):
        rep.error(f"{where}: '{sid}' points at mesh {mi!r}, which does not exist")
        return
    if "hash" not in hp:
        rep.error(f"{where}: '{sid}' has a mesh but no hash")
        return
    probs = S.mesh_problems(glb, mi)
    for p in probs[:3]:
        rep.error(f"{where}: '{sid}': {p}")
    if probs:
        return
    is_map = hp["bake"] == "MAP"
    if is_map and "uv1_px" not in hp:
        rep.error(f"{where}: '{sid}' has bake 'MAP' but no uv1_px")
        return
    try:
        h = S.surface_hash(glb, mi, hp["uv1_px"] if is_map else None)
    except GlbError as e:
        rep.error(f"{where}: '{sid}': {e}")
        return
    info["verts"] = S.vertex_count(glb, mi)
    if h != hp["hash"]:
        rep.error(f"{where}: '{sid}': hash {hp['hash']} does not match its geometry ({h}, {S.HASH_NAME})")
    if hp["kind"] in NO_LIGHT_KINDS and hp["bake"] != "NO":
        rep.error(f"{where}: '{sid}' is {hp['kind']}: it lets light through and must have bake 'NO'")
    if is_map:
        if not is_rigid(world[i]):
            rep.error(f"{where}: '{sid}' has bake 'MAP' but its node is scaled or mirrored – a surface with a light "
                      "map may only be turned and moved (its metres are the light map's metres)")
        else:
            _check_uv1(glb, mi, hp, rep, where, density(hp, quality))
    elif "uv1_px" in hp:
        rep.warn(f"{where}: '{sid}' has uv1_px but bake '{hp['bake']}' – it is ignored")
    info["box"] = _box(glb, mi, world[i])
    out.by_id[sid] = info


def _box(glb: Glb, mesh_index: int, m: list[float]) -> list[float]:
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for prim in glb.json["meshes"][mesh_index].get("primitives", []):
        for x, y, z in glb.accessor(prim["attributes"]["POSITION"]):
            w = (m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13],
                 m[2] * x + m[6] * y + m[10] * z + m[14])
            for k in range(3):
                lo[k] = min(lo[k], w[k])
                hi[k] = max(hi[k], w[k])
    return lo + hi


DENSITY_TOL = 0.02   # an edge's length in the map may differ 2 % (+ 0.1 texel) from its length in metres x texels_per_m
MAX_RASTER = 4 * 2048 * 2048


def _check_uv1(glb: Glb, mesh_index: int, hp: dict, rep: Report, where: str, texels_per_m) -> None:
    """hp-uv/1 (FORMAT.md section 6): float UV1 in 0 … 1; every edge as long in texels as in metres x
    texels_per_m (no stretching); charts (triangles joined by shared UV points) packed by their rectangles with
    GAP_PX between them and BORDER_PX to the map's edge; no texel centre covered twice."""
    sid = hp["id"]
    W, H = hp["uv1_px"]
    parent: dict = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    tris = []
    stretched = 0
    for prim in glb.json["meshes"][mesh_index]["primitives"]:
        if "TEXCOORD_1" not in prim["attributes"]:
            rep.error(f"{where}: '{sid}' has bake 'MAP' but a primitive without TEXCOORD_1 (the light-map UVs)")
            return
        if "TEXCOORD_0" not in prim["attributes"]:
            rep.error(f"{where}: '{sid}' has TEXCOORD_1 without TEXCOORD_0 – glTF numbers UV sets from 0 without "
                      "gaps, and Blender's importer then drops the light-map UVs")
            return
        uv = glb.accessor(prim["attributes"]["TEXCOORD_1"])
        pos = glb.accessor(prim["attributes"]["POSITION"])
        bad = [t for t in uv if not (-1e-6 <= t[0] <= 1 + 1e-6 and -1e-6 <= t[1] <= 1 + 1e-6)]
        if bad:
            rep.error(f"{where}: '{sid}': {len(bad)} light-map UVs lie outside 0 … 1")
            return
        idx = glb.accessor(prim["indices"]) if "indices" in prim else list(range(len(uv)))
        for k in range(0, len(idx) - 2, 3):
            tri = idx[k:k + 3]
            keys = []
            for j in tri:
                u, v = uv[j]
                key = (S.round_half_away(u * W * 64), S.round_half_away(v * H * 64))  # 1/64 texel
                parent.setdefault(key, key)
                keys.append(key)
            parent[find(keys[1])] = find(keys[0])
            parent[find(keys[2])] = find(keys[0])
            px = [(uv[j][0] * W, uv[j][1] * H) for j in tri]
            tris.append((px, keys[0]))
            if texels_per_m:
                for a, b in ((0, 1), (1, 2), (2, 0)):
                    want = math.dist(pos[tri[a]], pos[tri[b]]) * texels_per_m
                    if abs(math.dist(px[a], px[b]) - want) > DENSITY_TOL * want + 0.1:
                        stretched += 1
                        break
    if stretched:
        rep.error(f"{where}: '{sid}': {stretched} triangles are stretched in the light map – 1 m must be "
                  f"{texels_per_m:g} texels (the surface's texels_per_m) in every direction")
        return
    rects: dict = {}
    for pts, key in tris:
        r = find(key)
        x0, x1 = min(t[0] for t in pts), max(t[0] for t in pts)
        y0, y1 = min(t[1] for t in pts), max(t[1] for t in pts)
        if r in rects:
            a = rects[r]
            rects[r] = [min(a[0], x0), min(a[1], y0), max(a[2], x1), max(a[3], y1)]
        else:
            rects[r] = [x0, y0, x1, y1]
    rl = list(rects.values())
    for a in rl:
        if a[0] < BORDER_PX - TOL_PX or a[1] < BORDER_PX - TOL_PX or a[2] > W - BORDER_PX + TOL_PX \
                or a[3] > H - BORDER_PX + TOL_PX:
            rep.error(f"{where}: '{sid}': a light-map chart lies closer than {BORDER_PX} texels to the edge of its "
                      f"{W} x {H} map")
            return
    rl.sort()
    for i, a in enumerate(rl):
        for b in rl[i + 1:]:
            if b[0] >= a[2] + GAP_PX - TOL_PX:
                break
            if not (b[1] >= a[3] + GAP_PX - TOL_PX or a[1] >= b[3] + GAP_PX - TOL_PX):
                rep.error(f"{where}: '{sid}': two light-map charts lie closer than {GAP_PX} texels (or overlap) in "
                          f"its {W} x {H} map")
                return
    if W * H <= MAX_RASTER:
        twice = _covered_twice(tris, W, H)
        if twice:
            rep.error(f"{where}: '{sid}': {twice} texels are covered by two triangles – the light map folds over "
                      "itself")


def _covered_twice(tris, W: int, H: int) -> int:
    """How many texel centres lie in more than one triangle (both windings count)."""
    seen = bytearray(W * H)
    twice = 0
    ex, ey = 1.3e-4, 2.7e-4  # a hair off the centre, so a centre on a shared edge counts once
    for (a, b, c), _ in tris:
        area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(area) < 1e-12:
            continue
        sgn = 1 if area > 0 else -1
        x0 = max(0, math.floor(min(a[0], b[0], c[0]) - 0.5))
        x1 = min(W - 1, math.ceil(max(a[0], b[0], c[0]) - 0.5))
        y0 = max(0, math.floor(min(a[1], b[1], c[1]) - 0.5))
        y1 = min(H - 1, math.ceil(max(a[1], b[1], c[1]) - 0.5))
        for y in range(y0, y1 + 1):
            py = y + 0.5 + ey
            for x in range(x0, x1 + 1):
                qx = x + 0.5 + ex
                if sgn * ((b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (qx - a[0])) < 0:
                    continue
                if sgn * ((c[0] - b[0]) * (py - b[1]) - (c[1] - b[1]) * (qx - b[0])) < 0:
                    continue
                if sgn * ((a[0] - c[0]) * (py - c[1]) - (a[1] - c[1]) * (qx - c[0])) < 0:
                    continue
                k = y * W + x
                if seen[k]:
                    twice += 1
                else:
                    seen[k] = 1
    return twice


# ---------------------------------------------------------------- the scene package
def _picture(pkg: Package, path: str, rep: Report, what: str, size=None, kinds=("png", "jpeg")):
    if path not in pkg.files:
        rep.error(f"{what}: '{path}' is not in the package")
        return None
    info = picture_info(pkg.files[path])
    if info is None or info[0] not in kinds:
        rep.error(f"{what}: '{path}' is not a {' or '.join(k.upper() for k in kinds)} picture")
        return None
    if size is not None and [info[1], info[2]] != list(size):
        rep.error(f"{what}: '{path}' is {info[1]} x {info[2]}, bake.json says {size[0]} x {size[1]}")
    return info


def _unique(items, what: str, rep: Report) -> dict:
    out = {}
    for it in items:
        if it["id"] in out:
            rep.error(f"{what} '{it['id']}' is listed twice")
        out[it["id"]] = it
    return out


def off_ok(m: dict, season: dict, place: dict, north) -> bool | None:
    """False when the moment's sun lies more than 2° from the NOAA sun at its date, time and place."""
    try:
        az, el = sun_position(place["latitude"], place["longitude"],
                              utc_moment(season["date"], m["time"], m["utc_offset"]))
    except ValueError:
        return None
    if el < -5 and m["sun"]["elevation"] < -5:
        return True  # night: where exactly the sun is below the horizon does not matter
    return S.angle_between(S.sun_direction(az, el, north), m["sun"]["direction"]) <= 2.0


def check_scene(pkg: Package, rep: Report) -> dict | None:
    """Checks a .hpscene; returns what a bake check needs (or None when it could not be read)."""
    doc = pkg.doc
    relaxed = version_check(doc, "house-scene", rep)
    if relaxed is None:
        return None
    if not _validate(doc, "scene", relaxed, rep, "scene.json"):
        return None
    rec = doc["recipe"]
    used = {"scene.json"}
    storeys = _unique(doc["storeys"], "storey", rep)
    # north and the sun
    n = doc["place"]["north"]
    if abs(math.hypot(*n) - 1) > 1e-3:
        rep.error(f"place.north {n} is not a unit vector (x, z)")
        return None
    for sid in rec["include"]["storeys"]:
        if sid not in storeys:
            rep.error(f"recipe.include.storeys: '{sid}' is not a storey")
    levels = {s["id"]: s["level"] for s in doc["storeys"]}
    inc_levels = [levels[s] for s in rec["include"]["storeys"] if s in levels]
    for sid in rec["open_storeys"]:
        if sid not in rec["include"]["storeys"]:
            rep.error(f"recipe.open_storeys: '{sid}' is not an included storey")
        elif inc_levels and levels[sid] == max(inc_levels):
            rep.warn(f"recipe.open_storeys: '{sid}' is the top storey of the export – nothing above it to leave out")
    seasons = _unique(rec["seasons"], "season", rep)
    moments = _unique(rec["moments"], "moment", rep)
    cameras = _unique(rec["cameras"], "camera", rep)
    _unique(rec["photos"], "photo", rep)
    _unique(rec["videos"], "video", rep)
    for m in rec["moments"]:
        if m["season"] not in seasons:
            rep.error(f"moment '{m['id']}': season '{m['season']}' is not in recipe.seasons")
        sun = m["sun"]
        d = sun["direction"]
        if abs(math.sqrt(sum(x * x for x in d)) - 1) > 1e-3:
            rep.error(f"moment '{m['id']}': sun.direction is not a unit vector")
        else:
            want = S.sun_direction(sun["azimuth"], sun["elevation"], n)
            off = S.angle_between(want, d)
            if off > 0.5:
                rep.error(f"moment '{m['id']}': sun.direction is {off:.1f}° away from its azimuth and elevation "
                          "(with place.north)")
        if m["season"] in seasons and off_ok(m, seasons[m["season"]], doc["place"], n) is False:
            rep.warn(f"moment '{m['id']}': its sun is more than 2° from where the sun stands on "
                     f"{seasons[m['season']]['date']} at {m['time']} (UTC {m['utc_offset']}) at the place – "
                     "check the time zone")
    for c in rec["cameras"]:
        if math.dist(c["position"], c["target"]) < 1e-3:
            rep.error(f"camera '{c['id']}': position and target are the same point")
    for kind in ("photos", "videos"):
        for p in rec[kind]:
            if p["camera"] not in cameras:
                rep.error(f"{kind[:-1]} '{p['id']}': camera '{p['camera']}' is not in recipe.cameras")
            if p["moment"] not in moments:
                rep.error(f"{kind[:-1]} '{p['id']}': moment '{p['moment']}' is not in recipe.moments")
    if "preview" in doc["files"]:
        _picture(pkg, doc["files"]["preview"], rep, "files.preview")
        used.add(doc["files"]["preview"])
    # the house
    used.add("house.glb")
    if "house.glb" not in pkg.files:
        rep.error("house.glb is not in the package")
        return None
    if len(pkg.files["house.glb"]) > BIG_GLB:
        rep.warn(f"house.glb is {len(pkg.files['house.glb']) / 2**20:.0f} MB – large for a phone")
    try:
        glb = Glb.parse(pkg.files["house.glb"])
    except GlbError as e:
        rep.error(f"house.glb: {e}")
        return None
    surf = read_surfaces(glb, rep, "house.glb", relaxed, snow=False,
                         quality=rec["quality"])
    page = rec["quality"]["page_size"]
    inc_st, inc_gr = set(rec["include"]["storeys"]), set(rec["include"]["groups"])
    texels = 0
    for sid, info in surf.by_id.items():
        hp = info["hp"]
        if hp["group"] not in inc_gr:
            rep.error(f"house.glb: '{sid}' is in group '{hp['group']}', which recipe.include.groups leaves out")
        if hp["group"] not in S.GROUPS:
            pass  # a group of a newer minor version: its storey rule is not known here
        elif hp["group"] in SITE_GROUPS:
            if hp["storey"] is not None:
                rep.error(f"house.glb: '{sid}' (group '{hp['group']}') belongs to no storey: storey must be null")
        elif hp["storey"] is None:
            rep.error(f"house.glb: '{sid}' (group '{hp['group']}') needs its storey")
        elif hp["storey"] not in inc_st:
            rep.error(f"house.glb: '{sid}': storey '{hp['storey']}' is not an included storey")
        if hp["bake"] == "MAP" and "uv1_px" in hp:
            w, h = hp["uv1_px"]
            texels += w * h
            if w > page - 2 * BORDER_PX or h > page - 2 * BORDER_PX:
                rep.error(f"house.glb: '{sid}': its {w} x {h} map does not fit a {page} px page – split the "
                          "surface")
    if texels and rec["light"] != "LIVE":
        pages = texels / (page * page * 0.8)
        if pages > PHONE_PAGES:
            rep.warn(f"about {pages:.0f} light-map pages of {page} px per moment – more than a phone should hold "
                     f"({PHONE_PAGES}); lower texels_per_m or bake fewer parts")
    for m in rec["moments"]:
        if isinstance(m["lamps"], list):
            for lid in m["lamps"]:
                if lid not in surf.lamps:
                    rep.error(f"moment '{m['id']}': lamp '{lid}' is not a lamp in house.glb")
    want = S.scene_hash({k: v["hp"]["hash"] for k, v in surf.by_id.items() if "hash" in v["hp"]})
    if want != doc["scene_hash"]:
        rep.error(f"scene_hash {doc['scene_hash']} does not match the surfaces' hashes ({want})")
    for f in sorted(set(pkg.files) - used):
        rep.warn(f"'{f}' is in the package but scene.json does not use it")
    return {"doc": doc, "surfaces": surf, "levels": levels}


# ---------------------------------------------------------------- the bake package
def check_bake(pkg: Package, rep: Report, scene: dict | None = None) -> None:
    doc = pkg.doc
    relaxed = version_check(doc, "house-bake", rep)
    if relaxed is None:
        return
    if not _validate(doc, "bake", relaxed, rep, "bake.json"):
        return
    used = {"bake.json"}
    if doc["light"] != "SOFT":
        for m in doc["moments"]:
            if m.get("sun_light") is not None:
                rep.error(f"moment '{m['id']}': sun_light is only for light 'SOFT' (with '{doc['light']}' it is null)")
    pages = _unique(doc["pages"], "page", rep)
    vfiles = _unique(doc["vertex_files"], "vertex file", rep)
    page_size = {}
    for p in doc["pages"]:
        used.add(p["file"])
        if _picture(pkg, p["file"], rep, f"page '{p['id']}'", p["size"], kinds=("png",)):
            why = page_png_problem(pkg.files[p["file"]])
            if why:
                rep.error(f"page '{p['id']}' ({p['file']}): {why}")
        page_size[p["id"]] = p["size"]
        if "ktx2" in p:
            used.add(p["ktx2"])
            _picture(pkg, p["ktx2"], rep, f"page '{p['id']}' (KTX2 copy)", p["size"], kinds=("ktx2",))
    vcount = {}
    for v in doc["vertex_files"]:
        used.add(v["file"])
        if v["file"] not in pkg.files:
            rep.error(f"vertex file '{v['id']}': '{v['file']}' is not in the package")
            continue
        n = len(pkg.files[v["file"]])
        if n % 3:
            rep.error(f"vertex file '{v['id']}': {n} bytes is not a whole number of RGB values")
        vcount[v["id"]] = n // 3
    # snow
    snow_ids: dict[str, dict] = {}
    for s in doc["snow"]:
        used.add(s["file"])
        if s["file"] not in pkg.files:
            rep.error(f"snow '{s['season']}': '{s['file']}' is not in the package")
            continue
        try:
            g = Glb.parse(pkg.files[s["file"]])
        except GlbError as e:
            rep.error(f"snow '{s['season']}' ({s['file']}): {e}")
            continue
        found = read_surfaces(g, rep, s["file"], relaxed, snow=True)
        for sid, info in found.by_id.items():
            if sid in snow_ids:
                rep.error(f"snow id '{sid}' is in two snow files")
            info["season"] = s["season"]
            snow_ids[sid] = info
    if len({s["season"] for s in doc["snow"]}) != len(doc["snow"]):
        rep.error("two snow files for the same season")
    # results
    if doc["light"] == "LIVE" and (doc["pages"] or doc["vertex_files"]
                                   or any(m["maps"] or m["open"] for m in doc["moments"])):
        rep.error("light 'LIVE' bakes nothing, yet the package holds light maps")
    _unique(doc["moments"], "moment", rep)
    on_page: dict[str, list] = {}
    on_file: dict[str, list] = {}
    for m in doc["moments"]:
        variants = [("", m["maps"])] + [(f" open '{k}'", v) for k, v in m["open"].items()]
        for label, maps in variants:
            for sid, e in maps.items():
                where = f"moment '{m['id']}'{label} '{sid}'"
                if sid not in doc["surfaces"] and sid not in snow_ids:
                    rep.error(f"{where}: not in bake.json's surfaces or a snow file")
                if "page" in e:
                    if e["page"] not in pages:
                        rep.error(f"{where}: page '{e['page']}' does not exist")
                        continue
                    x, y, w, h = e["rect"]
                    pw, ph = page_size[e["page"]]
                    if w < 1 or h < 1 or x + w > pw or y + h > ph:
                        rep.error(f"{where}: rect {e['rect']} does not lie inside its {pw} x {ph} page")
                        continue
                    on_page.setdefault(e["page"], []).append((x, y, x + w, y + h, where))
                else:
                    if e["vertex"] not in vfiles:
                        rep.error(f"{where}: vertex file '{e['vertex']}' does not exist")
                    elif e["offset"] + e["count"] > vcount.get(e["vertex"], 0):
                        rep.error(f"{where}: its {e['count']} values from {e['offset']} run past the end of "
                                  f"vertex file '{e['vertex']}'")
                    else:
                        on_file.setdefault(e["vertex"], []).append((e["offset"], e["offset"] + e["count"], where))
                if sid in snow_ids:
                    s = snow_ids[sid]
                    if scene is not None:
                        ms = {x["id"]: x for x in scene["doc"]["recipe"]["moments"]}
                        if m["id"] in ms and ms[m["id"]]["season"] != s["season"]:
                            rep.error(f"{where}: snow of season '{s['season']}' lit in a moment of season "
                                      f"'{ms[m['id']]['season']}'")
                    _fits(e, s, where, rep)
    for pid, rects in on_page.items():
        rects.sort()
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                if b[0] >= a[2]:
                    break
                if b[1] < a[3] and a[1] < b[3]:
                    rep.error(f"page '{pid}': {a[4]} and {b[4]} overlap")
    for fid, ranges in on_file.items():
        ranges.sort()
        for a, b in zip(ranges, ranges[1:]):
            if b[0] < a[1]:
                rep.error(f"vertex file '{fid}': {a[2]} and {b[2]} share values – every result has its own")
    for p in doc["photos"]:
        used.add(p["file"])
        _picture(pkg, p["file"], rep, f"photo '{p['id']}'", p["size"])
    for v in doc["videos"]:
        used.add(v["file"])
        if v["file"] not in pkg.files:
            rep.error(f"video '{v['id']}': '{v['file']}' is not in the package")
        elif not v["file"].lower().endswith((".mp4", ".webm")):
            rep.error(f"video '{v['id']}': '{v['file']}' must be .mp4 or .webm")
    for f in sorted(set(pkg.files) - used):
        rep.warn(f"'{f}' is in the package but bake.json does not use it")
    if scene is not None:
        _against_scene(doc, scene, snow_ids, rep)


def _fits(e: dict, info: dict, where: str, rep: Report) -> None:
    hp = info["hp"]
    if "page" in e:
        if hp["bake"] != "MAP":
            rep.error(f"{where}: has a light map but its surface is bake '{hp['bake']}'")
        elif "uv1_px" in hp and list(e["rect"][2:]) != list(hp["uv1_px"]):
            rep.error(f"{where}: rect is {e['rect'][2]} x {e['rect'][3]}, its uv1_px {hp['uv1_px'][0]} x "
                      f"{hp['uv1_px'][1]}")
    else:
        if hp["bake"] != "VERTEX":
            rep.error(f"{where}: has light per vertex but its surface is bake '{hp['bake']}'")
        elif e["count"] != info["verts"]:
            rep.error(f"{where}: {e['count']} vertex values for {info['verts']} vertices")


def _against_scene(doc: dict, scene: dict, snow_ids: dict, rep: Report) -> None:
    sdoc = scene["doc"]
    rec = sdoc["recipe"]
    surf = scene["surfaces"].by_id
    same = doc["scene"]["id"] == sdoc["id"]
    if not same:
        rep.warn(f"the bake was made from export '{doc['scene']['id']}', this scene is '{sdoc['id']}': only "
                 "surfaces whose hash is unchanged can use it")
    elif doc["scene"]["scene_hash"] != sdoc["scene_hash"]:
        rep.error("bake.json's scene.scene_hash differs from the scene's, though the export id is the same")
    if doc["light"] != rec["light"]:
        rep.error(f"light '{doc['light']}' differs from the recipe's '{rec['light']}'")
    nights = {m["id"] for m in rec["moments"] if m["sun"]["elevation"] < 0}
    for m in doc["moments"]:
        if m.get("sun_light") is not None and m["id"] in nights:
            rep.error(f"moment '{m['id']}': sun_light at night – the sun is below the horizon (null)")
    for p in doc["pages"]:
        if max(p["size"]) > rec["quality"]["page_size"]:
            rep.error(f"page '{p['id']}' is larger than the recipe's page_size {rec['quality']['page_size']}")
    for sid, b in doc["surfaces"].items():
        if sid not in surf:
            (rep.error if same else rep.warn)(f"surface '{sid}' is not in the scene")
            continue
        info = surf[sid]
        if info["hp"].get("hash") != b["hash"]:
            (rep.error if same else rep.warn)(f"surface '{sid}': hash differs from the scene's" + (
                "" if same else " – out of date"))
        moved = not is_identity(info["matrix"], 1e-6)
        if moved and "matrix" not in b:
            rep.error(f"surface '{sid}' is placed by a matrix in the scene, but bake.json has no 'matrix' for it")
        if "matrix" in b and same and max(abs(x - y) for x, y in zip(b["matrix"], info["matrix"])) > 1e-4:
            rep.error(f"surface '{sid}': 'matrix' differs from its place in the scene")
        if same and "box" in info and max(abs(x - y) for x, y in zip(b["box"], info["box"])) > 0.01:
            rep.error(f"surface '{sid}': 'box' differs from its geometry by more than 1 cm")
    for sid, info in snow_ids.items():
        on = info["hp"]["on"]
        if on not in surf:
            (rep.error if same else rep.warn)(f"snow '{sid}' lies on '{on}', which is not in the scene")
        elif (info["hp"]["storey"], info["hp"]["group"]) != (surf[on]["hp"]["storey"], surf[on]["hp"]["group"]):
            rep.error(f"snow '{sid}': its storey and group must be those of '{on}' (it hides with it)")
    moments = {m["id"]: m for m in rec["moments"]}
    seasons = {s["id"]: s for s in rec["seasons"]}
    for s in doc["snow"]:
        if s["season"] not in seasons:
            rep.error(f"snow file for season '{s['season']}', which is not in the recipe")
    if rec["light"] != "LIVE":
        for s in rec["seasons"]:
            if s["snow_cover"] > 0 and s["id"] not in {x["season"] for x in doc["snow"]}:
                rep.warn(f"season '{s['id']}' has snow_cover {s['snow_cover']} but the bake has no snow for it")
    done = set()
    for m in doc["moments"]:
        if m["id"] not in moments:
            rep.error(f"moment '{m['id']}' is not in the recipe")
            continue
        done.add(m["id"])
        for label, maps, storey in [("", m["maps"], None)] + [(f" open '{k}'", v, k) for k, v in m["open"].items()]:
            if storey is not None and storey not in rec["open_storeys"]:
                rep.error(f"moment '{m['id']}': open '{storey}' is not in the recipe's open_storeys")
            for sid, e in maps.items():
                if sid in snow_ids or sid not in surf:
                    continue
                where = f"moment '{m['id']}'{label} '{sid}'"
                if sid not in doc["surfaces"]:
                    continue
                if storey is not None and surf[sid]["hp"]["storey"] != storey:
                    rep.error(f"{where}: an 'open' result belongs to surfaces of that storey only")
                _fits(e, surf[sid], where, rep)
        if rec["light"] != "LIVE":
            missing = [k for k, v in surf.items() if v["hp"]["bake"] != "NO" and k not in m["maps"]
                       and k in doc["surfaces"]]
            if missing:
                rep.warn(f"moment '{m['id']}': {len(missing)} baked surfaces have no result, e.g. '{missing[0]}'")
    for mid in moments:
        if mid not in done and rec["light"] != "LIVE":
            rep.warn(f"recipe moment '{mid}' has no result in the bake")
    photos = {p["id"]: p for p in rec["photos"]}
    cams = {c["id"]: c for c in rec["cameras"]}
    for kind, want in (("photos", photos), ("videos", {v["id"]: v for v in rec["videos"]})):
        for p in doc[kind]:
            if p["id"] not in want:
                rep.error(f"{kind[:-1]} '{p['id']}' is not in the recipe")
                continue
            r = want[p["id"]]
            if p["moment"] != r["moment"]:
                rep.error(f"{kind[:-1]} '{p['id']}': moment '{p['moment']}', the recipe asked for '{r['moment']}'")
            c = cams.get(r["camera"])
            if c and (math.dist(c["position"], p["camera"]["position"]) > 1e-3
                      or math.dist(c["target"], p["camera"]["target"]) > 1e-3 or abs(c["fov"] - p["camera"]["fov"]) > 1e-3):
                rep.warn(f"{kind[:-1]} '{p['id']}': its camera differs from the recipe's camera '{r['camera']}'")


# ---------------------------------------------------------------- entry point
def check(path_or_pkg, scene=None) -> Report:
    """Check one package. ``scene``: the .hpscene a .hpbake was made from (a path or a Package), for the
    cross-checks."""
    if isinstance(path_or_pkg, Package):
        name = path_or_pkg.name or "package"
    elif isinstance(path_or_pkg, (bytes, bytearray)):
        name = "package"
    else:
        name = str(path_or_pkg)
    rep = Report(name)
    try:
        pkg = path_or_pkg if isinstance(path_or_pkg, Package) else Package.open(path_or_pkg)
    except (PackageError, OSError) as e:
        rep.error(str(e))
        return rep
    try:
        return _check(pkg, rep, scene)
    except Exception as e:  # noqa: BLE001 – a hostile package is reported, never a crash
        rep.error(f"the checker could not read this package ({type(e).__name__}: {e})")
        return rep


def _check(pkg: Package, rep: Report, scene) -> Report:
    if pkg.kind == "house-scene":
        check_scene(pkg, rep)
        return rep
    sc = None
    if scene is not None:
        srep = Report("scene")
        try:
            spkg = scene if isinstance(scene, Package) else Package.open(scene)
            sc = check_scene(spkg, srep) if spkg.kind == "house-scene" else None
        except (PackageError, OSError) as e:
            srep.error(str(e))
        if sc is None or not srep.ok:
            rep.error("the scene given for the cross-checks has errors itself: check it first")
            sc = None
    check_bake(pkg, rep, sc)
    return rep
