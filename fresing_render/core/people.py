"""People in the scene (task 0157): paths, gaits, actions, carried items, meetings – worked out without Blender.

What comes in (from ``blender/people.py``): one ``PersonSpec`` per person (its height, where it stands, the points of
its path, its list of ``Action``s, the item it holds at the start), the ``ItemSpec``s lying in the scene, and
``ground(x, y, z_near) -> z``: the height of the surface below a point (rays in Blender, a plane in the tests).
``plan(people, items, ground)`` lays the actions out in time (``Plan``): walks, turns, waits for another person,
handshakes and talks that both people start together. ``Plan.sample(fps)`` then gives every frame of every person
(root place + heading + ``person_rig.Pose``) and the items' states (held by a hand / lying at a world matrix).

**Walking.** The feet are put down in the world (``Plant``): each step lands on the path at a fixed distance, the
left foot left of it and the right foot right of it; between two plants a foot swings in an arc. A foot rolls on its
heel when it lands and on its ball when it leaves, so the point it stands on never slides. The steps of one walk are
fitted so the last one lands on the walk's end point (the gait's step length changed by at most half a step), and the
time follows from the gait's speed: speed = step length x steps per second. The legs are turned to the feet by
``person_rig.Figure.leg_ik``; the pelvis is lowered where a leg would otherwise not reach.

Angles in radians unless a name says ``_deg``; lengths in metres; times in seconds from the animation's first frame.
The figure faces -y in its own space; a heading ``h`` turns it about z (``h`` = 0: facing -y).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import person_rig as R
from . import props_detail as P

# ---------------------------------------------------------------------------
# the choices (ids are stored in project files)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Gait:
    label: str
    speed: float              # m/s
    step: float               # one step (heel to heel), metres for a 1.75 m person
    duty: float               # share of a stride a foot is on the floor (< 0.5: a run, both feet off for a moment)
    lift: float               # how high the swinging ankle rises above where it stands, m
    drop: float               # the pelvis below standing height, m
    lean_deg: float           # forward lean of the body
    swing_deg: float          # arms swing forward and back
    elbow_deg: float          # elbows bent
    twist_deg: float          # pelvis turn with the steps


GAITS = {
    "STROLL": Gait("Stroll", 0.9, 0.6, 0.64, 0.05, 0.02, 1.0, 10.0, 12.0, 3.0),
    "WALK": Gait("Walk", 1.35, 0.72, 0.62, 0.07, 0.03, 2.0, 16.0, 18.0, 4.0),
    "BRISK": Gait("Brisk", 1.75, 0.8, 0.6, 0.08, 0.04, 4.0, 24.0, 30.0, 5.5),
    "CARRY": Gait("Carry-walk", 1.0, 0.58, 0.66, 0.05, 0.04, -2.0, 8.0, 15.0, 2.5),
    "RUN": Gait("Run", 3.2, 1.15, 0.38, 0.16, 0.05, 9.0, 30.0, 85.0, 7.0),
}
GAIT_ITEMS = (
    ("STROLL", "Stroll", "Slow and relaxed: 0.9 m/s, short steps"),
    ("WALK", "Walk", "A normal walk: 1.35 m/s"),
    ("BRISK", "Brisk", "A brisk walk, in a hurry: 1.75 m/s, longer steps, the arms swing more"),
    ("CARRY", "Carry-walk", "Slow, shorter steps for something heavy carried in both hands: 1.0 m/s"),
    ("RUN", "Run", "Running: 3.2 m/s, both feet off the floor for a moment, elbows bent"),
)

ACTION_ITEMS = (
    ("WALK", "Walk", "Walk along the path to a point (or its end) with the gait you pick"),
    ("STOP", "Stop", "Stand still for a while, breathing; the feet stay where they are"),
    ("TURN", "Turn to face", "Turn on the spot (two small steps) to face a person, a part or a point"),
    ("PICK_UP", "Pick up", "Bend down and pick up an item lying within reach; the person then carries it"),
    ("PUT_DOWN", "Put down", "Bend down and put the carried item on whatever is in front: the floor, a table, a "
                             "part's top"),
    ("WAVE", "Wave", "Wave with the right hand"),
    ("GREET", "Greet", "Shake hands with another person who greets this person too: both turn to each other, reach "
                       "out and shake – whoever is there first waits. Without a greeting back: a wave"),
    ("TALK", "Talk", "Talk with another person: they face each other and take turns, with hand gestures, nods "
                     "and head turns. Both start when both are there"),
    ("POINT", "Point at", "Point at a part, a person or a point with the right arm"),
    ("LOOK", "Look at", "Turn the head (and a little the chest) to look at a part, a person or a point"),
    ("IDLE", "Idle", "Stand and wait: shift weight, look around a little"),
    ("OPERATE", "Operate", "Both hands on a panel or a part at a point you pick, pressing buttons"),
)
ACTIONS = tuple(a[0] for a in ACTION_ITEMS)
NEEDS_OTHER = ("GREET", "TALK")
NEEDS_TARGET = ("TURN", "POINT", "LOOK", "OPERATE")
HAS_DURATION = ("STOP", "WAVE", "TALK", "POINT", "LOOK", "IDLE", "OPERATE")
DEFAULT_DURATION = {"STOP": 1.5, "WAVE": 2.0, "TALK": 8.0, "POINT": 2.5, "LOOK": 2.0, "IDLE": 4.0, "OPERATE": 4.0}

PLACE_ITEMS = (
    ("HERE", "Here", "Where the person stands after the step before"),
    ("POINT", "At a point", "Walk to a point of the path first (its number in the view)"),
    ("END", "At the end", "Walk to the end of the path first"),
)


@dataclass(frozen=True)
class ItemKind:
    label: str
    desc: str
    size: tuple               # length (x), width (y), height (z) of its box, m
    hands: str                # "R", "L" or "BOTH"
    style: str                # "SIDE" (hangs from the hand), "EDGE" (held by an edge in front), "FRONT" (both hands)
    heavy: bool = False


ITEMS = {
    "TOOLBOX": ItemKind("Toolbox", "A small red metal toolbox with a handle, carried at the side", (0.46, 0.2, 0.3),
                        "R", "SIDE"),
    "CLIPBOARD": ItemKind("Clipboard", "A clipboard with paper, held by its edge in front", (0.24, 0.32, 0.02), "L",
                          "EDGE"),
    "TABLET": ItemKind("Tablet", "A tablet in a rugged case, held by its edge in front", (0.27, 0.19, 0.016), "L",
                       "EDGE"),
    "HARD_HAT": ItemKind("Hard hat", "A white safety helmet carried by its brim", (0.28, 0.23, 0.16), "R", "SIDE"),
    "CABLE_DRUM": ItemKind("Cable drum", "A small wooden cable drum, carried in both hands", (0.32, 0.42, 0.42),
                           "BOTH", "FRONT", True),
    "CRATE": ItemKind("Crate", "A grey plastic crate, carried in both hands", (0.56, 0.38, 0.3), "BOTH", "FRONT", True),
    "SPANNER": ItemKind("Spanner", "A big open-ended spanner, held in the right hand", (0.32, 0.06, 0.016), "R",
                        "SIDE"),
    "HOSE": ItemKind("Hose", "A coil of black hose, carried by its top", (0.06, 0.42, 0.42), "R", "SIDE"),
}
ITEM_ITEMS = tuple((k, v.label, v.desc) for k, v in ITEMS.items())

# ---------------------------------------------------------------------------
# what comes in
# ---------------------------------------------------------------------------


@dataclass
class Action:
    kind: str
    place: str = "HERE"           # HERE / POINT / END
    point: int = 1                # the path point (1 = the first point clicked after the start)
    gait: str = "WALK"
    duration: float = 0.0         # 0: the kind's default
    other: str = ""               # another person (GREET, TALK, or the target of TURN / LOOK / POINT)
    target: tuple | None = None   # a world point (TURN / LOOK / POINT at a part or a point; OPERATE)
    item: str = ""                # PICK_UP: the item's name
    wait_person: str = ""         # start only when that person's step ``wait_step`` is done
    wait_step: int = 0


@dataclass
class PersonSpec:
    name: str
    height: float = P.DEFAULT_HEIGHT
    place: tuple = (0.0, 0.0, 0.0)    # where the person stands at the start (world)
    heading: float = 0.0              # its turn about z at the start
    path: tuple = ()                  # the points clicked after the start, world (x, y[, z])
    actions: tuple = ()
    start: float = 0.0                # seconds before it starts
    carry: str = ""                   # the item (its name) in hand at the start


@dataclass
class ItemSpec:
    name: str
    kind: str
    place: tuple = (0.0, 0.0, 0.0)    # base centre, world
    heading: float = 0.0              # turn about z (0: its length along x)


def flat_ground(z: float = 0.0):
    return lambda x, y, z_near=None: z


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def heading_of(d) -> float:
    """The heading that makes the figure (facing -y) face along the horizontal direction ``d``."""
    return math.atan2(float(d[0]), -float(d[1]))


def facing(h: float) -> np.ndarray:
    """The unit direction a figure with heading ``h`` faces."""
    return np.array((math.sin(h), -math.cos(h)))


def left_of(h: float) -> np.ndarray:
    """The figure's left side (its +x) with heading ``h``."""
    return np.array((math.cos(h), math.sin(h)))


def wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def smooth01(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def m4(Rm, p) -> np.ndarray:
    M = np.eye(4)
    M[:3, :3] = Rm
    M[:3, 3] = p
    return M


def inv4(M) -> np.ndarray:
    out = np.eye(4)
    out[:3, :3] = M[:3, :3].T
    out[:3, 3] = -M[:3, :3].T @ M[:3, 3]
    return out


# ---------------------------------------------------------------------------
# the path
# ---------------------------------------------------------------------------


class Path:
    """A walk along points (x, y): inner corners rounded with ``radius``, run through by arc length ``s``."""

    def __init__(self, points, radius: float = 0.6):
        pts = [np.asarray(p[:2], float) for p in points]
        keep = [pts[0]]
        for p in pts[1:]:
            if np.linalg.norm(p - keep[-1]) > 1e-4:
                keep.append(p)
        pts = keep
        if len(pts) > 2:
            pts3 = P.rounded_path([(p[0], p[1], 0.0) for p in pts], radius, 8)
            pts = [np.asarray(p[:2], float) for p in pts3]
        self.pts = np.asarray(pts, float).reshape(-1, 2)
        seg = np.linalg.norm(np.diff(self.pts, axis=0), axis=1) if len(self.pts) > 1 else np.zeros(0)
        self.s = np.concatenate([[0.0], np.cumsum(seg)])
        self.length = float(self.s[-1])

    def at(self, s: float) -> np.ndarray:
        if len(self.pts) == 1:
            return self.pts[0].copy()
        s = min(max(s, 0.0), self.length)
        i = int(np.clip(np.searchsorted(self.s, s, side="right") - 1, 0, len(self.pts) - 2))
        d = self.s[i + 1] - self.s[i]
        u = (s - self.s[i]) / d if d > 1e-12 else 0.0
        return self.pts[i] + (self.pts[i + 1] - self.pts[i]) * u

    def tangent(self, s: float, window: float = 0.12) -> np.ndarray:
        if self.length < 1e-6:
            return np.array((0.0, -1.0))
        a = self.at(max(0.0, s - window))
        b = self.at(min(self.length, s + window))
        d = b - a
        n = float(np.linalg.norm(d))
        return d / n if n > 1e-9 else np.array((0.0, -1.0))

    def turn_at(self, s: float) -> float:
        """How sharply the path turns at ``s`` (radians per metre)."""
        a, b = self.tangent(s - 0.15), self.tangent(s + 0.15)
        return abs(math.atan2(a[0] * b[1] - a[1] * b[0], float(np.dot(a, b)))) / 0.3


# ---------------------------------------------------------------------------
# feet
# ---------------------------------------------------------------------------

HEEL_ROLL = math.radians(18)        # toes up when the heel lands
TOE_ROLL = math.radians(32)         # heel up when the foot leaves
HEEL_AT, TOE_AT = -0.06, 0.212      # where the sole's back and front edges are, along the foot from the ankle
HEEL_SHARE, TOE_SHARE = 0.16, 0.42  # of the stance the heel / the ball rolls


@dataclass
class Plant:
    """A foot standing on the floor: its ankle (when flat) and heading, from ``down`` (lands, heel first) to ``up``
    (leaves, ball last). ``roll_in`` / ``roll_out``: how long the heel / ball roll take (0: put flat / lifted flat)."""
    pos: np.ndarray               # ankle when the foot is flat (world)
    yaw: float
    down: float = -math.inf
    up: float = math.inf
    roll_in: float = 0.0
    roll_out: float = 0.0
    lift: float = 0.07            # how high the swing to the next plant rises


class Foot:
    """The plants of one foot in time order; the swing between two plants."""

    def __init__(self, side: str, first: Plant):
        self.side = side
        self.plants = [first]

    @property
    def last(self) -> Plant:
        return self.plants[-1]

    def step_to(self, pos, yaw, t_up, t_down, roll_out, roll_in, lift):
        last = self.plants[-1]
        last.up = t_up
        last.roll_out = roll_out
        last.lift = lift
        self.plants.append(Plant(np.asarray(pos, float), float(yaw), t_down, math.inf, roll_in, 0.0, lift))

    def state(self, t: float, k: float):
        """(ankle position, yaw, pitch (toes up > 0)) at time ``t``; ``k`` = the person's size factor."""
        pl = self.plants
        lo, hi = 0, len(pl) - 1
        while lo < hi:                    # the last plant that has landed by t
            mid = (lo + hi + 1) // 2
            if pl[mid].down <= t:
                lo = mid
            else:
                hi = mid - 1
        p = pl[lo]
        if t <= p.up:                     # standing on it (perhaps rolling)
            if p.roll_in > 0 and t < p.down + p.roll_in:
                u = (t - p.down) / p.roll_in
                return _roll(p.pos, p.yaw, HEEL_ROLL * (1 - smooth01(u)), "heel", k)
            if p.roll_out > 0 and t > p.up - p.roll_out:
                u = (t - (p.up - p.roll_out)) / p.roll_out
                return _roll(p.pos, p.yaw, -TOE_ROLL * smooth01(u) ** 1.3, "ball", k)
            return p.pos.copy(), p.yaw, 0.0
        if lo + 1 >= len(pl):
            return p.pos.copy(), p.yaw, 0.0
        q = pl[lo + 1]                    # swinging from p to q
        u = (t - p.up) / max(1e-6, q.down - p.up)
        a_pos, _y, a_pitch = _roll(p.pos, p.yaw, -TOE_ROLL if p.roll_out > 0 else 0.0, "ball", k)
        b_pos, _y, b_pitch = _roll(q.pos, q.yaw, HEEL_ROLL if q.roll_in > 0 else 0.0, "heel", k)
        e = smooth01(u)
        pos = a_pos + (b_pos - a_pos) * e
        pos[2] += p.lift * k * math.sin(math.pi * min(1.0, max(0.0, u))) ** 1.2
        yaw = p.yaw + wrap(q.yaw - p.yaw) * e
        pitch = a_pitch + (b_pitch - a_pitch) * smooth01(min(1.0, u * 1.25))
        return pos, yaw, pitch

    def on_floor(self, t: float):
        """The plant the foot stands on at ``t`` (None while it swings)."""
        for p in self.plants:
            if p.down <= t <= p.up:
                return p
        return None


def _roll(flat_ankle, yaw, pitch, pivot, k):
    """The ankle of a foot turned ``pitch`` (toes up > 0) about its heel or its ball, which stay on the floor."""
    F = np.array((math.sin(yaw), -math.cos(yaw), 0.0))
    U = np.array((0.0, 0.0, 1.0))
    base = flat_ankle - U * (P.ANKLE_H * k)
    piv = base + F * ((HEEL_AT if pivot == "heel" else TOE_AT) * k)
    v = flat_ankle - piv
    a, b = float(np.dot(v, F)), float(np.dot(v, U))
    c, s = math.cos(pitch), math.sin(pitch)
    # toes up (pitch > 0) turns the foot's front up: a point ahead of the pivot rises
    na, nb = a * c - b * s, a * s + b * c
    return piv + F * na + U * nb, yaw, pitch


def foot_frame(yaw: float, pitch: float) -> np.ndarray:
    """A foot's frame (props_detail's: x across, y back, z up) for a heading and a pitch (toes up > 0)."""
    return R.rz(yaw) @ R.rx(-pitch)


# ---------------------------------------------------------------------------
# items: shapes, grips
# ---------------------------------------------------------------------------


def item_shapes(kind: str) -> list:
    """The item's shapes (``core/surroundings`` shapes), its base centre at the origin, its length along x."""
    from .surroundings import Box, Tube
    L, W, H = ITEMS[kind].size
    s: list = []
    if kind == "TOOLBOX":
        s.append(P.rbox("item_red", 0, 0, 0, L, W, H - 0.06, 0.012, 2))
        s.append(P.rbox("item_red_dark", 0, 0, H - 0.075, L + 0.006, W + 0.006, 0.02, 0.006, 1))
        s.append(Box("item_steel", 0.0, -W / 2 - 0.004, H - 0.12, 0.06, 0.008, 0.03))
        handle = P.rounded_path([(-0.12, 0, H - 0.06), (-0.12, 0, H - 0.005), (0.12, 0, H - 0.005),
                                 (0.12, 0, H - 0.06)], 0.025, 4)
        s.append(P.sweep("item_black", handle, 0.011, 10, True))
    elif kind == "CLIPBOARD":
        s.append(P.rbox("item_board", 0, 0, 0, L, W, 0.006, 0.006, 1))
        s.append(Box("item_paper", 0.0, -0.005, 0.006, L - 0.03, W - 0.05, 0.002))
        s.append(P.rbox("item_steel", 0, W / 2 - 0.03, 0.006, 0.11, 0.04, 0.012, 0.004, 1))
    elif kind == "TABLET":
        s.append(P.rbox("item_black", 0, 0, 0, L, W, H, 0.012, 2))
        s.append(Box("item_screen", 0.0, 0.0, H, L - 0.03, W - 0.03, 0.0008))
    elif kind == "HARD_HAT":
        s.append(P.ellipsoid("helmet_white", (0.0, 0.0, 0.035), 0.105, 0.125, 0.125, 16, lat_from=0.0))
        brim = [P._ellipse(np.array((0.0, 0.0, z)), np.array((1.0, 0, 0)), np.array((0, 1.0, 0)), rx, ry, 16)
                for z, rx, ry in ((0.04, 0.104, 0.124), (0.03, 0.115, 0.135), (0.024, 0.115, 0.135),
                                  (0.03, 0.104, 0.124))]
        s.append(P._loft("helmet_white", brim, caps=False))
    elif kind == "CABLE_DRUM":
        r = H / 2
        for x in (-L / 2 + 0.015, L / 2 - 0.015):
            s.append(Tube("item_wood", (x - 0.015, 0, r), (x + 0.015, 0, r), r, 24))
        s.append(Tube("item_cable", (-L / 2 + 0.03, 0, r), (L / 2 - 0.03, 0, r), r * 0.78, 24))
        s.append(Tube("item_wood", (-L / 2 + 0.03, 0, r), (L / 2 - 0.03, 0, r), r * 0.35, 12))
    elif kind == "CRATE":
        s.append(P.rbox("item_grey", 0, 0, 0, L, W, H, 0.015, 2))
        for x in (-L / 2 - 0.003, L / 2 + 0.003):
            s.append(Box("item_dark", x, 0.0, H - 0.09, 0.008, 0.14, 0.04))
        for y in (-W / 2 - 0.003, W / 2 + 0.003):
            for x in (-0.15, 0.0, 0.15):
                s.append(Box("item_dark", x, y, 0.06, 0.08, 0.008, H - 0.14))
    elif kind == "SPANNER":
        s.append(P.rbox("item_steel", 0.0, 0, 0, L - 0.08, 0.026, H, 0.006, 1))
        for x, sg in ((L / 2 - 0.04, 1), (-L / 2 + 0.035, -1)):
            s.append(P.rbox("item_steel", x, 0, 0, 0.07, 0.06, H, 0.008, 1))
            s.append(Box("item_dark", x + sg * 0.02, 0, 0.0, 0.035, 0.03, H + 0.001))
    elif kind == "HOSE":
        r = W / 2 - 0.02
        ring = [(0.0, r * math.sin(a), W / 2 + r * math.cos(a)) for a in np.linspace(0, 2 * math.pi, 33)]
        s.append(P.sweep("item_hose", ring, 0.02, 10, False))
        ring2 = [(0.025, (r - 0.03) * math.sin(a), W / 2 + (r - 0.03) * math.cos(a)) for a in
                 np.linspace(0, 2 * math.pi, 33)]
        s.append(P.sweep("item_hose", ring2, 0.02, 10, False))
        s.append(Box("item_red", 0.0, 0.0, W - 0.03, 0.08, 0.06, 0.035))
    return s


def _grip_local(side: str, k: float) -> np.ndarray:
    """Where a closed hand holds a handle, in its hand bone's frame (props_detail: fingers along -z)."""
    sd = 1.0 if side == "l" else -1.0
    return np.array((-sd * 0.028, 0.0, -0.088)) * k


def hand_in_item(kind: str, side: str, k: float) -> np.ndarray:
    """The hand bone's frame (4x4, its head = the wrist) in the item's coordinates while it holds the item."""
    it = ITEMS[kind]
    L, W, H = it.size
    if kind in ("TOOLBOX", "HOSE"):
        Rh = R.rz(math.radians(90))            # hanging hand, item along the walk
        handle = np.array((0.0, 0.0, H - 0.005)) if kind == "TOOLBOX" else np.array((0.0, 0.0, W - 0.02))
    elif kind == "HARD_HAT":
        Rh = R.rz(math.radians(90))
        handle = np.array((-0.125, 0.0, 0.03))
    elif kind == "SPANNER":
        Rh = np.column_stack(((0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (-1.0, 0.0, 0.0)))   # spanner hangs down
        handle = np.array((-0.06, 0.0, H / 2))
    elif it.style == "EDGE":                   # pinch the near edge, palm down, fingers over the top
        Rh = np.column_stack(((0.0, 0.0, 1.0), (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)))
        handle = np.array((0.0, -W / 2 + 0.02, H))
        if side == "r":
            Rh = np.column_stack(((0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)))
    else:                                      # FRONT: a hand at each end, fingers forward (item y = backwards)
        Rh = R.rx(math.radians(-90))
        x = -L / 2 - 0.01 if side == "r" else L / 2 + 0.01
        handle = np.array((x, 0.0, H * (0.72 if kind == "CRATE" else 0.5)))
    return m4(Rh, handle - Rh @ _grip_local(side, k))


def holding_hands(kind: str) -> tuple:
    return {"R": ("r",), "L": ("l",), "BOTH": ("r", "l")}[ITEMS[kind].hands]


def carry_item_frame(kind: str, fig: R.Figure, pose: R.Pose, fk=None) -> np.ndarray:
    """Where a carried item is in figure space (4x4) for this pose's chest, before the arms are posed (EDGE and
    FRONT items: in front of the chest; SIDE items: hanging from the shoulder at arm's length)."""
    it = ITEMS[kind]
    k = fig.k
    fk = fk or fig.fk(pose)
    ch, Rc, _t = fk["chest"]
    if it.style == "FRONT":
        Rm = Rc @ R.rx(math.radians(4))
        L, W, H = it.size
        h = H * (0.72 if kind == "CRATE" else 0.5)
        p = ch + Rc @ np.array((0.0, -(0.2 + W / 2) * k, -0.2 * k)) - Rm @ np.array((0.0, 0.0, h))
        return m4(Rm, p)
    if it.style == "EDGE":
        a = math.radians(48)
        Rm = Rc @ np.column_stack(((-1.0, 0.0, 0.0), (0.0, -math.cos(a), math.sin(a)), (0.0, math.sin(a),
                                                                                         math.cos(a))))
        H = it.size[2]
        edge = ch + Rc @ (np.array((0.06, -0.3, 0.0)) * k)
        return m4(Rm, edge - Rm @ np.array((0.0, -it.size[1] / 2 + 0.02, H)))
    # SIDE: the hand hangs beside the thigh; the item hangs from it
    side = "r" if it.hands == "R" else "l"
    sd = -1.0 if side == "r" else 1.0
    sh = fk[f"{side}_arm"][0]
    Rp = fk["pelvis"][1]
    wrist = sh + Rp @ (np.array((sd * 0.07, 0.01, -(R.Figure.ARM + R.Figure.FOREARM) * 0.985)) * k)
    hand = m4(Rp @ R.ry(math.radians(-6 * sd)), wrist)
    return hand @ inv4(hand_in_item(kind, side, k))


# ---------------------------------------------------------------------------
# the schedule
# ---------------------------------------------------------------------------


@dataclass
class Seg:
    """One stretch of a person's time line: what it does from ``t0`` to ``t1``."""
    kind: str                       # WALK, TURN, WAIT (waiting for someone), STOP, IDLE, PICK_UP, PUT_DOWN, WAVE,
    t0: float                       # HANDSHAKE, TALK, POINT, LOOK, OPERATE
    t1: float
    data: dict = field(default_factory=dict)


@dataclass
class Person:
    """A person's worked-out time line: root along the path, feet, segments, the item in hand over time."""
    spec: PersonSpec
    fig: R.Figure
    segs: list = field(default_factory=list)
    roots: list = field(default_factory=list)   # (t0, t1, fn(t) -> (x, y, z, heading)) in time order
    feet: dict = field(default_factory=dict)
    step_times: list = field(default_factory=list)   # per action: (start, end)
    step_places: list = field(default_factory=list)  # per action: (x, y, z, heading) when it starts its body
    held: list = field(default_factory=list)         # (t, item name or "") – what the hands hold from t on
    end: float = 0.0

    def root(self, t: float):
        for t0, t1, fn in self.roots:
            if t <= t1:
                return fn(max(t, t0))
        return self.roots[-1][2](self.roots[-1][1])

    def holding(self, t: float) -> str:
        cur = ""
        for tt, name in self.held:
            if tt <= t:
                cur = name
        return cur


@dataclass
class ItemState:
    t: float
    state: str                      # "HELD" or "PLACED"
    person: str = ""
    side: str = "r"                 # the hand bone ("r" / "l") the item rides on
    grip: np.ndarray | None = None  # HELD: the item in the hand bone's frame (props_detail frame, 4x4)
    world: np.ndarray | None = None  # PLACED: the item's world matrix


class Plan:
    """The worked-out schedule of every person; ``sample`` gives the frames."""

    def __init__(self):
        self.people: dict[str, Person] = {}
        self.items: dict[str, ItemSpec] = {}
        self.item_states: dict[str, list] = {}
        self.warnings: list[str] = []
        self.length = 0.0
        self.ground = flat_ground()

    def sample(self, fps: float, t_end: float | None = None) -> dict:
        """{person: [(root (x, y, z, heading), Pose)]} for frames 1 … n (frame f at time (f - 1) / fps)."""
        t_end = self.length if t_end is None else t_end
        n = int(math.floor(t_end * fps + 1e-6)) + 1
        times = [i / fps for i in range(n)]
        return {name: _sample_person(self, p, times) for name, p in self.people.items()}

    def pose_at(self, name: str, t: float):
        """One moment of one person (the Preview slider): (root, Pose)."""
        return _sample_person(self, self.people[name], [t])[0]


def _dur(a: Action) -> float:
    return float(a.duration) if a.duration and a.duration > 0 else DEFAULT_DURATION.get(a.kind, 1.0)


def plan(people: list, items: list = (), ground=None, iterations: int = 40) -> Plan:
    """Lay out every person's actions in time. Waits and paired actions (GREET, TALK) are settled by going over all
    people again until no time changes (a circle of waits is warned about and broken)."""
    pl = Plan()
    pl.ground = ground or flat_ground()
    pl.items = {it.name: it for it in items}
    ctx = _Ctx([p.name for p in people])
    _SPECS.clear()
    _SPECS.update({p.name: p for p in people})
    stable = False
    for _it in range(iterations):
        before = (dict(ctx.known), dict(ctx.pairs))
        ctx.prev, ctx.prev_items = pl.people, pl.item_states
        pl.people = {}
        pl.warnings = []
        pl.item_states = {it.name: [ItemState(0.0, "PLACED", world=_placed_matrix(it, pl.ground))] for it in items}
        for spec in people:
            person = _schedule(pl, spec, ctx)
            pl.people[spec.name] = person
            for i, (_t0, t1) in enumerate(person.step_times):
                ctx.known[(spec.name, i)] = t1
        if _it > 0 and _same(before, (ctx.known, ctx.pairs)):
            stable = True
            break
    if not stable and people:
        pl.warnings.append("Some people wait for each other in a circle (A waits for B, B for A): their times may "
                           "not line up – check the waits")
    for it in items:
        pl.item_states[it.name].sort(key=lambda s: s.t)
    pl.length = max([p.end for p in pl.people.values()] + [0.0])
    return pl


class _Ctx:
    """What the scheduling of one person knows of the others (from the round before)."""

    def __init__(self, names):
        self.names = names
        self.known: dict = {}             # (person, step index) -> end time
        self.pairs: dict = {}             # (kind, a, b, n) -> when a is ready for its n-th GREET / TALK with b
        self.prev: dict = {}              # person -> Person of the round before
        self.prev_items: dict = {}

    def where(self, name: str, t: float, specs=None):
        """Where another person stands at ``t`` (x, y), from the round before (None: not known yet)."""
        p = self.prev.get(name)
        if p is None or not p.roots:
            return None
        r = p.root(t)
        return np.array((r[0], r[1]))


def _same(a, b) -> bool:
    for x, y in zip(a, b):
        if x.keys() != y.keys():
            return False
        if any(abs(x[kk] - y[kk]) > 1e-6 for kk in x):
            return False
    return True


def _placed_matrix(it: ItemSpec, ground) -> np.ndarray:
    x, y, z = (float(c) for c in it.place)
    return m4(R.rz(it.heading), (x, y, z))


class _State:
    """Where a person is while its schedule is worked out."""

    def __init__(self, person: Person, ground):
        sp = person.spec
        self.p = person
        self.ground = ground
        self.k = person.fig.k
        self.xy = np.asarray(sp.place[:2], float)
        self.z = float(sp.place[2]) if len(sp.place) > 2 else float(ground(self.xy[0], self.xy[1], None))
        self.h = float(sp.heading)
        self.t = max(0.0, float(sp.start))
        self.point = 0                     # the path point the person stands on (0 = the start)
        self.lead = "r"
        wl = 0.1 * self.k
        L = left_of(self.h)
        for side, sg in (("l", 1.0), ("r", -1.0)):
            pos = self.ankle(self.xy + L * sg * wl)
            person.feet[side] = Foot(side, Plant(pos, self.h, -math.inf, math.inf))
        z0 = self.z
        xy0, h0 = self.xy.copy(), self.h
        person.roots.append((0.0, self.t, lambda t, a=(xy0[0], xy0[1], z0, h0): a))

    def ankle(self, xy) -> np.ndarray:
        z = float(self.ground(float(xy[0]), float(xy[1]), self.z))
        return np.array((xy[0], xy[1], z + P.ANKLE_H * self.k))

    def hold(self, t0: float, t1: float, kind: str = "STOP", **data) -> None:
        if t1 > t0 + 1e-9:
            xy, z, h = self.xy.copy(), self.z, self.h
            self.p.roots.append((t0, t1, lambda t, a=(xy[0], xy[1], z, h): a))
            self.p.segs.append(Seg(kind, t0, t1, dict(data)))
        self.t = max(self.t, t1)


def _schedule(pl: Plan, spec: PersonSpec, ctx: _Ctx) -> Person:
    fig = R.Figure(spec.height)
    _SPECS[spec.name] = spec
    person = Person(spec, fig)
    st = _State(person, pl.ground)
    pts = [np.asarray(spec.place[:2], float)] + [np.asarray(p[:2], float) for p in spec.path]
    if spec.carry:
        _hold_item(pl, person, spec.carry, 0.0, warn=True)
    counts: dict = {}
    for i, a in enumerate(spec.actions):
        kind = a.kind if a.kind in ACTIONS else "STOP"
        t_ready = st.t
        if a.wait_person:
            if a.wait_person not in ctx.names:
                pl.warnings.append(f"{spec.name}, step {i + 1}: waits for '{a.wait_person}', who is not in the scene")
            elif a.wait_person == spec.name:
                pl.warnings.append(f"{spec.name}, step {i + 1}: waits for itself")
            else:
                n = max(1, int(a.wait_step))
                t_ready = max(t_ready, ctx.known.get((a.wait_person, n - 1), 0.0))
        if kind == "WALK":
            if t_ready > st.t:
                st.hold(st.t, t_ready, "WAIT", who=a.wait_person)
            t_start = st.t
            target = _target_point(pl, spec, a, i, pts, st)
            if target is not None:
                _walk(pl, person, st, pts, target, _gait_for(pl, person, a, st.t))
            person.step_times.append((t_start, st.t))
            person.step_places.append((st.xy[0], st.xy[1], st.z, st.h))
            continue
        t_start = st.t
        target = _target_point(pl, spec, a, i, pts, st)
        if target is not None and target != st.point:
            _walk(pl, person, st, pts, target, _gait_for(pl, person, a, st.t))
        t_ready = max(t_ready, st.t)
        n_kind = counts.get((kind, a.other), 0)
        counts[(kind, a.other)] = n_kind + 1
        paired = (kind in NEEDS_OTHER and bool(a.other) and a.other in ctx.names and a.other != spec.name
                  and _answers(a.other, spec.name, kind, n_kind, ctx))
        if paired:
            ctx.pairs[(kind, spec.name, a.other, n_kind)] = t_ready
            t_ready = max(t_ready, ctx.pairs.get((kind, a.other, spec.name, n_kind), t_ready))
        elif kind in NEEDS_OTHER and a.other and a.other not in ctx.names:
            pl.warnings.append(f"{spec.name}, step {i + 1}: '{a.other}' is not in the scene")
        if t_ready > st.t + 1e-6:
            st.hold(st.t, t_ready, "WAIT", who=a.wait_person or a.other, look_at=a.other or a.wait_person)
        _act(pl, person, st, a, kind, i, paired, ctx, n_kind)
        person.step_times.append((t_start, st.t))
        person.step_places.append((st.xy[0], st.xy[1], st.z, st.h))
    person.end = st.t
    xy, z, h = st.xy.copy(), st.z, st.h
    person.roots.append((st.t, math.inf, lambda t, a=(xy[0], xy[1], z, h): a))
    return person


def _target_point(pl, spec, a, i, pts, st):
    if a.place == "END":
        if len(pts) < 2:
            pl.warnings.append(f"{spec.name}, step {i + 1}: there is no path to walk to its end – draw one first")
            return None
        return len(pts) - 1
    if a.place == "POINT":
        k = int(a.point)
        if k < 0 or k >= len(pts):
            pl.warnings.append(f"{spec.name}, step {i + 1}: the path has no point {k} (it has {len(pts) - 1}); the "
                               "person stays where it is")
            return None
        return k
    if a.kind == "WALK":
        if st.point + 1 < len(pts):
            return st.point + 1
        pl.warnings.append(f"{spec.name}, step {i + 1}: a walk with no point to go to – pick a point or the end")
    return None


def _gait_for(pl, person, a, t) -> str:
    g = a.gait if a.gait in GAITS else "WALK"
    held = person.holding(t)
    if held and g == "WALK":
        it = pl.items.get(held)
        if it is not None and ITEMS.get(it.kind, ITEMS["TOOLBOX"]).heavy:
            return "CARRY"
    return g


_SPECS: dict = {}


def _answers(other: str, me: str, kind: str, n: int, ctx: _Ctx) -> bool:
    """Has ``other`` an ``n``-th action of ``kind`` with ``me`` (a greeting answered, a talk both join)?"""
    spec = _SPECS.get(other)
    if spec is None:
        return False
    return sum(1 for a in spec.actions if a.kind == kind and a.other == me) > n


# -- walking ---------------------------------------------------------------------------------------------------------


def _walk(pl: Plan, person: Person, st: _State, pts: list, target: int, gait_id: str) -> None:
    """Walk from the point the person stands on to point ``target`` along the clicked points (backwards when it
    lies behind)."""
    if target == st.point:
        return
    idx = list(range(st.point, target + 1)) if target > st.point else list(range(st.point, target - 1, -1))
    way = [st.xy] + [pts[j] for j in idx[1:]]
    path = Path(way)
    if path.length < 0.05:
        st.point = target
        return
    g = GAITS[gait_id]
    k = st.k
    # face the way first when it turns back more than ~100°
    h_way = heading_of(path.tangent(0.0, 0.25))
    if abs(wrap(h_way - st.h)) > math.radians(100):
        _turn(pl, person, st, h_way)
    step = g.step * k
    m = max(1, int(round(path.length / step)))
    if path.length / m < 0.22 * k:
        m = max(1, int(path.length / (0.22 * k)))
    Ls = path.length / m
    f = g.speed / Ls                           # steps per second
    d = (2 * g.duty - 1) / 2                   # double support (> 0) or flight (< 0) at each end of a step, in steps
    t0 = st.t
    T = (m + 1) / f
    wl = 0.095 * k

    def s_of(p):
        if m == 0:
            return 0.0
        if p <= 1.0:
            return Ls * 0.5 * p * p
        if p >= m:
            q = m + 1 - p
            return Ls * (m - 0.5 * q * q)
        return Ls * (p - 0.5)

    h_start = st.h

    def root(t, path=path, t0=t0, f=f, z_from=st.z, h_start=h_start):
        p = min(max((t - t0) * f, 0.0), m + 1)
        s = s_of(p)
        xy = path.at(s)
        z = float(pl.ground(xy[0], xy[1], z_from))
        h = heading_of(path.tangent(s))
        return (xy[0], xy[1], z, h + wrap(h_start - h) * (1.0 - smooth01(p / 1.4)))

    person.roots.append((t0, t0 + T, root))
    lead = st.lead
    feet = person.feet
    stance = 2 * g.duty / f
    roll_in, roll_out = HEEL_SHARE * stance, TOE_SHARE * stance
    sides = [lead if j % 2 == 0 else ("l" if lead == "r" else "r") for j in range(m + 1)]
    for j in range(1, m + 2):
        side = sides[j - 1]
        s_k = min(j, m) * Ls
        xy = path.at(s_k)
        tan = path.tangent(s_k, 0.2)
        h = heading_of(tan)
        sg = 1.0 if side == "l" else -1.0
        pos = st.ankle(xy + left_of(h) * sg * wl)
        t_up = t0 + max(0.0, j - 1 + d) / f
        t_down = t0 + min(m + 1.0, j - d) / f
        last = j == m + 1
        ft = feet[side]
        prev = ft.last
        stood = t_up - max(prev.down, t0 - 1.0)
        r_out = max(0.0, min(roll_out, 0.6 * stood, 0.3 / f if j <= 2 else roll_out))
        ft.step_to(pos, h, t_up, t_down, r_out, 0.0 if last else roll_in, g.lift)
    _check_ground(pl, person, path)
    end = path.at(path.length)
    st.xy = np.asarray(end, float)
    st.z = float(pl.ground(end[0], end[1], st.z))
    st.h = heading_of(path.tangent(path.length))
    st.t = t0 + T
    st.lead = "l" if sides[-1] == "r" else "r"
    person.segs.append(Seg("WALK", t0, st.t, {"gait": gait_id, "f": f, "m": m, "d": d, "lead": lead}))
    st.point = target


def _check_ground(pl: Plan, person: Person, path: Path) -> None:
    n = max(2, int(path.length / 0.25) + 1)
    zs = []
    for i in range(n):
        xy = path.at(path.length * i / (n - 1))
        zs.append(float(pl.ground(xy[0], xy[1], None)))
    zs = np.asarray(zs)
    dz = np.abs(np.diff(zs))
    if len(dz) and dz.max() > 0.22:
        i = int(dz.argmax())
        pl.warnings.append(f"{person.spec.name}'s path jumps {dz.max():.2f} m in height about "
                           f"{path.length * i / (n - 1):.1f} m along a walk: it runs over or into something (stairs "
                           "are not walked yet)")
    elif len(dz) and (dz / (path.length / (n - 1))).max() > 0.16:
        pl.warnings.append(f"{person.spec.name}'s path is steeper than 1 in 6 somewhere: too steep to walk "
                           "comfortably")


def turn_time(dh: float, speed_deg: float = 160.0) -> float:
    """How long a turn on the spot by ``dh`` takes."""
    if abs(dh) < 1e-6:
        return 0.0
    return 0.3 if abs(dh) < math.radians(12) else abs(dh) / math.radians(speed_deg) + 0.45


def _turn(pl: Plan, person: Person, st: _State, h_new: float, speed_deg: float = 160.0, T: float = 0.0) -> None:
    """Turn on the spot to heading ``h_new`` (in ``T`` seconds when given): the root turns, the feet step round in
    two small steps."""
    dh = wrap(h_new - st.h)
    T = max(T, turn_time(dh, speed_deg))
    if T <= 0:
        return
    if abs(dh) < math.radians(12):
        if abs(dh) <= 1e-6:
            st.hold(st.t, st.t + T, "STOP")
            return
        t0, h0 = st.t, st.h                  # a small turn: the feet stay where they are
        xy, z = st.xy.copy(), st.z
        person.roots.append((t0, t0 + T, lambda t, h0=h0, dh=dh, t0=t0, T=T, xy=xy, z=z:
                             (xy[0], xy[1], z, h0 + dh * smooth01((t - t0) / T))))
        person.segs.append(Seg("TURN", t0, t0 + T, {"from": h0, "to": h0 + dh}))
        st.h = h0 + dh
        st.t = t0 + T
        return
    k = st.k
    t0 = st.t
    h0 = st.h
    xy, z = st.xy.copy(), st.z
    person.roots.append((t0, t0 + T, lambda t, h0=h0, dh=dh, t0=t0, T=T, xy=xy, z=z:
                         (xy[0], xy[1], z, h0 + dh * smooth01((t - t0) / T))))
    first = "l" if dh > 0 else "r"           # turning left: the left foot steps first
    order = (first, "r" if first == "l" else "l")
    wl = 0.1 * k
    for n, side in enumerate(order):
        sg = 1.0 if side == "l" else -1.0
        h = h0 + dh * (0.6 if n == 0 else 1.0)
        pos = st.ankle(xy + left_of(h) * sg * wl)
        a, b = t0 + T * (0.05 + 0.45 * n), t0 + T * (0.45 + 0.45 * n)
        person.feet[side].step_to(pos, h, a, b, 0.0, 0.0, 0.045)
    person.segs.append(Seg("TURN", t0, t0 + T, {"from": h0, "to": h0 + dh}))
    st.h = h0 + dh
    st.t = t0 + T


def _face(pl, person, st, xy_target, T: float = 0.0) -> None:
    d = np.asarray(xy_target[:2], float) - st.xy
    if np.linalg.norm(d) > 0.05:
        _turn(pl, person, st, st.h + wrap(heading_of(d) - st.h), T=T)
    elif T > 0:
        st.hold(st.t, st.t + T, "STOP")


def _face_together(pl, person, st, a: Action, kind: str, n_kind: int, ctx: _Ctx, oxy) -> None:
    """Two people meeting turn to each other in the same time, so what they do next starts together."""
    d = np.asarray(oxy[:2], float) - st.xy if oxy is not None else np.zeros(2)
    mine = turn_time(wrap(heading_of(d) - st.h)) if np.linalg.norm(d) > 0.05 else 0.0
    me = person.spec.name
    ctx.pairs[("FACE", kind, me, a.other, n_kind)] = mine
    T = max(mine, ctx.pairs.get(("FACE", kind, a.other, me, n_kind), mine))
    if oxy is not None:
        _face(pl, person, st, oxy, T)
    elif T > 0:
        st.hold(st.t, st.t + T, "STOP")


# -- items -----------------------------------------------------------------------------------------------------------


def _hold_item(pl: Plan, person: Person, name: str, t: float, warn: bool = False) -> bool:
    it = pl.items.get(name)
    if it is None or it.kind not in ITEMS:
        if warn:
            pl.warnings.append(f"{person.spec.name} should hold '{name}' but there is no such item")
        return False
    side = holding_hands(it.kind)[0]
    grip = inv4(hand_in_item(it.kind, side, person.fig.k))
    pl.item_states.setdefault(name, []).append(ItemState(t, "HELD", person.spec.name, side, grip))
    person.held.append((t, name))
    return True


def _drop_item(pl: Plan, person: Person, name: str, t: float, world: np.ndarray) -> None:
    pl.item_states.setdefault(name, []).append(ItemState(t, "PLACED", world=world))
    person.held.append((t, ""))


def _put_spot(pl: Plan, st: _State, kind: str) -> np.ndarray:
    """Where a person puts an item down: in front (a little to the side of the hand it is in), on whatever is there."""
    it = ITEMS[kind]
    k = st.k
    F, Lf = facing(st.h), left_of(st.h)
    side = {"R": -1.0, "L": 1.0, "BOTH": 0.0}[it.hands]
    xy = st.xy + F * (0.42 * k + it.size[1] / 2) + Lf * side * 0.12 * k
    z = float(pl.ground(xy[0], xy[1], st.z + 1.2))
    h = st.h - math.pi / 2 if it.style == "SIDE" else st.h
    return m4(R.rz(h), (xy[0], xy[1], z))


# -- one action --------------------------------------------------------------------------------------------------------


def _target_xy(pl, a: Action, ctx: _Ctx, t: float):
    if a.other:
        p = ctx.where(a.other, t)
        if p is None and a.other in _SPECS:
            p = np.asarray(_SPECS[a.other].place[:2], float)
        if p is not None:
            return np.asarray(p, float), None
    if a.target is not None:
        return np.asarray(a.target[:2], float), np.asarray(a.target, float)
    return None, None


def _act(pl: Plan, person: Person, st: _State, a: Action, kind: str, i: int, paired: bool, ctx: _Ctx,
         n_kind: int = 0) -> None:
    name = person.spec.name
    k = st.k
    if kind == "TURN":
        xy, _p3 = _target_xy(pl, a, ctx, st.t)
        if xy is None:
            pl.warnings.append(f"{name}, step {i + 1}: turn to face what? Pick a person, a part or a point")
            return
        _face(pl, person, st, xy)
        return
    if kind in ("STOP", "IDLE"):
        st.hold(st.t, st.t + _dur(a), kind)
        return
    if kind == "WAVE":
        st.hold(st.t, st.t + _dur(a), "WAVE")
        return
    if kind in ("LOOK", "POINT"):
        xy, p3 = _target_xy(pl, a, ctx, st.t)
        if xy is None:
            pl.warnings.append(f"{name}, step {i + 1}: {kind.lower()} at what? Pick a person, a part or a point")
            st.hold(st.t, st.t + _dur(a), "STOP")
            return
        if p3 is None:
            p3 = np.array((xy[0], xy[1], st.z + 1.5 * k))
        if kind == "POINT":
            d = xy - st.xy
            if np.linalg.norm(d) > 0.05 and abs(wrap(heading_of(d) - st.h)) > math.radians(60):
                _face(pl, person, st, xy)
        st.hold(st.t, st.t + _dur(a), kind, target=p3)
        return
    if kind == "OPERATE":
        if a.target is None:
            pl.warnings.append(f"{name}, step {i + 1}: operate where? Pick the point on the panel or part")
            st.hold(st.t, st.t + _dur(a), "STOP")
            return
        p3 = np.asarray(a.target, float)
        _face(pl, person, st, p3)
        reach = float(np.linalg.norm(p3[:2] - st.xy))
        if reach > 0.85 * k:
            pl.warnings.append(f"{name}, step {i + 1}: the point to operate is {reach:.2f} m away – too far to reach; "
                               "put the person's point closer (about 0.5 m in front)")
        st.hold(st.t, st.t + _dur(a), "OPERATE", target=p3)
        return
    if kind == "GREET":
        oxy, _p3 = _target_xy(pl, a, ctx, st.t + 0.5)
        if not paired or oxy is None:
            if oxy is not None:
                _face(pl, person, st, oxy)
            st.hold(st.t, st.t + 2.0, "WAVE")
            return
        _face_together(pl, person, st, a, kind, n_kind, ctx, oxy)
        dist = float(np.linalg.norm(np.asarray(oxy) - st.xy))
        if dist > 1.25 or dist < 0.55:
            pl.warnings.append(f"{name} and {a.other} stand {dist:.2f} m apart to shake hands – put their meeting "
                               "points about 0.8 m apart")
        mid = (np.asarray(oxy) + st.xy) / 2
        k_other = R.Figure(_SPECS[a.other].height).k if a.other in _SPECS else k
        st.hold(st.t, st.t + 2.4, "HANDSHAKE", mid=mid, other=a.other, hz=0.5 * (k + k_other))
        return
    if kind == "TALK":
        oxy = _target_xy(pl, a, ctx, st.t + 0.5)[0] if a.other else None
        if paired:
            _face_together(pl, person, st, a, kind, n_kind, ctx, oxy)
        elif oxy is not None:
            _face(pl, person, st, oxy)
        first = paired and name < a.other
        st.hold(st.t, st.t + _dur(a), "TALK", other=a.other, first=first or not paired,
                seed=sum(map(ord, name)) % 97, look=oxy)
        return
        return
    if kind == "PICK_UP":
        it = pl.items.get(a.item)
        if it is None:
            pl.warnings.append(f"{name}, step {i + 1}: pick up which item? Pick one from the list")
            return
        if person.holding(st.t):
            pl.warnings.append(f"{name}, step {i + 1}: already carries '{person.holding(st.t)}' – put it down first")
            return
        world = _item_world_at(pl, ctx, a.item, st.t)
        _face(pl, person, st, world[:2, 3])
        dist = float(np.linalg.norm(world[:2, 3] - st.xy))
        if dist > 0.95 * k:
            pl.warnings.append(f"{name}, step {i + 1}: '{a.item}' lies {dist:.2f} m away – too far to reach; put it "
                               "within about 0.6 m of the person's point")
        T = 2.2
        t0 = st.t
        st.hold(t0, t0 + T, "PICK_UP", item=a.item, world=world, grab=t0 + T * 0.45)
        _hold_item(pl, person, a.item, t0 + T * 0.45)
        return
    if kind == "PUT_DOWN":
        held = person.holding(st.t)
        if not held:
            pl.warnings.append(f"{name}, step {i + 1}: puts down nothing – the person carries no item then")
            return
        it = pl.items[held]
        world = _put_spot(pl, st, it.kind)
        T = 2.2
        t0 = st.t
        st.hold(t0, t0 + T, "PUT_DOWN", item=held, world=world, grab=t0 + T * 0.45)
        _drop_item(pl, person, held, t0 + T * 0.45, world)
        return


def _item_world_at(pl: Plan, ctx: _Ctx, name: str, t: float) -> np.ndarray:
    states = [s for s in pl.item_states.get(name, []) + ctx.prev_items.get(name, [])
              if s.t <= t + 1e-9 and s.state == "PLACED"]
    if states:
        return max(states, key=lambda s: s.t).world
    it = pl.items[name]
    return _placed_matrix(it, pl.ground)


# ---------------------------------------------------------------------------
# the frames
# ---------------------------------------------------------------------------


def _sample_person(pl: Plan, person: Person, times: list) -> list:
    fig = person.fig
    rest = fig.rest()
    rest_pelvis_z = float(rest.pelvis[2])
    out = []
    raw = []
    for t in times:
        root = person.root(t)
        seg = _seg_at(person, t)
        raw.append((t, root, seg))
    # the pelvis height: what the gait wants, lowered where a planted foot would not be reached, then smoothed
    want, cap = [], []
    for t, root, seg in raw:
        w, c = _pelvis_limits(pl, person, t, root, seg, rest_pelvis_z)
        want.append(w)
        cap.append(c)
    z = _smooth_under(np.asarray(want), np.asarray(cap))
    for n, (t, root, seg) in enumerate(raw):
        out.append((root, _pose(pl, person, t, root, seg, float(z[n]))))
    return out


def _seg_at(person: Person, t: float):
    for s in person.segs:
        if s.t0 - 1e-9 <= t <= s.t1 + 1e-9:
            return s
    return None


def _smooth_under(want: np.ndarray, cap: np.ndarray) -> np.ndarray:
    z = np.minimum(want, cap)
    if len(z) < 5:
        return z
    ker = np.array((1, 2, 3, 2, 1), float)
    ker /= ker.sum()
    for _ in range(2):
        zp = np.pad(z, 2, mode="edge")
        z = np.minimum(np.convolve(zp, ker, mode="valid"), cap)
    return z


def _to_fig(root, p) -> np.ndarray:
    """A world point into the figure's space (root = (x, y, z, heading))."""
    x, y, z, h = root
    v = np.asarray(p, float) - np.array((x, y, z))
    c, s = math.cos(h), math.sin(h)
    return np.array((c * v[0] + s * v[1], -s * v[0] + c * v[1], v[2]))


def _dir_to_fig(root, d) -> np.ndarray:
    h = root[3]
    c, s = math.cos(h), math.sin(h)
    return np.array((c * d[0] + s * d[1], -s * d[0] + c * d[1], d[2] if len(d) > 2 else 0.0))


def _rot_to_fig(root, Rw) -> np.ndarray:
    return R.rz(-root[3]) @ np.asarray(Rw, float)


def _walk_phase(person: Person, t: float, seg) -> tuple:
    """(phase in steps since the walk began or None, gait id, share 0..1 of full walking)."""
    if seg is None or seg.kind != "WALK":
        return None, None, 0.0
    f, m = seg.data["f"], seg.data["m"]
    p = (t - seg.t0) * f
    ramp = min(1.0, p, (m + 1) - p)
    return p, seg.data["gait"], max(0.0, min(1.0, ramp))


def _pelvis_limits(pl, person, t, root, seg, rest_z):
    fig = person.fig
    k = fig.k
    p, gid, w = _walk_phase(person, t, seg)
    want = rest_z
    if gid is not None:
        g = GAITS[gid]
        want = rest_z - g.drop * k * w - 0.012 * k * w * (1 + math.cos(2 * math.pi * p)) / 2
        if gid == "RUN":
            want += 0.03 * k * w * math.sin(math.pi * (p % 1.0))
    crouch = _crouch(person, t, seg)
    want -= crouch * 0.32 * k
    reach = (fig.THIGH + fig.SHIN) * k * 0.997
    cap = math.inf
    for side, ft in person.feet.items():
        ank, _yaw, _pitch = ft.state(t, k)
        a = _to_fig(root, ank)
        hip_off = np.array((0.09 if side == "l" else -0.09, 0.0, -0.04)) * k
        hx, hy = hip_off[0], hip_off[1]
        dx, dy = a[0] - hx, a[1] - hy
        hz2 = reach * reach - dx * dx - dy * dy
        if ft.on_floor(t) is not None and hz2 > 0:
            cap = min(cap, a[2] + math.sqrt(hz2) - hip_off[2])
    return want, cap


def _crouch(person: Person, t: float, seg) -> float:
    if seg is None or seg.kind not in ("PICK_UP", "PUT_DOWN"):
        return 0.0
    u = (t - seg.t0) / max(1e-6, seg.t1 - seg.t0)
    g = (seg.data["grab"] - seg.t0) / (seg.t1 - seg.t0)
    if u < g:
        return smooth01(u / g)
    return 1.0 - smooth01((u - g) / (1 - g))


def _pose(pl: Plan, person: Person, t: float, root, seg, pelvis_z: float) -> R.Pose:
    fig = person.fig
    k = fig.k
    p, gid, w = _walk_phase(person, t, seg)
    sway = 0.0
    if gid is not None:
        g = GAITS[gid]
        lead = 1.0 if seg.data.get("lead", "r") == "r" else -1.0
        c = -math.cos(math.pi * p) * lead                     # +1 when the right foot is forward
        ang = {"pelvis": (g.lean_deg * w * 0.4, 0.0, g.twist_deg * w * c),
               "spine": (g.lean_deg * w * 0.3, 0.0, 0.0),
               "chest": (g.lean_deg * w * 0.3, 0.0, -g.twist_deg * 1.4 * w * c),
               "head": (-g.lean_deg * w * 0.8, 0.0, 0.0)}
        sw = g.swing_deg * w
        ang["l_arm"] = (sw * c + 2, 7, 0)                   # the left arm forward with the right foot
        ang["r_arm"] = (-sw * c + 2, 7, 0)
        ang["l_forearm"] = 10 + (g.elbow_deg - 10) * w + 12 * w * max(0.0, c)
        ang["r_forearm"] = 10 + (g.elbow_deg - 10) * w + 12 * w * max(0.0, -c)
        ang["l_fingers"] = ang["r_fingers"] = 0.4
        sway = 0.014 * k * w * math.sin(math.pi * p) * lead
    else:
        ang = dict(P.POSES["STANDING"])
        ang["chest"] = (0.8 * math.sin(2 * math.pi * t / 4.2), 0, 0)       # breathing
        if seg is not None and seg.kind in ("IDLE", "WAIT", "TALK", "STOP"):
            sway = 0.012 * k * math.sin(2 * math.pi * t / 7.3 + len(person.spec.name))
    pose = fig._pose_of(ang, 0.0)
    crouch = _crouch(person, t, seg)
    if crouch > 0:
        bend = crouch * 38.0
        pose.local["spine"] = pose.local["spine"] @ R.rx(math.radians(bend * 0.55))
        pose.local["chest"] = pose.local["chest"] @ R.rx(math.radians(bend * 0.45))
        pose.local["head"] = pose.local["head"] @ R.rx(math.radians(-bend * 0.3))
    pose.pelvis = np.array((sway, 0.05 * k * crouch, pelvis_z))
    # the legs to the feet
    fwd = pose.local["pelvis"] @ np.array((0.0, -1.0, 0.0))
    for side, ft in person.feet.items():
        ank, yaw, pitch = ft.state(t, k)
        a = _to_fig(root, ank)
        yl = yaw - root[3]
        foot_fwd = np.array((math.sin(yl), -math.cos(yl), 0.0))
        fig.leg_ik(pose, side, a, foot_frame(yl, pitch), R.unit(foot_fwd * 0.7 + fwd * 0.3 + np.array((0, 0, 0.05))))
    # the upper body by what the person does, then the hands on a carried item
    _upper(pl, person, t, root, seg, pose)
    _held_arms(pl, person, t, root, seg, pose)
    return pose


def _upper(pl: Plan, person: Person, t: float, root, seg, pose: R.Pose) -> None:
    fig = person.fig
    k = fig.k
    if seg is None:
        return
    ease = smooth01(min(1.0, (t - seg.t0) / 0.5)) * smooth01(min(1.0, (seg.t1 - t) / 0.5))
    kind = seg.kind
    if kind == "WAIT" and seg.data.get("look_at") in pl.people:
        other = pl.people[seg.data["look_at"]]
        o = other.root(t)
        if math.hypot(o[0] - root[0], o[1] - root[1]) < 12.0:
            head = fig.fk(pose)["head"][0]
            target = np.array((o[0], o[1], o[2] + 1.55 * other.fig.k))
            fig.look(pose, _to_fig(root, target) - head, 0.8 * ease)
    if kind == "IDLE":
        yaw = 0.5 * math.sin(2 * math.pi * (t - seg.t0) / 5.5)
        d = np.array((math.sin(yaw), -math.cos(yaw), -0.1))
        fig.look(pose, d, ease)
    if kind == "WAVE":
        fk = fig.fk(pose)
        sh = fk["r_arm"][0]
        Rp = fk["pelvis"][1]
        wave = math.sin(2 * math.pi * 1.6 * (t - seg.t0))
        wrist = sh + Rp @ (np.array((-0.2 - 0.06 * wave, -0.12, 0.2)) * k)
        hand_R = Rp @ np.column_stack(((0.0, -1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, -1.0))) @ \
            R.ry(math.radians(15 * wave))
        _reach(fig, pose, "r", wrist, hand_R, ease, elbow=Rp @ np.array((-1.0, 0.3, -1.2)))
        pose.fingers["r"] = 0.35 + (0.0 - 0.35) * ease
    if kind == "HANDSHAKE":
        mid = seg.data["mid"]
        fk = fig.fk(pose)
        target = _to_fig(root, np.array((mid[0], mid[1], root[2] + 1.0 * seg.data.get("hz", k))))
        hand_R = fk["pelvis"][1] @ R.rx(math.radians(-90))
        palm_off = hand_R @ _grip_local("r", k)
        reach_e = smooth01(min(1.0, (t - seg.t0) / 0.6)) * smooth01(min(1.0, (seg.t1 - t) / 0.6))
        shake = 0.025 * k * math.sin(2 * math.pi * 2.4 * (t - seg.t0 - 0.6)) if 0.6 < t - seg.t0 < 1.8 else 0.0
        wrist = target - palm_off + np.array((0.0, 0.0, shake))
        pose.local["chest"] = pose.local["chest"] @ R.rx(math.radians(5 * reach_e))
        _reach(fig, pose, "r", wrist, hand_R, reach_e)
        pose.fingers["r"] = 0.35 + 0.3 * reach_e
        fk = fig.fk(pose)
        fig.look(pose, target + np.array((0, 0, 0.55 * k)) - fk["head"][0], 0.7 * ease)
    if kind == "TALK":
        _talk(pl, fig, person, t, root, seg, pose, ease)
    if kind in ("LOOK", "POINT"):
        target = _to_fig(root, seg.data["target"])
        fk = fig.fk(pose)
        fig.look(pose, target - fk["head"][0], ease, chest_share=0.3)
        if kind == "POINT":
            fk = fig.fk(pose)
            sh = fk["r_arm"][0]
            d = R.unit(target - sh)
            wrist = sh + d * (fig.ARM + fig.FOREARM) * k * 0.97
            z = -d
            down = np.array((0.0, 0.0, -1.0)) if abs(d[2]) < 0.95 else np.array((0.0, -1.0, 0.0))
            x = R.unit(down - z * float(np.dot(down, z)))      # the right palm faces down
            hand_R = np.column_stack((x, np.cross(z, x), z))
            _reach(fig, pose, "r", wrist, hand_R, ease, elbow=np.array((-0.6, 0.3, -1.0)))
            pose.fingers["r"] = 0.35 + 0.6 * ease
            pose.point["r"] = ease
    if kind == "OPERATE":
        target = _to_fig(root, seg.data["target"])
        fk = fig.fk(pose)
        sh_mid = (fk["l_arm"][0] + fk["r_arm"][0]) / 2
        dist = float(np.linalg.norm((target - sh_mid)[:2]))
        lean = max(0.0, min(30.0, (dist - 0.42 * k) / (0.3 * k) * 30.0)) * ease
        pose.local["spine"] = pose.local["spine"] @ R.rx(math.radians(lean * 0.5))
        pose.local["chest"] = pose.local["chest"] @ R.rx(math.radians(lean * 0.5))
        fk = fig.fk(pose)
        for side, sd in (("l", 1.0), ("r", -1.0)):
            press = 0.012 * k * max(0.0, math.sin(2 * math.pi * 0.9 * (t - seg.t0) + (0 if side == "r" else 2.1)))
            spot = target + np.array((0.0, 0.0, -press)) + fk["pelvis"][1] @ np.array((sd * 0.11 * k, 0.0, 0.0))
            if side == "r":
                hand_R = np.column_stack(((0.0, 0.0, -1.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
            else:
                hand_R = np.column_stack(((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
            hand_R = fk["pelvis"][1] @ hand_R
            wrist = spot - hand_R @ (np.array((-sd * 0.0, 0.0, -0.075)) * k) + np.array((0, 0, 0.02 * k))
            _reach(fig, pose, side, wrist, hand_R, ease)
            pose.fingers[side] = 0.35 - 0.2 * ease
        fig.look(pose, target - fig.fk(pose)["head"][0], ease)
    if kind in ("PICK_UP", "PUT_DOWN"):
        name = seg.data["item"]
        it = pl.items[name]
        world = seg.data["world"]
        reach_e = _crouch(person, t, seg)
        reach_e = smooth01(min(1.0, reach_e * 1.6))
        fk = fig.fk(pose)
        M = _rot4_to_fig(root, world)
        for side in holding_hands(it.kind):
            H = M @ hand_in_item(it.kind, side, k)
            hand_R, wrist = H[:3, :3], H[:3, 3]
            _reach(fig, pose, side, wrist, hand_R, reach_e)
            pose.fingers[side] = 0.35 + 0.5 * reach_e
        fig.look(pose, M[:3, 3] - fig.fk(pose)["head"][0], 0.8 * ease)


def _rot4_to_fig(root, M) -> np.ndarray:
    out = np.eye(4)
    out[:3, :3] = _rot_to_fig(root, M[:3, :3])
    out[:3, 3] = _to_fig(root, M[:3, 3])
    return out


def _reach(fig, pose, side, wrist, hand_R, w, elbow=None) -> float:
    """Move a hand ``w`` of the way (0 … 1) from where the pose has it to ``wrist`` / ``hand_R`` (figure space)."""
    if w <= 1e-4:
        return 0.0
    fk = fig.fk(pose)
    h0, R0, _t = fk[f"{side}_hand"]
    if w < 1.0:
        wrist = h0 + (np.asarray(wrist) - h0) * w
        hand_R = R.slerp(R0, hand_R, w) if hand_R is not None else None
    return fig.arm_ik(pose, side, wrist, elbow, hand_R)


def _talk(pl, fig, person, t, root, seg, pose, ease):
    """Two people talking: they look at each other and take turns; the one speaking moves the hands, the one
    listening nods now and then."""
    k = fig.k
    dt = t - seg.t0
    turn = 3.2
    speaking = (int(dt // turn) % 2 == 0) == bool(seg.data.get("first", True))
    seed = seg.data.get("seed", 0)
    other = pl.people.get(seg.data.get("other", ""))
    if other is not None:
        o = other.root(t)
        target = _to_fig(root, np.array((o[0], o[1], o[2] + 1.55 * other.fig.k)))
        fig.look(pose, target - fig.fk(pose)["head"][0], 0.9 * ease)
    nod = math.sin(2 * math.pi * (0.9 if speaking else 0.45) * dt + seed) * (4 if speaking else 2.5)
    pose.local["head"] = pose.local["head"] @ R.rx(math.radians(nod * ease))
    if not speaking:
        return
    w = ease * smooth01(min(1.0, (dt % turn) / 0.6)) * smooth01(min(1.0, (turn - dt % turn) / 0.6))
    held = person.holding(t)
    busy = holding_hands(pl.items[held].kind) if held in pl.items else ()
    Rp = fig.fk(pose)["pelvis"][1]
    for side, sd, ph, share in (("r", -1.0, 0.0, 1.0), ("l", 1.0, 1.7, 0.7)):
        if side in busy:
            continue
        a = 2 * math.pi * dt
        off = np.array((sd * (0.2 + 0.04 * math.sin(a * 0.7 + seed + ph)), -0.3 - 0.05 * math.sin(a * 0.53 + ph),
                        0.0)) * k
        target = Rp @ off
        target[2] = (0.98 + 0.05 * math.sin(a * 0.91 + seed * 0.3 + ph)) * k
        hand_R = Rp @ R.rx(math.radians(-70)) @ R.ry(math.radians(sd * (35 + 20 * math.sin(a * 0.4 + ph))))
        _reach(fig, pose, side, target, hand_R, w * share)
        pose.fingers[side] = 0.35 - 0.15 * w * share


def _held_arms(pl: Plan, person: Person, t: float, root, seg, pose: R.Pose) -> None:
    """The arms of a person carrying an item: the item where the carry pose puts it, the hands on it."""
    name = person.holding(t)
    if not name:
        return
    it = pl.items.get(name)
    if it is None:
        return
    fig = person.fig
    k = fig.k
    if seg is not None and seg.kind in ("PICK_UP", "PUT_DOWN"):
        # while bending, the hands follow the reach (done in _upper); after the grab (pick up) / before the release
        # (put down) the carry pose blends in as the person stands up
        u = (t - seg.t0) / max(1e-6, seg.t1 - seg.t0)
        g = (seg.data["grab"] - seg.t0) / (seg.t1 - seg.t0)
        if seg.kind == "PICK_UP":
            w = smooth01((u - g) / (1 - g)) if u > g else 0.0
        else:
            w = 1.0 - smooth01(u / g) if u < g else 0.0
        if w <= 0:
            return
    else:
        w = 1.0
    fk = fig.fk(pose)
    item = carry_item_frame(it.kind, fig, pose, fk)
    sides = holding_hands(it.kind)
    for side in sides:
        H = item @ hand_in_item(it.kind, side, k)
        _reach(fig, pose, side, H[:3, 3], H[:3, :3], w)
        pose.fingers[side] = pose.fingers[side] + (0.85 - pose.fingers[side]) * w
