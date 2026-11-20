"""The hang solver (task 0232, Lifting lane L5): where a load comes to rest under the hook, and what each leg carries –
plain Python + NumPy, no Blender.

**The model.** Rigid bodies (the load; a spreader beam or frame above it) and legs of a fixed length (slings, with
their shackles). A leg runs from the hook point – or a point of one body (a spreader's bottom padeye) – to a point of
another body (a lift point). A leg pulls when it is taut and carries nothing when it is slack; it never pushes. Every
body has its mass and its centre of gravity (CoG).

**How it is found.** The bodies come to rest where their weight is as low as the legs let it be (least potential
energy). The legs are taken as very stiff springs that only pull (``STIFF``: under the whole weight a leg stretches
about 0.1 mm – the forces change by about 0.003 % for it), and the energy is minimised by damped Newton steps; each body turns about its own CoG, so its weight
pulls only its CoG down. The start is the load as it stands, moved under the hook until its first leg is taut.
What comes out is the pose of each body (``Hang.poses``: rest -> hanging, 4 x 4, m) and each leg's force (stiffness x
stretch). With one, two or three taut legs to one hook a leg's force follows from statics alone; with four taut legs
it is the share of four equally stiff legs (study 0180 C3: plan with "two legs carry" – ``lifting.multi_leg``).

**Odd CoGs.** At the solution the energy's curvature (its Hessian, eigenvalues) tells whether the pose is stable: a
negative one means the slightest push makes the load roll over (a CoG above its lift points); a further zero one
(besides turning about the vertical through the hook) means it turns freely about a line (a CoG exactly on the line
between two lift points). Both are said in plain words (``Hang.problems`` / ``Hang.notes``), as are slack legs and
legs too short to reach.

Units: m, kg, N, degrees at the interface. Study 0180 section 3 (C2, C3) has the hand cases the tests use.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import lifting

G = lifting.G
STIFF = 1.0e4        # a leg's stiffness per unit of the whole weight, 1/m (stretch under the whole weight: 0.1 mm)
SLACK = 1.0e-9       # m: a leg stretched less than this carries nothing (slack)
TOO_SHORT = 0.01     # m: a leg stretched more than this does not reach its point
TILT_NOTE = 10.0     # degrees: a load tilted more than this gets a note
ROLL_TILT = 90.0     # degrees: a load turned further than this has rolled over
_H = 1.0e-6          # step of the numerical Hessian (well below a taut leg's stretch)
YAW = 1.0e-7         # a hair of stiffness that keeps the load's heading where turning about the vertical is free
FLAT = 1.0e-3        # an eigenvalue of the energy's curvature this close to 0 counts as 0


@dataclass
class Body:
    """A rigid body at rest: its mass (kg) and CoG (world, m). Its points are given with the legs."""
    mass: float
    cog: tuple
    name: str = "load"


@dataclass
class Leg:
    """A leg of fixed ``length`` (m) from ``top`` to ``bottom``. ``top``: None = the hook point, or (body index, point);
    ``bottom``: (body index, point). Points are world coordinates of the body at rest (m)."""
    name: str
    top: tuple | None
    bottom: tuple
    length: float


@dataclass
class LegResult:
    name: str
    top: np.ndarray            # world, hanging (m)
    bottom: np.ndarray
    length: float
    force: float               # N (0 when slack)
    angle: float               # degrees from vertical
    taut: bool
    stretch: float             # m (negative: slack by that much)
    at_hook: bool = True       # the leg's top is the hook point (not a spreader's padeye)


@dataclass
class Hang:
    poses: list                # per body: 4 x 4 rest -> hanging (m)
    legs: list                 # LegResult
    cogs: list                 # per body: CoG hanging (world, m)
    tilts: list                # per body: degrees between its own up and the world's up
    hook: np.ndarray
    weight: float              # N, all bodies
    stable: bool = True
    neutral: bool = False
    rolled: bool = False
    notes: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    iterations: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def taut(self) -> list:
        return [lg for lg in self.legs if lg.taut]

    def leg(self, name: str) -> LegResult:
        return next(lg for lg in self.legs if lg.name == name)


def _skew(v):
    x, y, z = v
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def _rot(r):
    """Rotation matrix of the rotation vector r (Rodrigues)."""
    th = float(np.linalg.norm(r))
    if th < 1e-15:
        return np.eye(3) + _skew(r)
    k = np.asarray(r, float) / th
    K = _skew(k)
    return np.eye(3) + math.sin(th) * K + (1.0 - math.cos(th)) * (K @ K)


class _System:
    """The bodies' poses as (R, c): a rest point p of body b lies at R_b (p - cog_b) + c_b."""

    def __init__(self, bodies, legs, hook):
        self.bodies = list(bodies)
        self.legs = list(legs)
        self.hook = np.asarray(hook, float)
        self.M = sum(float(b.mass) for b in self.bodies)
        if self.M <= 0:
            raise ValueError("The load has no mass: enter its mass first.")
        self.w = [float(b.mass) / self.M for b in self.bodies]
        self.rest = [np.asarray(b.cog, float) for b in self.bodies]
        n = len(self.bodies)
        self.R = [np.eye(3) for _ in range(n)]
        self.c = [c.copy() for c in self.rest]

    def yaw(self, x=None) -> float:
        """The load's turn about the vertical from where it stood (a 2-leg sling leaves it free: task 0232's
        independent tester found the answer turning with the crane's heading)."""
        R = self.R[0] if x is None else _rot(x[3:6]) @ self.R[0]
        return math.atan2(R[1, 0] - R[0, 1], R[0, 0] + R[1, 1])

    def point(self, end, R=None, c=None, x=None):
        if end is None:
            return self.hook
        b, p = end
        if x is not None:
            Rb = _rot(x[6 * b + 3:6 * b + 6]) @ self.R[b]
            cb = self.c[b] + x[6 * b:6 * b + 3]
        else:
            Rb, cb = self.R[b], self.c[b]
        return Rb @ (np.asarray(p, float) - self.rest[b]) + cb

    def energy(self, x):
        e = 0.0
        for b in range(len(self.bodies)):
            e += self.w[b] * (self.c[b][2] + x[6 * b + 2])
        for lg in self.legs:
            d = self.point(lg.top, x=x) - self.point(lg.bottom, x=x)
            s = float(np.linalg.norm(d)) - float(lg.length)
            if s > 0:
                e += 0.5 * STIFF * s * s
        return e + 0.5 * YAW * self.yaw(x) ** 2

    def gradient(self, x):
        """dE/dx (translations, then rotation vectors about each CoG); exact where x's turns are 0."""
        n = len(self.bodies)
        g = np.zeros(6 * n)
        for b in range(n):
            g[6 * b + 2] += self.w[b]
        g[5] += YAW * self.yaw(x)
        for lg in self.legs:
            P, Q = self.point(lg.top, x=x), self.point(lg.bottom, x=x)
            d = P - Q
            L = float(np.linalg.norm(d))
            s = L - float(lg.length)
            if s <= 0 or L < 1e-15:
                continue
            f = STIFF * s * d / L                     # dE/dP; dE/dQ = -f
            for end, sign, X in ((lg.top, 1.0, P), (lg.bottom, -1.0, Q)):
                if end is None:
                    continue
                b = end[0]
                cb = self.c[b] + x[6 * b:6 * b + 3]
                g[6 * b:6 * b + 3] += sign * f
                g[6 * b + 3:6 * b + 6] += np.cross(X - cb, sign * f)
        return g

    def hessian(self, x):
        n = x.size
        H = np.zeros((n, n))
        for i in range(n):
            e = np.zeros(n)
            e[i] = _H
            H[:, i] = (self.gradient(x + e) - self.gradient(x - e)) / (2 * _H)
        return 0.5 * (H + H.T)

    def take(self, x):
        for b in range(len(self.bodies)):
            self.R[b] = _rot(x[6 * b + 3:6 * b + 6]) @ self.R[b]
            self.c[b] = self.c[b] + x[6 * b:6 * b + 3]


def _depth_under(top_points, bottom_points, lengths, shift):
    """How far down a body (moved by ``shift`` in plan) may hang until its first leg is taut: the largest z-shift
    that keeps every leg within its length (None when a leg cannot reach in plan)."""
    best = None
    for T, B, L in zip(top_points, bottom_points, lengths):
        dx = T[0] - (B[0] + shift[0])
        dy = T[1] - (B[1] + shift[1])
        h2 = dx * dx + dy * dy
        if h2 > L * L:
            continue
        z = T[2] - math.sqrt(L * L - h2) - B[2]       # the z-shift that makes this leg just taut (hanging below)
        best = z if best is None else max(best, z)
    return best


def _start(sys: _System) -> None:
    """Each body level, its CoG under what carries it, just low enough that its first leg is taut."""
    order = []
    left = list(range(len(sys.bodies)))
    known = set()
    while left:                                       # bodies hung from the hook first, then those under them
        for b in list(left):
            tops = [lg.top for lg in sys.legs if lg.bottom[0] == b]
            if all(t is None or t[0] in known for t in tops):
                order.append(b)
                known.add(b)
                left.remove(b)
                break
        else:
            order += left
            break
    for b in order:
        legs = [lg for lg in sys.legs if lg.bottom[0] == b]
        tops = [sys.point(lg.top) for lg in legs]
        if not tops:
            continue
        over = np.mean([t for t in tops], axis=0)
        if any(lg.top is None for lg in legs):
            over = sys.hook
        shift = np.array([over[0] - sys.rest[b][0], over[1] - sys.rest[b][1], 0.0])
        bots = [np.asarray(lg.bottom[1], float) for lg in legs]
        z = _depth_under(tops, bots, [lg.length for lg in legs], shift)
        if z is None:                                 # no leg reaches: start with the lowest top a leg length below
            z = min(t[2] for t in tops) - max(lg.length for lg in legs) - min(p[2] for p in bots)
        shift[2] = z
        sys.c[b] = sys.rest[b] + shift


def solve(bodies, legs, hook=(0.0, 0.0, 0.0), max_iter: int = 400) -> Hang:
    """Hang the bodies from the hook point (world, m). Raises ValueError for input that cannot hang (no mass, a leg
    of no length, a body nothing holds)."""
    bodies = list(bodies)
    legs = list(legs)
    if not bodies:
        raise ValueError("Nothing to hang.")
    if not legs:
        raise ValueError("No legs: pick lift points and a sling set first.")
    for lg in legs:
        if not (float(lg.length) > 0 and math.isfinite(float(lg.length))):
            raise ValueError(f"Leg {lg.name}: its length must be above 0.")
    held = {lg.bottom[0] for lg in legs}
    for b in range(len(bodies)):
        if b not in held:
            raise ValueError(f"Nothing holds the {bodies[b].name}.")
    o = np.asarray(hook, float)                       # worked out round the hook (small numbers: less rounding)
    sh = lambda end: None if end is None else (end[0], np.asarray(end[1], float) - o)   # noqa: E731
    sys = _System([Body(b.mass, tuple(np.asarray(b.cog, float) - o), b.name) for b in bodies],
                  [Leg(lg.name, sh(lg.top), sh(lg.bottom), lg.length) for lg in legs], np.zeros(3))
    _start(sys)
    n = 6 * len(bodies)
    mu = 1e-9
    it = 0
    scale = STIFF
    for it in range(1, max_iter + 1):
        x0 = np.zeros(n)
        g = sys.gradient(x0)
        if float(np.max(np.abs(g))) < 1e-10:
            break
        H = sys.hessian(x0)
        e0 = sys.energy(x0)
        step = None
        for _ in range(40):
            try:
                d = np.linalg.solve(H + mu * scale * np.eye(n), -g)
            except np.linalg.LinAlgError:
                mu *= 10.0
                continue
            # keep a step physical: at most 0.5 m and 0.3 rad at once
            sc = 1.0
            for b in range(len(bodies)):
                sc = min(sc, 0.5 / max(1e-30, float(np.linalg.norm(d[6 * b:6 * b + 3]))),
                         0.3 / max(1e-30, float(np.linalg.norm(d[6 * b + 3:6 * b + 6]))))
            d = d * sc
            e1 = sys.energy(d)
            if e1 <= e0 - 1e-4 * abs(float(g @ d)) or e1 <= e0 - 1e-15 * max(1.0, abs(e0)):
                step = d
                break
            mu *= 8.0
        if step is None:
            break
        sys.take(step)
        mu = max(mu / 4.0, 1e-12)
        if float(np.max(np.abs(step))) < 1e-13:
            break
    return _result(sys, it, o)


def _result(sys: _System, iterations: int, o) -> Hang:
    W = sys.M * G
    poses = []
    for b in range(len(sys.bodies)):
        M = np.eye(4)
        M[:3, :3] = sys.R[b]
        M[:3, 3] = sys.c[b] - sys.R[b] @ sys.rest[b] + o - sys.R[b] @ o
        poses.append(M)
    legs = []
    problems, notes = [], []
    for lg in sys.legs:
        P, Q = sys.point(lg.top), sys.point(lg.bottom)
        d = P - Q
        L = float(np.linalg.norm(d))
        s = L - float(lg.length)
        taut = s > SLACK
        force = STIFF * s * W if taut else 0.0
        angle = math.degrees(math.atan2(math.hypot(d[0], d[1]), d[2])) if L > 0 else 0.0
        legs.append(LegResult(lg.name, P + o, Q + o, float(lg.length), force, angle, bool(taut), s, lg.top is None))
        if s > TOO_SHORT:
            problems.append(f"Leg {lg.name} is too short to reach its point ({s * 1000:.0f} mm short): choose longer "
                            "slings.")
    tilts = []
    for b in range(len(sys.bodies)):
        up = sys.R[b] @ np.array([0.0, 0.0, 1.0])
        tilts.append(math.degrees(math.acos(max(-1.0, min(1.0, float(up[2]))))))
    h = Hang(poses=poses, legs=legs, cogs=[c + o for c in sys.c], tilts=tilts, hook=sys.hook + o, weight=W,
             iterations=iterations)
    # stability: the curvature of the energy at the answer
    x0 = np.zeros(6 * len(sys.bodies))
    H = sys.hessian(x0)
    lam = np.linalg.eigvalsh(H)
    neg = int(np.sum(lam < -FLAT))
    zero = int(np.sum(np.abs(lam) <= FLAT))
    slack = [lg.name for lg in legs if not lg.taut]
    if slack:
        notes.append(f"Leg {slack[0]} is slack: it carries nothing." if len(slack) == 1 else
                     "Legs " + ", ".join(slack) + " are slack: they carry nothing.")
    if tilts[0] > ROLL_TILT:
        h.rolled = True
        problems.append(f"The load would roll over ({tilts[0]:.0f}°): its CoG lies above its lift points. Lift it at "
                        "points above its CoG, or with a spreader frame.")
    elif neg:
        h.stable = False
        problems.append("The load would roll over: its CoG lies above its lift points, so the slightest push turns it "
                        "over. Lift it at points above its CoG, or with a spreader frame.")
    elif zero > 1:
        h.neutral = True
        notes.append("The load turns freely about the line between its lift points (its CoG lies on that line): "
                     "steady it with tag lines.")
    if not h.rolled and tilts[0] > TILT_NOTE:
        notes.append(f"The load hangs tilted by {tilts[0]:.1f}°: its CoG is not under the middle of its lift points.")
    h.problems, h.notes = problems, notes
    return h


# ---------------------------------------------------------------------------------------------------------------------
# the usual set-ups

def single(mass: float, cog, points, lengths, hook, names=None) -> Hang:
    """One load on 1–4 legs (or more) that all meet at the hook. ``points``: the lift points (world at rest)."""
    points = [np.asarray(p, float) for p in points]
    lengths = list(lengths) if np.ndim(lengths) else [float(lengths)] * len(points)
    names = list(names) if names else [chr(ord("A") + i) for i in range(len(points))]
    legs = [Leg(names[i], None, (0, points[i]), float(lengths[i])) for i in range(len(points))]
    return solve([Body(float(mass), tuple(cog), "load")], legs, hook)


def with_spreader(mass: float, cog, points, bottom_lengths, sp_mass: float, sp_cog, sp_top, sp_bottom, top_lengths,
                  hook, names=None, top_names=None) -> Hang:
    """A load under a spreader beam or frame: legs from the hook to the spreader's top padeyes (``sp_top``, lengths
    ``top_lengths``), and from its bottom padeye k (``sp_bottom[k]``) to lift point k. Spreader points are world
    coordinates of the spreader at rest; it may be anywhere above the load (the start moves it under the hook)."""
    points = [np.asarray(p, float) for p in points]
    if len(sp_bottom) != len(points):
        raise ValueError(f"The spreader has {len(sp_bottom)} bottom padeyes for {len(points)} lift points: they must "
                         "be as many.")
    blen = list(bottom_lengths) if np.ndim(bottom_lengths) else [float(bottom_lengths)] * len(points)
    tlen = list(top_lengths) if np.ndim(top_lengths) else [float(top_lengths)] * len(sp_top)
    names = list(names) if names else [chr(ord("A") + i) for i in range(len(points))]
    top_names = list(top_names) if top_names else [f"top {i + 1}" for i in range(len(sp_top))]
    legs = [Leg(top_names[i], None, (1, np.asarray(sp_top[i], float)), float(tlen[i])) for i in range(len(sp_top))]
    legs += [Leg(names[k], (1, np.asarray(sp_bottom[k], float)), (0, points[k]), float(blen[k]))
             for k in range(len(points))]
    return solve([Body(float(mass), tuple(cog), "load"), Body(float(sp_mass), tuple(sp_cog), "spreader")], legs, hook)


# ---------------------------------------------------------------------------------------------------------------------
# the checks C2–C4 on a hang

def checks(h: Hang, mass: float, leg_wll: float | None = None, shackle_wll: float | None = None,
           mode: str = "rigid", spreader_wll: float | None = None, spreader_mass: float = 0.0,
           limits: lifting.Limits = lifting.DEFAULT_LIMITS) -> list:
    """The checks of study 0180 on the solved geometry (``lifting.two_leg`` / ``multi_leg`` / ``wll_use``): the legs
    that meet at the hook (C4 for one, C2 for two, C3 for three or four), with a spreader its WLL (C4) and each of its
    bottom legs (C4), and the shackles at the lift points (C4 with the force their leg is planned for). ``mass``: the
    load's mass in kg (with contingency); the spreader's own mass is added for the legs above it."""
    out = []
    hook_legs = [lg for lg in h.legs if lg.at_hook]
    spread = len(h.poses) > 1
    above = mass + (spreader_mass if spread else 0.0)
    n = len(hook_legs)
    if n == 1:
        lg = hook_legs[0]
        out.append(lifting.wll_use(lg.force, leg_wll, item=f"sling leg {lg.name}", angle=lg.angle, limits=limits))
    elif n == 2:
        out.append(lifting.two_leg(above, hook_legs[0].bottom, hook_legs[1].bottom, h.hook, leg_wll=leg_wll,
                                   limits=limits))
    elif n in (3, 4):
        out.append(lifting.multi_leg(above, [lg.bottom for lg in hook_legs], h.hook, leg_wll=leg_wll, mode=mode,
                                     limits=limits))
    if spread:
        out.append(lifting.wll_use(mass * G, spreader_wll, item="spreader", limits=limits))
        for lg in h.legs:
            if not lg.at_hook:
                out.append(lifting.wll_use(lg.force, leg_wll, item=f"sling leg {lg.name}", angle=lg.angle,
                                           limits=limits))
    if shackle_wll is not None:
        for lg in h.legs:
            if spread and lg.at_hook:
                continue
            out.append(lifting.wll_use(design_force(h, lg, mass, mode), shackle_wll, item=f"shackle {lg.name}",
                                       limits=limits))
    return out


def design_force(h: Hang, lg: LegResult, mass: float, mode: str = "rigid") -> float:
    """The force a leg (and its shackle) is planned for: its own force; on a 3- or 4-leg set to the hook the C3
    rule's (``rigid``: two legs carry, T = (W/2)·L/h; ``equalised``: W/n·L/h; ``dnv``: x 1.25)."""
    hook_legs = [x for x in h.legs if x.at_hook]
    if lg.at_hook and len(hook_legs) in (3, 4) and len(h.poses) == 1:
        dz = float(h.hook[2] - lg.bottom[2])
        L = float(np.linalg.norm(h.hook - lg.bottom))
        if dz > 0:
            if mode == "rigid":
                return mass * G / 2.0 * L / dz
            share = mass * G / len(hook_legs) * L / dz
            return share * (lifting.SKEW_FACTOR_DNV if mode == "dnv" else 1.0)
    return lg.force
