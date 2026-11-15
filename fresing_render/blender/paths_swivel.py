"""A sheave on a swivel follows its wire (task 0125).

A sheave head that turns about a post (a swivel: a rotate joint whose motion carries the sheave's own turn joint
and the sheave) is turned so the wire leaving the sheave lies in the sheave's plane. The contact names the swivel's
rotate joint (``FRCableContact.swivel``).

One closed form, no iteration. In the swivel's arrow (frame) coordinates the axis is local z through the origin; the
motion empty turns about it by the joint's value v. The sheave's centre C and axis n are fixed in the motion's
coordinates (C_m, n_m). P is where the wire goes after the sheave on the side away from the post's axis (the
neighbour – start / end point or the next wheel's centre – least parallel to the axis seen from it). The wire leaving
the sheave towards P lies in the sheave's plane when P does:

    n(v) . (P - C(v)) = 0   <=>   n_m . Rz(-v) P_f = n_m . C_m

With P_f = (rho cos phi, rho sin phi, z): |n_xy| rho cos(phi - v - alpha) + n_z z = n_m . C_m (alpha = the angle of
n_m in xy) – two answers; the one that puts C on P's side of the axis is taken. For a sheave whose plane holds the
post's axis this is "turn C's angle onto P's angle".

Live (no animation built): ``live`` sets each swivel for the pose shown. At Build: ``before_read`` reads P and the
swivel's arrow at every frame, works the values out at once (unwrapped: never a jump of a turn) and keys the joint
one key per frame (tagged ``TAG`` on its motion empty); a coupling of the swivel is put aside meanwhile (``WAS``)
and put back by ``after_clear``.
"""

from __future__ import annotations

import json
import math

import numpy as np

from . import joints

TAG = "fr_cable_swivel"                 # on a swivel's motion empty while Build's keys turn it: the cables' names
WAS = "fr_swivel_was"                   # on it too: the coupling it had before Build (JSON), put back at Clear keys
SET_TOL = 1e-5                          # rad: a live swivel is only set when it is further off than this
SMALL = 1e-6                            # m: C or P this near the post's axis: the swivel cannot help


def _np(m) -> np.ndarray:
    return np.array(m, dtype=float)


def _world(ob) -> np.ndarray:
    from . import flex
    return _np(flex._world(ob))


def _under(ob, motion) -> bool:
    """Is ``ob`` carried by ``motion`` (one of its parents)?"""
    p = ob
    for _ in range(256):
        if p is None:
            return False
        if p == motion:
            return True
        p = p.parent
    return False


def _swivels(scene) -> list:
    """(cable, contact index in the wheels, contact, swivel joint) for every enabled cable's sheave with a swivel."""
    from . import paths
    out = []
    for it in scene.fresing.cables:
        if not it.enabled or not paths._usable(scene, it):
            continue
        for k, c in enumerate(paths._wheels(it)):
            if c.kind != "SHEAVE" or not c.swivel:
                continue
            j = joints.find(scene, c.swivel)
            if j is None or j.kind != "ROTATE" or j.motion is None or j.frame is None:
                continue
            if c.carrier is None or not _under(c.carrier, j.motion):
                continue                        # (the sheave does not sit on that swivel: it cannot turn it)
            out.append((it, k, c, j))
    return out


def _candidates(item, k: int, motion) -> list:
    """The places the wire goes to beside wheel ``k``: (object, point in its coordinates) – the wheel before / after
    (its centre) or the start / end point. Places carried by the swivel itself are left out (they turn with it)."""
    from . import paths
    wheels = paths._wheels(item)
    out = []
    if k > 0:
        w = wheels[k - 1]
        out.append((w.carrier, np.array(w.centre, dtype=float)))
    elif item.a_kind == "FIXED" and item.a_part is not None:
        out.append((item.a_part, np.array(item.a_point, dtype=float)))
    if k < len(wheels) - 1:
        w = wheels[k + 1]
        out.append((w.carrier, np.array(w.centre, dtype=float)))
    elif item.b_kind == "FIXED" and item.b_part is not None:
        out.append((item.b_part, np.array(item.b_point, dtype=float)))
    return [(ob, p) for ob, p in out if ob is not None and not _under(ob, motion)]


def _at(m: np.ndarray, p: np.ndarray) -> np.ndarray:
    """``m`` (..., 4, 4) applied to the point ``p`` (3,)."""
    return np.einsum("...ij,j->...i", m[..., :3, :3], p) + m[..., :3, 3]


def _pick(frame_w: np.ndarray, cands: list, world) -> tuple | None:
    """The candidate least parallel to the swivel's axis, seen from a point on it (``frame_w``: the arrow, world)."""
    a, u = frame_w[:3, 3], frame_w[:3, 2] / max(np.linalg.norm(frame_w[:3, 2]), 1e-12)
    best, low = None, 2.0
    for ob, p in cands:
        d = _at(world(ob), p) - a
        n = float(np.linalg.norm(d))
        if n < SMALL:
            continue
        par = abs(float(d @ u)) / n
        if par < low:
            best, low = (ob, p), par
    return best


def _sheave_in_motion(c, j) -> tuple:
    """(C_m, n_m): the sheave's centre and axis in the swivel's motion coordinates (fixed: the sheave rides on it).
    Seen from the arrow with the joint at v they are Rz(v) C_m, Rz(v) n_m."""
    to_m = np.linalg.inv(_world(j.motion)) @ _world(c.carrier)
    cm = _at(to_m, np.array(c.centre, dtype=float))
    n = to_m[:3, :3] @ np.array(c.axis, dtype=float)
    return cm, n / max(float(np.linalg.norm(n)), 1e-12)


def _motion_in_frame(j) -> np.ndarray:
    """The motion empty's place in its arrow's coordinates with the joint at 0 (the identity, unless it was put
    elsewhere): what Rz(v) is applied to."""
    return _np(j.motion.matrix_parent_inverse) if j.motion.parent == j.frame else np.eye(4)


def values(cm: np.ndarray, nm: np.ndarray, pf: np.ndarray) -> np.ndarray:
    """(F,) the swivel's value (rad, wrapped to ±pi) that puts each P (``pf`` (F, 3), in the arrow's coordinates)
    in the sheave's plane on the sheave's side of the axis; NaN where the swivel cannot help (P or C on the axis,
    the sheave lying flat across the axis). ``cm``, ``nm``: the sheave's centre and axis in the motion's coordinates
    (joint at 0)."""
    pf = np.atleast_2d(np.asarray(pf, dtype=float))
    rho = np.hypot(pf[:, 0], pf[:, 1])
    phi = np.arctan2(pf[:, 1], pf[:, 0])
    gamma = math.atan2(cm[1], cm[0])            # where C lies round the axis at 0
    nxy = math.hypot(nm[0], nm[1])
    out = np.full(len(pf), np.nan)
    if math.hypot(cm[0], cm[1]) < SMALL:
        return out
    simple = phi - gamma                        # C turned onto P's side, square to nothing
    if nxy < 1e-6:                              # the sheave lies flat across the axis: no turn puts P in its plane
        return out
    alpha = math.atan2(nm[1], nm[0])
    d = float(nm @ cm)
    with np.errstate(divide="ignore", invalid="ignore"):
        k = np.clip((d - nm[2] * pf[:, 2]) / (nxy * rho), -1.0, 1.0)
    t = np.arccos(k)
    v1, v2 = phi - alpha - t, phi - alpha + t
    off1 = np.abs(np.angle(np.exp(1j * (v1 - simple))))
    off2 = np.abs(np.angle(np.exp(1j * (v2 - simple))))
    v = np.where(off1 <= off2, v1, v2)
    ok = rho > SMALL
    out[ok] = np.angle(np.exp(1j * v[ok]))
    return out


def _target(scene, item, k: int, c, j) -> float | None:
    """The swivel's value for the pose shown (nearest its value now), or None."""
    cands = _candidates(item, k, j.motion)
    fw = _world(j.frame)
    got = _pick(fw, cands, _world)
    if got is None:
        return None
    ob, p = got
    m0 = fw @ _motion_in_frame(j)               # the motion's place with the joint at 0
    pf = _at(np.linalg.inv(m0), _at(_world(ob), p))
    cm, nm = _sheave_in_motion(c, j)
    v = float(values(cm, nm, pf[None])[0])
    if not math.isfinite(v):
        return None
    now = joints.get_value(j)
    return now + math.remainder(v - now, 2.0 * math.pi)


def _keyed_by_others(j) -> bool:
    """Keys on the swivel's value that are not ours (an animation step, keys by hand)."""
    from . import paths
    if j.motion.get(TAG):
        return False
    return any(fc.data_path == joints.COUPLING_PATH for fc in paths._fcurves(j.motion))


def _coupled(j) -> bool:
    if not j.follows:
        return False
    fc = joints._coupling_fcurve(j)
    return fc is not None and not fc.mute


def live(scene) -> bool:
    """No animation built: every swivel turned for the pose shown. True when one was set."""
    try:
        if scene.fresing.anim_baked or not len(scene.fresing.cables):
            return False
        wrote = False
        for it, k, c, j in _swivels(scene):
            if _coupled(j) or _keyed_by_others(j):
                continue                        # (its leader or its keys decide)
            v = _target(scene, it, k, c, j)
            if v is None or abs(v - joints.get_value(j)) <= SET_TOL:
                continue
            joints.set_value(j, v, use_limits=False)
            wrote = True
        return wrote
    except Exception as exc:                    # never break the cables' update
        print("Fresing Render: swivel update failed:", exc)
        return False


def _stepped(scene, j) -> bool:
    """Does a step of the animation being built (else the chosen one) move the swivel?"""
    s = scene.fresing
    a = s.animations.get(s.anim_baked) if s.anim_baked else None
    if a is None and 0 <= s.animations_index < len(s.animations):
        a = s.animations[s.animations_index]
    return a is not None and any(b.enabled and b.joint == j.name for b in a.blocks)


def _put_aside(scene, j) -> None:
    """The swivel stops following its leader for the Build; what it followed is remembered on its motion empty."""
    if not j.follows or WAS in j.motion:
        return
    j.motion[WAS] = json.dumps({"follows": j.follows, "ratio": float(j.couple_ratio), "offset": joints.offset(j)})
    joints._free(scene, j)                      # (not set_follows: that would take the Build's keys off)


def before_read(scene, first: int, frames: int) -> list[str]:
    """Build: every swivel keyed to its wire, one key per frame, before the cables' places are read. Returns
    warnings."""
    notes: list[str] = []
    try:
        todo = _swivels(scene)
        if not todo:
            return notes
        from . import animation, flex, paths
        plans = {}
        for it, k, c, j in todo:
            if j.name in plans:
                continue
            if j.couple_table:
                notes.append(f"Swivel '{j.name}' of '{paths.label(it)}' follows '{j.follows}' by a table: it keeps "
                             "that motion and does not turn to the cable")
                plans[j.name] = None
                continue
            if _stepped(scene, j) or _keyed_by_others(j):
                notes.append(f"Swivel '{j.name}' of '{paths.label(it)}' is moved by the animation: it does not "
                             "turn to the cable")
                plans[j.name] = None
                continue
            cands = _candidates(it, k, j.motion)
            got = _pick(_world(j.frame), cands, _world)
            if got is None:
                plans[j.name] = None
                continue
            plans[j.name] = (it.name, c, j.name, got)
        work = [p for p in plans.values() if p is not None]
        if not work:
            return notes
        for _cab, _c, jn, _got in work:         # couplings aside first (they change the motion's drivers)
            _put_aside(scene, joints.find(scene, jn))
        if frames > 1:
            obs = {}
            for _cab, _c, jn, (ob, _p) in work:
                j = joints.find(scene, jn)
                obs[j.frame.name], obs[ob.name] = j.frame, ob
            mats = flex.read_places(scene, list(obs.values()), first, frames, keep_shown=False)
        else:
            mats = None
        for cab, c, jn, (ob, p) in work:
            j = joints.find(scene, jn)
            cm, nm = _sheave_in_motion(c, j)       # (C(v) = Rz(v) C_m in the arrow's coordinates)
            mi = _motion_in_frame(j)
            if mats is None:
                fw, pw = _world(j.frame)[None], _at(_world(ob), p)[None]
            else:
                fw, pw = mats[j.frame.name], _at(mats[ob.name], p)
            m0 = fw @ mi
            pf = np.einsum("fij,fj->fi", np.linalg.inv(m0), np.concatenate([pw, np.ones((len(pw), 1))], axis=1))[:, :3]
            v = values(cm, nm, pf)
            good = np.isfinite(v)
            if not good.any():
                continue
            if not good.all():                  # (P on the axis for a while: the swivel stays where it was)
                idx = np.arange(len(v))
                last = np.maximum.accumulate(np.where(good, idx, -1))
                nxt = np.where(last < 0, np.argmax(good), last)
                v = v[nxt]
            v = np.unwrap(v)
            now = joints.get_value(j)
            v = v + 2.0 * math.pi * round((now - v[0]) / (2.0 * math.pi))
            if len(v) == 1:
                joints.set_value(j, float(v[0]), use_limits=False)
            else:
                cb = animation._channelbag(j.motion, "OBJECT")
                animation._write(cb, joints.COUPLING_PATH, 0, [(first + f, float(x), "LINEAR", "AUTO")
                                                                 for f, x in enumerate(v)])
            j.motion[TAG] = cab
            if joints.outside_limits(j, float(v.min())) or joints.outside_limits(j, float(v.max())):
                notes.append(f"Swivel '{j.name}' of '{cab}' would turn beyond its limits to follow the cable")
        flex.drop_read()                        # (places read before the swivels were keyed are old now)
        try:                                    # (the frame shown with the new values, for what is read now)
            import bpy
            (bpy.context.view_layer if bpy.context.scene == scene else scene.view_layers[0]).update()
        except Exception:
            pass
    except Exception as exc:                    # a Build never fails over a swivel
        notes.append(f"The swivels could not be turned to their cables ({exc or type(exc).__name__})")
    return notes


def after_clear(scene) -> None:
    """'Clear keys': a swivel's coupling put aside at Build is put back, the tags go; the swivels follow live."""
    try:
        for j in list(scene.fresing.joints):
            m = j.motion
            if m is None or (TAG not in m and WAS not in m):
                continue
            name = j.name
            was = m.get(WAS)
            for key in (TAG, WAS):
                if key in m:
                    del m[key]
            if was:
                d = json.loads(was)
                j = joints.find(scene, name)
                if j is not None and joints.find(scene, d.get("follows", "")) is not None:
                    try:
                        joints.set_follows(scene, j, d["follows"], ratio=d.get("ratio"), offset_value=d.get("offset"))
                    except RuntimeError as exc:
                        print(f"Fresing Render: swivel '{name}' could not follow '{d['follows']}' again:", exc)
        live(scene)
    except Exception as exc:
        print("Fresing Render: swivel clear failed:", exc)
