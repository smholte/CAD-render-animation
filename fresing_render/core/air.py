"""Air blast: air that blows the chips away (task 0039). No Blender here.

How it works
------------
* **When**: the G-code step knows from the program when air blows (``gcode.Schedule.air_spans``: from the
  air-on code, M7 by default, to the air-off code, M9, or always while the spindle turns) and adds a final
  "Blow the part clean" span. Here they are frames: ``AirIn.spans`` = [(start, end, clean?)].
* **Where from**: a nozzle path in riding space (see ``core/chips.py``): through the spindle it is the bit's
  tip blowing down along the bit, an external nozzle is a part of the model (its tip and direction read per
  frame, so it moves with the head or stands with the frame).
* **The air**: a jet that spreads in a cone. Its speed falls off with the distance from the nozzle (about
  1 / distance, as a free jet does) and from the cone's middle, and ends at ``reach``. Where the jet meets a
  surface (found along its line in the height field of the chips) it fans out along that surface: a *wall
  jet* that blows outwards from the spot it hits, slowing down as about 1 / distance, strongest close to
  the surface. The wall jet is what clears a part: through the spindle the air hits the floor of the cut
  right under the tip and blows the chips away round the tool.
* **What it does to chips** (in ``core/chips.py``): a flying chip is pulled towards the air's speed (light
  chips and dust more than heavy ones), a chip lying in the jet is picked up again and blown away, and a chip
  that lands where the air is strong keeps sliding instead of coming to rest. No random numbers: the same
  set-up gives the same chips every time.
Units: metres, seconds; time in frames.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

MM = 0.001
REF = 20 * MM                    # the nozzle's speed holds up to this distance, then falls off as 1 / distance
CORE = 2 * MM                    # the jet's radius at the nozzle
FAN = 1.2                        # how much a jet fans out sideways (where it meets a surface)
LIFT = 0.25                      # a little upwards: air under a chip lifts it
COUPLE = 1.5                     # 1/s per unit of the chip's drag: how fast a chip takes the air's speed
WAKE = 2.0                       # m/s of air (for a chip of drag 2.5) that picks a lying chip up again
WALL_WIDTH = 20 * MM             # the wall jet keeps its speed this far beyond the jet's own width
WALL_HEIGHT = 15 * MM            # … and is this thick over the surface
HIT_STEPS = 48                   # points along the jet's line to find where it meets a surface
CLEAN_BOOST = 2.0                # "Blow the part clean": the operator opens the valve all the way
CLEAN_CONE = math.radians(30)    # … and the jet is at least this wide (half angle)

STRENGTHS = {"SOFT": 8.0, "NORMAL": 18.0, "STRONG": 35.0}     # m/s at REF from the nozzle

@dataclass
class AirIn:
    """Air for the chips: when it blows and from where (riding space)."""
    spans: np.ndarray            # (k, 3): start frame, end frame, 1 = "Blow the part clean"
    t: np.ndarray                # frames of the nozzle samples
    o: np.ndarray                # (n, 3) nozzle tip, riding space
    d: np.ndarray                # (n, 3) the way it blows (unit), riding space
    speed: float = STRENGTHS["NORMAL"]
    cone: float = math.radians(15)    # half angle
    reach: float = 0.25

    def __post_init__(self):
        self.spans = np.asarray(self.spans, float).reshape(-1, 3)
        self.t = np.asarray(self.t, float).reshape(-1)
        self.o = np.asarray(self.o, float).reshape(-1, 3)
        self.d = np.asarray(self.d, float).reshape(-1, 3)
        if len(self.spans):
            self.spans = self.spans[np.argsort(self.spans[:, 0], kind="stable")]

    def state(self, T: float) -> tuple:
        """(on, clean) at frame ``T``."""
        if not len(self.spans) or not len(self.t):
            return False, False
        m = (self.spans[:, 0] <= T + 1e-9) & (T < self.spans[:, 1] - 1e-9)
        if not m.any():
            return False, False
        return True, bool((self.spans[m, 2] > 0.5).any())

    def next_on(self, T: float) -> float:
        """The first frame at or after ``T`` with air on (inf: never again)."""
        if not len(self.t):
            return math.inf
        later = self.spans[self.spans[:, 1] > T + 1e-9]
        if not len(later):
            return math.inf
        return max(T, float(later[:, 0].min()))

    def nozzle(self, T: float) -> tuple:
        """(tip, direction) at frame ``T`` (riding space)."""
        o = np.array([np.interp(T, self.t, self.o[:, k]) for k in range(3)])
        d = np.array([np.interp(T, self.t, self.d[:, k]) for k in range(3)])
        n = float(np.linalg.norm(d))
        return o, (d / n if n > 1e-12 else np.array([0.0, 0.0, -1.0]))

    def settings(self, clean: bool) -> tuple:
        """(speed, cone) as they are now."""
        if clean:
            return self.speed * CLEAN_BOOST, max(self.cone, CLEAN_CONE)
        return self.speed, self.cone

    def seconds_on(self, fps: float) -> float:
        return float(np.maximum(self.spans[:, 1] - self.spans[:, 0], 0).sum() / fps) if len(self.spans) else 0.0


def hit(o: np.ndarray, d: np.ndarray, reach: float, surface) -> tuple | None:
    """(point, distance) where the jet's line first meets ``surface(x, y) -> z`` within ``reach``; None if not."""
    s = np.linspace(0.0, reach, HIT_STEPS)
    pts = o[None, :] + s[:, None] * d[None, :]
    z = surface(pts[:, 0], pts[:, 1])
    below = np.nonzero(pts[:, 2] <= z)[0]
    if not len(below):
        return None
    k = int(below[0])
    if k == 0:
        return o.copy(), 0.0
    # between the last point above and the first below: where the line crosses the surface
    a, b = pts[k - 1, 2] - z[k - 1], pts[k, 2] - z[k]
    f = a / (a - b) if np.isfinite(a) and np.isfinite(b) and a != b else 1.0
    sh = float(s[k - 1] + (s[k] - s[k - 1]) * min(max(f, 0.0), 1.0))
    p = o + sh * d
    if np.isfinite(z[k]):
        p[2] = max(p[2], float(z[k]) if f >= 1.0 else p[2])
    return p, sh


def wall_velocity(P: np.ndarray, h: np.ndarray, s_hit: float, d: np.ndarray, speed: float, cone: float,
                  reach: float, fallback: np.ndarray | None = None) -> np.ndarray:
    """The wall jet: air blowing outwards along the surface from the spot ``h`` the jet hits."""
    P = np.asarray(P, float).reshape(-1, 3)
    out = np.zeros((len(P), 3))
    if not len(P):
        return out
    hit_speed = speed * min(1.0, REF / max(s_hit, 1e-4)) * max(0.0, 1.0 - (s_hit / reach) ** 4)
    if hit_speed <= 0:
        return out
    r = P - h
    rh = r.copy()
    rh[:, 2] = 0.0
    rho = np.linalg.norm(rh, axis=1)
    w0 = CORE + s_hit * math.tan(min(max(cone, math.radians(1)), math.radians(80))) + WALL_WIDTH
    mag = hit_speed * np.minimum(1.0, w0 / np.maximum(rho, 1e-4))
    mag *= np.clip(1.0 - (rho / max(reach, 1e-3)) ** 4, 0.0, 1.0)
    mag *= np.exp(-(r[:, 2] / WALL_HEIGHT) ** 2)
    if fallback is not None:
        a = np.asarray(fallback, float).reshape(-1)
        fb = np.stack([np.cos(a), np.sin(a), np.zeros_like(a)], axis=1)
    else:
        fb = np.tile([1.0, 0.0, 0.0], (len(P), 1))
    way = np.where((rho > 1e-6)[:, None], rh / np.maximum(rho, 1e-12)[:, None], fb)
    dh = np.array([d[0], d[1], 0.0])
    way = way + 1.5 * dh[None, :] + np.array([0.0, 0.0, LIFT])
    way /= np.maximum(np.linalg.norm(way, axis=1, keepdims=True), 1e-12)
    return way * mag[:, None]


def velocity(P: np.ndarray, o: np.ndarray, d: np.ndarray, speed: float, cone: float, reach: float,
             fallback: np.ndarray | None = None, wall=None) -> np.ndarray:
    """The air's speed (m/s, vectors) at points ``P`` for a jet from ``o`` blowing along ``d``.
    ``fallback``: per point, an angle for the way out where a point lies right on the jet's line.
    ``wall``: (spot, distance) where the jet meets a surface (``hit``): adds the wall jet, and the free jet
    ends there."""
    P = np.asarray(P, float).reshape(-1, 3)
    n = len(P)
    out = np.zeros((n, 3))
    if n == 0 or speed <= 0 or reach <= 0:
        return out
    if wall is not None:
        out += wall_velocity(P, wall[0], wall[1], d, speed, cone, reach, fallback)
    r = P - o
    s = r @ d
    end = min(reach, wall[1] + CORE) if wall is not None else reach
    ok = (s > -CORE) & (s < end)
    if not ok.any():
        return out
    idx = np.nonzero(ok)[0]
    s = np.maximum(s[idx], 0.0)
    perp = r[idx] - s[:, None] * d
    rho = np.linalg.norm(perp, axis=1)
    width = CORE + s * math.tan(min(max(cone, math.radians(1)), math.radians(80)))
    across = np.exp(-(rho / width) ** 2)
    along = np.minimum(1.0, REF / np.maximum(s, 1e-4)) * np.clip(1.0 - (s / reach) ** 4, 0.0, 1.0)
    mag = speed * across * along
    # the way out: away from the jet's line, along the floor (horizontal)
    out_h = perp.copy()
    out_h[:, 2] = 0.0
    ln = np.linalg.norm(out_h, axis=1)
    if fallback is not None:
        a = np.asarray(fallback, float).reshape(-1)[idx]
        fb = np.stack([np.cos(a), np.sin(a), np.zeros_like(a)], axis=1)
    else:
        fb = np.tile([1.0, 0.0, 0.0], (len(idx), 1))
    out_h = np.where((ln > 1e-6)[:, None], out_h / np.maximum(ln, 1e-12)[:, None], fb)
    # a jet that leans over blows mostly its own way; one straight down fans out all round
    dh = np.array([d[0], d[1], 0.0])
    fan = FAN * (1.0 - min(1.0, float(np.linalg.norm(dh))))
    w = d[None, :] + fan * out_h + np.array([0.0, 0.0, LIFT])
    w /= np.maximum(np.linalg.norm(w, axis=1, keepdims=True), 1e-12)
    out[idx] += w * mag[:, None]
    return out


def nozzle_from_poses(world_o, world_d, carry) -> tuple:
    """Nozzle tip and direction per frame from world space into riding space (``carry``: riding -> world per
    frame, as for the chips; None = the same)."""
    o = np.asarray(world_o, float).reshape(-1, 3)
    d = np.asarray(world_d, float).reshape(-1, 3)
    if carry is None:
        return o.copy(), d.copy()
    n = min(len(o), len(carry))
    inv = np.linalg.inv(np.asarray(carry[:n], float))
    ro = np.einsum("fij,fj->fi", inv[:, :3, :3], o[:n]) + inv[:, :3, 3]
    rd = np.einsum("fij,fj->fi", inv[:, :3, :3], d[:n])
    rd /= np.maximum(np.linalg.norm(rd, axis=1, keepdims=True), 1e-12)
    return ro, rd


def spans_text(spans, fps: float) -> str:
    """'air on 3 times, 12.4 s in all' for the panel."""
    sp = np.asarray(spans, float).reshape(-1, 3)
    if not len(sp):
        return "no air"
    prog = sp[sp[:, 2] < 0.5]
    clean = sp[sp[:, 2] >= 0.5]
    parts = []
    if len(prog):
        n = len(prog)
        parts.append(f"on {n} time{'s' if n != 1 else ''}, {float((prog[:, 1] - prog[:, 0]).sum()) / fps:.1f} s in all")
    if len(clean):
        parts.append(f"blows the part clean for {float((clean[:, 1] - clean[:, 0]).sum()) / fps:.1f} s at the end")
    return "; ".join(parts)
