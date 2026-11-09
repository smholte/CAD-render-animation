"""Tool changes in the video (task 0041): what the machine does at every M6, as timed phases. No Blender.

Two kinds of machine:

    manual   the head goes to the change position (or stays where it is, or only lifts Z), pauses, and goes back;
             the tool is swapped in the pause (by the operator's hand when it is shown)
    ATC      the tools stand in pockets. The head goes above the old tool's pocket station (the carousel turns that
             pocket to the station meanwhile), the changer's own animation plays up to its swap moment, the spindle
             goes down and leaves the old tool in its pocket, goes up, the carousel turns to the new tool's pocket
             (a rack: the head goes over to it), the spindle goes down and takes the new tool, goes up, the rest of
             the changer's animation plays and the head goes back to where the program left off.

A :class:`Change` holds the phases of one tool change with their times (seconds from the step's start), the head's
path (machine coordinates, mm, straight between the knots), the carousel's turns and where the changer's own animation
plays. ``Schedule`` (core/gcode.py) puts one in the video at every M6; "Fit into" shortens them all by one factor,
each phase down to its minimum (:func:`fit`).

All positions are machine coordinates in mm of the reference tool's tip (the tool in the spindle when the set-up was
made): a station is where that tip is when the spindle's gauge line sits in the pocket.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

TURN = 2.0 * math.pi
MIN_TURN = 0.2               # s: the shortest carousel turn (also when "Fit into" squeezes the changes)
MIN_PAUSE = 0.2              # s: the shortest manual pause when "Fit into" squeezes the changes
CHANGE_SHARE = 0.5           # "Fit into": tool changes may take at most this share of the step's seconds
PAUSE_MAX = 5.0              # s: the pause slider's end

#: the operator's hand (manual change, "Show hand"): seconds of each move, in order. Between "away" and "back" it
#: waits for the rest of the pause (fetching the new tool).
HAND_MOVES = (("reach", 0.5), ("pull", 0.4), ("away", 0.5), ("back", 0.5), ("push", 0.4), ("leave", 0.5))
HAND_MIN = sum(d for _n, d in HAND_MOVES)


def hand_keys(t0: float, length: float) -> list:
    """[(time, pose)] of the hand in a pause from ``t0`` lasting ``length``: poses 'out' (outside the machine), 'grip'
    (round the holder in the spindle) and 'below' (the tool pulled out, below the spindle). It moves at its own pace
    and waits outside for the rest of the pause (fetching the new tool). The old tool leaves the spindle at the first
    'grip', the new one is in at the second."""
    k = 1.0 if length >= HAND_MIN else max(1e-3, length) / HAND_MIN
    wait = max(0.0, length - HAND_MIN * k)
    pose = {"reach": "grip", "pull": "below", "away": "out", "back": "below", "push": "grip", "leave": "out"}
    t = t0
    poses = [(t, "out")]
    for name, d in HAND_MOVES:
        if name == "back" and wait > 0:
            t += wait
            poses.append((t, "out"))
        t += d * k
        poses.append((t, pose[name]))
    return poses


def hand_events(t0: float, length: float) -> tuple[float, float]:
    """(old tool out of the spindle, new tool in) of a hand in a pause from ``t0`` lasting ``length``."""
    keys = hand_keys(t0, length)
    grips = [t for t, p in keys if p == "grip"]
    return grips[0], grips[1]


@dataclass
class Changer:
    """How tool changes play.

    ``atc``: the machine has a tool changer. ``position``: (x, y, z) machine mm where a manual change (or an ATC change
    of a tool without a pocket) happens; None in a place: that axis stays; None: the head stays where it is.
    ``pause``: seconds of a manual change's pause; ``hand``: the operator's hand is shown (the pause grows to
    HAND_MIN). ``seq`` / ``seq_swap``: length of the changer's own animation and when in it the tools swap (0: none).
    ``speed``: the changer runs this many times faster (turns, its animation). ``pockets``: {T: pocket};
    ``stations``: {pocket: (x, y, z)} where the reference tip is with the spindle's gauge line in that pocket (a
    carousel: one station for every pocket; None in a place: that axis stays); ``carousel``: {pocket: value of the
    carousel joint that brings it to the station}, empty without a carousel; ``turn_time``: s per ``pitch`` of
    turn. ``approach``: mm above a station the spindle comes from and goes back to. ``start_tool``: the tool in the
    spindle when the step starts (0: not known). ``rapid``: mm/min per axis."""
    atc: bool = False
    position: tuple | None = None
    pause: float = 1.0
    hand: bool = False
    seq: float = 0.0
    seq_swap: float = 0.0
    speed: float = 1.0
    pockets: dict = field(default_factory=dict)
    stations: dict = field(default_factory=dict)
    carousel: dict = field(default_factory=dict)
    carousel_start: float = 0.0
    carousel_limits: tuple | None = None
    turn_time: float = 0.5
    pitch: float = TURN / 8
    approach: float = 100.0
    start_tool: int = 0
    rapid: tuple = (5000.0, 5000.0, 5000.0)

    def pause_length(self) -> float:
        p = max(0.0, float(self.pause))
        return max(p, HAND_MIN) if self.hand else p

    def has_pocket(self, n: int) -> bool:
        p = self.pockets.get(n)
        return self.atc and p is not None and p in self.stations


@dataclass
class Phase:
    """A part of a tool change. ``kind``: 'move' (the head goes from ``a`` to ``b``), 'seq' (the changer's own
    animation from ``s0`` to ``s1`` s), 'turn' (the carousel from ``v0`` to ``v1``; a move may turn it meanwhile),
    'pause' (``hand``). ``after``: 'drop' (the old tool is in its pocket now) or 'swap' (the new tool is in the
    spindle now)."""
    kind: str
    dur: float
    a: tuple = ()
    b: tuple = ()
    v0: float | None = None
    v1: float | None = None
    s0: float = 0.0
    s1: float = 0.0
    hand: bool = False
    after: str = ""
    least: float = 0.0           # its shortest length when "Fit into" squeezes it
    span: int = 1                # a turn (v0 -> v1) lasts this phase and the next span - 1 ones
    role: str = ""               # 'out': the way from the program to the changer, 'back': the way back
    t0: float = 0.0              # when it starts (s from the step's start), set by place()


@dataclass
class Change:
    """One tool change as it plays: from ``start`` for ``length`` seconds."""
    tool: int
    old: int
    start: float = 0.0
    length: float = 0.0
    swap: float = 0.0            # the new tool is in the spindle from here on
    drop: float = 0.0            # the old tool has left the spindle from here on
    old_pocket: int | None = None
    new_pocket: int | None = None
    phases: list = field(default_factory=list)
    out_end: float = 0.0         # the head has left the program's point (tool length offsets ramp in this time)
    back_start: float = 0.0
    moves: bool = False          # the head goes somewhere (else it stays where the program left it)
    hand: tuple | None = None    # (start, length) of the hand's pause
    note: str = ""

    def knots(self) -> list:
        """[(t, (x, y, z))] of the head, from the change's start to its end."""
        out = []
        for ph in self.phases:
            if ph.kind == "move":
                if not out or abs(out[-1][0] - ph.t0) > 1e-12:
                    out.append((ph.t0, ph.a))
                out.append((ph.t0 + ph.dur, ph.b))
        return out

    def point_at(self, t: float, p: tuple) -> tuple:
        """The head (machine mm) at ``t``; ``p``: where the program left it."""
        k = self.knots()
        if not k or t <= k[0][0]:
            return k[0][1] if k and t >= self.start else p
        for (ta, a), (tb, b) in zip(k, k[1:]):
            if t <= tb:
                u = 0.0 if tb - ta <= 1e-12 else (t - ta) / (tb - ta)
                return tuple(x + (y - x) * u for x, y in zip(a, b))
        return k[-1][1]

    def turns(self) -> list:
        """[(t0, t1, v0, v1)] of the carousel."""
        out = []
        for k, ph in enumerate(self.phases):
            if ph.v0 is not None and abs(ph.v1 - ph.v0) > 1e-12:
                last = self.phases[min(len(self.phases), k + ph.span) - 1]
                out.append((ph.t0, last.t0 + last.dur, ph.v0, ph.v1))
        return out

    def seq_parts(self) -> list:
        """[(t, s0, s1, scale)]: the changer's own animation from ``s0`` to ``s1`` s plays from ``t`` on, ``scale``
        video seconds per second of it."""
        out = []
        for ph in self.phases:
            if ph.kind == "seq" and ph.s1 > ph.s0:
                out.append((ph.t0, ph.s0, ph.s1, ph.dur / (ph.s1 - ph.s0)))
        return out


def axis_time(a, b, rapid) -> float:
    """Seconds of a rapid from ``a`` to ``b`` (each axis at its own rapid speed, mm/min)."""
    return max(abs(b[i] - a[i]) / max(1e-6, rapid[i]) for i in range(3)) * 60.0


def resolve(p: tuple, where) -> tuple:
    """A position with None in some places: those axes stay at ``p``."""
    if where is None:
        return tuple(p)
    return tuple(float(p[i]) if where[i] is None else float(where[i]) for i in range(3))


def nearest_turn(v: float, target: float, limits=None) -> float:
    """The value equal to ``target`` (mod a full turn) closest to ``v`` – the shortest way – within ``limits``."""
    t = v + ((target - v + math.pi) % TURN - math.pi)
    if limits is None:
        return t
    lo, hi = limits
    best = None
    for k in range(-3, 4):
        c = t + k * TURN
        if lo - 1e-9 <= c <= hi + 1e-9 and (best is None or abs(c - v) < abs(best - v)):
            best = c
    return best if best is not None else min(max(t, lo), hi)


def _role(phases: list, role: str) -> list:
    for ph in phases:
        ph.role = role
    return phases


def _legs(a: tuple, b: tuple, rapid, rapid_factor: float, z_first: bool) -> list:
    """Rapid moves from a to b: up first (going up) or down last (coming down), the rest straight."""
    out = []
    pts = [a]
    if z_first and b[2] > a[2] + 1e-9 and (abs(b[0] - a[0]) > 1e-9 or abs(b[1] - a[1]) > 1e-9):
        pts.append((a[0], a[1], b[2]))
    elif not z_first and a[2] > b[2] + 1e-9 and (abs(b[0] - a[0]) > 1e-9 or abs(b[1] - a[1]) > 1e-9):
        pts.append((b[0], b[1], a[2]))
    pts.append(b)
    for x, y in zip(pts, pts[1:]):
        if math.dist(x, y) > 1e-9:
            out.append(Phase("move", axis_time(x, y, rapid) / rapid_factor, a=x, b=y))
    return out


def plan(old: int, new: int, p: tuple, ch: Changer, carousel_value: float, rapid_factor: float = 1.0) -> Change:
    """The phases of one tool change from tool ``old`` to ``new`` with the head at ``p`` (machine mm) and the carousel
    at ``carousel_value``. Times are relative (``place`` puts them on the time line)."""
    c = Change(tool=new, old=old)
    rf = max(1e-6, float(rapid_factor or 1.0))
    speed = max(1e-3, float(ch.speed or 1.0))
    p = tuple(float(x) for x in p)
    if old == new and old:
        return c                                       # T1 M6 with T1 in the spindle: nothing happens
    po = ch.pockets.get(old) if ch.has_pocket(old) else None
    pn = ch.pockets.get(new) if ch.has_pocket(new) else None
    c.old_pocket, c.new_pocket = po, pn
    ph: list = []
    v = carousel_value

    def turn_to(pocket):
        nonlocal v
        if pocket is None or pocket not in ch.carousel:
            return None, None
        v1 = nearest_turn(v, ch.carousel[pocket], ch.carousel_limits)
        v0, v = v, v1
        return v0, v1

    def turn_time(v0, v1):
        if v0 is None or abs(v1 - v0) < 1e-9:
            return 0.0
        return max(MIN_TURN, abs(v1 - v0) / max(1e-9, ch.pitch) * ch.turn_time) / speed

    seq_a = ch.seq_swap if ch.seq > 0 else 0.0
    seq_b = max(0.0, ch.seq - ch.seq_swap) if ch.seq > 0 else 0.0
    if ch.atc and (po is not None or pn is not None):
        def station(pocket):
            return resolve(p, ch.stations[pocket])

        def above(s):
            return (s[0], s[1], s[2] + ch.approach)

        first = station(po if po is not None else pn)
        here = above(first)
        out = _role(_legs(p, here, ch.rapid, rf, True), "out")
        v0, v1 = turn_to(po if po is not None else pn)
        tt = turn_time(v0, v1)
        if out and tt:                                 # the carousel turns while the head travels
            if tt > sum(x.dur for x in out):
                out[-1].dur += tt - sum(x.dur for x in out)
            out[0].v0, out[0].v1, out[0].span = v0, v1, len(out)
        elif tt:
            out = [Phase("turn", tt, a=here, b=here, v0=v0, v1=v1, least=MIN_TURN)]
        ph += out
        if seq_a > 0:
            ph.append(Phase("seq", seq_a / speed, a=here, b=here, s0=0.0, s1=seq_a))
        if po is not None:
            s = station(po)
            ph += _legs(here, s, ch.rapid, rf, False)
            ph[-1].after = "drop"
            ph += _legs(s, above(s), ch.rapid, rf, True)
            here = above(s)
        else:
            ph.append(Phase("pause", 0.0, a=here, b=here, after="drop"))
        if pn is not None:
            s = station(pn)
            target = above(s)
            v0, v1 = turn_to(pn)
            tt = turn_time(v0, v1)
            legs = _legs(here, target, ch.rapid, rf, True)
            if tt:
                if legs:
                    if tt > sum(x.dur for x in legs):
                        legs[-1].dur += tt - sum(x.dur for x in legs)
                    legs[0].v0, legs[0].v1, legs[0].span = v0, v1, len(legs)
                else:
                    legs = [Phase("turn", tt, a=here, b=here, v0=v0, v1=v1, least=MIN_TURN)]
            ph += legs
            ph += _legs(target, s, ch.rapid, rf, False)
            ph[-1].after = "swap"
            ph += _legs(s, target, ch.rapid, rf, True)
            here = target
        else:                                          # the new tool is put in by hand
            pl = ch.pause_length()
            ph.append(Phase("pause", pl, a=here, b=here, hand=ch.hand, after="swap",
                            least=HAND_MIN if ch.hand else min(pl, MIN_PAUSE)))
            c.note = f"T{new} has no pocket: it is put in by hand"
        if seq_b > 0:
            ph.append(Phase("seq", seq_b / speed, a=here, b=here, s0=seq_a, s1=ch.seq))
        ph += _role(_legs(here, p, ch.rapid, rf, False), "back")
        c.moves = True
    else:
        where = resolve(p, ch.position) if ch.position is not None else p
        moves = math.dist(where, p) > 1e-9
        out = _role(_legs(p, where, ch.rapid, rf, True), "out") if moves else []
        ph += out
        if ch.atc and ch.seq > 0:                      # a changer animation without pockets (task 0026)
            ph.append(Phase("seq", seq_a / speed, a=where, b=where, s0=0.0, s1=seq_a, after="swap"))
            ph.append(Phase("seq", seq_b / speed, a=where, b=where, s0=seq_a, s1=ch.seq))
        else:
            pl = ch.pause_length()
            ph.append(Phase("pause", pl, a=where, b=where, hand=ch.hand, after="swap",
                            least=HAND_MIN if ch.hand else min(pl, MIN_PAUSE)))
        ph += _role(_legs(where, p, ch.rapid, rf, False), "back") if moves else []
        c.moves = moves
    c.phases = ph
    return c


def place(c: Change, start: float, scale: float = 1.0) -> Change:
    """Put the change at ``start`` (s), each phase ``scale`` times its length (but not under its minimum); sets the
    swap and drop moments, the hand and the ramps of the tool length offsets."""
    t = start
    c.start = start
    c.drop = c.swap = None
    for ph in c.phases:
        ph.t0 = t
        ph.dur = max(ph.least, ph.dur * scale) if ph.dur > 0 else 0.0
        if ph.kind == "pause" and ph.after == "swap":
            if ph.hand and ph.dur > 0:              # the hand takes the old tool out, later puts the new one in
                c.hand = (t, ph.dur)
                out_t, in_t = hand_events(t, ph.dur)
            else:                                   # half way through the pause
                out_t = in_t = t + ph.dur / 2
            c.drop = out_t if c.drop is None else c.drop
            c.swap = in_t
        t += ph.dur
        if ph.after == "drop" and c.drop is None:
            c.drop = t
        if ph.after == "swap" and c.swap is None and ph.kind != "pause":
            c.swap = t
    c.length = t - start
    if c.swap is None:
        c.swap = start + (c.length / 2 if c.length > 0 else 0.0)
    if c.drop is None or c.drop > c.swap:
        c.drop = c.swap
    outs = [ph for ph in c.phases if ph.role == "out"]
    backs = [ph for ph in c.phases if ph.role == "back"]
    if c.moves and outs and backs:              # the tool length offsets ramp on the way out and the way back
        c.out_end = outs[-1].t0 + outs[-1].dur
        c.back_start = backs[0].t0
    else:
        c.out_end = c.back_start = c.swap
    return c


def fit(changes: list, target: float) -> float:
    """The factor every phase is scaled by so all changes together last ``target`` seconds (each phase not under its
    minimum). 1 when they already fit."""
    def total(k):
        return sum(max(ph.least, ph.dur * k) if ph.dur > 0 else 0.0 for c in changes for ph in c.phases)
    if total(1.0) <= target + 1e-9:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if total(mid) > target:
            hi = mid
        else:
            lo = mid
    return lo
