"""Write the finishes test model (task 0274, shapes of study 0270): a board of 23 invented sample parts – one per
finish – and an invented headphone-like set, as ONE STEP assembly. Nothing of a real product: no maker, no brand.

    python tools/make_test_finishes.py tests/data/test_finishes.step

Sizes in mm, Z up. Each sample sits on a 140 mm grid (6 columns, 4 rows, the board's front-left corner at 0, 0):

  KNOB …     knobs Ø20 x 15 with 0.8 mm chamfers (knurls, the grip pattern: round faces with their own axis)
  CAP …      domed caps Ø40 (spun rings)        SHAFT …    a shaft Ø22 with a shoulder (faced end, turned rings)
  BUSHING …  a half bushing Ø60 / Ø40 x 50 (the bore of a honed part is seen)
  CUP …      a double-curved cup shell Ø70     BLOCK …    a block 80 x 50 x 40 with 3 mm chamfers
  PLATE …    plates 110 x 110 x 3              WAY …      a machine way 120 x 45 x 30
  GRIP …     a handle Ø30 x 110                 DISC …     a disc Ø52 x 1 (grille, speaker cloth)
  BAND …     an arch 30 mm wide standing on its ends (soft-touch)

Task 0318 adds two rows: carbon fibre on a cup, a tube with a cone, a U-shaped folded panel, a free-form hood and a flat
plate; perlage on a disc; and a rust row (bare steel, cast iron, painted, galvanized, stainless, aluminium).

  TUBE …     a tube Ø40 / Ø36 x 90 with a cone to Ø28 over 30 mm, lying along x
  PANEL …    a U-shaped folded sheet 2 mm thick: a 44 mm base, two 32 mm legs, bends R 6 / 8 mm, 70 mm long
  HOOD …     a free-form shell 2 mm thick, 100 x 80, curved both ways (one smooth B-spline face on top)

The headset (front left of the board): a headband, two yokes, cups, cushions, grilles, caps and a knob.
Each part is ONE solid (a part of several solids loses its colour in the importer)."""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from fresing_render.demo_model import geom as g  # noqa: E402
import model_details as md  # noqa: E402


def knob():
    c = 0.8
    return g.revolve([(0, 0), (10 - c, 0), (10, c), (10, 15 - c), (10 - c, 15), (0, 15)])


def cap():
    """Ø40, 2 mm rim, a shallow dome (sphere R 101 mm) up to 4.5 mm, 0.5 mm chamfer on the rim."""
    R, rim, top = 101.0, 2.0, 4.5
    zc = top - R

    def z(r):
        return zc + math.sqrt(R * R - r * r)
    return g.revolve([(0, 0), (20, 0), (20, rim), (19.5, z(19.5)), ("arc", (10, z(10)), (0, top))])


CUP_RO, CUP_T = 37.0, 2.5


def cup():
    """A double-curved shell: outer sphere R 37 cut at Ø70 (25 mm deep), 2.5 mm wall, a flat land Ø40 on top."""
    Ro, t = CUP_RO, CUP_T
    zc = 25.0 - Ro
    ro = math.sqrt(Ro * Ro - zc * zc)
    Ri = Ro - t
    ri = math.sqrt(Ri * Ri - zc * zc)
    h = zc + math.sqrt(Ro * Ro - 20.0 ** 2)
    rh = math.sqrt(Ri * Ri - (h - t - zc) ** 2)

    def mid(R, r0, r1):
        a0, a1 = math.asin(r0 / R), math.asin(r1 / R)
        a = (a0 + a1) / 2
        return (R * math.sin(a), zc + R * math.cos(a))
    return g.revolve([(ri, 0), (ro, 0), ("arc", mid(Ro, ro, 20.0), (20.0, h)), (0, h), (0, h - t), (rh, h - t),
                      ("arc", mid(Ri, rh, ri), (ri, 0))])


CUP_TOP = 25.0 - CUP_RO + math.sqrt(CUP_RO ** 2 - 20.0 ** 2)     # height of the cup's flat land (mm)


def block():
    return md.chamfer(g.box(-40, -25, 0, 80, 50, 40), 3.0, lambda p: True)


def shaft():
    c = 1.0
    return g.revolve([(0, 0), (11 - c, 0), (11, c), (11, 60), (10.5, 60.5), (8, 60.5), (8, 100 - c), (8 - c, 100),
                      (0, 100)], d=(1, 0, 0))


def plate():
    return md.chamfer(g.box(-55, -55, 0, 110, 110, 3), 0.8, lambda p: abs(p[2] - 3) < 1e-6)


def bushing():
    """Ø60 / Ø40 x 50 tube cut in half along its axis (y), so the bore is seen from above."""
    t = g.tube(30, 20, 50, d=(0, 1, 0), p=(0, -25, 0))
    return g.cut(t, g.box(-40, -40, 0, 80, 80, 40))


def way():
    return md.chamfer(g.box(-60, -22.5, 0, 120, 45, 30), 1.5, lambda p: True)


def grip():
    r, L, f = 15.0, 110.0, 4.0
    s45, c45 = math.sin(math.radians(45)), math.cos(math.radians(45))
    return g.revolve([(0, 0), (r - f, 0), ("arc", (r - f + f * s45, f - f * c45), (r, f)), (r, L - f),
                      ("arc", (r - f + f * s45, L - f + f * c45), (r - f, L)), (0, L)], d=(1, 0, 0))


def band(r: float = 88.0):
    """A 180° arc of r to r + 6 mm radius, 30 mm wide, in the xz plane (its ends at x = ±(r + 3), z = 0)."""
    s = g.revolve([(r, -15), (r + 6, -15), (r + 6, 15), (r, 15)], angle=180.0)
    return g.xform(s, g.Rot((1, 0, 0), 90))


def yoke():
    s = g.revolve([(40, -4), (44, -4), (44, 4), (40, 4)], angle=180.0)
    return g.xform(s, g.Rot((0, 1, 0), -90) @ g.Rot((0, 0, 1), -90))


def cushion():
    return g.revolve([(19, 0), ("arc", (27, -8), (35, 0)), ("arc", (27, 8), (19, 0))])


def disc():
    return g.cyl(26, 1.0)


def tube():
    return g.revolve([(18, 0), (20, 0), (20, 90), (14, 120), (12, 120), (18, 90)], p=(-60, 0, 20), d=(1, 0, 0))


def panel():
    """A U-shaped folded sheet: base 44 mm between the bends, legs up to 40 mm, bends R 6 inside / 8 outside."""
    s45 = math.sin(math.radians(45))

    def arc(cx, cy, r, sx):
        return (cx + sx * r * s45, cy - r * s45)
    prof = [(-22, 0), (22, 0), ("arc", arc(22, 8, 8, 1), (30, 8)), (30, 40), (28, 40), (28, 8),
            ("arc", arc(22, 8, 6, 1), (22, 2)), (-22, 2), ("arc", arc(-22, 8, 6, -1), (-28, 8)), (-28, 40), (-30, 40),
            (-30, 8), ("arc", arc(-22, 8, 8, -1), (-22, 0))]
    return g.xform(g.prism(prof, 70.0), g.T(0, 35, 0) @ g.Rot((1, 0, 0), 90))


def hood():
    """A free-form shell 2 mm thick: arched sections of changing height lofted smooth (one double-curved top face)."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.gp import gp_Pnt
    ts = BRepOffsetAPI_ThruSections(True, False, 1e-6)
    for x in (-50.0, -25.0, 0.0, 25.0, 50.0):
        top = 6.0 + 20.0 * (1.0 - (x / 62.0) ** 2) + 3.0 * math.sin(x / 30.0)
        w = 40.0 - 6.0 * (x / 50.0) ** 2
        prof = [(-w, 0.0), ("arc", (0.0, top), (w, 0.0)), (w, -2.0), ("arc", (0.0, top - 2.0), (-w, -2.0))]
        ts.AddWire(g._wire2d(prof, plane=lambda u, v, x=x: gp_Pnt(x, u, v + 2.0)))
    ts.Build()
    return ts.Shape()


#: the board: (part name, shape, colour, z lift, turn) in grid order (6 per row); the tour gives each its finish
BOARD = [
    ("KNOB DIAMOND KNURL", knob), ("KNOB STRAIGHT KNURL", knob), ("GRIP HANDLE", grip), ("CAP SPUN", cap),
    ("SHAFT FACED", shaft), ("BUSHING HONED", bushing),
    ("CUP CROSS-HATCH", cup), ("DISC SPEAKER CLOTH", disc), ("DISC GRILLE", disc), ("PLATE TREAD", plate),
    ("PLATE PERFORATED", plate), ("PLATE EXPANDED", plate),
    ("WAY SCRAPED", way), ("BAND SOFT-TOUCH", lambda: band(44.0)), ("BLOCK BEAD-BLASTED", block), ("BLOCK SHOT-BLASTED", block),
    ("BLOCK HAMMERTONE", block), ("BLOCK WRINKLE", block),
    ("PLATE ANTI-SKID", plate), ("CUP VDI 30", cup), ("CUP LEATHER", cup), ("PLATE SPANGLE", plate),
    ("BLOCK AS-CAST", block),
    # task 0318
    ("CUP CARBON", cup), ("TUBE CARBON", tube), ("PANEL CARBON", panel), ("HOOD CARBON", hood),
    ("PLATE CARBON", plate), ("DISC PERLAGE", lambda: g.cyl(40, 3.0)),
    ("PLATE RUST BARE STEEL", plate), ("BLOCK RUST CAST IRON", block), ("PLATE RUST PAINTED", plate),
    ("PLATE RUST GALVANIZED", plate), ("PLATE RUST STAINLESS", plate), ("PLATE RUST ALUMINIUM", plate),
]
PITCH = 140.0
COLOURS = {"KNOB": (0.47, 0.47, 0.47), "CAP": (0.78, 0.78, 0.78), "CUP": (0.16, 0.27, 0.55),
           "BLOCK": (0.71, 0.71, 0.71), "SHAFT": (0.71, 0.71, 0.71), "PLATE": (0.59, 0.59, 0.59),
           "BUSHING": (0.67, 0.67, 0.67), "WAY": (0.67, 0.67, 0.67), "GRIP": (0.12, 0.12, 0.12),
           "BAND": (0.16, 0.16, 0.16), "DISC": (0.08, 0.08, 0.08), "YOKE": (0.75, 0.75, 0.75),
           "CUSHION": (0.12, 0.12, 0.12), "TUBE": (0.1, 0.1, 0.1), "PANEL": (0.1, 0.1, 0.1),
           "HOOD": (0.1, 0.1, 0.1)}


def headset():
    """The invented headphone-like set: cups on x = ±91, their centres 44 mm below the band's ends."""
    hs = g.Asm("HEADSET")
    P = {n: g.Part(f"HEADSET {n}", fn(), COLOURS[n.split()[0]]) for n, fn in
         (("BAND", band), ("YOKE", yoke), ("CUP", cup), ("CUSHION", cushion), ("DISC", disc), ("CAP", cap),
          ("KNOB", knob))}
    hs.add(P["BAND"])
    z0 = -44.0
    for side in (1, -1):
        out = g.Rot((0, 1, 0), 90 * side)
        hs.add(P["YOKE"], g.T(91 * side, 0, z0) @ (g.Rot((0, 0, 1), 180) if side < 0 else g.T()))
        hs.add(P["CUP"], g.T(79 * side, 0, z0) @ out)
        hs.add(P["CUSHION"], g.T(72 * side, 0, z0) @ out)
        hs.add(P["DISC"], g.T(76 * side, 0, z0) @ out)
        hs.add(P["CAP"], g.T((79 + CUP_TOP) * side, 0, z0) @ out)
    hs.add(P["KNOB"], g.T(79 + CUP_TOP + 4.5, 0, z0) @ g.Rot((0, 1, 0), 90))
    return hs


def make(path: str) -> None:
    root = g.Asm("TEST.FINISHES")
    for i, (name, fn) in enumerate(BOARD):
        j = i if i < 23 else i + 1                     # task 0318's two rows start on a row of their own
        x, y = PITCH * (j % 6), PITCH * (3 - j // 6)
        root.add(g.Part(name, fn(), COLOURS[name.split()[0]]), g.T(x, y, 0.0))
    root.add(headset(), g.T(-260.0, 200.0, 140.0) @ g.Rot((0, 0, 1), -20))
    g.write_step(root, path)


if __name__ == "__main__":
    make(sys.argv[1] if len(sys.argv) > 1 else "tests/data/test_finishes.step")
    print("written")
