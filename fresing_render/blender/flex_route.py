"""A route you can shape between a hose's two ends (task 0298): via points.

A **via point** is a point the hose runs through, set by hand in the view (``fresing.flex_route``): drag it, click on
the line to add one, X to remove one. Unlike a clip (task 0240, on a part, with its own direction) it sits on no part:
it is carried along by the two parts the hose's ends sit on, going over from the one to the other by its place along
the hose – the same way the CAD centreline guides a hose (``core/flex.carried``): near end A it moves with A's part,
near end B with B's, in between a share of the turn-and-slide between them (``core/clash.screw_between``). In the
pose it was set in it is exactly where it was put. The hose passes it along the bisector of the way in and the way
out (the line from the stop before and to the stop after).

A via point is kept as a clip with ``via`` on (``FRFlexClip``): ``point`` in end A's part's coordinates, ``rel`` =
A's place⁻¹ · B's place when it was set (16 numbers, row by row), ``weight`` = its share along the hose (0 … 1);
``part`` / ``uid`` are end A's, so everything that walks the clips (the list of parts an item hangs on, a model
update) keeps working. Clips and via points share one list, in their order along the hose; the hose is solved as one
segment per stretch between two stops, each with its share of the length (``item["shares"]``).

**Length**: ``FRFlex.length_auto`` on – the length is worked out again from the route whenever it changes (as a drawn
hose's first length: a smooth line through the stops that keeps its bends wide, 5 % more, over the travel of the
joints between the ends); off – the length stays as typed (or as CAD drew it) and only its split over the stretches
follows the route.
"""

from __future__ import annotations

import numpy as np

from ..core import clash as CC


def is_via(c) -> bool:
    return bool(getattr(c, "via", False))


def via_indices(item) -> list:
    return [k for k, c in enumerate(item.clips) if is_via(c)]


def count(item) -> int:
    return len(via_indices(item))


def _smooth(w: float) -> float:
    w = min(max(float(w), 0.0), 1.0)
    return w * w * (3.0 - 2.0 * w)


def via_world(c, a_m: np.ndarray, b_m: np.ndarray) -> np.ndarray:
    """Where the via point is at the moments of ``a_m``, ``b_m`` (F, 4, 4): (F, 3)."""
    p = np.append(np.array(c.point, dtype=float), 1.0)
    rel0 = np.array(c.rel, dtype=float).reshape(4, 4)
    w = _smooth(c.weight)
    out = np.empty((len(a_m), 3))
    try:
        rel0_inv = np.linalg.inv(rel0)
    except np.linalg.LinAlgError:
        rel0_inv = np.eye(4)
    for f in range(len(a_m)):
        a = a_m[f]
        try:
            d = np.linalg.solve(a, b_m[f]) @ rel0_inv          # B's motion against A since it was set (A's frame)
        except np.linalg.LinAlgError:
            d = np.eye(4)
        if w <= 0.0 or np.allclose(d, np.eye(4), atol=1e-9):
            local = p
        else:
            try:
                local = CC.screw_between(np.eye(4), d, w) @ p
            except Exception:                                # (no screw: blended plainly)
                local = (1.0 - w) * p + w * (d @ p)
            if not np.isfinite(local).all():
                local = (1.0 - w) * p + w * (d @ p)
        out[f] = (a @ local)[:3]
    return out


def _unit(v: np.ndarray, other: np.ndarray) -> np.ndarray:
    ln = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.where(ln > 1e-12, v / np.where(ln > 1e-12, ln, 1.0), other)


def stops_at(item, mats: dict) -> list:
    """[(points (F, 3), unit directions (F, 3))]: end A, the clips and via points, end B, at the moments of
    ``mats`` (object name -> (F, 4, 4)); directions along the hose from A to B."""
    a_m, b_m = mats[item.a_part.name], mats[item.b_part.name]

    def at(m, point, direction):
        p = np.array(point, dtype=float) @ m[:, :3, :3].transpose(0, 2, 1) + m[:, :3, 3]
        d = np.array(direction, dtype=float) @ m[:, :3, :3].transpose(0, 2, 1)
        return p, _unit(d, np.array([1.0, 0.0, 0.0]))

    out = [at(a_m, item.a_point, item.a_dir)]
    for c in item.clips:
        out.append((via_world(c, a_m, b_m), None) if is_via(c) else at(mats[c.part.name], c.point, c.dir))
    out.append(at(b_m, item.b_point, item.b_dir))
    for k, (p, d) in enumerate(out):
        if d is None:
            back = _unit(p - out[k - 1][0], out[k - 1][1])
            on = _unit(out[k + 1][0] - p, back)
            out[k] = (p, _unit(back + on, on))
    return out


def stops_now(item) -> list:
    """``stops_at`` for where the parts are now: [(point (3,), direction (3,))]."""
    from . import flex
    names = {ob.name: ob for ob in flex.end_objects(item) if ob is not None}
    mats = {n: np.array(flex._world(ob), dtype=float)[None] for n, ob in names.items()}
    return [(p[0], d[0]) for p, d in stops_at(item, mats)]


def _set(item, c, world_point, weight: float) -> None:
    a = np.array(item.a_part.matrix_world, dtype=float)
    b = np.array(item.b_part.matrix_world, dtype=float)
    inv = np.linalg.inv(a)
    c.part, c.uid = item.a_part, item.a_uid
    c.point = tuple(inv[:3, :3] @ np.asarray(world_point, dtype=float) + inv[:3, 3])
    c.dir = (1.0, 0.0, 0.0)
    c.rel = tuple((inv @ b).reshape(-1))
    c.weight = float(min(max(weight, 0.0), 1.0))


def where_on(item, points: np.ndarray, index: int) -> tuple:
    """(clip position to insert at, weight) for a click on the hose's line ``points`` (the shapes mesh's moment,
    ``flex.shape_now``) at point ``index``."""
    from . import flex
    per = flex.DRAWN - 1
    seg = min(max(int(index), 0) // per, len(item.clips))
    run = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])
    return seg, float(run[min(int(index), len(run) - 1)] / (run[-1] or 1.0))


def add(scene, item, world_point, at: int, weight: float):
    """A via point at ``world_point`` before clip ``at`` (0 = right after end A). Returns its index."""
    from . import flex
    with flex._quiet(item):
        c = item.clips.add()
        c.via = True
        _set(item, c, world_point, weight)
        k = len(item.clips) - 1
        at = min(max(int(at), 0), k)
        if at != k:
            item.clips.move(k, at)
    changed(scene, item)
    return at


def move(scene, item, k: int, world_point, solve: bool = True) -> None:
    """Via point ``k`` (index in the clips) to ``world_point`` (its weight stays)."""
    from . import flex
    c = item.clips[k]
    with flex._quiet(item):
        _set(item, c, world_point, c.weight)
    if solve:
        changed(scene, item)


def remove(scene, item, k: int) -> None:
    from . import flex
    if 0 <= k < len(item.clips) and is_via(item.clips[k]):
        with flex._quiet(item):
            item.clips.remove(k)
        changed(scene, item)


def clear(scene, item) -> int:
    """Every via point off (clips stay). Returns how many."""
    from . import flex
    ks = via_indices(item)
    with flex._quiet(item):
        for k in reversed(ks):
            item.clips.remove(k)
    changed(scene, item)
    return len(ks)


def snapshot(item) -> list:
    """The clips as they are (to put them back on Esc): plain numbers."""
    return [dict(via=is_via(c), part=c.part, uid=c.uid, point=tuple(c.point), dir=tuple(c.dir), rel=tuple(c.rel),
                 weight=float(c.weight)) for c in item.clips]


def restore(scene, item, snap: list) -> None:
    from . import flex
    with flex._quiet(item):
        item.clips.clear()
        for s in snap:
            c = item.clips.add()
            c.via, c.part, c.uid, c.point, c.dir, c.rel, c.weight = (s["via"], s["part"], s["uid"], s["point"],
                                                                     s["dir"], s["rel"], s["weight"])
    changed(scene, item)


def world_now(item) -> list:
    """The via points where they are now: [(index, world point)] (kept across a model update)."""
    a = np.array(item.a_part.matrix_world, dtype=float)[None] if item.a_part else None
    b = np.array(item.b_part.matrix_world, dtype=float)[None] if item.b_part else None
    if a is None or b is None:
        return []
    return [(k, via_world(item.clips[k], a, b)[0]) for k in via_indices(item)]


def put_back(item, places: list) -> None:
    """Via points set again from their world points (after a model update gave the ends new parts)."""
    if item.a_part is None or item.b_part is None:
        return
    for k, p in places:
        if k < len(item.clips) and is_via(item.clips[k]):
            _set(item, item.clips[k], p, item.clips[k].weight)


def changed(scene, item) -> None:
    """The route changed: each stretch's share of the length (and the length itself when it is automatic) follows
    the stops where they are now; then the hose is solved again."""
    from . import flex
    from ..core import flex as HS
    if not len(item.clips) and not item.length_auto:
        flex.changed(scene, item)
        return
    flex._STATE["busy"] += 1
    try:
        if item.length_auto:
            lengths, _lines, _free = flex._natural(scene, item)
        else:
            lengths, _lines = flex._natural_now(item)
    finally:
        flex._STATE["busy"] -= 1
    with flex._quiet(item):
        item["shares"] = [float(x) for x in HS.shares(lengths)]
        if item.length_auto:
            item.length = float(sum(lengths))
    flex.changed(scene, item)
