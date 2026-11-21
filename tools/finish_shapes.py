"""Study 0270 (finishes): the invented, generic shapes as ONE STEP file, so they come into the app through the real
importer (faces, round-face axes ``fr_axes``, coarse meshing) like any customer part.

    ~/venv/bin/python tools/finish_shapes.py <out.step>

Shapes (mm): a knob Ø20 x 15, a domed cap Ø40, a cup shell Ø70, a block 80 x 50 x 40 with chamfers, a shaft Ø22
with a shoulder, a plate 300 x 300 x 5, a half bushing (to see a bore), a machine way, a grip handle, a T-joint for a
weld seam, and an invented headphone-like set (headband, yokes, cups, cushions, grilles, caps, a knob). No brand, no
maker. Branch-only prototype; not part of the app."""

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
    """Ø40, 2.5 mm rim, a shallow dome (sphere R 101 mm) up to 4.5 mm, 0.5 mm chamfer on the rim."""
    R, rim, top = 101.0, 2.0, 4.5
    zc = top - R

    def z(r):
        return zc + math.sqrt(R * R - r * r)
    return g.revolve([(0, 0), (20, 0), (20, rim), (19.5, z(19.5)), ("arc", (10, z(10)), (0, top))])


def cup():
    """A double-curved shell: outer sphere R 37 cut at Ø70 (25 mm deep), 2.5 mm wall, a flat land Ø40 on top."""
    Ro, t = 37.0, 2.5
    zc = 25.0 - Ro                       # sphere centre below the rim plane
    ro = math.sqrt(Ro * Ro - zc * zc)    # = 35 at z = 0
    Ri = Ro - t
    ri = math.sqrt(Ri * Ri - zc * zc)
    h = zc + math.sqrt(Ro * Ro - 20.0 ** 2)          # a flat land Ø40 on top for the cap
    rh = math.sqrt(Ri * Ri - (h - t - zc) ** 2)

    def mid(R, r0, r1):
        a0, a1 = math.asin(r0 / R), math.asin(r1 / R)
        a = (a0 + a1) / 2
        return (R * math.sin(a), zc + R * math.cos(a))
    return g.revolve([(ri, 0), (ro, 0), ("arc", mid(Ro, ro, 20.0), (20.0, h)), (0, h), (0, h - t), (rh, h - t),
                      ("arc", mid(Ri, rh, ri), (ri, 0))])


CUP_TOP = 37.0 - 12.0 - 37.0 + math.sqrt(37.0 ** 2 - 20.0 ** 2)   # height of the cup's flat land (mm)


def block():
    s = g.box(-40, -25, 0, 80, 50, 40)
    return md.chamfer(s, 3.0, lambda p: True)


def shaft():
    c = 1.0
    return g.revolve([(0, 0), (11 - c, 0), (11, c), (11, 95), (10.5, 95.5), (8, 95.5), (8, 150 - c), (8 - c, 150),
                      (0, 150)], d=(1, 0, 0))


def plate():
    return md.chamfer(g.box(-150, -150, 0, 300, 300, 5), 1.0, lambda p: abs(p[2] - 5) < 1e-6)


def bushing():
    """Ø60 / Ø40 x 50 tube cut in half along its axis, so the bore is seen."""
    t = g.tube(30, 20, 50, d=(0, 1, 0), p=(0, -25, 0))
    return g.cut(t, g.box(-40, -40, -40, 80, 80, 40))


def way():
    s = g.box(-150, -22.5, 0, 300, 45, 30)
    return md.chamfer(s, 1.5, lambda p: True)


def grip():
    r, L = 15.0, 110.0
    return g.revolve([(0, 0), (r - 4, 0), ("arc", (r - 4 + 4 * math.sin(math.radians(45)), 4 - 4 * math.cos(math.radians(45))), (r, 4)),
                      (r, L - 4), ("arc", (r - 4 + 4 * math.sin(math.radians(45)), L - 4 + 4 * math.cos(math.radians(45))), (r - 4, L)),
                      (0, L)], d=(1, 0, 0))


def weld_base():
    return g.box(-75, -50, 0, 150, 100, 8)


def weld_web():
    return g.box(-75, -4, 8, 150, 8, 60)


def band():
    """Headband: a 180° arc of 88-94 mm radius, 30 mm wide, in the xz plane (its ends at x = ±91, z = 0)."""
    s = g.revolve([(88, -15), (94, -15), (94, 15), (88, 15)], angle=180.0)
    return g.xform(s, g.Rot((1, 0, 0), 90))


def yoke():
    """Half ring round a cup (axis x), radius 40-44, 8 wide, the top half."""
    s = g.revolve([(40, -4), (44, -4), (44, 4), (40, 4)], angle=180.0)      # in xy, from +x through +y to -x
    return g.xform(s, g.Rot((0, 1, 0), -90) @ g.Rot((0, 0, 1), -90))


def cushion():
    """Torus, minor radius 8, major 27, axis z."""
    return g.revolve([(19, 0), ("arc", (27, -8), (35, 0)), ("arc", (27, 8), (19, 0))])


def grille():
    return g.cyl(26, 1.0)


PARTS = [("KNOB", knob, (0.47, 0.47, 0.47)), ("CAP", cap, (0.78, 0.78, 0.78)), ("CUP", cup, (0.16, 0.27, 0.55)),
         ("BLOCK", block, (0.71, 0.71, 0.71)), ("SHAFT", shaft, (0.71, 0.71, 0.71)), ("PLATE", plate, (0.59, 0.59, 0.59)),
         ("BUSHING", bushing, (0.67, 0.67, 0.67)), ("WAY", way, (0.67, 0.67, 0.67)), ("GRIP", grip, (0.12, 0.12, 0.12)),
         ("WELD BASE", weld_base, (0.63, 0.63, 0.63)), ("WELD WEB", weld_web, (0.63, 0.63, 0.63)),
         ("BAND", band, (0.16, 0.16, 0.16)), ("YOKE", yoke, (0.75, 0.75, 0.75)), ("CUSHION", cushion, (0.12, 0.12, 0.12)),
         ("GRILLE", grille, (0.08, 0.08, 0.08))]


def headset(parts):
    """The invented headphone-like set: cups on x = ±91, their centres 44 mm below the band's ends."""
    hs = g.Asm("HEADSET")
    hs.add(parts["BAND"])
    z0 = -44.0
    for side in (1, -1):
        out = g.Rot((0, 1, 0), 90 * side)          # local z -> +x (right) / -x (left)
        hs.add(parts["YOKE"], g.T(91 * side, 0, z0) @ (g.Rot((0, 0, 1), 180) if side < 0 else g.T()))
        hs.add(parts["CUP"], g.T(79 * side, 0, z0) @ out)
        hs.add(parts["CUSHION"], g.T(72 * side, 0, z0) @ out)
        hs.add(parts["GRILLE"], g.T(76 * side, 0, z0) @ out)
        hs.add(parts["CAP"], g.T((79 + CUP_TOP) * side, 0, z0) @ out)
    hs.add(parts["KNOB"], g.T(79 + CUP_TOP + 4.5, 0, z0) @ g.Rot((0, 1, 0), 90))
    return hs


def make(path: str) -> None:
    parts = {name: g.Part(name, fn(), col) for name, fn, col in PARTS}
    root = g.Asm("FINISH STUDY")
    for i, (name, _fn, _c) in enumerate(PARTS):
        root.add(parts[name], g.T(400 * (i % 5), 400 * (i // 5), 0))
    root.add(headset(parts), g.T(0, -600, 0))
    g.write_step(root, path)


if __name__ == "__main__":
    make(sys.argv[1] if len(sys.argv) > 1 else "dist/finish_study.step")
    print("written")
