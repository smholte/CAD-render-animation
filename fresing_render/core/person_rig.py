"""The person's rig without Blender (task 0157; shared with task 0156): poses, forward kinematics, IK for legs and
arms, looking, and the numbers Blender's armature needs.

The bones are ``core/props_detail.BONES`` (17 bones, same names and parents). The person's mesh is made in the rest
pose ``REST_POSE`` (= the "Standing" pose), scaled to the person's height and lifted so its soles are on z = 0 – as
``props_detail.person()`` does. All points here are in that **figure space**: metres of this person, z up, the figure
faces -y, its right hand at -x. The person object in Blender carries the figure space into the world (place + turn).

A pose (``Pose``) holds per bone its turn against its parent (``local``: 3x3, in the frames ``props_detail._local``
uses: a limb's bone runs along its frame's -z, the feet along -y, the spine bones along +z; x points to the figure's
left, y backwards when standing), the pelvis's head (``pelvis``) and the hands' fingers (0 open … 1 fist; ``point``:
the index finger stays straight). ``Figure(height)`` makes poses (``rest``, ``from_angles``), works out where every
bone is (``fk``) and changes a pose so a foot or a hand reaches a point (``leg_ik``, ``arm_ik``) or the head looks
somewhere (``look``). ``blender_quaternion`` / ``blender_location`` turn a pose into a pose bone's rotation and the
pelvis's location for Blender (``blender/person_rig.py`` writes them).

Use (0156, 0157)::

    fig = Figure(1.75)
    pose = fig.rest()                                   # standing, feet on z = 0
    fig.arm_ik(pose, "r", wrist=np.array((-0.2, -0.45, 1.1)), elbow=np.array((-1.0, 0.6, -0.4)))
    pose.fingers["r"] = 0.9                             # a grip
    q = fig.blender_quaternion(pose, "r_arm")           # (w, x, y, z) for pose.bones["r_arm"].rotation_quaternion
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import props_detail as P

BONES = tuple(P.BONES)                                   # parents before children
PARENT = {b: P.BONES[b][0] for b in BONES}
AT = {b: np.asarray(P.BONES[b][1], float) for b in BONES}
VEC = {b: np.asarray(P.BONES[b][2], float) for b in BONES}
REST_POSE = "STANDING"
SIDES = ("l", "r")
FINGERS_REST = 0.35                                      # the curl of the rest mesh's fingers (props_detail STANDING)

# the fixed turn from a props_detail bone frame to Blender's bone frame (columns X, Y, Z; Y along the bone)
_C_DOWN = np.array(((1.0, 0, 0), (0, 0, 1.0), (0, -1.0, 0)))     # bone along -z: X = x, Y = -z, Z = y
_C_UP = np.array(((1.0, 0, 0), (0, 0, -1.0), (0, 1.0, 0)))       # bone along +z: X = x, Y = z, Z = -y
_C_FWD = np.array(((1.0, 0, 0), (0, -1.0, 0), (0, 0, -1.0)))     # bone along -y (feet): X = x, Y = -y, Z = -z


def _c_of(b: str) -> np.ndarray:
    v = VEC[b]
    if v[2] < -1e-9:
        return _C_DOWN
    if v[2] > 1e-9:
        return _C_UP
    return _C_FWD


C = {b: _c_of(b) for b in BONES}


def rx(a: float) -> np.ndarray:
    return P._rx(a)


def ry(a: float) -> np.ndarray:
    return P._ry(a)


def rz(a: float) -> np.ndarray:
    return P._rz(a)


def unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def quat(R) -> tuple:
    """(w, x, y, z) of a 3x3 rotation."""
    m = np.asarray(R, float)
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = (0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s)
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = ((m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s)
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = ((m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s)
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = ((m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s)
    q = np.asarray(q, float)
    q /= np.linalg.norm(q)
    return tuple(float(x) for x in (q if q[0] >= 0 else -q))


def matrix(q) -> np.ndarray:
    """3x3 rotation of a (w, x, y, z) quaternion."""
    w, x, y, z = (float(c) for c in q)
    return np.array(((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
                     (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
                     (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))))


def slerp(A, B, w: float) -> np.ndarray:
    """The turn ``w`` of the way from rotation A to rotation B (0 = A, 1 = B)."""
    if w <= 0.0:
        return np.array(A, float)
    if w >= 1.0:
        return np.array(B, float)
    qa, qb = np.asarray(quat(A)), np.asarray(quat(B))
    d = float(np.dot(qa, qb))
    if d < 0:
        qb, d = -qb, -d
    if d > 0.9995:
        q = qa + (qb - qa) * w
    else:
        th = math.acos(min(1.0, d))
        q = (math.sin((1 - w) * th) * qa + math.sin(w * th) * qb) / math.sin(th)
    return matrix(q / np.linalg.norm(q))


def angle_between(A, B) -> float:
    """How far apart two rotations are (radians)."""
    m = np.asarray(A, float).T @ np.asarray(B, float)
    return math.acos(max(-1.0, min(1.0, (float(np.trace(m)) - 1.0) / 2.0)))


@dataclass
class Pose:
    """One moment of the person: each bone's turn against its parent, the pelvis's place, the fingers."""
    local: dict
    pelvis: np.ndarray
    fingers: dict = field(default_factory=lambda: {"l": FINGERS_REST, "r": FINGERS_REST})
    point: dict = field(default_factory=lambda: {"l": 0.0, "r": 0.0})

    def copy(self) -> "Pose":
        return Pose({b: np.array(m) for b, m in self.local.items()}, np.array(self.pelvis, float),
                    dict(self.fingers), dict(self.point))


def blend(a: Pose, b: Pose, w: float, bones=None) -> Pose:
    """A pose ``w`` of the way from ``a`` to ``b`` (only ``bones`` when given; the rest stays ``a``)."""
    out = a.copy()
    if w <= 0.0:
        return out
    for bn in (bones or BONES):
        out.local[bn] = slerp(a.local[bn], b.local[bn], w)
    if bones is None or "pelvis" in bones:
        out.pelvis = a.pelvis + (b.pelvis - a.pelvis) * w
    for s in SIDES:
        if bones is None or f"{s}_hand" in bones:
            out.fingers[s] = a.fingers[s] + (b.fingers[s] - a.fingers[s]) * w
            out.point[s] = a.point[s] + (b.point[s] - a.point[s]) * w
    return out


_LIFTS: dict = {}


def _lift_of(angles) -> float:
    """How far ``props_detail.person`` lifts this pose so its lowest point is on the floor (before scaling)."""
    key = angles if isinstance(angles, str) else None
    if key is not None and key in _LIFTS:
        return _LIFTS[key]
    if key is not None:
        _sh, _sk, lift = P._raw_person(key, "WORKSHOP", True, False, 0, P.DETAILED)
        _LIFTS[key] = lift
        return lift
    return _approx_lift(P.skeleton(angles))


def _approx_lift(sk) -> float:
    """The lift from the skeleton alone: the soles' corners and the fronts of the knees."""
    low = math.inf
    for s in SIDES:
        head, R, _t = sk[f"{s}_foot"]
        X, F, U = R[:, 0], -R[:, 1], R[:, 2]
        for along in (-0.06, 0.03, 0.15, 0.19):
            for w in (-0.045, 0.0, 0.045):
                low = min(low, float((head + F * along + X * w + U * (-P.ANKLE_H))[2]))
        h, Rs, _t = sk[f"{s}_shin"]
        low = min(low, float((h + Rs @ np.array((0.0, -0.058, 0.0)))[2]))
    return -low


class Figure:
    """A person of one height: makes poses and works out where the bones are (figure space, metres)."""

    THIGH, SHIN = 0.43, 0.395
    ARM, FOREARM = 0.29, 0.255

    def __init__(self, height: float = P.DEFAULT_HEIGHT):
        self.height = float(height)
        self.k = self.height / P.REST_HEIGHT
        self.lift = _lift_of(REST_POSE)
        self.rest_angles = P.POSES[REST_POSE]
        self.rest_local = {b: P._local(b, self.rest_angles) for b in BONES}
        self._rest = self._pose_of(self.rest_angles, self.lift)
        self.rest_fk = self.fk(self._rest)

    # -- making poses ---------------------------------------------------------------------------------------------
    def _pose_of(self, angles: dict, lift: float) -> Pose:
        local = {b: P._local(b, angles) for b in BONES}
        pelvis = (AT["pelvis"] + np.array((0.0, 0.0, lift))) * self.k
        return Pose(local, pelvis, {s: float(angles.get(f"{s}_fingers", FINGERS_REST)) for s in SIDES},
                    {s: float(angles.get(f"{s}_point", 0.0)) for s in SIDES})

    def rest(self) -> Pose:
        """The rest pose (Standing): the mesh as it is made."""
        return self._rest.copy()

    def from_angles(self, angles) -> Pose:
        """Any ``props_detail`` pose (an id of ``POSES`` or an angle dict), standing on the floor as ``person()``."""
        d = P.POSES.get(angles, P.POSES[REST_POSE]) if isinstance(angles, str) else angles
        return self._pose_of(d, _lift_of(angles if isinstance(angles, str) else d))

    # -- where things are -----------------------------------------------------------------------------------------
    def fk(self, pose: Pose) -> dict:
        """{bone: (head, frame R, tail)} in figure space."""
        out: dict = {}
        k = self.k
        for b in BONES:
            par = PARENT[b]
            if par is None:
                head, R = np.asarray(pose.pelvis, float), pose.local[b]
            else:
                ph, PR, _t = out[par]
                head = ph + PR @ (AT[b] * k)
                R = PR @ pose.local[b]
            out[b] = (head, R, head + R @ (VEC[b] * k))
        return out

    def frame(self, pose: Pose, bone: str):
        """(head, R) of one bone, walking only its own chain."""
        chain = []
        b = bone
        while b is not None:
            chain.append(b)
            b = PARENT[b]
        head, R = np.asarray(pose.pelvis, float), np.eye(3)
        for i, b in enumerate(reversed(chain)):
            if i:
                head = head + R @ (AT[b] * self.k)
            R = R @ pose.local[b]
        return head, R

    def palm(self, pose: Pose, side: str, fk=None):
        """(point, frame) of the palm's centre: the frame's x = out of the back of the hand for the left hand and into
        the palm for the right, z = along the fingers (props_detail's hand)."""
        head, R = (fk[f"{side}_hand"][:2] if fk is not None else self.frame(pose, f"{side}_hand"))
        Z = -R[:, 2]
        sd = 1.0 if side == "l" else -1.0
        return head + Z * (0.075 * self.k) - R[:, 0] * sd * (0.018 * self.k), R

    def sole_points(self, pose: Pose, side: str, fk=None):
        """Heel, ball and toe of a sole (figure space): what a foot stands on."""
        head, R = (fk[f"{side}_foot"][:2] if fk is not None else self.frame(pose, f"{side}_foot"))
        F, U = -R[:, 1], R[:, 2]
        base = head - U * (P.ANKLE_H * self.k)
        return {"heel": base + F * (-0.06 * self.k), "ball": base + F * (0.15 * self.k),
                "toe": base + F * (0.212 * self.k)}

    # -- inverse kinematics --------------------------------------------------------------------------------------
    def hip(self, pose: Pose, side: str) -> np.ndarray:
        return np.asarray(pose.pelvis, float) + pose.local["pelvis"] @ (AT[f"{side}_thigh"] * self.k)

    def leg_ik(self, pose: Pose, side: str, ankle, foot_R=None, knee=None) -> float:
        """Turn thigh, shin and foot so the ankle is at ``ankle`` (figure space) and the foot's frame is ``foot_R``
        (3x3 in figure space; None: as the shin carries it). ``knee``: the way the knee points (default: the pelvis's
        front). Returns how far the ankle stays from the point (0 when it reaches)."""
        k = self.k
        a, b = self.THIGH * k, self.SHIN * k
        Rp = pose.local["pelvis"]
        hip = self.hip(pose, side)
        ankle = np.asarray(ankle, float)
        D = ankle - hip
        d = float(np.linalg.norm(D))
        e = D / d if d > 1e-9 else np.array((0.0, 0.0, -1.0))
        dc = min(max(d, abs(a - b) + 1e-4), (a + b) * (1.0 - 1e-5))
        pole = np.asarray(knee, float) if knee is not None else -Rp[:, 1]
        p = pole - e * float(np.dot(pole, e))
        if np.linalg.norm(p) < 1e-6:
            p = -Rp[:, 1] - e * float(np.dot(-Rp[:, 1], e))
        p = unit(p)
        ca = (a * a + dc * dc - b * b) / (2 * a * dc)
        sa = math.sqrt(max(0.0, 1.0 - ca * ca))
        u = e * ca + p * sa
        kn = hip + u * a
        w = (hip + e * dc - kn) / b
        perp = w - u * float(np.dot(u, w))
        Y = unit(perp) if np.linalg.norm(perp) > 1e-7 else -p
        Z = -u
        X = np.cross(Y, Z)
        Rt = np.column_stack((X, Y, Z))
        th = math.atan2(float(np.linalg.norm(perp)), float(np.dot(u, w)))
        Rs = Rt @ rx(th)
        pose.local[f"{side}_thigh"] = Rp.T @ Rt
        pose.local[f"{side}_shin"] = rx(th)
        if foot_R is not None:
            pose.local[f"{side}_foot"] = Rs.T @ np.asarray(foot_R, float)
        return max(0.0, d - dc)

    def shoulder(self, pose: Pose, side: str) -> np.ndarray:
        head, R = self.frame(pose, "chest")
        return head + R @ (AT[f"{side}_arm"] * self.k)

    def arm_ik(self, pose: Pose, side: str, wrist, elbow=None, hand_R=None) -> float:
        """Turn arm, forearm and hand so the wrist (the hand bone's head) is at ``wrist`` (figure space). ``elbow``:
        the way the elbow points (default back, out and down). ``hand_R``: the hand's frame (3x3, figure space) – the
        forearm twists to it. Returns how far the wrist stays from the point."""
        k = self.k
        a, b = self.ARM * k, self.FOREARM * k
        ch, Rc = self.frame(pose, "chest")
        sh = ch + Rc @ (AT[f"{side}_arm"] * k)
        sd = 1.0 if side == "l" else -1.0
        wrist = np.asarray(wrist, float)
        D = wrist - sh
        d = float(np.linalg.norm(D))
        e = D / d if d > 1e-9 else np.array((0.0, 0.0, -1.0))
        dc = min(max(d, abs(a - b) + 1e-4), (a + b) * (1.0 - 1e-5))
        pole = np.asarray(elbow, float) if elbow is not None else Rc @ np.array((0.6 * sd, 1.0, -0.4))
        p = pole - e * float(np.dot(pole, e))
        if np.linalg.norm(p) < 1e-6:
            p = Rc[:, 1] - e * float(np.dot(Rc[:, 1], e))
        p = unit(p)
        ca = (a * a + dc * dc - b * b) / (2 * a * dc)
        sa = math.sqrt(max(0.0, 1.0 - ca * ca))
        u = e * ca + p * sa
        el = sh + u * a
        w = (sh + e * dc - el) / b
        perp = w - u * float(np.dot(u, w))
        Y = -unit(perp) if np.linalg.norm(perp) > 1e-7 else p
        Z = -u
        X = np.cross(Y, Z)
        Ra = np.column_stack((X, Y, Z))
        v = math.atan2(float(np.linalg.norm(perp)), float(np.dot(u, w)))
        Rf0 = Ra @ rx(-v)
        pose.local[f"{side}_arm"] = Rc.T @ Ra
        if hand_R is not None:
            M = Rf0.T @ np.asarray(hand_R, float)
            tw = math.atan2(M[1, 0] - M[0, 1], M[0, 0] + M[1, 1])
            tw = max(-math.radians(110), min(math.radians(110), tw))
            pose.local[f"{side}_forearm"] = rx(-v) @ rz(tw)
            pose.local[f"{side}_hand"] = (Rf0 @ rz(tw)).T @ np.asarray(hand_R, float)
        else:
            tw_old = pose.local[f"{side}_forearm"]
            # keep the forearm's own twist (the part of its old turn about its own axis)
            tw = math.atan2(tw_old[1, 0] - tw_old[0, 1], tw_old[0, 0] + tw_old[1, 1])
            pose.local[f"{side}_forearm"] = rx(-v) @ rz(tw)
        return max(0.0, d - dc)

    def look(self, pose: Pose, direction, amount: float = 1.0, chest_share: float = 0.25) -> None:
        """Turn chest, neck and head so the face looks along ``direction`` (figure space; at most 80° to a side,
        40° up or down; ``amount`` 0 … 1 of the way)."""
        d = np.asarray(direction, float)
        hz = math.hypot(d[0], d[1])
        if hz < 1e-9 and abs(d[2]) < 1e-9:
            return
        Rp = pose.local["pelvis"]
        dl = Rp.T @ d                                      # in the pelvis's frame (front = -y)
        yaw = math.atan2(dl[0], -dl[1])
        pitch = math.atan2(-dl[2], math.hypot(dl[0], dl[1]))
        yaw = max(-math.radians(80), min(math.radians(80), yaw)) * amount
        pitch = max(-math.radians(40), min(math.radians(40), pitch)) * amount
        cs = chest_share
        pose.local["chest"] = pose.local["chest"] @ rz(yaw * cs)
        pose.local["neck"] = pose.local["neck"] @ rz(yaw * (1 - cs) * 0.4) @ rx(pitch * 0.4)
        pose.local["head"] = pose.local["head"] @ rz(yaw * (1 - cs) * 0.6) @ rx(pitch * 0.6)

    # -- Blender --------------------------------------------------------------------------------------------------
    def rest_matrix(self, bone: str):
        """(head, 3x3 frame with Blender's Y along the bone, length) of a bone in the rest pose (figure space)."""
        head, R, _t = self.rest_fk[bone]
        return head, R @ C[bone], float(np.linalg.norm(VEC[bone]) * self.k)

    def blender_quaternion(self, pose: Pose, bone: str) -> tuple:
        """The pose bone's rotation_quaternion (w, x, y, z) for this pose (in the bone's rest frame)."""
        Cb = C[bone]
        return quat(Cb.T @ self.rest_local[bone].T @ pose.local[bone] @ Cb)

    def blender_location(self, pose: Pose) -> tuple:
        """The pelvis pose bone's location (its rest frame) that puts its head at ``pose.pelvis``."""
        head, B, _ln = self.rest_matrix("pelvis")
        return tuple(float(x) for x in B.T @ (np.asarray(pose.pelvis, float) - head))


# ---------------------------------------------------------------------------
# skin weights: which bone moves which point of the rest mesh
# ---------------------------------------------------------------------------

# bones joined by a hinge that bends the skin (elbow, wrist, knee, the spine): their skin is blended near the joint.
# The shoulder, the hip and the ankle are not: a sleeve top, a thigh top and a shoe move with their own bone.
CHAINS = (("pelvis", "spine", "chest", "neck", "head"), ("l_arm", "l_forearm", "l_hand"),
          ("r_arm", "r_forearm", "r_hand"), ("l_thigh", "l_shin"), ("r_thigh", "r_shin"), ("l_foot",), ("r_foot",))
CHAIN_OF = {b: c for c in CHAINS for b in c}
BLEND = 0.06                  # metres either side of a hinge (1.75 m person) over which the skin is shared


def _segment_params(fig: Figure, pts: np.ndarray):
    """For every point and bone: (distance to the bone's segment, position along it in metres from its head)."""
    n = len(pts)
    dist = np.empty((n, len(BONES)))
    along = np.empty((n, len(BONES)))
    for j, b in enumerate(BONES):
        head, _R, tail = fig.rest_fk[b]
        d = tail - head
        ln = float(np.linalg.norm(d))
        u = (pts - head) @ (d / ln)
        uc = np.clip(u, 0.0, ln)
        foot = head + np.outer(uc, d / ln)
        dist[:, j] = np.linalg.norm(pts - foot, axis=1)
        along[:, j] = u
    return dist, along


def bind(fig: Figure, anchors, group=None) -> np.ndarray:
    """Weights (n points x 17 bones, rows sum to 1) for points of the rest mesh. ``anchors``: (n, 3) figure-space
    points (a loft's ring centre for each of its points: the ring moves as one); ``group``: an id per point – points
    with the same id are one shape, which stays on one chain of bones (its majority)."""
    pts = np.asarray(anchors, float).reshape(-1, 3)
    n = len(pts)
    W = np.zeros((n, len(BONES)))
    if n == 0:
        return W
    dist, along = _segment_params(fig, pts)
    near = dist.argmin(axis=1)
    groups = np.zeros(n, int) if group is None else np.asarray(group, int)
    index = {b: j for j, b in enumerate(BONES)}
    r = BLEND * fig.k
    for g in np.unique(groups):
        sel = np.nonzero(groups == g)[0]
        votes = np.bincount(near[sel], minlength=len(BONES))
        chain = CHAIN_OF[BONES[int(votes.argmax())]]
        cols = [index[b] for b in chain]
        sub = dist[np.ix_(sel, cols)]
        best = sub.argmin(axis=1)
        for row, ci in zip(sel, best):
            b = chain[ci]
            jb = index[b]
            u = along[row, jb]
            ln = float(np.linalg.norm(VEC[b]) * fig.k)
            w = {b: 1.0}
            if ci > 0 and u < r:                                     # near the joint with the bone before
                s = 0.5 * (1.0 - _smooth(max(0.0, u) / r))
                w[chain[ci - 1]] = s
                w[b] = 1.0 - s
            if ci + 1 < len(chain) and u > ln - r:                   # near the joint with the bone after
                s = 0.5 * (1.0 - _smooth(max(0.0, ln - u) / r))
                w[chain[ci + 1]] = w.get(chain[ci + 1], 0.0) + s
                w[b] = w[b] - s
            for bb, ww in w.items():
                W[row, index[bb]] += ww
    W /= W.sum(axis=1, keepdims=True)
    return W


def _smooth(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def skin(fig: Figure, rest_points, W, pose: Pose) -> np.ndarray:
    """The rest mesh's points moved by a pose (linear blend skinning, as Blender's Armature modifier): for tests and
    for checking a pose without Blender."""
    pts = np.asarray(rest_points, float).reshape(-1, 3)
    posed = fig.fk(pose)
    out = np.zeros_like(pts)
    for j, b in enumerate(BONES):
        w = W[:, j]
        if not np.any(w):
            continue
        h0, R0, _t = fig.rest_fk[b]
        h1, R1, _t = posed[b]
        M = R1 @ R0.T
        out += w[:, None] * ((pts - h0) @ M.T + h1)
    return out
