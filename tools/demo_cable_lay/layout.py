"""Everything placed on the vessel, the cable route, the ropes, the joint sheet and the files (task 0076).

``build(params)`` makes the scene (no files); ``write(out_dir, params)`` writes the STEP files and the two JSON
sheets. Model coordinates: mm, x to the bow (transom at 0), y to port, z up (waterline 0).
"""

from __future__ import annotations

import json
import math
import os
import time

import numpy as np

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
}
ROUTE_JSON = "demo_cable_route.json"
JOINTS_JSON = "demo_joints.json"


def _r(v, n=4):
    return [round(float(x), n) for x in v]


def _pt(W, p):
    return (W @ np.r_[np.asarray(p, float), 1.0])[:3]


class Scene:
    """The built model: assemblies, routes, handles to the parts the sheets name."""

    def __init__(self, p: Params):
        self.p = p
        self.pos = rt.positions(p)
        self.kit = m.Kit(p)
        self.handles: dict = {}          # name -> path of Child objects from the root
        self.files: dict = {}            # key -> root Asm
        self.routes: dict = {}
        self.ropes: dict = {}
        self.sheaves: list = []          # dicts with "path" (from root) and local data
        self.timings: dict = {}


def build(p: Params | None = None, with_lebus: bool = True) -> Scene:
    p = p or Params()
    S = Scene(p)
    pos, kit = S.pos, S.kit
    R, cr = p.bend_r, p.cable_r
    xc = pos["carousel_x"]
    t0 = time.time()
    root = Asm(ROOT)
    # ---- vessel
    ves = m.vessel(p, pos)
    S.handles["vessel"] = [root.add(ves, instance="VESSEL")]
    S.files["vessel"] = ves
    S.timings["vessel"] = time.time() - t0
    # ---- carousel + loading arm (local origin: the turntable's centre at the waterline)
    r_min, r_max = pos["trolley_coil_r"]
    gx_min = -math.hypot(r_max, R)
    gx_max = -math.hypot(r_min, R)
    la = {"tower_x": pos["tower_x"] - xc, "arm_z": pos["arm_z"], "line_z": p.line_z, "deck_z": p.deck_z,
          "guide_x": pos["guide_x"] - xc, "guide_x_min": gx_min, "guide_x_max": gx_max,
          "x_far": gx_max - R + 1500.0}
    t = time.time()
    car = m.carousel(p, kit, loading_arm=la)
    cc = root.add(car, T(xc, 0, 0), "CAROUSEL")
    S.handles["carousel"] = [cc]
    S.files["carousel"] = car
    gs = car.info["guide_sheave"]
    S.sheaves.append({"name": "Guide sheave (loading arm)", "path": [cc] + gs["path"], "local_centre": gs["centre"],
                      "local_axis": gs["axis"], "pitch_r": gs["pitch_r"], "groove_r": gs["groove_r"],
                      "carries": "cable", "frame": [cc]})
    S.timings["carousel"] = time.time() - t
    # ---- storage carousel (separate file only)
    t = time.time()
    S.files["storage_carousel"] = m.carousel(p, kit, name="STORAGE CAROUSEL", outer_d=max(14000.0, 2 * p.core_r + 6000),
                                             rim_h=3500.0, coil_h=2200.0, base_frame=True)
    S.timings["storage_carousel"] = time.time() - t
    # ---- tensioners
    t = time.time()
    ten = m.tensioner(p, kit)
    S.files["tensioner"] = ten
    for k, x in enumerate(pos["tensioners"]):
        S.handles[f"tensioner{k + 1}"] = [root.add(ten, T(x, 0, p.line_z), f"TENSIONER {k + 1}")]
    S.timings["tensioner"] = time.time() - t
    # ---- handling winches (port and starboard, their ropes towards the centre line)
    t = time.time()
    hw = m.winch(p, kit, "HANDLING WINCH", p.handling_rope_d, 600.0, 1600.0, layers=4, wound=0.6, fairlead=True)
    S.files["handling_winch"] = hw
    for side, y, ang in (("port", 5500.0, -90.0), ("starboard", -5500.0, 90.0)):
        c = root.add(hw, T(pos["handling_winch_x"], y, p.deck_z) @ Rot((0, 0, 1), ang), f"HANDLING WINCH {side.upper()}")
        S.handles[f"handling_winch_{side}"] = [c]
        fl = hw.info["fairlead"]
        S.sheaves.append({"name": f"Fairlead sheave (handling winch {side})", "path": [c, fl["child"]],
                          "local_centre": fl["centre"], "local_axis": [0, 1, 0], "pitch_r": fl["pitch_r"],
                          "groove_r": fl["groove_r"], "carries": "wire rope", "frame": [c]})
    S.timings["handling_winch"] = time.time() - t
    # ---- the cable route: rollers on stands along the deck line
    main = rt.main_route(p, pos)
    S.routes["main"] = main
    cr_asm = Asm("CABLE ROUTE")
    rr = 125.0
    roller = kit.roller(rr, 700.0)
    axle_z = p.line_z - cr - rr
    stand = kit.roller_stand(axle_z - p.deck_z, 900.0)
    x_hi = pos["tower_x"] - R - 700.0
    x_lo = pos["chute_x"] + 600.0
    busy = [(x - rt.TENSIONER_HALF - 400.0, x + rt.TENSIONER_HALF + 400.0) for x in pos["tensioners"]]
    xs = []
    x = x_hi
    while x >= x_lo:
        if not any(a <= x <= b for a, b in busy):
            xs.append(x)
        x -= 1500.0
    for k, x in enumerate(xs):
        ctr = np.array([x, 0.0, axle_z])
        c = cr_asm.add(roller, T(*ctr))
        cr_asm.add(stand, T(x, 0, p.deck_z))
        cr_asm.joint(f"Cable roller {k + 1} turn", "rotate", [c], ctr,
                     m.turn_axis(ctr, ctr + [0, 0, rr], [-1, 0, 0]), None, m.cable_drive(rr))
    S.handles["cable_route"] = [root.add(cr_asm, instance="CABLE ROUTE")]
    # ---- chute
    t = time.time()
    ch_origin = np.array([pos["chute_x"], 0.0, p.line_z - p.chute_r])
    ch = m.chute(p, kit, p.chute_r, pos["chute_deg"], p.deck_z - ch_origin[2], 0.0 - ch_origin[0])
    S.handles["chute"] = [root.add(ch, T(*ch_origin), "CHUTE")]
    S.timings["chute"] = time.time() - t
    # ---- quadrant system on the starboard lane (local origin: the stern's deck edge on the lane's centre)
    t = time.time()
    qs, qinfo = quadrant_system(p, S)
    qc = root.add(qs, T(0, p.quadrant_y, p.deck_z), "QUADRANT SYSTEM")
    S.handles["quadrant_system"] = [qc]
    S.files["quadrant"] = qs
    for sh in qinfo["sheaves"]:
        sh["path"] = [qc] + sh["path"]
        sh["frame"] = [qc] + sh.get("frame", [])
        S.sheaves.append(sh)
    S.quadrant_info = qinfo
    S.timings["quadrant"] = time.time() - t
    # ---- the cable along the main route (a static solid for stills)
    cable = Part("CABLE", g.route_solid(main, cr), m.CABLE_BLACK)
    S.handles["cable"] = [root.add(cable, instance="CABLE")]
    # ---- Lebus drum (separate file only)
    if with_lebus:
        t = time.time()
        S.files["drum_lebus"] = m.lebus_drum(p, p.handling_rope_d, 600.0, 1600.0)
        S.timings["drum_lebus"] = time.time() - t
    S.files["assembly"] = root
    S.root = root
    S.timings["total"] = time.time() - t0
    return S


def quadrant_system(p: Params, S: Scene):
    """Quadrant + hinge, stern frame with the tipping sheaves, lead sheave, quadrant handling winch, two tipping
    winches, their wire ropes, the cable end lying on the quadrant with its CPS, cable-end supports."""
    kit = S.kit
    R, cr = p.quadrant_r, p.cable_r
    qs = Asm("QUADRANT SYSTEM")
    hx, hz = p.quadrant_hinge
    C = np.array([hx, 0.0, hz - p.deck_z])                 # hinge = the quadrant's bend centre (local)
    quad = m.quadrant(p, kit, R)
    cq = qs.add(quad, T(*C))
    qs.joint("Quadrant tip", "rotate", [cq], C, (0, -1, 0), [0.0, 100.0],
             {"by": "operator", "note": "tips aft over the stern (positive), the quadrant handling winch pays out, "
                                        "the tipping winches start it over"})
    # hinge pin + brackets on the transom (x = 0)
    qs.add(Part("HINGE PIN", g.cyl(150.0, 1900.0, C + [0, -950, 0], (0, 1, 0)), m.STEEL))
    br = Part("HINGE BRACKET", g.box(C[0] - 500, 0, C[2] - 600, -C[0] + 500, 100, 1200), m.YELLOW)
    qs.add(br, T(0, -860.0, 0))
    qs.add(br, T(0, 760.0, 0))
    # stern frame: two legs from the deck leaning aft, a cross beam carrying the tipping sheaves
    top_x, top_z = -3000.0, 6900.0
    legs = [g.beam((1500.0, y, 0.0), (top_x, y, top_z), 400.0) for y in (-2400.0, 2400.0)]
    legs += [g.box(top_x - 250, -2650, top_z - 200, 500, 5300, 400)]
    legs += [g.box(1500 - 400, y - 400, 0, 800, 800, 60) for y in (-2400.0, 2400.0)]
    tip_rp = max(8 * p.tipping_rope_d, 300.0)
    tip_c = np.array([top_x, 0.0, top_z - 200 - tip_rp - 1.25 * p.tipping_rope_d / 2 - 150.0])
    for y in (-1300.0, 1300.0):
        legs.append(g.box(top_x - 150, y - 130, tip_c[2], 300, 40, top_z - 200 - tip_c[2] + 1))
        legs.append(g.box(top_x - 150, y + 90, tip_c[2], 300, 40, top_z - 200 - tip_c[2] + 1))
    qs.add(Part("STERN FRAME", g.fuse(*legs), m.YELLOW))
    tip_sheave = Part("TIPPING SHEAVE", g.sheave(tip_rp, p.tipping_rope_d / 2, holes=5), m.YELLOW)
    sheaves = []
    tip_children = {}
    for key, y in (("stb", -1300.0), ("port", 1300.0)):
        ctr = tip_c + [0, y, 0]
        c = qs.add(tip_sheave, T(*ctr) @ Rot((1, 0, 0), 90))
        tip_children[key] = (c, ctr)
        sheaves.append({"name": f"Tipping sheave ({key})", "path": [c], "local_centre": [0, 0, 0],
                        "local_axis": [0, 0, 1], "pitch_r": tip_rp, "groove_r": p.tipping_rope_d / 2,
                        "carries": "wire rope"})
    # lead sheave for the quadrant handling wire, on two plates from the deck
    lead_rp = max(8 * p.quadrant_rope_d, 300.0)
    lead_c = np.array([2500.0, -900.0, 3200.0])
    cl = qs.add(Part("LEAD SHEAVE", g.sheave(lead_rp, p.quadrant_rope_d / 2, holes=5), m.YELLOW),
                T(*lead_c) @ Rot((1, 0, 0), 90))
    qs.add(Part("LEAD SHEAVE FRAME", g.fuse(
        g.box(lead_c[0] - 250, lead_c[1] - 200, 0, 500, 60, lead_c[2] + 150),
        g.box(lead_c[0] - 250, lead_c[1] + 140, 0, 500, 60, lead_c[2] + 150),
        g.box(lead_c[0] - 400, lead_c[1] - 350, 0, 800, 700, 60)), m.YELLOW))
    sheaves.append({"name": "Lead sheave (quadrant handling wire)", "path": [cl], "local_centre": [0, 0, 0],
                    "local_axis": [0, 0, 1], "pitch_r": lead_rp, "groove_r": p.quadrant_rope_d / 2,
                    "carries": "wire rope"})
    # winches (turned 180°: their ropes leave the drum's top towards the stern)
    qw = m.winch(p, kit, "QUADRANT HANDLING WINCH", p.quadrant_rope_d, 700.0, 1400.0, layers=5, wound=0.7,
                 fairlead=False)
    tw = m.winch(p, kit, "TIPPING WINCH", p.tipping_rope_d, 400.0, 800.0, layers=4, wound=0.5, fairlead=False)
    qw_pos = np.array([15000.0, -900.0, 0.0])
    cqw = qs.add(qw, T(*qw_pos) @ Rot((0, 0, 1), 180.0), "QUADRANT HANDLING WINCH")
    tws = {}
    for key, y in (("stb", -1300.0), ("port", 1300.0)):
        tws[key] = (qs.add(tw, T(6000.0, y, 0.0) @ Rot((0, 0, 1), 180.0), f"TIPPING WINCH {key.upper()}"),
                    np.array([6000.0, y, 0.0]))
    eyes = {k: C + np.array(v) for k, v in quad.info["pad_eyes"].items()}
    ropes = {}

    def rope(name, d, y, drum_c, drum_r, sheave_c, sheave_r, eye):
        r = rt.rope_route(name, d, y, [
            ("sheave", (drum_c[0], drum_c[2]), drum_r, +1, {"name": "drum"}),
            ("sheave", (sheave_c[0], sheave_c[2]), sheave_r, +1, {"name": "sheave"}),
            ("point", (eye[0], eye[2]))])
        ropes[name] = r
        qs.add(Part("WIRE ROPE", g.route_solid(r, d / 2), m.ROPE_GREY))
        return r

    dq = qw.info["drum_centre"]
    rope("quadrant handling wire", p.quadrant_rope_d, -900.0, qw_pos + dq, qw.info["rope_centre_r"], lead_c, lead_rp,
         eyes["handling"])
    for key in ("stb", "port"):
        cpos = tws[key][1]
        rope(f"tipping wire {key}", p.tipping_rope_d, cpos[1], cpos + tw.info["drum_centre"], tw.info["rope_centre_r"],
             tip_children[key][1], tip_rp, eyes[f"tipping_{'stb' if key == 'stb' else 'port'}"])
    # the cable end lying on the quadrant: from its end forward on supports, over the gutter, down into the sea
    zq = C[2] + R
    end_x = 12000.0
    r_end = rt.Route("quadrant_end", p.cable_d)
    r_end.add(rt.Line([end_x, 0.0, zq], [C[0], 0.0, zq]), support="cable-end supports",
              note="the cable end with its CPS, held by the hang-off clamp at the quadrant's top")
    r_end.arc([0, 0, -1], R, 90.0, support="rollers", rollers="quadrant gutter")
    r_end.line_to([C[0] - R, 0.0, p.sea_end_z - p.deck_z], support="free", note="the laid cable, into the sea")
    qs.add(Part("CABLE END", g.route_solid(r_end, cr), m.CABLE_BLACK))
    cps, cps_len, cps_r = m.cps(p)
    qs.add(cps, g.Frame((end_x, 0.0, zq), (-1, 0, 0), (0, 0, 1)), "CPS")
    # supports: two under the CPS, one under the bare cable
    for x, r_on in ((end_x - 1500.0, cps_r), (end_x - 4500.0, cps_r), (1500.0, cr)):
        axle = zq - r_on - 125.0
        qs.add(kit.roller(125.0, 700.0), T(x, 0, axle))
        qs.add(kit.get(("end_support", round(axle)), lambda: Part("CABLE END SUPPORT",
                                                                  kit.roller_stand(axle, 900.0).shape, m.YELLOW)),
               T(x, 0, 0))
    info = {"hinge": C, "radius": R, "eyes": eyes, "ropes": ropes, "cable_end_route": r_end, "sheaves": sheaves,
            "cps": {"length": cps_len, "outer_r": cps_r, "end": [end_x, 0.0, zq]},
            "winches": {"quadrant_handling": cqw, "tipping": tws}}
    return qs, info


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


def route_sheet(S: Scene) -> dict:
    p, pos, root = S.p, S.pos, S.root
    ruid = f"{ROOT}#1"
    uid = lambda path: g.path_uid(ruid, path)  # noqa: E731
    W = lambda path: g.path_matrix(np.eye(4), path)  # noqa: E731
    main = S.routes["main"].to_dict()
    # name the parts each segment lies on
    car_uid = uid(S.handles["carousel"])
    for seg in main["segments"]:
        if seg.get("support") == "coil":
            seg["on"] = uid(S.handles["carousel"]) + "/CAROUSEL TURNTABLE#1/CABLE COIL#1"
        if seg.get("wheel") == "guide":
            seg["on"] = uid(S.sheaves[0]["path"])
        if seg.get("rollers") in ("tower top", "tower bottom"):
            seg["on"] = car_uid
        if seg.get("rollers") == "chute":
            seg["on"] = uid(S.handles["chute"])
    QW = W(S.handles["quadrant_system"])
    qend = _shift(S.quadrant_info["cable_end_route"], QW).to_dict()
    ropes = []
    for name, r in S.quadrant_info["ropes"].items():
        d = _shift(r, QW).to_dict()
        ropes.append(d)
    sheaves = []
    for sh in S.sheaves:
        Wf = W(sh["path"])
        sheaves.append({"name": sh["name"], "uid": uid(sh["path"]),
                        "centre": _r(_pt(Wf, [0, 0, 0])),
                        "axis": _r(Wf[:3, :3] @ np.array([0, 0, 1.0]), 6),
                        "pitch_radius": sh["pitch_r"], "groove_radius": sh["groove_r"],
                        "carries": sh["carries"],
                        "note": "the groove is a torus: major radius = pitch radius (the rope's or cable's centre)"})
    tens = []
    for k in (1, 2):
        path = S.handles[f"tensioner{k}"]
        Wt = W(path)
        ten = path[-1].node
        tracks = []
        for tr in ten.info["tracks"]:
            tracks.append({
                "name": tr["name"],
                "pads": [uid(path + tr["chain"] + [c]) for c in tr["pads"]],
                "links": [uid(path + tr["chain"] + [c]) for c in tr["links"]],
                "pins": [_r(_pt(Wt, q)) for q in tr["pins"]],
                "sprockets": {k2: _r(_pt(Wt, v)) for k2, v in tr["sprockets"].items()},
                "sprocket_axis": [0.0, 1.0, 0.0],
                "pitch": tr["pitch"], "sprocket_pitch_radius": round(tr["sprocket_pitch_r"], 4),
                "contact_run": tr["contact_run"], "travel": tr["travel"]})
        tens.append({"name": f"TENSIONER {k}", "uid": uid(path), "centre": _r(_pt(Wt, [0, 0, 0])),
                     "pads_per_track": p.pads_per_track, "squeeze_h": round(ten.info["squeeze_h"], 4),
                     "grips": [round(pos["tensioners"][k - 1] - rt.TENSIONER_HALF, 3),
                               round(pos["tensioners"][k - 1] + rt.TENSIONER_HALF, 3)],
                     "tracks": tracks})
    car = S.files["carousel"]
    xc = pos["carousel_x"]
    qi = S.quadrant_info
    return {
        "about": "Invented cable-lay spread (task 0076): the cable's centreline as straights and arcs, what each "
                 "part of it lies on, sheaves, tensioner tracks, ropes. Model coordinates of demo_cable_lay.step "
                 "(mm, x to the bow with the transom at 0, y to port, z up, waterline 0). The cable is laid towards "
                 "the stern (-x). Arcs: the start point turned about the axis (centre, normal) by angle, right hand.",
        "units": "mm",
        "cable": {"diameter": p.cable_d, "mbr": p.mbr, "bend_radius": p.bend_r,
                  "solid": uid(S.handles["cable"]), "solid_radius": p.cable_r,
                  "cable_end_solid": uid(S.handles["quadrant_system"]) + "/CABLE END#1"},
        "routes": [main, qend],
        "ropes": ropes,
        "sheaves": sheaves,
        "tensioners": tens,
        "carousel": {"uid": car_uid, "centre": [xc, 0.0, 0.0], "axis": [0.0, 0.0, -1.0],
                     "turn_note": "turns clockwise seen from above (about -z) while paying out",
                     "coil": {k: round(v + 0.0, 3) for k, v in car.info["coil"].items()},
                     "rest_coil_radius": p.coil_r, "trolley_coil_radius": pos["trolley_coil_r"]},
        "quadrant": {"uid": uid(S.handles["quadrant_system"]) + "/QUADRANT#1",
                     "hinge": _r(_pt(QW, qi["hinge"])), "axis": [0.0, -1.0, 0.0], "radius": qi["radius"],
                     "pad_eyes": {k: _r(_pt(QW, v)) for k, v in qi["eyes"].items()},
                     "cps": {"uid": uid(S.handles["quadrant_system"]) + "/CPS#1", "length": qi["cps"]["length"],
                             "outer_radius": qi["cps"]["outer_r"], "cable_end": _r(_pt(QW, qi["cps"]["end"]))}},
        "positions": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in pos.items()},
    }


def joint_sheet(S: Scene) -> dict:
    joints = g.resolve_joints(S.root)
    machines = {}
    for key in ("carousel", "storage_carousel", "tensioner", "handling_winch", "quadrant"):
        machines[FILES[key]] = g.resolve_joints(S.files[key])
    return {
        "about": "Every joint a set-up should make (task 0076; task 0077 makes them by script). Axis point and "
                 "direction in model coordinates (mm) of demo_cable_lay.step; parts are the importer's uids "
                 "(the node path NAME#n/…). A rotate joint turns the parts right-handed about the axis direction "
                 "(degrees), a slide joint moves them along it (mm); 0 = as modelled. drive.by: 'cable' = turned by "
                 "the cable or a rope running over it (deg_per_mm of payout, positive = paying out towards the "
                 "sea), 'follows' = a ratio of another joint, 'carousel' / 'winch' / 'operator' = driven on its own. "
                 "machine_files: the same joints in each separate machine file's own coordinates.",
        "units": {"length": "mm", "angle": "deg"},
        "model": FILES["assembly"],
        "joints": joints,
        "machine_files": machines,
    }


def write(out_dir: str, p: Params | None = None, log=print) -> Scene:
    os.makedirs(out_dir, exist_ok=True)
    S = build(p)
    for key, fname in FILES.items():
        if key not in S.files:
            continue
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
