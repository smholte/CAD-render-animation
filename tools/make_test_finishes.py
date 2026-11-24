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
]
PITCH = 140.0
COLOURS = {"KNOB": (0.47, 0.47, 0.47), "CAP": (0.78, 0.78, 0.78), "CUP": (0.16, 0.27, 0.55),
           "BLOCK": (0.71, 0.71, 0.71), "SHAFT": (0.71, 0.71, 0.71), "PLATE": (0.59, 0.59, 0.59),
           "BUSHING": (0.67, 0.67, 0.67), "WAY": (0.67, 0.67, 0.67), "GRIP": (0.12, 0.12, 0.12),
           "BAND": (0.16, 0.16, 0.16), "DISC": (0.08, 0.08, 0.08), "YOKE": (0.75, 0.75, 0.75),
           "CUSHION": (0.12, 0.12, 0.12)}


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
        x, y = PITCH * (i % 6), PITCH * (3 - i // 6)
        root.add(g.Part(name, fn(), COLOURS[name.split()[0]]), g.T(x, y, 0.0))
    root.add(headset(), g.T(-260.0, 200.0, 140.0) @ g.Rot((0, 0, 1), -20))
    g.write_step(root, path)


if __name__ == "__main__":
    make(sys.argv[1] if len(sys.argv) > 1 else "tests/data/test_finishes.step")
    print("written")
