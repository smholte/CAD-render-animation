"""Measuring in the 3D view (task 0322): what the mouse is over, the measurements kept with the project, the labels.

What a click takes (``look``): the ray is the hover highlight's (``hover.cast``: a sticker counts as the part under it),
but what is not a part – a weld, the floor, the surroundings – is looked through, and so is a slice (``cast``): where the ray meets a part on the side a
cut takes away, it goes on to the cut face, and when that point lies inside the part, the click takes the cut face.
The part's mesh knows its CAD faces (``fr_face_starts``) and the axes of its round faces (``fr_axes``,
``fr_axis_faces``); the 3D page's face data (``core/web3d_faces.py`` ``classify`` and ``edges``, one behaviour for
both) turns them into flat faces (plane), round faces (axis + radius) and the straight and round CAD edges between two
faces – worked out once per mesh (``data_of``). The hovered face offers its corners, edge middles, its centre (a flat
face's middle, a round face's axis centre), its round edges' centres, its edges and itself; ``core.measure.choose``
takes the nearest (Shift: the face under the mouse as it is).

A measurement (``FRMeasureItem`` in ``scene.fresing_measure.items``) keeps its picks in the clicked part's own
coordinates (``FRMeasurePick``): it follows the part when the part moves, a joint turns it or an animation plays
(the result is worked out from the parts' places at the frame shown, ``world``).

The labels are drawn by two draw handlers of the 3D view (lines, then the boxes with the text): never in a render.
**Show in renders** makes real objects of them (``render_objects``, a collection "FR measurements": a thin tube per
line and a text facing the camera), updated at every frame change while it is ticked. **Keep measurements** off: a
save leaves them out of the file (``_before_save`` / ``_after_save``); the Client view never saves them – there they
are only for looking.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import bpy
import numpy as np
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)
from bpy.types import PropertyGroup
from mathutils import Matrix, Vector

from ..core import measure as core
from . import build

COLLECTION = "FR measurements"
KIND = "measure"                     # fr_kind of the render objects
LINE = (0.10, 0.78, 1.00)            # a measurement's line: a clear blue (the hover highlight is magenta)
PENDING = (1.0, 0.10, 0.80)          # the clicks of a measurement not finished yet: the hover's magenta
DARK = (0.05, 0.05, 0.05, 0.85)
AXES = ((0.95, 0.25, 0.25), (0.45, 0.85, 0.20), (0.30, 0.55, 1.00))   # X / Y / Z parts: Blender's axis colours
NP = 24                              # numbers kept per pick (FRMeasurePick.v)
PULL = 0.2                           # render labels and lines sit at this share of their distance from the camera

# ---------------------------------------------------------------------------
# the settings (scene.fresing_measure)
# ---------------------------------------------------------------------------

UNIT_ITEMS = [("MM", "mm", "Millimetres, two decimals"), ("M", "m", "Metres, four decimals"),
              ("INCH", "inch", "Inches, three decimals")]
KIND_ITEMS = [(k, core.TITLES[k], core.HELP[k]) for k in core.KINDS]


def _redraw_views(_self=None, _context=None):
    for win in getattr(bpy.context.window_manager, "windows", ()):
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _render_changed(self, context):
    try:
        render_objects(context.scene)
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: measurements for renders not made:", exc)
    _redraw_views()


class FRMeasurePick(PropertyGroup):
    part: PointerProperty(type=bpy.types.Object)
    kind: StringProperty(default="point")         # core.Pick.kind
    v: FloatVectorProperty(size=NP)               # p n o d r a b s sweep, in the part's own coordinates (``_pack``)
    what: StringProperty(default="")


class FRMeasureItem(PropertyGroup):
    name: StringProperty(name="Name", default="")
    kind: StringProperty(default="SMART")
    picks: CollectionProperty(type=FRMeasurePick)
    show: BoolProperty(name="Show", default=True, update=_redraw_views,
                       description="Show this measurement in the 3D view (and in renders when Show in renders is on)")


class FRMeasureSettings(PropertyGroup):
    items: CollectionProperty(type=FRMeasureItem)
    units: EnumProperty(name="Units", items=UNIT_ITEMS, default="MM", update=_redraw_views,
                        description="The unit every measurement is shown and copied in: mm, m or inch")
    last: EnumProperty(name="Measure", items=KIND_ITEMS, default="SMART",
                       description="What the key M (Alt+M) measures: the last kind you picked in the Measure menu")
    keep: BoolProperty(name="Keep measurements", default=True,
                       description="Save the measurements with the project, so they are there when it is opened again. "
                                   "Off: they stay until you close the project, the file leaves them out")
    in_renders: BoolProperty(name="Show in renders", default=False, update=_render_changed,
                             description="Also show the measurements in pictures and videos you render (lines and "
                                         "labels as real objects). Off: they are only drawn in the 3D view")
    show: BoolProperty(name="Show measurements", default=True, update=_redraw_views,
                       description="Show the measurements in the 3D view; off hides them all without clearing them")
    label_size: FloatProperty(name="Label size", default=1.0, min=0.6, max=2.0, update=_redraw_views,
                              description="How big the labels are drawn in the 3D view")


CLASSES = (FRMeasurePick, FRMeasureItem, FRMeasureSettings)


def settings(scene=None):
    scene = scene or bpy.context.scene
    return scene.fresing_measure


# ---------------------------------------------------------------------------
# a mesh's CAD faces and edges (worked out once per mesh)
# ---------------------------------------------------------------------------

@dataclass
class MeshData:
    n_poly: int
    face_of_poly: np.ndarray                     # CAD face of each polygon (-1: none)
    rows: dict                                   # CAD face -> core/web3d_faces.py row (mesh coordinates)
    edges: list                                  # (face a, face b, kind, p1, p2, p3) mesh coordinates
    by_face: dict = field(default_factory=dict)  # CAD face -> [edge index]
    centre: dict = field(default_factory=dict)   # CAD face -> its centre (flat: area middle; round: axis centre)
    ms: float = 0.0


_DATA: dict = {}                                 # mesh session id -> MeshData


def data_of(me) -> MeshData | None:
    """The CAD faces and edges of a part's mesh (None: no CAD face data – a mesh model, a milled part)."""
    from ..core import web3d_faces as wf
    n = len(me.polygons)
    hit = _DATA.get(me.session_uid)
    if hit is not None and hit.n_poly == n:
        return hit
    t0 = time.perf_counter()
    starts = me.get("fr_face_starts")
    if starts is None or not n:
        return None
    starts = np.asarray(list(starts), np.int64)
    if len(starts) < 2 or int(starts[-1]) != n:
        return None
    face_of_poly = wf.face_of_triangles(n, starts)
    me.calc_loop_triangles()
    lt = me.loop_triangles
    tri = np.empty(len(lt) * 3, np.int64)
    lt.foreach_get("vertices", tri)
    tri = tri.reshape(-1, 3)
    poly = np.empty(len(lt), np.int64)
    lt.foreach_get("polygon_index", poly)
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    face = face_of_poly[poly]
    axes = list(me["fr_axes"]) if "fr_axes" in me else None
    axis_faces = list(me["fr_axis_faces"]) if "fr_axis_faces" in me else None
    if axis_faces:                       # counted in the import's triangles (= polygons): in loop triangles
        first_lt = np.full(n + 1, -1, np.int64)
        first_lt[poly[::-1]] = np.arange(len(poly))[::-1]
        af = np.asarray(axis_faces, np.int64).reshape(-1, 3).copy()
        af = af[(af[:, 0] >= 0) & (af[:, 0] < n)]
        af[:, 0] = first_lt[af[:, 0]]
        axis_faces = af[af[:, 0] >= 0].ravel().tolist()
    rows = wf.classify(co, tri, face, axes, axis_faces)
    found = wf.edges(co, tri, face, rows) if rows else []
    d = MeshData(n, face_of_poly, rows, found)
    for i, e in enumerate(found):
        for f in (int(e[0]), int(e[1])):
            d.by_face.setdefault(f, []).append(i)
    # face centres: flat = the middle of its area, round = the middle of the axis it spans
    order = np.argsort(face, kind="stable")
    cut = np.flatnonzero(np.diff(face[order])) + 1
    for block in np.split(order, cut):
        f = int(face[block[0]])
        if f < 0 or f not in rows:
            continue
        row = rows[f]
        a, b, c = co[tri[block, 0]], co[tri[block, 1]], co[tri[block, 2]]
        if int(row[0]) == wf.FLAT:
            area = np.linalg.norm(np.cross(b - a, c - a), axis=1)
            tot = float(area.sum())
            if tot > 0:
                d.centre[f] = tuple(((a + b + c) / 3.0 * area[:, None]).sum(axis=0) / tot)
        else:
            o, ax = np.asarray(row[1:4]), np.asarray(row[4:7])
            pts = np.concatenate([a, b, c])
            s = (pts - o) @ ax
            d.centre[f] = tuple(o + ax * (float(s.min()) + float(s.max())) / 2.0)
    d.ms = (time.perf_counter() - t0) * 1000.0
    if len(_DATA) > 200:
        _DATA.clear()
    _DATA[me.session_uid] = d
    return d


def forget() -> None:
    _DATA.clear()


# ---------------------------------------------------------------------------
# picks: in a part's coordinates and in the world
# ---------------------------------------------------------------------------

def _m3(M):
    return M.to_3x3()


def _normal_to_world(M, n) -> tuple:
    try:
        v = (M.to_3x3().inverted().transposed() @ Vector(n)).normalized()
    except ValueError:
        v = Vector(n)
    return tuple(v)


def _dir_to_world(M, d) -> tuple:
    return tuple((_m3(M) @ Vector(d)).normalized())


def _pt(M, p) -> tuple:
    return tuple(M @ Vector(p))


def _scale_along(M, d) -> float:
    """How much the matrix stretches a length square to ``d`` (a radius)."""
    perp = core._perp(tuple(d))
    return (_m3(M) @ Vector(perp)).length


def pick_to_world(kind: str, v, M, what: str = "") -> core.Pick:
    """A stored pick (its numbers ``v`` in the part's coordinates) at the part's place ``M``."""
    p, n, o, d = v[0:3], v[3:6], v[6:9], v[9:12]
    r, a, b, s, sweep = v[12], v[13:16], v[16:19], v[19:22], v[22]
    P = _pt(M, p)
    if kind == "flat":
        return core.flat(P, _normal_to_world(M, n), what)
    if kind in ("round", "axis"):
        return core.round_face(P, _pt(M, o), _dir_to_world(M, d), r * _scale_along(M, d) if r > 0 else 0.0, what)
    if kind == "line":
        return core.line(P, _pt(M, a), _pt(M, b), what)
    if kind == "circle":
        ax = _dir_to_world(M, d)
        return core.circle(P, _pt(M, o), _pt(M, s), ax, sweep, what)
    return core.point(P, what)


def _pack(pk: core.Pick) -> list:
    v = [0.0] * NP
    v[0:3], v[3:6], v[6:9], v[9:12] = pk.p, pk.n, pk.o, pk.d
    v[12] = pk.r
    v[13:16], v[16:19], v[19:22] = pk.a, pk.b, pk.s
    v[22] = pk.sweep
    return v


def world_picks(item, scene=None) -> list | None:
    """The picks of a measurement in the world at the frame shown; None when a part is gone."""
    scene = scene or item.id_data
    out = []
    for pk in item.picks:
        ob = pk.part
        if ob is None or ob.name not in scene.objects:
            return None
        out.append(pick_to_world(pk.kind, list(pk.v), ob.matrix_world, pk.what))
    return out


def result(scene, item) -> core.Result | None:
    picks = world_picks(item, scene)
    if picks is None:
        return None
    return core.measure(item.kind, picks, settings(scene).units)


def add(scene, kind: str, picks: list) -> object:
    """A new measurement from ``picks``: [(part object, local core.Pick)] (local = the part's own coordinates)."""
    st = settings(scene)
    item = st.items.add()
    item.kind = kind
    for ob, pk in picks:
        p = item.picks.add()
        p.part = ob
        p.kind = pk.kind
        p.v = _pack(pk)
        p.what = pk.what
    item.name = f"{core.TITLES.get(kind, kind)} {len(st.items)}"
    after_change(scene)
    return item


def remove(scene, index: int) -> None:
    st = settings(scene)
    if 0 <= index < len(st.items):
        st.items.remove(index)
    after_change(scene)


def clear(scene) -> int:
    st = settings(scene)
    n = len(st.items)
    st.items.clear()
    after_change(scene)
    return n


def after_change(scene) -> None:
    if settings(scene).in_renders:
        try:
            render_objects(scene)
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: measurements for renders not updated:", exc)
    _redraw_views()


def to_local(ob, pk: core.Pick) -> core.Pick:
    """A world pick in ``ob``'s own coordinates (what is stored)."""
    M = ob.matrix_world
    try:
        Mi = M.inverted()
    except ValueError:
        Mi = Matrix.Identity(4)
    return pick_to_world(pk.kind, _pack(pk), Mi, pk.what)


# ---------------------------------------------------------------------------
# the ray: parts, stickers, welds and slices
# ---------------------------------------------------------------------------

def _cut_takes(cut, ob, loc) -> bool:
    """Does the slice ``cut`` take away the point ``loc`` (world) of the part ``ob``?"""
    from . import section
    if not cut.enabled or cut.shape is None or not ob.get(section.ATTR + cut.key):
        return False
    try:
        q = cut.shape.matrix_world.inverted() @ Vector(loc)
    except ValueError:
        return False
    s = -1.0 if cut.flip else 1.0
    if cut.shape_kind == "BOX":
        sc = cut.shape.matrix_world.to_scale()
        big = max((abs(q[i]) - 1.0) * sc[i] for i in range(3))
        return s * big < 0.0
    return s * q.z > 0.0


def _leave(cut, o: Vector, d: Vector, t_hit: float):
    """Where the ray o + t d leaves what ``cut`` takes away, after ``t_hit``: (t, the cut face's normal towards the
    viewer) or None (the rest of the ray stays taken away)."""
    M = cut.shape.matrix_world
    try:
        Mi = M.inverted()
    except ValueError:
        return None
    lo, ld = Mi @ o, Mi.to_3x3() @ d
    s = -1.0 if cut.flip else 1.0
    if cut.shape_kind != "BOX":
        if abs(ld.z) < 1e-12:
            return None
        t = -lo.z / ld.z
        if t <= t_hit:
            return None
        n = (M.to_3x3().inverted().transposed() @ Vector((0.0, 0.0, 1.0))).normalized()
        if n.dot(d) > 0:
            n = -n
        return t, n
    tn, tf, an, af = -1e30, 1e30, None, None
    for i in range(3):
        if abs(ld[i]) < 1e-12:
            if abs(lo[i]) > 1.0:
                return None                       # the ray never meets the box
            continue
        t1, t2 = (-1.0 - lo[i]) / ld[i], (1.0 - lo[i]) / ld[i]
        if t1 > t2:
            t1, t2 = t2, t1
        if t1 > tn:
            tn, an = t1, i
        if t2 < tf:
            tf, af = t2, i
    if tn > tf:
        return None
    if s > 0:                                     # inside is taken away: the ray leaves the box at tf
        t, i = tf, af
    else:                                         # outside is taken away: the ray comes into the box at tn
        t, i = tn, an
    if t <= t_hit or i is None:
        return None
    nl = Vector((0.0, 0.0, 0.0))
    nl[i] = 1.0
    n = (M.to_3x3().inverted().transposed() @ nl).normalized()
    if n.dot(d) > 0:                              # the cut face looks at the viewer
        n = -n
    return t, n


@dataclass
class Hit:
    part: object = None                 # the part object
    polygon: int = -1                   # its polygon (-1: the cut face)
    location: Vector | None = None
    normal: Vector | None = None
    cut: str = ""                       # the slice whose cut face this is ("" = a face of the part)


def _ray(scene, depsgraph, o: Vector, d: Vector):
    """The first PART on the ray: (part, polygon, location, normal) or (None, -1, None, None). As ``hover.cast`` (a
    sticker counts as the part under it), but what is not a part – a weld, the floor, the surroundings, the measuring
    objects themselves – is looked through."""
    from . import decals
    for _k in range(16):
        hit, loc, normal, index, ob, _m = scene.ray_cast(depsgraph, o, d)
        if not hit or ob is None:
            return None, -1, None, None
        ob = getattr(ob, "original", ob)
        part, index, loc2, normal2 = decals.through(ob, index, loc, normal)
        if part.get(build.PROP_KIND) == "part":
            return part, index, Vector(loc2), Vector(normal2)
        o = Vector(loc) + d * 1e-5
    return None, -1, None, None


def cast(scene, depsgraph, origin, direction) -> Hit | None:
    """The part under the ray, a slice looked through: ``Hit`` or None."""
    o, d = Vector(origin), Vector(direction).normalized()
    cuts = [c for c in getattr(scene.fresing, "cuts", ()) if c.enabled and c.shape is not None]
    for _k in range(12):
        ob, index, loc, normal = _ray(scene, depsgraph, o, d)
        if index < 0 or ob is None:
            return None
        if not cuts:
            return Hit(ob, index, loc, normal)
        taker = next((c for c in cuts if _cut_takes(c, ob, loc)), None)
        if taker is None:
            return Hit(ob, index, loc, normal)
        t_hit = (loc - o).dot(d)
        got = _leave(taker, o, d, t_hit)
        if got is None:
            o = loc + d * 1e-5
            continue
        t, n = got
        x = o + d * t
        nob, nidx, _nloc, nnormal = _ray(scene, depsgraph, x, d)
        past = x + d * 1e-6                                       # just on the kept side of the cut face
        if nob is ob and nidx >= 0 and nnormal.dot(d) > 0 and not any(_cut_takes(c, ob, past) for c in cuts):
            return Hit(ob, -1, x, n, cut=taker.name)          # x lies inside the part: on its cut face
        o = x + d * 1e-5
    return None


# ---------------------------------------------------------------------------
# what the mouse is over
# ---------------------------------------------------------------------------

@dataclass
class Look:
    part: str = ""                      # object name ("" = nothing measurable under the mouse)
    pick: core.Pick | None = None       # what a click takes (world)
    cand: object = None                 # the core.Candidate chosen
    cands: list = field(default_factory=list)
    face: int = -1                      # CAD face (-1: none / a cut face)
    text: str = "Not a part"
    refused: str = ""
    ms: float = 0.0
    draw_pts: list = field(default_factory=list)    # the snapped point (world), for the dot
    draw_line: list = field(default_factory=list)   # the snapped edge's points (world), for the line


def _row_pick(row, M, p, what: str = "") -> core.Pick:
    from ..core import web3d_faces as wf
    kind = int(row[0])
    if kind == wf.FLAT:
        n = row[1:4]
        return core.flat(p, _normal_to_world(M, n), what or "flat face")
    o, d, r = row[1:4], row[4:7], float(row[7])
    rr = r * _scale_along(M, d) if r > 0 else 0.0
    if not what:
        what = f"round face Ø {core.fmt(2 * rr)}" if rr > 0 else "round face"
    return core.round_face(p, _pt(M, o), _dir_to_world(M, d), rr, what)


def candidates(ob, face: int, hit_loc, hit_normal, project, cut_name: str = "") -> list:
    """What the hovered face offers: [core.Candidate] (world), ``project(world) -> (x, y) | None``."""
    from ..core import web3d_faces as wf
    M = ob.matrix_world
    out = []
    loc = tuple(hit_loc)
    if cut_name:
        out.append(core.Candidate("face", core.flat(loc, tuple(hit_normal), f"cut face of {cut_name}")))
        return out
    d = data_of(ob.data) if ob.type == "MESH" and ob.data is not None else None
    if d is None or face < 0 or face not in d.rows:
        out.append(core.Candidate("face", core.point(loc, "spot on the part")))
        return out
    out.append(core.Candidate("face", _row_pick(d.rows[face], M, loc)))
    c = d.centre.get(face)
    if c is not None:
        w = _pt(M, c)
        kind = "axis centre" if int(d.rows[face][0]) != wf.FLAT else "face centre"
        out.append(core.Candidate("centre", core.point(w, kind), screen=project(w)))
    for i in d.by_face.get(face, ()):
        fa, fb, kind, p1, p2, p3 = d.edges[i]
        if kind == wf.LINE:
            a, b = _pt(M, p1), _pt(M, p2)
            ln = core.line(loc, a, b, f"edge {core.fmt(core.length(core.sub(b, a)))}")
            for q, k in ((a, "corner"), (b, "corner")):
                out.append(core.Candidate(k, core.point(q, "corner"), screen=project(q)))
            mid = core.mul(core.add(a, b), 0.5)
            out.append(core.Candidate("middle", core.point(mid, "edge middle"), screen=project(mid)))
            sa, sb = project(a), project(b)
            segs = [(sa, sb)] if sa is not None and sb is not None else []
            out.append(core.Candidate("edge", ln, segs=segs, world_segs=[(a, b)]))
        elif kind == wf.CIRCLE:
            cc, s = _pt(M, p1), _pt(M, p2)
            axw = tuple(_m3(M) @ Vector(p3))
            sweep = float(np.linalg.norm(p3))
            ci = core.circle(loc, cc, s, axw, sweep)
            ci.what = f"round edge Ø {core.fmt(2 * ci.r)}"
            out.append(core.Candidate("centre", core.point(cc, "centre of a round edge"), screen=project(cc)))
            pts = core.circle_points(cc, s, core.mul(core.unit(axw), sweep))
            if sweep < 2 * math.pi - 1e-3:
                for q in (pts[0], pts[-1]):
                    out.append(core.Candidate("corner", core.point(q, "corner"), screen=project(q)))
                m = pts[len(pts) // 2]
                out.append(core.Candidate("middle", core.point(m, "arc middle"), screen=project(m)))
            scr = [project(q) for q in pts]
            segs, wsegs = [], []
            for k in range(len(pts) - 1):
                if scr[k] is not None and scr[k + 1] is not None:
                    segs.append((scr[k], scr[k + 1]))
                    wsegs.append((pts[k], pts[k + 1]))
            out.append(core.Candidate("edge", ci, segs=segs, world_segs=wsegs))
    return out


def look(scene, depsgraph, origin, direction, mouse, project, kind: str = "SMART", picks: list | None = None,
         no_snap: bool = False, scale: float = 1.0) -> Look:
    """The work of one mouse move: what a click of measurement ``kind`` would take (its click number = len(picks))."""
    t0 = time.perf_counter()
    picks = picks or []
    lk = Look()
    hit = cast(scene, depsgraph, origin, direction)
    if hit is None:
        lk.ms = (time.perf_counter() - t0) * 1000.0
        return lk
    ob = hit.part
    face = -1
    if hit.polygon >= 0 and ob.type == "MESH" and ob.data is not None:
        d = data_of(ob.data)
        if d is not None and hit.polygon < len(d.face_of_poly):
            face = int(d.face_of_poly[hit.polygon])
    lk.part, lk.face = ob.name, face
    lk.cands = candidates(ob, face, hit.location, hit.normal, project, hit.cut)
    world = [p for _o, p in picks]
    offer = core.snap_kind(kind, len(picks), world)
    cand, at = core.choose(lk.cands, mouse, offer, scale, no_snap)
    if cand is None:
        cand = next((c for c in lk.cands if c.kind == "face"), None)
        at = None
    lk.cand = cand
    if cand is not None:
        pk = cand.pick
        if cand.kind == "edge" and at is not None:
            pk = core.Pick(**{**pk.__dict__, "p": tuple(at)})
        if core.wants(kind, len(picks), world) == "point" and pk.kind != "point":
            pk = core.point(pk.p, ("point on " if cand.kind == "edge" else "spot on ") + pk.what)
        lk.pick = pk
        lk.refused = core.refuse(kind, len(picks), world, pk)
        if cand.kind in ("corner", "middle", "centre") or pk.kind == "point":
            lk.draw_pts = [pk.p]
        if cand.kind == "edge" and cand.world_segs:
            lk.draw_line = [q for seg in cand.world_segs for q in seg]
        name = ob.get(build.PROP_NAME, ob.name)
        lk.text = lk.refused or f"{pk.what} – {name}"
    lk.ms = (time.perf_counter() - t0) * 1000.0
    return lk


# ---------------------------------------------------------------------------
# drawing (the 3D view only: never in a render)
# ---------------------------------------------------------------------------

_S: dict = {"handles": [], "tool": None, "rects": {}}
# tool: {"kind", "picks": [(part name, world Pick)], "look": Look, "mouse": (x, y) window, "area": pointer}


def tool_state() -> dict | None:
    return _S.get("tool")


def _lines(shader, pts, color, width):
    from gpu_extras.batch import batch_for_shader
    import gpu
    vp = gpu.state.viewport_get()
    shader.uniform_float("viewportSize", (vp[2], vp[3]))
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("color", color)
    batch_for_shader(shader, "LINES", {"pos": pts}).draw(shader)


def _dots(pts, color, size):
    from gpu_extras.batch import batch_for_shader
    import gpu
    flat = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.point_size_set(size)
    flat.uniform_float("color", color)
    batch_for_shader(flat, "POINTS", {"pos": pts}).draw(flat)


def drawn_lines(r: core.Result, units: str = "MM") -> list:
    """[(points in pairs, colour, width)] of a result: its line, a distance's X / Y / Z parts, an angle's arms."""
    out = []
    if r.corner is not None:
        out.append(([r.corner, r.arm_a, r.corner, r.arm_b], LINE, 2.5))
    elif r.frm is not None and r.to is not None and core.length(core.sub(r.to, r.frm)) > 1e-9:
        out.append(([r.frm, r.to], LINE, 2.5))
        if r.type == "points" and r.vec is not None:
            for prt in core.parts(r.frm, r.vec, units):
                out.append(([prt["from"], prt["to"]], AXES["XYZ".index(prt["axis"])], 1.5))
    return out


def _draw_view() -> None:
    try:
        context = bpy.context
        scene = context.scene
        st = getattr(scene, "fresing_measure", None)
        tool = _S.get("tool")
        if st is None or (not len(st.items) and tool is None):
            return
        import gpu
        line = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("NONE")
        if st.show:
            for item in st.items:
                if not item.show:
                    continue
                r = result(scene, item)
                if r is None:
                    continue
                for pts, col, w in drawn_lines(r, st.units):
                    _lines(line, pts, DARK, w + 2.0)
                    _lines(line, pts, (*col, 1.0), w)
                ends = [q for q in (r.frm, r.to) if q is not None] if r.corner is None else [r.corner, r.arm_a, r.arm_b]
                if ends:
                    _dots(ends, DARK, 9.0)
                    _dots(ends, (*LINE, 1.0), 6.0)
        if tool is not None:
            _draw_tool(tool, line)
        gpu.state.blend_set("NONE")
    except Exception:  # noqa: BLE001 - drawing must never break the view
        pass


def _draw_tool(tool, line) -> None:
    from . import hover
    lk = tool.get("look")
    picks = tool.get("picks", [])
    for _name, pk in picks:
        _dots([pk.p], DARK, 12.0)
        _dots([pk.p], (*PENDING, 1.0), 8.0)
    if lk is None or not lk.part:
        return
    col = hover.NO if lk.refused else PENDING
    ob = bpy.data.objects.get(lk.part)
    if ob is not None and lk.face >= 0 and ob.type == "MESH" and (lk.cand is None or lk.cand.kind == "face"):
        import gpu
        from gpu_extras.batch import batch_for_shader
        key = (ob.data.name, lk.face)
        hit = _S.get("batch")
        if hit is None or hit[0] != key:
            fill, outline = hover.face_shape(ob.data, lk.face)
            flat = gpu.shader.from_builtin("UNIFORM_COLOR")
            hit = (key, batch_for_shader(flat, "TRIS", {"pos": fill}), outline)
            _S["batch"] = hit
        gpu.matrix.push()
        gpu.matrix.multiply_matrix(ob.matrix_world)
        flat = gpu.shader.from_builtin("UNIFORM_COLOR")
        flat.uniform_float("color", (*col, 0.25))
        hit[1].draw(flat)
        if len(hit[2]):
            _lines(line, hit[2], (*col, 0.9), 1.5)
        gpu.matrix.pop()
    if lk.draw_line:
        _lines(line, lk.draw_line, DARK, 6.0)
        _lines(line, lk.draw_line, (*col, 1.0), 3.5)
    if lk.draw_pts:
        _dots(lk.draw_pts, DARK, 14.0)
        _dots(lk.draw_pts, (*col, 1.0), 9.0)
    # the value as it will be, before the last click
    prev = preview(tool)
    if prev is not None:
        for pts, c, w in drawn_lines(prev, settings().units):
            _lines(line, pts, (*PENDING, 0.9), w)


def preview(tool) -> core.Result | None:
    """The result the next click would give (the last click still to come), or None."""
    lk = tool.get("look")
    if lk is None or lk.pick is None or lk.refused:
        return None
    picks = [pk for _n, pk in tool.get("picks", [])] + [lk.pick]
    kind = tool.get("kind", "SMART")
    if len(picks) != core.needs(kind, picks):
        return None
    try:
        return core.measure(kind, picks, settings().units)
    except Exception:  # noqa: BLE001
        return None


def _brand():
    from ..core import brand
    return brand.hex_to_rgb(brand.DEFAULT_COLOR_1), brand.hex_to_rgb(brand.DEFAULT_COLOR_2, brand.DEFAULT_COLOR_2)


def labels(scene, region, rv3d) -> list:
    """[(index, lines, (x, y) px)] of the shown measurements' labels in this view (anchor = the line's middle)."""
    from bpy_extras import view3d_utils
    st = settings(scene)
    out = []
    if not st.show:
        return out
    for i, item in enumerate(st.items):
        if not item.show:
            continue
        r = result(scene, item)
        if r is None:
            continue
        at = core.anchor(r)
        if at is None:
            continue
        xy = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector(at))
        if xy is None:
            continue
        out.append((i, r.lines, (float(xy[0]), float(xy[1]))))
    return out


def _box(x, y, lines, scale, font, colours, alpha=0.88):
    import blf
    import gpu
    from gpu_extras.batch import batch_for_shader
    bg, fg = colours
    blf.size(font, 13 * scale)
    widths = [blf.dimensions(font, t)[0] for t in lines]
    lh = 17 * scale
    pad = 6 * scale
    w = max(widths) + 2 * pad
    h = lh * len(lines) + 2 * pad - 4 * scale
    x0, y0 = x, y
    box = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    flat = gpu.shader.from_builtin("UNIFORM_COLOR")
    flat.uniform_float("color", (*bg, alpha))
    batch_for_shader(flat, "TRI_FAN", {"pos": box}).draw(flat)
    blf.color(font, *fg, 1.0)
    for k, t in enumerate(lines):
        blf.position(font, x0 + pad, y0 + h - pad - (k + 1) * lh + 5 * scale, 0)
        blf.draw(font, t)
    return x0, y0, x0 + w, y0 + h


def place_labels(items: list, size_of, gap: float = 4.0) -> list:
    """Boxes that do not cover each other: each label starts right above its anchor and moves up until it is free.
    ``items`` [(key, (x, y))], ``size_of(key) -> (w, h)``; returns [(key, (x0, y0, x1, y1))]."""
    placed = []
    for key, (x, y) in items:
        w, h = size_of(key)
        x0, y0 = x - w / 2.0, y + 10.0
        for _k in range(30):
            if not any(not (x0 + w <= a0 or a1 <= x0 or y0 + h <= b0 or b1 <= y0) for _kk, (a0, b0, a1, b1) in placed):
                break
            y0 += h / 2.0 + gap
        placed.append((key, (x0, y0, x0 + w, y0 + h)))
    return placed


def _draw_text() -> None:
    try:
        context = bpy.context
        scene = context.scene
        st = getattr(scene, "fresing_measure", None)
        tool = _S.get("tool")
        region, rv3d = context.region, context.region_data
        if st is None or region is None or rv3d is None or (not len(st.items) and tool is None):
            return
        import blf
        import gpu
        font = 0
        scale = (context.preferences.system.ui_scale or 1.0) * st.label_size
        colours = _brand()
        gpu.state.blend_set("ALPHA")
        got = labels(scene, region, rv3d)
        text = {i: lines for i, lines, _xy in got}

        def size_of(i):
            blf.size(font, 13 * scale)
            w = max(blf.dimensions(font, t)[0] for t in text[i]) + 12 * scale
            return w, 17 * scale * len(text[i]) + 8 * scale

        rects = []
        for i, (x0, y0, _x1, _y1) in place_labels([(i, xy) for i, _l, xy in got], size_of):
            rects.append((*_box(x0, y0, text[i], scale, font, colours), i))
        _S["rects"][context.area.as_pointer() if context.area else 0] = (region.x, region.y, rects)
        if tool is not None and tool.get("area") == (context.area.as_pointer() if context.area else 0):
            lk = tool.get("look")
            mouse = tool.get("mouse")
            if mouse is not None:
                lines = []
                prev = preview(tool)
                if prev is not None:
                    lines += prev.lines
                if lk is not None:
                    lines.append(lk.text)
                head = tool.get("prompt", "")
                if head:
                    lines.append(head)
                x = mouse[0] - region.x + 18 * scale
                y = mouse[1] - region.y - 30 * scale - 17 * scale * len(lines)
                from . import hover
                bad = lk is not None and bool(lk.refused)
                _box(x, y, lines, scale, font, ((0.05, 0.05, 0.05), hover.NO if bad else (1.0, 1.0, 1.0)), 0.85)
        gpu.state.blend_set("NONE")
    except Exception:  # noqa: BLE001
        pass


def label_at(area_pointer: int, x: float, y: float) -> int:
    """The measurement whose label is under the window point (x, y) in that 3D view, or -1."""
    got = _S["rects"].get(area_pointer)
    if not got:
        return -1
    rx, ry, rects = got
    lx, ly = x - rx, y - ry
    for x0, y0, x1, y1, i in reversed(rects):
        if x0 <= lx <= x1 and y0 <= ly <= y1:
            return i
    return -1


def _add_handlers() -> None:
    if _S["handles"]:
        return
    sp = bpy.types.SpaceView3D
    _S["handles"] = [sp.draw_handler_add(_draw_view, (), "WINDOW", "POST_VIEW"),
                     sp.draw_handler_add(_draw_text, (), "WINDOW", "POST_PIXEL")]


def _remove_handlers() -> None:
    for i, hnd in enumerate(_S["handles"]):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(hnd, "WINDOW")
        except Exception:  # noqa: BLE001
            pass
    _S["handles"] = []


# ---------------------------------------------------------------------------
# the tool's state (the modal operator in ops_measure.py drives it)
# ---------------------------------------------------------------------------

def tool_start(kind: str, area_pointer: int) -> dict:
    _S["tool"] = {"kind": kind, "picks": [], "look": None, "mouse": None, "area": area_pointer, "prompt": ""}
    _S.pop("batch", None)
    _redraw_views()
    return _S["tool"]


def tool_end() -> None:
    _S["tool"] = None
    _S.pop("batch", None)
    _redraw_views()


def prompt_for(kind: str, picks: list) -> str:
    n = core.needs(kind, picks)
    w = core.wants(kind, len(picks), picks)
    what = {"point": "a point", "edge": "an edge", "flat": "a flat face", "round": "a round face or a round edge",
            "axis": "a hole, a shaft or an edge", "face_or_edge": "a face or an edge",
            "any": "a face, an edge or a point"}.get(w, "")
    return f"{core.TITLES[kind]} – click {len(picks) + 1} of {n}: {what} · Shift: no snap · Esc: done"


# ---------------------------------------------------------------------------
# in renders: real objects while "Show in renders" is ticked
# ---------------------------------------------------------------------------

def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _material(name, colour):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        em = nt.nodes.new("ShaderNodeEmission")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(em.outputs[0], out.inputs[0])
        em.inputs["Strength"].default_value = 1.0
    em = next((n for n in mat.node_tree.nodes if n.type == "EMISSION"), None)
    if em is not None:
        em.inputs["Color"].default_value = (*colour, 1.0)
    mat[KIND] = 1
    return mat


def _remove_render_objects() -> None:
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        return
    for ob in list(col.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
            elif isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
    if not col.objects and not col.children:
        bpy.data.collections.remove(col)


def _plate(name, tob, mat):
    """A dark box behind a label (a child of the text, so it faces the camera with it)."""
    lo = [min(v[i] for v in tob.bound_box) for i in range(3)]
    hi = [max(v[i] for v in tob.bound_box) for i in range(3)]
    m = 0.35 * tob.data.size
    x0, x1, y0, y1 = lo[0] - m, hi[0] + m, lo[1] - m, hi[1] + m
    z = -0.02 * tob.data.size
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    me.from_pydata([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [], [(0, 1, 2, 3)])
    if not me.materials:
        me.materials.append(mat)
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, me)
    ob.data = me
    ob.parent = tob
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.location = (0.0, 0.0, 0.0)
    ob[build.PROP_KIND] = KIND
    ob.hide_select = True
    return ob


def render_objects(scene) -> int:
    """Make (or take away) the measurements' render objects: one thin tube for the lines and one label per
    measurement – white text on a dark box, facing the scene's camera, moved apart on the picture as the view's
    labels are (``place_labels``). Returns how many labels were made."""
    from bpy_extras.object_utils import world_to_camera_view
    st = settings(scene)
    if not st.in_renders or not st.show or not len(st.items):
        _remove_render_objects()
        return 0
    col = _collection(scene)
    bg, fg = _brand()
    lines_mat = _material("FR measure line", LINE)
    text_mat = _material("FR measure text", fg)
    box_mat = _material("FR measure box", bg)
    cam = scene.camera
    keep = set()
    segs, texts = [], []
    for i, item in enumerate(st.items):
        if not item.show:
            continue
        r = result(scene, item)
        if r is None:
            continue
        for pts, _c, _w in drawn_lines(r, st.units)[:1]:
            segs += [(pts[k], pts[k + 1]) for k in range(0, len(pts) - 1, 2)]
        at = core.anchor(r)
        if at is not None:
            texts.append((i, r.lines[0], at))
    eye = cam.matrix_world.translation if cam is not None else None
    up = (cam.matrix_world.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized() if cam is not None else Vector((0, 0, 1))

    def far(p):
        return (Vector(p) - eye).length if eye is not None else 5.0

    fwd = (cam.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized() if cam is not None else None
    ortho = cam is not None and cam.data.type == "ORTHO"

    def pull(p):
        """A point moved towards the camera to PULL of its distance: the same spot on the picture, but in front of
        the model (so the model never hides a label or a line, as the view draws them on top)."""
        p = Vector(p)
        if cam is None:
            return p
        depth = (p - eye).dot(fwd)
        if depth <= 0:
            return p
        k = min(1.0, max(PULL, 3.0 * cam.data.clip_start / depth))   # never closer than 3 x the clip start
        if ortho:
            return p - fwd * (depth * (1.0 - k))
        return eye + (p - eye) * k

    # the lines: one curve object of straight pieces, as thick as ~1.5 px of a 1000 px picture
    name = "FR measure lines"
    cu = bpy.data.curves.get(name) or bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.splines.clear()
    segs = [(tuple(pull(a)), tuple(pull(b))) for a, b in segs]
    texts = [(i, txt, tuple(pull(at))) for i, txt, at in texts]
    cu.bevel_depth = max(0.0001, 0.0008 * min((far(a) for a, _b in segs), default=5.0))
    cu.bevel_resolution = 2
    for a, b in segs:
        sp = cu.splines.new("POLY")
        sp.points.add(1)
        sp.points[0].co = (*a, 1.0)
        sp.points[1].co = (*b, 1.0)
    if not cu.materials:
        cu.materials.append(lines_mat)
    tube = bpy.data.objects.get(name) or bpy.data.objects.new(name, cu)
    if tube.name not in col.objects:
        col.objects.link(tube)
    tube.data = cu
    tube[build.PROP_KIND] = KIND
    tube.hide_select = True
    keep.add(tube.name)
    made = []
    for i, txt, at in texts:
        tname = f"FR measure {i + 1:03d}"
        tc = bpy.data.curves.get(tname) or bpy.data.curves.new(tname, "FONT")
        tc.body = txt
        tc.align_x, tc.align_y = "CENTER", "BOTTOM"
        tc.size = max(0.001, far(at) * 0.016)
        tc.extrude = 0.0
        if not tc.materials:
            tc.materials.append(text_mat)
        tob = bpy.data.objects.get(tname) or bpy.data.objects.new(tname, tc)
        if tob.name not in col.objects:
            col.objects.link(tob)
        tob.data = tc
        tob[build.PROP_KIND] = KIND
        tob.hide_select = True
        tob.location = Vector(at)
        con = tob.constraints.get("FR face camera")
        if cam is not None:
            if con is None:
                con = tob.constraints.new("TRACK_TO")
                con.name = "FR face camera"
                con.track_axis, con.up_axis = "TRACK_Z", "UP_Y"
            con.target = cam
        elif con is not None:
            tob.constraints.remove(con)
        keep.add(tob.name)
        made.append((i, tob, at))
    if made:
        bpy.context.view_layer.update()
        for i, tob, _at in made:
            plate = _plate(f"FR measure box {i + 1:03d}", tob, box_mat)
            if plate.name not in col.objects:
                col.objects.link(plate)
            keep.add(plate.name)
    if made and cam is not None:                     # move the labels apart on the picture
        res = (scene.render.resolution_x, scene.render.resolution_y)
        info = {}
        for i, tob, at in made:
            a = world_to_camera_view(scene, cam, Vector(at))
            b = world_to_camera_view(scene, cam, Vector(at) + up * 0.1)
            ppm = max(1e-6, (b.y - a.y) * res[1] / 0.1)
            lo = [min(v[k] for v in tob.bound_box) for k in range(2)]
            hi = [max(v[k] for v in tob.bound_box) for k in range(2)]
            m = 0.7 * tob.data.size
            info[i] = (a.x * res[0], a.y * res[1], ppm, (hi[0] - lo[0] + m) * ppm, (hi[1] - lo[1] + m) * ppm, tob, at)
        placed = place_labels([(i, (v[0], v[1])) for i, v in info.items()], lambda i: (info[i][3], info[i][4]))
        for i, (_x0, y0, _x1, _y1) in placed:
            x, y, ppm, _w, _h, tob, at = info[i]
            tob.location = Vector(at) + up * ((y0 - y) / ppm)
    for ob in list(col.objects):
        if ob.name not in keep:
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and data.users == 0:
                if isinstance(data, bpy.types.Curve):
                    bpy.data.curves.remove(data)
                elif isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
    return len(made)


@persistent
def _frame_changed(scene, *_args):
    st = getattr(scene, "fresing_measure", None)
    if st is not None and st.in_renders and len(st.items):
        try:
            render_objects(scene)
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: measurements for renders not updated:", exc)


# ---------------------------------------------------------------------------
# saving: Keep measurements, the Client view
# ---------------------------------------------------------------------------

_STASH: dict = {}


def _snapshot(item) -> dict:
    return {"name": item.name, "kind": item.kind, "show": item.show,
            "picks": [(p.part, p.kind, list(p.v), p.what) for p in item.picks]}


def _restore(scene, snaps: list) -> None:
    st = settings(scene)
    for s in snaps:
        item = st.items.add()
        item.name, item.kind, item.show = s["name"], s["kind"], s["show"]
        for ob, kind, v, what in s["picks"]:
            p = item.picks.add()
            p.part, p.kind, p.v, p.what = ob, kind, v, what


def leave_out_of_save(scene) -> bool:
    """Are the measurements left out of the file at a save? Keep measurements off, or the Client view."""
    st = settings(scene)
    if not st.keep:
        return True
    try:
        from . import workspaces
        return bool(workspaces.locked(scene))
    except Exception:  # noqa: BLE001
        return False


@persistent
def _before_save(*_args):
    _STASH.clear()
    for scene in bpy.data.scenes:
        st = getattr(scene, "fresing_measure", None)
        if st is None or not len(st.items) or not leave_out_of_save(scene):
            continue
        _STASH[scene.name] = [_snapshot(it) for it in st.items]
        st.items.clear()
        if st.in_renders:
            _remove_render_objects()


@persistent
def _after_save(*_args):
    for name, snaps in list(_STASH.items()):
        scene = bpy.data.scenes.get(name)
        if scene is not None:
            _restore(scene, snaps)
            after_change(scene)
    _STASH.clear()


@persistent
def _after_load(*_args):
    forget()
    _S["tool"] = None
    _S["rects"] = {}
    _S.pop("batch", None)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.fresing_measure = PointerProperty(type=FRMeasureSettings)
    for lst, fn in ((bpy.app.handlers.save_pre, _before_save), (bpy.app.handlers.save_post, _after_save),
                    (bpy.app.handlers.load_post, _after_load), (bpy.app.handlers.frame_change_post, _frame_changed)):
        if fn not in lst:
            lst.append(fn)
    if not bpy.app.background:
        _add_handlers()


def unregister():
    _remove_handlers()
    for lst, fn in ((bpy.app.handlers.save_pre, _before_save), (bpy.app.handlers.save_post, _after_save),
                    (bpy.app.handlers.load_post, _after_load), (bpy.app.handlers.frame_change_post, _frame_changed)):
        while fn in lst:
            lst.remove(fn)
    if hasattr(bpy.types.Scene, "fresing_measure"):
        del bpy.types.Scene.fresing_measure
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# the test crane's known sizes (the test tour's "Measure" set and the PC check's view.measure)
# ---------------------------------------------------------------------------

KNOWN = {"thickness": 0.5, "bolts": 4.5, "cut_to_back": 1.5, "hole": 0.033}   # m: tools/make_test_crane.py's base
_PX = 200.0                                         # px per metre of the straight-down views the set-up "clicks" in


def _click(scene, x, y, kind, picks, up=False, side=None):
    """A click of the set-up: the mouse at (x, y) m in a view straight down (``up``: straight up from under the
    crane; ``side`` = (origin, direction) of a ray from the side)."""
    dg = bpy.context.evaluated_depsgraph_get()
    if side is not None:
        o, d = Vector(side[0]), Vector(side[1])
        proj = None
    else:
        o, d = (Vector((x, y, -2.0)), Vector((0, 0, 1))) if up else (Vector((x, y, 12.0)), Vector((0, 0, -1)))
        proj = (lambda p: (p[0] * _PX, p[1] * _PX))
    lk = look(scene, dg, o, d, (x * _PX, y * _PX), proj or (lambda p: None), kind, picks)
    if lk.pick is None or lk.refused:
        raise RuntimeError(f"the {core.TITLES[kind]} click at ({x:.3f}, {y:.3f}) took nothing: {lk.text}")
    return lk


def set_up_test(scene, with_slice: bool = True) -> dict:
    """On the test crane: a slice through the base (its front half goes) and four measurements of known sizes –
    the base's thickness (Face to face 500 mm), two bolt holes' centres (Distance 4500 mm, snapped from below), the
    cut face to the base's back face (Face to face 1500 mm) and a bolt hole's rim (Radius Ø33 mm). Returns
    {name: measurement item}."""
    from . import section
    base = next(o for o in scene.objects if o.get(build.PROP_NAME) == "BASE")
    st = settings(scene)
    out = {}

    def keep(name, kind, looks):
        out[name] = add(scene, kind, [(bpy.data.objects[lk.part], to_local(bpy.data.objects[lk.part], lk.pick))
                                      for lk in looks])
        out[name].name = name

    a = _click(scene, 1.0, 2.2, "FACES", [])
    b = _click(scene, 1.0, 2.2, "FACES", [(a.part, a.pick)], up=True)
    keep("Base thickness", "FACES", [a, b])
    a = _click(scene, 0.25 + 0.02, 2.75, "DISTANCE", [], up=True)
    b = _click(scene, 4.75 + 0.02, 2.75, "DISTANCE", [(a.part, a.pick)], up=True)
    keep("Bolt holes", "DISTANCE", [a, b])
    a = _click(scene, 4.75 + 0.019, 2.75, "RADIUS", [], up=True)
    keep("Bolt hole", "RADIUS", [a])
    if with_slice:
        cut = section.add(scene, [("PART", base, "")], "PLANE", name="Measure slice")
        section.set_world(scene, cut, Matrix.Translation((2.5, 1.5, 0.25))
                          @ Matrix.Rotation(math.pi / 2, 4, "X"))
        bpy.context.view_layer.update()
        a = _click(scene, 2.3, 0.0, "FACES", [], side=((2.3, -6.0, 0.25), (0.0, 1.0, 0.0)))
        b = _click(scene, 2.3, 0.0, "FACES", [(a.part, a.pick)], side=((2.3, 9.0, 0.25), (0.0, -1.0, 0.0)))
        if not a.text.startswith("cut face"):
            raise RuntimeError(f"the click through the slice took '{a.text}', not its cut face")
        keep("Cut face to the back", "FACES", [a, b])
    st.units = "MM"
    return out


def check_test(scene) -> list:
    """[(name, measured m, known m)] of ``set_up_test``'s measurements (as the view shows them now)."""
    want = {"Base thickness": KNOWN["thickness"], "Bolt holes": KNOWN["bolts"], "Bolt hole": KNOWN["hole"],
            "Cut face to the back": KNOWN["cut_to_back"]}
    out = []
    for item in settings(scene).items:
        if item.name in want:
            r = result(scene, item)
            out.append((item.name, None if r is None else r.dist, want[item.name]))
    return out
