"""Things fitted on a cable that ride along with it (task 0081): a CPS set (a tube and its bend-restrictor
segments), a bend restrictor, a pull head. They go over the wheels, through the tensioners and down the catenary
into the sea with the cable, each segment a stiff piece lying on the cable on its chord.

**What is read when it is added** (``add``): its parts (CAD parts; an assembly gives all the parts under it), in
the CAD pose, in the cable part's coordinates: the line through their middles (one part: its longest extent) is
the thing's **axis**, its *front* the end towards the cable's end (where the cable goes into the sea); each part's
place ``at`` (metres from the front end to the part's own front) and ``length`` along that axis. Where it sits on
the cable: ``where`` END = its front ``at`` metres from the cable's end (for a cable into the sea the end lying
on the seabed), with nothing paid out; MARK = its front passes the cable's last contact (horn, chute) when ``at``
metres have been paid out. That gives its **mark** (metres along the cable from its start, nothing paid out).

**Where it is drawn** (no Python per frame). A part lies at s = mark − at − length … mark − at + paid out along
the cable's drawn path (``paths.py``: its shapes mesh holds the path of every frame, the cable part's coordinates;
past the path's end it waits at the end). Each part is moved, as one stiff piece, from its CAD place onto its chord
on the path: its middle onto the chord's middle and its axis onto the chord by the shortest turn. One object per
cable, the **run** ("FR ride run <cable>", a point per part), works this out for all its parts at once in Geometry
Nodes (``_build_run``: the frame's slice of the shapes mesh as a curve, Sample Curve at the two lengths, Align
Rotation to Vector); the paid out metres come in by a simple-expression driver on the cable joint (``Pay``). Each
part has a modifier "FR ride" (tracks.py's part tree: inverse(own world) x the run's matrix) that moves its own
geometry there, so its looks, hiding and selection stay the part's own.

Units: metres; the run and its tree work in the cable part's units (``Unit`` = part units per metre).
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import build, flex, joints, logic

MOD = "FR ride"                         # on a part riding on a cable
RUN_MOD = "FR ride run"                 # on a cable's run object
RUN = "FR ride run"                     # + the cable's name
RUN_TREE = "FR ride run"
TAG = "fr_ride"                         # on a riding part and the run: the cable's name
VERSION = 1
BIAS = 2.0                              # Pay = metres paid out + BIAS (a driver's result is never near 0)
_INPUTS = (("Shapes", "NodeSocketObject"), ("First", "NodeSocketInt"), ("Frames", "NodeSocketInt"),
           ("Per frame", "NodeSocketInt"), ("Offset", "NodeSocketInt"), ("Count", "NodeSocketInt"),
           ("Cable", "NodeSocketObject"), ("Pay", "NodeSocketFloat"), ("Unit", "NodeSocketFloat"))
_STATE = {"inputs": {}}


class RiderError(RuntimeError):
    """Said to the user as it is."""


def _paths():
    from . import paths
    return paths


def _alive(scene, ob) -> bool:
    return flex._alive(scene, ob)


def _uid(ob) -> str:
    return str(ob.get(build.PROP_UID, ob.name))


def rider_parts(scene) -> list:
    """Every part riding on a cable (the clash check leaves them out: they lie on the cable on purpose)."""
    out = []
    for it in scene.fresing.cables:
        for r in it.riders:
            if r.enabled:
                out += [p.part for p in r.parts if _alive(scene, p.part)]
    return out


def cable_of(scene, rider):
    for it in scene.fresing.cables:
        for r in it.riders:
            if r == rider:
                return it
    return None


# ---------------------------------------------------------------------------
# the node tree of a cable's run
# ---------------------------------------------------------------------------

def _math(b, op, x, y=None):
    n = b.new("ShaderNodeMath", operation=op)
    for k, v in enumerate((x, y)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[k].default_value = v
        else:
            b.link(v, n.inputs[k])
    return n.outputs[0]


def _vmath(b, op, x, y=None):
    n = b.new("ShaderNodeVectorMath", operation=op)
    for k, v in enumerate((x, y)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[k].default_value = (v, v, v)
        else:
            b.link(v, n.inputs[k])
    return n.outputs["Value" if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else "Vector"]


def _attr(b, name: str, kind: str):
    n = b.new("GeometryNodeInputNamedAttribute", data_type=kind)
    n.inputs["Name"].default_value = name
    return flex._sock(n.outputs, "Attribute")


def _build_run(ng) -> None:
    """On the run's points (one per riding part: ``fr_sa`` the mark where its chord starts, ``fr_len`` its length,
    ``fr_mid`` its middle and ``fr_q`` the turn of +Z onto its axis in the CAD pose, ``fr_r0`` its own matrix in
    the cable part's coordinates): ``fr_m`` = the world matrix it is drawn with now."""
    b = flex._Nodes(ng)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
    shapes = flex._shapes_geometry(b, gin)
    line, index = flex._line(b, gin, flex._moment(b, gin))
    place = b.new("GeometryNodeSetPosition")
    b.link(line, place.inputs["Geometry"])
    b.link(flex._sample(b, shapes, index), place.inputs["Position"])
    curve = b.new("GeometryNodeMeshToCurve")
    b.link(place.outputs[0], curve.inputs["Mesh"])
    # the mark of the slice's first point (metres)
    s0 = b.new("GeometryNodeSampleIndex", data_type="FLOAT", domain="POINT")
    b.link(shapes, s0.inputs["Geometry"])
    b.link(flex._moment(b, gin), s0.inputs["Index"])
    b.link(_attr(b, "fr_s", "FLOAT"), flex._sock(s0.inputs, "Value"))
    pay = _math(b, "SUBTRACT", gin.outputs["Pay"], BIAS)
    start = _math(b, "MULTIPLY", _math(b, "SUBTRACT", _math(b, "ADD", _attr(b, "fr_sa", "FLOAT"), pay),
                                       flex._sock(s0.outputs, "Value")), gin.outputs["Unit"])
    end = _math(b, "ADD", start, _math(b, "MULTIPLY", _attr(b, "fr_len", "FLOAT"), gin.outputs["Unit"]))

    def at(length):
        sc = b.new("GeometryNodeSampleCurve", mode="LENGTH", use_all_curves=True)
        b.link(curve.outputs[0], sc.inputs["Curves"])
        b.link(length, sc.inputs["Length"])
        return sc.outputs["Position"]

    qa, qb = at(start), at(end)
    e = _vmath(b, "NORMALIZE", _vmath(b, "SUBTRACT", qb, qa))
    mid = _vmath(b, "SCALE", _vmath(b, "ADD", qa, qb), None)
    scale_node = mid.node
    scale_node.inputs["Scale"].default_value = 0.5
    rot0 = b.new("FunctionNodeEulerToRotation")
    b.link(_attr(b, "fr_q", "FLOAT_VECTOR"), rot0.inputs[0])
    align = b.new("FunctionNodeAlignRotationToVector", axis="Z", pivot_axis="AUTO")
    b.link(rot0.outputs[0], align.inputs["Rotation"])
    b.link(e, align.inputs["Vector"])
    inv0 = b.new("FunctionNodeInvertRotation")
    b.link(rot0.outputs[0], inv0.inputs[0])
    turn = b.new("FunctionNodeRotateRotation", rotation_space="GLOBAL")
    b.link(inv0.outputs[0], turn.inputs["Rotation"])
    b.link(align.outputs[0], turn.inputs["Rotate By"])
    there = b.new("FunctionNodeCombineTransform")
    b.link(mid, there.inputs["Translation"])
    b.link(turn.outputs[0], there.inputs["Rotation"])
    back = b.new("FunctionNodeCombineTransform")
    b.link(_vmath(b, "SCALE", _attr(b, "fr_mid", "FLOAT_VECTOR")), back.inputs["Translation"])
    back.inputs["Translation"].links[0].from_node.inputs["Scale"].default_value = -1.0
    cable = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    b.link(gin.outputs["Cable"], cable.inputs["Object"])
    m = None
    for factor in (cable.outputs["Transform"], there.outputs[0], back.outputs[0], _attr(b, "fr_r0", "FLOAT4X4")):
        if m is None:
            m = factor
            continue
        mm = b.new("FunctionNodeMatrixMultiply")
        b.link(m, mm.inputs[0])
        b.link(factor, mm.inputs[1])
        m = mm.outputs[0]
    store = b.new("GeometryNodeStoreNamedAttribute", data_type="FLOAT4X4", domain="POINT")
    store.inputs["Name"].default_value = "fr_m"
    b.link(gin.outputs["Geometry"], store.inputs["Geometry"])
    b.link(m, flex._sock(store.inputs, "Value"))
    b.link(store.outputs[0], gout.inputs[0])


def _run_tree():
    ng = bpy.data.node_groups.get(RUN_TREE)
    if ng is not None and ng.get(TAG) == VERSION:
        return ng
    if ng is not None:
        ng.name = RUN_TREE + " old"
    ng = bpy.data.node_groups.new(RUN_TREE, "GeometryNodeTree")
    ng[TAG] = VERSION
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for label_, kind_ in _INPUTS:
        ng.interface.new_socket(label_, in_out="INPUT", socket_type=kind_)
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    _build_run(ng)
    _STATE["inputs"].pop(RUN_TREE, None)
    return ng


def _inputs(ng) -> dict:
    out = _STATE["inputs"].get(ng.name)
    if out is None:
        out = {s.name: s.identifier for s in ng.interface.items_tree
               if getattr(s, "item_type", "SOCKET") == "SOCKET" and s.in_out == "INPUT"}
        _STATE["inputs"][ng.name] = out
    return out


def _part_tree():
    from . import tracks
    return tracks._tree("part"), tracks._inputs(tracks._tree("part"))


# ---------------------------------------------------------------------------
# reading a thing on the cable
# ---------------------------------------------------------------------------

def parts_from(objects) -> list:
    """The CAD parts of the picked objects (an assembly: every part under it), each once, in a fixed order."""
    out, seen = [], set()
    for ob in objects:
        if ob is None:
            continue
        group = [ob] if ob.type == "MESH" else [o for o in logic.descendants(ob) if o.type == "MESH"]
        for o in group:
            if o.type == "MESH" and o.name not in seen and o.get(build.PROP_KIND, "part") == "part":
                seen.add(o.name)
                out.append(o)
    return out


def _verts(ob) -> np.ndarray:
    me = ob.data
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def _at(m: np.ndarray, p: np.ndarray) -> np.ndarray:
    return p @ m[:3, :3].T + m[:3, 3]


def _axis_line(mids: np.ndarray):
    """(a point, rows whose first is the direction) of the line through the most parts' middles: a CPS tube and its
    rings lie on one line, chocks and brackets beside it do not. Every line through two middles is tried; the one
    that passes most middles within 1 mm (then the longest) is fitted again through those."""
    n = len(mids)
    extent = float(np.linalg.norm(mids.max(0) - mids.min(0)))
    tol = max(1e-3, 1e-4 * extent)
    best, best_key = None, (-1, -1.0)
    for i in range(n):
        for j in range(i + 1, n):
            d = mids[j] - mids[i]
            ln = float(np.linalg.norm(d))
            if ln < 1e-9:
                continue
            d = d / ln
            rel = mids - mids[i]
            dist = np.linalg.norm(rel - np.outer(rel @ d, d), axis=1)
            on = dist <= tol
            key = (int(on.sum()), float(np.ptp(rel[on] @ d)))
            if key > best_key:
                best, best_key = on, key
    on = best if best is not None and best.sum() >= 2 else np.ones(n, dtype=bool)
    cen = mids[on].mean(axis=0)
    _u, _s, vt = np.linalg.svd(mids[on] - cen)
    return cen, vt


def _read(scene, item, objects, flip: bool) -> dict:
    """The thing's axis, front and its parts' places along it, in the CAD pose (cable part coordinates)."""
    paths = _paths()
    memo: dict = {}
    inv_cp = np.linalg.inv(paths._cad(item.part, memo))
    scale = paths._scale(paths._world(item.part))
    pts, mids, R0 = [], [], []
    for ob in objects:
        m = inv_cp @ paths._cad(ob, memo)
        v = _at(m, _verts(ob)) if len(ob.data.vertices) else m[:3, 3][None]
        pts.append(v)
        mids.append(0.5 * (v.min(axis=0) + v.max(axis=0)))
        R0.append(m)
    mids = np.array(mids)
    if len(objects) >= 2 and float(np.linalg.norm(mids.max(0) - mids.min(0))) > 1e-6:
        cen, vt = _axis_line(mids)
    else:
        allp = np.concatenate(pts)
        cen = allp.mean(axis=0)
        _u, _s, vt = np.linalg.svd(allp - cen, full_matrices=False)
    a0 = vt[0] / np.linalg.norm(vt[0])
    # the front looks the way the cable goes (towards its end) where the thing lies next to it
    shape = paths.shape_now(scene, item)
    if len(shape) >= 2:
        world_cen = _at(np.array(paths._world(item.part)), cen[None])[0]
        k = int(np.argmin(np.linalg.norm(shape - world_cen, axis=1)))
        k = min(k, len(shape) - 2)
        t = shape[k + 1] - shape[k]
        t = np.linalg.inv(np.array(paths._world(item.part)))[:3, :3] @ t
        if float(t @ a0) < 0.0:
            a0 = -a0
    if flip:
        a0 = -a0
    spans = [((v - cen) @ a0) for v in pts]
    front = max(float(sp.max()) for sp in spans)
    rows = []
    for ob, sp, m in zip(objects, spans, R0):
        lo, hi = float(sp.min()), float(sp.max())
        rows.append({"ob": ob, "at": (front - hi) * scale, "length": max(hi - lo, 1e-6) * scale,
                     "mid": cen + a0 * (0.5 * (lo + hi)), "r0": m})
    total = (front - min(float(sp.min()) for sp in spans)) * scale
    return {"axis": a0, "front": cen + a0 * front, "rows": rows, "length": total, "scale": scale}


def _cable_end_mark(scene, item) -> float:
    """Mark of the cable's end (metres from its start with nothing paid out)."""
    paths = _paths()
    if item.b_kind == "SEA":
        return float(item.sea_mark)
    from . import paths_sea
    return float(item.length) - paths_sea.payout(scene, item)


def _hang_mark(scene, item) -> float:
    """Mark of the point the cable leaves its last contact now (metres along the drawn path, nothing paid out)."""
    paths = _paths()
    from . import paths_sea
    if item.b_kind == "SEA":
        got = paths_sea._STATE["sea"].get(paths._k(scene, item))
        if got is not None:
            arrays = paths._arrays(scene, item)
            if arrays is not None:
                pass
    wheels = paths._wheels(item)
    s = float(wheels[-1].s) + 0.5 * float(wheels[-1].wrap) * paths.radius_of(item, wheels[-1]) if wheels else 0.0
    return s - paths_sea.payout(scene, item)


def mark_of(scene, item, rider) -> float:
    """Mark of the rider's front end."""
    if rider.where == "MARK":
        return _hang_mark(scene, item) - float(rider.at)
    return _cable_end_mark(scene, item) - float(rider.at)


# ---------------------------------------------------------------------------
# the run object
# ---------------------------------------------------------------------------

def _run_name(item) -> str:
    return f"{RUN} {_paths().label(item)}"


def run_object(scene, item):
    ob = bpy.data.objects.get(_run_name(item))
    if ob is not None and ob.get(TAG) is None:
        return None
    return ob


def _rows(scene, item) -> list:
    """One row per riding part of the cable's riders that are on."""
    out = []
    for r in item.riders:
        if not r.enabled:
            continue
        mark = mark_of(scene, item, r)
        for p in r.parts:
            if not _alive(scene, p.part) or "fr_mid" not in p or "fr_r0" not in p:
                continue
            out.append({"ob": p.part, "sa": mark - float(p.at) - float(p.length), "len": float(p.length),
                        "mid": np.array(p["fr_mid"], dtype=float), "q": np.array(p["fr_q"], dtype=float),
                        "r0": np.array(p["fr_r0"], dtype=float).reshape(4, 4)})
    return out


def _run_mesh(name: str, rows: list):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(rows))
    for attr, kind, vals in (("fr_sa", "FLOAT", [r["sa"] for r in rows]), ("fr_len", "FLOAT", [r["len"] for r in rows])):
        at = me.attributes.new(attr, kind, "POINT")
        at.data.foreach_set("value", np.array(vals, dtype=np.float32))
    for attr, key in (("fr_mid", "mid"), ("fr_q", "q")):
        at = me.attributes.new(attr, "FLOAT_VECTOR", "POINT")
        at.data.foreach_set("vector", np.array([r[key] for r in rows], dtype=np.float32).reshape(-1))
    at = me.attributes.new("fr_r0", "FLOAT4X4", "POINT")
    at.data.foreach_set("value", np.array([r["r0"].T.reshape(-1) for r in rows], dtype=np.float32).reshape(-1))
    me[TAG] = True
    me.update()
    return me


def _pay_driver(scene, item, ob, ins) -> None:
    """The run's Pay = metres paid out + BIAS, by a simple-expression driver on the cable joint."""
    paths = _paths()
    path = f'modifiers["{RUN_MOD}"].properties.inputs.{ins["Pay"]}.value'
    j = joints.find(scene, item.joint) if item.joint else None
    top, k, c = joints.chain_affine(scene, j) if j is not None else (None, 1.0, 0.0)
    ad = ob.animation_data
    fc = ad.drivers.find(path) if ad is not None else None
    mod = ob.modifiers[RUN_MOD]
    if top is None or top.motion is None:
        if fc is not None:
            ob.driver_remove(path)
        getattr(mod.properties.inputs, ins["Pay"]).value = BIAS
        return
    sign = -1.0 if item.reverse else 1.0
    expr = joints.expression(k * sign, c * sign + BIAS)
    if fc is not None and fc.driver.expression == expr and len(fc.driver.variables) == 1 and \
            fc.driver.variables[0].targets[0].id == top.motion:
        return
    if fc is not None:
        ob.driver_remove(path)
    joints._scripted(ob.driver_add(path), top.motion, expr)
    del paths


def sync(scene, item) -> None:
    """The cable's run and its riding parts' modifiers for how the riders are set now (none: all of it goes)."""
    paths = _paths()
    rows = _rows(scene, item) if item.enabled and _alive(scene, item.part) else []
    ob = run_object(scene, item)
    if not rows:
        _remove_run(scene, item)
        return
    me = _run_mesh(_run_name(item), rows)
    if ob is None:
        ob = bpy.data.objects.new(_run_name(item), me)
        ob[TAG] = paths.label(item)
        ob.hide_select = True
        ob.hide_render = True
        flex._collection(scene).objects.link(ob)
    else:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    tree = _run_tree()
    ins = _inputs(tree)
    mod = ob.modifiers.get(RUN_MOD)
    if mod is None or mod.type != "NODES":
        mod = ob.modifiers.new(RUN_MOD, "NODES")
    if mod.node_group != tree:
        mod.node_group = tree
    after_draw(scene, item, ob=ob)
    _pay_driver(scene, item, ob, ins)
    ptree, pins = _part_tree()
    names = set()
    for k, r in enumerate(rows):
        part = r["ob"]
        names.add(part.name)
        part[TAG] = paths.label(item)
        m = part.modifiers.get(MOD)
        if m is None or m.type != "NODES":
            m = part.modifiers.new(MOD, "NODES")
        if m.node_group != ptree:
            m.node_group = ptree
        flex._put(m, pins["Run"], ob)
        flex._put(m, pins["Index"], k)
        if not (m.show_viewport and m.show_render):
            m.show_viewport = m.show_render = True
        part.update_tag()
    for r in item.riders:                       # parts of riders that are off: their CAD place
        for p in r.parts:
            if _alive(scene, p.part) and p.part.name not in names:
                _strip(p.part)
    ob.update_tag()


def after_draw(scene, item, ob=None) -> None:
    """The cable's shapes mesh was written again: the run reads its layout (frames, points per frame)."""
    paths = _paths()
    ob = ob if ob is not None else run_object(scene, item)
    if ob is None:
        return
    mod = ob.modifiers.get(RUN_MOD)
    if mod is None:
        return
    ins = _inputs(_run_tree())
    sh = paths._shapes(scene, item)
    frames, per, first = paths._layout_of(sh)
    scale = paths._scale(paths._world(item.part))
    values = {"Shapes": sh, "First": first, "Frames": max(frames, 1), "Per frame": per, "Offset": 0, "Count": per,
              "Cable": item.part, "Unit": 1.0 / max(scale, 1e-12)}
    changed_ = False
    for name, value in values.items():
        changed_ |= flex._put(mod, ins[name], value)
    if changed_:
        ob.update_tag()


def _strip(part) -> None:
    try:
        m = part.modifiers.get(MOD)
        if m is not None:
            part.modifiers.remove(m)
        if TAG in part:
            del part[TAG]
        part.update_tag()
    except ReferenceError:
        pass


def _remove_run(scene, item) -> None:
    ob = run_object(scene, item)
    if ob is not None:
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    for r in item.riders:
        for p in r.parts:
            if _alive(scene, p.part):
                _strip(p.part)


def remove_all(scene, item) -> None:
    """The cable goes: its riders' parts show where CAD has them."""
    _remove_run(scene, item)


# ---------------------------------------------------------------------------
# what the panel and 0082 call
# ---------------------------------------------------------------------------

def _write(scene, item, rider, objects) -> None:
    geo = _read(scene, item, objects, bool(rider.flip))
    with flex._quiet(rider):
        rider.parts.clear()
        for row in geo["rows"]:
            p = rider.parts.add()
            p.part, p.part_uid = row["ob"], _uid(row["ob"])
            p.at, p.length = row["at"], row["length"]
            p["fr_mid"] = [float(v) for v in row["mid"]]
            q = Vector((0.0, 0.0, 1.0)).rotation_difference(Vector(tuple(float(v) for v in geo["axis"])))
            p["fr_q"] = list(q.to_euler("XYZ"))
            p["fr_r0"] = [float(v) for v in np.asarray(row["r0"]).reshape(-1)]
        rider.length = geo["length"]
        rider.origin = tuple(float(v) for v in geo["front"])
        rider.axis = tuple(float(v) for v in geo["axis"])
        rider.mark = mark_of(scene, item, rider)


def add(scene, item, objects, where: str = "END", at: float = 5.0, name: str = ""):
    """Fit the picked parts (or assemblies) on the cable ``item``: they ride along with it. ``where`` END: the
    front ``at`` metres from the cable's end; MARK: the front passes the last contact when ``at`` metres are paid
    out. Returns the new rider. Raises RiderError."""
    paths = _paths()
    if paths.broken(scene, item):
        raise RiderError(f"Cable '{paths.label(item)}' is not drawn yet: {paths.broken(scene, item)}")
    parts = [o for o in parts_from(objects) if o != item.part]
    if not parts:
        raise RiderError("Click the parts (or the assembly) to put on the cable first")
    taken = {p.part.name for it in scene.fresing.cables for r in it.riders for p in r.parts if p.part is not None}
    double = [o.name for o in parts if o.name in taken]
    if double:
        raise RiderError(f"'{double[0]}' already rides on a cable")
    r = item.riders.add()
    with flex._quiet(r):
        base = name or (parts[0].parent.get(build.PROP_NAME) if parts[0].parent is not None and len(parts) > 1
                        else parts[0].get(build.PROP_NAME, parts[0].name)) or "Thing on the cable"
        names = {x.name for x in item.riders}
        r.name = base if base not in names else next(f"{base} {k}" for k in range(2, 999)
                                                       if f"{base} {k}" not in names)
        r.where, r.at = where, float(at)
    _write(scene, item, r, parts)
    item.riders_index = len(item.riders) - 1
    sync(scene, item)
    return r


def remove(scene, item, index: int) -> None:
    if not 0 <= index < len(item.riders):
        return
    for p in item.riders[index].parts:
        if _alive(scene, p.part):
            _strip(p.part)
    item.riders.remove(index)
    item.riders_index = max(0, min(item.riders_index, len(item.riders) - 1))
    sync(scene, item)


def changed(scene, rider) -> None:
    item = cable_of(scene, rider)
    if item is None:
        return
    objects = [p.part for p in rider.parts if _alive(scene, p.part)]
    if objects:
        _write(scene, item, rider, objects)
    sync(scene, item)


def after_model_update(scene, by_uid: dict) -> list[str]:
    """Riders go to the matching new parts (by their part IDs) and are read again."""
    out = []
    for it in scene.fresing.cables:
        for r in it.riders:
            objects = []
            for p in r.parts:
                ob = by_uid.get(p.part_uid) if p.part_uid else None
                if ob is None and _alive(scene, p.part):
                    ob = p.part
                if ob is not None:
                    objects.append(ob)
            if not objects:
                out.append(f"'{r.name}' on cable '{it.name}': its parts are no longer in the model")
                continue
            try:
                _write(scene, it, r, objects)
            except Exception as exc:               # (a model update never fails over a rider)
                out.append(f"'{r.name}' on cable '{it.name}' could not be read again: {exc}")
        if len(it.riders):
            sync(scene, it)
    return out


def matrix_now(scene, item, part) -> np.ndarray | None:
    """The world matrix the part is drawn with now (from the run's evaluated points), or None."""
    ob = run_object(scene, item)
    if ob is None:
        return None
    rows = _rows(scene, item)
    k = next((i for i, r in enumerate(rows) if r["ob"] == part), -1)
    if k < 0:
        return None
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    att = ev.data.attributes.get("fr_m")
    if att is None or len(att.data) <= k:
        return None
    vals = np.empty(len(att.data) * 16, np.float32)
    att.data.foreach_get("value", vals)
    return vals.reshape(-1, 4, 4)[k].T.astype(float)


def describe(scene, item, rider) -> str:
    """'6 parts, 4.05 m, front 5.00 m from the cable's end' …"""
    from ..core.words import plural
    where = (f"front {rider.at:.2f} m from the cable's end" if rider.where == "END"
             else f"passes the last contact at {rider.at:.2f} m paid out")
    return f"{plural(len(rider.parts), 'part')}, {rider.length:.2f} m long, {where}"


del math, Matrix
