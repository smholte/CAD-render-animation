"""Study 0306 – drive it yourself: keyboard or game controller -> a recorded drive -> an editable path. No Blender.

**Live** (``Driver``): every tick of the modal operator's timer (about 60 a second, irregular) the inputs move the
vehicle on the ground plane – a kinematic bicycle (the rear axle's middle never slides sideways): speed from throttle /
brake ramps, steer from the keys (rate-limited, back to the middle when let go, less lock at speed) or the stick
(dead zone, a curve, a light filter). Reverse: brake held at a standstill. The view shows the vehicle there (only its
root moves while driving: no suspension live – that is solved at Build).

**After** (``to_path``): the samples (t, x, y, heading, speed) are split where the direction changes (forward /
reverse: a 3-point turn is three pieces), resampled every 10 cm, smoothed (the tick jitter), and **reduced** to a few
points whose smooth curve (the same curve a drawn path uses, ``ride.Route``) stays within ``tol`` of the drive – the
path the user can edit like a drawn one. The speed becomes a few keys over the share of the way (kept when points are
moved). ``replay`` checks that the path + speed keys drive back where the user drove.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ride as R                                       # noqa: E402
from spec import Vehicle                               # noqa: E402


# ---------------------------------------------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class Inputs:
    """One moment's controls, all 0 … 1 (steer -1 … 1, + = left). ``analog``: from a stick (direct) or keys."""
    throttle: float = 0.0
    brake: float = 0.0
    steer: float = 0.0
    analog: bool = False


def stick(raw: float, dead: float = 0.12, expo: float = 0.45) -> float:
    """A stick axis -1 … 1 -> steer: a dead zone in the middle, finer near the centre (expo)."""
    a = abs(raw)
    if a <= dead:
        return 0.0
    u = (a - dead) / (1.0 - dead)
    u = (1 - expo) * u + expo * u ** 3
    return math.copysign(min(u, 1.0), raw)


# ---------------------------------------------------------------------------------------------------------------
# the live model
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class Driver:
    veh: Vehicle
    x: float = 0.0             # rear axle middle
    y: float = 0.0
    heading: float = 0.0
    v: float = 0.0             # + forward, - reverse
    steer: float = 0.0         # the bicycle's steer angle (rad)
    t: float = 0.0
    reverse: bool = False
    _still: float = 0.0
    samples: list = field(default_factory=list)
    lock_time: float = 1.3     # s from the middle to full lock with a key
    back_time: float = 0.8     # s from full lock back to the middle when the key is let go
    v_reverse: float = 2.5     # m/s top speed backwards

    def __post_init__(self):
        self.samples.append((self.t, self.x, self.y, self.heading, self.v, self.steer))

    def max_steer_at(self, v: float) -> float:
        """Less lock at speed, as a driver does (keys would otherwise flick the car round). At full lock the INNER
        wheel is at the vehicle's max_steer: the bicycle's (middle) angle is a little less."""
        veh = self.veh
        tr = veh.axles[0].track
        mid = math.atan(veh.wheelbase / (veh.wheelbase / math.tan(veh.max_steer) + tr / 2))
        return mid / (1.0 + (abs(v) / 9.0) ** 2)

    def tick(self, inp: Inputs, dt: float) -> None:
        """Move on by ``dt`` (the real time since the last tick). A slow redraw (a big model: 5–10 ticks a second)
        is cut into steps of at most 20 ms, so the drive keeps real time; a hitch over 0.5 s is not caught up."""
        dt = min(max(dt, 0.0), 0.5)
        k = max(1, int(math.ceil(dt / 0.02)))
        for _ in range(k):
            self._step(inp, dt / k)
        self.samples.append((self.t, self.x, self.y, self.heading, self.v, self.steer))

    def _step(self, inp: Inputs, dt: float) -> None:
        veh = self.veh
        # speed
        if self.reverse:
            acc = -veh.a_acc * 0.6 * inp.brake + veh.a_brake * inp.throttle
        else:
            acc = veh.a_acc * inp.throttle - veh.a_brake * inp.brake
        drag = 0.03 * self.v + 0.0004 * self.v * abs(self.v)
        v_new = self.v + (acc - drag) * dt
        if not self.reverse and self.v >= 0 and v_new < 0:
            v_new = 0.0
        if self.reverse and self.v <= 0 and v_new > 0:
            v_new = 0.0
        self.v = float(np.clip(v_new, -self.v_reverse, veh.v_max))
        # gear: brake held at a standstill -> reverse; throttle at a standstill in reverse -> forward
        if abs(self.v) < 0.05:
            self._still += dt
            if self._still > 0.35:
                if not self.reverse and inp.brake > 0.5 and inp.throttle < 0.1:
                    self.reverse = True
                elif self.reverse and inp.throttle > 0.5 and inp.brake < 0.1:
                    self.reverse = False
        else:
            self._still = 0.0
        # steer
        lim = self.max_steer_at(self.v)
        if inp.analog:
            target = inp.steer * lim
            k = 1.0 - math.exp(-dt / 0.08)        # a light filter: a twitchy thumb is not a twitchy car
            self.steer += (target - self.steer) * k
        else:
            if abs(inp.steer) > 0.01:
                rate = veh.max_steer / self.lock_time
                self.steer += math.copysign(rate * dt, inp.steer)
            else:
                rate = veh.max_steer / self.back_time
                self.steer -= math.copysign(min(rate * dt, abs(self.steer)), self.steer)
        self.steer = float(np.clip(self.steer, -lim, lim))
        # move (bicycle, rear axle middle)
        L = veh.wheelbase
        self.heading += self.v * math.tan(self.steer) / L * dt
        self.x += self.v * math.cos(self.heading) * dt
        self.y += self.v * math.sin(self.heading) * dt
        self.t += dt

    def array(self) -> np.ndarray:
        return np.array(self.samples, float)


# ---------------------------------------------------------------------------------------------------------------
# recorded drive -> editable path
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class Piece:
    """One forward or reverse stretch: control points (the editable path), speed keys over the share of its length
    (share 0 … 1, speed m/s, always >= 0), the direction, and when it starts (s) after the previous piece."""
    points: np.ndarray
    speed_keys: np.ndarray
    ends: tuple
    reverse: bool
    wait: float = 0.0
    max_dev: float = 0.0
    driven_length: float = 0.0


def _smooth(a: np.ndarray, sigma_pts: float) -> np.ndarray:
    if sigma_pts <= 0 or len(a) < 5:
        return a.copy()
    r = int(3 * sigma_pts)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_pts) ** 2)
    k /= k.sum()
    pad = np.concatenate([np.repeat(a[:1], r, 0), a, np.repeat(a[-1:], r, 0)])
    out = np.stack([np.convolve(pad[:, j], k, mode="valid") for j in range(a.shape[1])], -1)
    out[0], out[-1] = a[0], a[-1]                      # the ends stay where they were
    return out


def _deviation(route: R.Route, pts: np.ndarray) -> np.ndarray:
    """Distance of each point (in order along the drive) from the route: both run the same way, so each point is
    looked for only in a window of the route around the same share of the length (±2 m)."""
    rx = route.xy                                         # every 5 cm
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    guess = np.round(s / max(s[-1], 1e-9) * (len(rx) - 1)).astype(int)
    w = 40
    idx = np.clip(guess[:, None] + np.arange(-w, w + 1)[None, :], 0, len(rx) - 1)
    d = np.linalg.norm(rx[idx] - pts[:, None, :], axis=-1)
    return d.min(axis=1)


def reduce_path(xy: np.ndarray, tol: float, max_points: int = 400, r_min: float = 0.0,
                gap: float = 1.0, ends=(None, None)) -> tuple[np.ndarray, float]:
    """Few points (worst first, per stretch) whose smooth curve stays within ``tol`` of the line ``xy`` and, with
    ``r_min``, never turns tighter than the vehicle can (a sparse curve can cut a full-lock corner tighter)."""
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))])
    keep = [0, len(xy) - 1]
    # start with one point every ~25 m, so long straights do not wobble
    n0 = max(int(s[-1] / 25.0), 1)
    for k in range(1, n0):
        keep.append(int(np.searchsorted(s, s[-1] * k / n0)))
    keep = sorted(set(keep))
    while True:
        route = R.Route(xy[keep], start_dir=ends[0], end_dir=ends[1])
        dev = _deviation(route, xy)
        tight = []
        if r_min > 0:
            for s0, s1, _r in route.too_tight(r_min):
                tight.append(int(np.argmin(np.abs(s - 0.5 * (s0 + s1)))))
        if (dev.max() <= tol and not tight) or len(keep) >= max_points:
            return xy[keep], float(dev.max())
        # in every stretch between two kept points that is off by more than tol, or too tight: add its worst point
        # never closer than ``gap`` to a kept point: two points close together bend the curve sharply between them
        add = []
        for a, b in zip(keep[:-1], keep[1:]):
            ok = np.nonzero((s > s[a] + gap) & (s < s[b] - gap))[0]
            if len(ok):
                k = int(ok[np.argmax(dev[ok])])
                if dev[k] > tol:
                    add.append(k)
                    continue
            # too tight here: a point at the tightest spot, allowed closer (a full-lock arc needs them denser)
            near = [t for t in tight if s[a] <= s[t] <= s[b]]
            if near:
                ok = np.nonzero((s > s[a] + gap / 3) & (s < s[b] - gap / 3))[0]
                if len(ok):
                    add.append(int(ok[np.argmin(np.abs(s[ok] - s[near[0]]))]))
        if not add:
            return xy[keep], float(dev.max())
        keep = sorted(set(keep + add))


def reduce_speed(share: np.ndarray, v: np.ndarray, tol: float = 0.3) -> np.ndarray:
    """Few (share, speed) keys whose straight lines stay within ``tol`` m/s (Douglas–Peucker)."""
    def rec(i, j):
        if j <= i + 1:
            return [i]
        x0, x1 = share[i], share[j]
        lin = v[i] + (v[j] - v[i]) * (share[i:j + 1] - x0) / max(x1 - x0, 1e-12)
        e = np.abs(v[i:j + 1] - lin)
        k = int(np.argmax(e))
        if e[k] <= tol:
            return [i]
        return rec(i, i + k) + rec(i + k, j)
    idx = rec(0, len(v) - 1) + [len(v) - 1]
    return np.column_stack([share[idx], v[idx]])


def to_path(samples: np.ndarray, tol: float = 0.05, step: float = 0.10, smooth_m: float = 0.4,
            r_min: float = 0.0) -> list:
    """The recorded samples -> pieces (forward / reverse), each with few control points and speed keys."""
    t, x, y, h, v = samples[:, 0], samples[:, 1], samples[:, 2], samples[:, 3], samples[:, 4]
    moving = np.abs(v) > 0.05
    sign = np.where(v > 0.05, 1, np.where(v < -0.05, -1, 0))
    pieces = []
    i, n = 0, len(t)
    last_end_t = 0.0
    while i < n:
        while i < n and sign[i] == 0:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and (sign[j] == sign[i] or (sign[j] == 0 and j + 1 < n and sign[j + 1] == sign[i])):
            j += 1
        seg = slice(max(i - 1, 0), min(j + 1, n))
        xy = np.column_stack([x[seg], y[seg]])
        ds = np.linalg.norm(np.diff(xy, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(ds)])
        if s[-1] < 0.3:                                 # a twitch, not a piece
            i = j
            continue
        m = max(int(s[-1] / step), 2)
        ss = np.linspace(0, s[-1], m + 1)
        rs = np.column_stack([np.interp(ss, s, xy[:, 0]), np.interp(ss, s, xy[:, 1])])
        rs = _smooth(rs, smooth_m / step)
        def unit(v):
            return tuple(v / max(np.linalg.norm(v), 1e-9))
        k = max(int(0.3 / step), 1)
        ends = (unit(rs[min(k, len(rs) - 1)] - rs[0]), unit(rs[-1] - rs[max(len(rs) - 1 - k, 0)]))
        pts, dev = reduce_path(rs, tol, r_min=r_min, ends=ends)
        vs = np.interp(ss, s, np.abs(v[seg]))
        vs = _smooth(vs[:, None], 0.3 / step)[:, 0]
        keys = reduce_speed(ss / s[-1], vs)
        pieces.append(Piece(points=pts, speed_keys=keys, ends=ends, reverse=sign[i] < 0, wait=float(t[i] - last_end_t),
                            max_dev=dev, driven_length=float(s[-1])))
        last_end_t = float(t[min(j, n - 1)])
        i = j
    return pieces


def piece_profile(piece: Piece, route: R.Route) -> np.ndarray:
    """The speed keys put on a (possibly edited) route: speed at every ``route.ss`` by share of the length."""
    share = route.ss / max(route.length, 1e-9)
    v = np.interp(share, piece.speed_keys[:, 0], piece.speed_keys[:, 1])
    return np.maximum(v, 0.15)                           # never stand still inside a piece


def replay(piece: Piece) -> tuple[np.ndarray, float]:
    """Drive the piece's path at its speed keys: (xy every 10 cm, its duration in s)."""
    route = R.Route(piece.points, start_dir=piece.ends[0], end_dir=piece.ends[1])
    v = piece_profile(piece, route)
    vm = 0.5 * (v[1:] + v[:-1])
    T = float(np.sum(np.diff(route.ss) / vm))
    return route.xy, T
