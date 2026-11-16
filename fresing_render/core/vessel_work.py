"""What a working vessel does, and what the water shows of it (task 0154). No Blender.

**The setting.** The vessel lies *still*, sails *ahead* at N knots, is pushed *sideways* by its thrusters (DP: holding
or shifting its position) or *turns* on the spot. Each mode becomes a **command** per thruster: a load (0 … 1) and the
direction its jet of water goes. Directions are angles in the **vessel frame** (u to the bow, v to port, seen from
above): 0 = towards the bow, 90° = to port, 180° = straight aft, -90° = to starboard.

* An **azimuth** thruster turns on its steer joint: the steer angle is the jet's angle minus 180° (steer 0 = it pushes
  the vessel ahead, its jet goes aft).
* A **tunnel** thruster pushes water to port or to starboard through a tunnel across the hull.
* A **shaft** propeller pushes water aft (ahead) only.

Between two settings (an animation step that changes it) the commands blend: a tunnel's or a shaft's signed load
straight from one to the other (a tunnel reversing slows down through 0), an azimuth's load straight and its steer
angle the shortest way round.

**The water** (the formulas the sea shader draws; ``blender/vessel_work.py`` writes the same maths as shader nodes):

* ``kelvin`` – the ship's wave pattern behind the bow at speed V. A wave that travels at angle θ to the track stands
  still behind the vessel when its speed is V·cos θ, so its wave number is k0·sec²θ, k0 = g/V². A point at angle α
  off the track behind the bow sees the waves whose θ solves tan α = tan θ / (1 + 2 tan² θ) (stationary phase,
  Lord Kelvin 1887): two answers, t = tan θ = (1 ∓ q) / (4 tan α), q = √(1 − 8 tan² α) – the **transverse** waves (−,
  written 2 tan α / (1 + q) so it holds on the track) and the **divergent** ones (+). There are none outside
  tan α = 1/√8: the **19.47° wedge**. The phase of each is k0·√(1 + t²)·(x + |y|·t); the height is their sum,
  as tall as ``amplitude(V)`` near the bow and fading with the distance behind it.
* ``trail`` – the turbulent foam behind the stern (``core/sea.wake``, the wake of task 0109) at the vessel's speed.
* ``bow_wave`` – how white the foam round the hull is: a bow wave at the stem and wash along the sides, by speed.
* ``jet`` – a running thruster's jet of white, boiling water where it leaves the hull: as long as its load and the
  vessel's speed make it, widening and fading away from the hull.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import sea as sea_core

G = sea_core.G
KNOT = sea_core.KNOT
KELVIN = sea_core.KELVIN                    # 19.47°: tan = 1 / sqrt(8)
MODES = ("STILL", "AHEAD", "DP", "TURN")
KINDS = ("AZIMUTH", "TUNNEL", "SHAFT")
SIDES = ("PORT", "STBD")
MAX_THRUSTERS = 6
FULL_AHEAD = 12.0                           # knots at which the propellers run at full load
AHEAD_IDLE = 0.2                            # load of the propellers at the slowest speed ahead
AFT = math.pi                               # jet straight aft
PORT = math.pi / 2                          # jet to port
STBD = -math.pi / 2
PREFIX = "fr_vw_"                           # scene custom properties ("channels"), as the weather's ``fr_wx_``

# the wave pattern
KELVIN_AMP = 0.012                          # m per (m/s)^2: 0.32 m at 10 knots
KELVIN_AMP_MAX = 0.8
KELVIN_NEAR = 20.0                          # m: the waves fall off as sqrt(NEAR / (NEAR + x)) behind the bow ...
KELVIN_FADE = (80.0, 30.0)                  # ... and exp(-x / (a + b * knots)) (the pattern dies out far behind)
KELVIN_EDGE = 0.12                          # soft edge of the wedge, in units of 1 - 8 tan^2 alpha
DIVERGENT = 0.4                             # share of the divergent waves (the transverse ones: 1 - DIVERGENT)
DIVERGENT_FROM = (0.1, 0.4)                 # the divergent waves grow in between these shares of the wedge's angle
                                            # (on the track they are infinitely short and flat)
TAN_MIN = 1e-3

# a thruster's jet
JET_LENGTH = (6.0, 14.0, 1.5)               # m: a + b * load + c * knots
JET_WIDTH = (1.5, 0.3)                      # m: half width a + b * distance from the hull
JET_BACK = 3.0                              # m: the boil reaches this far back over the exit point
BOW_REACH = 0.6                             # the bow wave reaches this much further out than the hull foam
JET_BOIL = 0.25                             # m: how high the boiling water heaves (bump) at full load


def _clamp(x, lo=0.0, hi=1.0):
    return min(max(float(x), lo), hi)


def wrap(a: float) -> float:
    """An angle in (-pi, pi]."""
    a = math.fmod(float(a) + math.pi, 2 * math.pi)
    if a <= 0.0:
        a += 2 * math.pi
    return a - math.pi


# ---------------------------------------------------------------------------
# settings and commands
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Thruster:
    """One propeller of the vessel: its kind and where it sits (vessel frame, m, from the hull's middle)."""
    kind: str = "AZIMUTH"
    u: float = 0.0
    v: float = 0.0


@dataclass(frozen=True)
class Setting:
    """What the vessel does: ``mode`` one of MODES, ``speed`` knots (Ahead), ``side`` PORT / STBD (Sideways: where
    the vessel is pushed to; Turning: where the bow turns to), ``thrust`` 0 … 1 (Sideways and Turning)."""
    mode: str = "STILL"
    speed: float = 0.0
    side: str = "STBD"
    thrust: float = 0.6


@dataclass
class Command:
    """What every thruster does at one moment, and the vessel's speed through the water (knots)."""
    ahead: float = 0.0
    loads: list = field(default_factory=list)       # 0 … 1
    jets: list = field(default_factory=list)        # rad, vessel frame


def rest_jet(kind: str) -> float:
    """A thruster's jet when it does nothing: azimuths and shafts point aft, tunnels to port."""
    return PORT if kind == "TUNNEL" else AFT


def ahead_load(speed: float) -> float:
    """The propellers' load sailing ahead at ``speed`` knots: 0 standing, AHEAD_IDLE … 1 up to FULL_AHEAD."""
    v = max(float(speed), 0.0)
    if v <= 0.0:
        return 0.0
    return _clamp(AHEAD_IDLE + (1.0 - AHEAD_IDLE) * v / FULL_AHEAD)


def effective_mode(st: Setting) -> str:
    """Ahead at 0 knots and a push or turn with no thrust are Still."""
    if st.mode == "AHEAD" and st.speed <= 0.0:
        return "STILL"
    if st.mode in ("DP", "TURN") and st.thrust <= 0.0:
        return "STILL"
    return st.mode if st.mode in MODES else "STILL"


def command(st: Setting, thrusters) -> Command:
    """The command of every thruster for setting ``st``."""
    mode = effective_mode(st)
    loads, jets = [], []
    for t in thrusters:
        load, jet = 0.0, rest_jet(t.kind)
        if mode == "AHEAD" and t.kind != "TUNNEL":
            load = ahead_load(st.speed)
        elif mode == "DP" and t.kind != "SHAFT":
            # pushed to starboard: the water goes to port
            load, jet = _clamp(st.thrust), (PORT if st.side == "STBD" else STBD)
        elif mode == "TURN" and t.kind != "SHAFT":
            # bow to starboard: the bow's thrusters push the bow to starboard (water to port), the stern's the
            # stern to port (water to starboard)
            fwd = t.u > 0.0
            to_port = fwd if st.side == "STBD" else not fwd
            load, jet = _clamp(st.thrust), (PORT if to_port else STBD)
        loads.append(float(load))
        jets.append(float(jet))
    return Command(ahead=max(float(st.speed), 0.0) if mode == "AHEAD" else 0.0, loads=loads, jets=jets)


def _short(a: float, b: float) -> float:
    """b - a the shortest way round (exactly half a turn goes the positive way)."""
    d = wrap(b - a)
    return d


def mix(a: Command, b: Command, f: float, kinds) -> Command:
    """``a`` at f = 0 … ``b`` at f = 1 (see the module's text)."""
    f = _clamp(f)
    loads, jets = [], []
    for i, kind in enumerate(kinds):
        la, lb, ja, jb = a.loads[i], b.loads[i], a.jets[i], b.jets[i]
        if kind == "AZIMUTH":
            if la <= 1e-9:
                ja = jb                       # (it stood still: it steers straight to where it is going)
            elif lb <= 1e-9:
                jb = ja
            loads.append(la + (lb - la) * f)
            jets.append(wrap(ja + _short(ja, jb) * f))
        else:
            # a signed load along the thruster's one line (tunnel: port +, shaft: aft +)
            ref = PORT if kind == "TUNNEL" else AFT
            sa, sb = la * math.cos(ja - ref), lb * math.cos(jb - ref)
            sv = sa + (sb - sa) * f
            loads.append(abs(sv))
            jets.append(wrap(ref if sv >= 0.0 else ref + math.pi))
    return Command(ahead=a.ahead + (b.ahead - a.ahead) * f, loads=loads, jets=jets)


def steer(jet: float) -> float:
    """An azimuth's steer angle (rad, about the vertical, anticlockwise from above) for a jet going ``jet``."""
    return wrap(jet - AFT)


def rate(kind: str, load: float, jet: float, rpm: float, reverse: bool = False) -> float:
    """A propeller's turning rate (rad/s) for its command. Positive turns push water aft (azimuth, shaft) or to port
    (tunnel) unless ``reverse``; a tunnel pushing to starboard turns backwards."""
    w = float(load) * float(rpm) * 2.0 * math.pi / 60.0
    if kind == "TUNNEL" and math.sin(jet) < 0.0:
        w = -w
    elif kind == "SHAFT" and math.cos(jet) > 0.0:
        w = -w
    return -w if reverse else w


def turns(rates, dt: float, start: float = 0.0) -> np.ndarray:
    """The propeller's angle at each sample of ``rates`` (rad/s, one per frame ``dt`` s apart): the integral."""
    r = np.asarray(rates, float)
    if len(r) == 0:
        return np.zeros(0)
    steps = (r[1:] + r[:-1]) * 0.5 * dt
    return float(start) + np.concatenate([[0.0], np.cumsum(steps)])


def thin(values, eps: float = 1e-6) -> list[int]:
    """Indices of the samples a piecewise straight line needs (first, last and every bend)."""
    v = np.asarray(values, float)
    n = len(v)
    if n <= 2:
        return list(range(n))
    bend = np.abs(v[2:] - 2 * v[1:-1] + v[:-2]) > eps
    return [0] + [i + 1 for i in np.nonzero(bend)[0]] + [n - 1]


def channels(c: Command) -> dict:
    """The command as channel values: ``ahead`` and ``t<i>`` / ``a<i>`` for each thruster (unused slots: 0)."""
    out = {"ahead": float(c.ahead)}
    for i in range(MAX_THRUSTERS):
        out[f"t{i}"] = float(c.loads[i]) if i < len(c.loads) else 0.0
        out[f"a{i}"] = float(c.jets[i]) if i < len(c.jets) else 0.0
    return out


CHANNEL_NAMES = tuple(channels(Command()).keys())


def prop(name: str) -> str:
    return PREFIX + name


def words(st: Setting) -> str:
    """The setting in a few words (the panel's header, a step's label)."""
    mode = effective_mode(st)
    side = "port" if st.side == "PORT" else "starboard"
    if mode == "AHEAD":
        return f"Ahead {st.speed:g} kn"
    if mode == "DP":
        return f"Sideways to {side} {st.thrust * 100:.0f}%"
    if mode == "TURN":
        return f"Turning to {side} {st.thrust * 100:.0f}%"
    return "Still"


# ---------------------------------------------------------------------------
# the water
# ---------------------------------------------------------------------------

def smoothstep(a, b, x):
    return sea_core.smoothstep(a, b, x)


def amplitude(knots: float) -> float:
    """Height (m) of the wave pattern near the bow at ``knots``."""
    v = max(float(knots), 0.0) * KNOT
    return min(KELVIN_AMP * v * v, KELVIN_AMP_MAX)


def wavelength(knots: float) -> float:
    """The transverse waves' length (m) at ``knots``: 2 pi V^2 / g."""
    v = max(float(knots), 0.0) * KNOT
    return 2.0 * math.pi * v * v / G


def kelvin_roots(tan_a):
    """(transverse, divergent) tan θ for points at tan α off the track (inside the wedge; outside: the cusp's)."""
    ta = np.maximum(np.abs(np.asarray(tan_a, float)), TAN_MIN)
    q = np.sqrt(np.maximum(1.0 - 8.0 * ta * ta, 0.0))
    return 2.0 * ta / (1.0 + q), (1.0 + q) / (4.0 * ta)


def kelvin(xb, y, knots: float):
    """Height (m) of the ship's waves at ``xb`` metres behind the bow and ``y`` off the track (the wedge's middle)."""
    xb, y = np.asarray(xb, float), np.abs(np.asarray(y, float))
    v = max(float(knots), 0.0) * KNOT
    shape = np.broadcast(xb, y).shape
    if v <= 0.05:
        return np.zeros(shape)
    k0 = G / (v * v)
    xp = np.maximum(xb, 1e-6)
    ta = y / xp
    inside = smoothstep(0.0, KELVIN_EDGE, 1.0 - 8.0 * ta * ta)
    tt, td = kelvin_roots(ta)
    pt = k0 * np.sqrt(1.0 + tt * tt) * (xp + y * tt)
    pd = k0 * np.sqrt(1.0 + td * td) * (xp + y * td)
    fade = np.sqrt(KELVIN_NEAR / (KELVIN_NEAR + xp)) * np.exp(-xp / (KELVIN_FADE[0] + KELVIN_FADE[1] * knots))
    wd = DIVERGENT * smoothstep(DIVERGENT_FROM[0], DIVERGENT_FROM[1], ta * math.sqrt(8.0))
    h = amplitude(knots) * fade * inside * ((1.0 - DIVERGENT) * np.cos(pt) + wd * np.cos(pd))
    return np.where(xb > 0.0, h, 0.0)


def kelvin_envelope(xb, knots: float):
    """The largest height the pattern can have ``xb`` metres behind the bow (its fade)."""
    xp = np.maximum(np.asarray(xb, float), 1e-6)
    return amplitude(knots) * np.sqrt(KELVIN_NEAR / (KELVIN_NEAR + xp)) * np.exp(
        -xp / (KELVIN_FADE[0] + KELVIN_FADE[1] * knots))


def trail(xb, y, half_beam: float, knots: float):
    """Foam behind the stern (``xb`` metres behind it, ``y`` off the middle line): ``core/sea.wake``."""
    return sea_core.wake(xb, y, half_beam, knots)


def bow_wave(u, knots: float):
    """How white the foam round the hull gets from the vessel's speed, at ``u`` along the hull (0 the stern … 1 the
    bow): wash along the sides, a bow wave at the stem. Returns (strength 0 … 1, reach factor >= 1)."""
    u = np.asarray(u, float)
    s = smoothstep(0.5, 8.0, max(float(knots), 0.0))
    bow = smoothstep(0.75, 1.0, u)
    return s * (0.55 + 0.45 * bow), 1.0 + BOW_REACH * bow * s


def exit_distance(u: float, v: float, jet: float, half_length: float, half_beam: float) -> float:
    """How far a jet from (u, v) going ``jet`` travels before it leaves the hull's box (|u| <= half_length,
    |v| <= half_beam): where it comes up beside or behind the hull."""
    cu, sv = math.cos(jet), math.sin(jet)
    ru = (half_length - u * math.copysign(1.0, cu)) / abs(cu) if abs(cu) > 1e-9 else math.inf
    rv = (half_beam - v * math.copysign(1.0, sv)) / abs(sv) if abs(sv) > 1e-9 else math.inf
    return max(min(ru, rv), 0.0)


def jet(s, q, load: float, knots: float = 0.0):
    """Foam (0 … 1) of a thruster's jet at ``s`` metres along it from where it leaves the hull and ``q`` across."""
    s, q = np.asarray(s, float), np.abs(np.asarray(q, float))
    load = _clamp(load)
    length = JET_LENGTH[0] + JET_LENGTH[1] * load + JET_LENGTH[2] * max(float(knots), 0.0)
    sp = np.maximum(s, 0.0)
    w = JET_WIDTH[0] + JET_WIDTH[1] * sp
    along = np.exp(-sp / length) * (1.0 - smoothstep(0.0, JET_BACK, -s))
    across = 1.0 - smoothstep(0.45 * w, w, q)
    return load * along * across


def jet_at(pu, pv, t: Thruster, load: float, jet_angle: float, half_length: float, half_beam: float,
           knots: float = 0.0):
    """Foam of one thruster's jet at vessel-frame points (pu, pv)."""
    r = exit_distance(t.u, t.v, jet_angle, half_length, half_beam)
    du, dv = math.cos(jet_angle), math.sin(jet_angle)
    eu, ev = t.u + du * r, t.v + dv * r
    pu, pv = np.asarray(pu, float) - eu, np.asarray(pv, float) - ev
    return jet(pu * du + pv * dv, -pu * dv + pv * du, load, knots)


# ---------------------------------------------------------------------------
# the test model (tools/make_test_thrusters.py, blender/vessel_work.set_up_test_model): mm, x to the bow (transom at
# 0), y to port, the waterline at z = 0
# ---------------------------------------------------------------------------

TEST = {
    "hull_length": 36000.0, "bow_start": 30000.0, "half_beam": 6000.0, "bottom": -2500.0, "deck": 2500.0,
    "az_x": 3500.0, "az_y": 3000.0, "az_drop": -1600.0, "az_prop_x": -1500.0,    # (drop and prop: from the axis)
    "bow_x": 32000.0, "bow_z": -1300.0, "tunnel_r": 700.0,
}
