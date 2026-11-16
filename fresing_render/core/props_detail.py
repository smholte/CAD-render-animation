"""Detailed props for scale and the human figure (task 0155). Pure Python + NumPy, no Blender.

Every prop comes in two levels of detail: ``DETAILED`` for close shots and ``LIGHT`` for far away or many copies.
``blender/props_scale.py`` writes both into one mesh (a face attribute says which level a face belongs to) and a
Geometry Nodes modifier keeps one of them, by the distance to the active camera or by the scene's setting.

The person is made in code: a skeleton (``BONES``) posed by joint angles (``POSES``, forward kinematics), a skin of
lofted rings round each bone, a face without anybody's likeness (nose, ears, eyes as simple shapes), hands with
fingers, safety shoes, clothes by outfit (``OUTFITS``) and an optional helmet and gloves. The figure faces -y (it
looks at the camera of a front view); its right hand is at -x. After posing it is moved so its lowest point is on the
floor (z = 0): standing feet stand on the floor, a kneeling knee rests on it.

Units: metres. Shapes: ``core/surroundings.py`` (Box, Tube, Loft ...). Nothing is downloaded and nothing is a real
product: no logos, no brand colours.
"""

from __future__ import annotations

import math

import numpy as np

from .surroundings import Box, Loft, Tube, place

DETAILED, LIGHT = "DETAILED", "LIGHT"
LODS = (DETAILED, LIGHT)

# ---------------------------------------------------------------------------
# the person's choices (the items of the person's settings; ids are stored in project files)
# ---------------------------------------------------------------------------

HEIGHTS = (1.65, 1.75, 1.85)
DEFAULT_HEIGHT = 1.75

POSE_ITEMS = (
    ("STANDING", "Standing", "Stands relaxed, arms down"),
    ("WALKING", "Walking", "In mid-step: one foot forward, the arms swing"),
    ("POINTING", "Pointing", "Points with the right arm straight ahead"),
    ("PANEL", "Hands on a panel", "Both hands forward at waist height, as on a control panel or a desk"),
    ("KNEELING", "Kneeling", "On the right knee, the left foot flat in front"),
    ("OPERATOR", "Operator at a machine", "Stands at a machine, the right hand on a button at chest height"),
)
POSES_IDS = tuple(p[0] for p in POSE_ITEMS)

OUTFIT_ITEMS = (
    ("WORKSHOP", "Workshop", "Navy work overalls, black safety shoes"),
    ("OFFSHORE", "Offshore", "Orange coverall with reflective bands, white helmet"),
    ("OFFICE", "Office / visitor", "Shirt and trousers with a yellow high-visibility vest"),
)
OUTFITS = tuple(o[0] for o in OUTFIT_ITEMS)

# skin and hair by the person's "look" (0 … 3): subtle variation between copies
LOOKS = (("skin_1", "hair_dark"), ("skin_2", "hair_brown"), ("skin_3", "hair_dark"), ("skin_4", "hair_grey"))

# ---------------------------------------------------------------------------
# small geometry helpers
# ---------------------------------------------------------------------------


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array(((1, 0, 0), (0, c, -s), (0, s, c)), float)


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array(((c, 0, s), (0, 1, 0), (-s, 0, c)), float)


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)), float)


def _t(p) -> tuple:
    return (float(p[0]), float(p[1]), float(p[2]))


def _loft(mat, rings, closed=True, caps=True, smooth=True) -> Loft:
    return Loft(mat, tuple(tuple(_t(p) for p in r) for r in rings), closed, caps, smooth)


def _ellipse(c, X, Y, rx, ry, n, power=2.0):
    """A ring round ``c`` in the plane of the unit vectors X, Y (a superellipse when ``power`` > 2: boxier)."""
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        ca, sa = math.cos(a), math.sin(a)
        if power != 2.0:
            ca = math.copysign(abs(ca) ** (2 / power), ca)
            sa = math.copysign(abs(sa) ** (2 / power), sa)
        out.append(c + X * (rx * ca) + Y * (ry * sa))
    return out


def ellipsoid(mat, c, rx, ry, rz, n=16, frame=None, lat_from=-90.0, smooth=True) -> Loft:
    """An ellipsoid (``lat_from`` > -90: only the part above that latitude, open below: a dome)."""
    R = np.eye(3) if frame is None else np.asarray(frame, float)
    c = np.asarray(c, float)
    m = max(4, n // 2)
    rings = []
    lo = math.radians(lat_from)
    for j in range(m + 1):
        lat = lo + (math.pi / 2 - lo) * j / m
        if j == m:
            lat = math.pi / 2 - 1e-3
        if j == 0 and lat_from <= -90:
            lat = -math.pi / 2 + 1e-3
        cl, sl = math.cos(lat), math.sin(lat)
        rings.append([c + R @ np.array((rx * cl * math.cos(2 * math.pi * i / n), ry * cl * math.sin(2 * math.pi * i / n),
                                        rz * sl)) for i in range(n)])
    return _loft(mat, rings, caps=True, smooth=smooth)


def rbox(mat, x, y, z, sx, sy, sz, r=0.01, n=3, rot=0.0) -> Loft:
    """A box with rounded edges and corners (radius ``r``), standing on z, centred on x/y, turned ``rot`` about z."""
    r = max(1e-4, min(r, sx / 2 - 1e-4, sy / 2 - 1e-4, sz / 2 - 1e-4))
    rings = []
    arcs = [math.pi / 2 * k / n for k in range(n + 1)]
    levels = [(z + r * (1 - math.cos(a)), r * (1 - math.sin(a))) for a in arcs]
    levels += [(z + sz - r * (1 - math.cos(a)), r * (1 - math.sin(a))) for a in reversed(arcs)]
    for zz, inset in levels:
        ring = []
        hx, hy = sx / 2 - r, sy / 2 - r
        rr = r - inset
        for qx, qy, a0 in ((1, 1, 0.0), (-1, 1, 90.0), (-1, -1, 180.0), (1, -1, 270.0)):
            for k in range(n + 1):
                a = math.radians(a0 + 90.0 * k / n)
                ring.append((qx * hx + rr * math.cos(a), qy * hy + rr * math.sin(a), zz))
        rings.append(ring)
    lo = _loft(mat, rings, caps=True, smooth=True)
    return place([lo], x, y, 0.0, rot)[0]


def _frames_along(pts):
    """Unit tangent and two normals at each point of a polyline (parallel transport: no twist)."""
    pts = np.asarray(pts, float)
    tans = []
    for i in range(len(pts)):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        d = b - a
        tans.append(d / (np.linalg.norm(d) or 1.0))
    t0 = tans[0]
    ref = np.array((0, 0, 1.0)) if abs(t0[2]) < 0.9 else np.array((1.0, 0, 0))
    u = np.cross(t0, ref)
    u /= np.linalg.norm(u)
    out = []
    for t in tans:
        u = u - t * float(np.dot(u, t))
        u /= (np.linalg.norm(u) or 1.0)
        v = np.cross(t, u)
        out.append((t, u, v))
    return out


def sweep(mat, pts, r, n=8, caps=True, radii=None) -> Loft:
    """A round tube along a polyline (radius ``r``, or one radius per point)."""
    pts = np.asarray(pts, float)
    rings = []
    for i, (_t0, u, v) in enumerate(_frames_along(pts)):
        rr = r if radii is None else radii[i]
        rings.append(_ellipse(pts[i], u, v, rr, rr, n))
    return _loft(mat, rings, caps=caps, smooth=True)


def rounded_path(corners, radius, k=4):
    """A polyline through ``corners`` whose inner corners are rounded with ``radius`` (``k`` points per bend)."""
    c = [np.asarray(p, float) for p in corners]
    out = [c[0]]
    for i in range(1, len(c) - 1):
        a, b, d = c[i - 1], c[i], c[i + 1]
        u = (a - b) / np.linalg.norm(a - b)
        w = (d - b) / np.linalg.norm(d - b)
        cosang = float(np.clip(np.dot(u, w), -1, 1))
        ang = math.acos(cosang)
        if ang > math.pi - 1e-3:
            out.append(b)
            continue
        dist = min(radius / math.tan(ang / 2), 0.45 * np.linalg.norm(a - b), 0.45 * np.linalg.norm(d - b))
        p0, p1 = b + u * dist, b + w * dist
        for j in range(k + 1):
            s = j / k                                   # a quadratic Bezier through the corner: close to an arc
            out.append((1 - s) ** 2 * p0 + 2 * (1 - s) * s * b + s * s * p1)
    out.append(c[-1])
    return out


# ---------------------------------------------------------------------------
# the person: skeleton, poses, skin and clothes
# ---------------------------------------------------------------------------

# bone: parent, where it starts (in the parent's frame, from the parent's head), its rest vector (figure 1.75 m)
BONES = {
    "pelvis": (None, (0.0, 0.0, 0.95), (0.0, 0.0, 0.10)),
    "spine": ("pelvis", (0.0, 0.0, 0.10), (0.0, 0.0, 0.20)),
    "chest": ("spine", (0.0, 0.0, 0.20), (0.0, 0.0, 0.22)),
    "neck": ("chest", (0.0, 0.0, 0.22), (0.0, 0.0, 0.065)),
    "head": ("neck", (0.0, 0.0, 0.065), (0.0, 0.0, 0.215)),
}
for _sd, _p in ((1, "l"), (-1, "r")):
    BONES[f"{_p}_arm"] = ("chest", (0.172 * _sd, 0.0, 0.165), (0.0, 0.0, -0.29))
    BONES[f"{_p}_forearm"] = (f"{_p}_arm", (0.0, 0.0, -0.29), (0.0, 0.0, -0.255))
    BONES[f"{_p}_hand"] = (f"{_p}_forearm", (0.0, 0.0, -0.255), (0.0, 0.0, -0.18))
    BONES[f"{_p}_thigh"] = ("pelvis", (0.09 * _sd, 0.0, -0.04), (0.0, 0.0, -0.43))
    BONES[f"{_p}_shin"] = (f"{_p}_thigh", (0.0, 0.0, -0.43), (0.0, 0.0, -0.395))
    BONES[f"{_p}_foot"] = (f"{_p}_shin", (0.0, 0.0, -0.395), (0.0, -0.15, 0.0))

ANKLE_H = 0.085            # the ankle above the sole in the rest pose
REST_HEIGHT = 1.7835       # top of the hair of the standing skeleton above (no helmet): scaled to the height

# Poses: angles in degrees. Limbs (fwd, out, twist): fwd moves the limb towards the front (-y), out away from the
# body; spine bones (fwd, side, twist): fwd leans forward. Knees bend back, elbows bend forward, ankles: toe up > 0.
# fingers: 0 open … 1 fist; "point": the index finger stays straight.
POSES = {
    "STANDING": {
        "l_arm": (2, 7, 0), "r_arm": (2, 7, 0), "l_forearm": 10, "r_forearm": 10,
        "l_thigh": (0, 3, 0), "r_thigh": (0, 3, 0), "l_fingers": 0.35, "r_fingers": 0.35,
    },
    "WALKING": {
        "pelvis": (3, 0, 4), "chest": (2, 0, -6), "head": (-3, 0, 0),
        "r_thigh": (20, 2, 0), "r_shin": 3, "r_foot": 10,
        "l_thigh": (-14, 2, 0), "l_shin": 28, "l_foot": -24,
        "l_arm": (22, 6, 0), "l_forearm": 28, "r_arm": (-18, 6, 0), "r_forearm": 12,
        "l_fingers": 0.4, "r_fingers": 0.4,
    },
    "POINTING": {
        "chest": (0, 0, 8), "head": (0, 0, 8), "neck": (-4, 0, 0),
        "r_arm": (82, 12, 0), "r_forearm": 4, "r_hand": (0, 0), "r_fingers": 0.95, "r_point": 1.0,
        "l_arm": (2, 7, 0), "l_forearm": 12, "l_fingers": 0.35,
        "l_thigh": (0, 4, 0), "r_thigh": (0, 3, 0),
    },
    "PANEL": {
        "spine": (6, 0, 0), "chest": (6, 0, 0), "head": (16, 0, 0),
        "l_arm": (30, 10, 0), "r_arm": (30, 10, 0), "l_forearm": 62, "r_forearm": 62,
        "l_hand": (-22, 0), "r_hand": (-22, 0), "l_twist": 80, "r_twist": 80,
        "l_fingers": 0.15, "r_fingers": 0.15, "l_thigh": (0, 4, 0), "r_thigh": (0, 4, 0),
    },
    "KNEELING": {
        "spine": (10, 0, 0), "chest": (6, 0, 0), "head": (6, 0, 0),
        "r_thigh": (-2, 3, 0), "r_shin": 92, "r_foot": -50,
        "l_thigh": (88, 6, 0), "l_shin": 88, "l_foot": 0,
        "l_arm": (32, 6, 0), "l_forearm": 46, "r_arm": (18, 8, 0), "r_forearm": 30,
        "l_fingers": 0.4, "r_fingers": 0.5,
    },
    "OPERATOR": {
        "pelvis": (0, 2, 0), "spine": (4, 0, 0), "chest": (3, 0, 0), "head": (10, 0, -6),
        "r_arm": (40, 14, 0), "r_forearm": 70, "r_hand": (0, 0), "r_fingers": 0.85, "r_point": 1.0, "r_twist": 40,
        "l_arm": (4, 6, 0), "l_forearm": 14, "l_fingers": 0.4,
        "l_thigh": (0, 5, 0), "r_thigh": (3, 2, 0), "r_shin": 4,
    },
}


def _local(name: str, pose: dict) -> np.ndarray:
    """The bone's turn against its parent for a pose."""
    sd = -1.0 if name.startswith("r_") else 1.0
    v = pose.get(name)
    if name in ("pelvis", "spine", "chest", "neck", "head"):
        f, s, tw = v if v is not None else (0, 0, 0)
        return _rz(math.radians(tw)) @ _rx(math.radians(f)) @ _ry(math.radians(s))
    kind = name[2:]
    if kind in ("arm", "thigh"):
        f, o, tw = v if v is not None else (0, 0, 0)
        return _rz(math.radians(tw * sd)) @ _rx(math.radians(-f)) @ _ry(math.radians(-o * sd))
    if kind == "forearm":
        twist = pose.get(name[:2] + "twist", 0.0)
        return _rx(math.radians(-(v or 0.0))) @ _rz(math.radians(twist * sd))
    if kind == "shin":
        return _rx(math.radians(v or 0.0))
    if kind == "hand":
        b, s = v if v is not None else (0, 0)
        return _ry(math.radians(b * sd)) @ _rx(math.radians(s))
    if kind == "foot":
        return _rx(math.radians(-(v or 0.0)))
    return np.eye(3)


def skeleton(pose: str | dict = "STANDING") -> dict:
    """{bone: (head point, frame R, tail point)} for a pose (rest height 1.75 m, before the move to the floor)."""
    p = POSES[pose] if isinstance(pose, str) else pose
    out: dict = {}
    for name, (parent, at, vec) in BONES.items():
        at, vec = np.asarray(at, float), np.asarray(vec, float)
        if parent is None:
            head, Rp = at, np.eye(3)
        else:
            ph, Rp, _ = out[parent]
            head = ph + Rp @ at
        R = Rp @ _local(name, p)
        out[name] = (head, R, head + R @ vec)
    return out


class _Body:
    """Collects the person's shapes; ``n`` = points round a ring (detail)."""

    def __init__(self, sk: dict, lod: str):
        self.sk = sk
        self.detailed = lod == DETAILED
        self.n = 20 if self.detailed else 8
        self.shapes: list = []

    def bone_point(self, bone, t, dx=0.0, dy=0.0):
        head, R, tail = self.sk[bone]
        return head + (tail - head) * t + R @ np.array((dx, dy, 0.0))

    def limb(self, mat, bone, stations, n=None, caps=True, scale=1.0):
        """A loft along a bone: stations (t, rx, ry, dx, dy) in the bone's frame (x across, y front/back)."""
        head, R, tail = self.sk[bone]
        X, Y = R[:, 0], R[:, 1]
        rings = []
        for st in stations:
            t, rx, ry = st[:3]
            dx, dy = (st[3], st[4]) if len(st) > 3 else (0.0, 0.0)
            c = head + (tail - head) * t + X * dx + Y * dy
            rings.append(_ellipse(c, X, Y, rx * scale, ry * scale, n or self.n))
        self.shapes.append(_loft(mat, rings, caps=caps))

    def multi(self, mat, stations, n=None, scale=1.0, power=2.0, caps=True):
        """A loft through stations on several bones: (bone, t, rx, ry, dx, dy)."""
        rings = []
        for bone, t, rx, ry, dx, dy in stations:
            head, R, tail = self.sk[bone]
            c = head + (tail - head) * t + R[:, 0] * dx + R[:, 1] * dy
            rings.append(_ellipse(c, R[:, 0], R[:, 1], rx * scale, ry * scale, n or self.n, power))
        self.shapes.append(_loft(mat, rings, caps=caps))


# torso rings (bone, t, rx, ry, dx, dy): crotch to the base of the neck
_TORSO = (
    ("pelvis", -0.55, 0.12, 0.085, 0.0, 0.005),
    ("pelvis", -0.2, 0.165, 0.11, 0.0, 0.0),
    ("pelvis", 0.3, 0.172, 0.112, 0.0, 0.002),
    ("pelvis", 1.0, 0.158, 0.103, 0.0, 0.0),
    ("spine", 0.5, 0.148, 0.1, 0.0, -0.004),
    ("spine", 1.0, 0.158, 0.108, 0.0, -0.01),
    ("chest", 0.35, 0.172, 0.118, 0.0, -0.014),
    ("chest", 0.68, 0.185, 0.112, 0.0, -0.006),
    ("chest", 0.86, 0.178, 0.098, 0.0, 0.0),
    ("chest", 0.96, 0.148, 0.086, 0.0, 0.004),
    ("chest", 1.04, 0.09, 0.068, 0.0, 0.008),
    ("chest", 1.1, 0.058, 0.056, 0.0, 0.01),
)
_SPLIT = 4          # rings 0 … 4 = hips and belly (trousers), 4 … = chest (shirt)


def _skin_head(b: _Body, skin: str, hair: str, helmet: bool, helmet_mat: str):
    head, R, tail = b.sk["head"]
    X, Y, Z = R[:, 0], R[:, 1], R[:, 2]
    n = 24 if b.detailed else 10
    # (t along the head bone, half-width, half-depth, forward shift, power): jaw, face, skull
    st = ((0.0, 0.044, 0.05, -0.004, 2.0), (0.1, 0.057, 0.069, -0.012, 2.2), (0.26, 0.064, 0.082, -0.014, 2.3),
          (0.42, 0.072, 0.093, -0.008, 2.3), (0.58, 0.076, 0.098, -0.002, 2.2), (0.74, 0.073, 0.096, 0.004, 2.1),
          (0.87, 0.062, 0.083, 0.008, 2.0), (0.96, 0.04, 0.055, 0.01, 2.0), (1.0, 0.012, 0.016, 0.01, 2.0))
    rings = []
    for t, rx, ry, dy, pw in st:
        c = head + (tail - head) * t + Y * dy
        rings.append(_ellipse(c, X, Y, rx, ry, n, pw))
    b.shapes.append(_loft(skin, rings))
    b.limb(skin, "neck", ((-0.3, 0.054, 0.056), (0.5, 0.052, 0.055, 0.0, 0.006), (1.25, 0.048, 0.054, 0.0, 0.012)))

    def at(t, x, y):
        return head + (tail - head) * t + X * x + Y * y

    if b.detailed:
        nose = [_ellipse(at(t, 0.0, -0.1 - d), X, Z, w, h, 8) for t, d, w, h in
                ((0.52, -0.006, 0.008, 0.012), (0.44, 0.006, 0.009, 0.012), (0.35, 0.017, 0.011, 0.01),
                 (0.31, 0.013, 0.013, 0.006), (0.29, 0.0, 0.01, 0.003))]
        nose = [[p for p in r] for r in nose]
        b.shapes.append(_loft(skin, nose))
        for sd in (1, -1):
            b.shapes.append(ellipsoid("eye_dark", at(0.47, 0.031 * sd, -0.088), 0.012, 0.006, 0.0085, 10, R))
            b.shapes.append(ellipsoid(hair, at(0.535, 0.031 * sd, -0.088), 0.017, 0.005, 0.004, 8, R))
            b.shapes.append(ellipsoid(skin, at(0.44, 0.075 * sd, 0.008), 0.009, 0.019, 0.03, 10, R))
        b.shapes.append(ellipsoid("lips", at(0.2, 0.0, -0.092), 0.02, 0.006, 0.005, 10, R))
    if helmet:
        c = at(0.7, 0.0, 0.004)
        b.shapes.append(ellipsoid(helmet_mat, c, 0.106, 0.127, 0.124, n, R, lat_from=0.0))
        brim = [_ellipse(c + Z * dz, X, Y, rx, ry, n) for dz, rx, ry in
                ((0.004, 0.104, 0.125), (-0.002, 0.112, 0.133), (-0.006, 0.113, 0.134), (-0.003, 0.104, 0.124))]
        b.shapes.append(_loft(helmet_mat, brim, caps=False))
        peak = [_ellipse(c + Z * dz - Y * 0.12, X, Y, 0.075, ry, max(8, n // 2)) for dz, ry in
                ((0.0, 0.025), (-0.005, 0.03), (-0.008, 0.02))]
        b.shapes.append(_loft(helmet_mat, peak))
        if b.detailed:
            b.shapes.append(Tube(helmet_mat, _t(c + Z * 0.12 - Y * 0.08), _t(c + Z * 0.12 + Y * 0.08), 0.012, 8))
    else:
        tilt = R @ _rx(math.radians(-24))
        b.shapes.append(ellipsoid(hair, at(0.66, 0.0, 0.012), 0.079, 0.1, 0.108, n, tilt, lat_from=-10.0))


def _hand(b: _Body, sd: int, side: str, mat: str, curl: float, point: float):
    """A hand: the palm and, in detail, four fingers and a thumb that curl towards the palm."""
    head, R, tail = b.sk[f"{side}_hand"]
    X, Y, Z = R[:, 0], R[:, 1], -R[:, 2]          # Z: along the fingers; X points out of the back of the hand
    palm_len = 0.095
    if not b.detailed:
        b.limb(mat, f"{side}_hand", ((0.0, 0.016, 0.034), (0.5, 0.017, 0.045), (0.85, 0.014, 0.04),
                                     (1.0, 0.008, 0.022)), n=8)
        return
    b.limb(mat, f"{side}_hand", ((-0.05, 0.017, 0.028), (0.12, 0.018, 0.04), (0.35, 0.016, 0.047),
                                 (0.52, 0.0135, 0.046, 0.0, 0.0), (0.56, 0.008, 0.03)), n=12)
    base = head + Z * palm_len * 1.0
    lengths = (0.074, 0.082, 0.077, 0.061)
    for k, (dy, ln) in enumerate(zip((-0.03, -0.01, 0.01, 0.029), lengths)):
        c = point if k == 0 else 0.0
        bend = curl * (1.0 - c)
        pts = [base + Y * dy]
        d = Z.copy()
        for seg, share in enumerate((0.45, 0.32, 0.23)):
            ang = math.radians((60, 85, 60)[seg] * bend)
            # curl towards the palm (the palm faces -sd·X, i.e. towards the body when the arm hangs)
            d = d * math.cos(ang) - X * sd * math.sin(ang) if seg == 0 else _bend(d, X * sd, Y, ang)
            pts.append(pts[-1] + d * ln * share)
        rr = [0.0092, 0.0088, 0.008, 0.007]
        if k == 3:
            rr = [r * 0.88 for r in rr]
        b.shapes.append(sweep(mat, pts, 0.0, 6, True, rr))
    # thumb: from the palm's front edge, forward and down; it folds over the palm with the fingers
    tb = head + Z * 0.025 + Y * (-0.034) - X * sd * 0.008
    d = _unit(Z * 0.55 - Y * 0.75 - X * sd * 0.35)
    pts = [tb]
    for seg, share in enumerate((0.45, 0.33, 0.22)):
        ang = math.radians(40 * curl) if seg else math.radians(15 * curl)
        d = _bend(d, X * sd, Y, ang) if seg else d
        pts.append(pts[-1] + d * 0.075 * share * (1.35 if seg == 0 else 1.0))
    b.shapes.append(sweep(mat, pts, 0.0, 6, True, [0.011, 0.0105, 0.0095, 0.0085]))


def _unit(v):
    return v / (np.linalg.norm(v) or 1.0)


def _bend(d, towards, _axis, ang):
    """Turn direction ``d`` by ``ang`` towards ``-towards`` (the palm side)."""
    perp = -towards - d * float(np.dot(-towards, d))
    nrm = np.linalg.norm(perp)
    if nrm < 1e-9:
        return d
    perp = perp / nrm
    return _unit(d * math.cos(ang) + perp * math.sin(ang))


def _shoe(b: _Body, side: str, upper: str):
    head, R, _tail = b.sk[f"{side}_foot"]
    X, F, U = R[:, 0], -R[:, 1], R[:, 2]          # across, forward (toes), up
    n = 14 if b.detailed else 8
    # (s along the foot, half-width, sole level, top): heel to toe; the sole at -ANKLE_H
    st = ((-0.07, 0.03, -0.075, -0.035), (-0.06, 0.04, -0.082, 0.03), (-0.02, 0.045, -0.082, 0.07),
          (0.03, 0.048, -0.082, 0.035), (0.09, 0.05, -0.082, -0.005), (0.15, 0.05, -0.082, -0.03),
          (0.19, 0.044, -0.082, -0.04), (0.215, 0.03, -0.08, -0.05), (0.225, 0.012, -0.075, -0.06))
    rings = []
    for s, w, z0, z1 in st:
        c = head + F * s + U * ((z0 + z1) / 2)
        rings.append(_ellipse(c, X, U, w, (z1 - z0) / 2, n, 3.0))
    b.shapes.append(_loft(upper, rings))
    sole = []
    for s, w, *_ in st[1:-1]:
        c = head + F * s + U * (-ANKLE_H + 0.009)
        sole.append(_ellipse(c, X, U, w + 0.005, 0.009, n, 4.0))
    b.shapes.append(_loft("sole_rubber", sole))


def _outfit_mats(outfit: str):
    """(trousers/legs, chest and arms, gloves, helmet, shoes)."""
    return {"WORKSHOP": ("cloth_navy", "cloth_navy", "glove_grey", "helmet_yellow", "boots_black"),
            "OFFSHORE": ("cloth_orange", "cloth_orange", "glove_orange", "helmet_white", "boots_black"),
            "OFFICE": ("cloth_trousers", "cloth_shirt", "glove_grey", "helmet_white", "boots_brown")}[outfit]


def person(height: float = DEFAULT_HEIGHT, pose: str | dict = "STANDING", outfit: str = "WORKSHOP", helmet: bool = True,
           gloves: bool = False, look: int = 0, lod: str = DETAILED) -> list:
    """The person's shapes: posed, scaled to ``height`` (top of the head, without a helmet) and standing on z = 0.
    ``pose``: a ``POSES`` id or an angle dict as ``POSES`` holds them (task 0157: the rig's hand shapes)."""
    shapes, _sk, lift = _raw_person(pose, outfit, helmet, gloves, look, lod)
    k = float(height) / REST_HEIGHT
    return [_scaled(sh, k, lift) for sh in shapes]


def _raw_person(pose, outfit, helmet, gloves, look, lod):
    """(shapes before the move to the floor, skeleton, lift that puts the lowest point on z = 0)."""
    pose_d = pose if isinstance(pose, dict) else POSES.get(pose, POSES["STANDING"])   # task 0157: any angles
    if outfit not in OUTFITS:
        outfit = "WORKSHOP"
    skin, hair = LOOKS[int(look) % len(LOOKS)]
    legs, top, glove, helmet_mat, shoes = _outfit_mats(outfit)
    sk = skeleton(pose_d)
    b = _Body(sk, lod)
    # torso (two parts: trousers and shirt), the arms, the legs
    if outfit == "OFFICE":
        b.multi(legs, _TORSO[:_SPLIT + 1])
        b.multi(top, _TORSO[_SPLIT:])
        belt = [st for st in _TORSO[_SPLIT - 1:_SPLIT + 1]]
        b.multi("belt", [(bn, t, rx * 1.02, ry * 1.03, dx, dy) for bn, t, rx, ry, dx, dy in belt]
                if not b.detailed else [(belt[1][0], belt[1][1] - 0.08, belt[1][2] * 1.02, belt[1][3] * 1.04, 0, 0),
                                        (belt[1][0], belt[1][1] + 0.08, belt[1][2] * 1.02, belt[1][3] * 1.04, 0, 0)])
        # the high-visibility vest over the shirt: slightly bigger rings, open at the arms (it is over the chest)
        vest = [(bn, t, rx * 1.045, ry * 1.07, dx, dy) for bn, t, rx, ry, dx, dy in _TORSO[_SPLIT:-2]]
        b.multi("hivis_yellow", vest, caps=False)
        for t in (0.3, 0.62):
            bn = "chest"
            rx, ry = np.interp(t, (0.35, 0.68), (0.172, 0.19)), np.interp(t, (0.35, 0.68), (0.118, 0.112))
            b.multi("reflective", [(bn, t - 0.05, rx * 1.06, ry * 1.09, 0, -0.012), (bn, t + 0.05, rx * 1.06,
                                                                                    ry * 1.09, 0, -0.01)])
    else:
        b.multi(top, _TORSO)
        if b.detailed:      # a chest pocket and the collar
            b.shapes.append(rbox(top, 0, 0, 0, 0.09, 0.008, 0.1, 0.003, 2))
            chest_h, Rc, chest_t = sk["chest"]
            pocket = b.shapes.pop()
            pk = []
            c = chest_h + (chest_t - chest_h) * 0.42 + Rc @ np.array((0.07, -0.124, 0.0))
            for r in pocket.rings:
                pk.append([c + Rc @ np.array(p) for p in r])
            b.shapes.append(_loft(top + "_dark", pk))
        b.limb(top, "neck", ((-0.2, 0.074, 0.07, 0.0, 0.006), (0.3, 0.062, 0.062, 0.0, 0.008)), caps=False)
    if outfit == "OFFSHORE":
        for bn, t, rx, ry, dx, dy in (_TORSO[5], _TORSO[6]):
            b.multi("reflective", [(bn, t - 0.04, rx * 1.03, ry * 1.04, dx, dy), (bn, t + 0.04, rx * 1.03, ry * 1.04,
                                                                                dx, dy)])
    for sd, side in ((1, "l"), (-1, "r")):
        # shoulder and arm
        b.limb(top, f"{side}_arm", ((-0.1, 0.045, 0.05, -0.022 * sd, 0.0), (0.02, 0.06, 0.063),
                                    (0.25, 0.056, 0.058), (0.6, 0.048, 0.05), (1.0, 0.043, 0.045),
                                    (1.12, 0.03, 0.03)))
        cuff = 0.96 if not gloves else 1.0
        b.limb(top, f"{side}_forearm", ((-0.08, 0.041, 0.043), (0.25, 0.046, 0.044), (0.7, 0.036, 0.033),
                                        (cuff, 0.033, 0.03), (cuff + 0.02, 0.025, 0.022)))
        if not gloves:
            b.limb(skin, f"{side}_forearm", ((0.9, 0.028, 0.022), (1.03, 0.025, 0.02)), n=10)
        if outfit == "OFFSHORE":
            b.limb("reflective", f"{side}_arm", ((0.55, 0.0505, 0.0525), (0.68, 0.048, 0.05)), caps=False)
            b.limb("reflective", f"{side}_shin", ((0.3, 0.063, 0.066, 0.0, 0.008), (0.42, 0.06, 0.064, 0.0, 0.008)),
                   caps=False)
        _hand(b, sd, side, glove if gloves else skin, pose_d.get(f"{side}_fingers", 0.35),
              pose_d.get(f"{side}_point", 0.0))
        # leg: thigh, knee, shin
        b.limb(legs, f"{side}_thigh", ((-0.08, 0.085, 0.09, -0.01 * sd, 0.0), (0.05, 0.088, 0.092),
                                       (0.45, 0.075, 0.078), (0.85, 0.06, 0.062), (1.0, 0.057, 0.06),
                                       (1.1, 0.04, 0.04)))
        b.limb(legs, f"{side}_shin", ((-0.08, 0.056, 0.058), (0.05, 0.058, 0.06), (0.3, 0.06, 0.064, 0.0, 0.008),
                                      (0.7, 0.05, 0.052, 0.0, 0.004), (0.92, 0.047, 0.05), (0.97, 0.03, 0.03)))
        _shoe(b, side, shoes)
    _skin_head(b, skin, hair, helmet, helmet_mat)
    pts = np.array([p for sh in b.shapes for p in _points(sh)])
    return b.shapes, sk, -float(pts[:, 2].min())


def _points(sh):
    """Points that span a shape (a loft's own points; the two corners of any other shape's box)."""
    if isinstance(sh, Loft):
        return [p for r in sh.rings for p in r]
    if isinstance(sh, Tube):                    # the two end circles
        p0, p1 = np.asarray(sh.p0, float), np.asarray(sh.p1, float)
        frames = _frames_along([p0, p1])
        return [_t(c + (u * math.cos(a) + v * math.sin(a)) * sh.r) for c, (_d, u, v) in zip((p0, p1), frames)
                for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
    from .surroundings import footprint
    x0, x1, y0, y1, z0, z1 = footprint(sh)
    return [(x0, y0, z0), (x1, y1, z1)]


def _scaled(sh, k, lift):
    if isinstance(sh, Loft):
        return Loft(sh.mat, tuple(tuple((p[0] * k, p[1] * k, (p[2] + lift) * k) for p in r) for r in sh.rings),
                    sh.closed, sh.caps, sh.smooth)
    if isinstance(sh, Tube):
        f = (lambda p: (p[0] * k, p[1] * k, (p[2] + lift) * k))
        return Tube(sh.mat, f(sh.p0), f(sh.p1), sh.r * k, sh.seg)
    return sh


def feet_levels(height=DEFAULT_HEIGHT, pose="STANDING", outfit="WORKSHOP") -> dict:
    """For the tests: the lowest point of each sole and the front of each knee (metres above the floor) in a pose."""
    _shapes, sk, lift = _raw_person(pose, outfit, True, False, 0, LIGHT)
    k = float(height) / REST_HEIGHT
    out = {}
    for side in ("l", "r"):
        b = _Body(sk, LIGHT)
        _shoe(b, side, "x")
        sole = np.array(_points(b.shapes[1]))
        out[side + "_sole"] = (float(sole[:, 2].min()) + lift) * k
        b = _Body(sk, LIGHT)
        b.limb("x", f"{side}_shin", ((-0.08, 0.056, 0.058), (0.05, 0.058, 0.06)))
        out[side + "_knee"] = (float(np.array(_points(b.shapes[0]))[:, 2].min()) + lift) * k
    return out


# ---------------------------------------------------------------------------
# the other props: detailed versions (the light ones are the plain shapes of core/surroundings.py or a few boxes)
# ---------------------------------------------------------------------------


def _corrugated(mat, x0, x1, y_out, inward, z0, z1, pitch=0.278, depth=0.036):
    """A trapezoid-corrugated wall along x at y = ``y_out`` (``inward`` = +1/-1: which way the valleys go)."""
    line = []
    x = x0
    flat, slope = pitch * 0.26, pitch * 0.24
    while x < x1 - 1e-6:
        for dx, d in ((0.0, 0.0), (flat, 0.0), (flat + slope, depth), (2 * flat + slope, depth)):
            if x + dx <= x1:
                line.append((x + dx, y_out + inward * d))
        x += pitch
    line.append((x1, line[-1][1]))
    rings = [[(px, py, z) for px, py in line] for z in (z0, z1)]
    return _loft(mat, rings, closed=False, caps=False, smooth=False)


def container_detailed(colour: str = "prop_container_blue") -> list:
    """20 ft ISO container, doors at +x: corrugated sides, corner castings, door bars, handles and hinges."""
    from .surroundings import CONTAINER_SIZE
    L, W, H = CONTAINER_SIZE
    f, fr = 0.16, "container_frame"
    s: list = [Box(colour, 0.0, 0.0, 0.05, L - 0.12, W - 0.11, H - 0.1)]          # the inside, closed
    for sy in (1, -1):
        s.append(_corrugated(colour, -L / 2 + f, L / 2 - f, sy * (W / 2 - 0.006), -sy, 0.16, H - 0.11))
    for x in (-L / 2 + f / 2, L / 2 - f / 2):                                       # corner posts
        for y in (-W / 2 + f / 2, W / 2 - f / 2):
            s.append(rbox(fr, x, y, 0.118, f * 0.9, f * 0.9, H - 0.236, 0.008, 1))
    for z in (0.0, H - 0.118):                                                      # corner castings
        for x in (-L / 2 + 0.089, L / 2 - 0.089):
            for y in (-W / 2 + 0.081, W / 2 - 0.081):
                s.append(rbox(fr, x, y, z, 0.178, 0.162, 0.118, 0.006, 1))
                s.append(Box("casting_hole", x, y + (0.081 if y > 0 else -0.081), z + 0.035, 0.1, 0.004, 0.05))
    for y in (-W / 2 + 0.06, W / 2 - 0.06):                                         # bottom and top side rails
        s.append(Box(fr, 0.0, y, 0.0, L - 0.36, 0.12, 0.16))
        s.append(Box(fr, 0.0, y, H - 0.11, L - 0.36, 0.12, 0.11))
        for x in (-0.9, 0.9):                                                       # fork pockets
            s.append(Box("casting_hole", x, y + (0.061 if y > 0 else -0.061), 0.02, 0.36, 0.004, 0.11))
    s.append(Box(colour, 0.0, 0.0, H - 0.04, L - 0.36, W - 0.2, 0.04))              # roof
    s.append(Box(colour, -L / 2 + 0.03, 0.0, 0.16, 0.05, W - 0.32, H - 0.27))       # front wall
    for z in (0.0, H - 0.12):                                                       # end rails
        s.append(Box(fr, -L / 2 + 0.06, 0.0, z, 0.12, W - 0.32, 0.12))
        s.append(Box(fr, L / 2 - 0.08, 0.0, z, 0.16, W - 0.32, 0.12))
    # doors: two leaves with three ribs each, four locking bars with cams, handles and hinges
    xd = L / 2 - 0.02
    for side in (1, -1):
        yc = side * (W / 2 - 0.16) / 2
        s.append(Box(colour, xd, yc, 0.13, 0.03, (W - 0.33) / 2 - 0.01, H - 0.26))
        for z in (0.55, 1.25, 1.95):
            s.append(Box(colour, xd + 0.02, yc, z, 0.03, (W - 0.33) / 2 - 0.06, 0.12))
        for k in range(4):
            s.append(Box(fr, xd + 0.015, side * (W / 2 - 0.09), 0.35 + k * 0.6, 0.04, 0.07, 0.1))
        for y in (yc - side * 0.3, yc + side * 0.15):
            s.append(Tube("galvanized", (xd + 0.055, y, 0.1), (xd + 0.055, y, H - 0.1), 0.021, 10))
            for z in (0.12, H - 0.16):
                s.append(Box("galvanized", xd + 0.04, y, z, 0.07, 0.09, 0.04))
            s.append(Box("galvanized", xd + 0.085, y + side * 0.12, 1.08, 0.03, 0.26, 0.03))
            s.append(Box("galvanized", xd + 0.06, y, 1.07, 0.06, 0.06, 0.06))
    s.append(Box("plate_grey", xd + 0.04, 0.4, 1.55, 0.004, 0.2, 0.12))             # data plate (no text)
    return s


def pallet_detailed(seed: int = 7) -> list:
    """Euro-size pallet 1,200 x 800 x 144 mm with two layers of taped boxes (boards and blocks with chamfers)."""
    s: list = []
    b = 0.003
    for y, w in ((-0.3275, 0.145), (0.0, 0.145), (0.3275, 0.145)):             # bottom boards
        s.append(rbox("wood_2", 0.0, y, 0.0, 1.2, w, 0.022, b, 1))
    for y in (-0.3275, 0.0, 0.3275):                                             # blocks
        for x in (-0.5275, 0.0, 0.5275):
            s.append(rbox("wood_block", x, y, 0.022, 0.145 if x == 0.0 else 0.145, 0.1 if y else 0.145, 0.078, b, 1))
    for x in (-0.5275, 0.0, 0.5275):                                             # stringer boards
        s.append(rbox("wood", x, 0.0, 0.1, 0.145, 0.8, 0.022, b, 1))
    for i, x in enumerate((-0.5275, -0.26, 0.0, 0.26, 0.5275)):                  # top boards
        s.append(rbox("wood_2" if i % 2 else "wood", x, 0.0, 0.122, 0.145 if i in (0, 2, 4) else 0.1, 0.8, 0.022, b,
                      1))
    z = 0.144
    for layer in range(2):
        h = 0.36
        for x in (-0.3, 0.3):
            for y in (-0.2, 0.2):
                s.append(rbox("cardboard", x, y, z, 0.585, 0.39, h - 0.003, 0.006, 1))
                s.append(Box("tape", x, y, z + h - 0.003, 0.585, 0.05, 0.0015))
        z += h
    return s


def barrier_detailed() -> list:
    """2 m steel safety barrier: a bent tube frame on two feet, a mid rail and a red and white panel."""
    s: list = []
    for x in (-0.95, 0.95):
        s.append(rbox("barrier_foot", x, 0.0, 0.0, 0.09, 0.62, 0.045, 0.01, 2))
        s.append(rbox("rubber", x, 0.27, 0.0, 0.1, 0.06, 0.012, 0.004, 1))
        s.append(rbox("rubber", x, -0.27, 0.0, 0.1, 0.06, 0.012, 0.004, 1))
    path = rounded_path([(-0.95, 0.0, 0.045), (-0.95, 0.0, 1.0), (0.95, 0.0, 1.0), (0.95, 0.0, 0.045)], 0.09, 6)
    s.append(sweep("barrier_frame", path, 0.024, 12, True))
    s.append(Tube("barrier_frame", (-0.95, 0.0, 0.22), (0.95, 0.0, 0.22), 0.02, 12))
    s.append(Box("barrier", 0.0, 0.0, 0.3, 1.82, 0.012, 0.58))
    s.append(Box("barrier_frame", 0.0, 0.0, 0.29, 1.84, 0.016, 0.02))
    s.append(Box("barrier_frame", 0.0, 0.0, 0.87, 1.84, 0.016, 0.02))
    for x in (-0.6, 0.6):
        s.append(Box("reflective", x, -0.008, 0.78, 0.12, 0.004, 0.05))
    return s


def ibc_detailed() -> list:
    """1,000 l IBC tank: steel pallet base, white tank with rounded edges, galvanised cage, filler cap and valve."""
    s: list = []
    L, W = 1.2, 1.0
    for y in (-0.44, 0.0, 0.44):                                          # base: three skids and a deck
        s.append(Box("galvanized", 0.0, y, 0.0, L, 0.1, 0.11))
    s.append(Box("galvanized", 0.0, 0.0, 0.11, L, W, 0.03))
    s.append(rbox("ibc_tank", 0.0, 0.0, 0.145, 1.14, 0.95, 0.96, 0.07, 4))
    s.append(Tube("ibc_cap", (0.0, 0.0, 1.1), (0.0, 0.0, 1.135), 0.08, 20))
    s.append(Tube("ibc_cap", (0.0, 0.0, 1.135), (0.0, 0.0, 1.145), 0.06, 20))
    s.append(Tube("ibc_cap", (0.3, 0.2, 1.1), (0.3, 0.2, 1.125), 0.03, 12))
    # the valve at the front (-y), low
    s.append(Tube("ibc_valve", (0.0, -0.47, 0.22), (0.0, -0.56, 0.22), 0.045, 14))
    s.append(Tube("ibc_valve", (0.0, -0.56, 0.22), (0.0, -0.6, 0.22), 0.035, 14))
    s.append(Box("ibc_valve", 0.0, -0.53, 0.26, 0.14, 0.03, 0.02))
    s.append(Box("tank_label", -0.3, -0.477, 0.55, 0.3, 0.002, 0.2))
    # the cage: vertical and horizontal tubes, a frame on top
    r = 0.009
    top = 1.16
    for sy in (1, -1):
        y = sy * 0.49
        for k in range(7):
            x = -0.57 + k * 0.19
            s.append(Tube("galvanized", (x, y, 0.14), (x, y, top), r, 8))
    for sx in (1, -1):
        x = sx * 0.59
        for k in range(6):
            y = -0.47 + k * 0.188
            s.append(Tube("galvanized", (x, y, 0.14), (x, y, top), r, 8))
    for k in range(5):
        z = 0.32 + k * 0.2
        ring = [(-0.59, -0.49, z), (0.59, -0.49, z), (0.59, 0.49, z), (-0.59, 0.49, z), (-0.59, -0.49, z)]
        s.append(sweep("galvanized", rounded_path(ring, 0.03, 3), r, 8, False))
    for x in (-0.38, 0.0, 0.38):
        s.append(Tube("galvanized", (x, -0.49, top), (x, 0.49, top), r * 1.3, 8))
    ring = [(-0.59, -0.49, top), (0.59, -0.49, top), (0.59, 0.49, top), (-0.59, 0.49, top), (-0.59, -0.49, top)]
    s.append(sweep("galvanized", rounded_path(ring, 0.03, 3), r * 1.4, 8, False))
    return s


GAS_SHOULDERS = ("shoulder_white", "shoulder_green", "shoulder_maroon", "shoulder_black")   # EN 1089-3 colour code


def _bottle(x, y, shoulder) -> list:
    r, h = 0.115, 1.45
    prof = [(0.0, 0.0), (0.02, r * 0.85), (0.04, r), (h - 0.25, r), (h - 0.16, r * 0.82), (h - 0.1, r * 0.45),
            (h - 0.07, 0.03)]
    rings_body, rings_top = [], []
    for z, rr in prof:
        ring = _ellipse(np.array((x, y, z)), np.array((1.0, 0, 0)), np.array((0, 1.0, 0)), rr, rr, 16)
        (rings_top if z > h - 0.25 + 1e-9 else rings_body).append(ring)
    rings_top.insert(0, rings_body[-1])
    out = [_loft("bottle_grey", rings_body), _loft(shoulder, rings_top)]
    out.append(Tube("brass", (x, y, h - 0.07), (x, y, h - 0.02), 0.022, 10))
    out.append(Tube("galvanized", (x, y, h - 0.04), (x, y, h + 0.06), 0.045, 14))      # valve guard cap
    out.append(Box("tank_label", x, y - r - 0.001, 0.9, 0.08, 0.002, 0.12))
    return out


def gas_rack_detailed() -> list:
    """Galvanised rack with four gas bottles (shoulders coloured by gas), a chain across and two feet plates."""
    s: list = []
    w, d, h = 1.08, 0.36, 1.25
    for x in (-w / 2, w / 2):
        s.append(Box("galvanized", x, 0.0, 0.0, 0.05, d + 0.1, 0.008))
        for y in (-d / 2, d / 2):
            s.append(Box("galvanized", x, y, 0.0, 0.04, 0.04, h))
    for z in (0.02, 0.5, h - 0.04):
        s.append(Box("galvanized", 0.0, d / 2, z, w, 0.04, 0.04))
        s.append(Box("galvanized", -w / 2, 0.0, z, 0.04, d, 0.04))
        s.append(Box("galvanized", w / 2, 0.0, z, 0.04, d, 0.04))
    s.append(Box("galvanized", 0.0, 0.0, 0.0, w, d, 0.02))
    for i, sh in enumerate(GAS_SHOULDERS):
        s += _bottle(-0.39 + i * 0.26, 0.0, sh)
    chain = [(-w / 2, -d / 2, 1.0)] + [(-w / 2 + w * k / 12, -d / 2 - 0.13 - 0.03 * math.sin(math.pi * k / 12), 1.0 -
                                        0.04 * math.sin(math.pi * k / 12)) for k in range(1, 12)] + [(w / 2, -d / 2,
                                                                                                    1.0)]
    s.append(sweep("galvanized", chain, 0.006, 6, True))
    s.append(Box("warning_yellow", 0.0, d / 2 + 0.022, 0.9, 0.2, 0.004, 0.2, rot=0.0))
    return s


def tool_trolley_detailed() -> list:
    """Workshop tool trolley: a cabinet with six drawers and handles, a rubber top mat, a push handle, four castors."""
    s: list = []
    w, d, h0, hc = 0.68, 0.46, 0.13, 0.82
    s.append(rbox("trolley_red", 0.0, 0.0, h0, w, d, hc, 0.012, 2))
    s.append(rbox("rubber", 0.0, 0.0, h0 + hc, w - 0.02, d - 0.02, 0.012, 0.004, 1))
    heights = (0.075, 0.075, 0.1, 0.1, 0.15, 0.2)
    z = h0 + hc - 0.04
    for dh in heights:
        z -= dh
        s.append(rbox("trolley_grey", 0.0, -d / 2 - 0.004, z + 0.004, w - 0.06, 0.012, dh - 0.008, 0.003, 1))
        s.append(Tube("aluminium", (-0.2, -d / 2 - 0.03, z + dh - 0.025), (0.2, -d / 2 - 0.03, z + dh - 0.025), 0.007,
                      8))
        for x in (-0.2, 0.2):
            s.append(Box("aluminium", x, -d / 2 - 0.018, z + dh - 0.032, 0.012, 0.025, 0.014))
    s.append(Tube("aluminium", (0.0, -d / 2 - 0.006, h0 + hc - 0.025), (0.0, -d / 2 - 0.016, h0 + hc - 0.025), 0.009,
                  12))
    handle = rounded_path([(w / 2, -0.15, h0 + hc - 0.1), (w / 2 + 0.08, -0.15, h0 + hc - 0.1),
                           (w / 2 + 0.08, 0.15, h0 + hc - 0.1), (w / 2, 0.15, h0 + hc - 0.1)], 0.03, 4)
    s.append(sweep("aluminium", handle, 0.012, 10, True))
    for x in (-w / 2 + 0.07, w / 2 - 0.07):
        for y in (-d / 2 + 0.07, d / 2 - 0.07):
            s.append(Box("galvanized", x, y, h0 - 0.02, 0.07, 0.07, 0.02))
            s.append(Box("galvanized", x, y, 0.05, 0.05, 0.012, h0 - 0.07))
            s.append(Tube("rubber", (x - 0.022, y, 0.05), (x + 0.022, y, 0.05), 0.05, 16))
            s.append(Tube("trolley_grey", (x - 0.024, y, 0.05), (x + 0.024, y, 0.05), 0.02, 10))
    return s


# light versions of the new props (far away, many copies)
def ibc_light() -> list:
    return [Box("galvanized", 0.0, 0.0, 0.0, 1.2, 1.0, 0.14), Box("ibc_tank", 0.0, 0.0, 0.14, 1.14, 0.95, 0.97),
            Box("galvanized", 0.0, 0.0, 1.13, 1.2, 1.0, 0.03), Tube("ibc_valve", (0, -0.47, 0.22), (0, -0.6, 0.22), 0.045, 8)]


def gas_rack_light() -> list:
    s = [Box("galvanized", 0.0, 0.0, 0.0, 1.08, 0.36, 0.02), Box("galvanized", 0.0, 0.18, 0.0, 1.08, 0.04, 1.25),
         Box("galvanized", -0.54, 0.0, 0.0, 0.05, 0.46, 0.008), Box("galvanized", 0.54, 0.0, 0.0, 0.05, 0.46, 0.008),
         Tube("galvanized", (-0.54, -0.3, 0.98), (0.54, -0.3, 0.98), 0.008, 4)]
    for i, sh in enumerate(GAS_SHOULDERS):
        x = -0.39 + i * 0.26
        s.append(Tube("bottle_grey", (x, 0, 0.0), (x, 0, 1.2), 0.115, 8))
        s.append(Tube(sh, (x, 0, 1.2), (x, 0, 1.43), 0.08, 8))
        s.append(Tube("galvanized", (x, 0, 1.41), (x, 0, 1.51), 0.045, 8))
    return s


def tool_trolley_light() -> list:
    s = [Box("trolley_red", 0.0, 0.0, 0.13, 0.68, 0.46, 0.82), Box("rubber", 0.0, 0.0, 0.95, 0.66, 0.44, 0.012)]
    for x in (-0.27, 0.27):
        for y in (-0.16, 0.16):
            s.append(Tube("rubber", (x - 0.02, y, 0.05), (x + 0.02, y, 0.05), 0.05, 8))
            s.append(Box("galvanized", x, y, 0.1, 0.05, 0.05, 0.03))
    s.append(Box("aluminium", 0.42, 0.0, 0.83, 0.03, 0.3, 0.03))
    return s


# ---------------------------------------------------------------------------
# one entry point
# ---------------------------------------------------------------------------

PERSON_DEFAULTS = dict(height=DEFAULT_HEIGHT, pose="STANDING", outfit="WORKSHOP", helmet=True, gloves=False, look=0)


def model(kind: str, lod: str = DETAILED, **person_settings) -> list:
    """The shapes of a prop (the person takes its settings: height, pose, outfit, helmet, gloves, look)."""
    from . import surroundings as S
    if kind == "PERSON":
        opts = dict(PERSON_DEFAULTS)
        opts.update({k: v for k, v in person_settings.items() if k in PERSON_DEFAULTS})
        return person(lod=lod, **opts)
    detailed = lod == DETAILED
    if kind == "CONTAINER":
        return container_detailed() if detailed else S.recolor(S.container(), {"container_blue": "prop_container_blue"})
    if kind == "PALLET":
        return pallet_detailed() if detailed else S.pallet_load(__import__("random").Random(7), 0.86)
    if kind == "BARRIER":
        return barrier_detailed() if detailed else S.barrier()
    if kind == "IBC":
        return ibc_detailed() if detailed else ibc_light()
    if kind == "GAS_RACK":
        return gas_rack_detailed() if detailed else gas_rack_light()
    if kind == "TOOL_TROLLEY":
        return tool_trolley_detailed() if detailed else tool_trolley_light()
    raise KeyError(kind)
