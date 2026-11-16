"""Surfaces: ids, kinds, Show-button groups, the surface hash and the sun's direction (FORMAT.md sections 4–6).

Everything here is written so House Planner (JavaScript) can do exactly the same: the rounding rules are spelled out.
"""
from __future__ import annotations

import hashlib
import math
import re
import struct

from .glb import Glb, GlbError

HASH_NAME = "hp-hash/1"
UV1_NAME = "hp-uv/1"

# What a surface is (extras.hp.kind). FORMAT.md section 4.
KINDS = (
    "wall",        # one side of a wall ("a" / "b"), or its "edge": top, ends, reveals round openings
    "floor",       # the top of a room's floor
    "ceiling",     # the underside of the storey above, per room
    "slab-edge",   # the edges of a floor slab: round the house, round a stair void
    "roof",        # one roof face (top and its underside) or a flat roof
    "opening",     # door and window frames, door leaves
    "glass",       # glass: lets light through, never gets a result (bake "NO")
    "stair",       # a stair (steps, stringers, handrail)
    "furniture",   # one mesh of a furniture piece (extras.hp.piece = the piece's id)
    "install",     # electrics and things on walls and ceilings (not lamps themselves)
    "lamp",        # a light fitting's body; the light itself is a KHR_lights_punctual light on the same node
    "ground",      # the plot's ground outside garden areas
    "garden",      # a garden area, path, wall, hedge or pond edge
    "plant",       # a plant, shrub or tree trunk
    "foliage",     # a tree's or hedge's leaves (the baker hides it when a season's foliage is "bare")
    "street",      # road, pavement, kerb, street furniture
    "neighbour",   # a house around the plot
    "water",       # water surfaces: let light through or reflect, never get a result (bake "NO")
    "park",        # quays, reeds, the park
    "snow",        # a snow layer (only in a bake package's snow files)
    "other",
)

# House Planner's Show buttons, by its own settings keys; "house" = the building itself (shown per storey).
GROUPS = ("house", "garden", "street", "houses", "park", "furniture", "installs", "ceilItems")

BAKE = ("MAP", "VERTEX", "NO")
LAMP_GROUPS = ("ceilItems", "installs", "furniture")

ID_RE = re.compile(r"[a-z][a-z0-9-]*:[A-Za-z0-9_.:-]+")
ID_MAX = 63  # Blender's longest object name, in bytes


def id_problem(sid) -> str | None:
    if not isinstance(sid, str):
        return "is not text"
    if len(sid.encode("utf-8")) > ID_MAX:
        return f"is longer than {ID_MAX} bytes"
    if not ID_RE.fullmatch(sid):
        return "is not '<kind>:<name>' (letters, digits, _ . : - only)"
    return None


def round_half_away(x: float) -> int:
    """Round to the nearest integer, halves away from zero (JavaScript: Math.sign(x) * Math.floor(Math.abs(x) + 0.5))."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


INT32 = 2**31 - 1


def mesh_problems(glb: Glb, mesh_index: int) -> list[str]:
    """What makes a mesh unreadable in the same way by every reader (FORMAT.md section 4.2): triangles only, float
    positions, no sparse accessors, unsigned indices in range in threes, every vertex used."""
    out = []
    try:
        mesh = glb.json["meshes"][mesh_index]
        prims = mesh["primitives"]
        assert isinstance(prims, list) and prims
    except (KeyError, IndexError, TypeError, AssertionError):
        return [f"mesh {mesh_index} does not exist or has no primitives"]
    accs = glb.json.get("accessors", [])
    for k, prim in enumerate(prims):
        at = f"primitive {k}"
        if not isinstance(prim, dict) or not isinstance(prim.get("attributes"), dict):
            out.append(f"{at}: not a glTF primitive")
            continue
        if prim.get("mode", 4) != 4:
            out.append(f"{at}: only triangles (mode 4)")
        attrs = prim["attributes"]
        if "POSITION" not in attrs:
            out.append(f"{at}: no POSITION")
            continue
        used = list(attrs.values()) + ([prim["indices"]] if "indices" in prim else [])
        for a in used:
            if not isinstance(a, int) or not (0 <= a < len(accs)) or not isinstance(accs[a], dict):
                out.append(f"{at}: accessor {a!r} does not exist")
                return out
            if "sparse" in accs[a]:
                out.append(f"{at}: sparse accessors are not allowed")
        if "NORMAL" not in attrs:
            out.append(f"{at}: no NORMAL")
        n = accs[attrs["POSITION"]].get("count")
        for name in ("POSITION", "NORMAL", "TEXCOORD_1"):
            if name in attrs:
                acc = accs[attrs[name]]
                want = "VEC2" if name == "TEXCOORD_1" else "VEC3"
                if acc.get("componentType") != 5126 or acc.get("type") != want or acc.get("normalized"):
                    out.append(f"{at}: {name} must be float {want}")
        for name, a in attrs.items():
            if accs[a].get("count") != n:
                out.append(f"{at}: {name} has {accs[a].get('count')} values for {n} vertices")
        if out:
            return out
        if "indices" in prim:
            acc = accs[prim["indices"]]
            if acc.get("componentType") not in (5121, 5123, 5125) or acc.get("type") != "SCALAR" \
                    or acc.get("normalized"):
                out.append(f"{at}: indices must be unsigned integers")
                continue
            idx = glb.accessor(prim["indices"])
            if len(idx) % 3:
                out.append(f"{at}: {len(idx)} indices is not a whole number of triangles")
            if any(i >= n for i in idx):
                out.append(f"{at}: an index points past its {n} vertices")
            elif len(set(idx)) != n:
                out.append(f"{at}: {n - len(set(idx))} vertices are not used by any triangle (importers drop "
                           "them, and light per vertex would no longer line up)")
        elif n % 3:
            out.append(f"{at}: {n} vertices without indices is not a whole number of triangles")
    return out


def surface_hash(glb: Glb, mesh_index: int, uv1_px=None) -> str:
    """The surface hash ``hp-hash/1`` of a mesh (FORMAT.md section 5): SHA-256 of its primitives' positions (mm),
    light-map UVs (TEXCOORD_1, 1/65535) and indices, in the file's order, and the map size ``uv1_px``; the first 32
    hex digits."""
    try:
        mesh = glb.json["meshes"][mesh_index]
        prims = mesh["primitives"]
    except (KeyError, IndexError, TypeError):
        raise GlbError(f"mesh {mesh_index} does not exist") from None
    h = hashlib.sha256(HASH_NAME.encode() + b"\0")
    for prim in prims:
        attrs = prim.get("attributes", {})
        if "POSITION" not in attrs:
            raise GlbError(f"mesh {mesh_index}: a primitive without POSITION")
        pos = glb.accessor(attrs["POSITION"])
        if not all(math.isfinite(c) for p in pos for c in p):
            raise GlbError(f"mesh {mesh_index}: a position is not a finite number")
        flat = [round_half_away(c * 1000.0) for p in pos for c in p]
        if any(abs(c) > INT32 for c in flat):
            raise GlbError(f"mesh {mesh_index}: a position lies more than 2,147 km from the origin")
        h.update(b"P" + struct.pack("<I", len(pos)) + struct.pack(f"<{len(flat)}i", *flat))
        if "TEXCOORD_1" in attrs:
            uv = glb.accessor(attrs["TEXCOORD_1"])
            if len(uv) != len(pos):
                raise GlbError(f"mesh {mesh_index}: TEXCOORD_1 has {len(uv)} values for {len(pos)} vertices")
            if not all(math.isfinite(c) for t in uv for c in t):
                raise GlbError(f"mesh {mesh_index}: a light-map UV is not a finite number")
            q = [min(65535, max(0, round_half_away(c * 65535.0))) for t in uv for c in t]
            h.update(b"U" + struct.pack(f"<{len(q)}H", *q))
        else:
            h.update(b"N")
        idx = glb.accessor(prim["indices"]) if "indices" in prim else list(range(len(pos)))
        h.update(struct.pack("<I", len(idx)) + struct.pack(f"<{len(idx)}I", *[int(i) for i in idx]))
    if uv1_px is not None:
        h.update(b"S" + struct.pack("<II", int(uv1_px[0]), int(uv1_px[1])))
    return h.hexdigest()[:32]


def scene_hash(pairs: dict[str, str]) -> str:
    """One hash for the whole export: SHA-256 of the lines "<id> <hash>\\n" sorted by id (UTF-8), first 32 hex."""
    text = "".join(f"{k} {pairs[k]}\n" for k in sorted(pairs))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def vertex_count(glb: Glb, mesh_index: int) -> int:
    mesh = glb.json["meshes"][mesh_index]
    return sum(glb.json["accessors"][p["attributes"]["POSITION"]]["count"] for p in mesh.get("primitives", []))


# ---- the sun ----
def east_of(north: list[float]) -> tuple[float, float]:
    """East in the scene's horizontal plane (x, z) for a north (x, z): north turned clockwise seen from above."""
    nx, nz = north
    return (-nz, nx)


def sun_direction(azimuth: float, elevation: float, north: list[float]) -> tuple[float, float, float]:
    """Unit vector towards the sun in glTF coordinates (+Y up). Azimuth: degrees clockwise from north seen from
    above; elevation: degrees above the horizon."""
    a, e = math.radians(azimuth), math.radians(elevation)
    nx, nz = north
    ex, ez = east_of(north)
    hx = math.cos(a) * nx + math.sin(a) * ex
    hz = math.cos(a) * nz + math.sin(a) * ez
    return (math.cos(e) * hx, math.sin(e), math.cos(e) * hz)


def angle_between(u, v) -> float:
    lu = math.sqrt(sum(x * x for x in u)) or 1.0
    lv = math.sqrt(sum(x * x for x in v)) or 1.0
    c = sum(a * b for a, b in zip(u, v)) / (lu * lv)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))
