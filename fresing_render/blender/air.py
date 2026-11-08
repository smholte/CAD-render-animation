"""Air blast in Blender (task 0039): the settings live in 4 Motion > CNC machine > Air blast.

* **When it blows**: each Run G-code program step, when the animation is built (``record``), adds the frames
  its program has air on (``core.gcode.Schedule.air_spans``) and its "Blow the part clean" frames to
  ``scene.fresing.cnc["fr_air"]`` (start, end, clean) – reset at every build (``prepare``).
* **Where from**: through the spindle, the air follows the milling bit's own path (read by
  ``machining.sample``); an external nozzle is a part with a tip and a direction in its own space, read at
  every frame along with the bits (``machining.sample`` stores ``fr_air_o`` / ``fr_air_d``).
* **What it does**: ``core/air.py`` and ``core/chips.py`` (the chips are worked out with the air).
* **Show air**: a faint cone ("FR air") on the tool or the nozzle, shown only while the air blows (visibility
  keys of the build).
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..core import air as core
from . import build
from .idprops import store_array

CONE_NAME = "FR air"
TAG = "fr_air"


def settings(scene):
    return scene.fresing.cnc


def strength(scene) -> float:
    return core.STRENGTHS.get(settings(scene).air_strength, core.STRENGTHS["NORMAL"])


# ---------------------------------------------------------------------------
# the nozzle
# ---------------------------------------------------------------------------

def _workpiece_centre(scene):
    from . import machining
    wp = machining.workpiece(scene) or settings(scene).workpiece
    if wp is None:
        return None
    return machining._world_centre(wp)


def detect_nozzle(ob, toward=None) -> tuple:
    """(tip, direction) of a nozzle part in its own space: the end of its long axis nearest ``toward`` (the
    workpiece), blowing out of that end. Parts without a clear axis blow from their middle towards ``toward``."""
    from . import machining
    try:
        info = machining.detect(ob, toward=toward)
        tip = Vector(info["tip"])
        d = -Vector(info["axis"])
        if d.length > 1e-9:
            return tip, d.normalized()
    except Exception:
        pass
    pts = machining._mesh_points(ob) if ob.data is not None and len(ob.data.vertices) else np.zeros((1, 3))
    c = Vector(pts.mean(axis=0))
    return c, _towards_local(ob, c, toward)


def _towards_local(ob, tip_local: Vector, toward) -> Vector:
    if toward is None:
        return Vector((0.0, 0.0, -1.0))
    mw = ob.matrix_world
    d_world = Vector(toward) - mw @ tip_local
    if d_world.length < 1e-9:
        return Vector((0.0, 0.0, -1.0))
    d = mw.to_3x3().inverted_safe() @ d_world.normalized()
    return d.normalized() if d.length > 1e-12 else Vector((0.0, 0.0, -1.0))


def use_nozzle(scene, ob, point_world=None) -> str:
    """The part ``ob`` is the nozzle; its tip from its shape, or the clicked ``point_world``. Returns a note."""
    c = settings(scene)
    toward = _workpiece_centre(scene)
    if point_world is not None:
        tip = ob.matrix_world.inverted_safe() @ Vector(point_world)
        d = _towards_local(ob, tip, toward)
        note = "tip at the clicked point, aimed at the workpiece"
    else:
        tip, d = detect_nozzle(ob, toward)
        note = "tip and direction read from its shape"
    c["_busy"] = True
    try:
        c.air_nozzle = ob
        c.air_nozzle_uid = ob.get(build.PROP_UID, "")
        c.air_tip = tuple(tip)
        c.air_dir = tuple(d)
        c.air_source = "NOZZLE"
    finally:
        del c["_busy"]
    settings_changed(scene)
    return note


def aim_at_workpiece(scene) -> bool:
    c = settings(scene)
    toward = _workpiece_centre(scene)
    if c.air_nozzle is None or toward is None:
        return False
    c["_busy"] = True
    try:
        c.air_dir = tuple(_towards_local(c.air_nozzle, Vector(c.air_tip), toward))
    finally:
        del c["_busy"]
    settings_changed(scene)
    return True


def flip(scene) -> None:
    c = settings(scene)
    c["_busy"] = True
    try:
        c.air_dir = tuple(-Vector(c.air_dir))
    finally:
        del c["_busy"]
    settings_changed(scene)


def uses_nozzle(scene) -> bool:
    c = settings(scene)
    return c.air_source == "NOZZLE" and c.air_nozzle is not None


def nozzle_pose(scene) -> tuple:
    """(tip, direction) of the external nozzle in the world now."""
    c = settings(scene)
    mw = c.air_nozzle.matrix_world
    d = mw.to_3x3() @ Vector(c.air_dir)
    if d.length > 1e-12:
        d.normalize()
    o = mw @ Vector(c.air_tip)
    return (o.x, o.y, o.z), (d.x, d.y, d.z)


def nozzle_signature(scene) -> str:
    """For the milling path's fingerprint: the nozzle is read with the bits."""
    if not uses_nozzle(scene):
        return ""
    c = settings(scene)
    return (f"air:{c.air_nozzle.name}:{tuple(round(x, 7) for x in c.air_tip)}:"
            f"{tuple(round(x, 7) for x in c.air_dir)}")


def problem(scene) -> str:
    c = settings(scene)
    if c.air_source == "NOZZLE" and c.air_nozzle is None:
        return "Pick the nozzle: click its part, press Use clicked part (or Click the nozzle point)"
    return ""


# ---------------------------------------------------------------------------
# when it blows (written by the build)
# ---------------------------------------------------------------------------

def spans(scene) -> np.ndarray:
    c = settings(scene)
    if "fr_air" not in c or len(c["fr_air"]) < 3:
        return np.zeros((0, 3))
    return np.array(c["fr_air"], dtype=np.float64).reshape(-1, 3)


def prepare(scene) -> None:
    """Before a build: no air until the steps say so; the cone made (or removed) as set."""
    c = settings(scene)
    if "fr_air" in c:
        del c["fr_air"]
    if c.air_show:
        try:
            cone(scene)
        except Exception as exc:                        # the air itself still works
            print("Fresing Render: the air cone could not be made:", exc)
    else:
        remove_cone()


def clear(scene) -> None:
    """'Clear keys': no air any more."""
    c = settings(scene)
    if "fr_air" in c:
        del c["fr_air"]


def step_spans(scene, sch, b) -> list:
    """[(start s, end s, clean)] of a step, from the step's start."""
    c = settings(scene)
    out = [(a, z, 0.0) for a, z in sch.air_spans(int(c.air_on_code), int(c.air_off_code), bool(c.air_always))]
    if sch.clean_span is not None:
        out.append((sch.clean_span[0], sch.clean_span[1], 1.0))
    return out


def record(scene, sch, b, f0: float, fps: float, vkeys: dict, merge) -> None:
    """A Run G-code program step was built: add its air frames (and the cone's visibility keys)."""
    rows = [(f0 + a * fps, f0 + z * fps, cl) for a, z, cl in step_spans(scene, sch, b) if z > a]
    if not rows:
        return
    c = settings(scene)
    old = spans(scene)
    store_array(c, "fr_air", np.concatenate([old, np.array(rows, dtype=np.float64)]).reshape(-1))
    ob = bpy.data.objects.get(CONE_NAME)
    if c.air_show and ob is not None and ob.name in scene.objects:
        keys = vkeys.setdefault(ob.name, [(1, True, "CONSTANT", "AUTO")])
        for a, z, _cl in rows:
            merge(keys, a, False, "CONSTANT")
            merge(keys, z, True, "CONSTANT")


def describe(scene, sch) -> str:
    """'Air: on 3 times, 12.4 s in all' for the step (video seconds)."""
    sp = step_spans(scene, sch, None)
    if not sp:
        return "Air: off (no air code in the program)"
    return "Air: " + core.spans_text(np.array(sp, dtype=float), 1.0)


def codes_text(scene) -> str:
    c = settings(scene)
    text = f"M{c.air_on_code} … M{c.air_off_code}"
    if c.air_always:
        text += ", and always while the spindle turns"
    return text


# ---------------------------------------------------------------------------
# for the chips
# ---------------------------------------------------------------------------

def key(scene) -> tuple:
    c = settings(scene)
    sp = spans(scene)
    if not len(sp):
        return ("no air",)
    from . import machining
    s = machining.settings(scene)
    return (c.air_source, c.air_nozzle.name if c.air_nozzle else "", tuple(round(x, 7) for x in c.air_tip),
            tuple(round(x, 7) for x in c.air_dir), c.air_strength, round(c.air_cone, 6), round(c.air_reach, 6),
            sp.round(4).tobytes(), len(s.get("fr_air_o", ())),
            c.tool.name if c.tool else "")


def inputs(scene, bits_in: list, bit_objects: list, carry, f0: int):
    """core.AirIn for the chips (riding space), or None without air."""
    c = settings(scene)
    sp = spans(scene)
    if not len(sp) or not bits_in:
        return None
    if c.air_source == "NOZZLE":
        from . import machining
        s = machining.settings(scene)
        if c.air_nozzle is None or "fr_air_o" not in s or "fr_air_d" not in s:
            return None
        wo = np.array(s["fr_air_o"], dtype=np.float64).reshape(-1, 3)
        wd = np.array(s["fr_air_d"], dtype=np.float64).reshape(-1, 3)
        n = min(len(wo), len(wd), len(carry) if carry is not None else len(wo))
        o, d = core.nozzle_from_poses(wo[:n], wd[:n], carry[:n] if carry is not None else None)
        t = f0 + np.arange(n, dtype=np.float64)
    else:
        k = 0
        if c.tool is not None and c.tool.name in bit_objects:
            k = bit_objects.index(c.tool.name)
        k = min(k, len(bits_in) - 1)
        b = bits_in[k]
        t, o, d = b.t, b.o, -b.d
    return core.AirIn(sp, t, o, d, speed=strength(scene), cone=float(c.air_cone), reach=float(c.air_reach))


def settings_changed(scene) -> None:
    """An air setting changed: the cone follows, the chips are worked out again."""
    c = settings(scene)
    if not c.air_show:
        remove_cone()
    elif bpy.data.objects.get(CONE_NAME) is not None:
        try:
            cone(scene)
        except Exception:
            pass
    from . import chips, gcode, machining
    try:                                               # the steps' "Air: …" line and clean moves follow
        gcode.setup_changed(scene)
    except Exception:
        pass
    if not machining.is_active(scene):
        return
    if uses_nozzle(scene):
        machining.mark_stale(scene)                    # the nozzle is read along with the bits
        if bpy.app.background:
            machining.prepare(scene)
    if chips.wanted(scene):
        chips.settings_changed(scene)


# ---------------------------------------------------------------------------
# "Show air": a faint cone
# ---------------------------------------------------------------------------

def _cone_mesh(length: float, angle: float, seg: int = 32) -> bpy.types.Mesh:
    r = length * math.tan(angle)
    r0 = 1.5 * core.MM
    verts = []
    for z, rr in ((0.0, r0), (-length, r)):                # an open funnel: the jet's sides only
        for i in range(seg):
            a = 2 * math.pi * i / seg
            verts.append((rr * math.cos(a), rr * math.sin(a), z))
    faces = [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
    me = bpy.data.meshes.new(CONE_NAME)
    me.from_pydata(verts, [], faces)
    me.update()
    me[TAG] = "cone"
    return me


def _cone_material() -> bpy.types.Material:
    mat = bpy.data.materials.get(CONE_NAME)
    if mat is not None and mat.get(TAG) == "cone":
        return mat
    mat = bpy.data.materials.new(CONE_NAME)
    mat[TAG] = "cone"
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.07
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.85, 0.92, 1.0, 1.0)
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    try:
        mat.surface_render_method = "BLENDED"
    except (AttributeError, TypeError):
        pass
    mat.diffuse_color = (0.85, 0.92, 1.0, 0.1)
    return mat


def cone(scene):
    """The cone for "Show air", on the tool (through the spindle) or the nozzle; hidden until the air blows."""
    c = settings(scene)
    if c.air_source == "NOZZLE":
        parent = c.air_nozzle
        if parent is None:
            remove_cone()
            return None
        tip, d = Vector(c.air_tip), Vector(c.air_dir)
    else:
        parent = c.tool
        if parent is None:
            remove_cone()
            return None
        from . import gcode
        frame = gcode.tool_frame(parent)
        tip, d = frame.translation.copy(), -(frame.to_3x3() @ Vector((0, 0, 1)))
    if d.length < 1e-12:
        d = Vector((0, 0, -1))
    length = float(c.air_reach) * 0.6
    me = _cone_mesh(length, float(c.air_cone))
    me.materials.append(_cone_material())
    ob = bpy.data.objects.get(CONE_NAME)
    if ob is None:
        ob = bpy.data.objects.new(CONE_NAME, me)
        ob[TAG] = "cone"
        ob[build.PROP_KIND] = "cnc"
        scene.collection.objects.link(ob)
    else:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
        if ob.name not in scene.objects:
            scene.collection.objects.link(ob)
    # in the parent's own space: apex at the tip, -Z along the way it blows
    rot = (-d.normalized()).to_track_quat("Z", "Y").to_matrix().to_4x4()
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Translation(tip) @ rot
    ob.hide_select = True
    ob.visible_shadow = False
    try:
        ob.visible_diffuse = ob.visible_glossy = ob.visible_transmission = False
    except AttributeError:
        pass
    if not scene.fresing.anim_baked:
        ob.hide_render = True
        ob.hide_viewport = True
    return ob


def remove_cone() -> None:
    ob = bpy.data.objects.get(CONE_NAME)
    if ob is not None and ob.get(TAG) == "cone":
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


# ---------------------------------------------------------------------------
# model update
# ---------------------------------------------------------------------------

def before_model_update(scene) -> None:
    remove_cone()


def after_model_update(scene, new) -> list:
    c = settings(scene)
    if not c.air_nozzle_uid:
        return []
    ob = new(c.air_nozzle_uid)
    c["_busy"] = True
    try:
        c.air_nozzle = ob
        c.air_nozzle_uid = ob.get(build.PROP_UID, "") if ob is not None else ""
    finally:
        del c["_busy"]
    if ob is None:
        return ["CNC machine: the air nozzle is gone in the new revision (pick it again in 4 Motion > CNC machine "
                "> Air blast)"]
    return []
