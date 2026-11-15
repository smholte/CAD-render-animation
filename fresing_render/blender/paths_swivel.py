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

Live (no animation built): ``live`` sets each swivel for the pose shown. At Build no extra pass through the frames:
paths.py reads ``objects`` (the swivels' arrows and motions, the places their wires go to) in its own one pass, then
``after_read`` works the values out from those places at once (unwrapped: never a jump of a turn), keys the joint one
key per frame (tagged ``TAG`` on its motion empty; a coupling of the swivel put aside meanwhile, ``WAS``, put back by
``after_clear``) and moves what rides on the swivel in the places read, as if they had been read with the keys.
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


def objects(scene) -> list:
    """Build: the objects whose world matrix at every frame ``after_read`` needs (each swivel's arrow and motion
    empty, the places its wire goes to). paths.py reads them in its one pass through the frames."""
    out = {}
    try:
        for it, k, _c, j in _swivels(scene):
            out[j.frame.name], out[j.motion.name] = j.frame, j.motion
            for ob, _p in _candidates(it, k, j.motion):
                out[ob.name] = ob
    except Exception as exc:
        print("Fresing Render: swivel objects failed:", exc)
    return list(out.values())


def before_read(scene, first: int, frames: int) -> list[str]:
    """(Kept until paths.py calls ``objects`` / ``after_read``: nothing to do before the read any more.)"""
    return []


def _rz(v: np.ndarray) -> np.ndarray:
    """(F, 4, 4) turns about z by ``v`` (F,)."""
    out = np.zeros((len(v), 4, 4))
    c, s = np.cos(v), np.sin(v)
    out[:, 0, 0], out[:, 0, 1], out[:, 1, 0], out[:, 1, 1] = c, -s, s, c
    out[:, 2, 2] = out[:, 3, 3] = 1.0
    return out


def _plan(scene, notes: list) -> list:
    """(cable name, contact, joint name, (object, point)) for every swivel that turns to its wire at this Build."""
    from . import paths
    plans: dict = {}
    for it, k, c, j in _swivels(scene):
        if j.name in plans:
            continue
        plans[j.name] = None
        if j.couple_table:
            notes.append(f"Swivel '{j.name}' of '{paths.label(it)}' follows '{j.follows}' by a table: it keeps that "
                         "motion and does not turn to the cable")
        elif _stepped(scene, j) or _keyed_by_others(j):
            notes.append(f"Swivel '{j.name}' of '{paths.label(it)}' is moved by the animation: it does not turn to "
                         "the cable")
        else:
            got = _pick(_world(j.frame), _candidates(it, k, j.motion), _world)
            if got is not None:
                plans[j.name] = (it.name, c, j.name, got)
    return [p for p in plans.values() if p is not None]


def _correct(arrays: dict, delta: np.ndarray, motion, done: set) -> None:
    """Every object in ``arrays`` (name -> (F, 4, 4) world) carried by ``motion`` is moved by ``delta`` (F or 1, 4,
    4: the motion's new place times its old one turned inside out), in place; ``done``: arrays already moved."""
    import bpy
    for name, arr in arrays.items():
        if id(arr) in done:
            continue
        ob = bpy.data.objects.get(name)
        if ob is None or not _under(ob, motion):
            continue
        n = min(len(arr), len(delta))
        if len(delta) == 1:
            arr[...] = delta[0] @ arr
        else:
            arr[:n] = delta[:n] @ arr[:n]
        done.add(id(arr))


def after_read(scene, mats: dict, first: int, frames: int) -> list[str]:
    """Build: ``mats`` (object name -> (F, 4, 4) world, read in paths.py's one pass through the frames, F = frames
    or 1) holds the swivels' arrows and motions and the places their wires go to. Every swivel is keyed to its wire
    (one key per frame; a coupling put aside), and ``mats`` is corrected in place for everything that rides on a
    swivel's motion – as if it had been read with the keys. Returns warnings."""
    notes: list[str] = []
    try:
        if not len(scene.fresing.cables):
            return notes
        work = _plan(scene, notes)
        if not work:
            return notes
        from . import animation, flex
        cached = flex._STATE.get("read")
        for cab, c, jn, (ob, p) in work:
            done: set = set()                   # (an array the hoses' pass kept may be in ``mats`` too: once)
            j = joints.find(scene, jn)
            _put_aside(scene, j)                # (a follower's value cannot be set or keyed)
            j = joints.find(scene, jn)

            def at(o):
                return np.asarray(mats[o.name], dtype=float) if o.name in mats else _world(o)[None]
            fw, mw, pw = at(j.frame), at(j.motion), at(ob)
            F = max(len(fw), len(mw), len(pw))
            fw, mw, pw = (np.broadcast_to(x, (F, 4, 4)) for x in (fw, mw, pw))
            m0 = fw @ _motion_in_frame(j)       # the motion's place with the joint at 0
            inv0 = np.linalg.inv(m0)
            turned = inv0 @ mw                  # Rz(the value it had while read)
            old = np.unwrap(np.arctan2(turned[:, 1, 0], turned[:, 0, 0]))
            pf = np.einsum("fij,fj->fi", inv0[:, :3, :3], _at(pw, p)) + inv0[:, :3, 3]
            cm, nm = _sheave_in_motion(c, j)    # (C(v) = Rz(v) C_m in the arrow's coordinates)
            v = values(cm, nm, pf)
            good = np.isfinite(v)
            if not good.any():                  # (the swivel can do nothing for it: it stays as it is)
                v = old.copy()
            elif not good.all():                # (P on the axis for a while: the swivel stays where it was)
                idx = np.arange(len(v))
                last = np.maximum.accumulate(np.where(good, idx, -1))
                v = v[np.where(last < 0, int(np.argmax(good)), last)]
            v = np.unwrap(v)
            v = v + 2.0 * math.pi * round((old[0] - v[0]) / (2.0 * math.pi))
            if F > 1:                           # it turns only while its wire is shown, else it holds (task 0125:
                from . import paths             # a head turning through every frame cost the clash check twice the time)
                vis = paths._shown(paths.find(scene, cab), first, F)
                if not vis.any():
                    v = old.copy()
                elif not vis.all():
                    idx = np.arange(F)
                    last = np.maximum.accumulate(np.where(vis, idx, -1))
                    nxt = np.minimum.accumulate(np.where(vis, idx, F)[::-1])[::-1]
                    v = v[np.where(last >= 0, last, nxt)]
            if F == 1 or frames <= 1:
                joints.set_value(j, float(v[0]), use_limits=False)
            else:
                cb = animation._channelbag(j.motion, "OBJECT")
                animation._write(cb, joints.COUPLING_PATH, 0, [(first + f, float(x), "LINEAR", "AUTO")
                                                                 for f, x in enumerate(v[:frames])])
            j.motion[TAG] = cab
            if joints.outside_limits(j, float(v.min())) or joints.outside_limits(j, float(v.max())):
                notes.append(f"Swivel '{j.name}' of '{cab}' would turn beyond its limits to follow the cable")
            delta = mw @ np.linalg.inv(turned) @ _rz(v) @ np.linalg.inv(mw)    # M_new @ inv(M_old)
            _correct(mats, delta, j.motion, done)
            if cached is not None and cached[0] == (scene.name, int(first), F):
                _correct(cached[1], delta, j.motion, done)      # (the hoses' pass kept them: a later read gets them)
        try:                                    # (the frame shown with the new values)
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
