"""The user guide's picture of the tool library (docs/img/tools.jpg, task 0040): every tool type drawn from its
default sizes, with a holder on some, rendered with Cycles on the processor.

usage: ~/venv/bin/python tools/make_tool_picture.py [out.jpg]   (Blender as a Python module; ImageMagick for jpg)
"""

import math
import os
import subprocess
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fresing_render.core import tools as tcore  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs",
                                                         "img", "tools.jpg")
HOLDERS = {"FLAT": "ER", "BALL": "NONE", "BULL": "NONE", "VEE": "NONE", "DRILL": "NONE", "FACE": "SK40",
           "THREAD": "NONE", "SLOT": "NONE"}


def material(name, rgb, metal, rough):
    m = bpy.data.materials.new(name)
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    return m


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    steel = material("Carbide", (0.62, 0.63, 0.66), 1.0, 0.28)
    dark = material("Holder", (0.16, 0.17, 0.18), 1.0, 0.38)
    x = 0.0
    for kind in tcore.KINDS:
        s = tcore.default(kind)
        s.holder = HOLDERS[kind]
        s = tcore.resolved(s)
        v, t, part = tcore.tool_mesh(s, seg=64)
        me = bpy.data.meshes.new(kind)
        me.from_pydata(v.tolist(), [], t.tolist())
        me.polygons.foreach_set("material_index", part.tolist())
        me.materials.append(steel)
        me.materials.append(dark)
        me.update()
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(35))
        ob = bpy.data.objects.new(kind, me)
        sc.collection.objects.link(ob)
        w = max(s.diameter, s.holder_diameter if s.holder != "NONE" else 0.0, 0.0635 if s.holder in ("SK40", "BT40", "HSK63") else 0)
        x += w / 2 + 0.012
        ob.location = (x, 0.0, 0.0)
        x += w / 2 + 0.012
    # floor, light, camera
    bpy.ops.mesh.primitive_plane_add(size=4.0, location=(x / 2, 0, -0.0005))
    bpy.context.object.data.materials.append(material("Floor", (0.8, 0.8, 0.82), 0.0, 0.6))
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.85, 0.86, 0.88, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
    for loc, energy, size in (((x * 0.2, -0.5, 0.45), 14.0, 0.5), ((x * 0.95, -0.35, 0.3), 5.0, 0.3),
                              ((x / 2, 0.45, 0.35), 9.0, 0.6)):
        ld = bpy.data.lights.new("L", "AREA")
        ld.energy, ld.size = energy, size
        lo = bpy.data.objects.new("L", ld)
        lo.location = loc
        lo.rotation_euler = (Vector((x / 2, 0, 0.05)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(lo)
    cd = bpy.data.cameras.new("C")
    cd.lens = 70
    cam = bpy.data.objects.new("C", cd)
    sc.collection.objects.link(cam)
    target = Vector((x / 2, 0, 0.045))
    cam.location = target + Vector((0.0, -1.0, 0.2)) * (x / 0.45)
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1400, 520
    sc.view_settings.view_transform = "AgX"
    png = os.path.splitext(OUT)[0] + ".png"
    sc.render.filepath = png
    bpy.ops.render.render(write_still=True)
    subprocess.run(["convert", png, "-quality", "86", OUT], check=True)
    os.remove(png)
    print("written", OUT)


main()
