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

Double-arm changer (task 0064, ``Changer.arm``): the tools stand in pots of a magazine; the head goes to the change
position while the spindle stops at its orient angle; the magazine turns the new tool's pot to the change station
and the pot tips down (both already at the Tn before the M6 when the program has one: :func:`prep`, placed by
``Schedule`` while the machine still cuts). Then the arm turns from rest and grips both tools, pulls them out, turns
180°, pushes them in and turns back; the pot tips up and the head goes back. The old tool lands in the pot the new one
came from (random pockets: ``Schedule`` keeps the table). Such a change's phases run in *groups* one after the other;
the phases of a group's *tracks* (head, spindle, magazine, arm) run side by side.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

TURN = 2.0 * math.pi
MIN_TURN = 0.2               # s: the shortest carousel turn (also when "Fit into" squeezes the changes)
MIN_PAUSE = 0.2              # s: the shortest manual pause when "Fit into" squeezes the changes
CHANGE_SHARE = 0.5           # "Fit into": tool changes may take at most this share of the step's seconds
PAUSE_MAX = 5.0              # s: the pause slider's end

#: double-arm changer (task 0064): seconds of each arm phase at "ATC speed" 1 (a BT30 tool-to-tool change about
#: 1.5–2.5 s), and the shortest each may get when "Fit into" squeezes the changes
ARM_PHASES = ("grip", "pull", "swap", "push", "back")
ARM_TIMES = {"grip": 0.3, "pull": 0.25, "swap": 0.5, "push": 0.25, "back": 0.3}
ARM_MIN = 0.08
ORIENT_TIME = 0.3            # s: the spindle stops at its orient angle (M19) on the way to the change position
TIP_TIME = 0.4               # s: a pot tips down (or up) at the change station
TIP_MIN = 0.1

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
    # double-arm changer (task 0064): ``arm_times`` {phase: s at speed 1}; ``tip``: s a pot takes to tip (0: the pots
    # do not tip); ``orient``: s the spindle takes to stop at its orient angle
    # task 0096: {T: mm} each tool's length offset (how far the spindle sits higher for it than for the reference
    # tool). The head's way to and from the changer is planned for the spindle, so a longer new tool never comes back
    # lower than the program's point; a manual change in place lifts the spindle before a longer tool goes in.
    lengths: dict = field(default_factory=dict)
    arm: bool = False
    arm_times: dict = field(default_factory=lambda: dict(ARM_TIMES))
    tip: float = 0.0
    orient: float = ORIENT_TIME

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
    group: int = -1              # double-arm changes: phases of one group run side by side, one per track, the
    track: str = ""              # groups one after the other (-1: every phase after the one before)
    name: str = ""               # 'arm' phases: grip, pull, swap, push, back; 'tip': down, up
    pocket: int | None = None    # 'tip' / 'turn' of a double-arm change: the pot it moves to the station or tips


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
    kind: str = ""               # 'arm': a double-arm change (task 0064)
    prep: list = field(default_factory=list)   # double-arm: the magazine's turn and the pot's tip at the Tn before
    pre_at: float | None = None  # the Tn's moment (s) when ``prep`` plays before the change (pre-indexed)
    index: int = 0               # double-arm: how many double-arm changes came before this one in the step
    h_old: int = 0               # task 0096: whose length offset is in force before / after the change (the new
    h: int = 0                   # tool's, unless the program has no G43 for it)
    lift_end: float = 0.0        # task 0096: the spindle's length adjustment ends with the first leg out and
    lift_start: float = 0.0      # starts with the last leg back (the head's path is planned for the spindle)
    lift_mid: float = 0.0        # the lift in between: 0 at a pocket, the longer tool's at a manual change position

    def total(self, k: float = 1.0) -> float:
        """Its length with every phase ``k`` times as long (not under its minimum): groups side by side."""
        return group_length(self.phases, k)

    def arm_times(self) -> dict:
        """{arm phase: (start, end)} of a double-arm change, once placed."""
        return {ph.name: (ph.t0, ph.t0 + ph.dur) for ph in self.phases if ph.kind == "arm"}

    def tips(self) -> list:
        """[(t0, t1, pocket, down)] of the pot tipping (``down``: tipping down), the Tn's included."""
        return [(ph.t0, ph.t0 + ph.dur, ph.pocket, ph.name == "down") for ph in self.prep + self.phases
                if ph.kind == "tip" and ph.dur > 0]

    def orient_span(self):
        """(start, end) of the spindle stopping at its orient angle, or None."""
        for ph in self.phases:
            if ph.kind == "orient":
                return ph.t0, ph.t0 + ph.dur
        return None

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
        """[(t0, t1, v0, v1)] of the carousel (a double-arm change: its turn at the Tn too)."""
        out = [(ph.t0, ph.t0 + ph.dur, ph.v0, ph.v1) for ph in self.prep
               if ph.v0 is not None and abs(ph.v1 - ph.v0) > 1e-12]
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


def _way(a: tuple, b: tuple, rapid, rf: float) -> list:
    """Rapids from ``a`` to ``b`` that never go below the lower end: up first when going up, down last when going
    down (task 0096)."""
    return _legs(a, b, rapid, rf, b[2] > a[2] + 1e-9)


def _spindle(p: tuple, lift: float) -> tuple:
    return (p[0], p[1], p[2] + lift)


def _shift(legs: list, dz: float) -> list:
    """Legs planned for the spindle, as the reference tip's path when the spindle sits ``dz`` mm higher."""
    if dz:
        for ph in legs:
            ph.a, ph.b = _spindle(ph.a, -dz), _spindle(ph.b, -dz)
    return legs


def _from_program(legs: list, p: tuple) -> list:
    """The first leg of the way out starts at the program's point (the spindle's lift fades on it)."""
    if legs:
        legs[0].a = p
    return legs


def _to_program(legs: list, p: tuple) -> list:
    """The last leg of the way back ends at the program's point (the new tool's lift grows on it)."""
    if legs:
        legs[-1].b = p
    return legs


def lengths_of(ch: Changer, h_old: int, h_new: int) -> tuple[float, float]:
    """(mm, mm): the spindle's lift for the offset in force before and after a change."""
    lg = ch.lengths or {}
    return float(lg.get(h_old, 0.0)), float(lg.get(h_new, 0.0))


def plan(old: int, new: int, p: tuple, ch: Changer, carousel_value: float, rapid_factor: float = 1.0,
         h_old: int | None = None, h_new: int | None = None) -> Change:
    """The phases of one tool change from tool ``old`` to ``new`` with the head at ``p`` (machine mm) and the carousel
    at ``carousel_value``. Times are relative (``place`` puts them on the time line). ``h_old`` / ``h_new``: the tools
    whose length offsets are in force before and after (default: ``old`` / ``new``). The way out and back is planned
    for the spindle (``Changer.lengths``): its first knot and last knot are the program's point, where the lift of the
    old / new offset fades out and in (:func:`lift_knots`)."""
    c = Change(tool=new, old=old)
    rf = max(1e-6, float(rapid_factor or 1.0))
    speed = max(1e-3, float(ch.speed or 1.0))
    p = tuple(float(x) for x in p)
    cur_l, new_l = lengths_of(ch, old if h_old is None else h_old, new if h_new is None else h_new)
    p_out, p_back = _spindle(p, cur_l), _spindle(p, new_l)
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
        out = _role(_from_program(_way(p_out, here, ch.rapid, rf), p), "out")
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
        ph += _role(_to_program(_way(here, p_back, ch.rapid, rf), p), "back")
        c.moves = True
    else:
        where = resolve(p, ch.position) if ch.position is not None else p
        where = (where[0], where[1], max(where[2], p[2]))  # never lower than the program's point (task 0096)
        moves = math.dist(where, p) > 1e-9
        # no pocket here: the spindle sits as high as the longer of the two tools needs, so both tips stay at or
        # above the change position (and so above the program's point)
        c.lift_mid = max(cur_l, new_l)
        w_s = _spindle(where, c.lift_mid)
        out = _role(_from_program(_shift(_way(p_out, w_s, ch.rapid, rf), c.lift_mid), p), "out") if moves else []
        ph += out
        if ch.atc and ch.seq > 0:                      # a changer animation without pockets (task 0026)
            ph.append(Phase("seq", seq_a / speed, a=where, b=where, s0=0.0, s1=seq_a, after="swap"))
            ph.append(Phase("seq", seq_b / speed, a=where, b=where, s0=seq_a, s1=ch.seq))
        else:
            pl = ch.pause_length()
            ph.append(Phase("pause", pl, a=where, b=where, hand=ch.hand, after="swap",
                            least=HAND_MIN if ch.hand else min(pl, MIN_PAUSE)))
        ph += _role(_to_program(_shift(_way(w_s, p_back, ch.rapid, rf), c.lift_mid), p), "back") if moves else []
        c.moves = moves
    c.phases = ph
    return c


def place(c: Change, start: float, scale: float = 1.0) -> Change:
    """Put the change at ``start`` (s), each phase ``scale`` times its length (but not under its minimum); sets the
    swap and drop moments, the hand and the ramps of the tool length offsets."""
    if c.kind == "arm":
        return _place_arm(c, start, scale)
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
    _lift_span(c, outs, backs)
    return c


def _lift_span(c: Change, outs: list, backs: list) -> None:
    if c.moves and outs and backs:
        first = min(outs, key=lambda ph: ph.t0)
        last = max(backs, key=lambda ph: ph.t0)
        c.lift_end = first.t0 + first.dur
        c.lift_start = last.t0
    else:
        c.lift_end, c.lift_start = c.out_end, c.back_start


def lift_knots(c: Change, cur: float, new: float) -> list:
    """[(s, lift)] of the spindle over one placed change (task 0096): ``cur`` / ``new`` the lift of the offset in
    force before and after (any unit). The head goes somewhere: the lift fades on the first leg out (the path was
    planned for the spindle, so the tip only rises) and grows on the last leg back. The head stays: before a longer
    tool goes in, the spindle rises (while the hand has the old tool away, else from the change's start), and after
    the swap it comes down to the new tool's lift - the new tool's tip never goes below the program's point."""
    if c.length <= 0:
        return []
    end = c.start + c.length
    if c.moves and c.lift_end > c.start - 1e-12:
        return [(c.start, cur), (c.lift_end, c.lift_mid), (c.lift_start, c.lift_mid), (end, new)]
    if c.kind == "arm":                          # the arm hands the tools over at the spindle: it does not move then
        return [(c.swap, cur), (end, new)]
    hi = max(cur, new)
    up = c.drop if c.swap - c.drop > 1e-6 else c.start
    knots = [(c.start, cur)]
    if up > c.start + 1e-9:
        knots.append((up, cur))
    knots += [(c.swap, hi), (end, new)]
    return knots


def fit(changes: list, target: float) -> float:
    """The factor every phase is scaled by so all changes together last ``target`` seconds (each phase not under its
    minimum). 1 when they already fit."""
    def total(k):
        return sum(c.total(k) for c in changes)
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


# ---------------------------------------------------------------------------
# double-arm changer (task 0064)
# ---------------------------------------------------------------------------

def scaled(ph: Phase, k: float) -> float:
    """A phase's length when every phase is ``k`` times as long (not under its minimum)."""
    return max(ph.least, ph.dur * k) if ph.dur > 0 else 0.0


def group_length(phases: list, k: float = 1.0) -> float:
    """Length of phases where those of a group (``group`` >= 0) run side by side, one track after the other each."""
    total = 0.0
    groups: dict = {}
    for ph in phases:
        if ph.group < 0:
            total += scaled(ph, k)
        else:
            tracks = groups.setdefault(ph.group, {})
            tracks[ph.track] = tracks.get(ph.track, 0.0) + scaled(ph, k)
    return total + sum(max(t.values(), default=0.0) for t in groups.values())


def _arm_time(ch: Changer, name: str) -> float:
    return max(0.0, float(ch.arm_times.get(name, ARM_TIMES[name]))) / max(1e-3, float(ch.speed or 1.0))


def prep(ch: Changer, pocket, v: float) -> tuple[list, float]:
    """The magazine's work before the arm can take the tool from ``pocket``: turn it to the station (the shortest way,
    from carousel value ``v``) and tip the pot down. Returns (phases, carousel value after)."""
    out = []
    speed = max(1e-3, float(ch.speed or 1.0))
    if pocket is None:
        return out, v
    if pocket in ch.carousel:
        v1 = nearest_turn(v, ch.carousel[pocket], ch.carousel_limits)
        if abs(v1 - v) > 1e-9:
            tt = max(MIN_TURN, abs(v1 - v) / max(1e-9, ch.pitch) * ch.turn_time) / speed
            out.append(Phase("turn", tt, v0=v, v1=v1, least=MIN_TURN, track="mag", pocket=pocket))
        v = v1
    if ch.tip > 0:
        out.append(Phase("tip", ch.tip / speed, least=TIP_MIN, track="mag", name="down", pocket=pocket))
    return out, v


def plan_arm(old: int, new: int, p: tuple, ch: Changer, carousel_value: float, pockets: dict,
             rapid_factor: float = 1.0, pre: bool = False, h_old: int | None = None,
             h_new: int | None = None) -> tuple[Change, float]:
    """One double-arm change from tool ``old`` to ``new`` with the head at ``p`` (machine mm), the carousel at
    ``carousel_value`` and the tools in ``pockets`` ({T: pot}, now). ``pre``: the magazine already did its work at
    the Tn before (the phases are in ``Change.prep``, placed by ``Schedule``). Returns (change, carousel value after).
    A new tool without a pot is put in by hand (a pause, as a manual change)."""
    rf = max(1e-6, float(rapid_factor or 1.0))
    speed = max(1e-3, float(ch.speed or 1.0))
    p = tuple(float(x) for x in p)
    pn = pockets.get(new)
    if old == new and old:
        return Change(tool=new, old=old), carousel_value
    if pn is None:
        c = plan(old, new, p, Changer(position=ch.position, pause=ch.pause, hand=ch.hand, rapid=ch.rapid,
                                      lengths=ch.lengths), 0.0, rf, h_old=h_old, h_new=h_new)
        c.note = f"T{new} has no pot in the magazine: it is put in by hand"
        return c, carousel_value
    c = Change(tool=new, old=old, kind="arm", old_pocket=pn, new_pocket=pn)
    where = resolve(p, ch.position) if ch.position is not None else p
    c.moves = math.dist(where, p) > 1e-9
    cur_l, new_l = lengths_of(ch, old if h_old is None else h_old, new if h_new is None else h_new)
    mag, v = prep(ch, pn, carousel_value)
    ph: list = []
    for x in _role(_from_program(_way(_spindle(p, cur_l), where, ch.rapid, rf), p), "out") if c.moves else []:
        x.group, x.track = 0, "head"
        ph.append(x)
    if ch.orient > 0:
        ph.append(Phase("orient", ch.orient / speed, a=where, b=where, least=min(ch.orient / speed, ARM_MIN),
                        group=0, track="spindle"))
    if pre:
        c.prep = mag
    else:
        for x in mag:
            x.group = 0
        ph += mag
    for name in ARM_PHASES:
        d = _arm_time(ch, name)
        ph.append(Phase("arm", d, a=where, b=where, least=min(d, ARM_MIN), group=1, track="arm", name=name,
                        after={"grip": "drop", "push": "swap"}.get(name, "")))
    for x in _role(_to_program(_way(where, _spindle(p, new_l), ch.rapid, rf), p), "back") if c.moves else []:
        x.group, x.track = 2, "head"
        ph.append(x)
    if ch.tip > 0:
        ph.append(Phase("tip", ch.tip / speed, least=TIP_MIN, group=2, track="mag", name="up", pocket=pn))
    c.phases = ph
    return c, v


def _place_arm(c: Change, start: float, scale: float) -> Change:
    t = start
    c.start = start
    for g in sorted({ph.group for ph in c.phases}):
        ends = {}
        for ph in (x for x in c.phases if x.group == g):
            ph.dur = scaled(ph, scale)
            ph.t0 = ends.get(ph.track, t)
            ends[ph.track] = ph.t0 + ph.dur
        t = max(ends.values(), default=t)
    c.length = t - start
    times = c.arm_times()
    c.drop = times["grip"][1] if "grip" in times else start
    c.swap = times["push"][1] if "push" in times else start + c.length
    outs = [ph for ph in c.phases if ph.role == "out"]
    backs = [ph for ph in c.phases if ph.role == "back"]
    if c.moves and outs and backs:
        c.out_end = max(ph.t0 + ph.dur for ph in outs)
        c.back_start = min(ph.t0 for ph in backs)
    else:
        c.out_end = c.back_start = c.swap
    _lift_span(c, outs, backs)
    return c


def arm_start(c: Change) -> float:
    """When the arm starts to turn (s), once placed."""
    times = c.arm_times()
    return times["grip"][0] if "grip" in times else c.start


def place_prep(c: Change, at: float, scale: float) -> float:
    """Put a pre-indexed change's magazine work from ``at`` on (each phase scaled); returns when it is done."""
    t = at
    for ph in c.prep:
        ph.dur = scaled(ph, scale)
        ph.t0 = t
        t += ph.dur
    return t
