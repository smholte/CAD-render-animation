"""Driving a vessel, recording the drive and turning it into an editable path (study 0312). No Blender.

**The vessel** is a three-way model (forward, sideways, turning) set by a preset's few numbers – the top speed, how
long it takes to get to its cruise speed, how tight it turns, how fast it spins on the spot and slides sideways on
its thrusters. Waves move it up and down (0085's motion); they do not steer it here.

    du/dt = a (lever * u_top^2 - u|u|)            a from the time to 90 % of the cruise speed (tanh)
    T_r dr/dt + r = helm * u / R_min  +  spin * w(u)          R_min = half the tactical diameter
    v  = side * v_side  -  drift * r * L / 2                   (the stern swings out in a turn)

**The controls** (what a person presses; ``Keys`` holds the state):

    Up / Down      the throttle lever, 10 % a press (held: 40 % a second); it stays where it is set
    Left / Right   the helm while held; back to the middle when let go (1 a second)
    Q / E          slide to port / starboard on the thrusters (while held)
    A / D          turn on the spot (while held)
    Space          stop: the lever to 0 and hold the place (DP) when the vessel has it
    Shift          half the rates (fine)

A game controller gives the same four numbers (left stick x = helm, triggers = lever up / down, right stick =
slide / spin) – ``Keys.from_pad``.

**Recording** keeps 30 samples a second (x, y, heading, speed). **Smoothing** turns them into what a user edits:
a few path points (Ramer–Douglas–Peucker, then the app's own centripetal Catmull-Rom curve of ``core/camera_path``),
a few speed keys along the path and a few "crab" keys (heading off the path's direction: a sideways slide or a spin).
**Following** a drawn path drives the same vessel model along it (line-of-sight steering, a speed planner that slows
for bends the vessel cannot take at speed and spins where it must), so a drawn path is driven the way the vessel can.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from fresing_render.core import camera_path  # noqa: E402  (the app's own curve: the path the user edits)

KNOT = 0.514444
DT = 1.0 / 60.0
REC_HZ = 30


@dataclass
class Model:
    length: float
    u_top: float          # m/s
    u_cruise: float
    a: float              # 1/m
    r_min: float          # m
    t_r: float            # s
    spin: float           # rad/s
    v_side: float         # m/s
    drift: float = 0.25

    @classmethod
    def of(cls, p):
        u_top, u_c = p.speed_max * KNOT, max(p.speed_cruise, 0.5) * KNOT
        a = math.atanh(0.9) / (u_c * max(p.accel_s, 1.0))
        return cls(p.length, u_top, u_c, a, p.turn_diameter * p.length / 2, 0.15 * p.length / u_c + 1.5,
                   math.radians(p.spin_deg_s), p.side_knots * KNOT)

    def yaw_rate_max(self, u: float) -> float:
        return abs(u) / self.r_min + self.spin * self._spin_share(u)

    def _spin_share(self, u: float) -> float:
        return 1.0 if self.spin <= 0 else max(0.25, 1.0 - abs(u) / self.u_cruise)


@dataclass
class State:
    x: float = 0.0
    y: float = 0.0
    psi: float = 0.0       # heading, rad from +x (anticlockwise)
    u: float = 0.0
    v: float = 0.0
    r: float = 0.0
    t: float = 0.0


def step(m: Model, s: State, lever: float, helm: float, side: float, spin: float, dt: float = DT) -> State:
    target = lever * m.u_top * m.u_top
    target = target if lever >= 0 else 0.6 * target              # astern is weaker
    du = m.a * (target - s.u * abs(s.u)) if lever != 0 or s.u != 0 else 0.0
    if lever == 0:
        du = -m.a * s.u * abs(s.u) - 0.02 * s.u                  # coasts to a stop
    u = s.u + du * dt
    r_cmd = helm * u / m.r_min + spin * m.spin * m._spin_share(u)
    r = s.r + (r_cmd - s.r) * dt / m.t_r
    v_cmd = side * m.v_side - m.drift * r * m.length / 2
    v = s.v + (v_cmd - s.v) * dt / 3.0
    psi = s.psi + r * dt
    c, sn = math.cos(psi), math.sin(psi)
    return State(s.x + (u * c - v * sn) * dt, s.y + (u * sn + v * c) * dt, psi, u, v, r, s.t + dt)


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------

class Keys:
    """What is held, and the lever / helm it gives."""

    def __init__(self):
        self.down = set()
        self.lever = 0.0
        self.helm = 0.0

    def press(self, key: str):
        if key == "UP":
            self.lever = min(1.0, round(self.lever + 0.1, 3))
        elif key == "DOWN":
            self.lever = max(-1.0, round(self.lever - 0.1, 3))
        elif key == "SPACE":
            self.lever = 0.0
        self.down.add(key)

    def release(self, key: str):
        self.down.discard(key)

    def tick(self, dt: float):
        fine = 0.5 if "SHIFT" in self.down else 1.0
        if "UP" in self.down:
            self.lever = min(1.0, self.lever + 0.4 * fine * dt)
        if "DOWN" in self.down:
            self.lever = max(-1.0, self.lever - 0.4 * fine * dt)
        want = (("LEFT" in self.down) - ("RIGHT" in self.down)) * fine
        rate = 2.0 if want else 1.0
        self.helm += max(-rate * dt, min(rate * dt, want - self.helm))
        side = (("Q" in self.down) - ("E" in self.down)) * fine
        spin = (("A" in self.down) - ("D" in self.down)) * fine
        return self.lever, self.helm, side, spin

    @staticmethod
    def from_pad(lx: float, lt: float, rt: float, rx: float, ry: float):
        """A controller's sticks and triggers -> (lever change per second, helm, side, spin)."""
        dead = lambda a: 0.0 if abs(a) < 0.12 else (a - math.copysign(0.12, a)) / 0.88   # noqa: E731
        return (rt - lt) * 0.4, -dead(lx), -dead(rx), dead(ry)


def drive(m: Model, events, seconds: float, start: State | None = None):
    """Play a list of (t, "press"/"release", key) like a person at the keyboard; return the recorded samples
    (t, x, y, heading, speed over ground, lever, helm) at REC_HZ."""
    s = start or State()
    keys = Keys()
    ev = sorted(events)
    i = 0
    rec = []
    n = int(round(seconds / DT))
    every = int(round(1.0 / (REC_HZ * DT)))
    for k in range(n + 1):
        while i < len(ev) and ev[i][0] <= s.t + 1e-9:
            (keys.press if ev[i][1] == "press" else keys.release)(ev[i][2])
            i += 1
        lever, helm, side, spin = keys.tick(DT)
        if k % every == 0:
            rec.append((s.t, s.x, s.y, s.psi, math.hypot(s.u, s.v), lever, helm))
        s = step(m, s, lever, helm, side, spin)
    return np.array(rec)


# ---------------------------------------------------------------------------
# smoothing: recorded samples -> path points + speed keys + crab keys
# ---------------------------------------------------------------------------

def rdp(points: np.ndarray, eps: float) -> list[int]:
    """Indices kept by Ramer–Douglas–Peucker (iterative)."""
    keep = np.zeros(len(points), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p, q = points[a], points[b]
        d = q - p
        L = float(np.hypot(*d[:2])) if points.shape[1] >= 2 else abs(float(d[0]))
        seg = points[a + 1:b]
        if L < 1e-9:
            dist = np.linalg.norm(seg - p, axis=1)
        else:
            dist = np.abs(d[0] * (seg[:, 1] - p[1]) - d[1] * (seg[:, 0] - p[0])) / L
        j = int(np.argmax(dist))
        if dist[j] > eps:
            keep[a + 1 + j] = True
            stack += [(a, a + 1 + j), (a + 1 + j, b)]
    return list(np.nonzero(keep)[0])


@dataclass
class EditablePath:
    points: np.ndarray        # n x 3 path points (what the user drags)
    speed_keys: np.ndarray    # (distance along, knots)
    crab_keys: np.ndarray     # (distance along, degrees off the path's direction)
    path: object              # camera_path.Path
    max_off: float            # m: the largest distance from the recorded track to the path
    mean_off: float


def _dist_to_polyline(p: np.ndarray, line: np.ndarray) -> np.ndarray:
    a, b = line[:-1, :2], line[1:, :2]
    ab = b - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-12)
    out = np.empty(len(p))
    for i, q in enumerate(p[:, :2]):
        t = np.clip(((q - a) * ab).sum(1) / L2, 0, 1)
        out[i] = np.sqrt((((a + ab * t[:, None]) - q) ** 2).sum(1)).min()
    return out


def smooth(rec: np.ndarray, length: float) -> EditablePath:
    xy = rec[:, 1:3]
    eps = max(0.5, 0.03 * length)
    idx = rdp(xy, eps)
    # a point every ~4 lengths at most on long straights is not needed; a turn keeps its points
    pts = np.column_stack([xy[idx], np.zeros(len(idx))])
    path = camera_path.Path(pts)
    dense = path.dense
    off = _dist_to_polyline(np.column_stack([xy, np.zeros(len(xy))]), dense)
    # distance along the recorded track
    seg = np.r_[0.0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
    sp = rec[:, 4] / KNOT
    sk = rdp(np.column_stack([seg / max(seg[-1], 1e-9) * 100.0, sp]), 0.3)   # 0.3 kn
    tang = np.unwrap(np.arctan2(*np.gradient(xy, axis=0)[:, ::-1].T))
    crab = np.degrees(np.unwrap(rec[:, 3]) - tang)
    crab = (crab + 180) % 360 - 180
    moving = sp > 0.3
    crab = np.where(moving, crab, 0.0)
    ck = rdp(np.column_stack([seg / max(seg[-1], 1e-9) * 100.0, crab]), 1.5)
    return EditablePath(pts, np.column_stack([seg[sk], sp[sk]]), np.column_stack([seg[ck], crab[ck]]), path,
                        float(off.max()), float(off.mean()))


# ---------------------------------------------------------------------------
# following a drawn path
# ---------------------------------------------------------------------------

def follow(m: Model, pts, knots: float, start_heading: float | None = None, stop_at_end: bool = True,
           max_t: float = 900.0, start_speed: float = 0.0):
    """Drive the vessel along the path through ``pts`` (n x 2 or n x 3) at up to ``knots``: line-of-sight steering
    ``lookahead`` ahead, the speed lowered where the path bends tighter than the vessel turns at that speed (spin
    where it can), and a stop at the end. Returns (recorded samples, notes)."""
    pts = np.asarray(pts, float)
    if pts.shape[1] == 2:
        pts = np.column_stack([pts, np.zeros(len(pts))])
    path = camera_path.Path(pts)
    dense = np.array([path.point(d) for d in np.linspace(0, path.length, 3000)])[:, :2]
    seg = np.r_[0.0, np.cumsum(np.hypot(*np.diff(dense, axis=0).T))]
    total = seg[-1]
    # curvature -> the speed the vessel can take each bend at
    h = np.unwrap(np.arctan2(*np.gradient(dense, axis=0)[:, ::-1].T))
    kappa = np.abs(np.gradient(h) / np.maximum(np.gradient(seg), 1e-6))
    kappa = np.convolve(kappa, np.ones(25) / 25, mode="same")
    u_want = max(knots, 0.1) * KNOT
    u_bend = np.full(len(seg), u_want)
    notes = []
    for i, k in enumerate(kappa):
        R = 1.0 / max(k, 1e-9)
        if R < m.r_min:
            # yaw rate needed u / R must come from the helm (u / r_min) + spin: u <= spin_part * R / (1 - R / r_min)
            if m.spin > 0:
                u_ok = m.spin * 0.6 * R / max(1 - R / m.r_min, 1e-3)
            else:
                u_ok = 0.0
            u_bend[i] = min(u_want, max(u_ok, 0.5 * KNOT))
    # the vessel must slow down before a bend: back-propagate with its braking (a crash stop at a rough rate)
    brake = m.a * m.u_cruise ** 2 * 0.35
    for i in range(len(seg) - 2, -1, -1):
        ds = seg[i + 1] - seg[i]
        u_bend[i] = min(u_bend[i], math.sqrt(u_bend[i + 1] ** 2 + 2 * brake * ds))
    if stop_at_end:
        for i in range(len(seg) - 1, -1, -1):
            u_bend[i] = min(u_bend[i], math.sqrt(2 * brake * 0.5 * (total - seg[i])) + 0.05)
    tight = np.nonzero(1.0 / np.maximum(kappa, 1e-9) < m.r_min)[0]
    if len(tight):
        notes.append(f"{len(tight) / len(seg) * 100:.0f} % of the path bends tighter than R {m.r_min:.0f} m "
                     f"(its turning circle at speed): slowed to {u_bend[tight].min() / KNOT:.1f} kn there"
                     + (" and turned with its thrusters" if m.spin > 0 else " – it cannot follow there"))
    d0 = dense[1] - dense[0]
    s = State(dense[0, 0], dense[0, 1], start_heading if start_heading is not None else math.atan2(d0[1], d0[0]),
              start_speed * KNOT)
    rec = []
    j = 0
    look = max(1.2 * m.length, 15.0)
    every = int(round(1.0 / (REC_HZ * DT)))
    k = 0
    lever = 0.0
    xte = []
    while s.t < max_t:
        # nearest point ahead of the last one
        win = slice(j, min(j + 400, len(dense)))
        dd = np.hypot(dense[win, 0] - s.x, dense[win, 1] - s.y)
        j = j + int(np.argmin(dd))
        xte.append(float(dd.min()))
        if seg[j] > total - max(0.3 * m.length, 5.0):          # at the end: stop, no more steering
            if abs(s.u) < 0.1 and abs(s.r) < 0.01:
                break
            lever = -0.3 if s.u > 0.15 else 0.0
            if k % every == 0:
                rec.append((s.t, s.x, s.y, s.psi, math.hypot(s.u, s.v), lever, 0.0))
            s = step(m, s, lever, 0.0, 0.0, 0.0)
            k += 1
            continue
        tgt_i = int(np.searchsorted(seg, seg[j] + look))
        tgt = dense[min(tgt_i, len(dense) - 1)]
        want = math.atan2(tgt[1] - s.y, tgt[0] - s.x)
        err = (want - s.psi + math.pi) % (2 * math.pi) - math.pi
        r_need = 1.6 * err - 0.0 * s.r
        # helm and spin share the yaw rate the vessel can make now
        helm_rate = abs(s.u) / m.r_min
        helm = max(-1.0, min(1.0, r_need / max(helm_rate, 1e-6))) if helm_rate > 1e-4 else 0.0
        rest = r_need - helm * helm_rate
        spin = max(-1.0, min(1.0, rest / max(m.spin * m._spin_share(s.u), 1e-6))) if m.spin > 0 else 0.0
        u_t = u_bend[j]
        if abs(err) > math.radians(60) and m.spin <= 0:
            u_t = min(u_t, 0.5 * u_want)
        lever = max(-1.0, min(1.0, (u_t / m.u_top) ** 2 * math.copysign(1, u_t) + 0.8 * (u_t - s.u) / m.u_top))
        if k % every == 0:
            rec.append((s.t, s.x, s.y, s.psi, math.hypot(s.u, s.v), lever, helm))
        s = step(m, s, lever, helm, 0.0, spin)
        k += 1
    rec = np.array(rec)
    notes.append(f"followed in {s.t:.0f} s, cross-track off the path: mean {np.mean(xte):.1f} m, "
                 f"max {np.max(xte):.1f} m")
    return rec, notes, dense
