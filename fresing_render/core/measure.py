"""Measuring in the 3D view (task 0322): the numbers, the words and the snapping choice. No Blender here.

The app's Measure (top bar > Measure, the key M / Alt+M) works like the 3D page's measure tool (task 0135 / 0219,
``fresing_render/web/fr_measure.js``): the same picks, the same pairs and the same words, so a part measures the same
in the app and on the page. ``measure(PAGE, a, b)`` is exactly the page's ``measure(a, b, 'faces')``.

A **pick** (``Pick``) is what one click took, in world coordinates (metres):

* ``point`` – a point (a corner, an edge's middle, a face's or a hole's centre, or a spot on a face with Shift held);
* ``flat``  – a flat CAD face: the clicked point ``p`` and its normal ``n`` (unit, pointing out of the part);
* ``round`` – a cylinder: a point ``o`` on its axis, the axis ``d`` (unit) and its radius ``r``;
* ``axis``  – a round face without one radius (a cone, a rounding): ``o``, ``d``, ``r`` = 0;
* ``line``  – a straight CAD edge: its ends ``a`` and ``b`` (``o`` = a, ``d`` unit);
* ``circle`` – a round CAD edge (a hole's rim): centre ``o`` (= ``c``), axis ``d``, radius ``r``, where the arc starts
  ``s`` and its angle ``sweep`` (radians; 2π: a whole circle).

A **measurement kind** says what the clicks are for (``KINDS``):

* ``SMART``    – two clicks, the result by what was clicked (the page's "Faces" mode);
* ``DISTANCE`` – point to point, with its X / Y / Z parts;
* ``EDGE``     – one click on an edge: its length (a round edge: its Ø and the length of the arc);
* ``FACES``    – two flat faces: the gap between them (parallel) or the angle;
* ``ANGLE``    – two faces / edges / axes (the angle between them), or three points (the angle at the middle one);
* ``RADIUS``   – one click on a round face or a round edge: Ø and radius;
* ``AXIS``     – a point and an axis (a hole, a shaft, a round edge, a straight edge): the distance square to it.

Snapping (``choose``): what a click takes is the nearest of the hovered face's corners, edge middles, face / hole
centres within ``SNAP_PX`` pixels of the mouse; else the nearest edge within ``EDGE_PX``; else the face itself. Shift
takes the spot under the mouse as it is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

PARALLEL_DEG = 1.0                  # as the page: two faces / axes within 1° count as parallel
SNAP_PX = 14                        # a corner, middle or centre this close to the mouse (px at UI scale 1) is taken
EDGE_PX = 9                         # an edge this close is taken (after the points)
PAGE = "SMART"

KINDS = ("SMART", "DISTANCE", "EDGE", "FACES", "ANGLE", "RADIUS", "AXIS")
TITLES = {
    "SMART": "Measure",
    "DISTANCE": "Distance",
    "EDGE": "Edge length",
    "FACES": "Face to face",
    "ANGLE": "Angle",
    "RADIUS": "Radius / diameter",
    "AXIS": "Point to axis",
}
HELP = {
    "SMART": "Click two faces, edges or points: the result goes by what you clicked (as the 3D page's measure tool)",
    "DISTANCE": "Click two points: the straight distance and its X / Y / Z parts",
    "EDGE": "Click an edge: its length (a round edge: its Ø and the arc's length)",
    "FACES": "Click two flat faces: the gap between them (or their angle when they are not parallel)",
    "ANGLE": "Click two faces or edges – or three points, the corner in the middle: the angle",
    "RADIUS": "Click a round face or a round edge: its Ø and radius",
    "AXIS": "Click a point and a hole, shaft or edge: the distance square to its axis",
}
ICONS = {"SMART": "DRIVER_DISTANCE", "DISTANCE": "DRIVER_DISTANCE", "EDGE": "EDGESEL", "FACES": "FACESEL",
         "ANGLE": "DRIVER_ROTATIONAL_DIFFERENCE", "RADIUS": "MESH_CIRCLE", "AXIS": "EMPTY_SINGLE_ARROW"}
UNITS = ("MM", "M", "INCH")
UNIT_WORDS = {"MM": "mm", "M": "m", "INCH": "in"}
_DECIMALS = {"MM": 2, "M": 4, "INCH": 3}
_PER_M = {"MM": 1000.0, "M": 1.0, "INCH": 1000.0 / 25.4}


# ---------------------------------------------------------------------------
# small vector maths on 3-tuples
# ---------------------------------------------------------------------------

def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = length(a) or 1.0
    return mul(a, 1.0 / n)


def deg(rad):
    return rad * 180.0 / math.pi


def line_angle(u, v) -> float:
    """The angle between two directions taken as lines (0 … 90°)."""
    return deg(math.acos(min(1.0, abs(dot(unit(u), unit(v))))))


def on_line(p, o, d):
    """The foot of ``p`` on the line through ``o`` along the unit ``d``."""
    return add(o, mul(d, dot(sub(p, o), d)))


def on_plane(p, q, n):
    """The foot of ``p`` on the plane through ``q`` with the unit normal ``n``."""
    return sub(p, mul(n, dot(sub(p, q), n)))


def _t(v):
    return tuple(float(x) for x in v)


# ---------------------------------------------------------------------------
# picks and results
# ---------------------------------------------------------------------------

@dataclass
class Pick:
    kind: str = "point"                       # point | flat | round | axis | line | circle
    p: tuple = (0.0, 0.0, 0.0)                # the clicked (or snapped) point
    n: tuple = (0.0, 0.0, 1.0)                # flat: normal
    o: tuple = (0.0, 0.0, 0.0)                # round / axis / line / circle: a point on the axis (circle: centre)
    d: tuple = (0.0, 0.0, 1.0)                # … its unit direction
    r: float = 0.0                            # round / circle: radius
    a: tuple = (0.0, 0.0, 0.0)                # line: its ends
    b: tuple = (0.0, 0.0, 0.0)
    s: tuple = (0.0, 0.0, 0.0)                # circle: where the arc starts
    sweep: float = 0.0                        # circle: the arc's angle (2π: whole)
    what: str = ""                            # the words for it ("corner", "Ø 33.00 mm hole" …)

    @property
    def length(self) -> float:
        return length(sub(self.b, self.a)) if self.kind == "line" else 0.0

    def is_round(self) -> bool:
        return self.kind in ("round", "axis")

    def is_line(self) -> bool:
        return self.is_round() or self.kind == "line"

    def is_axis_like(self) -> bool:
        return self.is_line() or self.kind == "circle"

    def is_face(self) -> bool:
        return self.kind in ("flat", "round", "axis")

    def is_edge(self) -> bool:
        return self.kind in ("line", "circle")


def point(p, what: str = "point") -> Pick:
    return Pick("point", p=_t(p), what=what)


def flat(p, n, what: str = "flat face") -> Pick:
    return Pick("flat", p=_t(p), n=unit(_t(n)), what=what)


def round_face(p, o, d, r: float, what: str = "") -> Pick:
    o, d = _t(o), unit(_t(d))
    return Pick("round" if r > 0 else "axis", p=_t(p), o=o, d=d, r=float(r), what=what or "round face")


def line(p, a, b, what: str = "edge") -> Pick:
    a, b = _t(a), _t(b)
    return Pick("line", p=_t(p), o=a, d=unit(sub(b, a)), a=a, b=b, what=what)


def circle(p, c, s, axis, sweep: float, what: str = "round edge") -> Pick:
    c, s = _t(c), _t(s)
    return Pick("circle", p=_t(p), o=c, d=unit(_t(axis)), r=length(sub(s, c)), s=s, sweep=float(sweep), what=what)


@dataclass
class Result:
    type: str                                  # "points", "planes", "angle", "axes", "edge", "diameter" …
    lines: list                                # the label's lines, in the unit asked for
    dist: float | None = None                  # metres: the main length (None: an angle or no number)
    angle: float | None = None                 # degrees: the main angle when the result is an angle
    frm: tuple | None = None                   # the line drawn: its ends (world)
    to: tuple | None = None
    vec: tuple | None = None                   # to - frm: its X / Y / Z parts
    corner: tuple | None = None                # an angle's corner (three points), its arms' ends in arm_a / arm_b
    arm_a: tuple | None = None
    arm_b: tuple | None = None
    main_is_angle: bool = False
    extra: dict = field(default_factory=dict)

    def value_text(self, units: str = "MM") -> str:
        """The value a click on Copy puts on the clipboard: the number in the unit asked for (no thousands spaces)."""
        if self.main_is_angle and self.angle is not None:
            return f"{self.angle:.2f}°"
        if self.dist is None:
            return ""
        return f"{self.dist * _PER_M[units]:.{_DECIMALS[units]}f} {UNIT_WORDS[units]}"


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------

def fmt(m: float, units: str = "MM") -> str:
    """A length in the unit asked for: '500.00 mm', '0.5000 m', '19.685 in'; thin spaces between thousands."""
    v = m * _PER_M.get(units, 1000.0)
    dec = _DECIMALS.get(units, 2)
    a = abs(v)
    s = f"{a:,.{dec}f}".replace(",", " ")
    neg = v < 0 and round(a, dec) > 0
    return ("−" if neg else "") + s + " " + UNIT_WORDS.get(units, "mm")


def angle_text(a: float) -> str:
    return f"{a:.2f}°"


def parts(frm, vec, units: str = "MM") -> list:
    """The X / Y / Z parts of a vector as three steps one after the other (a staircase from ``frm``): dicts with
    axis, from, to, value (m) and text. A part smaller than 1e-7 m is left out (as the page)."""
    out, at = [], _t(frm)
    for i, name in enumerate("XYZ"):
        if abs(vec[i]) < 1e-7:
            continue
        to = list(at)
        to[i] += vec[i]
        to = tuple(to)
        out.append({"axis": name, "from": at, "to": to, "value": float(vec[i]), "text": f"{name} {fmt(vec[i], units)}"})
        at = to
    return out


def parts_line(vec, units: str = "MM") -> str:
    """'X 10.00 · Y −2.50 · Z 0.00 mm': the three parts on one line (the label's second line)."""
    w = UNIT_WORDS.get(units, "mm")
    nums = []
    for i, name in enumerate("XYZ"):
        t = fmt(vec[i], units)
        nums.append(f"{name} {t[:-len(w) - 1]}")
    return " · ".join(nums) + f" {w}"


# ---------------------------------------------------------------------------
# the page's pairs (fr_measure.js), in Python
# ---------------------------------------------------------------------------

def _points(a: Pick, b: Pick, u: str) -> Result:
    v = sub(b.p, a.p)
    return Result("points", [f"Distance {fmt(length(v), u)}"], dist=length(v), frm=a.p, to=b.p, vec=v)


def _planes(a: Pick, b: Pick, u: str) -> Result:
    ang = line_angle(a.n, b.n)
    if ang <= PARALLEL_DEG:
        n = mul(b.n, -1.0) if dot(a.n, b.n) < 0 else b.n
        nm = unit(add(a.n, n))
        foot = on_plane(b.p, a.p, nm)
        v = sub(b.p, foot)
        dist = abs(dot(sub(b.p, a.p), nm))
        return Result("planes", [f"Between the planes {fmt(dist, u)}",
                                 f"(parallel within {angle_text(ang)})" if ang > 0.05 else "parallel"],
                      dist=dist, angle=ang, frm=foot, to=b.p, vec=v)
    p = _points(a, b, u)
    return Result("angle", [f"Angle between the planes {angle_text(ang)}",
                            f"Not parallel; points {fmt(p.dist, u)} apart"],
                  dist=p.dist, angle=ang, frm=a.p, to=b.p, vec=p.vec, main_is_angle=True)


def _axes(a: Pick, b: Pick, u: str) -> Result:
    ang = line_angle(a.d, b.d)
    ea, eb = a.kind == "line", b.kind == "line"
    what = "Edge to edge " if ea and eb else "Edge to centre " if ea or eb else "Centre to centre "
    them = "edges" if ea and eb else "edge and the axis" if ea or eb else "axes"
    typ = "edges" if ea or eb else "axes"
    if ang <= PARALLEL_DEG:
        c1 = on_line(a.p, a.o, a.d)
        c2 = on_line(c1, b.o, b.d)
        v = sub(c2, c1)
        dist = length(v)
        lines = [what + fmt(0.0, u), "On one line" if ea and eb else "On one axis"] if dist < 1e-6 \
            else [what + fmt(dist, u)]
        if ang > 0.05:
            lines.append(f"({them} parallel within {angle_text(ang)})")
        return Result(typ, lines, dist=dist, angle=ang, frm=c1, to=c2, vec=v)
    w = cross(a.d, b.d)
    wl = length(w)
    r = sub(b.o, a.o)
    t1 = dot(cross(r, b.d), w) / (wl * wl)
    t2 = dot(cross(r, a.d), w) / (wl * wl)
    c1 = add(a.o, mul(a.d, t1))
    c2 = add(b.o, mul(b.d, t2))
    v2 = sub(c2, c1)
    d2 = length(v2)
    return Result(typ, [f"The {them} cross" if d2 < 1e-6 else f"Shortest between the {them} {fmt(d2, u)}",
                        f"Angle between the {them} {angle_text(ang)}"], dist=d2, angle=ang, frm=c1, to=c2, vec=v2)


def _face_axis(f: Pick, r: Pick, u: str) -> Result:
    s = abs(dot(f.n, r.d))
    edge = r.kind == "line"
    it = "edge" if edge else "axis"
    typ = "face-edge" if edge else "face-axis"
    ang = deg(math.asin(min(1.0, s)))
    if ang <= PARALLEL_DEG:
        c = on_line(r.p, r.o, r.d)
        foot = on_plane(c, f.p, f.n)
        v = sub(c, foot)
        dist = abs(dot(sub(c, f.p), f.n))
        lines = [("Face to edge " if edge else "Face to centre ") + fmt(dist, u)]
        if ang > 0.05:
            lines.append(f"({it} along the face within {angle_text(ang)})")
        return Result(typ, lines, dist=dist, angle=ang, frm=foot, to=c, vec=v)
    t = dot(sub(f.p, r.o), f.n) / dot(r.d, f.n)
    x = add(r.o, mul(r.d, t))
    v2 = sub(x, f.p)
    return Result(typ, [f"The {it} meets the face at {angle_text(ang)}", f"Click to crossing {fmt(length(v2), u)}"],
                  dist=0.0, angle=ang, frm=f.p, to=x, vec=v2, main_is_angle=True)


def _from_circle(c: Pick, o: Pick, u: str) -> Result:
    at = c.o
    if o.kind == "circle":
        v = sub(o.o, at)
        d = length(v)
        lines = [f"Centre to centre {fmt(d, u)}"]
        if line_angle(c.d, o.d) <= PARALLEL_DEG and d > 1e-9:
            along = abs(dot(v, c.d))
            across = math.sqrt(max(0.0, d * d - along * along))
            if along > 1e-6 and across > 1e-6:
                lines.append(f"Across the axes {fmt(across, u)} · along {fmt(along, u)}")
            elif along <= 1e-6:
                lines.append("In one plane")
            else:
                lines.append("On one axis")
        return Result("circles", lines, dist=d, frm=at, to=o.o, vec=v)
    if o.kind == "flat":
        to, what = on_plane(at, o.p, o.n), "Centre to face "
    elif o.is_line():
        to, what = on_line(at, o.o, o.d), "Centre to edge " if o.kind == "line" else "Centre to axis "
    else:
        to, what = o.p, "Centre to point "
    w = sub(to, at)
    dist = length(w)
    lines = [what + fmt(dist, u)]
    if o.is_line() and line_angle(c.d, o.d) > PARALLEL_DEG:
        lines.append(f"Angle between the axes {angle_text(line_angle(c.d, o.d))}")
    kind = "axis" if o.is_round() else "edge" if o.kind == "line" else "face" if o.kind == "flat" else "point"
    return Result("circle-" + kind, lines, dist=dist, frm=at, to=to, vec=w)


def _point_line(pt: Pick, ln: Pick, u: str) -> Result:
    f = on_line(pt.p, ln.o, ln.d)
    v = sub(pt.p, f)
    return Result("point-edge", [f"Point to edge {fmt(length(v), u)}"], dist=length(v), frm=f, to=pt.p, vec=v)


def _flip(r: Result) -> Result:
    r.frm, r.to = r.to, r.frm
    if r.vec is not None:
        r.vec = mul(r.vec, -1.0)
    return r


def pair(a: Pick, b: Pick, u: str = "MM") -> Result:
    """The page's ``measure(a, b, 'faces')``: the result by what was clicked."""
    if a.kind == "circle":
        return _from_circle(a, b, u)
    if b.kind == "circle":
        return _flip(_from_circle(b, a, u))
    if a.kind == "flat" and b.kind == "flat":
        return _planes(a, b, u)
    if a.is_line() and b.is_line():
        return _axes(a, b, u)
    if a.kind == "flat" and b.is_line():
        return _face_axis(a, b, u)
    if a.is_line() and b.kind == "flat":
        return _flip(_face_axis(b, a, u))
    if a.kind == "line":
        return _flip(_point_line(b, a, u))
    if b.kind == "line":
        return _point_line(a, b, u)
    return _points(a, b, u)


def single(a: Pick, u: str = "MM") -> Result:
    """One click: what the face or edge itself says (the page's ``single``)."""
    if a.kind == "round" and a.r > 0:
        return Result("diameter", [f"Ø {fmt(2 * a.r, u)}  (radius {fmt(a.r, u)})"], dist=2 * a.r,
                      frm=add(a.o, mul(_perp(a.d), -a.r)), to=add(a.o, mul(_perp(a.d), a.r)),
                      extra={"radius": a.r})
    if a.kind == "axis":
        return Result("axis", ["Round face (no single diameter: a cone or a rounded edge)"])
    if a.kind == "flat":
        return Result("flat", ["Flat face"])
    if a.kind == "line":
        return Result("edge", [f"Edge {fmt(a.length, u)}"], dist=a.length, frm=a.a, to=a.b, vec=sub(a.b, a.a))
    if a.kind == "circle":
        whole = a.sweep >= 2 * math.pi - 1e-3
        lines = [f"Ø {fmt(2 * a.r, u)}  (radius {fmt(a.r, u)})"]
        lines.append("Round edge (a whole circle)" if whole else
                     f"Round edge, an arc of {angle_text(deg(a.sweep))}, {fmt(a.r * a.sweep, u)} long")
        return Result("diameter", lines, dist=2 * a.r, frm=sub(a.o, sub(a.s, a.o)), to=a.s,
                      extra={"radius": a.r, "arc": a.r * a.sweep})
    return Result("point", ["Point"])


def _perp(d):
    """A unit direction square to ``d`` (where a diameter line is drawn)."""
    t = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
    return unit(cross(d, t))


def _dir_of(p: Pick):
    """The direction an angle uses: a flat face's normal, an axis or an edge's direction; None for a point."""
    if p.kind == "flat":
        return p.n
    if p.is_axis_like():
        return p.d
    return None


# ---------------------------------------------------------------------------
# the measurement kinds
# ---------------------------------------------------------------------------

def needs(kind: str, picks: list) -> int:
    """How many clicks this measurement takes (ANGLE: three when it starts with a point, else two)."""
    if kind in ("EDGE", "RADIUS"):
        return 1
    if kind == "ANGLE":
        return 3 if picks and picks[0].kind == "point" else 2
    return 2


def wants(kind: str, index: int, picks: list) -> str:
    """What the click number ``index`` (0-based) of a measurement takes: 'point', 'face', 'flat', 'edge', 'round',
    'axis' (an axis-like face or edge), 'any' (a face, an edge or a snapped point) or 'face_or_edge'."""
    if kind == "DISTANCE":
        return "point"
    if kind == "EDGE":
        return "edge"
    if kind == "FACES":
        return "flat"
    if kind == "RADIUS":
        return "round"
    if kind == "ANGLE":
        if index == 0:
            return "any"
        return "point" if picks and picks[0].kind == "point" else "face_or_edge"
    if kind == "AXIS":
        if index == 0:
            return "any"
        return "axis" if picks and picks[0].kind == "point" else "point"
    return "any"


def refuse(kind: str, index: int, picks: list, p: Pick) -> str:
    """'' when the click may take ``p``; else why not (plain words, shown next to the mouse)."""
    w = wants(kind, index, picks)
    if w == "point" or w == "any":
        if kind == "AXIS" and index == 0 and not (p.kind == "point" or p.is_axis_like()):
            return "Click a point, or a hole, shaft or edge"
        return ""
    if w == "edge" and not p.is_edge():
        return "Click an edge (move the mouse onto the line where two faces meet)"
    if w == "flat" and p.kind != "flat":
        return "Click a flat face"
    if w == "round" and not ((p.kind == "round" and p.r > 0) or p.kind == "circle"):
        return "Click a round face (a hole or a shaft) or a round edge" if p.kind != "axis" else \
            "This round face has no single diameter (a cone or a rounding): click a hole, a shaft or a round edge"
    if w == "axis" and not p.is_axis_like():
        return "Click a hole, a shaft or an edge (its axis)"
    if w == "face_or_edge" and _dir_of(p) is None:
        return "Click a face or an edge (or start with a point for three points)"
    return ""


def snap_kind(kind: str, index: int, picks: list) -> str:
    """What the snapping offers for this click: 'points' (corners, middles, centres first), 'edges' (edges first),
    'faces' (the face under the mouse) or 'all' (points, then edges, then the face)."""
    w = wants(kind, index, picks)
    return {"point": "points", "edge": "edges", "flat": "faces", "round": "round", "axis": "axis",
            "face_or_edge": "edges_faces"}.get(w, "all")


def measure(kind: str, picks: list, u: str = "MM") -> Result | None:
    """The result of a measurement of ``kind`` from its picks (world coordinates); None while clicks are missing."""
    if len(picks) < needs(kind, picks):
        return None
    if kind == "SMART":
        return pair(picks[0], picks[1], u)
    if kind == "DISTANCE":
        r = _points(picks[0], picks[1], u)
        r.lines.append(parts_line(r.vec, u))
        return r
    if kind in ("EDGE", "RADIUS"):
        return single(picks[0], u)
    if kind == "FACES":
        return _planes(picks[0], picks[1], u)
    if kind == "ANGLE":
        if picks[0].kind == "point":
            return angle3(picks[0].p, picks[1].p, picks[2].p, u)
        a, b = picks[0], picks[1]
        da, db = _dir_of(a), _dir_of(b)
        if da is None or db is None:
            return None
        ang = line_angle(da, db)
        what = {"flat": "face", "line": "edge", "circle": "axis", "round": "axis", "axis": "axis"}
        name = f"{what.get(a.kind, 'face')} and {what.get(b.kind, 'face')}"
        lines = [f"Angle {angle_text(ang)}", f"between the {name}"]
        if ang > 0.005 and abs(ang - 90.0) > 0.005:
            lines[1] += f" (or {angle_text(180.0 - ang)})"
        return Result("angle", lines, angle=ang, frm=a.p, to=b.p, vec=sub(b.p, a.p), main_is_angle=True)
    if kind == "AXIS":
        a, b = picks[0], picks[1]
        pt, ax = (a, b) if a.kind == "point" or not a.is_axis_like() else (b, a)
        if not ax.is_axis_like():
            return None
        foot = on_line(pt.p, ax.o, ax.d)
        v = sub(pt.p, foot)
        name = {"line": "edge", "circle": "round edge's axis"}.get(ax.kind, "axis")
        return Result("point-axis", [f"Point to {name} {fmt(length(v), u)}"], dist=length(v), frm=foot, to=pt.p, vec=v)
    return None


def angle3(a, b, c, u: str = "MM") -> Result:
    """The angle at ``b`` between b→a and b→c (0 … 180°)."""
    v1, v2 = sub(a, b), sub(c, b)
    l1, l2 = length(v1), length(v2)
    if l1 < 1e-12 or l2 < 1e-12:
        ang = 0.0
    else:
        ang = deg(math.acos(max(-1.0, min(1.0, dot(v1, v2) / (l1 * l2)))))
    return Result("angle3", [f"Angle {angle_text(ang)}", f"arms {fmt(l1, u)} and {fmt(l2, u)}"], angle=ang,
                  corner=_t(b), arm_a=_t(a), arm_b=_t(c), main_is_angle=True)


def anchor(r: Result) -> tuple | None:
    """Where a result's label sits (world): the middle of its line, an angle's corner, else None."""
    if r.corner is not None:
        return r.corner
    if r.frm is not None and r.to is not None:
        return mul(add(r.frm, r.to), 0.5)
    return r.frm or r.to


# ---------------------------------------------------------------------------
# snapping
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    kind: str                                  # corner | middle | centre | edge | face
    pick: Pick
    screen: tuple | None = None                # (x, y) px of a point candidate
    segs: list | None = None                   # edge: [((x0, y0), (x1, y1)) …] px of its drawn line
    world_segs: list | None = None             # … and those ends in the world (the point on the edge is found there)


def seg_closest(m, a, b) -> tuple[float, float]:
    """(distance px from ``m`` to the 2D segment a–b, where along it 0 … 1)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = 0.0 if ll <= 1e-12 else max(0.0, min(1.0, ((m[0] - ax) * dx + (m[1] - ay) * dy) / ll))
    px, py = ax + t * dx, ay + t * dy
    return math.hypot(m[0] - px, m[1] - py), t


ORDER = {"points": ("corner", "middle", "centre", "edge", "face"),
         "all": ("corner", "middle", "centre", "edge", "face"),
         "edges": ("edge",),
         "edges_faces": ("edge", "face"),
         "faces": ("face",),
         "round": ("edge", "face"),
         "axis": ("edge", "face")}


def choose(cands: list, mouse, offer: str = "all", scale: float = 1.0, no_snap: bool = False):
    """The candidate a click takes and where (``(Candidate, world point or None)``): the nearest point candidate
    within SNAP_PX, else the nearest edge within EDGE_PX (``offer`` 'edges': any distance – the face's nearest edge),
    else the face. ``no_snap`` (Shift): the face candidate only. ``scale`` = the UI scale."""
    if no_snap:
        f = next((c for c in cands if c.kind == "face"), None)
        return f, None
    want = ORDER.get(offer, ORDER["all"])
    pts = [c for c in cands if c.kind in ("corner", "middle", "centre") and c.kind in want and c.screen is not None]
    best, bd = None, SNAP_PX * scale
    for c in pts:
        d = math.hypot(c.screen[0] - mouse[0], c.screen[1] - mouse[1])
        if d <= bd:
            best, bd = c, d
    if best is not None:
        return best, None
    if "edge" in want:
        limit = 1e9 if offer == "edges" else EDGE_PX * scale
        eb, ed, et = None, limit, None
        for c in cands:
            if c.kind != "edge" or not c.segs:
                continue
            if offer == "round" and c.pick.kind != "circle":
                continue
            for k, (a, b) in enumerate(c.segs):
                d, t = seg_closest(mouse, a, b)
                if d <= ed:
                    eb, ed, et = c, d, (k, t)
        if eb is not None:
            at = None
            if eb.world_segs and et is not None:
                wa, wb = eb.world_segs[et[0]]
                at = add(wa, mul(sub(wb, wa), et[1]))
            return eb, at
    if "face" in want:
        f = next((c for c in cands if c.kind == "face"), None)
        return f, None
    return None, None


def circle_points(c, s, axis_sweep, n: int = 48) -> list:
    """Points along a round edge: centre ``c``, start ``s``, axis × angle ``axis_sweep`` (right hand), ``n`` steps
    for a whole circle (fewer for an arc, at least 4)."""
    sweep = length(axis_sweep)
    if sweep <= 1e-9:
        return [_t(s)]
    k = unit(axis_sweep)
    v = sub(s, c)
    steps = max(4, int(math.ceil(n * sweep / (2 * math.pi))))
    out = []
    for i in range(steps + 1):
        t = sweep * i / steps
        ct, st = math.cos(t), math.sin(t)
        # Rodrigues: v cos t + (k × v) sin t + k (k·v)(1 − cos t)
        r = add(add(mul(v, ct), mul(cross(k, v), st)), mul(k, dot(k, v) * (1 - ct)))
        out.append(add(c, r))
    return out


def summary(kind: str, r: Result | None, u: str = "MM") -> str:
    """One line for the list in the Measure drop-down: 'Distance  123.45 mm'."""
    if r is None:
        return f"{TITLES.get(kind, kind)}: –"
    return r.lines[0]
