"""Rollers the cable has left stand still (task 0125).

A roller of a cable (a ``ROLLER`` contact of ``blender/paths.py``) turns by a coupling: its rotate joint follows the
cable's speed joint (or the joint at the top of that joint's chain, as the demo's horn rollers follow 'Cable
travel'). Where a cable hangs into the sea from a horn it leaves the horn earlier than CAD drew it, and the rollers on
the rest of the horn are not touched – yet their coupling keeps them turning.

At Build (``after_bake``, called by ``paths._bake`` once every cable is drawn) every such roller is tested at every
frame: is a drawn cable that lists it on it? A roller touched at every frame keeps its coupling (nothing is done). Any
other gets one key per frame on its joint – it turns with its coupling while touched and stands still while not –
with the coupling put aside on the joint's motion empty (``WAS``, JSON: follows, ratio, offset). 'Clear keys'
(``after_clear``, from ``paths.after_clear``) puts every coupling put aside back.

Touching: the point of the drawn cable nearest the roller's centre lies within the roller's seat (its axis to the
cable's middle, ``paths.radius_of`` + the gap CAD left) + ``TOL`` of its axis, and within the roller's width (along its
axis, from its part's box) + ``TOL`` of its centre. Only the cable's pieces whose box over the whole animation comes
near a roller are looked at, all frames at once (NumPy).

Where the roller is, as the cable part sees it: a roller whose carrier moves with the cable part (or a cable that
stays as drawn) sits where CAD put it; one whose carrier moves with one of the cable's carriers (a horn on a tilting
frame) goes with that carrier's place per frame. A roller on anything else keeps its coupling.
"""

from __future__ import annotations

import json
import warnings

import numpy as np

WAS = "fr_roller_was"          # on a joint's motion empty: its coupling put aside at Build (JSON)
STILL = "fr_roller_still"      # on a joint's motion empty: its keys are this module's (the cables it was tested on)
TOL = (0.005, 0.02)            # touching: 5 mm + 2 % of the cable's diameter (m) beyond the seat and the width


def _paths():
    from . import paths
    return paths


def _joints():
    from . import joints
    return joints


# ---------------------------------------------------------------------------
# the rollers of every cable
# ---------------------------------------------------------------------------

def _rollers_by_joint(scene) -> dict:
    """{joint name: [(cable, contact), ...]} for every ROLLER contact with a joint, over every cable."""
    out: dict = {}
    for it in scene.fresing.cables:
        for c in it.contacts:
            if c.kind == "ROLLER" and c.joint:
                out.setdefault(c.joint, []).append((it, c))
    return out


def _top_name(scene, name: str):
    J = _joints()
    j = J.find(scene, name) if name else None
    if j is None:
        return None
    top = J.driver_of(scene, j)
    return top.name if top is not None else None


def _half_width(c, centre_w, axis_w, memo: dict) -> tuple:
    """(lo, hi) m: the roller's part along its axis from its centre (its box in the CAD pose)."""
    paths = _paths()
    part = c.part
    if part is None or getattr(part, "bound_box", None) is None:
        return None
    try:
        m = paths._cad(part, memo)
    except Exception:
        return None
    box = np.array([tuple(v) for v in part.bound_box], dtype=float)
    w = box @ m[:3, :3].T + m[:3, 3]
    along = (w - centre_w) @ axis_w
    return float(along.min()), float(along.max())


def _places(scene, item, c, rel, slots, memo: dict):
    """The roller as the cable part sees it: (centre (F_r, 3), axis (F_r, 3)) in the cable part's units, F_r 1 or
    rel's frames; None when its carrier moves by something the cable's places do not show."""
    paths = _paths()
    from . import flex
    carrier = c.carrier
    if not flex._alive(scene, carrier) or not flex._alive(scene, item.part):
        return None
    cad_c = paths._cad(carrier, memo)
    local_c = np.array(tuple(c.centre) + (1.0,), dtype=float)
    local_a = np.array(c.axis, dtype=float)
    mine = flex._movers(carrier)
    if item.still or mine == flex._movers(item.part):
        m = (np.linalg.inv(paths._cad(item.part, memo)) @ cad_c)[None]
    else:
        k = next((k for k, sl in enumerate(slots) if sl.part is None and not sl.role
                  and flex._alive(scene, sl.carrier) and flex._movers(sl.carrier) == mine), None)
        if k is None:
            return None
        m = rel[:, k] @ (np.linalg.inv(paths._cad(slots[k].carrier, memo)) @ cad_c)
    centre = np.einsum("fij,j->fi", m, local_c)[:, :3]
    axis = np.einsum("fij,j->fi", m[:, :3, :3], local_a)
    axis /= np.maximum(np.linalg.norm(axis, axis=1, keepdims=True), 1e-300)
    return centre, axis


# ---------------------------------------------------------------------------
# touching
# ---------------------------------------------------------------------------

def touching(points, ok, centres, axes, seat, lo, hi) -> np.ndarray:
    """(F, R) bool: is roller r touched at moment f? All lengths in one unit.

    ``points`` (F, n, 3) the drawn cable; ``ok`` (F,) moments with a path (the others take the moment before's
    answer; touched before any); ``centres`` / ``axes`` (R, F_r, 3), F_r 1 or F; ``seat`` (R,) the farthest the cable's
    middle may be from the axis; ``lo`` / ``hi`` (R,) the band along the axis (from the centre) it must lie in."""
    pts = np.asarray(points, dtype=float)
    F, n = pts.shape[0], pts.shape[1]
    R = len(seat)
    out = np.zeros((F, R), dtype=bool)
    if not R:
        return out
    if n < 2:
        return np.ones((F, R), dtype=bool)
    with warnings.catch_warnings(), np.errstate(invalid="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)         # (a point that is never drawn: all NaN)
        p_lo, p_hi = np.nanmin(pts, axis=0), np.nanmax(pts, axis=0)     # (n, 3): each point over every moment
    p_lo = np.where(np.isfinite(p_lo), p_lo, np.inf)
    p_hi = np.where(np.isfinite(p_hi), p_hi, -np.inf)
    box_lo = np.minimum(p_lo[:-1], p_lo[1:])                    # (n-1, 3): each piece's box over every moment
    box_hi = np.maximum(p_hi[:-1], p_hi[1:])
    reach = np.sqrt(np.asarray(seat, dtype=float) ** 2 + np.maximum(np.abs(lo), np.abs(hi)) ** 2)    # (R,)
    c_lo = np.array([np.asarray(cr).min(axis=0) for cr in centres]) - reach[:, None]
    c_hi = np.array([np.asarray(cr).max(axis=0) for cr in centres]) + reach[:, None]
    near = ((box_lo[None] <= c_hi[:, None]) & (box_hi[None] >= c_lo[:, None])).all(axis=2)    # (R, n-1)
    # every (roller, piece) pair that can come near, all at once: per pair the point of the piece nearest the
    # roller's centre; per roller the nearest of its pairs decides (x, y, z first: sums over 3 are fast that way)
    r_idx, s_idx = np.nonzero(near)                                 # sorted by roller
    if len(r_idx):
        rollers, starts = np.unique(r_idx, return_index=True)
        group = np.searchsorted(rollers, r_idx)                     # pair -> place among ``rollers``
        Fr = max(len(np.asarray(cr)) for cr in centres)
        # 32 bits, round the rollers' middle (micrometres on a cable 100 m long; the tolerance is millimetres)
        o = np.mean([np.asarray(cr, dtype=float).mean(axis=0) for cr in centres], axis=0)
        C = np.stack([(np.broadcast_to(np.asarray(cr, dtype=float), (Fr, 3)) - o).T for cr in centres],
                     axis=2).astype(np.float32)                     # (3, Fr, R)
        X = np.stack([np.broadcast_to(np.asarray(ax, dtype=float), (Fr, 3)).T for ax in axes],
                     axis=2).astype(np.float32)
        seat2 = (np.asarray(seat, dtype=float) ** 2)[r_idx].astype(np.float32)
        lo_p = np.asarray(lo, dtype=float)[r_idx].astype(np.float32)
        hi_p = np.asarray(hi, dtype=float)[r_idx].astype(np.float32)
        used, back = np.unique(np.concatenate([s_idx, s_idx + 1]), return_inverse=True)
        ia, ib = back[:len(s_idx)], back[len(s_idx):]               # pair -> its two points among ``used``
        P3 = np.ascontiguousarray(np.moveaxis(pts[:, used] - o, 2, 0), dtype=np.float32)   # (3, F, U): near a roller
        step = max(1, int(100_000 // max(len(r_idx), 1)))          # frames per chunk (in the cache)
        for f0 in range(0, F, step):
            f1 = min(F, f0 + step)
            A = P3[:, f0:f1][:, :, ia]                              # (3, Fc, K)
            AB = P3[:, f0:f1][:, :, ib] - A
            cen = C[:, f0:f1][:, :, r_idx] if Fr > 1 else C[:, :, r_idx]
            ax = X[:, f0:f1][:, :, r_idx] if Fr > 1 else X[:, :, r_idx]
            L2 = np.maximum((AB * AB).sum(axis=0), np.float32(1e-30))
            t = np.clip(((cen - A) * AB).sum(axis=0) / L2, 0.0, 1.0)
            v = A + AB * t - cen
            d2 = (v * v).sum(axis=0)
            along = (v * ax).sum(axis=0)
            d2 = np.where(np.isfinite(d2), d2, np.inf)
            fits = (d2 - along * along <= seat2) & (along >= lo_p) & (along <= hi_p) & np.isfinite(d2)
            best = d2 <= np.minimum.reduceat(d2, starts, axis=1)[:, group]
            out[f0:f1, rollers] = np.logical_or.reduceat(best & fits, starts, axis=1)
    okv = np.asarray(ok, dtype=bool).reshape(-1)
    if okv.shape[0] == F and not okv.all():
        last = np.ones(R, dtype=bool)
        for f in range(F):
            if okv[f]:
                last = out[f]
            else:
                out[f] = last
    return out


def _touched_by(scene, item, drawn_item, contacts: list, frames: int, memo: dict):
    """(frames, len(contacts)) bool: each roller touched by this cable at each frame; None when one of them cannot
    be placed (its carrier moves by something else) or the drawn shapes do not fit the frames."""
    paths = _paths()
    rel, _first, res = drawn_item
    pts = np.asarray(res.get("points"))
    ok = np.asarray(res.get("ok"), dtype=bool).reshape(-1)
    if pts.ndim != 3 or pts.shape[0] not in (1, frames) or ok.shape[0] != pts.shape[0]:
        return None
    if not ok.any():
        return None
    scale = float(res.get("scale", 1.0)) or 1.0
    _w, slots, _ws, _a, _b = paths._inputs_of(item)
    rel = np.asarray(rel, dtype=float)
    if rel.ndim != 4 or rel.shape[0] not in (1, pts.shape[0]):
        return None
    d = float(item.diameter)
    tol = TOL[0] + TOL[1] * d
    centres, axes, seat, lo, hi = [], [], [], [], []
    for c in contacts:
        got = _places(scene, item, c, rel, slots, memo)
        if got is None:
            return None
        cen, ax = got                                               # (the cable part's units)
        cad_c = paths._cad(c.carrier, memo)
        cw = cad_c[:3, :3] @ np.array(c.centre, dtype=float) + cad_c[:3, 3]
        aw = cad_c[:3, :3] @ np.array(c.axis, dtype=float)
        aw = aw / max(float(np.linalg.norm(aw)), 1e-300)
        band = _half_width(c, cw, aw, memo)
        if band is None:
            band = (-max(float(c.radius), d), max(float(c.radius), d))
        centres.append(cen)
        axes.append(ax)
        seat.append((paths.radius_of(item, c) + max(float(c.gap), 0.0) + tol) / scale)
        lo.append((band[0] - tol) / scale)
        hi.append((band[1] + tol) / scale)
    got = touching(pts, ok, centres, axes, np.array(seat), np.array(lo), np.array(hi))
    if got.shape[0] == 1 and frames > 1:
        got = np.repeat(got, frames, axis=0)
    return got


# ---------------------------------------------------------------------------
# the leader's values
# ---------------------------------------------------------------------------

def _values_of(top, first: int, frames: int):
    """(frames,) the top joint's value at each frame (from its keys), or None when it has no keys (it stands)."""
    paths = _paths()
    J = _joints()
    if top.motion is None:
        return None
    fc = next((f for f in paths._fcurves(top.motion) if f.data_path == J.COUPLING_PATH and f.array_index == 0), None)
    if fc is None or fc.mute or not len(fc.keyframe_points):
        return None
    return np.array([fc.evaluate(first + f) for f in range(frames)], dtype=float)


def held_values(coupled, touched) -> np.ndarray:
    """(F,) the roller's value: it turns as its coupling says between two frames only while touched at the later
    one; it starts where its coupling puts it at the first frame."""
    coupled = np.asarray(coupled, dtype=float)
    step = np.diff(coupled) * np.asarray(touched, dtype=bool)[1:]
    return coupled[0] + np.concatenate([[0.0], np.cumsum(step)])


def _keys(values, first: int) -> list:
    """One key per frame, the middle of a run that stands still left out (one key when it never moves)."""
    v = np.asarray(values, dtype=float)
    if not len(v) or float(np.ptp(v)) == 0.0:
        return [(first, float(v[0]) if len(v) else 0.0, "LINEAR", "AUTO")]
    keep = np.ones(len(v), dtype=bool)
    keep[1:-1] = ~((v[1:-1] == v[:-2]) & (v[1:-1] == v[2:]))
    return [(first + int(f), float(v[f]), "LINEAR", "AUTO") for f in np.flatnonzero(keep)]


# ---------------------------------------------------------------------------
# Build and Clear keys
# ---------------------------------------------------------------------------

def _put_aside(scene, j, cables: list) -> None:
    J = _joints()
    was = {"follows": j.follows, "ratio": float(j.couple_ratio), "offset": float(J.offset(j))}
    j.motion[WAS] = json.dumps(was)
    j.motion[STILL] = ", ".join(cables)
    # not set_follows(j, ''): that takes the built animation off, and its limits would clamp the keys (a follower's
    # value range is wide, a joint's own is ±10 turns); the coupling driver goes, the keys move it
    J._set_raw(j, follows="")
    J.write_coupling(scene, j)


def _write_keys(j, values, first: int) -> None:
    from . import animation
    J = _joints()
    cb = animation._channelbag(j.motion, "OBJECT")
    animation._write(cb, J.COUPLING_PATH, 0, _keys(values, first))
    j.motion.update_tag()


def after_bake(scene, first: int, frames: int, drawn: dict) -> list[str]:
    """Build: every roller whose joint turns with a cable and which no drawn cable touches at some frame gets one key
    per frame (standing still where it is not touched), its coupling put aside until 'Clear keys'. Returns
    warnings."""
    after_clear(scene)                          # (a coupling still aside from an earlier Build first)
    if frames < 1 or not drawn:
        return []
    J = _joints()
    by_joint = _rollers_by_joint(scene)
    if not by_joint:
        return []
    memo: dict = {}
    leaders: dict = {}
    # 1. the joints that turn with a cable, every cable that lists them drawn in this Build
    todo = []
    for name, uses in by_joint.items():
        j = J.find(scene, name)
        if j is None or j.motion is None or not j.follows or j.couple_table:
            continue
        top = J.driver_of(scene, j)
        if top is None or top.name == j.name:
            continue
        if any(it.name not in drawn for it, _c in uses):
            continue                            # a cable over it is not drawn (off, broken): leave it alone
        if not any(_top_name(scene, it.joint) == top.name for it, _c in uses):
            continue                            # it turns by something else than its cables
        todo.append((name, j, top, uses))
    if not todo:
        return []
    # 2. which of them each cable touches, per frame (one pass per cable over all its rollers)
    per_cable: dict = {}
    for name, _j, _top, uses in todo:
        for it, c in uses:
            per_cable.setdefault(it.name, (it, []))[1].append((name, c))
    touched: dict = {}                          # joint name -> (frames,) bool, or None: cannot tell
    for cname, (it, rows) in per_cable.items():
        try:
            got = _touched_by(scene, it, drawn[cname], [c for _n, c in rows], frames, memo)
        except Exception as exc:                # a Build never fails over a roller
            print("Fresing Render: rollers of cable", cname, ":", exc)
            got = None
        for k, (name, _c) in enumerate(rows):
            if got is None:
                touched[name] = None
            elif name not in touched:
                touched[name] = got[:, k].copy()
            elif touched[name] is not None:
                touched[name] |= got[:, k]
    # 3. keys for those left at some frame
    for name, j, top, uses in todo:
        t = touched.get(name)
        if t is None or bool(t.all()):
            continue
        if top.name not in leaders:
            leaders[top.name] = _values_of(top, first, frames)
        lead = leaders[top.name]
        if lead is None:
            continue                            # its leader stands: the roller does not turn anyway
        top_, fmap = J.chain_map(scene, j)
        if top_ is None:
            continue
        coupled = np.asarray(fmap(lead), dtype=float).reshape(-1)
        if float(np.ptp(coupled)) == 0.0:
            continue
        values = held_values(coupled, t)
        _put_aside(scene, j, sorted({it.name for it, _c in uses}))
        _write_keys(j, values, first)
    return []


def after_clear(scene) -> None:
    """'Clear keys': every coupling put aside at Build is back (the keys went with the others)."""
    J = _joints()
    back = False
    for j in list(scene.fresing.joints):
        mo = j.motion
        if mo is None or (WAS not in mo and STILL not in mo):
            continue
        raw = mo.get(WAS)
        for key in (WAS, STILL):
            if key in mo:
                del mo[key]
        try:
            was = json.loads(raw) if raw else None
        except (TypeError, ValueError):
            was = None
        if not was or not was.get("follows") or j.follows:
            continue
        name = str(was["follows"])
        reason = J.follow_check(scene, j, name)
        if reason:
            print("Fresing Render: roller coupling not restored:", reason)
            continue
        off = {"couple_offset_angle" if j.kind == "ROTATE" else "couple_offset_dist": float(was.get("offset", 0.0))}
        J._set_raw(j, couple_ratio=float(was.get("ratio", 1.0)), **off)
        J._set_raw(j, follows=name)
        J.write_coupling(scene, j)
        J.apply_limits(j, J._model_size(scene))
        back = True
    if back:
        J._update(scene)
