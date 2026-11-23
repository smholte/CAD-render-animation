"""Study 0306 – a vehicle driving a path over uneven ground, solved once at Build. No Blender.

1. **The path** is the line the middle of the unsteered axle(s) follows (the rear axle of a car: it never slides
   sideways). Points (x, y) -> a smooth curve (``Route``: the camera path's Catmull–Rom, ``core/camera_path.Path``),
   its curvature, the stretches tighter than the vehicle can turn.
2. **The speed** along it (``speed_profile``): the wanted speed, slower where the curve is tight (a comfortable
   lateral acceleration), ramps for speeding up and braking, a stop at the end; then time -> distance.
3. **Where every wheel is** at every moment (``kinematics``): bicycle model – heading = the path's, steer angle
   atan(L·κ), each front wheel by Ackermann; each wheel's own distance rolled (inner and outer wheels differ) -> its
   spin angle; each wheel's centre on the ground (``ground.wheel_centre_z``: the rolling envelope).
4. **The ride** (``Ride``): the sprung body (heave, pitch, roll) on springs and dampers per wheel (a solid axle:
   heave + roll of the axle, its springs at the leaf seats), tyres as springs that can leave the ground, bump and
   rebound stops, an anti-roll bar, the body's own weight pushed back in braking / corners. Integrated in 1 ms steps
   (semi-implicit Euler); out come, per video frame: the body's place and turn, each wheel's travel, steer and spin.

Nothing of this runs while the animation plays: Build writes keys.
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from fresing_render.core import camera_path as CP   # noqa: E402

import ground as G                                     # noqa: E402
from spec import Vehicle                               # noqa: E402

GRAV = 9.81


# ---------------------------------------------------------------------------------------------------------------
# 1. the path
# ---------------------------------------------------------------------------------------------------------------

def spline_c2(P: np.ndarray, samples: int, start_dir=None, end_dir=None) -> np.ndarray:
    """A cubic spline through the points P (n x 2), chord-length parameter, curvature continuous (C2): the steering
    of a vehicle following it never jumps. Ends clamped to the given directions, else natural (no bend at the end).
    Plain NumPy (Blender has no SciPy)."""
    P = np.asarray(P, float)
    n = len(P)
    if n == 2 and start_dir is None and end_dir is None:
        return np.linspace(P[0], P[1], samples + 1)
    h = np.maximum(np.linalg.norm(np.diff(P, axis=0), axis=1), 1e-9)       # knot spacing
    # unknowns: first derivatives D_i (tangent vectors per unit of chord length), the standard C2 system
    A = np.zeros((n, n))
    rhs = np.zeros((n, 2))
    for i in range(1, n - 1):
        A[i, i - 1] = h[i]
        A[i, i] = 2 * (h[i - 1] + h[i])
        A[i, i + 1] = h[i - 1]
        rhs[i] = 3 * (h[i] * (P[i] - P[i - 1]) / h[i - 1] + h[i - 1] * (P[i + 1] - P[i]) / h[i])
    if start_dir is not None:
        A[0, 0] = 1.0
        rhs[0] = np.asarray(start_dir, float)[:2]
    else:
        A[0, 0], A[0, 1] = 2.0, 1.0
        rhs[0] = 3 * (P[1] - P[0]) / h[0]
    if end_dir is not None:
        A[-1, -1] = 1.0
        rhs[-1] = np.asarray(end_dir, float)[:2]
    else:
        A[-1, -2], A[-1, -1] = 1.0, 2.0
        rhs[-1] = 3 * (P[-1] - P[-2]) / h[-1]
    D = np.linalg.solve(A, rhs)
    u = np.linspace(0.0, 1.0, samples + 1)[1:]
    out = [P[:1]]
    for i in range(n - 1):
        p0, p1, m0, m1 = P[i], P[i + 1], D[i] * h[i], D[i + 1] * h[i]
        h00 = 2 * u ** 3 - 3 * u ** 2 + 1
        h10 = u ** 3 - 2 * u ** 2 + u
        h01 = -2 * u ** 3 + 3 * u ** 2
        h11 = u ** 3 - u ** 2
        out.append(h00[:, None] * p0 + h10[:, None] * m0 + h01[:, None] * p1 + h11[:, None] * m1)
    return np.vstack(out)


class Route:
    """A smooth path through points (x, y) on the ground, dense every few cm, with curvature."""

    def __init__(self, points, samples: int = 24, start_dir=None, end_dir=None, curve: str = "spline"):
        """``start_dir`` / ``end_dir``: the way the path must leave its first point / reach its last one (a unit
        (x, y); the vehicle's heading where it stands, or the driven heading at a recorded piece's ends). Without
        them the curve leaves straight towards the next point (the camera path's mirrored ends)."""
        pts = np.asarray(points, float)
        pts3 = np.column_stack([pts[:, 0], pts[:, 1], np.zeros(len(pts))])
        gaps = np.linalg.norm(np.diff(pts[:, :2], axis=0), axis=1)
        samples = max(samples, int(np.ceil(gaps.max() / 0.02)) if len(gaps) else samples)   # a dense point every ~2 cm
        self.path = CP.Path(pts3, samples=samples)
        if curve == "spline":
            P = CP.clean(pts3)[:, :2]
            dense = spline_c2(P, samples, start_dir, end_dir)
            dense = np.column_stack([dense, np.zeros(len(dense))])
            self.path.dense = dense
            self.path.along = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))])
            self.path.length = float(self.path.along[-1])
        elif start_dir is not None or end_dir is not None:
            P = CP.clean(pts3)
            a = P[0] - (P[1] - P[0]) if start_dir is None else \
                P[0] - np.linalg.norm(P[1] - P[0]) * np.array([start_dir[0], start_dir[1], 0.0])
            b = P[-1] + (P[-1] - P[-2]) if end_dir is None else \
                P[-1] + np.linalg.norm(P[-1] - P[-2]) * np.array([end_dir[0], end_dir[1], 0.0])
            ends = np.vstack([a, P, b])
            pieces = [CP._catmull_rom(ends[i], ends[i + 1], ends[i + 2], ends[i + 3], samples)
                      for i in range(len(P) - 1)]
            dense = np.vstack([pieces[0]] + [q[1:] for q in pieces[1:]])
            self.path.dense = dense
            self.path.along = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))])
            self.path.length = float(self.path.along[-1])
        d = self.path.dense[:, :2]
        self.s = self.path.along
        self.length = self.path.length
        # even spacing (5 cm) for the curvature
        n = max(int(self.length / 0.05), 8)
        self.ss = np.linspace(0.0, self.length, n + 1)
        self.xy = np.column_stack([np.interp(self.ss, self.s, d[:, 0]), np.interp(self.ss, self.s, d[:, 1])])
        t = np.gradient(self.xy, self.ss, axis=0)
        self.heading = np.unwrap(np.arctan2(t[:, 1], t[:, 0]))
        k = np.gradient(self.heading, self.ss)
        w = max(int(0.15 / 0.05), 1)                      # over 15 cm: only the numeric noise of the dense line
        self.kappa = np.convolve(k, np.ones(w) / w, mode="same")

    def at(self, s):
        s = np.clip(s, 0.0, self.length)
        x = np.interp(s, self.ss, self.xy[:, 0])
        y = np.interp(s, self.ss, self.xy[:, 1])
        h = np.interp(s, self.ss, self.heading)
        k = np.interp(s, self.ss, self.kappa)
        return x, y, h, k

    def too_tight(self, r_min: float):
        """Stretches (s0, s1, tightest radius) where the path turns tighter than the vehicle can."""
        bad = np.abs(self.kappa) > 1.0 / r_min
        out, i = [], 0
        while i < len(bad):
            if bad[i]:
                j = i
                while j < len(bad) and bad[j]:
                    j += 1
                out.append((float(self.ss[i]), float(self.ss[j - 1]), float(1.0 / np.abs(self.kappa[i:j]).max())))
                i = j
            else:
                i += 1
        return out


# ---------------------------------------------------------------------------------------------------------------
# 2. the speed
# ---------------------------------------------------------------------------------------------------------------

def speed_profile(route: Route, veh: Vehicle, v_want: float, v_start: float = 0.0, v_end: float = 0.0,
                  slow=()):
    """Speed at every point of ``route.ss``: at most ``v_want``, at most sqrt(a_lat / |κ|) in curves, ramps
    a_acc / a_brake (forward and backward pass). ``slow``: (s0, s1, v) stretches to take slower (a speed bump)."""
    s = route.ss
    v = np.full(len(s), min(v_want, veh.v_max))
    k = np.abs(route.kappa)
    v = np.minimum(v, np.sqrt(veh.a_lat / np.maximum(k, 1e-6)))
    for s0, s1, vs in slow:
        v[(s >= s0) & (s <= s1)] = np.minimum(v[(s >= s0) & (s <= s1)], vs)
    v[0] = min(v[0], v_start)
    v[-1] = min(v[-1], v_end)
    ds = np.diff(s)
    for i in range(1, len(s)):
        v[i] = min(v[i], math.sqrt(v[i - 1] ** 2 + 2 * veh.a_acc * ds[i - 1]))
    for i in range(len(s) - 2, -1, -1):
        v[i] = min(v[i], math.sqrt(v[i + 1] ** 2 + 2 * veh.a_brake * ds[i]))
    return v


def time_along(route: Route, v: np.ndarray, dt: float):
    """Distance s(t) every ``dt`` from the speed profile; also v(t) and a(t)."""
    s = route.ss
    vm = np.maximum(0.5 * (v[1:] + v[:-1]), 1e-3)
    t = np.concatenate([[0.0], np.cumsum(np.diff(s) / vm)])
    T = float(t[-1])
    tt = np.arange(0.0, T + dt, dt)
    st = np.interp(tt, t, s)
    vt = np.interp(st, s, v)
    at = np.gradient(vt, dt)
    return tt, st, vt, at


# ---------------------------------------------------------------------------------------------------------------
# 3. where the wheels are
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class Wheel:
    axle: int
    side: int          # +1 left, -1 right
    x: float           # vehicle frame
    y: float
    r: float
    w: float
    steered: bool


def wheels_of(veh: Vehicle) -> list:
    out = []
    for ai, a in enumerate(veh.axles):
        for side in (1, -1):
            out.append(Wheel(ai, side, a.x, side * a.track / 2, a.wheel_r,
                             a.tyre_w * (2.3 if a.twin else 1.0), a.steered))
    return out


def kinematics(route: Route, veh: Vehicle, s, ground: G.Grid):
    """Per moment (arrays over s): the vehicle frame's place (the origin = ground under the front axle middle,
    as in spec.py), heading, steer per wheel (Ackermann), each wheel's centre over the ground, the ground lift of each
    wheel's centre (rolling envelope) and its rolled distance."""
    x, y, h, k = route.at(s)
    L = veh.wheelbase
    rx = veh.rear_x
    fwd = np.stack([np.cos(h), np.sin(h)], -1)
    left = np.stack([-np.sin(h), np.cos(h)], -1)
    origin = np.stack([x, y], -1) - fwd * rx               # the rear axle middle is at x = rx in the vehicle frame
    whs = wheels_of(veh)
    steer = np.zeros((len(whs), len(s)))
    cx = np.zeros((len(whs), len(s)))
    cy = np.zeros((len(whs), len(s)))
    for i, w in enumerate(whs):
        if w.steered:
            Lw = w.x - rx                                  # this axle's distance in front of the turning line
            steer[i] = np.arctan(Lw * k / (1.0 - w.y * k))  # tan d = Lw / (R - y): each wheel round the same centre
        p = origin + fwd * w.x + left * w.y
        cx[i], cy[i] = p[:, 0], p[:, 1]
    # per wheel (radius and width differ between axles)
    lift = np.zeros_like(cx)
    for i, w in enumerate(whs):
        zc_i, _ = G.wheel_centre_z(ground, cx[i], cy[i], h + steer[i], w.r, w.w)
        lift[i] = zc_i - w.r                               # 0 on flat ground at z = 0
    rolled = np.concatenate([np.zeros((len(whs), 1)),
                             np.cumsum(np.hypot(np.diff(cx, axis=1), np.diff(cy, axis=1)), axis=1)], axis=1)
    return dict(origin=origin, heading=h, kappa=k, steer=steer, cx=cx, cy=cy, lift=lift, rolled=rolled, wheels=whs)


# ---------------------------------------------------------------------------------------------------------------
# 4. the ride
# ---------------------------------------------------------------------------------------------------------------

class Ride:
    """The body (heave z at the centre of mass, pitch θ nose up, roll φ left side up) on its axles.

    Generalised coordinates q = [z, θ, φ, unsprung …]: an independent wheel has its own height; a solid axle has
    heave and roll (the wheels at ±track/2, the springs at the leaf seats ±seat/2). Every spring is an *element*
    between two points that move linearly with q (a row ``J``): deflection = J·q (+ the road for a tyre).
    """

    def __init__(self, veh: Vehicle, front_share: float):
        self.veh = veh
        L = veh.wheelbase
        rx = veh.rear_x
        self.xc = rx + front_share * L                     # centre of mass x (vehicle frame)
        ms = veh.sprung
        names = ["z", "pitch", "roll"]
        masses = [ms, veh.i_pitch, veh.i_roll]
        self.wheel_rows = []                               # per wheel: J of the wheel centre height
        self.body_rows = []                                # per wheel: J of the body point above it
        elems = []                                         # (kind, J, k, c, stops)
        whs = wheels_of(veh)
        self.whs = whs
        # static loads per axle (weight split by lever), for tyre lift-off
        loads = []
        for a in veh.axles:
            loads.append(None)
        n_q = 3
        col = {}
        for ai, a in enumerate(veh.axles):
            if a.kind.startswith("SOLID"):
                col[ai] = (n_q, n_q + 1)
                names += [f"{a.name} axle heave", f"{a.name} axle roll"]
                masses += [2 * a.unsprung, 2 * a.unsprung * (a.track / 2) ** 2]
                n_q += 2
            else:
                col[ai] = (n_q, n_q + 1)                   # left, right wheel heights
                names += [f"{a.name} L wheel", f"{a.name} R wheel"]
                masses += [a.unsprung, a.unsprung]
                n_q += 2
        self.n = n_q
        self.names = names
        self.M = np.array(masses)

        def body_at(x, y):
            J = np.zeros(n_q)
            J[0], J[1], J[2] = 1.0, x - self.xc, y
            return J

        # static wheel loads: sprung weight by lever between steered and unsteered axle groups, + unsprung
        steer_axles = [i for i, a in enumerate(veh.axles) if a.steered]
        rear_axles = [i for i, a in enumerate(veh.axles) if not a.steered]
        static = {}
        for group, share in ((steer_axles, front_share), (rear_axles, 1 - front_share)):
            for i in group:
                static[i] = (ms * share / len(group) / 2 + veh.axles[i].unsprung) * GRAV
        self.static = static

        for wi, w in enumerate(whs):
            a = veh.axles[w.axle]
            c0, c1 = col[w.axle]
            Jw = np.zeros(n_q)
            if a.kind.startswith("SOLID"):
                Jw[c0], Jw[c1] = 1.0, w.side * a.track / 2
                seat = abs(a.points.get("leaf_seat", (0, a.track / 2 * 0.5, 0))[1])
                Js = np.zeros(n_q)
                Js[c0], Js[c1] = 1.0, w.side * seat
                Jb = body_at(w.x, w.side * seat)
                # a leaf pack's rate is given per pack (at the seat)
                elems.append(("spring", Js - Jb, a.k_spring, a.c_damp, a.travel))
            else:
                Jw[c0 if w.side > 0 else c1] = 1.0
                Jb = body_at(w.x, w.y)
                elems.append(("spring", Jw - Jb, a.k_spring, a.c_damp, a.travel))
            self.wheel_rows.append(Jw)
            self.body_rows.append(body_at(w.x, w.y))
            elems.append(("tyre", Jw, a.k_tyre, 120.0, static[w.axle]))
        for ai, a in enumerate(veh.axles):
            if a.k_arb > 0 and not a.kind.startswith("SOLID"):
                l = [i for i, w in enumerate(whs) if w.axle == ai and w.side > 0][0]
                r = [i for i, w in enumerate(whs) if w.axle == ai and w.side < 0][0]
                J = (self.wheel_rows[l] - self.body_rows[l]) - (self.wheel_rows[r] - self.body_rows[r])
                elems.append(("arb", J, a.k_arb, 0.0, None))
        self.elems = elems
        self.J = np.array([e[1] for e in elems])
        self.k = np.array([e[2] for e in elems])
        self.c = np.array([e[3] for e in elems])
        self.is_tyre = np.array([e[0] == "tyre" for e in elems])
        self.is_spring = np.array([e[0] == "spring" for e in elems])
        self.tyre_static = np.array([e[4] if e[0] == "tyre" else 0.0 for e in elems])
        lo = np.array([e[4][0] if e[0] == "spring" else -np.inf for e in elems])
        hi = np.array([e[4][1] if e[0] == "spring" else np.inf for e in elems])
        self.lo, self.hi = lo, hi
        self.tyre_of_wheel = [i for i, e in enumerate(elems) if e[0] == "tyre"]
        self.roll_arm = veh.cog_h - (0.12 if veh.mass < 5000 else 0.55)   # above the roll centre
        self.pitch_arm = veh.cog_h

    def run(self, road, a_long, a_lat, dt: float):
        """road: (wheels, steps) the ground lift under each wheel's centre (m); a_long, a_lat: (steps,) m/s².
        Returns q (steps, n), tyre forces (steps, wheels)."""
        n = self.n
        q = np.zeros(n)
        qd = np.zeros(n)
        steps = road.shape[1]
        out = np.zeros((steps, n))
        tyref = np.zeros((steps, len(self.whs)))
        J, k, c = self.J, self.k, self.c
        tyre_rows = np.array(self.tyre_of_wheel)
        ms = self.veh.sprung
        Minv = 1.0 / self.M
        r = np.zeros(len(k))
        k_stop = 15.0 * k
        for i in range(steps):
            r[tyre_rows] = road[:, i]
            d = J @ q                                      # spring: wheel minus body (+ = compressed = bump)
            dv = J @ qd
            f = -k * d - c * dv                            # force on the "+" side (the wheel) of each element
            # tyre: compression = road - wheel; force up on the wheel, never pulling (it leaves the ground)
            comp = r[tyre_rows] - d[tyre_rows]
            ft = k[tyre_rows] * comp - c[tyre_rows] * dv[tyre_rows]
            ft = np.maximum(ft, -self.tyre_static[tyre_rows])
            f[tyre_rows] = ft
            # bump / rebound stops: a stiff spring past the travel
            sp = self.is_spring
            over = np.where(d > self.hi, d - self.hi, np.where(d < self.lo, d - self.lo, 0.0))
            f[sp] -= (k_stop * over)[sp]
            Q = J.T @ f
            Q[1] += ms * a_long[i] * self.pitch_arm         # speeding up: nose up (squat); braking: nose down
            Q[2] += ms * a_lat[i] * self.roll_arm           # a left turn (a_lat > 0): the body leans out, left side up
            qd += dt * Q * Minv
            q += dt * qd
            out[i] = q
            tyref[i] = ft + self.tyre_static[tyre_rows]
        return out, tyref

    def wheel_travel(self, q):
        """(steps, wheels): each wheel's travel relative to the body (+ = bump, compressed)."""
        Jw = np.array(self.wheel_rows)
        Jb = np.array(self.body_rows)
        return q @ (Jw - Jb).T


# ---------------------------------------------------------------------------------------------------------------
# all of it
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class Result:
    t: np.ndarray            # frame times
    origin: np.ndarray       # (frames, 2)
    heading: np.ndarray
    body_z: np.ndarray       # heave of the vehicle frame's origin (m) – with pitch and roll applied about the CoG
    pitch: np.ndarray        # rad, nose up
    roll: np.ndarray         # rad, left side up
    travel: np.ndarray       # (wheels, frames) m, + = bump
    steer: np.ndarray        # (wheels, frames) rad
    spin: np.ndarray         # (wheels, frames) rad
    tyre_force: np.ndarray   # (wheels, frames) N
    speed: np.ndarray
    xc: float
    timings: dict
    airborne: np.ndarray     # (wheels, frames) bool – off the ground


def drive(veh: Vehicle, points, ground: G.Grid, v_want: float, fps: float = 25.0, front_share: float = 0.55,
          dt: float = 1e-3, slow=(), route: Route | None = None, profile=None, v_start: float = 0.0,
          v_end: float = 0.0) -> Result:
    tm = {}
    t0 = time.perf_counter()
    route = route or Route(points)
    v = speed_profile(route, veh, v_want, v_start, v_end, slow=slow) if profile is None else profile
    tt, st, vt, at = time_along(route, v, dt)
    tm["path + speed"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    kin = kinematics(route, veh, st, ground)
    tm["wheels on the ground"] = time.perf_counter() - t0
    a_lat = vt ** 2 * kin["kappa"]
    t0 = time.perf_counter()
    ride = Ride(veh, front_share)
    q, tf = ride.run(kin["lift"], at, a_lat, dt)
    tm["ride (1 ms steps)"] = time.perf_counter() - t0
    # frames
    step = int(round(1.0 / (fps * dt)))
    idx = np.arange(0, len(tt), step)
    trav = ride.wheel_travel(q)[idx].T
    # the vehicle frame's origin height from the CoG heave and pitch (origin at x=0, CoG at xc)
    z0 = q[idx, 0] + (0.0 - ride.xc) * q[idx, 1]
    whs = kin["wheels"]
    spin = np.array([kin["rolled"][i, idx] / w.r for i, w in enumerate(whs)])
    air = tf[idx].T < 1.0
    return Result(t=tt[idx], origin=kin["origin"][idx], heading=kin["heading"][idx], body_z=z0,
                  pitch=q[idx, 1], roll=q[idx, 2], travel=trav, steer=kin["steer"][:, idx], spin=spin,
                  tyre_force=tf[idx].T, speed=vt[idx], xc=ride.xc, timings=tm, airborne=air)
