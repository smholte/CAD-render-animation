"""Lead motions as sliders on the web 3D page (task 0310): one glTF clip per joint they use, read in Blender.

For every joint a lead motion with a usable row names, the joint alone is stepped from the lowest to the highest value
any lead motion gives it (``core/web3d_lead.values``) – through ``joints.set_value``, as the app's slider sets it,
followers and mechanisms along – and every plain part's place is read. A part that ever stands elsewhere than in the
file gets a track in that joint's clip (thinned by ``web3d_keys.node_track``: within 0.1 mm / 0.05° of every read
value). Which joint carries which is measured with both set at once (``core.outer``). Hoses, cables, ropes, spools and
track links (drawn by modifiers, task 0142) are not in the clips: they stay where the page starts. Afterwards every
joint goes back and the frame shown is set again.

``read`` writes the clips and returns the page's settings block ``ST.lead`` = {t, joints, motions}; the same block
(without ``t``) is the file's ``extras.fr_lead`` for other viewers (Fresing Viewer).
"""

from __future__ import annotations

from contextlib import contextmanager

import bpy
import numpy as np

from ..core import lead_motions as lm_core
from ..core import web3d as w3
from ..core import web3d_keys as keys_core
from ..core import web3d_lead as core


def wanted(scene) -> list:
    """The lead motions that can go on the page: those with at least one joint that can move."""
    from . import lead_motions
    return [lm for lm in getattr(scene.fresing, "lead_motions", []) if lead_motions.usable(scene, lm)]


@contextmanager
def _held(scene):
    """While the joints are stepped: hoses and cables are not worked out (they are not in the clips), milling and
    coolant do not redraw; the joints and the frame shown are put back afterwards."""
    from . import clash, flex, joints, lead_motions, paths
    keep = {j.name: joints.get_value(j) for j in lead_motions.free_joints(scene)}
    frame = scene.frame_current
    flex._STATE["busy"] += 1
    paths._STATE["busy"] += 1
    guard = clash._Guard()
    guard.__enter__()
    try:
        yield keep
    finally:
        try:
            _put(scene, keep)
            scene.frame_set(frame)
        finally:
            guard.__exit__(None, None, None)
            flex._STATE["busy"] -= 1
            paths._STATE["busy"] -= 1


def _follow(scene) -> None:
    """Mechanisms follow the joints now (in the app their handler does; here also with no window)."""
    from . import linkages
    if len(getattr(scene.fresing, "mechanisms", [])):
        linkages.refresh_all(scene)
    bpy.context.view_layer.update()


def _put(scene, vals: dict) -> None:
    """Joints to these values ({name: value}), limits as the slider has them; mechanisms follow."""
    from . import joints
    for name, v in vals.items():
        j = joints.find(scene, name)
        if j is not None:
            joints.set_value(j, v)
    _follow(scene)


def _read(obs: list) -> np.ndarray:
    return np.array([np.array(ob.matrix_world) for ob in obs], np.float64)


def _trs(nd: dict, m: np.ndarray) -> None:
    """A node an animation moves holds its place as translation / rotation / scale (glTF: no ``matrix``)."""
    if "matrix" not in nd:
        return
    nd.pop("matrix")
    t, q, s = w3.decompose(np.asarray(m, np.float64)[None])
    nd["translation"] = [float(v) for v in t[0]]
    nd["rotation"] = [float(v) for v in q[0]]
    if np.abs(s[0] - 1.0).max() > 1e-5:
        nd["scale"] = [float(v) for v in s[0]]


def read(job) -> dict | None:
    """Writes one clip per joint the lead motions use into ``job.gltf`` and returns the page's block
    ``{t, joints, motions}`` (None when the project has no lead motion that can move a part the file holds).
    ``job._nodes`` = (object, node) of the parts in the file; only plain parts (not drawn by a modifier) move."""
    from . import joints as jmod
    from . import lead_motions
    scene = job.scene
    lms = wanted(scene)
    if not lms:
        return None
    pairs = [(ob, node) for ob, node in job._nodes if not job._drawn.kind(ob)]
    obs = [ob for ob, _n in pairs]
    if not obs:
        return None
    cores = [lead_motions.to_core(lm) for lm in lms]
    usable = [{r.joint for r, _j in lead_motions.usable(scene, lm)} for lm in lms]
    for c, ok in zip(cores, usable):
        c.rows = [r for r in c.rows if r.joint in ok]
    order = [j.name for j in scene.fresing.joints]
    ranges = core.joint_ranges(cores)
    names = sorted(ranges, key=lambda n: order.index(n) if n in order else len(order))
    reads = []
    with _held(scene) as current:
        _follow(scene)
        rest = _read(obs)
        reach = np.array([job._reach(ob) for ob in obs])
        for name in names:
            lo, hi = ranges[name]
            vs = core.values(lo, hi)
            mats = np.empty((len(vs), len(obs), 4, 4))
            for i, v in enumerate(vs):
                _put(scene, {name: float(v)})
                mats[i] = _read(obs)
            job.text = f"Lead motions: joint {len(reads) + 1} of {len(names)}"
            _put(scene, {name: current.get(name, 0.0)})
            reads.append((name, vs, mats))
        moved = [np.abs(m - rest[None]).max(axis=(0, 2, 3)) > 1e-6 for _n, _v, m in reads]
        far = [core.far_index(m, rest) for _n, _v, m in reads]
        carriers = {}
        for a in range(len(reads)):
            for b in range(a + 1, len(reads)):
                both = moved[a] & moved[b]
                if not both.any():
                    continue
                _put(scene, {reads[a][0]: float(reads[a][1][far[a]]), reads[b][0]: float(reads[b][1][far[b]])})
                m_both = _read(obs)
                _put(scene, {reads[a][0]: current.get(reads[a][0], 0.0), reads[b][0]: current.get(reads[b][0], 0.0)})
                s = core.outer(rest[both], reads[a][2][far[a]][both], reads[b][2][far[b]][both], m_both[both],
                               reach[both])
                if s:
                    carriers[(a, b)] = s
    apply = core.apply_order(len(reads), carriers, [int(m.sum()) for m in moved])
    ids, joints_out, kept = {}, [], 0
    for k in sorted(range(len(reads)), key=lambda k: apply[k]):   # the clips in the order the page applies them
        name, vs, mats = reads[k]
        if not moved[k].any():
            continue                                     # moves no part the file holds (a cable's speed)
        lo, hi = ranges[name]
        times = core.clip_time(vs, lo, hi)
        tracks = []
        for n in np.where(moved[k])[0]:
            ob, node = pairs[n]
            _trs(job.gltf.doc["nodes"][node], rest[n])
            t, q, _s = w3.decompose(mats[:, n])
            tr = keys_core.node_track(t, q, None, reach=reach[n], frames=times, packed=job.gltf.compress)
            kept += len(tr.keys)
            for path in ("translation", "rotation"):
                if path in tr.paths:
                    tracks.append((node, path, tr.paths[path][0], "LINEAR", times[tr.keys], tr.how(path)))
        if not tracks:
            continue
        j = jmod.find(scene, name)
        label = f"Joint {len(ids) + 1}" if job.hide_names else name
        clip = job.gltf.animation(label, times, tracks)
        ids[name] = len(ids)
        e = core.joint_entry(clip, lo, hi, len(joints_out), getattr(j, "kind", "ROTATE"), int(moved[k].sum()))
        job.gltf.doc["animations"][clip]["extras"] = {"fr_lead_joint": ids[name]}
        joints_out.append(e)
    motions = []
    for lm, c in zip(lms, cores):
        c.rows = [r for r in c.rows if r.joint in ids]
        if not c.rows:
            continue
        at = lm_core.position_of(c, {n: current.get(n, 0.0) for n in ids})
        ends = lm_core.end_labels(c, lambda jn, v: lead_motions.unit_text(scene, jn, v))
        motions.append(core.motion_entry(c, ids, at, ends))
    if not motions:
        return None
    job.result["lead_motions"] = len(motions)
    job.result["lead_joints"] = len(joints_out)
    job.result["lead_keys"] = kept
    block = {"joints": joints_out, "motions": motions}
    job.gltf.doc.setdefault("extras", {})["fr_lead"] = block      # for other viewers (Fresing Viewer)
    return dict(block, t=float(job.lead_time))
