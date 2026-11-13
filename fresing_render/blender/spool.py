"""Drums and carousels: the cable comes off a spool layer by layer (task 0080).

A **spool** is a winch or reel drum, or a carousel, that holds the start of a cable of 4 Motion > Cables and paths
(task 0078). The rope on it is one **wound path** from its anchor (the innermost turn) outwards, layer by layer
(``core/spool.py`` has the maths). With W0 metres on it when the cable's speed joint is at 0 and p metres paid out
since, the rope on the spool runs from 0 to ``W0 - p`` along that path, and its end there is where the cable leaves
the spool. Everything follows from p alone, so it is written once as tables and costs no Python per frame:

* **The spool turns by table.** Its rotate joint follows the cable's joint "by table" (``joints.set_table``): one
  straight piece per layer on a drum (and per crossover on a Lebus drum), a few per turn on a carousel, where the
  radius changes with every turn. The turn keeps the leave point where the cable runs off towards its first sheave
  or guide (the tangent from that point to the layer's circle).
* **Followers of the layer** (``FRSpoolFollower``) follow the cable's joint by table too: a level wind slides along
  the drum with the wrap being paid out (ACROSS), a loading arm swings so its guide stays over the turn being paid
  out (ARM), a guide's swivel keeps the guide along that turn (ALONG). A guide carried by such an arm moves with it,
  and so does the point the spool's turn is worked out from.
* **The rope on the spool is drawn by the app** on an object of its own ("FR spool <name>", a child of the part that
  was clicked, so it turns with the spool): Geometry Nodes make a tube along the whole wound path (a hidden polyline
  mesh "FR spool shapes <name>", in that object's coordinates) and trim it by two driven lengths – the end at
  ``W0 - p`` (a simple expression on the cable's joint), the start at the first layer still drawn as rope (a table
  that steps at each layer). The full layers below are one solid ("FR spool solid <name>": a sleeve on a drum, a ring
  on a carousel) whose size steps with the layers (a table on its scale). The CAD coil or wire solid is hidden by an
  empty Geometry Nodes modifier; switching the spool off shows it again.
* **The cable starts where the rope leaves the spool** (``FRCable.a_kind = "SPOOL"``): ``blender/paths.py`` asks
  ``starts`` for that point at every moment it solves. It reads the spool's turned place and the payout like any
  other carrier (the spool's motion empty and the cable joint's arrow and motion are "live" slots of the cable), so
  the free span always begins exactly where the drawn rope ends – also with a cable that stays as drawn.

The rope on the spool shows the cable's look; its pattern stands still on the spool (``fr_cable_pay`` stays at
nothing paid out, the point attribute ``fr_s`` = L - W0), and joins the moving pattern of the free cable where it
leaves. Units: metres, radians; the spool's numbers are in its joint's arrow coordinates (z = the turning axis).
"""

from __future__ import annotations

import json
import math

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix

from ..core import spool as S
from ..core.words import plural
from . import build, cable_looks, flex, idprops, joints

TAG = "fr_spool"                    # on the objects this module made: the spool's name
KIND = "spool"                      # their fr_kind (logic.Tree leaves them out of the CAD tree)
MOD = "FR spool"                    # the modifier that draws the rope on the spool's own object
HIDE = "FR spool hides"             # the modifier that hides the CAD coil
TREE = "FR spool rope"
HIDE_TREE = "FR spool nothing"
VERSION = 2
S_ATTR = "fr_L"                     # on the shapes' points: the metres from the anchor (the look's s = L - Wound)
OFF = "fr_off"                      # on a made object: 1 hides it (the spool is off)
SIDES = {"DRUM": 12, "CAROUSEL": 8}
DRAWN = {"DRUM": 2, "CAROUSEL": 1}  # layers drawn as rope (the rest: one solid)
GROOVE = 1.06                       # a spiral groove's pitch in rope diameters, when none was typed
COIL_WORDS = ("COIL", "WIRE", "ROPE", "CABLE", "SPOOL", "WOUND")
_INPUTS = (("Shapes", "NodeSocketObject"), ("Wound", "NodeSocketFloat"), ("Start", "NodeSocketFloat"),
           ("End", "NodeSocketFloat"),
           ("Radius", "NodeSocketFloat"), ("Sides", "NodeSocketInt"))

_STATE = {"busy": 0, "path": {}, "poly": {}, "inputs": {}}


class SpoolError(RuntimeError):
    """A spool cannot be made or changed: the message says why, in plain words."""


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def items(scene):
    return scene.fresing.spools


def active(scene):
    s = scene.fresing
    return s.spools[s.spools_index] if 0 <= s.spools_index < len(s.spools) else None


def find(scene, name: str):
    for sp in scene.fresing.spools:
        if sp.name == name:
            return sp
    return None


def index_of(scene, sp) -> int:
    for i, x in enumerate(scene.fresing.spools):
        if x == sp:
            return i
    return -1


def _spool(scene, i: int):
    return scene.fresing.spools[i]


def label(sp) -> str:
    return sp.name or ("Carousel" if sp.kind == "CAROUSEL" else "Drum")


def of_cable(scene, item):
    """The spool (switched on) that cable ``item`` comes off, or None."""
    if item is None or not len(scene.fresing.spools):
        return None
    for sp in scene.fresing.spools:
        if sp.enabled and sp.cable == item.name:
            return sp
    return None


def _cable(scene, sp):
    from . import paths
    return paths.find(scene, sp.cable) if sp.cable else None


def _joint(scene, sp):
    j = joints.find(scene, sp.joint) if sp.joint else None
    return j if j is not None and j.frame is not None and j.motion is not None else None


def _alive(scene, ob) -> bool:
    return flex._alive(scene, ob)


def _unique(scene, base: str) -> str:
    names = {x.name for x in scene.fresing.spools}
    name, n = base, 2
    while name in names:
        name, n = f"{base} {n}", n + 1
    return name


def _mm(metres: float) -> str:
    mm = metres * 1000.0
    return f"{mm:.1f}" if abs(mm) < 10.0 else f"{mm:.0f}"


def _metres(metres: float) -> str:
    return f"{metres:.2f}" if abs(metres) < 10.0 else f"{metres:.1f}" if abs(metres) < 1000.0 else f"{metres:.0f}"


# ---------------------------------------------------------------------------
# the numbers: the core's spool and wound path
# ---------------------------------------------------------------------------

def diameter(scene, sp) -> float:
    it = _cable(scene, sp)
    return float(it.diameter) if it is not None else 0.02


def pitch_of(scene, sp) -> float:
    d = diameter(scene, sp)
    return float(sp.pitch) if sp.pitch > 0.0 else GROOVE * d


def core_spool(scene, sp, hand: int | None = None) -> S.Spool:
    """The core's description of this spool (its arrow's coordinates, metres)."""
    d = diameter(scene, sp)
    start = -1 if sp.other_side else 1
    h = int(sp.hand if hand is None else hand) or 1
    if sp.kind == "CAROUSEL":
        # (the core's r_in / r_out are the coil's inner and outer edge: its spiral runs between the rope middles)
        return S.Spool(kind="CAROUSEL", d=d, r_in=float(sp.r_in) - 0.5 * d, r_out=float(sp.r_out) + 0.5 * d,
                       a_bot=float(sp.a_bot),
                       a_top=float(sp.a_top), start=start, hand=h)
    return S.Spool(kind="DRUM", d=d, r1=float(sp.r1), a_lo=float(sp.a_lo), a_hi=float(sp.a_hi),
                   pitch=pitch_of(scene, sp), start=start, hand=h, r_max=float(sp.r_max), groove=sp.groove,
                   crossover=float(sp.crossover))


def _key(scene, sp) -> tuple:
    c = core_spool(scene, sp)
    return tuple((k, round(v, 9) if isinstance(v, float) else v) for k, v in sorted(vars(c).items()))


def path_of(scene, sp):
    """The wound path (cached by the spool's numbers)."""
    key = _key(scene, sp)
    hit = _STATE["path"].get(key)
    if hit is None:
        hit = S.wind(core_spool(scene, sp))
        if len(_STATE["path"]) > 16:
            _STATE["path"].clear()
        _STATE["path"][key] = hit
    return hit


def sag_of(scene, sp) -> float:
    d = diameter(scene, sp)
    if sp.kind == "CAROUSEL":
        return min(max(d / 60.0, 0.001), 0.005)
    return min(max(d / 40.0, 0.0003), 0.002)


def polyline_of(scene, sp):
    """(points (n, 3) in the spool frame before its phase, L (n,)): the whole wound path as drawn."""
    key = _key(scene, sp) + (("sag", round(sag_of(scene, sp), 9)),)
    hit = _STATE["poly"].get(key)
    if hit is None:
        path = path_of(scene, sp)
        hit = S.polyline(path, 0.0, float(path.total), sag_of(scene, sp))
        if len(_STATE["poly"]) > 8:
            _STATE["poly"].clear()
        _STATE["poly"][key] = hit
    return hit


def _rz(angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    m = np.eye(4)
    m[0, 0], m[0, 1], m[1, 0], m[1, 1] = c, -s, s, c
    return m


def _flip(sp) -> np.ndarray:
    """The spool frame in its joint's arrow coordinates: the same, or turned over (z the other way) when the
    arrow points away from the side the layers grow to (a carousel whose joint axis points down)."""
    m = np.eye(4)
    if int(sp.zsign) < 0:
        m[1, 1] = m[2, 2] = -1.0
    return m


def frame_cad(scene, sp, memo: dict) -> np.ndarray:
    """The spool frame (z = its axis, the layers grow along +z on a carousel), world, CAD pose."""
    return _np_cad(_joint(scene, sp).frame, memo) @ _flip(sp)


def rope_point(scene, sp, L) -> np.ndarray:
    """The drawn rope's point at L (the polyline's, as the Trim Curve cuts it), spool frame with its phase, (..., 3)."""
    pts, Ls = polyline_of(scene, sp)
    L = np.clip(np.asarray(L, dtype=float), Ls[0], Ls[-1])
    out = np.stack([np.interp(L, Ls, pts[:, k]) for k in range(3)], axis=-1)
    return out @ (_flip(sp) @ _rz(float(sp.phase)))[:3, :3].T


def _pay_map(scene, sp):
    """(top joint, k, c, sign): metres paid out = sign x (k x top's value + c)."""
    it = _cable(scene, sp)
    j = joints.find(scene, it.joint) if it is not None and it.joint else None
    if j is None:
        return None, 1.0, 0.0, 1.0
    top, k, c = joints.chain_affine(scene, j)
    return top, k, c, (-1.0 if it.reverse else 1.0)


def payout(scene, sp) -> float:
    """Metres paid out now (the cable joint's value x direction)."""
    top, k, c, sign = _pay_map(scene, sp)
    if top is None:
        return 0.0
    return sign * (k * joints.get_value(top) + c)


# ---------------------------------------------------------------------------
# the cable's start (blender/paths.py asks)
# ---------------------------------------------------------------------------

def slot_objects(scene, item) -> list:
    """[(object, role)]: what the cable's start reads – the spool's motion empty (its turn), the cable joint's arrow
    and motion empty (the payout is the motion's place along its arrow)."""
    sp = of_cable(scene, item)
    j = _joint(scene, sp) if sp is not None else None
    top = _pay_map(scene, sp)[0] if sp is not None else None
    if j is None or top is None or top.frame is None or top.motion is None:
        ob = item.a_part if _alive(scene, item.a_part) else item.part
        return [(ob, "spool")]
    return [(j.motion, "spool"), (top.frame, "pay_frame"), (top.motion, "pay_motion")]


def live_carriers(scene, item) -> set:
    """Names of the carriers of ``item``'s contacts that a layer follower moves (read where they are, also when the
    cable stays as drawn)."""
    sp = of_cable(scene, item)
    if sp is None or not len(sp.followers):
        return set()
    motions = set()
    for f in sp.followers:
        j = joints.find(scene, f.joint)
        if j is not None and j.motion is not None:
            motions.add(j.motion.name)
    out = set()
    for c in item.contacts:
        ob = c.carrier
        if ob is None:
            continue
        p = ob
        while p is not None:
            if p.name in motions:
                out.add(ob.name)
                break
            p = p.parent
    return out


def starts(scene, item, rel: np.ndarray, slots, scale: float) -> np.ndarray:
    """(F, 3): where the cable leaves its spool at each of F moments, in the cable part's coordinates. ``rel``
    (F, K, 4, 4): the slots as the cable part sees them; the spool's three slots are found by their roles."""
    roles = {sl.role: k for k, sl in enumerate(slots) if sl.role}
    sp = of_cable(scene, item)
    F = rel.shape[0]
    if sp is None or "spool" not in roles:
        return np.zeros((F, 3))
    ks = roles["spool"]
    if "pay_frame" in roles and "pay_motion" in roles:
        local = np.linalg.inv(rel[:, roles["pay_frame"]]) @ rel[:, roles["pay_motion"]]
        x = local[:, 2, 3]
    else:
        x = np.zeros(F)
    _top, k, c, sign = _pay_map(scene, sp)
    p = sign * (k * x + c)
    path = path_of(scene, sp)
    L = np.clip(float(sp.wound) - p, 0.0, float(path.total))
    pt = rope_point(scene, sp, L)                                          # (F, 3) metres, spool frame
    return np.einsum("fij,fj->fi", rel[:, ks, :3, :3], pt) + rel[:, ks, :3, 3]


# ---------------------------------------------------------------------------
# reading the spool from the model
# ---------------------------------------------------------------------------

def _turning_joint(scene, part):
    """The rotate joint that turns ``part`` (directly or through an assembly above it), or None."""
    chain = []
    p = part
    while p is not None:
        chain.append(p)
        p = p.parent
    best = None
    for j in scene.fresing.joints:
        if j.kind != "ROTATE" or j.motion is None:
            continue
        if j.motion in chain:
            k = chain.index(j.motion)
            if best is None or k < best[0]:
                best = (k, j.name)
    return joints.find(scene, best[1]) if best is not None else None


def _turning_parts(scene, j) -> list:
    """The parts that turn with the spool's joint."""
    out = []
    for m in joints.members(j):
        if m.get(build.PROP_KIND) == "part":
            out.append(m)
        out += [o for o in m.children_recursive if o.get(build.PROP_KIND) == "part"]
    return list({o.name: o for o in out}.values())


def _mesh_in(ob, m_inv: np.ndarray, memo: dict):
    """(points, triangles) of a part's mesh in the coordinates ``m_inv`` maps the world to, in the CAD pose."""
    from . import paths
    if ob.type != "MESH" or ob.data is None or not len(ob.data.vertices):
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
    v, t = flex._mesh_arrays(ob.data)
    return flex._at(m_inv @ paths._cad(ob, memo), v), t


def _is_coil(ob) -> bool:
    name = (ob.get(build.PROP_NAME, ob.name) or "").upper()
    return any(w in name for w in COIL_WORDS)


def _on_spool(scene, item, j, turning: set) -> list[int]:
    """The cable's contacts that lie on the spool (indices): on a part that turns with it, or carried by its joint."""
    out = []
    for i, c in enumerate(item.contacts):
        if (c.part is not None and c.part.name in turning) or c.carrier in (j.frame, j.motion):
            out.append(i)
    return out


def _leave_cad(scene, item, on: list[int], memo: dict):
    """Where and which way the CAD cable leaves the spool (world, CAD pose), and the point it runs to next (where it
    comes onto the first contact after the spool, else its end) with the object that carries that point."""
    from . import paths
    line, _s, res = paths._cad_path(scene, item, memo)
    if not len(line):
        raise SpoolError("The cable has no path in the CAD pose: use 'From CAD cable' in Cables and paths first")
    wheels = paths._wheels(item)
    wi = [k for k, c in enumerate(wheels) if any(item.contacts[i] == c for i in on)]
    if wi:
        last = max(wi)
        i0 = int(res["first"][last]) + int(res["counts"][last]) - 1
    else:
        last, i0 = -1, 0
    i0 = min(max(i0, 0), len(line) - 2)
    leave = line[i0]
    t = line[i0 + 1] - line[i0]
    t = t / max(float(np.linalg.norm(t)), 1e-12)
    after = last + 1
    if 0 <= after < len(wheels):                # where the cable comes onto it: what an arm holds over the turn
        k = int(res["first"][after])
        q, q_on = line[min(k, len(line) - 1)], wheels[after].carrier
    else:
        q, q_on = line[-1], item.b_part
    if float(np.linalg.norm(q - leave)) < 1e-6:            # (no free span: a hair further on, so it has a way)
        q = leave + 1e-4 * t
    return leave, t, q, q_on


def _read(scene, sp, item, j, memo: dict, hit=None) -> dict:
    """The spool's numbers from the meshes and the CAD cable (arrow coordinates). Returns a dict for the item."""
    from ..core import paths as P
    A = _np_cad(j.frame, memo)
    zsign = 1
    if sp.kind == "CAROUSEL":                   # the layers grow away from the turntable: z that way
        inv0 = np.linalg.inv(A)
        coil0 = sp.coil if _alive(scene, sp.coil) else next(
            (item.contacts[i].part for i in _on_spool(scene, item, j, {o.name for o in _turning_parts(scene, j)})
             if item.contacts[i].part is not None and item.contacts[i].part != sp.part), None)
        v_t, _t = _mesh_in(sp.part, inv0, memo)
        if coil0 is not None and len(v_t):
            v_c, _t = _mesh_in(coil0, inv0, memo)
            if len(v_c) and float(v_c[:, 2].mean()) < float(v_t[:, 2].mean()):
                zsign = -1
    with flex._quiet(sp):
        sp.zsign = zsign
    A = A @ _flip(sp)
    inv = np.linalg.inv(A)
    turning = _turning_parts(scene, j)
    names = {o.name for o in turning}
    on = _on_spool(scene, item, j, names)
    on_start = bool(on) and on[0] == 0 or (item.a_part is not None and item.a_part.name in names)
    on_end = bool(on) and on[-1] == len(item.contacts) - 1 and not on_start
    if not on_start and not on_end:             # an end drawn on the spool without a wrap: by where it is
        from . import paths
        line, _s, _res = paths._cad_path(scene, item, memo)
        if len(line):
            box = _turning_box(scene, turning, sp.coil, inv, memo)
            on_start = _near_box(flex._at(inv, line[0]), box, float(item.diameter))
            on_end = not on_start and _near_box(flex._at(inv, line[-1]), box, float(item.diameter))
    if on_end:
        return {"flip": True}                   # read from its other end (paths.read_cad asks wants_flip)
    if not on_start:
        raise SpoolError(f"The cable '{item.name}' does not start on this {sp.kind.lower()}: pick the cable that "
                         "comes off it, or click the drum or turntable it is wound on")
    leave, t, q, q_on = _leave_cad(scene, item, on, memo)
    L = flex._at(inv, leave)
    T = inv[:3, :3] @ t
    Q = flex._at(inv, q)
    rho_L, a_L = float(math.hypot(L[0], L[1])), float(L[2])
    hand = 1 if (L[0] * T[1] - L[1] * T[0]) >= 0.0 else -1
    d = float(item.diameter)
    coil = sp.coil if _alive(scene, sp.coil) else None
    if coil is None:
        cand = [item.contacts[i].part for i in on if item.contacts[i].part is not None]
        cand += [o for o in turning if _is_coil(o)]
        cand = [o for o in cand if o != sp.part and o.name in names and _is_coil(o)]
        coil = cand[0] if cand else None
    out = {"hand": hand, "coil": coil, "leave": L, "q": Q, "q_on": q_on, "on": on}
    if sp.kind == "CAROUSEL":
        if coil is not None:
            v, _t = _mesh_in(coil, inv, memo)
            rho = np.hypot(v[:, 0], v[:, 1])
            out.update(r_in=float(rho.min()) + 0.5 * d, r_out=float(rho.max()) - 0.5 * d, a_bot=float(v[:, 2].min()))
        else:
            v, _t = _mesh_in(sp.part, inv, memo)
            rho = np.hypot(v[:, 0], v[:, 1])
            out.update(r_in=0.3 * float(rho.max()), r_out=0.9 * float(rho.max()), a_bot=float(v[:, 2].max()))
        top = -np.inf
        for o in turning:
            if o == coil:
                continue
            v, _t = _mesh_in(o, inv, memo)
            if len(v):
                top = max(top, float(v[:, 2].max()))
        out["a_top"] = top if np.isfinite(top) and top > out["a_bot"] + 2 * d else out["a_bot"] + 50.0 * d
        out["r_out"] = max(out["r_out"], out["r_in"] + d)
        return out
    # drum: the first layer's middle from the barrel, the flanges from what turns with it
    v, tr = _mesh_in(sp.part, inv, memo)
    if not len(v):
        raise SpoolError(f"'{sp.part.name}' has no shape to read the drum from")
    _place, seat = P.seat(v, tr, np.zeros(3), np.array([0.0, 0.0, 1.0]), a_L, 0.5 * d)
    if seat <= 0.0:
        surf = P.surface_radius(v, tr, np.zeros(3), np.array([0.0, 0.0, 1.0]), a_L, 2.0 * d)
        seat = surf + 0.5 * d if surf > 0.0 else max(rho_L - 0.5 * d, 0.5 * d)
    # a spiral or Lebus groove: the outline read all round shows its lands; the rope lies in the groove's bottom
    land = P.surface_radius(v, tr, np.zeros(3), np.array([0.0, 0.0, 1.0]), a_L, 2.0 * d)
    if land > 0.0:
        near = np.abs(v[:, 2] - a_L) < 2.0 * d
        rho = np.hypot(v[near, 0], v[near, 1])
        outer = rho[rho > land - 0.6 * d]
        if len(outer):
            bottom = float(outer.min())
            if land - bottom > 0.1 * d:
                seat = bottom + 0.5 * d
    seat = min(seat, rho_L) if rho_L > 0.0 else seat
    lo, hi, flange = -np.inf, np.inf, np.inf
    for o in turning:
        if o == coil:
            continue
        vv, _t = _mesh_in(o, inv, memo)
        if not len(vv):
            continue
        rho = np.hypot(vv[:, 0], vv[:, 1])
        big = rho > seat + 1.5 * d
        if not big.any():
            continue
        a = vv[big, 2]
        below, above = a[a < a_L], a[a > a_L]
        if len(below):
            lo = max(lo, float(below.max()))
            flange = min(flange, float(rho[big][a < a_L].max()))
        if len(above):
            hi = min(hi, float(above.min()))
            flange = min(flange, float(rho[big][a > a_L].max()))
    if not (np.isfinite(lo) and np.isfinite(hi)):
        raise SpoolError(f"No flanges found on both sides of where the cable leaves '{sp.part.name}': is it the "
                         "drum's barrel, and does its joint turn the flanges too?")
    out.update(r1=float(seat), a_lo=lo, a_hi=hi, r_max=float(flange) - 0.5 * d if np.isfinite(flange) else
               float(seat) + 20.0 * d)
    return out


def wants_flip(scene, item, line) -> bool:
    """paths.read_cad: should this cable's reading (``line``, world, CAD pose) be turned round so that it starts on
    the spool it comes off? (Its last point is on the spool and its first is not.)"""
    sp = of_cable(scene, item)
    j = _joint(scene, sp) if sp is not None else None
    if j is None or line is None or len(line) < 2:
        return False
    memo: dict = {}
    inv = np.linalg.inv(_np_cad(j.frame, memo))
    box = _turning_box(scene, _turning_parts(scene, j), None, inv, memo)
    d = float(item.diameter)
    return not _near_box(flex._at(inv, line[0]), box, d) and _near_box(flex._at(inv, line[-1]), box, d)


def _turning_box(scene, turning, coil, inv, memo) -> tuple:
    """(largest radius, lowest and highest place along the axis) of what turns with the spool (arrow coordinates)."""
    rmax, lo, hi = 0.0, np.inf, -np.inf
    for o in turning:
        v, _t = _mesh_in(o, inv, memo)
        if len(v):
            rmax = max(rmax, float(np.hypot(v[:, 0], v[:, 1]).max()))
            lo, hi = min(lo, float(v[:, 2].min())), max(hi, float(v[:, 2].max()))
    return rmax, lo, hi


def _near_box(p, box, d: float) -> bool:
    rmax, lo, hi = box
    return float(math.hypot(p[0], p[1])) <= rmax + d and lo - d <= float(p[2]) <= hi + d


def _np_cad(ob, memo: dict) -> np.ndarray:
    from . import paths
    return paths._cad(ob, memo)


# ---------------------------------------------------------------------------
# tables: the spool's turn and its followers against the cable's joint
# ---------------------------------------------------------------------------

def _follower_joint(scene, f):
    j = joints.find(scene, f.joint) if f.joint else None
    return j if j is not None and j.frame is not None and j.motion is not None else None


def _rides_on(ob, motion) -> bool:
    p = ob
    while p is not None:
        if p == motion:
            return True
        p = p.parent
    return False


def _axis_in(scene, sp, j, memo) -> tuple:
    """A joint's axis in the spool's frame: (origin (3,), direction (3,))."""
    inv = np.linalg.inv(frame_cad(scene, sp, memo))
    m = inv @ _np_cad(j.frame, memo)
    return m[:3, 3].copy(), m[:3, 2] / max(float(np.linalg.norm(m[:3, 2])), 1e-12)


def _keys(scene, sp, path, W0: float) -> np.ndarray:
    lo, hi = W0 - float(path.total), W0
    p = np.asarray(S.breaks(path, W0, lo, hi), dtype=float)
    return np.unique(np.concatenate([p, [lo, 0.0, hi]]))


def tables(scene, sp) -> dict:
    """{joint name: (p keys, values)} for the spool's turn and each follower (internal units: rad / m), and
    "psi" (p, the leave angle) for the tests. Raises SpoolError."""
    j = _joint(scene, sp)
    if j is None:
        raise SpoolError("Its turning joint is gone: make the drum or carousel again")
    memo: dict = {}
    path = path_of(scene, sp)
    W0 = float(sp.wound)
    p = _keys(scene, sp, path, W0)
    _phi, a, r, _layer = S.at(path, W0 - p)
    _phi0, a0, r0, _l0 = S.at(path, np.array([W0]))
    a0, r0 = float(a0[0]), float(r0[0])
    Q = np.array(sp.q, dtype=float)
    q_on = bpy.data.objects.get(sp.q_on) if sp.q_on else None
    out = {}
    arm_turns = {}                                  # joint name -> its turn about the spool's +z at each key
    q_xy = np.repeat(Q[None, :2], len(p), axis=0)
    for f in sp.followers:
        fj = _follower_joint(scene, f)
        if fj is None or f.mode != "ARM":
            continue
        c, n = _axis_in(scene, sp, fj, memo)
        if abs(abs(float(n[2])) - 1.0) > 1e-3:
            raise SpoolError(f"'{fj.name}' does not turn about an axis parallel to the {sp.kind.lower()}'s: it "
                             "cannot follow the layer as an arm")
        A0 = np.array(f.point[:2], dtype=float) if any(abs(x) > 0 for x in f.point) else Q[:2]
        h2 = max(float(A0 @ A0) - r0 * r0, 0.0)
        target = np.sqrt(r * r + h2)
        turn = np.zeros(len(p))
        k0 = int(np.argmin(np.abs(p)))
        prev = 0.0
        for idx in list(range(k0, len(p))) + list(range(k0 - 1, -1, -1)):
            if idx == k0 - 1:
                prev = float(turn[k0])
            ang = S.arm_angle(np.zeros(2), c[:2], A0, float(target[idx]), prefer=prev)
            turn[idx] = prev if not np.isfinite(ang) else float(ang)
            prev = turn[idx]
        arm_turns[fj.name] = turn
        out[fj.name] = (p, turn * float(np.sign(n[2])))
        if q_on is not None and _rides_on(q_on, fj.motion):
            cs, sn = np.cos(turn), np.sin(turn)
            rel = Q[:2] - c[:2]
            q_xy = c[None, :2] + np.stack([cs * rel[0] - sn * rel[1], sn * rel[0] + cs * rel[1]], axis=1)
    rho = np.hypot(q_xy[:, 0], q_xy[:, 1])
    alpha = np.unwrap(np.arctan2(q_xy[:, 1], q_xy[:, 0]))
    psi = np.asarray(S.tangency(rho, alpha, r, int(sp.hand)), dtype=float)
    k0 = int(np.argmin(np.abs(p)))
    psi = np.unwrap(psi)
    theta = np.asarray(S.angle_table(path, W0, psi, p), dtype=float)
    out[j.name] = (p, theta * float(sp.zsign))         # (the joint turns about its arrow's z)
    out["psi"] = (p, psi)
    for f in sp.followers:
        fj = _follower_joint(scene, f)
        if fj is None or f.mode == "ARM":
            continue
        c, n = _axis_in(scene, sp, fj, memo)
        if f.mode == "ACROSS":
            if fj.kind != "SLIDE":
                raise SpoolError(f"'{fj.name}' is a rotate joint: only a slide joint can follow across the drum")
            out[fj.name] = (p, (a - float(sp.leave[2])) * float(n[2]))     # (CAD: it stands over the CAD leave)
        else:
            if fj.kind != "ROTATE" or abs(abs(float(n[2])) - 1.0) > 1e-3:
                raise SpoolError(f"'{fj.name}' must be a rotate joint with an axis parallel to the "
                                 f"{sp.kind.lower()}'s to follow along the turn")
            turn = psi - psi[k0]
            for name, at in arm_turns.items():
                aj = joints.find(scene, name)
                if aj is not None and _rides_on(fj.frame, aj.motion):
                    turn = turn - at
            out[fj.name] = (p, turn * float(np.sign(n[2])))
    return out


def _write_tables(scene, sp, tab=None) -> list[str]:
    it = _cable(scene, sp)
    _top, k, c, sign = _pay_map(scene, sp)
    if it is None or _top is None or abs(k) < 1e-300:
        raise SpoolError("The cable's speed joint is gone: check the cable in Cables and paths")
    tab = tab if tab is not None else tables(scene, sp)
    owner = f"spool:{sp.name}"
    notes = []
    for name, (p, y) in tab.items():
        if name == "psi":
            continue
        j = joints.find(scene, name)
        if j is None:
            continue
        x = sign * p                                    # the cable joint's own value at each key
        order = np.argsort(x)
        x, y = x[order], np.asarray(y, dtype=float)[order]
        keep = np.r_[True, np.diff(x) > 1e-9]
        joints.set_table(scene, j, it.joint, x[keep], y[keep], owner)
    return notes


def _drop_tables(scene, sp, names=None) -> None:
    owner = f"spool:{sp.name}"
    for j in list(scene.fresing.joints):
        if j.couple_table == owner and (names is None or j.name in names):
            joints.set_follows(scene, j, "")


# ---------------------------------------------------------------------------
# drawing the rope on the spool
# ---------------------------------------------------------------------------

def _math(b, op: str, x, y=None, z=None):
    n = b.new("ShaderNodeMath", operation=op)
    for k, v in enumerate((x, y, z)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[k].default_value = float(v)
        else:
            b.link(v, n.inputs[k])
    return n.outputs[0]


def _build_tree(ng) -> None:
    """The rope on the spool: the wound path's points (attribute ``fr_L``, metres from the anchor) from Start to End.
    Each point is kept or dropped by its own length (Trim Curve adds the pieces' lengths up in 32-bit numbers: on a
    rope of 60 m its cut came out 1.7 mm too far); the first point beyond End is moved back onto End along its piece,
    so the rope ends exactly there."""
    from . import paths
    b = flex._Nodes(ng)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
    info = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    b.link(gin.outputs["Shapes"], info.inputs["Object"])
    geo = flex._sock(info.outputs, "Geometry")
    src = b.new("GeometryNodeInputNamedAttribute", data_type="FLOAT")
    src.inputs["Name"].default_value = S_ATTR
    L = flex._sock(src.outputs, "Attribute")
    idx = b.new("GeometryNodeInputIndex").outputs[0]
    prev = _math(b, "MAXIMUM", _math(b, "SUBTRACT", idx, 1.0), 0.0)
    pos = b.new("GeometryNodeInputPosition").outputs[0]
    sp_ = b.new("GeometryNodeSampleIndex", data_type="FLOAT_VECTOR", domain="POINT")
    b.link(geo, sp_.inputs["Geometry"])
    b.link(pos, flex._sock(sp_.inputs, "Value"))
    b.link(prev, sp_.inputs["Index"])
    p_prev = flex._sock(sp_.outputs, "Value")
    sl = b.new("GeometryNodeSampleIndex", data_type="FLOAT", domain="POINT")
    b.link(geo, sl.inputs["Geometry"])
    b.link(L, flex._sock(sl.inputs, "Value"))
    b.link(prev, sl.inputs["Index"])
    l_prev = flex._sock(sl.outputs, "Value")
    end = gin.outputs["End"]
    # t = (End - L_prev) / (L - L_prev), the first point past End goes back to there
    t = _math(b, "DIVIDE", _math(b, "SUBTRACT", end, l_prev), _math(b, "MAXIMUM", _math(b, "SUBTRACT", L, l_prev), 1e-9))
    mix = b.new("ShaderNodeMix", data_type="VECTOR", clamp_factor=True)
    b.link(t, mix.inputs["Factor"])
    b.link(p_prev, mix.inputs[4])
    b.link(pos, mix.inputs[5])
    past = b.new("FunctionNodeCompare", data_type="FLOAT", operation="GREATER_THAN")
    b.link(L, past.inputs[0])
    b.link(end, past.inputs[1])
    setp = b.new("GeometryNodeSetPosition")
    b.link(geo, setp.inputs["Geometry"])
    b.link(past.outputs[0], setp.inputs["Selection"])
    b.link(mix.outputs[1], setp.inputs["Position"])
    store_l = b.new("GeometryNodeStoreNamedAttribute", data_type="FLOAT", domain="POINT")
    store_l.inputs["Name"].default_value = S_ATTR
    b.link(setp.outputs[0], store_l.inputs["Geometry"])
    b.link(past.outputs[0], store_l.inputs["Selection"])
    b.link(end, flex._sock(store_l.inputs, "Value"))
    # drop: before Start, and every point whose piece starts past End (only the first one past it stays)
    gone_after = b.new("FunctionNodeCompare", data_type="FLOAT", operation="GREATER_THAN")
    b.link(l_prev, gone_after.inputs[0])
    b.link(end, gone_after.inputs[1])
    gone_before = b.new("FunctionNodeCompare", data_type="FLOAT", operation="LESS_THAN")
    b.link(L, gone_before.inputs[0])
    b.link(gin.outputs["Start"], gone_before.inputs[1])
    gone = b.new("FunctionNodeBooleanMath", operation="OR")
    b.link(gone_after.outputs[0], gone.inputs[0])
    b.link(gone_before.outputs[0], gone.inputs[1])
    cut = b.new("GeometryNodeDeleteGeometry", domain="POINT")
    b.link(store_l.outputs[0], cut.inputs["Geometry"])
    b.link(gone.outputs[0], cut.inputs["Selection"])
    curve = b.new("GeometryNodeMeshToCurve")
    b.link(cut.outputs[0], curve.inputs["Mesh"])
    src2 = b.new("GeometryNodeInputNamedAttribute", data_type="FLOAT")
    src2.inputs["Name"].default_value = S_ATTR
    s_val = _math(b, "SUBTRACT", flex._sock(src2.outputs, "Attribute"), gin.outputs["Wound"])   # the look's s
    path, along = paths._capture(b, curve.outputs[0], s_val)
    circle = b.new("GeometryNodeCurvePrimitiveCircle")
    b.link(gin.outputs["Sides"], circle.inputs["Resolution"])
    b.link(gin.outputs["Radius"], circle.inputs["Radius"])
    profile, share = paths._capture(b, circle.outputs["Curve"], b.new("GeometryNodeSplineParameter").outputs["Factor"])
    tube = b.new("GeometryNodeCurveToMesh")
    b.link(path, tube.inputs["Curve"])
    b.link(profile, tube.inputs["Profile Curve"])
    tube.inputs["Fill Caps"].default_value = True
    phi = b.new("ShaderNodeMath", operation="MULTIPLY")
    b.link(share, phi.inputs[0])
    phi.inputs[1].default_value = 2.0 * math.pi
    cos, sin = b.new("ShaderNodeMath", operation="COSINE"), b.new("ShaderNodeMath", operation="SINE")
    b.link(phi.outputs[0], cos.inputs[0])
    b.link(phi.outputs[0], sin.inputs[0])
    xyz = b.new("ShaderNodeCombineXYZ")
    b.link(cos.outputs[0], xyz.inputs["X"])
    b.link(sin.outputs[0], xyz.inputs["Y"])
    b.link(along, xyz.inputs["Z"])
    store = b.new("GeometryNodeStoreNamedAttribute", data_type="FLOAT_VECTOR", domain="POINT")
    store.inputs["Name"].default_value = cable_looks.ATTR
    b.link(tube.outputs[0], store.inputs["Geometry"])
    b.link(xyz.outputs[0], flex._sock(store.inputs, "Value"))
    b.link(flex._slot(b, flex._shade(b, store.outputs[0])), gout.inputs[0])


def _tree():
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get(TAG) == VERSION:
        return ng
    if ng is not None:
        ng.name = TREE + " old"
    ng = bpy.data.node_groups.new(TREE, "GeometryNodeTree")
    ng[TAG] = VERSION
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for name, kind in _INPUTS:
        ng.interface.new_socket(name, in_out="INPUT", socket_type=kind)
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    _build_tree(ng)
    _STATE["inputs"].pop(TREE, None)
    return ng


def _hide_tree():
    """A tree that gives nothing: the CAD coil's shape is gone while the spool draws the rope."""
    ng = bpy.data.node_groups.get(HIDE_TREE)
    if ng is not None and ng.get(TAG) == VERSION:
        return ng
    ng = bpy.data.node_groups.new(HIDE_TREE, "GeometryNodeTree")
    ng[TAG] = VERSION
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    ng.nodes.new("NodeGroupInput")
    ng.nodes.new("NodeGroupOutput")
    return ng


def _inputs(ng) -> dict:
    out = _STATE["inputs"].get(ng.name)
    if out is None:
        out = {s.name: s.identifier for s in ng.interface.items_tree
               if getattr(s, "item_type", "SOCKET") == "SOCKET" and s.in_out == "INPUT"}
        _STATE["inputs"][ng.name] = out
    return out


def _made(scene, sp, what: str):
    """The object this spool made for ``what`` ("rope", "shapes", "solid"), or None."""
    for ob in bpy.data.objects:
        if ob.get(TAG) == sp.name and ob.get("fr_spool_role") == what:
            return ob
    return None


def _remove_made(scene, sp) -> None:
    for what in ("rope", "shapes", "solid"):
        ob = _made(scene, sp, what)
        if ob is not None:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)


COLLECTION = "FR spools"


def _own_collection(scene):
    """The collection the drawn ropes and solids are in: their own, so a model update (which sets aside the
    collections that hold only the old model) is not held up by them."""
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _hide_driver(ob, part, prop: str) -> None:
    try:
        ob.driver_remove(prop)
    except TypeError:
        pass
    drv = ob.driver_add(prop).driver
    drv.type = "MAX"
    for name, target, path in (("part", part, "hide_render"), ("off", ob, f'["{OFF}"]')):
        var = drv.variables.new()
        var.name = name
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "OBJECT"
        var.targets[0].id = target
        var.targets[0].data_path = path


def _new_made(scene, sp, what: str, parent, mesh=None):
    me = mesh or bpy.data.meshes.new(f"FR spool {what} {label(sp)}")
    ob = bpy.data.objects.new(f"FR spool {what} {label(sp)}" if what != "rope" else f"FR spool {label(sp)}", me)
    ob[TAG] = sp.name
    ob["fr_spool_role"] = what
    ob[build.PROP_KIND] = KIND
    ob[OFF] = 0
    if what == "shapes":
        flex._collection(scene).objects.link(ob)
        ob.hide_viewport = ob.hide_render = ob.hide_select = True
        return ob
    _own_collection(scene).objects.link(ob)    # (not the model's: a model update sets the model's aside)
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.hide_select = True
    ob.lock_location = ob.lock_rotation = ob.lock_scale = (True,) * 3
    _hide_driver(ob, parent, "hide_render")
    _hide_driver(ob, parent, "hide_viewport")
    return ob


def _driver(ob, path: str, source, expr: str, index: int = -1):
    try:
        ob.driver_remove(path, index)
    except TypeError:
        pass
    fc = ob.driver_add(path, index) if index >= 0 else ob.driver_add(path)
    joints._scripted(fc, source, expr)
    return fc


def _step_driver(ob, path: str, source, xs, ys, index: int = -1) -> None:
    """A driver whose value steps: ys[i] from xs[i] on (CONSTANT keys), read from ``source``'s value + 2.0."""
    xs, ys, k = joints.table_keys(xs, ys)
    fc = _driver(ob, path, source, joints.expression(k, joints.BIAS), index)
    kp = fc.keyframe_points
    kp.clear()
    n = len(xs)
    kp.add(n)
    co = np.empty(2 * n, dtype=np.float32)
    co[0::2] = np.asarray(xs, dtype=float) + joints.BIAS
    co[1::2] = ys
    kp.foreach_set("co", co)
    const = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["CONSTANT"].value
    kp.foreach_set("interpolation", np.full(n, const, dtype=np.int32))
    fc.extrapolation = "CONSTANT"


def _steps(scene, sp, path, W0: float, value) -> tuple:
    """(x keys of the cable joint, values) of a quantity that steps with the layers: ``value(L_low, solid)``."""
    _top, k, c, sign = _pay_map(scene, sp)
    lo, hi = W0 - float(path.total), W0
    pb = np.unique(np.concatenate([np.asarray(S.stack_breaks(path, W0, lo, hi, DRAWN[sp.kind]), dtype=float),
                                   [lo, hi]]))
    xb = np.sort((sign * pb - c) / k)
    edges = np.concatenate([[xb[0] - 1e6], xb, [xb[-1] + 1e6]])
    mids = 0.5 * (edges[:-1] + edges[1:])
    pm = sign * (k * mids + c)
    L_low, solid = S.stack(path, W0, pm, DRAWN[sp.kind])
    vals = np.asarray(value(np.asarray(L_low, dtype=float), np.asarray(solid, dtype=float)), dtype=float)
    keys = edges[:-1].copy()
    keep = np.r_[True, np.abs(np.diff(vals)) > 1e-9]
    return keys[keep], vals[keep]


def _owner_matrix(scene, sp, memo: dict) -> np.ndarray:
    """Spool frame (with its phase) -> the coordinates of the clicked part (what the rope object hangs on)."""
    j = _joint(scene, sp)
    return np.linalg.inv(_np_cad(sp.part, memo)) @ frame_cad(scene, sp, memo) @ _rz(float(sp.phase))


def _solid_mesh(sp, path, scene) -> bpy.types.Mesh:
    """A unit sleeve (drum: radius 1 between the flanges) or a unit ring (carousel: height 1 from the coil's
    bottom), in its own frame: scaling it in x, y (drum) or z (carousel) gives the full layers' solid."""
    d = diameter(scene, sp)
    n = 96
    t = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    if sp.kind == "DRUM":
        z0, z1 = float(sp.a_lo), float(sp.a_hi)
        rings = [(1.0, z0), (1.0, z1)]
        inner = 0.0
    else:
        z0, z1 = 0.0, 1.0
        r_lo, r_hi = S.ring_radii(core_spool(scene, sp))      # (an Archimedean spiral leaves half a band free)
        rings = [(r_hi, z0), (r_hi, z1)]
        inner = r_lo
    verts = []
    for r, z in rings:
        verts += [(r * math.cos(a), r * math.sin(a), z) for a in t]
    if inner > 0.0:
        for z in (z1, z0):
            verts += [(inner * math.cos(a), inner * math.sin(a), z) for a in t]
    faces = []
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((k, k2, n + k2, n + k))                     # outside
    if inner > 0.0:
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((n + k, n + k2, 2 * n + k2, 2 * n + k))         # top
            faces.append((2 * n + k, 2 * n + k2, 3 * n + k2, 3 * n + k))  # inside
            faces.append((3 * n + k, 3 * n + k2, k2, k))                   # bottom
    else:
        faces.append(tuple(range(n - 1, -1, -1)))
        faces.append(tuple(range(n, 2 * n)))
    me = bpy.data.meshes.new(f"FR spool solid {label(sp)}")
    me.from_pydata(verts, [], faces)
    me.shade_flat()
    me.update()
    return me


def _materials(scene, sp, ob) -> None:
    it = _cable(scene, sp)
    part = it.part if it is not None else None
    mats = [s.material for s in part.material_slots] if _alive(scene, part) else []
    me = ob.data
    # on the object, as the cable part has it: a shape made by nodes brings an empty slot of its own (flex._slot)
    # that only an object's material fills
    while len(me.materials) < max(len(mats), 1):
        me.materials.append(None)
    for k, slot in enumerate(ob.material_slots):
        if slot.link != "OBJECT":
            slot.link = "OBJECT"
        m = mats[k] if k < len(mats) else None
        if slot.material != m:
            slot.material = m
    if _alive(scene, part) and cable_looks.LOOK in part:
        idprops.store_array(ob, cable_looks.LOOK, np.asarray(part[cable_looks.LOOK], dtype=float))
    elif cable_looks.LOOK in ob:
        del ob[cable_looks.LOOK]
    ob[cable_looks.PAY] = cable_looks.PAY_BIAS


def _draw(scene, sp) -> None:
    """The rope object, its shapes, its drivers; the solid; the CAD coil hidden."""
    j = _joint(scene, sp)
    it = _cable(scene, sp)
    if j is None or it is None or not _alive(scene, sp.part):
        return
    memo: dict = {}
    path = path_of(scene, sp)
    W0 = float(sp.wound)
    M = _owner_matrix(scene, sp, memo)
    scale = float(np.cbrt(abs(np.linalg.det(M[:3, :3])))) or 1.0
    pts, Ls = polyline_of(scene, sp)
    # shapes: the polyline (with edges) in the part's coordinates, fr_s = L - W0 (the look stands still on it)
    sh = _made(scene, sp, "shapes") or _new_made(scene, sp, "shapes", None)
    n = len(pts)
    me = bpy.data.meshes.new(sh.name)
    me.vertices.add(n)
    me.vertices.foreach_set("co", np.ascontiguousarray(flex._at(M, pts), np.float32).reshape(-1))
    me.edges.add(max(n - 1, 0))
    e = np.c_[np.arange(n - 1), np.arange(1, n)].astype(np.int32)
    me.edges.foreach_set("vertices", e.reshape(-1))
    me.attributes.new(S_ATTR, "FLOAT", "POINT").data.foreach_set("value", Ls.astype(np.float32))
    me.update()
    old = sh.data
    sh.data = me
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    # the rope object and its modifier
    rope = _made(scene, sp, "rope") or _new_made(scene, sp, "rope", sp.part)
    if rope.parent != sp.part:
        rope.parent = sp.part
        rope.matrix_parent_inverse = Matrix.Identity(4)
    rope.matrix_basis = Matrix.Identity(4)
    with flex._quiet(sp):
        sp.owner = rope
    tree = _tree()
    ins = _inputs(tree)
    mod = rope.modifiers.get(MOD)
    if mod is None or mod.type != "NODES":
        mod = rope.modifiers.new(MOD, "NODES")
    if mod.node_group != tree:
        mod.node_group = tree
    flex._put(mod, ins["Shapes"], sh)
    flex._put(mod, ins["Radius"], 0.5 * diameter(scene, sp) / scale)
    flex._put(mod, ins["Sides"], SIDES[sp.kind])
    flex._put(mod, ins["Wound"], W0)
    top, k, c, sign = _pay_map(scene, sp)
    base = f'modifiers["{MOD}"].properties.inputs.'
    if top is not None and top.motion is not None:
        # End = W0 - p = W0 - sign (k x + c);  Start = the first layer still drawn as rope (steps)
        _driver(rope, base + ins["End"] + ".value", top.motion,
                joints.expression(-sign * k, W0 - sign * c))          # (metres: the points' own fr_L)
        xs, ys = _steps(scene, sp, path, W0, lambda lo, _s: lo)
        _step_driver(rope, base + ins["Start"] + ".value", top.motion, xs, ys)
    rope[OFF] = 0 if sp.enabled else 1
    _materials(scene, sp, rope)
    rope.update_tag()
    # the solid: the full layers under the rope drawn
    solid = _made(scene, sp, "solid")
    if solid is None:
        solid = _new_made(scene, sp, "solid", sp.part, _solid_mesh(sp, path, scene))
    else:
        old = solid.data
        solid.data = _solid_mesh(sp, path, scene)
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    F = M.copy()
    if sp.kind == "CAROUSEL":
        F = M @ np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, float(sp.a_bot)], [0, 0, 0, 1.0]])
    if solid.parent != sp.part:
        solid.parent = sp.part
        solid.matrix_parent_inverse = Matrix.Identity(4)
    loc, rot, _sc = Matrix([list(r) for r in F]).decompose()
    solid.matrix_basis = Matrix.LocRotScale(loc, rot, None)
    solid.scale = (scale, scale, scale)
    if top is not None and top.motion is not None:
        d = diameter(scene, sp)
        if sp.kind == "DRUM":
            r_low = max(float(sp.r1) - 0.5 * d, 1e-4)
            xs, ys = _steps(scene, sp, path, W0, lambda _lo, sol: np.where(sol > 0.0, sol, r_low))
            for i in (0, 1):
                _step_driver(solid, "scale", top.motion, xs, ys / scale, index=i)
            try:
                solid.driver_remove("scale", 2)
            except TypeError:
                pass
            solid.scale[2] = 1.0 / scale
        else:
            xs, ys = _steps(scene, sp, path, W0, lambda _lo, sol: np.maximum(sol, 1e-4))
            _step_driver(solid, "scale", top.motion, xs, ys / scale, index=2)
            for i in (0, 1):
                try:
                    solid.driver_remove("scale", i)
                except TypeError:
                    pass
            solid.scale[0] = solid.scale[1] = 1.0 / scale
    solid[OFF] = 0 if sp.enabled else 1
    _materials(scene, sp, solid)
    # the CAD coil: hidden while the spool draws it
    coil = sp.coil if _alive(scene, sp.coil) else None
    if coil is not None and coil.type == "MESH":
        h = coil.modifiers.get(HIDE)
        if h is None:
            h = coil.modifiers.new(HIDE, "NODES")
            h.node_group = _hide_tree()
        if h.show_viewport != bool(sp.enabled) or h.show_render != bool(sp.enabled):
            h.show_viewport = h.show_render = bool(sp.enabled)


def _undraw(scene, sp) -> None:
    _remove_made(scene, sp)
    coil = sp.coil if _alive(scene, sp.coil) else None
    if coil is not None:
        h = coil.modifiers.get(HIDE)
        if h is not None:
            coil.modifiers.remove(h)
    with flex._quiet(sp):
        sp.owner = None


# ---------------------------------------------------------------------------
# the cable: its start on the spool
# ---------------------------------------------------------------------------

def _attach(scene, sp) -> list[str]:
    """The cable starts where it leaves the spool: its contacts on the spool go, its start becomes the spool's."""
    from . import paths
    it = _cable(scene, sp)
    j = _joint(scene, sp)
    if it is None or j is None:
        return []
    names = {o.name for o in _turning_parts(scene, j)}
    on = _on_spool(scene, it, j, names)
    iname = paths.index_of(scene, it)
    with paths._quiet(it):
        for i in reversed(on):
            it.contacts.remove(i)
        it.a_kind = "SPOOL"
        it.a_part = j.motion
        it.a_uid = ""
        it.a_point = (0.0, 0.0, 0.0)
        it.a_free_end = False
    it = paths._cable(scene, iname)
    _recarry(scene, sp, it)
    it = paths._cable(scene, iname)
    paths.forget()
    paths._set_cad_wraps(scene, it)
    with paths._quiet(it):
        it.moving = True
    return []


def _moved_parts(scene, j) -> list:
    out = []
    for m in joints.moved_objects(scene, j):
        if m.get(build.PROP_KIND) == "part":
            out.append(m)
        out += [o for o in m.children_recursive if o.get(build.PROP_KIND) == "part"]
    return list({o.name: o for o in out}.values())


def _recarry(scene, sp, it) -> int:
    """Bends of the cable that lie on what an arm or swivel following the layer moves are carried by that joint
    from now on (a bend in the air is carried by the cable part's parent: it would stay behind when the arm swings).
    The deepest such joint takes a bend. Returns how many. (Reading the cable again puts them back.)"""
    from . import paths
    fl = []
    for f in sp.followers:
        fj = _follower_joint(scene, f)
        if fj is not None and f.mode in ("ARM", "ALONG"):
            fl.append((joints.depth(scene, fj), fj))
    if not fl:
        return 0
    fl.sort(key=lambda t: -t[0])
    memo: dict = {}
    line, _s, _res = paths._cad_path(scene, it, memo)
    if not len(line):
        return 0
    boxes = []
    for _depth, fj in fl:
        corners = []
        for o in _moved_parts(scene, fj):
            bb = np.array([list(v) for v in o.bound_box], dtype=float)
            corners.append(flex._at(paths._cad(o, memo), bb))
        if corners:
            c = np.concatenate(corners)
            boxes.append((fj, c.min(axis=0), c.max(axis=0)))
    n = 0
    for c in it.contacts:
        if c.kind != "BEND" or c.carrier is None:
            continue
        m_old = paths._cad(c.carrier, memo)
        centre = flex._at(m_old, np.array(c.centre, dtype=float))
        p = line[int(np.argmin(np.linalg.norm(line - centre, axis=1)))]       # on the arc, nearest its centre
        for fj, lo, hi in boxes:
            if np.all(p >= lo) and np.all(p <= hi):
                m_new = np.linalg.inv(paths._cad(fj.motion, memo))
                axis = m_old[:3, :3] @ np.array(c.axis, dtype=float)
                with paths._quiet(c):
                    c.centre = tuple(flex._at(m_new, centre))
                    a = m_new[:3, :3] @ axis
                    c.axis = tuple(a / max(float(np.linalg.norm(a)), 1e-12))
                    c.carrier = fj.motion
                    c.carrier_uid = ""
                n += 1
                break
    return n


def _detach(scene, sp) -> list[str]:
    """The cable as 0078 reads it again (its CAD start), the spool no longer holds it."""
    from . import paths
    it = _cable(scene, sp)
    if it is None or it.a_kind != "SPOOL":
        return []
    with paths._quiet(it):
        it.a_kind = "FIXED"
        if _alive(scene, it.part):
            it.a_part = it.part
    if not _alive(scene, it.part):
        return []
    _STATE["busy"] += 1                         # (read_cad asks after_read: this spool no longer takes it)
    try:
        return paths.read_cad(scene, it, it.part)
    except paths.PathError as exc:
        return [f"Cable '{it.name}': {exc}"]
    finally:
        _STATE["busy"] -= 1


def after_read(scene, item) -> list[str]:
    """paths.read_cad read the cable again: a spool it comes off takes its start again (and its tables, which
    depend on the cable's first contact)."""
    if _STATE["busy"]:
        return []
    sp = of_cable(scene, item)
    if sp is None:
        return []
    try:
        return _setup(scene, sp, read=True)
    except SpoolError as exc:
        return [f"Drum or carousel '{label(sp)}': {exc}"]


# ---------------------------------------------------------------------------
# making, changing, removing
# ---------------------------------------------------------------------------

def _make_joint(scene, part, axis):
    origin, direction = axis
    p = part.parent if part.parent is not None and part.parent.get(build.PROP_KIND) == "assembly" and \
        not part.parent.get(build.PROP_ROOT) else part
    name = joints.unique_name(scene, f"{part.get(build.PROP_NAME, part.name)} turn")
    j = joints.create(scene, "ROTATE", [p], origin, direction, name=name)
    return j


def add(scene, kind: str, part, cable: str, axis=None, name: str = "", coil=None):
    """A drum or carousel the cable called ``cable`` comes off. ``part``: the barrel or turntable (it, or an
    assembly it is in, must turn with a rotate joint – else ``axis`` = (origin, direction) world makes one).
    ``coil``: the CAD coil or wire solid (found by itself when None). Returns the new item. Raises SpoolError."""
    from . import paths
    if kind not in ("DRUM", "CAROUSEL"):
        raise SpoolError("Pick a drum or a carousel")
    if part is None or part.get(build.PROP_KIND) not in build.MODEL_KINDS:
        raise SpoolError("Click the drum's barrel or the carousel's turntable")
    it = paths.find(scene, cable)
    if it is None:
        raise SpoolError(f"There is no cable called '{cable}': add it in 4 Motion > Cables and paths first")
    if not paths._usable(scene, it):
        raise SpoolError(f"The cable '{cable}' has no path yet (or is switched off): use 'From CAD cable' first")
    other = of_cable(scene, it)
    if other is not None:
        raise SpoolError(f"The cable '{cable}' already comes off '{label(other)}'")
    j = _turning_joint(scene, part)
    made = False
    if j is None:
        if axis is None:
            raise SpoolError(f"'{part.get(build.PROP_NAME, part.name)}' has no rotate joint that turns it: click its "
                             "round face so the app can make one, or make the joint in 4 Motion > Joints first")
        j = _make_joint(scene, part, axis)
        made = True
    s = scene.fresing
    sp = s.spools.add()
    i = len(s.spools) - 1
    with flex._quiet(sp):
        sp.name = _unique(scene, name or ("Carousel" if kind == "CAROUSEL" else "Drum"))
        sp.kind = kind
        sp.cable = it.name
        sp.part = part
        sp.part_uid = part.get(build.PROP_UID, "")
        if coil is not None:
            sp.coil = coil
            sp.coil_uid = coil.get(build.PROP_UID, "")
        sp.joint = j.name
        sp.made_joint = made
        sp.enabled = True
    s.spools_index = i
    try:
        _setup(scene, _spool(scene, i), read=True)
    except Exception:
        sp = _spool(scene, i)
        if made:
            jj = joints.find(scene, sp.joint)
            if jj is not None:
                joints.remove(scene, jj)
        s.spools.remove(i)
        s.spools_index = min(s.spools_index, len(s.spools) - 1)
        raise
    return _spool(scene, i)


def _setup(scene, sp, read: bool = False) -> list[str]:
    """Read (with ``read``), take the cable's start, write the tables, draw. Returns notes."""
    from . import paths
    i = index_of(scene, sp)
    it = _cable(scene, sp)
    j = _joint(scene, sp)
    if it is None or j is None:
        raise SpoolError("its cable or its turning joint is gone")
    _STATE["busy"] += 1
    try:
        if read:
            memo: dict = {}
            if it.a_kind == "SPOOL":                    # read from the CAD cable as 0078 drew it
                with paths._quiet(it):
                    it.a_kind = "FIXED"
                    it.a_part = it.part
                try:
                    paths.read_cad(scene, it, it.part)
                except paths.PathError as exc:
                    raise SpoolError(str(exc)) from exc
                it = _cable(scene, sp)
            geo = _read(scene, sp, it, j, memo)
            if geo.get("flip"):                         # the cable was read from its other end: again from here
                try:
                    paths.read_cad(scene, it, it.part)
                except paths.PathError as exc:
                    raise SpoolError(str(exc)) from exc
                it = _cable(scene, sp)
                memo = {}
                geo = _read(scene, _spool(scene, i), it, j, memo)
                if geo.get("flip"):
                    raise SpoolError(f"The cable '{it.name}' could not be read from the "
                                     f"{_spool(scene, i).kind.lower()}'s end")
            sp = _spool(scene, i)
            with flex._quiet(sp):
                for key in ("r1", "a_lo", "a_hi", "r_max", "r_in", "r_out", "a_bot", "a_top"):
                    if key in geo:
                        setattr(sp, key, float(geo[key]))
                sp.hand = int(geo["hand"])
                if geo["coil"] is not None and not _alive(scene, sp.coil):
                    sp.coil = geo["coil"]
                    sp.coil_uid = geo["coil"].get(build.PROP_UID, "")
                sp.q = tuple(float(v) for v in geo["q"])
                sp.q_on = geo["q_on"].name if geo["q_on"] is not None else ""
            path = path_of(scene, sp)
            L = geo["leave"]
            with flex._quiet(sp):
                sp.leave = tuple(float(v) for v in L)
            if not sp.wound_user:
                W0 = float(S.wound_at(path, float(L[2]), float(math.hypot(L[0], L[1]))))
                with flex._quiet(sp):
                    sp.wound = W0
            sp["wound_was"] = float(sp.wound)          # (a length typed from now on is the user's)
            _attach(scene, sp)
            sp = _spool(scene, i)
        # the rope's end at W0 leaves where the tangent to the first contact touches its layer (as the CAD cable
        # does; with a length that was typed, on that length's layer)
        path = path_of(scene, sp)
        tab = tables(scene, sp)
        kp, psi = tab["psi"]
        phi, _a, _r, _k = S.at(path, np.array([float(sp.wound)]))
        with flex._quiet(sp):
            sp.phase = float(np.interp(0.0, kp, psi) - float(np.asarray(phi).reshape(-1)[0]))
            sp.capacity = float(path.total)
        notes = _write_tables(scene, sp, tab)
        sp = _spool(scene, i)
        _draw(scene, sp)
        status(scene, sp, write=True)
    finally:
        _STATE["busy"] -= 1
    it = _cable(scene, sp)
    if it is not None:
        paths.forget()
        notes += paths._rebuild(scene, it)
    return notes


def changed(scene, sp) -> None:
    """A setting changed (props.py calls this): tables, drawing, the cable's start."""
    if _STATE["busy"] or index_of(scene, sp) < 0:
        return
    i = index_of(scene, sp)
    with flex._quiet(sp):
        if sp.get("wound_was", sp.wound) != sp.wound:
            sp.wound_user = True
        sp["wound_was"] = sp.wound
    if not sp.enabled:
        _STATE["busy"] += 1
        try:
            _drop_tables(scene, sp)
            _detach(scene, sp)
            sp = _spool(scene, i)
            _undraw(scene, sp)
            with flex._quiet(sp):
                sp.problem = ""
        finally:
            _STATE["busy"] -= 1
        return
    it = _cable(scene, sp)
    try:
        _setup(scene, sp, read=it is not None and it.a_kind != "SPOOL")
    except (SpoolError, RuntimeError) as exc:
        sp = _spool(scene, i)
        with flex._quiet(sp):
            sp.problem = str(exc)


def remove(scene, index: int) -> None:
    """Take the drum or carousel off the list: the cable starts as drawn in CAD again, the coil shows its CAD shape,
    the joints that followed by its tables move by themselves (a joint the app made goes)."""
    s = scene.fresing
    if not 0 <= index < len(s.spools):
        return
    sp = s.spools[index]
    _STATE["busy"] += 1
    try:
        _drop_tables(scene, sp)
        _detach(scene, _spool(scene, index))
        sp = _spool(scene, index)
        _undraw(scene, sp)
        if sp.made_joint:
            j = joints.find(scene, sp.joint)
            if j is not None:
                joints.remove(scene, j)
    finally:
        _STATE["busy"] -= 1
    s.spools.remove(index)
    s.spools_index = min(s.spools_index, len(s.spools) - 1)


def add_follower(scene, sp, joint_name: str, mode: str = "") -> str:
    """``joint_name`` follows the layer (a level wind, a loading arm, a guide swivel). ``mode`` '' = worked out
    from the joint. Returns the mode used. Raises SpoolError."""
    j = joints.find(scene, joint_name)
    if j is None:
        raise SpoolError(f"There is no joint called '{joint_name}'")
    sj = _joint(scene, sp)
    if sj is None:
        raise SpoolError("Its turning joint is gone")
    if j == sj:
        raise SpoolError("That is the drum's or carousel's own joint: it follows already")
    if any(f.joint == j.name for f in sp.followers):
        raise SpoolError(f"'{j.name}' follows the layer already")
    memo: dict = {}
    c, n = _axis_in(scene, sp, j, memo)
    if not mode:
        if j.kind == "SLIDE":
            mode = "ACROSS"
        else:
            # a swivel rides on an arm that follows already, or stands right at the cable's guide: along the turn
            arms = [_follower_joint(scene, f) for f in sp.followers if f.mode == "ARM"]
            on_arm = any(a is not None and _rides_on(j.frame, a.motion) for a in arms)
            q = np.array(sp.q, dtype=float)
            near = float(np.hypot(*(c[:2] - q[:2]))) < 0.25 * max(float(np.hypot(*q[:2])), 1e-6)
            mode = "ALONG" if on_arm or near else "ARM"
    if mode == "ACROSS" and j.kind != "SLIDE":
        raise SpoolError(f"'{j.name}' is a rotate joint: only a slide joint can follow across the drum")
    if mode in ("ARM", "ALONG") and (j.kind != "ROTATE" or abs(abs(float(n[2])) - 1.0) > 1e-3):
        raise SpoolError(f"'{j.name}' must be a rotate joint whose axis is parallel to the {sp.kind.lower()}'s")
    i = index_of(scene, sp)
    f = sp.followers.add()
    with flex._quiet(sp):
        f.joint, f.mode = j.name, mode
        f.point = (0.0, 0.0, 0.0)
        sp.followers_index = len(sp.followers) - 1
    try:
        _setup(scene, _spool(scene, i))
    except Exception:
        sp = _spool(scene, i)
        sp.followers.remove(len(sp.followers) - 1)
        raise
    return mode


def remove_follower(scene, sp, index: int) -> None:
    if not 0 <= index < len(sp.followers):
        return
    i = index_of(scene, sp)
    name = sp.followers[index].joint
    _STATE["busy"] += 1
    try:
        _drop_tables(scene, sp, {name})
        sp = _spool(scene, i)
        sp.followers.remove(index)
        sp.followers_index = min(sp.followers_index, len(sp.followers) - 1)
    finally:
        _STATE["busy"] -= 1
    _setup(scene, _spool(scene, i))


# ---------------------------------------------------------------------------
# what the panel shows; warnings for Build
# ---------------------------------------------------------------------------

def fleet(scene, sp) -> tuple:
    """(angle at the a_lo flange, at the a_hi flange) in rad, drum only; with a level wind the point it runs to moves
    along with the wrap."""
    if sp.kind != "DRUM":
        return 0.0, 0.0
    path = path_of(scene, sp)
    q = np.array(sp.q, dtype=float)
    across = next((f for f in sp.followers if f.mode == "ACROSS" and _follower_joint(scene, f) is not None), None)
    if across is None:
        lo, hi = S.fleet_angles(path, q)
        return float(lo), float(hi)
    d = diameter(scene, sp)
    out = []
    for a_end in (float(sp.a_lo) + 0.5 * d, float(sp.a_hi) - 0.5 * d):
        qq = q.copy()
        qq[2] += a_end - float(sp.leave[2])         # (the level wind stands over the CAD leave place at its 0)
        out.append(float(np.asarray(S.fleet_angles(path, qq))[0 if a_end < 0.5 * (sp.a_lo + sp.a_hi) else 1]))
    return out[0], out[1]


def flange_name(sp, at_lo: bool) -> str:
    """Which flange, in the panel's words: the one the first layer starts from, or the other."""
    starts_lo = not sp.other_side
    return "at the flange the first layer starts from" if at_lo == starts_lo else "at the other flange"


def fleet_text(sp, lo: float, hi: float) -> str:
    return f"fleet angle {math.degrees(max(lo, hi)):.1f}° {flange_name(sp, lo >= hi)}"


def status(scene, sp, write: bool = True) -> tuple[str, str]:
    """(text, icon) for the panel, also written into the item's state when Blender lets it (not while a panel
    draws: the panel shows the text, the state follows at the next change)."""
    if not sp.enabled:
        return "Off: the coil shows as in the CAD file", "HIDE_ON"
    it = _cable(scene, sp)
    if it is None:
        return "Its cable is gone: remove it", "ERROR"
    if _joint(scene, sp) is None:
        return "Its turning joint is gone: remove it", "ERROR"
    path = path_of(scene, sp)
    p = payout(scene, sp)
    W = float(sp.wound)
    on = W - p
    st = S.status(path, W, p)
    _phi, _a, _r, layer = S.at(path, np.array([min(max(on, 0.0), float(path.total))]))
    lo, hi = fleet(scene, sp)
    problem = ""
    if st == "empty":
        problem = f"runs empty: {_metres(-on)} m more is paid out than it held"
    elif st == "full":
        problem = f"overfills: {_metres(on - float(path.total))} m more than it holds ({_metres(path.total)} m)"
    elif sp.kind == "DRUM" and max(lo, hi) > float(sp.fleet_limit) + 1e-9:
        problem = (f"{fleet_text(sp, lo, hi)} (more than "
                   f"{math.degrees(sp.fleet_limit):.1f}°): the cable may not spool well – add a level wind, or move "
                   "the sheave further away")
    k, n = int(np.asarray(layer).reshape(-1)[0]) + 1, int(path.layer_count)
    if write:
        try:
            with flex._quiet(sp):
                if sp.problem != problem:
                    sp.problem = problem
                if sp.layer != k or sp.layers != n:
                    sp.layer, sp.layers = k, n
                if abs(sp.on_spool - on) > 1e-6 or abs(sp.capacity - float(path.total)) > 1e-6:
                    sp.on_spool, sp.capacity = float(on), float(path.total)
                if abs(sp.fleet_lo - lo) > 1e-9 or abs(sp.fleet_hi - hi) > 1e-9:
                    sp.fleet_lo, sp.fleet_hi = lo, hi
        except AttributeError:                  # (drawing: "Writing to ID classes in this context is not allowed")
            pass
    if problem:
        return problem[0].upper() + problem[1:], "ERROR"
    return (f"{_metres(on)} m on it, layer {k} of {n}; holds {_metres(path.total)} m", "CHECKMARK")


def after_draw(scene, item) -> None:
    """paths.py drew the cable again (a pose, a frame of a built animation): its spool's state follows."""
    sp = of_cable(scene, item)
    if sp is not None and not _STATE["busy"]:
        try:
            status(scene, sp)
        except Exception:                           # (never in the way of drawing the cable)
            pass


def bake(scene, anim) -> list[str]:
    """Warnings for Build: a spool that runs empty or overfills along the animation, a fleet angle."""
    if not len(scene.fresing.spools):
        return []
    out = []
    for sp in scene.fresing.spools:
        if not sp.enabled:
            continue
        try:
            top, k, c, sign = _pay_map(scene, sp)
            if top is None:
                continue
            path = path_of(scene, sp)
            vals = [joints.get_value(top)]
            ad = top.motion.animation_data if top.motion is not None else None
            if ad is not None and ad.action is not None:
                from bpy_extras import anim_utils
                cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot) if ad.action_slot else None
                fc = cb.fcurves.find(f'["{joints.VALUE}"]') if cb is not None else None
                if fc is not None:
                    co = np.empty(2 * len(fc.keyframe_points), np.float32)
                    fc.keyframe_points.foreach_get("co", co)
                    vals += list(co[1::2])
            p = sign * (k * np.asarray(vals, dtype=float) + c)
            on = float(sp.wound) - p
            if (on < -1e-6).any():
                out.append(f"Drum or carousel '{label(sp)}' runs empty in this animation: {_metres(-on.min())} m "
                           "more is paid out than it holds")
            elif (on > float(path.total) + 1e-6).any():
                out.append(f"Drum or carousel '{label(sp)}' overfills in this animation")
            lo, hi = fleet(scene, sp)
            if sp.kind == "DRUM" and max(lo, hi) > float(sp.fleet_limit) + 1e-9:
                out.append(f"Drum '{label(sp)}': {fleet_text(sp, lo, hi)} (more than "
                           f"{math.degrees(sp.fleet_limit):.1f}°)")
        except Exception as exc:                    # a Build never fails over a spool
            out.append(f"Drum or carousel '{label(sp)}' could not be checked ({exc or type(exc).__name__})")
    return out


def coil_parts(scene) -> list:
    return [sp.coil for sp in scene.fresing.spools if sp.enabled and _alive(scene, sp.coil)]


def _clash_hook(scene):
    """The clash check leaves the CAD coils out (the app draws the rope on the spool: it lies on its drum)."""
    if not len(scene.fresing.spools):
        return [], []
    return [], coil_parts(scene)


# ---------------------------------------------------------------------------
# model update
# ---------------------------------------------------------------------------

def after_model_update(scene, by_uid: dict, mapping: dict) -> list[str]:
    """The model was replaced: every spool goes to the matching new parts (by part ID) before the cables are read
    again (paths.after_model_update then reads each cable, and ``after_read`` sets its spool up again)."""
    s = scene.fresing
    if not len(s.spools):
        return []
    notes = []
    forget()
    from . import paths
    for i in range(len(s.spools)):
        sp = s.spools[i]
        _STATE["busy"] += 1
        try:
            _drop_tables(scene, sp)                 # (the cables are read as plain CAD cables; _setup writes them again)
        finally:
            _STATE["busy"] -= 1
        sp = s.spools[i]
        it = _cable(scene, sp)
        if it is not None and it.a_kind == "SPOOL":    # read again as the plain CAD cable; after_read takes it again
            with paths._quiet(it):
                it.a_kind = "FIXED"
                it.a_part = None
                it.a_uid = ""
        _remove_made(scene, sp)                     # (they hung on the old parts)
        part = flex._new_object(scene, sp.part_uid, by_uid, mapping) if sp.part_uid else None
        coil = flex._new_object(scene, sp.coil_uid, by_uid, mapping) if sp.coil_uid else None
        with flex._quiet(sp):
            sp.part, sp.coil, sp.owner = part, coil, None
        if part is None:
            notes.append(f"Drum or carousel '{label(sp)}': its part is gone in the new revision")
            with flex._quiet(sp):
                sp.enabled = False
        elif _joint(scene, sp) is None:
            notes.append(f"Drum or carousel '{label(sp)}': its turning joint is gone in the new revision")
            with flex._quiet(sp):
                sp.enabled = False
    return notes


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------

def forget() -> None:
    _STATE["path"].clear()
    _STATE["poly"].clear()
    _STATE["inputs"].clear()


@persistent
def _on_load(_dummy=None):
    forget()


def _handlers():
    h = bpy.app.handlers
    return ((h.load_post, _on_load), (h.undo_post, _on_load), (h.redo_post, _on_load))


def register() -> None:
    from . import clash
    for lst, fn in _handlers():
        if fn not in lst:
            lst.append(fn)
    if _clash_hook not in clash.HOOKS:
        clash.HOOKS.append(_clash_hook)


def unregister() -> None:
    from . import clash
    for lst, fn in _handlers():
        while fn in lst:
            lst.remove(fn)
    while _clash_hook in clash.HOOKS:
        clash.HOOKS.remove(_clash_hook)
    forget()


def summary(scene, sp) -> str:
    """One line for a report: kind, layers, length."""
    return (f"{label(sp)}: {sp.kind.lower()}, {plural(int(sp.layers), 'layer')}, {_metres(sp.on_spool)} m on it, "
            f"holds {_metres(sp.capacity)} m")


# ---------------------------------------------------------------------------
# the test model (tests, the test tour, the PC check)
# ---------------------------------------------------------------------------

TEST_ANIMATION = "Spooling"


def set_up_test_model(scene) -> dict:
    """The set-up of the spooling test model (test_spool.step, tools/make_test_spool.py), already imported: the
    joints "Drum turn" (about the drum's axis), "Level wind" (along it), "Carousel turn" and "Arm slew"; the cables
    "Wire" (steel wire rope) and "Power cable" read from the CAD; the drum "Drum" with its level wind following the
    layer, the carousel "Carousel" with its arm following; the animation "Spooling" (8 s: 6 m of wire, 6 m of cable).
    Not built. Returns the names of what was made."""
    from mathutils import Vector

    from . import paths

    def named(name):
        for ob in scene.objects:
            if ob.get(build.PROP_NAME) == name:
                return ob
        raise SpoolError(f"The model has no part '{name}'.")

    root = build.model_root_of(named("DRUM.ASM")) or named("DRUM.ASM")
    m = root.matrix_world
    mm = 0.001

    def at(x, y, z):
        return m @ Vector((x * mm, y * mm, z * mm))

    def way(x, y, z):
        return (m.to_3x3() @ Vector((x, y, z))).normalized()

    with joints._batch(scene):
        joints.create(scene, "ROTATE", [named("DRUM.ASM")], at(0, 0, 450), way(0, 1, 0), name="Drum turn")
        joints.create(scene, "SLIDE", [named("LEVEL WIND.ASM")], at(800, 0, 300), way(0, 1, 0), name="Level wind")
        joints.create(scene, "ROTATE", [named("CAROUSEL.ASM")], at(3000, 0, 0), way(0, 0, 1), name="Carousel turn")
        joints.create(scene, "ROTATE", [named("ARM.ASM")], at(4300, 0, 0), way(0, 0, 1), name="Arm slew")
    bpy.context.view_layer.update()
    out = {"joints": ["Drum turn", "Level wind", "Carousel turn", "Arm slew"], "notes": []}
    for cname, part, look in (("Wire", "WIRE ROPE", "ROPE"), ("Power cable", "POWER CABLE", "POWER")):
        item = paths.add_cable(scene, cname)
        with paths._quiet(item):
            item.look = look
        item["look_was"] = look
        out["notes"] += paths.read_cad(scene, item, named(part))
        out["joints"].append(paths.find(scene, cname).joint)
    drum = add(scene, "DRUM", named("WINCH DRUM"), "Wire", name="Drum", coil=named("WIRE ON DRUM"))
    add_follower(scene, find(scene, drum.name), "Level wind")
    car = add(scene, "CAROUSEL", named("TURNTABLE"), "Power cable", name="Carousel", coil=named("CABLE COIL"))
    add_follower(scene, find(scene, car.name), "Arm slew")
    a = scene.fresing.animations.add()
    a.name, a.tail, a.fps = TEST_ANIMATION, 0.0, "25"
    for cname in ("Wire", "Power cable"):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", paths.find(scene, cname).joint, 0.0, 8.0, "LINEAR"
        b.use_from = True
        b.to_dist = 6.0
    scene.fresing.animations_index = len(scene.fresing.animations) - 1
    out.update(spools=["Drum", "Carousel"], cables=["Wire", "Power cable"], animation=TEST_ANIMATION)
    return out
