"""Drag chains (energy chains): where every link is, without Blender (task 0058).

A drag chain is a row of rigid links hinged on pins, every pin exactly one ``pitch`` from the next. One end is
fixed, the other rides on the moving part. The chain lies along the fixed part, rolls over a bend of a fixed
radius and comes back to the moving end; when the moving end travels, the bend follows at half its speed.

**Chain coordinates.** Origin = the fixed end's pin (pin 0); **u** = along the fixed run towards the bend;
**v** = from the fixed run towards the moving run; **w** = u × v, across the chain. A chain of ``links`` links
has pins 0 … ``links``; link i goes from pin i to pin i + 1. Any unit of length (the app uses metres).

**The shape** is a path the pins lie on, walked in steps of exactly one pitch (measured straight from pin to pin,
a chord, as a real link does):

1. the fixed run: the line v = 0 from pin 0 to u = ``bend_u``;
2. the bend: a circle of ``radius`` round (``bend_u``, ``radius``), from its lowest point upwards;
3. STRAIGHT: the line that leaves the circle as a tangent and ends at the moving end. With the moving end at
   v = 2 × radius that is the classic picture (two runs and half a circle); a moving end that is a little
   higher, lower or further out is still met exactly, the bend is then a bit more or less than half a turn.
   GLIDE (a long chain whose upper run lies on the lower one): the circle is followed a little further, the run
   comes down as a straight line at ``glide_angle``, turns back level over an arc of 3 × the bend's radius (so
   no pin turns back by more than a third of what a link turns in the bend – no kink at the foot of the slope)
   and lies at the moving end's height up to the moving end. An end nearer to the bend gets only the part of
   that arc that still leads to it, and an end so near that there is no room to come down at all gets the
   STRAIGHT tangent line; the three meet without a jump. A rest height just under the top of the bend leaves no
   room for the slope: the S is then made with a smaller angle that fits. ``rest_v`` above the moving end's
   height (the app does not use it): the run comes down to ``rest_v`` (at most the top of the bend), lies
   there, and goes down to the moving end at the glide angle in one more straight piece.

Every step has a closed form: on a line the pins are one pitch apart; from the last pin of a piece to the first
pin of the next piece it is where a circle of one pitch round that pin meets the next piece; on the bend every
link turns by 2·asin(pitch / (2·radius)). The one unknown is where the bend is (``bend_u``): the further out,
the more links the path to the moving end takes. That count rises steadily with ``bend_u``, so the place where
it equals the chain's own number of links is found with secant steps kept inside a bracket (3-5 as a rule, at
most 48), all frames of a batch at once and each frame for itself: a frame that has settled is left alone. So
the shape is a pure function of the moving end: no memory of earlier frames, no jumps while it moves, and a
frame solved alone gives what it gives in a batch.

**Sideways (w).** A moving end that is not in the chain's plane (w ≠ 0) is met too: w rises evenly along the
chain from where the bend starts to the moving end (by pin number, counted from the exact place the bend starts,
so nothing jumps when a pin goes onto the bend). A link that rises by dw sideways is walked with the pitch
sqrt(pitch² − dw²) in the plane, so every pin-to-pin distance stays exactly one pitch in 3-D.

**Out of reach** (``short``): the moving end is further away than the chain is long (ahead, or so far back that
the fixed run would have to be shorter than nothing), or it lies where no path leads (inside the bend's circle,
below the fixed run in front of the bend). The bend then stops where it gets nearest (at pin 0 when the end is
too far), the pins are still one pitch apart and follow the path towards the moving end, and the last pin is
simply where the chain ends. Never NaN. ``short`` is also said where the links do reach but no drag chain
could be: the moving end on or under the fixed run (v ≤ 0: the run after the bend would lie in or pass through
the fixed run), and a chain pulled out ahead so far that less than a quarter turn is left of its bend (with the
end at v = 2 × radius: from u = length − a quarter circle on; the classic travel ends at length − half a
circle, where the upper run is used up). Up to there no pin moves faster than the moving end and the bend goes
forward; beyond, the bend runs backwards and the chain whips straight. The shape itself goes on without a jump.

**From the CAD pose** (``fit_links``): the links' matrices are put in order along the chain, the two pin points of
each kind of link are found from "the front pin of a link is the rear pin of the next" (linear least squares),
and pitch, bend radius, plane and the two ends follow from the pins. The radius comes from the angle the links
turn by inside the bend and is checked against the pose: the shape drawn with it must lie on the CAD pins (with
rounded numbers the radius that draws the pose best is taken). Every link then keeps its place on its two
pins (``local``), so ``link_matrices`` puts the CAD links on any later shape. ``fit_solid`` reads a chain drawn
as one U-shaped band.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

STEPS = 48                  # at most this many secant steps for the bend's place (pulled nearly straight: 20-35)
TOL_LINKS = 2e-12           # "settled": the path's link count is this close to the chain's
REACH_TOL = 1e-9            # x pitch: the last pin counts as on the moving end
MIN_RADIUS = 0.55           # x pitch: the smallest bend the walk is made for (a smaller radius counts as this)
MAX_SIDE = 0.9              # x pitch: the most one link may go sideways (w)
FIT_TOL = 0.02              # x pitch: the links' pins fit one rigid pattern when they meet this well
CHORD_TOL = 0.1             # x pitch: ... and no pin distance is further than this from the others
GLIDE_BELOW = 0.85          # the moving run lies under this x 2 radius in the CAD pose: mode GLIDE
TURN_WEIGHT = 0.7           # putting links in order: a link turned by 1 radian counts as this many spacings away
PITCH_PER_HEIGHT = 1.6      # fit_solid: the pitch suggested for a band of this height
GLIDE_BACK = 3.0            # GLIDE: the turn back at the foot of the slope has this x the bend's radius
GLIDE_ANGLES = (math.radians(1.0), math.radians(60.0))      # GLIDE: the glide angle is kept between these
MIN_TURN = 0.5 * math.pi    # a bend of less than a quarter turn is no pose of a drag chain: ``short``
LINE, ARC = 0, 1            # the pieces of the path after the bend
POSE_TOL = 0.25             # x pitch: a fit draws the CAD pose this closely, or its note says that it does not
POSE_NOTE = ("The app draws this chain up to %.1f link lengths away from where the CAD file has it. Check the bend "
             "radius and how the upper run is drawn.")


# ---------------------------------------------------------------------------
# what a chain is, and its shape
# ---------------------------------------------------------------------------

@dataclass
class ChainSpec:
    """What a chain is: how long its links are, how many, how tight its bend, how its upper run is drawn."""
    pitch: float                                    # pin to pin
    links: int
    radius: float                                   # the circle the pins lie on in the bend
    mode: str = "STRAIGHT"                          # or "GLIDE"
    glide_angle: float = math.radians(12.0)         # GLIDE: how steeply the run comes down (kept in 1 … 60 degrees)
    rest_v: float | None = None                     # GLIDE: v the run comes down to (default: the moving end's v)


@dataclass
class Chain:
    """The pins of a chain at B moving ends (frames)."""
    pins: np.ndarray        # (B, links + 1, 3) in chain coordinates (u, v, w)
    short: np.ndarray       # (B,) bool: the moving end is out of reach, or where no drag chain can be
    bend_u: np.ndarray      # (B,) u of the bend's centre
    radius: float = 0.0     # the bend radius the shape was made with (the spec's, or 0.55 x pitch if that is more)


def _checked(spec: ChainSpec):
    pitch, links, radius = float(spec.pitch), int(spec.links), float(spec.radius)
    if not (pitch > 0.0 and math.isfinite(pitch)):
        raise ValueError("a chain's pitch must be more than 0")
    if links < 1:
        raise ValueError("a chain has at least one link")
    if not (radius > 0.0 and math.isfinite(radius)):
        raise ValueError("a chain's bend radius must be more than 0")
    if spec.mode not in ("STRAIGHT", "GLIDE"):
        raise ValueError(f"unknown chain mode {spec.mode!r}")
    return pitch, links, max(radius, MIN_RADIUS * pitch)


class _Walk:
    """The path for B moving ends, walked in chords for any place of the bend (arrays of length B)."""

    def __init__(self, spec: ChainSpec, moving: np.ndarray):
        self.p, self.n, self.r = _checked(spec)
        self.um, self.vm, self.wm = moving[:, 0], moving[:, 1], moving[:, 2]
        r = self.r
        self.glide = spec.mode == "GLIDE"
        self.down = None                                # GLIDE with rest_v: the last piece, down to the moving end
        self.eu, self.ev = self.um, self.vm             # where the path after the bend is made for
        if self.glide:
            a = min(max(float(spec.glide_angle), GLIDE_ANGLES[0]), GLIDE_ANGLES[1])
            self.rho = GLIDE_BACK * r                   # the radius of the turn back at the foot of the slope
            if spec.rest_v is not None:
                # the run comes down to rest_v, lies there, and goes down to the moving end at the glide angle
                self.ev = np.maximum(min(float(spec.rest_v), 2.0 * r), self.vm)
                over = self.ev - self.vm
                self.eu = self.um + over / math.tan(a)
                self.down = (-math.cos(a), -math.sin(a), over / math.sin(a))
            # a rest height near the top of the bend leaves no room for the whole S: a smaller angle that fits
            room = np.minimum(np.maximum((2.0 * r - self.ev) / (r + self.rho), 0.0), 1.0)
            ae = np.minimum(a, np.arccos(1.0 - room))
            self.ae, self.sa, self.ca = ae, np.sin(ae), np.cos(ae)
            self.drop = self.rho * (1.0 - self.ca)      # how far the whole turn back leaves the slope's line
            safe = np.where(self.sa > 0.0, self.sa, 1.0)
            self.slope = np.maximum(r * (1.0 + self.ca) - self.ev - self.drop, 0.0) / safe      # the whole S's slope
        # an end lower than the bend's centre: while the bend passes it (from bend place gap_a to gap_b) no
        # tangent leads to it; there the path is led round the circle evenly so that the link count keeps rising
        self.low = self.ev < r
        self.any_low = bool(self.low.any())
        if self.any_low:
            reach = np.sqrt(np.maximum(self.ev * (2.0 * r - self.ev), 0.0))
            self.gap_a, self.gap_b = self.eu - reach, self.eu + r
            self.th_a = np.arctan2(reach, r - self.ev)
            self.len_a = np.sqrt(np.maximum((self.ev - r) ** 2 - r * r, 0.0))
        self.flat = not self.wm.any()
        self.phi = 2.0 * math.asin(self.p / (2.0 * self.r))

    def pieces(self, c):
        """The path after the fixed run for bend place ``c``: how far round the bend's circle, then the pieces:
        (LINE, start u, start v, direction u, direction v, length) and, GLIDE, the turn back at the foot of the
        slope (ARC, centre u, centre v, radius, the slope's angle where it starts, the angle it turns by)."""
        r = self.r
        du, dv = self.eu - c, self.ev - r
        tangent = np.sqrt(np.maximum(du * du + dv * dv - r * r, 0.0))       # 0: the end is inside the circle
        # the angle (from the circle's lowest point, the way the chain runs) where the tangent to the end leaves
        th = np.arctan2(du, -dv) - np.arctan2(tangent, r)
        th = np.maximum((th + 0.5 * math.pi) % (2.0 * math.pi) - 0.5 * math.pi, 0.0)
        if self.any_low:
            part = (c - self.gap_a) / (self.gap_b - self.gap_a)
            gap = self.low & (part > 0.0) & (part < 1.0)
            th = np.where(gap, self.th_a + part * (1.5 * math.pi - self.th_a), th)
            tangent = np.where(gap, self.len_a + part * (r - self.ev - self.len_a), tangent)
        if not self.glide:
            sn, cs = np.sin(th), np.cos(th)
            return th, [(LINE, c + r * sn, r - r * cs, cs, sn, tangent)]
        # GLIDE. Where the slope (at the glide angle) leaves the bend, and how far the end lies beyond its line:
        rho, sa, ca = self.rho, self.sa, self.ca
        off_u, off_v = self.eu - (c - r * sa), self.ev - r * (1.0 + ca)
        beyond = ca * off_v - sa * off_u
        room = (beyond > 0.0) & (self.ae > 0.0)         # else no room to come down: the tangent as for STRAIGHT
        # the turn back is as much of its arc as brings the path's line onto the end; the whole of it: flat after
        whole = room & (beyond >= self.drop)
        turn = np.where(room, np.arccos(np.minimum(np.maximum(1.0 - beyond / rho, ca), 1.0)), 0.0)
        along = -ca * off_u - sa * off_v                # the end along the slope's line
        th = np.where(room, math.pi + self.ae, th)
        sn, cs = np.sin(th), np.cos(th)                 # the slope's direction is (cs, sn)
        su, sv = c + r * sn, r - r * cs
        first = np.where(room, np.where(whole, self.slope, along - rho * np.sin(turn)), tangent)
        qu, qv = su + first * cs + rho * sn, sv + first * sn - rho * cs     # the centre of the turn back
        start = th - math.pi                            # the slope's angle below level
        ends = start - turn
        se, ce = np.sin(ends), np.cos(ends)
        hu, hv = qu + rho * se, qv - rho * ce           # where the turn back ends
        level = np.where(whole, hu - self.eu, 0.0)      # the run lying at the rest height
        tail = [(LINE, su, sv, cs, sn, first), (ARC, qu, qv, rho, start, turn), (LINE, hu, hv, -ce, -se, level)]
        if self.down is not None:
            tail.append((LINE, hu - ce * level, hv - se * level) + self.down)
        return th, tail

    def walk(self, c):
        """Walk the path for bend place ``c``. Returns ``count``: the (real) number of links the path takes to
        its end – it rises steadily with ``c``; the chain fits where it equals ``links`` – and what ``pins``
        needs."""
        p, n, r = self.p, self.n, self.r
        kap = c / p                                     # the (real) pin number where the bend starts
        n0 = np.floor(kap)                              # the last pin on the fixed run
        d = c - n0 * p                                  # ... and how far it is before the bend
        if self.flat:                                   # every moving end in the chain's plane
            side, p1, p0, phi = 0.0, p, p, self.phi
        else:
            side = self.wm / np.maximum(n - kap, 1.0)   # w per link after the bend's start
            side = np.minimum(np.maximum(side, -MAX_SIDE * p), MAX_SIDE * p)
            p1 = np.sqrt(p * p - side * side)           # those links' pitch in the plane
            side0 = side * (n0 + 1.0 - kap)             # the link that leaves the fixed run rises only partly
            p0 = np.sqrt(p * p - side0 * side0)
            phi = 2.0 * np.arcsin(p1 / (2.0 * r))       # the turn of one link on the bend
        th_end, tail = self.pieces(c)
        # the first pin on the circle: a triangle of the circle's centre, the last pin on the run and that pin
        dist = np.sqrt(r * r + d * d)
        cos_g = (d * d + 2.0 * r * r - p0 * p0) / (2.0 * r * dist)
        th1 = np.arccos(np.minimum(np.maximum(cos_g, -1.0), 1.0)) - np.arctan2(d, r)
        th1 = np.maximum(th1, 0.0)
        on = th1 <= th_end
        m = np.where(on, np.floor((th_end - th1) / phi) + 1.0, 0.0)     # pins on the circle
        th_last = th1 + (m - 1.0) * phi
        pu = np.where(on, c + r * np.sin(th_last), n0 * p)              # the last pin so far
        pv = np.where(on, r - r * np.cos(th_last), 0.0)
        k = n0 + m                                                      # ... and its number
        q = p if self.flat else np.where(on, p1, p0)                    # the pitch of the link that leaves it
        placed = []
        for piece in tail:
            if piece[0] == LINE:
                # the next pin: where a circle of one pitch round the last pin meets this piece's line
                _kind, su, sv, eu, ev, length = piece
                ru, rv = su - pu, sv - pv
                b = ru * eu + rv * ev
                gap = np.maximum(q * q - ru * ru - rv * rv, 0.0)
                root = np.sqrt(b * b + gap)
                s0 = np.where(b > 0.0, gap / np.maximum(b + root, 1e-300), root - b)
                has = s0 <= length                                      # else: no pin lands on this piece
                cnt = np.where(has, np.floor((length - s0) / p1) + 1.0, 0.0)
                s_last = s0 + (cnt - 1.0) * p1
                pu, pv = np.where(has, su + s_last * eu, pu), np.where(has, sv + s_last * ev, pv)
                placed.append((LINE, k + 1.0, s0, su, sv, eu, ev))
            else:
                # ... meets this arc: a triangle of the arc's centre, the last pin and the next
                _kind, qu, qv, rho, start, sweep = piece
                ru, rv = pu - qu, pv - qv
                dist = np.maximum(np.hypot(ru, rv), 1e-300)
                cos_g = (dist * dist + rho * rho - q * q) / (2.0 * rho * dist)
                t0 = start - np.arctan2(ru, -rv) + np.arccos(np.minimum(np.maximum(cos_g, -1.0), 1.0))
                t0 = np.maximum(t0, 0.0)                                # the angle from the arc's start
                has = t0 <= sweep
                step = 2.0 * np.arcsin(p1 / (2.0 * rho))                # the turn of one link on this arc
                cnt = np.where(has, np.floor((sweep - t0) / step) + 1.0, 0.0)
                at = start - (t0 + (cnt - 1.0) * step)
                pu, pv = np.where(has, qu + rho * np.sin(at), pu), np.where(has, qv - rho * np.cos(at), pv)
                placed.append((ARC, k + 1.0, t0, qu, qv, rho, start, step))
            k = k + cnt
            if not self.flat:
                q = np.where(has, p1, q)
        end_u, end_v = su + length * eu, sv + length * ev               # the last piece is a line
        count = k + np.hypot(end_u - pu, end_v - pv) / q
        return count, (kap, n0, side, p1, phi, th1, th_end, placed)

    def solve(self):
        """The bend's place for every moving end: where the path takes exactly ``links`` links."""
        p, n = self.p, self.n
        top = n * p
        x = 0.5 * (top - math.pi * self.r + self.um)    # the first guess: a chain without links (a smooth band)
        if self.glide:                                  # ... lying at its rest height after the whole S
            more = (self.r * (self.ae - self.sa) + self.slope * (1.0 - self.ca) + self.rho * (self.ae - self.sa))
            x = 0.5 * (top - math.pi * self.r - more + self.eu - (self.down[2] if self.down is not None else 0.0))
        x = np.minimum(np.maximum(x, 0.0), top)
        lo, hi = np.zeros_like(x), np.full_like(x, top)
        slope = 2.0 / p
        x_old = f_old = None
        with np.errstate(divide="ignore", invalid="ignore"):
            for step in range(STEPS):
                f = self.walk(x)[0] - n
                lo, hi = np.where(f < 0.0, x, lo), np.where(f > 0.0, x, hi)
                if step:
                    slope = (f - f_old) / (x - x_old)
                new = x - f / slope
                inside = (new > lo) & (new < hi)                    # False for NaN too
                new = np.where(inside, new, 0.5 * (lo + hi))
                settled = np.abs(f) <= TOL_LINKS
                if settled.all():                                   # nothing would change any more
                    break
                x_old, f_old = x, f
                x = np.where(settled, x, new)
        return x

    def pins(self, c):
        """The pins (B, links + 1, 3) for bend place ``c``, how far the last one is from the moving end, and how
        far round the bend the chain goes."""
        p, n, r = self.p, self.n, self.r
        _count, (kap, n0, side, p1, phi, th1, th_end, placed) = self.walk(c)
        col = lambda a: np.asarray(a, dtype=float).reshape(-1, 1)      # noqa: E731
        i = np.arange(n + 1.0)[None, :]
        out = np.empty((len(c), n + 1, 3))
        th = col(th1) + (i - col(n0) - 1.0) * col(phi)
        bend = i > col(n0)
        u = np.where(bend, col(c) + r * np.sin(th), i * p)
        v = np.where(bend, r - r * np.cos(th), 0.0)
        for piece in placed:
            here = i >= col(piece[1])
            more = i - col(piece[1])
            if piece[0] == LINE:
                _kind, _first, s0, su, sv, eu, ev = piece
                s = col(s0) + more * col(p1)
                u, v = np.where(here, col(su) + s * col(eu), u), np.where(here, col(sv) + s * col(ev), v)
            else:
                _kind, _first, t0, qu, qv, rho, start, step = piece
                at = col(start) - (col(t0) + more * col(step))
                u, v = np.where(here, col(qu) + rho * np.sin(at), u), np.where(here, col(qv) - rho * np.cos(at), v)
        out[:, :, 0], out[:, :, 1] = u, v
        out[:, :, 2] = col(side) * np.maximum(i - col(kap), 0.0)
        end = out[:, -1, :]
        miss = np.sqrt((end[:, 0] - self.um) ** 2 + (end[:, 1] - self.vm) ** 2 + (end[:, 2] - self.wm) ** 2)
        return out, miss, th_end


def chain_pins(spec: ChainSpec, moving) -> Chain:
    """Where the pins are for the moving end(s) ``moving`` ((B, 3), or (3,) = one frame: B = 1; chain coordinates).

    Exact: pins[:, 0] is the origin, every pin is one pitch from the next, the pins of the bend lie on the circle
    of ``radius`` round (bend_u, radius), pins[:, -1] is the moving end – unless ``short`` (see the top of this
    file). A pure function of its arguments, continuous in ``moving``; rows do not influence each other.
    A radius under 0.55 × pitch is taken as 0.55 × pitch (``Chain.radius`` says what was used), a glide angle
    outside 1° … 60° as the nearer of the two.
    """
    moving = np.asarray(moving, dtype=float)
    if moving.ndim == 1:
        moving = moving[None, :]
    if moving.ndim != 2 or moving.shape[1] != 3:
        raise ValueError("moving must be (3,) or (B, 3)")
    bad = ~np.isfinite(moving).all(axis=1)
    if bad.any():
        moving = np.where(bad[:, None], 0.0, moving)
    w = _Walk(spec, moving)
    c = w.solve()
    pins, miss, th_end = w.pins(c)
    met = miss <= REACH_TOL * w.p
    pins[met, -1, :] = moving[met]
    # met, but no pose of a drag chain: the run after the bend would lie in or under the fixed run; pulled out
    # so far that less than a quarter of a turn is left of the bend (from there on the bend runs back and the
    # chain whips straight)
    odd = (moving[:, 1] <= 0.0) | (th_end < MIN_TURN)
    return Chain(pins, ~met | odd | bad, c, w.r)


# ---------------------------------------------------------------------------
# the links on their pins
# ---------------------------------------------------------------------------

def link_frames(pins):
    """The frame of every link on its two pins: (origin, x, z), each (..., links, 3) for pins (..., links + 1, 3).

    origin = pin i, x = the unit vector from pin i to pin i + 1, z = the unit vector square to x that is nearest
    to w = (0, 0, 1) (across the chain); y = z × x points from the fixed run towards the moving run.
    """
    pins = np.asarray(pins, dtype=float)
    origin = pins[..., :-1, :]
    x = pins[..., 1:, :] - origin
    length = np.linalg.norm(x, axis=-1, keepdims=True)
    x = np.where(length > 0.0, x / np.where(length > 0.0, length, 1.0), np.array([1.0, 0.0, 0.0]))
    z = np.array([0.0, 0.0, 1.0]) - x * x[..., 2:3]
    size = np.linalg.norm(z, axis=-1, keepdims=True)
    lost = size < 1e-9                                  # a link pointing straight across: any z square to it
    if lost.any():
        z = np.where(lost, np.array([0.0, 1.0, 0.0]) - x * x[..., 1:2], z)
        size = np.where(lost, np.linalg.norm(z, axis=-1, keepdims=True), size)
    return origin, x, z / size


def pin_matrices(pins) -> np.ndarray:
    """``link_frames`` as matrices (..., links, 4, 4): columns x, y = z × x, z, origin."""
    origin, x, z = link_frames(pins)
    out = np.zeros(origin.shape[:-1] + (4, 4))
    out[..., :3, 0], out[..., :3, 1], out[..., :3, 2], out[..., :3, 3] = x, np.cross(z, x), z, origin
    out[..., 3, 3] = 1.0
    return out


def link_matrices(pins, local, frame=None) -> np.ndarray:
    """Every link's matrix for a shape: ``frame @ pin_matrices(pins) @ local``, (..., links, 4, 4).

    ``pins`` in chain coordinates (``chain_pins(...).pins``), ``local`` from the fit, ``frame`` (4, 4) = chain
    coordinates → the coordinates wanted (the fit's ``frame`` moved along with the fixed part; None: stay in
    chain coordinates).
    """
    out = pin_matrices(pins) @ np.asarray(local, dtype=float)
    return out if frame is None else np.asarray(frame, dtype=float) @ out


# ---------------------------------------------------------------------------
# the chain read from its CAD pose
# ---------------------------------------------------------------------------

def _none(*shape):
    return field(default_factory=lambda: np.zeros(shape))


@dataclass
class ChainFit:
    ok: bool = False
    problem: str = ""                   # plain words: why it is not a chain; with ok: a note ('' = none)
    order: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))   # the given links, end A first
    frame: np.ndarray = field(default_factory=lambda: np.eye(4))    # chain coordinates → the given coordinates
    pins: np.ndarray = _none(0, 3)      # (links + 1, 3) the CAD pins in the given coordinates
    local: np.ndarray = _none(0, 4, 4)  # (links, 4, 4) each link's matrix in its pin frame, in chain order
    pitch: float = 0.0
    radius: float = 0.0
    links: int = 0
    moving: np.ndarray = _none(3)       # the moving end (the last pin) in chain coordinates
    mode: str = "STRAIGHT"
    residual: float = 0.0               # how well neighbouring links meet on their pins (RMS, a length)
    width: float = 0.0                  # fit_solid: the band across the chain
    height: float = 0.0                 # fit_solid: the thickness of one run
    pose_error: float = 0.0             # the furthest a CAD pin is from the shape chain_pins draws for this fit

    def spec(self) -> ChainSpec:
        return ChainSpec(self.pitch, self.links, self.radius, self.mode)

    def reversed(self) -> "ChainFit":
        """The same chain with the other end as the fixed one: order, pins, frame, local and moving again."""
        if not self.ok:
            return replace(self)
        note = self.problem.split(POSE_NOTE[:20])[0].strip()        # (the note on the pose is made again)
        mats = self.frame @ pin_matrices(self.pins_chain()) @ self.local if len(self.local) else None
        out = _from_pins(self.pins[::-1], None if mats is None else mats[::-1], self.order[::-1], self.residual,
                         note, known=(self.pitch, self.radius))
        out.width, out.height = self.width, self.height
        return out

    def pins_chain(self) -> np.ndarray:
        """The CAD pins in chain coordinates."""
        return (self.pins - self.frame[:3, 3]) @ self.frame[:3, :3]


def _unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n > 0.0, n, 1.0)


def _turns(pins):
    """Unit link directions, the plane's normal (None: no bend) and the signed turn at every inner pin."""
    x = _unit(np.diff(pins, axis=0))
    n = np.cross(x[:-1], x[1:])
    total = n.sum(axis=0)
    size = float(np.linalg.norm(total))
    if size < 1e-9:
        return x, None, np.zeros(len(n))
    w = total / size
    return x, w, np.arctan2(n @ w, np.einsum("ij,ij->i", x[:-1], x[1:]))


def _bend_turn(psi):
    """The turn of one link inside the bend, and whether the pose's numbers are exact.

    Inside the bend every pin turns by the same angle; where the chain goes onto the bend and leaves it, one or
    two pins turn by less. So it is the largest turn that counts: exact numbers have two or more pins that agree
    on it; with rounded or noisy numbers it is the middle one of the turns near the largest.
    """
    top = float(psi.max())
    for tol in (1e-9, 1e-7):
        near = psi[psi >= top * (1.0 - tol)]
        if len(near) >= 2:
            return float(near.mean()), True
    return float(np.median(psi[psi >= 0.8 * top])), False


def _straight_ends(psi, phi):
    """How many links at the start and at the end lie on a straight run (a link counts until it has turned a
    quarter of a link's turn in the bend away from the end link)."""
    limit = 0.25 * phi
    off = np.abs(np.cumsum(psi)) > limit
    lead = int(np.argmax(off)) + 1 if off.any() else len(psi) + 1
    off = np.abs(np.cumsum(psi[::-1])) > limit
    trail = int(np.argmax(off)) + 1 if off.any() else len(psi) + 1
    return lead, trail


def _mode(heading, moving, radius) -> str:
    """GLIDE when the moving run comes back and its end lies clearly lower than the top of the bend."""
    return "GLIDE" if heading < 0.0 and moving[1] < GLIDE_BELOW * 2.0 * radius else "STRAIGHT"


def _circle_radius(chain, psi):
    """The radius of the circle through the pins that turn like bend pins (least squares), or None."""
    on = np.nonzero(psi >= 0.8 * float(psi.max()))[0] + 1
    if len(on) < 3:
        return None
    u, v = chain[on, 0], chain[on, 1]
    sol, _res, rank, _sv = np.linalg.lstsq(np.stack([2.0 * u, 2.0 * v, np.ones(len(on))], axis=1), u * u + v * v,
                                           rcond=None)
    if rank < 3:
        return None
    return math.sqrt(max(float(sol[2] + sol[0] ** 2 + sol[1] ** 2), 0.0))


def _read_radius(chain, pitch, psi, phi, exact, moving, heading) -> float:
    """The bend radius of a chain from its pins (chain coordinates).

    First from the angle the links turn by in the bend. That is checked against the pose: the shape ``chain_pins``
    draws with it must lie on the CAD pins. Exact numbers that do are done. Else other readings are tried (half
    the distance between the runs when they are parallel, the circle through the bend's pins), and with rounded
    or noisy numbers the radius near the best of them that draws the CAD pose best (all pins weigh in, so 0.1 mm
    of noise costs under 1 %).
    """
    links = len(chain) - 1

    def miss(radius):                                   # (RMS, largest) distance of the drawn pins from the CAD's
        if not radius >= MIN_RADIUS * pitch:
            return math.inf, math.inf
        drawn = chain_pins(ChainSpec(pitch, links, radius, _mode(heading, moving, radius)), moving).pins[0]
        dist = np.linalg.norm(drawn - chain, axis=1)
        return float(np.sqrt(np.mean(dist * dist))), float(dist.max())

    first = pitch / (2.0 * math.sin(0.5 * phi))
    first_miss = miss(first)
    if exact and first_miss[1] <= POSE_TOL * pitch:
        return first
    tried = {first: first_miss}
    if heading < -0.999:
        tried[0.5 * float(moving[1])] = miss(0.5 * float(moving[1]))
    circle = _circle_radius(chain, psi)
    if circle is not None:
        tried[circle] = miss(circle)
    best = min(tried, key=lambda radius: tried[radius][0])
    if exact:                                           # exact numbers, drawn another way: only a clear gain counts
        return best if tried[best][1] < 0.5 * first_miss[1] else first
    # golden section to a per mille, then the lowest point of a parabola through three radii (twice)
    lo, hi = 0.9 * best, 1.1 * best
    g = 0.5 * (math.sqrt(5.0) - 1.0)
    a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    miss_a, miss_b = miss(a)[0], miss(b)[0]
    for _ in range(10):
        if miss_a < miss_b:
            hi, b, miss_b = b, a, miss_a
            a = hi - g * (hi - lo)
            miss_a = miss(a)[0]
        else:
            lo, a, miss_a = a, b, miss_b
            b = lo + g * (hi - lo)
            miss_b = miss(b)[0]
    fine, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
    for _ in range(2):
        under, at, over = miss(fine - half)[0] ** 2, miss(fine)[0] ** 2, miss(fine + half)[0] ** 2
        curve = under - 2.0 * at + over
        move = 0.5 * half * (under - over) / curve if curve > 0.0 else 0.0
        move = min(max(move, -half), half)
        fine, half = fine + move, max(abs(move), 0.05 * half)
    fine_miss = miss(fine)
    return fine if fine_miss[0] < tried[best][0] and fine_miss[1] <= POSE_TOL * pitch else best


def _from_pins(pins, mats, order, residual, note, known=None) -> ChainFit:
    """The chain from its pins in order (end A first): plane, runs, pitch, radius, frame, the links' places."""
    pins = np.asarray(pins, dtype=float)
    links = len(pins) - 1
    pitch = float(np.median(np.linalg.norm(np.diff(pins, axis=0), axis=1)))
    x, w, psi = _turns(pins)
    if w is None or float(psi.sum()) < math.radians(30.0) or float(psi.max()) < 1e-6:
        return ChainFit(False, "The chain is drawn straight: it has no bend to read the bend radius from. "
                               "Set the bend radius by hand.", pitch=pitch, links=links, residual=residual)
    phi, exact = _bend_turn(psi)
    lead, trail = _straight_ends(psi, phi)
    # all on the bend - or nearly, with pins that are only guessed from the centres (``note``)
    if known is None and lead == 1 and trail == 1 and (note or min(abs(psi[0]), abs(psi[-1])) > 0.5 * phi):
        return ChainFit(False, "Too few links lie off the bend to read the chain: it needs links on a straight run "
                               "as well as on the bend.", pitch=pitch, links=links, residual=residual)
    # the last link counted as straight may already lean onto the bend a little: leave it out
    u = _unit(pins[max(lead - 1, 1)] - pins[0])
    if lead == 1 and abs(psi[0]) > 0.5 * phi:       # no straight run at this end: the circle's tangent at pin 0
        half = 0.5 * phi
        u = _unit(u * math.cos(half) - np.cross(w, u) * math.sin(half))
    w = _unit(w - u * float(w @ u))
    v = np.cross(w, u)
    frame = np.eye(4)
    frame[:3, 0], frame[:3, 1], frame[:3, 2], frame[:3, 3] = u, v, w, pins[0]
    chain = (pins - pins[0]) @ frame[:3, :3]
    moving = chain[-1].copy()
    heading = float(x[-1] @ u)                      # -1: the moving run comes straight back along the fixed run
    if known is not None:
        pitch, radius = known
    else:
        radius = _read_radius(chain, pitch, psi, phi, exact, moving, heading)
    local = np.zeros((0, 4, 4))
    if mats is not None:
        local = np.linalg.inv(frame @ pin_matrices(chain)) @ np.asarray(mats, dtype=float)
    fit = ChainFit(True, note, np.asarray(order, dtype=int).copy(), frame, pins.copy(), local, pitch, radius,
                   links, moving, _mode(heading, moving, radius), residual)
    drawn = chain_pins(fit.spec(), moving)
    fit.pose_error = float(np.linalg.norm(drawn.pins[0] - chain, axis=1).max())
    if fit.pose_error > POSE_TOL * pitch:
        fit.problem = (note + " " if note else "") + POSE_NOTE % (fit.pose_error / pitch)
    return fit


def _rotations(mats):
    """The turning part of each matrix, without its scale."""
    rot = mats[:, :3, :3]
    det = np.abs(np.linalg.det(rot))
    return rot / np.cbrt(np.where(det > 0.0, det, 1.0))[:, None, None]


def _order(centres, rot, use_turn: bool):
    """Links of one kind in order along the chain (indices), or None when they are not one chain.

    Neighbours are the nearest links; with ``use_turn`` a link that is turned differently counts as further away
    (0.7 spacings per radian), which keeps the two runs of a chain apart when one lies on the other.
    """
    k = len(centres)
    gap = np.linalg.norm(centres[:, None, :] - centres[None, :, :], axis=2)
    metric = gap.copy()
    np.fill_diagonal(metric, np.inf)
    if use_turn:
        cos = (np.einsum("iab,jab->ij", rot, rot) - 1.0) * 0.5
        angle = np.arccos(np.minimum(np.maximum(cos, -1.0), 1.0))
        for _ in range(2):
            spacing = float(np.median(metric.min(axis=1)))
            metric = np.sqrt(gap * gap + (TURN_WEIGHT * spacing * angle) ** 2)
            np.fill_diagonal(metric, np.inf)
    if not np.isfinite(metric.min(axis=1)).all():
        return None
    # two links are neighbours when each is among the other's two nearest; the ends have one neighbour
    two = np.argsort(metric, axis=1)[:, :2]
    near = np.zeros((k, k), dtype=bool)
    near[np.arange(k)[:, None], two] = True
    near &= near.T
    ends = np.nonzero(near.sum(axis=1) == 1)[0]
    if len(ends) != 2 or near.sum(axis=1).max() > 2:
        return None
    order, last = [int(ends[0])], -1
    while len(order) < k:
        step = [int(j) for j in np.nonzero(near[order[-1]])[0] if j != last]
        if len(step) != 1:
            return None                             # the chain stops early: these are several chains
        last = order[-1]
        order.append(step[0])
    steps = gap[order[:-1], order[1:]]
    if steps.min() <= 0.0 or steps.max() > 1.5 * float(np.median(steps)):
        return None                                 # a link missing in between, or links of two chains
    return np.array(order)


def open_row(matrices, centres=None) -> bool:
    """Do these links (one kind) lie in one open row with two ends, as a drag chain's do? A chain that runs round in
    a loop (a roller chain on its sprockets, a track) has no end and is not one. ``matrices`` (K, 4, 4), ``centres``
    (K, 3) (default: the matrices' places)."""
    m = np.asarray(matrices, dtype=float)
    if m.ndim != 3 or m.shape[0] < 3:
        return False
    c = m[:, :3, 3] if centres is None else np.asarray(centres, dtype=float)
    return _order(c, m[:, :3, :3], True) is not None


def _order_kinds(centres, rot, kind):
    """All links in order when there are several kinds (inner and outer links, end pieces).

    How two different meshes are turned says nothing, so the most common kind is put in order first (as above);
    every other link then goes into the gap between two of those (or beyond an end) that its centre is nearest to.
    """
    k = len(centres)
    main = np.nonzero(kind == np.argmax(np.bincount(kind)))[0]
    if len(main) == k:
        return _order(centres, rot, True)
    if len(main) < 4:
        return None
    sub = _order(centres[main], rot[main], True)
    if sub is None:
        return None
    main = main[sub]
    cm = centres[main]
    step = np.vstack([cm[1:2] - cm[0:1], cm[1:] - cm[:-1], cm[-1:] - cm[-2:-1]])       # along the chain at each gap
    slots = np.vstack([cm[0:1] - 0.5 * step[0:1], 0.5 * (cm[:-1] + cm[1:]), cm[-1:] + 0.5 * step[-1:]])
    rest = np.nonzero(~np.isin(np.arange(k), main))[0]
    slot = np.argmin(np.linalg.norm(centres[rest][:, None, :] - slots[None, :, :], axis=2), axis=1)
    along = np.einsum("ij,ij->i", centres[rest] - slots[slot], step[slot])
    order = []
    for j in range(len(main) + 1):
        here = np.nonzero(slot == j)[0]
        order.extend(int(i) for i in rest[here[np.argsort(along[here], kind="stable")]])
        if j < len(main):
            order.append(int(main[j]))
    return np.array(order)


def _pins_of_links(mats, rot, centres, kind):
    """The pins of links in chain order from "a link's front pin is the next link's rear pin".

    Unknown per kind of link: its rear pin a and front pin b in its own coordinates. Returns (pins, residual,
    sound): sound is False when the links' poses do not pin the points down (every pair of neighbours stands the
    same way to each other: all in a row, or all in the bend).
    """
    k = len(mats)
    turn, pos = mats[:, :3, :3], mats[:, :3, 3] - mats[:, :3, 3].mean(axis=0)
    kinds = int(kind.max()) + 1
    # a link placed the other way round: the chain runs backwards through it, seen in its own coordinates
    along = np.empty((k, 3))
    along[1:-1], along[0], along[-1] = centres[2:] - centres[:-2], centres[1] - centres[0], centres[-1] - centres[-2]
    own = np.einsum("iba,ib->ia", rot, along)
    flipped = np.zeros(k, dtype=bool)
    for t in range(kinds):
        same = np.nonzero(kind == t)[0]
        if len(same):
            flipped[same] = own[same] @ own[same[0]] < 0.0
    rear = 2 * kind + flipped                       # which unknown point is each link's rear / front pin
    front = 2 * kind + (1 - flipped)
    a_mat = np.zeros((3 * (k - 1), 6 * kinds))
    group = list(range(2 * kinds))                  # points that meet on a pin belong together

    def root(i):
        while group[i] != i:
            i = group[i]
        return i

    used = np.zeros(2 * kinds, dtype=bool)
    for i in range(k - 1):
        rows, f, r = slice(3 * i, 3 * i + 3), 3 * int(front[i]), 3 * int(rear[i + 1])
        a_mat[rows, f:f + 3] += turn[i]
        a_mat[rows, r:r + 3] -= turn[i + 1]
        group[root(int(front[i]))] = root(int(rear[i + 1]))
        used[front[i]] = used[rear[i + 1]] = True
    rhs = (pos[1:] - pos[:-1]).reshape(-1)
    sol, _res, rank, _sv = np.linalg.lstsq(a_mat, rhs, rcond=1e-9)
    groups = len({root(i) for i in range(2 * kinds) if used[i]})
    sound = rank >= 3 * int(used.sum()) - groups    # all but each group's place along the pins' own axis
    point = lambda i, at: turn[i] @ sol[3 * at[i]:3 * at[i] + 3] + mats[i, :3, 3]      # noqa: E731
    fronts = np.array([point(i, front) for i in range(k)])
    rears = np.array([point(i, rear) for i in range(k)])
    pins = np.vstack([rears[:1], 0.5 * (fronts[:-1] + rears[1:]), fronts[-1:]])
    residual = float(np.sqrt(np.mean(np.sum((fronts[:-1] - rears[1:]) ** 2, axis=1))))
    # along the pins' axis every group of points is free: put all pins in the plane of the links' centres
    of_pin = np.array([root(int(rear[0]))] + [root(int(f)) for f in front])
    axis = np.zeros(3)
    for t in range(kinds):                          # the axis: how each link is turned from the last one of its kind
        same = np.nonzero((kind == t) & ~flipped)[0]
        q = np.einsum("iab,icb->iac", rot[same[1:]], rot[same[:-1]])
        axis += np.array([q[:, 2, 1] - q[:, 1, 2], q[:, 0, 2] - q[:, 2, 0], q[:, 1, 0] - q[:, 0, 1]]).sum(axis=1)
    if np.linalg.norm(axis) < 1e-6:
        axis = _turns(centres)[1]
    if axis is not None:
        axis = _unit(axis)
        level = float(np.mean(centres @ axis))
        for g in set(of_pin.tolist()):
            mine = of_pin == g
            pins[mine] -= axis * (float(np.mean(pins[mine] @ axis)) - level)
    # an end piece of a kind of its own: nothing says where its outer pin is. Straight on from its neighbour, one
    # pitch from its inner pin - the piece then sits rigidly on its inner pin and a straight run stays straight.
    if not used[rear[0]]:
        pins[0] = 2.0 * pins[1] - pins[2]
    if not used[front[-1]]:
        pins[-1] = 2.0 * pins[-2] - pins[-3]
    return pins, residual, bool(sound)


def _pins_between(centres):
    """Fallback pins: half-way between neighbouring centres, the two ends as far out again."""
    mid = 0.5 * (centres[:-1] + centres[1:])
    return np.vstack([2.0 * centres[0] - mid[0], mid, 2.0 * centres[-1] - mid[-1]])


def fit_links(matrices, centres=None, types=None) -> ChainFit:
    """What chain a set of CAD links is, from the pose it is drawn in.

    ``matrices`` (K, 4, 4): the link objects' matrices in any common coordinates, in any order. ``centres``
    (K, 3): the links' mesh centres in the same coordinates (default: the matrices' origins). ``types`` (K,)
    ints: the same number = the same mesh (default: all the same).

    The fit puts every link rigidly on its two pins: for any later shape,
    ``frame_now @ pin_matrices(chain_pins(fit.spec(), moving).pins[b]) @ fit.local`` (``link_matrices``) are the
    links' matrices, in the order ``fit.order``. End A (the fixed end) is the end whose straight run is the
    longer one in the CAD pose (equal: the end with the lower link index); ``reversed()`` gives the other choice.
    Across the chain the pins lie in the plane of the links' centres. Several kinds of links are fine (inner and
    outer links by turns, end pieces of their own: an end piece's outer "pin" is taken one pitch straight on
    from its neighbour). A link placed the other way round (turned end for end) is understood for a chain of one
    kind of link whose runs do not lie on each other.

    ``pitch`` = the median pin distance. ``radius`` from the angle the links turn by inside the bend
    (pitch / (2 sin(angle / 2)): the largest turns count, the pins where the chain goes onto and off the bend
    turn by less). It is checked against the pose: exact numbers whose shape lies on the CAD pins are done (exact
    with four or more pins on the bend). Else half the distance between the runs (when they are parallel) and
    the circle through the bend's pins are tried too, and with rounded or noisy numbers (an exported file, 32-bit
    matrices) the radius near the best of them that draws the CAD pose best is taken: numbers rounded to
    0.01 mm give the radius to 0.02 %, 0.1 mm of noise to 0.5 % (40 chains each, one and two kinds of link).
    ``mode`` is GLIDE when the moving run comes back clearly lower than 2 × radius. ``pose_error`` says how far
    the shape ``chain_pins`` draws for the fit is from the CAD pose (0 for a chain drawn the way this file
    draws it).

    ``ok`` False with ``problem`` in plain words: fewer than 4 links, the links are not one chain, the chain is
    drawn straight (then ``pitch`` and ``links`` are still filled in), or too few links lie off the bend to read
    it. ``ok`` True with a note in ``problem``: the links do not hinge on common pins (or the pose does not show
    where the pins are: a chain needs links on a straight run and links on the bend for that), so they are
    placed by their centres; and / or the app draws the chain more than a quarter of a link away from where the
    CAD file has it (``pose_error``; the chain is drawn another way than this file does it, or it was not read
    right).
    """
    mats = np.asarray(matrices, dtype=float)
    if mats.ndim != 3 or mats.shape[1:] != (4, 4):
        raise ValueError("matrices must be (K, 4, 4)")
    k = len(mats)
    if k < 4:
        return ChainFit(False, "A drag chain needs at least 4 links.", links=k)
    centres = mats[:, :3, 3].copy() if centres is None else np.asarray(centres, dtype=float).reshape(k, 3)
    kind = np.zeros(k, dtype=int) if types is None else np.unique(np.asarray(types).reshape(k), return_inverse=True)[1]
    kind = kind.reshape(k)
    if not (np.isfinite(mats).all() and np.isfinite(centres).all()):
        return ChainFit(False, "The links' places could not be read.", links=k)
    rot = _rotations(mats)
    best = None
    for by_turn in (True, False):
        order = _order_kinds(centres, rot, kind) if by_turn else _order(centres, rot, False)
        if order is None:
            continue
        pins, residual, sound = _pins_of_links(mats[order], rot[order], centres[order], kind[order])
        chords = np.linalg.norm(np.diff(pins, axis=0), axis=1)
        pitch = float(np.median(chords))
        spacing = float(np.median(np.linalg.norm(np.diff(centres[order], axis=0), axis=1)))
        mid = 0.5 * (pins[:-1] + pins[1:])
        good = (sound and pitch > 0.0 and residual <= FIT_TOL * pitch and
                np.abs(chords - pitch).max() <= CHORD_TOL * pitch and
                np.linalg.norm(mid - centres[order], axis=1).max() <= 2.0 * max(spacing, pitch))
        if good:
            best = (order, pins, residual, "")
            break
        if best is None:
            best = (order, _pins_between(centres[order]), residual,
                    "The links do not hinge on common pins: they are placed by their centres.")
    if best is None:
        return ChainFit(False, "These parts are not one chain: its links follow each other at even distances "
                               "from one end to the other.", links=k)
    order, pins, residual, note = best
    fit = _from_pins(pins, mats[order], order, residual, note)
    if fit.ok:
        _x, _w, psi = _turns(pins)
        lead, trail = _straight_ends(psi, _bend_turn(psi)[0])
        if trail > lead or (trail == lead and order[-1] < order[0]):
            fit = _from_pins(pins[::-1], mats[order[::-1]], order[::-1], residual, note)
    return fit


def fit_solid(verts, pitch: float | None = None) -> ChainFit:
    """A chain drawn as one solid – a band of constant width bent into a U: two straight runs and half a turn.

    ``verts`` (V, 3) the solid's mesh points. Returns the bend radius (to the band's middle), ``height`` (the
    band's thickness), ``width``, a pitch (``pitch``, else about 1.6 × height) and how many links of that pitch
    the band is long; ``frame`` and ``moving`` as for ``fit_links`` (the fixed end = the longer run), ``pins`` =
    the shape ``chain_pins`` draws for it, ``local`` empty. ``residual`` = how far the points are from a clean
    U band (RMS). Anything else (a block, a band with a different bend, runs that are too short to see) is not
    guessed at: ``ok`` False with the reason.
    """
    pts = np.asarray(verts, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 16 or not np.isfinite(pts).all():
        return ChainFit(False, "The part has too few points to read a drag chain from.")
    mid = pts.mean(axis=0)
    rel = pts - mid
    _val, vec = np.linalg.eigh(rel.T @ rel)

    def on_faces(axis):
        t = rel @ axis
        lo, hi = float(t.min()), float(t.max())
        tol = 0.02 * (hi - lo)
        return float(np.mean((t - lo < tol) | (hi - t < tol))), t, lo, hi

    # across the chain the band is the same everywhere: all its points lie on its two side faces
    share, t, lo, hi = max((on_faces(vec[:, i]) for i in range(3)), key=lambda item: item[0])
    top = rel[t > 0.5 * (lo + hi)]
    if share >= 0.5 and len(top) >= 3:                              # the exact direction: square to one side face
        w = np.linalg.svd(top - top.mean(axis=0), full_matrices=False)[2][2]
        share, t, lo, hi = on_faces(w)
    if share < 0.9 or hi - lo <= 0.0:
        return ChainFit(False, "The part is not a band of one width, so it cannot be read as a drag chain.")
    width = hi - lo
    e1 = _unit(np.cross(w, vec[:, int(np.argmin(np.abs(vec.T @ w)))]))
    e2 = np.cross(w, e1)
    flat = np.stack([rel @ e1, rel @ e2], axis=1)

    def across(angle):                                              # the band's extent square to this direction
        s = flat @ np.array([-math.sin(angle), math.cos(angle)])
        return float(s.max() - s.min())

    # the runs lie along the direction in which the band is narrowest across
    angles = np.linspace(0.0, math.pi, 360, endpoint=False)
    best = float(angles[int(np.argmin([across(a) for a in angles]))])
    a, b = best - math.pi / 360.0, best + math.pi / 360.0
    g = 0.5 * (math.sqrt(5.0) - 1.0)
    for _ in range(60):
        c, d = b - g * (b - a), a + g * (b - a)
        a, b = (a, d) if across(c) < across(d) else (c, b)
    angle = 0.5 * (a + b)
    du = np.array([math.cos(angle), math.sin(angle)])
    dv = np.array([-du[1], du[0]])
    su, sv = flat @ du, flat @ dv
    total = float(sv.max() - sv.min())
    v_mid = 0.5 * float(sv.max() + sv.min())
    middle = np.abs(sv - v_mid) < 0.15 * total                     # only the bend has points half-way up
    if total <= 0.0 or not middle.any():
        return ChainFit(False, "No bend found: the part is not a U-shaped drag chain.")
    if float(np.median(su[middle])) < 0.5 * float(su.max() + su.min()):
        su, du = -su, -du                                           # the bend at +u
    centre_u = float(su.max()) - 0.5 * total
    runs = su < centre_u - 0.05 * total
    low, high = runs & (sv < v_mid), runs & (sv > v_mid)
    if not (low.any() and high.any()):
        return ChainFit(False, "The chain's two straight runs are too short to read.")
    h_low, h_high = float(sv[low].max() - sv.min()), float(sv.max() - sv[high].min())
    height = 0.5 * (h_low + h_high)
    if abs(h_low - h_high) > 0.05 * total or not (0.0 < height < 0.45 * total):
        return ChainFit(False, "The part is not a band of one thickness bent into a U.")
    radius = 0.5 * (total - height)
    end_low, end_high = float(su[low].min()), float(su[high].min())
    # how far every point is from a clean U band's outline (its faces, the two arcs, the two end faces)
    r_pt = np.hypot(su - centre_u, sv - v_mid)
    off = np.minimum(np.abs(r_pt - 0.5 * total), np.abs(r_pt - 0.5 * total + height))
    off = np.where(su >= centre_u, off, np.inf)
    for level in (sv.min(), sv.min() + height, sv.max() - height, sv.max()):
        off = np.minimum(off, np.where(su <= centre_u + 1e-6 * total, np.abs(sv - level), np.inf))
    off = np.minimum(off, np.where(sv < v_mid, np.abs(su - end_low), np.abs(su - end_high)))
    if float(np.mean(off < 0.02 * total)) < 0.95:
        return ChainFit(False, "The part is not two straight runs and one bend: it cannot be read as a drag chain.")
    residual = float(np.sqrt(np.mean(np.minimum(off, 0.02 * total) ** 2)))
    fixed_low = (centre_u - end_low) >= (centre_u - end_high)
    end_fixed, end_moving = (end_low, end_high) if fixed_low else (end_high, end_low)
    v_fixed = float(sv.min()) + 0.5 * height if fixed_low else float(sv.max()) - 0.5 * height
    if not fixed_low:
        dv = -dv
    u3, v3 = du[0] * e1 + du[1] * e2, dv[0] * e1 + dv[1] * e2
    w3 = np.cross(u3, v3)
    frame = np.eye(4)
    frame[:3, 0], frame[:3, 1], frame[:3, 2] = u3, v3, w3
    origin2 = end_fixed * du + (v_fixed if fixed_low else -v_fixed) * dv
    frame[:3, 3] = mid + origin2[0] * e1 + origin2[1] * e2 + 0.5 * (lo + hi) * w
    length = (centre_u - end_fixed) + math.pi * radius + (centre_u - end_moving)
    if pitch is None:
        pitch = min(PITCH_PER_HEIGHT * height, radius / 0.75)
    pitch = float(pitch)
    if not (0.0 < pitch <= radius / MIN_RADIUS):
        return ChainFit(False, "The link length is too long for this chain's bend.", radius=radius, width=width,
                        height=height)
    links = int(round(length / pitch))
    if links < 4:
        return ChainFit(False, "The chain is too short for links of this length.", pitch=pitch, radius=radius,
                        width=width, height=height)
    moving = np.array([end_moving - end_fixed, 2.0 * radius, 0.0])
    fit = ChainFit(True, "", np.zeros(0, dtype=int), frame, np.zeros((0, 3)), np.zeros((0, 4, 4)), pitch, radius,
                   links, moving, "STRAIGHT", residual, width, height)
    drawn = chain_pins(fit.spec(), moving)
    if bool(drawn.short[0]):
        return ChainFit(False, "The chain's two straight runs are too short to read.", pitch=pitch, radius=radius,
                        width=width, height=height)
    fit.pins = drawn.pins[0] @ frame[:3, :3].T + frame[:3, 3]
    return fit
