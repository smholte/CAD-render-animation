"""The wind park round the cable-lay vessel (task 0166): nine turbines in three rows, an offshore substation between
the rows, and the first end of the cable the vessel lays – from turbine A's J-tube over its scour rock down to the
seabed, where the app's cable (``blender/paths_sea.py``) carries on to the touch-down. Its own file
``demo_park.step`` (``layout.FILES["park"]``), imported as its own model by the demo (``blender/demo.py``, stage
``park``) and placed on the moving seabed there.

**Park coordinates** (mm): the origin is where the CAD piece "CABLE FIRST END" meets the seabed lay line (the end
of the app's laid cable), +x along the lay line towards the vessel (the way it sails), +y to port, z 0 the waterline,
the seabed at -``ParkParams.water_depth``. The grid's rows run at a small angle to the lay line, so turbine B (the next
one along A's row) stands ``b_off`` beside it: the vessel passes it and lays the second end down beside it.

Joints (all in the root assembly, names without a prefix): "Park: on to turbine B" (slide along +x; the demo moves the
park by it between shot 8b and shot 9 – the shots lie a kilometre of laying apart), per turbine "WTG nn: Yaw" (rides on
it) and "WTG nn: Rotor" (rides on the yaw; a motor; + = clockwise seen from the front). Every rotor faces the wind from
``ParkParams.wind_from`` and stands at its own phase.
"""

from __future__ import annotations

import math

import numpy as np

from . import geom as g
from . import route as rt
from . import substation as sub
from . import turbine as tb
from . import turbine_parts as tp
from .geom import Asm, Part, T
from .params import ParkParams, Params

ROOT = "DEMO WIND PARK"
SHIFT = "Park: on to turbine B"
CABLE_PIECE = "CABLE FIRST END"
CLEAR = 30.0                      # mm: the cable piece lies this far over the rock (the rock is a 72-gon: its ridge)
CABLE_BLACK = (0.04, 0.04, 0.045)


def name(k: int) -> str:
    return f"WTG {k + 1:02d}"


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def grid(pp: ParkParams) -> tuple[np.ndarray, np.ndarray]:
    """The grid's two steps (park xy, mm): along A's row (to B) and across to the next row (to port)."""
    e1 = _unit((math.sqrt(pp.along ** 2 - pp.b_off ** 2), pp.b_off))
    e2 = np.array([-e1[1], e1[0]])
    return e1 * pp.along, e2 * pp.across


# ---------------------------------------------------------------------------------------------------------------
# the first end: from A's J-tube bell-mouth over the scour rock down to the seabed (in A's T frame, then placed)
# ---------------------------------------------------------------------------------------------------------------

def _fillet_route(name_: str, d: float, pts2, n3, origin, radius: float) -> rt.Route:
    """A route in the vertical plane (origin, radial n3, z) through the 2D corners ``pts2`` [(rho, z)], each inner
    corner rounded with ``radius`` (straight - arc - straight)."""
    z3 = np.array([0.0, 0.0, 1.0])

    def p3(q):
        return np.asarray(origin, float) + q[0] * n3 + q[1] * z3

    def v3(v):
        return v[0] * n3 + v[1] * z3

    P = [np.asarray(q, float) for q in pts2]
    r = rt.Route(name_, d)
    cur = P[0]
    for a, b, c in zip(P[:-2], P[1:-1], P[2:]):
        u, v = _unit(b - a), _unit(c - b)
        turn = math.atan2(u[0] * v[1] - u[1] * v[0], float(u @ v))
        t = radius * math.tan(abs(turn) / 2.0)
        t1 = b - u * t
        if not r.segments:
            r.add(rt.Line(p3(cur), p3(t1)))
        else:
            r.line_to(p3(t1))
        side = 1.0 if turn > 0 else -1.0
        bend = np.array([-u[1], u[0]]) * side
        r.arc(v3(bend), radius, math.degrees(abs(turn)))
        cur = b + v * t
    r.line_to(p3(P[-1]))
    return r


def first_end(p: Params, pp: ParkParams) -> tuple[rt.Route, dict]:
    """The CAD piece in turbine A's own T frame, before its turn (J-tube ``tb.JTUBE_CABLE`` at its own azimuth): from
    450 mm inside the bell-mouth along its axis, bending onto the rock (``CLEAR`` over its ridge), down its three
    slopes, over the filter layer's edge and onto the seabed, ``join_run`` straight there. Returns (route, numbers)."""
    sb = -pp.water_depth
    if abs(sb - tb.SEABED_Z) > 1e-6:
        raise ValueError("the park's water depth must be the turbine's (turbine.SEABED_Z)")
    bell, axis = tb.bell()
    n = _unit((axis[0], axis[1], 0.0))
    n3 = np.array([n[0], n[1], 0.0])
    rho_b, z_b = float(bell[:2] @ n[:2]), float(bell[2])
    a2 = np.array([math.hypot(axis[0], axis[1]), axis[2]])               # the bell's axis in (rho, z): 30° down
    c = p.cable_r + CLEAR
    prof = tp.scour_profile(tb.FIT)              # (ri, z0), (filter, z0), (filter, z0+250), armour, crown, (ri, top)
    rock = [prof[5], prof[4], prof[3], prof[2]]  # its top from the pile out to the filter's edge (absolute z)

    def offset_line(q0, q1):
        t = _unit(np.subtract(q1, q0))
        nn = np.array([-t[1], t[0]])
        return np.asarray(q0, float) + nn * c, t

    def meet(pa, ta, pb, tb_):
        A = np.array([ta, -tb_]).T
        s = np.linalg.solve(A, pb - pa)
        return pa + ta * s[0]

    lines = [offset_line(q0, q1) for q0, q1 in zip(rock[:-1], rock[1:])]
    z_end = sb + (0.5 - 0.3) * p.cable_d                 # paths_sea.bottom_z: the laid cable sinks 30 % of its Ø
    start = np.array([rho_b, z_b]) - a2 * 450.0
    corners = [start, meet(start, a2, *lines[0])]
    for (pa, ta), (pb, tb_) in zip(lines[:-1], lines[1:]):
        corners.append(meet(pa, ta, pb, tb_))
    flat_p, flat_t = np.array([0.0, z_end]), np.array([1.0, 0.0])
    corners.append(meet(*lines[-1], flat_p, flat_t))
    # the straight on the seabed: past the last fillet, then join_run more
    last = corners[-1]
    tl = lines[-1][1]
    turn = math.atan2(tl[0] * flat_t[1] - tl[1] * flat_t[0], float(tl @ flat_t))
    run = p.bend_r * math.tan(abs(turn) / 2.0) + pp.join_run
    end = np.array([last[0] + run, z_end])
    route = _fillet_route(CABLE_PIECE, p.cable_d, corners + [end], n3, np.zeros(3), p.bend_r)
    return route, {"rho_end": float(end[0]), "z_end": float(z_end), "n": n3, "rock": [list(map(float, q)) for q in rock],
                   "bell": bell, "bell_axis": axis, "clear": CLEAR}


# ---------------------------------------------------------------------------------------------------------------
# the park
# ---------------------------------------------------------------------------------------------------------------

def _turn_to(az_want: float) -> float:
    """The turn (deg, counter-clockwise from above) that points J-tube 1 to compass ``az_want``."""
    return (tp.AZ_JTUBES[tb.JTUBE_CABLE] - az_want) % 360.0


def build(p: Params | None = None, pp: ParkParams | None = None, kit: tb.Kit | None = None) -> tuple[Asm, dict]:
    """(root Asm, info for the route sheet). The route sheet's numbers are in park coordinates (mm)."""
    p = p or Params()
    pp = pp or ParkParams()
    kit = kit or tb.Kit()
    route_T, fe = first_end(p, pp)
    # turbine A: its J-tube 1 towards +x (compass 90): turned, the piece's end lands on the origin
    turn_a = _turn_to(90.0)
    Ra = g.Rot((0, 0, 1), turn_a)
    end_T = (Ra @ np.r_[fe["n"] * fe["rho_end"], 1.0])[:3]
    a_xy = -end_T[:2]                                   # A's tower axis in park coordinates
    e1, e2 = grid(pp)
    ra, ca = pp.first
    root = Asm(ROOT)
    park = Asm("WIND PARK")
    c_park = root.add(park, np.eye(4), "WIND PARK")
    turbines = []
    k = 0
    for row in range(pp.rows):
        for col in range(pp.cols):
            xy = a_xy + (col - ca) * e1 + (row - ra) * e2
            role = "A" if (row, col) == (ra, ca) else "B" if (row, col) == (ra, ca + 1) else ""
            turn = turn_a if role == "A" else _turn_to(0.0 if pp.b_off < 0 else 180.0) if role == "B" \
                else (37.0 * k + 15.0) % 360.0
            phase = (29.0 * k + 11.0) % 120.0
            asm = tb.turbine(kit, name(k), turn, phase, pp.wind_from)
            c = park.add(asm, T(xy[0], xy[1], 0.0), name(k))
            bell, axis = tb.bell()
            R = g.Rot((0, 0, 1), turn)
            turbines.append({"name": name(k), "role": role, "row": row, "col": col, "xy": [float(v) for v in xy],
                             "turn": turn, "phase": phase, "child": c, "asm": asm,
                             "bell": [float(v) for v in (R @ np.r_[bell, 1.0])[:3] + np.r_[xy, 0.0]],
                             "bell_axis": [float(v) for v in R[:3, :3] @ axis]})
            k += 1
    s_xy = a_xy + pp.substation[0] * e1 + pp.substation[1] * e2
    st = sub.substation(next(prt for prt, _M in kit.fixed if prt.name == "MARINE LIGHT"))
    c_sub = park.add(st, T(s_xy[0], s_xy[1], 0.0), "OFFSHORE SUBSTATION")
    # the cable piece, in park coordinates (A's T frame turned and moved)
    MA = T(a_xy[0], a_xy[1], 0.0) @ Ra
    piece = Part(CABLE_PIECE, g.route_solid(route_T, p.cable_r), CABLE_BLACK)
    c_piece = park.add(piece, MA, CABLE_PIECE)
    # joints: the park's shift, then each turbine's yaw and rotor (riding on it)
    root.joint(SHIFT, "slide", [[c_park]], (0.0, 0.0, -pp.water_depth), (1.0, 0.0, 0.0))
    for t in turbines:
        a, c = t["asm"], t["child"]
        M = c.M
        info = a.info
        c_nac = next(ch for ch in a.children if ch.instance == "NACELLE")
        c_rot = next(ch for ch in c_nac.node.children if ch.instance == "ROTOR")
        tower_top = (M @ np.r_[0.0, 0.0, tb.TOWER_TOP, 1.0])[:3]
        hub = (M @ np.r_[info["hub"], 1.0])[:3]
        root.joint(f"{t['name']}: Yaw", "rotate", [[c_park, c, c_nac]], tower_top, (0.0, 0.0, 1.0), rides_on=SHIFT)
        root.joint(f"{t['name']}: Rotor", "rotate", [[c_park, c, c_nac, c_rot]], hub, info["down"],
                   rides_on=f"{t['name']}: Yaw", motor=True)
        t["hub"] = [float(v) for v in hub]
        t["down"] = [float(v) for v in info["down"]]
    for t in turbines:
        t["asm"].joints.clear()                        # (their own copies of the joints: the root's are the ones)
    route = rt.Route(CABLE_PIECE, p.cable_d)
    for seg in route_T.segments:
        q0 = (MA @ np.r_[seg.start, 1.0])[:3]
        if seg.kind == "line":
            route.add(rt.Line(q0, (MA @ np.r_[seg.end, 1.0])[:3]))
        else:
            route.add(rt.Arc((MA @ np.r_[seg.centre, 1.0])[:3], MA[:3, :3] @ seg.normal, q0, seg.angle))
    a_t = next(t for t in turbines if t["role"] == "A")
    b_t = next(t for t in turbines if t["role"] == "B")
    info = {
        "about": "task 0166: park coordinates (mm): origin = where the first end's CAD piece meets the seabed lay line "
                 "(the end of the app's laid cable), +x along the lay line towards the vessel, z 0 the waterline. "
                 "turbines: name, role (A: the first end goes up its J-tube; B: the second end is laid down beside "
                 "it), tower axis xy, turn (deg, counter-clockwise from above), rotor phase (deg, clockwise from the "
                 "front), hub, down (the rotor joint's axis), the J-tube's bell-mouth (open end) and its axis.",
        "file": "demo_park.step", "root": ROOT, "shift_joint": SHIFT,
        "water_depth": pp.water_depth, "wind_from": pp.wind_from, "rpm": pp.rpm, "b_end": pp.b_end,
        "first": a_t["name"], "second": b_t["name"],
        "turbines": [{k_: v for k_, v in t.items() if k_ not in ("child", "asm")} for t in turbines],
        "substation": {"xy": [float(v) for v in s_xy], "top": sub.ROOF, "helideck": sub.HELI_Z,
                       "half": list(sub.TOP_HALF), "foot_r": st.info["foot"]},
        "cable_piece": {"route": route.to_dict(), "end": [0.0, 0.0, fe["z_end"]], "clear": CLEAR,
                        "rock_top": fe["rock"], "radius": p.cable_r},
        "scour_r": tb.scour_radius(), "pile_r": tb.PILE_R, "seabed_z": -pp.water_depth,
        "platform_r": tp.DECK_RO, "rotor_r": tb.HUB_TO_BLADE + tb.BLADE_LENGTH, "hub_height": float(tb.HUB[2]),
    }
    del c_sub, c_piece
    return root, info
