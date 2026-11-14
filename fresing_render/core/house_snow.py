"""Snow layers for a House Planner bake (task 0114; FORMAT.md section 8.6 of github.com/smholte/house-scene-format,
tag v1.0). No Blender.

House Planner cannot run 0109's snow (a material layer traced by Cycles), so a bake package brings the snow as new
geometry: per season with snow, one ``snow/<season>.glb`` with one **layer** per surface that holds snow. The layers
follow 0109's own rule (``blender/weather_look.py``, ``_snow``) so Fresing Render's photos and House Planner agree:

- a face holds snow when it faces up: the up part of its normal is at least ``min_up(cover)`` (the middle of 0109's
  ramp ``lo = 0.85 - 0.45 cover`` … ``lo + 0.12``: more snow, steeper slopes hold it);
- and only under the open sky: nothing within ``SKY_DISTANCE`` (25 m) straight above it (0109 looks up with an
  Ambient Occlusion node; here a ray straight up through the house's triangles, ``open_sky``);
- the layer is ``THICKNESS_PER_COVER * cover`` thick (cover 1 = 10 cm), cut so no edge is longer than ``PIECE``
  (0.5 m: its light is stored per vertex, so a big plot needs points), welded (one vertex per corner point, so its
  light is smooth) and closed round its outline by a skirt down to the surface.

Coordinates: glTF world **G** (metres, +Y up), as ``house.glb``. Input:

- ``build_layers(sources, cover, blockers)``: ``sources`` = the surfaces that may hold snow, each a dict ``{id,
  storey, group, points (n, 3) G world, tris (m, 3)}``; ``blockers`` = ``(points, tris)`` G world of everything shown
  in that season (what can keep the snow off).
- ``sources_from_glb(glb_bytes, season_foliage)`` reads both from a ``house.glb`` itself.

Output: ``layers_glb(layers)`` -> the bytes of ``snow/<season>.glb`` (float32 positions and normals, uint32
indices, ``extras.hp`` per node, no extensions). The layer hashes are ``hp-hash/1`` (``core/house_hash.py``), which
the format's checker recomputes.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass

import numpy as np

from .house_hash import hash_primitives
from .web3d import accessor_array, quat_to_matrix, read_glb

SKY_DISTANCE = 25.0               # m: 0109's weather_look.SKY_DISTANCE – what lies this close above keeps snow off
THICKNESS_PER_COVER = 0.10        # m: cover 1 ≈ 10 cm (0109)
PIECE = 0.5                       # m: largest edge of a layer's triangles (their light is per vertex)
LIFT = 0.001                      # m: a point looks up from 1 mm above itself (its own face never blocks it)
WELD = 1e-5                       # m: corner points closer than this are one point
NOT_SNOW = ("glass", "water", "snow", "lamp")   # kinds that never hold a snow layer
SNOW_COLOUR = (0.92, 0.94, 0.97, 1.0)           # the plain glTF material of the layers (House Planner uses its own)


def min_up(cover) -> float:
    """The smallest up part of a face normal that holds snow at this cover: the middle of 0109's ramp
    (``lo = 0.85 - 0.45 cover``, ``hi = lo + 0.12``) = 0.91 - 0.45 cover."""
    return 0.91 - 0.45 * float(cover)


@dataclass
class Layer:
    """One snow layer on one surface. ``positions`` / ``normals`` (n, 3) float32 G world; ``indices`` (k,) uint32:
    first the ``top`` triangles (the snow's upper face), then the skirt round its outline."""
    id: str                       # "snow:<on>"
    on: str                       # the surface it lies on
    storey: str | None            # those of ``on``: the layer hides with it
    group: str
    positions: np.ndarray
    normals: np.ndarray
    indices: np.ndarray
    hash: str
    top: int = 0                  # number of top triangles (the rest is the skirt)


# ---------------------------------------------------------------------------
# under the open sky
# ---------------------------------------------------------------------------

def _as_corners(tris_points_g) -> np.ndarray:
    """Triangle corners (m, 3, 3) from (m, 3, 3) corners or a (points, tris) pair."""
    if isinstance(tris_points_g, tuple) and len(tris_points_g) == 2:
        pts = np.asarray(tris_points_g[0], np.float64).reshape(-1, 3)
        tri = np.asarray(tris_points_g[1], np.int64).reshape(-1, 3)
        return pts[tri] if len(tri) else np.zeros((0, 3, 3))
    return np.asarray(tris_points_g, np.float64).reshape(-1, 3, 3)


def open_sky(points_g, tris_points_g, distance: float = SKY_DISTANCE, lift: float = LIFT) -> np.ndarray:
    """For each point (G world): True when no triangle lies within ``distance`` straight above it (+Y), seen from
    ``lift`` above the point. ``tris_points_g``: triangle corners (m, 3, 3), or a pair (points, tris).

    The triangles are sorted into a grid over (x, z) by their boxes; each point only tests the triangles of its own
    cell (a vertical ray meets a triangle where the point lies inside its (x, z) shadow), so 100 k triangles x 10 k
    points stay fast. Upright triangles (no shadow) never block a vertical ray."""
    pts = np.asarray(points_g, np.float64).reshape(-1, 3)
    out = np.ones(len(pts), bool)
    tp = _as_corners(tris_points_g)
    if not len(pts) or not len(tp):
        return out
    x, y, z = tp[:, :, 0], tp[:, :, 1], tp[:, :, 2]
    det = (x[:, 1] - x[:, 0]) * (z[:, 2] - z[:, 0]) - (x[:, 2] - x[:, 0]) * (z[:, 1] - z[:, 0])
    lo = pts.min(0)
    hi = pts.max(0)
    keep = ((np.abs(det) > 1e-12)                                       # has a shadow on the ground
            & (y.max(1) > lo[1] + lift) & (y.min(1) <= hi[1] + distance)   # can be above some point, in reach
            & (x.max(1) >= lo[0]) & (x.min(1) <= hi[0])                 # over the points at all
            & (z.max(1) >= lo[2]) & (z.min(1) <= hi[2]))
    if not keep.any():
        return out
    x, y, z, det = x[keep], y[keep], z[keep], det[keep]
    x0, x1 = np.maximum(x.min(1), lo[0]), np.minimum(x.max(1), hi[0])   # the part of a box over the points
    z0, z1 = np.maximum(z.min(1), lo[2]), np.minimum(z.max(1), hi[2])
    # cell size: about a triangle's size, at most 2048 cells across; coarser while the cell lists grow too long
    extent = max(hi[0] - lo[0], hi[2] - lo[2], 1e-3)
    h = max(float(np.median(np.maximum(x1 - x0, z1 - z0))), extent / 2048.0, 1e-3)
    while True:
        i0 = np.floor((x0 - lo[0]) / h).astype(np.int64)
        i1 = np.floor((x1 - lo[0]) / h).astype(np.int64)
        k0 = np.floor((z0 - lo[2]) / h).astype(np.int64)
        k1 = np.floor((z1 - lo[2]) / h).astype(np.int64)
        ni, nk = i1 - i0 + 1, k1 - k0 + 1
        cells = ni * nk
        if cells.sum() <= 8_000_000 or h > extent:
            break
        h *= 2.0
    nz = int(np.floor((hi[2] - lo[2]) / h)) + 1
    # (cell, triangle) pairs, sorted by cell
    tri_of = np.repeat(np.arange(len(x)), cells)
    k = np.arange(len(tri_of)) - np.repeat(np.cumsum(cells) - cells, cells)     # number within its triangle
    key = (i0[tri_of] + k // nk[tri_of]) * nz + (k0[tri_of] + k % nk[tri_of])
    order = np.argsort(key, kind="stable")
    key, tri_of = key[order], tri_of[order]
    ukey, start, count = np.unique(key, return_index=True, return_counts=True)
    # each point: the triangles of its cell
    pkey = np.floor((pts[:, 0] - lo[0]) / h).astype(np.int64) * nz + np.floor((pts[:, 2] - lo[2]) / h).astype(np.int64)
    at = np.searchsorted(ukey, pkey)
    at = np.clip(at, 0, len(ukey) - 1)
    found = ukey[at] == pkey
    n_of = np.where(found, count[at], 0)
    s_of = np.where(found, start[at], 0)
    blocked = np.zeros(len(pts), bool)
    chunk = 2_000_000
    first = 0
    while first < len(pts):
        # as many points as keep the pairs below `chunk`
        csum = np.cumsum(n_of[first:])
        last = first + max(1, int(np.searchsorted(csum, chunk, side="right")))
        idx = np.arange(first, min(last, len(pts)))
        first = idx[-1] + 1
        cnt = n_of[idx]
        if not cnt.sum():
            continue
        p_of = np.repeat(idx, cnt)
        j = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        t = tri_of[s_of[p_of] + j]
        px, py, pz = pts[p_of, 0], pts[p_of, 1], pts[p_of, 2]
        ax, az = x[t, 0], z[t, 0]
        l1 = ((px - ax) * (z[t, 2] - az) - (x[t, 2] - ax) * (pz - az)) / det[t]
        l2 = ((x[t, 1] - ax) * (pz - az) - (px - ax) * (z[t, 1] - az)) / det[t]
        l0 = 1.0 - l1 - l2
        eps = -1e-9
        inside = (l0 >= eps) & (l1 >= eps) & (l2 >= eps)
        ty = l0 * y[t, 0] + l1 * y[t, 1] + l2 * y[t, 2]                 # the triangle's height over the point
        hit = inside & (ty > py + lift) & (ty <= py + distance)
        blocked[p_of[hit]] = True
    out[blocked] = False
    return out


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------

def _weld(points: np.ndarray, tris: np.ndarray, tol: float = WELD):
    """One point per place: (points, tris) with corner points closer than ``tol`` merged."""
    keys = np.round(points / tol).astype(np.int64)
    _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    return points[first], inverse.reshape(-1)[tris]


def _face_normals(points: np.ndarray, tris: np.ndarray):
    """(unit normals (m, 3), areas (m,)) of counter-clockwise triangles."""
    c = np.cross(points[tris[:, 1]] - points[tris[:, 0]], points[tris[:, 2]] - points[tris[:, 0]])
    a = np.linalg.norm(c, axis=1)
    return c / np.where(a > 0, a, 1.0)[:, None], 0.5 * a


def _compact(points: np.ndarray, tris: np.ndarray):
    """Only the points the triangles use, in the order they are first used."""
    used, first = np.unique(tris.ravel(), return_index=True)
    used = used[np.argsort(first)]
    new = np.full(len(points), -1, np.int64)
    new[used] = np.arange(len(used))
    return points[used], new[tris]


def _edges_once(tris: np.ndarray):
    """The directed edges (a, b) that only one triangle has (an outline, or one side of a T-junction)."""
    a = tris.ravel()
    b = np.roll(tris, -1, axis=1).ravel()
    n = int(tris.max()) + 1
    key = np.minimum(a, b) * (n + 1) + np.maximum(a, b)
    _, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    once = cnt[inv] == 1
    return a[once], b[once], np.repeat(np.arange(len(tris)), 3)[once]


def mend(points, tris, tol: float = 1e-4):
    """Close T-junctions: a corner point that lies on another triangle's outline edge (House Planner's plot is four
    quads round the house, one long edge meeting two short ones). Such a triangle is split there – its outline
    with the points on it is fanned from its centre – so the mesh is one closed piece: cutting stays conforming, the
    layer's light is welded across, and no skirt stands inside the snow. Returns (points, tris)."""
    P = np.asarray(points, np.float64).reshape(-1, 3)
    T = np.asarray(tris, np.int64).reshape(-1, 3)
    if not len(T):
        return P, T
    ea, eb, et = _edges_once(T)
    on_edge: dict[int, list] = {}                    # triangle -> [(edge corner i, s along it, point)]
    step = max(1, 1_000_000 // len(P))               # edges x points at a time
    for k in range(0, len(ea), step):
        a, b, t = ea[k:k + step], eb[k:k + step], et[k:k + step]
        d = P[b] - P[a]
        dd = np.maximum((d * d).sum(1), 1e-18)
        s = np.einsum("eij,ej->ei", P[None, :, :] - P[a][:, None, :], d) / dd[:, None]
        off = P[None, :, :] - (P[a][:, None, :] + s[:, :, None] * d[:, None, :])
        hit = (s > 1e-6) & (s < 1 - 1e-6) & ((off * off).sum(2) < tol * tol)
        for e, q in zip(*np.nonzero(hit)):
            tri = int(t[e])
            corner = int(np.nonzero(T[tri] == a[e])[0][0])
            on_edge.setdefault(tri, []).append((corner, float(s[e, q]), int(q)))
    if not on_edge:
        return P, T
    keep = np.ones(len(T), bool)
    new_pts, new_tris = [], []
    n = len(P)
    for tri, items in on_edge.items():
        keep[tri] = False
        ring = []
        for corner in range(3):                      # the outline in order, with the points on each edge
            ring.append(int(T[tri, corner]))
            ring += [q for c, s, q in sorted(it for it in items if it[0] == corner) if c == corner]
        centre = n + len(new_pts)
        new_pts.append(P[T[tri]].mean(0))
        new_tris += [(centre, ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring))]
    return (np.concatenate([P, np.array(new_pts)]),
            np.concatenate([T[keep], np.array(new_tris, np.int64).reshape(-1, 3)]))


def cut(points, tris, piece: float = PIECE, *, passes: int = 64):
    """Cut triangles until no edge is longer than ``piece``: every edge that is too long is halved (one midpoint per
    edge, shared by both its triangles, so the mesh stays closed), and each triangle split by the pattern of its
    halved edges (1: in two, 2: a corner and a quad over its shorter diagonal, 3: in four). Returns (points, tris)."""
    P = np.asarray(points, np.float64).reshape(-1, 3)
    T = np.asarray(tris, np.int64).reshape(-1, 3)
    for _ in range(passes):
        if not len(T):
            break
        a = T
        b = np.roll(T, -1, axis=1)                                    # edge i runs from corner i to corner i+1
        length = np.linalg.norm(P[b] - P[a], axis=2)
        long = length > piece
        if not long.any():
            break
        n = len(P)
        ekey = np.minimum(a, b) * (n + 1) + np.maximum(a, b)           # one key per undirected edge
        ukeys, inv = np.unique(ekey[long], return_inverse=True)
        mid = np.full(T.shape, -1, np.int64)
        mid[long] = n + inv                                            # its midpoint, shared by both triangles
        P = np.concatenate([P, 0.5 * (P[ukeys // (n + 1)] + P[ukeys % (n + 1)])])
        cnt = long.sum(1)
        out = [T[cnt == 0]]
        # one halved edge: turn it to edge 0
        s = np.where(cnt == 1)[0]
        if len(s):
            r = np.argmax(long[s], axis=1)
            v = np.stack([T[s, (r + i) % 3] for i in range(3)], 1)
            m01 = mid[s, r]
            out.append(np.stack([v[:, 0], m01, v[:, 2]], 1))
            out.append(np.stack([m01, v[:, 1], v[:, 2]], 1))
        # two halved edges: turn the whole one to edge 2
        s = np.where(cnt == 2)[0]
        if len(s):
            whole = np.argmin(long[s], axis=1)
            r = (whole + 1) % 3
            v = np.stack([T[s, (r + i) % 3] for i in range(3)], 1)
            m01 = mid[s, r]
            m12 = mid[s, (r + 1) % 3]
            out.append(np.stack([m01, v[:, 1], m12], 1))                # the corner
            d_a = np.linalg.norm(P[v[:, 0]] - P[m12], axis=1)          # quad v0 m01 m12 v2: the shorter diagonal
            d_b = np.linalg.norm(P[m01] - P[v[:, 2]], axis=1)
            ua = d_a <= d_b
            out.append(np.where(ua[:, None], np.stack([v[:, 0], m01, m12], 1), np.stack([v[:, 0], m01, v[:, 2]], 1)))
            out.append(np.where(ua[:, None], np.stack([v[:, 0], m12, v[:, 2]], 1), np.stack([m01, m12, v[:, 2]], 1)))
        # three: in four
        s = np.where(cnt == 3)[0]
        if len(s):
            v, m = T[s], mid[s]
            out.append(np.stack([v[:, 0], m[:, 0], m[:, 2]], 1))
            out.append(np.stack([m[:, 0], v[:, 1], m[:, 1]], 1))
            out.append(np.stack([m[:, 2], m[:, 1], v[:, 2]], 1))
            out.append(np.stack([m[:, 0], m[:, 1], m[:, 2]], 1))
        T = np.concatenate(out)
    return P, T


# ---------------------------------------------------------------------------
# the layers
# ---------------------------------------------------------------------------

def _pieces(src: dict, cover: float):
    """The faces of a surface that face up enough, welded, T-junctions closed and cut into pieces: (P, T) or None."""
    pts = np.asarray(src["points"], np.float64).reshape(-1, 3)
    tri = np.asarray(src["tris"], np.int64).reshape(-1, 3)
    if not len(tri):
        return None
    P, T = _weld(pts, tri)
    n, area = _face_normals(P, T)
    up = (area > 1e-10) & (n[:, 1] >= min_up(cover))                 # faces that face up enough
    if not up.any():
        return None
    P, T = mend(*_compact(P, T[up]))
    return cut(P, T, PIECE)


def _one_layer(src: dict, cover: float, P: np.ndarray, T: np.ndarray) -> Layer:
    """The layer on the kept pieces (P, T) of one surface: the lifted top, the skirt, the hash."""
    P, T = _compact(P, T)
    fn, fa = _face_normals(P, T)
    # the top: each point lifted along the mean normal of its faces, far enough to lie `thick` above every one
    thick = THICKNESS_PER_COVER * cover
    vn = np.zeros_like(P)
    for i in range(3):
        np.add.at(vn, T[:, i], fn * fa[:, None])
    vn /= np.maximum(np.linalg.norm(vn, axis=1), 1e-12)[:, None]
    cos = np.ones(len(P))
    for i in range(3):
        np.minimum.at(cos, T[:, i], np.einsum("ij,ij->i", vn[T[:, i]], fn))
    top = P + vn * (thick / np.clip(cos, 1.0 / 3.0, 1.0))[:, None]
    # the outline: edges used by one top triangle only, in that triangle's (counter-clockwise) direction
    ea, eb, et = _edges_once(T)
    efn = fn[et]
    out_dir = np.cross(P[eb] - P[ea], efn)                            # away from the layer, along its surface
    out_dir /= np.maximum(np.linalg.norm(out_dir, axis=1), 1e-12)[:, None]
    ring = np.unique(np.concatenate([ea, eb]))
    at = np.full(len(P), -1, np.int64)
    at[ring] = np.arange(len(ring))
    rn = np.zeros((len(ring), 3))
    np.add.at(rn, at[ea], out_dir)
    np.add.at(rn, at[eb], out_dir)
    rn /= np.maximum(np.linalg.norm(rn, axis=1), 1e-12)[:, None]
    nt = len(P)
    up_i = nt + at                                                    # the skirt's own points: top copy …
    dn_i = nt + len(ring) + at                                        # … and down on the surface
    skirt = np.concatenate([np.stack([up_i[ea], dn_i[ea], dn_i[eb]], 1),
                            np.stack([up_i[ea], dn_i[eb], up_i[eb]], 1)])
    positions = np.concatenate([top, top[ring], P[ring]]).astype(np.float32)
    normals = np.concatenate([vn, rn, rn]).astype(np.float32)
    indices = np.concatenate([T.ravel(), skirt.ravel()]).astype(np.uint32)
    h = hash_primitives([{"positions": positions, "uv1": None, "indices": indices}], None)
    on = src["id"]
    return Layer(id=f"snow:{on}", on=on, storey=src.get("storey"), group=src.get("group", "house"),
                 positions=positions, normals=normals, indices=indices, hash=h, top=len(T))


def build_layers(sources, cover, blockers, *, sky_distance: float = SKY_DISTANCE) -> list[Layer]:
    """The snow layers of one season. ``sources``: the surfaces that may hold snow, dicts ``{id, storey, group,
    points (n, 3) G world, tris (m, 3)}`` (``sources_from_glb`` picks them); ``cover``: the season's snow_cover
    (0 … 1); ``blockers``: ``(points, tris)`` G world of everything shown in that season. A surface without snow
    gets no layer; cover 0 gives none. Ids longer than the format's 63 bytes are left out."""
    cover = min(float(cover), 1.0)
    if cover <= 0:
        return []
    if isinstance(blockers, list) and len(blockers) == 2:
        blockers = tuple(blockers)
    corners = _as_corners(blockers)
    found = []                                     # (source, P, T) of every surface with faces that face up
    for src in sources:
        if len(f"snow:{src['id']}".encode("utf-8")) > 63:
            continue
        pieces = _pieces(src, cover)
        if pieces is not None:
            found.append((src, *pieces))
    if not found:
        return []
    # one look at the sky for every piece of every surface: the blockers are sorted into their grid once
    sky = open_sky(np.concatenate([P[T].mean(1) for _, P, T in found]), corners, sky_distance)
    out, at = [], 0
    for src, P, T in found:
        kept = sky[at:at + len(T)]
        at += len(T)
        if kept.any():
            out.append(_one_layer(src, cover, P, T[kept]))
    return out


# ---------------------------------------------------------------------------
# reading house.glb
# ---------------------------------------------------------------------------

def _local(node: dict) -> np.ndarray:
    """A node's own transform (4 x 4, row-major) from ``matrix`` (column-major) or translation / rotation / scale."""
    if "matrix" in node:
        return np.asarray(node["matrix"], np.float64).reshape(4, 4).T
    m = np.eye(4)
    s = np.asarray(node.get("scale", [1, 1, 1]), np.float64)
    m[:3, :3] = quat_to_matrix(node.get("rotation", [0, 0, 0, 1])) * s[None, :]
    m[:3, 3] = node.get("translation", [0, 0, 0])
    return m


def _mesh(doc: dict, binary: bytes, mi: int):
    """All primitives of a mesh as one (points, tris), in the file's order."""
    pts, tris, base = [], [], 0
    for prim in doc["meshes"][mi].get("primitives", []):
        if prim.get("mode", 4) != 4:
            continue
        p = accessor_array(doc, binary, prim["attributes"]["POSITION"]).astype(np.float64)
        if "indices" in prim:
            t = accessor_array(doc, binary, prim["indices"]).astype(np.int64).reshape(-1)
        else:
            t = np.arange(len(p))
        t = t[:len(t) // 3 * 3].reshape(-1, 3)
        pts.append(p)
        tris.append(t + base)
        base += len(p)
    if not pts:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    return np.concatenate(pts), np.concatenate(tris)


def sources_from_glb(glb_bytes: bytes, season_foliage: str = "full"):
    """(sources, blockers) for ``build_layers`` from a ``house.glb``: every node with a mesh reached from the default
    scene, placed in G world by its node tree. Sources: ``extras.hp`` with bake MAP or VERTEX and a kind that can
    hold snow (not glass, water, snow or lamp). Blockers: every mesh shown in the season. With foliage ``"bare"``
    the leaves (kind ``foliage``) are hidden: they neither hold snow nor keep it off."""
    doc, binary = read_glb(glb_bytes)
    nodes = doc.get("nodes", [])
    scenes = doc.get("scenes", [])
    roots = scenes[doc.get("scene", 0)].get("nodes", []) if scenes else []
    bare = season_foliage == "bare"
    sources, b_pts, b_tris, b_n = [], [], [], 0
    stack = [(r, np.eye(4)) for r in roots]
    seen = set()
    while stack:
        i, parent = stack.pop()
        if i in seen:
            continue
        seen.add(i)
        node = nodes[i]
        world = parent @ _local(node)
        stack.extend((c, world) for c in node.get("children", []))
        if "mesh" not in node:
            continue
        hp = (node.get("extras") or {}).get("hp") or {}
        kind = hp.get("kind", "other")
        if bare and kind == "foliage":
            continue
        p, t = _mesh(doc, binary, node["mesh"])
        if not len(t):
            continue
        p = p @ world[:3, :3].T + world[:3, 3]
        if np.linalg.det(world[:3, :3]) < 0:                     # a mirroring node turns its triangles round
            t = t[:, ::-1]
        b_pts.append(p)
        b_tris.append(t + b_n)
        b_n += len(p)
        if hp.get("id") and hp.get("bake") in ("MAP", "VERTEX") and kind not in NOT_SNOW:
            sources.append({"id": hp["id"], "storey": hp.get("storey"), "group": hp.get("group", "house"),
                            "points": p, "tris": t})
    blockers = ((np.concatenate(b_pts), np.concatenate(b_tris)) if b_pts
                else (np.zeros((0, 3)), np.zeros((0, 3), np.int64)))
    return sources, blockers


# ---------------------------------------------------------------------------
# snow/<season>.glb
# ---------------------------------------------------------------------------

def layers_glb(layers) -> bytes:
    """``snow/<season>.glb``: one node per layer (named by its id, no transform) with one mesh: POSITION (with
    min/max) and NORMAL float32, TEXCOORD_0 (x, z in metres: the format's SHOULD, for a snow picture), uint32
    indices; ``extras.hp`` {id, kind "snow", storey, group, bake "VERTEX", hash, on}. One scene, no extensions."""
    views, accessors, meshes, nodes = [], [], [], []
    blob = bytearray()

    def add(arr: np.ndarray, type_: str, comp: int, target: int, minmax: bool = False) -> int:
        while len(blob) % 4:
            blob.append(0)
        data = arr.tobytes()
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target})
        blob.extend(data)
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": int(len(arr)), "type": type_}
        if minmax:
            acc["min"] = [float(v) for v in arr.min(0)]
            acc["max"] = [float(v) for v in arr.max(0)]
        accessors.append(acc)
        return len(accessors) - 1

    for layer in layers:
        pos = np.ascontiguousarray(layer.positions, "<f4").reshape(-1, 3)
        nrm = np.ascontiguousarray(layer.normals, "<f4").reshape(-1, 3)
        uv0 = np.ascontiguousarray(pos[:, [0, 2]], "<f4")
        idx = np.ascontiguousarray(layer.indices, "<u4").reshape(-1)
        attrs = {"POSITION": add(pos, "VEC3", 5126, 34962, True), "NORMAL": add(nrm, "VEC3", 5126, 34962),
                 "TEXCOORD_0": add(uv0, "VEC2", 5126, 34962)}
        meshes.append({"name": layer.id, "primitives": [{"attributes": attrs, "indices": add(idx, "SCALAR", 5125,
                                                                                               34963),
                                                         "material": 0, "mode": 4}]})
        hp = {"id": layer.id, "kind": "snow", "storey": layer.storey, "group": layer.group, "bake": "VERTEX",
              "hash": layer.hash, "on": layer.on}
        nodes.append({"name": layer.id, "mesh": len(meshes) - 1, "extras": {"hp": hp}})
    while len(blob) % 4:
        blob.append(0)
    scene = {"name": "snow"}
    if nodes:
        scene["nodes"] = list(range(len(nodes)))
    doc = {"asset": {"version": "2.0", "generator": "Fresing Render snow layers"}, "scene": 0, "scenes": [scene]}
    if nodes:                     # glTF allows no empty lists: an empty season's file is a scene and nothing else
        doc.update(nodes=nodes, meshes=meshes, accessors=accessors, bufferViews=views,
                   buffers=[{"byteLength": len(blob)}],
                   materials=[{"name": "snow", "pbrMetallicRoughness": {
                       "baseColorFactor": list(SNOW_COLOUR), "metallicFactor": 0.0, "roughnessFactor": 0.9}}])
    js = json.dumps(doc, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + (8 + len(blob) if blob else 0)
    out = struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
    if blob:
        out += struct.pack("<II", len(blob), 0x004E4942) + bytes(blob)
    return out
