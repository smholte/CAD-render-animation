"""Spooling: a rope on a winch drum, a cable on a carousel, layer by layer, without Blender (task 0080).

**The spool frame.** The origin lies on the spool's axis and local **z is the axis**. A point of the rope's middle line
is ``(r cos phi, r sin phi, a)``: ``r`` its distance from the axis, ``phi`` its angle round it and ``a`` its place along
it. Metres and radians, NumPy only.

**The wound path.** The rope on a full spool is one path from its anchor (``L = 0``, the innermost turn) to its outer
end (``L = total``), laid layer by layer. The path is a list of **pieces**; in each piece ``phi``, ``a`` and ``r`` are
linear in one number ``u`` that runs from 0 to 1 (a helix, an Archimedean spiral, a climb), and ``L`` is the true
length along it (Gauss-Legendre; inside a piece whose radius changes, ``u`` is found from ``L`` by Newton), so ``L`` is
the rope's length to within 1e-9. On a helix ``phi`` is exactly linear in ``L``; pieces whose radius changes are cut
so small (the radius changes by at most 0.25 % in one) that ``phi`` is linear in ``L`` there to about 1e-5 rad.
``hand`` (+1 / -1): ``phi`` grows (+1) or shrinks (-1) as ``L`` grows – the whole rope is wound the same way round;
the place along the axis goes back and forth.

*Drum* (``kind="DRUM"``): layer k has its rope's middle at ``r1 + k * d * cos 30°`` (each layer lies in the grooves
the one below leaves). The rope's middle runs from ``a_lo + d/2`` to ``a_hi - d/2``: a layer is one helix piece with
``(a_hi - a_lo - d) / pitch`` turns (a real number: the layer fills from flange to flange). Layer 0 starts at the
``start`` side (+1: at ``a_lo``), the next layer runs back. Between two layers a **climb** at the flange: ``a``
stays, ``r`` rises from one layer to the next over ``climb`` of turn (default 90°), in small pieces (``SHARE``).
Layers are laid while their radius is at most ``r_max`` (and at most ``layers`` of them).

*Lebus* (``groove="LEBUS"``): in a layer the rope runs parallel to the flanges (``a`` stays) and moves over by half a
pitch in two **crossover** zones per turn, each ``crossover`` wide (default 35°), the first starting at the drum angle
``crossover_at``, the second half a turn later. The zones are fixed on the drum, so every layer crosses over in the
same places. Pieces: parallel, crossover, parallel, crossover …; the layer ends where it has moved over by the width.

*Carousel* (``kind="CAROUSEL"``): flat layers, layer k with its rope's middle at ``a = a_bot + d/2 + k * d``; in a
layer an Archimedean spiral from ``r_in + d/2`` to ``r_out - d/2`` (layer 0 from the inside out when ``start`` is +1)
or back, the radius changing by ``d`` per turn. Spiral pieces are at most ``min(10°, SPIRAL_SHARE * pi * r / d)`` of
turn each, so that the turn per metre is right to 0.1 % everywhere. The climb to the next layer takes the first
``climb`` of the next layer's spiral (``r`` keeps changing as the spiral does, ``a`` rises by ``d``), so that every
layer covers exactly the ring between the rope's innermost and outermost middle: a stack of k layers then holds the
volume of a ring of that width and ``k * d`` high (``ring_volume``).

A climb piece belongs to the layer it climbs **from** (``Path.layer``). ``layer_start(path, k)`` is where the climb
into layer k begins (the end of layer k - 1's own pieces).

**Paying out.** With ``W0`` metres wound at the start and ``p`` metres paid out, the rope on the spool is the path from
0 to ``W0 - p``; its end there is the **leave point**. The spool turns by

    theta(p) = (psi(p) - psi(0)) - (phi(W0 - p) - phi(W0))

about +z (``angle_table``, ``exact_angle``): ``psi`` is the world angle at which the rope leaves the spool (0 when the
place the rope goes to does not move round the axis, see ``tangency``). Between two neighbouring ``breaks`` (the
payouts where a piece of the path begins or ends) ``phi(W0 - p)`` is linear (exactly on a helix, to about 1e-5 rad on
the other pieces), so a table with a key at every break is right for a fixed ``psi``.

**Drawing** (``polyline``): points so that the straight lines between them stay within ``sag`` of the true path, and so
that the straight distance between two neighbours equals their difference in ``L`` (to 1e-9): a curve trimmed by its
length then ends exactly at the leave point. Every second point lies on the path; the points between are moved out a
little (about ``r * step^2 / 12``), onto the circle of points that lie the right distances from both neighbours.

**The stack** (``stack``): only the top layers are drawn as rope, the full layers below as one solid (a drum: a
sleeve with the outer radius of the top full layer; a carousel: a ring as high as the full layers).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

COS30 = math.cos(math.radians(30.0))
SPIRAL_MAX = math.radians(10.0)     # rad: a carousel spiral piece turns at most this much …
SPIRAL_SHARE = 0.0025               # … and at most SPIRAL_SHARE * pi * r / d (the radius changes by 0.125 %)
SHARE = 0.0025                      # a drum's climb: pieces in which the radius changes by at most this share
_GAUSS = np.polynomial.legendre.leggauss(20)    # nodes and weights for a piece's length
_TINY = 1e-12                       # m / rad: shorter than this is nothing

DRUM, CAROUSEL = "DRUM", "CAROUSEL"
SPIRAL, LEBUS = "SPIRAL", "LEBUS"
# the kinds of pieces (Path.kind)
HELIX = "HELIX"             # a drum layer in a spiral groove
PARALLEL = "PARALLEL"       # Lebus: the rope runs square to the axis
CROSSOVER = "CROSSOVER"     # Lebus: the rope moves over by half a pitch
CLIMB = "CLIMB"             # from one layer to the next
FLAT = "FLAT"               # a carousel layer's spiral


@dataclass
class Spool:
    """The numbers of one spool, metres and radians. A drum uses ``r1, a_lo, a_hi, pitch, r_max, groove, crossover,
    crossover_at``; a carousel ``r_in, r_out, a_bot, a_top``; both ``d, start, hand, climb, layers``."""
    kind: str                       # DRUM | CAROUSEL
    d: float                        # the rope's (cable's) diameter
    # drum
    r1: float = 0.0                 # the rope's middle in layer 0 (barrel radius + d/2)
    a_lo: float = 0.0               # the inner faces of the two flanges along the axis
    a_hi: float = 0.0
    pitch: float | None = None      # the groove's pitch (None: d)
    r_max: float = math.inf         # layers while the rope's middle is at most this far out
    groove: str = SPIRAL            # SPIRAL | LEBUS
    crossover: float = math.radians(35.0)   # Lebus: the width of a crossover zone (turn)
    crossover_at: float = 0.0       # Lebus: the drum angle where the first crossover zone starts
    # carousel
    r_in: float = 0.0               # the coil's inside (the core) and outside (the rim) radius
    r_out: float = 0.0
    a_bot: float = 0.0              # the turntable's top: the bottom of layer 0
    a_top: float = math.inf         # the coil may not be higher than this
    # both
    start: int = 1                  # drum +1: layer 0 from a_lo; carousel +1: layer 0 from the inside out
    hand: int = 1                   # +1: phi grows with L (the rope is wound about +z)
    climb: float = math.pi / 2      # turn taken to climb from one layer to the next
    layers: int | None = None       # at most this many layers (None: as many as r_max / a_top allow)


@dataclass
class Path:
    """The wound path, one row per piece: phi, a and r are linear in u (0 … 1), L is the length along it."""
    L0: np.ndarray
    L1: np.ndarray
    phi0: np.ndarray
    phi1: np.ndarray
    a0: np.ndarray
    a1: np.ndarray
    r0: np.ndarray
    r1: np.ndarray
    layer: np.ndarray       # int: the layer the piece belongs to (a climb: the layer it climbs from)
    kind: np.ndarray        # str: HELIX, PARALLEL, CROSSOVER, CLIMB, FLAT
    total: float            # the whole length: a full spool
    spool: Spool

    @property
    def layer_count(self) -> int:
        return int(self.layer.max()) + 1


# ---------------------------------------------------------------------------------------------------------
# building the path
# ---------------------------------------------------------------------------------------------------------

def _check(spool: Spool) -> None:
    def bad(text):
        raise ValueError(text)
    if spool.kind not in (DRUM, CAROUSEL):
        bad(f"A spool is a drum or a carousel, not '{spool.kind}'.")
    numbers = [spool.d, spool.climb]
    if not all(math.isfinite(x) for x in numbers) or spool.d <= 0.0:
        bad("The rope's diameter must be a number above 0.")
    if spool.climb < 0.0:
        bad("The turn to climb to the next layer cannot be less than nothing.")
    if spool.hand not in (1, -1) or spool.start not in (1, -1):
        bad("Hand and start are +1 or -1.")
    if spool.layers is not None and spool.layers < 1:
        bad("A spool needs at least one layer.")
    if spool.kind == DRUM:
        pitch = spool.d if spool.pitch is None else spool.pitch
        if not math.isfinite(pitch) or pitch <= 0.0:
            bad("The groove's pitch must be a number above 0.")
        if spool.a_hi - spool.a_lo - spool.d <= _TINY:
            bad("The drum is narrower between its flanges than one rope.")
        if spool.r1 <= 0.0:
            bad("The rope's first layer must lie outside the axis.")
        if spool.r1 > spool.r_max:
            bad("The drum's first layer already lies beyond the largest radius allowed.")
        if spool.layers is None and not math.isfinite(spool.r_max):
            bad("A drum needs a largest radius or a number of layers.")
        if spool.groove not in (SPIRAL, LEBUS):
            bad(f"A drum's groove is spiral or Lebus, not '{spool.groove}'.")
        if spool.groove == LEBUS and not (0.0 < spool.crossover < math.pi):
            bad("A Lebus crossover zone is more than 0° and less than 180° wide.")
    else:
        if spool.r_out - spool.r_in - spool.d <= _TINY or spool.r_in < 0.0:
            bad("The carousel's coil is narrower than one cable.")
        if spool.a_top - spool.a_bot < spool.d - _TINY:
            bad("The carousel has no room for one layer.")
        if spool.layers is None and not math.isfinite(spool.a_top):
            bad("A carousel needs a top or a number of layers.")


def _drum_layers(spool: Spool) -> int:
    step = spool.d * COS30
    n = int(math.floor((spool.r_max - spool.r1) / step + 1e-9)) + 1 if math.isfinite(spool.r_max) else 10**9
    if spool.layers is not None:
        n = min(n, spool.layers)
    return n


def _carousel_layers(spool: Spool) -> int:
    n = int(math.floor((spool.a_top - spool.a_bot) / spool.d + 1e-9)) if math.isfinite(spool.a_top) else 10**9
    if spool.layers is not None:
        n = min(n, spool.layers)
    return n


class _Pieces:
    """Collects pieces one after another; phi is carried on (a piece is given by its turn)."""

    def __init__(self):
        self.rows = []          # (dphi, a0, a1, r0, r1, layer, kind)

    def add(self, dphi, a0, a1, r0, r1, layer, kind):
        if abs(dphi) < _TINY and abs(a1 - a0) < _TINY and abs(r1 - r0) < _TINY:
            return
        self.rows.append((dphi, a0, a1, r0, r1, layer, kind))

    def path(self, spool: Spool) -> Path:
        dphi, a0, a1, r0, r1, layer, kind = (np.array(c) for c in zip(*self.rows))
        phi1 = np.cumsum(dphi.astype(np.float64))
        phi0 = np.concatenate([[0.0], phi1[:-1]])
        length = _length(dphi, a1 - a0, r0, r1)
        L1 = np.cumsum(length)
        L0 = np.concatenate([[0.0], L1[:-1]])
        return Path(L0=L0, L1=L1, phi0=phi0, phi1=phi1, a0=a0.astype(np.float64), a1=a1.astype(np.float64),
                    r0=r0.astype(np.float64), r1=r1.astype(np.float64), layer=layer.astype(np.int64),
                    kind=kind.astype(str), total=float(L1[-1]), spool=spool)


def _length(dphi, da, r0, r1):
    """The true length of curves whose phi, a and r are linear in one parameter (Gauss-Legendre, 20 nodes)."""
    x, w = _GAUSS
    u = 0.5 * (x + 1.0)
    r = r0[:, None] + (r1 - r0)[:, None] * u[None, :]
    speed = np.sqrt((r * dphi[:, None]) ** 2 + ((r1 - r0) ** 2 + da ** 2)[:, None])
    return 0.5 * (speed * w[None, :]).sum(axis=1)


def _wind_drum(spool: Spool) -> _Pieces:
    pitch = spool.d if spool.pitch is None else spool.pitch
    lo, hi = spool.a_lo + spool.d / 2.0, spool.a_hi - spool.d / 2.0
    travel = hi - lo
    pieces = _Pieces()
    phi = 0.0
    n = _drum_layers(spool)
    for k in range(n):
        r = spool.r1 + k * spool.d * COS30
        going = spool.start if k % 2 == 0 else -spool.start
        a_from, a_to = (lo, hi) if going > 0 else (hi, lo)
        if spool.groove == LEBUS:
            phi = _lebus_layer(pieces, spool, phi, a_from, going, travel, pitch, r, k)
        else:
            dphi = spool.hand * 2.0 * math.pi * travel / pitch
            pieces.add(dphi, a_from, a_to, r, r, k, HELIX)
            phi += dphi
        if k < n - 1:
            r_next = spool.r1 + (k + 1) * spool.d * COS30
            parts = max(1, int(math.ceil((r_next - r) / (SHARE * r))))
            for j in range(parts):
                dphi = spool.hand * spool.climb / parts
                pieces.add(dphi, a_to, a_to, r + (r_next - r) * j / parts, r + (r_next - r) * (j + 1) / parts, k, CLIMB)
                phi += dphi
    return pieces


def _lebus_layer(pieces: _Pieces, spool: Spool, phi: float, a: float, going: int, travel: float,
                 pitch: float, r: float, k: int) -> float:
    """One Lebus layer from the drum angle phi: parallel runs and crossovers in the zones fixed on the drum (two per
    turn, half a turn apart), until the rope has moved over by ``travel``. Gives the angle where the layer ends."""
    w, hand = spool.crossover, spool.hand
    rate = 0.5 * pitch / w              # m along the axis per rad of turn in a crossover
    left = travel
    for _ in range(100000):
        if left <= _TINY:
            break
        x = (phi - spool.crossover_at) % math.pi       # where we are in the zone pattern (period half a turn)
        if hand > 0:
            inside = x < w - _TINY
            step = (w - x) if inside else (math.pi - x)
        else:
            inside = _TINY < x <= w + _TINY
            step = x if inside else ((x - w) if x > w else (math.pi - w + x))
        if step <= _TINY:               # standing on a zone's edge: take the next stretch
            step = (math.pi - w) if inside else w
            inside = not inside
        if inside:
            move = rate * step
            if move >= left:
                step, move = left / rate, left
            pieces.add(hand * step, a, a + going * move, r, r, k, CROSSOVER)
            a += going * move
            left -= move
        else:
            pieces.add(hand * step, a, a, r, r, k, PARALLEL)
        phi += hand * step
    return phi


def _wind_carousel(spool: Spool) -> _Pieces:
    d = spool.d
    r_a, r_b = spool.r_in + d / 2.0, spool.r_out - d / 2.0
    turn_all = 2.0 * math.pi * (r_b - r_a) / d      # turn of one layer
    pieces = _Pieces()
    n = _carousel_layers(spool)
    for k in range(n):
        out = spool.start if k % 2 == 0 else -spool.start
        r_from = r_a if out > 0 else r_b
        a = spool.a_bot + d / 2.0 + k * d
        climb = 0.0 if k == 0 else min(spool.climb, turn_all)
        if climb > 0.0:     # the first part of this layer's spiral, rising from the layer below
            _spiral(pieces, spool, r_from, out, climb, a - d, a, k - 1, CLIMB)
        r_climbed = r_from + out * d * climb / (2.0 * math.pi)
        _spiral(pieces, spool, r_climbed, out, turn_all - climb, a, a, k, FLAT)
    return pieces


def _spiral(pieces: _Pieces, spool: Spool, r: float, out: int, turn: float, a0: float, a1: float, layer: int,
            kind: str) -> None:
    """An Archimedean spiral from radius r over ``turn`` (rad), outwards (out +1) or inwards, a rising from a0 to a1,
    cut into pieces that turn at most min(SPIRAL_MAX, SPIRAL_SHARE * pi * r / d)."""
    d = spool.d
    grow = out * d / (2.0 * math.pi)        # m of radius per rad
    done = 0.0
    while turn - done > _TINY:
        r_here = r + grow * done
        step = min(SPIRAL_MAX, SPIRAL_SHARE * math.pi * r_here / d, turn - done)
        r_end = r_here + grow * step        # the smaller end decides (inwards it is the end)
        step = min(step, max(SPIRAL_SHARE * math.pi * min(r_here, r_end) / d, 1e-9))
        u0, u1 = done / turn, (done + step) / turn
        pieces.add(spool.hand * step, a0 + (a1 - a0) * u0, a0 + (a1 - a0) * u1,
                   r_here, r_here + grow * step, layer, kind)
        done += step


def wind(spool: Spool) -> Path:
    """The whole spool, from the anchor (L = 0) to full (L = total). Refuses impossible numbers in plain words
    (ValueError)."""
    _check(spool)
    pieces = _wind_drum(spool) if spool.kind == DRUM else _wind_carousel(spool)
    return pieces.path(spool)


# ---------------------------------------------------------------------------------------------------------
# reading the path
# ---------------------------------------------------------------------------------------------------------

def _index(path: Path, L, upper: bool = False):
    """The piece that holds L: L0 <= L < L1 (the last piece holds total), or with ``upper`` L0 < L <= L1 (the first
    piece holds 0) – at a boundary the piece before it."""
    L = np.clip(np.asarray(L, dtype=np.float64), 0.0, path.total)
    if upper:
        i = np.searchsorted(path.L1, L, side="left")
    else:
        i = np.searchsorted(path.L1, L, side="right")
    return np.clip(i, 0, len(path.L1) - 1), L


def _speed(path: Path, i, u):
    """|d point / du| on piece i at u."""
    r = path.r0[i] + (path.r1[i] - path.r0[i]) * u
    rest = (path.r1[i] - path.r0[i]) ** 2 + (path.a1[i] - path.a0[i]) ** 2
    return np.sqrt((r * (path.phi1[i] - path.phi0[i])) ** 2 + rest)


def _length_to(path: Path, i, u):
    """The length along piece i from its start to u (Gauss-Legendre on [0, u])."""
    x, w = _GAUSS
    nodes = 0.5 * (x + 1.0)
    sp = _speed(path, np.asarray(i)[..., None], np.asarray(u)[..., None] * nodes)
    return 0.5 * np.asarray(u) * (sp * w).sum(axis=-1)


def _u_of(path: Path, i, L):
    """The u of length L on piece i: linear where the radius stays (a helix), else by Newton on the length."""
    span = path.L1[i] - path.L0[i]
    t = L - path.L0[i]
    u = t / span
    bent = path.r1[i] != path.r0[i]
    if np.any(bent):
        ib, tb, ub = i[bent], t[bent], u[bent]
        for _ in range(6):
            ub = np.clip(ub - (_length_to(path, ib, ub) - tb) / _speed(path, ib, ub), 0.0, 1.0)
        u = u.copy()
        u[bent] = ub
    return u


def _eval(path: Path, i, L):
    i = np.asarray(i)
    L = np.asarray(L, dtype=np.float64)
    shape = np.broadcast(i, L).shape
    i, L = np.broadcast_to(i, shape).reshape(-1), np.broadcast_to(L, shape).reshape(-1)
    u = _u_of(path, i, L)
    phi = path.phi0[i] + (path.phi1[i] - path.phi0[i]) * u
    a = path.a0[i] + (path.a1[i] - path.a0[i]) * u
    r = path.r0[i] + (path.r1[i] - path.r0[i]) * u
    return phi.reshape(shape), a.reshape(shape), r.reshape(shape)


def at(path: Path, L):
    """(phi, a, r, layer) of the rope's middle at length L from the anchor; L is clipped to [0, total]. Vectorised:
    arrays of L's shape (0-d for a number)."""
    i, L = _index(path, L)
    phi, a, r = _eval(path, i, L)
    return phi, a, r, path.layer[i]


def xyz(phi, a, r):
    """The point (..., 3) in the spool frame."""
    phi, a, r = np.broadcast_arrays(*(np.asarray(v, dtype=np.float64) for v in (phi, a, r)))
    return np.stack([r * np.cos(phi), r * np.sin(phi), a], axis=-1)


def tangent(path: Path, L):
    """The rope's direction (..., 3), unit, the way L grows (towards the free rope)."""
    i, L = _index(path, L)
    phi, a, r = _eval(path, i, L)
    dphi = path.phi1[i] - path.phi0[i]          # per unit of u: the direction is the same
    da = path.a1[i] - path.a0[i]
    dr = path.r1[i] - path.r0[i]
    c, s = np.cos(phi), np.sin(phi)
    t = np.stack([dr * c - r * dphi * s, dr * s + r * dphi * c, da], axis=-1)
    return t / np.linalg.norm(t, axis=-1, keepdims=True)


def turn_per_metre(path: Path, L):
    """dphi / dL at L (rad per metre of rope; the sign of ``hand``), exact: on a carousel's spiral
    1 / sqrt(r^2 + (d / 2 pi)^2). Vectorised."""
    i, L = _index(path, L)
    i = np.asarray(i)
    shape = np.broadcast(i, L).shape
    ii, LL = np.broadcast_to(i, shape).reshape(-1), np.broadcast_to(L, shape).reshape(-1)
    u = _u_of(path, ii, LL)
    return ((path.phi1[ii] - path.phi0[ii]) / _speed(path, ii, u)).reshape(shape)


def layer_radius(path: Path, k):
    """The radius of a drum layer's rope middle: r1 + k * d * cos 30°."""
    s = path.spool
    if s.kind != DRUM:
        raise ValueError("Only a drum's layers have a radius; a carousel's have a place along the axis.")
    return s.r1 + np.asarray(k, dtype=np.float64) * s.d * COS30


def layer_place(path: Path, k):
    """The place along the axis of a carousel layer's rope middle: a_bot + d/2 + k * d."""
    s = path.spool
    if s.kind != CAROUSEL:
        raise ValueError("Only a carousel's layers have a place along the axis; a drum's have a radius.")
    return s.a_bot + s.d / 2.0 + np.asarray(k, dtype=np.float64) * s.d


def layer_start(path: Path, k: int) -> float:
    """Where layer k begins: the start of the climb into it (0 for layer 0; total beyond the last layer)."""
    if k <= 0:
        return 0.0
    if k >= path.layer_count:
        return path.total
    climbs = np.nonzero((path.layer == k - 1) & (path.kind == CLIMB))[0]
    if len(climbs):
        return float(path.L0[climbs[0]])
    return float(path.L0[np.nonzero(path.layer == k)[0][0]])     # no climb (climb = 0)


def layer_end(path: Path, k: int) -> float:
    """Where layer k's own pieces end (the start of the climb out of it; total for the last layer)."""
    return layer_start(path, k + 1)


def _first_of_layer(path: Path, k: int) -> float:
    """The L where the pieces labelled layer k begin (after the climb into it)."""
    if k <= 0:
        return 0.0
    if k >= path.layer_count:
        return path.total
    return float(path.L0[np.nonzero(path.layer == k)[0][0]])


def capacity(path: Path) -> float:
    """The rope a full spool holds (m)."""
    return path.total


def status(path: Path, W0, p):
    """'' when the leave point is on the spool, 'empty' when more is paid out than was wound (W0 - p < 0), 'full'
    when more is wound than the spool holds (W0 - p > total). A string for a number, an array of strings for an
    array."""
    left = np.asarray(W0, dtype=np.float64) - np.asarray(p, dtype=np.float64)
    out = np.where(left < -1e-9, "empty", np.where(left > path.total + 1e-9, "full", ""))
    return str(out) if out.ndim == 0 else out


def wound_at(path: Path, a, r):
    """The L whose point is nearest (a, r) – seen along the axis the turn does not count: the leave point of a CAD
    rope. Where several L share (a, r) (a Lebus parallel run, a layer's end and its climb) the smallest. Vectorised."""
    a = np.asarray(a, dtype=np.float64)
    r = np.asarray(r, dtype=np.float64)
    shape = np.broadcast(a, r).shape
    q = np.stack(np.broadcast_arrays(a, r), axis=-1).reshape(-1, 2)
    A = np.stack([path.a0, path.r0], axis=-1)
    D = np.stack([path.a1 - path.a0, path.r1 - path.r0], axis=-1)
    dd = np.einsum("ij,ij->i", D, D)
    out = np.empty(len(q))
    for s in range(0, len(q), 256):     # a block of points against every piece
        rel = q[s:s + 256, None, :] - A[None, :, :]
        t = np.where(dd > 0.0, np.einsum("pij,ij->pi", rel, D) / np.where(dd > 0.0, dd, 1.0), 0.0)
        t = np.clip(t, 0.0, 1.0)
        gap = np.linalg.norm(rel - t[..., None] * D[None, :, :], axis=-1)
        best = np.argmin(gap + 1e-12 * np.arange(len(dd))[None, :] / len(dd), axis=1)
        tb = t[np.arange(len(best)), best]
        out[s:s + 256] = path.L0[best] + _length_to(path, best, tb)
    return out.reshape(shape) if shape else float(out[0])


# ---------------------------------------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------------------------------------

def _curvature(path: Path, i: int) -> float:
    """The largest curvature of piece i (at its two ends and its middle)."""
    dphi = path.phi1[i] - path.phi0[i]          # derivatives by u: the curvature does not depend on the parameter
    da = path.a1[i] - path.a0[i]
    dr = path.r1[i] - path.r0[i]
    worst = 0.0
    for u in (0.0, 0.5, 1.0):
        r = path.r0[i] + (path.r1[i] - path.r0[i]) * u
        d1 = np.array([dr, r * dphi, da])           # in the (radial, round, axis) frame at that point
        d2 = np.array([-r * dphi * dphi, 2.0 * dr * dphi, 0.0])
        worst = max(worst, float(np.linalg.norm(np.cross(d1, d2)) / np.linalg.norm(d1) ** 3))
    return worst


def polyline(path: Path, L_lo: float, L_hi: float, sag: float):
    """Points for drawing the rope from L_lo to L_hi: the straight lines between them stay within ``sag`` of the true
    path, and the straight distance between two neighbours equals their difference in L (to 1e-9), so a curve
    trimmed by its length ends at the true L. Gives (pts (n, 3) in the spool frame, L (n,)); the first and last
    points are L_lo and L_hi exactly, on the path."""
    if not (sag > 0.0):
        raise ValueError("The drawing tolerance must be above 0.")
    L_lo = float(np.clip(L_lo, 0.0, path.total))
    L_hi = float(np.clip(L_hi, 0.0, path.total))
    if L_hi < L_lo:
        L_lo, L_hi = L_hi, L_lo
    if L_hi - L_lo <= _TINY:
        phi, a, r, _ = at(path, np.array([L_lo, L_lo]))
        return xyz(phi, a, r), np.array([L_lo, L_lo])
    first = int(_index(path, L_lo)[0])
    last = int(_index(path, L_hi, upper=True)[0])
    grids = []
    for i in range(first, last + 1):
        lo, hi = max(path.L0[i], L_lo), min(path.L1[i], L_hi)
        if hi - lo <= _TINY:
            continue
        kappa = _curvature(path, i)
        h = math.sqrt(8.0 * sag / kappa) if kappa > 0.0 else hi - lo     # one segment's length
        m = max(1, int(math.ceil((hi - lo) / (2.0 * h))))               # pairs of segments
        Ls = lo + (hi - lo) * np.arange(2 * m + 1) / (2 * m)
        Ls[-1] = hi
        grids.append((i, Ls if not grids else Ls[1:]))
    L = np.concatenate([g for _, g in grids])
    L[0], L[-1] = L_lo, L_hi
    piece = np.concatenate([np.full(len(g), i) for i, g in grids])
    phi, a, r = _eval(path, piece, L)
    # a point that ends a piece is worked out on that piece (the same point as on the next, to rounding)
    pts = xyz(phi, a, r)
    # every odd point: on the circle of points L[j] - L[j-1] from the one before and L[j+1] - L[j] from the one after,
    # the point of that circle nearest the true one
    j = np.arange(1, len(L) - 1, 2)
    A, B, C = pts[j - 1], pts[j + 1], pts[j]
    l1, l2 = L[j] - L[j - 1], L[j + 1] - L[j]
    ab = B - A
    c = np.linalg.norm(ab, axis=-1)
    n = ab / c[:, None]
    x = (c * c + l1 * l1 - l2 * l2) / (2.0 * c)
    h = np.sqrt(np.maximum(l1 * l1 - x * x, 0.0))
    foot = A + x[:, None] * n
    off = C - foot
    off = off - np.einsum("ij,ij->i", off, n)[:, None] * n
    size = np.linalg.norm(off, axis=-1)
    m = off / np.where(size > 0.0, size, 1.0)[:, None]
    pts[j] = foot + h[:, None] * m
    return pts, L


# ---------------------------------------------------------------------------------------------------------
# paying out: the leave point, the spool's turn, followers
# ---------------------------------------------------------------------------------------------------------

def tangency(rho, alpha, r, hand):
    """The angle psi at which a rope paid out towards a point at polar (rho, alpha) (seen along the axis) leaves
    the circle r: psi = alpha - hand * acos(min(1, r / rho)). The rope then runs from (r, psi) to the point along the
    rope's own direction there – the way L grows on the spool (see ``tangent``) – square to the radius. Vectorised.

    (The Design wrote ``alpha + hand * acos``; that is the other tangent, where the rope would have to run back
    over itself: tests/test_spool_core.py checks the sign.)"""
    rho = np.asarray(rho, dtype=np.float64)
    ratio = np.minimum(1.0, np.asarray(r, dtype=np.float64) / np.where(rho > 0.0, rho, 1e-300))
    return np.asarray(alpha, dtype=np.float64) - np.asarray(hand) * np.arccos(ratio)


def breaks(path: Path, W0: float, p_lo: float, p_hi: float):
    """The payouts between p_lo and p_hi where the leave point (L = W0 - p) passes the start or end of a piece,
    with p_lo and p_hi: sorted, each once. Between two neighbours phi(W0 - p) is linear in p (to about 1e-5 rad)."""
    edges = W0 - np.concatenate([[0.0], path.L1])
    inside = edges[(edges > p_lo) & (edges < p_hi)]
    return np.unique(np.concatenate([[p_lo, p_hi], inside]))


def _psi(psi, p, psi0):
    if psi is None:
        return np.zeros_like(p), 0.0
    if callable(psi):
        return np.asarray(psi(p), dtype=np.float64), float(psi(0.0)) if psi0 is None else psi0
    psi = np.broadcast_to(np.asarray(psi, dtype=np.float64), p.shape)
    if psi0 is None:
        if psi.ndim == 0 or psi.size == 1:
            psi0 = float(psi.reshape(-1)[0]) if psi.size else 0.0
        else:
            order = np.argsort(p.reshape(-1))
            psi0 = float(np.interp(0.0, p.reshape(-1)[order], psi.reshape(-1)[order]))
    return psi, psi0


def angle_table(path: Path, W0: float, psi, p, psi0: float | None = None):
    """The spool's turn about +z after paying out p (array), to be written as a table at ``breaks``:

        theta(p) = (psi(p) - psi(0)) - (phi(W0 - p) - phi(W0))

    ``psi``: None (0), a number, an array like p, or a function of p. psi(0) is ``psi0``; when not given, the
    function's value at 0, or the array's interpolated at p = 0 (its first value when p does not reach 0). W0 - p is
    clipped to [0, total]: an empty or full spool stands still. Same shape as p."""
    p = np.asarray(p, dtype=np.float64)
    psi_p, psi_0 = _psi(psi, p, psi0)
    phi_p = at(path, W0 - p)[0]
    phi_0 = at(path, W0)[0]
    return (psi_p - psi_0) - (phi_p - phi_0)


def exact_angle(path: Path, W0: float, p, psi=None, psi0: float | None = None):
    """The spool's turn at any payout p – the same formula as ``angle_table`` (the table is this function written
    at the breaks; between them it is linear to about 1e-5 rad for a fixed psi, exactly on a helix)."""
    return angle_table(path, W0, psi, p, psi0)


def arm_angle(c_s, c_a, a0, r_target, prefer=0.0):
    """Plane geometry (2-vectors, seen along the axis): the turn about c_a that brings the point a0 to the distance
    r_target from c_s – an arm on its own pivot whose guide must stand over the leave radius. Of the two answers the
    one nearest ``prefer`` (also over whole turns); nan when no turn reaches r_target. Vectorised over r_target and
    prefer."""
    c_s = np.asarray(c_s, dtype=np.float64)
    c_a = np.asarray(c_a, dtype=np.float64)
    v = np.asarray(a0, dtype=np.float64) - c_a
    D = c_a - c_s
    rv, rd = float(np.hypot(*v)), float(np.hypot(*D))
    r_target = np.asarray(r_target, dtype=np.float64)
    prefer = np.asarray(prefer, dtype=np.float64)
    if rv == 0.0 or rd == 0.0:      # the point on the pivot, or the pivot on the spool's axis: any turn or none
        same = np.isclose(r_target, math.hypot(*(np.asarray(a0, float) - c_s)), rtol=0.0, atol=1e-12)
        return np.where(same, prefer, np.nan) + 0.0 * r_target
    c = (r_target ** 2 - rd * rd - rv * rv) / (2.0 * rd * rv)
    beta = math.atan2(v[1], v[0])
    gamma = math.atan2(D[1], D[0])
    with np.errstate(invalid="ignore"):
        spread = np.arccos(np.clip(c, -1.0, 1.0))
    best = None
    for sign in (1.0, -1.0):
        t = gamma - beta + sign * spread       # cos(beta + t - gamma) = c
        t = t + 2.0 * math.pi * np.round((prefer - t) / (2.0 * math.pi))
        best = t if best is None else np.where(np.abs(t - prefer) < np.abs(best - prefer), t, best)
    return np.where(np.abs(c) <= 1.0 + 1e-12, best, np.nan)


def fleet_angles(path: Path, q):
    """Drum only: the fleet angle (rad, >= 0) of the rope from the top layer's middle at each flange to the point q
    (spool frame; the first sheave's groove): the angle between the rope and the plane square to the axis.
    Gives (at a_lo, at a_hi)."""
    s = path.spool
    if s.kind != DRUM:
        raise ValueError("Fleet angles are worked out for drums.")
    q = np.asarray(q, dtype=np.float64)
    r = float(layer_radius(path, path.layer_count - 1))
    rho = math.hypot(q[0], q[1])
    run = math.sqrt(max(rho * rho - r * r, 0.0))       # the rope's length seen along the axis (tangent)
    out = []
    for a in (s.a_lo + s.d / 2.0, s.a_hi - s.d / 2.0):
        out.append(math.atan2(abs(q[2] - a), run))
    return out[0], out[1]


# ---------------------------------------------------------------------------------------------------------
# the stack: rope on top, a solid below
# ---------------------------------------------------------------------------------------------------------

def _stack_low(path: Path, W0, p, drawn_layers: int):
    left = np.asarray(W0, dtype=np.float64) - np.asarray(p, dtype=np.float64)
    i, _ = _index(path, left - 1e-9, upper=True)     # a hair below: W0 - p keyed at a step may round up past it
    current = path.layer[i]
    return current - int(drawn_layers) + 1


def stack(path: Path, W0, p, drawn_layers: int):
    """Vectorised over p: (L_low, solid). Draw the rope from L_low to W0 - p; the full layers below it as one solid:
    a drum's is the outer radius of the top full layer (its rope middle + d/2; 0: none), a carousel's its height
    above a_bot (k * d; 0: none). ``drawn_layers``: how many layers are drawn as rope – the current one (the layer
    of W0 - p; on a climb the layer it climbs from) and those just below it. At a step (``stack_breaks``) the value
    is the one for the payouts just after it."""
    s = path.spool
    low = np.maximum(_stack_low(path, W0, p, drawn_layers), 0)
    starts = np.array([layer_start(path, k) for k in range(path.layer_count + 1)])
    L_low = starts[low]
    if s.kind == DRUM:
        solid = np.where(low >= 1, s.r1 + (low - 1) * s.d * COS30 + s.d / 2.0, 0.0)
    else:
        solid = low * s.d
    return L_low, solid.astype(np.float64)


def stack_breaks(path: Path, W0: float, p_lo: float, p_hi: float, drawn_layers: int):
    """The payouts between p_lo and p_hi (both left out) where stack's L_low and solid step: where the leave point
    passes the start of a layer's own pieces (the end of the climb into it) of a layer k >= drawn_layers. Sorted;
    the steps belong to the payouts after them (a CONSTANT table keyed here)."""
    ks = range(max(int(drawn_layers), 1), path.layer_count)
    p = np.array([W0 - _first_of_layer(path, k) for k in ks], dtype=np.float64)
    return np.sort(p[(p > p_lo) & (p < p_hi)])


# ---------------------------------------------------------------------------------------------------------
# volumes (a carousel's solid keeps the rope's volume)
# ---------------------------------------------------------------------------------------------------------

def ring_radii(spool: Spool) -> tuple[float, float]:
    """The inner and outer radius of the solid that stands for a carousel's full layers: the rope's innermost and
    outermost middle. (A spiral of pitch d fills exactly that ring at the density of square packing.)"""
    return spool.r_in + spool.d / 2.0, spool.r_out - spool.d / 2.0


def ring_volume(spool: Spool, layers) -> float:
    """The volume of the solid ring of ``layers`` full carousel layers (``ring_radii``, layers * d high). Times
    pi / 4 it is the volume of the rope those layers hold."""
    lo, hi = ring_radii(spool)
    return math.pi * (hi * hi - lo * lo) * np.asarray(layers, dtype=np.float64) * spool.d


def rope_volume(length, d: float):
    """The volume of a round rope: length * pi * d^2 / 4."""
    return np.asarray(length, dtype=np.float64) * math.pi * d * d / 4.0
