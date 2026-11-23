"""Study 0306 - writes the two invented test vehicles as STEP files (real size, mm) + a points JSON each.

usage: python make_vehicles.py <out_dir> [car|truck|both]     (CHECK=0 skips the overlap check)

Everything stands in the CAD pose in the vehicle frame of spec.py (x forward, y left, z up, origin on the ground
under the front axle's middle); the STEP's assembly children carry the identity matrix, so a part's mesh is where
it is in the vehicle. Part names carry the side: "Front L Tyre", "Front R Upright", "Rear L Spring" ...
Every part is ONE solid. Invented and generic: no real make or model.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)

from fresing_render.demo_model import geom as G  # noqa: E402
from spec import CAR, TRUCK, mm  # noqa: E402

Y = (0.0, 1.0, 0.0)
X = (1.0, 0.0, 0.0)
Z = (0.0, 0.0, 1.0)
BLACK, GREY, SILVER = (0.08, 0.08, 0.09), (0.35, 0.36, 0.38), (0.78, 0.8, 0.82)
TYRE, SPRING, STEEL = (0.1, 0.1, 0.1), (0.95, 0.8, 0.15), (0.45, 0.47, 0.5)
DZ = lambda v: np.array([0.0, 0.0, v])  # noqa: E731


def pt(p, side=1):
    """A hard point (m, left side) -> mm array, mirrored for side -1."""
    return np.array(mm((p[0], side * p[1], p[2])), float)


def at_y(p, y):
    p = np.array(p, float)
    p[1] = y
    return p


def eye(p, r, w, d=Y):
    """Round eye (cylinder) of width w centred on p along d."""
    return G.cyl(r, w, np.array(p, float) - G.D_(d) * w / 2, d)


# ------------------------------------------------------------------------------------------------ wheels
def tyre(c, r_out, r_in, w):
    ch = 0.12 * (r_out - r_in)
    h = w / 2
    prof = [(r_in, -h), (r_out - ch, -h), (r_out, -h + ch), (r_out, h - ch), (r_out - ch, h), (r_in, h)]
    return G.revolve(prof, c, Y)


def rim(c, rim_r, w):
    """Barrel ring + a dished disc with 5 holes + a hub, one solid."""
    c = np.array(c, float)
    ring_w = 0.6 * w
    ring = G.tube(rim_r - 2, rim_r - 17, ring_w, c - np.array([0, ring_w / 2, 0]), Y)
    dw = 0.12 * rim_r + 8
    disc = G.cyl(rim_r - 10, dw, c - np.array([0, dw / 2, 0]), Y)
    holes = []
    for k in range(5):
        a = 2 * math.pi * k / 5
        hc = c + np.array([0.6 * rim_r * math.cos(a), -30.0, 0.6 * rim_r * math.sin(a)])
        holes.append(G.cyl(0.2 * rim_r, 60, hc, Y))
    hub = G.cyl(0.3 * rim_r, 90, c - np.array([0, 45, 0]), Y)
    return G.fuse(ring, G.cut(disc, *holes), hub)


def coil(p0, p1, r, wire, turns):
    """A coil spring (a helix swept with a round wire: one solid) from p0 to p1."""
    d = np.array(p1, float) - np.array(p0, float)
    pitch = (float(np.linalg.norm(d)) - 2 * wire) / turns
    return G.xform(G.sweep_round(G._helix_edge(r, wire, pitch, turns), wire), G.on_axis(p0, d))


def damper(p0, p1, r=22.0):
    p0, p1 = np.array(p0, float), np.array(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    u = (p1 - p0) / L
    return G.fuse(G.cyl(r, 0.55 * L, p0, u), G.cyl(0.55 * r, 0.5 * L, p0 + u * 0.5 * L, u),
                  eye(p0, 0.9 * r, 70, X), G.cyl(r * 0.9, 20, p1 - u * 20, u))


def aarm(a, b, out, r_eye=20.0, w=36.0, h=18.0):
    """A-arm: two beams from the inner pivots to the outer joint, round bushes along x at the inner pivots."""
    a, b, out = (np.array(v, float) for v in (a, b, out))
    return G.fuse(G.beam(a, out, w, h), G.beam(b, out, w, h), G.sphere(26, out),
                  eye(a, r_eye, 60, X), eye(b, r_eye, 60, X))


class Collect:
    def __init__(self, name):
        self.asm = G.Asm(name)
        self.parts = {}
        self.pts = {}

    def add(self, name, shape, color):
        self.parts[name] = shape
        self.asm.add(G.Part(name, shape, color))

    def points(self, axle_name, S, side, ax):
        for k, v in ax.points.items():
            self.pts[f"{axle_name} {S} {k}"] = [round(c, 4) for c in (v[0], side * v[1], v[2])]


# ------------------------------------------------------------------------------------------------ car
def car_body():
    b = CAR.body
    front_x = 1000 * b["front"]
    rear_x = 1000 * (CAR.rear_x - b["rear"])
    half = 1000 * b["width"] / 2
    floor = 460.0               # spec floor 0.42 + 3 cm: the trailing arm's eye clears the body
    lower = G.box(rear_x, -half, floor, front_x - rear_x, 2 * half, 1000 - floor)
    cabin = G.box(-3300, -800, 1000, 3400, 1600, 1000 * b["roof"] - 1000)
    body = G.fuse(lower, cabin)
    cuts = []
    for ax in CAR.axles:
        for s in (1, -1):
            c = pt(ax.points["wheel"], s)
            y0 = 400.0 if s > 0 else -1100.0
            cuts.append(G.cyl(1000 * (ax.wheel_r + 0.05), 700, (c[0], y0, c[2]), Y))
            cuts.append(G.box(c[0] - 420, y0, 0, 840, 700, 740))   # wheel well for the springs and arms
    return G.cut(body, *cuts)


def build_car():
    C = Collect("Test car")
    C.add("Body", car_body(), (0.15, 0.3, 0.6))
    fr, rr = CAR.axles
    racks = []
    for side, S in ((1, "L"), (-1, "R")):
        for ax, A in ((fr, "Front"), (rr, "Rear")):
            C.points(A, S, side, ax)
            w = pt(ax.points["wheel"], side)
            C.add(f"{A} {S} Tyre", tyre(w, 1000 * ax.wheel_r, 1000 * ax.rim_r, 1000 * ax.tyre_w), TYRE)
            C.add(f"{A} {S} Rim", rim(w, 1000 * ax.rim_r, 1000 * ax.tyre_w), SILVER)
        p = {k: pt(v, side) for k, v in fr.points.items()}
        lo, up, wc = p["lca_out"], p["uca_out"], p["wheel"]
        stub0 = lo + (up - lo) * (wc[2] - lo[2]) / (up[2] - lo[2])
        C.add(f"Front {S} Upright", G.fuse(G.rod(lo, up, 25), G.rod(stub0, at_y(wc, wc[1] - side * 60), 28),
                                           G.beam(stub0 - DZ(60), p["tie_out"], 24, 16),
                                           G.sphere(30, lo), G.sphere(30, up)), GREY)
        C.add(f"Front {S} Lower arm", aarm(p["lca_in_f"], p["lca_in_r"], lo), BLACK)
        C.add(f"Front {S} Upper arm", aarm(p["uca_in_f"], p["uca_in_r"], up, 16, 30, 14), BLACK)
        C.add(f"Front {S} Coil over", damper(p["spring_low"], p["spring_top"]), GREY)
        C.add(f"Front {S} Spring", coil(p["spring_low"] + DZ(40), p["spring_top"] - DZ(30), 40, 4, 8), SPRING)
        C.add(f"Front {S} Tie rod", G.fuse(G.rod(p["tie_in"], p["tie_out"], 10), G.sphere(14, p["tie_in"]),
                                           G.sphere(14, p["tie_out"])), STEEL)
        racks.append(p["tie_in"])
        q = {k: pt(v, side) for k, v in rr.points.items()}
        wc, a = q["wheel"], q["arm_pivot"]
        k1 = np.array([a[0] - 100, side * 620.0, 390.0])     # the arm runs inboard of the tyre (y < 692 mm, clear of the spring too)
        k2 = at_y(wc, side * 620.0)
        C.add(f"Rear {S} Trailing arm", G.fuse(eye(a, 25, 60), G.beam(a, k1, 40, 50), G.beam(k1, k2, 40, 50),
                                               G.sphere(25, k1), G.sphere(25, k2),
                                               G.rod(k2, at_y(wc, side * 750.0), 30)), BLACK)
        C.add(f"Rear {S} Damper", damper(q["spring_low"], q["spring_top"]), GREY)
        C.add(f"Rear {S} Spring", coil(q["spring_low"] + DZ(40), q["spring_top"] - DZ(30), 40, 4, 7), SPRING)
    C.add("Steering rack", G.tube(22, 16, abs(racks[0][1] - racks[1][1]), racks[1], Y), GREY)
    return C


# ------------------------------------------------------------------------------------------------ truck
def leaf_pack(front, rear, seat, n=5, t=12.0, width=80.0):
    """Leaf spring through three points (parabola in x-z), n leaves under each other, eyes at the ends, one solid."""
    f, r, s = (np.array(v, float) for v in (front, rear, seat))
    cz = np.polyfit([f[0], s[0], r[0]], [f[2], s[2], r[2]], 2)
    leaves = []
    for k in range(n):
        if k == 0:
            xa, xb = f[0], r[0]
        else:
            frac = 1.0 - 0.17 * k
            xa, xb = s[0] + (f[0] - s[0]) * frac, s[0] + (r[0] - s[0]) * frac
        xx = np.linspace(xb, xa, 15)                       # rear -> front
        zz = np.polyval(cz, xx) - k * t
        poly = [(x, z + t / 2) for x, z in zip(xx, zz)] + [(x, z - t / 2) for x, z in zip(xx[::-1], zz[::-1])]
        leaves.append(G.polygon_prism(poly, width, G.T(0, s[1] + width / 2, 0) @ G.Rot(X, 90)))
    eyes = [G.tube(30, 16, width, np.array([x, s[1] - width / 2, np.polyval(cz, x)]), Y) for x in (f[0], r[0])]
    pack = G.fuse(*leaves, *eyes)
    holes = [G.cyl(16, width + 20, np.array([x, s[1] - width / 2 - 10, np.polyval(cz, x)]), Y) for x in (f[0], r[0])]
    return G.cut(pack, *holes)             # the leaf's flat end filled the eye: bore it out for the pin


def build_truck():
    b = TRUCK.body
    fr, rr = TRUCK.axles
    C = Collect("Test truck")
    fh, fw = 1000 * b["frame_h"], 1000 * b["frame_w"] / 2
    rail_h, tk = 150.0, 12.0
    x_front, x_rear = 1000 * b["front"], 1000 * (rr.x - b["rear"])
    shack = [(1000 * a.points["shackle_top"][0], 1000 * a.points["shackle_top"][2]) for a in (fr, rr)]
    rails = []
    for side in (1, -1):                       # C channel: web inside, flanges open outwards
        ya, yb = (fw - 40, fw + 40) if side > 0 else (-fw - 40, -fw + 40)
        wy = ya if side > 0 else yb - tk
        rail = G.fuse(G.box(x_rear, wy, fh - rail_h, x_front - x_rear, tk, rail_h),
                      G.box(x_rear, ya, fh - rail_h, x_front - x_rear, yb - ya, tk),
                      G.box(x_rear, ya, fh - tk, x_front - x_rear, yb - ya, tk))
        rails.append(G.cut(rail, *[G.cyl(16.5, 120, (x, ya - 20, z), Y) for x, z in shack]))
    cross = [G.box(x - 40, -(fw - 40), fh - rail_h, 80, 2 * (fw - 40), rail_h) for x in (1300, -1000, -3000, -6000, -7100)]
    C.add("Frame", G.fuse(*rails, *cross), (0.12, 0.12, 0.13))
    prof = [(1200, fh), (1200, 2300), (750, 3200), (-1000, 3200), (-1000, fh)]
    cab = G.polygon_prism(prof, 2400, G.T(0, 1200, 0) @ G.Rot(X, 90))
    C.add("Cab", G.cut(cab, *[G.cyl(1000 * (fr.wheel_r + 0.08), 700, (0, y0, 1000 * fr.wheel_r), Y) for y0 in (500, -1200)]),
          (0.85, 0.85, 0.88))
    bx = G.box(-1150 - 1000 * b["box_len"], -1250, fh, 1000 * b["box_len"], 2500, 1000 * b["height"] - fh)
    C.add("Box body", G.cut(bx, *[G.cyl(1000 * (rr.wheel_r + 0.08), 800, (1000 * rr.x, y0, 1000 * rr.wheel_r), Y)
                                  for y0 in (400, -1200)]), (0.9, 0.55, 0.1))

    # axles: front I-beam between the kingpins, rear tube housing with a differential bulge
    p = {k: pt(v) for k, v in fr.points.items()}
    kp = abs(p["kingpin"][1])
    L = 2 * (kp - 35)
    ibeam = G.fuse(G.box(-50, -L / 2, 440, 100, L, 20), G.box(-50, -L / 2, 580, 100, L, 20), G.box(-10, -L / 2, 460, 20, L, 120))
    pads = [G.box(-60, s * 430 - 60, 600, 120, 120, 1000 * fr.points["leaf_seat"][2] - 54 - 600) for s in (1, -1)]
    C.add("Front Axle", G.fuse(ibeam, *pads), (0.2, 0.2, 0.22))
    rp = pt(rr.points["wheel"])
    axle = G.fuse(G.tube(70, 55, 1320, (rp[0], -660, rp[2]), Y), G.sphere(220, (rp[0], 0, rp[2])))
    rpads = [G.box(rp[0] - 60, s * 430 - 60, rp[2] + 60, 120, 120, 1000 * rr.points["leaf_seat"][2] - 54 - rp[2] - 60)
             for s in (1, -1)]
    C.add("Rear Axle", G.fuse(axle, *rpads), (0.2, 0.2, 0.22))

    for side, S in ((1, "L"), (-1, "R")):
        for ax, A in ((fr, "Front"), (rr, "Rear")):
            C.points(A, S, side, ax)
            w = pt(ax.points["wheel"], side)
            off = 1000 * (ax.tyre_w / 2 + 0.02)
            if ax.twin:
                cs = [(at_y(w, w[1] - side * off), "inner"), (at_y(w, w[1] + side * off), "outer")]
            else:
                cs = [(w, "")]
            for c, io in cs:
                tag = f"{A} {S}" + (f" {io}" if io else "")
                C.add(f"{tag} Tyre", tyre(c, 1000 * ax.wheel_r, 1000 * ax.rim_r, 1000 * ax.tyre_w), TYRE)
                C.add(f"{tag} Rim", rim(c, 1000 * ax.rim_r, 1000 * ax.tyre_w), SILVER)
            q = {k: pt(v, side) for k, v in ax.points.items()}
            C.add(f"{A} {S} Leaf spring", leaf_pack(q["leaf_front"], q["leaf_rear"], q["leaf_seat"]), (0.3, 0.3, 0.3))
            lr, st = q["leaf_rear"], q["shackle_top"]
            plates = [G.beam(at_y(lr, lr[1] + d), at_y(st, st[1] + d), 30, 12, up=Y) for d in (-52, 52)]
            pin = lambda base: G.cyl(15, 116, at_y(base, base[1] - 58), Y)   # noqa: E731
            C.add(f"{A} {S} Shackle", G.fuse(*plates, pin(lr), pin(st)), STEEL)
            lf = q["leaf_front"]
            hp = [G.box(lf[0] - 50, lf[1] + s * 52 - 6, lf[2] - 30, 100, 12, 150) for s in (1, -1)]
            C.add(f"{A} {S} Spring hanger", G.fuse(*hp, pin(lf)), STEEL)
        q = {k: pt(v, side) for k, v in fr.points.items()}
        kpt = q["kingpin"]
        C.add(f"Front {S} Stub axle", G.fuse(G.cyl(35, 260, kpt - DZ(130), Z), G.rod(kpt, at_y(kpt, q["wheel"][1] - side * 50), 30),
                                             G.beam(kpt, np.array([-200.0, kpt[1] - side * 20, kpt[2]]), 30, 30)),
              (0.25, 0.25, 0.28))
    C.add("Track rod", G.rod(np.array([-200.0, -kp + 35, 520.0]), np.array([-200.0, kp - 35, 520.0]), 15), STEEL)
    return C


# ------------------------------------------------------------------------------------------------ main
def check(parts, pairs):
    """Volume of the common part of the given pairs (name fragments), mm^3; returns the overlapping ones."""
    bad = []
    for a_pat, b_pat in pairs:
        for na, sa in parts.items():
            for nb, sb in parts.items():
                if a_pat in na and b_pat in nb and na != nb:
                    try:
                        v = G.volume(G.common(sa, sb))
                    except Exception:
                        v = -1
                    if v > 1.0:
                        bad.append((na, nb, round(v)))
    return bad


CAR_PAIRS = [("Tyre", k) for k in ("Body", "arm", "Upright", "Spring", "Coil", "Damper", "Tie rod", "rack", "Rim")] + \
            [("Rim", k) for k in ("arm", "Upright", "Body", "Spring", "Coil", "Damper")]
TRUCK_PAIRS = [("Tyre", k) for k in ("Frame", "Box", "Cab", "Axle", "Leaf", "Shackle", "hanger", "Stub", "Track", "Rim")] + \
              [("Rim", k) for k in ("Axle", "Stub", "Leaf", "Frame", "Track")]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    which = sys.argv[2] if len(sys.argv) > 2 else "both"
    os.makedirs(out, exist_ok=True)
    for key, build, name, pairs in (("car", build_car, "test_car", CAR_PAIRS), ("truck", build_truck, "test_truck", TRUCK_PAIRS)):
        if which not in ("both", key):
            continue
        t0 = time.time()
        C = build()
        path = os.path.join(out, name + ".step")
        G.write_step(C.asm, path)
        with open(os.path.join(out, name + ".points.json"), "w") as f:
            json.dump({"unit": "m", "frame": "x forward, y left, z up, origin on the ground under the front axle middle",
                       "points": C.pts}, f, indent=1)
        t1 = time.time()
        print(f"{name}: {G.count_parts(C.asm)} parts, {os.path.getsize(path) / 1e3:.0f} KB, made+written {t1 - t0:.1f} s")
        if os.environ.get("CHECK", "1") == "1":
            bad = check(C.parts, pairs)
            print(f"  overlap check {time.time() - t1:.1f} s: {len(bad)} overlapping pairs")
            for b in bad:
                print("  OVERLAP", b)


if __name__ == "__main__":
    main()
