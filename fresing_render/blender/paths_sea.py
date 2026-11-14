"""A cable into the sea (task 0081): the catenary from its last contact down to the seabed, the cable lying on the
seabed behind it, and things fitted on the cable (CPS sets, bend restrictors) riding along it.

**The sea end** (``item.b_kind == "SEA"``, settings ``sea_*`` on the cable item). The cable's last contact it
bends round (a horn, a chute, an overboarding sheave) is the hang-off. From there the cable hangs as a catenary
(``core/catenary.py``) down to where it touches the seabed and lies on the seabed behind it to its end, which lies
still. "Add sea end" (or any change of its settings) sets the touch-down at the pose shown: from the **layback**
(the flat distance from where the cable leaves the hang-off to the touch-down) or from the **bottom tension** and
the cable's weight in water; ``sea_laid`` metres lie on the seabed behind it. That fixes two numbers: where the
cable's end lies on the seabed (``sea_start``, in the seabed's coordinates) and its mark (``sea_mark``: metres
along the cable from its start, with nothing paid out – a point at s along the drawn path has the mark s − paid
out, the rule the cable looks follow). From then on the length from the hang-off down to the end is mark + paid
out − s(hang-off), at every moment: the catenary keeps its length exactly, the touch-down moves with the payout and
the vessel, and the stripes on the part lying on the seabed stand still by themselves.

**The seabed moves aft.** The scene keeps the vessel where it is; the seabed and the cable on it move aft under it.
That motion is the empty "FR seabed motion" (``BED``, one per scene, in flex's hidden collection): its place is
advance x the lay direction + the waterline's height, the advance a simple-expression driver – the metres paid out
("With the lay": the touch-down stays where it is behind the vessel) or the vessel speed of Weather & time x the
time (the speed the wake reads: one setting). The Sea surroundings' seabed follows it (a Copy Location constraint,
``surroundings.follow_seabed_motion``). The empty is a **slot** of the cable (``paths._inputs_of``), as the
cable joint's arrow and motion are (the payout, read as spool.py reads it): the live handler and Build's bake see
them move, so a catenary costs no Python per frame (Build writes every frame's shape into the cable's shapes mesh).

**Leaving the hang-off.** The path up to the hang-off wheel is the tight-string solver's (``core/paths.py``); from
where the cable arrives on that wheel ``core.catenary.hang_off`` finds where it leaves: where the catenary's tangent
is the wheel's (no kink). A chute or bend ends where the CAD cable leaves it (its wrap in the CAD pose); a sheave
after half a turn. Steeper than that, the cable leaves at the end with a kink and the app warns.

**Riders** (things on the cable): see the second half of this file.

Units: metres, radians. Nothing here runs unless a cable has a sea end or a rider.
"""

from __future__ import annotations

import json
import math

import bpy
import numpy as np

from ..core import catenary as C
from ..core import paths as P
from . import flex, joints

BED = "FR seabed motion"                # the empty that carries the seabed (one per scene)
TAG = "fr_sea"                          # on that empty
BOX = "fr_sea_box"                      # on a cable item: hang-off and touch-down (world, CAD place) when last set
SINK = 0.3                              # the cable lying on the seabed sinks this share of its Ø into the silt
SAG = 0.001                             # m: the drawn catenary lies at most this far inside the true curve
N_LAID, N_PILED = 2, 64                 # points of the part on the seabed (straight / snaking)
N_MIN, N_MAX = 16, 600                  # points of the hanging part
WRAP_SHEAVE = math.pi                   # a sheave lets the cable go at most half round it before it leaves
SHORT = 1e-4                            # m: an arc this short on the hang-off wheel: the cable just touches it
_STATE = {"sea": {}}                    # runtime: per cable the last solve's numbers (dropped at load / undo)


def forget() -> None:
    _STATE["sea"].clear()
    _STATE.get("moment", {}).clear()


def _paths():
    from . import paths
    return paths


def sea_cables(scene) -> list:
    return [it for it in scene.fresing.cables if it.b_kind == "SEA"]


def is_sea(item) -> bool:
    return item is not None and item.b_kind == "SEA"


# ---------------------------------------------------------------------------
# numbers: water, weight, payout
# ---------------------------------------------------------------------------

def waterline(scene) -> float:
    """World height of the water's surface: the Sea surroundings' water, else 0."""
    for ob in scene.objects:
        if ob.get("fr_env") == "sea":
            return float(ob.matrix_world.translation.z)
    return 0.0


def wants_flip(scene, item, line) -> bool:
    """paths.read_cad: should this cable's reading (``line``, world, CAD pose) be turned round so that it ends in
    the sea? (Its first point is under water and its last is not.)"""
    if line is None or len(line) < 2:
        return False
    w = waterline(scene)
    return float(line[0][2]) < w - 1e-6 and float(line[-1][2]) >= w - 1e-6


def depth(scene, item) -> float:
    d = float(item.sea_depth)
    return d if d > 0.0 else float(scene.fresing.sea_depth)


def weight(item) -> float:
    """kg/m in water: typed, else from the diameter."""
    w = float(item.sea_weight)
    return w if w > 0.0 else C.wet_weight(float(item.diameter))


def bottom_z(scene, item) -> float:
    """Height of the middle of the cable lying on the seabed, in the seabed's coordinates (0 = the waterline)."""
    return -depth(scene, item) + (0.5 - SINK) * float(item.diameter)


def _pay_map(scene, item):
    """(top joint, k, c, sign): metres paid out = sign x (k x top's value + c)."""
    j = joints.find(scene, item.joint) if item.joint else None
    if j is None:
        return None, 1.0, 0.0, 1.0
    top, k, c = joints.chain_affine(scene, j)
    return top, k, c, (-1.0 if item.reverse else 1.0)


def payout(scene, item) -> float:
    top, k, c, sign = _pay_map(scene, item)
    if top is None:
        return 0.0
    return sign * (k * joints.get_value(top) + c)


def _wrap_max(item, c) -> float:
    """How far round the hang-off the cable may go before it leaves: a chute or bend ends where CAD drew the cable
    leave it, a sheave after half a turn."""
    if c.kind == "SHEAVE":
        return WRAP_SHEAVE
    w = float(c.wrap_cad)
    return w if w > 1e-6 else math.radians(90.0)


# ---------------------------------------------------------------------------
# the seabed's motion
# ---------------------------------------------------------------------------

def bed(scene, create: bool = False):
    ob = bpy.data.objects.get(BED)
    if ob is not None and ob.get(TAG) != "bed":
        ob = None
    if ob is None and create:
        ob = bpy.data.objects.new(BED, None)
        ob[TAG] = "bed"
        ob.empty_display_size = 0.01
        ob.hide_render = ob.hide_select = True
        flex._collection(scene).objects.link(ob)
    if ob is not None and create and ob.name not in scene.objects:
        flex._collection(scene).objects.link(ob)
    return ob


def moves_by_time(scene, item) -> bool:
    """The seabed moves with the clock (Weather & time's vessel speed), not with the payout."""
    w = getattr(scene.fresing, "weather", None)
    return item.sea_speed == "WEATHER" and w is not None and bool(w.enabled) and float(w.vessel_speed) > 0.0


def _speed_ms(scene) -> float:
    w = getattr(scene.fresing, "weather", None)
    if w is None or not w.enabled:
        return 0.0
    return float(w.vessel_speed) * 0.514444


def _drive(ob, index: int, expr: str, variables: list) -> None:
    fc = ob.animation_data.drivers.find("location", index=index) if ob.animation_data else None
    if fc is None:
        fc = ob.driver_add("location", index)
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    d = fc.driver
    d.type = "SCRIPTED"
    while d.variables:
        d.variables.remove(d.variables[0])
    for name, id_type, idb, path in variables:
        v = d.variables.new()
        v.name, v.type = name, "SINGLE_PROP"
        v.targets[0].id_type = id_type
        v.targets[0].id = idb
        v.targets[0].data_path = path
    d.expression = expr


def _undrive(ob) -> None:
    ad = ob.animation_data
    if ad is None:
        return
    for fc in list(ad.drivers):
        if fc.data_path == "location":
            ad.drivers.remove(fc)


def sync_bed(scene) -> None:
    """The empty "FR seabed motion" for the scene's sea cables: at the waterline, moved aft by the payout or by the
    vessel speed x time (the first cable with a sea end decides the lay direction and the speed); the seabed of the
    Sea surroundings follows it. Nothing without a sea end."""
    sea = [it for it in sea_cables(scene) if it.enabled]
    ob = bed(scene, create=bool(sea))
    if ob is None:
        return
    z = waterline(scene)
    if abs(ob.location.z - z) > 1e-7:
        ob.location.z = z
    if not sea:
        _undrive(ob)
        ob.location.x = ob.location.y = 0.0
        return
    it = sea[0]
    u = np.array(it.sea_dir, dtype=float)
    u[2] = 0.0
    u = u / max(np.linalg.norm(u), 1e-12)
    if moves_by_time(scene, it):
        v = _speed_ms(scene)
        for i in (0, 1):
            k = v * float(u[i])
            _drive(ob, i, f"(frame - f0) * b / max(fps, 1) * {k!r}",
                   [("fps", "SCENE", scene, "render.fps"), ("b", "SCENE", scene, "render.fps_base"),
                    ("f0", "SCENE", scene, "frame_start")])
    else:
        top, k, c, sign = _pay_map(scene, it)
        if top is None or top.motion is None:
            _undrive(ob)
            ob.location.x = ob.location.y = 0.0
        else:
            for i in (0, 1):
                kk = k * sign * float(u[i])
                _drive(ob, i, joints.expression(kk, c * sign * float(u[i])),
                       [("a", "OBJECT", top.motion, joints.COUPLING_PATH)])
    try:
        from . import surroundings
        follow = getattr(surroundings, "follow_seabed_motion", None)
        if follow is not None:
            for o in scene.objects:
                if o.get("fr_env") in ("seabed", "stones"):
                    follow(o)
    except Exception:                           # (the seabed is the Sea's: never in the way of the cable)
        pass


def slot_objects(scene, item) -> list:
    """[(object, role)]: what a sea end reads every moment – the seabed's motion, the cable joint's arrow and
    motion (the payout is the motion's place along its arrow)."""
    ob = bed(scene, create=True)
    out = [(ob, "sea_bed")]
    top = _pay_map(scene, item)[0]
    if top is not None and top.frame is not None and top.motion is not None:
        out += [(top.frame, "sea_pay_frame"), (top.motion, "sea_pay_motion")]
    return out


def _roles(slots) -> dict:
    return {sl.role: k for k, sl in enumerate(slots) if sl.role}


def _pay_of(scene, item, rel, roles) -> np.ndarray:
    F = rel.shape[0]
    if "sea_pay_frame" not in roles or "sea_pay_motion" not in roles:
        return np.full(F, payout(scene, item))
    local = np.linalg.inv(rel[:, roles["sea_pay_frame"]]) @ rel[:, roles["sea_pay_motion"]]
    _top, k, c, sign = _pay_map(scene, item)
    return sign * (k * local[:, 2, 3] + c)


# ---------------------------------------------------------------------------
# solving
# ---------------------------------------------------------------------------

def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-300)


def _apply(M, p):
    return np.einsum("fij,fj->fi", M[:, :3, :3], p) + M[:, :3, 3]


def _turn(M, v):
    return _unit(np.einsum("fij,fj->fi", M[:, :3, :3], v))


class _Arrive:
    """The path from the cable's start up to where it arrives on the hang-off wheel, and that wheel, for F moments:
    the solver's points (part coordinates) and the wheel in the seabed's coordinates (metres)."""

    def __init__(self, scene, item, rel, slots, starts, centres, axes, radii, sides, on0, wraps0, scale, counts=None,
                 last: int = -1):
        paths = _paths()
        roles = _roles(slots)
        F, W = rel.shape[0], len(radii)
        self.F, self.W, self.scale = F, W, scale
        self.bed = rel[:, roles["sea_bed"]]
        self.inv = np.linalg.inv(self.bed)
        self.pay = _pay_of(scene, item, rel, roles)
        wheels = paths._wheels(item)
        c_last = wheels[last]                   # (the hang-off: the last wheel, or one before it, task 0082)
        self.wmax = _wrap_max(item, c_last)
        n = axes[:, -1]
        sd = float(sides[-1])
        down = _turn(self.bed, np.tile([0.0, 0.0, -1.0], (F, 1)))      # (part coordinates)
        e = _unit(down - (down * n).sum(1, keepdims=True) * n)
        td = centres[:, -1] + radii[-1] * sd * np.cross(e, n)          # where the wheel's tangent points down
        ends = td + e * max(float(radii[-1]), 1e-3)
        if counts is None:
            res = P.solve_frames(starts, centres, axes, radii, sides, ends, on0, False, held=True, wraps0=wraps0)
            ok = res["ok"]
            widest = res["wrap"][ok].max(axis=0) if ok.any() else np.zeros(W)
            widest[-1] = max(float(widest[-1]), self.wmax)
            counts = paths._counts(np.asarray(radii) * scale, widest)
        res = P.solve_frames(starts, centres, axes, radii, sides, ends, on0, False, counts=counts, held=True,
                             wraps0=wraps0)
        self.res, self.counts = res, counts
        i0 = int(res["first"][-1])
        self.i0, self.n_arc = i0, int(res["counts"][-1])
        self.arrive = _apply(self.inv, res["points"][:, i0])
        self.s_arrive = res["s"][:, i0] * scale
        self.centre = _apply(self.inv, centres[:, -1])
        self.axis = _turn(self.inv, axes[:, -1])
        self.radius = float(radii[-1]) * scale
        self.side = sd

    def take(self, idx):
        """The same for some of the moments only (``idx``: their indices)."""
        out = _Arrive.__new__(_Arrive)
        out.__dict__.update(self.__dict__)
        idx = np.asarray(idx, dtype=np.int64)
        out.F = len(idx)
        for key in ("bed", "inv", "pay", "arrive", "s_arrive", "centre", "axis"):
            setattr(out, key, getattr(self, key)[idx])
        res = dict(self.res)
        for key in ("points", "s", "wrap", "length", "ok", "bad", "held", "lifted"):
            res[key] = res[key][idx]
        res["problems"] = {j: self.res["problems"][int(f)] for j, f in enumerate(idx) if int(f) in self.res["problems"]}
        out.res = res
        return out


def _down_point(centre, axis, radius: float, side: float, down) -> np.ndarray:
    """(F, 3): where a wheel's tangent points straight down – where a cable hanging from it leaves it."""
    e = _unit(down - (down * axis).sum(1, keepdims=True) * axis)
    return centre + radius * side * np.cross(e, axis)


def _sub_arrive(scene, item, rel, slots, parts, idx, h: int, counts) -> _Arrive:
    """The path up to wheel ``h`` (the wheels after it left out) for the moments ``idx``."""
    starts, centres, axes, radii, sides, on0, wraps0, scale = parts
    return _Arrive(scene, item, rel[idx], slots, starts[idx], centres[idx][:, :h + 1], axes[idx][:, :h + 1],
                   radii[:h + 1], sides[:h + 1], on0, None if wraps0 is None else list(wraps0)[:h + 1], scale,
                   counts=list(counts)[:h + 1], last=h)


def _hang_of(scene, item, a, idx, h: int, prev, F: int):
    """``core.catenary.hang_off`` for the moments ``idx`` hanging from wheel ``h`` (``a``: their _Arrive)."""
    W = len(_paths()._wheels(item))
    L0 = float(item.sea_mark) + a.pay - a.s_arrive
    psi0 = None
    if prev is not None and len(prev["psi"]) == F and \
            (np.asarray(prev.get("hang", np.full(F, W - 1)))[idx] == h).all():
        psi0 = prev["psi"][idx]
    return C.hang_off(a.centre, a.axis, a.radius, a.side, a.arrive, a.wmax, np.array(item.sea_start, dtype=float),
                      np.array(item.sea_dir, dtype=float), bottom_z(scene, item), L0, psi0=psi0)


def _take_hung(hr: dict, sel, n: int) -> dict:
    return {k: (v[sel] if isinstance(v, np.ndarray) and v.shape[:1] == (n,) else v) for k, v in hr.items()}


def _hang_offs(scene, item, rel, slots, parts, ar, prev=None) -> tuple:
    """(hang (F,), {wheel index: (moments, _Arrive for them, hang_off for them)}) – task 0082. The cable hangs from
    its last wheel, unless that wheel is **released**: the solver lifts it (the cable runs past it), the cable would
    leave it where it arrives (it does not bend round it), or the wheel before it has gone past it in the lay
    direction (its hanging point lies further aft: a quadrant carried over the stern and down past the horn), so a
    cable hanging from that one never comes to it. Then the wheel before hangs it, and so on (never the first).
    Along an animation a wheel once released stays released for the later moments."""
    _starts, centres, axes, radii, sides, _on0, _wraps0, _scale = parts
    F, W = rel.shape[0], len(radii)
    hang = np.full(F, W - 1, dtype=np.int64)
    got = {W - 1: (np.arange(F), ar)}
    hung = {}
    down = _turn(ar.bed, np.tile([0.0, 0.0, -1.0], (F, 1)))
    lay = np.array(item.sea_dir, dtype=float)
    lay[2] = 0.0
    lay = _turn(ar.bed, np.tile(lay, (F, 1)))
    for h in range(W - 1, -1, -1):
        idx = np.flatnonzero(hang == h)
        if not len(idx):
            break
        if h not in got:
            got[h] = (idx, _sub_arrive(scene, item, rel, slots, parts, idx, h, ar.counts))
        a = got[h][1]
        hung[h] = _hang_of(scene, item, a, idx, h, prev, F)
        if h == 0:
            break
        lifted = a.res["lifted"][:, h] & a.res["ok"]
        touch = hung[h]["psi"] * a.radius >= SHORT
        td_h = _down_point(centres[idx, h], axes[idx, h], radii[h], sides[h], down[idx])
        td_p = _down_point(centres[idx, h - 1], axes[idx, h - 1], radii[h - 1], sides[h - 1], down[idx])
        past = ((td_p - td_h) * lay[idx]).sum(1) > 1e-6
        free = np.zeros(F, dtype=bool)
        free[idx] = lifted | past | ~touch
        if F > 1:
            free = np.maximum.accumulate(free) & (hang == h)
        if not free.any():
            break
        hang[free] = h - 1
    out = {}
    for h in np.unique(hang):
        h = int(h)
        want = np.flatnonzero(hang == h)
        if h not in got:
            a = _sub_arrive(scene, item, rel, slots, parts, want, h, ar.counts)
            hr = _hang_of(scene, item, a, want, h, prev, F)
        else:
            idx, a = got[h]
            hr = hung[h]
            if len(idx) != len(want) or (idx != want).any():
                sel = np.searchsorted(idx, want)
                a, hr = a.take(sel), _take_hung(hr, sel, len(idx))
        out[h] = (want, a, hr)
    return hang, out


def _wheel_parts(scene, item, rel, slots, scale):
    """starts, centres, axes, radii, sides, on0 as paths._solve_item works them out (part coordinates)."""
    paths = _paths()
    return paths._solve_parts(scene, item, rel, slots)


def laid_points(piled: float) -> int:
    """Points for a cable piled up on the seabed (it snakes in waves of ``core.catenary.SNAKE`` m): 16 per wave."""
    return int(np.clip(math.ceil(max(piled, 0.0) / C.SNAKE) * 16, N_PILED, 4000))


_SEA_KEYS = ("kind", "psi", "a", "layback", "angle", "laid", "suspended", "excess", "steep", "short", "kink", "tdp",
             "T", "pay", "bottom", "top", "T_part", "tdp_part", "length", "h")


def solve(scene, item, rel, slots, starts, centres, axes, radii, sides, on0, wraps0, scale) -> dict:
    """The cable's shape at F moments with its end in the sea: ``core.paths.solve_frames``' result (points in the
    cable part's coordinates) with the hang-off wheel's arc ending where the cable leaves it, the catenary and the
    part on the seabed after it; plus ``sea`` (the numbers per moment, "hang": the wheel it hangs from),
    ``released`` (F, W: the wheels it has left, task 0082) and ``sea_notes`` [(moment, words)].

    Every moment has the same points: a moment that hangs from an earlier wheel puts the points of the wheels it has
    left on its catenary."""
    F = rel.shape[0]
    W = len(radii)
    if not W:
        res = P.solve_frames(starts, centres, axes, radii, sides, starts, on0, False)
        res["ok"][:] = False
        res["problems"] = {f: "a cable into the sea needs a contact it hangs from (a horn, chute or sheave)"
                           for f in range(F)}
        return res
    parts = (starts, centres, axes, radii, sides, on0, wraps0, scale)
    ar = _Arrive(scene, item, rel, slots, starts, centres, axes, radii, sides, on0, wraps0, scale)
    prev = _STATE["sea"].get(_paths()._k(scene, item))
    hang, groups = _hang_offs(scene, item, rel, slots, parts, ar, prev)
    counts = np.asarray(ar.counts, dtype=np.int64)
    hung = {hh: g[2] for hh, g in groups.items()}
    # how many points the hanging part needs (one count for all moments)
    good = np.concatenate([hr["a"][(hr["kind"] == C.NORMAL) | (hr["kind"] == C.LIFTED)] for hr in hung.values()])
    a_min = float(good.min()) if len(good) else 10.0
    step = math.sqrt(8.0 * SAG * max(a_min, 0.05))
    s_max = max(float(hr["suspended"].max(initial=1.0)) for hr in hung.values())
    n_cat = int(np.clip(math.ceil(s_max / step), N_MIN, N_MAX))
    piles = np.concatenate([hr["laid"][hr["kind"] == C.PILED] for hr in hung.values()])
    n_laid = laid_points(float(piles.max())) if len(piles) else N_LAID
    n_pts = int(ar.i0) + int(counts[-1]) + n_cat + n_laid
    pts, s_all = np.zeros((F, n_pts, 3)), np.zeros((F, n_pts))
    ok = np.zeros(F, dtype=bool)
    wrap, lifted = np.zeros((F, W)), np.zeros((F, W), dtype=bool)
    released = np.zeros((F, W), dtype=bool)
    bad, held = ar.res["bad"].copy(), ar.res["held"].copy()
    problems = {}
    sea = {}
    for hh, (idx, a, hr) in groups.items():
        res = a.res
        psi, kind, s_h, L = hr["psi"], hr["kind"], hr["suspended"], hr["L"]
        n_arc = int(counts[hh])
        n_hang = int(counts[hh + 1:].sum()) + n_cat         # (the left wheels' points: more on the catenary)
        jc = np.arange(1, n_hang + 1) / n_hang
        jl = np.arange(1, n_laid + 1) / n_laid
        lam = np.concatenate([s_h[:, None] * jc, s_h[:, None] + (L - s_h)[:, None] * jl], axis=1)
        flat = (L - s_h) < 1e-4                 # nothing on the seabed (lifted off, too short)
        if flat.any():
            lam[flat] = L[flat, None] * (np.arange(1, n_hang + n_laid + 1) / (n_hang + n_laid))
        # the arc on the hang-off wheel; a wrap of (almost) nothing: its points go onto the first few cm of the catenary
        jj = np.linspace(0.0, 1.0, n_arc)
        arc = np.stack([C.wheel_point(a.centre, a.axis, a.radius, a.side, a.arrive, psi * t)[0] for t in jj], axis=1)
        s_arc = a.s_arrive[:, None] + a.radius * psi[:, None] * jj
        short = psi * a.radius < SHORT
        if short.any() and n_arc > 1:
            eps = np.minimum(0.05, 0.1 * np.maximum(L[short], 1e-3))
            lam_s = lam[short]
            lam[short] = eps[:, None] + lam_s * ((L[short] - eps) / np.maximum(L[short], 1e-300))[:, None]
            hs = {k: (v[short] if isinstance(v, np.ndarray) and v.shape[:1] == (len(idx),) else v)
                  for k, v in hr.items()}
            arc[short, 1:] = C.points(hs, eps[:, None] * jj[1:])
            s_arc[short] = a.s_arrive[short, None] + eps[:, None] * jj
        sea_pts = C.points(hr, lam)
        s_T = s_arc[:, -1]
        s_sea = np.where(short[:, None], a.s_arrive[:, None], s_T[:, None]) + lam
        bed = a.bed
        i0 = a.i0
        g_pts = np.concatenate([res["points"][:, :i0], _apply_n(bed, arc), _apply_n(bed, sea_pts)], axis=1)
        g_s = np.concatenate([res["s"][:, :i0], s_arc / a.scale, s_sea / a.scale], axis=1)
        if g_pts.shape[1] != n_pts:
            raise RuntimeError("the cable's points do not add up where it hangs from another wheel")   # (a bug)
        pts[idx], s_all[idx] = g_pts, g_s
        ok[idx] = res["ok"] & np.isfinite(g_pts).all(axis=(1, 2)) & np.isfinite(g_s).all(axis=1)
        wrap[np.ix_(idx, np.arange(hh + 1))] = res["wrap"]
        wrap[idx, hh] = psi
        lifted[np.ix_(idx, np.arange(hh + 1))] = res["lifted"]
        lifted[idx, hh] = short
        released[idx, hh + 1:] = True
        bad[idx], held[idx] = res["bad"], res["held"]
        for j, text in res["problems"].items():
            problems[int(idx[j])] = text
        bottom, top = C.tensions(hr["a"], hr["h"], weight(item))
        part = {"kind": kind, "psi": psi, "a": hr["a"], "layback": hr["layback"], "angle": hr["angle"],
                "laid": hr["laid"], "suspended": s_h, "excess": hr["excess"], "steep": hr["steep"],
                "short": hr["short"], "kink": hr["kink"], "tdp": hr["tdp"], "T": hr["T"], "pay": a.pay,
                "bottom": bottom, "top": top, "T_part": _apply(bed, hr["T"]), "tdp_part": _apply(bed, hr["tdp"]),
                "length": L, "h": hr["h"]}
        for key in _SEA_KEYS:
            v = np.asarray(part[key])
            if key not in sea:
                sea[key] = np.zeros((F,) + v.shape[1:], dtype=v.dtype)
            sea[key][idx] = v
    sea["hang"] = hang
    out = dict(ar.res)
    out.update(points=pts, s=s_all, length=s_all[:, -1].copy(), wrap=wrap, lifted=lifted, ok=ok, bad=bad, held=held,
               problems=problems, released=released, sea=sea, sea_notes=_notes(item, sea, ok))
    _STATE["sea"][_paths()._k(scene, item)] = {k: np.array(v) for k, v in sea.items()}
    if F == 1 or not item.sea_info:             # what the panel shows before anything is solved after a load
        info = {"layback": float(sea["layback"][0]), "angle": math.degrees(float(sea["angle"][0])),
                "bottom": float(sea["bottom"][0]), "top": float(sea["top"][0]), "laid": float(sea["laid"][0]),
                "hanging": float(sea["suspended"][0]), "kind": int(sea["kind"][0]), "a": float(sea["a"][0]),
                "height": float(sea["h"][0]), "depth": depth(scene, item), "weight": weight(item),
                "hang": int(hang[0])}
        text = json.dumps({key: round(v, 4) if isinstance(v, float) else v for key, v in info.items()})
        if item.sea_info != text:
            try:
                with flex._quiet(item):
                    item.sea_info = text
            except AttributeError:              # (asked while drawing: not written then)
                pass
    if F > 1:
        _STATE.get("moment", {}).clear()
    return out


def _apply_n(M, p):
    """(F, n, 3): points p (F, n, 3) through the matrices M (F, 4, 4)."""
    return np.einsum("fij,fnj->fni", M[:, :3, :3], p) + M[:, None, :3, 3]


def _notes(item, sea, ok) -> list:
    """[(moment, words)]: what is wrong with the hanging cable, the first moment each happens."""
    wheels = _paths()._wheels(item)
    hangs = np.asarray(sea.get("hang", np.full(len(ok), len(wheels) - 1)))
    out = []
    kind = sea["kind"]

    def first(mask):
        idx = np.flatnonzero(mask & ok)
        return int(idx[0]) if len(idx) else -1

    def name(k):
        h = int(hangs[k]) if len(hangs) > k else -1
        return wheels[h].name if 0 <= h < len(wheels) else ""

    k = first(kind == C.STRETCHED)
    if k >= 0:
        out.append((k, f"is {abs(float(sea['excess'][k])):.2f} m too short to reach its end on the seabed: drawn "
                       "straight – set the touch-down again or pay out more"))
    k = first(kind == C.PILED)
    if k >= 0:
        out.append((k, f"has {float(sea['excess'][k]):.2f} m more cable than the water is deep: it piles up on "
                       f"the seabed under '{name(k)}'"))
    k = first(kind == C.LIFTED)
    if k >= 0:
        out.append((k, "is so tight that it lifts its end off the seabed"))
    k = first(sea["steep"])
    if k >= 0:
        out.append((k, f"bends over the end of '{name(k)}' – more bottom tension or a longer chute"))
    k = first(sea["short"])
    if k >= 0:
        out.append((k, f"hangs too flat to touch '{name(k)}': more cable or less bottom tension"))
    return out


# ---------------------------------------------------------------------------
# setting the touch-down
# ---------------------------------------------------------------------------

def lay_direction(scene, item) -> np.ndarray:
    """The flat direction (world = seabed coordinates) the cable goes away from its hang-off in: outward from the
    wheel where its tangent points straight down."""
    paths = _paths()
    wheels, slots, w_slots, _a, _b = paths._inputs_of(item)
    if not wheels:
        return np.array([-1.0, 0.0, 0.0])
    c = wheels[-1]
    memo: dict = {}
    m = paths._world(c.carrier)
    n = _unit(m[:3, :3] @ np.array(c.axis, dtype=float))
    rho = float(c.side) * np.cross(np.array([0.0, 0.0, -1.0]), n)
    rho[2] = 0.0
    if np.linalg.norm(rho) < 1e-6:
        return np.array([-1.0, 0.0, 0.0])
    del memo
    return _unit(rho)


def anchor(scene, item) -> list[str]:
    """Set the touch-down at the pose shown: from the layback or the bottom tension, ``sea_laid`` on the seabed
    behind it. Writes ``sea_start``, ``sea_mark`` (and ``sea_dir`` when ``direction``)."""
    paths = _paths()
    wheels, slots, _w, _a, _b = paths._inputs_of(item)
    if not wheels:
        return ["A cable into the sea needs a contact it hangs from: add the horn, chute or sheave first"]
    sync_bed(scene)
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass
    rel = paths._rel_now(item, slots)[None]
    parts = paths._solve_parts(scene, item, rel, slots)
    ar = _Arrive(scene, item, rel, slots, *parts)
    if not ar.res["ok"].all():
        return [f"Cable '{paths.label(item)}': {ar.res['problems'].get(0, 'no path')}"]
    u = np.array(item.sea_dir, dtype=float)
    zb = bottom_z(scene, item)
    if item.sea_mode == "TENSION":
        a = float(item.sea_tension) * 1000.0 / (weight(item) * C.G)
        an = C.anchor(ar.centre, ar.axis, ar.radius, ar.side, ar.arrive, ar.wmax, u, zb, a=a, laid=item.sea_laid)
    else:
        an = C.anchor(ar.centre, ar.axis, ar.radius, ar.side, ar.arrive, ar.wmax, u, zb,
                      layback=float(item.sea_layback), laid=item.sea_laid)
    mark = float(ar.s_arrive[0] + an["length0"][0] - ar.pay[0])
    with flex._quiet(item):
        item.sea_start = tuple(float(v) for v in an["start"][0])
        item.sea_mark = mark
    # the cut-away box (Sea surroundings): from the hang-off and the touch-down, the vessel in its CAD place
    cad = np.array(paths._cad(item.part, {}), dtype=float)
    T_w, tdp_w = (cad[:3, :3] @ _apply(ar.bed, an[k])[0] + cad[:3, 3] for k in ("T", "tdp"))
    item[BOX] = [float(v) for v in tuple(T_w) + tuple(tdp_w)]
    out = []
    if float(an["T"][0, 2]) <= zb:
        out.append(f"Cable '{paths.label(item)}': its hang-off is under the seabed – a smaller water depth?")
    return out


def add_sea_end(scene, item) -> list[str]:
    """The cable's end goes into the sea from its last contact (4 Motion > Cables and paths > Into the sea)."""
    paths = _paths()
    if not paths._wheels(item):
        raise paths.PathError("Add the horn, chute or sheave the cable hangs from first: a cable into the sea "
                              "hangs from its last contact")
    with flex._quiet(item):
        if item.b_kind != "SEA":
            item.sea_was = item.b_kind
        item.b_kind = "SEA"
        item.sea_dir = tuple(float(v) for v in lay_direction(scene, item))
        item.sea_info = ""
    notes = anchor(scene, item)
    if paths._alive(scene, item.part):
        from . import build
        item.part[build.BOUNDS_CAD] = True      # the model's size: its CAD shape, not the cable down to the seabed
    paths.changed(scene, item)
    return notes


def remove_sea_end(scene, item) -> None:
    paths = _paths()
    with flex._quiet(item):
        item.b_kind = item.sea_was if item.sea_was in ("FIXED", "WHEEL") else "FIXED"
        item.sea_was = ""
        item.sea_info = ""
    _STATE["sea"].pop(paths._k(scene, item), None)
    from . import build
    if paths._alive(scene, item.part) and build.BOUNDS_CAD in item.part:
        del item.part[build.BOUNDS_CAD]
    sync_bed(scene)
    paths.changed(scene, item)


def weather_changed(scene) -> None:
    """Weather & time changed (its vessel speed, on or off): the seabed of a cable sailing at that speed follows."""
    if any(it.b_kind == "SEA" and it.sea_speed == "WEATHER" for it in scene.fresing.cables):
        sync_bed(scene)
        _paths().refresh(scene)


def water_changed(scene) -> None:
    """The sea's water depth or level changed: cables into the sea whose depth is the sea's are set again on the new
    seabed (their layback or tension kept); the seabed's motion goes to the new waterline."""
    try:
        bpy.context.view_layer.update()         # (a sea just made again has no world place before an update)
    except Exception:
        pass
    sync_bed(scene)
    for i, it in enumerate(scene.fresing.cables):
        if it.b_kind == "SEA" and it.enabled:
            changed(scene, scene.fresing.cables[i])


def changed(scene, item) -> None:
    """A sea-end setting changed: the touch-down is set again at the pose shown, the seabed follows, the cable is
    drawn again."""
    paths = _paths()
    if paths._STATE["busy"] or paths.index_of(scene, item) < 0 or not is_sea(item):
        return
    sync_bed(scene)
    anchor(scene, item)
    paths.changed(scene, item)


# ---------------------------------------------------------------------------
# what the panel and the surroundings read
# ---------------------------------------------------------------------------

def numbers(scene, item) -> dict:
    """The hanging cable's numbers at the frame shown (from the last solve): layback, angle (deg), tensions (kN),
    laid and hanging lengths, the problem kind. {} before the first solve."""
    paths = _paths()
    got = _STATE["sea"].get(paths._k(scene, item))
    if (got is None or len(got["kind"]) == 1) and paths._baked(scene) and paths._usable(scene, item):
        got = _moment(scene, item)             # (a reopened project: the frame shown, from the places read at Build)
    if got is None:
        try:
            info = json.loads(item.sea_info) if item.sea_info else {}
        except ValueError:
            return {}
        if "hang" in info:
            info.update(_hang_names(scene, item, {"hang": [info["hang"]], "kind": [0]}, 0))
        return info
    k = paths._moment_now(scene, item) if len(got["kind"]) > 1 else 0
    k = min(max(k, 0), len(got["kind"]) - 1)
    out = {"layback": float(got["layback"][k]), "angle": math.degrees(float(got["angle"][k])),
           "bottom": float(got["bottom"][k]), "top": float(got["top"][k]), "laid": float(got["laid"][k]),
           "hanging": float(got["suspended"][k]), "kind": int(got["kind"][k]), "a": float(got["a"][k]),
           "height": float(got["h"][k]), "depth": depth(scene, item), "weight": weight(item)}
    out.update(_hang_names(scene, item, got, k))
    return out                                  # (it is drawn by the panel: it must not write anything)


def _hang_names(scene, item, got, k: int) -> dict:
    """{"hang_off": the wheel it hangs from at moment k, and when it has left a later wheel: "left" (that wheel's
    name), "left_frame" (the first frame it hangs from an earlier one; None in the pose shown)} – task 0082."""
    paths = _paths()
    wheels = paths._wheels(item)
    if not wheels:
        return {}
    hang = np.asarray(got.get("hang", np.full(len(got["kind"]), len(wheels) - 1)))
    h = int(hang[min(k, len(hang) - 1)]) if len(hang) else len(wheels) - 1
    h = min(max(h, 0), len(wheels) - 1)
    out = {"hang_off": wheels[h].name}
    if h < len(wheels) - 1:
        out["left"] = wheels[h + 1].name
        out["left_frame"] = None
        if len(hang) > 1:
            first = paths._layout_of(paths._shapes(scene, item))[2]
            out["left_frame"] = int(first + int(np.argmax(hang < len(wheels) - 1)))
    return out


def _moment(scene, item):
    """The numbers of the frame shown of a built animation, solved for that one moment (kept per frame)."""
    paths = _paths()
    key = (paths._k(scene, item), int(scene.frame_current))
    hit = _STATE.setdefault("moment", {}).get(key)
    if hit is not None:
        return hit
    slots = paths._inputs_of(item)[1]
    stored = paths._stored_places(scene, item, slots)
    if stored is None:
        return None
    rel, first = stored
    k = min(max(int(scene.frame_current) - first, 0), len(rel) - 1)
    keep = _STATE["sea"].get(paths._k(scene, item))
    try:
        paths._solve_item(scene, item, rel[k:k + 1], first=first + k)
        hit = _STATE["sea"].get(paths._k(scene, item))
    finally:
        if keep is not None:
            _STATE["sea"][paths._k(scene, item)] = keep
        else:
            _STATE["sea"].pop(paths._k(scene, item), None)
    if len(_STATE["moment"]) > 64:
        _STATE["moment"].clear()
    _STATE["moment"][key] = hit
    return hit


def tdp_world(scene, item, moment=None, cad: bool = False):
    """(hang-off point, touch-down point) in world coordinates, or None: of the frame shown (or ``moment`` of the
    last solve), the vessel where it is now – or in its CAD place (``cad``: what the cut-away box is placed by, so
    it does not move with the vessel's motion)."""
    paths = _paths()
    got = _STATE["sea"].get(paths._k(scene, item))
    if got is None and paths._usable(scene, item) and is_sea(item):         # (a project just opened)
        if paths._baked(scene):
            got, moment = _moment(scene, item), 0
        else:
            paths._rebuild(scene, item)
            got = _STATE["sea"].get(paths._k(scene, item))
    if got is None or not paths._alive(scene, item.part):
        return None
    if moment is None:
        moment = paths._moment_now(scene, item) if len(got["kind"]) > 1 else 0
    k = min(max(int(moment), 0), len(got["kind"]) - 1)
    m = np.array(paths._cad(item.part, {}) if cad else paths._world(item.part), dtype=float)
    return m[:3, :3] @ got["T_part"][k] + m[:3, 3], m[:3, :3] @ got["tdp_part"][k] + m[:3, 3]


def cut_box(scene):
    """The cut-away box the Sea surroundings draw when it is placed by the cable (world): {"origin": (x, y) the
    box's front middle (under the hang-off, 3 m towards the vessel), "dir": (ux, uy) aft, "length", "width"}; None
    without a cable into the sea."""
    for it in sea_cables(scene):
        if not it.enabled or BOX not in it:
            continue
        v = [float(x) for x in it[BOX]]
        T, tdp = np.array(v[:3]), np.array(v[3:6])
        u = np.array(it.sea_dir, dtype=float)
        u[2] = 0.0
        u = u / max(float(np.linalg.norm(u)), 1e-12)
        lay = float(np.dot((tdp - T)[:2], u[:2]))
        front = T[:2] - 3.0 * u[:2]
        length = max(12.0, 3.0 + 1.35 * max(lay, 0.0) + 6.0)
        width = max(14.0, 0.45 * length, 0.9 * depth(scene, it) + 6.0)     # (wide enough to see the seabed)
        return {"origin": (float(front[0]), float(front[1])), "dir": (float(u[0]), float(u[1])),
                "length": float(length), "width": float(width)}
    return None


# ---------------------------------------------------------------------------
# riders: things fitted on the cable (CPS sets, bend restrictors, a pull head)
# ---------------------------------------------------------------------------

def rider_changed(scene, rider) -> None:
    """A rider setting changed: it is placed again."""
    from . import paths_riders
    paths_riders.changed(scene, rider)


# ---------------------------------------------------------------------------
# the test model (tests, test tour, PC check)
# ---------------------------------------------------------------------------

TEST_ANIMATION = "Cable into the sea"
TEST_CABLE = "Sea cable"
TEST_RIDER = "CPS set"


def set_up_test_model(scene, speed: float = 60.0, seconds: float = 8.0) -> dict:
    """The set-up of the sea cable test model (test_sea.step, tools/make_test_sea.py), already imported: the cable
    read from its part CABLE (power cable look) and hung into the sea from its HORN (15 m of water, layback 20 m),
    the CPS SET on it passing the horn at 1 m paid out, and the animation "Cable into the sea": the cable pays out at
    ``speed`` m/min for ``seconds`` s. Not built. Returns the names of what was made."""
    from . import build, paths_riders
    paths = _paths()

    def named(name):
        for ob in scene.objects:
            if ob.get(build.PROP_NAME) == name:
                return ob
        raise paths.PathError(f"The model has no part '{name}'.")

    item = paths.add_cable(scene, TEST_CABLE)
    name = item.name
    notes = paths.read_cad(scene, item, named("CABLE"))
    item = paths.find(scene, name)
    item.pitch = 0.4
    with flex._quiet(item):
        item.sea_depth, item.sea_layback, item.sea_laid = 15.0, 20.0, 40.0
    notes += add_sea_end(scene, item)
    item = paths.find(scene, name)
    r = paths_riders.add(scene, item, [named("CPS SET")], where="MARK", at=1.0, name=TEST_RIDER)
    a = scene.fresing.animations.add()
    a.name, a.tail, a.fps = TEST_ANIMATION, 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", item.joint, 0.0, float(seconds), "LINEAR"
    b.speed_mmin = float(speed)
    scene.fresing.animations_index = len(scene.fresing.animations) - 1
    return {"cable": name, "joint": item.joint, "rider": r.name, "animation": TEST_ANIMATION, "notes": notes}


def view_matrix(scene, item, lens: float = 30.0):
    """A camera place (4 x 4 world matrix) that shows the cable hanging into the sea: aft of the touch-down, to
    the side and above the water, looking forward and down at the middle of the catenary (the test tour, the PC
    check and the guide picture use it)."""
    from mathutils import Matrix, Vector
    got = tdp_world(scene, item)
    if got is None:
        return None
    T, tdp = got
    u = np.array(item.sea_dir, dtype=float)
    u[2] = 0.0
    u /= max(float(np.linalg.norm(u)), 1e-12)
    side = np.cross(np.array([0.0, 0.0, 1.0]), u)
    span = float(np.linalg.norm(T - tdp))
    target = 0.5 * (T + tdp)
    target[2] = 0.5 * (T[2] + tdp[2]) * 0.6
    loc = target + u * 0.55 * span + side * 0.85 * span + np.array([0.0, 0.0, 1.0]) * (0.9 * span)
    look = Vector(tuple(target - loc)).to_track_quat("-Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation(Vector(tuple(loc))) @ look
