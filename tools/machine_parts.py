"""Machine details shared by the invented test machines (task 0122): profile rails and their guide blocks, servo and
spindle motors, T-slots, edge clamps, bearing caps, the STEP writer with the one-solid check. Plain OpenCascade shapes
in mm, each one solid, made with ``fresing_render/demo_model/geom.py`` and ``tools/model_details.py``.

Used by make_test_mill.py, make_test_toolpath.py, make_test_gantry.py, make_test_atc.py, make_test_4axis.py and
make_test_5axis.py. Nothing of a real machine.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from fresing_render.demo_model import geom as g  # noqa: E402
from model_details import chamfer, chamfered_rect, hex_prism, socket_screw  # noqa: E402,F401

GREY, BLUE, STEEL, DARK = (0.55, 0.57, 0.6), (0.075, 0.267, 0.486), (0.8, 0.8, 0.82), (0.25, 0.27, 0.3)
ALU = (0.75, 0.76, 0.78)
BLACK = (0.1, 0.1, 0.11)
RAIL_STEEL = (0.68, 0.7, 0.72)
SCREW_BLACK = (0.12, 0.12, 0.13)
LIGHT_GREY = (0.86, 0.87, 0.88)          # covers and guards (RAL 7035-ish)

# a profile rail 20 wide, 16 high (x: width, y: height from its foot), with the side grooves of a ball rail
RAIL_W, RAIL_H = 20.0, 16.0
_RAIL = [(-10.0, 0.0), (10.0, 0.0), (10.0, 7.0), (8.5, 9.0), (10.0, 11.0), (10.0, 16.0), (-10.0, 16.0), (-10.0, 11.0),
         (-8.5, 9.0), (-10.0, 7.0)]
# its guide block: straddles the rail with 1 mm all round, 4 mm above the rail's foot; its back is 22 from the foot
BLOCK_BACK = 22.0
_BLOCK = [(-17.0, 4.0), (-11.0, 4.0), (-11.0, 17.0), (11.0, 17.0), (11.0, 4.0), (17.0, 4.0), (17.0, BLOCK_BACK),
          (-17.0, BLOCK_BACK)]


def on(shape, origin, width, along):
    """A shape made in local coordinates (x = width, y = height, z = along) placed at ``origin``: local x along
    ``width``, local z along ``along`` (local y = along x width)."""
    return g.xform(shape, g.Frame(origin, width, along))


def rail(length: float):
    """A profile rail along local z (0 .. length), its foot on local y = 0, centred on local x = 0."""
    return g.polygon_prism(_RAIL, length)


def guide_block(length: float = 50.0, z0: float | None = None):
    """A guide block round ``rail`` (local coordinates as the rail), local z ``z0`` .. ``z0 + length`` (centred on 0
    when ``z0`` is None), the ends chamfered."""
    z0 = -length / 2 if z0 is None else z0
    b = g.polygon_prism(_BLOCK, length, g.T(0, 0, z0))
    return chamfer(b, 2.0, lambda p: abs(p[1] - BLOCK_BACK) < 1e-6 and abs(abs(p[0]) - 17.0) < 1e-6)


def servo_motor(size: float = 70.0, length: float = 120.0):
    """A servo motor along +z, its flange face on z = 0: a square flange, a body with chamfered corners, a rear cap
    and a connector on its side (+x)."""
    fl = g.polygon_prism(chamfered_rect(-size / 2, -size / 2, size, size, size * 0.12), 12.0)
    s2 = size - 8.0
    body = g.polygon_prism(chamfered_rect(-s2 / 2, -s2 / 2, s2, s2, s2 * 0.2), length - 30.0, g.T(0, 0, 12.0))
    cap = g.polygon_prism(chamfered_rect(-s2 / 2 + 4, -s2 / 2 + 4, s2 - 8, s2 - 8, s2 * 0.2), 18.0,
                          g.T(0, 0, length - 18.0))
    plug = g.box(s2 / 2 - 1.0, -12.0, length - 52.0, 16.0, 24.0, 26.0)
    pilot = g.cyl(size * 0.3, 4.0, (0, 0, -4.0))
    return g.fuse(fl, body, cap, plug, pilot)


def tslot(length: float, centre, along=(1.0, 0.0, 0.0), top: float = 0.0, open_w: float = 14.0,
          wide: float = 24.0, depth: float = 20.0):
    """The cutter of a T-slot along ``along`` through ``centre`` (its middle), the slot's top at ``top`` (world z):
    an opening ``open_w`` wide and half ``depth`` deep, the wide part below it."""
    h = depth / 2
    prof = [(-open_w / 2, 1.0), (-open_w / 2, -h), (-wide / 2, -h), (-wide / 2, -depth), (wide / 2, -depth),
            (wide / 2, -h), (open_w / 2, -h), (open_w / 2, 1.0)]
    a = g.D_(along)
    width = (-a[1], a[0], 0.0)
    origin = (centre[0] - a[0] * length / 2, centre[1] - a[1] * length / 2, top)
    # local x = width (across the slot), local y = up, local z = along
    m = g.Frame(origin, width, a)
    if m[2, 1] < 0:                               # make local y point up
        m = g.Frame(origin, (-width[0], -width[1], 0.0), a)
    return g.xform(g.polygon_prism(prof, length), m)


def toe_clamp(e: float, base: float, top: float, width: float = 36.0, reach: float = 34.0, hole_at: float = 18.0):
    """A low toe clamp for a face at y = ``e`` (the stock on the -y side), at x = 0, standing on z = ``base``: its
    nose on the face (8 mm lower than its top), its screw hole ``hole_at`` mm out."""
    prof = [(e, base), (e + reach, base), (e + reach, top), (e + 8.0, top), (e, top - 8.0)]
    body = g.xform(g.polygon_prism(prof, width), g.Frame((-width / 2, 0, 0), (0, 1, 0), (1, 0, 0)))
    body = chamfer(body, 2.0, lambda p: abs(p[1] - (e + reach)) < 1e-6)
    return g.cut(body, g.cyl(6.6, top - base + 10.0, (0, e + hole_at, base - 5.0)))


def bearing_cap(r_out: float, r_bolts: float, thick: float, bolts: int = 6, bolt: int = 8):
    """A round bearing cap along +z (0 .. thick) with a bolt circle of socket heads (ISO 4762) on it and a boss."""
    _af, _k, dk, k, s, _m = (13, 5.3, 13, 8, 6, 6.8) if bolt == 8 else (10, 4.0, 10, 6, 5, 5.2)
    cap = g.fuse(g.cyl(r_out, thick), g.cyl(r_out * 0.55, thick + 4.0))
    heads = []
    for i in range(bolts):
        a = 2 * math.pi * (i + 0.5) / bolts
        x, y = r_bolts * math.cos(a), r_bolts * math.sin(a)
        heads.append(g.cut(g.cyl(dk / 2, k * 0.7, (x, y, thick)), g.xform(hex_prism(s, k), g.T(x, y, thick + k * 0.3))))
    return g.fuse(cap, *heads)


def one_solid(name: str, shape):
    n = g.solids(shape)
    if n != 1:
        raise RuntimeError(f"{name}: {n} solids (a test model part is one solid)")
    return shape


def part(name: str, shape, color=None):
    return g.Part(name, one_solid(name, shape), color)


def asm(name: str, *children) -> g.Asm:
    """An assembly of (node) or (node, (x, y, z)) or (node, 4 x 4 matrix) children."""
    a = g.Asm(name)
    for c in children:
        if isinstance(c, tuple):
            node, where = c
            a.add(node, where if getattr(where, "shape", None) == (4, 4) else g.T(*where))
        else:
            a.add(c)
    return a


def write(root: g.Asm, path: str) -> None:
    g.write_step(root, path)


# ---------------------------------------------------------------------------
# task 0249: the larger vertical machining centre (shared with task 0250's mills)
# ---------------------------------------------------------------------------

ENCLOSURE_GREY = (0.82, 0.83, 0.84)      # sheet metal of an enclosure (RAL 7035-ish, a shade darker than covers)
COVER_GREY = (0.6, 0.62, 0.64)           # way-cover sheet steel
TRAY_GREY = (0.45, 0.47, 0.5)            # the chip tray
SCREEN = (0.05, 0.06, 0.08)


def rail_along(length: float, start, along, up):
    """A profile rail from ``start`` (its foot's middle at the start) ``length`` along ``along``, its height towards
    ``up`` (the three are square to each other)."""
    a, u = g.D_(along), g.D_(up)
    width = tuple(np.cross(u, a))                      # local y (height) = along x width  ->  width = up x along
    return on(rail(length), start, width, a)


def block_on(length: float, at, along, up):
    """A guide block (``guide_block``) round a rail laid with ``rail_along(.., along, up)``, its middle at ``at`` (on
    the rail's foot line); its back is ``BLOCK_BACK`` from the foot along ``up``."""
    a, u = g.D_(along), g.D_(up)
    width = tuple(np.cross(u, a))
    return on(guide_block(length), at, width, a)


def way_cover_section(length: float, half_width: float, z_base: float, z_top: float, y_back: float,
                      slope_deg: float = 2.0, t: float = 3.0, towards: float = -1.0):
    """One section of a telescopic way cover lying along y: a sheet-steel hat – a gable roof falling ``slope_deg`` to
    both sides (it sheds coolant sideways) and two skirts down to ``z_base`` – ``t`` thick, open at both ends. Its
    roof's edges at ``z_top``, ``half_width`` out from x = 0; it runs from ``y_back`` ``length`` towards ``towards``
    (-1: to -y, +1: to +y). Nested sections: each 2 t narrower and lower than the one round it (a gap of t)."""
    w, tan = half_width, math.tan(math.radians(slope_deg))
    peak = z_top + w * tan
    prof = [(-w, z_base), (-w, z_top), (0.0, peak), (w, z_top), (w, z_base), (w - t, z_base), (w - t, z_top - t),
            (0.0, peak - t), (-w + t, z_top - t), (-w + t, z_base)]
    s = g.polygon_prism(prof, length)                 # local (x, y) = world (x, z), extruded along local z
    start = y_back if towards < 0 else y_back + length
    m = g.Frame((0.0, start, 0.0), (1, 0, 0), (0, -1, 0))        # local z -> -y, local y -> +z
    return g.xform(s, m)


def sliding_door(x0: float, x1: float, z0: float, z1: float, y_back: float, thick: float = 16.0, frame: float = 60.0,
                 handle_x: float | None = None, handle_z=(380.0, 780.0), handle_r: float = 10.0,
                 handle_out: float = 30.0, sides=None):
    """A sliding door in the plane y = ``y_back`` .. ``y_back - thick`` (its front towards -y): a sheet frame
    ``frame`` wide round a window opening (drawn open, like clear glass; ``sides``: (left, right) widths of the frame
    instead), and a vertical handle bar (Ø 2 r) at ``handle_x`` standing ``handle_out`` in front of the door on two
    feet."""
    yf = y_back - thick
    fl, fr = sides or (frame, frame)
    door = g.box(x0, yf, z0, x1 - x0, thick, z1 - z0)
    win = g.box(x0 + fl, yf - 1.0, z0 + frame + 40.0, x1 - x0 - fl - fr, thick + 2.0, z1 - z0 - 2 * frame - 120.0)
    door = g.cut(door, win)
    if handle_x is None:
        return door
    yc = yf - handle_out + handle_r
    za, zb = handle_z
    bar = g.cyl(handle_r, zb - za, (handle_x, yc, za))
    feet = [g.box(handle_x - 8.0, yc, z - 8.0, 16.0, yf - yc + 1.0, 16.0) for z in (za + 30.0, zb - 30.0)]
    return g.fuse(door, bar, *feet)


def bt40_holder_with_end_mill(stick: float = 38.0, gauge: float = 120.0, d: float = 10.0):
    """A BT40-like holder with a flat end mill Ø ``d`` (its tip at z = 0) along +z: the cutter, a collet nut Ø32, a
    body Ø44 tapering to the flange Ø63.5 with its V groove and two drive slots; the flange's top (the gauge line) at
    z = ``gauge`` – the taper above it sits inside the spindle and is not drawn."""
    cutter = g.cyl(d / 2, stick)
    nut = g.cyl(16.0, 14.0, (0.0, 0.0, stick - 2.0))
    body = g.revolve([(0.0, stick + 12.0), (17.0, stick + 12.0), (22.0, stick + 30.0), (22.0, gauge - 26.0),
                      (0.0, gauge - 26.0)])
    fl = gauge - 26.0
    flange = g.revolve([(0.0, fl), (31.75, fl), (31.75, fl + 8.0), (27.5, fl + 13.0), (31.75, fl + 18.0),
                        (31.75, gauge), (0.0, gauge)])
    slots = [g.box(x, -8.0, gauge - 8.0, 10.0, 16.0, 9.0) for x in (-32.0, 22.0)]
    return g.cut(g.fuse(cutter, nut, body, flange), *slots)
