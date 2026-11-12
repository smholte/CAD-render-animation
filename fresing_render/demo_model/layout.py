"""Everything placed on the vessel, the cable route, the ropes, the joint sheet and the files (tasks 0076, 0084).

``build(params)`` makes the scene (no files); ``write(out_dir, params)`` writes the STEP files and the two JSON
sheets. Model coordinates: mm, x to the bow (transom at 0), y to port, z up (waterline 0).

Deck layout (task 0084, the owner's way of working): side A (starboard) and side B (port) lanes of V roller highways
with walkways, the quadrant's middle lane with rails, a lower path beside and below side A. The cable's oval: coil ->
arch -> down the loading tower -> lower path aft -> stern turn -> side B forward (rise, cable engine, tensioner 1) ->
round the D-quadrant -> side A aft (tensioner 2) -> horn A -> sea. The quay file (vessel moored starboard side to)
holds the quay, the storage carousel with its own tower and arch, and the cable from it onto side A's highway.
"""

from __future__ import annotations

import json
import math
import os
import time

import numpy as np

from . import deck as dk
from . import geom as g
from . import machines as m
from . import route as rt
from .geom import Asm, Part, Rot, T
from .params import Params

ROOT = "DEMO CABLE LAY"
FILES = {
    "assembly": "demo_cable_lay.step",
    "vessel": "demo_vessel.step",
    "carousel": "demo_carousel.step",
    "storage_carousel": "demo_storage_carousel.step",
    "tensioner": "demo_tensioner.step",
    "handling_winch": "demo_handling_winch.step",
    "drum_lebus": "demo_drum_lebus.step",
    "quadrant": "demo_quadrant.step",
    "quay_loading": "demo_quay_loading.step",
}
MACHINE_FILES = ("carousel", "storage_carousel", "tensioner", "handling_winch", "quadrant", "quay_loading")
ROUTE_JSON = "demo_cable_route.json"
JOINTS_JSON = "demo_joints.json"

STORAGE_D = 16000.0             # the quay's storage carousel
STORAGE_LAYERS = 11
CPS_LENGTH = 15000.0


def _r(v, n=4):
    return [round(float(x), n) for x in v]


def _pt(W, p):
    return (W @ np.r_[np.asarray(p, float), 1.0])[:3]


def _deg(v) -> float:
    return math.degrees(math.atan2(v[1], v[0]))


class Scene:
    """The built model: assemblies, routes, handles to the parts the sheets name."""

    def __init__(self, p: Params):
        self.p = p
        self.pos = rt.positions(p)
        self.kit = m.Kit(p)
        self.handles: dict = {}          # name -> path of Child objects from the root
        self.files: dict = {}            # key -> root Asm
        self.routes: dict = {}           # model coordinates
        self.ropes: dict = {}
        self.sheaves: list = []          # dicts with "path" (from root) and local data
        self.stations: dict = {}         # roller stations per stretch: lists of (s, x)
        self.info: dict = {}
        self.timings: dict = {}


# ---------------------------------------------------------------------------------------------------------
# Roller stations along the route
# ---------------------------------------------------------------------------------------------------------

def _samples(route: rt.Route, step: float = 150.0):
    """Points along a route with their distance s from its start."""
    pts, ss = [], []
    s0 = 0.0
    for seg in route.segments:
        n = max(2, int(math.ceil(seg.length / step)) + 1)
        for s in np.linspace(0.0, seg.length, n):
            pts.append(seg.point(s))
            ss.append(s0 + s)
        s0 += seg.length
    return np.array(pts), np.array(ss)


def _where(route: rt.Route, s: float):
    acc = 0.0
    for i, seg in enumerate(route.segments):
        if s <= acc + seg.length + 1e-9:
            u = s - acc
            return i, seg.point(u), (seg.tangent(u) if seg.kind == "arc" else seg.tangent())
        acc += seg.length
    seg = route.segments[-1]
    return len(route.segments) - 1, seg.end, seg.end_tangent


class Clearance:
    """Rejects a roller station whose stand would stand in another stretch of cable or in a machine."""

    def __init__(self, p, routes: list, boxes: list):
        self.p = p
        self.clouds = [(_samples(r)) for r in routes]
        self.boxes = boxes               # (x0, x1, y0, y1, z0, z1)

    def ok(self, route_index: int, s0: float, q, t, half_len: float, half_w: float, z_top: float) -> bool:
        th = np.array([t[0], t[1], 0.0])
        th = th / max(np.linalg.norm(th), 1e-9)
        nh = np.cross([0, 0, 1.0], th)
        cr = self.p.cable_r
        for i, (pts, ss) in enumerate(self.clouds):
            sel = pts if i != route_index else pts[np.abs(ss - s0) > 2.0 * half_len + 1500.0]
            d = sel - q
            a = np.abs(d @ th)
            c = np.abs(d @ nh)
            inside = (a < half_len + cr + 50) & (c < half_w + cr + 50) & (sel[:, 2] < z_top + cr + 50)
            if inside.any():
                return False
        corners = [q + sa * half_len * th + sb * half_w * nh for sa in (-1, 1) for sb in (-1, 1)]
        for x0, x1, y0, y1, z0, z1 in self.boxes:
            if z0 > z_top:
                continue
            for c in corners + [q]:
                if x0 <= c[0] <= x1 and y0 <= c[1] <= y1:
                    return False
        return True


def _stations(route: rt.Route, keys: set, step: float, margin: float = 400.0):
    """Every ``step`` along the route's segments whose rollers name is in ``keys``: (s, segment index)."""
    out = []
    acc = 0.0
    for i, (seg, info) in enumerate(zip(route.segments, route.info)):
        if info.get("rollers") in keys and seg.length > 2 * margin:
            n = max(1, int((seg.length - 2 * margin) // step) + 1)
            span = (n - 1) * step
            s_first = acc + 0.5 * (seg.length - span)
            for k in range(n):
                out.append((s_first + k * step, i))
        acc += seg.length
    return out


# ---------------------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------------------

def build(p: Params | None = None, with_lebus: bool = True) -> Scene:
    p = p or Params()
    S = Scene(p)
    pos, kit = S.pos, S.kit
    R, Rq, cr = p.bend_r, p.quadrant_r, p.cable_r
    yA, yB, y_low = pos["side_a_y"], pos["side_b_y"], pos["lower_y"]
    xc = pos["carousel_x"]
    xT = pos["tensioners"][0]
    t0 = time.time()
    root = Asm(ROOT)
    # ---- vessel
    ves = m.vessel(p, pos)
    S.handles["vessel"] = [root.add(ves, instance="VESSEL")]
    S.files["vessel"] = ves
    S.timings["vessel"] = time.time() - t0
    # ---- routes
    main = rt.main_route(p, pos)
    S.routes["main"] = main
    q = quay_positions(p, pos)
    S.info["quay"] = q
    quay_r = rt.quay_route(p, pos, q)
    S.routes["quay_loading"] = quay_r
    cps_r = rt.cps_slide_route(p, pos)
    S.routes["cps_slide"] = cps_r
    # ---- carousel (its cable end through the hole at the foot of the core) + loading tower with the arch
    t = time.time()
    core_local = rt.core_end_route(p, pos["coil_in"], p.turntable_t + cr)
    car = m.carousel(p, kit, core_end=core_local)
    cc = root.add(car, T(xc, 0, 0), "CAROUSEL")
    S.handles["carousel"] = [cc]
    S.routes["core_end"] = _shift(core_local, T(xc, 0, 0))
    ar = pos["arch"]
    G = np.array(ar["guide"])
    L, t1 = rt.lift_off(p, (xc, 0.0), p.coil_r, G, pos["coil_z"])
    tower = dk.loading_tower(p, kit, "LOADING TOWER", ar["span"], pos["arch_z"], p.low_z, p.deck_z, 180.0,
                             _deg(G - [pos["tower_x"], y_low]), _deg(-t1), pos["coil_z"], ar["slew_limits"])
    ctw = root.add(tower, T(pos["tower_x"], y_low, 0), "LOADING TOWER")
    S.handles["tower"] = [ctw]
    spread = Asm("CAROUSEL AND LOADING TOWER")
    spread.add(car, T(0, 0, 0), "CAROUSEL")
    spread.add(tower, T(pos["tower_x"] - xc, y_low, 0), "LOADING TOWER")
    S.files["carousel"] = spread
    S.timings["carousel"] = time.time() - t
    # ---- the quay's storage carousel (also its own file)
    t = time.time()
    storage = m.carousel(p, kit, name="STORAGE CAROUSEL", outer_d=q["outer_d"], rim_h=3500.0, layers=STORAGE_LAYERS,
                         rest_r=q["rest_r"], base_frame=True)
    S.files["storage_carousel"] = storage
    S.timings["storage_carousel"] = time.time() - t
    # ---- tensioners: 1 on side B (cable forward, hinge aft), 2 on side A (cable aft, hinge aft)
    t = time.time()
    ten1 = m.tensioner(p, kit, hinge_end=+1)
    ten2 = m.tensioner(p, kit, hinge_end=-1)
    S.files["tensioner"] = ten2
    S.handles["tensioner1"] = [root.add(ten1, T(xT, yB, p.line_z) @ Rot((0, 0, 1), 180.0), "TENSIONER 1")]
    S.handles["tensioner2"] = [root.add(ten2, T(xT, yA, p.line_z), "TENSIONER 2")]
    S.timings["tensioner"] = time.time() - t
    # ---- linear cable engine on side B
    ce = dk.cable_engine(p, kit)
    S.handles["cable_engine"] = [root.add(ce, T(pos["engine_x"], yB, p.line_z) @ Rot((0, 0, 1), 180.0), "CABLE ENGINE")]
    # ---- handling winches (starboard, outboard of the lower path; their ropes inboard)
    t = time.time()
    hw = m.winch(p, kit, "HANDLING WINCH", p.handling_rope_d, 600.0, 1600.0, layers=4, wound=0.6, fairlead=True)
    S.files["handling_winch"] = hw
    for k, x in enumerate((pos["quadrant_x"] - 3000.0, pos["quadrant_x"] + 3500.0)):
        c = root.add(hw, T(x, y_low - 3450.0, p.deck_z) @ Rot((0, 0, 1), 90.0), f"HANDLING WINCH {k + 1}")
        S.handles[f"handling_winch_{k + 1}"] = [c]
        fl = hw.info["fairlead"]
        S.sheaves.append({"name": f"Fairlead sheave (handling winch {k + 1})", "path": [c, fl["child"]],
                          "pitch_r": fl["pitch_r"], "groove_r": fl["groove_r"], "carries": "wire rope"})
    S.timings["handling_winch"] = time.time() - t
    # ---- horns at the stern ends of the side lanes (side A carries the cable)
    for key, y in (("A", yA), ("B", yB)):
        o = np.array([pos["horn_x"], y, p.line_z - R])
        ch = m.chute(p, kit, R, pos["chute_deg"], p.deck_z - o[2], 0.0 - o[0])
        S.handles[f"horn_{key}"] = [root.add(ch, T(*o), f"HORN {key}")]
    # ---- stern turn under the quadrant's rails
    st = dk.flat_bend(p, kit, pos["stern_turn_r"], p.low_z, p.deck_z)
    S.handles["stern_turn"] = [root.add(st, T(pos["stern_turn_x"], pos["stern_turn_y"], 0), "STERN RADIUS CONTROLLER")]
    # ---- quadrant system: D-quadrant, rails, handler, handling winch, tipping winches + swivel sheaves, wires
    t = time.time()
    qs = quadrant_system(p, S)
    S.handles["quadrant_system"] = [root.add(qs, T(0, 0, 0), "QUADRANT SYSTEM")]
    S.files["quadrant"] = qs
    S.timings["quadrant"] = time.time() - t
    # ---- roller stations: V cradles on the highways, rollers on stands on the lower path
    t = time.time()
    _roller_stations(p, S, root)
    S.timings["stations"] = time.time() - t
    # ---- walkways beside the highways
    wz = p.line_z - 1000.0
    T_out = (xT - rt.TENSIONER_HALF - 300.0, xT + rt.TENSIONER_HALF + 300.0)
    for name, y_in, y_out, ranges in (
            ("B", yB + 650.0, yB + 1200.0, [(pos["stern_turn_x"] + 600.0, pos["engine_x"] - rt.ENGINE_HALF - 300.0)]),
            ("A", yA - 650.0, yA - 1350.0, [(pos["stern_turn_x"] + 600.0, T_out[0]), (T_out[1], pos["s_bend_x"])])):
        for k, (x0, x1) in enumerate(ranges):
            if x1 - x0 > 1500.0:
                root.add(dk.walkway(x0, x1, y_in, y_out, wz), T(0, 0, 0), f"WALKWAY {name}{k + 1}")
    # ---- CPS store: rack with five sets, the orange twisted ramp and the curved slide
    t = time.time()
    _cps_store(p, S, root)
    S.timings["cps"] = time.time() - t
    # ---- the cable along the oval (a static solid for stills)
    cable = Part("CABLE", g.route_solid(main, cr), m.CABLE_BLACK)
    S.handles["cable"] = [root.add(cable, instance="CABLE")]
    # ---- the quay (its own file; placed for the vessel moored starboard side to)
    t = time.time()
    S.files["quay_loading"] = quay_loading(p, S, storage)
    S.timings["quay"] = time.time() - t
    # ---- Lebus drum (separate file only)
    if with_lebus:
        t = time.time()
        S.files["drum_lebus"] = m.lebus_drum(p, p.handling_rope_d, 600.0, 1600.0)
        S.timings["drum_lebus"] = time.time() - t
    S.files["assembly"] = root
    S.root = root
    S.timings["total"] = time.time() - t0
    return S


def _roller_stations(p, S: Scene, root: Asm) -> None:
    pos, kit = S.pos, S.kit
    main = S.routes["main"]
    xT = pos["tensioners"][0]
    boxes = []
    for y in (pos["side_a_y"], pos["side_b_y"]):           # the tensioners, the cable engine
        boxes.append((xT - rt.TENSIONER_HALF - 200, xT + rt.TENSIONER_HALF + 200, y - rt.TENSIONER_WIDTH,
                      y + rt.TENSIONER_WIDTH, -1e9, 1e9))
    boxes.append((pos["engine_x"] - rt.ENGINE_HALF - 200, pos["engine_x"] + rt.ENGINE_HALF + 200,
                  pos["side_b_y"] - 1100, pos["side_b_y"] + 1100, -1e9, 1e9))
    boxes.append((pos["tower_x"] - 1700, pos["tower_x"] + 1700, pos["lower_y"] - 1700, pos["lower_y"] + 1700, -1e9, 1e9))
    for sy in (-1, 1):                                      # the rails' girders (stations must not stand on them)
        boxes.append((pos["pulley_x"], pos["quadrant_apex_x"], sy * dk.RAIL_Y - 300, sy * dk.RAIL_Y + 300, -1e9, 1e9))
    clear = Clearance(p, [main, S.routes["quay_loading"]], boxes)
    cradle = dk.cradle(p, kit)
    lower_roller = kit.roller(125.0, 700.0)
    rr = 125.0
    S.stations = {"highway": [], "lower path": []}
    n_hw, n_lp = 0, 0
    hw_keys = {"side A", "side B", "side B rise", "side B bend", "side A bend"}
    for s, i in _stations(main, hw_keys | {"lower path"}, p.roller_step):
        _i, q, t = _where(main, s)
        info = main.info[i]
        if info.get("rollers") == "side A" and q[0] < pos["horn_x"] + 700.0:
            continue
        if info.get("rollers") == "lower path":
            axle_z = q[2] - p.cable_r - rr
            if not clear.ok(0, s, q, t, 250.0, 520.0, q[2]):
                continue
            n_lp += 1
            ax = np.cross([0, 0, 1.0], t)
            part, M = dk.roller_about(kit, [q[0], q[1], axle_z], ax, rr, 700.0)
            c = root.add(part, M, f"LOWER PATH ROLLER {n_lp}")
            stand = kit.roller_stand(axle_z - p.deck_z, 900.0)
            root.add(stand, T(q[0], q[1], p.deck_z) @ Rot((0, 0, 1), _deg(t) + 90.0), f"LOWER PATH STAND {n_lp}")
            ctr = np.array([q[0], q[1], axle_z])
            root.joint(f"Lower path roller {n_lp} turn", "rotate", [c], ctr,
                       m.turn_axis(ctr, ctr + [0, 0, rr], t), None, m.cable_drive(rr))
            S.stations["lower path"].append(round(float(s), 1))
            continue
        if not clear.ok(0, s, q, t, 250.0, 650.0, q[2]):
            continue
        n_hw += 1
        up = np.array([0, 0, 1.0]) - t * t[2]
        up /= np.linalg.norm(up)
        M = g.Frame(q, -t, up)
        root.add(cradle, M, f"CRADLE {n_hw}")
        base = _pt(M, [0, 0, -dk.CRADLE_BASE - 40.0])
        h = base[2] - p.deck_z
        root.add(dk.trestle(kit, h), T(base[0], base[1], p.deck_z) @ Rot((0, 0, 1), _deg(t)), f"TRESTLE {n_hw}")
        S.stations["highway"].append(round(float(s), 1))


def quay_positions(p, pos: dict) -> dict:
    """The quay and its loading tower and storage carousel (model coordinates, vessel moored starboard side to)."""
    R, cr = p.bend_r, p.cable_r
    q: dict = {}
    q["edge_y"] = -(p.beam / 2.0 + 1500.0)
    q["z"] = p.deck_z + 500.0
    xb = pos["board_x"]
    q["tower_xy"] = [xb, min(q["edge_y"] - 3500.0, -p.lane_y - R - 3000.0) - R]
    q["outer_d"] = max(STORAGE_D, 2.0 * (p.core_r + 3700.0))
    Ro = q["outer_d"] / 2.0
    q["carousel_xy"] = [xb - 2000.0, q["tower_xy"][1] - (Ro + 600.0 + 1800.0 + 200.0)]
    q["carousel_z"] = q["z"] + 1200.0                     # the turntable's underside (the base frame under it)
    coil_in, coil_out = p.core_r + 60.0, Ro - 300.0
    q["rest_r"] = p.core_r + 0.5 * (coil_out - p.core_r)
    q["coil_z"] = q["carousel_z"] + p.turntable_t + STORAGE_LAYERS * p.cable_d + cr
    rim_top = q["carousel_z"] + p.turntable_t + 3500.0
    q["arch_z"] = max(p.arch_h, q["coil_z"] + 2 * R + 1000.0, rim_top + R + 1500.0)
    arch = rt.arch_geometry(p, q["tower_xy"], q["carousel_xy"], (p.core_r + rt.GUIDE_IN, coil_out - cr), q["rest_r"],
                            Ro)
    q["arch"] = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in arch.items()}
    return q


def quadrant_system(p, S: Scene) -> Asm:
    """In model coordinates: the D-quadrant at its stationary position (the oval's forward turn), its rails along
    the middle lane, the quadrant handler at the stern, the quadrant handling winch in front of the carousel (its
    wire over the handler's top pulley, parked on the handler), two tipping winches on the stern with swivel sheaves
    (their wires parked: they are connected when the quadrant is on the handler)."""
    pos, kit = S.pos, S.kit
    Rq = p.quadrant_r
    qs = Asm("QUADRANT SYSTEM")
    xq = pos["quadrant_x"]
    # D-quadrant
    quad = dk.quadrant_d(p, kit)
    cq = qs.add(quad, T(xq, 0, p.rail_z), "QUADRANT")
    qs.joint("Quadrant travel", "slide", [cq], (xq, 0, p.rail_z), (-1, 0, 0), [0.0, round(pos["quadrant_travel"], 3)],
             {"by": "operator", "note": "travels aft on its rails (positive) from its stationary position (0, the "
                                        "cable's forward turn) onto the quadrant handler at the stern"})
    hang = _pt(T(xq, 0, p.rail_z), quad.info["hang_off"])
    qs.joint("Quadrant tip", "rotate", [cq], hang, (0, -1, 0), [-180.0, 180.0],
             {"by": "operator", "note": "turns about the hang-off point (the handling wire) along the bar: positive "
                                        "lifts the curve; on the handler it rides the handler's tilt (task 0082 "
                                        "decides the order)"}, rides_on="Quadrant travel")
    # rails on girders and trestles along the middle lane (they bridge the stern turn)
    x0, x1 = pos["pulley_x"] + 50.0, pos["quadrant_apex_x"]
    route_pts, _ss = _samples(S.routes["main"])
    for sy in (-1, 1):
        y = sy * dk.RAIL_Y
        qs.add(dk.rail_girder(x0, x1), T(0, y, p.rail_z), "QUADRANT RAIL")
        h = p.rail_z - 400.0 - p.deck_z
        post = kit.get(("rail_post", round(h)), lambda: Part("RAIL TRESTLE", g.fuse(
            g.box(-150, -200, 0, 300, 400, h + 1), g.box(-300, -300, 0, 600, 600, 30)), m.YELLOW))
        for x in np.arange(x0 + 300.0, x1, 3000.0):
            d = route_pts - [x, y, 0]
            near = (np.abs(d[:, 0]) < 300 + p.cable_r + 300) & (np.abs(d[:, 1]) < 300 + p.cable_r + 300) & \
                   (route_pts[:, 2] < p.rail_z)
            if not near.any():
                qs.add(post, T(x, y, p.deck_z))
    # quadrant handler
    z_h = p.rail_z - 400.0
    hd = dk.quadrant_handler(p, kit, pos["handler_len"], z_h, p.deck_z)
    ch = qs.add(hd, T(pos["hinge_x"], 0, z_h), "QUADRANT HANDLER")
    S.sheaves.append({"name": "Handler top pulley (quadrant handling wire)", "path": [ch] + hd.info["pulley_path"],
                      "pitch_r": hd.info["pulley_r"], "groove_r": p.quadrant_rope_d / 2, "carries": "wire rope",
                      "local": True})
    # quadrant handling winch in front of the carousel, on a pedestal; its wire over the D to the handler's pulley
    qw = m.winch(p, kit, "QUADRANT HANDLING WINCH", p.quadrant_rope_d, 700.0, 1400.0, layers=5, wound=0.7,
                 fairlead=False)
    xw = pos["qh_winch_x"]
    qs.add(Part("WINCH PEDESTAL", g.box(xw - 1500, -1700, p.deck_z, 3000, 3400, 300), m.YELLOW))
    cqw = qs.add(qw, T(xw, 0, p.deck_z + 300.0) @ Rot((0, 0, 1), 180.0), "QUADRANT HANDLING WINCH")
    dz = qw.info["drum_centre"][2] + p.deck_z + 300.0
    pc = _pt(T(pos["hinge_x"], 0, z_h), hd.info["pulley_centre"])
    rp = hd.info["pulley_r"]
    ropes = {}
    hr = rt.rope_route("quadrant handling wire", p.quadrant_rope_d, 0.0, [
        ("sheave", (xw, dz), qw.info["rope_centre_r"], +1, {"name": "drum"}),
        ("sheave", (pc[0], pc[2]), rp, +1, {"name": "handler top pulley"}),
        ("point", (pc[0] - rp, p.rail_z + 150.0))])
    ropes["quadrant handling wire"] = hr
    qs.add(Part("WIRE ROPE", g.route_solid(hr, p.quadrant_rope_d / 2), m.ROPE_GREY))
    qs.add(_shackle(p.quadrant_rope_d), T(pc[0] - rp, 0, p.rail_z + 150.0))
    # tipping winches (port, starboard) and their swivel sheaves on the stern
    tw = m.winch(p, kit, "TIPPING WINCH", p.tipping_rope_d, 400.0, 800.0, layers=4, wound=0.5, fairlead=False)
    trp = max(8 * p.tipping_rope_d, 288.0)
    sw = dk.swivel_sheave(p, kit, p.tipping_rope_d, trp, pos["swivel_sheave"][2] - p.deck_z)
    tips = {}
    for key, sy in (("port", 1.0), ("stb", -1.0)):
        wxy = np.array([pos["tipping_winch"][0], sy * pos["tipping_winch"][1]])
        sxy = np.array([pos["swivel_sheave"][0], sy * pos["swivel_sheave"][1]])
        u = (sxy - wxy) / np.linalg.norm(sxy - wxy)
        ang = _deg(u)
        cw = qs.add(tw, T(wxy[0], wxy[1], p.deck_z) @ Rot((0, 0, 1), ang), f"TIPPING WINCH {key.upper()}")
        cs = qs.add(sw, T(sxy[0], sxy[1], p.deck_z) @ Rot((0, 0, 1), ang), f"SWIVEL SHEAVE {key.upper()}")
        dist = float(np.linalg.norm(sxy - wxy))
        zs = pos["swivel_sheave"][2]
        r = rt.rope_route(f"tipping wire {key}", p.tipping_rope_d, 0.0, [
            ("sheave", (0.0, tw.info["drum_centre"][2] + p.deck_z), tw.info["rope_centre_r"], -1, {"name": "drum"}),
            ("sheave", (dist, zs), trp, -1, {"name": "swivel sheave"}),
            ("point", (dist + trp, p.deck_z + 1200.0))], origin=wxy, udir=u)
        ropes[f"tipping wire {key}"] = r
        qs.add(Part("WIRE ROPE", g.route_solid(r, p.tipping_rope_d / 2), m.ROPE_GREY))
        qs.add(_shackle(p.tipping_rope_d), T(*(sxy + u * trp), p.deck_z + 1200.0) @ Rot((0, 0, 1), ang))
        qs.joint(f"Swivel sheave {key} swivel", "rotate", [[cs, sw.info["head"]]], (sxy[0], sxy[1], 0), (0, 0, 1),
                 [-120.0, 120.0], {"by": "follows wire", "note": "the head turns about the post to follow the "
                                                                 "tipping wire to the quadrant (task 0082)"})
        qs.joint(f"Swivel sheave {key} turn", "rotate", [[cs, sw.info["head"], sw.info["sheave"]]],
                 (sxy[0], sxy[1], zs), (-u[1], u[0], 0.0), None,
                 m.cable_drive(trp, note="turned by the tipping wire (positive = paying out)"))
        tips[key] = {"winch": cw, "sheave": cs, "sheave_centre": [sxy[0], sxy[1], zs], "u": u.tolist()}
        S.sheaves.append({"name": f"Swivel tipping sheave ({key})", "path": [cs, sw.info["head"], sw.info["sheave"]],
                          "pitch_r": trp, "groove_r": p.tipping_rope_d / 2, "carries": "wire rope", "local": True})
    S.quadrant_info = {"quadrant": cq, "handler": ch, "ropes": ropes, "tipping": tips, "hang": hang,
                       "quad_asm": quad, "handler_asm": hd, "qh_winch": cqw}
    return qs


def _shackle(d: float) -> Part:
    return Part("SHACKLE", g.fuse(g.torus_piece((0, 0, -2.2 * d), (0, 1, 0), (1.2 * d, 0, -2.2 * d), 2 * math.pi, d * 0.45),
                                  g.cyl(d * 0.6, 1.8 * d, (0, -0.9 * d, -0.9 * d), (0, 1, 0))), m.STEEL)


def _cps_store(p, S: Scene, root: Asm) -> None:
    pos, kit = S.pos, S.kit
    route = S.routes["cps_slide"]
    start = route.segments[0].start
    cps = dk.cps_set(p, kit, CPS_LENGTH)
    R0 = cps.info["outer_r"]
    x1 = start[0] + 300.0
    x0 = x1 - CPS_LENGTH - 500.0
    rows = [start[1], start[1] + 1200.0]
    levels = [p.deck_z + 1200.0, p.deck_z + 2400.0, pos["cps_shelf_z"]]
    root.add(dk.cps_rack(x0, x1, rows, levels, p.deck_z, R0), T(0, 0, 0), "CPS RACK")
    n_sets = 0
    for z in levels:
        for y in rows:
            if z == levels[0] and y == rows[1]:
                continue                                      # one slot empty: five sets
            n_sets += 1
            root.add(cps, T(x1 - 200.0, y, z) @ Rot((0, 0, 1), 180.0), f"CPS SET {n_sets}")
    ramp_len = route.segments[0].length
    ramp, _ = dk.trough_along(route, 0.0, ramp_len, R0, twist_deg=30.0)
    root.add(Part("CPS RAMP", ramp, dk.ORANGE), T(0, 0, 0), "CPS RAMP")
    # the slide: the arcs, ending where it is clear of side B's cradles
    s_end = route.length
    for s in np.arange(ramp_len, route.length, 100.0):
        _i, q, _t = _where(route, s)
        if abs(q[1] - pos["side_b_y"]) < 900.0:
            s_end = s
            break
    slide, pts = dk.trough_along(route, ramp_len, s_end, R0, step=300.0)
    root.add(Part("CPS SLIDE", slide, dk.ORANGE), T(0, 0, 0), "CPS SLIDE")
    # supports from the deck every ~3 m under ramp and slide
    for k, s in enumerate(np.arange(1500.0, s_end, 3000.0)):
        _i, q, _t = _where(route, s)
        h = q[2] - 0.75 * (R0 + 120.0) - p.deck_z
        root.add(Part("RAMP SUPPORT", g.fuse(g.box(-120, -120, 0, 240, 240, h + 20),
                                             g.box(-300, -300, 0, 600, 600, 30)), m.YELLOW), T(q[0], q[1], p.deck_z),
                 f"RAMP SUPPORT {k + 1}")
    S.info["cps"] = {"rack": [x0, x1], "rows_y": rows, "levels_z": levels, "length": cps.info["length"],
                     "outer_r": R0, "sets": n_sets}


def quay_loading(p, S: Scene, storage: Asm) -> Asm:
    """The quay file: quay, storage carousel, quay loading tower with its arch, cable rollers across the quay, the
    boarding stands and the 90° boarding bend on the vessel's deck, and the cable along the loading route."""
    pos, kit, q = S.pos, S.kit, S.info["quay"]
    R, cr = p.bend_r, p.cable_r
    a = Asm("QUAY LOADING")
    a.add(dk.quay(-30000.0, 40000.0, q["edge_y"], 30000.0, q["z"]), T(0, 0, 0), "QUAY")
    cxy = q["carousel_xy"]
    a.add(storage, T(cxy[0], cxy[1], q["carousel_z"]), "STORAGE CAROUSEL")
    ar = q["arch"]
    G = np.array(ar["guide"])
    _L, t1 = rt.lift_off(p, cxy, q["rest_r"], G, q["coil_z"])
    tw = dk.loading_tower(p, kit, "QUAY LOADING TOWER", ar["span"], q["arch_z"], p.line_z, q["z"], 90.0,
                          _deg(G - q["tower_xy"]), _deg(-t1), q["coil_z"], ar["slew_limits"])
    a.add(tw, T(q["tower_xy"][0], q["tower_xy"][1], 0), "QUAY LOADING TOWER")
    route = S.routes["quay_loading"]
    # rollers on stands along the quay, cradles on the vessel's deck before the boarding bend
    cradle = dk.cradle(p, kit)
    n = 0
    for s, i in _stations(route, {"quay"}, p.roller_step):
        _i, qq, t = _where(route, s)
        on_quay = qq[1] < q["edge_y"] - 600.0
        on_deck = qq[1] > -(p.beam / 2.0) + 1200.0
        if not (on_quay or on_deck):
            continue
        n += 1
        up = np.array([0, 0, 1.0])
        M = g.Frame(qq, -t, up)
        a.add(cradle, M, f"QUAY CRADLE {n}")
        base = _pt(M, [0, 0, -dk.CRADLE_BASE - 40.0])
        z0 = q["z"] if on_quay else p.deck_z
        a.add(dk.trestle(kit, base[2] - z0), T(base[0], base[1], z0) @ Rot((0, 0, 1), _deg(t)), f"QUAY TRESTLE {n}")
    # the boarding bend onto side A's highway (90°, heading forward)
    bend = route.segments[-1]
    bb = dk.flat_bend(p, kit, R, p.line_z, p.deck_z, 180.0, 90.0, "BOARDING RADIUS CONTROLLER", "Boarding bend")
    a.add(bb, T(bend.centre[0], bend.centre[1], 0), "BOARDING RADIUS CONTROLLER")
    a.add(Part("CABLE", g.route_solid(route, cr), m.CABLE_BLACK), instance="CABLE")
    a.info["route"] = route
    return a


# ---------------------------------------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------------------------------------


def _shift(route: rt.Route, M) -> rt.Route:
    """The route moved by a rigid matrix (local -> model)."""
    out = rt.Route(route.name, route.diameter)
    for seg, info in zip(route.segments, route.info):
        if seg.kind == "line":
            s2 = rt.Line(_pt(M, seg.p0), _pt(M, seg.p1))
        else:
            s2 = rt.Arc(_pt(M, seg.centre), M[:3, :3] @ seg.normal, _pt(M, seg.p0), seg.angle)
        out.segments.append(s2)
        out.info.append(dict(info))
    return out


def tensioner_grips(S: Scene) -> list:
    """Each tensioner's gripping run (model coordinates): where its tracks' contact runs hold the cable."""
    out = []
    for k in (1, 2):
        path = S.handles[f"tensioner{k}"]
        W = g.path_matrix(np.eye(4), path)
        ten = path[-1].node
        a0, a1 = ten.info["grip_run"]
        out.append([_r(_pt(W, [a0, 0, 0])), _r(_pt(W, [a1, 0, 0]))])
    return out


def route_sheet(S: Scene) -> dict:
    p, pos, root = S.p, S.pos, S.root
    ruid = f"{ROOT}#1"
    uid = lambda path: g.path_uid(ruid, path)  # noqa: E731
    W = lambda path: g.path_matrix(np.eye(4), path)  # noqa: E731
    main = S.routes["main"].to_dict()
    tower_uid = uid(S.handles["tower"])
    on = {"guide cage": tower_uid + "/LOADING ARCH#1/GUIDE CAGE#1", "guide frame": tower_uid + "/LOADING ARCH#1",
          "arch": tower_uid + "/LOADING ARCH#1", "tower foot": tower_uid + "/TOWER FOOT#1",
          "stern turn": uid(S.handles["stern_turn"]), "horn A": uid(S.handles["horn_A"]),
          "quadrant gutter": uid(S.handles["quadrant_system"]) + "/QUADRANT#1"}
    for seg in main["segments"]:
        if seg.get("support") == "coil":
            seg["on"] = uid(S.handles["carousel"]) + "/CAROUSEL TURNTABLE#1/CABLE COIL#1"
        elif seg.get("rollers") in on:
            seg["on"] = on[seg["rollers"]]
    qi = S.quadrant_info
    QW = W(S.handles["quadrant_system"])
    ropes = [_shift(r, QW).to_dict() for r in qi["ropes"].values()]
    sheaves = []
    for sh in S.sheaves:
        path = S.handles["quadrant_system"] + sh["path"] if sh.get("local") else sh["path"]
        Wf = W(path)
        sheaves.append({"name": sh["name"], "uid": uid(path), "centre": _r(_pt(Wf, [0, 0, 0])),
                        "axis": _r(Wf[:3, :3] @ np.array([0, 0, 1.0]), 6),
                        "pitch_radius": sh["pitch_r"], "groove_radius": sh["groove_r"], "carries": sh["carries"],
                        "note": "the groove is a torus: major radius = pitch radius (the rope's centre)"})
    tens = []
    grips = tensioner_grips(S)
    for k in (1, 2):
        path = S.handles[f"tensioner{k}"]
        Wt = W(path)
        ten = path[-1].node
        tracks = []
        for tr in ten.info["tracks"]:
            tracks.append({
                "name": tr["name"],
                "pads": [uid(path + tr["chain"] + [c]) for c in tr["pads"]],
                "back_plates": [uid(path + tr["chain"] + [c]) for c in tr["plates"]],
                "links": [uid(path + tr["chain"] + [c]) for c in tr["links"]],
                "pins": [_r(_pt(Wt, q)) for q in tr["pins"]],
                "sprockets": {k2: _r(_pt(Wt, v)) for k2, v in tr["sprockets"].items()},
                "sprocket_axis": _r(Wt[:3, :3] @ np.array([0.0, 1.0, 0.0]), 6),
                "pitch": tr["pitch"], "sprocket_pitch_radius": round(tr["sprocket_pitch_r"], 4),
                "contact_run": tr["contact_run"], "travel": tr["travel"]})
        tens.append({"name": f"TENSIONER {k}", "uid": uid(path), "centre": _r(_pt(Wt, [0, 0, 0])),
                     "side": "B (port), cable forward" if k == 1 else "A (starboard), cable aft",
                     "pads_per_track": p.pads_per_track, "gripping_run_links": p.links_per_run,
                     "pad_v_deg": p.pad_v_deg, "squeeze_h": round(ten.info["squeeze_h"], 4),
                     "lift_limits": _r(ten.info["lift_limits"], 3), "tilt_hinge": _r(_pt(Wt, ten.info["hinge"])),
                     "grip_line": grips[k - 1], "tracks": tracks})
    car = S.handles["carousel"][-1].node
    xc = pos["carousel_x"]
    quad = qi["quad_asm"]
    qpath = S.handles["quadrant_system"] + [qi["quadrant"]]
    QD = W(qpath)
    hpath = S.handles["quadrant_system"] + [qi["handler"]]
    HD = W(hpath)
    hd = qi["handler_asm"]
    tower = S.handles["tower"][-1].node
    q = S.info["quay"]
    cps = S.info["cps"]
    return {
        "about": "Invented cable-lay spread (tasks 0076, 0084, the owner's deck layout): the cable's centreline as "
                 "straights and arcs, what each part of it lies on, sheaves, tensioner tracks, ropes, the quadrant, "
                 "the CPS store and the quay. Model coordinates of demo_cable_lay.step (mm, x to the bow with the "
                 "transom at 0, y to port, z up, waterline 0). Side A = starboard, side B = port. Arcs: the start "
                 "point turned about the axis (centre, normal) by angle, right hand.",
        "units": "mm",
        "cable": {"diameter": p.cable_d, "mbr": p.mbr, "bend_radius": p.bend_r,
                  "solid": uid(S.handles["cable"]), "solid_radius": p.cable_r,
                  "cable_end_solid": uid(S.handles["carousel"]) + "/CAROUSEL TURNTABLE#1/CABLE END#1"},
        "routes": [main, S.routes["core_end"].to_dict(), S.routes["cps_slide"].to_dict(),
                   S.routes["quay_loading"].to_dict()],
        "route_notes": {
            "main": "the oval during lay: coil -> arch -> tower -> lower path aft (side A, outboard and below) -> "
                    "stern turn -> side B forward through tensioner 1 -> round the quadrant -> side A aft through "
                    "tensioner 2 -> horn A -> sea. Loading from the quay is the same route backwards from side A.",
            "core_end": "the cable's end at the carousel's core: along the core, through the hole at its foot, "
                        "into the clamp (turns with the carousel)",
            "cps_slide": "a CPS's way from the rack's top shelf down the orange twisted ramp and the curved slide "
                         "onto side B's highway (task 0082)",
            "quay_loading": "demo_quay_loading.step: from the quay's storage carousel over its arch, across the quay, "
                            "over the vessel's starboard side at the stern and round the boarding bend onto side A's "
                            "highway heading forward, where it meets the main route"},
        "ropes": ropes,
        "sheaves": sheaves,
        "tensioners": tens,
        "carousel": {"uid": uid(S.handles["carousel"]), "centre": [xc, 0.0, 0.0], "axis": [0.0, 0.0, -1.0],
                     "turn_note": "turns clockwise seen from above (about -z) while paying out",
                     "coil": {k: (round(v + 0.0, 3) if isinstance(v, float) else v) for k, v in car.info["coil"].items()},
                     "rest_coil_radius": p.coil_r},
        "loading_arch": {"uid": tower_uid, "axis_point": [pos["tower_x"], pos["lower_y"], 0.0], "axis": [0, 0, 1.0],
                         "span": round(tower.info["span"], 3), "guide_rest": _r(pos["arch"]["guide"]),
                         "slew_limits": _r(pos["arch"]["slew_limits"], 3),
                         "coil_radii": _r(pos["arch"]["coil_radii"], 3),
                         "note": "the arch only slews; the guide's coil radius rho follows from the angle: the guide "
                                 "lies at hypot(rho, bend radius) from the carousel's centre"},
        "quadrant": {"uid": uid(qpath), "curve_centre": _r(_pt(QD, [0, 0, quad.info["cable_z"]])),
                     "radius": quad.info["radius"], "axis": [0.0, 0.0, 1.0],
                     "hang_off": _r(qi["hang"]),
                     "pad_eyes": {k: _r(_pt(QD, v)) for k, v in quad.info["eyes"].items()},
                     "rails_y": [-dk.RAIL_Y, dk.RAIL_Y], "rail_top_z": p.rail_z,
                     "travel": [0.0, round(pos["quadrant_travel"], 3)], "travel_direction": [-1.0, 0.0, 0.0],
                     "handler": {"uid": uid(hpath), "hinge": _r(_pt(HD, [0, 0, 0])), "axis": [0.0, -1.0, 0.0],
                                 "tilt": [0.0, 100.0], "length": pos["handler_len"],
                                 "top_pulley": _r(_pt(HD, hd.info["pulley_centre"])),
                                 "cylinders": [{"barrel": uid(hpath + c["barrel"]), "rod": uid(hpath + c["rod"]),
                                                "barrel_pin": _r(_pt(HD, c["barrel_pin"])),
                                                "rod_pin": _r(_pt(HD, c["rod_pin"]))} for c in hd.info["cylinders"]]}},
        "cps_store": {"rack_x": _r(cps["rack"]), "rows_y": _r(cps["rows_y"]), "levels_z": _r(cps["levels_z"]),
                      "sets": cps["sets"], "set_length": round(cps["length"], 1), "outer_radius": cps["outer_r"],
                      "parts": "pull head (steel), grey tube, yellow segments, brown vertebrae, grey sleeve, yellow "
                               "bend restrictors"},
        "quay": {"file": FILES["quay_loading"], "edge_y": q["edge_y"], "top_z": q["z"],
                 "storage_carousel_centre": _r(list(q["carousel_xy"]) + [q["carousel_z"]]),
                 "tower": _r(list(q["tower_xy"]) + [0.0]), "moored": "starboard side to the quay"},
        "roller_stations": S.stations,
        "positions": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in pos.items()},
    }


def joint_sheet(S: Scene) -> dict:
    joints = g.resolve_joints(S.root)
    machines = {}
    for key in MACHINE_FILES:
        machines[FILES[key]] = g.resolve_joints(S.files[key])
    return {
        "about": "Every joint a set-up should make (tasks 0076, 0084; task 0077 makes them by script). Axis point and "
                 "direction in model coordinates (mm) of demo_cable_lay.step; parts are the importer's uids "
                 "(the node path NAME#n/…). A rotate joint turns the parts right-handed about the axis direction "
                 "(degrees), a slide joint moves them along it (mm); 0 = as modelled. drive.by: 'cable' = turned by "
                 "the cable or a rope running over it (deg_per_mm of payout, positive = paying out towards the "
                 "sea), 'follows' = a ratio of another joint, 'carousel' / 'winch' / 'operator' = driven on its own. "
                 "rides_on: the joint whose parts carry this joint's axis (a stacked joint). machine_files: the same "
                 "joints in each separate machine file's own coordinates.",
        "units": {"length": "mm", "angle": "deg"},
        "model": FILES["assembly"],
        "joints": joints,
        "machine_files": machines,
    }


def write(out_dir: str, p: Params | None = None, log=print, only: tuple = (), progress=None) -> Scene:
    """Write the files (``only``: these keys of FILES, else all) and the two sheets. ``progress(done, total)`` is
    called before each file (the app's demo project shows "Writing the model 2/3")."""
    os.makedirs(out_dir, exist_ok=True)
    S = build(p, with_lebus=not only or "drum_lebus" in only)
    keys = [k for k in FILES if k in S.files and (not only or k in only)]
    for i, key in enumerate(keys):
        fname = FILES[key]
        if progress:
            progress(i, len(keys))
        t = time.time()
        g.write_step(S.files[key], os.path.join(out_dir, fname))
        S.timings["write " + fname] = time.time() - t
        log(f"{fname}: {os.path.getsize(os.path.join(out_dir, fname)) / 1e6:.2f} MB, "
            f"{g.count_parts(S.files[key])} placed parts")
    with open(os.path.join(out_dir, ROUTE_JSON), "w", encoding="utf-8") as fh:
        json.dump(route_sheet(S), fh, indent=1)
    with open(os.path.join(out_dir, JOINTS_JSON), "w", encoding="utf-8") as fh:
        json.dump(joint_sheet(S), fh, indent=1)
    log(f"{ROUTE_JSON}, {JOINTS_JSON}: written")
    return S
