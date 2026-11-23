"""Task 0313 (study, prototype – not app code): ready-made camera moves.

No Blender here. Every move is the same three things, so one editor serves them all:

    handles   the points the camera flies through (a smooth curve, ``core/camera_path.Path``, flown at an even speed
              with a ramp up and down) – the points the user drags, adds or removes in the view
    aim       where it looks: the model's middle, a part's middle (a point per frame), ahead along the path, a held
              direction, or one aim point per handle (turned smoothly between them)
    lens      mm per handle (a zoom follows the field of view, as the app's Move to does)

``Shot.sample(n)`` gives n frames of (place, point looked at, lens, focus distance, roll). ``shake`` adds handheld,
walk or vehicle shake to any move (a sum of sines with a seed: the same every time, baked to plain keys).

The moves place themselves round a ``Subject`` (the corners of the model or of a picked part) with the app's fit rule
(``fit_distance``: every point inside the picture with a margin, the rule of ``cameras.fit``).

Units: metres, degrees in the options, radians inside. z is up. Blender's camera looks along its -Z, up = +Y.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from fresing_render.core import camera_path as P  # noqa: E402

SENSOR = 36.0                       # mm, the app's cameras (Blender's default sensor, fit "auto" = the long side)
UP = np.array([0.0, 0.0, 1.0])


# ---------------------------------------------------------------------------
# the subject and fitting
# ---------------------------------------------------------------------------

@dataclass
class Subject:
    """What a move is placed round: corner points (n x 3, world, m)."""
    points: np.ndarray

    def __post_init__(self):
        self.points = np.asarray(self.points, dtype=float).reshape(-1, 3)
        self.lo = self.points.min(axis=0)
        self.hi = self.points.max(axis=0)
        self.centre = (self.lo + self.hi) / 2
        self.size = self.hi - self.lo
        self.radius = float(np.linalg.norm(self.size) / 2)
        self.ground = float(self.lo[2])


def half_tans(lens: float, aspect: float) -> tuple[float, float]:
    """tan of the half field of view across and up (sensor fit on the long side, as Blender's AUTO)."""
    t = SENSOR / (2.0 * lens)
    return (t, t / aspect) if aspect >= 1 else (t * aspect, t)


def look_matrix(pos, target, roll: float = 0.0) -> np.ndarray:
    """4 x 4 camera matrix at ``pos`` looking at ``target``, upright (roll in radians about the view)."""
    pos, target = np.asarray(pos, float), np.asarray(target, float)
    f = target - pos
    n = np.linalg.norm(f)
    f = f / n if n > 1e-12 else np.array([0.0, 1.0, 0.0])
    r = np.cross(f, UP)
    if np.linalg.norm(r) < 1e-6:                  # straight down / up: keep +Y as the picture's top
        r = np.cross(f, np.array([0.0, 1.0, 0.0]))
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    if roll:
        c, s = math.cos(roll), math.sin(roll)
        r, u = c * r + s * u, -s * r + c * u
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = r, u, -f, pos
    return m


def fit_distance(points, target, direction, lens: float, aspect: float, margin: float = 1.08) -> float:
    """How far from ``target`` along ``direction`` (pointing from the target to the camera) the camera must stand
    so every point is in the picture (the projection rule of ``cameras.fit``, without moving the target)."""
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    m = look_matrix(np.asarray(target) + d, target)
    R = m[:3, :3]
    p = (np.asarray(points) - np.asarray(target)) @ R          # camera axes: x right, y up, z towards the camera
    tx, ty = half_tans(lens, aspect)
    tx, ty = tx / margin, ty / margin
    return float(max(np.max(np.abs(p[:, 0]) / tx + p[:, 2]), np.max(np.abs(p[:, 1]) / ty + p[:, 2]), 0.05))


def direction(az_deg: float, el_deg: float) -> np.ndarray:
    """Unit vector from the target towards the camera: azimuth from +X anticlockwise seen from above, elevation up."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    return np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])


# ---------------------------------------------------------------------------
# a shot
# ---------------------------------------------------------------------------

@dataclass
class Shot:
    name: str
    handles: np.ndarray                      # k x 3
    aim: str = "MODEL"                       # MODEL | PART | AHEAD | HELD | KEYS
    aim_point: np.ndarray | None = None      # MODEL: the point; HELD: the point at the start (a direction is kept)
    aim_keys: np.ndarray | None = None       # KEYS: one aim point per handle
    aim_track: np.ndarray | None = None      # PART: n x 3 (the part's middle per frame), given at sample time
    lens: list = field(default_factory=lambda: [50.0])        # one value, or one per handle
    focus_keys: list | None = None           # focus distance per handle (focus pull), else distance to the aim
    easing: str = "SMOOTH"
    ramp: float = 0.35                       # share of the time to get up to speed (and to stop)
    options: dict = field(default_factory=dict)
    shake: dict | None = None

    def _u(self, path, s):
        """Fractional handle index at ``s`` metres along the path."""
        return float(np.interp(s, path.at_point, np.arange(len(path.at_point))))

    def sample(self, n: int, aim_track=None) -> dict:
        n = max(2, int(n))
        h = P.clean(self.handles)
        still = len(h) < 2
        path = None if still else P.Path(h)
        up = self.ramp if self.easing in ("SMOOTH", "EASE_IN") else 0.0
        down = self.ramp if self.easing in ("SMOOTH", "EASE_OUT") else 0.0
        track = self.aim_track if aim_track is None else aim_track
        k = len(self.handles)
        pos, tgt, lens, focus, us = [], [], [], [], []
        held = None
        for i in range(n):
            p = i / (n - 1)
            if still:
                x, u, s = h[0], 0.0, 0.0
            else:
                s = P.ramped(p, up, down) * path.length
                x, u = path.point(s), self._u(path, s)
            if self.aim == "MODEL":
                t = self.aim_point
            elif self.aim == "PART":
                t = track[min(i, len(track) - 1)]
            elif self.aim == "AHEAD":
                t = x + (path.direction(s) if path is not None else np.array([0.0, 1.0, 0.0]))
            elif self.aim == "HELD":
                if held is None:
                    held = self.aim_point - x
                t = x + held
            else:                                                   # KEYS: smooth between one aim point per handle
                j = min(int(math.floor(u)), k - 2) if k > 1 else 0
                f = _smooth(u - j) if k > 1 else 0.0
                t = self.aim_keys[j] * (1 - f) + self.aim_keys[min(j + 1, k - 1)] * f
            if len(self.lens) == 1 or k < 2:
                ln = self.lens[0]
            else:                                                   # zoom: even in the field of view
                j = min(int(math.floor(u)), k - 2)
                f = _smooth(u - j)
                fa, fb = math.atan(18 / self.lens[j]), math.atan(18 / self.lens[j + 1])
                ln = 18 / math.tan(fa + (fb - fa) * f)
            if self.focus_keys is not None:
                fk = self.focus_keys
                ff = _smooth(min(1.0, max(0.0, (p - self.options.get("pull_at", 0.35)) /
                                         max(1e-6, self.options.get("pull_for", 0.3)))))
                fd = fk[0] + (fk[-1] - fk[0]) * ff
            else:
                fd = float(np.linalg.norm(np.asarray(t) - x))
            pos.append(np.array(x, float))
            tgt.append(np.array(t, float))
            lens.append(ln)
            focus.append(fd)
            us.append(p)
        out = {"pos": np.array(pos), "target": np.array(tgt), "lens": np.array(lens), "focus": np.array(focus),
               "roll": np.zeros(n)}
        if self.shake:
            add_shake(out, **self.shake)
        return out


def _smooth(f: float) -> float:
    f = min(1.0, max(0.0, f))
    return f * f * (3 - 2 * f)


def matrices(sampled: dict) -> np.ndarray:
    """n x 4 x 4 camera matrices of a sampled shot."""
    return np.array([look_matrix(p, t, r) for p, t, r in zip(sampled["pos"], sampled["target"], sampled["roll"])])


# ---------------------------------------------------------------------------
# shake
# ---------------------------------------------------------------------------

SHAKES = {
    #           turn (deg)  freqs (Hz)          place (m per m of distance)  bob (Hz)
    "HANDHELD": dict(turn=0.35, hz=(0.31, 0.53, 1.1), move=0.0006, bob=0.0),
    "WALK":     dict(turn=0.45, hz=(0.27, 0.9, 1.8), move=0.0025, bob=1.8),
    "VEHICLE":  dict(turn=0.25, hz=(0.7, 3.1, 7.3), move=0.0012, bob=0.0),
}


def add_shake(out: dict, kind: str = "HANDHELD", strength: float = 1.0, seed: int = 1, fps: float = 25.0) -> None:
    """Adds shake in place: a sum of a few sines per axis with random phases (``seed``), so it is the same at every
    Build and plays as plain keys. The aim point moves with the camera (a turn of ``turn`` degrees at strength 1)."""
    cfg = SHAKES[kind]
    rng = np.random.default_rng(seed)
    n = len(out["pos"])
    t = np.arange(n) / fps
    def wave(amp):
        ph = rng.uniform(0, 2 * math.pi, len(cfg["hz"]))
        w = rng.uniform(0.6, 1.0, len(cfg["hz"]))
        s = sum(wi * np.sin(2 * math.pi * hz * t + p) for wi, hz, p in zip(w, cfg["hz"], ph)) / sum(w)
        return amp * s
    dist = np.linalg.norm(out["target"] - out["pos"], axis=1)
    fwd = (out["target"] - out["pos"]) / np.maximum(dist, 1e-9)[:, None]
    right = np.cross(fwd, UP)
    right /= np.maximum(np.linalg.norm(right, axis=1), 1e-9)[:, None]
    upv = np.cross(right, fwd)
    turn = math.radians(cfg["turn"]) * strength
    yaw, pitch = wave(turn), wave(turn)
    out["roll"] = out["roll"] + wave(turn * 0.6)
    move = cfg["move"] * strength * dist
    dx, dz = wave(1.0) * move, wave(1.0) * move
    if cfg["bob"]:
        dz = dz + move * 1.5 * np.abs(np.sin(math.pi * cfg["bob"] * t))
    out["pos"] = out["pos"] + right * dx[:, None] + upv * dz[:, None]
    out["target"] = out["target"] + right * dx[:, None] + upv * dz[:, None] \
        + (right * np.tan(yaw)[:, None] + upv * np.tan(pitch)[:, None]) * dist[:, None]


# ---------------------------------------------------------------------------
# the moves
# ---------------------------------------------------------------------------

HEIGHTS = {"LOW": 6.0, "EYE": 18.0, "HIGH": 38.0}            # elevation (deg) of Orbit's three heights
DISTANCES = {"TIGHT": 1.0, "NORMAL": 1.12, "ROOMY": 1.35}    # margin round the model (1 = touching the frame)


def _fit_round(S: Subject, target, az0, az1, el, lens, aspect, margin, n=13) -> float:
    """One distance for a whole arc: the largest the fit needs anywhere on it (a steady orbit, no breathing)."""
    return max(fit_distance(S.points, target, direction(a, el), lens, aspect, margin)
               for a in np.linspace(az0, az1, n))


def orbit(S: Subject, turn=180.0, height="EYE", way="LEFT", distance="NORMAL", start_az=-60.0, lens=50.0,
          aspect=16 / 9, around=None) -> Shot:
    """Turns round the model (or a picked part: ``around`` = its Subject) at one height and one distance."""
    T = around or S
    el = HEIGHTS.get(height, height) if isinstance(height, str) else float(height)
    sgn = 1.0 if way == "LEFT" else -1.0
    az = start_az + sgn * np.linspace(0.0, turn, max(3, int(abs(turn) / 30) + 1))
    d = _fit_round(T, T.centre, az[0], az[-1], el, lens, aspect, DISTANCES[distance])
    h = np.array([T.centre + direction(a, el) * d for a in az])
    return Shot("Orbit", h, "MODEL", aim_point=T.centre.copy(), lens=[lens], easing="SMOOTH", ramp=0.25,
                options=dict(turn=turn, height=height, way=way, distance=distance))


def push_in(S: Subject, part: Subject, closeness=0.5, az=-50.0, el=20.0, lens=50.0, aspect=16 / 9,
            reverse=False) -> Shot:
    """From the whole model to a part (``reverse``: pull out = a reveal). ``closeness`` 0 … 1: how much of the way
    to a close-up of the part it goes. The aim slides from the model's middle to the part's middle."""
    d0 = fit_distance(S.points, S.centre, direction(az, el), lens, aspect, 1.12)
    d1 = fit_distance(part.points, part.centre, direction(az, el), lens, aspect, 1.6)
    a = S.centre + direction(az, el) * d0
    b_full = part.centre + direction(az, el) * d1
    b = a + (b_full - a) * closeness
    t1 = S.centre + (part.centre - S.centre) * min(1.0, closeness * 1.4)
    h, k = np.array([a, (a + b) / 2, b]), np.array([S.centre, (S.centre + t1) / 2, t1])
    if reverse:
        h, k = h[::-1].copy(), k[::-1].copy()
    return Shot("Pull out" if reverse else "Push in", h, "KEYS", aim_keys=k, lens=[lens], easing="SMOOTH",
                ramp=0.4, options=dict(closeness=closeness, reverse=reverse))


def crane(S: Subject, rise="UP", how_high=1.0, push=0.15, az=-40.0, lens=40.0, aspect=16 / 9) -> Shot:
    """The camera rises (or sinks) at about one distance from the model, still looking at it: from near the floor
    to high above (``how_high`` 0.3 … 1.5 times the model's height above its top), with a little push in."""
    d = fit_distance(S.points, S.centre, direction(az, 15), lens, aspect, 1.15)
    lowz = S.ground + max(0.25, 0.08 * S.size[2])
    highz = S.hi[2] + how_high * max(S.size[2], 0.3 * S.radius)
    flat = direction(az, 0)
    a = np.array([*(S.centre[:2] + flat[:2] * d), lowz])
    b = np.array([*(S.centre[:2] + flat[:2] * d * (1 - push)), highz])
    h = np.array([a + (b - a) * f for f in (0.0, 0.5, 1.0)])
    look_low = S.centre + np.array([0, 0, 0.15 * S.size[2]])
    k = np.array([look_low, S.centre, S.centre - np.array([0, 0, 0.1 * S.size[2]])])
    if rise == "DOWN":
        h, k = h[::-1].copy(), k[::-1].copy()
    return Shot("Crane " + rise.lower(), h, "KEYS", aim_keys=k, lens=[lens], easing="SMOOTH", ramp=0.35,
                options=dict(rise=rise, how_high=how_high, push=push))


def slide(S: Subject, length=0.8, side=-90.0, el=12.0, look="MODEL", lens=50.0, aspect=16 / 9) -> Shot:
    """Slides past the model's side, square to the view (a dolly track): ``length`` = how far, in model lengths;
    look MODEL turns to keep the middle (the parts in front pass the ones behind); HELD looks straight ahead."""
    dvec = direction(side, el)
    d = fit_distance(S.points, S.centre, dvec, lens, aspect, 1.05) * 0.8
    across = np.cross(UP, dvec)
    across /= np.linalg.norm(across)
    span = length * float(np.max(np.abs((S.points - S.centre) @ across))) * 2
    mid = S.centre + dvec * d
    h = np.array([mid - across * span / 2, mid, mid + across * span / 2])
    return Shot("Slide past", h, look, aim_point=S.centre.copy(), lens=[lens], easing="SMOOTH", ramp=0.3,
                options=dict(length=length, look=look))


def fly_over(S: Subject, height=0.6, along=True, look="MODEL", lens=35.0, aspect=16 / 9) -> Shot:
    """Comes in low on one side, passes over the top, leaves on the other side (along or across the model)."""
    ax = 0 if (S.size[0] >= S.size[1]) == along else 1
    e = np.zeros(3)
    e[ax] = 1.0
    reach = S.size[ax] / 2 + 0.9 * S.radius
    top = S.hi[2] + height * S.radius
    mid_z = S.centre[2] + 0.25 * S.size[2]
    side = np.zeros(3)
    side[1 - ax] = 0.25 * S.size[1 - ax]
    h = np.array([S.centre - e * reach + np.array([0, 0, mid_z - S.centre[2]]) + side,
                  S.centre - e * 0.35 * reach + np.array([0, 0, top - S.centre[2]]) + side * 0.5,
                  S.centre + e * 0.35 * reach + np.array([0, 0, top - S.centre[2]]) - side * 0.5,
                  S.centre + e * reach + np.array([0, 0, mid_z - S.centre[2]]) - side])
    return Shot("Fly-over", h, look, aim_point=S.centre.copy(), lens=[lens], easing="LINEAR", ramp=0.2,
                options=dict(height=height, along=along, look=look))


def top_down(S: Subject, end_az=-60.0, end_el=8.0, distance="NORMAL", lens=50.0, aspect=16 / 9,
             reverse=False) -> Shot:
    """Starts straight above, looking down (a plan view), swings down to a side view in one vertical arc."""
    els = np.linspace(89.0, end_el, 6)
    d = max(fit_distance(S.points, S.centre, direction(end_az, e), lens, aspect, DISTANCES[distance]) for e in els)
    h = np.array([S.centre + direction(end_az, e) * d for e in els])
    if reverse:
        h = h[::-1].copy()
    return Shot("Top-down to side", h, "MODEL", aim_point=S.centre.copy(), lens=[lens], easing="SMOOTH",
                ramp=0.35, options=dict(end_az=end_az, end_el=end_el, reverse=reverse))


def hero(S: Subject, turn=70.0, low=0.12, lens=24.0, start_az=-80.0, aspect=16 / 9) -> Shot:
    """Low and close with a wide lens, a slow arc: the machine towers over the picture."""
    aim = S.centre + np.array([0, 0, 0.12 * S.size[2]])
    z = S.ground + max(0.15, low * S.size[2])
    az = start_az + np.linspace(0.0, turn, max(3, int(abs(turn) / 20) + 1))
    d = 0.0
    for a in az:
        dirv = direction(a, 0)
        d = max(d, fit_distance(S.points, aim, dirv, lens, aspect, 1.0))
    d *= 0.82                                             # a little closer than "all in": the top may leave the frame
    h = np.array([[*(aim[:2] + direction(a, 0)[:2] * d), z] for a in az])
    return Shot("Hero arc", h, "MODEL", aim_point=aim, lens=[lens], easing="SMOOTH", ramp=0.3,
                options=dict(turn=turn, low=low, lens=lens))


def follow(track: np.ndarray, part: Subject, az=-50.0, el=25.0, distance=1.0, lag=0.5, fps=25.0, lens=50.0,
           aspect=16 / 9) -> dict:
    """A chase camera: keeps an offset from a moving part's middle (``track``: n x 3), level, smoothed by ``lag``
    seconds (a crane's hook swinging does not shake the picture). Returns sampled frames, not handles: the path IS
    the part's (today's Ride along with Keep level, plus the lag)."""
    d = fit_distance(part.points, part.centre, direction(az, el), lens, aspect, 1.6) * distance
    off = direction(az, el) * d
    k = 1.0 - math.exp(-1.0 / max(1e-3, lag * fps)) if lag > 0 else 1.0
    sm = np.array(track[0], float)
    pos, tgt = [], []
    for x in track:
        sm = sm + (np.asarray(x) - sm) * k
        pos.append(sm + off)
        tgt.append(sm.copy())
    n = len(track)
    return {"pos": np.array(pos), "target": np.array(tgt), "lens": np.full(n, lens),
            "focus": np.full(n, d), "roll": np.zeros(n)}


def focus_pull(S: Subject, near: Subject, far: Subject, az=-35.0, el=12.0, lens=85.0, aspect=16 / 9,
               creep=0.06, room=2.4) -> Shot:
    """Long lens, close on ``near`` (framed with ``room`` x its size round it, so ``far`` lies well behind), the
    camera nearly still (``creep``: a slow push, share of the distance); the sharp spot moves from ``near`` to ``far``
    in the middle of the step. The aim moves a little towards ``far``. A pull needs depth: framed on both parts, the
    two lay at nearly one distance and the change was hard to see (first try on the test mill)."""
    aim0 = near.centre
    aim1 = near.centre + (far.centre - near.centre) * 0.25
    d = fit_distance(near.points, aim0, direction(az, el), lens, aspect, room)
    a = aim0 + direction(az, el) * d
    b = aim0 + direction(az, el) * d * (1 - creep)
    fa = float(np.linalg.norm(near.centre - a))
    fb = float(np.linalg.norm(far.centre - b))
    return Shot("Focus pull", np.array([a, b]), "KEYS", aim_keys=np.array([aim0, aim1]), lens=[lens],
                focus_keys=[fa, fb], easing="LINEAR", ramp=0.0, options=dict(pull_at=0.35, pull_for=0.3))


def drawn(handles, look="AHEAD", aim_point=None, lens=28.0) -> Shot:
    """A path the user draws (today's Fly a path)."""
    return Shot("Fly-through", np.asarray(handles, float), look, aim_point=aim_point, lens=[lens], easing="SMOOTH",
                ramp=0.25)


# ---------------------------------------------------------------------------
# editing a path
# ---------------------------------------------------------------------------

def move_handle(shot: Shot, i: int, to) -> Shot:
    """The user drags handle ``i``: the move becomes a free path (its other handles and aim stay)."""
    h = shot.handles.copy()
    h[i] = to
    out = Shot(shot.name + " (edited)", h, shot.aim, shot.aim_point, shot.aim_keys, shot.aim_track, list(shot.lens),
               shot.focus_keys, shot.easing, shot.ramp, dict(shot.options), shot.shake)
    return out


def add_handle(shot: Shot, after: int) -> Shot:
    """A point added halfway between ``after`` and the next one, on the curve (nothing moves until it is dragged)."""
    path = P.Path(shot.handles)
    s = (path.at_point[after] + path.at_point[after + 1]) / 2
    h = np.insert(shot.handles, after + 1, path.point(s), axis=0)
    k = None if shot.aim_keys is None else np.insert(shot.aim_keys, after + 1,
                                                     (shot.aim_keys[after] + shot.aim_keys[after + 1]) / 2, axis=0)
    return Shot(shot.name + " (edited)", h, shot.aim, shot.aim_point, k, shot.aim_track, list(shot.lens),
                shot.focus_keys, shot.easing, shot.ramp, dict(shot.options), shot.shake)


def orbit_error(n_per_turn: int = 12, turn: float = 360.0) -> float:
    """How far (share of the radius) the smooth curve through an orbit's handles strays from the true circle."""
    k = int(round(n_per_turn * turn / 360.0)) + 1
    a = np.radians(np.linspace(0.0, turn, k))
    h = np.stack([np.cos(a), np.sin(a), np.zeros_like(a)], axis=1)
    path = P.Path(h)
    r = np.linalg.norm(path.dense[:, :2], axis=1)
    return float(np.max(np.abs(r - 1.0)))


if __name__ == "__main__":
    for n in (4, 8, 12, 24):
        print(f"orbit, {n} handles per turn: off the circle by up to {orbit_error(n) * 100:.3f} % of the radius")
