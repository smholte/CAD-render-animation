"""The hoist rope reeved in its falls (task 0232, Lifting lane L5) – plain Python + NumPy, no Blender.

A crane's hook block hangs in ``falls`` parts of line. The rope comes off the winch drum, runs up to the boom head,
over the head's **lead sheave**, down to the first block sheave, round it, up over the next head sheave … and ends
at the **dead end**: on the head when the falls are even, on the block when they are odd. So ``falls`` = 8 has 4 head
sheaves (the lead sheave and three more) and 4 block sheaves; 7 falls have 4 head and 3 block sheaves.

**Frames** (``Reeving``): the head frame has its origin on the head sheaves' axle, in the middle of them; x points
along the boom (seen from above), y along the axle, z up. The block frame is the same at the block sheaves' axle;
the drum frame at the drum's axle (x, y, z as the head's at the CAD pose). Sheave k of n lies at
y = (k − (n − 1) / 2) · pitch. Ropes going down leave a sheave on its +x side, ropes going up on its −x side; the
falls are the straight lines between them (they lean a little across where a head and a block sheave are not in
line). ``path`` gives the rope's middle line as points, each in one frame: a drawing whose points follow their
frames (Blender: hooks) stays right whatever the hoist does, because only the straight falls change length.

**Paying out.** Lowering the hook by dh pays out falls x dh of rope off the drum (``payout``). The drum's layers come
from ``core/spool.py`` (``drum_table``): the turn of the drum and the outside of the rope on it for every hoist value.

**Line pull** (check C10 in ``core/lifting.py``): gross / (falls x E), E the reeving efficiency of API RP 9B.

Units: m, rad.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import lifting, spool as S

ARC_STEP = math.radians(12.0)     # rad: the points round a sheave this far apart


def sheaves_for(falls: int) -> tuple[int, int, str]:
    """(head sheaves, block sheaves, dead end 'head' | 'block') for a rope in ``falls`` parts of line."""
    n = int(falls)
    if n < 1:
        raise ValueError("The rope needs at least one fall.")
    return 1 + (n - 1) // 2, n // 2, ("head" if n % 2 == 0 else "block")


def payout(falls: int, dh: float) -> float:
    """Rope off the drum when the hook goes down by dh (m): falls x dh."""
    return int(falls) * float(dh)


def efficiency(falls: int, k: float = lifting.K_ROLLER) -> float:
    """Reeving efficiency (API RP 9B) with as many sheaves as falls (the lead sheave counted)."""
    return lifting.reeving_efficiency(falls, None, k)


def line_pull(gross: float, falls: int, k: float = lifting.K_ROLLER) -> float:
    """The pull in the line from the drum, kg (as a mass): gross / (falls x E)."""
    return float(gross) / (int(falls) * efficiency(falls, k))


@dataclass
class Reeving:
    """A crane's reeving, m. ``head_r`` / ``block_r``: the rope's middle round a sheave (sheave radius − half a rope);
    ``drum_r``: the drum's barrel radius; ``drum_w``: between its flanges."""
    falls: int
    head_r: float
    block_r: float
    head_pitch: float
    block_pitch: float
    rope_d: float
    drum_r: float = 0.3
    drum_w: float = 0.8
    k: float = lifting.K_ROLLER

    @property
    def head(self) -> int:
        return sheaves_for(self.falls)[0]

    @property
    def block(self) -> int:
        return sheaves_for(self.falls)[1]

    @property
    def dead_end(self) -> str:
        return sheaves_for(self.falls)[2]


def from_data(d: dict, falls: int) -> Reeving:
    """A Reeving from a crane file's ``reeving`` table (mm, as the files write lengths for the rig) and its falls."""
    mm = 0.001
    rope = float(d.get("rope_d", 16.0)) * mm
    head_r = float(d["head_r"]) * mm
    block_r = float(d["block_r"]) * mm
    return Reeving(falls=int(falls), head_r=head_r, block_r=block_r,
                   head_pitch=float(d.get("head_pitch", max(2.5 * rope * 1000, 40.0))) * mm,
                   block_pitch=float(d.get("block_pitch", max(2.5 * rope * 1000, 40.0))) * mm,
                   rope_d=rope, drum_r=float(d.get("drum_r", 300.0)) * mm, drum_w=float(d.get("drum_w", 800.0)) * mm,
                   k=float(d.get("k", lifting.K_ROLLER)))


def ys(n: int, pitch: float) -> np.ndarray:
    return (np.arange(n) - (n - 1) / 2.0) * pitch


def _arc(r: float, y: float, a0: float, a1: float) -> list:
    """Points round a sheave of rope radius r at y, from angle a0 to a1 (x-z plane, angle from +x towards +z)."""
    n = max(2, int(math.ceil(abs(a1 - a0) / ARC_STEP)) + 1)
    return [np.array([r * math.cos(a), y, r * math.sin(a)]) for a in np.linspace(a0, a1, n)]


def tangent_in(r: float, p) -> float:
    """The angle on a sheave (radius r, centre 0, x-z plane) where a rope coming straight from the point p (x, z)
    touches it and then runs round over the top towards +x (clockwise seen along +y). Between 0 and 2 pi."""
    px, pz = float(p[0]), float(p[1])
    rho = math.hypot(px, pz)
    if rho <= r:
        return math.pi / 2
    phi = math.atan2(pz, px)
    al = math.acos(r / rho)
    best = None
    for th in (phi + al, phi - al):
        T = np.array([r * math.cos(th), r * math.sin(th)])
        travel = np.array([math.sin(th), -math.cos(th)])        # clockwise direction at th
        if float((T - np.array([px, pz])) @ travel) > 0:
            best = th
    th = best if best is not None else phi + al
    return th % (2 * math.pi)


def tangent_out(r: float, p) -> float:
    """The angle on a drum (radius r) where a rope running off its top towards the point p (x, z) leaves it."""
    px, pz = float(p[0]), float(p[1])
    rho = math.hypot(px, pz)
    if rho <= r:
        return math.pi / 2
    phi = math.atan2(pz, px)
    al = math.acos(r / rho)
    cands = [phi + al, phi - al]
    return max(cands, key=lambda th: math.sin(th))               # the upper one: the rope comes off the top


def path(rv: Reeving, drum_in_head, head_in_drum, drum_out: float | None = None) -> list:
    """The rope's middle line from the drum to the dead end: a list of (frame, point) with frame 'drum', 'head' or
    'block' and the point in that frame (m). ``drum_in_head``: the drum's centre in the head frame (to find where the
    lead comes onto the lead sheave); ``head_in_drum``: the head's centre in the drum frame. ``drum_out``: the rope's
    radius on the drum (default: its first layer)."""
    hy, by = ys(rv.head, rv.head_pitch), ys(max(rv.block, 1), rv.block_pitch)
    R, r = rv.head_r, rv.block_r
    rd = rv.drum_r + rv.rope_d / 2 if drum_out is None else float(drum_out)
    dh = np.asarray(drum_in_head, float)
    hd = np.asarray(head_in_drum, float)
    out = []
    # the lead: off the drum's top towards the lead sheave, onto it, over its top to the +x side
    # where the lead touches the lead sheave, seen from the drum (two rounds: each tangent depends on the other)
    th_in = tangent_in(R, (dh[0], dh[2]))
    for _ in range(3):
        t_head = np.array([R * math.cos(th_in), R * math.sin(th_in)])           # head frame (x, z)
        th_out = tangent_out(rd, (hd[0] + t_head[0], hd[2] + t_head[1]))
        t_drum = np.array([rd * math.cos(th_out), rd * math.sin(th_out)])         # drum frame
        th_in = tangent_in(R, (dh[0] + t_drum[0], dh[2] + t_drum[1]))
    out.append(("drum", np.array([t_drum[0], hy[0], t_drum[1]])))
    out += [("head", p) for p in _arc(R, hy[0], th_in, 0.0)]
    hi, bi = 0, 0
    for i in range(1, rv.falls + 1):
        if i % 2 == 1:                                    # down from head sheave hi (+x side)
            if i < rv.falls:
                out += [("block", p) for p in _arc(r, by[bi], 0.0, -math.pi)]
            else:                                         # odd falls: the dead end on the block, at its axle
                ya = (by[-1] + rv.block_pitch) if rv.block else 0.0
                out.append(("block", np.array([r, ya, 0.0])))
        else:                                             # up from block sheave bi (-x side)
            if i < rv.falls:
                hi += 1
                out += [("head", p) for p in _arc(R, hy[hi], math.pi, 0.0)]
                bi += 1
            else:                                         # even falls: the dead end on the head
                out.append(("head", np.array([-R, hy[-1] + rv.head_pitch, 0.0])))
    return out


def falls_of(points) -> int:
    """How many straight pieces of a ``path`` run between the head and the block (= the falls)."""
    n = 0
    for (fa, _), (fb, _) in zip(points, points[1:]):
        if {fa, fb} == {"head", "block"}:
            n += 1
    return n


def sheave_list(rv: Reeving) -> list:
    """(frame, y, rope radius) of every sheave: the head's, then the block's."""
    return ([("head", float(y), rv.head_r) for y in ys(rv.head, rv.head_pitch)]
            + [("block", float(y), rv.block_r) for y in ys(rv.block, rv.block_pitch)])


# ---------------------------------------------------------------------------------------------------------------------
# the drum

@dataclass
class DrumTable:
    hoist: np.ndarray      # m, the hoist joint's value (0 = hook highest)
    angle: np.ndarray      # rad, the drum's turn about its axle (grows as rope pays out)
    outside: np.ndarray    # m, the outside radius of the rope on the drum
    wound0: float          # m of rope on the drum at hoist 0
    layers: int


def drum_spool(rv: Reeving, layers: int) -> S.Spool:
    d = rv.rope_d
    return S.Spool(kind=S.DRUM, d=d, r1=rv.drum_r + d / 2.0, a_lo=-rv.drum_w / 2.0, a_hi=rv.drum_w / 2.0,
                   layers=int(layers))


def drum_table(rv: Reeving, hmax: float, dead_turns: float = 3.0) -> DrumTable:
    """The drum's turn and the rope's outside radius for hoist values 0 … hmax (the hoist joint's value: 0 = the hook
    at its highest = the drum fullest; hmax = the hook lowest, only ``dead_turns`` left on the drum). Every metre the
    hook goes down pays falls metres off (spool.py's drum, layer by layer)."""
    hmax = max(float(hmax), 1e-3)
    d = rv.rope_d
    w0 = rv.falls * hmax + dead_turns * 2 * math.pi * (rv.drum_r + d / 2.0)
    layers = 1
    path_ = None
    while layers <= 60:
        path_ = S.wind(drum_spool(rv, layers))
        if S.capacity(path_) >= w0:
            break
        layers += 1
    p_hi = rv.falls * hmax
    pts = S.breaks(path_, w0, 0.0, p_hi)
    if len(pts) > 400:                                    # many layers: thin out (the angle is linear between)
        pts = np.unique(np.concatenate([pts[:: max(1, len(pts) // 400)], [0.0, p_hi]]))
    ang = S.angle_table(path_, w0, None, pts)
    if ang[-1] < ang[0]:
        ang = -ang
    _low, solid = S.stack(path_, w0, pts, 0)
    outside = np.where(solid > 0, solid, rv.drum_r)
    return DrumTable(hoist=pts / rv.falls, angle=ang - ang[0], outside=outside, wound0=w0,
                     layers=path_.layer_count)
