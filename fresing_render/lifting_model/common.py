"""Shapes and helpers the crane makers share (task 0191) – OpenCascade through ``demo_model/geom.py``.

Every part is one solid (the importer reads its colour only then). Shapes are made in the model's own coordinates
(mm, the CAD pose) and placed with the identity, except repeated parts (wheels, lattice members, track links), which
are one ``Part`` placed many times (the app makes one mesh of them).
"""

from __future__ import annotations

import math
import os

import numpy as np

from ..demo_model import geom as g
from ..demo_model.geom import Asm, Part
from . import classes as C

# ---- colours (sRGB) – generic, no maker's livery -------------------------------------------------------------------
BOOM_YELLOW = (0.93, 0.70, 0.08)
CARRIER_GREY = (0.32, 0.34, 0.36)
CAB_WHITE = (0.90, 0.90, 0.88)
GLASS = (0.10, 0.14, 0.18)
COUNTERWEIGHT = (0.22, 0.23, 0.24)
STEEL = (0.60, 0.61, 0.62)
CHROME = (0.86, 0.87, 0.88)
RUBBER = (0.06, 0.06, 0.065)
ROPE = (0.45, 0.46, 0.47)
HOOK_RED = (0.72, 0.12, 0.10)
TRACK_DARK = (0.14, 0.14, 0.15)
PAD_ORANGE = (0.90, 0.42, 0.06)
TRUCK_BLUE = (0.16, 0.27, 0.45)

ARR = np.asarray


def unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def perp(d) -> np.ndarray:
    """A unit vector square to d (for frames along d)."""
    d = unit(d)
    ref = np.array([0.0, 1.0, 0.0]) if abs(d[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x = np.cross(ref, d)
    return x / np.linalg.norm(x)


def along_frame(p0, d) -> np.ndarray:
    """4 x 4 frame at p0 whose z points along d."""
    return g.Frame(np.asarray(p0, float), perp(d), unit(d))


def put(asm: Asm, node, M=None):
    return asm.add(node, np.eye(4) if M is None else M)


def one(*shapes):
    """The shapes fused into one solid; ValueError naming the pieces that do not touch the first."""
    s = g.fuse(*shapes)
    n = g.solids(s)
    if n != 1:
        loose = [i for i, x in enumerate(shapes) if x is not None and g.solids(g.fuse(shapes[0], x)) != 1]
        raise ValueError(f"{n} solids: pieces {loose} do not touch the first")
    return s


class Kit:
    """Each shared part made once (one mesh in the app for every place)."""

    def __init__(self):
        self._cache: dict = {}

    def get(self, key, make):
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    def tube(self, name: str, r: float, length: float, color) -> Part:
        """A round bar along local z, 0 .. length."""
        return self.get(("tube", name, round(r, 3), round(length, 3)),
                        lambda: Part(name, g.cyl(r, length, (0, 0, 0), (0, 0, 1)), color))


# ---------------------------------------------------------------------------------------------------------------------
# Solids in model coordinates

def box_tube(p0, u, n, a0: float, a1: float, w: float, h: float, wall: float, closed=False):
    """A rectangular hollow section along u from a0 to a1 (a measured from p0), w across (y), h along n.
    ``closed``: its front end (a1) closed by a plate."""
    p0, u, n = (np.asarray(v, float) for v in (p0, u, n))
    M = g.Frame(p0 + a0 * u - (h / 2) * n, n, u)      # local z along u, local x along n
    outer = g.box(0.0, -w / 2, 0.0, h, w, a1 - a0)
    inner = g.box(wall, -w / 2 + wall, -1.0, h - 2 * wall, w - 2 * wall, a1 - a0 + (1.0 - wall if closed else 2.0))
    return g.xform(g.cut(outer, inner), M)


def solid_box(p0, u, n, a0: float, a1: float, w: float, h: float, dn: float = 0.0, dy: float = 0.0):
    """A solid block along u (a0 .. a1), w across (its middle at y = dy), h along n (its middle ``dn`` from the
    axis). u and n lie in the x-z plane."""
    p0, u, n = (np.asarray(v, float) for v in (p0, u, n))
    M = g.Frame(p0 + a0 * u + (dn - h / 2) * n, n, u)
    return g.xform(g.box(0.0, dy - w / 2, 0.0, h, w, a1 - a0), M)


def pin_across(c, r: float, half: float, axis=(0.0, 1.0, 0.0)):
    """A round pin through point c along ``axis`` (y), from -half to +half."""
    a = unit(axis)
    return g.cyl(r, 2 * half, np.asarray(c, float) - half * a, a)


def lug_pair(pin, toward, gap: float, plate: float, r: float, length: float, bore: float):
    """Two plates (square to y) round a pin, reaching ``length`` from the pin towards ``toward`` (a direction):
    the eye of a cylinder or a boom sits in the ``gap`` between them; each plate has a bore for the pin."""
    pin = np.asarray(pin, float)
    t = unit(toward)
    shapes = []
    for side in (-1, 1):
        y0 = side * (gap / 2) + (0 if side > 0 else -plate)
        c = pin + np.array([0.0, y0 + plate / 2, 0.0])
        disc = g.cyl(r, plate, (pin[0], pin[1] + y0, pin[2]), (0, 1, 0))
        # the plate's body: from the pin along `toward`
        x = np.cross([0.0, 1.0, 0.0], t)
        M = g.Frame(c - np.array([0.0, plate / 2, 0.0]) - r * x, x, t)
        body = g.xform(g.box(0.0, 0.0, 0.0, 2 * r, plate, length), M)
        M2 = g.Frame(np.array([c[0], pin[1] + y0, c[2]]), (1, 0, 0), (0, 1, 0))
        shapes.append(g.cut(g.fuse(disc, body), g.xform(g.cyl(bore, plate + 2, (0, 0, -1)), M2)))
    return shapes


def cylinder_parts(barrel_name: str, rod_name: str, barrel_pin, rod_pin, fit: dict, barrel_color=BOOM_YELLOW,
                   eye_w: float | None = None):
    """A hydraulic cylinder between its two pins (axes along y): barrel (a tube with its eye at the barrel pin) and
    rod (with its eye at the rod pin), lengths from ``classes.fit_cylinder``. Returns two Parts (model coordinates)."""
    b, r = np.asarray(barrel_pin, float), np.asarray(rod_pin, float)
    d = unit(r - b)
    rb, rr = fit["barrel_r"], fit["rod_r"]
    ew = eye_w or 1.6 * rr
    bore = rr + 0.04 * rr + 2.0
    eye_b = g.cyl(1.3 * rr, ew, b - np.array([0, ew / 2, 0]), (0, 1, 0))
    tube = g.cyl(rb, fit["barrel_len"] - 0.9 * rr, b + 0.9 * rr * d, d)
    # the bore only as deep as the rod's end ever goes (task 0204): a bore along a whole 30 m pendant bar made the
    # clash check's inside test read the rod's end, deep in that long thin hole, as inside the bar
    h0 = max(1.3 * rr + 0.15 * rb, fit["dmin"] - fit["rod_len"] - 2.0 * rr)
    hole = g.cyl(bore, fit["barrel_len"] + 1.3 * rr + 0.15 * rb - h0, b + h0 * d, d)
    barrel = g.cut(g.fuse(eye_b, tube), hole, pin_across(b, 0.45 * rr, ew))
    eye_r = g.cyl(1.25 * rr, ew, r - np.array([0, ew / 2, 0]), (0, 1, 0))
    rod_bar = g.cyl(rr, fit["rod_len"] - 0.9 * rr, r - fit["rod_len"] * d, d)
    rod = g.cut(g.fuse(eye_r, rod_bar), pin_across(r, 0.45 * rr, ew))
    return Part(barrel_name, barrel, barrel_color), Part(rod_name, rod, CHROME)


def tyre_shape(r: float, w: float):
    """A tyre about local y (centred): a rounded ring."""
    ri = 0.62 * r
    k = 0.18 * w
    prof = [(ri, -w / 2), (r - k, -w / 2), (r, -w / 2 + k), (r, w / 2 - k), (r - k, w / 2), (ri, w / 2)]
    return g.revolve(prof, (0, 0, 0), (0, 1, 0))


def rim_shape(r: float, w: float):
    ri = 0.62 * r
    return g.fuse(g.cyl(ri - 2.0, 0.8 * w, (0, -0.4 * w, 0), (0, 1, 0)),
                  g.cyl(0.25 * r, 0.9 * w, (0, -0.45 * w, 0), (0, 1, 0)))


def wheels(asm: Asm, kit: Kit, xs, r: float, y_out: float, z: float | None = None):
    """A tyre and rim at both ends of each axle (x in ``xs``); tyres' outer faces at ±y_out."""
    w = 0.72 * r
    tyre = kit.get(("tyre", r), lambda: Part("TYRE", tyre_shape(r, w), RUBBER))
    rim = kit.get(("rim", r), lambda: Part("WHEEL RIM", rim_shape(r, w), STEEL))
    zc = r if z is None else z
    for x in xs:
        for side in (-1, 1):
            M = g.T(x, side * (y_out - w / 2), zc)
            put(asm, tyre, M)
            put(asm, rim, M)


def lattice(asm: Asm, kit: Kit, prefix: str, p0, u, n, W: float, a0: float, a1: float, chord_r: float,
            lace_r: float, color=BOOM_YELLOW) -> int:
    """A square lattice section along u from a0 to a1 (from p0): 4 chords at (±W/2 along n, ±W/2 across y) and a
    zigzag of diagonals on each face (one diagonal shape, placed again and again). Returns the number of parts."""
    p0, u, n = (np.asarray(v, float) for v in (p0, u, n))
    y = np.array([0.0, 1.0, 0.0])
    length = a1 - a0
    chord = kit.tube(f"{prefix} CHORD", chord_r, length, color)
    corners = [(+1, +1), (+1, -1), (-1, -1), (-1, +1)]
    count = 0
    for cn, cy in corners:
        put(asm, chord, along_frame(p0 + a0 * u + cn * W / 2 * n + cy * W / 2 * y, u))
        count += 1
    bays = max(2, int(round(length / W)))
    b = length / bays
    dl = math.hypot(b, W)
    cut_end = chord_r * dl / W          # the diagonal starts on the chord's surface, not its middle line
    lace = kit.tube(f"{prefix} LACING", lace_r, dl - 2 * cut_end, color)
    faces = [((+1, +1), (+1, -1)), ((-1, +1), (-1, -1)), ((+1, +1), (-1, +1)), ((+1, -1), (-1, -1))]
    for i in range(bays):
        for c1, c2 in faces:
            s, e = (c1, c2) if i % 2 == 0 else (c2, c1)
            ps = p0 + (a0 + i * b) * u + s[0] * W / 2 * n + s[1] * W / 2 * y
            pe = p0 + (a0 + (i + 1) * b) * u + e[0] * W / 2 * n + e[1] * W / 2 * y
            d = unit(pe - ps)
            put(asm, lace, along_frame(ps + cut_end * d, d))
            count += 1
    return count


def sheave_groove(r: float) -> tuple[float, float]:
    """(groove radius, rope-centre radius) of a sheave of outer radius r."""
    rr = max(6.0, 0.06 * r)
    return rr, r - 1.2 * rr


def sheave_part(name: str, centre, r: float, width: float, color=STEEL) -> Part:
    """A head or block sheave about y through ``centre`` (model coordinates)."""
    rr, rp = sheave_groove(r)
    s = g.sheave(rp, rr, width=width)
    M = g.Frame(np.asarray(centre, float), (1, 0, 0), (0, 1, 0))
    return Part(name, g.xform(s, M), color)


class _Seg:
    """A straight or a round piece of a rope's middle line (what ``geom.route_wire`` reads)."""

    def __init__(self, kind, start, end, centre=None):
        self.kind = kind
        self.start, self.end = np.asarray(start, float), np.asarray(end, float)
        self.centre = None if centre is None else np.asarray(centre, float)
        if kind == "line":
            self.length = float(np.linalg.norm(self.end - self.start))
            self.start_tangent = unit(self.end - self.start)
        else:
            r = float(np.linalg.norm(self.start - self.centre))
            a = math.acos(max(-1.0, min(1.0, float(unit(self.start - self.centre) @ unit(self.end - self.centre)))))
            self.length = r * a
            n = unit(np.cross(self.start - self.centre, self.end - self.centre))
            self.start_tangent = unit(np.cross(n, self.start - self.centre))

    def point(self, s: float) -> np.ndarray:
        if self.kind == "line":
            return self.start + self.start_tangent * s
        u = self.start - self.centre
        r = float(np.linalg.norm(u))
        n = unit(np.cross(u, self.end - self.centre))
        t = s / r
        return self.centre + u * math.cos(t) + np.cross(n, u) * math.sin(t)


class _Route:
    def __init__(self, segments):
        self.segments = segments


def hook_block(sheave_c, sheave_r: float, d0: float, block_h: float, block_w: float, rope_r: float,
               name: str = "HOOK BLOCK") -> tuple:
    """The hook block hanging under a head sheave centre (model coordinates, CAD pose): the block (cheek plates with
    its sheaves, one solid), the hook (shank + bowl, one solid; its saddle at sheave - d0, plumb under the sheave
    centre) and the hoist rope from the head sheave's bottom down to the block. Returns (block, hook, rope) Parts
    and the hook point."""
    s = np.asarray(sheave_c, float)
    hook_z = s[2] - d0
    top = hook_z + block_h
    body_h = 0.58 * block_h
    t = 0.42 * block_w
    body = g.fuse(g.box(s[0] - block_w / 2, -t / 2, top - body_h, block_w, t, body_h),
                  g.cyl(0.42 * block_w, 0.8 * t, (s[0], -0.4 * t, top - 0.42 * body_h), (0, 1, 0)))
    trunnion = g.box(s[0] - 0.18 * block_w, -0.3 * t, top - body_h - 0.08 * block_h, 0.36 * block_w, 0.6 * t,
                     0.08 * block_h + 1.0)
    block = Part(name, g.fuse(body, trunnion), HOOK_RED)
    tb = 0.075 * block_h                                  # the hook's bar radius
    R = 0.13 * block_h + tb                               # its bowl's middle line
    cz = hook_z + R - tb
    neck_top = top - body_h - 0.08 * block_h
    shank = g.cyl(0.8 * tb, neck_top - (cz + R) + 0.5 * tb, (s[0], 0.0, cz + R - 0.5 * tb), (0, 0, 1))
    bowl = g.torus_piece((s[0], 0.0, cz), (0, -1, 0), (s[0], 0.0, cz + R), 290.0, tb)
    tip_a = math.radians(90.0 - 290.0)          # the bar runs from the top towards +x and round
    tip = g.sphere(tb, (s[0] + R * math.cos(tip_a), 0.0, cz + R * math.sin(tip_a)))
    hook = Part(f"{name} HOOK", g.fuse(shank, bowl, tip), STEEL)
    rr, rp = sheave_groove(sheave_r)
    rope_r = min(rope_r, 0.85 * rr)
    x_t = s[0] + rp                                       # the rope leaves the sheave here, straight down
    # straight down from the sheave, round its top (a quarter turn) and a little back along the boom: one bar
    c = np.array([s[0], 0.0, s[2]])
    route = _Route([_Seg("line", (x_t, 0.0, top - 0.3 * block_h), (x_t, 0.0, s[2])),
                    _Seg("arc", (x_t, 0.0, s[2]), (s[0], 0.0, s[2] + rp), c),
                    _Seg("line", (s[0], 0.0, s[2] + rp), (s[0] - 0.6 * sheave_r, 0.0, s[2] + rp))])
    rope = Part("HOIST ROPE", g.route_solid(route, rope_r), ROPE)
    return block, hook, rope, (float(s[0]), 0.0, float(hook_z))


def hook_tree(parent: Asm, sheave_c, sheave_r: float, d0: float, block_h: float, block_w: float, rope_r: float,
              swings: int = 1) -> Asm:
    """HOOK SWING.ASM (+ HOOK SWING 2.ASM) holding the rope and HOOK BLOCK.ASM, added to ``parent``."""
    block, hook, rope, _hp = hook_block(sheave_c, sheave_r, d0, block_h, block_w, rope_r)
    swing = Asm("HOOK SWING.ASM")
    put(parent, swing)
    inner = swing
    if swings == 2:
        inner = Asm("HOOK SWING 2.ASM")
        put(swing, inner)
    put(inner, rope)
    hb = Asm("HOOK BLOCK.ASM")
    put(inner, hb)
    put(hb, block)
    put(hb, hook)
    return hb


BOX_GAP = C.BOX_GAP
box_half = C.box_half


def box_shapes(xs, beam_w: float, beam_h: float, beam_z: float, width: float) -> tuple:
    """(outer shapes, the beams' channels) of the outrigger boxes at ``xs`` (both beams of a pair side by side)."""
    gap, wall = BOX_GAP, 0.08 * beam_w
    half = width / 2
    outers, holes = [], []
    for x_box in xs:
        L = 2 * box_half(beam_w)
        H = beam_h + 2 * gap + 2 * wall
        outers.append(g.box(x_box - L / 2, -half, beam_z - H / 2, L, width, H))
        holes += [g.box(x_box + sx * (beam_w / 2 + gap / 2) - beam_w / 2 - gap, -half - 10, beam_z - beam_h / 2 - gap,
                        beam_w + 2 * gap, width + 20, beam_h + 2 * gap) for sx in (-1, 1)]
    return outers, holes


def frame_with_boxes(frame, xs, beam_w: float, beam_h: float, beam_z: float, width: float):
    """A chassis frame the outrigger beams run through: the frame and the boxes as one solid, the beams' channels cut
    through both (task 0214, bug hunt 0209 row 17: the beams ran through a solid frame, up to 190 mm deep)."""
    outers, holes = box_shapes(xs, beam_w, beam_h, beam_z, width)
    return one(g.cut(g.fuse(frame, *outers), *holes))


def outrigger_set(root: Asm, kit: Kit, prefix: str, xs, side_x: float, pad_in: float, ext: float, beam_z: float,
                  beam_w: float, beam_h: float, pad_z0: float, pad_r: float, carrier: Asm, width: float,
                  color=CARRIER_GREY, boxes: bool = True):
    """Four two-stage outrigger beams + jacks (``prefix`` "OUTRIGGER" / "STABILISER"): the carrier gets a box per
    pair (both beams side by side, the left one at +x) unless the chassis frame holds them (``boxes`` False,
    ``frame_with_boxes``), each beam's sub-assembly holds its second stage and the jack. ``ext`` = the stroke of each
    stage (the joints' range). Names as ``classes`` writes the joints."""
    leg = "JACK" if prefix == "OUTRIGGER" else "STABILISER LEG"
    gap, wall = BOX_GAP, 0.08 * beam_w
    half = width / 2
    if boxes:
        outers, holes = box_shapes(xs, beam_w, beam_h, beam_z, width)
        for k, outer in enumerate(outers):
            put(carrier, Part(f"{prefix} BOX", g.cut(outer, *holes[2 * k:2 * k + 2]), color))
    s1_len = width - 160.0
    for fr, x_box in zip("FR", xs):
        for side in "LR":
            sy = 1.0 if side == "L" else -1.0
            x = x_box + (0.5 if side == "L" else -0.5) * side_x
            a1 = Asm(f"{prefix} BEAM {fr}{side}.ASM")
            put(root, a1)
            # stage 1: from its inner end to the carrier's side (retracted), hollow
            y_out1 = sy * (half + 30.0)
            y_in1 = y_out1 - sy * s1_len
            y0, y1 = sorted((y_in1, y_out1))
            s1 = g.cut(g.box(x - beam_w / 2, y0, beam_z - beam_h / 2, beam_w, y1 - y0, beam_h),
                       g.box(x - beam_w / 2 + wall, y0 - 10, beam_z - beam_h / 2 + wall, beam_w - 2 * wall,
                             y1 - y0 + 20, beam_h - 2 * wall))
            put(a1, Part(f"{prefix} BEAM {fr}{side}", s1, color))
            a2 = Asm(f"{prefix} BEAM {fr}{side} 2.ASM")
            put(a1, a2)
            # stage 2: inside stage 1, out to the jack at pad_in
            w2, h2 = beam_w - 2 * wall - 2 * gap, beam_h - 2 * wall - 2 * gap
            y_out2 = sy * (pad_in - 0.55 * pad_r)
            y_in2 = y_out1 - sy * (s1_len - 2 * wall - 60.0)
            y0, y1 = sorted((y_in2, y_out2))
            s2 = g.box(x - w2 / 2, y0, beam_z - h2 / 2, w2, y1 - y0, h2)
            # jack housing radius: clear of stage 1's outer end when retracted (task 0214: 22 mm into it on AT-250/500)
            jr = min(0.45 * pad_r, pad_in - (half + 30.0) - 20.0)
            housing = g.cyl(jr, beam_h + 350.0, (x, sy * pad_in, beam_z - beam_h / 2 - 150.0), (0, 0, 1))
            arm = g.box(x - w2 / 2, min(sy * pad_in, y_out2) - (5 if sy > 0 else 0), beam_z - h2 / 2,
                        w2, abs(sy * pad_in - y_out2) + 5, h2)
            hous_bore = g.cyl(jr - 0.18 * jr, beam_h + 400.0, (x, sy * pad_in, beam_z - beam_h / 2 - 160.0),
                              (0, 0, 1))
            put(a2, Part(f"{prefix} BEAM {fr}{side} STAGE 2", g.cut(g.fuse(s2, arm, housing), hous_bore), color))
            a3 = Asm(f"{leg} {fr}{side}.ASM")
            put(a2, a3)
            rod_r = jr - 0.18 * jr - 4.0
            bottom = beam_z - beam_h / 2 - 150.0                       # the housing's lower end
            rod_len = (bottom - pad_z0) + pad_z0 + beam_h * 0.8        # stays in the housing at full stroke
            rod = g.cyl(rod_r, rod_len, (x, sy * pad_in, pad_z0 + 0.12 * pad_r), (0, 0, 1))
            pad = g.cyl(pad_r, 0.12 * pad_r, (x, sy * pad_in, pad_z0), (0, 0, 1))
            put(a3, Part(f"{leg} {fr}{side}", rod, CHROME))
            put(a3, Part(f"{leg} PAD {fr}{side}", pad, PAD_ORANGE))
    return s1_len


# ---------------------------------------------------------------------------------------------------------------------
# Mass groups, writing

def group_cogs(root: Asm, groups: dict) -> dict:
    """Group -> centre of volume [x, y, z] in m of the parts under the group's ``parts`` (sub-assembly or part names
    on their path), less those under its ``exclude``."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    acc = {k: [0.0, np.zeros(3)] for k in groups}
    props: dict = {}
    for node, _uid, W, _label, path in g.walk(root):
        if not isinstance(node, Part):
            continue
        names = [c.node.name for c in path]
        for k, gd in groups.items():
            if any(nm in gd["parts"] for nm in names) and not any(nm in gd.get("exclude", ()) for nm in names):
                if id(node) not in props:
                    gp = GProp_GProps()
                    BRepGProp.VolumeProperties_s(node.shape, gp)
                    c = gp.CentreOfMass()
                    props[id(node)] = (gp.Mass(), np.array([c.X(), c.Y(), c.Z(), 1.0]))
                v, c = props[id(node)]
                acc[k][0] += v
                acc[k][1] += v * (W @ c)[:3]
                break
    out = {}
    for k, (v, m) in acc.items():
        if v <= 0:
            raise ValueError(f"mass group '{k}' has no parts")
        out[k] = (m / v / 1000.0).tolist()
    return out


def count_parts(root: Asm) -> int:
    return g.count_parts(root)


def write_step(root: Asm, path: str) -> None:
    """The STEP file, without the faces' 2D parameter curves (OpenCascade's reader makes them again; the file is half
    the size)."""
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_Controller
    STEPControl_Controller.Init_s()          # sets the defaults once; the setting below must come after it
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    was = Interface_Static.IVal_s("write.surfacecurve.mode")
    Interface_Static.SetIVal_s("write.surfacecurve.mode", 0)
    try:
        g.write_step(root, path)
    finally:
        Interface_Static.SetIVal_s("write.surfacecurve.mode", was)
