"""Milling in Blender (task 0027): the bit takes material away from the workpiece as the animation runs.

The geometry work is in ``core/machining.py``; this module connects it to the scene:

* **Set-up** (``scene.fresing.milling``): the bits, the workpiece, the optional finished part, the
  detail level. The workpiece shows a mesh of its own (``cut_mesh``, "<part> (milled)"); its CAD
  mesh (``stock_mesh``) stays untouched, so other copies of the part and "Stop milling" are unaffected.
* **Path**: the bits' tips and axes relative to the workpiece, read once at every frame of the
  animation (``sample``) and kept with the project (on each bit item: ``fr_t``, ``fr_o``, ``fr_d``).
  A fingerprint of everything that moves the bits or the workpiece (keys, drivers, joint axes,
  parents) tells when the path must be read again: after "Build & play", a joint change, a model
  update. In the 3D view that happens by itself a moment later; the render queue reads it before
  it renders (``prepare``).
* **Frames**: on every frame change the workpiece mesh is replaced by the state at that frame
  (a frame handler; works in the background renderer too). States at the end of straight moves
  are kept in memory, so scrubbing back and forth is quick and always gives the same mesh.

Nothing here needs the joints' or the animation's internals: the path is read from where Blender
puts the objects, so couplings, motors and G-code (later tasks) drive the bit like any other motion.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core import machining as core
from . import build
from .idprops import store_array

CUT_TAG = "fr_milled"                 # on the workpiece's own mesh
SHARP_ANGLE = math.radians(30.0)      # edges sharper than this stay crisp; round faces look smooth

_RUNTIME: dict = {}                   # per scene name: {"key", "timeline", "shown", ...}
_STATE = {"guard": 0, "pending": False}
#: answers kept while one frame is shown (``_on_frame``): "is this part in the scene", the G-code tool copies.
#: Both walk every object of the file; the frame code asked about 13 and 3 times a frame (bug hunt row 20c)
_FRAME: dict = {}


# ---------------------------------------------------------------------------
# set-up access
# ---------------------------------------------------------------------------

def settings(scene):
    return scene.fresing.milling


def name_of(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name) if ob is not None else ""


def _in_scene(scene, ob) -> bool:
    memo = _FRAME.get("in_scene")
    if memo is None:
        return ob.name in scene.objects
    key = (scene.name, ob.name)
    hit = memo.get(key)
    if hit is None:
        hit = memo[key] = ob.name in scene.objects
    return hit


def _tool_copies(scene) -> dict:
    """``gcode.copies``, once per frame while a frame is shown."""
    from . import gcode
    if "in_scene" not in _FRAME:
        return gcode.copies(scene)
    if "copies" not in _FRAME:
        _FRAME["copies"] = gcode.copies(scene)
    return _FRAME["copies"]


def bits(scene) -> list:
    """(bit item, object) for every bit whose part still exists."""
    return [(b, b.obj) for b in settings(scene).bits if b.obj is not None and _in_scene(scene, b.obj)]


def workpiece(scene):
    ob = settings(scene).workpiece
    return ob if ob is not None and _in_scene(scene, ob) else None


def is_set_up(scene) -> bool:
    return workpiece(scene) is not None and bool(bits(scene))


def is_active(scene) -> bool:
    return core.available() and is_set_up(scene) and settings(scene).enabled


def runtime(scene) -> dict:
    return _RUNTIME.setdefault(scene.name, {})


def status(scene) -> str:
    return runtime(scene).get("status", "")


# ---------------------------------------------------------------------------
# the bit's shape
# ---------------------------------------------------------------------------

def _mesh_points(ob) -> np.ndarray:
    me = ob.data
    v = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", v)
    return v.reshape(-1, 3)


def _triangles(me):
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", t)
    return t.reshape(-1, 3)


def _main_axis(ob, pts):
    """The bit's axis in its own space: the round faces' axis the most faces share, else its length."""
    me = ob.data
    if me is not None and "fr_axes" in me and "fr_axis_faces" in me:
        axes = np.array(me["fr_axes"], dtype=float).reshape(-1, 7)
        faces = list(me["fr_axis_faces"])
        weight = np.zeros(len(axes))
        for k in range(0, len(faces), 3):
            if faces[k + 2] < len(axes):
                weight[faces[k + 2]] += faces[k + 1]
        _c, long_dir = core.axis_from_points(pts)
        best, score = None, -1.0
        for i, a in enumerate(axes):
            d = a[3:6] / (np.linalg.norm(a[3:6]) or 1.0)
            if abs(d @ long_dir) < 0.95:             # a cross hole, not the bit's axis
                continue
            # coaxial round faces count together
            same = [j for j, b in enumerate(axes)
                    if abs(abs((b[3:6] / (np.linalg.norm(b[3:6]) or 1.0)) @ d) - 1) < 1e-4
                    and np.linalg.norm(np.cross(b[:3] - a[:3], d)) < 1e-5]
            w = weight[same].sum() + 1e-3 * a[6]
            if w > score:
                best, score = (a[:3].copy(), d), w
        if best is not None:
            return best
    return core.axis_from_points(pts)


#: a tool's tip read from its mesh this close to the axis its spindle turns about is put on that axis (task 0049)
SNAP_DIST = 0.5e-3
SNAP_ANGLE = 3.0                 # degrees


def on_turning_axis(ob, tip, axis, scene=None) -> tuple:
    """(tip, axis) in ``ob``'s own space, moved onto the axis of the rotate joint that turns ``ob`` (the spindle)
    when they are close (``SNAP_DIST``, ``SNAP_ANGLE``). A tip read from the mesh can lie a few hundredths of a mm
    beside the spindle's axis (a fluted tool's points are not round): turning, it went round in a small circle and
    the tip left the program's path by up to twice that (task 0049). Unchanged when nothing turns the part."""
    tip, axis = Vector(tip), Vector(axis)
    if scene is None:
        scene = ob.users_scene[0] if getattr(ob, "users_scene", ()) else None
    if scene is None or not hasattr(scene, "fresing") or axis.length < 1e-12:
        return tip, axis
    from . import joints
    axis = axis.normalized()
    mw = ob.matrix_world
    tip_w = mw @ tip
    ax_w = (mw.to_3x3() @ axis).normalized()
    best = None
    for j in scene.fresing.joints:
        if j.kind != "ROTATE" or j.motion is None or j.frame is None:
            continue
        p = ob
        while p is not None and p is not j.motion:
            p = p.parent
        if p is None:
            continue
        o, d = joints.axis_world(j)
        if abs(d.dot(ax_w)) < math.cos(math.radians(SNAP_ANGLE)):
            continue
        foot = o + d * (tip_w - o).dot(d)
        dist = (tip_w - foot).length
        if dist <= SNAP_DIST and (best is None or dist < best[0]):
            best = (dist, foot, d if d.dot(ax_w) >= 0 else -d)
    if best is None:
        return tip, axis
    inv = mw.inverted()
    new_axis = (inv.to_3x3() @ best[2]).normalized()
    return inv @ best[1], new_axis


def detect(ob, toward=None, flip: bool = False, snap: bool = True) -> dict:
    """Recognise the bit from its mesh: tip and axis (in its own space) and the shape.

    ``toward``: a world point the tip faces (the workpiece's centre); without it the tip is the
    end that is lowest in the world (bits point down). ``flip``: the tip is the other end."""
    pts = _mesh_points(ob)
    if len(pts) < 4:
        raise RuntimeError("This part has no shape to read")
    origin, d = _main_axis(ob, pts)
    tris = _triangles(ob.data)
    prof, zmin, zmax = core.profile_from_points(pts, origin, d, tris)
    ends = [Vector(origin + d * zmin), Vector(origin + d * zmax)]
    mw = ob.matrix_world
    wends = [mw @ e for e in ends]
    if toward is not None:
        tip_low = (wends[0] - Vector(toward)).length <= (wends[1] - Vector(toward)).length
    else:
        tip_low = wends[0].z <= wends[1].z
    if flip:
        tip_low = not tip_low
    if not tip_low:                                  # the tip is at the other end: turn the axis round
        d = -d
        prof, zmin, zmax = core.profile_from_points(pts, origin, d, tris)
    tip = origin + d * zmin
    if snap:                                         # on the spindle's axis when it turns the part (task 0049)
        t2, d2 = on_turning_axis(ob, Vector(tip), Vector(d))
        tip, d = np.array(t2), np.array(d2)
    tool = core.classify(prof)
    return {"tip": tuple(float(x) for x in tip), "axis": tuple(float(x) for x in d), "tool": tool,
            "profile": prof}


def apply_detection(item, info: dict, fill: bool = True) -> None:
    """Store what was read from the part; ``fill``: also put its sizes in the fields typed by hand."""
    t = info["tool"]
    item.tip = info["tip"]
    item.axis = info["axis"]
    item.auto = json.dumps({"kind": t.kind, "radius": t.radius, "length": t.length, "corner": t.corner,
                            "angle": t.angle, "profile": [list(p) for p in info["profile"]]})
    item.detected = core.describe(t)
    if not fill:
        return
    item["_busy"] = True
    try:
        item.diameter = 2 * t.radius
        item.length = t.length
        item.corner = t.corner if t.kind == "BULL" else min(1e-3, t.radius)
        item.angle = math.radians(t.angle if t.kind in ("VEE", "DRILL") else 90.0)
    finally:
        del item["_busy"]


def tool_of(item) -> core.Tool:
    """The shape a bit cuts with: recognised from the part, or the numbers typed in."""
    try:
        auto = json.loads(item.auto) if item.auto else {}
    except ValueError:
        auto = {}
    if item.shape == "AUTO":
        if not auto:
            return core.Tool("FLAT", radius=max(item.diameter / 2, 1e-4), length=max(item.length, 1e-3))
        return core.Tool(auto["kind"], radius=auto["radius"], length=auto["length"], corner=auto["corner"],
                         angle=auto["angle"],
                         profile=tuple(tuple(p) for p in auto.get("profile", ())) if auto["kind"] == "CUSTOM" else ())
    return core.Tool(item.shape, radius=max(item.diameter / 2, 1e-5), length=max(item.length, 1e-4),
                     corner=item.corner, angle=math.degrees(item.angle))


# ---------------------------------------------------------------------------
# the workpiece's own mesh
# ---------------------------------------------------------------------------

def _take_workpiece(scene, ob) -> None:
    """``ob`` shows a mesh of its own from now on; its CAD mesh is kept for 'Stop milling'."""
    s = settings(scene)
    stock = ob.data
    if stock.get(CUT_TAG):                       # already ours (undo, a second click)
        s.cut_mesh = stock
        return
    cut = stock.copy()
    cut.name = f"{stock.name} (milled)"
    cut[CUT_TAG] = True
    for key in ("fr_face_starts", "fr_axes", "fr_axis_faces"):     # they describe the CAD mesh only
        if key in cut:
            del cut[key]
    cut.fresing_decals.clear()               # decals stay on the CAD mesh (task 0051, bug hunt row 3)
    s.stock_mesh = stock
    s.cut_mesh = cut
    ob.data = cut
    lock_interface(scene)


def _give_back(scene, ob) -> None:
    """Put the CAD mesh back on ``ob`` and drop the milled one."""
    s = settings(scene)
    stock, cut = s.stock_mesh, s.cut_mesh
    if ob is not None and cut is not None and ob.data is cut and CUT_SLOT in cut:
        while len(cut.materials) > int(cut[CUT_SLOT]):          # the cut faces' slot is the milled mesh's only
            cut.materials.pop()
    if ob is not None and stock is not None and ob.data is not stock:
        while len(stock.materials) < len(ob.data.materials):   # the rules may have added slots meanwhile
            stock.materials.append(None)
        ob.data = stock
    s.stock_mesh = None
    s.cut_mesh = None
    if cut is not None and cut.users == 0:
        bpy.data.meshes.remove(cut)
    runtime(scene).clear()


def _drop_copied_decals(s) -> None:
    """Projects milled before 0.2.40 copied the block's decals onto the milled mesh, where an edit emptied them
    (bug hunt 0045 row 3): drop the copies and make the real ones (on the CAD mesh) again."""
    cut = s.cut_mesh
    if cut is None or not len(cut.fresing_decals):
        return
    cut.fresing_decals.clear()
    from . import decals
    for it in s.stock_mesh.fresing_decals:
        decals.rebuild(it)


def _ensure_own_mesh(scene, ob) -> bool:
    """The workpiece shows its milled mesh (after a model update it may have a new CAD mesh)."""
    s = settings(scene)
    if ob.data is not None and ob.data is s.cut_mesh and s.stock_mesh is not None:
        _drop_copied_decals(s)
        return True
    if ob.data is not None and ob.data.get(CUT_TAG) and s.stock_mesh is not None:
        s.cut_mesh = ob.data
        _drop_copied_decals(s)
        return True
    if ob.data is not None and ob.data.get(CUT_TAG):
        return False                             # the CAD mesh is lost: nothing to cut from
    old = s.cut_mesh
    s.cut_mesh = None
    _take_workpiece(scene, ob)
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    runtime(scene).clear()
    return True


def set_workpiece(scene, ob) -> None:
    s = settings(scene)
    old = workpiece(scene)
    if old is not None:
        _give_back(scene, old)
    s.workpiece = ob
    s.workpiece_uid = ob.get(build.PROP_UID, "")
    if ob is not None and s.enabled:
        _take_workpiece(scene, ob)
    mark_stale(scene)


def set_finished(scene, ob, update: bool = True) -> None:
    from . import logic
    s = settings(scene)
    old = s.finished
    if old is not None and old.name in scene.objects and old.get("fr_mill_hid"):
        del old["fr_mill_hid"]
        logic.set_hidden(old, False)
    s.finished = ob
    s.finished_uid = ob.get(build.PROP_UID, "") if ob is not None else ""
    if ob is not None and not logic.is_hidden(ob):
        logic.set_hidden(ob, True)                # only a limit: drawn twice it would flicker
        ob["fr_mill_hid"] = True
    for key in ("timeline", "wp", "wp_key", "shown"):
        runtime(scene).pop(key, None)
    if update:
        refresh(scene)


def add_bit(scene, ob):
    s = settings(scene)
    for i, b in enumerate(s.bits):
        if b.obj is ob:
            s.bits_index = i
            return b
    item = s.bits.add()
    item.obj = ob
    item.uid = ob.get(build.PROP_UID, "")
    apply_detection(item, detect(ob, _toward(scene)))
    s.bits_index = len(s.bits) - 1
    mark_stale(scene)
    return item


def _toward(scene):
    wp = workpiece(scene)
    return _world_centre(wp) if wp is not None else None


def flip_bit(scene, item) -> None:
    """The tip is at the other end of the part (read the shape again from there)."""
    if item.obj is None:
        return
    item.flipped = not item.flipped
    apply_detection(item, detect(item.obj, _toward(scene), item.flipped), fill=item.shape == "AUTO")
    mark_stale(scene)


def tool_changed(scene) -> None:
    """A bit's shape or size was changed by hand: cut again with it."""
    rt = runtime(scene)
    rt["timeline"] = None
    rt["shown"] = None
    refresh(scene)


def remove_bit(scene, index: int) -> None:
    s = settings(scene)
    if 0 <= index < len(s.bits):
        s.bits.remove(index)
        s.bits_index = max(0, min(s.bits_index, len(s.bits) - 1))
    runtime(scene).clear()
    if not s.bits:
        show_uncut(scene)
    else:
        mark_stale(scene)


def stop(scene) -> None:
    """Remove the whole set-up; the workpiece gets its CAD mesh back."""
    s = settings(scene)
    wp = workpiece(scene)
    s.bits.clear()
    if wp is not None:
        _give_back(scene, wp)
    set_finished(scene, None, update=False)
    s.workpiece = None
    s.workpiece_uid = ""
    s.path_sig = ""
    _RUNTIME.pop(scene.name, None)
    from . import chips
    chips.remove(scene)


def _world_centre(ob) -> Vector:
    corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return sum(corners, Vector()) / 8.0


def show_uncut(scene) -> None:
    """The milled mesh shows the workpiece as it came from CAD (milling off, or nothing to cut with)."""
    s = settings(scene)
    wp = workpiece(scene)
    from . import chips
    chips.hide(scene)
    if wp is None or s.stock_mesh is None or s.cut_mesh is None or wp.data is not s.cut_mesh:
        return
    _write_stock(s.cut_mesh, s.stock_mesh)
    runtime(scene)["shown"] = None


def enabled_changed(scene) -> None:
    s = settings(scene)
    wp = workpiece(scene)
    if wp is None:
        return
    if s.enabled:
        _take_workpiece(scene, wp)
        refresh(scene)
    else:
        _give_back(scene, wp)
        from . import chips
        chips.hide(scene)


# ---------------------------------------------------------------------------
# the look of the faces the cutter made (task 0051)
# ---------------------------------------------------------------------------

CUT_SLOT = "fr_cut_slot"              # on the milled mesh: the number of its material slot for cut faces
CUT_MAT_PREFIX = "FR_cut "            # the materials of cut faces ("FR " + name is a material group's)
CUT_KEY = "fr_cut_key"


def block_look(scene, wp) -> tuple:
    """(material id, colour) of the workpiece in 3 Looks: its group's, else what its material was built from."""
    g = wp.get(build.PROP_GROUP, "") if wp is not None else ""
    grp = scene.fresing.groups.get(g) if g else None
    if grp is not None:
        return grp.material, grp.color
    mat = wp.material_slots[0].material if wp is not None and wp.material_slots else None
    return (str(mat.get("fr_material", "")), str(mat.get("fr_color", ""))) if mat is not None else ("", "")


def cut_look(scene, wp) -> tuple | None:
    """(material id, tweaks, label, colour) of the faces the cutter made, or None: they look like the block."""
    from ..core import materials_lib
    s = settings(scene)
    if s.cut_look == "SAME":
        return None
    block_id, colour = block_look(scene, wp)
    if s.cut_look == "PICK":
        mid = s.cut_material
        look = (mid, {}, materials_lib.get(mid)["label"])
    else:
        look = core.cut_look(block_id)
        if look is None:
            return None
    mid, tweak, label = look
    return mid, tweak, label, (colour if materials_lib.needs_color(mid) else "")


def cut_material(scene, wp):
    """The Blender material of the faces the cutter made, or None (they show the block's own, slot 0)."""
    from . import materials
    look = cut_look(scene, wp)
    if look is None:
        return None
    mid, tweak, label, colour = look
    key = json.dumps([mid, tweak, colour, materials.LOOK_VERSION], sort_keys=True)
    name = CUT_MAT_PREFIX + label + (f" {colour}" if colour else "")
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    if mat.get(CUT_KEY) != key or mat.node_tree is None or not mat.node_tree.nodes:
        if mat.node_tree is None:
            mat.use_nodes = True
        materials.build_nodes(mat, mid, colour, 0.0, tweak)
        mat[CUT_KEY] = key
    return mat


def _cut_slot(scene, wp) -> int:
    """The milled mesh's material slot for cut faces (after the block's own slots), with its material set."""
    s = settings(scene)
    cut, stock = s.cut_mesh, s.stock_mesh
    n = len(stock.materials) if stock is not None else max(1, len(cut.materials))
    n = max(n, 1)
    if cut.get(CUT_SLOT) != n:
        cut[CUT_SLOT] = n
    while len(cut.materials) < n + 1:
        cut.materials.append(None)
    if wp.data is not cut or len(wp.material_slots) <= n:
        return n
    slot = wp.material_slots[n]
    if slot.link != "OBJECT":
        slot.link = "OBJECT"
    mat = cut_material(scene, wp)
    if mat is None:
        mat = wp.material_slots[0].material
    if slot.material is not mat:
        slot.material = mat
    return n


def cut_look_changed(scene) -> None:
    """'Cut faces' or its material changed: show it now."""
    wp = workpiece(scene)
    s = settings(scene)
    if wp is None or s.cut_mesh is None or wp.data is not s.cut_mesh:
        return
    _cut_slot(scene, wp)
    wp.update_tag()


def cut_look_text(scene) -> str:
    """What the cut faces look like, in words (the Milling panel)."""
    wp = workpiece(scene)
    if wp is None:
        return ""
    look = cut_look(scene, wp)
    if look is None:
        return "Cut faces look like the block"
    return f"Cut faces: {look[2]}" + (f" {look[3]}" if look[3] else "")


# ---------------------------------------------------------------------------
# what moves the bits: fingerprint and path
# ---------------------------------------------------------------------------

def _fcurves(id_block):
    ad = getattr(id_block, "animation_data", None)
    if ad is None or ad.action is None:
        return []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return list(cb.fcurves) if cb is not None else []
    except Exception:
        return list(getattr(ad.action, "fcurves", []))


def _hash_fcurve(h, fc) -> None:
    h.update(f"{fc.data_path}[{fc.array_index}]".encode())
    n = len(fc.keyframe_points)
    if n:
        a = np.empty(n * 2, dtype=np.float32)
        for prop in ("co", "handle_left", "handle_right"):
            fc.keyframe_points.foreach_get(prop, a)
            h.update(np.round(a.astype(np.float64), 7).tobytes())
        e = np.empty(n, dtype=np.int32)
        for prop in ("interpolation", "easing"):
            try:
                fc.keyframe_points.foreach_get(prop, e)
                h.update(e.tobytes())
            except (TypeError, AttributeError):
                pass
    h.update(str(len(fc.modifiers)).encode())


def _mat_bytes(m) -> bytes:
    return np.round(np.array([v for row in m for v in row], dtype=np.float64), 7).tobytes()


def chain_objects(scene) -> list:
    """Everything whose motion can move a bit or the workpiece: their parents up to the root, and
    the objects their drivers read."""
    s = settings(scene)
    start = [b for _i, b in bits(scene)] + ([workpiece(scene)] if workpiece(scene) else []) + _copies(scene)
    from . import air
    if air.uses_nozzle(scene):                        # the air nozzle is read along with the bits (task 0039)
        start.append(air.settings(scene).air_nozzle)
    seen, out, stack = set(), [], list(start)
    while stack:
        ob = stack.pop()
        if ob is None or ob.name in seen:
            continue
        seen.add(ob.name)
        out.append(ob)
        stack.append(ob.parent)
        ad = ob.animation_data
        if ad is not None:
            for fc in ad.drivers:
                for var in fc.driver.variables:
                    for tg in var.targets:
                        if isinstance(tg.id, bpy.types.Object):
                            stack.append(tg.id)
        for c in getattr(ob, "constraints", []):
            tgt = getattr(c, "target", None)
            if isinstance(tgt, bpy.types.Object):
                stack.append(tgt)
    _ = s
    return out


def signature(scene) -> str:
    """Changes whenever the bits' path relative to the workpiece may change."""
    h = hashlib.blake2b(digest_size=16)
    s = settings(scene)
    h.update(f"{scene.frame_start}:{scene.frame_end}:{scene.render.fps}:{scene.render.fps_base}".encode())
    for item, ob in bits(scene):
        h.update(f"bit:{ob.name}:{tuple(round(x, 7) for x in item.tip)}:{tuple(round(x, 7) for x in item.axis)}".encode())
    for ob in _copies(scene):                       # tool copies of a G-code build (task 0040)
        h.update(f"copy:{ob.name}:{tuple(round(x, 7) for x in ob['fr_tip'])}:"
                 f"{tuple(round(x, 7) for x in ob['fr_axis'])}".encode())
    from . import gcode
    h.update(repr(gcode.schedule(scene)).encode())
    h.update(repr([round(f, 6) for f in gcode.corners(scene)]).encode())
    wp = workpiece(scene)
    h.update(f"wp:{wp.name if wp else ''}:{s.detail}".encode())
    from . import air
    h.update(air.nozzle_signature(scene).encode())
    for ob in sorted(chain_objects(scene), key=lambda o: o.name):
        h.update(ob.name.encode())
        h.update((ob.parent.name if ob.parent else "").encode())
        h.update(_mat_bytes(ob.matrix_parent_inverse))
        fcs = _fcurves(ob)
        ad = ob.animation_data
        drivers = list(ad.drivers) if ad is not None else []
        for fc in fcs:
            _hash_fcurve(h, fc)
        for fc in drivers:
            dr = fc.driver
            h.update(f"drv:{fc.data_path}[{fc.array_index}]:{dr.type}:{dr.expression}".encode())
            for var in dr.variables:
                for tg in var.targets:
                    h.update(f"{var.name}:{var.type}:{getattr(tg.id, 'name', '')}:{tg.data_path}:"
                             f"{tg.transform_type}:{tg.transform_space}".encode())
        if not fcs and not drivers:
            h.update(_mat_bytes(ob.matrix_basis))
        for key in ("fr_value",):
            if key in ob and not any(fc.data_path == f'["{key}"]' for fc in fcs):
                h.update(f"{key}={round(float(ob[key]), 9)}".encode())
        for c in getattr(ob, "constraints", []):
            h.update(f"con:{c.type}:{c.mute}:{getattr(getattr(c, 'target', None), 'name', '')}".encode())
    return h.hexdigest()


def _pose(wi: Matrix, ob, tip, axis) -> tuple:
    m = wi @ ob.matrix_world
    o = m @ tip
    d = (m.to_3x3() @ axis)
    if d.length > 1e-12:
        d.normalize()
    return (o.x, o.y, o.z), (d.x, d.y, d.z)


def sample(scene, progress=None) -> int:
    """Read every bit's tip and axis relative to the workpiece at each frame (and between frames where
    a cutting move is curved). Stores the path on the bits. Returns the number of samples."""
    wp = workpiece(scene)
    items = bits(scene)
    if wp is None or not items:
        return 0
    s = settings(scene)
    f0, f1 = int(scene.frame_start), int(max(scene.frame_start, scene.frame_end))
    keep = (scene.frame_current, scene.frame_subframe)
    items = items + [(ob, ob) for ob in _copies(scene)]      # tool copies of a G-code program (task 0040)
    tips = [Vector(_tip_of(it)) for it, _o in items]
    axes = [Vector(_axis_of(it)).normalized() if Vector(_axis_of(it)).length > 1e-9 else Vector((0, 0, 1))
            for it, _o in items]
    for k, (it, ob) in enumerate(items):            # a bit the spindle turns: its tip on the spindle's axis (0049)
        if not isinstance(it, bpy.types.Object):
            tips[k], axes[k] = on_turning_axis(ob, tips[k], axes[k], scene)
    tools = [core.Cutter(_tool_any(it), "FAST") for it, _o in items]
    tol = core.detail(s.detail)["tol"]
    # the stock's box in its own space, to skip refining moves far away from it
    me = s.stock_mesh or wp.data
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) if len(co) else np.zeros((1, 3))
    lo, hi = co.min(axis=0), co.max(axis=0)
    from . import air
    nozzle = air.uses_nozzle(scene)
    air_o, air_d = [], []                           # the air nozzle in the world at every frame (task 0039)
    _STATE["guard"] += 1
    t0 = time.perf_counter()
    try:
        def read(t: float):
            f = math.floor(t + 1e-9)
            scene.frame_set(int(f), subframe=float(t - f))
            wi = wp.matrix_world.inverted()
            return [_pose(wi, ob, tip, ax) for (_it, ob), tip, ax in zip(items, tips, axes)]

        rows = [[] for _ in items]                  # per bit: (t, o, d)
        from . import gcode
        # the program's corners between frames: read there too, or the cut goes straight across them (task 0049)
        corner = sorted(t for t in gcode.corners(scene) if f0 < t < f1 and abs(t - round(t)) > 1e-4)
        ci = 0
        wp_m = []                                   # the workpiece in the world at every frame (chips, task 0028)
        prev, prev_t = None, float(f0)
        total = f1 - f0 + 1
        for n, f in enumerate(range(f0, f1 + 1)):
            while ci < len(corner) and corner[ci] < f:
                if prev is not None and corner[ci] > f - 1:
                    tc = corner[ci]
                    pc = read(tc)
                    extra = _refine(read, prev_t, tc, prev, pc, tools, tol, lo, hi, depth=0)
                    for t, poses in extra + [(tc, pc)]:
                        for b, (o, d) in enumerate(poses):
                            rows[b].append((t, o, d))
                    prev, prev_t = pc, tc
                ci += 1
            cur = read(float(f))
            wp_m.append([v for row in wp.matrix_world for v in row])
            if nozzle:
                o, d = air.nozzle_pose(scene)
                air_o.append(o)
                air_d.append(d)
            if prev is not None:
                extra = _refine(read, prev_t, float(f), prev, cur, tools, tol, lo, hi, depth=0)
                for t, poses in extra:
                    for b, (o, d) in enumerate(poses):
                        rows[b].append((t, o, d))
            for b, (o, d) in enumerate(cur):
                rows[b].append((float(f), o, d))
            prev, prev_t = cur, float(f)
            if progress is not None and n % 50 == 0:
                progress(n / total)
    finally:
        scene.frame_set(keep[0], subframe=keep[1])
        _STATE["guard"] -= 1
    count = 0
    for (item, _ob), r in zip(items, rows):          # (a copy is its own item: its path is kept on it)
        r.sort(key=lambda x: x[0])
        # never assign an array of another length over the old one: Blender 5.2.3 corrupts memory (task 0038)
        store_array(item, "fr_t", [x[0] for x in r])
        store_array(item, "fr_o", [x[1] for x in r])
        store_array(item, "fr_d", [x[2] for x in r])
        count += len(r)
    store_array(s, "fr_wp_m", wp_m)
    if nozzle:
        store_array(s, "fr_air_o", air_o)
        store_array(s, "fr_air_d", air_d)
    else:
        for k in ("fr_air_o", "fr_air_d"):
            if k in s:
                del s[k]
    s["fr_wp_f0"] = f0
    s.path_sig = signature(scene)
    rt = runtime(scene)
    rt["sample_s"] = time.perf_counter() - t0
    rt["timeline"] = None
    return count


def _refine(read, ta, tb, pa, pb, tools, tol, lo, hi, depth) -> list:
    """Extra samples between ``ta`` and ``tb`` where a bit near the stock moves on a curve."""
    need = False
    for (oa, da), (ob_, db), tool in zip(pa, pb, tools):
        oa, ob_, da, db = np.array(oa), np.array(ob_), np.array(da), np.array(db)
        reach = tool.reach + 1e-4
        top = np.maximum(oa, ob_) + np.abs(da) * tool.length
        bot = np.minimum(oa, ob_) - np.abs(da) * tool.length
        if np.any(top + reach < lo) or np.any(bot - reach > hi):
            continue
        if np.linalg.norm(ob_ - oa) > 0.25 * tool.reach or float(da @ db) < math.cos(math.radians(0.5)):
            need = True
            break
    if not need or depth >= 4:
        return []
    tm = 0.5 * (ta + tb)
    pm = read(tm)
    curved = False
    for (oa, da), (om, dm), (ob_, db) in zip(pa, pm, pb):
        mid = 0.5 * (np.array(oa) + np.array(ob_))
        if np.linalg.norm(np.array(om) - mid) > tol or float(np.array(da) @ np.array(dm)) < math.cos(core.ANGLE_TOL):
            curved = True
    if not curved:
        return []
    return (_refine(read, ta, tm, pa, pm, tools, tol, lo, hi, depth + 1) + [(tm, pm)]
            + _refine(read, tm, tb, pm, pb, tools, tol, lo, hi, depth + 1))


def _copies(scene) -> list:
    """The copies of the tools a G-code build made, when the part in the spindle is a bit (they cut while they are
    in the spindle, task 0040)."""
    from . import gcode
    if not gcode.schedule(scene):
        return []
    spindle = gcode.settings(scene).tool
    if spindle is None or not any(ob is spindle for _it, ob in bits(scene)):
        return []
    return [ob for _n, ob in sorted(_tool_copies(scene).items()) if _in_scene(scene, ob)]


def _tip_of(it):
    return tuple(it["fr_tip"]) if isinstance(it, bpy.types.Object) else tuple(it.tip)


def _axis_of(it):
    return tuple(it["fr_axis"]) if isinstance(it, bpy.types.Object) else tuple(it.axis)


def _tool_any(it) -> core.Tool:
    if isinstance(it, bpy.types.Object):
        spec = _spec_of_copy(it)
        from ..core import tools as tcore
        return tcore.cutting_tool(spec) if spec is not None else core.Tool("FLAT", radius=3e-3, length=0.03)
    return tool_of(it)


def _spec_of_copy(ob):
    from . import tools
    return tools.spec_from_json(ob.get("fr_spec", ""))


class CutItem:
    """One thing that cuts for a while: a bit, or a tool of a G-code program while it is in the spindle."""

    def __init__(self, name: str, ob, path: core.Path, tool: core.Tool, chip: str = "", spindle=None):
        self.name, self.ob, self.path, self.tool, self.chip = name, ob, path, tool, chip
        self.spindle = spindle            # the bit in the spindle this is a piece of (a G-code tool), else None

    def key(self) -> tuple:
        return (self.name, self.tool.key(), len(self.path.t), round(float(self.path.t[0]), 6),
                round(float(self.path.t[-1]), 6))


def cut_items(scene) -> list:
    """What cuts, and when. Without a G-code tool schedule: every bit along its whole path (as in task 0027). With
    one (a program with tool changes, task 0040): the part in the spindle is split up – while tool T is in the
    spindle, T's copy cuts with T's sizes (its tool list row); a row that is the spindle's own part cuts with that
    row's sizes."""
    from ..core import tools as tcore
    from . import gcode, tools
    sched = gcode.schedule(scene)
    spindle = gcode.settings(scene).tool
    cps = {n: ob for n, ob in _tool_copies(scene).items() if _in_scene(scene, ob)} if sched else {}
    out = []
    for it, ob in bits(scene):
        p = _path(it)
        if p is None:
            continue
        if not sched or ob is not spindle:
            out.append(CutItem(ob.name, ob, p, tool_of(it)))
            continue
        bounds, mounted = [-math.inf], [0]
        for f, n in sched:                        # one piece per stay in the spindle
            if n != mounted[-1]:
                bounds.append(f)
                mounted.append(n)
        bounds.append(math.inf)
        for k, n in enumerate(mounted):
            a, b = bounds[k], bounds[k + 1]
            if b <= a:
                continue
            src, spec = ob, None
            if n and n in cps:
                src = cps[n]
                spec = _spec_of_copy(src)
                path = _path(src)
            else:
                path = p
                row = gcode.tool_entry(scene, n) if n else None
                if row is not None and row.obj is spindle:
                    spec = tools.spec_of(row)
            if path is None:
                continue
            sel = (path.t >= a - 1e-9) & (path.t <= b + 1e-9)
            if not np.any(sel):
                continue
            sub = core.Path(path.t[sel], path.o[sel], path.d[sel])
            tool = tcore.cutting_tool(spec) if spec is not None else tool_of(it)
            chip = tcore.chip_kind(spec) if spec is not None else ""
            out.append(CutItem(f"{src.name}@{k}", src, sub, tool, chip, spindle=ob))
    return out


def _path(item) -> core.Path | None:
    if "fr_t" not in item or "fr_o" not in item or "fr_d" not in item:
        return None
    t = np.array(item["fr_t"], dtype=np.float64)
    if len(t) == 0:
        return None
    return core.Path(t, np.array(item["fr_o"], dtype=np.float64), np.array(item["fr_d"], dtype=np.float64))


# ---------------------------------------------------------------------------
# solids and the timeline
# ---------------------------------------------------------------------------

def _mesh_tris(me) -> tuple:
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    v = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", v)
    t = np.empty(n * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", t)
    p = np.empty(n, dtype=np.int32)
    me.loop_triangles.foreach_get("polygon_index", p)
    return v.reshape(-1, 3), t.reshape(-1, 3), p


def _cad_world(ob) -> Matrix:
    m = Matrix.Identity(4)
    chain = []
    p = ob
    while p is not None:
        chain.append(p)
        p = build.logical_parent(p)
    for c in reversed(chain):
        m = m @ build.cad_basis(c)
    return m


def _stock_key(s, wp) -> tuple:
    me = s.stock_mesh
    fin = s.finished
    rel = None
    if fin is not None and fin.type == "MESH":
        rel = tuple(round(v, 7) for row in (_cad_world(wp).inverted() @ _cad_world(fin)) for v in row)
    return (me.name if me else "", len(me.vertices) if me else 0, len(me.polygons) if me else 0,
            fin.data.name if fin is not None and fin.data else "", rel, s.detail)


def _workpiece_solid(scene):
    s = settings(scene)
    wp = workpiece(scene)
    rt = runtime(scene)
    key = _stock_key(s, wp)
    if rt.get("wp_key") == key and rt.get("wp") is not None:
        return rt["wp"]
    v, t, p = _mesh_tris(s.stock_mesh)
    stock = core.solid_from_mesh(v, t, p)
    fin_solid = None
    fin = s.finished
    if fin is not None and fin.type == "MESH" and fin.data is not None:
        fv, ft, _fp = _mesh_tris(fin.data)
        m = np.array(_cad_world(wp).inverted() @ _cad_world(fin))
        fv = fv.astype(np.float64) @ m[:3, :3].T + m[:3, 3]
        try:
            fin_solid = core.solid_from_mesh(fv, ft)
        except core.SolidError:
            fin_solid = None
            rt["note"] = "The finished part is not a closed solid: it is not used"
    wpc = core.Workpiece(stock, fin_solid, s.detail)
    mats = np.empty(len(s.stock_mesh.polygons), dtype=np.int32)
    s.stock_mesh.polygons.foreach_get("material_index", mats)
    rt["wp"], rt["wp_key"], rt["mats"] = wpc, key, mats
    return wpc


def _timeline(scene):
    """The timeline for the current set-up (made again when anything changed)."""
    s = settings(scene)
    rt = runtime(scene)
    items = cut_items(scene)
    key = (s.path_sig, _stock_key(s, workpiece(scene)), tuple(c.key() for c in items))
    if rt.get("key") == key and rt.get("timeline") is not None:
        return rt["timeline"]
    wpc = _workpiece_solid(scene)
    cutters, paths = [], []
    for c in items:
        cutters.append(core.Cutter(c.tool, s.detail))
        paths.append(c.path)
    tl = core.Timeline(wpc, cutters, paths, s.detail) if paths else None
    rt["timeline"], rt["key"], rt["shown"] = tl, key, None
    return tl


# ---------------------------------------------------------------------------
# showing a frame
# ---------------------------------------------------------------------------

def _write_mesh(me, v: np.ndarray, t: np.ndarray, mat: np.ndarray) -> None:
    me.clear_geometry()
    if len(t) == 0:
        me.update()
        return
    me.vertices.add(len(v))
    me.vertices.foreach_set("co", v.reshape(-1))
    me.loops.add(len(t) * 3)
    me.loops.foreach_set("vertex_index", t.reshape(-1))
    me.polygons.add(len(t))
    me.polygons.foreach_set("loop_start", np.arange(0, len(t) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("material_index", mat)
    me.update(calc_edges=True)
    me.shade_smooth()
    me.set_sharp_from_angle(angle=SHARP_ANGLE)


def _write_stock(cut, stock) -> None:
    v, t, p = _mesh_tris(stock)
    mats = np.empty(len(stock.polygons), dtype=np.int32)
    stock.polygons.foreach_get("material_index", mats)
    _write_mesh(cut, v, t, mats[p] if len(p) else np.zeros(0, np.int32))


def refresh(scene, frame: float | None = None, force: bool = False) -> bool:
    """Show the workpiece as it is at ``frame`` (default: the current frame). True when shown."""
    rt = runtime(scene)
    if not core.available() or not is_set_up(scene):
        return False
    s = settings(scene)
    if not s.enabled:
        return False
    wp = workpiece(scene)
    try:
        if not _ensure_own_mesh(scene, wp):
            rt["status"] = rt["error"] = "The workpiece lost its CAD shape: press 'Stop milling' and pick it again"
            return False
        T = float(scene.frame_current + scene.frame_subframe) if frame is None else float(frame)
        tl = _timeline(scene)
        if tl is None:
            rt["status"] = "Waiting for the motion to be read"
            return False
        if not force and rt.get("shown") == (id(tl), T):
            _cut_slot(scene, wp)                       # a look changed in 3 Looks shows at once
            return True
        v, t, src = tl.mesh_at(T)
        mats = rt.get("mats")
        mi = np.zeros(len(t), dtype=np.int32)
        mi[src < 0] = _cut_slot(scene, wp)             # faces the cutter made: their own look (task 0051)
        if mats is not None and len(mats):
            ok = (src >= 0) & (src < len(mats))
            mi[ok] = mats[src[ok]]
        _write_mesh(s.cut_mesh, v, t, mi)
        rt["shown"] = (id(tl), T)
        _show_chips(scene, T)
        st = tl.stats
        rt["status"] = (f"Frame {T:g}: {st.triangles:,} triangles, {st.last_ms:.0f} ms "
                        f"({st.cutting_segments} cutting moves)")
        rt.pop("error", None)
        return True
    except core.SolidError:
        rt["error"] = "The workpiece is not a closed solid in the CAD file, so it cannot be cut"
        rt["status"] = rt["error"]
        return False


def _show_chips(scene, T: float) -> None:
    """Chips (task 0028) at this frame; never stops the cut from showing."""
    from . import chips
    try:
        chips.show(scene, T)
    except Exception as exc:
        runtime(scene)["chips_error"] = str(exc)
        print("Fresing Render: chips failed:", exc)


def mark_stale(scene) -> None:
    """Something that moves the bits changed: read the path again (soon, in the 3D view)."""
    rt = runtime(scene)
    rt["timeline"] = None
    if bpy.app.background:
        return
    _schedule()


def _schedule(delay: float = 0.3) -> None:
    if _STATE["pending"]:
        return
    _STATE["pending"] = True
    bpy.app.timers.register(_check_timer, first_interval=delay)


def _check_timer():
    _STATE["pending"] = False
    try:
        for scene in bpy.data.scenes:
            if hasattr(scene, "fresing") and is_active(scene):
                update_if_needed(scene)
    except Exception as exc:                         # never break the app over a preview update
        print("Fresing Render: milling update failed:", exc)
    return None


def update_if_needed(scene, progress=None) -> bool:
    """Read the path again if the motion changed, then show the current frame."""
    s = settings(scene)
    if not is_active(scene):
        return False
    if s.path_sig != signature(scene) or any(_path(it) is None for it, _o in bits(scene)) or \
            any(_path(ob) is None for ob in _copies(scene)):
        wm = bpy.context.window_manager if not bpy.app.background else None
        if wm is not None:
            wm.progress_begin(0, 100)
        try:
            sample(scene, progress or ((lambda f: wm.progress_update(int(f * 100))) if wm else None))
        finally:
            if wm is not None:
                wm.progress_end()
    return refresh(scene)


def prepare(scene, progress=None) -> None:
    """Before rendering (the render queue): read the path for the animation as it is now."""
    if not is_active(scene):
        return
    if progress is not None:
        progress(0, "Milling: reading the motion of the bits")
    sample(scene)
    refresh(scene, force=True)


# ---------------------------------------------------------------------------
# model update
# ---------------------------------------------------------------------------

def before_model_update(scene) -> None:
    """The model is made again: the workpiece gets its CAD mesh back first (the set-up is kept by part IDs)."""
    wp = workpiece(scene)
    if wp is not None:
        _give_back(scene, wp)


def after_model_update(scene, mapping: dict, by_uid_new: dict) -> list[str]:
    """Point the set-up at the new revision's parts. Returns notes for the report."""
    s = settings(scene)
    notes = []
    _RUNTIME.pop(scene.name, None)

    def new(uid):
        if not uid:
            return None
        nu = mapping.get(uid, uid)
        return by_uid_new.get(uid) or next((o for o in scene.objects if o.get(build.PROP_UID) == nu), None)

    if s.workpiece_uid:
        ob = new(s.workpiece_uid)
        s.workpiece = ob
        if ob is None:
            notes.append("Milling: the workpiece is gone in the new revision (pick it again in 4 Motion > Milling)")
            s.workpiece_uid = ""
        else:
            s.workpiece_uid = ob.get(build.PROP_UID, "")
            if s.enabled:
                _take_workpiece(scene, ob)
    if s.finished_uid:
        ob = new(s.finished_uid)
        s.finished = ob
        s.finished_uid = ob.get(build.PROP_UID, "") if ob is not None else ""
        if ob is not None:
            from . import logic
            logic.set_hidden(ob, True)
            ob["fr_mill_hid"] = True
    for i in reversed(range(len(s.bits))):
        it = s.bits[i]
        ob = new(it.uid)
        if ob is None:
            notes.append("Milling: a bit is gone in the new revision")
            s.bits.remove(i)
            continue
        it.obj = ob
        it.uid = ob.get(build.PROP_UID, "")
        try:
            apply_detection(it, detect(ob, _world_centre(s.workpiece) if s.workpiece else None, it.flipped),
                            fill=it.shape == "AUTO")
        except RuntimeError:
            pass
    s.path_sig = ""
    mark_stale(scene)
    return notes


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------

def lock_interface(scene) -> None:
    """Renders started in the window lock the interface while milling is on (bug hunt 0045 row 13): Blender
    calls the frame handler on its render thread, and a cut written there must not meet the window drawing the
    same mesh. Set only on change (a set render setting stops a running viewport preview)."""
    r = scene.render
    if not r.use_lock_interface:
        r.use_lock_interface = True


def _off_main_thread() -> bool:
    return threading.current_thread() is not threading.main_thread()


def _in_window() -> bool:
    return not bpy.app.background


@persistent
def _on_frame(scene, _depsgraph=None):
    if _STATE["guard"] or scene is None or not hasattr(scene, "fresing"):
        return
    _FRAME.clear()
    _FRAME["in_scene"] = {}
    try:
        if not is_active(scene):
            return
        if _in_window() and _off_main_thread() and not scene.render.use_lock_interface:
            return                               # a render in the window that may draw this mesh meanwhile
        s = settings(scene)
        if s.path_sig != signature(scene):
            runtime(scene)["status"] = "The motion changed: reading it again"
            mark_stale(scene)                    # 3D view: read soon; the queue reads it before rendering
            if not bpy.app.background:
                return
        refresh(scene)
    except Exception as exc:
        print("Fresing Render: milling frame update failed:", exc)
    finally:
        _FRAME.clear()


@persistent
def _on_depsgraph(scene, depsgraph=None):
    if _STATE["guard"] or depsgraph is None or scene is None or not hasattr(scene, "fresing"):
        return
    try:
        if not is_active(scene):
            return
        names = runtime(scene).get("chain_names")
        if names is None:
            names = {o.name for o in chain_objects(scene)}
            runtime(scene)["chain_names"] = names
        for u in depsgraph.updates:
            idb = u.id
            if isinstance(idb, bpy.types.Action) or (
                    isinstance(idb, bpy.types.Object) and u.is_updated_transform and idb.name in names):
                runtime(scene).pop("chain_names", None)
                _schedule()
                return
    except Exception:
        pass


@persistent
def _on_load(_dummy=None):
    _RUNTIME.clear()
    from . import chips, gcode
    chips.forget()
    gcode.forget()                               # the G-code steps' summaries (task 0051)
    _STATE["pending"] = False
    if bpy.app.background:
        return
    try:
        active = [sc for sc in bpy.data.scenes if hasattr(sc, "fresing") and is_active(sc)]
        for sc in active:                        # projects milled before 0.2.40
            lock_interface(sc)
        if active:
            _schedule(0.5)
    except Exception:
        pass


def register():
    for lst, fn in ((bpy.app.handlers.frame_change_post, _on_frame),
                    (bpy.app.handlers.depsgraph_update_post, _on_depsgraph),
                    (bpy.app.handlers.load_post, _on_load)):
        if fn not in lst:
            lst.append(fn)


def unregister():
    for lst, fn in ((bpy.app.handlers.frame_change_post, _on_frame),
                    (bpy.app.handlers.depsgraph_update_post, _on_depsgraph),
                    (bpy.app.handlers.load_post, _on_load)):
        while fn in lst:
            lst.remove(fn)
    if bpy.app.timers.is_registered(_check_timer):
        bpy.app.timers.unregister(_check_timer)
    _STATE["pending"] = False
    _RUNTIME.clear()
    from . import chips
    chips.forget()
