"""Planar linkages: scissor lifts, four-bar and parallel arms, slider-cranks, toggles (task 0014). No Blender.

A mechanism is a number of rigid *links* in one plane (every pin axis parallel). Link 0 is the base: it
does not move (the whole mechanism moves with whatever moves the base). The links are held together by

    Pin(a, b, p)        links a and b share the point p and turn about it
    Slot(link, guide, p, d)
                        the point p of ``link`` runs along the line (p, d) fixed on ``guide`` (a roller in a
                        track, a pin in a slotted hole); ``link`` may turn
    Slide(link, guide, p, d)
                        ``link`` slides along d on ``guide`` without turning (a slider block, a piston)

One of the pins or slides between the base and a link is the *input*: its value (an angle in radians,
counter-clockwise about the plane's normal, or a distance in metres along d; 0 = CAD position) places that
link, and everything else follows.

Positions are 2D points in the mechanism's plane, in metres, as they are in the CAD model. A link's place is
its *pose* (theta, tx, ty): a CAD point p of the link is now at R(theta) p + t. In the CAD pose every pose
is (0, 0, 0).

How it is solved
----------------
Exactly, in steps (``plan``): starting from the base and the input link, a link with two connections to
links already placed is placed by a formula – two pins: straight away; a pin and a track: a circle meets a
line; a pin and a slotted link: the line through a point – and two links joined by a pin, each with one
connection to placed links, by the triangle of the three pins (two circles meet: the four-bar's coupler and
rocker, a scissor stage). A slider-crank is a circle meeting a line, a scissor lift a chain of such steps.
What cannot be split up like that is solved together by Newton's method (``_newton``), starting from the
last solution.

A formula with two answers (a circle meets a line or another circle twice) is an *assembly mode*: the
mechanism never jumps to the other one. The input moves in small steps (``walk``); each step takes the answer
that continues the motion (nearest to where the last two steps were heading; with no history, the one on the
same side as before – in the CAD pose: the CAD model's side). That also carries a parallelogram through the
position where its four pins are in line, where the "same side" rule would cross it over.

A position the mechanism cannot reach (a link too short, a roller off the end of its track's line, the
Newton solve not closing) raises ``Unreachable`` with a reason; the solver keeps its last good position.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

ROT_STEP = math.radians(1.0)      # largest input step for a turning input (branch tracking)
SLIDE_STEP_SHARE = 0.01           # largest input step for a sliding input, share of the mechanism's size
FULL_TURN = 2.0 * math.pi


class Unreachable(Exception):
    """The mechanism cannot be put together at that input value."""


class SetupError(ValueError):
    """The links and pins do not make a mechanism that moves with one input."""


# ---------------------------------------------------------------------------
# small 2D helpers
# ---------------------------------------------------------------------------

def _rot(t: float, p) -> tuple[float, float]:
    c, s = math.cos(t), math.sin(t)
    return (c * p[0] - s * p[1], s * p[0] + c * p[1])


def place(pose, p) -> tuple[float, float]:
    """Where the CAD point ``p`` of a link with ``pose`` is now."""
    x, y = _rot(pose[0], p)
    return (x + pose[1], y + pose[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _mul(a, k: float):
    return (a[0] * k, a[1] * k)


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _len(a) -> float:
    return math.hypot(a[0], a[1])


def _unit(a):
    n = _len(a)
    if n < 1e-15:
        raise SetupError("A direction of length 0")
    return (a[0] / n, a[1] / n)


def _angle(a) -> float:
    return math.atan2(a[1], a[0])


def _pose_from_points(x1, q1, x2, q2):
    """The pose that puts the CAD points x1, x2 at q1, q2 (rigid: the angle of the line between them)."""
    t = _angle(_sub(q2, q1)) - _angle(_sub(x2, x1))
    r = _rot(t, x1)
    return (t, q1[0] - r[0], q1[1] - r[1])


def _pose_from_point(theta: float, x, q):
    r = _rot(theta, x)
    return (theta, q[0] - r[0], q[1] - r[1])


IDENTITY = (0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# the mechanism
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Pin:
    a: int
    b: int
    p: tuple


@dataclass(frozen=True)
class Slot:
    link: int
    guide: int
    p: tuple
    d: tuple


@dataclass(frozen=True)
class Slide:
    link: int
    guide: int
    p: tuple
    d: tuple


@dataclass(frozen=True)
class Distance:
    """Distance between point a of link i and point b of link j (a cylinder's pins)."""
    i: int
    a: tuple
    j: int
    b: tuple

    def of(self, poses) -> float:
        return _len(_sub(place(poses[self.i], self.a), place(poses[self.j], self.b)))


@dataclass(frozen=True)
class Height:
    """Height of point a of link i above the base point ``ref``, measured along ``up`` (a scissor's platform)."""
    i: int
    a: tuple
    ref: tuple
    up: tuple

    def of(self, poses) -> float:
        return _dot(_sub(place(poses[self.i], self.a), self.ref), self.up)


class Linkage:
    """Links, the constraints between them and the input (``("pin", index)`` or ``("slide", index)``)."""

    def __init__(self, names, pins=(), slots=(), slides=(), input=("pin", 0)):
        self.names = list(names)
        self.pins = [Pin(int(p.a), int(p.b), tuple(map(float, p.p))) for p in pins]
        self.slots = [Slot(int(s.link), int(s.guide), tuple(map(float, s.p)), _unit(s.d)) for s in slots]
        self.slides = [Slide(int(s.link), int(s.guide), tuple(map(float, s.p)), _unit(s.d)) for s in slides]
        self.input = (str(input[0]), int(input[1]))
        n = len(self.names)
        if n < 2:
            raise SetupError("A mechanism needs at least one moving link")
        for c in self.pins:
            if not (0 <= c.a < n and 0 <= c.b < n) or c.a == c.b:
                raise SetupError("A pin must join two different links")
        for c in self.slots + self.slides:
            if not (0 <= c.link < n and 0 <= c.guide < n) or c.link == c.guide:
                raise SetupError("A track must join two different links")
        kind, k = self.input
        pool = self.pins if kind == "pin" else self.slides if kind == "slide" else None
        if pool is None or not 0 <= k < len(pool):
            raise SetupError("The input must be one of the pins or slides")
        c = pool[k]
        ends = (c.a, c.b) if kind == "pin" else (c.link, c.guide)
        if 0 not in ends:
            raise SetupError("The input must sit on the base: the link it moves turns or slides on the base")
        self.input_link = ends[1] if ends[0] == 0 else ends[0]
        # a pin's value turns the link about the pin; the sign is the same whichever side the base is on
        pts = [c.p for c in self.pins] + [s.p for s in self.slots + self.slides]
        span = max((_len(_sub(a, b)) for a in pts for b in pts), default=0.0)
        self.size = max(span, 1e-3)
        self.check_dof()

    # -- counting ---------------------------------------------------------------
    def equations(self) -> int:
        n = 2 * len(self.pins) + len(self.slots) + 2 * len(self.slides)
        return n - 2       # the input's own pin or slide places the input link with the value

    def check_dof(self) -> None:
        unknown = 3 * (len(self.names) - 2)
        eq = self.equations()
        # links nothing reaches
        reach = {0, self.input_link}
        changed = True
        while changed:
            changed = False
            for c in self.pins:
                if (c.a in reach) != (c.b in reach):
                    reach |= {c.a, c.b}
                    changed = True
            for c in self.slots + self.slides:
                if (c.link in reach) != (c.guide in reach):
                    reach |= {c.link, c.guide}
                    changed = True
        loose = [self.names[i] for i in range(len(self.names)) if i not in reach]
        if loose:
            raise SetupError(f"Not connected to the rest: {', '.join(loose)}")
        if eq < unknown:
            raise SetupError("Not enough pins or tracks: part of the mechanism could still move by itself "
                             f"({unknown - eq} free motion{'s' if unknown - eq != 1 else ''} besides the input)")

    def input_pose(self, value: float):
        kind, k = self.input
        if kind == "pin":
            p = self.pins[k].p
            return _pose_from_point(value, p, p)
        d = self.slides[k].d
        return (0.0, d[0] * value, d[1] * value)

    def is_turning(self) -> bool:
        return self.input[0] == "pin"


# ---------------------------------------------------------------------------
# the plan: which formula places which link, in which order
# ---------------------------------------------------------------------------

@dataclass
class Step:
    kind: str                 # "pp" "rp" "rl" "pl" "pt" (one link) · "dyad_pp" "dyad_pl" "dyad_ll" (two)
    links: tuple
    data: tuple
    cad_marker: tuple | None = None    # for steps with two answers: the CAD answer's marker point


def _items(lk: Linkage, known: set, L: int) -> list:
    """What ties the unknown link L to placed links: ("at", xL, K, xK), ("online", xL, K, o, d),
    ("through", o, d, K, xK) (L's line through K's point), ("rot", K)."""
    out = []
    for c in lk.pins:
        if c.a == L and c.b in known:
            out.append(("at", c.p, c.b, c.p, c))
        elif c.b == L and c.a in known:
            out.append(("at", c.p, c.a, c.p, c))
    for c in lk.slots:
        if c.link == L and c.guide in known:
            out.append(("online", c.p, c.guide, c.p, c.d, c))
        elif c.guide == L and c.link in known:
            out.append(("through", c.p, c.d, c.link, c.p, c))
    for c in lk.slides:
        if c.link == L and c.guide in known:
            out.append(("rot", c.guide, c))
            out.append(("online", c.p, c.guide, c.p, c.d, c))
        elif c.guide == L and c.link in known:
            out.append(("rot", c.link, c))
            out.append(("through", c.p, c.d, c.link, c.p, c))
    return out


def _single(lk: Linkage, items: list, tol: float):
    """A formula placing one link from its ties to placed links, or None. Returns (kind, data, used)."""
    ats = [i for i in items if i[0] == "at"]
    rots = [i for i in items if i[0] == "rot"]
    lines = [i for i in items if i[0] in ("online", "through")]
    for a in ats:                                  # two pins at two different points
        for b in ats:
            if a is not b and _len(_sub(a[1], b[1])) > tol:
                return "pp", (a, b), [a[-1], b[-1]]
    if rots and ats:
        return "rp", (rots[0], ats[0]), [rots[0][-1], ats[0][-1]]
    if rots and len(lines) >= 2:
        for a in lines:
            for b in lines:
                if a is b:
                    continue
                da = a[4] if a[0] == "online" else a[2]
                db = b[4] if b[0] == "online" else b[2]
                if abs(_cross(da, db)) > 1e-6:
                    return "rl", (rots[0], a, b), [rots[0][-1], a[-1], b[-1]]
    for a in ats:
        for b in lines:
            if b[0] == "online" and _len(_sub(a[1], b[1])) > tol:
                return "pl", (a, b), [a[-1], b[-1]]
            if b[0] == "through":
                # the slotted link turns about the pin; its line must miss the pin itself... or not: a line
                # through the pin gives the line's direction straight away
                return "pt", (a, b), [a[-1], b[-1]]
    return None


def _dyad(lk: Linkage, known: set, used: set, tol: float):
    """Two unknown links joined by a pin, each tied to placed links by a pin or by a slide. Or None."""
    for c in lk.pins:
        L1, L2 = c.a, c.b
        if L1 in known or L2 in known or id(c) in used:
            continue
        sides = []
        for L in (L1, L2):
            it = [i for i in _items(lk, known, L) if id(i[-1]) not in used]
            ats = [i for i in it if i[0] == "at" and _len(_sub(i[1], c.p)) > tol]
            rot = [i for i in it if i[0] == "rot"]
            online = [i for i in it if i[0] == "online" and rot and i[-1] is rot[0][-1]]
            if ats:
                sides.append(("at", ats[0]))
            elif rot and online:
                sides.append(("slide", rot[0], online[0]))
            else:
                sides.append(None)
        if sides[0] is None or sides[1] is None:
            continue
        k0, k1 = sides[0][0], sides[1][0]
        if k0 == "at" and k1 == "at":
            kind = "dyad_pp"
        elif k0 == "slide" and k1 == "slide":
            kind = "dyad_ll"
        else:
            kind = "dyad_pl"
            if k0 == "slide":                       # the pinned side first
                L1, L2 = L2, L1
                sides = [sides[1], sides[0]]
        used = [c] + [x[-1] for s in sides for x in s[1:]]
        return kind, (L1, L2), (c, sides[0], sides[1]), used
    return None


def plan(lk: Linkage):
    """(steps, newton links, leftover constraints) – see the module text."""
    tol = 1e-9 * lk.size + 1e-12
    known = {0, lk.input_link}
    kind, k = lk.input
    used = {id(lk.pins[k] if kind == "pin" else lk.slides[k])}
    steps: list[Step] = []
    n = len(lk.names)
    while True:
        unknown = [L for L in range(n) if L not in known]
        if not unknown:
            break
        found = False
        for L in unknown:
            items = [i for i in _items(lk, known, L) if id(i[-1]) not in used]
            r = _single(lk, items, tol)
            if r is not None:
                skind, data, u = r
                steps.append(Step(skind, (L,), data))
                used |= {id(x) for x in u}
                known.add(L)
                found = True
                break
        if found:
            continue
        r = _dyad(lk, known, used, tol)
        if r is not None:
            dkind, links, data, u = r
            steps.append(Step(dkind, links, data))
            used |= {id(x) for x in u}
            known |= set(links)
            continue
        break
    newton = [L for L in range(n) if L not in known]
    leftover = [c for c in lk.pins + lk.slots + lk.slides if id(c) not in used]
    if newton:
        leftover = [c for c in leftover if not _touches(c, newton)]
    return steps, newton, leftover


def _touches(c, links) -> bool:
    ends = (c.a, c.b) if isinstance(c, Pin) else (c.link, c.guide)
    return any(e in links for e in ends)


# ---------------------------------------------------------------------------
# residuals (Newton, checks)
# ---------------------------------------------------------------------------

def residual(c, poses) -> list[float]:
    if isinstance(c, Pin):
        a, b = place(poses[c.a], c.p), place(poses[c.b], c.p)
        return [a[0] - b[0], a[1] - b[1]]
    pl, pg = poses[c.link], poses[c.guide]
    d = _rot(pg[0], c.d)
    off = _cross(d, _sub(place(pl, c.p), place(pg, c.p)))
    if isinstance(c, Slot):
        return [off]
    dt = math.remainder(pl[0] - pg[0], FULL_TURN)
    return [off, dt * 0.1]           # (an angle against metres: a tenth keeps them in step for usual sizes)


# ---------------------------------------------------------------------------
# the solver
# ---------------------------------------------------------------------------

class Solver:
    """Places every link for an input value, never jumping to another assembly mode.

    ``value`` and ``poses`` are the last good position; ``solve(v)`` walks there in small steps."""

    def __init__(self, lk: Linkage):
        self.lk = lk
        self.steps, self.newton, self.leftover = plan(lk)
        self.tol = 1e-7 * lk.size + 1e-9
        self.value = 0.0
        self.poses = [IDENTITY] * len(lk.names)
        self.signs = [0] * len(self.steps)
        self.hist: dict[int, list] = {}
        self.direction = 0
        self._cad_markers()
        # the CAD pose itself must solve (the pins fit), and the leftover pins must hold: else over-constrained
        self.poses = self._place(0.0, mode="cad")
        self.cad_signs = list(self.signs)
        self._check_leftover(self.poses, setup=True)
        self.step = ROT_STEP if lk.is_turning() else SLIDE_STEP_SHARE * lk.size
        moves = False
        for v in (self.step, -self.step):
            try:
                self.copy().solve(v)
                moves = True
            except Unreachable:
                pass
        if not moves:
            raise SetupError("It cannot move: too many pins or tracks lock it (check the pins it found)")

    # -- state ------------------------------------------------------------------
    def copy(self) -> "Solver":
        s = Solver.__new__(Solver)
        s.__dict__.update(self.__dict__)
        s.poses = list(self.poses)
        s.signs = list(self.signs)
        s.hist = {k: list(v) for k, v in self.hist.items()}
        return s

    def state(self) -> tuple[float, list[int]]:
        return self.value, list(self.signs)

    def set_state(self, value: float, signs) -> None:
        """Back to a position saved earlier (``state()``): the same assembly mode, no walk needed."""
        if self.newton:                       # Newton needs a start near the answer: walk from the CAD pose
            self.reset()
            self.solve(value)
            return
        signs = list(signs)
        if len(signs) != len(self.steps):
            signs = list(self.cad_signs)
        self.signs = signs
        self.hist = {}
        self.direction = 0
        self.poses = self._place(float(value), mode="sign")
        self.value = float(value)

    def reset(self) -> None:
        self.value = 0.0
        self.signs = list(self.cad_signs)
        self.poses = [IDENTITY] * len(self.lk.names)
        self.hist = {}
        self.direction = 0

    # -- moving -------------------------------------------------------------------
    def solve(self, value: float) -> list:
        """Walk to ``value``; returns the poses. Unreachable: stays at the last good position, raises."""
        value = float(value)
        delta = value - self.value
        if abs(delta) < 1e-15:
            return self.poses
        direction = 1 if delta > 0 else -1
        if direction != self.direction:
            self.hist = {}                  # turning back: the same side, never the prediction
            self.direction = direction
        n = max(1, math.ceil(abs(delta) / self.step - 1e-9))
        start = self.value
        for i in range(1, n + 1):
            v = start + delta * i / n
            try:
                poses = self._place(v, mode="track")
            except Unreachable:
                self.hist = {}
                raise
            self.poses = poses
            self.value = v
        return self.poses

    # -- one position ---------------------------------------------------------------
    def _place(self, v: float, mode: str) -> list:
        lk = self.lk
        poses = list(self.poses)
        poses[0] = IDENTITY
        poses[lk.input_link] = lk.input_pose(v)
        new_signs = list(self.signs)
        new_hist = {}
        self._v = v
        for k, st in enumerate(self.steps):
            self._do(k, st, poses, mode, new_signs, new_hist)
        if self.newton:
            self._newton(poses)
        self._check_leftover(poses)
        self.signs = new_signs
        for k, m in new_hist.items():
            h = self.hist.get(k, [])
            self.hist[k] = (h + [(v, m)])[-2:]
        return poses

    def _pick(self, k: int, roots: list, mode: str, signs: list, hist: dict):
        """roots: [(sign, marker, payload), ...] (two answers). The one that continues the motion."""
        if mode == "cad":
            m0 = self.markers[k]
            best = min(roots, key=lambda r: _len(_sub(r[1], m0)))
        else:
            h = self.hist.get(k, [])
            if mode == "track" and len(h) == 2 and abs(h[1][0] - h[0][0]) > 1e-15:
                # where the last two steps were heading, scaled to this step's size
                (v0, m0), (v1, m1) = h
                f = (self._v - v1) / (v1 - v0)
                pred = _add(m1, _mul(_sub(m1, m0), f))
                best = min(roots, key=lambda r: _len(_sub(r[1], pred)))
            else:
                same = [r for r in roots if r[0] == signs[k]]
                best = same[0] if same else roots[0]
        signs[k] = best[0]
        hist[k] = best[1]
        return best[2]

    def _do(self, k: int, st: Step, poses: list, mode: str, signs: list, hist: dict) -> None:
        names = self.lk.names
        tol = self.tol

        def world_at(it):           # ("at", xL, K, xK, c) -> world point
            return place(poses[it[2]], it[3])

        def world_line(it):         # ("online", xL, K, o, d, c) -> (O, D)
            pk = poses[it[2]]
            return place(pk, it[3]), _rot(pk[0], it[4])

        if st.kind == "pp":
            a, b = st.data
            L = st.links[0]
            q1, q2 = world_at(a), world_at(b)
            if abs(_len(_sub(q2, q1)) - _len(_sub(b[1], a[1]))) > tol * 10:
                raise Unreachable(f"'{names[L]}' does not fit between its two pins in this position: the mechanism "
                                  "is locked (too many pins)")
            poses[L] = _pose_from_points(a[1], q1, b[1], q2)
            return
        if st.kind == "rp":
            r, a = st.data
            L = st.links[0]
            poses[L] = _pose_from_point(poses[r[1]][0], a[1], world_at(a))
            return
        if st.kind == "rl":
            r, a, b = st.data
            L = st.links[0]
            th = poses[r[1]][0]
            rows, rhs = [], []
            for it in (a, b):
                if it[0] == "online":       # cross(D, R x + t - O) = 0
                    O, D = world_line(it)
                    rx = _rot(th, it[1])
                    rows.append((-D[1], D[0]))
                    rhs.append(-_cross(D, _sub(rx, O)))
                else:                        # L's line (o, d) through q: cross(R d, q - R o - t) = 0
                    q = place(poses[it[3]], it[4])
                    Rd, Ro = _rot(th, it[2]), _rot(th, it[1])
                    rows.append((Rd[1], -Rd[0]))
                    rhs.append(-_cross(Rd, _sub(q, Ro)))
            m = np.array(rows, dtype=float)
            t = np.linalg.solve(m, np.array(rhs, dtype=float))
            poses[L] = (th, float(t[0]), float(t[1]))
            return
        if st.kind == "pl":
            a, b = st.data
            L = st.links[0]
            q1 = world_at(a)
            O, D = world_line(b)
            r = _len(_sub(b[1], a[1]))
            roots = _circle_line(q1, r, O, D, tol)
            if roots is None:
                raise Unreachable(f"'{names[L]}' cannot reach its track in this position")
            pick = self._pick(k, [(s, p, p) for s, p in roots], mode, signs, hist)
            poses[L] = _pose_from_points(a[1], q1, b[1], pick)
            return
        if st.kind == "pt":
            a, b = st.data
            L = st.links[0]
            q1, q2 = world_at(a), place(poses[b[3]], b[4])
            o, d, x1 = b[1], b[2], a[1]
            h = _cross(d, _sub(o, x1))
            w = _sub(q2, q1)
            D = _len(w)
            alpha = _angle(d)
            if D < tol:
                if abs(h) > tol:
                    raise Unreachable(f"'{names[L]}' cannot reach its track in this position")
                raise Unreachable(f"'{names[L]}': its track runs through the pin it turns on")
            if abs(h) > D + tol:
                raise Unreachable(f"'{names[L]}' cannot reach its track in this position")
            g = math.asin(max(-1.0, min(1.0, h / D)))
            beta = _angle(w)
            ell = self.lk.size
            roots = []
            for s, phi in ((1, beta - g), (-1, beta - (math.pi - g))):
                th = phi - alpha
                pose = _pose_from_point(th, x1, q1)
                roots.append((s, place(pose, _add(x1, _mul(d, ell))), pose))
            poses[L] = self._pick(k, roots, mode, signs, hist)
            return
        # two links joined by a pin
        c, s1, s2 = st.data
        L1, L2 = st.links
        if st.kind == "dyad_pp":
            a1, a2 = s1[1], s2[1]
            q1, q2 = world_at(a1), world_at(a2)
            r1, r2 = _len(_sub(c.p, a1[1])), _len(_sub(c.p, a2[1]))
            roots = _circle_circle(q1, r1, q2, r2, tol)
            if roots is None:
                raise Unreachable(f"'{names[L1]}' and '{names[L2]}' cannot meet in this position (the links are "
                                  "too short or too long for it)")
            C = self._pick(k, [(s, p, p) for s, p in roots], mode, signs, hist)
            poses[L1] = _pose_from_points(a1[1], q1, c.p, C)
            poses[L2] = _pose_from_points(a2[1], q2, c.p, C)
            return
        if st.kind == "dyad_pl":
            a1 = s1[1]
            rot, online = s2[1], s2[2]
            q1 = world_at(a1)
            r1 = _len(_sub(c.p, a1[1]))
            th2 = poses[rot[1]][0]
            O, D = world_line(online)
            # L2's pin point runs along a line: O + R2 (c - x2) + s D
            O2 = _add(O, _rot(th2, _sub(c.p, online[1])))
            roots = _circle_line(q1, r1, O2, D, tol)
            if roots is None:
                raise Unreachable(f"'{names[L1]}' cannot reach '{names[L2]}' in this position")
            C = self._pick(k, [(s, p, p) for s, p in roots], mode, signs, hist)
            poses[L1] = _pose_from_points(a1[1], q1, c.p, C)
            poses[L2] = _pose_from_point(th2, c.p, C)
            return
        if st.kind == "dyad_ll":
            lines = []
            for side in (s1, s2):
                rot, online = side[1], side[2]
                th = poses[rot[1]][0]
                O, D = world_line(online)
                lines.append((_add(O, _rot(th, _sub(c.p, online[1]))), D, th))
            (O1, D1, t1), (O2, D2, t2) = lines
            den = _cross(D1, D2)
            if abs(den) < 1e-12:
                raise Unreachable(f"'{names[L1]}' and '{names[L2]}' slide in parallel: their pin is not fixed")
            s = _cross(_sub(O2, O1), D2) / den
            C = _add(O1, _mul(D1, s))
            poses[L1] = _pose_from_point(t1, c.p, C)
            poses[L2] = _pose_from_point(t2, c.p, C)
            return
        raise RuntimeError(st.kind)

    def _cad_markers(self) -> None:
        """The CAD answer of every step with two answers (the CAD model's assembly mode)."""
        self.markers = {}
        ell = self.lk.size
        for k, st in enumerate(self.steps):
            if st.kind == "pl":
                self.markers[k] = st.data[1][1]
            elif st.kind == "pt":
                a, b = st.data
                self.markers[k] = _add(a[1], _mul(b[2], ell))
            elif st.kind in ("dyad_pp", "dyad_pl"):
                self.markers[k] = st.data[0].p

    def _newton(self, poses: list) -> None:
        links = self.newton
        cons = [c for c in self.lk.pins + self.lk.slots + self.lk.slides if _touches(c, links)]
        x = np.array([v for L in links for v in poses[L]], dtype=float)

        def res(x):
            p = list(poses)
            for i, L in enumerate(links):
                p[L] = (x[3 * i], x[3 * i + 1], x[3 * i + 2])
            return np.array([v for c in cons for v in residual(c, p)], dtype=float)

        lam = 1e-6
        r = res(x)
        for _ in range(60):
            if np.max(np.abs(r), initial=0.0) < self.tol * 1e-3:
                break
            J = np.empty((len(r), len(x)))
            h = 1e-7
            for j in range(len(x)):
                dx = np.zeros_like(x)
                dx[j] = h
                J[:, j] = (res(x + dx) - res(x - dx)) / (2 * h)
            A = J.T @ J
            g = J.T @ r
            while True:
                try:
                    step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-12), -g)
                except np.linalg.LinAlgError:
                    lam *= 10
                    continue
                r2 = res(x + step)
                if np.dot(r2, r2) < np.dot(r, r) or lam > 1e8:
                    break
                lam *= 10
            x = x + step
            r = r2
            lam = max(lam / 10, 1e-9)
        if np.max(np.abs(r), initial=0.0) > self.tol:
            raise Unreachable("The mechanism cannot be put together in this position")
        for i, L in enumerate(links):
            poses[L] = (float(x[3 * i]), float(x[3 * i + 1]), float(x[3 * i + 2]))

    def _check_leftover(self, poses, setup: bool = False) -> None:
        for c in self.leftover:
            r = residual(c, poses)
            if max(abs(v) for v in r) > self.tol * 10:
                names = self.lk.names
                ends = (c.a, c.b) if isinstance(c, Pin) else (c.link, c.guide)
                what = f"'{names[ends[0]]}' and '{names[ends[1]]}'"
                if setup:
                    raise SetupError(f"The pins do not fit together: check the pin between {what}")
                raise Unreachable(f"The pin between {what} does not fit in this position: the mechanism is "
                                  "locked (too many pins)")

    # -- ranges and other inputs ------------------------------------------------------
    def limits(self, max_turn: float = FULL_TURN, max_slide: float | None = None) -> tuple[float, float]:
        """The input's reachable range from the CAD pose (rad / m). ±inf: it turns all the way round."""
        reach = max_turn if self.lk.is_turning() else (max_slide if max_slide is not None else 10 * self.lk.size)
        out = []
        for direction in (-1, 1):
            s = self.copy()
            s.reset()
            good = 0.0
            bad = None
            steps = math.ceil(reach / self.step)
            for i in range(1, steps + 1):
                v = direction * i * self.step
                try:
                    s.solve(v)
                    good = v
                except Unreachable:
                    bad = v
                    break
            if bad is None:
                out.append(direction * math.inf if self.lk.is_turning() else good)
                continue
            base = s.copy()
            for _ in range(40):
                mid = (good + bad) / 2
                t = base.copy()
                try:
                    t.solve(mid)
                    good, base = mid, t
                except Unreachable:
                    bad = mid
            out.append(good)
        return out[0], out[1]

    def value_for(self, measure, target: float, lo: float = -math.inf, hi: float = math.inf) -> float:
        """The input value (near the current one) at which ``measure`` reads ``target``; the solver walks
        there. Beyond reach: the nearest value it gets to, and Unreachable is raised from there."""
        f = measure.of(self.poses)
        if abs(f - target) < 1e-9 * self.lk.size:
            return self.value
        h = self.step * 0.5
        probe = None
        for v in (self.value + h, self.value - h):
            if lo <= v <= hi:
                try:
                    probe = self.copy()
                    probe.solve(v)
                    break
                except Unreachable:
                    probe = None
        if probe is None:
            raise Unreachable("The mechanism cannot move from here")
        slope = (measure.of(probe.poses) - f) / (probe.value - self.value)
        if abs(slope) < 1e-15:
            raise Unreachable("This input does not change it here")
        direction = 1 if (target - f) * slope > 0 else -1
        prev_val, prev_f = self.value, f
        for _ in range(100000):
            v = self.value + direction * self.step
            if v > hi or v < lo:
                v = hi if v > hi else lo
                if abs(v - self.value) < 1e-15:
                    raise Unreachable("Beyond the limits of the input")
            before = self.copy()
            self.solve(v)                       # Unreachable propagates: the solver stays at its last position
            fv = measure.of(self.poses)
            if (fv - target) * (prev_f - target) <= 0:
                a, b, fa = prev_val, v, prev_f
                base = before
                for _ in range(60):
                    mid = (a + b) / 2
                    t = base.copy()
                    t.solve(mid)
                    fm = measure.of(t.poses)
                    if (fm - target) * (fa - target) <= 0:
                        b = mid
                    else:
                        a, fa, base = mid, fm, t
                    if abs(b - a) < 1e-12:
                        break
                t = base.copy()
                t.solve((a + b) / 2)
                self.__dict__.update(t.__dict__)
                return self.value
            if (fv - prev_f) * direction * slope < 0:
                raise Unreachable("It turns back before getting there: out of reach")
            prev_val, prev_f = v, fv
        raise Unreachable("Out of reach")


def _circle_line(q, r, O, D, tol):
    """Points O + s D at distance r from q: [(sign, point), (sign, point)] or None."""
    w = _sub(O, q)
    b = _dot(D, w)
    c = _dot(w, w) - r * r
    disc = b * b - c
    if disc < -tol * max(r, tol):
        return None
    sq = math.sqrt(max(disc, 0.0))
    return [(1, _add(O, _mul(D, -b + sq))), (-1, _add(O, _mul(D, -b - sq)))]


def _circle_circle(q1, r1, q2, r2, tol):
    """Where the circles (q1, r1) and (q2, r2) meet: [(sign, point), ...] (sign: side of the line q1 -> q2)."""
    w = _sub(q2, q1)
    d = _len(w)
    if d < 1e-15:
        return None
    if d > r1 + r2 + tol or d < abs(r1 - r2) - tol:
        return None
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h2 = r1 * r1 - a * a
    h = math.sqrt(max(h2, 0.0))
    u = (w[0] / d, w[1] / d)
    m = _add(q1, _mul(u, a))
    perp = (-u[1], u[0])
    return [(1, _add(m, _mul(perp, h))), (-1, _add(m, _mul(perp, -h)))]


# ---------------------------------------------------------------------------
# finding the pins from the parts' round faces
# ---------------------------------------------------------------------------

def find_pins(link_points: list[list[tuple]], tol: float, chain: bool = True) -> list[Pin]:
    """Pins from where links have a round face (hole or shaft) on the same line.

    ``link_points[i]``: the 2D points of link i's round-face axes (parallel to the plane's normal). A point
    shared by k links gives k - 1 pins (a chain: each link turns about it), or with ``chain=False`` one pin
    for every pair (to find links that cannot turn against each other)."""
    pts = [(tuple(p), i) for i, plist in enumerate(link_points) for p in plist]
    clusters: list[list] = []
    for p, i in pts:
        for cl in clusters:
            if _len(_sub(cl[0][0], p)) <= tol:
                cl.append((p, i))
                break
        else:
            clusters.append([(p, i)])
    pins = []
    for cl in clusters:
        links = sorted({i for _p, i in cl})
        if len(links) < 2:
            continue
        cx = sum(p[0] for p, _ in cl) / len(cl)
        cy = sum(p[1] for p, _ in cl) / len(cl)
        pairs = zip(links, links[1:]) if chain else ((a, b) for k, a in enumerate(links) for b in links[k + 1:])
        for a, b in pairs:
            pins.append(Pin(a, b, (cx, cy)))
    return pins


def rigid_groups(n: int, pins: list[Pin], tol: float) -> list[int]:
    """Links joined by pins at two or more different points cannot turn against each other: one rigid body.
    Returns the group of every link (the group of link 0, the base, is 0)."""
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    changed = True
    while changed:
        changed = False
        by_pair: dict = {}
        for c in pins:
            a, b = find(c.a), find(c.b)
            if a == b:
                continue
            key = (min(a, b), max(a, b))
            plist = by_pair.setdefault(key, [])
            if not any(_len(_sub(p, c.p)) <= tol for p in plist):
                plist.append(c.p)
        for (a, b), plist in by_pair.items():
            if len(plist) >= 2 and find(a) != find(b):
                ra, rb = find(a), find(b)
                if rb == 0 or (ra != 0 and rb < ra):
                    ra, rb = rb, ra
                parent[rb] = ra
                changed = True
    roots = [find(i) for i in range(n)]
    num = {roots[0]: 0}
    for r in roots:
        if r not in num:
            num[r] = len(num)
    return [num[r] for r in roots]


def merge(names: list[str], pins: list[Pin], groups: list[int], tol: float):
    """Names and pins of the merged mechanism: one link per rigid group, pins inside a group dropped, and
    the links on one point chained (k links on a point: k - 1 pins)."""
    ng = max(groups) + 1
    new_names = [""] * ng
    for i, g in enumerate(groups):
        new_names[g] = names[i] if not new_names[g] else new_names[g] + " + " + names[i]
    points: list[list] = []                    # [point, {groups}]
    for c in pins:
        a, b = groups[c.a], groups[c.b]
        if a == b:
            continue
        for pt in points:
            if _len(_sub(pt[0], c.p)) <= tol:
                pt[1] |= {a, b}
                break
        else:
            points.append([c.p, {a, b}])
    out = []
    for p, gs in points:
        gs = sorted(gs)
        out += [Pin(a, b, p) for a, b in zip(gs, gs[1:])]
    return new_names, out


# ---------------------------------------------------------------------------
# scissor lifts: which arm ends run in tracks
# ---------------------------------------------------------------------------

@dataclass
class ScissorLayout:
    slots: list
    stages: list            # [(arm, arm), ...] from the base up
    base_pin: tuple
    platform: int | None
    height: Height | None
    input_pin: int          # index into the pins: the fixed pin on the base


def scissor(n_links: int, pins: list[Pin], points: list[list[tuple]], platform: int | None, tol: float
            ) -> ScissorLayout:
    """The layout of a scissor lift: link 0 is the base, ``platform`` the top (or None), the rest the arms.

    Each stage is two arms crossing at a pin near both their middles. An arm end with no pin is a roller: on
    the base when the arm is in the bottom stage and not pinned to the base, on the platform when it is in the
    top stage and not pinned to it. A roller runs along the line from the fixed pin (base or platform) to it."""
    arms = [i for i in range(1, n_links) if i != platform]
    if len(arms) < 2:
        raise SetupError("A scissor lift needs at least two arms (one stage)")

    def ends(i):
        pl = points[i]
        if len(pl) < 2:
            raise SetupError("An arm needs a round face (hole, pin or roller) at both ends")
        far = max(((a, b) for a in pl for b in pl), key=lambda ab: _len(_sub(ab[0], ab[1])))
        u = _unit(_sub(far[1], far[0]))
        proj = [_dot(p, u) for p in pl]
        return pl[proj.index(min(proj))], pl[proj.index(max(proj))], u

    end = {i: ends(i) for i in arms}

    def pins_at(i, p):
        return [c for c in pins if i in (c.a, c.b) and _len(_sub(c.p, p)) <= tol]

    # centre pins: between two arms, away from both arms' ends
    partner = {}
    for c in pins:
        if c.a in end and c.b in end:
            ok = True
            for i in (c.a, c.b):
                e0, e1, _u = end[i]
                if min(_len(_sub(c.p, e0)), _len(_sub(c.p, e1))) <= tol:
                    ok = False
            if ok:
                partner[c.a] = c.b
                partner[c.b] = c.a
    lonely = [i for i in arms if i not in partner]
    if lonely:
        raise SetupError("Every arm must cross another arm on a pin near its middle (one stage = two arms)")
    base_pins = [k for k, c in enumerate(pins) if 0 in (c.a, c.b) and (c.a in end or c.b in end)]
    if len(base_pins) != 1:
        raise SetupError("The bottom stage must have exactly one arm pinned to the base (the other one rolls)"
                         if not base_pins else "More than one arm is pinned to the base: only one may be")
    k_in = base_pins[0]
    bp = pins[k_in]
    a1 = bp.b if bp.a == 0 else bp.a
    # stages from the base up: the next stage is pinned end to end to this one
    stages = [(a1, partner[a1])]
    seen = {a1, partner[a1]}
    while True:
        nxt = None
        for i in stages[-1]:
            for c in pins:
                if i in (c.a, c.b):
                    o = c.b if c.a == i else c.a
                    if o in end and o not in seen:
                        nxt = o
        if nxt is None:
            break
        stages.append((nxt, partner[nxt]))
        seen |= {nxt, partner[nxt]}
    if len(seen) != len(arms):
        raise SetupError("Some arms are not joined to the stages below them")
    top = stages[-1]
    plat_pin = None
    if platform is not None:
        pp = [c for c in pins if platform in (c.a, c.b) and (c.a in top or c.b in top)]
        if len(pp) != 1:
            raise SetupError("The platform must be pinned to exactly one arm of the top stage (the other one "
                             "rolls under it)")
        plat_pin = pp[0]
    slots = []
    for st_i, stage in enumerate(stages):
        for i in stage:
            e0, e1, _u = end[i]
            free = [e for e in (e0, e1) if not pins_at(i, e)]
            for e in free:
                if st_i == 0 and i != a1:
                    d = _sub(e, bp.p)
                    slots.append(Slot(i, 0, e, _unit(d)))
                elif st_i == len(stages) - 1 and platform is not None and i not in (plat_pin.a, plat_pin.b):
                    d = _sub(e, plat_pin.p)
                    slots.append(Slot(i, platform, e, _unit(d)))
    height = None
    if platform is not None:
        base_slot = next((s for s in slots if s.guide == 0), None)
        along = base_slot.d if base_slot is not None else (1.0, 0.0)
        up = (-along[1], along[0])
        if _dot(_sub(plat_pin.p, bp.p), up) < 0:
            up = (-up[0], -up[1])
        height = Height(platform, plat_pin.p, bp.p, up)
    return ScissorLayout(slots, stages, bp.p, platform, height, k_in)


def crossing_links(n_links: int, pins: list[Pin], points: list[list[tuple]], tol: float) -> set:
    """Links pinned to another link near the middle of both (the arms of a scissor's stages)."""
    out = set()

    def far_ends(i):
        pl = points[i]
        if len(pl) < 2:
            return None
        return max(((a, b) for a in pl for b in pl), key=lambda ab: _len(_sub(ab[0], ab[1])))

    for c in pins:
        if 0 in (c.a, c.b):
            continue
        ok = True
        for i in (c.a, c.b):
            e = far_ends(i)
            if e is None or min(_len(_sub(c.p, e[0])), _len(_sub(c.p, e[1]))) <= tol:
                ok = False
        if ok:
            out |= {c.a, c.b}
    return out


def scissor_platform(n_links: int, pins: list[Pin], points: list[list[tuple]], tol: float) -> int | None:
    """The scissor's platform: the one moving link that is not an arm (None when every link is an arm)."""
    arms = crossing_links(n_links, pins, points, tol)
    rest = [i for i in range(1, n_links) if i not in arms]
    if len(rest) > 1:
        raise SetupError("A scissor lift has arms (crossing in pairs) and one platform; more than one other part "
                         "was picked")
    return rest[0] if rest else None
