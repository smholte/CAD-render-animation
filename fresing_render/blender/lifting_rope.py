"""The hoist rope reeved in its falls (task 0232, Lifting lane L5): 8 Lifting plan > Equipment > Reeve the rope.

A placed crane's rope runs from its winch drum over the head's lead sheave, down and up through the hook block's
sheaves (``core/lifting_reeve.path``) to the dead end. The app draws it itself:

* **The rope**: one object "FR rope <crane>" – a polyline mesh whose points belong to three vertex groups (drum, head,
  block); a **Hook** modifier per group ties them to the motion empty of the joint that carries that frame (the slew,
  the hook swing, the hoist), and Geometry Nodes sweep a round tube along it. Raising or lowering the hook, luffing,
  telescoping or slewing moves the hooked points: the falls get longer or shorter by themselves, in the view, in a
  Build, in renders and in the render queue – no Python runs per frame, and scripts may be off.
* **The sheaves**: "FR head sheaves <crane>" (child of the hook swing's motion) and "FR block sheaves <crane>" (child
  of the hoist's motion), one disc per sheave (4 + 4 on the AT-100).
* **The drum**: a joint "<crane> · Hoist drum" (moves nothing of the CAD model, sits on the slew) that follows the
  hoist by a table from ``core/spool.py``'s layers (``lifting_reeve.drum_table``): hook 1 m up = falls metres wound on.
  "FR drum <crane>" (barrel, flanges, spokes) turns with it; "FR drum rope <crane>" is the rope on it, its outside
  radius driven by the same table.

The CAD's one-piece "HOIST ROPE" part is hidden for good (excluded) and its cable (4 Motion > Cables and paths) goes.
New cranes are reeved when they are placed; cranes of older projects keep their one-piece rope until Reeve the rope.
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..core import lifting_reeve as RV
from . import joints, lifting, logic

ROPE = "FR rope "
HEAD = "FR head sheaves "
BLOCK = "FR block sheaves "
DRUM = "FR drum "
COIL = "FR drum rope "
TAG = "fr_reeved"          # on every object the reeving made: the crane's name
DRUM_JOINT = "Hoist drum"
OWNER = "lifting:rope"


# ---------------------------------------------------------------------------------------------------------------------
# what the crane's file says (or a guess for a crane whose file has no reeving)

def falls_of(data: dict) -> int:
    hb = (data.get("hook_blocks") or [{}])[0]
    n = hb.get("falls") or (data.get("rig") or {}).get("hook", {}).get("falls") or hb.get("sheaves") or 1
    return max(1, int(n))


def spec(data: dict, rig) -> dict:
    """The crane file's ``reeving`` table, or one guessed from its rig (an own crane set up before task 0232)."""
    rv = data.get("reeving")
    if isinstance(rv, dict) and "head_r" in rv:
        return rv
    hoist = rig.role["hoist"]
    head = np.asarray(rig._p[hoist], float)
    luff = np.asarray(rig._p[rig.role["luff"]], float)
    d = 16.0
    return {"units": "mm", "rope_d": d, "head_r": 250.0, "block_r": 200.0, "head_pitch": 3 * d, "block_pitch": 3 * d,
            "block_above_hook": 800.0,
            "drum": {"centre": [float(luff[0] - 1200.0), 0.0, float(max(luff[2] - 900.0, 600.0))], "r": 250.0,
                     "w": 600.0, "joint": rig.role["slew"]},
            "k": 1.04, "guessed": True, "head_at": head.tolist()}


# ---------------------------------------------------------------------------------------------------------------------
# small meshes

def _disc(vs, fs, c, u, v, w, r, half, n=24):
    """A closed round disc (cylinder) about axis w through c, radius r, half its width along w."""
    base = len(vs)
    for side in (-half, half):
        for k in range(n):
            a = 2 * math.pi * k / n
            vs.append(c + w * side + r * (u * math.cos(a) + v * math.sin(a)))
    for k in range(n):
        k2 = (k + 1) % n
        fs.append((base + k, base + k2, base + n + k2, base + n + k))
    fs.append(tuple(base + k for k in reversed(range(n))))
    fs.append(tuple(base + n + k for k in range(n)))


def _mesh_object(name: str, vs, fs, coll, material=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, p)) for p in vs], [], fs)
    me.update()
    for p in me.polygons:
        p.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if material is not None:
        ob.data.materials.append(material)
    return ob


def _keep_on(ob, target) -> None:
    """Parent ``ob`` to ``target`` and keep where it is now."""
    ob.parent = target
    ob.matrix_parent_inverse = target.matrix_world.inverted()


def _material(kind: str):
    from . import materials
    try:
        if kind == "rope":
            return materials.ensure_material("Hoist rope", "galvanized", "")
        if kind == "sheave":
            return materials.ensure_material("Sheaves", "steel_machined", "")
        return materials.ensure_material("Winch drum", "paint_satin", "RAL 9005")
    except Exception:  # noqa: BLE001 - a look is not worth a failed reeving
        return None


def _tube_tree(name: str, radius: float):
    from . import flex
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    b = flex._Nodes(ng)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
    curve = b.new("GeometryNodeMeshToCurve")
    b.link(gin.outputs[0], curve.inputs["Mesh"])
    circle = b.new("GeometryNodeCurvePrimitiveCircle")
    circle.inputs["Resolution"].default_value = 8
    circle.inputs["Radius"].default_value = float(radius)
    tube = b.new("GeometryNodeCurveToMesh")
    b.link(curve.outputs[0], tube.inputs["Curve"])
    b.link(circle.outputs["Curve"], tube.inputs["Profile Curve"])
    tube.inputs["Fill Caps"].default_value = True
    b.link(flex._slot(b, flex._shade(b, tube.outputs[0])), gout.inputs[0])
    return ng


# ---------------------------------------------------------------------------------------------------------------------
# reeving a crane

def is_reeved(crane) -> bool:
    return bool(crane.reeved) and any(r.obj is not None for r in crane.rope_objects)


def _motion(scene, crane, name: str):
    j = joints.find(scene, lifting.prefix(crane) + name)
    if j is None or j.motion is None:
        raise RuntimeError(f"{crane.name}: its joint '{name}' is gone – the rope cannot be reeved.")
    return j


def _frames(scene, crane, rig, sp, vals):
    """World matrices (m) of the three frames now: their origins on the head axle, the block axle and the drum."""
    hoist = rig.role["hoist"]
    head_joint = rig.by[hoist].get("rides_on") or hoist
    drum_joint = (sp.get("drum") or {}).get("joint") or rig.role["slew"]
    if drum_joint not in rig.by:
        drum_joint = rig.role["slew"]
    root = np.array(crane.root.matrix_world)
    head_c = np.asarray(rig._p[hoist], float)
    hook = np.asarray(rig.rig_data["hook"]["point"], float)
    block_c = hook + np.array([0.0, 0.0, float(sp.get("block_above_hook", 800.0))])
    drum_c = np.asarray(sp["drum"]["centre"], float)
    out = {}
    for key, jn, c in (("head", head_joint, head_c), ("block", hoist, block_c), ("drum", drum_joint, drum_c)):
        M = rig.motion(jn, vals)                         # mm, model frame, relative to the CAD pose
        F = np.eye(4)
        F[:3, :3] = M[:3, :3]
        F[:3, 3] = (M[:3, :3] @ c + M[:3, 3]) / 1000.0
        out[key] = (root @ F, jn)
    return out


def reeve(scene, crane) -> dict:
    """Reeve the crane's rope (again): the objects, the drum joint and its table. Returns a summary dict."""
    rig = lifting.rig_of(crane)
    data = lifting.item_at(lifting.path_of(crane)).data
    sp = spec(data, rig)
    falls = falls_of(data)
    rv = RV.from_data(sp, falls)
    unreeve(scene, crane, keep_cad=True)
    lifting._update()
    vals = lifting.values(scene, crane)
    fr = _frames(scene, crane, rig, sp, vals)
    targets = {k: _motion(scene, crane, jn).motion for k, (_M, jn) in fr.items()}
    H, B, D = (fr[k][0] for k in ("head", "block", "drum"))
    s = float(np.linalg.norm(H[:3, 0]))                  # the root's scale (1 for the built-ins)

    def local(M, p):
        return (np.linalg.inv(M) @ np.r_[p, 1.0])[:3] / s
    pts = RV.path(rv, local(H, D[:3, 3]), local(D, H[:3, 3]))
    coll = crane.root.users_collection[0] if crane.root.users_collection else scene.collection
    made = []
    # the rope
    world = [(H if fr_ == "head" else B if fr_ == "block" else D) @ np.r_[p * s, 1.0] for fr_, p in pts]
    me = bpy.data.meshes.new(ROPE + crane.name)
    me.from_pydata([tuple(map(float, w[:3])) for w in world], [(i, i + 1) for i in range(len(world) - 1)], [])
    me.update()
    rope = bpy.data.objects.new(ROPE + crane.name, me)
    coll.objects.link(rope)
    mat = _material("rope")
    if mat is not None:
        rope.data.materials.append(mat)
    for key in ("drum", "head", "block"):
        vg = rope.vertex_groups.new(name=key)
        vg.add([i for i, (f, _p) in enumerate(pts) if f == key], 1.0, "REPLACE")
    for key in ("drum", "head", "block"):
        m = rope.modifiers.new(f"FR hook {key}", "HOOK")
        m.object = targets[key]
        m.vertex_group = key
        m.falloff_type = "NONE"
        m.matrix_inverse = targets[key].matrix_world.inverted() @ rope.matrix_world
    gn = rope.modifiers.new("FR rope tube", "NODES")
    gn.node_group = _tube_tree("FR rope tube " + crane.name, rv.rope_d / 2.0 * s)
    made.append(rope)
    # the sheaves: one disc per sheave, a little bigger than the rope's middle
    smat = _material("sheave")
    for key, M, prefix_ in (("head", H, HEAD), ("block", B, BLOCK)):
        vs, fs = [], []
        u, v, w = M[:3, 0] / s, M[:3, 2] / s, M[:3, 1] / s
        for fr_, y, r in RV.sheave_list(rv):
            if fr_ != key:
                continue
            c = (M @ np.r_[0.0, y * s, 0.0, 1.0])[:3]
            pitch = rv.head_pitch if key == "head" else rv.block_pitch
            _disc(vs, fs, c, u, v, w, (r + rv.rope_d * 0.9) * s, 0.42 * pitch * s)
        if vs:
            ob = _mesh_object(prefix_ + crane.name, vs, fs, coll, smat)
            _keep_on(ob, targets[key])
            made.append(ob)
    # the drum: a joint that turns with the hoist by a table, the barrel and the rope on it
    made += _drum(scene, crane, rig, rv, D, s, targets["drum"], coll)
    for ob in made:
        ob[TAG] = crane.name
        ob.hide_select = True
    for ob in made:
        r = crane.rope_objects.add()
        r.obj = ob
    _hide_cad_rope(scene, crane, data)
    crane.reeved = True
    crane.falls = falls
    lifting._update()
    return {"falls": falls, "head": rv.head, "block": rv.block, "dead_end": rv.dead_end, "points": len(pts),
            "guessed": bool(sp.get("guessed"))}


def _drum(scene, crane, rig, rv, D, s, carrier, coll) -> list:
    hoist = rig.role["hoist"]
    hj = joints.find(scene, lifting.prefix(crane) + hoist)
    hmax = joints.limits(hj)[1] if hj.use_limits else 60.0
    hmax = min(max(hmax, 1.0), 300.0)
    table = RV.drum_table(rv, hmax)
    origin = Vector(tuple(D[:3, 3]))
    axis = Vector(tuple(D[:3, 1])).normalized()
    name = lifting.prefix(crane) + DRUM_JOINT
    old = joints.find(scene, name)
    if old is not None:
        _remove_joint(scene, name)
    j = joints.create(scene, "ROTATE", [], origin, axis, name=name, base=carrier, allow_empty=True)
    j = joints.find(scene, name)
    j.use_limits = False
    joints.set_table(scene, j, lifting.prefix(crane) + hoist, table.hoist, table.angle, OWNER)
    j = joints.find(scene, name)
    lifting._update()
    turn = j.motion
    u, v, w = D[:3, 0] / s, D[:3, 2] / s, D[:3, 1] / s
    c = D[:3, 3]
    vs, fs = [], []
    _disc(vs, fs, c, u, v, w, rv.drum_r * s, rv.drum_w / 2 * s)                 # barrel
    for side in (-1, 1):                                                         # flanges
        _disc(vs, fs, c + w * side * (rv.drum_w / 2 + 0.02) * s, u, v, w,
              (float(table.outside.max()) + rv.rope_d) * s, 0.02 * s)
    for k in range(4):                                                           # spokes on the flanges: it turns
        a = k * math.pi / 2
        d = u * math.cos(a) + v * math.sin(a)
        for side in (-1, 1):
            p = c + w * side * (rv.drum_w / 2 + 0.045) * s + d * rv.drum_r * 0.6 * s
            _disc(vs, fs, p, u, v, w, 0.03 * s + 0.08 * rv.drum_r * s, 0.008 * s, n=8)
    drum = _mesh_object(DRUM + crane.name, vs, fs, coll, _material("drum"))
    _keep_on(drum, turn)
    # the rope on the drum: a unit cylinder about local z, scaled out to the rope's outside radius by a table driver
    vs, fs = [], []
    _disc(vs, fs, np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0]), 1.0,
          rv.drum_w / 2 * s * 0.98, n=32)
    coil = _mesh_object(COIL + crane.name, vs, fs, coll, _material("rope"))
    F = np.eye(4)
    F[:3, 0], F[:3, 1], F[:3, 2], F[:3, 3] = u, v, w, c
    coil.matrix_world = Matrix(F.tolist())
    lifting._update()
    _keep_on(coil, turn)
    src = hj.motion
    for i in (0, 1):
        fc = coil.driver_add("scale", i)
        joints._table_driver(fc, src, joints.Map(xs=table.hoist, ys=table.outside * s), 0.0)
    return [drum, coil]


def _hide_cad_rope(scene, crane, data) -> None:
    from . import paths, sheet
    s = scene.fresing
    p = lifting.prefix(crane)
    for i in reversed(range(len(s.cables))):
        if s.cables[i].name.startswith(p):
            paths.remove(scene, i)
    m = sheet.Model(scene, lifting.sheet_of(data), root=crane.root, prefix=p)
    parts = []
    for cab in (data.get("rig") or {}).get("cables") or []:
        parts += m.by_name.get(cab.get("part", ""), [])
    if parts:
        logic.exclude(parts)


def _remove_joint(scene, name: str) -> None:
    s = scene.fresing
    j = joints.find(scene, name)
    if j is None:
        return
    for ob in (j.motion, j.frame):
        if ob is not None:
            for ch in list(ob.children):
                if ch.get(TAG):
                    ch.parent = None
            bpy.data.objects.remove(ob, do_unlink=True)
    idx = next(i for i, x in enumerate(s.joints) if x.name == name)
    s.joints.remove(idx)
    s.joints_index = max(0, min(s.joints_index, len(s.joints) - 1))


def unreeve(scene, crane, keep_cad: bool = False) -> int:
    """Take the reeving away: its objects, their node trees and the drum joint. ``keep_cad`` False: the CAD rope part
    shows again (it stays a plain part; Place again makes it a cable)."""
    n = 0
    trees = []
    for r in crane.rope_objects:
        ob = r.obj
        if ob is None:
            continue
        for m in ob.modifiers:
            if m.type == "NODES" and m.node_group is not None:
                trees.append(m.node_group)
        me = ob.data if ob.type == "MESH" else None
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
        n += 1
    for ng in trees:
        try:
            if ng.users == 0:
                bpy.data.node_groups.remove(ng)
        except ReferenceError:
            pass
    crane.rope_objects.clear()
    _remove_joint(scene, lifting.prefix(crane) + DRUM_JOINT)
    if not keep_cad and crane.root is not None:
        data = lifting.item_at(lifting.path_of(crane)).data
        from . import sheet
        m = sheet.Model(scene, lifting.sheet_of(data), root=crane.root, prefix=lifting.prefix(crane))
        for cab in (data.get("rig") or {}).get("cables") or []:
            for ob in m.by_name.get(cab.get("part", ""), []):
                logic.exclude([ob], excluded=False)
    crane.reeved = False
    return n


# ---------------------------------------------------------------------------------------------------------------------
# reading it back (PC check, tour, tests)

def rope_object(crane):
    for r in crane.rope_objects:
        if r.obj is not None and r.obj.name.startswith(ROPE):
            return r.obj
    return None


def evaluated_points(scene, crane) -> np.ndarray:
    """The rope's middle line as Blender has it now (world, m): the polyline after the hooks."""
    ob = rope_object(crane)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    # the hooks' result is the mesh before the tube: read it from a copy without the tube
    keep = ob.modifiers["FR rope tube"].show_viewport
    ob.modifiers["FR rope tube"].show_viewport = False
    try:
        lifting._update()
        ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        co = np.zeros(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        ev.to_mesh_clear()
    finally:
        ob.modifiers["FR rope tube"].show_viewport = keep
        lifting._update()
    M = np.array(ob.matrix_world)
    co = co.reshape(-1, 3)
    return (M[:3, :3] @ co.T).T + M[:3, 3]


def falls_drawn(scene, crane) -> int:
    """How many straight pieces of the drawn rope run between a head point and a block point."""
    ob = rope_object(crane)
    if ob is None:
        return 0
    grp = {}
    for v in ob.data.vertices:
        for g in v.groups:
            grp[v.index] = ob.vertex_groups[g.group].name
    n = 0
    for i in range(len(ob.data.vertices) - 1):
        if {grp.get(i), grp.get(i + 1)} == {"head", "block"}:
            n += 1
    return n


def sheaves_drawn(crane) -> tuple[int, int]:
    """(head discs, block discs) of the drawn sheaves (24-sided discs: 26 faces each)."""
    out = []
    for prefix_ in (HEAD, BLOCK):
        ob = next((r.obj for r in crane.rope_objects if r.obj is not None and r.obj.name.startswith(prefix_)), None)
        out.append(len(ob.data.polygons) // 26 if ob is not None else 0)
    return out[0], out[1]


def drum_angle(scene, crane) -> float:
    j = joints.find(scene, lifting.prefix(crane) + DRUM_JOINT)
    return joints.get_value(j) if j is not None else 0.0


def check(scene, crane, travel: float = 1.0) -> str:
    """The reeving as drawn: its falls, its sheaves, and the rope wound on when the hook goes up ``travel`` m (the
    drum's turn x the rope's radius on it within a layer step of falls x travel). Raises ValueError."""
    if not is_reeved(crane):
        raise ValueError(f"{crane.name}: the rope is not reeved")
    data = lifting.item_at(lifting.path_of(crane)).data
    rig = lifting.rig_of(crane)
    falls = falls_of(data)
    rv = RV.from_data(spec(data, rig), falls)
    got = falls_drawn(scene, crane)
    if got != falls:
        raise ValueError(f"{got} falls drawn, the hook block has {falls}")
    hs, bs = sheaves_drawn(crane)
    if (hs, bs) != (rv.head, rv.block):
        raise ValueError(f"{hs} + {bs} sheaves drawn, the reeving needs {rv.head} + {rv.block}")
    hoist = rig.role["hoist"]
    was = lifting.values(scene, crane)
    h0 = float(was.get(hoist, 0.0))
    up = h0 - travel * 1000.0 if h0 - travel * 1000.0 >= 0 else h0 + travel * 1000.0
    try:
        p0 = evaluated_points(scene, crane)
        a0 = drum_angle(scene, crane)
        lifting.set_values(scene, crane, {hoist: up})
        p1 = evaluated_points(scene, crane)
        a1 = drum_angle(scene, crane)
    finally:
        lifting.set_values(scene, crane, {hoist: h0})
    length = lambda p: float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))   # noqa: E731
    dl = abs(length(p1) - length(p0))                    # the rope between drum and dead end: falls x travel
    want = falls * travel
    if abs(dl - want) > 0.01 * want + 0.05:
        raise ValueError(f"the drawn rope changed by {dl:.3f} m for {travel:g} m of hook travel, not {want:g} m")
    turned = abs(a1 - a0)
    r_lo = rv.drum_r + rv.rope_d / 2
    r_hi = r_lo + 60 * rv.rope_d
    if turned <= 0 or not (r_lo - 1e-6 <= want / turned <= r_hi):
        raise ValueError(f"the drum turned {math.degrees(turned):.0f}° for {want:g} m of rope")
    return (f"{crane.name}: {falls} falls over {hs} + {bs} sheaves, dead end on the {rv.dead_end}; hook "
            f"{travel:g} m: rope {dl:.3f} m, drum {math.degrees(abs(a1 - a0)):.0f}°")
