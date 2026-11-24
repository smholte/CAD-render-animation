"""Writes the invented stress-test assembly of the PC check "Stress" (task 0315).

    python stress_scene.py <out.step> [--small] [--revision B] [--json <info.json>]

An **invented offshore substation topside module**, about 10,000 placed parts at full size: primary steel (columns,
beams, braces with bolted end plates), three decks of gratings with clips, handrails, stairs and a ladder, two
transformer rooms (a transformer each: tank, corrugated fins, radiators, bushings, conservator, a bolted lid), two
switchgear rooms (lines of cabinets with doors, breakers and busbars), cable trays with their cables, a pipe rack
with flanged spools, valves and supports, HVAC units, a pedestal crane on the roof and a davit. About 40 % of the
placed parts are bolts, nuts and washers with ISO / DIN names, as a real assembly has them; subassemblies are named
the way Inventor writes them (``Name:1``), five to seven levels deep; a few parts have no useful name ("Part12").
Faces like a real model: lofted fins, blades, boom and cables are B-spline surfaces, castings (valve bodies, bushings,
the hook) are turned into B-splines, doors and tanks have filleted edges.

Joints-ready: ``<out>.joints.json`` beside the STEP lists the crane's slew, boom and hoist, the davit's slew and the
room doors (the importer's uids, mm), for ``pccheck/stress.py``. ``--revision B`` writes the same model with about
1 % of the placed parts changed (the model update line); its JSON says which.

Runs as its own program (Blender's Python with the bundled OpenCascade, like ``heavy_scene.py``), so its memory does
not count for the app. Uses the app's shape library ``demo_model/geom.py`` (loaded by its path). Nothing of any real
design: every size is made up; nothing of it is in the repository – it is written at run time and deleted after.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GEOM = os.path.join(os.path.dirname(HERE), "demo_model", "geom.py")


def _geom():
    name = "fresing_stress_geom"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, GEOM)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------------------------------------
# sizes
# ---------------------------------------------------------------------------------------------------------

FULL = dict(bays_x=6, bays_y=3, bay_x=6000.0, bay_y=8000.0, deck_h=6000.0, decks=3, cabinets=16, swg_rooms=2,
            tx_rooms=2, fins=8, radiators=6, tray_runs=6, cables=8, pipe_lines=8, spools=4, valves=12,
            hvac=4, stairs=1, lid_bolts=36, slew_bolts=40, lacings=20, grating=(1000.0, 3000.0))
SMALL = dict(bays_x=2, bays_y=1, bay_x=6000.0, bay_y=8000.0, deck_h=6000.0, decks=2, cabinets=3, swg_rooms=1,
             tx_rooms=1, fins=4, radiators=1, tray_runs=1, cables=3, pipe_lines=1, spools=2, valves=1,
             hvac=1, stairs=1, lid_bolts=8, slew_bolts=8, lacings=4, grating=(2000.0, 6000.0))

ROOT = "OSS-TOPSIDE-M01"
CRANE = "PEDESTAL CRANE PC-40"
DAVIT = "DAVIT DV-2"

STEEL = (0.86, 0.68, 0.12)          # offshore yellow
GREY = (0.55, 0.57, 0.6)
GALV = (0.68, 0.7, 0.72)
LIGHT = (0.82, 0.82, 0.8)           # RAL 7035-like
DARK = (0.2, 0.21, 0.23)
BLUE = (0.18, 0.32, 0.55)
RED = (0.7, 0.15, 0.12)
ORANGE = (0.9, 0.45, 0.1)
COPPER = (0.72, 0.45, 0.2)
BLACK = (0.08, 0.08, 0.09)


class Maker:
    """Builds the tree. Every unique part is one ``geom.Part``; placed parts are children with Inventor's
    occurrence names ``Name:n`` (counted per parent assembly)."""

    def __init__(self, size: dict, revision: str = "A", seed: int = 15):
        self.g = _geom()
        self.z = size
        self.rev = revision
        self.rnd = random.Random(seed)
        self.parts: dict = {}               # key -> Part (shared shapes)
        self.changed: list = []             # revision B: unique part names that changed
        self.nameless = 0
        self.nurbs = 0

    # --- tree helpers
    def asm(self, name: str):
        return self.g.Asm(name)

    def add(self, parent, node, M=None):
        n = 1 + sum(1 for c in parent.children if c.node is node or c.node.name == node.name)
        return parent.add(node, M, instance=f"{node.name}:{n}")

    def part(self, key, name: str, make, color=None, nurbs: bool = False):
        """A shared unique part, made once per ``key``."""
        if key in self.parts:
            return self.parts[key]
        shape = make()
        if nurbs:
            from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
            shape = BRepBuilderAPI_NurbsConvert(shape, True).Shape()
            self.nurbs += 1
        p = self.g.Part(name, shape, color)
        self.parts[key] = p
        return p

    def unnamed(self) -> str:
        self.nameless += 1
        return f"Part{self.nameless + 11}"

    # --- shapes
    def i_profile(self, h: float, b: float, tw: float, tf: float, r: float):
        """An I section (web along y) with root radii, as a closed (x, y) profile."""
        x0, y0 = b / 2, h / 2
        a = tw / 2
        k = r * (1 - math.sqrt(0.5))
        p = [(-x0, -y0), (x0, -y0), (x0, -y0 + tf), (a + r, -y0 + tf),
             ("arc", (a + k, -y0 + tf + k), (a, -y0 + tf + r)), (a, y0 - tf - r),
             ("arc", (a + k, y0 - tf - k), (a + r, y0 - tf)), (x0, y0 - tf), (x0, y0), (-x0, y0), (-x0, y0 - tf),
             (-a - r, y0 - tf), ("arc", (-a - k, y0 - tf - k), (-a, y0 - tf - r)), (-a, -y0 + tf + r),
             ("arc", (-a - k, -y0 + tf + k), (-a - r, -y0 + tf)), (-x0, -y0 + tf)]
        return p

    def member(self, p0, p1, prof, up=(0.0, 0.0, 1.0)):
        """An I member from p0 to p1 in its own part coordinates (along z), and the matrix that places it."""
        g = self.g
        import numpy as np
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        d = p1 - p0
        L = float(np.linalg.norm(d))
        up = np.asarray(up, float)
        if abs(up @ d) > 0.99 * L:
            up = np.array([0.0, 1.0, 0.0])
        x = np.cross(up, d / L)
        return L, g.Frame(p0, x, d)

    def hex_prism(self, s: float, h: float, z0: float = 0.0):
        g = self.g
        r = s / math.sqrt(3.0)
        pts = [(r * math.cos(math.radians(30 + 60 * i)), r * math.sin(math.radians(30 + 60 * i))) for i in range(6)]
        return g.polygon_prism(pts, h, g.T(0, 0, z0))

    def fillet(self, shape, r: float, vertical_only: bool = False):
        """Every edge of ``shape`` (or only its vertical ones) rounded with radius r."""
        from OCP.BRep import BRep_Tool
        from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS
        mk = BRepFilletAPI_MakeFillet(shape)
        ex = TopExp_Explorer(shape, TopAbs_EDGE)
        while ex.More():
            e = TopoDS.Edge(ex.Current())
            if vertical_only:
                from OCP.TopExp import TopExp
                p0, p1 = BRep_Tool.Pnt_s(TopExp.FirstVertex_s(e)), BRep_Tool.Pnt_s(TopExp.LastVertex_s(e))
                if abs(p0.X() - p1.X()) > 1e-6 or abs(p0.Y() - p1.Y()) > 1e-6:
                    ex.Next()
                    continue
            mk.Add(r, e)
            ex.Next()
        return mk.Shape()

    # --- fasteners (bolt along -z from its head at z = 0: the head sits on the face, the shank goes in)
    def bolt(self, d: int, L: int, cls: str = "8.8"):
        g = self.g

        def make():
            k = 0.65 * d
            head = self.hex_prism(1.6 * d, k)
            cham = g.cone(0.95 * 1.6 * d, 0.6 * d, 0.45 * k, (0, 0, k * 0.55))
            head = g.common(head, g.fuse(g.cyl(0.95 * 1.6 * d, k * 0.55), cham))
            return g.fuse(head, g.cyl(d / 2.0, L, (0, 0, 0), (0, 0, -1)))
        return self.part(("bolt", d, L), f"ISO 4017 M{d} x {L} - {cls} HDG", make, GALV)

    def nut(self, d: int):
        g = self.g
        return self.part(("nut", d), f"ISO 4032 M{d} - 8 HDG",
                         lambda: g.cut(self.hex_prism(1.6 * d, 0.8 * d), g.cyl(d / 2.0, 0.8 * d + 2, (0, 0, -1))),
                         GALV)

    def washer(self, d: int):
        g = self.g
        t = max(1.6, round(0.15 * d, 1))
        return self.part(("washer", d), f"ISO 7089 {d} - 200 HV HDG",
                         lambda: g.tube(1.05 * d, 0.54 * d, t), GALV)

    def screw(self, d: int, L: int):
        g = self.g

        def make():
            head = g.cut(g.cyl(0.75 * d, d), self.hex_prism(0.5 * d, 0.6 * d, 0.45 * d))
            return g.fuse(head, g.cyl(d / 2.0, L, (0, 0, 0), (0, 0, -1)))
        return self.part(("screw", d, L), f"ISO 4762 M{d} x {L} - 12.9", make, DARK)

    def stud(self, d: int, L: int):
        g = self.g
        return self.part(("stud", d, L), f"Stud bolt M{d} x {L} ASTM A193 B7",
                         lambda: g.cyl(d / 2.0, L, (0, 0, -L / 2.0)), DARK)

    def bolt_set(self, parent, M, d: int, grip: float, washers: int = 2):
        """Bolt + washers + nut through a grip of ``grip`` mm along -z of M (head at M's origin). ``washers``: 0 none,
        1 under the nut, 2 under the head too."""
        g = self.g
        wt = max(1.6, round(0.15 * d, 1))
        L = int(math.ceil((grip + washers * wt + 0.8 * d + 0.4 * d) / 10.0) * 10)
        z = 0.0
        if washers >= 2:
            self.add(parent, self.washer(d), M @ g.T(0, 0, 0))
            z = wt
        self.add(parent, self.bolt(d, L), M @ g.T(0, 0, z))
        below = 0.0
        if washers >= 1:
            self.add(parent, self.washer(d), M @ g.T(0, 0, -grip - wt))
            below = wt
        self.add(parent, self.nut(d), M @ g.T(0, 0, -grip - below - 0.8 * d))

    def grating_clip(self, parent, M):
        g = self.g
        clip = self.part("clip", "GRATING CLIP GC-40 HDG",
                         lambda: g.fuse(g.box(-20, -15, 0, 40, 30, 4), g.box(-20, -15, -30, 4, 30, 30)), GALV)
        self.add(parent, clip, M)
        self.add(parent, self.screw(8, 30), M @ g.T(0, 0, 4))

    # -----------------------------------------------------------------------------------------------------
    # the model
    # -----------------------------------------------------------------------------------------------------

    def build(self):
        z = self.z
        self.L = z["bays_x"] * z["bay_x"]
        self.W = z["bays_y"] * z["bay_y"]
        self.levels = [i * z["deck_h"] for i in range(z["decks"])]
        self.top = self.levels[-1] + z["deck_h"]
        root = self.asm(ROOT)
        self.add(root, self.primary_steel())
        names = ["CELLAR DECK", "MAIN DECK", "MEZZANINE DECK", "UPPER DECK"]
        for i, lev in enumerate(self.levels + [self.top]):
            name = (names[i] if i < len(self.levels) else "WEATHER DECK") + f" EL+{lev / 1000:.0f}"
            self.add(root, self.deck(name, i, lev), self.g.T(0, 0, lev))
        self.add(root, self.stairs(), self.g.T(0, 0, 0))
        crane = self.crane()
        self.add(root, crane, self.g.T(self.L * 0.25, self.W * 0.5, self.top))
        self.add(root, self.davit(), self.g.T(self.L - 1500, 600, self.top) @ self.g.Rot((0, 0, 1), 180))
        return root

    # --- primary steel (welded: columns, deck beams and braces; bolted: the secondary beams) -----------------
    def primary_steel(self):
        g, z = self.g, self.z
        a = self.asm("PRIMARY STEEL")
        cols = self.asm("COLUMNS")
        beams = self.asm("DECK BEAMS")
        secs = self.asm("SECONDARY BEAMS")
        braces = self.asm("BRACING")
        prof_c = self.i_profile(400, 300, 13.5, 24, 27)
        prof_b = self.i_profile(300, 300, 11, 19, 27)
        prof_s = self.i_profile(200, 100, 5.6, 8.5, 12)
        heights = self.levels + [self.top]
        n = 0
        xs = [i * z["bay_x"] for i in range(z["bays_x"] + 1)]
        ys = [j * z["bay_y"] for j in range(z["bays_y"] + 1)]
        for x in xs:
            for y in ys:
                for k in range(len(heights) - 1):
                    n += 1
                    Lc = heights[k + 1] - heights[k]
                    p = self.part(("col", n), f"HEB 400 - {Lc:.0f} ({n:03d})",
                                  self._copy(lambda: g.prism(prof_c, Lc)), STEEL)
                    self.add(cols, p, g.T(x, y, heights[k]))
                    cap = self.part(("capplate", n), f"PL25 SPLICE PLATE {n:03d}", self._copy(
                        lambda: g.box(-200, -200, 0, 400, 400, 25)), STEEL)
                    self.add(cols, cap, g.T(x, y, heights[k + 1] - 25))
        for h in heights:
            for y in ys:
                for i in range(len(xs) - 1):
                    n += 1
                    self._beam(beams, (xs[i] + 200, y, h - 150), (xs[i + 1] - 200, y, h - 150), prof_b, n)
            for x in xs:
                for j in range(len(ys) - 1):
                    n += 1
                    self._beam(beams, (x, ys[j] + 150, h - 150), (x, ys[j + 1] - 150, h - 150), prof_b, n)
            for x0, x1 in zip(xs[:-1], xs[1:]):           # secondary beams under the gratings, bolted to fin plates
                for j in range(len(ys) - 1):
                    n += 1
                    xm = (x0 + x1) / 2
                    L, M = self.member((xm, ys[j] + 160, h - 100), (xm, ys[j + 1] - 160, h - 100), prof_s)
                    p = self.part(("sec", n), f"IPE 200 - {L:.0f} ({n:03d})", self._copy(lambda: g.prism(prof_s, L)),
                                  STEEL)
                    self.add(secs, p, M)
                    fin = self.part("finplate", "PL10 FIN PLATE FP-200",
                                    lambda: g.cut(g.box(-5, -80, -10, 10, 160, 110),
                                                  *[g.cyl(11, 14, (-7, yy, 60), (1, 0, 0)) for yy in (-40, 40)]), STEEL)
                    for end in (-10.0, L):
                        Mf = M @ g.T(8, 0, end)
                        self.add(secs, fin, Mf)
                        for yy in (-40, 40):
                            self.bolt_set(secs, Mf @ g.T(-5, yy, 60) @ g.Rot((0, 1, 0), 90), 20, 16, washers=0)
        for k in range(len(heights) - 1):                   # X braces in the outer walls, with gussets
            for x0, x1 in zip(xs[:-1], xs[1:]):
                for y in (ys[0], ys[-1]):
                    if (int(x0 / z["bay_x"]) + k) % 2:
                        continue
                    for a0, a1 in (((x0, heights[k]), (x1, heights[k + 1])), ((x1, heights[k]), (x0, heights[k + 1]))):
                        n += 1
                        L, M = self.member((a0[0], y, a0[1] + 300), (a1[0], y, a1[1] - 300), prof_s,
                                           up=(0.0, 1.0, 0.0))
                        p = self.part(("brace", n), f"HEA 200 - {L:.0f} ({n:03d})",
                                      self._copy(lambda: g.prism(prof_s, L)), STEEL)
                        self.add(braces, p, M)
                        for end in (0.0, L):
                            gus = self.part(("gusset", n, end), f"PL15 GUSSET G{n:03d}{'AB'[end > 0]}", self._copy(
                                lambda: g.polygon_prism([(-15, -150), (-15, 150), (260, 0)], 15, g.T(0, 0, -7.5))),
                                STEEL)
                            self.add(braces, gus, M @ g.T(0, 0, end) @ g.Rot((0, 1, 0), 90 if end else -90))
        for c in (cols, beams, secs, braces):
            self.add(a, c)
        return a

    def _copy(self, make):
        """A part of its own file (Frame Generator writes one per member): a copy of the shape, its own label."""
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
        return lambda: BRepBuilderAPI_Copy(make()).Shape()

    def _beam(self, beams, p0, p1, prof, n):
        """A welded deck beam with two web stiffeners of its own (a weldment's parts)."""
        g = self.g
        L, M = self.member(p0, p1, prof)
        p = self.part(("beam", n), f"HEB 300 - {L:.0f} ({n:03d})", self._copy(lambda: g.prism(prof, L)), STEEL)
        self.add(beams, p, M)
        thick = 15.0 if self.rev == "B" and n % 9 == 0 else 12.0      # revision B: thicker stiffeners on some beams
        for k, t in enumerate((0.25, 0.5, 0.75)):
            nm = f"PL12 STIFFENER S{n:03d}-{k + 1}"
            if thick != 12.0:
                self.changed.append(nm)
            st = self.part(("stiff", n, k, thick), nm, self._copy(lambda: g.cut(
                g.box(5.5, -131, -thick / 2, 140, 262, thick), g.box(4, -140, -9, 30, 20, 18),
                g.box(4, 120, -9, 30, 20, 18))), STEEL)
            self.add(beams, st, M @ g.T(0, 0, L * t))

    # --- a deck --------------------------------------------------------------------------------------------
    def deck(self, name, i, lev):
        g, z = self.g, self.z
        d = self.asm(name)
        if i % 2 == 0 and i < len(self.levels):
            self.add(d, self.gratings(i))
        else:
            self.add(d, self.deck_plates(i))
        if i in (0, len(self.levels)):
            self.add(d, self.handrails(i))
        self.add(d, self.deck_equipment(i))
        if i == 0:
            self.add(d, self.pipe_rack(), g.T(0, 0, 0))
            for k in range(z["tray_runs"] // 2):
                self.add(d, self.tray_run(f"CABLE TRAY RUN C{k + 1}", k, self.W * (0.2 + 0.6 * k / max(1, z["tray_runs"]))),
                         g.T(0, 0, z["deck_h"] - 900))
        elif i == 1:
            for k in range(z["tx_rooms"]):
                self.add(d, self.tx_room(k), g.T(800 + k * 7000, 800, 0))
            for k in range(z["tray_runs"] - z["tray_runs"] // 2):
                self.add(d, self.tray_run(f"CABLE TRAY RUN M{k + 1}", 10 + k, self.W * (0.3 + 0.5 * k / max(1, z["tray_runs"]))),
                         g.T(0, 0, z["deck_h"] - 700))
        if i == min(2, len(self.levels) - 1):
            for k in range(z["swg_rooms"]):
                self.add(d, self.swg_room(k), g.T(self.L * 0.5 + 400, 800 + k * self.W * 0.45, 0))
        if i == len(self.levels):
            for k in range(z["hvac"]):
                self.add(d, self.hvac(k), g.T(self.L * 0.55 + k * 3200, self.W - 3500, 0))
        return d

    def gratings(self, i):
        g, z = self.g, self.z
        a = self.asm("GRATING FIELD")
        gw, gl = z["grating"]
        nx, ny = int(self.L // gl), int(self.W // gw)
        bars = int(gw // 45)
        for ix in range(nx):
            for iy in range(ny):
                cut_out = (ix * 7 + iy * 3 + i) % 4 == 0          # a penetration: a grating of its own
                key = ("grating", gw, gl) if not cut_out else ("grating", gw, gl, i, ix, iy)
                nm = f"GRATING 30x3 {gw:.0f}x{gl:.0f}" + (f" CUT {i}{ix:02d}{iy:02d}" if cut_out else "")

                def make(cut_out=cut_out):
                    plate = g.box(0, 0, -30, gl, gw, 30)
                    slots = [g.box(40, 25 + 45 * b, -31, gl - 80, 25, 32) for b in range(bars - 1)]
                    if cut_out:
                        slots.append(g.cyl(220, 32, (gl * 0.5, gw * 0.5, -31)))
                    return g.cut(plate, *slots)
                p = self.part(key, nm, make, GALV)
                M = g.T(ix * gl, iy * gw, 0)
                self.add(a, p, M)
                self.grating_clip(a, M @ g.T(gl * 0.5, gw * 0.5, 0))
        return a

    def deck_plates(self, i):
        """A plated deck: 8 mm plates 6 x 3 m, each with its own cut-outs (a part of its own)."""
        g = self.g
        a = self.asm("DECK PLATING")
        pl, pw = 6000.0, 3000.0
        for ix in range(int(self.L // pl)):
            for iy in range(int(self.W // pw)):
                holes = [(300 + (ix * 977 + iy * 613 + i * 131 + k * 1777) % 5400, 300 + (ix * 389 + k * 997) % 2400)
                         for k in range(1 + (ix + iy) % 3)]
                p = self.part(("plate", i, ix, iy), f"DECK PLATE t8 {i}{ix:02d}{iy:02d}", lambda holes=holes: g.cut(
                    g.box(0, 0, -8, pl, pw, 8), *[g.box(hx - 150, hy - 100, -9, 300, 200, 10) for hx, hy in holes]),
                    GREY)
                self.add(a, p, g.T(ix * pl, iy * pw, 0))
        return a

    def deck_equipment(self, i):
        """Lights on every other column and junction boxes with their own tag plates."""
        g, z = self.g, self.z
        a = self.asm("LIGHTING AND JUNCTION BOXES")
        light = self.asm("FLOODLIGHT FL-60W")
        self.add(light, self.part("lamphouse", "LUMINAIRE HOUSING LH-60", lambda: g.fuse(
            g.box(-150, 0, -90, 300, 120, 180), g.cyl(60, 40, (0, 0, -130))), DARK, nurbs=True))
        self.add(light, self.part("lens", "LENS GLASS LG-60", lambda: g.box(-130, 120, -70, 260, 8, 140), (0.85, 0.9, 0.95)))
        self.add(light, self.part("lampbr", "MOUNTING BRACKET MB-2", lambda: g.box(-60, -10, -160, 120, 10, 320), GALV))
        for zz in (-120, 120):
            self.bolt_set(light, g.T(0, 0, zz) @ g.Rot((1, 0, 0), 90), 10, 15, washers=0)
        k = 0
        for x in range(0, z["bays_x"] + 1, 2):
            for y in (0, z["bays_y"]):
                self.add(a, light, g.T(x * z["bay_x"] + 220, y * z["bay_y"], 2600) @ g.Rot((0, 0, 1), -90 if y else 90))
                k += 1
        for j in range(max(2, z["bays_x"] + 4)):
            jb = self.asm(f"JUNCTION BOX JB-{i}{j:02d}")
            self.add(jb, self.part("jbbody", "ENCLOSURE GRP 400x300x200", lambda: g.cut(
                g.box(0, 0, 0, 400, 200, 300), g.box(10, 10, 10, 380, 200, 280)), (0.3, 0.3, 0.32)))
            self.add(jb, self.part("jblid", "ENCLOSURE LID 400x300", lambda: g.box(0, 200, 0, 400, 15, 300), (0.3, 0.3, 0.32)))
            gland = self.part("gland", "CABLE GLAND M32 EX", lambda: g.fuse(self.hex_prism(41, 12), g.cyl(16, 30, (0, 0, 12))),
                              BLACK, nurbs=True)
            for q in range(4):
                self.add(jb, gland, g.T(60 + q * 90, 100, 0) @ g.Rot((1, 0, 0), 180))
            self.add(jb, self.part(("tag", i, j), f"TAG PLATE JB-{i}{j:02d}", lambda: g.box(150, 215, 220, 100, 2, 40),
                                   (0.95, 0.95, 0.95)))
            for cx in (20, 380):
                for cz in (20, 280):
                    self.add(jb, self.part(("pan", 5, 12), "ISO 7045 M5 x 12",
                                           lambda: g.fuse(g.cyl(4.5, 3.5), g.cyl(2.5, 12, (0, 0, 0), (0, 0, -1))), DARK),
                             g.T(cx, 215, cz) @ g.Rot((1, 0, 0), -90))
            self.add(a, jb, g.T(z["bay_x"] * (j % z["bays_x"]) + 1200, 400 if j % 2 else self.W - 600, 1200))
        return a

    def handrails(self, i):
        g = self.g
        a = self.asm("HANDRAIL")
        segs = []
        for x0 in range(0, int(self.L), 3000):
            segs.append(((x0, 0), (0.0)))
            segs.append(((x0 + 3000, self.W), (180.0)))
        for y0 in range(0, int(self.W), 3000):
            segs.append(((self.L, y0), (90.0)))
            segs.append(((0, y0 + 3000), (-90.0)))
        for k, ((x, y), turn) in enumerate(segs):
            L = 3000.0 if k % 9 else 2400.0
            toe = 160.0 if self.rev == "B" and i == 0 and turn == 0.0 else 150.0    # revision B: a higher toe plate
            if toe != 150.0:
                self.changed.append(f"HANDRAIL SECTION HR-{L:.0f}-{i}{k:02d}")
            sec = self.part(("hr", i, k, toe), f"HANDRAIL SECTION HR-{L:.0f}-{i}{k:02d}", lambda L=L, toe=toe: g.fuse(
                g.rod((100, 0, 0), (100, 0, 1100), 24), g.rod((L - 100, 0, 0), (L - 100, 0, 1100), 24),
                g.rod((60, 0, 1100), (L - 60, 0, 1100), 24), g.rod((60, 0, 550), (L - 60, 0, 550), 17),
                g.box(60, -30, 0, L - 120, 6, toe),
                g.box(40, -40, 0, 120, 80, 12), g.box(L - 160, -40, 0, 120, 80, 12)), ORANGE)
            M = g.T(x, y, 0) @ g.Rot((0, 0, 1), turn)
            asm = self.asm(f"HANDRAIL HR-{L:.0f}")
            self.add(asm, sec)
            for px in (100, L - 100):
                self.bolt_set(asm, g.T(px, 0, 12.1), 12, 12 + 30, washers=0)
            self.add(a, asm, M)
        return a

    # --- rooms --------------------------------------------------------------------------------------------
    def room_walls(self, a, w, d, h, door_x):
        """Modular A60 wall panels (600 mm wide, one part per height) round the room, a door in the front wall."""
        g = self.g
        walls = self.asm("A60 WALLS")
        panel = self.part(("wallpanel", h), f"A60 WALL PANEL WP-600x{h:.0f}", lambda: g.cut(
            g.box(0, 0, 0, 600, 80, h), g.box(20, 20, 20, 560, 40, h - 40)), LIGHT)
        cleat = self.part("wallclip", "PANEL CLIP PC-80", lambda: g.box(-20, -10, 0, 40, 100, 60), GALV)
        for side, (x0, y0, turn, length) in enumerate(((0, 0, 0, w), (w, d, 180, w), (w, 0, 90, d), (0, d, -90, d))):
            M0 = g.T(x0, y0, 0) @ g.Rot((0, 0, 1), turn)
            for k in range(int(length // 600)):
                if side == 0 and door_x - 600 < k * 600 < door_x + 1000:
                    continue
                self.add(walls, panel, M0 @ g.T(k * 600, 0, 0))
                self.add(walls, cleat, M0 @ g.T(k * 600, 0, h))
        self.add(a, walls)
        self.add(a, self.door(), g.T(door_x, 0, 0))

    def door(self):
        g = self.g
        a = self.asm("DOOR D-1 1000x2100 A60")
        frame = self.part("doorframe", "DOOR FRAME DF-1000", lambda: g.cut(
            g.box(-60, -40, 0, 1120, 160, 2160), g.box(0, -50, -1, 1000, 200, 2101)), DARK)
        self.add(a, frame)
        leaf_asm = self.asm("DOOR LEAF ASM")

        def leaf():
            return g.cut(self.fillet(g.box(5, 0, 5, 990, 60, 2090), 8.0), g.box(300, -1, 1500, 400, 10, 300))        # a vision panel recess
        self.add(leaf_asm, self.part("leaf", "DOOR LEAF DL-1000 A60", leaf, BLUE))
        handle = self.part("handle", "LEVER HANDLE LH-20", lambda: g.fuse(
            g.cyl(25, 15, (0, 0, 0), (0, -1, 0)), g.rod((0, -15, 0), (0, -70, 0), 10),
            g.rod((0, -70, 0), (-140, -70, 0), 11)), (0.75, 0.75, 0.77), nurbs=True)
        self.add(leaf_asm, handle, g.T(900, 0, 1050))
        closer = self.part("closer", "DOOR CLOSER TS-83", lambda: g.box(0, 0, 0, 300, 50, 60), DARK)
        self.add(leaf_asm, closer, g.T(80, 60, 1950))
        hinge = self.part("hinge", "HINGE H-120", lambda: g.fuse(
            g.cyl(12, 120), g.box(0, -2, 0, 60, 4, 120), g.box(-60, -2, 0, 60, 4, 120)), (0.6, 0.6, 0.62))
        for zz in (200, 1000, 1800):
            self.add(a, hinge, g.T(0, -14, zz))
            for k in range(3):
                self.add(leaf_asm, self.part(("screw7380", 6, 16), "ISO 7380 M6 x 16",
                                             lambda: g.fuse(g.sphere(5.5), g.cyl(3, 16, (0, 0, 0), (0, 0, -1))), DARK),
                         g.T(20 + k * 15, -2, zz + 60) @ g.Rot((1, 0, 0), -90))
        c = self.add(a, leaf_asm)
        a.joint("Swing", "rotate", [c], (0.0, -14.0, 0.0), (0.0, 0.0, 1.0), limits=(0.0, 100.0))
        return a

    def tx_room(self, k):
        g = self.g
        a = self.asm(f"TRANSFORMER ROOM T{k + 1}")
        self.room_walls(a, 6200, 7000, 5200, 400)
        self.add(a, self.transformer(), g.T(1400, 1600, 0))
        return a

    def transformer(self):
        g, z = self.g, self.z
        if "tx" in self.parts:
            return self.parts["tx"]
        a = self.asm("TRANSFORMER 66/33 kV 120 MVA")
        W, D, H = 3200.0, 2200.0, 2600.0

        def tank():
            return self.fillet(g.box(0, 0, 0, W, D, H), 120.0, vertical_only=True)
        self.add(a, self.part("txtank", "TANK WELDMENT TW-120", tank, GREY))
        lid = self.part("txlid", "TANK COVER TC-120", lambda: g.box(-60, -60, 0, W + 120, D + 120, 40), GREY)
        self.add(a, lid, g.T(0, 0, H))
        nb = z["lid_bolts"]
        per = [(W + 120) * 2, (D + 120) * 2]
        for k in range(nb):
            t = k / nb * (sum(per))
            if t < W + 120:
                x, y = -30 + t, -30
            elif t < W + 120 + D + 120:
                x, y = W + 30, -30 + (t - W - 120)
            elif t < 2 * (W + 120) + D + 120:
                x, y = W + 30 - (t - W - 120 - D - 120), D + 30
            else:
                x, y = -30, D + 30 - (t - 2 * (W + 120) - D - 120)
            self.bolt_set(a, g.T(x, y, H + 40.1), 16, 40 + 20, washers=1)

        def fin_wall():                       # corrugated cooling wall: a smooth loft (B-spline faces)
            secs = []
            for j in range(9):
                zz = 300 + j * (H - 600) / 8
                pts = []
                n = 12
                for s in range(n):
                    x = s * 1400 / (n - 1)
                    pts.append((x, 0.0 + (j % 2) * 6, zz))
                for s in reversed(range(n)):
                    x = s * 1400 / (n - 1)
                    pts.append((x, 260.0 + 30 * math.sin(s * 0.9 + j * 0.4), zz))
                secs.append(pts)
            return g.loft(secs, ruled=False)
        fins = self.part("txfin", "COOLING FIN PANEL CF-1400", fin_wall, GREY)
        for k in range(z["fins"]):              # fin walls along both long sides, two high
            side, col, row = k % 2, (k // 2) % 2, k // 4
            if row > 1:
                break
            M = g.T(200 + col * 1500, -280 if side == 0 else D + 20, row * 0.0)
            self.add(a, fins, M)
        rad = self.radiator()
        for k in range(z["radiators"]):
            self.add(a, rad, g.T(-450 if k % 2 == 0 else W + 450, 200 + (k // 2) * 650, 300) @
                     g.Rot((0, 0, 1), 0 if k % 2 == 0 else 180))
        bush_hv = self.part("bushhv", "BUSHING HV 72.5 kV", lambda: self.bushing(1100, 110), (0.55, 0.3, 0.2), nurbs=True)
        bush_lv = self.part("bushlv", "BUSHING LV 36 kV", lambda: self.bushing(600, 80), (0.55, 0.3, 0.2), nurbs=True)
        for k in range(3):
            self.add(a, bush_hv, g.T(600 + k * 700, 500, H + 40))
            self.add(a, bush_lv, g.T(600 + k * 700, D - 500, H + 40))
        cons = self.part("txcons", "CONSERVATOR CV-600", lambda: g.fuse(
            g.cyl(300, 2200, (0, 0, 0), (1, 0, 0)), g.sphere(300, (0, 0, 0)), g.sphere(300, (2200, 0, 0))),
            GREY, nurbs=True)
        self.add(a, cons, g.T(500, D * 0.5, H + 900))
        wheel = self.part("txwheel", "FLANGED WHEEL FW-250", lambda: g.revolve(
            [(0, -60), (125, -60), (125, -40), (140, -40), (140, 40), (125, 40), (125, 60), (0, 60)],
            (0, 0, 0), (0, 1, 0)), DARK, nurbs=True)
        for x in (300, W - 300):
            for y in (200, D - 200):
                self.add(a, wheel, g.T(x, y, -140))
        nm = self.unnamed()
        self.add(a, self.part(nm, nm, lambda: g.box(0, 0, 0, 400, 300, 600), GREY), g.T(W * 0.5, -320, 800))
        self.parts["tx"] = a
        return a

    def bushing(self, h: float, r: float):
        g = self.g
        prof = [(0, 0), (r * 1.6, 0), (r * 1.6, 40)]
        n = int(h // 90)
        z = 40.0
        for s in range(n):
            prof += [(r, z), (r * 1.9, z + 25), ("arc", (r * 1.95, z + 35), (r * 1.9, z + 45)), (r, z + 70)]
            z += 90
        prof += [(r * 0.6, z), (r * 0.6, z + 80), (0, z + 80)]
        return g.revolve(prof)

    def radiator(self):
        g = self.g
        if "rad" in self.parts:
            return self.parts["rad"]
        a = self.asm("RADIATOR RD-20")
        panel = self.part("radpanel", "RADIATOR ELEMENT RE-520", lambda: g.loft([
            [(0, -3, z0), (520, -3, z0), (520, 3, z0), (0, 3, z0)] if z0 in (0, 1800) else
            [(0, -10, z0), (520, -10, z0), (520, 10, z0), (0, 10, z0)] for z0 in (0, 300, 900, 1500, 1800)],
            ruled=False), GREY)
        for k in range(20):
            self.add(a, panel, g.T(0, -300 + k * 30, 0))
        hdr = self.part("radhdr", "HEADER PIPE HP-80", lambda: g.cyl(40, 640, (260, -330, 0), (0, 1, 0)), GREY)
        self.add(a, hdr, g.T(0, 0, 1850))
        self.add(a, hdr, g.T(0, 0, -50))
        self.parts["rad"] = a
        return a

    def swg_room(self, k):
        g, z = self.g, self.z
        a = self.asm(f"SWITCHGEAR ROOM S{k + 1}")
        n = z["cabinets"]
        self.room_walls(a, 900 * (n // 2 + 1) + 1600, 6200, 3600, 600)
        line_ = self.asm("SWITCHGEAR LINEUP 33 kV")
        xs = [0.0, 0.0]
        for c in range(n):
            t = "ABCDE"[(c * 3 + k) % 5]
            w = {"A": 600, "B": 800, "C": 900, "D": 600, "E": 1000}[t]
            row = 0 if c < (n + 1) // 2 else 1
            M = g.T(xs[row], 0, 0) if row == 0 else g.T(xs[row], 3400, 0) @ g.Rot((0, 0, 1), 180, (w / 2, 600, 0))
            self.add(line_, self.cabinet(t, w, c, k), M)
            xs[row] += w
        self.add(a, line_, g.T(800, 1200, 0))
        return a

    def cabinet(self, t, w, c, room):
        """A switchgear cabinet: body, door with hinges and handle, internals (breakers vary per cabinet: unique)."""
        g = self.g
        H, D = 2300.0, 1200.0
        a = self.asm(f"SWG CABINET {t}{w}")
        vents = 3 if not (self.rev == "B" and t == "C") else 5
        key = ("cab", t, w, vents)
        if self.rev == "B" and t == "C":
            self.changed.append(f"SWG CABINET BODY {t}{w}")
        body = self.part(key, f"SWG CABINET BODY {t}{w}", lambda: g.cut(
            g.box(0, 0, 100, w, D, H - 100), g.box(15, -1, 115, w - 30, D - 14, H - 130),
            *[g.box(w * 0.2, D - 20, 400 + k * 150, w * 0.6, 30, 40) for k in range(vents)]), LIGHT)
        self.add(a, body)
        plinth = self.part(("plinth", w), f"PLINTH PL-{w}", lambda: g.cut(g.box(0, 0, 0, w, D, 100),
                                                                         g.box(20, 20, -1, w - 40, D - 40, 102)), DARK)
        self.add(a, plinth)
        for px in (60, w - 60):
            for py in (100, D - 100):
                self.add(a, self.washer(12), g.T(px, py, 20))
                self.add(a, self.screw(12, 40), g.T(px, py, 20 + 2.5))
        door = self.asm(f"CABINET DOOR {w}")

        def leaf():
            return self.fillet(g.box(0, -25, 100, w, 25, H - 100), 4.0)
        self.add(door, self.part(("cabdoor", w), f"CABINET DOOR LEAF {w}", leaf, LIGHT))
        grip = self.part("cabgrip", "SWING HANDLE SH-1", lambda: g.fuse(
            g.box(-20, -30, -100, 40, 30, 200), g.rod((0, -30, -80), (0, -60, -80), 8)), BLACK, nurbs=True)
        self.add(door, grip, g.T(w - 60, -25, 1300))
        for zz in (400, 1900):
            self.add(door, self.part("cabhinge", "CABINET HINGE CH-1", lambda: g.cyl(10, 80), DARK), g.T(0, -25, zz))
            for k in range(2):
                self.add(door, self.part(("screw7380", 4, 10), "ISO 7380 M4 x 10",
                                         lambda: g.fuse(g.sphere(3.8), g.cyl(2, 10, (0, 0, 0), (0, 0, -1))), DARK),
                         g.T(20, -25, zz + 20 + 30 * k) @ g.Rot((1, 0, 0), -90))
        self.add(a, door)
        # internals: three breaker trucks and a busbar set; the breakers' ratings vary per cabinet (unique parts)
        for k in range(3):
            amps = (630, 1250, 2000, 2500, 3150)[(c + k + room * 2) % 5]
            br = self.part(("breaker", room, c, k), f"VCB 36 kV {amps} A - {room + 1}{c:02d}-{k + 1}", lambda amps=amps: g.fuse(
                g.box(40, 80, 0, w - 80, 600, 420), *[g.cyl(20 + amps / 400, 160, (w * (0.25 + 0.25 * p), 680, 210), (0, 1, 0))
                                                     for p in range(3)]), DARK)
            self.add(a, br, g.T(0, 0, 300 + k * 600))
            for s in range(2):
                self.add(a, self.screw(8, 20), g.T(60 + s * (w - 120), 120, 300 + k * 600 + 420.1))
        bus = self.part(("bus", w), f"BUSBAR CU 10x100 L{w}", lambda: g.box(0, 0, 0, w, 10, 100), COPPER)
        for p in range(3):
            self.add(a, bus, g.T(0, D - 200 - p * 60, H - 300))
        rail = self.part(("dinrail", w), f"DIN RAIL TS35 L{w - 60}", lambda: g.box(30, 0, 0, w - 60, 35, 7.5), GALV)
        term = self.part("terminal", "TERMINAL BLOCK UT 10", lambda: g.fuse(
            g.box(0, 0, 0, 10.2, 47, 40), g.box(0, 8, 40, 10.2, 31, 12)), (0.6, 0.62, 0.66))
        for r in range(2):
            self.add(a, rail, g.T(0, D - 120, 1850 + r * 160))
            for t in range(int((w - 100) // 40)):
                self.add(a, term, g.T(50 + t * 40, D - 120 - 47, 1857 + r * 160))
        gl = self.part("gland25", "CABLE GLAND M25 EX", lambda: g.fuse(self.hex_prism(32, 10), g.cyl(12.5, 24, (0, 0, 10))),
                       BLACK, nurbs=True)
        for q in range(6):
            self.add(a, gl, g.T(80 + q * (w - 160) / 5, D * 0.5, 100) @ g.Rot((1, 0, 0), 180))
        self.add(a, self.part(("nameplate", room, c), f"NAMEPLATE =S{room + 1}+H{c + 1:02d}",
                              lambda: g.box(w * 0.3, -27, 2050, w * 0.4, 2, 80), (0.95, 0.95, 0.95)))
        self.add(a, self.part(("loom", room, c), f"WIRING LOOM W-S{room + 1}H{c + 1:02d}",
                              lambda: self.cable(1200 + 40 * c, 160.0, c + 3 * room, 9.0, False), (0.15, 0.15, 0.6)),
                 g.T(60, D - 300, 1700) @ g.Rot((1, 0, 0), 90))
        if (c + room) % 4 == 0:
            nm = self.unnamed()
            self.add(a, self.part(nm, nm, lambda: g.box(0, 0, 0, 120, 80, 200), BLACK), g.T(w * 0.5, 300, 2000))
        return a

    # --- cable trays and cables ---------------------------------------------------------------------------
    def tray_run(self, name, k, y):
        g, z = self.g, self.z
        a = self.asm(name)
        sec_L = 3000.0
        n = int(self.L // sec_L)
        wid = 600.0
        reroute = self.rev == "B" and k == 0
        for s in range(n):
            pitch = 290.0 if reroute else 300.0                         # revision B: the run's ladders re-made
            nm_t = f"CABLE LADDER CL-{wid:.0f} L{sec_L:.0f} R{k:02d}-{s:02d}"
            if reroute:
                self.changed.append(nm_t)
            sec = self.part(("tray", k, s, pitch), nm_t, lambda pitch=pitch: g.fuse(
                g.box(0, 0, 0, sec_L, 3, 100), g.box(0, wid - 3, 0, sec_L, 3, 100),
                *[g.box(150 + r * pitch, 0, 0, 30, wid, 20) for r in range(10)]), GALV)
            M = g.T(s * sec_L, y, 0)
            self.add(a, sec, M)
            cleat = self.part("cleat", "CABLE CLEAT TREFOIL CC-38", lambda: g.fuse(
                g.box(-20, 0, 0, 40, 160, 10), g.torus_piece((0, 80, 40), (1, 0, 0), (0, 80, 75), math.pi, 6)), BLACK)
            for q in range(3):
                self.add(a, cleat, M @ g.T(450 + q * 1000, 40 + (q * 170) % int(wid - 200), 20))
            if s:
                sp = self.part("splice", "SPLICE PLATE SP-100", lambda: g.box(-75, -6, 10, 150, 6, 80), GALV)
                for yy in (-6, wid + 6):
                    self.add(a, sp, M @ g.T(0, yy, 0))
                    for dx in (-45, 45):
                        self.bolt_set(a, M @ g.T(dx, yy, 50) @ g.Rot((1, 0, 0), 90 if yy < 0 else -90), 8, 8, 0)
            if s % 2:
                continue
            br = self.part(("traybr", k, s), f"TRAY BRACKET TB-{700 + 100 * (k % 3)}-{k:02d}{s:02d}", lambda k=k: g.fuse(
                g.box(-40, -50, -40, 80, wid + 100, 40), g.box(-40, -50, 0, 80, 10, 700 + 100 * (k % 3))), GALV)
            self.add(a, br, M @ g.T(300, 0, 0))
            for yy in (0, wid):
                self.bolt_set(a, M @ g.T(300, yy - 40, 700 + 100 * (k % 3) + 0.1) @ g.Rot((1, 0, 0), 90), 12, 15, 0)
        for c in range(z["cables"]):
            r = 14.0 + (c % 4) * 6
            nm = f"CABLE {('33kV 3x240', '33kV 3x400', 'LV 4x95', 'FO 48F')[c % 4]} W{k:02d}-{c + 1:02d}"
            key = ("cable", k, c, reroute)
            if reroute:
                self.changed.append(nm)
            self.add(a, self.part(key, nm, lambda c=c, r=r: self.cable(n * sec_L, wid, c, r, reroute), BLACK),
                     g.T(0, y, 0))
        return a

    def cable(self, length: float, wid: float, c: int, r: float, reroute: bool):
        """One cable along the tray, dropping down at its end: a circle swept along a B-spline (B-spline faces). A
        sweep OpenCascade cannot close is made again with less wobble."""
        for wobble in (6.0, 2.0, 0.0):
            try:
                return self._cable(length, wid, c, r, reroute, wobble)
            except Exception:  # noqa: BLE001
                if not wobble:
                    raise

    def _cable(self, length: float, wid: float, c: int, r: float, reroute: bool, wobble: float):
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
        from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
        from OCP.GeomAPI import GeomAPI_PointsToBSpline
        from OCP.collections import Array1_gp_Pnt as TColgp_Array1OfPnt
        from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
        lane = 40 + (c * 41) % int(wid - 80)
        end = length * (0.45 + 0.5 * ((c * 37) % 11) / 10.0)
        pts = [(0.0, lane, 20 + r)]
        steps = 5
        for s in range(1, steps + 1):
            x = end * s / steps
            wob = wobble * math.sin(s * 1.3 + c)
            pts.append((x, lane + wob, 20 + r))
        drop = -1600.0 if not reroute else -1200.0
        pts += [(end + 500, lane, 20 + r - 250), (end + 800, lane, drop * 0.45), (end + 900, lane, drop)]
        arr = TColgp_Array1OfPnt(1, len(pts))
        for i, p in enumerate(pts):
            arr.SetValue(i + 1, gp_Pnt(*p))
        curve = GeomAPI_PointsToBSpline(arr, 3, 3).Curve()
        edge = BRepBuilderAPI_MakeEdge(curve).Edge()
        t0 = curve.DN(curve.FirstParameter(), 1)
        prof = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(*pts[0]), gp_Dir(t0)), r)).Edge()).Wire()
        ps = BRepOffsetAPI_MakePipeShell(BRepBuilderAPI_MakeWire(edge).Wire())
        ps.SetMode(False)
        tol, seg = getattr(self, "_tol", (0.05, 24))
        ps.SetTolerance(tol, 0.5, 1e-3)         # as loose as a CAD cable: the surface's control points stay few
        ps.SetMaxSegments(seg)
        ps.Add(prof)
        ps.Build()
        ps.MakeSolid()
        return ps.Shape()

    # --- piping ---------------------------------------------------------------------------------------------
    def pipe_rack(self):
        g, z = self.g, self.z
        a = self.asm("PIPE RACK PR-01")
        nps = (100, 150, 200, 250, 100, 150, 80, 300)
        y0 = self.W * 0.5
        spool_L = (self.L - 1200) / z["spools"]
        for ln in range(z["pipe_lines"]):
            dn = nps[ln % len(nps)]
            od = {80: 88.9, 100: 114.3, 150: 168.3, 200: 219.1, 250: 273.0, 300: 323.9}[dn]
            line_ = self.asm(f"LINE {('FW', 'DW', 'HV', 'DO', 'SW', 'FW')[ln % 6]}-{dn}-{ln + 1:03d}")
            y = y0 - 2000 + ln * 550
            zz = 2400 + (ln % 2) * 700
            flange = self.flange(dn, od)
            for s in range(z["spools"]):
                Ls = spool_L - 6 + (50 if (self.rev == "B" and ln == 1 and s == 1) else 0)
                key = ("spool", ln, s, round(Ls))
                nm = f"SPOOL {dn} {ln + 1:03d}-{s + 1:02d}"
                if self.rev == "B" and ln == 1 and s == 1:
                    self.changed.append(nm)
                sp = self.part(key, nm, lambda od=od, Ls=Ls: g.tube(od / 2, od / 2 - 7, Ls, (0, 0, 0), (1, 0, 0)),
                               (0.8, 0.2, 0.15) if ln % 6 in (0, 5) else (0.3, 0.45, 0.25))
                x = 600 + s * spool_L
                self.add(line_, sp, g.T(x + 3, y, zz))
                for e, rot in ((x + 3, 90), (x + 3 + Ls, -90)):
                    self.add(line_, flange, g.T(e, y, zz) @ g.Rot((0, 1, 0), rot))
                if s:
                    self.flanged_joint(line_, g.T(x, y, zz), dn, od)
                sup = self.part(("pipesup", ln, s), f"PIPE SUPPORT PS-{dn}-{ln + 1:02d}{s + 1:02d}", lambda od=od, zz=zz: g.fuse(
                    g.box(-60, -od, -zz + 200, 120, 2 * od, 20), g.box(-10, -od, -zz + 200, 20, 2 * od, zz - 200 - od / 2)),
                    STEEL)
                self.add(line_, sup, g.T(x + spool_L * 0.5, y, zz))
                ub = self.part(("ubolt", dn), f"U-BOLT DN{dn} M12", lambda od=od: g.fuse(
                    g.torus_piece((0, 0, 0), (1, 0, 0), (0, od / 2 + 8, 0), math.pi, 6),
                    g.rod((0, od / 2 + 8, 0), (0, od / 2 + 8, -od / 2 - 40), 6),
                    g.rod((0, -od / 2 - 8, 0), (0, -od / 2 - 8, -od / 2 - 40), 6)), GALV)
                self.add(line_, ub, g.T(x + spool_L * 0.5, y, zz) @ g.Rot((1, 0, 0), 90))
                for sy in (-1, 1):
                    self.add(line_, self.nut(12), g.T(x + spool_L * 0.5, y + sy * (od / 2 + 8), zz - od / 2 - 30))
                pg = self.part("gauge", "PRESSURE GAUGE PG-100", lambda: g.fuse(
                    g.cyl(50, 30, (0, 0, 120), (0, 1, 0)), g.rod((0, 15, 0), (0, 15, 120), 8)), (0.85, 0.85, 0.85), nurbs=True)
                self.add(line_, pg, g.T(x + spool_L * 0.25, y, zz + od / 2))
                self.add(line_, self.part(("pgtag", ln, s), f"TAG PLATE PI-{ln + 1:02d}{s + 1:02d}",
                                          lambda: g.box(-30, 0, 180, 60, 2, 25), (0.95, 0.95, 0.95)),
                         g.T(x + spool_L * 0.25, y, zz + od / 2))
            for v in range(z["valves"] // z["pipe_lines"] + (1 if ln < z["valves"] % z["pipe_lines"] else 0)):
                xv = 600 + (v + 1) * spool_L - spool_L * 0.5
                self.add(line_, self.valve(dn, od), g.T(xv, y, zz + od / 2 + 40))
            self.add(a, line_)
        return a

    def flange(self, dn, od):
        g = self.g
        D = od + 2 * (70 + dn * 0.25)
        bolts = 8 if dn <= 200 else 12
        pcd = (od + D) / 2

        def make():
            f = g.revolve([(od / 2 - 7, 0), (D / 2, 0), (D / 2, 28), (od / 2 + 20, 28), (od / 2 + 6, 90),
                           (od / 2 - 7, 90)])
            return g.cut(f, *[g.cyl(12, 40, (pcd / 2 * math.cos(2 * math.pi * k / bolts),
                                             pcd / 2 * math.sin(2 * math.pi * k / bolts), -5)) for k in range(bolts)])
        return self.part(("flange", dn), f"FLANGE WN DN{dn} PN40 EN 1092-1", make, GREY)

    def flanged_joint(self, parent, M, dn, od):
        g = self.g
        D = od + 2 * (70 + dn * 0.25)
        bolts = 8 if dn <= 200 else 12
        pcd = (od + D) / 2
        gasket = self.part(("gasket", dn), f"GASKET SPW DN{dn}", lambda: g.tube(od / 2 + 30, od / 2, 3), DARK)
        self.add(parent, gasket, M @ g.Rot((0, 1, 0), 90) @ g.T(0, 0, -1.5))
        for k in range(bolts):
            a = 2 * math.pi * (k + 0.5) / bolts
            Mb = M @ g.T(0, pcd / 2 * math.cos(a), pcd / 2 * math.sin(a)) @ g.Rot((0, 1, 0), 90)
            self.add(parent, self.stud(20, 150), Mb)
            for s in (-1, 1):
                self.add(parent, self.nut(20), Mb @ g.T(0, 0, s * 31 - (16 if s < 0 else 0)))

    def valve(self, dn, od):
        g = self.g
        key = ("valve", dn)
        if key in self.parts:
            return self.parts[key]
        a = self.asm(f"GATE VALVE DN{dn} PN40")
        body = self.part(("vbody", dn), f"VALVE BODY GV-{dn}", lambda: g.loft([
            [(x, od * 0.6 * math.cos(t), od * 0.6 * math.sin(t) + zz) for t in [2 * math.pi * i / 10 for i in range(10)]]
            for x, zz in ((-od * 0.8, 0), (-od * 0.3, 20), (0, 40), (od * 0.3, 20), (od * 0.8, 0))], ruled=False),
            (0.25, 0.35, 0.55), nurbs=True)
        self.add(a, body)
        bonnet_b = self.rev == "B" and dn == 150
        if bonnet_b:
            self.changed.append(f"BONNET GV-{dn}")
        bonnet = self.part(("bonnet", dn, bonnet_b), f"BONNET GV-{dn}", lambda: g.fuse(
            g.cyl(od * 0.55, 60, (0, 0, od * 0.5)), g.cyl(od * 0.3, od * (1.6 if not bonnet_b else 1.8), (0, 0, od * 0.5 + 60))),
            (0.25, 0.35, 0.55), nurbs=True)
        self.add(a, bonnet)
        hw = self.part(("hwheel", dn), f"HANDWHEEL HW-{int(od * 1.6)}", lambda: g.fuse(
            g.torus_piece((0, 0, 0), (0, 0, 1), (od * 0.8, 0, 0), 2 * math.pi, 12),
            *[g.rod((0, 0, 0), (od * 0.8 * math.cos(k * 2.094), od * 0.8 * math.sin(k * 2.094), 0), 8) for k in range(3)],
            g.cyl(25, 40, (0, 0, -20))), RED)
        self.add(a, hw, g.T(0, 0, od * 2.3 + 80))
        for k in range(8):
            t = 2 * math.pi * k / 8
            self.bolt_set(a, g.T(od * 0.45 * math.cos(t), od * 0.45 * math.sin(t), od * 0.5 + 60.1), 16, 60, 0)
        self.parts[key] = a
        return a

    # --- HVAC, stairs ----------------------------------------------------------------------------------------
    def hvac(self, k):
        g = self.g
        a = self.asm(f"HVAC UNIT AHU-{k + 1:02d}")
        casing = self.part("ahu", "AHU CASING 2800x2200", lambda: g.cut(
            g.box(0, 0, 0, 2800, 2200, 1800), g.box(40, 40, 40, 2720, 2120, 1800), g.cyl(500, 100, (1400, 1100, 1700))),
            LIGHT)
        self.add(a, casing)

        def fan():
            hub = g.cyl(120, 160)
            blades = []
            for b in range(7):
                t = 2 * math.pi * b / 7
                secs = []
                for j, rr in enumerate((110.0, 280.0, 470.0)):
                    tw = math.radians(35 - j * 12)
                    c, s = math.cos(t + 0.05 * j), math.sin(t + 0.05 * j)
                    pts = []
                    for u, v in ((-90, -5), (90, -5), (90, 5), (-90, 5)):
                        uu, vv = u * math.cos(tw) - v * math.sin(tw), u * math.sin(tw) + v * math.cos(tw)
                        pts.append((rr * c - uu * s, rr * s + uu * c, 80 + vv))
                    secs.append(pts)
                blades.append(g.loft(secs, ruled=False))
            return g.fuse(hub, *blades)
        self.add(a, self.part("fan", "AXIAL FAN IMPELLER AF-1000", fan, DARK), g.T(1400, 1100, 1500))
        motor = self.part("fanmotor", "MOTOR IEC 132M 7.5 kW", lambda: g.fuse(
            g.cyl(130, 380), *[g.box(-140, -4, 40 + 25 * i, 280, 8, 12) for i in range(12)]), BLUE, nurbs=True)
        self.add(a, motor, g.T(1400, 1100, 1100))
        for x in (100, 2700):
            for y in (100, 2100):
                self.bolt_set(a, g.T(x, y, 40.1), 16, 40, 2)
        return a

    def stairs(self):
        g, z = self.g, self.z
        a = self.asm("STAIR TOWERS")
        for t in range(z["stairs"]):
            tower = self.asm(f"STAIR TOWER ST-{t + 1}")
            for lv in range(len(self.levels)):
                fl = self.asm("STAIR FLIGHT SF-6000")
                rise = z["deck_h"]
                n = int(rise // 200)
                run = n * 250
                stringer = self.part("stringer", "STRINGER UPN 200 SF-6000", lambda: g.beam(
                    (0, 0, 0), (run, 0, rise), 75, 200), ORANGE)
                for yy in (0, 1000):
                    self.add(fl, stringer, g.T(0, yy, 0))
                tread = self.part("tread", "STAIR TREAD ST-1000x250", lambda: g.cut(
                    g.box(0, 40, -40, 250, 920, 40), *[g.box(20, 60 + 40 * i, -41, 210, 20, 42) for i in range(22)]), GALV)
                for s in range(n):
                    Mt = g.T(s * 250, 0, (s + 1) * 200)
                    self.add(fl, tread, Mt)
                    for yy in (40, 960):
                        self.bolt_set(fl, Mt @ g.T(125, yy, 0.1) @ g.Rot((1, 0, 0), 90 if yy < 100 else -90), 10, 15, 0)
                self.add(tower, fl, g.T(0, 0, self.levels[lv]) @ (g.T() if lv % 2 == 0 else g.Rot((0, 0, 1), 180, (run / 2, 1100, 0))))
            self.add(a, tower, g.T(self.L - 6000 if t == 0 else 1000, self.W + 400 if t == 0 else -1600, 0))
        lad = self.asm("LADDER LD-3000")
        rail = self.part("ladrail", "LADDER RAIL 60x10 L3000", lambda: g.box(0, 0, 0, 10, 60, 3000), ORANGE)
        rung = self.part("rung", "RUNG RD25 L450", lambda: g.rod((0, 30, 0), (460, 30, 0), 12.5), ORANGE)
        self.add(lad, rail)
        self.add(lad, rail, g.T(450, 0, 0))
        for k in range(10):
            self.add(lad, rung, g.T(0, 0, 150 + k * 300))
        self.add(a, lad, g.T(self.L - 600, self.W * 0.5, self.top - 3000))
        return a

    # --- pedestal crane and davit (joints) -------------------------------------------------------------------
    def crane(self):
        g, z = self.g, self.z
        a = self.asm(CRANE)
        H = 4000.0
        ped = self.part("pedestal", "PEDESTAL PD-1800", lambda: g.fuse(
            g.tube(900, 860, H), g.revolve([(860, H - 80), (1150, H - 80), (1150, H), (860, H)]),
            g.revolve([(860, 0), (1300, 0), (1300, 60), (860, 60)])), STEEL)
        self.add(a, ped)
        ring = self.part("slewring", "SLEWING BEARING SB-2000", lambda: g.revolve(
            [(700, 0), (1100, 0), (1100, 90), (1050, 90), ("arc", (1000, 140), (950, 90)), (700, 90)]),
            DARK, nurbs=True)
        self.add(a, ring, g.T(0, 0, H))
        nb = z["slew_bolts"]
        for k in range(nb):
            t = 2 * math.pi * (k + 0.5) / nb
            self.bolt_set(a, g.T(1050 * math.cos(t), 1050 * math.sin(t), H - 80) @ g.Rot((1, 0, 0), 180), 24, 80 + 45, 1)
        up = self.asm("SLEWING UNIT")
        house = self.part("house", "CRANE HOUSE CH-40", lambda: g.fuse(
            g.box(-1500, -1300, 0, 3600, 2600, 2400),
            g.loft([[(-1500, -1300, 2400), (2100, -1300, 2400), (2100, 1300, 2400), (-1500, 1300, 2400)],
                    [(-1300, -1100, 2900), (1900, -1100, 2900), (1900, 1100, 2900), (-1300, 1100, 2900)]], ruled=False)),
            STEEL)
        self.add(up, house, g.T(0, 0, 100))
        for k in range(nb):
            t = 2 * math.pi * (k + 0.5) / nb
            self.bolt_set(up, g.T(800 * math.cos(t), 800 * math.sin(t), 100.1), 24, 100, 1)
        cab = self.part("crcab", "OPERATOR CABIN OC-2", lambda: g.cut(
            g.box(0, 0, 0, 1400, 1100, 2000), g.box(-10, 100, 900, 1300, 900, 900)), (0.9, 0.9, 0.88))
        self.add(up, cab, g.T(1600, 1300, 300))
        winch = self.asm("HOIST WINCH HW-15")
        drum = self.part("drum", "WINCH DRUM WD-600", lambda: g.revolve(
            [(0, 0), (450, 0), (450, 40), (300, 40), (300, 860), (450, 860), (450, 900), (0, 900)], (0, 0, 0), (0, 1, 0)),
            DARK, nurbs=True)
        self.add(winch, drum)
        self.add(winch, self.part("winchmotor", "HYDRAULIC MOTOR HM-250", lambda: g.cyl(180, 400, (0, 900, 0), (0, 1, 0)),
                                  BLUE), g.T(0, 0, 0))
        self.add(up, winch, g.T(-900, -450, 1200))
        boom = self.asm("LATTICE BOOM LB-28")
        Lb = 28000.0
        chord = self.part("chord", "BOOM CHORD CHS 168x10 L28000", lambda: g.tube(84, 74, Lb, (0, 0, 0), (1, 0, 0)), STEEL)
        for y in (-700, 700):
            for zz in (-500, 500):
                self.add(boom, chord, g.T(0, y, zz))
        nl = z["lacings"]
        for k in range(nl):
            x0 = 600 + k * (Lb - 1200) / nl
            x1 = x0 + (Lb - 1200) / nl * 0.5
            for side, (p0, p1) in enumerate((((x0, -700, -500), (x1, -700, 500)), ((x0, 700, -500), (x1, 700, 500)),
                                             ((x0, -700, 500), (x1, 700, 500)), ((x0, -700, -500), (x1, 700, -500)))):
                lac = self.part(("lacing", side), f"LACING CHS 60x5 B{side + 1}", lambda p0=p0, p1=p1: g.tube(
                    30, 25, float(math.dist(p0, p1))), STEEL)
                self.add(boom, lac, g.on_axis(p0, [b - a for a, b in zip(p0, p1)]))
        heel = self.part("heel", "BOOM HEEL SECTION BH-1", lambda: g.loft([
            [(-400, -900, -650), (-400, 900, -650), (-400, 900, 650), (-400, -900, 650)],
            [(600, -700, -500), (600, 700, -500), (600, 700, 500), (600, -700, 500)]], ruled=False), STEEL)
        self.add(boom, heel)
        tip_b = self.rev == "B"
        if tip_b:
            self.changed.append("BOOM TIP SHEAVE BS-900")
        sheave = self.part(("sheave", tip_b), "BOOM TIP SHEAVE BS-900", lambda: g.sheave(
            450 if not tip_b else 470, 16, 120, 50, 80), DARK, nurbs=True)
        self.add(boom, sheave, g.T(Lb, 0, 0) @ g.Rot((1, 0, 0), 90))
        pin = self.part("boompin", "BOOM FOOT PIN BP-160", lambda: g.cyl(80, 2200, (0, -1100, 0), (0, 1, 0)), DARK)
        self.add(boom, pin)
        hook = self.asm("HOOK BLOCK HB-40")
        self.add(hook, self.part("hooksheaves", "HOOK BLOCK SIDE PLATES HB-40", lambda: g.fuse(
            g.box(-400, -260, -600, 800, 40, 900), g.box(-400, 220, -600, 800, 40, 900), g.cyl(60, 520, (0, -260, 0), (0, 1, 0))),
            ORANGE))
        self.add(hook, self.part("hook", "RAMSHORN HOOK RH-40", lambda: g.fuse(
            g.cyl(60, 400, (0, 0, -1000)),
            g.torus_piece((0, 0, -1150), (0, 1, 0), (180, 0, -1150), math.radians(250), 70)), ORANGE, nurbs=True))
        for k in range(3):
            self.add(hook, self.part("hbsheave", "SHEAVE S-500", lambda: g.sheave(250, 14, 70, 60, 70), DARK, nurbs=True),
                     g.T(0, -140 + 140 * k, 0) @ g.Rot((1, 0, 0), 90))
        import numpy as np
        luff = 50.0
        R = g.Rot((0, 1, 0), -luff)
        down = R[:3, :3].T @ np.array([0.0, 0.0, -1.0])            # straight down at the drawn luff angle
        hook_at = np.array([Lb, 0.0, 0.0]) + 2500.0 * down
        c_hook = self.add(boom, hook, g.T(*hook_at) @ R.T)
        boom.joint("Hoist", "slide", [c_hook], hook_at, down, limits=(-1000.0, 20000.0))
        c_boom = self.add(up, boom, g.T(1900, 0, 1600) @ R)
        up.joint("Boom luff", "rotate", [c_boom], (1900.0, 0.0, 1600.0), (0.0, -1.0, 0.0), limits=(-50.0, 30.0))
        c_up = self.add(a, up, g.T(0, 0, H + 90))
        a.joint("Slew", "rotate", [c_up], (0.0, 0.0, H), (0.0, 0.0, 1.0), limits=(-360.0, 360.0))
        return a

    def davit(self):
        g = self.g
        a = self.asm(DAVIT)
        base = self.part("davbase", "DAVIT BASE DB-400", lambda: g.fuse(
            g.box(-300, -300, 0, 600, 600, 30), g.tube(160, 140, 600, (0, 0, 30))), ORANGE)
        self.add(a, base)
        for sx in (-1, 1):
            for sy in (-1, 1):
                self.bolt_set(a, g.T(sx * 240, sy * 240, 30.1), 20, 30 + 25, 2)
        arm = self.asm("DAVIT ARM DA-2500")
        self.add(arm, self.part("davpost", "DAVIT POST DP-2400", lambda: g.cyl(130, 2400), ORANGE))
        self.add(arm, self.part("davarm", "DAVIT JIB DJ-2500", lambda: g.loft([
            [(0, -100, 2200), (0, 100, 2200), (0, 100, 2450), (0, -100, 2450)],
            [(2500, -60, 2300), (2500, 60, 2300), (2500, 60, 2420), (2500, -60, 2420)]], ruled=False), ORANGE))
        self.add(arm, self.part("davsheave", "SHEAVE S-250", lambda: g.sheave(125, 8, 40, 20, 40), DARK, nurbs=True),
                 g.T(2450, 0, 2280) @ g.Rot((1, 0, 0), 90))
        c = self.add(a, arm, g.T(0, 0, 630))
        a.joint("Davit slew", "rotate", [c], (0.0, 0.0, 630.0), (0.0, 0.0, 1.0), limits=(-180.0, 180.0))
        return a


# ---------------------------------------------------------------------------------------------------------
# counts and the files
# ---------------------------------------------------------------------------------------------------------

def stats(g, root, maker) -> dict:
    from OCP.GeomAbs import GeomAbs_SurfaceType
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    placed = unique_seen = 0
    fasteners = 0
    seen: dict = {}
    depth = 0
    for node, _uid, _W, _label, path in g.walk(root):
        depth = max(depth, len(path))
        if not isinstance(node, g.Part):
            continue
        placed += 1
        n = node.name
        if n.startswith(("ISO ", "DIN ", "Stud bolt", "U-BOLT")):
            fasteners += 1
        if id(node) not in seen:
            seen[id(node)] = node
    faces = bspline = 0
    for node in seen.values():
        ex = TopExp_Explorer(node.shape, TopAbs_FACE)
        while ex.More():
            faces += 1
            t = BRepAdaptor_Surface(TopoDS.Face(ex.Current())).GetType()
            if t in (GeomAbs_SurfaceType.GeomAbs_BSplineSurface, GeomAbs_SurfaceType.GeomAbs_BezierSurface,
                     GeomAbs_SurfaceType.GeomAbs_OffsetSurface, GeomAbs_SurfaceType.GeomAbs_SurfaceOfExtrusion):
                bspline += 1
            ex.Next()
        unique_seen += 1
    return {"placed": placed, "unique": unique_seen, "fasteners": fasteners,
            "fastener_share": round(fasteners / max(1, placed), 3), "faces_unique": faces,
            "bspline_faces": bspline, "bspline_share": round(bspline / max(1, faces), 3), "levels": depth,
            "nurbs_converted": maker.nurbs, "nameless": maker.nameless}


def build(path: str, small: bool = False, revision: str = "A", info_path: str = "") -> dict:
    t0 = time.time()
    g = _geom()
    m = Maker(SMALL if small else FULL, revision)
    root = m.build()
    t_shapes = time.time() - t0
    joints = g.resolve_joints(root)
    g.write_step(root, path)
    info = stats(g, root, m)
    changed = set(m.changed)
    info["changed_unique"] = sorted(changed)
    info["changed_placed"] = sum(1 for n, *_ in g.walk(root) if isinstance(n, g.Part) and n.name in changed)
    info.update({"revision": revision, "small": small, "root": ROOT, "seconds_shapes": round(t_shapes, 1),
                 "seconds": round(time.time() - t0, 1), "mb": round(os.path.getsize(path) / 1e6, 1)})
    with open(os.path.splitext(path)[0] + ".joints.json", "w", encoding="utf-8") as fh:
        json.dump({"root": ROOT, "units": "mm", "joints": joints}, fh, indent=1)
    if info_path:
        with open(info_path, "w", encoding="utf-8") as fh:
            json.dump(info, fh, indent=1)
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out")
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--revision", default="A", choices=("A", "B"))
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    info = build(a.out, a.small, a.revision, a.json)
    print(json.dumps(info), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
