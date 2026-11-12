"""The cable route and rope paths of the demo model (tasks 0076, 0084): pure Python + NumPy, no OpenCascade.

A route is a chain of straights (``Line``) and circular arcs (``Arc``) that meet with the same direction (G1). Every
arc of the cable route has a radius of at least the cable's MBR. ``positions`` places the machines along the vessel
from the stern forward, so a bigger cable (bigger bends) moves the tensioners, the loading tower and the carousel
forward instead of breaking the route. Millimetres, model coordinates (x to the bow, y to port, z up, waterline 0).
"""

from __future__ import annotations

import math

import numpy as np


def unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    if n == 0:
        raise ValueError("zero vector")
    return v / n


def rotate(v, axis, ang: float) -> np.ndarray:
    """Rodrigues: v turned by ``ang`` (rad) about the unit ``axis`` (right hand)."""
    v = np.asarray(v, float)
    k = unit(axis)
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(k, v) * s + k * np.dot(k, v) * (1.0 - c)


def _r(v) -> list:
    return [round(float(x), 4) for x in v]


class Line:
    kind = "line"

    def __init__(self, p0, p1):
        self.p0 = np.asarray(p0, float)
        self.p1 = np.asarray(p1, float)

    @property
    def length(self) -> float:
        return float(np.linalg.norm(self.p1 - self.p0))

    @property
    def start(self):
        return self.p0

    @property
    def end(self):
        return self.p1

    def tangent(self, s: float = 0.0):
        return unit(self.p1 - self.p0)

    start_tangent = property(lambda self: self.tangent())
    end_tangent = property(lambda self: self.tangent())

    def point(self, s: float):
        return self.p0 + self.tangent() * s

    def distance(self, pts: np.ndarray) -> np.ndarray:
        d = self.p1 - self.p0
        t = np.clip(((pts - self.p0) @ d) / max(float(d @ d), 1e-12), 0.0, 1.0)
        return np.linalg.norm(pts - (self.p0 + t[:, None] * d), axis=1)

    def to_dict(self) -> dict:
        return {"type": "line", "start": _r(self.p0), "end": _r(self.p1), "direction": _r(self.tangent()),
                "length": round(self.length, 4)}


class Arc:
    """Circle arc: ``start`` turned about the axis (``centre``, unit ``normal``) by ``angle`` rad, right hand."""
    kind = "arc"

    def __init__(self, centre, normal, start, angle: float):
        self.centre = np.asarray(centre, float)
        self.normal = unit(normal)
        self.p0 = np.asarray(start, float)
        self.angle = float(angle)
        u = self.p0 - self.centre
        if abs(float(u @ self.normal)) > 1e-6 * max(1.0, np.linalg.norm(u)):
            raise ValueError("arc start not in the arc's plane")
        self.radius = float(np.linalg.norm(u))

    @classmethod
    def from_tangent(cls, start, tangent, bend, radius: float, angle_deg: float) -> "Arc":
        """Arc that leaves ``start`` along ``tangent`` and bends towards ``bend`` (unit, square to the tangent)."""
        t, b = unit(tangent), unit(bend)
        if abs(float(t @ b)) > 1e-9:
            raise ValueError("bend direction must be square to the tangent")
        start = np.asarray(start, float)
        return cls(start + radius * b, np.cross(t, b), start, math.radians(angle_deg))

    @property
    def length(self) -> float:
        return self.radius * self.angle

    @property
    def start(self):
        return self.p0

    def point(self, s: float):
        return self.centre + rotate(self.p0 - self.centre, self.normal, s / self.radius)

    @property
    def end(self):
        return self.point(self.length)

    def tangent(self, s: float):
        return unit(np.cross(self.normal, self.point(s) - self.centre))

    start_tangent = property(lambda self: self.tangent(0.0))
    end_tangent = property(lambda self: self.tangent(self.length))

    def distance(self, pts: np.ndarray) -> np.ndarray:
        q = pts - self.centre
        h = q @ self.normal
        qp = q - h[:, None] * self.normal
        u0 = (self.p0 - self.centre) / self.radius
        v0 = np.cross(self.normal, u0)
        phi = np.arctan2(qp @ v0, qp @ u0)
        phi = np.where(phi < -1e-9, phi + 2 * math.pi, phi)
        rho = np.linalg.norm(qp, axis=1)
        on = (phi >= 0.0) & (phi <= self.angle)
        d_arc = np.sqrt((rho - self.radius) ** 2 + h ** 2)
        d_end = np.minimum(np.linalg.norm(pts - self.p0, axis=1), np.linalg.norm(pts - self.end, axis=1))
        return np.where(on, d_arc, d_end)

    def to_dict(self) -> dict:
        return {"type": "arc", "start": _r(self.p0), "end": _r(self.end), "centre": _r(self.centre),
                "normal": _r(self.normal), "radius": round(self.radius, 4),
                "angle_deg": round(math.degrees(self.angle), 4), "length": round(self.length, 4),
                "start_tangent": _r(self.start_tangent), "end_tangent": _r(self.end_tangent)}


class Route:
    """A chain of segments; ``info[i]`` says what segment i lies on (free span, coil, a wheel, rollers …)."""

    def __init__(self, name: str, diameter: float):
        self.name = name
        self.diameter = float(diameter)
        self.segments: list = []
        self.info: list[dict] = []

    def add(self, seg, **info):
        if self.segments:
            gap = float(np.linalg.norm(seg.start - self.segments[-1].end))
            if gap > 1e-6:
                raise ValueError(f"{self.name}: segment {len(self.segments)} starts {gap:.3f} mm off the last end")
        self.segments.append(seg)
        self.info.append(info)
        return seg

    def line_to(self, p, **info):
        return self.add(Line(self.end, p), **info)

    def arc(self, bend, radius: float, angle_deg: float, **info):
        return self.add(Arc.from_tangent(self.end, self.end_tangent, bend, radius, angle_deg), **info)

    @property
    def end(self):
        return self.segments[-1].end

    @property
    def end_tangent(self):
        return self.segments[-1].end_tangent

    @property
    def length(self) -> float:
        return sum(s.length for s in self.segments)

    def sample(self, step: float = 50.0) -> np.ndarray:
        pts = []
        for seg in self.segments:
            n = max(2, int(math.ceil(seg.length / step)) + 1)
            pts += [seg.point(s) for s in np.linspace(0.0, seg.length, n)]
        return np.array(pts)

    def distance(self, pts) -> np.ndarray:
        """Distance of each point to the route's centreline."""
        pts = np.atleast_2d(np.asarray(pts, float))
        return np.min(np.stack([seg.distance(pts) for seg in self.segments]), axis=0)

    def joins(self) -> list[tuple[float, float]]:
        """(gap mm, direction change °) where each segment meets the next: both 0 for a smooth route."""
        out = []
        for a, b in zip(self.segments, self.segments[1:]):
            gap = float(np.linalg.norm(b.start - a.end))
            c = float(np.clip(a.end_tangent @ b.start_tangent, -1.0, 1.0))
            out.append((gap, math.degrees(math.acos(c))))
        return out

    def min_radius(self) -> float:
        return min((s.radius for s in self.segments if s.kind == "arc"), default=math.inf)

    def to_dict(self) -> dict:
        segs = []
        s0 = 0.0
        for seg, info in zip(self.segments, self.info):
            d = seg.to_dict()
            d["s_start"] = round(s0, 4)
            s0 += seg.length
            d.update(info)
            segs.append(d)
        return {"name": self.name, "diameter": self.diameter, "length": round(self.length, 4),
                "min_bend_radius_used": round(self.min_radius(), 4), "segments": segs}


# ---------------------------------------------------------------------------------------------------------
# Where things go (task 0084: the owner's deck layout)
# ---------------------------------------------------------------------------------------------------------

TENSIONER_HALF = 3100.0         # half the tensioner's length along the cable (frame + tilt hinge)
TENSIONER_WIDTH = 1380.0        # half its width (frame + side cylinders)
ENGINE_HALF = 1700.0            # half the linear cable engine's length
GUIDE_IN = 500.0                # the arch's guide reaches this close to the core
GUIDE_RIM = 700.0               # its hanging frame stays this far inside the rim
WINCH_HALF = 1450.0             # quadrant handling winch: half its length along x
CPS_OUT = 2000.0                # the CPS ramp runs this much outboard of side B (clear of tensioner 1)


def turn(r: Route, side: int, radius: float, deg: float, **info):
    """Horizontal bend: side +1 turns left (seen from above), -1 right."""
    t = r.end_tangent
    left = unit(np.cross([0.0, 0.0, 1.0], t))
    return r.arc(side * left, radius, deg, **info)


def pitch(r: Route, up: int, radius: float, deg: float, **info):
    """Vertical bend in the plane of the tangent and z: up +1 bends upwards, -1 downwards."""
    t = r.end_tangent
    z = np.array([0.0, 0.0, 1.0])
    b = z - t * float(t @ z)
    return r.arc(up * unit(b), radius, deg, **info)


def s_bend_angle(offset: float, radius: float) -> float:
    """Each arc's angle (deg) of an S-bend of two arcs (radius) that shifts the line sideways by ``offset``."""
    if offset > 2 * radius:
        raise ValueError("S-bend offset larger than 2 x the radius")
    return math.degrees(math.acos(1.0 - offset / (2.0 * radius)))


def arch_geometry(p, tower_xy, centre_xy, coil_rs: tuple, rest_r: float, rim_r: float, side: int = -1) -> dict:
    """The overhead arch on a loading tower: span (tower axis -> guide), the guide at the rest coil radius, the
    slew limits (deg, about +z, 0 = rest) for the guide over the coil radii ``coil_rs`` (min, max).

    The cable lifts off the coil at radius rho turning clockwise (seen from above): its vertical rise (the guide)
    lies at hypot(rho, R) from the carousel's centre."""
    R = p.bend_r
    T = np.asarray(tower_xy, float)
    C = np.asarray(centre_xy, float)
    D = float(np.linalg.norm(C - T))
    r_lo, r_hi = coil_rs
    r_hi = min(r_hi, math.sqrt(max((rim_r - GUIDE_RIM) ** 2 - R ** 2, 1.0)))
    d_lo, d_hi = math.hypot(r_lo, R), math.hypot(r_hi, R)
    span = max(2.0 * R, D - d_lo + 300.0)
    base = math.atan2(C[1] - T[1], C[0] - T[0])

    def ang(d):
        c = (D * D + span * span - d * d) / (2.0 * D * span)
        return math.acos(max(-1.0, min(1.0, c)))
    a_rest = base + side * ang(math.hypot(rest_r, R))
    guide = T + span * np.array([math.cos(a_rest), math.sin(a_rest)])
    lims = sorted(math.degrees(base + side * ang(d) - a_rest) for d in (d_lo, d_hi))
    return {"span": span, "guide": guide, "slew_rest_deg": math.degrees(a_rest), "slew_limits": lims,
            "coil_radii": [r_lo, r_hi], "distance": D}


def positions(p) -> dict:
    """Machine positions for the parameter set (mm), from the stern forward. A bigger cable (bigger bends) moves
    everything forward and the lanes outward instead of breaking the route."""
    R, Rq, cr = p.bend_r, p.quadrant_r, p.cable_r
    pos: dict = {"bend_r": R, "line_z": p.line_z, "low_z": p.low_z, "rail_z": p.rail_z}
    yA, yB = -p.lane_y, p.lane_y
    y_low = yA - p.lower_off
    pos.update({"side_a_y": yA, "side_b_y": yB, "lower_y": y_low})
    # horn A: an arc of the bend radius from the highway down to 500 mm above the water, at most 90°
    drop = p.line_z - 500.0
    chute_deg = 90.0 if drop >= R else math.degrees(math.acos(1.0 - drop / R))
    pos["chute_deg"] = chute_deg
    pos["horn_x"] = p.chute_drop_x + R * math.sin(math.radians(chute_deg))   # where the horn's bend starts
    # quadrant handler: hinged at the transom, lying flat forward of it; its top pulley at the forward end
    handler_len = Rq + 1500.0
    pos["hinge_x"] = p.hinge_x
    pos["handler_len"] = handler_len
    pos["pulley_x"] = p.hinge_x + handler_len
    # stern turn: 180° from the lower path (side A, outboard) across to side B, forward of the handler
    r_turn = 0.5 * (yB - y_low)
    pos["stern_turn_r"] = r_turn
    pos["stern_turn_y"] = 0.5 * (yB + y_low)
    x_st = pos["pulley_x"] + 1500.0 + r_turn
    pos["stern_turn_x"] = x_st                       # the turn's centre; it starts and ends at this x
    # side B: rise from the lower level to the highway, cable engine, tensioner 1
    rise = p.line_z - p.low_z
    pos["rise_deg"] = s_bend_angle(rise, R)
    x = x_st + 400.0
    pos["rise_x"] = x
    x += 2.0 * R * math.sin(math.radians(pos["rise_deg"]))
    pos["engine_x"] = x + 600.0 + ENGINE_HALF
    t_x = pos["engine_x"] + ENGINE_HALF + 800.0 + TENSIONER_HALF
    pos["tensioners"] = [t_x, t_x]                   # tensioner 1 on side B, tensioner 2 on side A, side by side
    # the CPS slide runs outboard of tensioner 1 and joins side B forward of it with an S-curve
    pos["cps_level_y"] = p.lane_y + CPS_OUT
    pos["cps_s_deg"] = s_bend_angle(CPS_OUT, R)
    pos["cps_join_x"] = t_x + TENSIONER_HALF + 300.0 + 2.0 * R * math.sin(math.radians(pos["cps_s_deg"]))
    pos["s_bend_x"] = pos["cps_join_x"] + 1500.0
    pos["s_bend_deg"] = s_bend_angle(p.lane_y - Rq, R)
    x_q = pos["s_bend_x"] + 2.0 * R * math.sin(math.radians(pos["s_bend_deg"]))
    pos["quadrant_x"] = x_q                          # the D's straight bar (its curve's centre line)
    pos["quadrant_apex_x"] = x_q + Rq
    pos["quadrant_travel"] = x_q - (p.hinge_x + 700.0)   # rails: from the stationary position onto the handler
    # quadrant handling winch in front of the carousel, on the centre line
    pos["qh_winch_x"] = x_q + Rq + cr + 250.0 + 1500.0 + WINCH_HALF
    well_r = p.carousel_d / 2.0 + 900.0
    pos["well_r"] = well_r
    xc = max(p.carousel_x, pos["qh_winch_x"] + WINCH_HALF + 1500.0 + well_r)
    pos["carousel_x"] = xc
    # loading tower beside the carousel (on the lower path's line), as close as the well allows
    reach = well_r + 1800.0
    x_t = xc - math.sqrt(max(reach ** 2 - y_low ** 2, 0.0))
    x_t = min(x_t, xc - 1000.0)
    pos["tower_x"] = x_t
    pos["tower_y"] = y_low
    rc_out = p.carousel_d / 2.0
    coil_in = p.core_r + 60.0
    coil_out = rc_out - 300.0
    arch = arch_geometry(p, (x_t, y_low), (xc, 0.0), (p.core_r + GUIDE_IN, coil_out - cr), p.coil_r, rc_out)
    pos["arch"] = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in arch.items()}
    z0 = p.coil_top_z + cr
    pos["coil_z"] = z0
    rim_top = p.turntable_t + p.rim_h
    pos["arch_z"] = max(p.arch_h, z0 + 2 * R + 1000.0, rim_top + R + 1500.0)
    pos["coil_in"], pos["coil_out"] = coil_in, coil_out
    # the hull's length follows the carousel; the deckhouse and the bow forward of it
    pos["length"] = max(p.length, xc + rc_out + 900.0 + 41100.0)
    pos["beam"] = p.beam
    # stern: tipping winches and their swivel sheaves (port +1, starboard -1)
    pos["tipping_winch"] = [2500.0, p.lane_y + 4150.0]
    pos["swivel_sheave"] = [400.0, p.lane_y + 1150.0, p.deck_z + 5500.0]
    # where the quay's cable comes aboard (task 0084: loading from the quay, vessel moored starboard side to)
    pos["board_x"] = pos["tipping_winch"][0] + 2450.0    # the quay cable crosses the deck edge here, heading +y
    pos["cps_shelf_z"] = p.deck_z + 3600.0          # the CPS rack's top shelf (CPS centre line)
    return pos


def lift_off(p, centre, rest_r: float, guide_xy, z0: float):
    """The coil point where the cable lifts off (clockwise coil, seen from above) and its direction."""
    R = p.bend_r
    C = np.asarray(centre, float)[:2]
    G = np.asarray(guide_xy, float)
    a = math.atan2(G[1] - C[1], G[0] - C[0]) + math.atan2(R, rest_r)
    u = np.array([math.cos(a), math.sin(a)])
    L = C + rest_r * u
    t = np.array([u[1], -u[0]])
    return np.array([L[0], L[1], z0]), np.array([t[0], t[1], 0.0])


def coil_to_tower(r: Route, p, centre, rest_r: float, guide_xy, z0: float, tower_xy, z_arch: float, z_foot: float,
                  foot_dir, names: dict):
    """Coil (last quarter turn) -> lift-off bend (the guide's roller cage) -> up the hanging guide -> over the arch
    (two 90° bends and the straight between) -> down the tower's axis -> the foot bend to level ``foot_dir``."""
    R = p.bend_r
    C3 = np.array([centre[0], centre[1], z0])
    L, t1 = lift_off(p, centre, rest_r, guide_xy, z0)
    start = C3 + rotate(L - C3, [0, 0, 1], math.pi / 2)
    r.add(Arc(C3, [0, 0, -1], start, math.pi / 2), support="coil", on=names.get("coil"))
    r.arc([0, 0, 1], R, 90.0, support="rollers", rollers=names["cage"],
          note="lifts off the coil through the guide's roller cage (bellmouth)")
    G = np.asarray(guide_xy, float)
    r.line_to([G[0], G[1], z_arch - R], support="rollers", rollers=names["guide"], note="up the hanging guide frame")
    T = np.asarray(tower_xy, float)
    w = np.r_[unit(T - G), 0.0]
    r.arc(w, R, 90.0, support="rollers", rollers=names["arch"])
    span = float(np.linalg.norm(T - G))
    if span - 2 * R > 1.0:
        r.line_to([G[0] + (span - R) * w[0], G[1] + (span - R) * w[1], z_arch], support="rollers",
                  rollers=names["arch"], note="over the arch")
    r.arc([0, 0, -1], R, 90.0, support="rollers", rollers=names["arch"])
    r.line_to([T[0], T[1], z_foot + R], support="free", note="down the tower's slewing axis")
    r.arc(np.r_[unit(np.asarray(foot_dir, float)[:2]), 0.0], R, 90.0, support="rollers", rollers=names["foot"])
    return L


def main_route(p, pos: dict) -> Route:
    """The owner's oval: carousel coil -> arch -> tower -> lower path aft (side A, outboard) -> stern turn (180°) ->
    side B forward (rise, cable engine, tensioner 1) -> round the quadrant (180°) -> side A aft (tensioner 2) ->
    horn A -> into the sea."""
    R, Rq = p.bend_r, p.quadrant_r
    xc = pos["carousel_x"]
    r = Route("main", p.cable_d)
    names = {"coil": "CABLE COIL", "cage": "guide cage", "guide": "guide frame", "arch": "arch",
             "foot": "tower foot"}
    coil_to_tower(r, p, (xc, 0.0), p.coil_r, pos["arch"]["guide"], pos["coil_z"], (pos["tower_x"], pos["tower_y"]),
                  pos["arch_z"], p.low_z, [-1.0, 0.0], names)
    r.line_to([pos["stern_turn_x"], pos["lower_y"], p.low_z], support="rollers", rollers="lower path",
              note="the lower path aft, beside and below side A's highway")
    turn(r, -1, pos["stern_turn_r"], 180.0, support="rollers", rollers="stern turn",
         note="the stern turn: from the lower path across to side B, under the quadrant's rails")
    r.line_to([pos["rise_x"], p.lane_y, p.low_z], support="rollers", rollers="side B")
    pitch(r, +1, R, pos["rise_deg"], support="rollers", rollers="side B rise")
    pitch(r, -1, R, pos["rise_deg"], support="rollers", rollers="side B rise")
    r.line_to([pos["s_bend_x"], p.lane_y, p.line_z], support="rollers", rollers="side B",
              note="side B forward: cable engine, tensioner 1 (its tracks grip the cable), V roller cradles")
    turn(r, -1, R, pos["s_bend_deg"], support="rollers", rollers="side B bend")
    turn(r, +1, R, pos["s_bend_deg"], support="rollers", rollers="side B bend")
    turn(r, -1, Rq, 180.0, support="rollers", rollers="quadrant gutter",
         note="round the D-quadrant at its stationary position")
    turn(r, +1, R, pos["s_bend_deg"], support="rollers", rollers="side A bend")
    turn(r, -1, R, pos["s_bend_deg"], support="rollers", rollers="side A bend")
    r.line_to([pos["horn_x"], -p.lane_y, p.line_z], support="rollers", rollers="side A",
              note="side A aft: tensioner 2 (its tracks grip the cable), V roller cradles")
    pitch(r, -1, R, pos["chute_deg"], support="rollers", rollers="horn A")
    t = r.end_tangent
    k = (p.sea_end_z - r.end[2]) / t[2]
    r.line_to(r.end + k * t, support="free", note="into the sea (task 0081 makes the catenary)")
    return r


def cps_slide_route(p, pos: dict) -> Route:
    """The CPS's way from the rack's top shelf down the orange twisted ramp (outboard of tensioner 1) and the curved
    slide (an S-curve) onto side B's highway, joining the cable route tangentially just forward of tensioner 1."""
    R = p.bend_r
    J = np.array([pos["cps_join_x"], p.lane_y, p.line_z])
    back = Route("cps back", 400.0)
    back.add(Line(J + [1.0, 0, 0], J))
    turn(back, -1, R, pos["cps_s_deg"])
    turn(back, +1, R, pos["cps_s_deg"])
    pitch(back, +1, R, 8.0)
    t = back.end_tangent
    k = (pos["cps_shelf_z"] - back.end[2]) / t[2]
    back.line_to(back.end + k * t)
    # reversed: rack -> ramp -> slide -> J
    out = Route("cps_slide", 400.0)
    segs = back.segments[1:][::-1]
    for i, seg in enumerate(segs):
        if seg.kind == "line":
            s2 = Line(seg.end, seg.start)
            info = {"support": "ramp", "note": "the orange twisted ramp from the rack's top shelf"}
        else:
            s2 = Arc(seg.centre, -seg.normal, seg.end, seg.angle)
            info = {"support": "slide", "note": "the curved slide onto side B's highway"}
        out.add(s2, **info)
    return out


def core_end_route(p, coil_in: float, z: float) -> Route:
    """The cable's end at the carousel's core (carousel coordinates, centre on the z axis): the last part of the
    first turn along the core, then a bend (the MBR) inward through the hole at the foot of the core to the clamp."""
    cr = p.cable_r
    rho = coil_in + cr
    a = p.mbr
    r = Route("core_end", p.cable_d)
    start = np.array([rho, 0.0, z])
    r.add(Arc(np.array([0.0, 0.0, z]), [0, 0, 1], start, math.radians(60.0)), support="coil",
          note="the first turn, along the core")
    # internally tangent circle of radius a: turn left (towards the centre) until inside the core by 600 mm
    target = p.core_r - 600.0
    off = rho - a
    c = (target ** 2 - off ** 2 - a ** 2) / (2.0 * off * a)
    phi = math.degrees(math.acos(max(-1.0, min(1.0, c))))
    turn(r, +1, a, phi, support="hole", note="through the hole at the foot of the core")
    r.line_to(r.end + 500.0 * r.end_tangent, support="clamp", note="the cable end, held by the clamp inside the core")
    return r


def quay_route(p, pos: dict, q: dict) -> Route:
    """Loading from the quay (task 0084): the storage carousel's coil -> its arch -> down the quay tower -> rollers
    across the quay -> over the vessel's starboard side at the stern -> a 90° bend onto side A's highway (heading
    forward: the vessel's route backwards from there)."""
    R = p.bend_r
    r = Route("quay_loading", p.cable_d)
    names = {"coil": "CABLE COIL", "cage": "guide cage", "guide": "guide frame", "arch": "arch",
             "foot": "tower foot"}
    coil_to_tower(r, p, q["carousel_xy"], q["rest_r"], q["arch"]["guide"], q["coil_z"], q["tower_xy"], q["arch_z"],
                  p.line_z, [0.0, 1.0], names)
    xb = q["tower_xy"][0]
    r.line_to([xb, -p.lane_y - R, p.line_z], support="rollers", rollers="quay",
              note="across the quay on cable rollers, a free span over the quay edge and the vessel's side")
    turn(r, -1, R, 90.0, support="rollers", rollers="boarding bend", note="onto side A's highway, heading forward")
    return r


# ---------------------------------------------------------------------------------------------------------
# Ropes round sheaves, in one vertical plane (x, z)
# ---------------------------------------------------------------------------------------------------------

def _perp(v):
    """Unit direction of travel on a circle at offset v from the centre, turning anticlockwise in (x, z)."""
    return np.array([-v[1], v[0]]) / np.linalg.norm(v)


def tangent_from_point(P, c, r: float, wrap: int):
    """Point where a rope coming from P meets circle (c, r) and goes on round it (wrap +1 anticlockwise in the
    (x, z) plane, -1 clockwise)."""
    P, c = np.asarray(P, float), np.asarray(c, float)
    d = P - c
    L = float(np.linalg.norm(d))
    if L <= r:
        raise ValueError("point inside the circle")
    a = math.atan2(d[1], d[0])
    b = math.acos(r / L)
    for ang in (a + b, a - b):
        T = c + r * np.array([math.cos(ang), math.sin(ang)])
        if float((T - P) @ (wrap * _perp(T - c))) > 0:
            return T
    raise ValueError("no tangent")


def tangent_to_point(c, r: float, wrap: int, Q):
    """Point where a rope going round circle (c, r) with ``wrap`` leaves it towards Q."""
    Q, c = np.asarray(Q, float), np.asarray(c, float)
    d = Q - c
    L = float(np.linalg.norm(d))
    a = math.atan2(d[1], d[0])
    b = math.acos(r / L)
    for ang in (a + b, a - b):
        T = c + r * np.array([math.cos(ang), math.sin(ang)])
        if float((Q - T) @ (wrap * _perp(T - c))) > 0:
            return T
    raise ValueError("no tangent")


def tangent_circles(c1, r1: float, w1: int, c2, r2: float, w2: int):
    """Rope leaving circle 1 (wrap w1) to circle 2 (wrap w2): the two tangent points (fixed-point iteration)."""
    c1, c2 = np.asarray(c1, float), np.asarray(c2, float)
    T2 = c2.copy()
    for _ in range(60):
        T1 = tangent_to_point(c1, r1, w1, T2)
        T2n = tangent_from_point(T1, c2, r2, w2)
        if np.linalg.norm(T2n - T2) < 1e-9:
            T2 = T2n
            break
        T2 = T2n
    return tangent_to_point(c1, r1, w1, T2), T2


def rope_route(name: str, d: float, y: float, items: list, origin=None, udir=None) -> Route:
    """A rope in the vertical plane at ``y`` (x, z), or – with ``origin`` (x, y) and a horizontal ``udir`` – in the
    vertical plane through origin along udir (u, z): items are ("point", (x, z)) or ("sheave", (x, z), radius, wrap, info)
    with radius = the rope centre's radius on that sheave or drum. The first and last item are points or the
    first item a drum (the rope leaves it)."""
    pts2 = []                                  # list of (kind, data) resolved to 2D tangent points
    n = len(items)
    entry = [None] * n
    leave = [None] * n
    for i in range(n - 1):
        a, b = items[i], items[i + 1]
        if a[0] == "point" and b[0] == "point":
            leave[i], entry[i + 1] = np.asarray(a[1], float), np.asarray(b[1], float)
        elif a[0] == "point":
            leave[i] = np.asarray(a[1], float)
            entry[i + 1] = tangent_from_point(a[1], b[1], b[2], b[3])
        elif b[0] == "point":
            leave[i] = tangent_to_point(a[1], a[2], a[3], b[1])
            entry[i + 1] = np.asarray(b[1], float)
        else:
            leave[i], entry[i + 1] = tangent_circles(a[1], a[2], a[3], b[1], b[2], b[3])
    if udir is None:
        o3, u3 = np.array([0.0, y, 0.0]), np.array([1.0, 0.0, 0.0])
    else:
        o3, u3 = np.array([origin[0], origin[1], 0.0]), unit([udir[0], udir[1], 0.0])
    to3 = lambda q: o3 + q[0] * u3 + np.array([0.0, 0.0, q[1]])  # noqa: E731
    axis = np.cross(u3, [0.0, 0.0, 1.0])            # (u, z) anticlockwise turns about u x z
    r = Route(name, d)
    for i in range(n - 1):
        a = items[i]
        if a[0] == "sheave" and entry[i] is not None:
            c = np.asarray(a[1], float)
            u0, u1 = entry[i] - c, leave[i] - c
            ang = math.atan2(u0[0] * u1[1] - u0[1] * u1[0], u0 @ u1)
            if a[3] > 0 and ang < 0:
                ang += 2 * math.pi
            if a[3] < 0 and ang > 0:
                ang -= 2 * math.pi
            r.add(Arc(to3(c), a[3] * axis, to3(entry[i]), abs(ang)), support="sheave", **a[4])
        seg = Line(to3(leave[i]), to3(entry[i + 1]))
        if r.segments:
            r.add(seg, support="free")
        else:
            info = dict(items[0][4]) if items[0][0] == "sheave" else {}
            r.add(seg, support="free", **({"from": info.get("name")} if info else {}))
    return r
