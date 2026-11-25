"""Long cables and hoses meshed by their own rule (task 0325).

A cable or hose from CAD is a circle swept along a long curve: one B-spline face (or a few in a row) closed round, and a
flat cap at each end. OpenCascade's mesher refines such a face along its whole length by the face's high degree and the
Detail's gap in mm: a 30 m cable of the Stress model came to 30,000–220,000 triangles at Normal – and on long, lumpy
sweeps it even flattened stretches of the tube (the mesh had 56–82 % of the CAD surface's area). Here the face is
meshed as a grid instead:

* **round:** ``segments`` from the diameter – the sag between the true circle and a segment stays below the Detail's
  ``tube_gap`` (``FACETS``; Ø20 mm: 10 / 16 / 25 segments at Draft / Normal / Fine); more where the kept rows need it
  (rows that run slanted across the tube, a lumpy stretch: ``_round_sag``);
* **along:** rings only where the tube bends – a row is left out while the surface there stays within the same gap of
  the mesh between its neighbours (``rings``). Straight runs get few rings, a bend as many as it needs;
* **normals** are the surface's own at every point, so smooth shading shows no facets;
* **caps** are fans on the very points of the tube's end ring, and faces of a tube in a row share their ring: the mesh
  stays closed (no cracks).

Recognised by shape only (never by names): every face is either a tube face – not a plane, cylinder, cone, sphere or
torus (those mesh light already), closed round one direction, round by its own curvature (1 / curvature round it the
same on at least ``ROUND_SHARE`` of it, along it at most half that) and the whole part at least ``LONG`` times as long
as it is thick – or a flat cap on a tube's end, straight across it. Anything else (a hollow hose with ring-shaped caps,
a cable with a moulded end, an end cut at a slant, a square duct) returns None, and the part is meshed by OpenCascade
as before.

No bpy; OpenCascade is imported lazily. Points are in the faces' own frame (without the shape's location), as
OpenCascade's triangulations are: the caller places them.
"""

from __future__ import annotations

import math

import numpy as np

LONG = 20.0           # length / diameter: shorter tubes (a bolt's shank, a short hose) mesh as before
ROUND_DEV = 0.10      # round: 1 / curvature round the tube within this share of the face's median radius …
ROUND_ALONG = 0.5     # … and along it at most half that curvature (a bend at least 3 radii round its middle) …
ROUND_SHARE = 0.75    # … on this share of the face at least (a lumpy stretch – an approximated sweep – is meshed as it is:
                      # the sag along and round is checked on the surface itself); nowhere a crease (radius < a tenth)
MIN_SEG, MAX_SEG = 8, 48
DENSE_PER_R = 0.5     # the first look along: one row of points every half radius …
DENSE_MAX = 6000      # … at most this many rows per face
AROUND_LOOK = 12      # points round each row of that first look
MAX_FACES = 64

_ANALYTIC = ("GeomAbs_Plane", "GeomAbs_Cylinder", "GeomAbs_Cone", "GeomAbs_Sphere", "GeomAbs_Torus")


def segments(radius_mm: float, gap_mm: float) -> int:
    """Segments round a circle of this radius so that a segment's middle lies at most ``gap_mm`` inside it."""
    if radius_mm <= 0:
        return MIN_SEG
    c = 1.0 - gap_mm / radius_mm
    if c <= -1.0:
        return MIN_SEG
    step = 2.0 * math.acos(max(-1.0, min(1.0, c)))
    n = math.ceil(2.0 * math.pi / step) if step > 0 else MAX_SEG
    return int(min(MAX_SEG, max(MIN_SEG, n)))


def rings(rows: np.ndarray, gap_mm: float) -> list[int]:
    """Which rows of a densely sampled tube to keep: ``rows`` (D, n, 3) = D rows along of the n points round the mesh
    will have. The first and the last row always; in between, a row is left out while every row between two kept ones
    lies within ``gap_mm`` of the mesh there: its points are compared, square to the tube, with the mesh's cross-section
    at that place (the two kept rows blended, a closed line through the n points) – so a bend, a wobble and rows that
    twist against each other (the mesh's lines then cut inside the tube) all count. Greedy: from a kept row, the
    farthest row that still fits (doubling, then halving the step)."""
    d = len(rows)
    if d <= 2:
        return list(range(d))
    near = (-2, -1, 0, 1)                     # segments of the cross-section looked at round each point

    def fits(i: int, j: int) -> bool:
        if j - i < 2:
            return True
        a, b = rows[i], rows[j]                                   # (n, 3)
        mid = rows[i + 1:j]                                       # (m, n, 3)
        t = (np.arange(1, j - i) / float(j - i))[:, None, None]
        q = a + t * (b - a)                                       # the mesh's cross-sections (m, n, 3)
        ax = b.mean(axis=0) - a.mean(axis=0)
        ln = float(np.linalg.norm(ax))
        if ln > 0:                                                # square to the tube: along it is no error
            ax = ax / ln
            mid = mid - np.einsum("mkc,c->mk", mid, ax)[..., None] * ax
            q = q - np.einsum("mkc,c->mk", q, ax)[..., None] * ax
        best = None
        for o in near:
            s0 = np.roll(q, -o, axis=1)
            s1 = np.roll(q, -(o + 1), axis=1)
            seg = s1 - s0
            ll = np.einsum("mkc,mkc->mk", seg, seg)
            ll[ll == 0] = 1.0
            u = np.clip(np.einsum("mkc,mkc->mk", mid - s0, seg) / ll, 0.0, 1.0)
            dist = np.linalg.norm(mid - (s0 + u[..., None] * seg), axis=2)
            best = dist if best is None else np.minimum(best, dist)
        return float(best.max()) <= gap_mm

    keep = [0]
    i = 0
    while i < d - 1:
        step = 1
        while i + step * 2 <= d - 1 and fits(i, i + step * 2):
            step *= 2
        lo, hi = i + step, min(d - 1, i + step * 2)               # lo fits, hi may not
        if hi == d - 1 and fits(i, hi):
            lo = hi
        else:
            while hi - lo > 1:
                m = (lo + hi) // 2
                if fits(i, m):
                    lo = m
                else:
                    hi = m
        keep.append(lo)
        i = lo
    return keep


# --------------------------------------------------------------------------
# OpenCascade side
# --------------------------------------------------------------------------

class _Tube:
    """One tube face: which parameter goes round, its ranges, its first look along."""

    def __init__(self, k, face, surf, round_is_u):
        self.k = k
        self.face = face
        self.surf = surf
        self.round_is_u = round_is_u
        self.ends: list = [None, None]             # per end: ("cap", plane face k) / ("tube", other k, its end) / None
        self.pts = None                            # (rows, n, 3) once meshed
        self.nrm = None
        self.round_params = None                   # (rows, n): the round parameter of every point (rows of a chain
                                                   # may be turned against each other)

    def at(self, along, around):
        return (around, along) if self.round_is_u else (along, around)


def _surface_point(surf, u, v):
    p = surf.Value(u, v)
    return (p.X(), p.Y(), p.Z())


def _point_normal(surf, u, v):
    from OCP.gp import gp_Pnt, gp_Vec
    p, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    surf.D1(u, v, p, du, dv)
    n = du.Crossed(dv)
    m = n.Magnitude()
    return (p.X(), p.Y(), p.Z()), ((n.X() / m, n.Y() / m, n.Z() / m) if m > 1e-12 else None)


def _type_name(surf) -> str:
    try:
        return surf.GetType().name
    except Exception:
        return str(surf.GetType())


def _ends_straight_across(face, surf, round_is_u, a0, a1) -> bool:
    """Every edge of the face that is not its seam runs along one end (constant along-parameter)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve2d
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    to_edge = getattr(TopoDS, "Edge", None) or getattr(TopoDS, "Edge_s")
    tol = 1e-4 * abs(a1 - a0) + 1e-9
    exp = TopExp_Explorer(face, TopAbs_EDGE)
    while exp.More():
        e = to_edge(exp.Current())
        exp.Next()
        if BRep_Tool.IsClosed_s(e, face) or BRep_Tool.Degenerated_s(e):
            continue                                              # the seam (or a pole)
        pc = BRepAdaptor_Curve2d(e, face)                         # the edge on the face: (u, v) along it
        f, l = pc.FirstParameter(), pc.LastParameter()
        if not (math.isfinite(f) and math.isfinite(l)):
            return False
        for s in np.linspace(f, l, 7):
            q = pc.Value(float(s))
            along = q.Y() if round_is_u else q.X()
            if min(abs(along - a0), abs(along - a1)) > tol:
                return False
    return True


def _first_look(tube: _Tube, a0, a1, r0, r1):
    """Is the face a round tube, and the rows of a first look along it. Round = the surface curves round by the same
    radius everywhere (1 / its larger curvature, each point within ``ROUND_DEV`` of the face's median; along it curves
    at most half as much): judged from the surface's own curvature, so a face whose rows run slanted across the tube
    (a sweep approximated by OpenCascade or a CAD program) is round too. Returns (along params, rows (D, K, 3),
    row middles, radius per row) or None."""
    from OCP.BRepLProp import BRepLProp_SLProps
    surf = tube.surf
    rr = np.linspace(r0, r1, AROUND_LOOK, endpoint=False)
    probe = np.linspace(a0, a1, 33)
    props = BRepLProp_SLProps(surf, 2, 1e-9)
    radii, along_ok = [], []
    for a in probe:
        for r in rr:
            props.SetParameters(*tube.at(float(a), float(r)))
            if not props.IsCurvatureDefined():
                return None
            k1, k2 = props.MaxCurvature(), props.MinCurvature()
            big, small = max(abs(k1), abs(k2)), min(abs(k1), abs(k2))
            if big <= 0:
                return None                                       # flat round the face: no tube
            radii.append(1.0 / big)
            along_ok.append(small <= ROUND_ALONG * big)
    radii = np.array(radii)
    radius = float(np.median(radii))
    tube_like = (np.abs(radii - radius) <= ROUND_DEV * radius) & np.array(along_ok)
    if tube_like.mean() < ROUND_SHARE or float(radii.min()) < 0.1 * radius:
        return None
    rows = np.array([[_surface_point(surf, *tube.at(a, r)) for r in rr] for a in probe])
    cen = rows.mean(axis=1)
    length = float(np.linalg.norm(np.diff(cen, axis=0), axis=1).sum())
    dense = int(min(DENSE_MAX, max(33, math.ceil(length / max(1e-6, DENSE_PER_R * radius)) + 1)))
    params = np.linspace(a0, a1, dense)
    rows = np.array([[_surface_point(surf, *tube.at(a, r)) for r in rr] for a in params])
    return params, rows, rows.mean(axis=1), np.full(dense, radius)


def plan(shape, gap_mm: float):
    """{face number: (points Nx3, normals Nx3, triangles Mx3)} for a long cable or hose (faces in the order of
    ``step_reader._faces``; points in the faces' own frame, mm; normals the surfaces' own, before the face's
    orientation), or None when the part is not one."""
    try:
        return _plan(shape, gap_mm)
    except Exception:                                  # any doubt: OpenCascade meshes it as before
        return None


def _plan(shape, gap_mm: float):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    to_face = getattr(TopoDS, "Face", None) or getattr(TopoDS, "Face_s")
    faces = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        faces.append(to_face(exp.Current()))
        exp.Next()
        if len(faces) > MAX_FACES:
            return None
    if not faces:
        return None
    loc0 = faces[0].Location()
    if any(not f.Location().IsEqual(loc0) for f in faces):
        return None
    bare = [to_face(f.Located(TopLoc_Location())) for f in faces]

    tubes: list[_Tube] = []
    planes: list[int] = []
    for k, f in enumerate(bare):
        surf = BRepAdaptor_Surface(f, True)
        name = _type_name(surf)
        if name.endswith("GeomAbs_Plane") or name == "GeomAbs_Plane":
            planes.append(k)
            continue
        if any(name.endswith(a) for a in _ANALYTIC):
            return None
        uc, vc = surf.IsUClosed(), surf.IsVClosed()
        if uc == vc:
            return None
        tubes.append(_Tube(k, f, surf, bool(uc)))
    if not tubes:
        return None

    # the first look along every tube face
    looks = {}
    total_len, r_max = 0.0, 0.0
    for t in tubes:
        s = t.surf
        u0, u1, v0, v1 = s.FirstUParameter(), s.LastUParameter(), s.FirstVParameter(), s.LastVParameter()
        (r0, r1), (a0, a1) = ((u0, u1), (v0, v1)) if t.round_is_u else ((v0, v1), (u0, u1))
        if not (a1 > a0 and r1 > r0):
            return None
        if not _ends_straight_across(t.face, s, t.round_is_u, a0, a1):
            return None
        look = _first_look(t, a0, a1, r0, r1)
        if look is None:
            return None
        params, rows, cen, rm = look
        if float(rm.max()) > 3.0 * float(rm.min()):
            return None
        looks[t.k] = (a0, a1, r0, r1, params, rows, cen, rm)
        total_len += float(np.linalg.norm(np.diff(cen, axis=0), axis=1).sum())
        r_max = max(r_max, float(rm.max()))
    if total_len < LONG * 2.0 * r_max:
        return None
    n = segments(r_max, gap_mm)

    # what lies at each end: another tube face's end, a flat cap, or nothing
    def end_ring(k, e):
        look = looks[k]
        return look[5][0 if e == 0 else -1], look[6][0 if e == 0 else -1], look[7][0 if e == 0 else -1]
    for t in tubes:
        for e in (0, 1):
            if t.ends[e] is not None:
                continue
            _ring, c, r = end_ring(t.k, e)
            for o in tubes:
                if o is t:
                    continue
                for oe in (0, 1):
                    if o.ends[oe] is None:
                        _r2, c2, rr2 = end_ring(o.k, oe)
                        if np.linalg.norm(c - c2) < 0.1 * r and abs(r - rr2) < 0.1 * r:
                            t.ends[e] = ("tube", o.k, oe)
                            o.ends[oe] = ("tube", t.k, e)
                            break
                if t.ends[e] is not None:
                    break
    used_planes: set = set()
    for t in tubes:
        for e in (0, 1):
            if t.ends[e] is not None:
                continue
            ring, c, r = end_ring(t.k, e)
            for k in planes:
                if k in used_planes:
                    continue
                pl = BRepAdaptor_Surface(bare[k], True).Plane()
                o, d = pl.Location(), pl.Axis().Direction()
                nv = np.array((d.X(), d.Y(), d.Z()))
                dist = (ring - np.array((o.X(), o.Y(), o.Z()))) @ nv
                if np.abs(dist).max() > max(0.01 * r, 1e-3):
                    continue
                props = GProp_GProps()
                BRepGProp.SurfaceProperties_s(bare[k], props)
                area = props.Mass()
                circle = _ring_area(t, e, looks)
                if circle <= 0 or abs(area - circle) > 0.03 * circle:
                    continue
                t.ends[e] = ("cap", k)
                used_planes.add(k)
                break
    if len(used_planes) != len(planes):
        return None                                    # a flat face that is no cap on a tube's end

    # the rows kept along each face; then enough segments round that the sag stays within the gap on every kept row
    # (rows that run slanted across the tube are longer round than the tube's circle)
    # – checked along every one of the mesh's own lines round, so a lump between them cannot slip through
    for _ in range(4):
        alongs = {}
        for t in tubes:
            a0, a1, r0, r1, params = looks[t.k][:5]
            dense = np.array([[_surface_point(t.surf, *t.at(float(a), float(r)))
                               for r in np.linspace(r0, r1, n, endpoint=False)] for a in params])
            alongs[t.k] = params[rings(dense, gap_mm)]
        worst = max(_round_sag(t, alongs[t.k], looks[t.k], n) for t in tubes)
        if worst <= 1.05 * gap_mm or n >= MAX_SEG:
            break
        n = min(MAX_SEG, max(n + 1, math.ceil(n * math.sqrt(worst / gap_mm))))

    # mesh the tubes, a chain of faces from one end to the other (rings shared)
    out = {}
    done: set = set()
    order = sorted(tubes, key=lambda t: (t.ends[0] is not None and t.ends[0][0] == "tube"))
    by_k = {t.k: t for t in tubes}
    for start in order:
        if start.k in done:
            continue
        queue = [(start, None)]
        while queue:
            t, shared = queue.pop(0)
            if t.k in done:
                continue
            _mesh_tube(t, looks[t.k], alongs[t.k], n, shared)
            done.add(t.k)
            for e in (0, 1):
                end = t.ends[e]
                if end is not None and end[0] == "tube" and end[1] not in done:
                    row = 0 if e == 0 else -1
                    queue.append((by_k[end[1]], (end[2], t.pts[row], t.nrm[row])))
        # (a ring of tubes closes on itself: its last seam is shared by the first face's points – see _mesh_tube)
    for t in tubes:
        rows, nn, _ = t.pts.shape
        pts = t.pts.reshape(-1, 3)
        nrm = t.nrm.reshape(-1, 3)
        i = np.arange(rows - 1)[:, None]
        j = np.arange(n)[None, :]
        a = i * n + j
        b = i * n + (j + 1) % n
        c = (i + 1) * n + (j + 1) % n
        d = (i + 1) * n + j
        tri = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, d], -1).reshape(-1, 3)])
        tri = _orient(pts, nrm, tri)
        out[t.k] = (pts, nrm, tri)
        for e in (0, 1):
            end = t.ends[e]
            if end is not None and end[0] == "cap":
                out[end[1]] = _cap(bare[end[1]], t.pts[0 if e == 0 else -1])
    return out


def _ring_area(t: _Tube, e: int, looks) -> float:
    """Area inside the tube's end ring (64 points: close to the true curve), mm²."""
    a0, a1, r0, r1 = looks[t.k][:4]
    a = a0 if e == 0 else a1
    pts = np.array([_surface_point(t.surf, *t.at(a, r)) for r in np.linspace(r0, r1, 64, endpoint=False)])
    c = pts.mean(axis=0)
    cr = np.cross(pts - c, np.roll(pts, -1, axis=0) - c)
    return float(np.linalg.norm(cr.sum(axis=0)) / 2.0)


def _round_sag(t: _Tube, along, look, n: int, most: int = 5000) -> float:
    """The largest gap between a segment's middle and the surface half way round, over the kept rows (at most
    ``most`` of them), mm."""
    r0, r1 = look[2], look[3]
    rp = np.linspace(r0, r1, n + 1)
    mid = (rp[:-1] + rp[1:]) / 2.0
    rows = along if len(along) <= most else along[np.linspace(0, len(along) - 1, most).astype(int)]
    worst = 0.0
    for a in rows:
        p = np.array([_surface_point(t.surf, *t.at(float(a), float(r))) for r in rp])
        m = np.array([_surface_point(t.surf, *t.at(float(a), float(r))) for r in mid])
        worst = max(worst, float(np.linalg.norm(m - (p[:-1] + p[1:]) / 2.0, axis=1).max()))
    return worst


def _mesh_tube(t: _Tube, look, along, n: int, shared) -> None:
    """The grid of one tube face: the kept rows x n points round. ``shared``: (this face's end, the ring's points,
    their normals) from the face before it in the chain – that end row takes those very points, and the round
    parameters of every row follow them (the faces' seams need not line up)."""
    r0, r1 = look[2], look[3]
    round_p = np.linspace(r0, r1, n, endpoint=False)
    offset = None
    if shared is not None:
        end, ring_pts, _ring_nrm = shared
        a_end = along[0] if end == 0 else along[-1]
        fine = np.linspace(r0, r1, 16 * n, endpoint=False)
        cand = np.array([_surface_point(t.surf, *t.at(a_end, r)) for r in fine])
        idx = [int(np.argmin(np.linalg.norm(cand - p, axis=1))) for p in ring_pts]
        offset = fine[idx]
    pts = np.empty((len(along), n, 3))
    nrm = np.empty((len(along), n, 3))
    missing = []
    rp = offset if offset is not None else round_p
    for i, a in enumerate(along):
        for j, r in enumerate(rp):
            p, nv = _point_normal(t.surf, *t.at(float(a), float(r)))
            pts[i, j] = p
            if nv is None:                                       # a pole of the parameters: filled in below
                missing.append((i, j))
                nv = (0.0, 0.0, 0.0)
            nrm[i, j] = nv
    if missing:                                                  # from the ring's middle, on the side the surface's
        c = pts.mean(axis=1, keepdims=True)                      # own normals point (out or in)
        out = np.sign(np.einsum("ijc,ijc->", pts - c, nrm)) or 1.0
        for i, j in missing:
            v = pts[i, j] - c[i, 0]
            ln = float(np.linalg.norm(v))
            nrm[i, j] = out * v / ln if ln else (0.0, 0.0, 1.0)
    if shared is not None:
        end, ring_pts, _ring_nrm = shared
        row = 0 if end == 0 else -1
        pts[row] = ring_pts                                      # the very same points: no crack
    t.pts, t.nrm = pts, nrm


def _orient(pts, nrm, tri):
    """Triangles wound so that their normals agree with the point normals (most of them)."""
    v0, v1, v2 = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    agree = np.einsum("ic,ic->i", fn, nrm[tri[:, 0]] + nrm[tri[:, 1]] + nrm[tri[:, 2]])
    if (agree < 0).sum() > (agree > 0).sum():
        tri = tri[:, (0, 2, 1)]
    return tri


def _cap(face, ring):
    """A flat cap: a fan from the ring's middle on the tube's own end points; normals the plane's own."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    d = BRepAdaptor_Surface(face, True).Plane().Axis().Direction()
    nv = np.array((d.X(), d.Y(), d.Z()))
    n = len(ring)
    pts = np.vstack([ring, ring.mean(axis=0)[None, :]])
    nrm = np.tile(nv, (n + 1, 1))
    j = np.arange(n)
    tri = np.stack([j, (j + 1) % n, np.full(n, n)], -1)
    v0, v1, v2 = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
    if float(np.cross(v1 - v0, v2 - v0).sum(axis=0) @ nv) < 0:
        tri = tri[:, (0, 2, 1)]
    return pts, nrm, tri
