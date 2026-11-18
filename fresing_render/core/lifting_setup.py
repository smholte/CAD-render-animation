"""The Check step of "Set up a crane" (task 0203) – plain Python, no Blender.

``check(data)`` runs every check on an equipment file's data (as ``lifting_library`` reads it; the rig as
``blender/lifting_rig_out.py`` writes it) and gives a list of ``Problem``: which set-up step can mend it (``step``: a
role key of ``lifting_reach.ROLE_KEYS``, or "hook_block", "masses", "chart", "poses"; None when no step owns it), the
problem in plain words, and how bad (``lifting.RED`` – Hook to here or the plan cannot be trusted – or ``lifting.AMBER``).

* ``missing_roles`` – the joints each kind needs (mobile: slew, luff, telescope, hoist; crawler: slew, luff, hoist;
  knuckle-boom: slew, luff, knuckle, hoist; other: slew, luff, hoist) and the hook point; what Hook to here refuses,
* ``sweep`` – each driven joint with limits run from min to max (9 steps, the others at the start pose): its followers
  stay inside their own limits, the hook hangs plumb (within 0.5°),
* ``pose_problems`` – the poses' values inside the joints' limits, the start pose there,
* ``mass_problems`` – every group with parts has a mass above 0 and a centre of gravity,
* ``cog_problems`` – the crane's centre of gravity at the start pose inside its support (``footprint``),
* ``chart_problems`` – the load charts as L1 / L2 check them; none: amber "Not checked – no chart".

Masses are in the file's mass unit, centres of gravity in its length unit, in the model frame; a group's centre of
gravity moves with its ``moves_with`` joint. Joint values are the rig's (mm, degrees).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import lifting, lifting_library as LL, lifting_reach as LR

KIND_ROLES = {
    "mobile_crane": ("slew", "luff", "telescope", "hoist"),
    "crawler_crane": ("slew", "luff", "hoist"),
    "knuckle_boom_crane": ("slew", "luff", "knuckle", "hoist"),
}
OTHER_ROLES = ("slew", "luff", "hoist")
SWEEP_STEPS = 9
PLUMB_DEG = 0.5          # the hoist this close to straight down
LIMIT_TOL = 1e-3         # deg / mm past a limit that is only rounding
SUPPORT_GROUPS = ("carrier", "lower", "truck", "base")
REACH_ROLES = ("luff", "telescope", "jib", "knuckle", "extension", "hoist")   # Hook to here and the chart need limits


@dataclass
class Problem:
    step: str | None
    text: str
    severity: str = lifting.RED


def _rig(data) -> dict:
    r = data.get("rig") if isinstance(data, dict) else None
    return r if isinstance(r, dict) else {}


def _kin(data):
    """(Kinematics or None, problems reading the joints)."""
    try:
        return LR.Kinematics(data), []
    except LR.ReachError as exc:
        return None, [Problem(exc.step, str(exc))]


def _unit(kin, name: str) -> str:
    return "°" if kin.by[name]["kind"] == "ROTATE" else " mm"


def _fmt(v: float) -> str:
    return f"{v:.4g}" if abs(v) < 1000 else f"{v:.0f}"


def start_values(data) -> dict:
    """The start pose's joint values (an empty dict when the file names none)."""
    rig = _rig(data)
    name = rig.get("start_pose")
    for p in rig.get("poses") or []:
        if isinstance(p, dict) and p.get("name") == name and isinstance(p.get("values"), dict):
            return {k: float(v) for k, v in p["values"].items() if isinstance(v, (int, float))}
    return {}


# ---------------------------------------------------------------------------------------------------------------------
# roles

def needed_roles(kind: str) -> tuple:
    return KIND_ROLES.get(kind, OTHER_ROLES)


def missing_roles(data) -> list[Problem]:
    """The roles the crane's kind needs that no driven joint has, and a missing hook point."""
    rig = _rig(data)
    have = {LR.role_of(j) for j in rig.get("joints") or [] if isinstance(j, dict) and not j.get("follows")}
    out = []
    kind = str(data.get("kind", "")) if isinstance(data, dict) else ""
    for r in needed_roles(kind):
        if r not in have:
            out.append(Problem(r, f"No {LR.ROLE_WORDS[r]} joint: make it in the step '{r.capitalize()}' (or give a "
                               f"joint the role '{r}')."))
    hook = rig.get("hook")
    if not isinstance(hook, dict) or LR._vec3(hook.get("point")) is None:
        out.append(Problem("hook_block", "The hook point is not set: pick it in the step 'Hook block'."))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# joints run through their range

def _down(kin) -> np.ndarray:
    return -kin.up


def sweep(data, steps: int = SWEEP_STEPS) -> list[Problem]:
    """Each driven joint with limits from its min to its max (the others at the start pose): its followers stay inside
    their limits, and the hook hangs plumb along the hoist."""
    kin, out = _kin(data)
    if kin is None:
        return out
    start = start_values(data)
    hoists = [j["name"] for j in kin.driven() if LR.role_of(j) == "hoist"]
    hook = _rig(data).get("hook") or {}
    hoist = hook.get("joint") if isinstance(hook, dict) and hook.get("joint") in hoists else (hoists[0] if hoists
                                                                                               else None)
    hoist_chain = set(kin.chain(hoist)) if hoist else set()
    followers: dict = {}
    for j in kin.joints:
        if j.get("follows"):
            lead, r = kin.leader_of(j["name"])
            followers.setdefault(lead, []).append((j["name"], r))
    for j in kin.driven():
        n = j["name"]
        if j.get("limits"):
            lo, hi = kin.limits(n)
        else:
            role = LR.role_of(j)
            if role in REACH_ROLES:
                out.append(Problem(role, f"The {LR.ROLE_WORDS[role]} joint '{n}' has no limits: Hook to here and the "
                                   "chart need them – set its Min and Max."))
            # the hook's plumb is still checked over a sensible range: ±90° or the CAD place ± 3 m
            lo, hi = (-90.0, 90.0) if j["kind"] == "ROTATE" else (-3000.0, 3000.0)
        vs = np.linspace(lo, hi, steps)
        for f, r in followers.get(n, []):
            if not kin.by[f].get("limits") or not j.get("limits"):
                continue
            flo, fhi = kin.limits(f)
            fv = r * vs
            badv = np.flatnonzero((fv < flo - LIMIT_TOL) | (fv > fhi + LIMIT_TOL))
            if len(badv):
                k = badv[-1] if fv[badv[-1]] > fhi else badv[0]
                u, fu = _unit(kin, n), _unit(kin, f)
                out.append(Problem(LR.role_of(kin.by[f]) or LR.role_of(j),
                                   f"When '{n}' is at {_fmt(vs[k])}{u}, '{f}' follows it to {_fmt(fv[k])}{fu}: "
                                   f"past its limits {_fmt(flo)} … {_fmt(fhi)}{fu}. Set its ratio or its limits."))
        moves_hoist = any(kin.leader_of(x)[0] == n for x in hoist_chain)
        if hoist and moves_hoist:
            q = dict(start)
            q[n] = vs
            D = np.atleast_2d(kin.axis(hoist, q))
            D = D / np.linalg.norm(D, axis=-1, keepdims=True)
            ang = np.atleast_1d(np.degrees(np.arccos(np.clip(D @ _down(kin), -1.0, 1.0))))
            k = int(np.argmax(ang))
            if ang[k] > PLUMB_DEG:
                out.append(Problem("hook_block",
                                   f"The hook does not hang plumb when '{n}' is at {_fmt(vs[k])}{_unit(kin, n)}: the "
                                   f"hoist leans {ang[k]:.1f}° from straight down. The hook swing joints must follow "
                                   "the boom's turns (ratio −1)."))
    return out


def pose_problems(data) -> list[Problem]:
    """Every pose's values name joints of the rig and lie inside their limits (followers too); the start pose exists."""
    kin, out = _kin(data)
    if kin is None:
        return out
    rig = _rig(data)
    poses = [p for p in rig.get("poses") or [] if isinstance(p, dict)]
    names = [p.get("name") for p in poses]
    sp = rig.get("start_pose")
    if sp and sp not in names:
        out.append(Problem("poses", f"The start pose '{sp}' is not one of the crane's poses.", lifting.AMBER))
    for p in poses:
        vals = p.get("values") if isinstance(p.get("values"), dict) else {}
        for k, v in vals.items():
            if k not in kin.by:
                out.append(Problem("poses", f"The pose '{p.get('name')}' sets '{k}', which is not a joint of the "
                                   "crane.", lifting.AMBER))
            elif not isinstance(v, (int, float)) or not math.isfinite(v):
                out.append(Problem("poses", f"The pose '{p.get('name')}' gives '{k}' no number."))
        given = {k: float(v) for k, v in vals.items() if k in kin.by and isinstance(v, (int, float))}
        for j in kin.joints:
            if not j.get("limits"):
                continue
            v = float(kin.value_of(j["name"], given))
            lo, hi = kin.limits(j["name"])
            if v < lo - LIMIT_TOL or v > hi + LIMIT_TOL:
                u = _unit(kin, j["name"])
                out.append(Problem("poses", f"The pose '{p.get('name')}' puts '{j['name']}' at {_fmt(v)}{u}, past its "
                                   f"limits {_fmt(lo)} … {_fmt(hi)}{u}."))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# masses and the centre of gravity

def _units(data) -> tuple[str, str]:
    try:
        return LL.units_of(data)
    except LL.LibraryError:
        return "t", "m"


def _rig_to_file(data) -> float:
    """Factor: the rig's lengths (mm) -> the file's length unit."""
    _m, length = _units(data)
    ru = str(_rig(data).get("units") or "mm")
    return lifting.LENGTH_UNITS.get(ru, 0.001) / lifting.LENGTH_UNITS[length]


def _groups(data) -> dict:
    g = _rig(data).get("groups")
    return g if isinstance(g, dict) else {}


def mass_problems(data) -> list[Problem]:
    """Every group with parts has a mass above 0 and a centre of gravity; the masses add up to more than 0."""
    mu, _l = _units(data)
    out = []
    m = data.get("mass")
    cog = data.get("cog")
    groups = {k: v for k, v in _groups(data).items() if isinstance(v, dict) and v.get("parts")}
    if m is None:
        return [Problem("masses", "No masses: enter each group's mass in the step 'Masses & CoG'.")]
    if isinstance(m, (int, float)):
        if not m > 0:
            out.append(Problem("masses", f"The crane's mass must be more than 0 {mu}."))
        if LR._vec3(cog) is None:
            out.append(Problem("masses", "The crane's centre of gravity is not set."))
        return out
    if not isinstance(m, dict):
        return [Problem("masses", "The masses cannot be read (one number per group).")]
    cog = cog if isinstance(cog, dict) else {}
    for g in groups:
        v = m.get(g)
        if not isinstance(v, (int, float)) or not v > 0:
            out.append(Problem("masses", f"The group '{g}' has parts but no mass: enter it in {mu} (or work it out "
                               "from the volume)."))
        if LR._vec3(cog.get(g)) is None:
            out.append(Problem("masses", f"The group '{g}' has no centre of gravity."))
    total = sum(float(v) for v in m.values() if isinstance(v, (int, float)) and math.isfinite(v))
    if not total > 0 and not out:
        out.append(Problem("masses", f"The masses add up to {total:g} {mu}: enter each group's mass."))
    return out


def total_cog(data, values: dict | None = None):
    """(total mass in the file's mass unit, centre of gravity in its length unit, model frame) at joint values (the
    start pose when None); (0, None) when the file has no masses with a centre of gravity."""
    m = data.get("mass")
    cog = data.get("cog")
    if isinstance(m, (int, float)):
        c = LR._vec3(cog)
        return (float(m), c) if c is not None and m > 0 else (0.0, None)
    if not isinstance(m, dict) or not isinstance(cog, dict):
        return 0.0, None
    vals = start_values(data) if values is None else dict(values)
    try:
        kin = LR.Kinematics(data)
    except LR.ReachError:
        kin = None
    f = _rig_to_file(data)
    groups = _groups(data)
    tot, mom = 0.0, np.zeros(3)
    for g, mg in m.items():
        c = LR._vec3(cog.get(g))
        if c is None or not isinstance(mg, (int, float)) or not math.isfinite(mg) or mg <= 0:
            continue
        mw = groups.get(g, {}).get("moves_with") if isinstance(groups.get(g), dict) else None
        if kin is not None and mw in kin.by:
            c = kin.moved(mw, c / f, vals) * f
        tot += float(mg)
        mom += float(mg) * c
    if tot <= 0:
        return 0.0, None
    return tot, mom / tot


def _flat(data, p) -> np.ndarray:
    """A model point's two level coordinates: (x, y) for Z up, (x, z) for Y up."""
    up = str(_rig(data).get("up_axis") or "Z").strip().upper().lstrip("+")
    p = np.asarray(p, float)
    return np.array([p[0], p[2]]) if up == "Y" else np.array([p[0], p[1]])


def _box(cx, cy, hx, hy) -> list:
    cx, cy, hx, hy = float(cx), float(cy), float(hx), float(hy)
    return [(cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)]


def _num(x) -> bool:
    return LR._number(x)


def _xy(c):
    """A level point [x, y] of two numbers, else None (missing: the origin)."""
    if c is None:
        return 0.0, 0.0
    if isinstance(c, (list, tuple)) and len(c) == 2 and _num(c[0]) and _num(c[1]):
        return float(c[0]), float(c[1])
    return None


def _support(data, values: dict | None = None):
    """(polygon or None, the support blocks the file has but that cannot be read)."""
    vals = start_values(data) if values is None else dict(values)
    f = _rig_to_file(data)
    bad = []
    o = data.get("outriggers")
    if o and not (isinstance(o, dict) and not any(k in o for k in ("a", "b_in"))):
        c = _xy(o.get("centre")) if isinstance(o, dict) else None
        st = o.get("stages", 1) if isinstance(o, dict) else None
        st = 1 if st is None else st
        if isinstance(o, dict) and _num(o.get("a")) and _num(o.get("b_in")) and c is not None and _num(st):
            v = vals.get(o.get("joint"), 0.0) if o.get("joint") else 0.0
            v = float(v) * f if _num(v) else 0.0
            return _box(c[0], c[1], float(o["a"]), float(o["b_in"]) + float(st) * v), bad
        bad.append("outriggers")
    t = data.get("tracks")
    if t and not (isinstance(t, dict) and not any(k in t for k in ("gauge", "length"))):
        c = _xy(t.get("centre")) if isinstance(t, dict) else None
        if isinstance(t, dict) and _num(t.get("gauge")) and _num(t.get("length")) and c is not None:
            cx, cy = c
            j = t.get("joint")
            try:
                kin = LR.Kinematics(data)
            except LR.ReachError:
                kin = None
            if kin is not None and j in kin.by:
                up = str(_rig(data).get("up_axis") or "Z").strip().upper()
                p = np.array([cx, 0.0, cy]) if up == "Y" else np.array([cx, cy, 0.0])
                cx, cy = _flat(data, kin.moved(j, p / f, vals) * f)
            return _box(cx, cy, float(t["length"]) / 2, float(t["gauge"]) / 2), bad
        bad.append("tracks")
    fp = data.get("footprint")
    if fp:
        pts = [_xy(q) if q is not None else None for q in fp] if isinstance(fp, list) else []
        if len(pts) >= 3 and all(q is not None for q in pts):
            return pts, bad
        bad.append("footprint")
    a = data.get("axles")
    if isinstance(a, dict) and "width" in a:
        xs = a.get("x")
        if isinstance(xs, list) and xs and all(_num(x) for x in xs) and _num(a.get("width")):
            xs = [float(x) for x in xs]
            return _box(0.5 * (min(xs) + max(xs)), 0.0, 0.5 * (max(xs) - min(xs)), float(a["width"]) / 2), bad
        bad.append("axles")
    return None, bad


def footprint(data, values: dict | None = None) -> list | None:
    """The crane's support at joint values (the start pose when None), a counter-clockwise polygon of level points in
    the file's length unit: the outrigger pads (``outriggers``: a, b_in + stages x the joint), the tracks' centre lines
    (``tracks``: length x gauge, moved with their joint), the ``footprint`` the set-up writes, or the axles (``axles``
    with a ``width``). None when the file has none it can read."""
    return _support(data, values)[0]


def inside(point, polygon) -> bool:
    """A level point inside a polygon (or on its edge)."""
    x, y = float(point[0]), float(point[1])
    n = len(polygon)
    hit = False
    for i in range(n):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % n]
        # on the edge
        dx, dy = x1 - x0, y1 - y0
        ll = dx * dx + dy * dy
        if ll > 0:
            t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / ll))
            if math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)) <= 1e-9 * max(1.0, math.sqrt(ll)):
                return True
        if (y0 > y) != (y1 > y):
            if x < x0 + (y - y0) * dx / dy:
                hit = not hit
    return hit


def _outside_by(point, polygon) -> float:
    x, y = float(point[0]), float(point[1])
    best = math.inf
    n = len(polygon)
    for i in range(n):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        ll = dx * dx + dy * dy
        t = 0.0 if ll == 0 else max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / ll))
        best = min(best, math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)))
    return best


def cog_problems(data, values: dict | None = None) -> list[Problem]:
    """The crane's centre of gravity at rest (the start pose, or ``values``) inside its support."""
    fp, bad = _support(data, values)
    _mu, lu = _units(data)
    out = [Problem("masses", f"The file's '{b}' cannot be read (its sizes must be numbers, in {lu}): the support "
                   "area leaves it out.") for b in bad]
    m, c = total_cog(data, values)
    if c is None:
        return out                                 # mass_problems says what is missing
    if fp is None:
        return out + [Problem("masses", "Not checked – no support area: the file has no outriggers, tracks or "
                              "footprint.", lifting.AMBER)]
    p = _flat(data, c)
    if not inside(p, fp):
        pose = _rig(data).get("start_pose") if values is None else None
        where = f" in the pose '{pose}'" if pose else ""
        out.append(Problem("masses", f"The crane's centre of gravity{where} lies {_outside_by(p, fp):.2f} {lu} "
                           "outside its support (outriggers / tracks): check the masses and centres of gravity."))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# charts

def chart_problems(data) -> list[Problem]:
    """The load charts as the library reads and checks them (L1 / L2); none: amber, crane use is not checked."""
    mu, lu = _units(data)
    raw = data.get("charts")
    if not raw:
        return [Problem("chart", "Not checked – no chart: the crane can be placed and moved, crane use shows 'Not "
                        "checked'.", lifting.AMBER)]
    problems: list = []
    charts = LL._read_charts(data, mu, lu, problems)
    out = [Problem("chart", t) for t in problems]
    if charts:
        e, w = lifting.validate_charts(charts)
        out += [Problem("chart", t) for t in e]
        out += [Problem("chart", t, lifting.AMBER) for t in w]
    return out


# ---------------------------------------------------------------------------------------------------------------------
# all of it

def check(data, values: dict | None = None) -> list[Problem]:
    """Every check of the Check step, in the order of the set-up's steps; ``values``: the pose for the centre of
    gravity (the start pose when None)."""
    if not isinstance(data, dict):
        return [Problem(None, "The crane's file cannot be read.")]
    out = missing_roles(data)
    kin, kp = _kin(data)
    out += kp
    if kin is not None:
        if not out:
            try:
                LR.Rig(data)
            except LR.ReachError as exc:
                out.append(Problem(exc.step, str(exc)))
        out += sweep(data)
        out += pose_problems(data)
    out += mass_problems(data)
    out += cog_problems(data, values)
    out += chart_problems(data)
    return out
