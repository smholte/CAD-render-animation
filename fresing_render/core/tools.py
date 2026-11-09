"""The tool library (task 0040): one list of tools per project. No Blender here.

Every tool is a row with its T number, a type and the sizes of that type (``Spec``). From the sizes come

* the **cutting shape** (``cutting_tool``): the outline milling sweeps (``core/machining.Tool``), so every tool
  cuts with its own shape, also after a tool change;
* a **mesh to show** (``tool_mesh``): the tool with flutes along a helix (end mills, drills), inserts on a face
  mill, teeth on a thread mill or a slot cutter, and an optional generic holder (SK40, BT30, BT40, HSK63, ER collet);
* the **chip type** (``chip_kind``) for the chips (task 0028).

The rows are filled from sizes typed in, from files the owner already has (``read_fusion`` for Fusion tool
libraries ``.json`` / ``.tools``, ``read_linuxcnc`` for a LinuxCNC ``tool.tbl``, ``from_info`` for the tool comments
of a program) or from a shape: ``from_outline`` turns the outline read from a part or a tool STEP into a first guess.

Units: metres (Blender's), angles in degrees. A size of 0 means "not given": ``resolved`` fills in what the type
usually has, so a row with only a diameter works at once.
"""

from __future__ import annotations

import json
import math
import re
import zipfile
from dataclasses import dataclass, field, fields, replace

import numpy as np

from . import machining

MM = 0.001
INCH = 0.0254

# ---------------------------------------------------------------------------
# types
# ---------------------------------------------------------------------------

#: id -> (name, sizes the type uses). The first five are the shapes milling knew before (task 0027).
TYPES = {
    "FLAT": ("Flat end mill", ("diameter", "flute_length", "flutes")),
    "BALL": ("Ball end mill", ("diameter", "flute_length", "flutes")),
    "BULL": ("Bull-nose end mill", ("diameter", "corner", "flute_length", "flutes")),
    "VEE": ("Spot drill / chamfer mill", ("diameter", "angle")),
    "DRILL": ("Drill", ("diameter", "angle", "flute_length")),
    "FACE": ("Face mill", ("diameter", "inserts", "insert_size", "lead_angle")),
    "THREAD": ("Thread mill", ("diameter", "pitch", "flute_length")),
    "SLOT": ("Slot / T-slot cutter", ("diameter", "width", "neck")),
}
KINDS = tuple(TYPES)

HOLDERS = {
    "NONE": "None (the spindle of the model holds it)",
    "ER": "ER collet",
    "SK40": "SK40 (DIN 69871)",
    "BT30": "BT30",
    "BT40": "BT40",
    "HSK63": "HSK63",
}

#: a new row of each type: sizes in mm (converted below), angles in degrees
_DEFAULTS_MM = {
    "FLAT": dict(diameter=10, flute_length=22, flutes=3, stick_out=35),
    "BALL": dict(diameter=6, flute_length=12, flutes=2, stick_out=30),
    "BULL": dict(diameter=12, corner=1, flute_length=24, flutes=4, stick_out=40),
    "VEE": dict(diameter=10, angle=90, flute_length=8, flutes=2, stick_out=35),
    "DRILL": dict(diameter=6.8, angle=118, flute_length=40, flutes=2, stick_out=60),
    "FACE": dict(diameter=50, inserts=5, insert_size=12, lead_angle=45, stick_out=40),
    "THREAD": dict(diameter=10, pitch=1.5, flute_length=15, flutes=3, stick_out=40),
    "SLOT": dict(diameter=25, width=6, neck=12, flutes=8, stick_out=35),
}
_LENGTHS = ("diameter", "corner", "flute_length", "insert_size", "pitch", "width", "neck", "shank", "stick_out",
            "holder_diameter", "holder_length", "gauge")


@dataclass
class Spec:
    """One tool. Lengths in metres, angles in degrees; 0 = not given (``resolved`` fills it in)."""
    number: int = 1
    name: str = ""
    kind: str = "FLAT"
    diameter: float = 10 * MM
    corner: float = 0.0           # BULL: corner radius
    angle: float = 0.0            # DRILL: point angle, VEE: included tip angle
    flute_length: float = 0.0     # how far from the tip it cuts
    flutes: int = 0
    inserts: int = 0              # FACE
    insert_size: float = 0.0      # FACE: edge length of an insert
    lead_angle: float = 0.0       # FACE: 90 = square shoulder, 45 = a 45° face mill
    pitch: float = 0.0            # THREAD
    width: float = 0.0            # SLOT: cutting width (height of the disc)
    neck: float = 0.0             # SLOT: neck diameter
    shank: float = 0.0            # shank diameter (0: as the type usually has)
    stick_out: float = 0.0        # from the tip to the holder (length below the holder)
    holder: str = "NONE"
    holder_diameter: float = 0.0  # nose of the holder
    holder_length: float = 0.0    # from the nose to the spindle face (gauge length of the holder)
    gauge: float = 0.0            # from the tip to the gauge line (0: stick-out + holder length), task 0049
    pocket: int = 0               # changer pocket (task 0041)
    note: str = ""                # e.g. "Fusion type 'lollipop mill' read as a ball end mill"
    source: str = ""              # typed, program comment, tool table, Fusion library, STEP, part

    def label(self) -> str:
        return f"T{self.number} {self.name or describe(self)}"


def type_name(kind: str) -> str:
    return TYPES.get(kind, (kind.title(),))[0]


def default(kind: str = "FLAT", number: int = 1) -> Spec:
    """A new row of this type with sizes a common tool has."""
    kind = kind if kind in TYPES else "FLAT"
    vals = dict(_DEFAULTS_MM[kind])
    for k in list(vals):
        if k in _LENGTHS:
            vals[k] = vals[k] * MM
    return resolved(Spec(number=number, kind=kind, **vals))


def resolved(spec: Spec) -> Spec:
    """A copy with every size the type needs filled in (sizes given are kept)."""
    s = replace(spec)
    k = s.kind if s.kind in TYPES else "FLAT"
    s.kind = k
    D = max(s.diameter, 0.05 * MM)
    s.diameter = D
    R = D / 2
    if s.flutes <= 0:
        s.flutes = {"FLAT": 3, "BALL": 2, "BULL": 4, "VEE": 2, "DRILL": 2, "THREAD": 3, "SLOT": 8}.get(k, 3)
    if k == "BULL":
        s.corner = min(max(s.corner, 0.0), R) if s.corner > 0 else min(1 * MM, R / 2)
    else:
        s.corner = R if k == "BALL" else 0.0
    if k == "DRILL":
        s.angle = s.angle if 30 <= s.angle <= 175 else 118.0
    elif k == "VEE":
        s.angle = s.angle if 10 <= s.angle <= 175 else 90.0
    if k == "FACE":
        s.inserts = s.inserts if s.inserts > 0 else max(3, min(12, int(round(D / (10 * MM)))))
        s.insert_size = s.insert_size if s.insert_size > 0 else min(max(0.22 * D, 6 * MM), 16 * MM)
        s.lead_angle = s.lead_angle if 10 <= s.lead_angle <= 90 else 90.0
    if k == "THREAD":
        s.pitch = s.pitch if s.pitch > 0 else max(0.25 * MM, round(D * 0.15 * 4000) / 4000)
    if k == "SLOT":
        s.width = s.width if s.width > 0 else max(1 * MM, 0.25 * D)
        s.neck = s.neck if 0 < s.neck < D else max(0.3 * D, min(0.5 * D, 16 * MM))
    if s.flute_length <= 0:
        s.flute_length = {"VEE": R / math.tan(math.radians(s.angle or 90) / 2) + 2 * MM,
                          "DRILL": max(6 * D, 10 * MM), "FACE": cutting_height(s), "SLOT": s.width,
                          "THREAD": max(1.5 * D, 3 * s.pitch)}.get(k, max(2.5 * D, 3 * MM))
    if k == "FACE":
        s.flute_length = cutting_height(s)
    if k == "SLOT":
        s.flute_length = s.width
    if s.stick_out <= 0:
        s.stick_out = max(s.flute_length * 1.4, s.flute_length + 8 * MM, 15 * MM)
    if s.shank <= 0:
        s.shank = {"FACE": min(D * 0.45, 32 * MM), "SLOT": s.neck}.get(k, D if D >= 3 * MM else 3 * MM)
    if s.holder not in HOLDERS:
        s.holder = "NONE"
    if s.holder != "NONE":
        dflt = HOLDER_SIZES[s.holder]
        if s.holder_diameter <= 0:
            s.holder_diameter = dflt[0]
        if s.holder_length <= 0:
            s.holder_length = dflt[1]
    return s


def cutting_height(s: Spec) -> float:
    """How high the inserts of a face mill cut (from the tip)."""
    return max(1 * MM, 0.5 * (s.insert_size or 12 * MM))


def describe(spec: Spec) -> str:
    """'Flat end mill Ø10 mm' / 'Face mill Ø50 mm, 5 inserts, 45°' ..."""
    s = resolved(spec)
    d = f"Ø{_mm(s.diameter)} mm"
    extra = {"BULL": f" R{_mm(s.corner)}", "VEE": f" {s.angle:g}°", "DRILL": f" {s.angle:g}°",
             "FACE": f", {s.inserts} inserts" + ("" if s.lead_angle >= 89.9 else f", {s.lead_angle:g}°"),
             "THREAD": f" pitch {_mm(s.pitch)}", "SLOT": f" × {_mm(s.width)} wide"}.get(s.kind, "")
    return f"{type_name(s.kind)} {d}{extra}"


def _mm(v: float) -> str:
    return f"{v * 1000:.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# what it cuts with, and its chips
# ---------------------------------------------------------------------------

def cutting_tool(spec: Spec) -> machining.Tool:
    """The outline milling sweeps (tip at z = 0, up to the end of the flutes)."""
    s = resolved(spec)
    R, L = s.diameter / 2, max(s.flute_length, 0.1 * MM)
    if s.kind in ("FLAT", "THREAD", "SLOT"):              # a thread mill's teeth reach its diameter; a slot
        return machining.Tool("FLAT", radius=R, length=L)  # cutter's disc is as high as it cuts
    if s.kind == "BALL":
        return machining.Tool("BALL", radius=R, length=L)
    if s.kind == "BULL":
        return machining.Tool("BULL", radius=R, length=L, corner=s.corner)
    if s.kind in ("VEE", "DRILL"):
        return machining.Tool(s.kind, radius=R, length=max(L, R / math.tan(math.radians(s.angle) / 2)),
                              angle=s.angle)
    # FACE: the inserts' band; with a lead angle below 90° it widens upwards
    h = cutting_height(s)
    if s.lead_angle >= 89.9:
        return machining.Tool("FLAT", radius=R, length=h)
    grow = h / math.tan(math.radians(s.lead_angle))
    return machining.Tool("CUSTOM", radius=R, length=h, profile=((0.0, R), (h, R + grow)))


def chip_kind(spec: Spec) -> str:
    """The chip type (``core/chips.BIT_KINDS``) of a tool; thread mills and slot cutters as end mills."""
    return {"BALL": "BALL", "FACE": "FACE", "DRILL": "DRILL", "VEE": "ENGRAVE"}.get(spec.kind, "END")


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def checks(spec: Spec, travel=None) -> list:
    """Warnings (not errors) for sizes that look wrong. ``travel``: the machine's X/Y/Z travel (m), if known."""
    s = resolved(spec)
    out = []
    if s.diameter > 0.25:
        out.append(f"T{s.number}: Ø{_mm(s.diameter)} mm is wider than tools usually are – check the unit")
    if s.diameter < 0.1 * MM:
        out.append(f"T{s.number}: Ø{_mm(s.diameter)} mm is very small – check the unit")
    if s.stick_out > 0.3:
        out.append(f"T{s.number}: it sticks out {_mm(s.stick_out)} mm – longer than tools usually are")
    if s.flute_length > s.stick_out + 1e-9 and s.kind not in ("FACE", "SLOT"):
        out.append(f"T{s.number}: the flutes ({_mm(s.flute_length)} mm) are longer than the tool sticks out "
                   f"({_mm(s.stick_out)} mm)")
    if s.kind == "SLOT" and s.neck >= s.diameter:
        out.append(f"T{s.number}: the neck is not narrower than the cutter")
    if travel is not None:
        tr = list(travel) + [None] * (3 - len(travel))
        xy = [float(t) for t in tr[:2] if t and t > 0]
        if xy and s.diameter > 0.5 * min(xy):
            out.append(f"T{s.number}: Ø{_mm(s.diameter)} mm is more than half the machine's travel")
        if tr[2] and tr[2] > 0 and s.stick_out > tr[2]:
            out.append(f"T{s.number}: it sticks out further than the machine's Z travel")
    return out


# ---------------------------------------------------------------------------
# mesh to show (tip at the origin, the tool along +Z)
# ---------------------------------------------------------------------------

#: holder type -> (nose diameter, gauge length from the nose to the spindle face), metres
HOLDER_SIZES = {"ER": (50 * MM, 22 * MM), "SK40": (40 * MM, 60 * MM), "BT30": (32 * MM, 45 * MM),
                "BT40": (40 * MM, 60 * MM), "HSK63": (40 * MM, 60 * MM)}

#: steep-taper and HSK holders: flange radius, flange thickness (from the gauge line), taper radius at the gauge
#: line, taper length, pull stud (length, radius); metres
_TAPERS = {"SK40": (31.75 * MM, 15.9 * MM, 22.225 * MM, 68.4 * MM, 25 * MM, 7 * MM),
           "BT30": (23.0 * MM, 20.0 * MM, 15.875 * MM, 48.4 * MM, 23 * MM, 5 * MM),
           "BT40": (31.75 * MM, 22.0 * MM, 22.225 * MM, 65.4 * MM, 25 * MM, 7 * MM),
           "HSK63": (31.5 * MM, 20.0 * MM, 24.0 * MM, 32.0 * MM, 0.0, 0.0)}


def gauge_length(spec: Spec) -> float:
    """From the tip to the gauge line (the spindle face): the length a tool length offset (G43) uses. The gauge length
    typed in when there is one (a part or STEP model with its holder inside), else the stick-out plus the holder."""
    s = resolved(spec)
    if s.gauge > 0:
        return s.gauge
    return s.stick_out + (s.holder_length if s.holder != "NONE" else 0.0)


class _Mesh:
    def __init__(self):
        self.v: list = []
        self.t: list = []
        self.part: list = []      # per triangle: 0 = the tool, 1 = the holder

    def add(self, verts, tris, part: int) -> None:
        off = sum(len(x) for x in self.v)
        self.v.append(np.asarray(verts, dtype=np.float64).reshape(-1, 3))
        self.t.append(np.asarray(tris, dtype=np.int64).reshape(-1, 3) + off)
        self.part.append(np.full(len(self.t[-1]), part, dtype=np.int32))

    def result(self) -> tuple:
        if not self.v:
            return np.zeros((0, 3)), np.zeros((0, 3), np.int64), np.zeros(0, np.int32)
        return np.concatenate(self.v), np.concatenate(self.t), np.concatenate(self.part)


def lathe(rings: list, seg: int) -> tuple:
    """A closed surface from rings bottom to top. A ring is (z, radii) – radii one per corner (``seg`` of them),
    or a single number; a radius of 0 everywhere is a point on the axis. Rings at the same height with other radii
    make flat steps. Returns (verts, tris)."""
    ang = np.linspace(0.0, 2 * math.pi, seg, endpoint=False)
    c, s = np.cos(ang), np.sin(ang)
    verts, tris, idx = [], [], []
    n = 0
    for z, r in rings:
        r = np.broadcast_to(np.asarray(r, dtype=np.float64), (seg,))
        if float(np.max(r)) <= 1e-12:
            verts.append(np.array([[0.0, 0.0, z]]))
            idx.append(np.array([n]))
            n += 1
        else:
            verts.append(np.stack([c * r, s * r, np.full(seg, z)], axis=1))
            idx.append(np.arange(n, n + seg))
            n += seg
    k = np.arange(seg)
    k1 = (k + 1) % seg
    for a, b in zip(idx, idx[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            tris.append(np.stack([np.full(seg, a[0]), b[k], b[k1]], axis=1))
        elif len(b) == 1:
            tris.append(np.stack([a[k], np.full(seg, b[0]), a[k1]], axis=1))
        else:
            tris.append(np.stack([a[k], b[k], b[k1]], axis=1))
            tris.append(np.stack([a[k], b[k1], a[k1]], axis=1))
    for ring, top in ((idx[0], False), (idx[-1], True)):      # caps
        if len(ring) == 1:
            continue
        z = verts[0][0, 2] if not top else verts[-1][0, 2]
        verts.append(np.array([[0.0, 0.0, z]]))
        cc = n
        n += 1
        if top:
            tris.append(np.stack([np.full(seg, cc), ring[k], ring[k1]], axis=1))
        else:
            tris.append(np.stack([np.full(seg, cc), ring[k1], ring[k]], axis=1))
    return np.concatenate(verts), np.concatenate(tris)


def _grooves(seg: int, flutes: int, phase: float, depth: float, width: float = 0.42) -> np.ndarray:
    """Factor (<= 1) on the radius around a ring: ``flutes`` grooves, the lands stay at 1 (the outer diameter)."""
    ang = np.linspace(0.0, 2 * math.pi, seg, endpoint=False)
    u = np.mod((ang - phase) * flutes / (2 * math.pi), 1.0)
    bump = np.where(u < width, np.sin(np.pi * np.clip(u / width, 0, 1)), 0.0)
    return 1.0 - depth * bump


def _outline(s: Spec, seg_arc: int = 6) -> list:
    """(z, r) of the cutter from the tip up to the end of its flutes (no flutes, no shank)."""
    R, L = s.diameter / 2, s.flute_length
    if s.kind == "BALL":
        return [(R - R * math.cos(t), R * math.sin(t)) for t in np.linspace(0, math.pi / 2, seg_arc + 1)] + [(L, R)]
    if s.kind == "BULL":
        c = s.corner
        return [(c - c * math.cos(t), (R - c) + c * math.sin(t)) for t in np.linspace(0, math.pi / 2, seg_arc + 1)] \
            + [(L, R)]
    if s.kind in ("VEE", "DRILL"):
        h = R / math.tan(math.radians(s.angle) / 2)
        out = [(0.0, 0.0), (h * 0.5, R * 0.5), (h, R)]
        return out + ([(L, R)] if L > h + 1e-6 else [])
    return [(0.0, R), (L, R)]


def tool_mesh(spec: Spec, seg: int = 48) -> tuple:
    """(verts (n, 3), tris (m, 3), part (m,)) of the tool – flutes, inserts or teeth – and its holder.
    The tip is at the origin, the tool along +Z; part 0 = the tool, 1 = the holder."""
    s = resolved(spec)
    out = _Mesh()
    R = s.diameter / 2
    if s.kind == "FACE":
        _face_mill(out, s, seg)
    elif s.kind == "SLOT":
        _slot_cutter(out, s, seg)
    else:
        _fluted(out, s, seg)
    if s.holder != "NONE":
        hv, ht = lathe(holder_rings(s), seg)
        hv[:, 2] += s.stick_out
        out.add(hv, ht, 1)
    _ = R
    return out.result()


def _fluted(out: _Mesh, s: Spec, seg: int) -> None:
    R, L, top = s.diameter / 2, s.flute_length, s.stick_out
    seg = max(seg, 12 * s.flutes)
    helix = {"VEE": 0.0, "THREAD": 0.0}.get(s.kind, 30.0)
    depth = {"DRILL": 0.32, "VEE": 0.18, "THREAD": 0.22}.get(s.kind, 0.26)
    prof = _outline(s)
    L = min(L, top)
    # rings along the flutes: often enough that the helix looks smooth (and every thread crest has one)
    zs = sorted({z for z, _r in prof if z <= L})
    if helix > 0:
        dz = max(R * 0.25 / math.tan(math.radians(helix)), 0.05 * MM)
        zs += list(np.arange(dz, L, dz))
    if s.kind == "THREAD":
        zs += list(np.arange(s.pitch / 4, L, s.pitch / 4))
    zs = sorted(set(round(z, 9) for z in zs if 0 <= z <= L))[:400]
    pz, pr = np.array([p[0] for p in prof]), np.array([p[1] for p in prof])
    run_out = max(0.4 * s.diameter, 1 * MM)
    rings = []
    for z in zs:
        r = float(np.interp(z, pz, pr))
        if s.kind == "THREAD":                      # teeth: crests at the diameter every pitch
            u = (z / s.pitch) % 1.0
            r = R - 0.55 * s.pitch * (2 * abs(u - 0.5))
        fade = 1.0 if z <= L - run_out else max(0.0, (L - z) / run_out)
        phase = z * math.tan(math.radians(helix)) / max(R, 1e-6)
        f = _grooves(seg, s.flutes, phase, depth * fade)
        rings.append((z, r * f if r > 1e-9 else 0.0))
    rs = s.shank / 2
    if abs(rs - R) > 1e-6:
        rings.append((L, rs))
    if top > L + 1e-6:
        rings.append((top, rs))
    v, t = lathe(rings, seg)
    out.add(v, t, 0)


def _face_mill(out: _Mesh, s: Spec, seg: int) -> None:
    """The body (a little up from the tip and in from the edge) and the inserts as small blocks round its rim."""
    R = s.diameter / 2
    h = cutting_height(s)
    a = s.insert_size
    lead = math.radians(s.lead_angle)
    grow = h / math.tan(lead) if s.lead_angle < 89.9 else 0.0
    lift = min(0.6 * MM, 0.15 * h)                          # the inserts stand out below the body
    rb = max(R - 0.45 * a, 0.5 * R)
    neck = s.shank / 2
    top = max(s.stick_out, h + 5 * MM)
    rings = [(lift, rb * 0.92), (lift + 0.25 * MM, rb), (h * 1.6 + 2 * MM, rb + grow * 0.5),
             (h * 1.6 + 2 * MM, max(neck, rb * 0.7)), (top, max(neck, rb * 0.7))]
    v, t = lathe(rings, seg)
    out.add(v, t, 0)
    thick = max(0.28 * a, 1.5 * MM)
    for i in range(s.inserts):
        phi = 2 * math.pi * i / s.inserts
        cs, sn = math.cos(phi), math.sin(phi)
        # local (radial, tangential, z): outer edge at R (bottom) .. R + grow (top)
        pts = []
        for z, rout in ((0.0, R), (h, R + grow)):
            for rad in (rout - 0.8 * a, rout):
                for tan in (-thick / 2, thick / 2):
                    pts.append((rad, tan, z))
        loc = np.array(pts)
        world = np.stack([loc[:, 0] * cs - loc[:, 1] * sn, loc[:, 0] * sn + loc[:, 1] * cs, loc[:, 2]], axis=1)
        out.add(world, _BOX, 0)


# corners: index = z*4 + rad*2 + tan  (z, rad, tan in {0, 1})
_BOX = np.array([[0, 2, 3], [0, 3, 1], [4, 5, 7], [4, 7, 6],      # bottom, top
                 [0, 1, 5], [0, 5, 4], [2, 6, 7], [2, 7, 3],      # inner, outer
                 [0, 4, 6], [0, 6, 2], [1, 3, 7], [1, 7, 5]])     # sides


def _slot_cutter(out: _Mesh, s: Spec, seg: int) -> None:
    R, w, rn, rs = s.diameter / 2, s.width, s.neck / 2, s.shank / 2
    seg = max(seg, 6 * s.flutes)
    teeth = _grooves(seg, s.flutes, 0.0, 0.12, width=0.3)
    neck_top = max(w + 1.2 * (R - rn) + 2 * MM, w + 5 * MM)
    top = max(s.stick_out, neck_top + 5 * MM)
    rings = [(0.0, R * teeth), (w, R * teeth), (w, rn), (neck_top, rn)]
    if abs(rs - rn) > 1e-6:
        rings.append((neck_top, rs))
    rings.append((top, rs))
    v, t = lathe(rings, seg)
    out.add(v, t, 0)


def holder_rings(s: Spec) -> list:
    """(z, r) of a generic holder, z from its nose (where the tool comes out) to the top of its taper."""
    D, A = s.holder_diameter, s.holder_length
    r = D / 2
    if s.holder == "ER":                                # a collet nut and the bit of the chuck above it
        return [(0.0, r * 0.7), (0.15 * A, r), (A, r), (A, r * 0.9), (A + 6 * MM, r * 0.9)]
    flange_r, ft, taper_r, tl, stud_l, stud_r = _TAPERS[s.holder]
    rings = [(0.0, r * 0.85), (2 * MM, r), (max(A - ft - 4 * MM, 3 * MM), r),
             (max(A - ft, 4 * MM), flange_r * 0.9), (max(A - ft, 4 * MM) + 1 * MM, flange_r)]
    gz = max(A - ft, 4 * MM) + ft * 0.5                  # the V-groove the changer grips
    rings += [(gz - 2.5 * MM, flange_r), (gz, flange_r - 3 * MM), (gz + 2.5 * MM, flange_r), (A, flange_r)]
    if s.holder == "HSK63":                              # hollow short taper
        rings += [(A, taper_r), (A + tl, taper_r - 1 * MM), (A + tl, 0.0)]
    else:                                                # 7:24 steep taper and a pull stud
        rings += [(A, taper_r), (A + tl, taper_r - tl * 7 / 48), (A + tl, stud_r + 1 * MM), (A + tl + stud_l, stud_r),
                  (A + tl + stud_l, 0.0)]
    return rings


# ---------------------------------------------------------------------------
# a first guess from a shape (a part of the model, or a tool STEP)
# ---------------------------------------------------------------------------

def from_outline(profile: list, number: int = 1, name: str = "") -> Spec:
    """A row from the outline (z, r) read about the tool's axis from its tip: the cutter is the part up to where
    the outline first widens a lot (the holder) – its outer diameter over all flutes."""
    prof = [(float(z), float(r)) for z, r in profile]
    if len(prof) < 2:
        return default("FLAT", number)
    Z = np.array([p[0] for p in prof])
    Rr = np.array([p[1] for p in prof])
    total = float(Z[-1])
    # where the holder starts: the first step out (after 2 mm) to 1.3 × the radius just below it and to a holder's
    # size (Ø16 or more) - also when the holder's nose is narrower than a face mill's cutter
    stick = total
    below = 0.0
    for z, r in prof:
        if z > 2 * MM and below > 0 and r > 1.3 * below + 0.5 * MM and r >= 8 * MM:
            stick = z
            break
        below = r
    cut = [(z, r) for z, r in prof if z <= stick + 1e-9]
    tool = machining.classify(cut)
    R = tool.radius
    kind = tool.kind if tool.kind in TYPES else "FLAT"
    note = ""
    if tool.kind == "CUSTOM":
        note = "The shape was not recognised: it cuts as a flat end mill of its outer diameter – pick the type"
        R = max(r for z, r in cut)
    # the flutes end where the outline leaves the cutter's radius (a neck or a shank of another size)
    flute = stick
    zc = [z for z, r in cut if abs(r - R) <= max(0.03 * R, 0.05 * MM)]
    if zc:
        after = [z for z, r in cut if z > zc[0] + 1e-6 and abs(r - R) > max(0.03 * R, 0.05 * MM)]
        if after:
            flute = after[0]
    if kind == "FLAT" and 2 * R >= 30 * MM and flute <= 0.4 * 2 * R:
        kind = "FACE"                                     # wide, cutting only near its tip: a face mill
    spec = Spec(number=number, name=name, kind=kind, diameter=round(2 * R, 6), stick_out=round(stick, 6),
                flute_length=round(min(flute, stick), 6), corner=tool.corner if kind == "BULL" else 0.0,
                angle=tool.angle if kind in ("VEE", "DRILL") else 0.0, note=note)
    if kind == "FACE":
        spec.flute_length = 0.0
        spec.insert_size = round(2 * min(flute, stick), 6)       # the inserts cut half their size deep
    return resolved(spec)


# ---------------------------------------------------------------------------
# reading tool files
# ---------------------------------------------------------------------------

#: words in a type or a description -> type; the first match wins (English, Dutch, German)
_TYPE_WORDS = (
    ("FACE", ("face mill", "facemill", "planfräser", "planfrees", "messerkopf", "shell mill")),
    ("THREAD", ("thread mill", "threadmill", "gewindefräser", "draadfrees", "tap ", "tap", "gewindebohrer")),
    ("SLOT", ("slot mill", "slot cutter", "t-slot", "tslot", "woodruff", "disc mill", "scheibenfräser",
              "dovetail", "zwaluwstaart", "schijffrees")),
    ("BULL", ("bull nose", "bullnose", "bull", "torus", "corner radius", "radius mill", "torusfräser")),
    ("BALL", ("ball", "lollipop", "kugel", "bolkop")),
    ("VEE", ("chamfer", "spot drill", "spotdrill", "center drill", "centre drill", "centerdrill", "nc spot",
             "countersink", "counter sink", "engrav", "v-bit", "vbit", "v bit", "anfas", "fase", "zentrier",
             "senker", "verzinker")),
    ("DRILL", ("drill", "bohrer", "boor", "reamer", "reibahle", "ruimer")),
    ("FLAT", ("flat end mill", "end mill", "endmill", "flat", "schaftfräser", "vingerfrees", "frees", "fräser",
              "counterbore", "counter bore", "boring", "form mill", "tapered mill", "mill")),
)

#: Fusion types that are read as another type: (type, note)
_FUSION_NEAREST = {
    "lollipop mill": "BALL", "dovetail mill": "SLOT", "tapered mill": "FLAT", "radius mill": "BULL",
    "counter sink": "VEE", "center drill": "VEE", "reamer": "DRILL", "boring bar": "FLAT", "counter bore": "FLAT",
    "tap right hand": "THREAD", "tap left hand": "THREAD", "form mill": "FLAT", "engrave": "VEE",
}
_FUSION_EXACT = {"flat end mill": "FLAT", "ball end mill": "BALL", "bull nose end mill": "BULL",
                 "chamfer mill": "VEE", "spot drill": "VEE", "drill": "DRILL", "face mill": "FACE",
                 "thread mill": "THREAD", "slot mill": "SLOT"}
_FUSION_SKIP = ("probe", "holder", "turning", "laser", "plasma", "waterjet", "jet", "grooving", "boring turning")


def kind_from_text(text: str) -> str:
    """The type a tool's description names ('' when it names none)."""
    t = " " + (text or "").lower().replace("_", " ") + " "
    for kind, words in _TYPE_WORDS:
        for w in words:
            end = "" if len(w.strip()) >= 5 else r"(?![a-zäöü])"     # long words also as the start of a
            if re.search(r"(?<![a-zäöü])" + re.escape(w.strip()) + end, t):  # compound (Kugelfräser)
                return kind
    return ""


@dataclass
class ReadResult:
    tools: list = field(default_factory=list)       # Spec
    notes: list = field(default_factory=list)       # things read but changed or left out


def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def read_fusion(data) -> ReadResult:
    """A Fusion tool library: the JSON text or bytes of a ``.json`` file, or the bytes of a ``.tools`` file (a zip
    with the JSON inside). Unknown fields are ignored; unknown types are read as the nearest type, with a note."""
    if isinstance(data, (bytes, bytearray)) and bytes(data[:2]) == b"PK":
        import io
        with zipfile.ZipFile(io.BytesIO(bytes(data))) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".json")] or zf.namelist()
            if not names:
                raise ValueError("The .tools file holds no tool list")
            data = zf.read(names[0])
    if isinstance(data, (bytes, bytearray)):
        data = bytes(data).decode("utf-8-sig", errors="replace")
    doc = json.loads(data)
    rows = doc.get("data", doc.get("tools", [])) if isinstance(doc, dict) else doc
    res = ReadResult()
    used = set()
    for k, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        ftype = str(row.get("type", "")).strip().lower()
        desc = str(row.get("description", "") or row.get("product-id", "") or "").strip()
        if any(w in ftype for w in _FUSION_SKIP) and ftype not in _FUSION_EXACT:
            res.notes.append(f"'{desc or ftype}': a {ftype} is not a milling tool – left out")
            continue
        g = row.get("geometry", {}) or {}
        pp = row.get("post-process", {}) or {}
        unit = str(row.get("unit", "millimeters")).lower()
        k_ = INCH if unit.startswith("inch") else MM
        kind = _FUSION_EXACT.get(ftype, "")
        note = ""
        if not kind:
            kind = _FUSION_NEAREST.get(ftype, "") or kind_from_text(ftype) or kind_from_text(desc) or "FLAT"
            note = f"Fusion type '{ftype or '?'}' read as a {type_name(kind).lower()}"
        n = int(_num(pp.get("number"), 0))
        if n <= 0 or n in used:
            n = max(used | {0}) + 1
            note = (note + "; " if note else "") + "it had no T number of its own: numbered " + str(n)
        used.add(n)
        D = _num(g.get("DC")) * k_
        s = Spec(number=n, name=desc or type_name(kind), kind=kind, diameter=D, source="Fusion library", note=note)
        s.flute_length = _num(g.get("LCF")) * k_
        s.flutes = int(_num(g.get("NOF"), 0))
        s.shank = _num(g.get("SFDM")) * k_
        lb = _num(g.get("LB")) * k_ or _num(g.get("shoulder-length")) * k_
        s.stick_out = lb or (_num(g.get("OAL")) * k_ * 0.75)
        if kind == "BULL":
            s.corner = _num(g.get("RE")) * k_
        if kind == "DRILL":
            s.angle = _num(g.get("SIG"), 118.0)
        if kind == "VEE":
            ta = _num(g.get("TA"))
            s.angle = _num(g.get("SIG")) or (2 * ta if 0 < ta < 90 else 90.0)
            if ftype == "chamfer mill" and _num(g.get("tip-diameter")):
                s.note = (s.note + "; " if s.note else "") + "its tip is cut flat: shown pointed"
        if kind == "FACE":
            ta = _num(g.get("TA"))
            s.lead_angle = 90.0 - ta if 0 < ta < 80 else 90.0
            s.inserts = s.flutes
        if kind == "THREAD":
            s.pitch = _num(g.get("TP")) * k_ or (25.4 * MM / _num(g.get("TPI")) if _num(g.get("TPI")) else 0.0)
        if kind == "SLOT":
            s.width = s.flute_length
            s.neck = _num(g.get("shoulder-diameter")) * k_ or s.shank
        holder = row.get("holder") or {}
        if isinstance(holder, dict) and holder:
            hd = str(holder.get("description", "") or holder.get("product-id", "")).upper().replace("-", "")
            ht = next((h for h in ("HSK63", "SK40", "BT30", "BT40") if h in hd.replace(" ", "")), "")
            if not ht and ("ER" in hd.split() or re.search(r"\bER\d", hd)):
                ht = "ER"
            segs = holder.get("segments") or []
            gl = sum(_num(sg.get("height")) for sg in segs if isinstance(sg, dict)) * k_
            if ht:
                s.holder = ht
                s.holder_length = gl if gl > 0 else 0.0
                widest = max((_num(sg.get("lower-diameter")) for sg in segs if isinstance(sg, dict)), default=0.0)
                s.holder_diameter = widest * k_ if widest > 0 else 0.0
        res.tools.append(resolved(s))
    res.tools.sort(key=lambda x: x.number)
    return res


def read_linuxcnc(text: str, inch: bool = False) -> ReadResult:
    """A LinuxCNC tool table: ``T1 P1 D6.0 Z+30.0 ;6 mm end mill``. The Z offset is used as the stick-out, the
    comment gives the name and the type."""
    k = INCH if inch else MM
    res = ReadResult()
    for raw in text.splitlines():
        code, _sep, comment = raw.partition(";")
        words = {}
        for w in code.split():
            if len(w) > 1 and w[0].isalpha():
                words[w[0].upper()] = w[1:]
        if "T" not in words:
            continue
        try:
            n = int(float(words["T"]))
            d = abs(float(words.get("D", "0"))) * k
            z = abs(float(words.get("Z", "0"))) * k
            p = int(float(words.get("P", "0")))
        except ValueError:
            res.notes.append(f"Line '{raw.strip()}' could not be read")
            continue
        if n <= 0:
            continue
        comment = comment.strip()
        kind = kind_from_text(comment) or "FLAT"
        s = Spec(number=n, name=comment or f"Tool {n}", kind=kind, diameter=d or 6 * MM, stick_out=z,
                 pocket=p, source="tool table")
        if not d:
            s.note = "no diameter in the table: Ø6 mm used"
        m = re.search(r"\bR\s*(\d+(?:\.\d+)?)", comment, re.I)
        if kind == "BULL" and m:
            s.corner = float(m.group(1)) * k
        m = re.search(r"(\d+(?:\.\d+)?)\s*°|\b(\d{2,3})\s*deg", comment, re.I)
        if kind in ("VEE", "DRILL") and m:
            s.angle = float(m.group(1) or m.group(2))
        res.tools.append(resolved(s))
    res.tools.sort(key=lambda x: x.number)
    return res


def from_info(info) -> Spec:
    """A row from a program's tool comment or tool table entry (``core/gcode.ToolInfo``, sizes in mm)."""
    kind = kind_from_text(info.comment) or info.kind or "FLAT"
    if kind not in TYPES:
        kind = "FLAT"
    s = Spec(number=info.number, name=_name_from_comment(info.comment), kind=kind,
             diameter=(info.diameter or 6.0) * MM, corner=(info.corner or 0.0) * MM if kind == "BULL" else 0.0,
             angle=info.angle if kind in ("VEE", "DRILL") else 0.0, stick_out=(info.length or 0.0) * MM,
             source={"comment": "program comment", "table": "tool table"}.get(info.source, info.source or "program"))
    if not info.diameter:
        s.note = "the program gives no size: Ø6 mm used"
    return resolved(s)


def _name_from_comment(comment: str) -> str:
    """'T1 D=6. CR=0. - ZMIN=-3. - flat end mill' -> 'flat end mill'."""
    c = (comment or "").strip()
    if " - " in c:
        c = c.split(" - ")[-1].strip()
    c = re.sub(r"^T\d+\s*", "", c)
    c = re.sub(r"\b(D|DIA|CR|TAPER|ZMIN|L|LEN|OL|LB)\s*=\s*[-+]?\d*\.?\d+", "", c, flags=re.I).strip(" -")
    return c[:60]


def spec_fields() -> list:
    """The names of the fields of a row (for copying between rows and Blender properties)."""
    return [f.name for f in fields(Spec)]


def missing(numbers, specs) -> list:
    """T numbers used in a program that are not in the list."""
    have = {s.number for s in specs}
    return sorted(n for n in set(numbers) if n and n not in have)
