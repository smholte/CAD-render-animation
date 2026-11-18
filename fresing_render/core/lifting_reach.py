"""Hook to here and the crane's readout (task 0201, Lifting lane L4; the general solver: task 0203) – plain Python.

A placed crane is rigged from its equipment file (``rig``: joints in the model frame, mm and degrees, as the render-kit
sheet writes them; ``limits``; ``charts``). This module

* gives every joint its **role** (``role_of``: the joint's ``"role"``, else its name – the built-ins have none):
  slew, luff, telescope, jib, knuckle, extension, hoist, swing, outrigger, jack, track, travel,
* works out where the hook is for joint values (``Kinematics``: the app's joint rules – a joint that ``rides_on``
  another moves with it, a follower takes ``ratio`` x its leader – the same as ``lifting_model/classes.hook_point``;
  ``Kinematics.transforms`` does it for many joint values at once, NumPy arrays of 3 x 3 turns and moves),
* finds joint values that put the hook on a point (``hook_to``) on **any** crane rigged with these roles: the boom's
  plane is measured from the 3-D kinematics (the luff joint's axis, wherever the crane is drawn: turned about up, up
  along Y, the boom beside the slew axis), the reach joints solved in that plane – luff and telescope / extension, a
  luffing jib with the main boom at its charts' angle, or main boom + knuckle (+ extensions) with the shortest hoist
  rope – and every answer polished and checked by the 3-D kinematics: the hook within 1 mm of the point, every joint
  inside its limits, else refused. Among several answers the one with the lowest crane use on the chart that applies,
  then the shortest boom. Out of reach: by how much (radius or height),
* picks the chart for the crane's set-up (``chart_for``): only combinations the file has; an in-between counterweight
  or outrigger spread takes the next safer chart (less counterweight, narrower spread) and says why,
* gives the live readout (``readout``): radius, hook height, boom length and angle, the chart row (next longer
  radius), capacity, gross load, crane use with the status word (``lifting.crane_use``).

Hook to here needs a driven slew joint (turning about the up axis), a luff joint (turning about a level axis) riding
on it and a hoist joint (sliding the hook down) riding on those; the hook hangs plumb (swing joints that follow the
boom's turns with ratio -1). Units inside: mm and degrees (the rig's), kg for masses; the readout gives metres and kg.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from . import lifting

ROLE_KEYS = ("slew", "luff", "telescope", "jib", "knuckle", "extension", "hoist", "swing", "outrigger", "jack",
             "track", "travel")
ROLE_WORDS = {"slew": "slew", "luff": "luff (main boom)", "telescope": "telescope", "jib": "jib",
              "knuckle": "knuckle", "extension": "extension", "hoist": "hoist", "swing": "hook swing",
              "outrigger": "outrigger", "jack": "jack", "track": "track", "travel": "travel"}
# a joint without a "role" gets it from its name (the built-in cranes' names)
_ROLE_NAMES = (
    ("swing", r"hook\s*swing\b"),
    ("slew", r"slew"),
    ("luff", r"(luff|main\s*boom)\b"),
    ("telescope", r"telescop"),
    ("jib", r"((luffing|fly)\s+)?jib\b"),
    ("knuckle", r"knuckle\b"),
    ("extension", r"extension"),
    ("hoist", r"hoist\b"),
    ("outrigger", r"(outrigger|stabili[sz]er)"),
    ("jack", r"(jacks?|legs?)\b"),
    ("track", r"tracks?\b"),
    ("travel", r"travel\b"),
)
_ROLE_RE = tuple((r, re.compile(p, re.I)) for r, p in _ROLE_NAMES)

NEEDED = ("slew", "luff", "hoist")
UP_AXES = {"Z": (0.0, 0.0, 1.0), "Y": (0.0, 1.0, 0.0)}
CRANE_KINDS = ("mobile_crane", "crawler_crane", "knuckle_boom_crane", "other_crane")
TOL = 1e-6           # degrees / mm: limits are met within this
HOIST_TOL = 0.01     # mm: a hoist value this far past its limit counts as at the limit (the solve's own rounding)
JIB_ANGLE_TOL = 0.5  # degrees: a luffing jib's charts hold with the main boom this close to their boom angle
CHECK_MM = 1.0       # the 3-D kinematics must put the hook this close to the target, else the answer is refused
SLEW_UP = 1e-6       # 1 - |cos|: the slew axis this close to the up axis (0.08°)
LEVEL = 1e-3         # |sin|: a luff axis this close to level, a knuckle / jib axis this close to the luff's (0.06°)
PLANE_MM = 1.0       # mm: the hook leaves the boom's plane by no more than this as the telescope runs
LINE_MM = 0.01       # mm: the telescope moves the boom head along a straight line within this
GRID_E = 61          # telescope / extension values tried
GRID_HOIST = 401     # hoist values tried for a knuckle-boom crane (the lowest rope that reaches)


class ReachError(ValueError):
    """The crane's file cannot be used by Hook to here (the message says why, in plain words). ``step``: the set-up
    step that can mend it (a role key, "hook_block", …) or None."""

    def __init__(self, message: str, step: str | None = None):
        super().__init__(message)
        self.step = step


def role_of(joint: dict) -> str | None:
    """A joint's role: its ``"role"`` (one of ``ROLE_KEYS``), else from its name; None when neither says."""
    if not isinstance(joint, dict):
        return None
    r = joint.get("role")
    if isinstance(r, str) and r.strip():
        r = r.strip().lower()
        return r if r in ROLE_KEYS else None
    name = joint.get("name")
    if not isinstance(name, str):
        return None
    name = name.strip()
    for role, rx in _ROLE_RE:
        if rx.match(name):
            return role
    return None


# ---------------------------------------------------------------------------------------------------------------------
# kinematics (mm, degrees)

def _r2(v, psi):
    c, s = np.cos(psi), np.sin(psi)
    v = np.asarray(v, float)
    return np.stack([v[..., 0] * c - v[..., 1] * s, v[..., 0] * s + v[..., 1] * c], axis=-1)


def _wrap_into(deg: float, lim, near: float | None = None) -> float | None:
    """``deg`` + k x 360 inside ``lim`` (the one nearest ``near``), or None."""
    lo, hi = lim
    best = None
    for k in range(-3, 4):
        v = deg + 360.0 * k
        if lo - TOL <= v <= hi + TOL:
            if best is None or abs(v - (near if near is not None else 0.0)) < abs(best - (near or 0.0)):
                best = v
    return None if best is None else min(max(best, lo), hi)


_KS = 360.0 * np.arange(-3, 4)


def _wrap_v(deg, lim):
    """``_wrap_into`` for arrays (nearest 0): NaN where no turn fits."""
    deg = np.asarray(deg, float)
    lo, hi = lim
    if hi - lo < 360.0 - 2 * TOL and -1080.0 < lo and hi < 1080.0:   # one turn fits (or two, at the range's ends)
        v1 = lo + np.mod(deg - lo, 360.0)                  # in [lo, lo + 360)
        v0 = v1 - 360.0
        in1 = v1 <= hi + TOL
        in0 = v0 >= lo - TOL
        pick0 = in0 & (~in1 | (np.abs(v0) < np.abs(v1)))
        best = np.where(pick0, v0, v1)
        return np.where(in1 | in0, np.clip(best, lo, hi), np.nan)
    v = deg[..., None] + _KS
    inside = (v >= lo - TOL) & (v <= hi + TOL)
    d = np.where(inside, np.abs(v), np.inf)
    k = np.argmin(d, axis=-1)
    best = np.take_along_axis(v, k[..., None], axis=-1)[..., 0]
    return np.where(inside.any(axis=-1), np.clip(best, lo, hi), np.nan)


def _vec3(v):
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        return None
    try:
        a = np.array([float(x) for x in v])
    except (TypeError, ValueError):
        return None
    return a if np.all(np.isfinite(a)) else None


def _number(x) -> bool:
    """A real, finite number (a hand-edited file can hold words or nothing where a number belongs)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _positive(x):
    return float(x) if _number(x) and x > 0 else None


def _pair(x):
    """[lo, hi] as two numbers, else None."""
    if isinstance(x, (list, tuple)) and len(x) == 2 and _number(x[0]) and _number(x[1]):
        return float(x[0]), float(x[1])
    return None


class Kinematics:
    """A crane's joint chain from its equipment file (``data``: the whole file as read, ``rig`` inside) – the joints
    only, no roles. ``by``: name -> the joint's dict; values are degrees (ROTATE) and mm (SLIDE), 0 in the CAD pose."""

    def __init__(self, data: dict):
        if not isinstance(data, dict):
            raise ReachError("The crane's file cannot be read (it is not a table).")
        self.data = data
        rig = data.get("rig") or {}
        if not isinstance(rig, dict):
            raise ReachError("The crane's file has no rig (rig > joints).")
        self.rig_data = rig
        up = str(rig.get("up_axis") or "Z").strip().upper().lstrip("+")
        if up not in UP_AXES:
            raise ReachError(f"The rig's up axis '{rig.get('up_axis')}' is neither Z nor Y.")
        self.up_axis = up
        self.up = np.array(UP_AXES[up], float)
        joints = rig.get("joints") or []
        if not isinstance(joints, list):
            raise ReachError("The rig's joints must be a list.")
        self.joints = []
        self.by = {}
        self._p, self._d, self._K = {}, {}, {}
        for i, j in enumerate(joints):
            if not isinstance(j, dict) or not isinstance(j.get("name"), str) or not j["name"].strip():
                raise ReachError(f"Joint {i + 1} in the crane's file has no name.")
            n = j["name"]
            if n in self.by:
                raise ReachError(f"Two joints are named '{n}': every joint needs a name of its own.", role_of(j))
            if j.get("kind") not in ("ROTATE", "SLIDE"):
                raise ReachError(f"The joint '{n}' is neither a turning (ROTATE) nor a sliding (SLIDE) joint.",
                                 role_of(j))
            p, d = _vec3(j.get("point")), _vec3(j.get("direction"))
            if p is None or d is None or np.linalg.norm(d) < 1e-12:
                raise ReachError(f"The joint '{n}' has no axis (a point and a direction).", role_of(j))
            lim = j.get("limits")
            if lim is not None:
                ok = isinstance(lim, (list, tuple)) and len(lim) == 2
                try:
                    ok = ok and math.isfinite(float(lim[0])) and math.isfinite(float(lim[1])) \
                        and float(lim[0]) <= float(lim[1])
                except (TypeError, ValueError):
                    ok = False
                if not ok:
                    raise ReachError(f"The joint '{n}' has limits that are not two numbers, lowest first.", role_of(j))
            self.joints.append(j)
            self.by[n] = j
            a = d / np.linalg.norm(d)
            self._p[n], self._d[n] = p, a
            K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
            self._K[n] = (K, K @ K)
        for j in self.joints:
            n = j["name"]
            for key, word in (("rides_on", "rides on"), ("follows", "follows")):
                o = j.get(key)
                if o and o not in self.by:
                    raise ReachError(f"The joint '{n}' {word} '{o}', which is not in the file.", role_of(j))
                if o == n:
                    raise ReachError(f"The joint '{n}' {word} itself.", role_of(j))
            if j.get("follows"):
                try:
                    r = float(j.get("ratio"))
                except (TypeError, ValueError):
                    r = float("nan")
                if not math.isfinite(r):
                    raise ReachError(f"The joint '{n}' follows '{j['follows']}' without a ratio.", role_of(j))
        for j in self.joints:
            for key in ("rides_on", "follows"):
                seen, m = set(), j["name"]
                while m:
                    if m in seen:
                        raise ReachError(f"The joints round '{j['name']}' ride on or follow each other in a circle.",
                                         role_of(j))
                    seen.add(m)
                    m = self.by[m].get(key)

    # -- joint values ---------------------------------------------------------------------------------------------
    def driven(self) -> list:
        """The joints a user drives (not followers)."""
        return [j for j in self.joints if not j.get("follows")]

    def leader_of(self, name: str) -> tuple[str, float]:
        """(the driven joint a joint's value comes from, the product of the ratios)."""
        r = 1.0
        while self.by[name].get("follows"):
            r *= float(self.by[name]["ratio"])
            name = self.by[name]["follows"]
        return name, r

    def value_of(self, name: str, given: dict):
        """A joint's value: a follower ``ratio`` x its leader's; values may be NumPy arrays (many poses at once)."""
        lead, r = self.leader_of(name)
        v = given.get(lead, 0.0)
        return r * (v if isinstance(v, np.ndarray) else float(v))

    def chain(self, name: str) -> list:
        """The joint and those it rides on, from the bottom up."""
        out = []
        while name:
            out.append(name)
            name = self.by[name].get("rides_on")
        return out[::-1]

    def limits(self, name: str):
        lim = self.by[name].get("limits")
        return (float(lim[0]), float(lim[1])) if lim else (-1e9, 1e9)

    def transforms(self, name: str | None, given: dict, after: str | None = None):
        """(R, t): the motion of what the joint moves, relative to the CAD pose (x' = R x + t, mm, model frame) – for
        many poses at once when values in ``given`` are arrays (R: (..., 3, 3), t: (..., 3)). ``after``: leave out that
        joint and those below it (the motion in its moving frame, e.g. the slew's base)."""
        names = self.chain(name) if name else []
        if after is not None and after in names:
            names = names[names.index(after) + 1:]
        R, t = None, None
        for nm in names:
            v = self.value_of(nm, given)
            if self.by[nm]["kind"] == "ROTATE":
                th = np.radians(v)
                s, c = np.sin(th), np.cos(th)
                K, K2 = self._K[nm]
                s = np.asarray(s)[..., None, None]
                c = np.asarray(c)[..., None, None]
                Rl = np.eye(3) + s * K + (1.0 - c) * K2
                p = self._p[nm]
                tl = p - Rl @ p
            else:
                Rl = None
                tl = np.asarray(v, float)[..., None] * self._d[nm]
            if R is None:
                R = Rl if Rl is not None else np.eye(3)
                t = tl
            else:
                t = t + (R @ tl[..., None])[..., 0]
                if Rl is not None:
                    R = R @ Rl
        if R is None:
            return np.eye(3), np.zeros(3)
        return R, t

    def motion(self, name: str, given: dict) -> np.ndarray:
        """4 x 4 world motion (mm, model frame) of what the joint moves, relative to the CAD pose."""
        R, t = self.transforms(name, {k: float(v) for k, v in given.items()} if given else {})
        M = np.eye(4)
        M[:3, :3] = R
        M[:3, 3] = t
        return M

    def moved(self, name: str | None, point, given: dict, after: str | None = None) -> np.ndarray:
        """A point carried by what ``name`` moves (``name`` None: it stays)."""
        R, t = self.transforms(name, given, after)
        return (R @ np.asarray(point, float)[..., None])[..., 0] + t

    def point(self, name: str, given: dict) -> np.ndarray:
        """A joint's axis point now (moved by what it rides on)."""
        return self.moved(self.by[name].get("rides_on"), self._p[name], given)

    def axis(self, name: str, given: dict, after: str | None = None) -> np.ndarray:
        """A joint's axis direction now (unit; turned by what it rides on)."""
        R, _t = self.transforms(self.by[name].get("rides_on"), given, after)
        return R @ self._d[name]


# ---------------------------------------------------------------------------------------------------------------------
# the boom's plane, measured from the 3-D kinematics

@dataclass
class Plane:
    """The boom in its plane, in the slew's base frame with the slew at 0 (mm): x along the boom's level direction,
    z up the slew axis, measured from the slew axis' point; the hook ``y`` beside the plane:

        sheave = P1 + R(s1 a1) [ (P2 - P1) + R(s2 a2) [ V0 + e w ] ],   hook (hoist 0) = sheave + h

    a1 = the luff value, a2 = the jib / knuckle value (P2 = P1 when there is none), e = the telescope / extension
    value. ``Vb0`` + e ``wb``: the boom's head for its length (a fly jib's foot; else the sheave)."""

    c: np.ndarray
    u: np.ndarray
    n: np.ndarray
    ex: np.ndarray
    e2: np.ndarray
    sz: float
    s1: float
    s2: float
    P1: np.ndarray
    P2: np.ndarray
    V0: np.ndarray
    w: np.ndarray
    Vb0: np.ndarray
    wb: np.ndarray
    h: np.ndarray
    y: float
    dz: float
    model_boom: float | None = None

    def sheave(self, a1, a2=0.0, e=0.0) -> np.ndarray:
        e = np.asarray(e, float)
        inner = _r2(self.V0 + e[..., None] * self.w, np.radians(self.s2 * np.asarray(a2, float)))
        v = _r2(self.P2 - self.P1 + inner, np.radians(self.s1 * np.asarray(a1, float)))
        return self.P1 + v

    def hook0(self, a1, a2=0.0, e=0.0) -> np.ndarray:
        return self.sheave(a1, a2, e) + self.h

    def boom_m(self, e):
        if self.model_boom:
            return np.full(np.shape(e), float(self.model_boom)) if np.ndim(e) else float(self.model_boom)
        e = np.asarray(e, float)
        out = np.round((np.linalg.norm(self.P2 - self.P1) + np.linalg.norm(self.Vb0 + e[..., None] * self.wb,
                                                                           axis=-1)) / 1000.0, 4)
        return out if out.ndim else float(out)   # 0.1 mm: no float noise past a chart's boom length

    def coords(self, p):
        d = np.asarray(p, float) - self.c
        return np.stack([d @ self.ex, d @ self.u], axis=-1)


class Rig(Kinematics):
    """A crane rigged for Hook to here: its joints with their roles (``role``: 'slew', 'luff', 'hoist' and, when the
    crane has them, 'second' – a luffing jib or a knuckle – and 'tele' – the telescope / extension leader). Any crane
    kind; refusals in plain words (``ReachError``)."""

    def __init__(self, data: dict):
        super().__init__(data)
        self.kind = str(data.get("kind", ""))
        if "crane" not in self.kind:
            raise ReachError(f"Hook to here works on cranes, not on '{self.kind or 'an item without a kind'}'.")
        rig = self.rig_data
        self.roles: dict = {}
        for j in self.joints:
            r = role_of(j)
            if r:
                self.roles.setdefault(r, []).append(j["name"])
        hook = rig.get("hook") or {}
        # the hoist (the hook's joint)
        hoists = [n for n in self.roles.get("hoist", []) if not self.by[n].get("follows")]
        if not hoists:
            raise ReachError("The crane's file has no hoist joint (named 'Hoist' or given the role 'hoist'): Hook to "
                             "here needs it.", "hoist")
        hj = hook.get("joint") if isinstance(hook, dict) else None
        hoist = hj if hj in hoists else hoists[0]
        if self.by[hoist]["kind"] != "SLIDE":
            raise ReachError(f"The hoist joint '{hoist}' must slide (it lowers the hook).", "hoist")
        chain_h = self.chain(hoist)
        self.role = {}

        def pick(role, above=None):
            names = [n for n in chain_h if role_of(self.by[n]) == role and not self.by[n].get("follows")]
            if above is not None:
                names = [n for n in names if chain_h.index(n) > chain_h.index(above)]
            return names[0] if names else None

        slew = pick("slew")
        if slew is None:
            if self.roles.get("slew"):
                raise ReachError(f"The hoist does not ride on the slew joint '{self.roles['slew'][0]}': set the "
                                 "hoist to ride on the boom, which rides on the slew.", "slew")
            raise ReachError("The crane's file has no slew joint (named 'Slew' or given the role 'slew'): Hook to "
                             "here needs it.", "slew")
        luff = pick("luff", slew)
        if luff is None:
            if self.roles.get("luff"):
                raise ReachError(f"The luff joint '{self.roles['luff'][0]}' does not ride on the slew joint, or the "
                                 "hoist does not ride on it.", "luff")
            raise ReachError("The crane's file has no luff joint (named 'Luff' or 'Main boom', or given the role "
                             "'luff'): Hook to here needs it.", "luff")
        for r, n in (("slew", slew), ("luff", luff)):
            if self.by[n]["kind"] != "ROTATE":
                raise ReachError(f"The {ROLE_WORDS[r]} joint '{n}' must turn (ROTATE).", r)
        self.role.update(slew=slew, luff=luff, hoist=hoist)
        tele = pick("telescope", luff) or pick("extension", luff)
        knuckle = pick("knuckle", luff)
        jib = pick("jib", luff)
        self.fly = None
        if knuckle is not None:
            self.mode = "knuckle"
            self.role["second"] = knuckle
        elif jib is not None and (self.kind == "crawler_crane"
                                  or (self.kind not in ("mobile_crane", "knuckle_boom_crane") and tele is None)):
            self.mode = "jib"
            self.role["second"] = jib
            tele = None
        else:
            self.mode = "luff"
            self.fly = jib
        if "second" in self.role and self.by[self.role["second"]]["kind"] != "ROTATE":
            r = role_of(self.by[self.role["second"]])
            raise ReachError(f"The {ROLE_WORDS[r]} joint '{self.role['second']}' must turn (ROTATE).", r)
        if tele is not None:
            if self.by[tele]["kind"] != "SLIDE":
                r = role_of(self.by[tele])
                raise ReachError(f"The {ROLE_WORDS[r]} joint '{tele}' must slide (SLIDE).", r)
            if not self.by[tele].get("limits"):
                r = role_of(self.by[tele])
                raise ReachError(f"The {ROLE_WORDS[r]} joint '{tele}' has no limits: Hook to here needs how far it "
                                 "runs out.", r)
            self.role["tele"] = tele
        if not isinstance(hook, dict) or _vec3(hook.get("point")) is None:
            raise ReachError("The crane's file does not say where the hook is (rig > hook > point).", "hook_block")
        self.hook_cad = _vec3(hook["point"])
        lim = data.get("limits") or {}
        self.limits_data = lim if isinstance(lim, dict) else {}
        lim = self.limits_data
        self.model_boom = _positive(lim.get("model_boom"))           # a hand-edited file: words count as none
        self.model_jib = _positive(lim.get("model_jib"))
        jba = lim.get("jib_charts_boom_angle")
        self.jib_boom_angle = float(jba) if self.mode == "jib" and _number(jba) else None
        self._planes: dict = {}
        self._hoist_hi = None
        pl = self.plane({})
        # how far the hook can go down when the hoist has no limits: past the ground by as far as the boom reaches
        reach = float(np.linalg.norm(pl.P2 - pl.P1) + np.linalg.norm(pl.V0))
        if "tele" in self.role:
            reach += float(np.linalg.norm(pl.w)) * max(abs(x) for x in self.limits(self.role["tele"]))
        self._hoist_hi = max(float(self.hook_cad @ self.up), 0.0) + 2.0 * reach + 3000.0
        # the boom's angle above level in the CAD pose (the file's limits say it; else the geometry)
        luffj = self.by[luff]
        ang = _pair(lim.get("boom_angle")) or _pair(lim.get("main_boom_angle"))
        if ang and luffj.get("limits"):
            self.th0 = float(ang[0]) - float(luffj["limits"][0])
        else:
            head = pl.P2 if "second" in self.role else pl.sheave(0.0)
            v = head - pl.P1
            self.th0 = math.degrees(math.atan2(v[1], v[0])) if np.linalg.norm(v) > 1e-9 else 0.0
        self.second_cad = 0.0
        if "second" in self.role:
            sj = self.by[self.role["second"]]
            rel = _pair(lim.get("jib_angle_to_boom")) or _pair(lim.get("knuckle_angle"))
            if rel and sj.get("limits"):
                self.second_cad = float(rel[0]) - float(sj["limits"][0])
            else:
                v1, v2 = pl.P2 - pl.P1, pl.V0
                self.second_cad = math.degrees(math.atan2(v2[1], v2[0]) - math.atan2(v1[1], v1[0]))
                self.second_cad = (self.second_cad + 180.0) % 360.0 - 180.0

    def solve_range(self, name: str):
        """The range Hook to here solves a joint in: its limits; without them a turning joint within one turn
        (-180 … 180°) and the hoist from 0 (the hook never above its sheave) to past the ground."""
        if self.by[name].get("limits"):
            return self.limits(name)
        if name == self.role.get("hoist"):
            return 0.0, float(self._hoist_hi or 1e6)
        if self.by[name]["kind"] == "ROTATE":
            return -180.0, 180.0
        return self.limits(name)

    # -- the plane --------------------------------------------------------------------------------------------------
    def _base_values(self, given: dict) -> dict:
        reach = set(self.role.values())
        return {k: v for k, v in given.items() if k not in reach}

    def plane(self, given: dict | None = None) -> Plane:
        """The boom's plane for the other joints' values (those not solved keep theirs), measured from the 3-D
        kinematics; ReachError when the boom does not move in one plane."""
        vals = self._base_values(dict(given or {}))
        slew = self.role["slew"]
        hoist = self.role["hoist"]
        chain_h = self.chain(hoist)
        above = chain_h[chain_h.index(slew) + 1:]
        key = tuple(round(float(self.value_of(n, vals)), 9) for n in above)
        got = self._planes.get(key)
        if got is None:
            if len(self._planes) > 64:
                self._planes.clear()
            got = self._make_plane(vals)
            self._planes[key] = got
        return got

    def _make_plane(self, vals: dict) -> Plane:
        R_ = self.role
        slew, luff, hoist = R_["slew"], R_["luff"], R_["hoist"]
        ds = self._d[slew]
        cos_up = float(ds @ self.up)
        if 1.0 - abs(cos_up) > SLEW_UP:
            raise ReachError(f"The slew joint '{slew}' does not turn about the up axis ({self.up_axis}): Hook to here "
                             "cannot work it out.", "slew")
        sz = 1.0 if cos_up > 0 else -1.0
        u = ds * sz
        c = self._p[slew]
        P1_3 = self.moved(self.by[luff].get("rides_on"), self._p[luff], vals, after=slew)
        n1 = self.axis(luff, vals, after=slew)
        if abs(float(n1 @ u)) > LEVEL:
            raise ReachError(f"The luff joint '{luff}' does not turn about a level axis: Hook to here cannot work it "
                             "out.", "luff")
        n = n1 - (n1 @ u) * u
        n = n / np.linalg.norm(n)
        ex = np.cross(u, n)
        S0_3 = self.moved(self.by[hoist].get("rides_on"), self._p[hoist], vals, after=slew)
        s1 = 1.0
        if float((S0_3 - P1_3) @ ex) < 0:
            ex, s1 = -ex, -1.0

        def co(p):
            d = np.asarray(p, float) - c
            return np.stack([d @ ex, d @ u], axis=-1)

        s2 = 1.0
        P2 = co(P1_3)
        if "second" in R_:
            sec = R_["second"]
            n2 = self.axis(sec, vals, after=slew)
            if np.linalg.norm(np.cross(n2, n)) > LEVEL:
                raise ReachError(f"The joint '{sec}' does not turn about an axis parallel to the luff joint's: Hook "
                                 "to here cannot work it out.", role_of(self.by[sec]))
            s2 = s1 * (1.0 if float(n2 @ n) > 0 else -1.0)
            P2_3 = self.moved(self.by[sec].get("rides_on"), self._p[sec], vals, after=slew)
            P2 = co(P2_3)
            if "tele" in R_:
                hi = self.limits(R_["tele"])[1]
                q = dict(vals)
                q[R_["tele"]] = hi if hi > 0 else 1000.0
                moved = self.moved(self.by[sec].get("rides_on"), self._p[sec], q, after=slew)
                if np.linalg.norm(moved - P2_3) > LINE_MM:
                    raise ReachError(f"The {ROLE_WORDS[role_of(self.by[R_['tele']]) or 'telescope']} '{R_['tele']}' "
                                     f"moves the joint '{sec}': it must ride on the outer boom.",
                                     role_of(self.by[R_["tele"]]))
        P1 = co(P1_3)
        S0 = co(S0_3)
        w = np.zeros(2)
        Vb0, wb = None, None
        y_S = float((S0_3 - c) @ n)
        fly = self.fly

        def head(q):
            return self.moved(self.by[fly].get("rides_on"), self._p[fly], q, after=slew) if fly else None

        if "tele" in R_:
            tn = R_["tele"]
            lo, hi = self.limits(tn)
            span = hi if hi > 0 else 1000.0
            es = np.unique(np.r_[np.linspace(lo, hi, 11), 0.0, span])
            q = dict(vals)
            q[tn] = es
            S_e = self.moved(self.by[hoist].get("rides_on"), self._p[hoist], q, after=slew)
            xs = co(S_e)
            w = (xs[es == span][0] - xs[es == 0.0][0]) / span
            if np.max(np.linalg.norm(xs - (S0 + es[:, None] * w), axis=-1)) > LINE_MM:
                raise ReachError(f"The {ROLE_WORDS[role_of(self.by[tn]) or 'telescope']} '{tn}' does not move the boom "
                                 "head in a straight line.", role_of(self.by[tn]))
            ys = (S_e - c) @ n
            if np.max(np.abs(ys - y_S)) > PLANE_MM:
                raise ReachError("The boom does not move in one plane (the telescope leaves the luff joint's plane): "
                                 "Hook to here cannot work it out.", role_of(self.by[tn]))
            if fly:
                B0 = co(head(vals))
                q1 = dict(vals)
                q1[tn] = span
                wb = (co(head(q1)) - B0) / span
                Vb0 = B0 - P2
        elif fly:
            Vb0 = co(head(vals)) - P2
            wb = np.zeros(2)
        V0 = S0 - P2
        if Vb0 is None:
            Vb0, wb = V0, w
        hval = dict(vals)
        hval[hoist] = 0.0
        hook0 = self.moved(hoist, self.hook_cad, hval, after=slew)
        h = co(hook0) - S0
        y = float((hook0 - c) @ n)
        Rp, _t = self.transforms(self.by[hoist].get("rides_on"), vals, after=slew)
        D = Rp @ self._d[hoist]
        dz = -float(D @ u)
        if dz < 0.5:
            raise ReachError(f"The hoist joint '{hoist}' does not lower the hook (its direction does not point down).",
                             "hoist")
        return Plane(c=c, u=u, n=n, ex=ex, e2=np.cross(u, ex), sz=sz, s1=s1, s2=s2, P1=P1, P2=P2, V0=V0, w=w, Vb0=Vb0,
                     wb=wb, h=h, y=y, dz=dz, model_boom=self.model_boom)

    # -- joint values ---------------------------------------------------------------------------------------------
    def name(self, role: str) -> str | None:
        return self.role.get(role)

    def hook(self, given: dict) -> np.ndarray:
        """The hook's point in the model frame (mm)."""
        return self.moved(self.role["hoist"], self.hook_cad, given)

    def hook_dir(self, given: dict) -> np.ndarray:
        """The way the hoist lowers the hook (unit, model frame): straight down when the hook hangs plumb."""
        return self.axis(self.role["hoist"], given)

    def slew_centre(self, given: dict) -> np.ndarray:
        return self.point(self.role["slew"], given)

    def radius_height(self, given: dict) -> tuple[float, float]:
        """(radius from the slew axis, hook height above the model's ground) in m."""
        p = self.hook(given)
        c = self.slew_centre(given)
        a = self.axis(self.role["slew"], given)
        d = p - c
        r = d - (d @ a) * a
        return float(np.linalg.norm(r) / 1000.0), float((p @ self.up) / 1000.0)

    def boom_length(self, given: dict) -> float:
        """The boom length the charts mean (m): a crawler's model boom; else pivot -> (knuckle ->) head sheave (a fly
        jib's foot when it has one)."""
        if self.model_boom:
            return float(self.model_boom)
        pl = self.plane(given)
        e = float(self.value_of(self.role["tele"], given)) if "tele" in self.role else 0.0
        return pl.boom_m(e)

    def boom_angle(self, given: dict) -> float:
        """The (main) boom's angle above horizontal, degrees."""
        return self.th0 + float(self.value_of(self.role["luff"], given))

    def second_angle(self, given: dict) -> float | None:
        """The jib's / outer boom's angle to the main boom's line, degrees (None: the crane has none)."""
        if "second" not in self.role:
            return None
        return self.second_cad + float(self.value_of(self.role["second"], given))

    def jib_length(self) -> float | None:
        return float(self.model_jib) if self.model_jib else None

    def jib_angle_note(self, boom_angle: float) -> str:
        """'' or why a luffing jib's charts do not hold: they are for the main boom at one angle."""
        if self.jib_boom_angle is None or self.mode != "jib":
            return ""
        if abs(boom_angle - float(self.jib_boom_angle)) <= JIB_ANGLE_TOL:
            return ""
        return (f"No chart: the jib charts are for the main boom at {float(self.jib_boom_angle):g}°; it stands at "
                f"{boom_angle:.1f}°.")


# ---------------------------------------------------------------------------------------------------------------------
# charts for a set-up

SETUP_KEYS = ("counterweight", "outriggers")          # chosen by the user; the boom (and a crawler's jib) by the pose
SETUP_WORDS = {"counterweight": "counterweight", "outriggers": "outrigger spread"}


def setup_values(charts) -> dict:
    """{config key: sorted values the charts have} for the keys a user sets (counterweight in kg, spread in m)."""
    out: dict = {}
    for c in charts:
        for k in SETUP_KEYS:
            v = c.config.get(k)
            if isinstance(v, (int, float)) and math.isfinite(v):
                out.setdefault(k, set()).add(float(v))
    return {k: sorted(v) for k, v in out.items()}


def _shown(key: str, v: float) -> str:
    return f"{lifting.tonnes(v):g} t" if key == "counterweight" else f"{v:g} m"


def _close(a, b) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


def chart_for(charts, boom: float | None, setup: dict | None = None, jib: float | None = None):
    """(chart or None, sentence) for a boom length (m), the user's set-up ({"counterweight": kg, "outriggers": m};
    a key left out or None = the smallest the charts have) and a crawler's jib (m, None = main boom charts).

    Only combinations the file has. An in-between counterweight or spread takes the next lower one (the next safer
    chart); a combination the file does not have steps the counterweight down, then the spread, and says so."""
    charts = list(charts)
    if not charts:
        return None, "The crane's file has no load chart."
    setup = dict(setup or {})
    vals = setup_values(charts)
    notes = []
    config = {}
    for k in SETUP_KEYS:
        if k not in vals:
            continue
        have = vals[k]
        v = setup.get(k)
        if v is None:
            config[k] = have[0]
            continue
        v = float(v)
        hit = next((x for x in have if _close(x, v)), None)
        if hit is None:
            lower = [x for x in have if x < v]
            if not lower:
                return None, (f"No chart for a {SETUP_WORDS[k]} of {_shown(k, v)} or less (the charts start at "
                              f"{_shown(k, have[0])}).")
            hit = lower[-1]
            where = ("is more than the charts have" if hit == have[-1] else "lies between the charts' values")
            notes.append(f"the {SETUP_WORDS[k]} {_shown(k, v)} {where}: the {_shown(k, hit)} chart is the next "
                         "safer one")
        config[k] = hit
    has_jib = any(c.config.get("jib") is not None for c in charts)
    jib_cfg = {}
    if has_jib:
        jib_cfg = {"jib": None}
    if jib is not None:
        jibs = sorted({c.config["jib"] for c in charts if isinstance(c.config.get("jib"), (int, float))})
        longer = [x for x in jibs if x >= jib - 1e-6]
        if not longer:
            return None, f"No chart for a jib of {jib:g} m or longer."
        jib_cfg = {"jib": longer[0]}
        if not _close(longer[0], jib):
            notes.append(f"the next longer jib {longer[0]:g} m")
    tries = [dict(config)]
    # a combination the file does not have: step the counterweight down, then the spread
    for k in ("counterweight", "outriggers"):
        if k in config:
            for x in reversed([x for x in vals[k] if x < config[k]]):
                t = dict(tries[-1])
                t[k] = x
                tries.append(t)
    for i, cfg in enumerate(tries):
        chart, why = lifting.pick_chart(charts, boom=boom, **cfg, **jib_cfg)
        if chart is not None:
            if i:
                changed = [f"{SETUP_WORDS[k]} {_shown(k, cfg[k])}" for k in cfg if not _close(cfg[k], config[k])]
                notes.append("the file has no chart for the set-up as chosen: using " + ", ".join(changed)
                             + " (the next safer one)")
            if why != "Chart found.":
                notes.append(why.rstrip(".").replace("Using ", "", 1))
            text = "Chart: " + (chart.name or "unnamed")
            if notes:
                text += ". " + "; ".join(notes)[0].upper() + "; ".join(notes)[1:] + "."
            return chart, text
    _c, why = lifting.pick_chart(charts, boom=boom, **config, **jib_cfg)
    return None, why


def outrigger_spread(data: dict, values: dict) -> float | None:
    """The outrigger / stabiliser spread across (m) the pose gives, from the file's ``outriggers`` block
    (b = b_in + stages x value; spread = 2 b), or None."""
    o = data.get("outriggers") or {}
    if not isinstance(o, dict):
        return None
    j = o.get("joint")
    if not j or not _number(o.get("b_in")):
        return None
    stages = o.get("stages", 1)
    stages = float(stages) if _number(stages) else 1.0
    v = values.get(j, 0.0)
    v = float(v) / 1000.0 if _number(v) else 0.0
    return 2.0 * (float(o["b_in"]) + stages * v)


# ---------------------------------------------------------------------------------------------------------------------
# Hook to here

@dataclass
class Answer:
    ok: bool
    values: dict = field(default_factory=dict)   # joint name -> value (deg / mm) to set; empty when not ok
    reason: str = ""                             # out of reach: by how much; else what was chosen
    radius: float = 0.0                          # m
    height: float = 0.0                          # m (hook)
    boom: float = 0.0                            # m
    chart: object = None
    chart_note: str = ""
    use: float | None = None
    error_mm: float = 0.0                        # the 3-D kinematics' hook against the target
    candidates: int = 0


def _single(P, V, s, lim, Xs):
    """Turn V (from P) about P by a in ``lim`` so the end's x is Xs, for rows of P (k, 2) and V (k, 2) at once:
    (degrees (k, 2), end (k, 2, 2), ok (k, 2)) and, per row without an answer, (kind, by mm) – far / close / limits."""
    P = np.broadcast_to(np.asarray(P, float), np.shape(V))
    V = np.asarray(V, float)
    rho = np.hypot(V[:, 0], V[:, 1])
    gam = np.arctan2(V[:, 1], V[:, 0])
    with np.errstate(divide="ignore", invalid="ignore"):
        c = (Xs - P[:, 0]) / rho
    c = np.where((np.abs(c) > 1.0) & (np.abs(c) <= 1.0 + 1e-9), np.sign(c), c)  # the boom at the end of its range
    valid = (np.abs(c) <= 1.0) & (rho >= 1e-9)
    a = np.arccos(np.clip(c, -1.0, 1.0))
    psi = np.stack([a - gam, -a - gam], axis=1)
    deg = _wrap_v(np.degrees(psi) / s, lim)
    ang = gam[:, None] + np.radians(s * deg)
    end = np.stack([P[:, None, 0] + rho[:, None] * np.cos(ang), P[:, None, 1] + rho[:, None] * np.sin(ang)], axis=-1)
    ok = valid[:, None] & np.isfinite(deg) & (np.abs(end[..., 0] - Xs) < 1e-3)
    fails = [None] * len(V)
    bad = np.flatnonzero(~ok.any(axis=1))
    if len(bad):
        aa = np.radians(s * np.linspace(lim[0], lim[1], 721))
        xs = P[bad, 0, None] + rho[bad, None] * np.cos(gam[bad, None] + aa)
        for i, k in enumerate(bad):
            if rho[k] < 1e-9:
                fails[k] = ("far", 0.0)
            elif Xs > xs[i].max():
                fails[k] = ("far", Xs - xs[i].max())
            elif Xs < xs[i].min():
                fails[k] = ("close", xs[i].min() - Xs)
            else:
                fails[k] = ("limits", 0.0)
    return deg, end, ok, fails


class _Search:
    """The solves in the boom's plane for one target (in-plane X, height Z relative to the slew axis' point)."""

    def __init__(self, rig: Rig, pl: Plane, X: float, Z: float):
        self.rig, self.pl, self.X, self.Z = rig, pl, X, Z
        self.hoist_lim = rig.solve_range(rig.role["hoist"])
        self.lim1 = rig.solve_range(rig.role["luff"])
        self.lim2 = rig.solve_range(rig.role["second"]) if "second" in rig.role else (0.0, 0.0)
        self.Xs = X - pl.h[0]
        self.fails: list = []

    def _hoist(self, hook0_z):
        """Hoist values for hook heights (array): (values clamped, ok); fails recorded."""
        hv = (np.asarray(hook0_z, float) - self.Z) / self.pl.dz
        lo, hi = self.hoist_lim
        ok = (hv >= lo - HOIST_TOL) & (hv <= hi + HOIST_TOL)
        for v in hv[hv < lo - HOIST_TOL]:
            self.fails.append(("high", lo - v))
        for v in hv[hv > hi + HOIST_TOL]:
            self.fails.append(("low", v - hi))
        return np.clip(hv, lo, hi), ok

    # one rotation: the boom (luff) for telescope values E, or the jib with the boom at a1 values (e = 0)
    def at(self, E=None, a1=None) -> list:
        pl = self.pl
        if a1 is None:
            E = np.atleast_1d(np.asarray(E, float))
            V = (pl.P2 - pl.P1) + pl.V0 + E[:, None] * pl.w
            deg, end, ok, fails = _single(pl.P1, V, pl.s1, self.lim1, self.Xs)
            rows = [(i, {"a1": None, "a2": 0.0, "e": float(E[i])}) for i in range(len(E))]
        else:
            A = np.atleast_1d(np.asarray(a1, float))
            r = np.radians(pl.s1 * A)
            P2 = pl.P1 + _r2(pl.P2 - pl.P1, r)
            V = _r2(np.broadcast_to(pl.V0, (len(A), 2)), r)
            deg, end, ok, fails = _single(P2, V, pl.s2, self.lim2, self.Xs)
            rows = [(i, {"a1": float(A[i]), "a2": None, "e": 0.0}) for i in range(len(A))]
        self.fails += [f for f in fails if f is not None]
        out = [[] for _ in rows]
        idx = np.argwhere(ok)
        if len(idx):
            hv, hok = self._hoist(end[idx[:, 0], idx[:, 1], 1] + pl.h[1])
            for (i, k), v, good in zip(idx, hv, hok):
                if good:
                    s = dict(rows[i][1])
                    s["a1" if a1 is None else "a2"] = float(deg[i, k])
                    s["hoist"] = float(v)
                    out[i].append(s)
        return out

    # two rotations + free height (knuckle-boom): IK in the plane for telescope values (rows) x hoist values (cols)
    def _ik(self, E, HV):
        pl = self.pl
        E = np.asarray(E, float)[:, None]
        l1v = pl.P2 - pl.P1
        l2v = pl.V0 + E[..., None] * pl.w                      # (ne, 1, 2)
        l1 = float(np.linalg.norm(l1v))
        l2 = np.linalg.norm(l2v, axis=-1)                      # (ne, 1)
        al1 = math.atan2(l1v[1], l1v[0])
        al2 = np.arctan2(l2v[..., 1], l2v[..., 0])
        Zs = self.Z + HV * pl.dz - pl.h[1]
        dx, dz = self.Xs - pl.P1[0], Zs - pl.P1[1]
        cb = (dx * dx + dz * dz - l1 * l1 - l2 * l2) / (2 * l1 * l2)
        valid = (cb >= -1.0) & (cb <= 1.0)
        acb = np.arccos(np.clip(cb, -1.0, 1.0))
        ok_any = np.zeros(np.shape(Zs), bool)
        A1 = np.full(np.shape(Zs), np.nan)
        A2 = np.full(np.shape(Zs), np.nan)
        Eb = np.broadcast_to(E, np.shape(Zs))
        for b in (acb, -acb):                                  # the elbow-down branch first (knuckle below the line)
            base = np.arctan2(dz, dx) - np.arctan2(l2 * np.sin(b), l1 + l2 * np.cos(b))
            a1 = _wrap_v(np.degrees(base - al1) / pl.s1, self.lim1)
            a2 = _wrap_v(np.degrees(b - (al2 - al1)) / pl.s2, self.lim2)
            good = valid & np.isfinite(a1) & np.isfinite(a2)
            S = pl.sheave(np.nan_to_num(a1), np.nan_to_num(a2), Eb)
            good &= (np.abs(S[..., 0] - self.Xs) < 0.01) & (np.abs(S[..., 1] - Zs) < 0.01)
            take = good & ~ok_any
            A1 = np.where(take, a1, A1)
            A2 = np.where(take, a2, A2)
            ok_any |= good
        return ok_any, A1, A2

    def reaches_two(self, E) -> list:
        """For each telescope value: does any of the 401 hoist values reach (yes / no only)."""
        E = np.atleast_1d(np.asarray(E, float))
        lo, hi = self.hoist_lim
        grid = np.linspace(lo, hi, GRID_HOIST)
        ok, _a1, _a2 = self._ik(E, np.broadcast_to(grid, (len(E), len(grid))))
        return ok.any(axis=1).tolist()

    def reaches_one(self, E) -> list:
        return [bool(g) for g in self.at(E=E)]

    def two(self, E) -> list:
        """For each telescope value: the lowest hoist rope that reaches (the class solver's 401 values, then the
        boundary between the last that does not and the first that does), as solutions."""
        E = np.atleast_1d(np.asarray(E, float))
        lo, hi = self.hoist_lim
        grid = np.linspace(lo, hi, GRID_HOIST)
        ok, A1, A2 = self._ik(E, np.broadcast_to(grid, (len(E), len(grid))))
        out = [[] for _ in E]
        has = ok.any(axis=1)
        first = np.argmax(ok, axis=1)
        rows0 = np.flatnonzero(has & (first == 0))
        for i in rows0:
            out[i].append({"a1": float(A1[i, 0]), "a2": float(A2[i, 0]), "e": float(E[i]), "hoist": float(lo)})
        rows = np.flatnonzero(has & (first > 0))
        if len(rows):
            a = grid[first[rows] - 1].astype(float)
            b = grid[first[rows]].astype(float)
            sa1, sa2 = A1[rows, first[rows]], A2[rows, first[rows]]
            Er = E[rows]
            K = 32
            f = np.arange(1, K + 1) / K
            for _ in range(12):
                if np.all(b - a <= 1e-6):
                    break
                pts = a[:, None] + (b - a)[:, None] * f
                pts[:, -1] = b                                 # b itself reaches (no rounding past it)
                okp, p1, p2 = self._ik(Er, pts)
                any_ = okp.any(axis=1)
                j = np.argmax(okp, axis=1)
                r = np.arange(len(rows))
                a = np.where(any_ & (j > 0), pts[r, np.maximum(j - 1, 0)], a)
                b = np.where(any_, pts[r, j], b)
                sa1 = np.where(any_, p1[r, j], sa1)
                sa2 = np.where(any_, p2[r, j], sa2)
            for k, i in enumerate(rows):
                out[i].append({"a1": float(sa1[k]), "a2": float(sa2[k]), "e": float(E[i]), "hoist": float(b[k])})
        return out


def _candidates_e(rig: Rig, pl: Plane, charts, X: float | None = None) -> list:
    """Telescope / extension values worth trying: a fine grid, every chart's boom length and – one turning joint –
    the lengths that reach the radius with the boom at either end of its luff range (the ends of the lengths that
    reach: a window can be narrower than the grid)."""
    if "tele" not in rig.role:
        return [0.0]
    lo, hi = rig.limits(rig.role["tele"])
    es = [float(x) for x in np.linspace(lo, hi, GRID_E)]
    if X is not None and rig.mode == "luff":
        Xs = X - pl.h[0]
        for a1 in rig.solve_range(rig.role["luff"]):
            r = math.radians(pl.s1 * a1)
            rv = _r2(pl.P2 - pl.P1 + pl.V0, r)
            rw = _r2(pl.w, r)
            if abs(rw[0]) > 1e-12:
                e = (Xs - pl.P1[0] - rv[0]) / rw[0]
                if lo - 1e-9 <= e <= hi + 1e-9:
                    es.append(min(max(e, lo), hi))
    L0, L1 = pl.boom_m(lo), pl.boom_m(hi)
    for c in charts or ():
        b = c.config.get("boom")
        if isinstance(b, (int, float)) and L0 - 1e-6 <= b <= L1 + 1e-6 and L1 > L0:
            es.append(lo + (hi - lo) * (b - L0) / (L1 - L0))
    return sorted(set(round(e, 6) for e in es))


def _words_fail(fails, R: float, X: float, y: float) -> str:
    """Why no answer, from the solves' failures (in-plane mm turned into radius where the hook is beside it)."""
    if not fails:
        return "Out of reach within the joints' limits."
    by = {}
    for kind, d in fails:
        by[kind] = min(by.get(kind, 1e18), d)

    def radial(kind):
        if not y:
            return by[kind]
        x = X - by[kind] if kind == "far" else X + by[kind]
        return abs(R - math.hypot(x, y))

    if "far" in by and not any(k in by for k in ("high", "low")):
        return f"Out of reach: {radial('far') / 1000:.2f} m further out than the hook reaches."
    if "close" in by and not any(k in by for k in ("high", "low", "far")):
        return f"Out of reach: {radial('close') / 1000:.2f} m closer to the slew axis than the hook reaches."
    if "high" in by:
        return f"Out of reach: {by['high'] / 1000:.2f} m higher than the hook reaches at this radius."
    if "low" in by:
        return f"Out of reach: {by['low'] / 1000:.2f} m lower than the hoist rope reaches."
    if "far" in by:
        return f"Out of reach: {radial('far') / 1000:.2f} m further out than the hook reaches."
    return "Out of reach within the joints' limits."


def _diagnose(rig: Rig, pl: Plane, R: float, X: float, Z: float) -> str:
    """Why a point is out of reach, from the hook's places over a grid of the boom's joints (two turning joints:
    no closed form for the whole reach)."""
    lim1 = rig.solve_range(rig.role["luff"])
    lim2 = rig.solve_range(rig.role["second"]) if "second" in rig.role else (0.0, 0.0)
    lime = rig.limits(rig.role["tele"]) if "tele" in rig.role else (0.0, 0.0)
    a1 = np.radians(pl.s1 * np.linspace(*lim1, 121))[:, None, None]
    a2 = np.radians(pl.s2 * np.linspace(*lim2, 121 if "second" in rig.role else 1))[None, :, None]
    e = np.linspace(*lime, 9 if "tele" in rig.role else 1)[None, None, :]
    vx, vz = pl.V0[0] + e * pl.w[0], pl.V0[1] + e * pl.w[1]
    ix, iz = vx * np.cos(a2) - vz * np.sin(a2), vx * np.sin(a2) + vz * np.cos(a2)
    ux, uz = pl.P2[0] - pl.P1[0] + ix, pl.P2[1] - pl.P1[1] + iz
    hx = pl.P1[0] + ux * np.cos(a1) - uz * np.sin(a1) + pl.h[0]
    hz = pl.P1[1] + ux * np.sin(a1) + uz * np.cos(a1) + pl.h[1]
    r = hx.ravel()
    z = hz.ravel()
    y = pl.y
    if X > r.max():
        far = (R - math.hypot(r.max(), y)) if y else X - r.max()
        return f"Out of reach: about {far / 1000:.2f} m further out than the hook reaches."
    if X < r.min():
        close = (math.hypot(r.min(), y) - R) if y else r.min() - X
        return f"Out of reach: about {close / 1000:.2f} m closer to the slew axis than the hook reaches."
    band = np.abs(r - X) < max(100.0, 0.01 * (r.max() - r.min()))
    lo, hi = rig.solve_range(rig.role["hoist"])
    if band.any():
        zmax, zmin = z[band].max() - lo * pl.dz, z[band].min() - hi * pl.dz
        if Z > zmax:
            return f"Out of reach: about {(Z - zmax) / 1000:.2f} m higher than the hook reaches at this radius."
        if Z < zmin:
            return f"Out of reach: about {(zmin - Z) / 1000:.2f} m lower than the hoist rope reaches."
    return "Out of reach within the joints' limits."


def _shortest(reaches, solve, a: float, b: float, sols: list, steps: int = 40) -> None:
    """The shortest telescope that reaches, between ``a`` (does not) and ``b`` (does), by halving (``reaches(E)`` ->
    yes / no per value); the shortest found is solved (``solve(E)`` -> solutions per value) and joins ``sols``. (The
    values between it and ``b`` take the same chart, so the shortest of them is the one ranked first.)"""
    b0 = b
    for _ in range(steps):
        m = 0.5 * (a + b)
        if reaches([m])[0]:
            b = m
        else:
            a = m
    if b != b0:
        for g in solve([b]):
            sols += g


def _hook_rz(rig: Rig, pl: Plane, vals: dict):
    """The hook's (radius, height) about the slew axis (mm) in the slew's base frame, slew at 0, for values that may
    be arrays; and the hook points."""
    p = rig.moved(rig.role["hoist"], rig.hook_cad, vals, after=rig.role["slew"])
    d = p - pl.c
    z = d @ pl.u
    hor = d - z[..., None] * pl.u
    return np.linalg.norm(hor, axis=-1), z, p


def _polish(rig: Rig, pl: Plane, vals: dict, names: tuple, R: float, Z: float) -> dict:
    """Newton on the 3-D kinematics: the two ``names`` moved so the hook's radius and height are R and Z (the plane's
    closed forms are exact for a plane rig; this takes out what a drawn axis' last decimals leave)."""
    vals = dict(vals)
    lims = [rig.solve_range(n) for n in names]
    best, best_res = dict(vals), math.inf
    steps = np.array([1e-4 if rig.by[n]["kind"] == "ROTATE" else 1e-3 for n in names])
    for _ in range(6):
        q = dict(vals)
        for k, n in enumerate(names):
            q[n] = np.array([vals[n], vals[n] + (steps[k] if k == 0 else 0.0), vals[n] + (steps[k] if k == 1 else 0.0)])
        r, z, _p = _hook_rz(rig, pl, q)
        res = np.array([r[0] - R, z[0] - Z])
        size = float(np.max(np.abs(res)))
        if size >= best_res:
            break                                              # no better: keep the best (a joint at its limit)
        best, best_res = dict(vals), size
        if size < 1e-3:
            break
        J = np.array([[(r[1] - r[0]) / steps[0], (r[2] - r[0]) / steps[1]],
                      [(z[1] - z[0]) / steps[0], (z[2] - z[0]) / steps[1]]])
        try:
            dq = np.linalg.solve(J, -res)
        except np.linalg.LinAlgError:
            break
        if not np.all(np.isfinite(dq)):
            break
        for k, n in enumerate(names):
            vals[n] = float(min(max(vals[n] + dq[k], lims[k][0]), lims[k][1]))
    return best


def hook_to(rig: Rig, target, current: dict | None = None, charts=(), setup: dict | None = None,
            load_kg: float = 0.0, hook_block_kg: float = 0.0) -> Answer:
    """Joint values that put the hook (hanging plumb) on ``target`` (model frame, mm). ``current``: the joints' values
    now (deg / mm; a crawler's travel and every joint Hook to here does not solve stay). Among several answers the
    lowest crane use on the chart that applies (``chart_for`` with ``setup``; gross = load + hook block unless the chart
    includes it), then the shortest boom. Out of reach: ``ok`` False and the reason (by how much)."""
    current = dict(current or {})
    T = np.asarray(target, float)
    role = rig.role
    slew = rig.by[role["slew"]]
    keep = rig._base_values(current)
    if slew.get("rides_on"):
        Rb, tb = rig.transforms(slew["rides_on"], keep)
        Tb = Rb.T @ (T - tb)
    else:
        Tb = T
    pl = rig.plane(keep)
    d = Tb - pl.c
    Z = float(d @ pl.u)
    hor = d - Z * pl.u
    R = float(np.linalg.norm(hor))
    height = float(Tb @ rig.up) / 1000.0
    y = pl.y
    X = math.sqrt(max(R * R - y * y, 0.0))
    cur_slew = float(current.get(role["slew"], 0.0))
    phi_T = math.atan2(float(hor @ pl.e2), float(hor @ pl.ex))
    slew_lim = rig.limits(role["slew"])
    if R < 1.0:
        slew_v = cur_slew
    else:
        phi_h = math.atan2(y * float(pl.n @ pl.e2), X)
        slew_v = _wrap_into(math.degrees(phi_T - phi_h) * pl.sz, slew_lim, near=cur_slew)
        if slew_v is None:
            return Answer(False, reason="Out of reach: the point lies outside the slew range.")
    search = _Search(rig, pl, X, Z)
    sols: list = []
    es = _candidates_e(rig, pl, charts, X)
    if rig.mode == "jib":                                        # a luffing jib: the boom at its charts' angle
        lim1 = rig.solve_range(role["luff"])
        pref = (rig.jib_boom_angle - rig.th0) if rig.jib_boom_angle is not None else 0.5 * (lim1[0] + lim1[1])
        pref = min(max(pref, lim1[0]), lim1[1])
        order = sorted(np.arange(lim1[0], lim1[1] + 1e-9, 0.5).tolist() + [pref], key=lambda a: abs(a - pref))
        for got in search.at(a1=np.array(order)):
            if got:
                sols = got
                break
    elif rig.mode == "knuckle":
        for g in search.two(es):
            sols += g
    else:
        for g in search.at(E=es):
            sols += g
    if R * R < y * y - 1e-9 and not sols:
        return Answer(False, reason=f"Out of reach: {(abs(y) - R) / 1000:.2f} m closer to the slew axis than the hook "
                      "reaches.", radius=R / 1000.0, height=height)
    if not sols:
        why = _diagnose(rig, pl, R, X, Z) if "second" in role else _words_fail(search.fails, R, X, y)
        return Answer(False, reason=why, radius=R / 1000.0, height=height)
    # the shortest boom that reaches: between the last telescope value that does not and the first that does
    if "tele" in role and len(es) > 1:
        first = min(s["e"] for s in sols)
        below = [e for e in es if e < first]
        if below:
            if rig.mode == "knuckle":
                _shortest(search.reaches_two, search.two, below[-1], first, sols)
            else:
                _shortest(search.reaches_one, lambda E: search.at(E=E), below[-1], first, sols)
    best, best_key = None, None
    cache: dict = {}
    jib = rig.jib_length()
    for s in sols:
        boom = pl.boom_m(s["e"])
        ck = round(boom, 9)
        if ck not in cache:
            chart, note = chart_for(charts, boom, setup, jib) if charts else (None, "")
            use = cap = None
            if chart is not None:
                r = lifting.crane_use(load_kg, R / 1000.0, chart, hook_block=hook_block_kg)
                use, cap = r.use, r.limit
            cache[ck] = (chart, note, use, cap)
        chart, note, use, cap = cache[ck]
        why = rig.jib_angle_note(rig.th0 + s["a1"])
        if why:
            chart, note, use, cap = None, why, None, None
        # no chart / no capacity last; then the lowest use, then the shortest boom (the brief's order)
        key = (0 if cap else 1, round(use, 12) if use is not None else math.inf, round(boom, 6), s["hoist"])
        if best_key is None or key < best_key:
            best, best_key = (s, boom, chart, note, use), key
    s, boom, chart, note, use = best
    vals = {role["luff"]: s["a1"], role["hoist"]: s["hoist"]}
    if "second" in role:
        vals[role["second"]] = s["a2"]
    if "tele" in role:
        vals[role["tele"]] = s["e"]
    # the 3-D kinematics: polish (a drawn axis' last decimals), the slew from the hook's own bearing, the check
    full = dict(keep)
    full.update(vals)
    if R >= 1.0:
        if rig.mode == "knuckle":
            unknown = (role["luff"], role["second"])
        elif rig.mode == "jib":
            unknown = (role["second"], role["hoist"])
        else:
            unknown = (role["luff"], role["hoist"])
        full = _polish(rig, pl, full, unknown, R, Z)
        for n in unknown:
            vals[n] = full[n]
        _r, _z, p = _hook_rz(rig, pl, full)
        dh = p - pl.c
        phi_h = math.atan2(float(dh @ pl.e2), float(dh @ pl.ex))
        sv = _wrap_into(math.degrees(phi_T - phi_h) * pl.sz, slew_lim, near=cur_slew)
        if sv is not None:
            slew_v = sv
    vals = {role["slew"]: slew_v, **vals}
    full = dict(keep)
    full.update(vals)
    err = float(np.linalg.norm(rig.hook(full) - T))
    bad = [n for n in rig.chain(role["hoist"]) if rig.by[n].get("limits")
           and not (rig.limits(n)[0] - 1e-3 <= rig.value_of(n, full) <= rig.limits(n)[1] + 1e-3)]
    if err > CHECK_MM or bad:
        return Answer(False, reason="Hook to here found no answer inside the joints' limits"
                      + (f" ({', '.join(bad)})" if bad else f" (the hook would be {err:.1f} mm off)") + ".",
                      radius=R / 1000.0, height=height)
    return Answer(True, values=vals, reason="", radius=R / 1000.0, height=height, boom=boom, chart=chart,
                  chart_note=note, use=use, error_mm=err, candidates=len(sols))


# ---------------------------------------------------------------------------------------------------------------------
# the live readout

NO_CHART_WORDS = "Not checked – no chart"


@dataclass
class Readout:
    radius: float = 0.0          # m, slew axis -> hook, horizontal
    height: float = 0.0          # m, hook above the crane's ground
    boom: float = 0.0            # m
    boom_angle: float = 0.0      # deg
    second_angle: float | None = None
    jib: float | None = None     # m (crawler's luffing jib)
    chart: object = None
    chart_note: str = ""
    row: float | None = None     # m, the chart row used (next longer radius)
    capacity: float | None = None  # kg
    load: float = 0.0            # kg, load x contingency
    hook_block: float = 0.0      # kg, added (0 when the chart includes it)
    rigging: float = 0.0         # kg (0 until rigging comes, L5)
    gross: float = 0.0           # kg
    use: float | None = None
    status: str = lifting.NOT_CHECKED
    words: str = lifting.STATUS_WORDS[lifting.NOT_CHECKED]
    reason: str = ""
    sample: bool = False
    result: object = None


def readout(rig: Rig, values: dict, charts=(), setup: dict | None = None, load_kg: float = 0.0,
            contingency: float = 1.0, hook_block_kg: float = 0.0, rigging_kg: float = 0.0,
            limits: lifting.Limits = lifting.DEFAULT_LIMITS) -> Readout:
    """What the panel shows for the crane's pose: geometry, chart, capacity, gross load and crane use."""
    r, z = rig.radius_height(values)
    out = Readout(radius=r, height=z, boom=rig.boom_length(values), boom_angle=rig.boom_angle(values),
                  second_angle=rig.second_angle(values), jib=rig.jib_length())
    out.load = max(0.0, load_kg) * max(contingency, 0.0)
    out.rigging = rigging_kg
    if not list(charts or ()):
        # no chart at all: placed and moved, but nothing to judge against – grey, never "over" a limit nobody entered
        out.status, out.words = lifting.NOT_CHECKED, NO_CHART_WORDS
        out.reason = out.chart_note = "The crane's file has no load chart: crane use is not checked."
        out.hook_block = hook_block_kg
        out.gross = out.load + rigging_kg + hook_block_kg
        return out
    chart, note = chart_for(charts, out.boom, setup, out.jib)
    why = rig.jib_angle_note(out.boom_angle)
    if why:
        chart, note = None, why
    out.chart, out.chart_note = chart, note
    if chart is None:
        out.status, out.words = lifting.RED, lifting.STATUS_WORDS[lifting.RED]
        out.reason = note
        out.hook_block = hook_block_kg
        out.gross = out.load + rigging_kg + hook_block_kg
        return out
    out.sample = bool(chart.sample)
    res = lifting.crane_use(out.load, r, chart, rigging=rigging_kg, hook_block=hook_block_kg, limits=limits)
    out.result = res
    out.hook_block = 0.0 if chart.includes_hook_block else hook_block_kg
    out.gross = float(res.value or 0.0)
    out.capacity = res.details.get("capacity")
    out.row = res.details.get("row_radius")
    out.use = res.use
    out.status, out.words = res.status, res.words
    if out.capacity is None:
        out.reason = f"No capacity here: {res.details.get('reason', '')}."
    return out
