"""The demo's offshore substation (task 0166): invented, of a usual kind for a wind park of this size – a four-legged
jacket on piles, a topside with three decks under cladding, a helideck on top, a pedestal crane, a cable deck the
array and export cables come up to through J-tubes along the jacket's legs, a boat landing with its ladder, deck
floodlights and yellow marine lights on the corners. Nothing of it is a real substation.

Frame: mm, the jacket's axis = z, sea level (the waterline) z 0, the seabed at ``turbine.SEABED_Z``; the boat landing
on the -y face. Every part is one solid (CLAUDE.md section 8); the same Part placed several times is one mesh.
"""

from __future__ import annotations

import math

import numpy as np

from . import geom as g
from . import occ
from . import turbine as tb
from .geom import Asm, Part, Rot, T

LEG_TOP = 11000.0                 # half the legs' spacing at the top of the jacket (a square)
BATTER = 0.1                      # the legs lean out 1 : 10
LEG_R = 900.0
JACKET_TOP = 18000.0              # the jacket's top (the topside sits on it)
LEVELS = (-28000.0, -12000.0, 3000.0, JACKET_TOP - 1000.0)      # horizontal frames
BRACE_R = 400.0
PILE_R, PILE_UP = 1100.0, 4000.0  # pile sleeves at the legs' feet
DECKS = (20000.0, 26000.0, 32000.0)      # cable deck, main deck, upper deck (tops)
ROOF = 38000.0
TOP_HALF = (18000.0, 15000.0)     # the topside's half length (x) and width (y)
DECK_T = 400.0
HELI_Z = 40500.0
HELI_R = 11000.0                  # the helideck's octagon (circumradius), over the +x end
CRANE_AT = (-12500.0, -11000.0)
J_TUBES = 6                       # array and export cables up the -y legs and faces
YELLOW = (0.93, 0.70, 0.05)
WHITE = (0.88, 0.89, 0.89)
GREY = (0.45, 0.47, 0.48)


def leg_xy(z: float) -> float:
    """Half the legs' spacing at height z (the legs lean out going down)."""
    return LEG_TOP + BATTER * (JACKET_TOP - z)


def _leg():
    """The (+x, +y) leg from below the seabed to the top; the other three are it turned 90° about z."""
    zb = tb.SEABED_Z - 2000.0
    a, b = leg_xy(zb), leg_xy(JACKET_TOP)
    return g.rod((a, a, zb), (b, b, JACKET_TOP + 600.0), LEG_R)


def _pile():
    """A pile sleeve beside the leg's foot, a short pile in it standing out of the seabed."""
    a = leg_xy(tb.SEABED_Z) + 2600.0
    z0 = tb.SEABED_Z - 1000.0
    sleeve = g.cyl(PILE_R + 150.0, PILE_UP, (a, a, z0 + 500.0))
    pile = g.cyl(PILE_R, PILE_UP + 1500.0, (a, a, z0))
    arms = [g.rod((leg_xy(z0 + h), leg_xy(z0 + h), z0 + h), (a, a, z0 + h), 250.0) for h in (1500.0, PILE_UP)]
    return occ.one_solid(g.fuse(sleeve, pile, *arms), "pile")


def _face_brace(z0: float, z1: float):
    """An X brace on the +x face between two levels."""
    a0, a1 = leg_xy(z0), leg_xy(z1)
    return occ.one_solid(g.fuse(g.rod((a0, -a0, z0), (a1, a1, z1), BRACE_R),
                                g.rod((a0, a0, z0), (a1, -a1, z1), BRACE_R)), "brace")


def _frame(z: float):
    """A horizontal frame at height z: the four sides and one diagonal pair."""
    a = leg_xy(z)
    c = [(a, a, z), (-a, a, z), (-a, -a, z), (a, -a, z)]
    tubes = [g.rod(c[k], c[(k + 1) % 4], BRACE_R * 0.9) for k in range(4)]
    tubes += [g.rod(c[0], c[2], BRACE_R * 0.8), g.rod(c[1], c[3], BRACE_R * 0.8)]
    return occ.one_solid(g.fuse(*tubes), "frame")


def _deck(z_top: float, hole: bool = False):
    hx, hy = TOP_HALF
    d = g.box(-hx, -hy, z_top - DECK_T, 2 * hx, 2 * hy, DECK_T)
    if hole:                                    # the cable deck: open where the J-tubes come up
        d = g.cut(d, g.box(-6000.0, -hy - 10.0, z_top - DECK_T - 10.0, 12000.0, 4000.0, DECK_T + 20.0))
    return occ.one_solid(d, "deck")


def _columns():
    """The topside's frame: columns from the jacket top to the roof, edge beams under each deck."""
    hx, hy = TOP_HALF
    bits = []
    for x in (-hx + 400.0, -hx / 3.0, hx / 3.0, hx - 400.0):
        for y in (-hy + 400.0, 0.0, hy - 400.0):
            bits.append(g.box(x - 400.0, y - 400.0, JACKET_TOP + 600.0, 800.0, 800.0, ROOF - JACKET_TOP - 600.0))
    for z in DECKS:
        zb = z - DECK_T - 900.0
        bits += [g.box(-hx, -hy, zb, 2 * hx, 600.0, 901.0), g.box(-hx, hy - 600.0, zb, 2 * hx, 600.0, 901.0),
                 g.box(-hx, -hy, zb, 600.0, 2 * hy, 901.0), g.box(hx - 600.0, -hy, zb, 600.0, 2 * hy, 901.0),
                 g.box(-hx, -300.0, zb, 2 * hx, 600.0, 901.0)]
    # the transition from the four legs to the topside: a cross of girders on the jacket's top
    b = LEG_TOP
    bits += [g.box(-hx, -b - 700.0, JACKET_TOP, 2 * hx, 1400.0, 1301.0),
             g.box(-hx, b - 700.0, JACKET_TOP, 2 * hx, 1400.0, 1301.0),
             g.box(-b - 700.0, -hy, JACKET_TOP, 1400.0, 2 * hy, 1301.0),
             g.box(b - 700.0, -hy, JACKET_TOP, 1400.0, 2 * hy, 1301.0)]
    return occ.one_solid(g.fuse(*bits), "topside frame")


def _cladding():
    """The walls round the main and upper decks (a shell 150 thick) with louvre bands, and the roof."""
    hx, hy = TOP_HALF
    z0, z1 = DECKS[0] + 200.0, ROOF
    outer = g.box(-hx + 150.0, -hy + 150.0, z0, 2 * hx - 300.0, 2 * hy - 300.0, z1 - z0)
    inner = g.box(-hx + 300.0, -hy + 300.0, z0 - 10.0, 2 * hx - 600.0, 2 * hy - 600.0, z1 - z0 - 290.0)
    shell = g.cut(outer, inner)
    bands = []
    for z in (DECKS[1] - 2800.0, DECKS[2] - 2800.0, ROOF - 2800.0):         # louvre bands: grooves round the walls
        for k in range(-8, 9):
            x = k * 2000.0
            bands.append(g.box(x - 600.0, -hy + 100.0, z, 1200.0, 120.0, 1500.0))
            bands.append(g.box(x - 600.0, hy - 220.0, z, 1200.0, 120.0, 1500.0))
    door = g.box(-900.0, -hy + 100.0, DECKS[0] + 200.0, 1800.0, 220.0, 2600.0)
    return occ.one_solid(g.cut(shell, *bands, door), "cladding")


def _helideck():
    """An octagon on eight raked legs over the +x end of the roof, a safety net shelf round it."""
    cx, z = TOP_HALF[0] - HELI_R * 0.55, HELI_Z
    pts = [(cx + HELI_R * math.cos(math.radians(22.5 + 45.0 * k)), HELI_R * math.sin(math.radians(22.5 + 45.0 * k)))
           for k in range(8)]
    plate = g.polygon_prism(pts, 300.0, T(0, 0, z))
    shelf_pts = [(cx + (HELI_R + 1500.0) * math.cos(math.radians(22.5 + 45.0 * k)),
                  (HELI_R + 1500.0) * math.sin(math.radians(22.5 + 45.0 * k))) for k in range(8)]
    shelf = g.cut(g.polygon_prism(shelf_pts, 100.0, T(0, 0, z + 100.0)), g.polygon_prism(pts, 300.0, T(0, 0, z - 50.0)))
    legs = []
    for x, y in pts:
        fx = min(max(cx + 0.55 * (x - cx), -TOP_HALF[0] + 500.0), TOP_HALF[0] - 500.0)
        fy = min(max(0.55 * y, -TOP_HALF[1] + 500.0), TOP_HALF[1] - 500.0)
        legs.append(g.rod((fx, fy, ROOF - 10.0), (x * 0.92 + cx * 0.08, y * 0.92, z + 10.0), 250.0))
    return occ.one_solid(g.fuse(plate, shelf, *legs), "helideck")


def _crane():
    """A pedestal crane on the roof's -x, -y corner (fixed: it does not slew in the demo)."""
    x, y = CRANE_AT
    ped = g.cyl(1200.0, 3500.0, (x, y, ROOF))
    house = g.box(x - 2200.0, y - 1600.0, ROOF + 3500.0, 4400.0, 3200.0, 3000.0)
    boom = g.beam((x + 1500.0, y, ROOF + 5000.0), (x + 22000.0, y + 9000.0, ROOF + 14000.0), 900.0, 1100.0)
    return occ.one_solid(g.fuse(ped, house, boom), "crane")


def _j_tube(k: int):
    """J-tube k up the -y face: from a bell-mouth on the seabed beside the jacket's foot to the cable deck."""
    x = -5000.0 + 2000.0 * k
    zb = tb.SEABED_Z + 1500.0
    yb = -leg_xy(zb) - 3500.0
    y1 = -leg_xy(DECKS[0]) + 1200.0
    pts = [(x, yb - 2000.0, tb.SEABED_Z + 600.0), (x, yb, zb), (x, -leg_xy(zb + 6000.0) - 900.0, zb + 6000.0),
           (x, y1 - 900.0, DECKS[0] - DECK_T - 1600.0), (x, y1 - 900.0, DECKS[0] + 400.0)]
    tubes = [g.rod(a, b, 230.0) for a, b in zip(pts[:-1], pts[1:])]
    tubes += [g.sphere(230.0, p) for p in pts[1:-1]]
    bell = g.cone(500.0, 230.0, 900.0, pts[0], np.subtract(pts[1], pts[0]))
    return occ.one_solid(g.fuse(*tubes, bell), "j-tube")


def _boat_landing():
    """Two bumper tubes on the -y face's middle with brackets to the jacket, and the ladder up to the cable deck."""
    y = -leg_xy(0.0) - 2200.0
    tubes = []
    for x in (-900.0, 900.0):
        tubes.append(g.cyl(220.0, 9000.0, (x, y, -4000.0)))
        for z in (-3000.0, 3500.0):
            tubes.append(g.rod((x, y, z), (x, -leg_xy(z) + 50.0, z), 120.0))
    for z in (-3000.0, 3500.0):
        tubes.append(g.rod((-900.0, y, z), (900.0, y, z), 120.0))
    landing = occ.one_solid(g.fuse(*tubes), "boat landing")
    ladder = [g.box(s - 30.0, y + 400.0, -3000.0, 60.0, 70.0, DECKS[0] + 3000.0) for s in (-260.0, 260.0)]
    ladder += [g.rod((-260.0, y + 435.0, z), (260.0, y + 435.0, z), 14.0)
               for z in np.arange(-2700.0, DECKS[0] - 200.0, 300.0)]
    for z in np.arange(-2000.0, DECKS[0], 4000.0):
        ladder.append(g.box(-300.0, y + 470.0, z, 600.0, -leg_xy(z) - (y + 470.0) + 10.0, 80.0))
    return landing, occ.one_solid(g.fuse(*ladder), "ladder")


def _railing(z: float):
    hx, hy = TOP_HALF
    c = [(-hx + 100.0, -hy + 100.0), (hx - 100.0, -hy + 100.0), (hx - 100.0, hy - 100.0), (-hx + 100.0, hy - 100.0)]
    bits = []
    for (x0, y0), (x1, y1) in zip(c, c[1:] + c[:1]):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 1800.0))
        for t in np.linspace(0.0, 1.0, n + 1)[:-1]:
            bits.append(g.cyl(25.0, 1100.0, (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z)))
        for h in (550.0, 1100.0):
            bits.append(g.rod((x0, y0, z + h), (x1, y1, z + h), 25.0))
        bits.append(g.sphere(25.0, (x0, y0, z + 1100.0)))
        bits.append(g.sphere(25.0, (x0, y0, z + 550.0)))
    return occ.one_solid(g.fuse(*bits), "railing")


def _floodlight():
    """A deck floodlight: a bracket and a lamp box looking out and down (made at the origin, looking along -y)."""
    return occ.one_solid(g.fuse(g.box(-60.0, -60.0, 0.0, 120.0, 120.0, 700.0),
                                g.box(-350.0, -400.0, 600.0, 700.0, 340.0, 420.0)), "floodlight")


def substation(marine_light: Part | None = None) -> Asm:
    """The substation (``marine_light``: the turbines' lantern Part, so it is one mesh in the park)."""
    a = Asm("OFFSHORE SUBSTATION")
    leg = Part("JACKET LEG", occ.one_solid(_leg(), "leg"), YELLOW)
    pile = Part("PILE SLEEVE", _pile(), YELLOW)
    for k in range(4):
        R = Rot((0, 0, 1), 90.0 * k)
        a.add(leg, R)
        a.add(pile, R)
    for i, (z0, z1) in enumerate(zip(LEVELS[:-1], LEVELS[1:])):
        br = Part(f"JACKET BRACE {i + 1}", _face_brace(z0, z1), YELLOW)
        for k in range(4):
            a.add(br, Rot((0, 0, 1), 90.0 * k))
    for i, z in enumerate(LEVELS):
        a.add(Part(f"JACKET FRAME {i + 1}", _frame(z), YELLOW))
    for i, z in enumerate(DECKS):
        a.add(Part(f"TOPSIDE DECK {i + 1}", _deck(z, hole=i == 0), GREY))
    a.add(Part("TOPSIDE FRAME", _columns(), GREY))
    a.add(Part("CLADDING", _cladding(), WHITE))
    a.add(Part("HELIDECK", _helideck(), GREY))
    a.add(Part("CRANE PEDESTAL", _crane(), YELLOW))
    for k in range(J_TUBES):
        a.add(Part(f"J-TUBE SUBSTATION {k + 1}", _j_tube(k), YELLOW))
    landing, ladder = _boat_landing()
    a.add(Part("BOAT LANDING SUBSTATION", landing, YELLOW))
    a.add(Part("LADDER SUBSTATION", ladder, YELLOW))
    a.add(Part("RAIL SUBSTATION", _railing(DECKS[0])))
    lamp = Part("DECK LIGHT", _floodlight(), WHITE)
    hx, hy = TOP_HALF
    for x in (-hx + 3000.0, 0.0, hx - 3000.0):
        for y, turn in ((-hy + 600.0, 0.0), (hy - 600.0, 180.0)):
            a.add(lamp, T(x, y, ROOF) @ Rot((0, 0, 1), turn))
    if marine_light is not None:
        for sx in (-1, 1):
            for sy in (-1, 1):
                a.add(marine_light, T(sx * (hx - 800.0), sy * (hy - 800.0), DECKS[0]))
    a.info = {"top": ROOF, "helideck": HELI_Z, "half": TOP_HALF, "foot": leg_xy(tb.SEABED_Z) + 2600.0 + PILE_R}
    return a
