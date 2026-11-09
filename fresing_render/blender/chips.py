"""Chips in Blender (task 0028): what flies off the bit while milling, per bit type and workpiece material.

The physics is in ``core/chips.py``; this module connects it to the scene:

* **Inputs** come from the milling set-up (``blender/machining.py``): the bits' paths relative to the workpiece
  (read once per motion), the workpiece's CAD mesh, the finished part, and where the workpiece is in the world
  at every frame (read along with the paths).
* **Catch areas**: height fields made by casting rays straight down onto the parts that move together with
  the workpiece (the table, the vise) and onto the parts that stand still (the machine bed). A part counts as
  moving when it or one of its parents has keys, drivers or constraints on its position (joints).
* **Worked out once** ("baked") whenever the motion, the bits or the chip settings change: in the 3D view a
  moment after the change, in the render queue before the first frame (``machining.prepare``). Same input,
  same chips, on every PC and in any frame order.
* **Shown** as two point clouds whose points carry a chip shape, rotation, size and colour shade, instanced
  with a small Geometry Nodes group (no Python drivers, so it also works with scripts off): "FR Chips" rides
  along with the workpiece (Copy Transforms), "FR Chips (fallen)" holds the chips on the machine bed and the
  floor. The frame handler of milling writes them at every frame change.
"""

from __future__ import annotations

import time

import bpy
import numpy as np
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

from ..core import chips as core
from ..core import machining as mcore
from . import air, build, machining

COLLECTION = "FR Chips"
SHAPES_COLLECTION = "FR Chip shapes"
OBJ_RIDE = "FR Chips"
OBJ_WORLD = "FR Chips (fallen)"
NODE_GROUP = "FR Chips"
MAT_PREFIX = "FR chips "
TAG = "fr_chips"                      # on everything made here (value: its role)
MAT_VERSION = 1

TRANSFORM_PATHS = ("location", "rotation_euler", "rotation_quaternion", "rotation_axis_angle", "scale",
                   "delta_location", "delta_rotation_euler", "delta_rotation_quaternion", "delta_scale")

_RUNTIME: dict = {}                   # per scene name: {"key", "bake", "status", "error", "shapes_key", ...}


def settings(scene):
    return scene.fresing.milling


def runtime(scene) -> dict:
    return _RUNTIME.setdefault(scene.name, {})


def wanted(scene) -> bool:
    return settings(scene).chips != "NONE"


def is_on(scene) -> bool:
    return wanted(scene) and machining.is_active(scene)


def status(scene) -> str:
    return runtime(scene).get("status", "")


# ---------------------------------------------------------------------------
# what the chips are made of
# ---------------------------------------------------------------------------

def _workpiece_material(scene, wp) -> tuple:
    """(material key of its group in 3 Looks, group name)."""
    g = wp.get(build.PROP_GROUP, "") if wp is not None else ""
    grp = scene.fresing.groups.get(g) if g else None
    return (grp.material if grp is not None else ""), g


def family(scene) -> tuple:
    """(family, why): 'name', 'material', 'default' (read from the workpiece) or 'chosen'."""
    s = settings(scene)
    if s.chip_material != "AUTO":
        return s.chip_material, "chosen"
    wp = machining.workpiece(scene)
    key, group = _workpiece_material(scene, wp)
    names = [machining.name_of(wp) if wp is not None else "", group]
    return core.family_for(names, key)


def family_text(scene) -> str:
    fam, why = family(scene)
    label = core.FAMILIES.get(fam, fam)
    return {"name": f"{label} (from the workpiece's name)",
            "material": f"{label} (from the workpiece's material in 3 Looks)",
            "default": f"{label} (nothing in the workpiece's name or material: change it if needed)",
            "chosen": label}[why]


def _workpiece_colour(wp) -> tuple | None:
    """Linear base colour of the workpiece's material (plastic chips have the colour of their block)."""
    mat = wp.active_material if wp is not None else None
    nt = getattr(mat, "node_tree", None)
    if nt is None:
        return None
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return tuple(float(c) for c in n.inputs["Base Color"].default_value[:3])
    return None


# ---------------------------------------------------------------------------
# what moves with the workpiece, what stands still
# ---------------------------------------------------------------------------

def _moves_itself(ob) -> bool:
    ad = ob.animation_data
    if ad is not None:
        if any(fc.data_path in TRANSFORM_PATHS for fc in ad.drivers):
            return True
        if any(fc.data_path in TRANSFORM_PATHS for fc in machining._fcurves(ob)):
            return True
    return any(not c.mute for c in getattr(ob, "constraints", []))


def mover(ob, cache: dict) -> str:
    """Name of the nearest object (itself or a parent) that moves; '' when nothing above it moves."""
    chain = []
    p = ob
    while p is not None:
        if p.name in cache:
            out = cache[p.name]
            break
        chain.append(p)
        if _moves_itself(p):
            out = p.name
            chain.pop()
            cache[p.name] = out
            break
        p = p.parent
    else:
        out = ""
    for c in chain:
        cache[c.name] = out
    return out


def _tris_world(ob, m: Matrix) -> tuple:
    return _tris_world_mesh(ob.data, m)


def _bvh(meshes: list):
    vs, ts, off = [], [], 0
    for v, t in meshes:
        if not len(t):
            continue
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    if not vs:
        return None
    return BVHTree.FromPolygons(np.concatenate(vs).tolist(), np.concatenate(ts).tolist(), all_triangles=True)


def _cast(grid: core.Grid, bvh, z_from: float, down: bool = True) -> np.ndarray:
    """Heights where a ray from z_from going down (or up) first hits; -inf where it hits nothing."""
    from mathutils import Vector
    out = np.full(grid.h.shape, -np.inf if down else np.inf)
    if bvh is None:
        return out
    xs, ys = grid.centres()
    d = Vector((0.0, 0.0, -1.0 if down else 1.0))
    rc = bvh.ray_cast
    o = Vector((0.0, 0.0, z_from))
    for j, y in enumerate(ys):
        o.y = y
        row = out[j]
        for i, x in enumerate(xs):
            o.x = x
            hit = rc(o, d)[0]
            if hit is not None:
                row[i] = hit.z
    return out


def _parts_box(objs, m_of) -> tuple:
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for ob in objs:
        mm = np.array(m_of(ob))
        bb = np.array([list(c) + [1.0] for c in ob.bound_box])
        w = (mm @ bb.T).T[:, :3]
        lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
    return lo, hi


# ---------------------------------------------------------------------------
# inputs for the simulation
# ---------------------------------------------------------------------------

def _carry(s) -> tuple:
    """(M0, per-frame riding->world matrices) from the workpiece matrices read with the paths."""
    if "fr_wp_m" not in s or len(s["fr_wp_m"]) < 16:
        return None, None
    ms = np.array(s["fr_wp_m"], dtype=np.float64).reshape(-1, 4, 4)
    m0 = ms[0]
    inv0 = np.linalg.inv(m0)
    return m0, ms @ inv0


def _key(scene) -> tuple:
    s = settings(scene)
    wp = machining.workpiece(scene)
    fam, _why = family(scene)
    items = machining.cut_items(scene)
    return (s.path_sig, machining._stock_key(s, wp) if wp is not None else None,
            tuple(c.key() + (c.chip,) for c in items),
            s.chips, fam, s.chip_spindle, bool(s.chip_mist), scene.render.fps, round(scene.render.fps_base, 6),
            len(s.get("fr_wp_m", ())), air.key(scene))


def _inputs(scene) -> core.SimIn | None:
    s = settings(scene)
    wp = machining.workpiece(scene)
    m0, carry = _carry(s)
    if wp is None or m0 is None or s.stock_mesh is None:
        return None
    M0 = Matrix([list(r) for r in m0])
    fam, _why = family(scene)
    spin = 1.0 if s.chip_spindle == "CW" else -1.0
    # the bits: paths from the workpiece's own space into riding space
    bits_in = []
    for c in machining.cut_items(scene):            # a tool of a G-code program only while it is in the spindle
        p, tool = c.path, c.tool
        o = p.o @ m0[:3, :3].T + m0[:3, 3]
        d = p.d @ m0[:3, :3].T
        kind = c.chip or core.bit_kind(tool.kind, tool.radius)     # the tool list's type wins (task 0040)
        bits_in.append(core.BitIn(p.t, o, d, tool.radius, tool.length, mcore.tool_profile(tool),
                                  core.presets_for(fam, kind), spin))
    if not bits_in:
        return None
    # the air through the spindle follows each bit's whole path (task 0039); for the part in the spindle of a
    # program with tool changes: the path of the tool that is in the spindle at each moment (task 0040)
    air_in, bit_names = [], []
    pieces = {}
    for c in machining.cut_items(scene):
        if c.spindle is not None:
            pieces.setdefault(c.spindle.name, []).append(c.path)
    for it, ob in machining.bits(scene):
        p = machining._path(it)
        if p is None:
            continue
        if ob.name in pieces:
            ps = pieces[ob.name]
            t = np.concatenate([x.t for x in ps])
            order = np.argsort(t, kind="stable")
            p = mcore.Path(t[order], np.concatenate([x.o for x in ps])[order], np.concatenate([x.d for x in ps])[order])
        bit_names.append(ob.name)
        air_in.append(core.BitIn(p.t, p.o @ m0[:3, :3].T + m0[:3, 3], p.d @ m0[:3, :3].T, 1e-3, 1e-2,
                                 [(0.0, 1e-3), (1e-2, 1e-3)], [], spin))
    reach = core.throw_reach([pr for b in bits_in for pr in b.presets])
    if len(air.spans(scene)):                         # blown chips fly further: catch them there too (task 0039)
        reach = max(reach, min(float(air.settings(scene).air_reach), 1.0))
    # the workpiece: its CAD mesh in riding space
    sv, st = _tris_world_mesh(s.stock_mesh, M0)
    lo, hi = sv.min(axis=0), sv.max(axis=0)
    wgrid = core.grid_for(lo[:2] - 0.5 * core.MM, hi[:2] + 0.5 * core.MM, 0.25 * core.MM)
    sb = _bvh([(sv, st)])
    top = _cast(wgrid, sb, hi[2] + 0.01, down=True)
    bottom = _cast(wgrid, sb, lo[2] - 0.01, down=False)
    bottom = np.where(np.isfinite(bottom), bottom, -np.inf)
    wgrid.h = top
    floor = None
    fin = s.finished
    if fin is not None and fin.type == "MESH" and fin.data is not None:
        rel = machining._cad_world(wp).inverted() @ machining._cad_world(fin)
        fv, ft = _tris_world_mesh(fin.data, M0 @ rel)
        floor = _cast(wgrid, _bvh([(fv, ft)]), hi[2] + 0.01, down=True)
    work = core.WorkField(wgrid, bottom, floor)
    core.stamp_paths(work, bits_in)
    ride, static, floor_z = _catch(scene, wp, M0, lo, hi, reach, carry)
    f0 = int(s.get("fr_wp_f0", scene.frame_start))
    f1 = f0 + len(carry) - 1
    fps = scene.render.fps / (scene.render.fps_base or 1.0)
    return core.SimIn(fps=fps, f0=f0, f1=f1, bits=bits_in, work=work, ride=ride, static=static, floor_z=floor_z,
                      carry=carry, amount=s.chips, mist=bool(s.chip_mist),
                      air=air.inputs(scene, air_in, bit_names, carry, f0) if air_in else None)


def _tris_world_mesh(me, m: Matrix) -> tuple:
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", v)
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", t)
    mm = np.array(m)
    return v.reshape(-1, 3) @ mm[:3, :3].T + mm[:3, 3], t.reshape(-1, 3)


def _catch(scene, wp, M0: Matrix, lo, hi, reach: float, carry) -> tuple:
    """Height fields of what moves with the workpiece (riding space) and what stands still (world), and the floor."""
    s = settings(scene)
    skip = {wp.name}
    if s.finished is not None:
        skip.add(s.finished.name)
    skip |= {ob.name for _it, ob in machining.bits(scene)}
    cache = {}
    wp_mover = mover(wp, cache)
    riding, static, all_parts = [], [], []
    for ob in build.iter_parts(scene):
        if ob.get(build.PROP_EXCLUDED):
            continue
        all_parts.append(ob)
        if ob.name in skip or ob.hide_render or ob.data is None or not len(ob.data.polygons):
            continue
        mv = mover(ob, cache)
        if wp_mover and mv == wp_mover:
            riding.append(ob)
        elif not mv:
            static.append(ob)
    if not wp_mover:                                  # the workpiece stands still: so does everything around it
        riding, static = static, []
    to_ride = M0 @ wp.matrix_world.inverted()         # now -> riding space (for parts that move with it)
    floor_z = float(build.world_bounds(all_parts)[0][2]) if all_parts else float(lo[2]) - 0.5
    # riding: the table, vise, clamps around the workpiece; rays start a little above the workpiece
    box_lo, box_hi = lo[:2] - reach, hi[:2] + reach
    near = [ob for ob in riding if _overlaps(ob, lambda o: to_ride @ o.matrix_world, box_lo, box_hi)]
    rgrid = core.grid_for(box_lo, box_hi, 2 * core.MM)
    rgrid.h = _cast(rgrid, _bvh([_tris_world(ob, to_ride @ ob.matrix_world) for ob in near]), hi[2] + 0.05)
    # standing still: below the lowest point the riding chips can fall to (the table top or the workpiece bottom)
    static_grid = None
    if static:
        level = min(float(np.min(rgrid.h[np.isfinite(rgrid.h)])) if np.isfinite(rgrid.h).any() else np.inf,
                    float(lo[2]))
        # where the workpiece goes in the world during the animation
        corners = np.array([[x, y, z, 1.0] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        pts = np.einsum("fij,cj->fci", carry, corners)[:, :, :3].reshape(-1, 3) if carry is not None else corners[:, :3]
        slo, shi = pts.min(axis=0)[:2] - reach, pts.max(axis=0)[:2] + reach
        near_s = [ob for ob in static if _overlaps(ob, lambda o: o.matrix_world, slo, shi)]
        static_grid = core.grid_for(slo, shi, 4 * core.MM)
        z_from = level + 0.001 if np.isfinite(level) else float(hi[2]) + 0.05
        static_grid.h = _cast(static_grid, _bvh([_tris_world(ob, ob.matrix_world) for ob in near_s]), z_from)
    return rgrid, static_grid, floor_z


def _overlaps(ob, m_of, lo, hi) -> bool:
    blo, bhi = _parts_box([ob], m_of)
    return bool(bhi[0] >= lo[0] and blo[0] <= hi[0] and bhi[1] >= lo[1] and blo[1] <= hi[1])


# ---------------------------------------------------------------------------
# working them out
# ---------------------------------------------------------------------------

def bake(scene, force: bool = False):
    """The chips for the current set-up (worked out again when anything they depend on changed)."""
    rt = runtime(scene)
    if not is_on(scene):
        return None
    key = _key(scene)
    if not force and rt.get("key") == key and rt.get("bake") is not None:
        return rt["bake"]
    wm = None if bpy.app.background else bpy.context.window_manager
    t0 = time.perf_counter()
    if wm is not None:
        wm.progress_begin(0, 100)
    try:
        inp = _inputs(scene)
        if inp is None:
            rt.update(key=None, bake=None, status="Waiting for the motion to be read")
            return None
        t_in = time.perf_counter() - t0
        out = core.simulate(inp, (lambda f: wm.progress_update(int(f * 100))) if wm is not None else None)
    finally:
        if wm is not None:
            wm.progress_end()
    out.stats["inputs_s"] = t_in
    out.stats["family"] = family(scene)[0]
    rt.update(key=key, bake=out, error="", shown=None)
    rt["status"] = (f"{core.describe(out)} (+{t_in:.1f} s reading the machine)"
                    if out.count else "No chips: the bits do not cut anything in this animation")
    return out


def settings_changed(scene) -> None:
    """A chip setting changed: show it (read the motion again first if it was read before chips existed)."""
    s = settings(scene)
    if not wanted(scene):
        remove(scene)
        return
    if not machining.is_active(scene):
        return
    if "fr_wp_m" not in s:
        s.path_sig = ""                               # read with the workpiece's place at every frame
        machining.mark_stale(scene)
        if bpy.app.background:
            machining.prepare(scene)
        return
    show(scene)


# ---------------------------------------------------------------------------
# showing them
# ---------------------------------------------------------------------------

def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col[TAG] = "collection"
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _shapes_collection():
    col = bpy.data.collections.get(SHAPES_COLLECTION)
    if col is None:
        col = bpy.data.collections.new(SHAPES_COLLECTION)
        col[TAG] = "shapes"
        col.use_fake_user = True
    return col


def _node_group(shapes) -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.get(NODE_GROUP)
    if ng is not None and ng.get(TAG) == "nodes":
        info = next((n for n in ng.nodes if n.bl_idname == "GeometryNodeCollectionInfo"), None)
        if info is not None:
            sock = info.inputs["Collection"]
            if sock.default_value != shapes:       # every assignment rebuilds the whole dependency graph (0051)
                sock.default_value = shapes
            return ng
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(NODE_GROUP, "GeometryNodeTree")
    ng[TAG] = "nodes"
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    gin = n.new("NodeGroupInput")
    gout = n.new("NodeGroupOutput")
    gout.location = (700, 0)
    info = n.new("GeometryNodeCollectionInfo")
    info.location = (0, -200)
    info.inputs["Collection"].default_value = shapes
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    inst = n.new("GeometryNodeInstanceOnPoints")
    inst.location = (400, 0)
    inst.inputs["Pick Instance"].default_value = True

    def attr(name, kind, y):
        a = n.new("GeometryNodeInputNamedAttribute")
        a.data_type = kind
        a.inputs["Name"].default_value = name
        a.location = (0, y)
        return a
    idx = attr("fr_slot", "INT", -400)
    rot = attr("fr_rot", "QUATERNION", -550)
    sc = attr("fr_scale", "FLOAT", -700)
    ng.links.new(gin.outputs[0], inst.inputs["Points"])
    ng.links.new(info.outputs[0], inst.inputs["Instance"])
    ng.links.new(idx.outputs["Attribute"], inst.inputs["Instance Index"])
    ng.links.new(rot.outputs["Attribute"], inst.inputs["Rotation"])
    ng.links.new(sc.outputs["Attribute"], inst.inputs["Scale"])
    ng.links.new(inst.outputs[0], gout.inputs[0])
    return ng


def _display_object(scene, name: str, role: str):
    ob = bpy.data.objects.get(name)
    if ob is None or ob.get(TAG) != role or ob.type != "MESH":
        me = bpy.data.meshes.new(name)
        me[TAG] = role
        ob = bpy.data.objects.new(name, me)
        ob[TAG] = role
        ob.hide_select = True
    col = _collection(scene)
    if ob.name not in col.objects:
        col.objects.link(ob)
    mod = ob.modifiers.get("Chips")
    if mod is None:
        mod = ob.modifiers.new("Chips", "NODES")
    shapes = _shapes_collection()
    ng = _node_group(shapes)
    if mod.node_group is not ng:
        mod.node_group = ng
    return ob


def _follow(ob, wp) -> None:
    """The riding chips go wherever the workpiece goes (also with scripts off: a constraint, no Python)."""
    con = ob.constraints.get("Follow the workpiece")
    if con is None:
        con = ob.constraints.new("COPY_TRANSFORMS")
        con.name = "Follow the workpiece"
    if con.target is not wp:
        con.target = wp


def _material(fam: str, colour=None) -> bpy.types.Material:
    look = core.LOOKS.get(fam, core.LOOKS["ALU"])
    stops = look.stops
    if fam == "PLASTIC" and colour is not None:
        c = tuple(min(1.0, max(0.0, x)) for x in colour)
        stops = ((0.0, tuple(x * 0.85 for x in c)), (1.0, c))
    name = MAT_PREFIX + fam
    sig = repr((MAT_VERSION, stops, look.metallic, look.roughness, look.transmission))
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get(TAG) == sig:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    mat[TAG] = sig
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_type = "INSTANCER"
    attr.attribute_name = "fr_tint"
    attr.location = (-300, 0)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (0, 0)
    els = ramp.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1.0)
    for pos, rgb in stops[1:]:
        e = els.new(pos)
        e.color = (*rgb, 1.0)
    nt.links.new(attr.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = look.metallic
    bsdf.inputs["Roughness"].default_value = look.roughness
    if look.transmission:
        bsdf.inputs["Transmission Weight"].default_value = look.transmission
        bsdf.inputs["IOR"].default_value = 1.33
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mat.diffuse_color = (*stops[-1][1], 1.0)          # the colour in the solid view
    return mat


def _ensure_shapes(scene, bk) -> None:
    """One object per chip shape and variant in the shapes collection, in instance-index order."""
    rt = runtime(scene)
    fam = bk.stats.get("family", "ALU")
    wp = machining.workpiece(scene)
    colour = _workpiece_colour(wp) if fam == "PLASTIC" else None
    key = (tuple((p.family, p.bit, p.shape, p.length, p.width, p.thick, v) for p, v in bk.shapes), fam,
           tuple(round(c, 4) for c in colour) if colour else None)
    col = _shapes_collection()
    names = [f"FR chip {i:03d}" for i in range(len(bk.shapes))]
    if rt.get("shapes_key") == key and [o.name for o in sorted(col.objects, key=lambda o: o.name)] == names:
        return
    for ob in list(col.objects):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    for i, (p, v) in enumerate(bk.shapes):
        verts, tris = core.shape_mesh(p, v)
        me = bpy.data.meshes.new(names[i])
        me.from_pydata(verts.tolist(), [], tris.tolist())
        me.update()
        if p.shape in ("CURL", "HELIX", "COMMA", "RIBBON", "FLAKE", "DROP"):
            me.shade_smooth()
        me.materials.append(_material("MIST" if p.family == "MIST" else fam, colour))
        ob = bpy.data.objects.new(names[i], me)
        ob[TAG] = "shape"
        col.objects.link(ob)
    rt["shapes_key"] = key


def _write_points(me, pos, rot, slot, scale, tint) -> None:
    me.clear_geometry()
    n = len(pos)
    if n:
        me.vertices.add(n)
        me.vertices.foreach_set("co", np.asarray(pos, np.float32).reshape(-1))
    for name, kind, data in (("fr_slot", "INT", np.asarray(slot, np.int32)),
                             ("fr_rot", "QUATERNION", np.asarray(rot, np.float32)),
                             ("fr_scale", "FLOAT", np.asarray(scale, np.float32)),
                             ("fr_tint", "FLOAT", np.asarray(tint, np.float32))):
        a = me.attributes.get(name)
        if a is None or a.data_type != kind:
            if a is not None:
                me.attributes.remove(a)
            a = me.attributes.new(name, kind, "POINT")
        if n:
            a.data.foreach_set("value", data.reshape(-1))
    me.update()


def show(scene, T: float | None = None) -> bool:
    """Show the chips as they are at frame ``T`` (default: the current frame). True when shown."""
    rt = runtime(scene)
    if not is_on(scene):
        hide(scene)
        return False
    bk = bake(scene)
    if bk is None:
        hide(scene)
        return False
    if T is None:
        T = float(scene.frame_current + scene.frame_subframe)
    wp = machining.workpiece(scene)
    m0, _carry_m = _carry(settings(scene))
    _ensure_shapes(scene, bk)
    ride = _display_object(scene, OBJ_RIDE, "ride")
    world = _display_object(scene, OBJ_WORLD, "world")
    _follow(ride, wp)
    data = bk.at(T)
    inv = np.linalg.inv(m0)
    r = data[0]
    pos = r["pos"] @ inv[:3, :3].T + inv[:3, 3]
    q_inv = core.q_from_matrix(inv[:3, :3] / np.cbrt(max(abs(np.linalg.det(inv[:3, :3])), 1e-12)))
    rot = core.q_mul(np.broadcast_to(q_inv, (len(r["rot"]), 4)), r["rot"]) if len(r["rot"]) else r["rot"]
    _write_points(ride.data, pos, rot, r["slot"], r["scale"], r["tint"])
    w = data[1]
    _write_points(world.data, w["pos"], w["rot"], w["slot"], w["scale"], w["tint"])
    for ob in (ride, world):
        if ob.hide_render or ob.hide_viewport:
            ob.hide_render = ob.hide_viewport = False
    rt["shown"] = T
    rt["count"] = int(len(r["pos"]) + len(w["pos"]))
    return True


def hide(scene) -> None:
    """No chips in the picture (milling off, chips None, nothing to show): the objects stay, empty."""
    for name in (OBJ_RIDE, OBJ_WORLD):
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.get(TAG) and ob.data is not None and len(ob.data.vertices):
            ob.data.clear_geometry()
            ob.data.update()
    runtime(scene)["count"] = 0


def remove(scene) -> None:
    """Take every chip object, shape and node group out of the file."""
    _RUNTIME.pop(scene.name, None)
    for name in (OBJ_RIDE, OBJ_WORLD):
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.get(TAG):
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
    col = bpy.data.collections.get(SHAPES_COLLECTION)
    if col is not None and col.get(TAG):
        for ob in list(col.objects):
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        bpy.data.collections.remove(col)
    ng = bpy.data.node_groups.get(NODE_GROUP)
    if ng is not None and ng.get(TAG):
        bpy.data.node_groups.remove(ng)
    col = bpy.data.collections.get(COLLECTION)
    if col is not None and col.get(TAG) and not col.objects:
        bpy.data.collections.remove(col)
    for mat in [m for m in bpy.data.materials if m.name.startswith(MAT_PREFIX) and m.get(TAG)]:
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def clear(scene) -> None:
    """'Clear chips': no chips any more (the setting goes to None)."""
    s = settings(scene)
    if s.chips != "NONE":
        s.chips = "NONE"                              # its update removes everything
    else:
        remove(scene)


def forget() -> None:
    """A file was opened or the extension stops: what was worked out belongs to the old file."""
    _RUNTIME.clear()
