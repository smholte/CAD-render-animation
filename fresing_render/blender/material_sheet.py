"""Material sheet (task 0046): every library material on the same three shapes, in one picture.

A block with a chamfer, a short turned disc and a round shaft per material, in rows, in a scene of
its own ("FR material sheet"), lit by the app's own studio light. Used by ``tools/material_sheet.py``
(before/after pictures, Cycles and EEVEE) and by the PC check line ``looks.materials``.
The shapes are meshed coarsely, like STEP parts (no UV maps, sharp edges, long thin triangles)."""

from __future__ import annotations

import math
import os
import time

import bmesh
import bpy

from ..core import materials_lib

SCENE = "FR material sheet"
TILE = 0.30          # metres between two materials
COLUMNS = 6
# a colour for the materials that take one, so the sheet shows them in a typical colour
SHEET_COLOURS = {"paint_gloss": "RAL 3020", "paint_satin": "RAL 5010", "paint_matte": "RAL 7016",
                 "powder_coat": "RAL 9005", "paint_marine": "RAL 1003", "wire_mesh": "RAL 9005",
                 "aluminium_anodized_color": "#3A5A8C", "plastic_gloss": "RAL 3020", "plastic_matte": "RAL 9005",
                 "glass_tinted": "RAL 7016", "emission_light": "RAL 9010", "cast_iron_painted": "RAL 6011"}


def _block(name: str) -> bpy.types.Mesh:
    """80 x 50 x 40 mm with a 6 mm chamfer round its top."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 0.080
        v.co.y *= 0.050
        v.co.z = (v.co.z + 0.5) * 0.040
    top = [e for e in bm.edges if all(v.co.z > 0.039 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=top, offset=0.006, segments=1, affect="EDGES")
    return _mesh(bm, name)


def _cylinder(name: str, radius: float, length: float, segments: int, along_x: bool) -> bpy.types.Mesh:
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=radius, radius2=radius,
                          depth=length)
    for v in bm.verts:
        if along_x:
            v.co.x, v.co.z = v.co.z, v.co.x + radius
        else:
            v.co.z += length / 2
    bm.normal_update()
    return _mesh(bm, name, 0 if along_x else 2)


def _mesh(bm, name: str, smooth_axis: int = -1) -> bpy.types.Mesh:
    """Flat faces flat, the round side of a cylinder smooth (``smooth_axis``: the cylinder's axis)."""
    for f in bm.faces:
        f.smooth = smooth_axis >= 0 and abs(f.normal[smooth_axis]) < 0.1
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _label(scene, coll, text: str, x: float, y: float):
    cu = bpy.data.curves.new("FR sheet label", "FONT")
    cu.body = text
    cu.size = 0.018
    cu.align_x = "CENTER"
    ob = bpy.data.objects.new("FR sheet label", cu)
    ob.location = (x, y, 0.0005)
    coll.objects.link(ob)
    mat = bpy.data.materials.get("FR sheet label") or bpy.data.materials.new("FR sheet label")
    mat.diffuse_color = (0.02, 0.02, 0.02, 1)
    try:
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
    except Exception:
        pass
    cu.materials.append(mat)


def build(ids=None, columns: int = COLUMNS, wear: float = 0.0):
    """Make (or remake) the sheet scene with ``ids`` (default: every library material), every material with
    ``wear`` (0 = new). Returns it."""
    from . import materials
    ids = list(ids or materials_lib.MATERIALS)
    old = bpy.data.scenes.get(SCENE)
    if old is not None:
        for ob in list(old.collection.all_objects):
            bpy.data.objects.remove(ob)
        bpy.data.scenes.remove(old)
    scene = bpy.data.scenes.new(SCENE)
    scene.unit_settings.system = "METRIC"
    coll = scene.collection
    shapes = {"block": _block("FR sheet block"),
              "disc": _cylinder("FR sheet disc", 0.032, 0.026, 40, False),
              "shaft": _cylinder("FR sheet shaft", 0.011, 0.150, 24, True)}
    for me in shapes.values():
        me.materials.append(None)
        if hasattr(materials, "part_axes"):
            materials.part_axes(me)
    rows = (len(ids) + columns - 1) // columns
    for i, mid in enumerate(ids):
        cx = (i % columns - (columns - 1) / 2) * TILE
        cy = ((rows - 1) / 2 - i // columns) * TILE
        mat = bpy.data.materials.get("FR sheet " + mid) or bpy.data.materials.new("FR sheet " + mid)
        try:
            mat.use_nodes = True
        except Exception:
            pass
        if wear:
            materials.build_nodes(mat, mid, SHEET_COLOURS.get(mid, ""), wear)
        else:
            materials.build_nodes(mat, mid, SHEET_COLOURS.get(mid, ""))
        for key, (dx, dy) in (("block", (-0.06, 0.05)), ("disc", (0.075, 0.055)), ("shaft", (0.03, -0.045))):
            ob = bpy.data.objects.new(f"FR sheet {mid} {key}", shapes[key])
            ob.location = (cx + dx, cy + dy, 0.0)
            if key == "shaft":
                ob.location.x -= 0.075
                ob.rotation_euler.z = math.radians(-8)
            elif key == "block":
                ob.rotation_euler.z = math.radians(28)
            else:                                           # the disc leans back towards the camera
                ob.rotation_euler.x = math.radians(-28)
                ob.location.z += 0.016
            ob.material_slots[0].link = "OBJECT"
            ob.material_slots[0].material = mat
            coll.objects.link(ob)
        _label(scene, coll, materials_lib.get(mid)["label"][:30], cx, cy - 0.115)
    # floor and camera
    w, h = columns * TILE, rows * TILE
    me = bpy.data.meshes.new("FR sheet floor")
    me.from_pydata([(-w, -h, 0), (w, -h, 0), (w, h, 0), (-w, h, 0)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new("FR sheet floor", me)
    fm = bpy.data.materials.get("FR sheet floor") or bpy.data.materials.new("FR sheet floor")
    try:
        fm.use_nodes = True
        b = fm.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (0.55, 0.55, 0.56, 1)
        b.inputs["Roughness"].default_value = 0.6
    except Exception:
        pass
    me.materials.append(fm)
    coll.objects.link(floor)
    cam_data = bpy.data.cameras.new("FR sheet camera")
    cam_data.type = "ORTHO"                      # every row the same size, however many rows
    cam_data.ortho_scale = w
    cam_data.sensor_fit = "HORIZONTAL"           # the scale is the width, also for a tall sheet
    cam = bpy.data.objects.new("FR sheet camera", cam_data)
    tilt = math.radians(35)
    cam.rotation_euler = (tilt, 0.0, 0.0)
    cam.location = (0.0, -3.0 * math.sin(tilt) - 0.03, 3.0 * math.cos(tilt))
    coll.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x = 1600
    scene.render.resolution_y = int(1600 * (h * math.cos(tilt) + 0.07) / w)
    scene.render.resolution_percentage = 100
    _light(scene)
    return scene


def _light(scene) -> None:
    """The app's studio light (product look), with a plain background."""
    from . import world
    s = scene.fresing
    s.background = "COLOR"
    s.floor = "NONE"
    try:
        world.apply(scene, s)
    except Exception as exc:
        print("Fresing Render: material sheet light:", exc)
    scene.render.film_transparent = False


def render(scene, path: str, engine: str = "CYCLES", samples: int = 32, width: int = 0,
           use_gpu: bool = False) -> dict:
    """Render the sheet to ``path`` (PNG, 8 bit) with the app's own colour settings (AgX), Cycles on the
    processor or the graphics card, or EEVEE. Returns {"seconds", "device", "size"}."""
    from . import render as fr_render
    device = fr_render.apply_quality(scene, "preview", use_gpu)
    r = scene.render
    r.resolution_percentage = 100
    if width:
        r.resolution_y = int(r.resolution_y * width / r.resolution_x)
        r.resolution_x = width
    if engine == "EEVEE":
        r.engine = "BLENDER_EEVEE"
        device = "EEVEE"
        try:
            scene.eevee.taa_render_samples = samples
        except Exception:
            pass
    else:
        scene.cycles.samples = samples
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    r.filepath = path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    t0 = time.time()
    bpy.ops.render.render(write_still=True, scene=scene.name)
    return {"seconds": round(time.time() - t0, 2), "device": device, "size": (r.resolution_x, r.resolution_y)}


def remove() -> None:
    """Delete the sheet scene and everything only it used."""
    scene = bpy.data.scenes.get(SCENE)
    if scene is None:
        return
    for ob in list(scene.collection.all_objects):
        data = ob.data
        bpy.data.objects.remove(ob)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
            elif isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)
    bpy.data.scenes.remove(scene)
    for mat in list(bpy.data.materials):
        if mat.name.startswith("FR sheet") and mat.users == 0:
            bpy.data.materials.remove(mat)
