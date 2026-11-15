"""Task 0126: measure the demo's CPS run (shot 8b) frame by frame – used by ``tests/test_demo_project.py``.

The CPS set rides on its line as a rider (paths_riders: Geometry Nodes move each piece's own geometry; the clash check
leaves riders out, as they lie on a cable on purpose), so this reads the pieces' evaluated meshes at every frame of the
shot and measures, in the model's coordinates (the vessel moves):

- **line**: how far each piece's axis (its two ends and three points between, from its place in the CAD pose) lies from
  the CPS's middle line (``cps_store.run_route`` of the route sheet: its straights and arcs);
- **clash**: how deep a piece's corners lie inside any other part near the way, and that part's corners inside the
  piece (both ways: a roller's edge can cut a piece without a corner of the piece inside the roller). Everything else
  stands still during the shot (nothing is paid out), so the other parts are read once.
"""

from __future__ import annotations

import math

import numpy as np


def route_points(route: dict, step: float = 5.0) -> np.ndarray:
    """Points every ``step`` mm along a route of the sheet (model mm)."""
    out = []
    for g in route["segments"]:
        a, b = np.array(g["start"], float), np.array(g["end"], float)
        n = max(2, int(math.ceil(float(g["length"]) / step)) + 1)
        if g["type"] == "line":
            out.append(a + np.linspace(0.0, 1.0, n)[:, None] * (b - a))
        else:
            c, k = np.array(g["centre"], float), np.array(g["normal"], float)
            k /= np.linalg.norm(k)
            v = a - c
            for t in np.linspace(0.0, math.radians(float(g["angle_deg"])), n):
                out.append((c + v * math.cos(t) + np.cross(k, v) * math.sin(t) + k * float(k @ v) * (1 - math.cos(t)))
                           [None])
    return np.concatenate(out)


class Line:
    """Distance to a dense polyline (a KD tree of its points, then the two segments next to the nearest point)."""

    def __init__(self, pts: np.ndarray):
        from mathutils.kdtree import KDTree
        self.p = pts
        self.tree = KDTree(len(pts))
        for i, q in enumerate(pts.tolist()):
            self.tree.insert(q, i)
        self.tree.balance()

    def distance(self, q) -> float:
        _co, i, _d = self.tree.find(list(q))
        best = math.inf
        for j in (i - 1, i):
            if 0 <= j < len(self.p) - 1:
                a, b = self.p[j], self.p[j + 1]
                ab = b - a
                t = min(1.0, max(0.0, float((q - a) @ ab) / max(float(ab @ ab), 1e-12)))
                best = min(best, float(np.linalg.norm(a + t * ab - q)))
        return best


def _mesh(ob, depsgraph=None):
    """(vertices (n, 3) in the object's space, triangles (m, 3)) – evaluated when ``depsgraph`` is given."""
    src = ob.evaluated_get(depsgraph) if depsgraph is not None else ob
    me = src.to_mesh()
    try:
        me.calc_loop_triangles()
        v = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", v)
        t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", t)
    finally:
        src.to_mesh_clear()
    return v.reshape(-1, 3), t.reshape(-1, 3)


def measure(scene, d, frames, pieces, others, every: int = 1, clash_every: int = 1) -> dict:
    """Over ``frames``: {"line": largest distance (mm) of a piece's axis from the middle line, "line_at": (frame, name),
    "depth": deepest clash (mm), "depth_at": (frame, piece, other), "frames": how many were measured}. The line is
    measured at every ``every``-th frame, the clash at every ``clash_every``-th of those (the set moves at most
    0.15 m a frame: a piece 0.5 m long and a roller 0.23 m wide overlap over 0.7 m of its way, so every second frame
    sees each overlap)."""
    from fresing_render.blender import clash

    route = d.sheet("route")["cps_store"]["run_route"]
    line = Line(route_points(route))
    root = d.root()
    # each piece: five points on the set's axis (the rack's line, model x) along its length, in its own space
    cs = d.sheet("route")["cps_store"]
    y0, z0 = float(cs["rows_y"][0]), float(cs["levels_z"][-1])
    R0 = np.linalg.inv(np.array(root.matrix_world))
    axes, cad = {}, {}
    for ob in pieces:
        v, _t = _mesh(ob)
        cad[ob.name] = v
        M = R0 @ np.array(ob.matrix_world)
        xs = (v @ M[:3, :3].T + M[:3, 3])[:, 0] * 1000.0
        pts = np.array([[x, y0, z0] for x in np.linspace(xs.min(), xs.max(), 5)]) / 1000.0
        Mi = np.linalg.inv(M)
        axes[ob.name] = pts @ Mi[:3, :3].T + Mi[:3, 3]
    sc = scene
    keep = sc.frame_current
    sc.frame_set(frames[0])
    R0 = np.linalg.inv(np.array(root.matrix_world))
    env = []
    for ob in others:
        v, t = _mesh(ob)
        if not len(t):
            continue
        M = R0 @ np.array(ob.matrix_world)
        vm = v @ M[:3, :3].T + M[:3, 3]                 # (metres: the clash module's tolerances are in metres)
        env.append((ob.name, clash.Mesh(vm, t, oriented=True), vm.min(0), vm.max(0)))
    out = {"line": 0.0, "line_at": None, "depth": 0.0, "depth_at": None, "frames": 0}
    for n, f in enumerate(frames[::every]):
        sc.frame_set(f)
        dg = __import__("bpy").context.evaluated_depsgraph_get()
        R = np.linalg.inv(np.array(root.matrix_world))
        for ob in pieces:
            v, t = _mesh(ob, dg)
            M = R @ np.array(ob.matrix_world)
            vm = v @ M[:3, :3].T + M[:3, 3]
            # the axis: the piece's own points moved as its geometry was (a stiff move: fit it from three corners)
            W = _fit(cad[ob.name], v)
            ax = (axes[ob.name] @ W[:3, :3].T + W[:3, 3])
            ax = (ax @ M[:3, :3].T + M[:3, 3]) * 1000.0
            dist = max(line.distance(q) for q in ax)
            if dist > out["line"]:
                out["line"], out["line_at"] = dist, (f, ob.name)
            if n % clash_every:
                continue
            lo, hi = vm.min(0) - 1e-3, vm.max(0) + 1e-3
            piece = None
            for name, mesh, elo, ehi in env:
                if (elo > hi).any() or (ehi < lo).any():
                    continue
                dpt, _g = mesh.depths(vm)
                deep = float(dpt.max()) if len(dpt) else 0.0
                if piece is None:
                    piece = clash.Mesh(vm, t, oriented=True)
                inside = (mesh.v >= lo).all(1) & (mesh.v <= hi).all(1)
                if inside.any():
                    d2, _g = piece.depths(mesh.v[inside])
                    deep = max(deep, float(d2.max()))
                if 1000.0 * deep > out["depth"]:
                    out["depth"], out["depth_at"] = 1000.0 * deep, (f, ob.name, name)
        out["frames"] += 1
    sc.frame_set(keep)
    return out


def _fit(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The stiff move (4 x 4) that takes points ``a`` onto ``b`` (same order)."""
    ca, cb = a.mean(0), b.mean(0)
    U, _S, Vt = np.linalg.svd((a - ca).T @ (b - cb))
    D = np.eye(3)
    D[2, 2] = np.sign(np.linalg.det(Vt.T @ U.T))
    Rm = Vt.T @ D @ U.T
    M = np.eye(4)
    M[:3, :3], M[:3, 3] = Rm, cb - Rm @ ca
    return M


def near_parts(scene, d, margin: float = 1500.0) -> list:
    """The parts within ``margin`` mm of the CPS's line (its box), but cables and things riding on a cable (the clash
    check leaves them out too) and excluded parts."""
    from fresing_render.blender import build, paths, paths_riders

    pts = route_points(d.sheet("route")["cps_store"]["run_route"], 50.0)
    lo, hi = pts.min(0) - margin, pts.max(0) + margin
    R0 = np.linalg.inv(np.array(d.root().matrix_world))
    skip = {o.name for o in paths.cable_parts(scene)} | {o.name for o in paths_riders.rider_parts(scene)}
    out = []
    for o in build.iter_parts(scene):
        if o.name in skip or o.type != "MESH" or o.get(build.PROP_EXCLUDED):
            continue
        M = R0 @ np.array(o.matrix_world)
        bb = (np.array([tuple(c) for c in o.bound_box]) @ M[:3, :3].T + M[:3, 3]) * 1000.0
        if (bb.min(0) > hi).any() or (bb.max(0) < lo).any():
            continue
        out.append(o)
    return out
